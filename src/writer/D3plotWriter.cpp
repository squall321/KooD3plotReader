/**
 * @file D3plotWriter.cpp
 * @brief Implementation of D3plotWriter class
 */

#include "kood3plot/writer/D3plotWriter.h"
#include <iostream>
#include <iomanip>
#include <cmath>
#include <algorithm>

namespace kood3plot {
namespace writer {

// ============================================================
// Implementation Class
// ============================================================

class D3plotWriter::Impl {
public:
    std::string output_path;
    WriterOptions options;
    BinaryWriter writer;

    data::ControlData control;
    data::Mesh mesh;
    std::vector<data::StateData> states;

    std::string last_error;
    size_t total_bytes_written = 0;
    size_t states_written = 0;
    std::vector<std::string> output_files;

    int current_file_index = 0;
    bool has_control = false;
    bool has_mesh = false;

    // ========================================
    // Write Functions
    // ========================================

    ErrorCode writeAll();
    void writeControlData();
    void writeGeometry();
    void writeNARBS();
    void writeState(const data::StateData& state);
    void writeEOFMarker();

    // ========================================
    // Helper Functions
    // ========================================

    std::string getFilePath(int index);
    void startNewFile();
    bool shouldSplitFile(size_t additional_bytes);
    void log(const std::string& msg);
};

// ============================================================
// D3plotWriter Public Methods
// ============================================================

D3plotWriter::D3plotWriter(const std::string& output_path)
    : pImpl(std::make_unique<Impl>())
{
    pImpl->output_path = output_path;
}

D3plotWriter::~D3plotWriter() = default;

void D3plotWriter::setOptions(const WriterOptions& options) {
    pImpl->options = options;
}

const WriterOptions& D3plotWriter::getOptions() const {
    return pImpl->options;
}

void D3plotWriter::setPrecision(Precision prec) {
    pImpl->options.precision = prec;
}

void D3plotWriter::setEndian(Endian endian) {
    pImpl->options.endian = endian;
}

void D3plotWriter::setMaxFileSize(size_t bytes) {
    pImpl->options.max_file_size = bytes;
}

void D3plotWriter::setControlData(const data::ControlData& control) {
    pImpl->control = control;
    pImpl->has_control = true;
}

void D3plotWriter::setMesh(const data::Mesh& mesh) {
    pImpl->mesh = mesh;
    pImpl->has_mesh = true;
}

void D3plotWriter::addState(const data::StateData& state) {
    pImpl->states.push_back(state);
}

void D3plotWriter::setStates(const std::vector<data::StateData>& states) {
    pImpl->states = states;
}

void D3plotWriter::clearStates() {
    pImpl->states.clear();
}

ErrorCode D3plotWriter::write() {
    return pImpl->writeAll();
}

ErrorCode D3plotWriter::writeGeometryOnly() {
    // Temporarily clear states and write
    auto temp_states = std::move(pImpl->states);
    pImpl->states.clear();
    auto result = pImpl->writeAll();
    pImpl->states = std::move(temp_states);
    return result;
}

std::string D3plotWriter::getLastError() const {
    return pImpl->last_error;
}

size_t D3plotWriter::getWrittenBytes() const {
    return pImpl->total_bytes_written;
}

std::vector<std::string> D3plotWriter::getOutputFiles() const {
    return pImpl->output_files;
}

size_t D3plotWriter::getStatesWritten() const {
    return pImpl->states_written;
}

// ============================================================
// Implementation Methods
// ============================================================

ErrorCode D3plotWriter::Impl::writeAll() {
    // Validate input
    if (!has_control) {
        last_error = "Control data not set";
        return ErrorCode::INVALID_FORMAT;
    }

    if (!has_mesh) {
        last_error = "Mesh data not set";
        return ErrorCode::INVALID_FORMAT;
    }

    // Reset state
    total_bytes_written = 0;
    states_written = 0;
    output_files.clear();
    current_file_index = 0;

    // Configure writer
    writer.set_precision(options.precision);
    writer.set_endian(options.endian);

    // Open first file
    std::string filepath = getFilePath(0);
    if (writer.open(filepath) != ErrorCode::SUCCESS) {
        last_error = "Failed to open output file: " + filepath;
        return ErrorCode::IO_ERROR;
    }
    output_files.push_back(filepath);

    log("Writing d3plot to: " + filepath);

    // Write control data
    log("Writing control data...");
    writeControlData();

    // Write geometry
    log("Writing geometry...");
    writeGeometry();

    // Write NARBS if available
    if (options.write_narbs && control.NARBS > 0) {
        log("Writing NARBS section...");
        writeNARBS();
    }

    // Write states
    for (size_t i = 0; i < states.size(); ++i) {
        // Check if we need to split to a new file
        // Estimate state size
        size_t state_size = (1 + control.NGLBV + control.NND + control.ENN) * writer.get_word_size();
        if (shouldSplitFile(state_size)) {
            writer.close();
            startNewFile();
        }

        log("Writing state " + std::to_string(i) + " (t=" + std::to_string(states[i].time) + ")...");
        writeState(states[i]);
        states_written++;
    }

    // Write EOF marker
    writeEOFMarker();

    // Close file
    total_bytes_written = writer.get_bytes_written();
    writer.close();

    log("Write complete. Total bytes: " + std::to_string(total_bytes_written));

    return ErrorCode::SUCCESS;
}

void D3plotWriter::Impl::writeControlData() {
    // D3plot format: Control data is 64 words (or 64+EXTRA words)
    //
    // IMPORTANT: In D3plot format, control data words are stored with
    // precision-dependent word size BUT the actual data is:
    //   - Integers: stored as raw 4-byte int32 (padded with zeros in double precision)
    //   - Floats: stored as float/double based on precision
    //
    // Layout (word addresses):
    //   Words 0-9:   Title (raw bytes, word_size dependent)
    //   Word 10:     Runtime (float - unused, 0)
    //   Word 11:     File type (int - 1 = d3plot)
    //   Word 12:     Source version (int - 0)
    //   Word 13:     Release version (int - 960)
    //   Word 14:     Version (FLOAT - 960.0, used for format detection!)
    //   Word 15:     NDIM (int)
    //   Word 16:     NUMNP (int)
    //   ... etc

    // Determine word size based on precision
    size_t word_size = writer.get_word_size();
    size_t title_bytes = 10 * word_size;  // 10 words for title

    // Helper to write an integer as a single word
    // In single precision: writes 4-byte int
    // In double precision: writes 4-byte int padded with 4 zero bytes
    auto write_int_word = [this, word_size](int32_t value) {
        writer.write_int(value);
        if (word_size == 8) {
            // Pad with 4 zero bytes for double precision
            writer.write_int(0);
        }
    };

    // Helper to write a float word (respects precision setting)
    auto write_float_word = [this](double value) {
        writer.write_float(value);
    };

    // Write title (10 words)
    writer.write_string(control.TITLE, title_bytes);

    // Word 10: Runtime (float, unused = 0)
    write_float_word(0.0);

    // Word 11: File type (int, d3plot = 1)
    write_int_word(1);

    // Word 12: Source version (int, 0)
    write_int_word(0);

    // Word 13: Release version (int, 960)
    write_int_word(960);

    // Word 14: Version (FLOAT - 960.0, CRITICAL for format detection!)
    write_float_word(960.0);

    // Word 15: NDIM (int)
    write_int_word(control.NDIM);

    // Word 16: NUMNP (int)
    write_int_word(control.NUMNP);

    // Word 17: ICODE (int)
    write_int_word(control.ICODE);

    // Word 18: NGLBV (int)
    write_int_word(control.NGLBV);

    // Word 19: IT (int)
    write_int_word(control.IT);

    // Word 20: IU (int)
    write_int_word(control.IU);

    // Word 21: IV (int)
    write_int_word(control.IV);

    // Word 22: IA (int)
    write_int_word(control.IA);

    // Word 23: NEL8 (int)
    write_int_word(control.NEL8);

    // Word 24: NUMMAT8 (int)
    write_int_word(control.NUMMAT8);

    // Word 25: NUMDS (int, unused = 0)
    write_int_word(0);

    // Word 26: NUMST (int, unused = 0)
    write_int_word(0);

    // Word 27: NV3D (int)
    write_int_word(control.NV3D);

    // Word 28: NEL2 (int)
    write_int_word(control.NEL2);

    // Word 29: NUMMAT2 (int)
    write_int_word(control.NUMMAT2);

    // Word 30: NV1D (int)
    write_int_word(control.NV1D);

    // Word 31: NEL4 (int)
    write_int_word(control.NEL4);

    // Word 32: NUMMAT4 (int)
    write_int_word(control.NUMMAT4);

    // Word 33: NV2D (int)
    write_int_word(control.NV2D);

    // Word 34: NEIPH (int)
    write_int_word(control.NEIPH);

    // Word 35: NEIPS (int)
    write_int_word(control.NEIPS);

    // Word 36: MAXINT (int)
    write_int_word(control.MAXINT);

    // Word 37: EDLOPT/NMSPH (int)
    write_int_word(control.NMSPH);

    // Word 38: NGPSPH (int)
    write_int_word(control.NGPSPH);

    // Word 39: NARBS (int)
    write_int_word(control.NARBS);

    // Word 40: NELT (int)
    write_int_word(control.NELT);

    // Word 41: NUMMATT (int)
    write_int_word(control.NUMMATT);

    // Word 42: NV3DT (int)
    write_int_word(control.NV3DT);

    // Word 43: IOSHL(1) (int, 1000 = yes, 999 = no)
    write_int_word(control.IOSHL[0] ? 1000 : 999);

    // Word 44: IOSHL(2) (int)
    write_int_word(control.IOSHL[1] ? 1000 : 999);

    // Word 45: IOSHL(3) (int)
    write_int_word(control.IOSHL[2] ? 1000 : 999);

    // Word 46: IOSHL(4) (int)
    write_int_word(control.IOSHL[3] ? 1000 : 999);

    // Word 47: IALEMAT (int)
    write_int_word(control.IALEMAT);

    // Word 48: NCFDV1 (int, unused = 0)
    write_int_word(0);

    // Word 49: Reserved (int, 0)
    write_int_word(0);

    // Word 50: Reserved (int, 0)
    write_int_word(0);

    // Word 51: NMMAT (int)
    write_int_word(control.NMMAT);

    // Word 52: NCFDV2 (int, unused = 0)
    write_int_word(0);

    // Word 53: Reserved (int, 0)
    write_int_word(0);

    // Word 54: Reserved (int, 0)
    write_int_word(0);

    // Word 55: DT (float)
    write_float_word(control.DT);

    // Word 56: IDTDT (int)
    write_int_word(control.IDTDT);

    // Word 57: EXTRA (int)
    write_int_word(control.EXTRA);

    // Words 58-63: Reserved (int, zeros)
    for (int i = 58; i < 64; ++i) {
        write_int_word(0);
    }

    // Extended control words (if EXTRA > 0)
    if (control.EXTRA > 0) {
        for (int i = 0; i < control.EXTRA; ++i) {
            write_int_word(0);
        }
    }
}

void D3plotWriter::Impl::writeGeometry() {
    // ========================================
    // Node Coordinates
    // ========================================
    // IMPORTANT: Always write 3 coordinates per node (X, Y, Z)
    // Even if NDIM=5 or NDIM=7, the geometry section only stores 3 coords
    // (ls-dyna_database.txt lines 227-234: NDIM is reset to 3 for geometry)

    for (size_t i = 0; i < mesh.nodes.size(); ++i) {
        const auto& node = mesh.nodes[i];
        writer.write_float(node.x);
        writer.write_float(node.y);
        writer.write_float(node.z);
    }

    // ========================================
    // Solid Elements (8-node hexahedra)
    // ========================================
    // 9 words per element: 8 node IDs + 1 material ID
    int nel8 = std::abs(control.NEL8);

    for (size_t i = 0; i < mesh.solids.size() && i < static_cast<size_t>(nel8); ++i) {
        const auto& elem = mesh.solids[i];

        // Write 8 node IDs
        for (int n = 0; n < 8; ++n) {
            if (n < static_cast<int>(elem.node_ids.size())) {
                writer.write_int(elem.node_ids[n]);
            } else {
                writer.write_int(0);
            }
        }

        // Material ID
        if (i < mesh.solid_parts.size()) {
            writer.write_int(mesh.solid_parts[i]);
        } else {
            writer.write_int(1);
        }
    }

    // Pad remaining solids with zeros
    for (size_t i = mesh.solids.size(); i < static_cast<size_t>(nel8); ++i) {
        for (int n = 0; n < 9; ++n) {
            writer.write_int(0);
        }
    }

    // Extra nodes for 10-node solids (if NEL8 < 0)
    if (control.NEL8 < 0) {
        // Write 2 extra node IDs per element
        for (int i = 0; i < nel8; ++i) {
            writer.write_int(0);
            writer.write_int(0);
        }
    }

    // ========================================
    // Thick Shell Elements
    // ========================================
    // 9 words per element: 8 node IDs + 1 material ID
    for (size_t i = 0; i < mesh.thick_shells.size() && i < static_cast<size_t>(control.NELT); ++i) {
        const auto& elem = mesh.thick_shells[i];

        for (int n = 0; n < 8; ++n) {
            if (n < static_cast<int>(elem.node_ids.size())) {
                writer.write_int(elem.node_ids[n]);
            } else {
                writer.write_int(0);
            }
        }

        if (i < mesh.thick_shell_parts.size()) {
            writer.write_int(mesh.thick_shell_parts[i]);
        } else {
            writer.write_int(1);
        }
    }

    // ========================================
    // Beam Elements
    // ========================================
    // 6 words per element: 2 node IDs + orientation node + 2 nulls + material ID
    for (size_t i = 0; i < mesh.beams.size() && i < static_cast<size_t>(control.NEL2); ++i) {
        const auto& elem = mesh.beams[i];

        // Node 1
        if (!elem.node_ids.empty()) {
            writer.write_int(elem.node_ids[0]);
        } else {
            writer.write_int(0);
        }

        // Node 2
        if (elem.node_ids.size() > 1) {
            writer.write_int(elem.node_ids[1]);
        } else {
            writer.write_int(0);
        }

        // Orientation node (usually 0)
        writer.write_int(0);

        // Two null values
        writer.write_int(0);
        writer.write_int(0);

        // Material ID
        if (i < mesh.beam_parts.size()) {
            writer.write_int(mesh.beam_parts[i]);
        } else {
            writer.write_int(1);
        }
    }

    // ========================================
    // Shell Elements (4-node)
    // ========================================
    // 5 words per element: 4 node IDs + 1 material ID
    for (size_t i = 0; i < mesh.shells.size() && i < static_cast<size_t>(control.NEL4); ++i) {
        const auto& elem = mesh.shells[i];

        for (int n = 0; n < 4; ++n) {
            if (n < static_cast<int>(elem.node_ids.size())) {
                writer.write_int(elem.node_ids[n]);
            } else {
                writer.write_int(0);
            }
        }

        if (i < mesh.shell_parts.size()) {
            writer.write_int(mesh.shell_parts[i]);
        } else {
            writer.write_int(1);
        }
    }
}

void D3plotWriter::Impl::writeNARBS() {
    // NARBS section contains arbitrary numbering information
    // This is a simplified implementation

    if (control.NARBS <= 0) return;

    // Write NARBS header
    // Word 1: NSORT (sorting flag)
    writer.write_int(0);

    // Word 2: NSRH
    writer.write_int(0);

    // Word 3: NSRB
    writer.write_int(0);

    // Word 4: NSRS
    writer.write_int(0);

    // Word 5: NSRT
    writer.write_int(0);

    // Word 6: NSORTD
    writer.write_int(0);

    // Word 7: NSRHD
    writer.write_int(0);

    // Word 8: NSRBD
    writer.write_int(0);

    // Word 9: NSRSD
    writer.write_int(0);

    // Word 10: NSRTD
    writer.write_int(0);

    // Write node IDs
    if (!mesh.real_node_ids.empty()) {
        writer.write_int_array(mesh.real_node_ids);
    } else {
        // Write sequential IDs
        for (int i = 1; i <= control.NUMNP; ++i) {
            writer.write_int(i);
        }
    }

    // Write element IDs (solids)
    int nel8 = std::abs(control.NEL8);
    if (!mesh.real_solid_ids.empty()) {
        writer.write_int_array(mesh.real_solid_ids);
    } else {
        for (int i = 1; i <= nel8; ++i) {
            writer.write_int(i);
        }
    }

    // Write element IDs (beams)
    if (!mesh.real_beam_ids.empty()) {
        writer.write_int_array(mesh.real_beam_ids);
    } else {
        for (int i = 1; i <= control.NEL2; ++i) {
            writer.write_int(i);
        }
    }

    // Write element IDs (shells)
    if (!mesh.real_shell_ids.empty()) {
        writer.write_int_array(mesh.real_shell_ids);
    } else {
        for (int i = 1; i <= control.NEL4; ++i) {
            writer.write_int(i);
        }
    }

    // Write element IDs (thick shells)
    if (!mesh.real_thick_shell_ids.empty()) {
        writer.write_int_array(mesh.real_thick_shell_ids);
    } else {
        for (int i = 1; i <= control.NELT; ++i) {
            writer.write_int(i);
        }
    }

    // Material type array
    if (!mesh.material_types.empty()) {
        writer.write_int_array(mesh.material_types);
    } else if (control.NMMAT > 0) {
        for (int i = 1; i <= control.NMMAT; ++i) {
            writer.write_int(i);
        }
    }
}

void D3plotWriter::Impl::writeState(const data::StateData& state) {
    // ========================================
    // Time
    // ========================================
    writer.write_float(state.time);

    // ========================================
    // Global Variables (NGLBV words)
    // ========================================
    for (int i = 0; i < control.NGLBV; ++i) {
        if (i < static_cast<int>(state.global_vars.size())) {
            writer.write_float(state.global_vars[i]);
        } else {
            writer.write_float(0.0);
        }
    }

    // ========================================
    // Nodal Data (NND words total)
    // ========================================

    // Temperatures (if IT > 0)
    if (control.IT > 0) {
        for (int i = 0; i < control.NUMNP; ++i) {
            if (i < static_cast<int>(state.node_temperatures.size())) {
                writer.write_float(state.node_temperatures[i]);
            } else {
                writer.write_float(0.0);
            }
        }
    }

    // Displacements (if IU > 0) - 3 components per node
    if (control.IU > 0) {
        for (int i = 0; i < control.NUMNP * 3; ++i) {
            if (i < static_cast<int>(state.node_displacements.size())) {
                writer.write_float(state.node_displacements[i]);
            } else {
                writer.write_float(0.0);
            }
        }
    }

    // Velocities (if IV > 0) - 3 components per node
    if (control.IV > 0) {
        for (int i = 0; i < control.NUMNP * 3; ++i) {
            if (i < static_cast<int>(state.node_velocities.size())) {
                writer.write_float(state.node_velocities[i]);
            } else {
                writer.write_float(0.0);
            }
        }
    }

    // Accelerations (if IA > 0) - 3 components per node
    if (control.IA > 0) {
        for (int i = 0; i < control.NUMNP * 3; ++i) {
            if (i < static_cast<int>(state.node_accelerations.size())) {
                writer.write_float(state.node_accelerations[i]);
            } else {
                writer.write_float(0.0);
            }
        }
    }

    // ========================================
    // Element Data (ENN words total)
    // ========================================

    // Solid data (NEL8 * NV3D words)
    int nel8 = std::abs(control.NEL8);
    int solid_words = nel8 * control.NV3D;
    for (int i = 0; i < solid_words; ++i) {
        if (i < static_cast<int>(state.solid_data.size())) {
            writer.write_float(state.solid_data[i]);
        } else {
            writer.write_float(0.0);
        }
    }

    // Thick shell data (NELT * NV3DT words)
    int tshell_words = control.NELT * control.NV3DT;
    for (int i = 0; i < tshell_words; ++i) {
        if (i < static_cast<int>(state.thick_shell_data.size())) {
            writer.write_float(state.thick_shell_data[i]);
        } else {
            writer.write_float(0.0);
        }
    }

    // Beam data (NEL2 * NV1D words)
    int beam_words = control.NEL2 * control.NV1D;
    for (int i = 0; i < beam_words; ++i) {
        if (i < static_cast<int>(state.beam_data.size())) {
            writer.write_float(state.beam_data[i]);
        } else {
            writer.write_float(0.0);
        }
    }

    // Shell data (NEL4 * NV2D words)
    int shell_words = control.NEL4 * control.NV2D;
    for (int i = 0; i < shell_words; ++i) {
        if (i < static_cast<int>(state.shell_data.size())) {
            writer.write_float(state.shell_data[i]);
        } else {
            writer.write_float(0.0);
        }
    }
}

void D3plotWriter::Impl::writeEOFMarker() {
    // Write -999999.0 as EOF marker
    writer.write_float(-999999.0);
}

std::string D3plotWriter::Impl::getFilePath(int index) {
    if (index == 0) {
        return output_path;
    }

    // Generate numbered filename: d3plot01, d3plot02, etc.
    char suffix[16];
    std::snprintf(suffix, sizeof(suffix), "%02d", index);
    return output_path + suffix;
}

void D3plotWriter::Impl::startNewFile() {
    current_file_index++;
    std::string filepath = getFilePath(current_file_index);

    if (writer.open(filepath) != ErrorCode::SUCCESS) {
        log("Failed to open new file: " + filepath);
        return;
    }

    output_files.push_back(filepath);
    log("Started new file: " + filepath);
}

bool D3plotWriter::Impl::shouldSplitFile(size_t additional_bytes) {
    if (options.max_file_size == 0) return false;

    size_t current_size = writer.get_bytes_written();
    return (current_size + additional_bytes) > options.max_file_size;
}

void D3plotWriter::Impl::log(const std::string& msg) {
    if (options.verbose) {
        std::cout << "[D3plotWriter] " << msg << std::endl;
    }
}

} // namespace writer
} // namespace kood3plot
