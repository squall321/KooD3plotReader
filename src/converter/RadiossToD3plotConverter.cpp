/**
 * @file RadiossToD3plotConverter.cpp
 * @brief Direct OpenRadioss A00/A01 → LS-DYNA d3plot converter
 *
 * No VTK intermediate — maps RadiossReader output directly to D3plotWriter.
 */

#include "kood3plot/converter/RadiossToD3plotConverter.h"
#include <iostream>
#include <set>
#include <algorithm>
#include <cmath>

namespace kood3plot {
namespace converter {

// ============================================================
// Mesh mapping: RadiossMesh → d3plot Mesh + ControlData
// ============================================================

void RadiossToD3plotConverter::mapMesh(
    const RadiossMesh& src,
    const RadiossHeader& header,
    data::Mesh& dst,
    data::ControlData& control,
    const RadiossConversionOptions& options)
{
    // Title
    control.TITLE = options.title.empty() ? header.title : options.title;
    control.NDIM = 5;  // Standard 3D

    // ── Nodes ──
    const size_t num_nodes = src.nodes.size();
    dst.nodes.resize(num_nodes);
    for (size_t i = 0; i < num_nodes; ++i) {
        dst.nodes[i] = src.nodes[i];
    }
    control.NUMNP = static_cast<int32_t>(num_nodes);

    // ── Solid elements ──
    dst.solids.reserve(src.solids.size());
    dst.solid_parts.reserve(src.solids.size());
    for (size_t i = 0; i < src.solids.size(); ++i) {
        Element elem;
        elem.id = src.solids[i].id;
        elem.type = ElementType::SOLID;
        elem.material_id = (i < src.solid_parts.size()) ? src.solid_parts[i] : 1;

        // d3plot expects 8-node hex; pad shorter elements
        elem.node_ids.resize(8, 0);
        const auto& src_nodes = src.solids[i].node_ids;
        size_t n = std::min(src_nodes.size(), (size_t)8);
        for (size_t j = 0; j < n; ++j) {
            elem.node_ids[j] = src_nodes[j];
        }
        // Degenerate: repeat last node for tet/wedge/pyramid
        for (size_t j = n; j < 8; ++j) {
            elem.node_ids[j] = src_nodes[n - 1];
        }

        dst.solids.push_back(std::move(elem));
        dst.solid_parts.push_back(elem.material_id);
    }

    // ── Shell elements ──
    dst.shells.reserve(src.shells.size());
    dst.shell_parts.reserve(src.shells.size());
    for (size_t i = 0; i < src.shells.size(); ++i) {
        Element elem;
        elem.id = src.shells[i].id;
        elem.type = ElementType::SHELL;
        elem.material_id = (i < src.shell_parts.size()) ? src.shell_parts[i] : 1;

        // d3plot expects 4-node quad; pad triangle
        elem.node_ids.resize(4, 0);
        const auto& src_nodes = src.shells[i].node_ids;
        size_t n = std::min(src_nodes.size(), (size_t)4);
        for (size_t j = 0; j < n; ++j) {
            elem.node_ids[j] = src_nodes[j];
        }
        // Degenerate: repeat last node for triangle
        for (size_t j = n; j < 4; ++j) {
            elem.node_ids[j] = src_nodes[n - 1];
        }

        dst.shells.push_back(std::move(elem));
        dst.shell_parts.push_back(elem.material_id);
    }

    // ── Beam elements ──
    dst.beams.reserve(src.beams.size());
    dst.beam_parts.reserve(src.beams.size());
    for (size_t i = 0; i < src.beams.size(); ++i) {
        Element elem;
        elem.id = src.beams[i].id;
        elem.type = ElementType::BEAM;
        elem.material_id = (i < src.beam_parts.size()) ? src.beam_parts[i] : 1;

        // d3plot beam: 2 nodes + 1 orientation node
        elem.node_ids.resize(3, 0);
        const auto& src_nodes = src.beams[i].node_ids;
        for (size_t j = 0; j < std::min(src_nodes.size(), (size_t)3); ++j) {
            elem.node_ids[j] = src_nodes[j];
        }

        dst.beams.push_back(std::move(elem));
        dst.beam_parts.push_back(elem.material_id);
    }

    // ── Control data ──
    control.NEL8 = static_cast<int32_t>(dst.solids.size());
    control.NEL4 = static_cast<int32_t>(dst.shells.size());
    control.NEL2 = static_cast<int32_t>(dst.beams.size());
    control.NELT = 0;

    // Variables per element — only set if elements of that type exist
    // NV3D/NV2D: always set if elements exist (zero-fill if no stress data)
    control.NV3D = (control.NEL8 > 0) ? 7 : 0;
    control.NV2D = (control.NEL4 > 0) ? 33 : 0;
    control.NV1D = 0;   // Beam results not extracted from Radioss animation
    control.NV3DT = 0;

    // Material counts
    std::set<int32_t> parts;
    for (auto p : dst.solid_parts) parts.insert(p);
    for (auto p : dst.shell_parts) parts.insert(p);
    for (auto p : dst.beam_parts) parts.insert(p);

    control.NUMMAT8 = (control.NEL8 > 0 && !dst.solid_parts.empty()) ?
        static_cast<int32_t>(std::set<int32_t>(dst.solid_parts.begin(), dst.solid_parts.end()).size()) : 0;
    control.NUMMAT4 = (control.NEL4 > 0 && !dst.shell_parts.empty()) ?
        static_cast<int32_t>(std::set<int32_t>(dst.shell_parts.begin(), dst.shell_parts.end()).size()) : 0;
    control.NUMMAT2 = (control.NEL2 > 0 && !dst.beam_parts.empty()) ?
        static_cast<int32_t>(std::set<int32_t>(dst.beam_parts.begin(), dst.beam_parts.end()).size()) : 0;
    control.NUMMATT = 0;
    control.NMMAT = static_cast<int32_t>(parts.size());
    if (control.NMMAT == 0) control.NMMAT = 1;

    // Nodal output flags
    control.IU = header.has_displacement ? 1 : 0;
    control.IV = header.has_velocity ? 1 : 0;
    control.IA = header.has_acceleration ? 1 : 0;
    control.IT = 0;

    // Global variables
    control.NGLBV = 6;  // KE, IE, total, X-vel, Y-vel, Z-vel
    control.NARBS = 0;
    control.EXTRA = 0;
    control.ISTRN = 0;  // Radioss animation files don't contain strain tensor

    // Compute derived values
    control.compute_derived_values();
}

// ============================================================
// State mapping: RadiossState → d3plot StateData
// ============================================================

data::StateData RadiossToD3plotConverter::mapState(
    const RadiossState& src,
    const RadiossHeader& header,
    const data::ControlData& control)
{
    data::StateData dst;
    dst.time = src.time;

    // Global variables (6 zeros as placeholder)
    dst.global_vars.resize(control.NGLBV, 0.0);

    // ── Nodal data ──
    if (control.IU && !src.node_displacements.empty()) {
        dst.node_displacements = src.node_displacements;
    }
    if (control.IV && !src.node_velocities.empty()) {
        dst.node_velocities = src.node_velocities;
    }
    if (control.IA && !src.node_accelerations.empty()) {
        dst.node_accelerations = src.node_accelerations;
    }

    // ── Solid element data ──
    // d3plot solid layout: per element → [sxx, syy, szz, sxy, syz, szx, eps, (exx..ezx if ISTRN)]
    const int nv3d = control.NV3D;
    const int num_solids = control.NEL8;

    if (num_solids > 0) {
        dst.solid_data.resize(static_cast<size_t>(num_solids) * nv3d, 0.0);

        for (int i = 0; i < num_solids; ++i) {
            size_t dst_base = static_cast<size_t>(i) * nv3d;

            // Stress tensor (6 components, Voigt: sxx, syy, szz, sxy, syz, szx)
            if (!src.solid_stress.empty()) {
                size_t src_base = static_cast<size_t>(i) * 6;
                if (src_base + 5 < src.solid_stress.size()) {
                    for (int j = 0; j < 6; ++j) {
                        dst.solid_data[dst_base + j] = src.solid_stress[src_base + j];
                    }
                }
            }

            // Effective plastic strain
            if (!src.plastic_strain.empty() && static_cast<size_t>(i) < src.plastic_strain.size()) {
                dst.solid_data[dst_base + 6] = src.plastic_strain[i];
            }

            // Strain tensor (6 components, if available)
            if (header.has_strain && !src.solid_strain.empty()) {
                size_t src_base = static_cast<size_t>(i) * 6;
                if (src_base + 5 < src.solid_strain.size()) {
                    for (int j = 0; j < 6; ++j) {
                        dst.solid_data[dst_base + 7 + j] = src.solid_strain[src_base + j];
                    }
                }
            }
        }
    }

    // ── Shell element data ──
    // d3plot shell layout: NV2D=33 for 3 integration points
    // Per integration point: [sxx, syy, szz, sxy, syz, szx, eps] = 7 vars
    // 3 points × 7 = 21, + 12 extras (resultants, etc.) = 33
    const int nv2d = control.NV2D;
    const int num_shells = control.NEL4;

    if (num_shells > 0 && nv2d > 0) {
        dst.shell_data.resize(static_cast<size_t>(num_shells) * nv2d, 0.0);

        for (int i = 0; i < num_shells; ++i) {
            size_t dst_base = static_cast<size_t>(i) * nv2d;

            // Write stress to mid-surface (integration point 2, offset 7)
            if (!src.shell_stress.empty()) {
                size_t src_base = static_cast<size_t>(i) * 6;
                if (src_base + 5 < src.shell_stress.size()) {
                    // Write to all 3 integration points
                    for (int ip = 0; ip < 3; ++ip) {
                        size_t ip_base = dst_base + ip * 7;
                        for (int j = 0; j < 6; ++j) {
                            dst.shell_data[ip_base + j] = src.shell_stress[src_base + j];
                        }
                    }
                }
            }

            // Plastic strain for shells
            if (!src.plastic_strain.empty()) {
                size_t eps_idx = static_cast<size_t>(num_solids + i);
                if (eps_idx < src.plastic_strain.size()) {
                    // Write to all 3 integration points
                    for (int ip = 0; ip < 3; ++ip) {
                        dst.shell_data[dst_base + ip * 7 + 6] = src.plastic_strain[eps_idx];
                    }
                }
            }
        }
    }

    return dst;
}

// ============================================================
// Main conversion pipeline
// ============================================================

RadiossConversionResult RadiossToD3plotConverter::convert(
    const std::string& a00_path,
    const std::string& d3plot_path,
    const RadiossConversionOptions& options,
    RadiossConversionCallback callback)
{
    RadiossConversionResult result;

    // Step 1: Read Radioss geometry
    if (callback) callback("Opening Radioss A00 file...");

    RadiossReader reader(a00_path);
    ErrorCode err = reader.open();
    if (err != ErrorCode::SUCCESS) {
        result.error_message = "Failed to open Radioss A00: " + reader.getLastError();
        return result;
    }

    const auto& header = reader.getHeader();
    const auto& radioss_mesh = reader.getMesh();

    if (options.verbose || callback) {
        std::string info = "Radioss model: " +
            std::to_string(header.num_nodes) + " nodes, " +
            std::to_string(header.num_solids) + " solids, " +
            std::to_string(header.num_shells) + " shells, " +
            std::to_string(header.num_beams) + " beams";
        if (options.verbose) std::cout << "[RadiossToD3plot] " << info << "\n";
        if (callback) callback(info);
    }

    // Step 2: Map mesh and control data
    if (callback) callback("Mapping mesh to d3plot format...");

    data::Mesh d3_mesh;
    data::ControlData control;
    mapMesh(radioss_mesh, header, d3_mesh, control, options);

    result.num_nodes = d3_mesh.nodes.size();
    result.num_solids = d3_mesh.solids.size();
    result.num_shells = d3_mesh.shells.size();
    result.num_beams = d3_mesh.beams.size();

    // Step 3: Read and map all states
    if (callback) callback("Reading Radioss state files...");

    auto radioss_states = reader.readAllStates(options.max_states);
    result.num_states = radioss_states.size();

    if (options.verbose) {
        std::cout << "[RadiossToD3plot] Read " << radioss_states.size() << " states\n";
    }

    // Step 4: Write d3plot
    if (callback) callback("Writing d3plot (" + std::to_string(radioss_states.size()) + " states)...");

    writer::D3plotWriter writer(d3plot_path);
    writer::WriterOptions wopts;
    wopts.precision = options.precision;
    wopts.endian = options.endian;
    wopts.max_file_size = options.max_file_size;
    wopts.verbose = options.verbose;
    writer.setOptions(wopts);

    writer.setControlData(control);
    writer.setMesh(d3_mesh);

    // Map states one at a time to minimize memory usage
    for (size_t i = 0; i < radioss_states.size(); ++i) {
        auto d3_state = mapState(radioss_states[i], header, control);
        writer.addState(d3_state);

        if (options.verbose && (i % 50 == 0 || i == radioss_states.size() - 1)) {
            std::cout << "[RadiossToD3plot] Mapped state " << (i + 1)
                      << "/" << radioss_states.size() << "\n";
        }
    }

    err = writer.write();
    if (err != ErrorCode::SUCCESS) {
        result.error_message = "Failed to write d3plot: " + writer.getLastError();
        return result;
    }

    result.success = true;
    result.bytes_written = writer.getWrittenBytes();
    result.output_files = writer.getOutputFiles();

    if (callback) {
        callback("Done: " + std::to_string(result.bytes_written) + " bytes, " +
                 std::to_string(result.output_files.size()) + " file(s)");
    }

    if (options.verbose) {
        std::cout << "[RadiossToD3plot] Complete: "
                  << result.bytes_written << " bytes written to "
                  << result.output_files.size() << " file(s)\n";
    }

    return result;
}

} // namespace converter
} // namespace kood3plot
