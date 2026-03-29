/**
 * @file RadiossReader.cpp
 * @brief Implementation of OpenRadioss animation file (A00/A01) reader
 * @author KooD3plot V2 Development Team
 * @date 2026-01-24
 * @version 2.0.0
 *
 * Based on reverse engineering of OpenRadioss genani.F source code
 *
 * File structure (from genani.F analysis):
 * A00 File:
 * - MAGIC (int32): 21548 (0x542b)
 * - Time (float32)
 * - Text strings: "Time=", title (81 bytes each, null-padded)
 * - ANIM_M (int32): animation mode
 * - Flags (9 x int32): has_3d, has_1d, hierarchy, th, shell_ref, sph, vers, reserved, reserved
 * - NUMNOD (int32): number of nodes
 * - NBF (int32): number of 2D elements (shells)
 * - NBPART (int32): number of parts
 * - NN_ANI (int32): number of nodal scalar variables
 * - NCE_ANI (int32): number of element scalar variables
 * - NV_ANI (int32): number of nodal vector variables (1=vel, 2=disp, 3=acc)
 * - NCT_ANI (int32): number of element tensor variables
 * - NSKEW (int32): number of skew systems
 * - Skew systems data (if NSKEW > 0)
 * - Node coordinates: NUMNOD * 3 float32 (X, Y, Z)
 * - Element connectivity: depends on element types
 * - Part IDs: one int32 per element
 * - Variable names: 81-byte text strings
 *
 * A01, A02, ... State files:
 * - Time (float32)
 * - Nodal vectors (if NV_ANI > 0): velocity, displacement, acceleration
 * - Nodal scalars (if NN_ANI > 0)
 * - Element scalars (if NCE_ANI > 0)
 * - Element tensors (if NCT_ANI > 0)
 */

#include "kood3plot/converter/RadiossReader.h"
#include <fstream>
#include <cstring>
#include <filesystem>
#include <algorithm>

namespace kood3plot {
namespace converter {

RadiossReader::RadiossReader(const std::string& a00_filepath)
    : a00_path_(a00_filepath)
{
    // Extract base path: strip trailing digits to get the stem before index
    // e.g., "tube_crushA001" → "tube_crushA"
    //        "simA000"       → "simA"
    size_t pos = a00_filepath.size();
    while (pos > 0 && a00_filepath[pos - 1] >= '0' && a00_filepath[pos - 1] <= '9') {
        --pos;
    }
    if (pos > 0) {
        base_path_ = a00_filepath.substr(0, pos);
    } else {
        base_path_ = a00_filepath + "_";
    }
}

RadiossReader::~RadiossReader() {
    close();
}

ErrorCode RadiossReader::open() {
    last_error_.clear();

    file_.open(a00_path_, std::ios::binary);
    if (!file_) {
        last_error_ = "Cannot open A00 file: " + a00_path_;
        return ErrorCode::IO_ERROR;
    }

    auto err = parseHeader();
    if (err != ErrorCode::SUCCESS) {
        file_.close();
        return err;
    }

    err = parseGeometry();
    if (err != ErrorCode::SUCCESS) {
        file_.close();
        return err;
    }

    file_.close();
    return ErrorCode::SUCCESS;
}

void RadiossReader::close() {
    if (file_.is_open()) {
        file_.close();
    }
}

std::vector<RadiossState> RadiossReader::readAllStates(size_t max_states) {
    std::vector<RadiossState> states;

    // A001 = geometry (header), state files start from A002
    // Detect: if A001 was used as geometry, start from index 2
    size_t state_index = 2;
    // But if separate A000 was used, states start from A001
    if (a00_path_.find("A000") != std::string::npos ||
        a00_path_.find("a000") != std::string::npos) {
        state_index = 1;
    }
    size_t count = 0;

    while (stateFileExists(state_index)) {
        if (max_states > 0 && count >= max_states) {
            break;
        }

        RadiossState state;
        std::string filepath = getStateFilePath(state_index);

        if (parseStateFile(filepath, state) == ErrorCode::SUCCESS) {
            states.push_back(state);
            count++;
        } else {
            break;  // Stop on first error
        }

        state_index++;
    }

    return states;
}

RadiossState RadiossReader::readState(size_t state_index) {
    RadiossState state;
    std::string filepath = getStateFilePath(state_index);
    parseStateFile(filepath, state);
    return state;
}

std::string RadiossReader::readString(size_t length) {
    std::vector<char> buffer(length);
    file_.read(buffer.data(), length);

    // Remove null padding
    size_t actual_len = 0;
    for (size_t i = 0; i < length; ++i) {
        if (buffer[i] == '\0') break;
        actual_len = i + 1;
    }

    return std::string(buffer.data(), actual_len);
}

void RadiossReader::swapBytes(void* data, size_t size) {
    auto* bytes = reinterpret_cast<uint8_t*>(data);
    for (size_t i = 0; i < size / 2; ++i) {
        std::swap(bytes[i], bytes[size - 1 - i]);
    }
}

void RadiossReader::swapArray(void* data, size_t elem_size, size_t count) {
    auto* bytes = reinterpret_cast<uint8_t*>(data);
    for (size_t i = 0; i < count; ++i) {
        swapBytes(bytes + i * elem_size, elem_size);
    }
}

ErrorCode RadiossReader::parseHeader() {
    // 1. Read magic number (4 bytes int32) — auto-detect endianness
    int32_t magic;
    file_.read(reinterpret_cast<char*>(&magic), sizeof(int32_t));

    // Valid magic numbers: 0x5426..0x542c (versions 4..10)
    if (magic >= 0x5426 && magic <= 0x542c) {
        need_swap_ = false;
    } else {
        // Try byte-swapped
        swapBytes(&magic, sizeof(int32_t));
        if (magic >= 0x5426 && magic <= 0x542c) {
            need_swap_ = true;
        } else {
            last_error_ = "Invalid magic number (neither endian matched)";
            return ErrorCode::INVALID_FORMAT;
        }
    }

    // Word size: Radioss uses float32 by default
    header_.word_size = 4;

    // 2. Read time value (float32)
    float time = readBinary<float>();

    // 3. Read text strings (from ANI_TXT calls in genani.F)
    // - "Time=" or "Frequency=" (81 bytes)
    std::string time_label = readString(81);

    // - Title (81 bytes)
    header_.title = readString(81);

    // - "Radioss Run=" (81 bytes)
    std::string run_label = readString(81);

    // 4. Read animation mode flag
    int32_t anim_mode = readBinary<int32_t>();

    // 5. Read additional flag
    int32_t flag1 = readBinary<int32_t>();

    // 6. Read element type flags (from genani.F lines 1145-1180)
    int32_t has_3d = readBinary<int32_t>();      // Has solids/shells/SPH
    int32_t has_1d = readBinary<int32_t>();      // Has beams/trusses
    int32_t hierarchy = readBinary<int32_t>();    // Hierarchy flag (always 1)
    int32_t th_flag = readBinary<int32_t>();      // Time history flag (always 0)
    int32_t shell_ref = readBinary<int32_t>();    // Shell reference frame
    int32_t sph_flag = readBinary<int32_t>();     // SPH flag
    int32_t vers_flag = readBinary<int32_t>();    // Version >= 47 flag
    int32_t reserved = readBinary<int32_t>();     // Reserved (always 0)

    // 7. Read counts (from genani.F lines 1186-1214)
    header_.num_nodes = readBinary<int32_t>();
    int32_t num_2d_elems = readBinary<int32_t>();  // NBF: shells + other 2D
    int32_t num_3d_elems = readBinary<int32_t>();  // NBV: solids (8-node hexahedra)
    int32_t num_parts = readBinary<int32_t>();
    int32_t nn_ani = readBinary<int32_t>();        // Number of nodal scalar variables
    int32_t nce_ani = readBinary<int32_t>();       // Number of element scalar variables
    int32_t nv_ani = readBinary<int32_t>();        // Number of nodal vector variables
    int32_t nct_ani = readBinary<int32_t>();       // Number of element tensor variables
    int32_t nskew = readBinary<int32_t>();         // Number of skew systems

    // Parse variable flags from counts
    header_.has_velocity = (nv_ani >= 1);
    header_.has_displacement = (nv_ani >= 2);
    header_.has_acceleration = (nv_ani >= 3);
    header_.has_stress = (nct_ani > 0);
    header_.has_strain = false;  // Would need more detailed parsing
    header_.has_plastic_strain = (nce_ani > 0);

    // Element counts - now properly read from file
    header_.num_shells = num_2d_elems;
    header_.num_solids = num_3d_elems;
    header_.num_beams = (has_1d > 0) ? 100 : 0;  // Still rough estimate for beams
    header_.num_states = 0;  // Unknown until we scan files

    // Skip skew systems data (6 floats * nskew)
    if (nskew > 0) {
        file_.seekg(nskew * 6 * sizeof(float), std::ios::cur);
    }

    return ErrorCode::SUCCESS;
}

ErrorCode RadiossReader::parseGeometry() {
    // Node coordinates are stored after header
    // Format: X, Y, Z as float32 for each node (from xyznod.F)

    mesh_.nodes.resize(header_.num_nodes);

    for (int32_t i = 0; i < header_.num_nodes; ++i) {
        float x = readBinary<float>();
        float y = readBinary<float>();
        float z = readBinary<float>();

        Node node;
        node.id = i + 1;  // 1-based indexing
        node.x = x;
        node.y = y;
        node.z = z;

        mesh_.nodes[i] = node;
    }

    // Element connectivity follows node coordinates
    // Format: shells (4-node quads), then solids (8-node hexahedra)

    // Read shell elements (4-node quads)
    if (header_.num_shells > 0) {
        mesh_.shells.resize(header_.num_shells);

        for (int32_t i = 0; i < header_.num_shells; ++i) {
            Element elem;
            elem.id = i + 1;
            elem.type = ElementType::SHELL;

            // Read 4 node IDs for quad element
            for (int j = 0; j < 4; ++j) {
                int32_t node_id = readBinary<int32_t>();
                elem.node_ids.push_back(node_id);
            }

            mesh_.shells[i] = elem;
        }
    }

    // Read solid elements (8-node hexahedra)
    if (header_.num_solids > 0) {
        mesh_.solids.resize(header_.num_solids);

        for (int32_t i = 0; i < header_.num_solids; ++i) {
            Element elem;
            elem.id = i + 1;
            elem.type = ElementType::SOLID;

            // Read 8 node IDs for hexahedron element
            for (int j = 0; j < 8; ++j) {
                int32_t node_id = readBinary<int32_t>();
                elem.node_ids.push_back(node_id);
            }

            mesh_.solids[i] = elem;
        }
    }

    // Read shell part IDs (one int32 per shell element)
    if (header_.num_shells > 0) {
        mesh_.shell_parts.resize(header_.num_shells);
        for (int32_t i = 0; i < header_.num_shells; ++i) {
            mesh_.shell_parts[i] = readBinary<int32_t>();
        }
    }

    // Read solid part IDs (one int32 per solid element)
    if (header_.num_solids > 0) {
        mesh_.solid_parts.resize(header_.num_solids);
        for (int32_t i = 0; i < header_.num_solids; ++i) {
            mesh_.solid_parts[i] = readBinary<int32_t>();
        }
    }

    return ErrorCode::SUCCESS;
}

ErrorCode RadiossReader::parseStateFile(const std::string& filepath, RadiossState& state) {
    std::ifstream state_file(filepath, std::ios::binary);
    if (!state_file) {
        last_error_ = "Cannot open state file: " + filepath;
        return ErrorCode::IO_ERROR;
    }

    // State files start with time value (float32)
    state.time = readBinaryFrom<float>(state_file);

    // Read nodal vectors in order (from genani.F VELVEC calls):
    // 1. Velocity (if ANIM_V(1)==1)
    // 2. Displacement (if ANIM_V(2)==1)
    // 3. Acceleration (if ANIM_V(3)==1)

    size_t vector_size = header_.num_nodes * 3;

    if (header_.has_velocity) {
        state.node_velocities.resize(vector_size);
        for (size_t i = 0; i < vector_size; ++i) {
            state.node_velocities[i] = readBinaryFrom<float>(state_file);
        }
    }

    if (header_.has_displacement) {
        state.node_displacements.resize(vector_size);
        for (size_t i = 0; i < vector_size; ++i) {
            state.node_displacements[i] = readBinaryFrom<float>(state_file);
        }
    }

    if (header_.has_acceleration) {
        state.node_accelerations.resize(vector_size);
        for (size_t i = 0; i < vector_size; ++i) {
            state.node_accelerations[i] = readBinaryFrom<float>(state_file);
        }
    }

    // Read element data (stress, strain, etc.) if present
    // This would require more detailed parsing based on header flags
    // For now, basic implementation

    if (header_.has_plastic_strain && header_.num_shells > 0) {
        state.plastic_strain.resize(header_.num_shells);
        for (int32_t i = 0; i < header_.num_shells; ++i) {
            state.plastic_strain[i] = readBinaryFrom<float>(state_file);
        }
    }

    if (header_.has_stress && header_.num_shells > 0) {
        size_t stress_size = header_.num_shells * 6;
        state.shell_stress.resize(stress_size);
        for (size_t i = 0; i < stress_size; ++i) {
            state.shell_stress[i] = readBinaryFrom<float>(state_file);
        }
    }

    if (header_.has_stress && header_.num_solids > 0) {
        size_t stress_size = header_.num_solids * 6;
        state.solid_stress.resize(stress_size);
        for (size_t i = 0; i < stress_size; ++i) {
            state.solid_stress[i] = readBinaryFrom<float>(state_file);
        }
    }

    state_file.close();
    return ErrorCode::SUCCESS;
}

std::string RadiossReader::getStateFilePath(size_t state_index) const {
    // Format: A001, A002, ..., A099, A100, etc. (3-digit zero-padded)
    char buf[16];
    snprintf(buf, sizeof(buf), "%03zu", state_index);
    return base_path_ + buf;
}

bool RadiossReader::stateFileExists(size_t state_index) const {
    std::string filepath = getStateFilePath(state_index);
    return std::filesystem::exists(filepath);
}

template<typename T>
T RadiossReader::readBinary() {
    T value;
    file_.read(reinterpret_cast<char*>(&value), sizeof(T));
    if (need_swap_) swapBytes(&value, sizeof(T));
    return value;
}

template<typename T>
T RadiossReader::readBinaryFrom(std::ifstream& f) {
    T value;
    f.read(reinterpret_cast<char*>(&value), sizeof(T));
    if (need_swap_) swapBytes(&value, sizeof(T));
    return value;
}

void RadiossReader::readBinaryArray(void* data, size_t size) {
    file_.read(reinterpret_cast<char*>(data), size);
}

} // namespace converter
} // namespace kood3plot
