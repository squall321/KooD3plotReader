/**
 * @file RadiossReader.cpp
 * @brief Implementation of OpenRadioss animation file reader
 *
 * Rewritten based on anim_to_vtk.cpp from OpenRadioss source.
 * Handles big-endian (default OpenRadioss) and little-endian files.
 *
 * Format (FASTMAGI10 = 0x542c):
 *   A001: magic + time + texts + flags[10] + 2D geom + 3D geom + 1D geom + hierarchy + TH + SPH
 *   A002...: state data (vectors + scalars + tensors per section)
 */

#include "kood3plot/converter/RadiossReader.h"
#include <fstream>
#include <cstring>
#include <filesystem>
#include <algorithm>
#include <iostream>
#include <vector>

namespace kood3plot {
namespace converter {

// ============================================================
// Constructor / Destructor
// ============================================================

RadiossReader::RadiossReader(const std::string& a00_filepath)
    : a00_path_(a00_filepath)
{
    // Strip trailing digits to get base: "tube_crushA001" → "tube_crushA"
    size_t pos = a00_filepath.size();
    while (pos > 0 && a00_filepath[pos - 1] >= '0' && a00_filepath[pos - 1] <= '9') {
        --pos;
    }
    base_path_ = (pos > 0) ? a00_filepath.substr(0, pos) : (a00_filepath + "_");
}

RadiossReader::~RadiossReader() {
    close();
}

// ============================================================
// Endian helpers
// ============================================================

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

// ============================================================
// Binary reading helpers
// ============================================================

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

std::string RadiossReader::readString(size_t length) {
    std::vector<char> buffer(length + 1, 0);
    file_.read(buffer.data(), length);
    // Trim trailing spaces and nulls
    size_t actual_len = length;
    while (actual_len > 0 && (buffer[actual_len - 1] == '\0' || buffer[actual_len - 1] == ' ')) {
        --actual_len;
    }
    return std::string(buffer.data(), actual_len);
}

// Skip N bytes
void RadiossReader::skipBytes(size_t n) {
    file_.seekg(n, std::ios::cur);
}

void RadiossReader::skipBytesFrom(std::ifstream& f, size_t n) {
    f.seekg(n, std::ios::cur);
}

// Read and discard (with endian swap)
void RadiossReader::skipInts(size_t count) {
    for (size_t i = 0; i < count; ++i) readBinary<int32_t>();
}

void RadiossReader::skipFloats(size_t count) {
    file_.seekg(count * sizeof(float), std::ios::cur);
}

// ============================================================
// Open
// ============================================================

ErrorCode RadiossReader::open() {
    last_error_.clear();

    file_.open(a00_path_, std::ios::binary);
    if (!file_) {
        last_error_ = "Cannot open file: " + a00_path_;
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
    if (file_.is_open()) file_.close();
}

// ============================================================
// Parse header (magic + time + texts + flags + counts)
// ============================================================

ErrorCode RadiossReader::parseHeader() {
    // 1. Magic number — auto-detect endianness
    int32_t magic;
    file_.read(reinterpret_cast<char*>(&magic), sizeof(int32_t));

    if (magic >= 0x5426 && magic <= 0x542c) {
        need_swap_ = false;
    } else {
        swapBytes(&magic, sizeof(int32_t));
        if (magic >= 0x5426 && magic <= 0x542c) {
            need_swap_ = true;
        } else {
            last_error_ = "Invalid magic number (neither endian matched)";
            return ErrorCode::INVALID_FORMAT;
        }
    }

    // 2. Time
    readBinary<float>();  // initial time (usually 0)

    // 3. Three text strings (81 bytes each): Time=, Title, RadiossRun=
    readString(81);  // "Time=..."
    header_.title = readString(81);  // model title
    readString(81);  // "Radioss Run=..."

    // 4. Ten flags (matching anim_to_vtk.cpp flagA[0..9])
    for (int i = 0; i < 10; ++i) {
        flags_[i] = readBinary<int32_t>();
    }

    // 5. 2D geometry counts
    nbNodes_ = readBinary<int32_t>();
    nbFacets_ = readBinary<int32_t>();
    nbParts2D_ = readBinary<int32_t>();
    nbFunc_ = readBinary<int32_t>();     // nodal scalars
    nbEFunc_ = readBinary<int32_t>();    // element scalars
    nbVect_ = readBinary<int32_t>();     // nodal vectors (vel/disp/acc)
    nbTens_ = readBinary<int32_t>();     // element tensors (stress)
    nbSkew_ = readBinary<int32_t>();     // skew systems

    // Set header counts
    header_.num_nodes = nbNodes_;
    header_.num_shells = nbFacets_;
    header_.num_solids = 0;
    header_.num_beams = 0;
    header_.num_states = 0;
    header_.word_size = 4;

    // Variable flags from counts
    header_.has_velocity = (nbVect_ >= 1);
    header_.has_displacement = (nbVect_ >= 2);
    header_.has_acceleration = (nbVect_ >= 3);
    header_.has_stress = (nbTens_ > 0);
    header_.has_strain = false;
    header_.has_plastic_strain = (nbEFunc_ > 0);

    return ErrorCode::SUCCESS;
}

// ============================================================
// Parse geometry — follows exact anim_to_vtk.cpp order
// ============================================================

ErrorCode RadiossReader::parseGeometry() {
    // ── Skew systems ──
    if (nbSkew_ > 0) {
        // uint16_t * 6 * nbSkew (we skip)
        skipBytes(nbSkew_ * 6 * sizeof(uint16_t));
    }

    // ── Node coordinates (3 * nbNodes floats) ──
    mesh_.nodes.resize(nbNodes_);
    for (int32_t i = 0; i < nbNodes_; ++i) {
        float x = readBinary<float>();
        float y = readBinary<float>();
        float z = readBinary<float>();
        mesh_.nodes[i] = {i + 1, x, y, z};
    }

    // ── 2D element connectivity (4 * nbFacets ints) ──
    if (nbFacets_ > 0) {
        mesh_.shells.resize(nbFacets_);
        for (int32_t i = 0; i < nbFacets_; ++i) {
            Element elem;
            elem.id = i + 1;
            elem.type = ElementType::SHELL;
            for (int j = 0; j < 4; ++j) {
                int32_t nid = readBinary<int32_t>();
                elem.node_ids.push_back(nid + 1);  // 0-based → 1-based
            }
            mesh_.shells[i] = std::move(elem);
        }

        // Deleted elements (1 byte per facet)
        skipBytes(nbFacets_);

        // Part definition (nbParts2D ints — cumulative element count per part)
        if (nbParts2D_ > 0) {
            std::vector<int32_t> partDef(nbParts2D_);
            for (int32_t i = 0; i < nbParts2D_; ++i) {
                partDef[i] = readBinary<int32_t>();
            }

            // Convert cumulative to per-element part IDs
            mesh_.shell_parts.resize(nbFacets_, 1);
            int32_t prev = 0;
            for (int32_t p = 0; p < nbParts2D_; ++p) {
                for (int32_t e = prev; e < partDef[p] && e < nbFacets_; ++e) {
                    mesh_.shell_parts[e] = p + 1;
                }
                prev = partDef[p];
            }

            // Part names (50 chars each)
            for (int32_t i = 0; i < nbParts2D_; ++i) {
                readString(50);
            }
        }
    }

    // ── 2D section continued: normals, scalars, vectors, tensors ──
    // These are based on nbNodes (not nbFacets) so must be read even if nbFacets==0

    // Normals (uint16_t * 3 * nbNodes)
    skipBytes(static_cast<size_t>(nbNodes_) * 3 * sizeof(uint16_t));

    // Scalar names + data
    if (nbFunc_ + nbEFunc_ > 0) {
        for (int32_t i = 0; i < nbFunc_ + nbEFunc_; ++i) readString(81);
        if (nbFunc_ > 0) skipFloats(static_cast<size_t>(nbNodes_) * nbFunc_);
        if (nbEFunc_ > 0) skipFloats(static_cast<size_t>(nbFacets_) * nbEFunc_);
    }

    // Vector names (always present if nbVect > 0)
    if (nbVect_ > 0) {
        for (int32_t i = 0; i < nbVect_; ++i) readString(81);
    }
    // Vector values (always written: 3 * nbNodes * nbVect)
    skipFloats(3ULL * nbNodes_ * nbVect_);

    // Tensor names + data
    if (nbTens_ > 0) {
        for (int32_t i = 0; i < nbTens_; ++i) readString(81);
        skipFloats(static_cast<size_t>(nbFacets_) * 3 * nbTens_);
    }

    // Mass
    if (flags_[0] == 1) {
        if (nbFacets_ > 0) skipFloats(nbFacets_);
        skipFloats(nbNodes_);
    }

    // Node/element numbering
    if (flags_[1] == 1) {
        skipBytes(static_cast<size_t>(nbNodes_) * sizeof(int32_t));
        if (nbFacets_ > 0) skipBytes(static_cast<size_t>(nbFacets_) * sizeof(int32_t));
    }

    // Hierarchy for 2D parts
    if (flags_[4] && nbParts2D_ > 0) {
        skipBytes(static_cast<size_t>(nbParts2D_) * sizeof(int32_t) * 3);
    }

    // ── 3D geometry (if flagA[2]) ──
    if (flags_[2]) {
        int32_t nbElts3D = readBinary<int32_t>();
        int32_t nbParts3D = readBinary<int32_t>();
        int32_t nbEFunc3D = readBinary<int32_t>();
        int32_t nbTens3D = readBinary<int32_t>();

        header_.num_solids = nbElts3D;

        // 3D connectivity (8 * nbElts3D ints)
        if (nbElts3D > 0) {
            mesh_.solids.resize(nbElts3D);
            for (int32_t i = 0; i < nbElts3D; ++i) {
                Element elem;
                elem.id = i + 1;
                elem.type = ElementType::SOLID;
                for (int j = 0; j < 8; ++j) {
                    int32_t nid = readBinary<int32_t>();
                    elem.node_ids.push_back(nid + 1);
                }
                mesh_.solids[i] = std::move(elem);
            }

            // Deleted 3D elements
            skipBytes(nbElts3D);

            // 3D part definition
            if (nbParts3D > 0) {
                std::vector<int32_t> partDef(nbParts3D);
                for (int32_t i = 0; i < nbParts3D; ++i) {
                    partDef[i] = readBinary<int32_t>();
                }

                mesh_.solid_parts.resize(nbElts3D, 1);
                int32_t prev = 0;
                for (int32_t p = 0; p < nbParts3D; ++p) {
                    for (int32_t e = prev; e < partDef[p] && e < nbElts3D; ++e) {
                        mesh_.solid_parts[e] = nbParts2D_ + p + 1;  // offset by 2D parts
                    }
                    prev = partDef[p];
                }

                for (int32_t i = 0; i < nbParts3D; ++i) readString(50);
            }

            // 3D scalar names + data
            if (nbEFunc3D > 0) {
                for (int32_t i = 0; i < nbEFunc3D; ++i) readString(81);
                skipFloats(nbEFunc3D * nbElts3D);
            }

            // 3D tensor names + data
            if (nbTens3D > 0) {
                for (int32_t i = 0; i < nbTens3D; ++i) readString(81);
                skipFloats(nbElts3D * 6 * nbTens3D);
            }

            // 3D mass
            if (flags_[0] == 1) skipFloats(nbElts3D);

            // 3D numbering
            if (flags_[1] == 1) skipBytes(nbElts3D * sizeof(int32_t));

            // 3D hierarchy
            if (flags_[4]) skipBytes(nbParts3D * sizeof(int32_t) * 3);
        }
    }

    // ── 1D geometry (if flagA[3]) ──
    if (flags_[3]) {
        int32_t nbElts1D = readBinary<int32_t>();
        int32_t nbParts1D = readBinary<int32_t>();
        int32_t nbEFunc1D = readBinary<int32_t>();
        int32_t nbTors1D = readBinary<int32_t>();
        int32_t isSkew1D = readBinary<int32_t>();

        header_.num_beams = nbElts1D;

        if (nbElts1D > 0) {
            mesh_.beams.resize(nbElts1D);
            for (int32_t i = 0; i < nbElts1D; ++i) {
                Element elem;
                elem.id = i + 1;
                elem.type = ElementType::BEAM;
                for (int j = 0; j < 2; ++j) {
                    int32_t nid = readBinary<int32_t>();
                    elem.node_ids.push_back(nid + 1);
                }
                mesh_.beams[i] = std::move(elem);
            }

            // Deleted 1D, parts, names (skip for now)
            skipBytes(nbElts1D);  // deleted
            if (nbParts1D > 0) {
                skipBytes(nbParts1D * sizeof(int32_t));  // part def
                for (int32_t i = 0; i < nbParts1D; ++i) readString(50);
            }
            if (nbEFunc1D > 0) {
                for (int32_t i = 0; i < nbEFunc1D; ++i) readString(81);
                skipFloats(nbElts1D * nbEFunc1D);
            }
            if (nbTors1D > 0) {
                for (int32_t i = 0; i < nbTors1D; ++i) readString(81);
                skipFloats(nbElts1D * 9 * nbTors1D);
            }
            if (isSkew1D) skipBytes(nbElts1D * sizeof(int32_t));
            if (flags_[0] == 1) skipFloats(nbElts1D);
            if (flags_[1] == 1) skipBytes(nbElts1D * sizeof(int32_t));
            if (flags_[4]) skipBytes(nbParts1D * sizeof(int32_t) * 3);
        }
    }

    // Remaining sections (hierarchy, TH, SPH) — skip
    // These are read in anim_to_vtk but not needed for d3plot conversion

    return ErrorCode::SUCCESS;
}

// ============================================================
// State file parsing
// ============================================================

std::vector<RadiossState> RadiossReader::readAllStates(size_t max_states) {
    std::vector<RadiossState> states;

    // State files start from index 2 when A001 is geometry
    size_t state_index = 2;
    if (a00_path_.find("A000") != std::string::npos ||
        a00_path_.find("a000") != std::string::npos) {
        state_index = 1;
    }
    size_t count = 0;

    while (stateFileExists(state_index)) {
        if (max_states > 0 && count >= max_states) break;

        RadiossState state;
        std::string filepath = getStateFilePath(state_index);

        if (parseStateFile(filepath, state) == ErrorCode::SUCCESS) {
            states.push_back(std::move(state));
            count++;
        } else {
            break;
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

ErrorCode RadiossReader::parseStateFile(const std::string& filepath, RadiossState& state) {
    // Each state file is a FULL animation file (magic + time + texts + flags + data)
    // Same structure as A001, but with updated coordinates and field values

    std::ifstream sf(filepath, std::ios::binary);
    if (!sf) {
        last_error_ = "Cannot open state file: " + filepath;
        return ErrorCode::IO_ERROR;
    }

    // ── Header (same as geometry file) ──
    int32_t magic;
    sf.read(reinterpret_cast<char*>(&magic), sizeof(int32_t));
    if (need_swap_) swapBytes(&magic, sizeof(int32_t));

    state.time = readBinaryFrom<float>(sf);

    // Skip 3 texts (81 bytes each)
    sf.seekg(81 * 3, std::ios::cur);

    // Skip 10 flags
    sf.seekg(10 * sizeof(int32_t), std::ios::cur);

    // Read 2D section counts (must match geometry file)
    int32_t sNbNodes = readBinaryFrom<int32_t>(sf);
    int32_t sNbFacets = readBinaryFrom<int32_t>(sf);
    int32_t sNbParts = readBinaryFrom<int32_t>(sf);
    int32_t sNbFunc = readBinaryFrom<int32_t>(sf);
    int32_t sNbEFunc = readBinaryFrom<int32_t>(sf);
    int32_t sNbVect = readBinaryFrom<int32_t>(sf);
    int32_t sNbTens = readBinaryFrom<int32_t>(sf);
    int32_t sNbSkew = readBinaryFrom<int32_t>(sf);

    // Skew data
    if (sNbSkew > 0) {
        sf.seekg(sNbSkew * 6 * sizeof(uint16_t), std::ios::cur);
    }

    // ── Node coordinates (current deformed position) ──
    // Compute displacement = current_pos - initial_pos
    size_t vec_size = static_cast<size_t>(sNbNodes) * 3;
    state.node_displacements.resize(vec_size, 0.0);
    for (int32_t i = 0; i < sNbNodes; ++i) {
        float x = readBinaryFrom<float>(sf);
        float y = readBinaryFrom<float>(sf);
        float z = readBinaryFrom<float>(sf);
        if (static_cast<size_t>(i) < mesh_.nodes.size()) {
            state.node_displacements[i * 3 + 0] = x - mesh_.nodes[i].x;
            state.node_displacements[i * 3 + 1] = y - mesh_.nodes[i].y;
            state.node_displacements[i * 3 + 2] = z - mesh_.nodes[i].z;
        }
    }

    // ── 2D element connectivity (skip — same as geometry) ──
    if (sNbFacets > 0) {
        sf.seekg(sNbFacets * 4 * sizeof(int32_t), std::ios::cur);  // connectivity
        sf.seekg(sNbFacets, std::ios::cur);  // deleted elements
    }
    if (sNbParts > 0) {
        sf.seekg(sNbParts * sizeof(int32_t), std::ios::cur);  // part def
        sf.seekg(sNbParts * 50, std::ios::cur);  // part names
    }

    // Normals
    sf.seekg(static_cast<size_t>(sNbNodes) * 3 * sizeof(uint16_t), std::ios::cur);

    // Scalars
    if (sNbFunc + sNbEFunc > 0) {
        sf.seekg((sNbFunc + sNbEFunc) * 81, std::ios::cur);  // names
        if (sNbFunc > 0) sf.seekg(static_cast<size_t>(sNbNodes) * sNbFunc * sizeof(float), std::ios::cur);
        if (sNbEFunc > 0) {
            // Element scalars — could be plastic strain
            state.plastic_strain.resize(sNbFacets);
            for (int32_t i = 0; i < sNbFacets; ++i) {
                state.plastic_strain[i] = readBinaryFrom<float>(sf);
            }
        }
    }

    // Vectors (velocity, displacement, acceleration) — read names then data
    if (sNbVect > 0) {
        sf.seekg(sNbVect * 81, std::ios::cur);  // vector names
    }
    // Vector data: 3 * nbNodes per vector
    if (sNbVect >= 1) {
        state.node_velocities.resize(vec_size);
        for (size_t i = 0; i < vec_size; ++i) {
            state.node_velocities[i] = readBinaryFrom<float>(sf);
        }
    }
    // Vector 2 is displacement — but we already computed from coordinates, skip
    if (sNbVect >= 2) {
        sf.seekg(vec_size * sizeof(float), std::ios::cur);
    }
    if (sNbVect >= 3) {
        state.node_accelerations.resize(vec_size);
        for (size_t i = 0; i < vec_size; ++i) {
            state.node_accelerations[i] = readBinaryFrom<float>(sf);
        }
    }

    // 2D Tensors (shell stress)
    if (sNbTens > 0 && sNbFacets > 0) {
        sf.seekg(sNbTens * 81, std::ios::cur);  // tensor names
        state.shell_stress.resize(sNbFacets * 6, 0.0);
        for (int32_t t = 0; t < sNbTens; ++t) {
            for (int32_t i = 0; i < sNbFacets; ++i) {
                float sxx = readBinaryFrom<float>(sf);
                float syy = readBinaryFrom<float>(sf);
                float sxy = readBinaryFrom<float>(sf);
                if (t == 0) {
                    state.shell_stress[i * 6 + 0] = sxx;
                    state.shell_stress[i * 6 + 1] = syy;
                    state.shell_stress[i * 6 + 3] = sxy;
                }
            }
        }
    } else if (sNbTens > 0) {
        sf.seekg(sNbTens * 81, std::ios::cur);  // tensor names only
    }

    // Mass, numbering, hierarchy for 2D (skip)
    if (flags_[0] == 1) {
        if (sNbFacets > 0) sf.seekg(sNbFacets * sizeof(float), std::ios::cur);
        sf.seekg(sNbNodes * sizeof(float), std::ios::cur);
    }
    if (flags_[1] == 1) {
        sf.seekg(sNbNodes * sizeof(int32_t), std::ios::cur);
        if (sNbFacets > 0) sf.seekg(sNbFacets * sizeof(int32_t), std::ios::cur);
    }
    if (flags_[4] && sNbParts > 0) {
        sf.seekg(sNbParts * sizeof(int32_t) * 3, std::ios::cur);
    }

    // ── 3D section ──
    if (flags_[2]) {
        int32_t nbE3D = readBinaryFrom<int32_t>(sf);
        int32_t nbP3D = readBinaryFrom<int32_t>(sf);
        int32_t nbEF3D = readBinaryFrom<int32_t>(sf);
        int32_t nbT3D = readBinaryFrom<int32_t>(sf);

        if (nbE3D > 0) {
            sf.seekg(nbE3D * 8 * sizeof(int32_t), std::ios::cur);  // connectivity
            sf.seekg(nbE3D, std::ios::cur);  // deleted
        }
        if (nbP3D > 0) {
            sf.seekg(nbP3D * sizeof(int32_t), std::ios::cur);  // part def
            sf.seekg(nbP3D * 50, std::ios::cur);  // names
        }

        // 3D element scalars
        if (nbEF3D > 0 && nbE3D > 0) {
            sf.seekg(nbEF3D * 81, std::ios::cur);  // names
            sf.seekg(static_cast<size_t>(nbEF3D) * nbE3D * sizeof(float), std::ios::cur);
        }

        // 3D tensors (solid stress: 6 components)
        if (nbT3D > 0 && nbE3D > 0) {
            sf.seekg(nbT3D * 81, std::ios::cur);  // names
            state.solid_stress.resize(nbE3D * 6, 0.0);
            for (int32_t t = 0; t < nbT3D; ++t) {
                for (int32_t i = 0; i < nbE3D; ++i) {
                    float sxx = readBinaryFrom<float>(sf);
                    float syy = readBinaryFrom<float>(sf);
                    float szz = readBinaryFrom<float>(sf);
                    float sxy = readBinaryFrom<float>(sf);
                    float syz = readBinaryFrom<float>(sf);
                    float szx = readBinaryFrom<float>(sf);
                    if (t == 0) {
                        size_t base = i * 6;
                        state.solid_stress[base + 0] = sxx;
                        state.solid_stress[base + 1] = syy;
                        state.solid_stress[base + 2] = szz;
                        state.solid_stress[base + 3] = sxy;
                        state.solid_stress[base + 4] = syz;
                        state.solid_stress[base + 5] = szx;
                    }
                }
            }
        }
    }

    sf.close();
    return ErrorCode::SUCCESS;
}

// ============================================================
// File path helpers
// ============================================================

std::string RadiossReader::getStateFilePath(size_t state_index) const {
    char buf[16];
    snprintf(buf, sizeof(buf), "%03zu", state_index);
    return base_path_ + buf;
}

bool RadiossReader::stateFileExists(size_t state_index) const {
    return std::filesystem::exists(getStateFilePath(state_index));
}

} // namespace converter
} // namespace kood3plot
