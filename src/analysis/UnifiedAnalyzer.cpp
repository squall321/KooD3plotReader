/**
 * @file UnifiedAnalyzer.cpp
 * @brief Unified job-based analyzer implementation
 *
 * Note: processRenderJobs is implemented in UnifiedAnalyzerRender.cpp
 * to avoid circular dependency with kood3plot_render library.
 */

#include "kood3plot/analysis/UnifiedAnalyzer.hpp"
#include "kood3plot/analysis/UnifiedConfigParser.hpp"
#include "kood3plot/analysis/PartAnalyzer.hpp"
#include "kood3plot/analysis/TimeHistoryAnalyzer.hpp"
#include "kood3plot/analysis/SinglePassAnalyzer.hpp"
#include "kood3plot/analysis/SurfaceStressAnalyzer.hpp"
#include "kood3plot/analysis/SurfaceExtractor.hpp"
#include "kood3plot/Version.hpp"
#include <algorithm>
#include <cmath>
#include <limits>
#include <map>

#ifdef _OPENMP
#include <omp.h>
#endif

namespace kood3plot {
namespace analysis {

ExtendedAnalysisResult UnifiedAnalyzer::analyze(const UnifiedConfig& config) {
    return analyze(config, nullptr);
}

ExtendedAnalysisResult UnifiedAnalyzer::analyze(const UnifiedConfig& config, UnifiedProgressCallback callback) {
    success_ = false;
    last_error_.clear();
    ExtendedAnalysisResult result;

    // Validate configuration
    if (config.d3plot_path.empty()) {
        last_error_ = "d3plot path is required";
        return result;
    }

    if (config.analysis_jobs.empty() && config.render_jobs.empty() && config.section_views.empty()) {
        last_error_ = "No analysis or render jobs defined";
        return result;
    }

    if (callback) callback("Opening d3plot file...");

    // Open d3plot file
    D3plotReader reader(config.d3plot_path);
    ErrorCode err = reader.open();
    if (err != ErrorCode::SUCCESS) {
        last_error_ = "Failed to open d3plot file";
        return result;
    }

    if (callback) callback("Reading all states (parallel)...");

    // Read all states in parallel (family files read concurrently)
    // Use configured thread count (0 = auto-detect)
    auto all_states = reader.read_all_states_parallel(config.num_threads);
    if (all_states.empty()) {
        last_error_ = "No states found in d3plot";
        return result;
    }

    if (callback) {
        callback("Read " + std::to_string(all_states.size()) + " states");
    }

    // Categorize jobs by type
    std::vector<AnalysisJob> stress_jobs;
    std::vector<AnalysisJob> strain_jobs;
    std::vector<AnalysisJob> motion_jobs;
    std::vector<AnalysisJob> surface_stress_jobs;
    std::vector<AnalysisJob> surface_strain_jobs;

    for (const auto& job : config.analysis_jobs) {
        switch (job.type) {
            case AnalysisJobType::VON_MISES:
                stress_jobs.push_back(job);
                break;
            case AnalysisJobType::EFF_PLASTIC_STRAIN:
                strain_jobs.push_back(job);
                break;
            case AnalysisJobType::PART_MOTION:
                motion_jobs.push_back(job);
                break;
            case AnalysisJobType::SURFACE_STRESS:
                surface_stress_jobs.push_back(job);
                break;
            case AnalysisJobType::SURFACE_STRAIN:
                surface_strain_jobs.push_back(job);
                break;
            case AnalysisJobType::COMPREHENSIVE:
                // Comprehensive jobs get split into multiple categories
                if (job.requiresStress()) {
                    AnalysisJob stress_job = job;
                    stress_job.type = AnalysisJobType::VON_MISES;
                    stress_jobs.push_back(stress_job);
                }
                if (job.requiresStrain()) {
                    AnalysisJob strain_job = job;
                    strain_job.type = AnalysisJobType::EFF_PLASTIC_STRAIN;
                    strain_jobs.push_back(strain_job);
                }
                if (job.requiresDisplacement()) {
                    AnalysisJob motion_job = job;
                    motion_job.type = AnalysisJobType::PART_MOTION;
                    motion_jobs.push_back(motion_job);
                }
                break;
        }
    }

    // Count total analysis steps for progress reporting
    int total_steps = 0;
    if (!stress_jobs.empty()) total_steps++;
    if (!strain_jobs.empty()) total_steps++;
    if (!motion_jobs.empty()) total_steps++;
    if (!surface_stress_jobs.empty()) total_steps++;
    if (!surface_strain_jobs.empty()) total_steps++;

    std::vector<AnalysisJob> quality_jobs;
    for (const auto& job : config.analysis_jobs) {
        if (job.type == AnalysisJobType::ELEMENT_QUALITY) {
            quality_jobs.push_back(job);
        }
    }
    if (!quality_jobs.empty()) total_steps++;
    if (config.hasSectionViews()) total_steps++;
    total_steps++; // metadata

    int current_step = 0;

    // Process each category
    if (!stress_jobs.empty()) {
        current_step++;
        if (callback) callback("[Step " + std::to_string(current_step) + "/" + std::to_string(total_steps) + "] Stress analysis (" + std::to_string(all_states.size()) + " states x " + std::to_string(stress_jobs.size()) + " jobs)...");
        processStressJobs(reader, stress_jobs, all_states, result, callback);
    }

    if (!strain_jobs.empty()) {
        current_step++;
        if (callback) callback("[Step " + std::to_string(current_step) + "/" + std::to_string(total_steps) + "] Strain analysis (" + std::to_string(all_states.size()) + " states x " + std::to_string(strain_jobs.size()) + " jobs)...");
        processStrainJobs(reader, strain_jobs, all_states, result, callback);
    }

    if (!motion_jobs.empty()) {
        current_step++;
        if (callback) callback("[Step " + std::to_string(current_step) + "/" + std::to_string(total_steps) + "] Motion analysis (" + std::to_string(all_states.size()) + " states x " + std::to_string(motion_jobs.size()) + " jobs)...");
        processMotionJobs(reader, motion_jobs, all_states, result, callback);
    }

    if (!surface_stress_jobs.empty()) {
        current_step++;
        if (callback) callback("[Step " + std::to_string(current_step) + "/" + std::to_string(total_steps) + "] Surface stress analysis...");
        processSurfaceStressJobs(reader, surface_stress_jobs, all_states, result, callback);
    }

    if (!surface_strain_jobs.empty()) {
        current_step++;
        if (callback) callback("[Step " + std::to_string(current_step) + "/" + std::to_string(total_steps) + "] Surface strain analysis...");
        processSurfaceStrainJobs(reader, surface_strain_jobs, all_states, result, callback);
    }

    if (!quality_jobs.empty()) {
        current_step++;
        if (callback) callback("[Step " + std::to_string(current_step) + "/" + std::to_string(total_steps) + "] Element quality analysis...");
        processElementQualityJobs(reader, quality_jobs, all_states, result, callback);
    }

    // Section view jobs — run here to share all_states (no d3plot re-read)
    if (config.hasSectionViews()) {
        current_step++;
        if (callback) callback("[Step " + std::to_string(current_step) + "/" + std::to_string(total_steps) + "] Section view rendering...");
        processSectionViews(reader, config, all_states, callback);
        section_views_done_ = true;
    }

    // Fill metadata
    current_step++;
    if (callback) callback("[Step " + std::to_string(current_step) + "/" + std::to_string(total_steps) + "] Collecting metadata...");
    fillMetadata(reader, config, all_states, result);

    // Note: render jobs are processed separately in unified_analyzer.cpp main,
    // not here, to avoid double-execution.

    success_ = true;
    if (callback) callback("Analysis complete!");

    return result;
}

void UnifiedAnalyzer::processStressJobs(
    D3plotReader& reader,
    const std::vector<AnalysisJob>& jobs,
    const std::vector<data::StateData>& all_states,
    ExtendedAnalysisResult& result,
    UnifiedProgressCallback callback
) {
    // Use PartAnalyzer with pre-loaded states (no redundant file I/O!)
    PartAnalyzer analyzer(reader);
    if (!analyzer.initialize()) {
        if (callback) callback("  Stress: Failed to initialize PartAnalyzer");
        return;
    }

    if (callback) callback("  Analyzing Von Mises stress (" + std::to_string(all_states.size()) + " states)...");

    // Use analyze_with_states_progress to show per-state progress
    auto histories = analyzer.analyze_with_states_progress(all_states, StressComponent::VON_MISES,
        [&callback](size_t current, size_t total, const std::string&) {
            if (callback && (current % 20 == 0 || current == total)) {
                callback("    Von Mises: state " + std::to_string(current) + "/" + std::to_string(total));
            }
        });

    // Collect part IDs from jobs (empty means all, or use part_pattern)
    std::vector<int32_t> requested_parts;
    bool want_all = false;
    for (const auto& job : jobs) {
        if (job.part_ids.empty() && job.part_pattern.empty()) {
            want_all = true;
            break;
        }
        // Add explicit part IDs
        for (int32_t pid : job.part_ids) {
            if (std::find(requested_parts.begin(), requested_parts.end(), pid) == requested_parts.end()) {
                requested_parts.push_back(pid);
            }
        }
        // Add parts matching pattern
        if (!job.part_pattern.empty()) {
            auto pattern_parts = UnifiedConfigParser::filterPartsByPattern(reader, job.part_pattern);
            for (int32_t pid : pattern_parts) {
                if (std::find(requested_parts.begin(), requested_parts.end(), pid) == requested_parts.end()) {
                    requested_parts.push_back(pid);
                }
            }
        }
    }

    // Convert to PartTimeSeriesStats
    for (const auto& history : histories) {
        // Filter by requested parts
        if (!want_all && std::find(requested_parts.begin(), requested_parts.end(), history.part_id) == requested_parts.end()) {
            continue;
        }

        PartTimeSeriesStats stats;
        stats.part_id = history.part_id;
        stats.part_name = "Part_" + std::to_string(history.part_id);
        stats.quantity = "von_mises";
        stats.unit = "MPa";

        for (size_t i = 0; i < history.times.size(); ++i) {
            TimePointStats tp;
            tp.time = history.times[i];
            tp.max_value = history.max_values[i];
            tp.min_value = history.min_values[i];
            tp.avg_value = history.avg_values[i];
            tp.max_element_id = i < history.max_elem_ids.size() ? history.max_elem_ids[i] : 0;
            tp.min_element_id = 0;  // Not tracked in PartTimeHistory
            stats.data.push_back(tp);
        }

        result.stress_history.push_back(stats);
    }

    if (callback) callback("  Stress analysis complete: " + std::to_string(result.stress_history.size()) + " parts");

    // Run SinglePassAnalyzer for principal stress + tensor history
    if (callback) callback("  Analyzing principal stress and tensor history (" + std::to_string(all_states.size()) + " states)...");
    SinglePassAnalyzer sp_analyzer(reader);
    AnalysisConfig sp_config;
    sp_config.analyze_stress = true;
    sp_config.analyze_strain = false;
    sp_config.part_ids = want_all ? std::vector<int32_t>{} : requested_parts;

    auto sp_result = sp_analyzer.analyzeWithStates(sp_config, all_states,
        [&callback](size_t current, size_t total, const std::string&) {
            if (callback && (current % 20 == 0 || current == total)) {
                callback("    Principal stress: state " + std::to_string(current) + "/" + std::to_string(total));
            }
        });

    // Move principal stress results
    result.max_principal_history = std::move(sp_result.max_principal_history);
    result.min_principal_history = std::move(sp_result.min_principal_history);

    // Move principal strain results (conditional - only when strain tensor exists in d3plot)
    result.max_principal_strain_history = std::move(sp_result.max_principal_strain_history);
    result.min_principal_strain_history = std::move(sp_result.min_principal_strain_history);

    // Move peak element tensor histories
    result.peak_element_tensors = std::move(sp_result.peak_element_tensors);

    if (callback) {
        callback("  Principal stress: " + std::to_string(result.max_principal_history.size()) + " parts, " +
                 "Tensors: " + std::to_string(result.peak_element_tensors.size()) + " elements");
    }
}

void UnifiedAnalyzer::processStrainJobs(
    D3plotReader& reader,
    const std::vector<AnalysisJob>& jobs,
    const std::vector<data::StateData>& all_states,
    ExtendedAnalysisResult& result,
    UnifiedProgressCallback callback
) {
    // Use PartAnalyzer with pre-loaded states (no redundant file I/O!)
    PartAnalyzer analyzer(reader);
    if (!analyzer.initialize()) {
        if (callback) callback("  Strain: Failed to initialize PartAnalyzer");
        return;
    }

    if (callback) callback("  Analyzing effective plastic strain (" + std::to_string(all_states.size()) + " states)...");

    // Use analyze_with_states_progress to show per-state progress
    auto histories = analyzer.analyze_with_states_progress(all_states, StressComponent::EFF_PLASTIC,
        [&callback](size_t current, size_t total, const std::string&) {
            if (callback && (current % 20 == 0 || current == total)) {
                callback("    Eff. plastic strain: state " + std::to_string(current) + "/" + std::to_string(total));
            }
        });

    // Collect part IDs from jobs (empty means all, or use part_pattern)
    std::vector<int32_t> requested_parts;
    bool want_all = false;
    for (const auto& job : jobs) {
        if (job.part_ids.empty() && job.part_pattern.empty()) {
            want_all = true;
            break;
        }
        // Add explicit part IDs
        for (int32_t pid : job.part_ids) {
            if (std::find(requested_parts.begin(), requested_parts.end(), pid) == requested_parts.end()) {
                requested_parts.push_back(pid);
            }
        }
        // Add parts matching pattern
        if (!job.part_pattern.empty()) {
            auto pattern_parts = UnifiedConfigParser::filterPartsByPattern(reader, job.part_pattern);
            for (int32_t pid : pattern_parts) {
                if (std::find(requested_parts.begin(), requested_parts.end(), pid) == requested_parts.end()) {
                    requested_parts.push_back(pid);
                }
            }
        }
    }

    // Convert to PartTimeSeriesStats
    for (const auto& history : histories) {
        // Filter by requested parts
        if (!want_all && std::find(requested_parts.begin(), requested_parts.end(), history.part_id) == requested_parts.end()) {
            continue;
        }

        PartTimeSeriesStats stats;
        stats.part_id = history.part_id;
        stats.part_name = "Part_" + std::to_string(history.part_id);
        stats.quantity = "eff_plastic_strain";
        stats.unit = "";

        for (size_t i = 0; i < history.times.size(); ++i) {
            TimePointStats tp;
            tp.time = history.times[i];
            tp.max_value = history.max_values[i];
            tp.min_value = history.min_values[i];
            tp.avg_value = history.avg_values[i];
            tp.max_element_id = i < history.max_elem_ids.size() ? history.max_elem_ids[i] : 0;
            tp.min_element_id = 0;
            stats.data.push_back(tp);
        }

        result.strain_history.push_back(stats);
    }

    if (callback) callback("  Strain analysis complete: " + std::to_string(result.strain_history.size()) + " parts");
}

void UnifiedAnalyzer::processMotionJobs(
    D3plotReader& reader,
    const std::vector<AnalysisJob>& jobs,
    const std::vector<data::StateData>& all_states,
    ExtendedAnalysisResult& result,
    UnifiedProgressCallback callback
) {
    // Collect all part IDs (empty means all, or use part_pattern)
    std::vector<int32_t> all_parts;
    bool want_all = false;
    for (const auto& job : jobs) {
        if (job.part_ids.empty() && job.part_pattern.empty()) {
            want_all = true;
            all_parts.clear();
            break;
        }
        // Add explicit part IDs
        for (int32_t pid : job.part_ids) {
            if (std::find(all_parts.begin(), all_parts.end(), pid) == all_parts.end()) {
                all_parts.push_back(pid);
            }
        }
        // Add parts matching pattern
        if (!job.part_pattern.empty()) {
            auto pattern_parts = UnifiedConfigParser::filterPartsByPattern(reader, job.part_pattern);
            for (int32_t pid : pattern_parts) {
                if (std::find(all_parts.begin(), all_parts.end(), pid) == all_parts.end()) {
                    all_parts.push_back(pid);
                }
            }
        }
    }

    // Use MotionAnalyzer
    MotionAnalyzer analyzer(reader);
    if (!want_all) {
        analyzer.setParts(all_parts);
    }

    if (!analyzer.initialize()) {
        if (callback) callback("  Motion: Failed to initialize - " + analyzer.getLastError());
        return;
    }

    // Process each state
    for (size_t i = 0; i < all_states.size(); ++i) {
        analyzer.processState(all_states[i]);

        if (callback && (i == 0 || i == all_states.size() - 1 || (i + 1) % 20 == 0)) {
            callback("    Motion: state " + std::to_string(i + 1) + "/" + std::to_string(all_states.size()));
        }
    }

    // Get results
    result.motion_analysis = analyzer.getResults();
}

void UnifiedAnalyzer::processSurfaceStressJobs(
    D3plotReader& reader,
    const std::vector<AnalysisJob>& jobs,
    const std::vector<data::StateData>& all_states,
    ExtendedAnalysisResult& result,
    UnifiedProgressCallback callback
) {
    // Use SurfaceExtractor to get exterior surfaces
    SurfaceExtractor extractor(reader);
    if (!extractor.initialize()) {
        if (callback) callback("  Surface stress: Failed to initialize extractor - " + extractor.getLastError());
        return;
    }

    // Use SurfaceStressAnalyzer for stress calculation
    SurfaceStressAnalyzer surf_analyzer(reader);

    for (const auto& job : jobs) {
        if (callback) callback("  Surface stress: " + job.name);

        // Collect part IDs (empty means all, or use part_pattern)
        std::vector<int32_t> target_parts = job.part_ids;
        if (!job.part_pattern.empty()) {
            auto pattern_parts = UnifiedConfigParser::filterPartsByPattern(reader, job.part_pattern);
            for (int32_t pid : pattern_parts) {
                if (std::find(target_parts.begin(), target_parts.end(), pid) == target_parts.end()) {
                    target_parts.push_back(pid);
                }
            }
        }

        // Extract faces for this surface
        SurfaceExtractionResult extraction;
        if (target_parts.empty()) {
            extraction = extractor.extractExteriorSurfaces();
        } else {
            extraction = extractor.extractExteriorSurfaces(target_parts);
        }

        // Filter by direction
        auto filtered = SurfaceExtractor::filterByDirection(extraction.faces, job.surface.direction, job.surface.angle);

        if (filtered.empty()) {
            continue;
        }

        SurfaceAnalysisStats stats;
        stats.description = job.name;
        stats.reference_direction = job.surface.direction;
        stats.angle_threshold_degrees = job.surface.angle;
        stats.part_ids = job.part_ids;
        stats.num_faces = static_cast<int32_t>(filtered.size());

        // Process each state using SurfaceStressAnalyzer
        for (size_t si = 0; si < all_states.size(); ++si) {
            const auto& state = all_states[si];
            // Use the analyzeState method that takes faces and state
            SurfaceStressStats stress_stats = surf_analyzer.analyzeState(filtered, state);

            SurfaceTimePointStats tp;
            tp.time = state.time;
            tp.normal_stress_max = stress_stats.normal_stress_max;
            tp.normal_stress_min = stress_stats.normal_stress_min;
            tp.normal_stress_avg = stress_stats.normal_stress_avg;
            tp.normal_stress_max_element_id = stress_stats.normal_stress_max_element;
            tp.shear_stress_max = stress_stats.shear_stress_max;
            tp.shear_stress_avg = stress_stats.shear_stress_avg;
            tp.shear_stress_max_element_id = stress_stats.shear_stress_max_element;

            stats.data.push_back(tp);

            if (callback && (si == 0 || si == all_states.size() - 1 || (si + 1) % 20 == 0)) {
                callback("    Surface stress [" + job.name + "]: state " + std::to_string(si + 1) + "/" + std::to_string(all_states.size()));
            }
        }

        result.surface_analysis.push_back(stats);
    }
}

void UnifiedAnalyzer::processSurfaceStrainJobs(
    D3plotReader& reader,
    const std::vector<AnalysisJob>& jobs,
    const std::vector<data::StateData>& all_states,
    ExtendedAnalysisResult& result,
    UnifiedProgressCallback callback
) {
    // Use SurfaceStrainAnalyzer
    SurfaceStrainAnalyzer analyzer(reader);

    // Add all surface specifications
    for (const auto& job : jobs) {
        // Collect part IDs (empty means all, or use part_pattern)
        std::vector<int32_t> target_parts = job.part_ids;
        if (!job.part_pattern.empty()) {
            auto pattern_parts = UnifiedConfigParser::filterPartsByPattern(reader, job.part_pattern);
            for (int32_t pid : pattern_parts) {
                if (std::find(target_parts.begin(), target_parts.end(), pid) == target_parts.end()) {
                    target_parts.push_back(pid);
                }
            }
        }
        analyzer.addSurface(job.name, job.surface.direction, job.surface.angle, target_parts);
    }

    if (!analyzer.initialize()) {
        if (callback) callback("  Surface strain: Failed to initialize - " + analyzer.getLastError());
        return;
    }

    // Process each state
    for (size_t i = 0; i < all_states.size(); ++i) {
        analyzer.processState(all_states[i]);

        if (callback && (i == 0 || i == all_states.size() - 1 || (i + 1) % 20 == 0)) {
            callback("    Surface strain: state " + std::to_string(i + 1) + "/" + std::to_string(all_states.size()));
        }
    }

    // Get results
    result.surface_strain_analysis = analyzer.getResults();
}

// ============================================================
// Element Quality Computation Helpers
// ============================================================

namespace {

struct Vec3Q {
    double x = 0, y = 0, z = 0;
    Vec3Q() = default;
    Vec3Q(double a, double b, double c) : x(a), y(b), z(c) {}
    Vec3Q operator-(const Vec3Q& o) const { return {x-o.x, y-o.y, z-o.z}; }
    Vec3Q operator+(const Vec3Q& o) const { return {x+o.x, y+o.y, z+o.z}; }
    Vec3Q operator*(double s) const { return {x*s, y*s, z*s}; }
    double dot(const Vec3Q& o) const { return x*o.x + y*o.y + z*o.z; }
    Vec3Q cross(const Vec3Q& o) const {
        return {y*o.z - z*o.y, z*o.x - x*o.z, x*o.y - y*o.x};
    }
    double mag() const { return std::sqrt(x*x + y*y + z*z); }
};

// Get current position of node (initial + displacement)
Vec3Q getNodePos(const data::Mesh& mesh, const data::StateData& state, size_t node_idx) {
    double dx = 0, dy = 0, dz = 0;
    if (!state.node_displacements.empty() && node_idx * 3 + 2 < state.node_displacements.size()) {
        dx = state.node_displacements[node_idx * 3 + 0];
        dy = state.node_displacements[node_idx * 3 + 1];
        dz = state.node_displacements[node_idx * 3 + 2];
    }
    return {mesh.nodes[node_idx].x + dx, mesh.nodes[node_idx].y + dy, mesh.nodes[node_idx].z + dz};
}

Vec3Q getNodeInitialPos(const data::Mesh& mesh, size_t node_idx) {
    return {mesh.nodes[node_idx].x, mesh.nodes[node_idx].y, mesh.nodes[node_idx].z};
}

// Aspect ratio: max edge length / min edge length
double computeAspectRatio4(const Vec3Q& p0, const Vec3Q& p1, const Vec3Q& p2, const Vec3Q& p3) {
    double edges[4] = {
        (p1 - p0).mag(), (p2 - p1).mag(), (p3 - p2).mag(), (p0 - p3).mag()
    };
    double mn = edges[0], mx = edges[0];
    for (int i = 1; i < 4; ++i) {
        if (edges[i] < mn) mn = edges[i];
        if (edges[i] > mx) mx = edges[i];
    }
    return (mn > 1e-20) ? mx / mn : 1e6;
}

// Skewness for quad: max deviation of corner angles from 90 degrees / 90
double computeSkewness4(const Vec3Q& p0, const Vec3Q& p1, const Vec3Q& p2, const Vec3Q& p3) {
    auto angle = [](const Vec3Q& a, const Vec3Q& b, const Vec3Q& c) -> double {
        Vec3Q ba = a - b, bc = c - b;
        double d = ba.dot(bc);
        double m = ba.mag() * bc.mag();
        if (m < 1e-20) return 0;
        double cosA = std::max(-1.0, std::min(1.0, d / m));
        return std::acos(cosA) * 180.0 / 3.14159265358979;
    };
    double angles[4] = {
        angle(p3, p0, p1), angle(p0, p1, p2), angle(p1, p2, p3), angle(p2, p3, p0)
    };
    double max_dev = 0;
    for (int i = 0; i < 4; ++i) {
        double dev = std::abs(angles[i] - 90.0) / 90.0;
        if (dev > max_dev) max_dev = dev;
    }
    return max_dev;
}

// Warpage for quad: angle between normals of two triangles
double computeWarpage4(const Vec3Q& p0, const Vec3Q& p1, const Vec3Q& p2, const Vec3Q& p3) {
    Vec3Q n1 = (p1 - p0).cross(p2 - p0);
    Vec3Q n2 = (p2 - p0).cross(p3 - p0);
    double m1 = n1.mag(), m2 = n2.mag();
    if (m1 < 1e-20 || m2 < 1e-20) return 0;
    double cosA = std::max(-1.0, std::min(1.0, n1.dot(n2) / (m1 * m2)));
    return std::acos(cosA) * 180.0 / 3.14159265358979;
}

// Area of quad (sum of two triangle areas)
double computeArea4(const Vec3Q& p0, const Vec3Q& p1, const Vec3Q& p2, const Vec3Q& p3) {
    return 0.5 * ((p1 - p0).cross(p2 - p0).mag() + (p2 - p0).cross(p3 - p0).mag());
}

// Jacobian determinant at center for 8-node hex
// Simplified: compute volume and compare sign
double computeHexVolume(const Vec3Q* p) {
    // 8-node hex volume via 5-tetrahedron decomposition
    auto tetVol = [](const Vec3Q& a, const Vec3Q& b, const Vec3Q& c, const Vec3Q& d) -> double {
        return (b - a).dot((c - a).cross(d - a)) / 6.0;
    };
    double vol = tetVol(p[0], p[1], p[3], p[4])
               + tetVol(p[1], p[2], p[3], p[6])
               + tetVol(p[1], p[4], p[5], p[6])
               + tetVol(p[3], p[4], p[6], p[7])
               + tetVol(p[1], p[3], p[4], p[6]);
    return vol;
}

// Aspect ratio for hex: max edge / min edge (12 edges)
double computeAspectRatio8(const Vec3Q* p) {
    int edges[12][2] = {
        {0,1},{1,2},{2,3},{3,0},
        {4,5},{5,6},{6,7},{7,4},
        {0,4},{1,5},{2,6},{3,7}
    };
    double mn = 1e30, mx = 0;
    for (int i = 0; i < 12; ++i) {
        double len = (p[edges[i][1]] - p[edges[i][0]]).mag();
        if (len < mn) mn = len;
        if (len > mx) mx = len;
    }
    return (mn > 1e-20) ? mx / mn : 1e6;
}

} // anonymous namespace

void UnifiedAnalyzer::processElementQualityJobs(
    D3plotReader& reader,
    const std::vector<AnalysisJob>& jobs,
    const std::vector<data::StateData>& all_states,
    ExtendedAnalysisResult& result,
    UnifiedProgressCallback callback
) {
    auto mesh = reader.read_mesh();

    // Collect target parts
    std::vector<int32_t> target_parts;
    bool want_all = false;
    for (const auto& job : jobs) {
        if (job.part_ids.empty() && job.part_pattern.empty()) {
            want_all = true;
            break;
        }
        for (int32_t pid : job.part_ids) {
            if (std::find(target_parts.begin(), target_parts.end(), pid) == target_parts.end())
                target_parts.push_back(pid);
        }
        if (!job.part_pattern.empty()) {
            auto pparts = UnifiedConfigParser::filterPartsByPattern(reader, job.part_pattern);
            for (int32_t pid : pparts) {
                if (std::find(target_parts.begin(), target_parts.end(), pid) == target_parts.end())
                    target_parts.push_back(pid);
            }
        }
    }

    // Build part → element index maps
    struct ElemInfo {
        size_t idx;          // index in mesh.shells / mesh.solids
        bool is_solid;
    };
    std::map<int32_t, std::vector<ElemInfo>> part_elements;
    std::map<int32_t, std::string> part_types;  // "shell" or "solid"

    for (size_t i = 0; i < mesh.shells.size(); ++i) {
        int32_t pid = (i < mesh.shell_parts.size()) ? mesh.shell_parts[i] : 0;
        if (!want_all && std::find(target_parts.begin(), target_parts.end(), pid) == target_parts.end())
            continue;
        part_elements[pid].push_back({i, false});
        part_types[pid] = "shell";
    }
    for (size_t i = 0; i < mesh.solids.size(); ++i) {
        int32_t pid = (i < mesh.solid_parts.size()) ? mesh.solid_parts[i] : 0;
        if (!want_all && std::find(target_parts.begin(), target_parts.end(), pid) == target_parts.end())
            continue;
        part_elements[pid].push_back({i, true});
        part_types[pid] = "solid";
    }

    // Compute initial volumes/areas for reference
    struct InitialMetric {
        double volume_or_area;
    };
    std::map<int32_t, std::vector<InitialMetric>> initial_metrics;
    for (auto& [pid, elems] : part_elements) {
        auto& metrics = initial_metrics[pid];
        metrics.resize(elems.size());
        for (size_t ei = 0; ei < elems.size(); ++ei) {
            const auto& info = elems[ei];
            if (info.is_solid) {
                const auto& elem = mesh.solids[info.idx];
                if (elem.node_ids.size() >= 8) {
                    Vec3Q p[8];
                    for (int n = 0; n < 8; ++n)
                        p[n] = getNodeInitialPos(mesh, elem.node_ids[n] - 1);
                    metrics[ei].volume_or_area = std::abs(computeHexVolume(p));
                }
            } else {
                const auto& elem = mesh.shells[info.idx];
                if (elem.node_ids.size() >= 4) {
                    Vec3Q p[4];
                    for (int n = 0; n < 4; ++n)
                        p[n] = getNodeInitialPos(mesh, elem.node_ids[n] - 1);
                    metrics[ei].volume_or_area = computeArea4(p[0], p[1], p[2], p[3]);
                }
            }
        }
    }

    // Sample states (not all — use ~10 evenly spaced states for performance)
    std::vector<size_t> sample_indices;
    size_t n_states = all_states.size();
    size_t n_samples = std::min(n_states, size_t(10));
    if (n_samples <= 1) {
        sample_indices.push_back(0);
        if (n_states > 1) sample_indices.push_back(n_states - 1);
    } else {
        for (size_t i = 0; i < n_samples; ++i) {
            size_t idx = i * (n_states - 1) / (n_samples - 1);
            sample_indices.push_back(idx);
        }
    }

    // Initialize result stats
    std::map<int32_t, ElementQualityStats> stats_map;
    for (auto& [pid, elems] : part_elements) {
        auto& qs = stats_map[pid];
        qs.part_id = pid;
        qs.part_name = "Part_" + std::to_string(pid);
        qs.element_type = part_types[pid];
        qs.num_elements = elems.size();
    }

    // Process sampled states
    for (size_t si = 0; si < sample_indices.size(); ++si) {
        size_t state_idx = sample_indices[si];
        const auto& state = all_states[state_idx];

        if (callback) {
            callback("    Quality: sample " + std::to_string(si + 1) + "/" + std::to_string(sample_indices.size()) +
                     " (state " + std::to_string(state_idx + 1) + "/" + std::to_string(n_states) + ")");
        }

        for (auto& [pid, elems] : part_elements) {
            ElementQualityTimePoint tp;
            tp.time = state.time;

            double ar_sum = 0, sk_sum = 0, wp_sum = 0, jac_sum = 0;
            int count = 0;

            for (size_t ei = 0; ei < elems.size(); ++ei) {
                const auto& info = elems[ei];
                int32_t elem_id = 0;

                if (info.is_solid) {
                    const auto& elem = mesh.solids[info.idx];
                    elem_id = elem.id;
                    if (elem.node_ids.size() < 8) continue;

                    Vec3Q p[8];
                    for (int n = 0; n < 8; ++n)
                        p[n] = getNodePos(mesh, state, elem.node_ids[n] - 1);

                    double ar = computeAspectRatio8(p);
                    double vol = computeHexVolume(p);
                    double jac = (vol >= 0) ? 1.0 : -1.0;  // simplified: sign of volume
                    double init_vol = initial_metrics[pid][ei].volume_or_area;
                    double vol_ratio = (init_vol > 1e-20) ? std::abs(vol) / init_vol : 1.0;

                    if (ar > tp.aspect_ratio_max) { tp.aspect_ratio_max = ar; tp.worst_aspect_ratio_elem = elem_id; }
                    if (jac < tp.jacobian_min) { tp.jacobian_min = jac; tp.worst_jacobian_elem = elem_id; }
                    if (vol_ratio < tp.volume_change_min) { tp.volume_change_min = vol_ratio; tp.worst_volume_change_elem = elem_id; }
                    if (vol_ratio > tp.volume_change_max) tp.volume_change_max = vol_ratio;
                    if (vol < 0) tp.n_negative_jacobian++;
                    if (ar > 5.0) tp.n_high_aspect++;

                    ar_sum += ar;
                    jac_sum += jac;
                    count++;
                } else {
                    const auto& elem = mesh.shells[info.idx];
                    elem_id = elem.id;
                    if (elem.node_ids.size() < 4) continue;

                    // Check for degenerate quad (tria element: node 3 == node 4)
                    bool is_tria = (elem.node_ids[2] == elem.node_ids[3]);

                    Vec3Q p[4];
                    for (int n = 0; n < 4; ++n)
                        p[n] = getNodePos(mesh, state, elem.node_ids[n] - 1);

                    double ar, sk, wp, area;
                    if (is_tria) {
                        // Triangle: aspect ratio from 3 edges
                        double e0 = (p[1]-p[0]).mag(), e1 = (p[2]-p[1]).mag(), e2 = (p[0]-p[2]).mag();
                        double mn = std::min({e0,e1,e2}), mx = std::max({e0,e1,e2});
                        ar = (mn > 1e-20) ? mx / mn : 1e6;
                        sk = 0; wp = 0;
                        area = 0.5 * (p[1]-p[0]).cross(p[2]-p[0]).mag();
                    } else {
                        ar = computeAspectRatio4(p[0], p[1], p[2], p[3]);
                        sk = computeSkewness4(p[0], p[1], p[2], p[3]);
                        wp = computeWarpage4(p[0], p[1], p[2], p[3]);
                        area = computeArea4(p[0], p[1], p[2], p[3]);
                    }

                    double init_area = initial_metrics[pid][ei].volume_or_area;
                    double area_ratio = (init_area > 1e-20) ? area / init_area : 1.0;

                    if (ar > tp.aspect_ratio_max) { tp.aspect_ratio_max = ar; tp.worst_aspect_ratio_elem = elem_id; }
                    if (sk > tp.skewness_max) { tp.skewness_max = sk; tp.worst_skewness_elem = elem_id; }
                    if (wp > tp.warpage_max) { tp.warpage_max = wp; tp.worst_warpage_elem = elem_id; }
                    if (area_ratio < tp.volume_change_min) { tp.volume_change_min = area_ratio; tp.worst_volume_change_elem = elem_id; }
                    if (area_ratio > tp.volume_change_max) tp.volume_change_max = area_ratio;
                    if (ar > 5.0) tp.n_high_aspect++;

                    ar_sum += ar; sk_sum += sk; wp_sum += wp;
                    count++;
                }
            }

            if (count > 0) {
                tp.aspect_ratio_avg = ar_sum / count;
                tp.skewness_avg = sk_sum / count;
                tp.warpage_avg = wp_sum / count;
                tp.jacobian_avg = jac_sum / count;
            }

            stats_map[pid].data.push_back(tp);
        }
    }

    // Compute global stats and add to result
    for (auto& [pid, qs] : stats_map) {
        qs.computeGlobalStats();
        result.element_quality.push_back(std::move(qs));
    }

    if (callback) callback("  Element quality complete: " + std::to_string(result.element_quality.size()) + " parts");
}

void UnifiedAnalyzer::fillMetadata(
    D3plotReader& reader,
    const UnifiedConfig& config,
    const std::vector<data::StateData>& all_states,
    ExtendedAnalysisResult& result
) {
    result.metadata.d3plot_path = config.d3plot_path;
    result.metadata.setCurrentDate();
    result.metadata.kood3plot_version = Version::get_version_string();
    result.metadata.num_states = static_cast<int32_t>(all_states.size());

    if (!all_states.empty()) {
        result.metadata.start_time = all_states.front().time;
        result.metadata.end_time = all_states.back().time;
    }

    // Collect all analyzed parts
    std::vector<int32_t> all_parts;
    for (const auto& stats : result.stress_history) {
        if (std::find(all_parts.begin(), all_parts.end(), stats.part_id) == all_parts.end()) {
            all_parts.push_back(stats.part_id);
        }
    }
    for (const auto& stats : result.strain_history) {
        if (std::find(all_parts.begin(), all_parts.end(), stats.part_id) == all_parts.end()) {
            all_parts.push_back(stats.part_id);
        }
    }
    for (const auto& stats : result.motion_analysis) {
        if (std::find(all_parts.begin(), all_parts.end(), stats.part_id) == all_parts.end()) {
            all_parts.push_back(stats.part_id);
        }
    }

    std::sort(all_parts.begin(), all_parts.end());
    result.metadata.analyzed_parts = all_parts;
}

// Note: processRenderJobs is implemented in UnifiedAnalyzerRender.cpp
// when KOOD3PLOT_HAS_RENDER is defined. This is a stub for when
// render support is not available.
#ifndef KOOD3PLOT_HAS_RENDER
bool UnifiedAnalyzer::processRenderJobs(
    D3plotReader& /* reader */,
    const UnifiedConfig& config,
    UnifiedProgressCallback callback
) {
    if (config.render_jobs.empty()) {
        return true;  // No render jobs to process
    }

    // Render module not available
    if (callback) callback("  Render jobs skipped: LSPrePost renderer not available");
    if (callback) callback("  Build with KOOD3PLOT_BUILD_V4_RENDER=ON to enable rendering");
    return false;
}
#endif

// Note: processSectionViews is implemented in UnifiedAnalyzerSectionRender.cpp
// when KOOD3PLOT_HAS_SECTION_RENDER is defined.
#ifndef KOOD3PLOT_HAS_SECTION_RENDER
bool UnifiedAnalyzer::processSectionViews(
    D3plotReader& /* reader */,
    const UnifiedConfig& config,
    UnifiedProgressCallback callback
) {
    if (config.section_views.empty()) {
        return true;
    }
    if (callback) callback("  Section view jobs skipped: software renderer not available");
    if (callback) callback("  Build with KOOD3PLOT_BUILD_SECTION_RENDER=ON to enable");
    return false;
}

bool UnifiedAnalyzer::processSectionViews(
    D3plotReader& /* reader */,
    const UnifiedConfig& config,
    const std::vector<data::StateData>& /* all_states */,
    UnifiedProgressCallback callback
) {
    if (config.section_views.empty()) {
        return true;
    }
    if (callback) callback("  Section view jobs skipped: software renderer not available");
    return false;
}
#endif

} // namespace analysis
} // namespace kood3plot
