/**
 * @file unified_analyzer.cpp
 * @brief Unified CLI for d3plot analysis with YAML configuration
 * @author KooD3plot Development Team
 * @date 2025-12-04
 *
 * This tool uses UnifiedAnalyzer with job-based YAML configuration.
 *
 * Usage:
 *   ./unified_analyzer --config analysis.yaml
 *   ./unified_analyzer --config analysis.yaml --threads 4
 *   ./unified_analyzer --config analysis.yaml --analysis-only
 *   ./unified_analyzer --generate-config > my_config.yaml
 */

#include "kood3plot/analysis/UnifiedAnalyzer.hpp"
#include "kood3plot/analysis/UnifiedConfigParser.hpp"
#include <iostream>
#include <fstream>
#include <filesystem>
#include <iomanip>
#include <chrono>
#include <ctime>
#include <sstream>

#ifdef _OPENMP
#include <omp.h>
#endif

namespace fs = std::filesystem;
using namespace kood3plot;
using namespace kood3plot::analysis;

/**
 * @brief Write part time series to CSV
 */
void writePartCSV(const std::string& filepath, const PartTimeSeriesStats& stats) {
    std::ofstream ofs(filepath);
    if (!ofs) {
        std::cerr << "Failed to open " << filepath << "\n";
        return;
    }

    ofs << "Time,Max_" << stats.quantity << ",Min_" << stats.quantity
        << ",Avg_" << stats.quantity << ",Max_Element_ID,Min_Element_ID\n";

    for (const auto& point : stats.data) {
        ofs << std::fixed << std::setprecision(6)
            << point.time << ","
            << point.max_value << ","
            << point.min_value << ","
            << point.avg_value << ","
            << point.max_element_id << ","
            << point.min_element_id << "\n";
    }

    ofs.close();
    std::cout << "  Written: " << filepath << " (" << stats.data.size() << " states)\n";
}

/**
 * @brief Write motion analysis to CSV
 */
void writeMotionCSV(const std::string& filepath, const PartMotionStats& stats) {
    std::ofstream ofs(filepath);
    if (!ofs) {
        std::cerr << "Failed to open " << filepath << "\n";
        return;
    }

    ofs << "Time,Avg_Disp_X,Avg_Disp_Y,Avg_Disp_Z,Avg_Disp_Mag,"
        << "Avg_Vel_X,Avg_Vel_Y,Avg_Vel_Z,Avg_Vel_Mag,"
        << "Avg_Acc_X,Avg_Acc_Y,Avg_Acc_Z,Avg_Acc_Mag,"
        << "Max_Disp_Mag,Max_Disp_Node_ID\n";

    for (const auto& point : stats.data) {
        ofs << std::fixed << std::setprecision(6)
            << point.time << ","
            << point.avg_displacement.x << ","
            << point.avg_displacement.y << ","
            << point.avg_displacement.z << ","
            << point.avg_displacement_magnitude << ","
            << point.avg_velocity.x << ","
            << point.avg_velocity.y << ","
            << point.avg_velocity.z << ","
            << point.avg_velocity_magnitude << ","
            << point.avg_acceleration.x << ","
            << point.avg_acceleration.y << ","
            << point.avg_acceleration.z << ","
            << point.avg_acceleration_magnitude << ","
            << point.max_displacement_magnitude << ","
            << point.max_displacement_node_id << "\n";
    }

    ofs.close();
    std::cout << "  Written: " << filepath << " (" << stats.data.size() << " states)\n";
}

/**
 * @brief Write surface analysis to CSV
 */
void writeSurfaceCSV(const std::string& filepath, const SurfaceAnalysisStats& stats) {
    std::ofstream ofs(filepath);
    if (!ofs) {
        std::cerr << "Failed to open " << filepath << "\n";
        return;
    }

    ofs << "Time,Normal_Max,Normal_Min,Normal_Avg,Normal_Max_ElemID,"
        << "Shear_Max,Shear_Avg,Shear_Max_ElemID,"
        << "VonMises_Max,VonMises_Min,VonMises_Avg,VonMises_Max_ElemID,"
        << "MaxPrincipal_Max,MaxPrincipal_Min,MaxPrincipal_Avg,MaxPrincipal_Max_ElemID,"
        << "MinPrincipal_Max,MinPrincipal_Min,MinPrincipal_Avg,MinPrincipal_Min_ElemID\n";

    for (const auto& point : stats.data) {
        ofs << std::fixed << std::setprecision(6)
            << point.time << ","
            << point.normal_stress_max << ","
            << point.normal_stress_min << ","
            << point.normal_stress_avg << ","
            << point.normal_stress_max_element_id << ","
            << point.shear_stress_max << ","
            << point.shear_stress_avg << ","
            << point.shear_stress_max_element_id << ","
            << point.von_mises_max << ","
            << point.von_mises_min << ","
            << point.von_mises_avg << ","
            << point.von_mises_max_element_id << ","
            << point.max_principal_max << ","
            << point.max_principal_min << ","
            << point.max_principal_avg << ","
            << point.max_principal_max_element_id << ","
            << point.min_principal_max << ","
            << point.min_principal_min << ","
            << point.min_principal_avg << ","
            << point.min_principal_min_element_id << "\n";
    }

    ofs.close();
    std::cout << "  Written: " << filepath << " (" << stats.data.size() << " states)\n";
}

/**
 * @brief Write surface strain to CSV
 */
void writeSurfaceStrainCSV(const std::string& filepath, const SurfaceStrainStats& stats) {
    std::ofstream ofs(filepath);
    if (!ofs) {
        std::cerr << "Failed to open " << filepath << "\n";
        return;
    }

    // 변형률 텐서가 없으면 수직/전단·주변형률·ε_vm 컬럼은 전부 0 이다.
    // '0 이었음' 으로 오독하지 않도록 헤더 앞에 사유를 주석으로 남긴다.
    if (!stats.has_strain_tensor) {
        ofs << "# 변형률 텐서 미기록 — 아래 EffPlastic_* 만 유효\n";
        if (!stats.note.empty()) ofs << "# " << stats.note << "\n";
    }

    ofs << "Time,Normal_Max,Normal_Min,Normal_Avg,Normal_Max_ElemID,"
        << "Shear_Max,Shear_Avg,Shear_Max_ElemID,"
        << "MaxPrincipal_Max,MaxPrincipal_Min,MaxPrincipal_Avg,MaxPrincipal_Max_ElemID,"
        << "MinPrincipal_Max,MinPrincipal_Min,MinPrincipal_Avg,MinPrincipal_Min_ElemID,"
        << "VMStrain_Max,VMStrain_Min,VMStrain_Avg,VMStrain_Max_ElemID,"
        << "EffPlastic_Max,EffPlastic_Min,EffPlastic_Avg,EffPlastic_Max_ElemID\n";

    // 텐서가 없으면 텐서 기반 컬럼은 빈 칸 — 0 으로 채우면 '변형률 0' 으로
    // 읽힌다. eff_plastic 만 항상 유효하다.
    const bool T = stats.has_strain_tensor;
    auto tnum = [&ofs, T](double v) { if (T) ofs << v; ofs << ","; };
    auto tid  = [&ofs, T](int32_t v) { if (T) ofs << v; ofs << ","; };

    for (const auto& point : stats.data) {
        ofs << std::scientific << std::setprecision(6) << point.time << ",";
        tnum(point.normal_strain_max);
        tnum(point.normal_strain_min);
        tnum(point.normal_strain_avg);
        tid (point.normal_strain_max_element_id);
        tnum(point.shear_strain_max);
        tnum(point.shear_strain_avg);
        tid (point.shear_strain_max_element_id);
        tnum(point.max_principal_strain_max);
        tnum(point.max_principal_strain_min);
        tnum(point.max_principal_strain_avg);
        tid (point.max_principal_strain_max_element_id);
        tnum(point.min_principal_strain_max);
        tnum(point.min_principal_strain_min);
        tnum(point.min_principal_strain_avg);
        tid (point.min_principal_strain_min_element_id);
        tnum(point.vm_strain_max);
        tnum(point.vm_strain_min);
        tnum(point.vm_strain_avg);
        tid (point.vm_strain_max_element_id);
        ofs << point.eff_plastic_strain_max << ","
            << point.eff_plastic_strain_min << ","
            << point.eff_plastic_strain_avg << ","
            << point.eff_plastic_strain_max_element_id << "\n";
    }

    ofs.close();
    std::cout << "  Written: " << filepath << " (" << stats.data.size() << " states)\n";
}

/**
 * @brief Write element quality to CSV
 */
void writeQualityCSV(const std::string& filepath, const ElementQualityStats& stats) {
    std::ofstream ofs(filepath);
    if (!ofs) {
        std::cerr << "Failed to open " << filepath << "\n";
        return;
    }

    // 미산출 지표는 **빈 칸**으로 남긴다. 예전에는 기본값(Jacobian 1.0,
    // 뒤틀림/왜곡도 0.0)이 그대로 찍혀서 CSV 만 보면 '완벽한 메시' 로 읽혔다.
    // JSON 쪽에는 *_measured 플래그가 있지만 CSV 에는 실을 자리가 없어
    // 빈 칸이 유일하게 정직한 표기다.
    const bool m_ar  = stats.aspect_measured;
    const bool m_jac = stats.jacobian_measured;
    const bool m_sk  = stats.skewness_measured;
    const bool m_wp  = stats.warpage_measured;
    const bool m_vol = stats.volume_measured;
    if (!(m_ar && m_jac && m_sk && m_wp && m_vol)) {
        ofs << "# 미산출 지표는 빈 칸:";
        if (!m_ar)  ofs << " AspectRatio";
        if (!m_jac) ofs << " Jacobian";
        if (!m_sk)  ofs << " Skewness";
        if (!m_wp)  ofs << " Warpage";
        if (!m_vol) ofs << " VolumeChange";
        ofs << " (축퇴 요소뿐이거나 해당 요소 종류가 없음)\n";
    }

    ofs << "Time,AspectRatio_Max,AspectRatio_Avg,Jacobian_Min,Jacobian_Avg,"
        << "Skewness_Max,Skewness_Avg,Warpage_Max,Warpage_Avg,"
        << "VolumeChange_Min,VolumeChange_Max,"
        << "N_NegativeJacobian,N_HighAspectRatio,"
        << "Worst_AR_Elem,Worst_Jac_Elem,Worst_Skew_Elem,Worst_Warp_Elem,Worst_Vol_Elem\n";

    auto num = [&ofs](bool measured, double v) {
        if (measured) ofs << v;
        ofs << ",";
    };

    for (const auto& tp : stats.data) {
        ofs << std::fixed << std::setprecision(6) << tp.time << ",";
        num(tp.aspect_measured,   tp.aspect_ratio_max);
        num(tp.aspect_measured,   tp.aspect_ratio_avg);
        num(tp.jacobian_measured, tp.jacobian_min);
        num(tp.jacobian_measured, tp.jacobian_avg);
        num(tp.skewness_measured, tp.skewness_max);
        num(tp.skewness_measured, tp.skewness_avg);
        num(tp.warpage_measured,  tp.warpage_max);
        num(tp.warpage_measured,  tp.warpage_avg);
        num(tp.volume_measured,   tp.volume_change_min);
        num(tp.volume_measured,   tp.volume_change_max);
        ofs << tp.n_negative_jacobian << "," << tp.n_high_aspect << ","
            << tp.worst_aspect_ratio_elem << "," << tp.worst_jacobian_elem << ","
            << tp.worst_skewness_elem << "," << tp.worst_warpage_elem << ","
            << tp.worst_volume_change_elem << "\n";
    }

    ofs.close();
    std::cout << "  Written: " << filepath << " (" << stats.data.size() << " states)\n";
}

/**
 * @brief Export results to files
 */
void exportResults(const ExtendedAnalysisResult& result, const UnifiedConfig& config) {
    std::string output_dir = config.output_directory;
    if (output_dir.empty()) {
        output_dir = "./analysis_output";
    }

    // Create subdirectories
    std::string stress_dir = output_dir + "/stress";
    std::string strain_dir = output_dir + "/strain";
    std::string motion_dir = output_dir + "/motion";
    std::string surface_dir = output_dir + "/surface";

    fs::create_directories(stress_dir);
    fs::create_directories(strain_dir);
    fs::create_directories(motion_dir);
    fs::create_directories(surface_dir);

    // Export stress history
    if (config.output_csv && !result.stress_history.empty()) {
        std::cout << "\nExporting stress history:\n";
        for (const auto& stats : result.stress_history) {
            std::string filename = stress_dir + "/part_" + std::to_string(stats.part_id) + "_von_mises.csv";
            writePartCSV(filename, stats);
        }
    }

    // Export principal stress history
    if (config.output_csv && !result.max_principal_history.empty()) {
        std::cout << "\nExporting max principal stress history:\n";
        for (const auto& stats : result.max_principal_history) {
            std::string filename = stress_dir + "/part_" + std::to_string(stats.part_id) + "_max_principal_stress.csv";
            writePartCSV(filename, stats);
        }
    }
    if (config.output_csv && !result.min_principal_history.empty()) {
        std::cout << "\nExporting min principal stress history:\n";
        for (const auto& stats : result.min_principal_history) {
            std::string filename = stress_dir + "/part_" + std::to_string(stats.part_id) + "_min_principal_stress.csv";
            writePartCSV(filename, stats);
        }
    }

    // Export strain history
    if (config.output_csv && !result.strain_history.empty()) {
        std::cout << "\nExporting strain history:\n";
        for (const auto& stats : result.strain_history) {
            std::string filename = strain_dir + "/part_" + std::to_string(stats.part_id) + "_eff_plastic_strain.csv";
            writePartCSV(filename, stats);
        }
    }

    // von Mises 등가 변형률 (변형률 텐서가 있는 덱에서만)
    if (config.output_csv && !result.vm_strain_history.empty()) {
        std::cout << "\nExporting von Mises strain history:\n";
        for (const auto& stats : result.vm_strain_history) {
            std::string filename = strain_dir + "/part_" + std::to_string(stats.part_id) + "_von_mises_strain.csv";
            writePartCSV(filename, stats);
        }
    }

    // Export principal strain history (conditional - only when strain tensor exists in d3plot)
    if (config.output_csv && !result.max_principal_strain_history.empty()) {
        std::cout << "\nExporting principal strain history:\n";
        for (const auto& stats : result.max_principal_strain_history) {
            std::string filename = strain_dir + "/part_" + std::to_string(stats.part_id) + "_max_principal_strain.csv";
            writePartCSV(filename, stats);
        }
        for (const auto& stats : result.min_principal_strain_history) {
            std::string filename = strain_dir + "/part_" + std::to_string(stats.part_id) + "_min_principal_strain.csv";
            writePartCSV(filename, stats);
        }
    }

    // Export motion analysis
    if (config.output_csv && !result.motion_analysis.empty()) {
        std::cout << "\nExporting motion analysis:\n";
        for (const auto& stats : result.motion_analysis) {
            std::string filename = motion_dir + "/part_" + std::to_string(stats.part_id) + "_motion.csv";
            writeMotionCSV(filename, stats);
        }
    }

    // Export Custom Report set results — set_reports/<safe_name>/{metrics.json, series CSV}
    if (!result.set_report_results.empty()) {
        std::string sets_root = output_dir + "/set_reports";
        std::error_code ec;
        fs::remove_all(sets_root, ec);   // 재실행 시 낡은 산출물 제거
        fs::create_directories(sets_root);
        std::cout << "\nExporting set reports:\n";

        auto safe = [](const std::string& s2) {
            std::string out;
            for (char c : s2) {
                out.push_back((std::isalnum(static_cast<unsigned char>(c)) ||
                               c == '-' || c == '_') ? c : '_');
            }
            return out.empty() ? std::string("set") : out;
        };

        for (const auto& sr : result.set_report_results) {
            const std::string dir = sets_root + "/" + safe(sr.name);
            fs::create_directories(dir);

            // metrics.json — Python 보고서가 단독으로 읽는 per-set 파일
            {
                std::ofstream mj(dir + "/metrics.json");
                mj << "{\n  \"name\": \"" << sr.name << "\",\n";
                mj << "  \"set_type\": \"" << sr.set_type << "\",\n";
                mj << "  \"set_id\": " << sr.set_id << ",\n";
                mj << "  \"title\": \"" << sr.title << "\",\n";
                mj << "  \"resolved_parts\": [";
                for (size_t i = 0; i < sr.resolved_parts.size(); ++i) {
                    if (i) mj << ", ";
                    mj << sr.resolved_parts[i];
                }
                mj << "],\n  \"missing_parts\": [";
                for (size_t i = 0; i < sr.missing_parts.size(); ++i) {
                    if (i) mj << ", ";
                    mj << sr.missing_parts[i];
                }
                mj << "],\n  \"notes\": [";
                for (size_t i = 0; i < sr.notes.size(); ++i) {
                    if (i) mj << ", ";
                    mj << "\"" << sr.notes[i] << "\"";
                }
                mj << "],\n  \"fields\": [";
                for (size_t i = 0; i < sr.fields.size(); ++i) {
                    const auto& f = sr.fields[i];
                    if (i) mj << ",";
                    mj << "\n    {\"field\": \"" << f.field << "\", \"measured\": "
                       << (f.measured ? "true" : "false");
                    if (f.measured) {
                        mj << std::setprecision(9)
                           << ", \"peak\": " << f.peak
                           << ", \"peak_time\": " << f.peak_time
                           << ", \"peak_element_id\": " << f.peak_element_id
                           << ", \"peak_part_id\": " << f.peak_part_id;
                    } else {
                        mj << ", \"note\": \"" << f.note << "\"";
                    }
                    mj << "}";
                }
                mj << "\n  ]\n}\n";
            }

            // 필드별 시계열 CSV (원해상도)
            for (const auto& f : sr.fields) {
                if (!f.measured) continue;
                std::ofstream cf(dir + "/" + f.field + ".csv");
                cf << "Time," << f.field << "\n";
                cf << std::setprecision(9);
                for (size_t i = 0; i < f.times.size(); ++i) {
                    cf << f.times[i] << "," << f.values[i] << "\n";
                }
            }
            std::cout << "  Written: " << dir << "/ (필드 " << sr.fields.size() << "개)\n";
        }
    }

    // Export beam resultants — 축력은 부호가 의미이므로 max/min 을 함께 낸다
    if (config.output_csv && !result.beam_analysis.empty()) {
        std::string beam_dir = output_dir + "/beam";
        fs::create_directories(beam_dir);
        std::cout << "\nExporting beam resultants:\n";
        for (const auto& stats : result.beam_analysis) {
            std::string filename = beam_dir + "/part_" + std::to_string(stats.part_id)
                                 + "_" + stats.quantity + ".csv";
            writePartCSV(filename, stats);
        }
    }

    // Export surface stress
    if (config.output_csv && !result.surface_analysis.empty()) {
        std::cout << "\nExporting surface stress:\n";
        for (const auto& stats : result.surface_analysis) {
            std::string safe_name = stats.description;
            for (char& c : safe_name) {
                if (c == ' ' || c == '/' || c == '\\' || c == '(' || c == ')') c = '_';
            }
            std::string filename = surface_dir + "/" + safe_name + "_stress.csv";
            writeSurfaceCSV(filename, stats);
        }
    }

    // Export surface strain
    if (config.output_csv && !result.surface_strain_analysis.empty()) {
        std::cout << "\nExporting surface strain:\n";
        for (const auto& stats : result.surface_strain_analysis) {
            std::string safe_name = stats.description;
            for (char& c : safe_name) {
                if (c == ' ' || c == '/' || c == '\\' || c == '(' || c == ')') c = '_';
            }
            std::string filename = surface_dir + "/" + safe_name + "_strain.csv";
            writeSurfaceStrainCSV(filename, stats);
        }
    }

    // Export element quality
    if (config.output_csv && !result.element_quality.empty()) {
        std::string quality_dir = output_dir + "/quality";
        fs::create_directories(quality_dir);
        std::cout << "\nExporting element quality:\n";
        for (const auto& stats : result.element_quality) {
            std::string filename = quality_dir + "/part_" + std::to_string(stats.part_id) + "_quality.csv";
            writeQualityCSV(filename, stats);
        }
    }

    // Export peak element tensor histories (stress ellipsoid data)
    if (config.output_csv && !result.peak_element_tensors.empty()) {
        std::string tensor_dir = output_dir + "/stress/tensor";
        fs::create_directories(tensor_dir);
        std::cout << "\nExporting peak element tensor histories:\n";
        for (const auto& hist : result.peak_element_tensors) {
            std::string filename = tensor_dir + "/part_" + std::to_string(hist.part_id)
                                 + "_elem_" + std::to_string(hist.element_id)
                                 + "_" + hist.reason + ".csv";
            std::ofstream file(filename);
            if (file) {
                file << "Time,sxx,syy,szz,sxy,syz,szx\n";
                file << std::fixed << std::setprecision(8);
                for (size_t i = 0; i < hist.time.size(); ++i) {
                    file << hist.time[i] << ","
                         << hist.sxx[i] << "," << hist.syy[i] << "," << hist.szz[i] << ","
                         << hist.sxy[i] << "," << hist.syz[i] << "," << hist.szx[i] << "\n";
                }
                std::cout << "  " << filename << " (" << hist.time.size() << " states)\n";
            }
        }
    }

    // Export JSON summary (use extended JSON to include motion/quality data)
    if (config.output_json) {
        std::string json_path = output_dir + "/analysis_result.json";
        if (result.saveExtendedToFile(json_path)) {
            std::cout << "\nJSON summary: " << json_path << "\n";
        }
    }
}

// ============================================================
// Recursive Analysis Functions
// ============================================================

/**
 * @brief Find all directories containing d3plot files
 * @param root_dir Root directory to search
 * @return Vector of directory paths containing d3plot
 */
std::vector<fs::path> findD3plotDirectories(const fs::path& root_dir) {
    std::vector<fs::path> result;

    try {
        for (const auto& entry : fs::recursive_directory_iterator(root_dir,
                fs::directory_options::follow_directory_symlink |
                fs::directory_options::skip_permission_denied)) {
            if (entry.is_regular_file() || entry.is_symlink()) {
                std::string filename = entry.path().filename().string();
                // Look for base d3plot file (not d3plot01, d3plot02, etc.)
                if (filename == "d3plot") {
                    result.push_back(entry.path().parent_path());
                }
            }
        }
    } catch (const std::exception& e) {
        std::cerr << "Error scanning directories: " << e.what() << "\n";
    }

    return result;
}

/**
 * @brief Generate unique result folder name from d3plot path
 * @param d3plot_dir Directory containing d3plot
 * @param root_dir Root directory for relative path calculation
 * @return Sanitized folder name
 */
std::string generateResultFolderName(const fs::path& d3plot_dir, const fs::path& root_dir) {
    // Resolve symlinks and get canonical paths
    fs::path canonical_dir, canonical_root;
    try {
        canonical_dir = fs::canonical(d3plot_dir);
        canonical_root = fs::canonical(root_dir);
    } catch (...) {
        canonical_dir = d3plot_dir;
        canonical_root = root_dir;
    }

    // Get relative path from root
    fs::path rel_path = fs::relative(canonical_dir, canonical_root);

    // Convert to string — keep '/' for nested directory structure, only sanitize spaces
    std::string name = rel_path.string();
    for (char& c : name) {
        if (c == '\\') {
            c = '/';
        } else if (c == ' ') {
            c = '_';
        }
    }

    // Remove leading ".._" patterns
    while (name.size() >= 3 && name.substr(0, 3) == ".._") {
        name = name.substr(3);
    }

    return name;
}

/**
 * @brief Check if analysis was already completed for a d3plot
 * @param result_dir Result directory to check
 * @return true if analysis_result.json exists
 */
bool isAnalysisCompleted(const fs::path& result_dir) {
    return fs::exists(result_dir / "analysis_result.json");
}

/**
 * @brief Save analysis metadata for tracking
 * @param result_dir Result directory
 * @param d3plot_path Original d3plot path
 * @param config_path Config file used
 */
void saveAnalysisMetadata(const fs::path& result_dir,
                          const fs::path& d3plot_path,
                          const std::string& config_path) {
    std::ofstream ofs(result_dir / ".analysis_info");
    if (ofs) {
        auto now = std::chrono::system_clock::now();
        auto time_t = std::chrono::system_clock::to_time_t(now);

        ofs << "d3plot_path: " << d3plot_path.string() << "\n";
        ofs << "config_file: " << config_path << "\n";
        ofs << "analyzed_at: " << std::ctime(&time_t);
    }
}

/**
 * @brief Run analysis on a single d3plot with specified output directory
 * @return true if analysis succeeded
 */
bool runSingleAnalysis(const fs::path& d3plot_path,
                       const fs::path& result_dir,
                       UnifiedConfig base_config,
                       bool analysis_only,
                       const std::string& config_path) {
    // Update config for this specific d3plot
    base_config.d3plot_path = d3plot_path.string();
    base_config.output_directory = result_dir.string();

    // Create output directory
    try {
        fs::create_directories(result_dir);
    } catch (const std::exception& e) {
        std::cerr << "Failed to create output directory: " << e.what() << "\n";
        return false;
    }

    // Run analyzer
    UnifiedAnalyzer analyzer;
    auto start_time = std::chrono::high_resolution_clock::now();

    auto result = analyzer.analyze(base_config, [](const std::string& msg) {
        std::cout << "  " << msg << "\n";
    });

    auto end_time = std::chrono::high_resolution_clock::now();
    double elapsed = std::chrono::duration<double>(end_time - start_time).count();

    if (!analyzer.wasSuccessful()) {
        std::cerr << "Analysis failed: " << analyzer.getLastError() << "\n";
        return false;
    }

    // Export results
    exportResults(result, base_config);

    // Run render jobs if not analysis_only
    if (!analysis_only && base_config.hasRenderJobs()) {
        D3plotReader render_reader(d3plot_path.string());
        auto error = render_reader.open();
        if (error == ErrorCode::SUCCESS) {
            UnifiedAnalyzer render_analyzer;
            render_analyzer.processRenderJobs(render_reader, base_config,
                [](const std::string& msg) {
                    std::cout << "  " << msg << "\n";
                });
        }
    }

    // Run section view jobs if not analysis_only and not already done in analyze()
    if (!analysis_only && base_config.hasSectionViews() && !analyzer.sectionViewsDone()) {
        D3plotReader sv_reader(d3plot_path.string());
        auto error = sv_reader.open();
        if (error == ErrorCode::SUCCESS) {
            auto sv_states = sv_reader.read_all_states_parallel(base_config.num_threads);
            UnifiedAnalyzer sv_analyzer;
            sv_analyzer.processSectionViews(sv_reader, base_config, sv_states,
                [](const std::string& msg) {
                    std::cout << "  " << msg << "\n";
                });
        }
    }

    // Save metadata
    saveAnalysisMetadata(result_dir, d3plot_path, config_path);

    std::cout << "  Completed in " << std::fixed << std::setprecision(2)
              << elapsed << " seconds\n";

    return true;
}

/**
 * @brief Run recursive analysis on all d3plot files under root directory
 */
int runRecursiveAnalysis(const fs::path& root_dir,
                         const fs::path& output_root,
                         const UnifiedConfig& base_config,
                         const std::string& config_path,
                         bool analysis_only,
                         bool skip_existing) {
    std::cout << "\n=============================================================\n";
    std::cout << "Recursive Analysis Mode\n";
    std::cout << "=============================================================\n";
    std::cout << "Scanning: " << root_dir << "\n";
    std::cout << "Output to: " << output_root << "\n";
    std::cout << "Skip existing: " << (skip_existing ? "yes" : "no") << "\n\n";

    // Find all d3plot directories
    auto d3plot_dirs = findD3plotDirectories(root_dir);

    if (d3plot_dirs.empty()) {
        std::cout << "No d3plot files found.\n";
        return 0;
    }

    std::cout << "Found " << d3plot_dirs.size() << " d3plot file(s):\n";
    for (const auto& dir : d3plot_dirs) {
        std::cout << "  - " << fs::relative(dir, root_dir) << "\n";
    }
    std::cout << "\n";

    // Create output root directory
    try {
        fs::create_directories(output_root);
    } catch (const std::exception& e) {
        std::cerr << "Failed to create output directory: " << e.what() << "\n";
        return 1;
    }

    // Process each d3plot
    int success_count = 0;
    int skip_count = 0;
    int fail_count = 0;

    for (size_t i = 0; i < d3plot_dirs.size(); ++i) {
        const auto& d3plot_dir = d3plot_dirs[i];
        fs::path d3plot_path = d3plot_dir / "d3plot";

        // Generate result folder name
        std::string folder_name = generateResultFolderName(d3plot_dir, root_dir);
        fs::path result_dir = output_root / folder_name;

        std::cout << "[" << (i + 1) << "/" << d3plot_dirs.size() << "] "
                  << fs::relative(d3plot_dir, root_dir) << "\n";

        // Check if already analyzed
        if (skip_existing && isAnalysisCompleted(result_dir)) {
            std::cout << "  Skipped (already analyzed)\n\n";
            ++skip_count;
            continue;
        }

        // Run analysis
        if (runSingleAnalysis(d3plot_path, result_dir, base_config, analysis_only, config_path)) {
            ++success_count;
        } else {
            ++fail_count;
        }
        std::cout << "\n";
    }

    // Summary
    std::cout << "=============================================================\n";
    std::cout << "Recursive Analysis Complete\n";
    std::cout << "=============================================================\n";
    std::cout << "Total: " << d3plot_dirs.size() << "\n";
    std::cout << "Success: " << success_count << "\n";
    std::cout << "Skipped: " << skip_count << "\n";
    std::cout << "Failed: " << fail_count << "\n";
    std::cout << "Results saved to: " << output_root << "\n";
    std::cout << "=============================================================\n";

    return (fail_count > 0) ? 1 : 0;
}

/**
 * @brief Print usage
 */
void printUsage(const char* prog_name) {
    std::cout << "=============================================================\n";
    std::cout << "KooD3plot Unified Analyzer (v2.0)\n";
    std::cout << "=============================================================\n\n";

    std::cout << "Usage:\n";
    std::cout << "  " << prog_name << " --config <yaml_file> [options]\n";
    std::cout << "  " << prog_name << " --recursive <dir> --config <yaml_file> [options]\n";
    std::cout << "  " << prog_name << " --generate-config\n\n";

    std::cout << "Options:\n";
    std::cout << "  --config <file>     Load configuration from YAML file\n";
    std::cout << "  --recursive <dir>   Scan directory recursively for d3plot files\n";
    std::cout << "  --output <dir>      Output directory for recursive mode (default: ./analysis_results)\n";
    std::cout << "  --skip-existing     Skip already analyzed d3plot folders\n";
    std::cout << "  --threads N         Set number of OpenMP threads (0=auto)\n";
    std::cout << "  --analysis-only     Run only analysis jobs (skip rendering)\n";
    std::cout << "  --render-only       Run only render jobs (skip analysis)\n";
    std::cout << "  --generate-config   Print example YAML configuration\n";
    std::cout << "  --help              Show this help message\n\n";

    std::cout << "Single Analysis Mode:\n";
    std::cout << "  Uses d3plot path from YAML config file.\n\n";

    std::cout << "Recursive Analysis Mode:\n";
    std::cout << "  Scans specified directory for all d3plot files in subdirectories.\n";
    std::cout << "  Applies same analysis config to each d3plot.\n";
    std::cout << "  Creates result folders mirroring source directory structure.\n";
    std::cout << "  Use --skip-existing for incremental analysis.\n\n";

    std::cout << "Features:\n";
    std::cout << "  - Job-based analysis configuration\n";
    std::cout << "  - Von Mises stress, effective plastic strain\n";
    std::cout << "  - Motion analysis (displacement, velocity, acceleration)\n";
    std::cout << "  - Surface stress and strain analysis\n";
    std::cout << "  - Section view rendering (with LSPrePost)\n";
    std::cout << "  - CSV and JSON output\n";
    std::cout << "  - Recursive batch processing\n\n";

    std::cout << "Examples:\n";
    std::cout << "  # Single analysis\n";
    std::cout << "  " << prog_name << " --config my_analysis.yaml\n\n";

    std::cout << "  # Recursive analysis of all simulations\n";
    std::cout << "  " << prog_name << " --recursive /data/simulations --config common.yaml\n\n";

    std::cout << "  # Incremental analysis (skip already done)\n";
    std::cout << "  " << prog_name << " --recursive /data/simulations --config common.yaml --skip-existing\n\n";

    std::cout << "  # Custom output directory\n";
    std::cout << "  " << prog_name << " --recursive /data/sims --config common.yaml --output /results\n";
}

/**
 * @brief Print summary
 */
void printSummary(const ExtendedAnalysisResult& result, const UnifiedConfig& config, double elapsed_seconds) {
    std::cout << "\n=============================================================\n";
    std::cout << "Analysis Complete!\n";
    std::cout << "=============================================================\n";
    std::cout << "Metadata:\n";
    std::cout << "  States analyzed: " << result.metadata.num_states << "\n";
    std::cout << "  Time range: " << result.metadata.start_time << " to "
              << result.metadata.end_time << "\n";
    std::cout << "  Parts analyzed: " << result.metadata.analyzed_parts.size() << "\n";
    std::cout << "  Elapsed time: " << std::fixed << std::setprecision(2) << elapsed_seconds << " seconds\n\n";

    std::cout << "Results saved to: " << config.output_directory << "\n";
    std::cout << "  - Stress history: " << result.stress_history.size() << " parts\n";
    std::cout << "  - Strain history: " << result.strain_history.size() << " parts\n";
    std::cout << "  - Motion analysis: " << result.motion_analysis.size() << " parts\n";
    std::cout << "  - Beam resultants: " << result.beam_analysis.size() << " series\n";
    std::cout << "  - Set reports: " << result.set_report_results.size() << " sets\n";
    std::cout << "  - Surface stress: " << result.surface_analysis.size() << " surfaces\n";
    std::cout << "  - Surface strain: " << result.surface_strain_analysis.size() << " surfaces\n";
    std::cout << "  - Element quality: " << result.element_quality.size() << " parts\n";
    std::cout << "=============================================================\n";
}

// ============================================================
// Build-time expiry check (Windows builds only)
// ============================================================
#ifdef _WIN32
namespace {
bool checkBuildExpiry() {
    // __DATE__ format: "Mar 16 2026"
    const char* build_date_str = __DATE__;
    const char* months[] = {"Jan","Feb","Mar","Apr","May","Jun",
                            "Jul","Aug","Sep","Oct","Nov","Dec"};
    char mon_str[4] = {};
    int day = 0, year = 0;
    std::sscanf(build_date_str, "%3s %d %d", mon_str, &day, &year);
    int mon = 0;
    for (int i = 0; i < 12; ++i) {
        if (std::strncmp(mon_str, months[i], 3) == 0) { mon = i; break; }
    }

    // Build date as time_t
    std::tm build_tm = {};
    build_tm.tm_year = year - 1900;
    build_tm.tm_mon  = mon;
    build_tm.tm_mday = day;
    std::time_t build_time = std::mktime(&build_tm);

    // Expiry = build_time + 365 days
    std::time_t expiry_time = build_time + 365 * 24 * 3600;
    std::time_t now = std::time(nullptr);

    if (now > expiry_time) {
        std::tm* exp_tm = std::localtime(&expiry_time);
        char buf[64];
        std::strftime(buf, sizeof(buf), "%Y-%m-%d", exp_tm);
        std::cerr << "=============================================================\n"
                  << " This build has expired on " << buf << ".\n"
                  << " Please obtain an updated build.\n"
                  << " Build date: " << build_date_str << "\n"
                  << "=============================================================\n";
        return false;
    }

    // Show remaining days as info
    int remaining = static_cast<int>((expiry_time - now) / (24 * 3600));
    if (remaining <= 30) {
        std::cerr << "[WARNING] This build expires in " << remaining << " day(s).\n";
    }
    return true;
}
} // anon
#endif

int main(int argc, char* argv[]) {
#ifdef _WIN32
    if (!checkBuildExpiry()) return 1;
#endif

    // Parse command line arguments
    std::string config_file;
    std::string recursive_dir;
    std::string output_dir;
    int num_threads = 0;
    bool generate_config = false;
    bool analysis_only = false;
    bool render_only = false;
    bool skip_existing = false;

    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];

        if (arg == "--help" || arg == "-h") {
            printUsage(argv[0]);
            return 0;
        }
        else if (arg == "--generate-config") {
            generate_config = true;
        }
        else if (arg == "--config" && i + 1 < argc) {
            config_file = argv[++i];
        }
        else if (arg == "--recursive" && i + 1 < argc) {
            recursive_dir = argv[++i];
        }
        else if (arg == "--output" && i + 1 < argc) {
            output_dir = argv[++i];
        }
        else if (arg == "--skip-existing") {
            skip_existing = true;
        }
        else if (arg == "--threads" && i + 1 < argc) {
            try {
                num_threads = std::stoi(argv[++i]);
            } catch (...) {
                std::cerr << "Invalid thread count\n";
                return 1;
            }
        }
        else if (arg == "--analysis-only") {
            analysis_only = true;
        }
        else if (arg == "--render-only") {
            render_only = true;
        }
    }

    // Handle --generate-config
    if (generate_config) {
        std::cout << UnifiedConfigParser::generateExampleYAML();
        return 0;
    }

    // Require config file
    if (config_file.empty()) {
        printUsage(argv[0]);
        return 1;
    }

    // Load configuration
    UnifiedConfig config;
    std::cout << "Loading configuration from: " << config_file << "\n";
    if (!UnifiedConfigParser::loadFromYAML(config_file, config)) {
        std::cerr << "Failed to load config: " << UnifiedConfigParser::getLastError() << "\n";
        return 1;
    }

    // Validate (but skip d3plot path validation in recursive mode)
    if (recursive_dir.empty() && !UnifiedConfigParser::validate(config)) {
        std::cerr << "Invalid configuration: " << UnifiedConfigParser::getLastError() << "\n";
        return 1;
    }

    // Override threads if specified on command line
    if (num_threads > 0) {
        config.num_threads = num_threads;
    }

    // Set OpenMP threads
#ifdef _OPENMP
    if (config.num_threads > 0) {
        omp_set_num_threads(config.num_threads);
        std::cout << "Using " << config.num_threads << " threads\n";
    } else {
        std::cout << "Using " << omp_get_max_threads() << " threads (auto)\n";
    }
#endif

    // ============================================================
    // Recursive Mode
    // ============================================================
    if (!recursive_dir.empty()) {
        fs::path root_path(recursive_dir);
        if (!fs::exists(root_path) || !fs::is_directory(root_path)) {
            std::cerr << "Invalid directory: " << recursive_dir << "\n";
            return 1;
        }

        // Determine output directory
        fs::path output_root;
        if (!output_dir.empty()) {
            output_root = output_dir;
        } else {
            // Default: analysis_results in current directory
            output_root = fs::current_path() / "analysis_results";
        }

        return runRecursiveAnalysis(root_path, output_root, config, config_file,
                                    analysis_only, skip_existing);
    }

    // ============================================================
    // Single Analysis Mode
    // ============================================================

    // Create output directory
    try {
        fs::create_directories(config.output_directory);
    } catch (const std::exception& e) {
        std::cerr << "Failed to create output directory: " << e.what() << "\n";
        return 1;
    }

    // Print configuration
    std::cout << "\n";
    std::cout << "=============================================================\n";
    std::cout << "KooD3plot Unified Analyzer (v2.0)\n";
    std::cout << "=============================================================\n";
    std::cout << "Input: " << config.d3plot_path << "\n";
    std::cout << "Output: " << config.output_directory << "\n";
    std::cout << "Analysis jobs: " << config.analysis_jobs.size() << "\n";
    if (!config.set_reports.empty()) {
        std::cout << "Set reports: " << config.set_reports.size() << "\n";
    }
    std::cout << "Render jobs: " << config.render_jobs.size() << "\n";
    std::cout << "=============================================================\n\n";

    // Carry analyzed part IDs across the analysis → part-section-render boundary
    std::vector<int32_t> analyzed_pids;

    // Run analysis
    auto start_time = std::chrono::high_resolution_clock::now();
    bool sv_done_in_analyze = false;

    if (!render_only && (config.hasAnalysisJobs() || !config.set_reports.empty())) {
        UnifiedAnalyzer analyzer;
        ExtendedAnalysisResult result = analyzer.analyze(config,
            [](const std::string& msg) {
                std::cout << msg << "\n";
            }
        );

        if (!analyzer.wasSuccessful()) {
            std::cerr << "Analysis failed: " << analyzer.getLastError() << "\n";
            return 1;
        }

        sv_done_in_analyze = analyzer.sectionViewsDone();
        analyzed_pids = result.metadata.analyzed_parts;

        // Export results
        std::cout << "\n[EXPORT] Writing results (JSON + CSV)...\n";
        exportResults(result, config);
        std::cout << "[EXPORT] Done.\n";

        auto end_time = std::chrono::high_resolution_clock::now();
        double elapsed = std::chrono::duration<double>(end_time - start_time).count();

        // Print summary
        printSummary(result, config, elapsed);
    }

    // Run rendering (if V4 Render is available and not analysis_only)
    if (!analysis_only && config.hasRenderJobs()) {
        std::cout << "\n[RENDER] Processing " << config.render_jobs.size() << " render job(s)...\n";

        D3plotReader render_reader(config.d3plot_path);
        auto error = render_reader.open();
        if (error != ErrorCode::SUCCESS) {
            std::cerr << "Failed to open d3plot for render jobs\n";
        } else {
            UnifiedAnalyzer render_analyzer;
            bool render_success = render_analyzer.processRenderJobs(render_reader, config,
                [](const std::string& msg) {
                    std::cout << msg << "\n";
                });

            if (render_success) {
                std::cout << "\n[RENDER] All render jobs completed successfully.\n";
            } else {
                std::cerr << "\n[RENDER] Some render jobs failed.\n";
            }
        }
    }

    // Run part section renders (LSPrePost renderAllPartSections)
    if (!analysis_only && config.hasPartSectionRenders()) {
        std::cout << "\n[PART_SECTION] Processing " << config.part_section_renders.size()
                  << " part section render job(s)...\n";

        D3plotReader psr_reader(config.d3plot_path);
        auto error = psr_reader.open();
        if (error != ErrorCode::SUCCESS) {
            std::cerr << "Failed to open d3plot for part section renders\n";
        } else {
            UnifiedAnalyzer psr_analyzer;
            bool psr_success = psr_analyzer.processPartSectionRenders(
                psr_reader, config, analyzed_pids,
                [](const std::string& msg) {
                    std::cout << msg << "\n";
                });

            if (psr_success) {
                std::cout << "\n[PART_SECTION] All part section renders completed.\n";
            } else {
                std::cerr << "\n[PART_SECTION] Some part section renders failed.\n";
            }
        }
    }

    // Run section view jobs — only if not already done inside analyze()
    if (!analysis_only && config.hasSectionViews() && !sv_done_in_analyze) {
        std::cout << "\n[SECTION_VIEW] Processing " << config.section_views.size()
                  << " section view job(s) with shared state data...\n";

        D3plotReader sv_reader(config.d3plot_path);
        auto error = sv_reader.open();
        if (error != ErrorCode::SUCCESS) {
            std::cerr << "Failed to open d3plot for section view jobs\n";
        } else {
            // Read all states once, then run all section views in parallel
            std::cout << "[SECTION_VIEW] Reading all states...\n";
            auto sv_states = sv_reader.read_all_states_parallel(config.num_threads);
            std::cout << "[SECTION_VIEW] " << sv_states.size() << " states loaded\n";

            UnifiedAnalyzer sv_analyzer;
            bool sv_success = sv_analyzer.processSectionViews(sv_reader, config, sv_states,
                [](const std::string& msg) {
                    std::cout << msg << "\n";
                });

            if (sv_success) {
                std::cout << "\n[SECTION_VIEW] All section view jobs completed successfully.\n";
            } else {
                std::cerr << "\n[SECTION_VIEW] Some section view jobs failed.\n";
            }
        }
    }

    return 0;
}
