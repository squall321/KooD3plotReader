/**
 * @file UnifiedAnalyzer.cpp
 * @brief Unified job-based analyzer implementation
 */

#include "kood3plot/analysis/UnifiedAnalyzer.hpp"
#include "kood3plot/analysis/PartAnalyzer.hpp"
#include "kood3plot/analysis/SurfaceStressAnalyzer.hpp"
#include "kood3plot/analysis/SurfaceExtractor.hpp"
#include "kood3plot/Version.hpp"
#include <algorithm>
#include <cmath>
#include <limits>

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

    if (config.analysis_jobs.empty()) {
        last_error_ = "No analysis jobs defined";
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
    auto all_states = reader.read_all_states_parallel();
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

    // Process each category
    if (!stress_jobs.empty()) {
        if (callback) callback("Processing stress analysis jobs...");
        processStressJobs(reader, stress_jobs, all_states, result, callback);
    }

    if (!strain_jobs.empty()) {
        if (callback) callback("Processing strain analysis jobs...");
        processStrainJobs(reader, strain_jobs, all_states, result, callback);
    }

    if (!motion_jobs.empty()) {
        if (callback) callback("Processing motion analysis jobs...");
        processMotionJobs(reader, motion_jobs, all_states, result, callback);
    }

    if (!surface_stress_jobs.empty()) {
        if (callback) callback("Processing surface stress analysis jobs...");
        processSurfaceStressJobs(reader, surface_stress_jobs, all_states, result, callback);
    }

    if (!surface_strain_jobs.empty()) {
        if (callback) callback("Processing surface strain analysis jobs...");
        processSurfaceStrainJobs(reader, surface_strain_jobs, all_states, result, callback);
    }

    // Fill metadata
    fillMetadata(reader, config, all_states, result);

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

    if (callback) callback("  Analyzing Von Mises stress...");

    // Use analyze_with_states to avoid re-reading d3plot files
    auto histories = analyzer.analyze_with_states(all_states, StressComponent::VON_MISES);

    // Collect part IDs from jobs (empty means all)
    std::vector<int32_t> requested_parts;
    bool want_all = false;
    for (const auto& job : jobs) {
        if (job.part_ids.empty()) {
            want_all = true;
            break;
        }
        for (int32_t pid : job.part_ids) {
            if (std::find(requested_parts.begin(), requested_parts.end(), pid) == requested_parts.end()) {
                requested_parts.push_back(pid);
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

    if (callback) callback("  Analyzing effective plastic strain...");

    // Use analyze_with_states to avoid re-reading d3plot files
    auto histories = analyzer.analyze_with_states(all_states, StressComponent::EFF_PLASTIC);

    // Collect part IDs from jobs (empty means all)
    std::vector<int32_t> requested_parts;
    bool want_all = false;
    for (const auto& job : jobs) {
        if (job.part_ids.empty()) {
            want_all = true;
            break;
        }
        for (int32_t pid : job.part_ids) {
            if (std::find(requested_parts.begin(), requested_parts.end(), pid) == requested_parts.end()) {
                requested_parts.push_back(pid);
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
    // Collect all part IDs
    std::vector<int32_t> all_parts;
    for (const auto& job : jobs) {
        if (job.part_ids.empty()) {
            all_parts.clear();
            break;
        }
        for (int32_t pid : job.part_ids) {
            if (std::find(all_parts.begin(), all_parts.end(), pid) == all_parts.end()) {
                all_parts.push_back(pid);
            }
        }
    }

    // Use MotionAnalyzer
    MotionAnalyzer analyzer(reader);
    analyzer.setParts(all_parts);

    if (!analyzer.initialize()) {
        if (callback) callback("  Motion: Failed to initialize - " + analyzer.getLastError());
        return;
    }

    // Process each state
    for (size_t i = 0; i < all_states.size(); ++i) {
        analyzer.processState(all_states[i]);

        if (callback && (i == 0 || i == all_states.size() - 1 || (i + 1) % 100 == 0)) {
            callback("  Motion: state " + std::to_string(i + 1) + "/" + std::to_string(all_states.size()));
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

        // Extract faces for this surface
        SurfaceExtractionResult extraction;
        if (job.part_ids.empty()) {
            extraction = extractor.extractExteriorSurfaces();
        } else {
            extraction = extractor.extractExteriorSurfaces(job.part_ids);
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
        for (const auto& state : all_states) {
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
        analyzer.addSurface(job.name, job.surface.direction, job.surface.angle, job.part_ids);
    }

    if (!analyzer.initialize()) {
        if (callback) callback("  Surface strain: Failed to initialize - " + analyzer.getLastError());
        return;
    }

    // Process each state
    for (size_t i = 0; i < all_states.size(); ++i) {
        analyzer.processState(all_states[i]);

        if (callback && (i == 0 || i == all_states.size() - 1 || (i + 1) % 100 == 0)) {
            callback("  Surface strain: state " + std::to_string(i + 1) + "/" + std::to_string(all_states.size()));
        }
    }

    // Get results
    result.surface_strain_analysis = analyzer.getResults();
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

} // namespace analysis
} // namespace kood3plot
