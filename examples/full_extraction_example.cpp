/**
 * @file full_extraction_example.cpp
 * @brief Comprehensive example demonstrating ALL data extraction capabilities
 * @author KooD3plot Development Team
 * @date 2025-12-05
 *
 * This example demonstrates all extractable data from d3plot files:
 * - Mesh data (nodes, elements, parts, material IDs)
 * - State data (time, displacements, velocities, accelerations)
 * - Stress data (6 components, Von Mises, pressure)
 * - Strain data (effective plastic strain, 6 strain components)
 * - Surface extraction (exterior surfaces, direction filtering)
 * - Time history analysis (SinglePassAnalyzer)
 * - Surface stress analysis
 *
 * Usage:
 *   ./full_extraction_example <d3plot_path> [output_dir]
 */

#include "kood3plot/D3plotReader.hpp"
#include "kood3plot/data/Mesh.hpp"
#include "kood3plot/data/StateData.hpp"
#include "kood3plot/data/ControlData.hpp"
#include "kood3plot/analysis/PartAnalyzer.hpp"
#include "kood3plot/analysis/SurfaceExtractor.hpp"
#include "kood3plot/analysis/SurfaceStressAnalyzer.hpp"
#include "kood3plot/analysis/SinglePassAnalyzer.hpp"
#include "kood3plot/analysis/TimeHistoryAnalyzer.hpp"
#include "kood3plot/analysis/AnalysisResult.hpp"
#include "kood3plot/analysis/VectorMath.hpp"

#include <iostream>
#include <fstream>
#include <sstream>
#include <iomanip>
#include <chrono>
#include <filesystem>
#include <algorithm>
#include <cmath>

namespace fs = std::filesystem;
using namespace kood3plot;
using namespace kood3plot::analysis;

// ============================================================
// Utility Functions
// ============================================================

/**
 * @brief Timer utility class
 */
class Timer {
public:
    Timer() : start_(std::chrono::high_resolution_clock::now()) {}

    double elapsed_ms() const {
        auto now = std::chrono::high_resolution_clock::now();
        return std::chrono::duration<double, std::milli>(now - start_).count();
    }

    void reset() { start_ = std::chrono::high_resolution_clock::now(); }

private:
    std::chrono::high_resolution_clock::time_point start_;
};

/**
 * @brief Print section header
 */
void print_section(const std::string& title) {
    std::cout << "\n";
    std::cout << "============================================================\n";
    std::cout << title << "\n";
    std::cout << "============================================================\n";
}

/**
 * @brief Print subsection header
 */
void print_subsection(const std::string& title) {
    std::cout << "\n--- " << title << " ---\n";
}

// ============================================================
// 1. Mesh Data Extraction
// ============================================================

void extract_mesh_data(D3plotReader& reader, const std::string& output_dir) {
    print_section("1. Mesh Data Extraction");
    Timer timer;

    auto mesh = reader.read_mesh();

    std::cout << "Mesh read time: " << std::fixed << std::setprecision(2)
              << timer.elapsed_ms() << " ms\n";

    // 1.1 Node data
    print_subsection("1.1 Nodes");
    std::cout << "Total nodes: " << mesh.nodes.size() << "\n";

    // Export node coordinates to CSV
    std::string node_file = output_dir + "/nodes.csv";
    std::ofstream ofs(node_file);
    if (ofs) {
        ofs << "NodeID,X,Y,Z\n";
        for (size_t i = 0; i < mesh.nodes.size(); ++i) {
            const auto& node = mesh.nodes[i];
            int32_t real_id = (i < mesh.real_node_ids.size()) ? mesh.real_node_ids[i] : node.id;
            ofs << std::fixed << std::setprecision(8)
                << real_id << "," << node.x << "," << node.y << "," << node.z << "\n";
        }
        ofs.close();
        std::cout << "  Exported: " << node_file << "\n";
    }

    // Print sample nodes
    std::cout << "  Sample (first 5 nodes):\n";
    for (size_t i = 0; i < std::min(size_t(5), mesh.nodes.size()); ++i) {
        const auto& node = mesh.nodes[i];
        int32_t real_id = (i < mesh.real_node_ids.size()) ? mesh.real_node_ids[i] : node.id;
        std::cout << "    Node " << real_id << ": ("
                  << std::fixed << std::setprecision(4)
                  << node.x << ", " << node.y << ", " << node.z << ")\n";
    }

    // 1.2 Element data
    print_subsection("1.2 Elements");
    std::cout << "Solid elements:      " << mesh.num_solids << "\n";
    std::cout << "Shell elements:      " << mesh.num_shells << "\n";
    std::cout << "Beam elements:       " << mesh.num_beams << "\n";
    std::cout << "Thick shell elements:" << mesh.num_thick_shells << "\n";
    std::cout << "Total elements:      " << mesh.get_num_elements() << "\n";

    // Export solid element connectivity
    if (!mesh.solids.empty()) {
        std::string solid_file = output_dir + "/solid_elements.csv";
        std::ofstream ofs_solid(solid_file);
        if (ofs_solid) {
            ofs_solid << "ElementID,PartID,N1,N2,N3,N4,N5,N6,N7,N8\n";
            for (size_t i = 0; i < mesh.solids.size(); ++i) {
                const auto& elem = mesh.solids[i];
                int32_t real_id = (i < mesh.real_solid_ids.size()) ? mesh.real_solid_ids[i] : elem.id;
                int32_t part_id = (i < mesh.solid_parts.size()) ? mesh.solid_parts[i] : 0;
                ofs_solid << real_id << "," << part_id;
                for (auto nid : elem.node_ids) {
                    ofs_solid << "," << nid;
                }
                ofs_solid << "\n";
            }
            ofs_solid.close();
            std::cout << "  Exported: " << solid_file << "\n";
        }
    }

    // 1.3 Part information
    print_subsection("1.3 Parts");
    std::unordered_map<int32_t, size_t> part_elem_count;
    for (size_t i = 0; i < mesh.solid_parts.size(); ++i) {
        part_elem_count[mesh.solid_parts[i]]++;
    }

    std::cout << "Parts found: " << part_elem_count.size() << "\n";
    std::cout << "  Part ID    Elements\n";
    for (const auto& [part_id, count] : part_elem_count) {
        std::cout << "  " << std::setw(8) << part_id << "  " << std::setw(8) << count << "\n";
    }

    // Export part summary
    std::string part_file = output_dir + "/parts_summary.csv";
    std::ofstream ofs_part(part_file);
    if (ofs_part) {
        ofs_part << "PartID,SolidElements\n";
        for (const auto& [part_id, count] : part_elem_count) {
            ofs_part << part_id << "," << count << "\n";
        }
        ofs_part.close();
        std::cout << "  Exported: " << part_file << "\n";
    }
}

// ============================================================
// 2. State Data Extraction
// ============================================================

void extract_state_data(D3plotReader& reader, const std::string& output_dir) {
    print_section("2. State Data Extraction");
    Timer timer;

    // Read all states in parallel for performance
    auto states = reader.read_all_states_parallel();

    std::cout << "States read time: " << std::fixed << std::setprecision(2)
              << timer.elapsed_ms() << " ms\n";
    std::cout << "Total states: " << states.size() << "\n";

    if (states.empty()) {
        std::cout << "No states found!\n";
        return;
    }

    // 2.1 Time values
    print_subsection("2.1 Time Values");
    double t_start = states.front().time;
    double t_end = states.back().time;
    std::cout << "Time range: " << t_start << " to " << t_end << "\n";

    // Export time values
    std::string time_file = output_dir + "/time_values.csv";
    std::ofstream ofs_time(time_file);
    if (ofs_time) {
        ofs_time << "StateIndex,Time\n";
        for (size_t i = 0; i < states.size(); ++i) {
            ofs_time << std::fixed << std::setprecision(10) << i << "," << states[i].time << "\n";
        }
        ofs_time.close();
        std::cout << "  Exported: " << time_file << "\n";
    }

    // 2.2 Global variables
    print_subsection("2.2 Global Variables");
    if (!states[0].global_vars.empty()) {
        std::cout << "Global variables per state: " << states[0].global_vars.size() << "\n";

        std::string gv_file = output_dir + "/global_variables.csv";
        std::ofstream ofs_gv(gv_file);
        if (ofs_gv) {
            ofs_gv << "Time";
            for (size_t i = 0; i < states[0].global_vars.size(); ++i) {
                ofs_gv << ",Var" << i;
            }
            ofs_gv << "\n";

            for (const auto& state : states) {
                ofs_gv << std::fixed << std::setprecision(10) << state.time;
                for (double v : state.global_vars) {
                    ofs_gv << "," << v;
                }
                ofs_gv << "\n";
            }
            ofs_gv.close();
            std::cout << "  Exported: " << gv_file << "\n";
        }
    } else {
        std::cout << "No global variables in this file.\n";
    }

    // 2.3 Node displacements
    print_subsection("2.3 Node Displacements");
    if (!states[0].node_displacements.empty()) {
        size_t num_nodes = states[0].node_displacements.size() / 3;
        std::cout << "Displacement data available: " << num_nodes << " nodes x 3 components (Ux, Uy, Uz)\n";

        // Find max displacement across all states
        double max_disp = 0;
        size_t max_node = 0;
        size_t max_state = 0;

        for (size_t s = 0; s < states.size(); ++s) {
            const auto& disp = states[s].node_displacements;
            for (size_t i = 0; i < num_nodes; ++i) {
                double ux = disp[i * 3 + 0];
                double uy = disp[i * 3 + 1];
                double uz = disp[i * 3 + 2];
                double mag = std::sqrt(ux*ux + uy*uy + uz*uz);
                if (mag > max_disp) {
                    max_disp = mag;
                    max_node = i;
                    max_state = s;
                }
            }
        }
        std::cout << "  Max displacement magnitude: " << std::fixed << std::setprecision(6) << max_disp << "\n";
        std::cout << "  At node index: " << max_node << ", state: " << max_state
                  << " (t=" << states[max_state].time << ")\n";

        // Export final state displacements
        std::string disp_file = output_dir + "/displacements_final.csv";
        std::ofstream ofs_disp(disp_file);
        if (ofs_disp) {
            ofs_disp << "NodeIndex,Ux,Uy,Uz,Magnitude\n";
            const auto& final_disp = states.back().node_displacements;
            for (size_t i = 0; i < num_nodes; ++i) {
                double ux = final_disp[i * 3 + 0];
                double uy = final_disp[i * 3 + 1];
                double uz = final_disp[i * 3 + 2];
                double mag = std::sqrt(ux*ux + uy*uy + uz*uz);
                ofs_disp << std::fixed << std::setprecision(8)
                        << i << "," << ux << "," << uy << "," << uz << "," << mag << "\n";
            }
            ofs_disp.close();
            std::cout << "  Exported: " << disp_file << "\n";
        }
    } else {
        std::cout << "No displacement data (IU=0)\n";
    }

    // 2.4 Node velocities
    print_subsection("2.4 Node Velocities");
    if (!states[0].node_velocities.empty()) {
        size_t num_nodes = states[0].node_velocities.size() / 3;
        std::cout << "Velocity data available: " << num_nodes << " nodes x 3 components (Vx, Vy, Vz)\n";

        std::string vel_file = output_dir + "/velocities_final.csv";
        std::ofstream ofs_vel(vel_file);
        if (ofs_vel) {
            ofs_vel << "NodeIndex,Vx,Vy,Vz,Magnitude\n";
            const auto& vel = states.back().node_velocities;
            for (size_t i = 0; i < num_nodes; ++i) {
                double vx = vel[i * 3 + 0];
                double vy = vel[i * 3 + 1];
                double vz = vel[i * 3 + 2];
                double mag = std::sqrt(vx*vx + vy*vy + vz*vz);
                ofs_vel << std::fixed << std::setprecision(8)
                       << i << "," << vx << "," << vy << "," << vz << "," << mag << "\n";
            }
            ofs_vel.close();
            std::cout << "  Exported: " << vel_file << "\n";
        }
    } else {
        std::cout << "No velocity data (IV=0)\n";
    }

    // 2.5 Node accelerations
    print_subsection("2.5 Node Accelerations");
    if (!states[0].node_accelerations.empty()) {
        size_t num_nodes = states[0].node_accelerations.size() / 3;
        std::cout << "Acceleration data available: " << num_nodes << " nodes x 3 components (Ax, Ay, Az)\n";

        std::string acc_file = output_dir + "/accelerations_final.csv";
        std::ofstream ofs_acc(acc_file);
        if (ofs_acc) {
            ofs_acc << "NodeIndex,Ax,Ay,Az,Magnitude\n";
            const auto& acc = states.back().node_accelerations;
            for (size_t i = 0; i < num_nodes; ++i) {
                double ax = acc[i * 3 + 0];
                double ay = acc[i * 3 + 1];
                double az = acc[i * 3 + 2];
                double mag = std::sqrt(ax*ax + ay*ay + az*az);
                ofs_acc << std::fixed << std::setprecision(8)
                       << i << "," << ax << "," << ay << "," << az << "," << mag << "\n";
            }
            ofs_acc.close();
            std::cout << "  Exported: " << acc_file << "\n";
        }
    } else {
        std::cout << "No acceleration data (IA=0)\n";
    }
}

// ============================================================
// 3. Stress Data Extraction
// ============================================================

void extract_stress_data(D3plotReader& reader, const std::string& output_dir) {
    print_section("3. Stress Data Extraction");
    Timer timer;

    const auto& ctrl = reader.get_control_data();
    int nv3d = ctrl.NV3D;
    std::cout << "Values per solid element (NV3D): " << nv3d << "\n";

    // Stress component indices in solid_data
    // [0] = Sigma_xx, [1] = Sigma_yy, [2] = Sigma_zz
    // [3] = Sigma_xy, [4] = Sigma_yz, [5] = Sigma_zx
    // [6] = Effective plastic strain

    auto states = reader.read_all_states_parallel();
    auto mesh = reader.read_mesh();

    if (states.empty() || mesh.solids.empty()) {
        std::cout << "No data available\n";
        return;
    }

    size_t num_elements = mesh.solids.size();
    std::cout << "Solid elements: " << num_elements << "\n";
    std::cout << "States: " << states.size() << "\n";

    // 3.1 All stress components for final state
    print_subsection("3.1 Stress Components (Final State)");

    std::string stress_file = output_dir + "/stress_components_final.csv";
    std::ofstream ofs_stress(stress_file);
    if (ofs_stress) {
        ofs_stress << "ElementIndex,PartID,Sxx,Syy,Szz,Sxy,Syz,Szx,VonMises,Pressure\n";

        const auto& solid_data = states.back().solid_data;
        double max_vm = 0, min_vm = 1e30;

        for (size_t i = 0; i < num_elements && i * nv3d + 6 <= solid_data.size(); ++i) {
            double sxx = solid_data[i * nv3d + 0];
            double syy = solid_data[i * nv3d + 1];
            double szz = solid_data[i * nv3d + 2];
            double sxy = solid_data[i * nv3d + 3];
            double syz = solid_data[i * nv3d + 4];
            double szx = solid_data[i * nv3d + 5];

            // Calculate Von Mises stress
            double vm = std::sqrt(0.5 * ((sxx-syy)*(sxx-syy) + (syy-szz)*(syy-szz) + (szz-sxx)*(szz-sxx)
                                + 6.0 * (sxy*sxy + syz*syz + szx*szx)));

            // Calculate pressure (negative mean stress)
            double pressure = -(sxx + syy + szz) / 3.0;

            int32_t part_id = (i < mesh.solid_parts.size()) ? mesh.solid_parts[i] : 0;

            ofs_stress << std::fixed << std::setprecision(6)
                      << i << "," << part_id << ","
                      << sxx << "," << syy << "," << szz << ","
                      << sxy << "," << syz << "," << szx << ","
                      << vm << "," << pressure << "\n";

            if (vm > max_vm) max_vm = vm;
            if (vm < min_vm && vm > 0) min_vm = vm;
        }
        ofs_stress.close();
        std::cout << "  Exported: " << stress_file << "\n";
        std::cout << "  Von Mises range: " << std::fixed << std::setprecision(2)
                  << min_vm << " to " << max_vm << " MPa\n";
    }

    // 3.2 Von Mises stress time history (using PartAnalyzer)
    print_subsection("3.2 Von Mises Time History (per Part)");

    PartAnalyzer part_analyzer(reader);
    if (part_analyzer.initialize()) {
        timer.reset();
        auto histories = part_analyzer.analyze_with_states(states, StressComponent::VON_MISES);
        std::cout << "  Analysis time: " << timer.elapsed_ms() << " ms\n";

        for (const auto& history : histories) {
            double global_max = *std::max_element(history.max_values.begin(), history.max_values.end());
            std::cout << "  Part " << history.part_id << ": max Von Mises = "
                      << std::fixed << std::setprecision(2) << global_max << " MPa\n";
        }

        // Export combined time history
        std::string vm_file = output_dir + "/von_mises_history.csv";
        part_analyzer.export_to_csv(histories, vm_file);
        std::cout << "  Exported: " << vm_file << "\n";
    }

    std::cout << "Total stress extraction time: " << timer.elapsed_ms() << " ms\n";
}

// ============================================================
// 4. Strain Data Extraction
// ============================================================

void extract_strain_data(D3plotReader& reader, const std::string& output_dir) {
    print_section("4. Strain Data Extraction");
    Timer timer;

    const auto& ctrl = reader.get_control_data();
    int nv3d = ctrl.NV3D;
    bool has_strain = (ctrl.ISTRN != 0);

    std::cout << "NV3D = " << nv3d << "\n";
    std::cout << "ISTRN = " << ctrl.ISTRN << " (strain output: " << (has_strain ? "YES" : "NO") << ")\n";

    auto states = reader.read_all_states_parallel();
    auto mesh = reader.read_mesh();

    if (states.empty() || mesh.solids.empty()) {
        std::cout << "No data available\n";
        return;
    }

    size_t num_elements = mesh.solids.size();

    // 4.1 Effective plastic strain
    print_subsection("4.1 Effective Plastic Strain");

    // Eff. plastic strain is at index 6 in solid data
    std::string eps_file = output_dir + "/eff_plastic_strain_final.csv";
    std::ofstream ofs_eps(eps_file);
    if (ofs_eps) {
        ofs_eps << "ElementIndex,PartID,EffPlasticStrain\n";

        const auto& solid_data = states.back().solid_data;
        double max_eps = 0;
        size_t max_elem = 0;

        for (size_t i = 0; i < num_elements && i * nv3d + 7 <= solid_data.size(); ++i) {
            double eps = solid_data[i * nv3d + 6];
            int32_t part_id = (i < mesh.solid_parts.size()) ? mesh.solid_parts[i] : 0;

            ofs_eps << std::fixed << std::setprecision(8)
                   << i << "," << part_id << "," << eps << "\n";

            if (eps > max_eps) {
                max_eps = eps;
                max_elem = i;
            }
        }
        ofs_eps.close();
        std::cout << "  Exported: " << eps_file << "\n";
        std::cout << "  Max eff. plastic strain: " << max_eps << " at element " << max_elem << "\n";
    }

    // 4.2 Strain time history per part
    print_subsection("4.2 Strain Time History (per Part)");

    PartAnalyzer part_analyzer(reader);
    if (part_analyzer.initialize()) {
        timer.reset();
        auto histories = part_analyzer.analyze_with_states(states, StressComponent::EFF_PLASTIC);
        std::cout << "  Analysis time: " << timer.elapsed_ms() << " ms\n";

        for (const auto& history : histories) {
            double global_max = *std::max_element(history.max_values.begin(), history.max_values.end());
            std::cout << "  Part " << history.part_id << ": max strain = "
                      << std::fixed << std::setprecision(6) << global_max << "\n";
        }

        std::string strain_file = output_dir + "/strain_history.csv";
        part_analyzer.export_to_csv(histories, strain_file);
        std::cout << "  Exported: " << strain_file << "\n";
    }

    // 4.3 Strain components (if available)
    if (has_strain && nv3d >= 13) {
        print_subsection("4.3 Strain Components (Final State)");

        std::string strain_comp_file = output_dir + "/strain_components_final.csv";
        std::ofstream ofs_sc(strain_comp_file);
        if (ofs_sc) {
            ofs_sc << "ElementIndex,Exx,Eyy,Ezz,Exy,Eyz,Ezx\n";

            const auto& solid_data = states.back().solid_data;
            for (size_t i = 0; i < num_elements && i * nv3d + 13 <= solid_data.size(); ++i) {
                double exx = solid_data[i * nv3d + 7];
                double eyy = solid_data[i * nv3d + 8];
                double ezz = solid_data[i * nv3d + 9];
                double exy = solid_data[i * nv3d + 10];
                double eyz = solid_data[i * nv3d + 11];
                double ezx = solid_data[i * nv3d + 12];

                ofs_sc << std::fixed << std::setprecision(8)
                      << i << "," << exx << "," << eyy << "," << ezz << ","
                      << exy << "," << eyz << "," << ezx << "\n";
            }
            ofs_sc.close();
            std::cout << "  Exported: " << strain_comp_file << "\n";
        }
    }
}

// ============================================================
// 5. Surface Extraction
// ============================================================

void extract_surface_data(D3plotReader& reader, const std::string& output_dir) {
    print_section("5. Surface Extraction");
    Timer timer;

    SurfaceExtractor extractor(reader);
    if (!extractor.initialize()) {
        std::cerr << "Failed to initialize SurfaceExtractor: " << extractor.getLastError() << "\n";
        return;
    }

    // 5.1 Extract all exterior surfaces
    print_subsection("5.1 All Exterior Surfaces");
    auto result = extractor.extractExteriorSurfaces();
    std::cout << "Total exterior faces: " << result.total_exterior_faces << "\n";
    std::cout << "Extraction time: " << timer.elapsed_ms() << " ms\n";

    // Export all faces
    std::string face_file = output_dir + "/exterior_faces.csv";
    std::ofstream ofs_face(face_file);
    if (ofs_face) {
        ofs_face << "FaceIndex,ElementID,PartID,N1,N2,N3,N4,NormalX,NormalY,NormalZ,Area\n";
        for (size_t i = 0; i < result.faces.size(); ++i) {
            const auto& face = result.faces[i];
            ofs_face << std::fixed << std::setprecision(6)
                    << i << "," << face.element_real_id << "," << face.part_id;
            for (auto nid : face.node_real_ids) {
                ofs_face << "," << nid;
            }
            // Pad with 0 if less than 4 nodes
            for (size_t j = face.node_real_ids.size(); j < 4; ++j) {
                ofs_face << ",0";
            }
            ofs_face << "," << face.normal.x << "," << face.normal.y << "," << face.normal.z
                    << "," << face.area << "\n";
        }
        ofs_face.close();
        std::cout << "  Exported: " << face_file << "\n";
    }

    // 5.2 Direction-filtered surfaces
    print_subsection("5.2 Direction-Filtered Surfaces");

    struct DirectionFilter {
        std::string name;
        Vec3 direction;
        double angle;
    };

    std::vector<DirectionFilter> filters = {
        {"bottom_Z-", Vec3(0, 0, -1), 45.0},
        {"top_Z+", Vec3(0, 0, 1), 45.0},
        {"front_X+", Vec3(1, 0, 0), 45.0},
        {"back_X-", Vec3(-1, 0, 0), 45.0},
        {"left_Y-", Vec3(0, -1, 0), 45.0},
        {"right_Y+", Vec3(0, 1, 0), 45.0}
    };

    for (const auto& filter : filters) {
        auto filtered = SurfaceExtractor::filterByDirection(result.faces, filter.direction, filter.angle);
        std::cout << "  " << filter.name << " (angle<" << filter.angle << "): "
                  << filtered.size() << " faces\n";

        // Export filtered faces
        std::string filtered_file = output_dir + "/surface_" + filter.name + ".csv";
        std::ofstream ofs_filt(filtered_file);
        if (ofs_filt) {
            ofs_filt << "ElementID,PartID,NormalX,NormalY,NormalZ,Area\n";
            for (const auto& face : filtered) {
                ofs_filt << std::fixed << std::setprecision(6)
                        << face.element_real_id << "," << face.part_id << ","
                        << face.normal.x << "," << face.normal.y << "," << face.normal.z
                        << "," << face.area << "\n";
            }
            ofs_filt.close();
        }
    }
}

// ============================================================
// 6. SinglePass Time History Analysis
// ============================================================

void extract_singlepass_analysis(D3plotReader& reader, const std::string& output_dir) {
    print_section("6. SinglePassAnalyzer (High-Performance Analysis)");
    Timer timer;

    // Create configuration
    AnalysisConfig config;
    config.d3plot_path = reader.getFilePath();
    config.analyze_stress = true;
    config.analyze_strain = true;
    config.analyze_acceleration = false;

    // Add surface analysis specifications
    config.addSurfaceAnalysis("Bottom (-Z)", Vec3(0, 0, -1), 45.0);
    config.addSurfaceAnalysis("Top (+Z)", Vec3(0, 0, 1), 45.0);

    // Run SinglePassAnalyzer
    SinglePassAnalyzer analyzer(reader);
    analyzer.setUseStateLevelParallel(true);  // Use optimized state-level parallelization

    std::cout << "Running SinglePassAnalyzer (state-level parallel)...\n";
    timer.reset();

    auto result = analyzer.analyze(config, [](size_t current, size_t total, const std::string& msg) {
        if (current % 100 == 0 || current == total) {
            std::cout << "  Progress: " << current << "/" << total << " - " << msg << "\n";
        }
    });

    double elapsed = timer.elapsed_ms();
    std::cout << "Analysis time: " << std::fixed << std::setprecision(2) << elapsed << " ms\n";

    if (!analyzer.wasSuccessful()) {
        std::cerr << "Analysis failed: " << analyzer.getLastError() << "\n";
        return;
    }

    // Print summary
    print_subsection("6.1 Results Summary");
    std::cout << "States analyzed: " << result.metadata.num_states << "\n";
    std::cout << "Time range: " << result.metadata.start_time << " to " << result.metadata.end_time << "\n";
    std::cout << "Parts analyzed: " << result.metadata.analyzed_parts.size() << "\n";

    // 6.2 Stress results
    print_subsection("6.2 Stress Time History");
    if (!result.stress_history.empty()) {
        std::cout << "Parts with stress data: " << result.stress_history.size() << "\n";

        for (const auto& stats : result.stress_history) {
            double gmax = stats.globalMax();
            double tmax = stats.timeOfGlobalMax();
            std::cout << "  Part " << std::setw(3) << stats.part_id
                      << ": max = " << std::fixed << std::setprecision(2) << gmax
                      << " MPa at t=" << std::setprecision(6) << tmax << "\n";
        }

        // Export to CSV
        result.exportStressToCSV(output_dir + "/singlepass_stress.csv");
        std::cout << "  Exported: " << output_dir << "/singlepass_stress.csv\n";
    }

    // 6.3 Strain results
    print_subsection("6.3 Strain Time History");
    if (!result.strain_history.empty()) {
        std::cout << "Parts with strain data: " << result.strain_history.size() << "\n";

        for (const auto& stats : result.strain_history) {
            double gmax = stats.globalMax();
            std::cout << "  Part " << std::setw(3) << stats.part_id
                      << ": max strain = " << std::fixed << std::setprecision(6) << gmax << "\n";
        }

        result.exportStrainToCSV(output_dir + "/singlepass_strain.csv");
        std::cout << "  Exported: " << output_dir << "/singlepass_strain.csv\n";
    }

    // 6.4 Surface stress results
    print_subsection("6.4 Surface Stress Analysis");
    if (!result.surface_analysis.empty()) {
        std::cout << "Surfaces analyzed: " << result.surface_analysis.size() << "\n";

        for (const auto& surf : result.surface_analysis) {
            double max_normal = 0, max_shear = 0;
            for (const auto& pt : surf.data) {
                if (pt.normal_stress_max > max_normal) max_normal = pt.normal_stress_max;
                if (pt.shear_stress_max > max_shear) max_shear = pt.shear_stress_max;
            }
            std::cout << "  " << surf.description << " (" << surf.num_faces << " faces):\n";
            std::cout << "    Max normal stress: " << std::fixed << std::setprecision(2) << max_normal << " MPa\n";
            std::cout << "    Max shear stress:  " << max_shear << " MPa\n";
        }

        result.exportSurfaceToCSV(output_dir + "/singlepass_surface.csv");
        std::cout << "  Exported: " << output_dir << "/singlepass_surface.csv\n";
    }

    // 6.5 Export full JSON
    print_subsection("6.5 Full JSON Export");
    std::string json_file = output_dir + "/analysis_result.json";
    if (result.saveToFile(json_file)) {
        std::cout << "  Exported: " << json_file << "\n";
    }
}

// ============================================================
// 7. Control Data Information
// ============================================================

void print_control_data(D3plotReader& reader) {
    print_section("7. Control Data (File Format Information)");

    const auto& ctrl = reader.get_control_data();
    auto fmt = reader.get_file_format();

    std::cout << "File Information:\n";
    std::cout << "  Title: " << fmt.title << "\n";
    std::cout << "  LS-DYNA Version: " << fmt.version << "\n";
    std::cout << "  Precision: " << (fmt.precision == Precision::DOUBLE ? "Double (8 bytes)" : "Single (4 bytes)") << "\n";
    std::cout << "  Endian: " << (fmt.endian == Endian::LITTLE ? "Little" : "Big") << "\n";

    std::cout << "\nControl Parameters:\n";
    std::cout << "  NDIM = " << ctrl.NDIM << " (dimensionality code)\n";
    std::cout << "  NUMNP = " << ctrl.NUMNP << " (number of nodes)\n";
    std::cout << "  NEL8 = " << ctrl.NEL8 << " (8-node solid elements)\n";
    std::cout << "  NEL2 = " << ctrl.NEL2 << " (2-node beam elements)\n";
    std::cout << "  NEL4 = " << ctrl.NEL4 << " (4-node shell elements)\n";
    std::cout << "  NELT = " << ctrl.NELT << " (thick shell elements)\n";
    std::cout << "  NMMAT = " << ctrl.NMMAT << " (total number of materials/parts)\n";

    std::cout << "\nOutput Flags:\n";
    std::cout << "  IU = " << ctrl.IU << " (displacement output: " << (ctrl.IU ? "YES" : "NO") << ")\n";
    std::cout << "  IV = " << ctrl.IV << " (velocity output: " << (ctrl.IV ? "YES" : "NO") << ")\n";
    std::cout << "  IA = " << ctrl.IA << " (acceleration output: " << (ctrl.IA ? "YES" : "NO") << ")\n";
    std::cout << "  IT = " << ctrl.IT << " (temperature output: " << (ctrl.IT ? "YES" : "NO") << ")\n";
    std::cout << "  ISTRN = " << ctrl.ISTRN << " (strain output: " << (ctrl.ISTRN ? "YES" : "NO") << ")\n";

    std::cout << "\nElement Data:\n";
    std::cout << "  NV3D = " << ctrl.NV3D << " (values per solid element)\n";
    std::cout << "  NV2D = " << ctrl.NV2D << " (values per shell element)\n";
    std::cout << "  NV1D = " << ctrl.NV1D << " (values per beam element)\n";
    std::cout << "  NGLBV = " << ctrl.NGLBV << " (global variables per state)\n";
}

// ============================================================
// Main Function
// ============================================================

int main(int argc, char* argv[]) {
    std::cout << "============================================================\n";
    std::cout << "KooD3plot Full Extraction Example\n";
    std::cout << "Comprehensive demonstration of ALL data extraction features\n";
    std::cout << "============================================================\n";

    if (argc < 2) {
        std::cerr << "\nUsage: " << argv[0] << " <d3plot_path> [output_dir]\n\n";
        std::cerr << "This example extracts and exports:\n";
        std::cerr << "  - Mesh data (nodes, elements, parts)\n";
        std::cerr << "  - State data (time, displacements, velocities, accelerations)\n";
        std::cerr << "  - Stress data (6 components, Von Mises, pressure)\n";
        std::cerr << "  - Strain data (effective plastic, 6 strain components)\n";
        std::cerr << "  - Surface extraction (exterior faces, direction filtering)\n";
        std::cerr << "  - Time history analysis (SinglePassAnalyzer)\n";
        std::cerr << "  - Control data (file format information)\n";
        return 1;
    }

    std::string d3plot_path = argv[1];
    std::string output_dir = (argc >= 3) ? argv[2] : "./full_extraction_output";

    // Create output directory
    try {
        fs::create_directories(output_dir);
    } catch (const std::exception& e) {
        std::cerr << "Failed to create output directory: " << e.what() << "\n";
        return 1;
    }

    std::cout << "\nInput:  " << d3plot_path << "\n";
    std::cout << "Output: " << output_dir << "\n";

    // Open d3plot file
    Timer total_timer;
    D3plotReader reader(d3plot_path);

    if (reader.open() != ErrorCode::SUCCESS) {
        std::cerr << "Failed to open d3plot file: " << d3plot_path << "\n";
        return 1;
    }

    std::cout << "File opened successfully.\n";

    // Run all extraction functions
    try {
        // 1. Control data (file info)
        print_control_data(reader);

        // 2. Mesh data
        extract_mesh_data(reader, output_dir);

        // 3. State data (displacements, velocities, accelerations)
        extract_state_data(reader, output_dir);

        // 4. Stress data
        extract_stress_data(reader, output_dir);

        // 5. Strain data
        extract_strain_data(reader, output_dir);

        // 6. Surface extraction
        extract_surface_data(reader, output_dir);

        // 7. SinglePassAnalyzer (high-performance analysis)
        extract_singlepass_analysis(reader, output_dir);

    } catch (const std::exception& e) {
        std::cerr << "\nError during extraction: " << e.what() << "\n";
        return 1;
    }

    // Final summary
    print_section("Summary");
    std::cout << "Total execution time: " << std::fixed << std::setprecision(2)
              << total_timer.elapsed_ms() / 1000.0 << " seconds\n";
    std::cout << "All data exported to: " << output_dir << "\n";
    std::cout << "\nExported files:\n";

    // List exported files
    for (const auto& entry : fs::directory_iterator(output_dir)) {
        std::cout << "  " << entry.path().filename().string() << "\n";
    }

    std::cout << "\n============================================================\n";
    std::cout << "Full Extraction Complete!\n";
    std::cout << "============================================================\n";

    return 0;
}
