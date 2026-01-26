/**
 * @file RadiossWriter.cpp
 * @brief Implementation of OpenRadioss animation file writer
 * @author KooD3plot V2 Development Team
 * @date 2026-01-25
 * @version 2.0.0
 *
 * Writes OpenRadioss A00/A01/A02... animation files.
 * Format based on reverse engineering of OpenRadioss genani.F source code.
 */

#include "kood3plot/converter/RadiossWriter.h"
#include <cstring>
#include <filesystem>
#include <iostream>

namespace kood3plot {
namespace converter {

RadiossWriter::RadiossWriter(const std::string& base_path)
    : base_path_(base_path)
{
    // A00 path: base_path + "0" (e.g., "output/A0" -> "output/A00")
    a00_path_ = base_path_ + "0";
}

RadiossWriter::~RadiossWriter() {
    if (file_.is_open()) {
        file_.close();
    }
}

void RadiossWriter::setOptions(const RadiossWriterOptions& options) {
    options_ = options;
}

ErrorCode RadiossWriter::writeHeader(const RadiossHeader& header, const RadiossMesh& mesh) {
    last_error_.clear();
    bytes_written_ = 0;
    header_ = header;

    // Create output directory if needed
    std::filesystem::path path(a00_path_);
    if (path.has_parent_path()) {
        std::filesystem::create_directories(path.parent_path());
    }

    file_.open(a00_path_, std::ios::binary);
    if (!file_) {
        last_error_ = "Cannot create A00 file: " + a00_path_;
        return ErrorCode::IO_ERROR;
    }

    // 1. Magic number (int32): 21548 (0x542b)
    writeBinary<int32_t>(21548);

    // 2. Time (float32): 0.0 for header file
    writeBinary<float>(0.0f);

    // 3. Text strings (81 bytes each, null-padded)
    writeString("Time=", 81);
    writeString(options_.title.empty() ? header.title : options_.title, 81);
    writeString("Radioss Run=", 81);

    // 4. Animation mode (int32)
    writeBinary<int32_t>(0);  // Normal mode

    // 5. Additional flag (int32)
    writeBinary<int32_t>(1);

    // 6. Element type flags (from genani.F)
    int32_t has_3d = (header.num_solids > 0) ? 1 : 0;
    int32_t has_shells = (header.num_shells > 0) ? 1 : 0;
    int32_t has_1d = (header.num_beams > 0) ? 1 : 0;

    writeBinary<int32_t>(has_3d || has_shells);  // Has 3D/2D elements
    writeBinary<int32_t>(has_1d);                 // Has 1D elements
    writeBinary<int32_t>(1);                      // Hierarchy flag (always 1)
    writeBinary<int32_t>(0);                      // TH flag (always 0)
    writeBinary<int32_t>(1);                      // Shell reference frame
    writeBinary<int32_t>(0);                      // SPH flag
    writeBinary<int32_t>(1);                      // Version >= 47 flag
    writeBinary<int32_t>(0);                      // Reserved

    // 7. Counts
    int32_t num_nodes = static_cast<int32_t>(mesh.nodes.size());
    int32_t num_2d_elems = header.num_shells;
    int32_t num_3d_elems = header.num_solids;
    int32_t num_parts = 1;  // Simplified: single part

    // Calculate variable counts
    int32_t nv_ani = 0;  // Nodal vector count
    if (options_.write_velocity) nv_ani = 1;
    if (options_.write_displacement) nv_ani = 2;
    if (options_.write_acceleration) nv_ani = 3;

    int32_t nn_ani = 0;  // Nodal scalar count
    int32_t nce_ani = options_.write_plastic_strain ? 1 : 0;  // Element scalar count
    int32_t nct_ani = options_.write_stress ? 1 : 0;  // Element tensor count
    int32_t nskew = 0;   // No skew systems

    writeBinary<int32_t>(num_nodes);
    writeBinary<int32_t>(num_2d_elems);
    writeBinary<int32_t>(num_3d_elems);  // NBV: number of 3D elements (solids)
    writeBinary<int32_t>(num_parts);
    writeBinary<int32_t>(nn_ani);
    writeBinary<int32_t>(nce_ani);
    writeBinary<int32_t>(nv_ani);
    writeBinary<int32_t>(nct_ani);
    writeBinary<int32_t>(nskew);

    // 8. Node coordinates (X, Y, Z as float32)
    for (const auto& node : mesh.nodes) {
        writeBinary<float>(static_cast<float>(node.x));
        writeBinary<float>(static_cast<float>(node.y));
        writeBinary<float>(static_cast<float>(node.z));
    }

    // 9a. Shell element connectivity (4-node quads)
    for (const auto& elem : mesh.shells) {
        for (size_t j = 0; j < 4 && j < elem.node_ids.size(); ++j) {
            writeBinary<int32_t>(elem.node_ids[j]);
        }
        // Pad with zeros if less than 4 nodes
        for (size_t j = elem.node_ids.size(); j < 4; ++j) {
            writeBinary<int32_t>(0);
        }
    }

    // 9b. Solid element connectivity (8-node hexahedra)
    for (const auto& elem : mesh.solids) {
        for (size_t j = 0; j < 8 && j < elem.node_ids.size(); ++j) {
            writeBinary<int32_t>(elem.node_ids[j]);
        }
        // Pad with zeros if less than 8 nodes
        for (size_t j = elem.node_ids.size(); j < 8; ++j) {
            writeBinary<int32_t>(0);
        }
    }

    // 10a. Shell part IDs (one int32 per element)
    for (size_t i = 0; i < mesh.shells.size(); ++i) {
        int32_t part_id = (i < mesh.shell_parts.size()) ? mesh.shell_parts[i] : 1;
        writeBinary<int32_t>(part_id);
    }

    // 10b. Solid part IDs (one int32 per element)
    for (size_t i = 0; i < mesh.solids.size(); ++i) {
        int32_t part_id = (i < mesh.solid_parts.size()) ? mesh.solid_parts[i] : 1;
        writeBinary<int32_t>(part_id);
    }

    // 11. Variable names (81-byte text strings)
    if (options_.write_velocity) {
        writeString("Velocity", 81);
    }
    if (options_.write_displacement) {
        writeString("Displacement", 81);
    }
    if (options_.write_acceleration) {
        writeString("Acceleration", 81);
    }
    if (options_.write_plastic_strain) {
        writeString("Plastic Strain", 81);
    }
    if (options_.write_stress) {
        writeString("Stress", 81);
    }

    file_.close();

    if (options_.verbose) {
        std::cout << "[RadiossWriter] Wrote A00: " << a00_path_ << "\n";
        std::cout << "  Nodes: " << num_nodes << "\n";
        std::cout << "  Shells: " << num_2d_elems << "\n";
        std::cout << "  Solids: " << num_3d_elems << "\n";
        std::cout << "  Bytes: " << bytes_written_ << "\n";
    }

    return ErrorCode::SUCCESS;
}

ErrorCode RadiossWriter::writeState(size_t state_index, const RadiossState& state) {
    std::string filepath = getStateFilePath(state_index);

    file_.open(filepath, std::ios::binary);
    if (!file_) {
        last_error_ = "Cannot create state file: " + filepath;
        return ErrorCode::IO_ERROR;
    }

    // 1. Time (float32)
    writeBinary<float>(static_cast<float>(state.time));

    // 2. Nodal vectors (in order: velocity, displacement, acceleration)
    if (options_.write_velocity && !state.node_velocities.empty()) {
        for (size_t i = 0; i < state.node_velocities.size(); ++i) {
            writeBinary<float>(static_cast<float>(state.node_velocities[i]));
        }
    }

    if (options_.write_displacement && !state.node_displacements.empty()) {
        for (size_t i = 0; i < state.node_displacements.size(); ++i) {
            writeBinary<float>(static_cast<float>(state.node_displacements[i]));
        }
    }

    if (options_.write_acceleration && !state.node_accelerations.empty()) {
        for (size_t i = 0; i < state.node_accelerations.size(); ++i) {
            writeBinary<float>(static_cast<float>(state.node_accelerations[i]));
        }
    }

    // 3. Element scalars (plastic strain)
    if (options_.write_plastic_strain && !state.plastic_strain.empty()) {
        for (size_t i = 0; i < state.plastic_strain.size(); ++i) {
            writeBinary<float>(static_cast<float>(state.plastic_strain[i]));
        }
    }

    // 4a. Shell stress tensors (6 components Voigt)
    if (options_.write_stress && !state.shell_stress.empty()) {
        for (size_t i = 0; i < state.shell_stress.size(); ++i) {
            writeBinary<float>(static_cast<float>(state.shell_stress[i]));
        }
    }

    // 4b. Solid stress tensors (6 components Voigt)
    if (options_.write_stress && !state.solid_stress.empty()) {
        for (size_t i = 0; i < state.solid_stress.size(); ++i) {
            writeBinary<float>(static_cast<float>(state.solid_stress[i]));
        }
    }

    file_.close();

    if (options_.verbose) {
        std::cout << "[RadiossWriter] Wrote state " << state_index
                  << ": " << filepath << " (t=" << state.time << ")\n";
    }

    return ErrorCode::SUCCESS;
}

ErrorCode RadiossWriter::writeAllStates(const std::vector<RadiossState>& states) {
    for (size_t i = 0; i < states.size(); ++i) {
        auto err = writeState(i + 1, states[i]);  // A01, A02, ...
        if (err != ErrorCode::SUCCESS) {
            return err;
        }
    }
    return ErrorCode::SUCCESS;
}

std::string RadiossWriter::getStateFilePath(size_t state_index) const {
    // Format: A01, A02, ..., A09, A10, ..., A99, A100, etc.
    std::string index_str;
    if (state_index < 10) {
        index_str = "0" + std::to_string(state_index);
    } else {
        index_str = std::to_string(state_index);
    }
    return base_path_ + index_str;
}

template<typename T>
void RadiossWriter::writeBinary(T value) {
    file_.write(reinterpret_cast<const char*>(&value), sizeof(T));
    bytes_written_ += sizeof(T);
}

void RadiossWriter::writeBinaryArray(const void* data, size_t size) {
    file_.write(reinterpret_cast<const char*>(data), size);
    bytes_written_ += size;
}

void RadiossWriter::writeString(const std::string& str, size_t length) {
    std::vector<char> buffer(length, '\0');
    size_t copy_len = std::min(str.size(), length - 1);
    std::memcpy(buffer.data(), str.c_str(), copy_len);
    file_.write(buffer.data(), length);
    bytes_written_ += length;
}

} // namespace converter
} // namespace kood3plot
