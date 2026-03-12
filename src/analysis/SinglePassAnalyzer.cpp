/**
 * @file SinglePassAnalyzer.cpp
 * @brief Implementation of high-performance single-pass analysis
 */

#include "kood3plot/analysis/SinglePassAnalyzer.hpp"
#include "kood3plot/analysis/TimeHistoryAnalyzer.hpp"
#include "kood3plot/Version.hpp"
#include <algorithm>
#include <cmath>
#include <iostream>
#include <set>

namespace kood3plot {
namespace analysis {

// ========================================
// Constructor
// ========================================

SinglePassAnalyzer::SinglePassAnalyzer(D3plotReader& reader)
    : reader_(reader)
    , nv3d_(0)
    , num_solid_elements_(0)
{
}

// ========================================
// Public API
// ========================================

AnalysisResult SinglePassAnalyzer::analyze(const AnalysisConfig& config) {
    return analyze(config, nullptr);
}

// ========================================
// State-level parallel implementation (optimized)
// ========================================

AnalysisResult SinglePassAnalyzer::analyzeParallel(const AnalysisConfig& config) {
    return analyzeParallel(config, nullptr);
}

AnalysisResult SinglePassAnalyzer::analyzeParallel(
    const AnalysisConfig& config,
    SinglePassProgressCallback callback
) {
    success_ = false;
    last_error_.clear();

    // Initialize
    if (!initialize(config)) {
        return AnalysisResult();
    }

    if (callback) {
        callback(0, 1, "Reading all states from d3plot files...");
    }

    // Read ALL states at once
    std::vector<data::StateData> all_states = reader_.read_all_states_parallel();
    size_t num_states = all_states.size();

    if (num_states == 0) {
        last_error_ = "No states found in d3plot";
        return AnalysisResult();
    }

    num_states_ = num_states;

    // Initialize result storage
    initializeResults(num_states, config);

    // Extract surfaces if needed
    if (!config.surface_specs.empty()) {
        extractSurfaces(config);
    }

    if (callback) {
        callback(0, num_states, "Starting state-level parallel analysis (" +
                 std::to_string(num_states) + " states)");
    }

    // ========================================
    // STATE-LEVEL PARALLEL: Process states in parallel
    // Each thread handles a subset of states sequentially
    // ========================================
#ifdef _OPENMP
    std::atomic<size_t> completed_states{0};

    #pragma omp parallel for schedule(dynamic, 1)
    for (int64_t state_idx = 0; state_idx < static_cast<int64_t>(num_states); ++state_idx) {
        const data::StateData& state = all_states[state_idx];

        // Analyze parts (sequential within thread)
        if (config.analyze_stress || config.analyze_strain) {
            analyzePartStatsSequential(state_idx, state, config.analyze_stress, config.analyze_strain);
        }

        // Analyze surfaces (sequential within thread)
        if (!surface_faces_.empty()) {
            analyzeSurfaceStatsSequential(state_idx, state);
        }

        // Progress callback (thread-safe)
        if (callback) {
            size_t count = ++completed_states;
            if (count == 1 || count == num_states || count % 100 == 0) {
                #pragma omp critical
                {
                    callback(count, num_states, "Processing states (parallel)");
                }
            }
        }
    }
#else
    // Fallback to sequential if OpenMP not available
    for (size_t state_idx = 0; state_idx < num_states; ++state_idx) {
        const data::StateData& state = all_states[state_idx];
        processState(state_idx, state, config);

        if (callback && (state_idx == 0 || state_idx == num_states - 1 || (state_idx + 1) % 50 == 0)) {
            callback(state_idx + 1, num_states, "Processing state " + std::to_string(state_idx + 1));
        }
    }
#endif

    if (callback) {
        callback(num_states, num_states, "Analysis complete (state-level parallel)");
    }

    success_ = true;
    AnalysisResult result = buildResult(config);

    // Extract peak element tensor histories (2nd lightweight pass over in-memory states)
    if (config.analyze_stress) {
        extractPeakElementTensors(all_states, result);
    }

    return result;
}

// ========================================
// Pre-loaded states implementation (no file I/O)
// ========================================

AnalysisResult SinglePassAnalyzer::analyzeWithStates(
    const AnalysisConfig& config,
    const std::vector<data::StateData>& all_states,
    SinglePassProgressCallback callback
) {
    success_ = false;
    last_error_.clear();

    // Initialize
    if (!initialize(config)) {
        return AnalysisResult();
    }

    size_t num_states = all_states.size();
    if (num_states == 0) {
        last_error_ = "No states provided";
        return AnalysisResult();
    }

    num_states_ = num_states;

    // Initialize result storage
    initializeResults(num_states, config);

    // Extract surfaces if needed
    if (!config.surface_specs.empty()) {
        extractSurfaces(config);
    }

    if (callback) {
        callback(0, num_states, "Starting analysis with pre-loaded states (" +
                 std::to_string(num_states) + " states)");
    }

#ifdef _OPENMP
    std::atomic<size_t> completed_states{0};

    #pragma omp parallel for schedule(dynamic, 1)
    for (int64_t state_idx = 0; state_idx < static_cast<int64_t>(num_states); ++state_idx) {
        const data::StateData& state = all_states[state_idx];

        if (config.analyze_stress || config.analyze_strain) {
            analyzePartStatsSequential(state_idx, state, config.analyze_stress, config.analyze_strain);
        }

        if (!surface_faces_.empty()) {
            analyzeSurfaceStatsSequential(state_idx, state);
        }

        if (callback) {
            size_t count = ++completed_states;
            if (count == 1 || count == num_states || count % 100 == 0) {
                #pragma omp critical
                {
                    callback(count, num_states, "Processing states (parallel)");
                }
            }
        }
    }
#else
    for (size_t state_idx = 0; state_idx < num_states; ++state_idx) {
        const data::StateData& state = all_states[state_idx];
        processState(state_idx, state, config);

        if (callback && (state_idx == 0 || state_idx == num_states - 1 || (state_idx + 1) % 50 == 0)) {
            callback(state_idx + 1, num_states, "Processing state " + std::to_string(state_idx + 1));
        }
    }
#endif

    if (callback) {
        callback(num_states, num_states, "Analysis complete (pre-loaded states)");
    }

    success_ = true;
    AnalysisResult result = buildResult(config);

    // Extract peak element tensor histories
    if (config.analyze_stress) {
        extractPeakElementTensors(all_states, result);
    }

    return result;
}

// ========================================
// Element-level parallel implementation (legacy)
// ========================================

AnalysisResult SinglePassAnalyzer::analyzeLegacy(const AnalysisConfig& config) {
    return analyzeLegacy(config, nullptr);
}

AnalysisResult SinglePassAnalyzer::analyzeLegacy(
    const AnalysisConfig& config,
    SinglePassProgressCallback callback
) {
    success_ = false;
    last_error_.clear();

    // Initialize
    if (!initialize(config)) {
        return AnalysisResult();
    }

    if (callback) {
        callback(0, 1, "Reading all states from d3plot files...");
    }

    // Read ALL states at once
    std::vector<data::StateData> all_states = reader_.read_all_states_parallel();
    size_t num_states = all_states.size();

    if (num_states == 0) {
        last_error_ = "No states found in d3plot";
        return AnalysisResult();
    }

    num_states_ = num_states;

    // Initialize result storage
    initializeResults(num_states, config);

    // Extract surfaces if needed
    if (!config.surface_specs.empty()) {
        extractSurfaces(config);
    }

    if (callback) {
        callback(0, num_states, "Starting element-level parallel analysis (" +
                 std::to_string(num_states) + " states)");
    }

    // ========================================
    // ELEMENT-LEVEL PARALLEL (legacy): Sequential state loop, parallel element loop
    // ========================================
    for (size_t state_idx = 0; state_idx < num_states; ++state_idx) {
        const data::StateData& state = all_states[state_idx];

        // Process all analyses for this state (uses element-level parallelism)
        processState(state_idx, state, config);

        if (callback && (state_idx == 0 || state_idx == num_states - 1 || (state_idx + 1) % 50 == 0)) {
            callback(state_idx + 1, num_states, "Processing state " + std::to_string(state_idx + 1));
        }
    }

    if (callback) {
        callback(num_states, num_states, "Analysis complete (element-level parallel)");
    }

    success_ = true;
    AnalysisResult result = buildResult(config);

    // Extract peak element tensor histories (2nd lightweight pass over in-memory states)
    if (config.analyze_stress) {
        extractPeakElementTensors(all_states, result);
    }

    return result;
}

AnalysisResult SinglePassAnalyzer::analyze(
    const AnalysisConfig& config,
    SinglePassProgressCallback callback
) {
    // Dispatch based on parallelization mode
    if (use_state_level_parallel_) {
        return analyzeParallel(config, callback);
    } else {
        return analyzeLegacy(config, callback);
    }
}

// ========================================
// Initialization
// ========================================

bool SinglePassAnalyzer::initialize(const AnalysisConfig& config) {
    // Get control data
    const auto& control_data = reader_.get_control_data();
    nv3d_ = control_data.NV3D;
    num_solid_elements_ = control_data.NEL8;
    has_strain_tensor_ = (control_data.ISTRN != 0 && nv3d_ >= 13);

    // Read mesh
    mesh_ = reader_.read_mesh();

    // Build element mapping
    buildElementMapping();

    return true;
}

void SinglePassAnalyzer::buildElementMapping() {
    // Build elem_id_to_index mapping
    elem_id_to_index_.clear();
    if (!mesh_.real_solid_ids.empty()) {
        for (size_t i = 0; i < mesh_.real_solid_ids.size(); ++i) {
            elem_id_to_index_[mesh_.real_solid_ids[i]] = i;
        }
    } else {
        for (size_t i = 0; i < mesh_.solids.size(); ++i) {
            elem_id_to_index_[mesh_.solids[i].id] = i;
        }
    }

    // Build elem_to_part mapping (index -> part_id)
    elem_to_part_.resize(num_solid_elements_);
    std::set<int32_t> unique_parts;

    for (size_t i = 0; i < num_solid_elements_ && i < mesh_.solid_parts.size(); ++i) {
        elem_to_part_[i] = mesh_.solid_parts[i];
        unique_parts.insert(mesh_.solid_parts[i]);
    }

    // Store unique part IDs and create mapping
    part_ids_.assign(unique_parts.begin(), unique_parts.end());
    for (size_t i = 0; i < part_ids_.size(); ++i) {
        part_id_to_result_index_[part_ids_[i]] = i;
    }
}

void SinglePassAnalyzer::initializeResults(size_t num_states, const AnalysisConfig& config) {
    size_t num_parts = part_ids_.size();

    // Initialize stress results
    if (config.analyze_stress) {
        stress_results_.resize(num_parts);
        for (size_t i = 0; i < num_parts; ++i) {
            stress_results_[i].part_id = part_ids_[i];
            stress_results_[i].quantity = "von_mises";
            stress_results_[i].unit = "MPa";
            stress_results_[i].data.resize(num_states);
        }
    }

    // Initialize principal stress results (always alongside von_mises)
    if (config.analyze_stress) {
        max_principal_results_.resize(num_parts);
        min_principal_results_.resize(num_parts);
        for (size_t i = 0; i < num_parts; ++i) {
            max_principal_results_[i].part_id = part_ids_[i];
            max_principal_results_[i].quantity = "max_principal_stress";
            max_principal_results_[i].unit = "MPa";
            max_principal_results_[i].data.resize(num_states);

            min_principal_results_[i].part_id = part_ids_[i];
            min_principal_results_[i].quantity = "min_principal_stress";
            min_principal_results_[i].unit = "MPa";
            min_principal_results_[i].data.resize(num_states);
        }
    }

    // Initialize principal strain results (conditional on strain tensor availability)
    if (config.analyze_strain && has_strain_tensor_) {
        max_principal_strain_results_.resize(num_parts);
        min_principal_strain_results_.resize(num_parts);
        for (size_t i = 0; i < num_parts; ++i) {
            max_principal_strain_results_[i].part_id = part_ids_[i];
            max_principal_strain_results_[i].quantity = "max_principal_strain";
            max_principal_strain_results_[i].unit = "";
            max_principal_strain_results_[i].data.resize(num_states);

            min_principal_strain_results_[i].part_id = part_ids_[i];
            min_principal_strain_results_[i].quantity = "min_principal_strain";
            min_principal_strain_results_[i].unit = "";
            min_principal_strain_results_[i].data.resize(num_states);
        }
    }

    // Initialize strain results
    if (config.analyze_strain) {
        strain_results_.resize(num_parts);
        for (size_t i = 0; i < num_parts; ++i) {
            strain_results_[i].part_id = part_ids_[i];
            strain_results_[i].quantity = "eff_plastic_strain";
            strain_results_[i].unit = "";
            strain_results_[i].data.resize(num_states);
        }
    }

    // Initialize surface results
    surface_results_.resize(config.surface_specs.size());
    for (size_t i = 0; i < config.surface_specs.size(); ++i) {
        surface_results_[i].description = config.surface_specs[i].description;
        surface_results_[i].reference_direction = config.surface_specs[i].direction;
        surface_results_[i].angle_threshold_degrees = config.surface_specs[i].angle_threshold_degrees;
        surface_results_[i].part_ids = config.surface_specs[i].part_ids;
        surface_results_[i].data.resize(num_states);
    }
}

void SinglePassAnalyzer::extractSurfaces(const AnalysisConfig& config) {
    surface_specs_ = config.surface_specs;
    surface_faces_.resize(config.surface_specs.size());

    // Extract all exterior surfaces once
    SurfaceExtractor extractor(reader_);
    auto all_surfaces = extractor.extractExteriorSurfaces();

    // Filter for each surface spec
    for (size_t i = 0; i < config.surface_specs.size(); ++i) {
        const auto& spec = config.surface_specs[i];

        // Filter by direction
        auto filtered = SurfaceExtractor::filterByDirection(
            all_surfaces.faces, spec.direction, spec.angle_threshold_degrees);

        // Filter by parts if specified
        if (!spec.part_ids.empty()) {
            filtered = SurfaceExtractor::filterByPart(filtered, spec.part_ids);
        }

        surface_faces_[i] = std::move(filtered);
        surface_results_[i].num_faces = static_cast<int32_t>(surface_faces_[i].size());
    }
}

// ========================================
// Single-pass processing
// ========================================

void SinglePassAnalyzer::processState(
    size_t state_idx,
    const data::StateData& state,
    const AnalysisConfig& config
) {
    // Analyze part statistics (stress/strain)
    if (config.analyze_stress || config.analyze_strain) {
        analyzePartStats(state_idx, state, config.analyze_stress, config.analyze_strain);
    }

    // Analyze surface stress
    if (!surface_faces_.empty()) {
        analyzeSurfaceStats(state_idx, state);
    }
}

void SinglePassAnalyzer::analyzePartStats(
    size_t state_idx,
    const data::StateData& state,
    bool analyze_stress,
    bool analyze_strain
) {
    const auto& solid_data = state.solid_data;
    if (solid_data.empty()) return;

    size_t num_parts = part_ids_.size();

    // Per-part accumulators for this state
    std::vector<PartStateStats> part_stats(num_parts);

    // Reset all stats
    for (auto& stats : part_stats) {
        stats.reset();
    }

#ifdef _OPENMP
    // Parallel processing with thread-local stats
    int num_threads = omp_get_max_threads();
    std::vector<std::vector<PartStateStats>> thread_stats(num_threads);
    for (auto& ts : thread_stats) {
        ts.resize(num_parts);
        for (auto& s : ts) s.reset();
    }

    #pragma omp parallel
    {
        int tid = omp_get_thread_num();
        auto& local_stats = thread_stats[tid];

        #pragma omp for nowait
        for (int64_t elem_idx = 0; elem_idx < static_cast<int64_t>(num_solid_elements_); ++elem_idx) {
            if (elem_idx >= elem_to_part_.size()) continue;

            int32_t part_id = elem_to_part_[elem_idx];
            auto it = part_id_to_result_index_.find(part_id);
            if (it == part_id_to_result_index_.end()) continue;

            size_t part_idx = it->second;
            auto& stats = local_stats[part_idx];

            // Get element ID
            int32_t elem_id = (elem_idx < mesh_.real_solid_ids.size()) ?
                              mesh_.real_solid_ids[elem_idx] :
                              static_cast<int32_t>(elem_idx + 1);

            if (analyze_stress) {
                double vm = extractVonMises(solid_data, elem_idx);
                if (vm > stats.stress_max) {
                    stats.stress_max = vm;
                    stats.stress_max_elem = elem_id;
                }
                if (vm < stats.stress_min) {
                    stats.stress_min = vm;
                    stats.stress_min_elem = elem_id;
                }
                stats.stress_sum += vm;
                stats.stress_count++;

                // Principal stresses (always computed alongside von_mises)
                auto tensor = extractStressTensor(solid_data, elem_idx);
                double s1 = tensor.maxPrincipal();
                double s3 = tensor.minPrincipal();
                if (s1 > stats.max_principal_max) {
                    stats.max_principal_max = s1;
                    stats.max_principal_max_elem = elem_id;
                }
                if (s1 < stats.max_principal_min) stats.max_principal_min = s1;
                stats.max_principal_sum += s1;

                if (s3 < stats.min_principal_min) {
                    stats.min_principal_min = s3;
                    stats.min_principal_min_elem = elem_id;
                }
                if (s3 > stats.min_principal_max) stats.min_principal_max = s3;
                stats.min_principal_sum += s3;

                stats.principal_count++;
            }

            if (analyze_strain) {
                double strain = extractEffPlasticStrain(solid_data, elem_idx);
                if (strain > stats.strain_max) {
                    stats.strain_max = strain;
                    stats.strain_max_elem = elem_id;
                }
                if (strain < stats.strain_min) {
                    stats.strain_min = strain;
                }
                stats.strain_sum += strain;
                stats.strain_count++;

                // Principal strains (only when strain tensor is available)
                if (has_strain_tensor_) {
                    auto etensor = extractStrainTensor(solid_data, elem_idx);
                    double e1 = etensor.maxPrincipal();
                    double e3 = etensor.minPrincipal();
                    if (e1 > stats.max_principal_strain_max) {
                        stats.max_principal_strain_max = e1;
                        stats.max_principal_strain_max_elem = elem_id;
                    }
                    if (e1 < stats.max_principal_strain_min) stats.max_principal_strain_min = e1;
                    stats.max_principal_strain_sum += e1;

                    if (e3 < stats.min_principal_strain_min) {
                        stats.min_principal_strain_min = e3;
                        stats.min_principal_strain_min_elem = elem_id;
                    }
                    if (e3 > stats.min_principal_strain_max) stats.min_principal_strain_max = e3;
                    stats.min_principal_strain_sum += e3;

                    stats.principal_strain_count++;
                }
            }
        }
    }

    // Merge thread results
    for (const auto& ts : thread_stats) {
        for (size_t i = 0; i < num_parts; ++i) {
            part_stats[i].merge(ts[i]);
        }
    }

#else
    // Sequential processing
    for (size_t elem_idx = 0; elem_idx < num_solid_elements_; ++elem_idx) {
        if (elem_idx >= elem_to_part_.size()) continue;

        int32_t part_id = elem_to_part_[elem_idx];
        auto it = part_id_to_result_index_.find(part_id);
        if (it == part_id_to_result_index_.end()) continue;

        size_t part_idx = it->second;
        auto& stats = part_stats[part_idx];

        int32_t elem_id = (elem_idx < mesh_.real_solid_ids.size()) ?
                          mesh_.real_solid_ids[elem_idx] :
                          static_cast<int32_t>(elem_idx + 1);

        if (analyze_stress) {
            double vm = extractVonMises(solid_data, elem_idx);
            if (vm > stats.stress_max) {
                stats.stress_max = vm;
                stats.stress_max_elem = elem_id;
            }
            if (vm < stats.stress_min) {
                stats.stress_min = vm;
                stats.stress_min_elem = elem_id;
            }
            stats.stress_sum += vm;
            stats.stress_count++;

            // Principal stresses (always computed alongside von_mises)
            auto tensor = extractStressTensor(solid_data, elem_idx);
            double s1 = tensor.maxPrincipal();
            double s3 = tensor.minPrincipal();
            if (s1 > stats.max_principal_max) {
                stats.max_principal_max = s1;
                stats.max_principal_max_elem = elem_id;
            }
            if (s1 < stats.max_principal_min) stats.max_principal_min = s1;
            stats.max_principal_sum += s1;

            if (s3 < stats.min_principal_min) {
                stats.min_principal_min = s3;
                stats.min_principal_min_elem = elem_id;
            }
            if (s3 > stats.min_principal_max) stats.min_principal_max = s3;
            stats.min_principal_sum += s3;

            stats.principal_count++;
        }

        if (analyze_strain) {
            double strain = extractEffPlasticStrain(solid_data, elem_idx);
            if (strain > stats.strain_max) {
                stats.strain_max = strain;
                stats.strain_max_elem = elem_id;
            }
            if (strain < stats.strain_min) {
                stats.strain_min = strain;
            }
            stats.strain_sum += strain;
            stats.strain_count++;

            // Principal strains (only when strain tensor is available)
            if (has_strain_tensor_) {
                auto etensor = extractStrainTensor(solid_data, elem_idx);
                double e1 = etensor.maxPrincipal();
                double e3 = etensor.minPrincipal();
                if (e1 > stats.max_principal_strain_max) {
                    stats.max_principal_strain_max = e1;
                    stats.max_principal_strain_max_elem = elem_id;
                }
                if (e1 < stats.max_principal_strain_min) stats.max_principal_strain_min = e1;
                stats.max_principal_strain_sum += e1;

                if (e3 < stats.min_principal_strain_min) {
                    stats.min_principal_strain_min = e3;
                    stats.min_principal_strain_min_elem = elem_id;
                }
                if (e3 > stats.min_principal_strain_max) stats.min_principal_strain_max = e3;
                stats.min_principal_strain_sum += e3;

                stats.principal_strain_count++;
            }
        }
    }
#endif

    // Store results
    for (size_t i = 0; i < num_parts; ++i) {
        const auto& stats = part_stats[i];

        if (analyze_stress && i < stress_results_.size()) {
            auto& tp = stress_results_[i].data[state_idx];
            tp.time = state.time;
            tp.max_value = stats.stress_max;
            tp.min_value = stats.stress_min;
            tp.avg_value = (stats.stress_count > 0) ?
                           stats.stress_sum / stats.stress_count : 0.0;
            tp.max_element_id = stats.stress_max_elem;
            tp.min_element_id = stats.stress_min_elem;

            // Principal stress results
            if (i < max_principal_results_.size()) {
                auto& tp1 = max_principal_results_[i].data[state_idx];
                tp1.time = state.time;
                tp1.max_value = stats.max_principal_max;
                tp1.min_value = stats.max_principal_min;
                tp1.avg_value = (stats.principal_count > 0) ?
                                stats.max_principal_sum / stats.principal_count : 0.0;
                tp1.max_element_id = stats.max_principal_max_elem;
            }
            if (i < min_principal_results_.size()) {
                auto& tp3 = min_principal_results_[i].data[state_idx];
                tp3.time = state.time;
                tp3.max_value = stats.min_principal_max;
                tp3.min_value = stats.min_principal_min;
                tp3.avg_value = (stats.principal_count > 0) ?
                                stats.min_principal_sum / stats.principal_count : 0.0;
                tp3.min_element_id = stats.min_principal_min_elem;
            }
        }

        if (analyze_strain && i < strain_results_.size()) {
            auto& tp = strain_results_[i].data[state_idx];
            tp.time = state.time;
            tp.max_value = stats.strain_max;
            tp.min_value = stats.strain_min;
            tp.avg_value = (stats.strain_count > 0) ?
                           stats.strain_sum / stats.strain_count : 0.0;
            tp.max_element_id = stats.strain_max_elem;

            // Principal strain results
            if (i < max_principal_strain_results_.size()) {
                auto& tpe1 = max_principal_strain_results_[i].data[state_idx];
                tpe1.time = state.time;
                tpe1.max_value = stats.max_principal_strain_max;
                tpe1.min_value = stats.max_principal_strain_min;
                tpe1.avg_value = (stats.principal_strain_count > 0) ?
                                 stats.max_principal_strain_sum / stats.principal_strain_count : 0.0;
                tpe1.max_element_id = stats.max_principal_strain_max_elem;
            }
            if (i < min_principal_strain_results_.size()) {
                auto& tpe3 = min_principal_strain_results_[i].data[state_idx];
                tpe3.time = state.time;
                tpe3.max_value = stats.min_principal_strain_max;
                tpe3.min_value = stats.min_principal_strain_min;
                tpe3.avg_value = (stats.principal_strain_count > 0) ?
                                 stats.min_principal_strain_sum / stats.principal_strain_count : 0.0;
                tpe3.min_element_id = stats.min_principal_strain_min_elem;
            }
        }
    }
}

void SinglePassAnalyzer::analyzeSurfaceStats(
    size_t state_idx,
    const data::StateData& state
) {
    const auto& solid_data = state.solid_data;
    if (solid_data.empty()) return;

    for (size_t spec_idx = 0; spec_idx < surface_faces_.size(); ++spec_idx) {
        const auto& faces = surface_faces_[spec_idx];
        if (faces.empty()) continue;

        SurfaceStateStats stats;
        stats.reset();

#ifdef _OPENMP
        int num_threads = omp_get_max_threads();
        std::vector<SurfaceStateStats> thread_stats(num_threads);
        for (auto& ts : thread_stats) ts.reset();

        #pragma omp parallel
        {
            int tid = omp_get_thread_num();
            auto& local_stats = thread_stats[tid];

            #pragma omp for nowait
            for (int64_t fi = 0; fi < static_cast<int64_t>(faces.size()); ++fi) {
                const auto& face = faces[fi];

                // Get element index
                auto it = elem_id_to_index_.find(face.element_id);
                if (it == elem_id_to_index_.end()) continue;

                size_t elem_idx = it->second;
                StressTensor tensor = extractStressTensor(solid_data, elem_idx);

                double vm = tensor.vonMises();
                double normal = tensor.normalStress(face.normal);
                double shear = tensor.shearStress(face.normal);

                // Von Mises
                if (vm > local_stats.von_mises_max) {
                    local_stats.von_mises_max = vm;
                    local_stats.von_mises_max_elem = face.element_id;
                }
                if (vm < local_stats.von_mises_min) {
                    local_stats.von_mises_min = vm;
                }
                local_stats.von_mises_sum += vm;

                // Normal stress
                if (normal > local_stats.normal_max) {
                    local_stats.normal_max = normal;
                    local_stats.normal_max_elem = face.element_id;
                }
                if (normal < local_stats.normal_min) {
                    local_stats.normal_min = normal;
                }
                local_stats.normal_sum += normal;

                // Shear stress
                if (shear > local_stats.shear_max) {
                    local_stats.shear_max = shear;
                    local_stats.shear_max_elem = face.element_id;
                }
                if (shear < local_stats.shear_min) {
                    local_stats.shear_min = shear;
                }
                local_stats.shear_sum += shear;

                local_stats.count++;
            }
        }

        // Merge
        for (const auto& ts : thread_stats) {
            stats.merge(ts);
        }

#else
        for (const auto& face : faces) {
            auto it = elem_id_to_index_.find(face.element_id);
            if (it == elem_id_to_index_.end()) continue;

            size_t elem_idx = it->second;
            StressTensor tensor = extractStressTensor(solid_data, elem_idx);

            double vm = tensor.vonMises();
            double normal = tensor.normalStress(face.normal);
            double shear = tensor.shearStress(face.normal);

            if (vm > stats.von_mises_max) {
                stats.von_mises_max = vm;
                stats.von_mises_max_elem = face.element_id;
            }
            if (vm < stats.von_mises_min) {
                stats.von_mises_min = vm;
            }
            stats.von_mises_sum += vm;

            if (normal > stats.normal_max) {
                stats.normal_max = normal;
                stats.normal_max_elem = face.element_id;
            }
            if (normal < stats.normal_min) {
                stats.normal_min = normal;
            }
            stats.normal_sum += normal;

            if (shear > stats.shear_max) {
                stats.shear_max = shear;
                stats.shear_max_elem = face.element_id;
            }
            if (shear < stats.shear_min) {
                stats.shear_min = shear;
            }
            stats.shear_sum += shear;

            stats.count++;
        }
#endif

        // Store results
        auto& result_tp = surface_results_[spec_idx].data[state_idx];
        result_tp.time = state.time;
        result_tp.normal_stress_max = stats.normal_max;
        result_tp.normal_stress_min = stats.normal_min;
        result_tp.normal_stress_avg = (stats.count > 0) ?
                                       stats.normal_sum / stats.count : 0.0;
        result_tp.normal_stress_max_element_id = stats.normal_max_elem;
        result_tp.shear_stress_max = stats.shear_max;
        result_tp.shear_stress_avg = (stats.count > 0) ?
                                      stats.shear_sum / stats.count : 0.0;
        result_tp.shear_stress_max_element_id = stats.shear_max_elem;
    }
}

// ========================================
// Sequential analysis for state-level parallelization
// ========================================

void SinglePassAnalyzer::analyzePartStatsSequential(
    size_t state_idx,
    const data::StateData& state,
    bool analyze_stress,
    bool analyze_strain
) {
    const auto& solid_data = state.solid_data;
    if (solid_data.empty()) return;

    size_t num_parts = part_ids_.size();

    // Per-part accumulators for this state
    std::vector<PartStateStats> part_stats(num_parts);
    for (auto& stats : part_stats) {
        stats.reset();
    }

    // Sequential processing (no OpenMP - this runs inside parallel state loop)
    for (size_t elem_idx = 0; elem_idx < num_solid_elements_; ++elem_idx) {
        if (elem_idx >= elem_to_part_.size()) continue;

        int32_t part_id = elem_to_part_[elem_idx];
        auto it = part_id_to_result_index_.find(part_id);
        if (it == part_id_to_result_index_.end()) continue;

        size_t part_idx = it->second;
        auto& stats = part_stats[part_idx];

        int32_t elem_id = (elem_idx < mesh_.real_solid_ids.size()) ?
                          mesh_.real_solid_ids[elem_idx] :
                          static_cast<int32_t>(elem_idx + 1);

        if (analyze_stress) {
            double vm = extractVonMises(solid_data, elem_idx);
            if (vm > stats.stress_max) {
                stats.stress_max = vm;
                stats.stress_max_elem = elem_id;
            }
            if (vm < stats.stress_min) {
                stats.stress_min = vm;
                stats.stress_min_elem = elem_id;
            }
            stats.stress_sum += vm;
            stats.stress_count++;

            // Principal stresses (always computed alongside von_mises)
            auto tensor = extractStressTensor(solid_data, elem_idx);
            double s1 = tensor.maxPrincipal();
            double s3 = tensor.minPrincipal();
            if (s1 > stats.max_principal_max) {
                stats.max_principal_max = s1;
                stats.max_principal_max_elem = elem_id;
            }
            if (s1 < stats.max_principal_min) stats.max_principal_min = s1;
            stats.max_principal_sum += s1;

            if (s3 < stats.min_principal_min) {
                stats.min_principal_min = s3;
                stats.min_principal_min_elem = elem_id;
            }
            if (s3 > stats.min_principal_max) stats.min_principal_max = s3;
            stats.min_principal_sum += s3;

            stats.principal_count++;
        }

        if (analyze_strain) {
            double strain = extractEffPlasticStrain(solid_data, elem_idx);
            if (strain > stats.strain_max) {
                stats.strain_max = strain;
                stats.strain_max_elem = elem_id;
            }
            if (strain < stats.strain_min) {
                stats.strain_min = strain;
            }
            stats.strain_sum += strain;
            stats.strain_count++;

            // Principal strains (only when strain tensor is available)
            if (has_strain_tensor_) {
                auto etensor = extractStrainTensor(solid_data, elem_idx);
                double e1 = etensor.maxPrincipal();
                double e3 = etensor.minPrincipal();
                if (e1 > stats.max_principal_strain_max) {
                    stats.max_principal_strain_max = e1;
                    stats.max_principal_strain_max_elem = elem_id;
                }
                if (e1 < stats.max_principal_strain_min) stats.max_principal_strain_min = e1;
                stats.max_principal_strain_sum += e1;

                if (e3 < stats.min_principal_strain_min) {
                    stats.min_principal_strain_min = e3;
                    stats.min_principal_strain_min_elem = elem_id;
                }
                if (e3 > stats.min_principal_strain_max) stats.min_principal_strain_max = e3;
                stats.min_principal_strain_sum += e3;

                stats.principal_strain_count++;
            }
        }
    }

    // Store results (each thread writes to its own state_idx - no race condition)
    for (size_t i = 0; i < num_parts; ++i) {
        const auto& stats = part_stats[i];

        if (analyze_stress && i < stress_results_.size()) {
            auto& tp = stress_results_[i].data[state_idx];
            tp.time = state.time;
            tp.max_value = stats.stress_max;
            tp.min_value = stats.stress_min;
            tp.avg_value = (stats.stress_count > 0) ?
                           stats.stress_sum / stats.stress_count : 0.0;
            tp.max_element_id = stats.stress_max_elem;
            tp.min_element_id = stats.stress_min_elem;

            // Principal stress results
            if (i < max_principal_results_.size()) {
                auto& tp1 = max_principal_results_[i].data[state_idx];
                tp1.time = state.time;
                tp1.max_value = stats.max_principal_max;
                tp1.min_value = stats.max_principal_min;
                tp1.avg_value = (stats.principal_count > 0) ?
                                stats.max_principal_sum / stats.principal_count : 0.0;
                tp1.max_element_id = stats.max_principal_max_elem;
            }
            if (i < min_principal_results_.size()) {
                auto& tp3 = min_principal_results_[i].data[state_idx];
                tp3.time = state.time;
                tp3.max_value = stats.min_principal_max;
                tp3.min_value = stats.min_principal_min;
                tp3.avg_value = (stats.principal_count > 0) ?
                                stats.min_principal_sum / stats.principal_count : 0.0;
                tp3.min_element_id = stats.min_principal_min_elem;
            }
        }

        if (analyze_strain && i < strain_results_.size()) {
            auto& tp = strain_results_[i].data[state_idx];
            tp.time = state.time;
            tp.max_value = stats.strain_max;
            tp.min_value = stats.strain_min;
            tp.avg_value = (stats.strain_count > 0) ?
                           stats.strain_sum / stats.strain_count : 0.0;
            tp.max_element_id = stats.strain_max_elem;

            // Principal strain results
            if (i < max_principal_strain_results_.size()) {
                auto& tpe1 = max_principal_strain_results_[i].data[state_idx];
                tpe1.time = state.time;
                tpe1.max_value = stats.max_principal_strain_max;
                tpe1.min_value = stats.max_principal_strain_min;
                tpe1.avg_value = (stats.principal_strain_count > 0) ?
                                 stats.max_principal_strain_sum / stats.principal_strain_count : 0.0;
                tpe1.max_element_id = stats.max_principal_strain_max_elem;
            }
            if (i < min_principal_strain_results_.size()) {
                auto& tpe3 = min_principal_strain_results_[i].data[state_idx];
                tpe3.time = state.time;
                tpe3.max_value = stats.min_principal_strain_max;
                tpe3.min_value = stats.min_principal_strain_min;
                tpe3.avg_value = (stats.principal_strain_count > 0) ?
                                 stats.min_principal_strain_sum / stats.principal_strain_count : 0.0;
                tpe3.min_element_id = stats.min_principal_strain_min_elem;
            }
        }
    }
}

void SinglePassAnalyzer::analyzeSurfaceStatsSequential(
    size_t state_idx,
    const data::StateData& state
) {
    const auto& solid_data = state.solid_data;
    if (solid_data.empty()) return;

    for (size_t spec_idx = 0; spec_idx < surface_faces_.size(); ++spec_idx) {
        const auto& faces = surface_faces_[spec_idx];
        if (faces.empty()) continue;

        SurfaceStateStats stats;
        stats.reset();

        // Sequential processing (no OpenMP - this runs inside parallel state loop)
        for (const auto& face : faces) {
            auto it = elem_id_to_index_.find(face.element_id);
            if (it == elem_id_to_index_.end()) continue;

            size_t elem_idx = it->second;
            StressTensor tensor = extractStressTensor(solid_data, elem_idx);

            double vm = tensor.vonMises();
            double normal = tensor.normalStress(face.normal);
            double shear = tensor.shearStress(face.normal);

            if (vm > stats.von_mises_max) {
                stats.von_mises_max = vm;
                stats.von_mises_max_elem = face.element_id;
            }
            if (vm < stats.von_mises_min) {
                stats.von_mises_min = vm;
            }
            stats.von_mises_sum += vm;

            if (normal > stats.normal_max) {
                stats.normal_max = normal;
                stats.normal_max_elem = face.element_id;
            }
            if (normal < stats.normal_min) {
                stats.normal_min = normal;
            }
            stats.normal_sum += normal;

            if (shear > stats.shear_max) {
                stats.shear_max = shear;
                stats.shear_max_elem = face.element_id;
            }
            if (shear < stats.shear_min) {
                stats.shear_min = shear;
            }
            stats.shear_sum += shear;

            stats.count++;
        }

        // Store results (each thread writes to its own state_idx - no race condition)
        auto& result_tp = surface_results_[spec_idx].data[state_idx];
        result_tp.time = state.time;
        result_tp.normal_stress_max = stats.normal_max;
        result_tp.normal_stress_min = stats.normal_min;
        result_tp.normal_stress_avg = (stats.count > 0) ?
                                       stats.normal_sum / stats.count : 0.0;
        result_tp.normal_stress_max_element_id = stats.normal_max_elem;
        result_tp.shear_stress_max = stats.shear_max;
        result_tp.shear_stress_avg = (stats.count > 0) ?
                                      stats.shear_sum / stats.count : 0.0;
        result_tp.shear_stress_max_element_id = stats.shear_max_elem;
    }
}

// ========================================
// Stress/Strain extraction
// ========================================

double SinglePassAnalyzer::extractVonMises(
    const std::vector<double>& solid_data,
    size_t elem_idx
) {
    size_t base = elem_idx * nv3d_;
    if (base + 6 > solid_data.size()) return 0.0;

    double sxx = solid_data[base + 0];
    double syy = solid_data[base + 1];
    double szz = solid_data[base + 2];
    double sxy = solid_data[base + 3];
    double syz = solid_data[base + 4];
    double szx = solid_data[base + 5];

    // Von Mises formula
    double s1 = sxx - syy;
    double s2 = syy - szz;
    double s3 = szz - sxx;
    double vm = std::sqrt(0.5 * (s1*s1 + s2*s2 + s3*s3) +
                          3.0 * (sxy*sxy + syz*syz + szx*szx));
    return vm;
}

double SinglePassAnalyzer::extractEffPlasticStrain(
    const std::vector<double>& solid_data,
    size_t elem_idx
) {
    size_t base = elem_idx * nv3d_;
    if (base + 7 > solid_data.size()) return 0.0;

    return solid_data[base + 6];  // Word 6 is effective plastic strain
}

StressTensor SinglePassAnalyzer::extractStressTensor(
    const std::vector<double>& solid_data,
    size_t elem_idx
) {
    size_t base = elem_idx * nv3d_;
    if (base + 6 > solid_data.size()) {
        return StressTensor(0, 0, 0, 0, 0, 0);
    }

    return StressTensor(
        solid_data[base + 0],  // sxx
        solid_data[base + 1],  // syy
        solid_data[base + 2],  // szz
        solid_data[base + 3],  // sxy
        solid_data[base + 4],  // syz
        solid_data[base + 5]   // szx
    );
}

StressTensor SinglePassAnalyzer::extractStrainTensor(
    const std::vector<double>& solid_data,
    size_t elem_idx
) {
    // Strain tensor at words 7-12 (after 6 stress + 1 eff_plastic_strain)
    size_t base = elem_idx * nv3d_;
    if (base + 13 > solid_data.size()) {
        return StressTensor(0, 0, 0, 0, 0, 0);
    }

    return StressTensor(
        solid_data[base + 7],   // exx
        solid_data[base + 8],   // eyy
        solid_data[base + 9],   // ezz
        solid_data[base + 10],  // exy
        solid_data[base + 11],  // eyz
        solid_data[base + 12]   // ezx
    );
}

// ========================================
// Peak element tensor extraction
// ========================================

void SinglePassAnalyzer::extractPeakElementTensors(
    const std::vector<data::StateData>& all_states,
    AnalysisResult& result
) {
    // For each part, identify peak elements and extract their full tensor history.
    // Peak elements: max von Mises, max σ1, min σ3 (per part).
    // Deduplicate by element_id per part to avoid duplicate histories.

    struct PeakInfo {
        int32_t element_id = 0;
        int32_t part_id = 0;
        std::string reason;
        double peak_value = 0.0;
        double peak_time = 0.0;
    };

    std::vector<PeakInfo> peaks;

    // Find peak von Mises element per part
    for (const auto& part_stats : result.stress_history) {
        double best_val = -std::numeric_limits<double>::infinity();
        int32_t best_elem = 0;
        double best_time = 0.0;
        for (const auto& tp : part_stats.data) {
            if (tp.max_value > best_val) {
                best_val = tp.max_value;
                best_elem = tp.max_element_id;
                best_time = tp.time;
            }
        }
        if (best_elem != 0) {
            peaks.push_back({best_elem, part_stats.part_id, "peak_von_mises", best_val, best_time});
        }
    }

    // Find peak max principal (σ1) element per part
    for (const auto& part_stats : result.max_principal_history) {
        double best_val = -std::numeric_limits<double>::infinity();
        int32_t best_elem = 0;
        double best_time = 0.0;
        for (const auto& tp : part_stats.data) {
            if (tp.max_value > best_val) {
                best_val = tp.max_value;
                best_elem = tp.max_element_id;
                best_time = tp.time;
            }
        }
        if (best_elem != 0) {
            // Check if same element already tracked for this part
            bool duplicate = false;
            for (const auto& p : peaks) {
                if (p.part_id == part_stats.part_id && p.element_id == best_elem) {
                    duplicate = true;
                    break;
                }
            }
            if (!duplicate) {
                peaks.push_back({best_elem, part_stats.part_id, "peak_max_principal", best_val, best_time});
            }
        }
    }

    // Find peak min principal (σ3) element per part (most compressive)
    for (const auto& part_stats : result.min_principal_history) {
        double best_val = std::numeric_limits<double>::infinity();
        int32_t best_elem = 0;
        double best_time = 0.0;
        for (const auto& tp : part_stats.data) {
            if (tp.min_value < best_val) {
                best_val = tp.min_value;
                best_elem = tp.min_element_id;
                best_time = tp.time;
            }
        }
        if (best_elem != 0) {
            bool duplicate = false;
            for (const auto& p : peaks) {
                if (p.part_id == part_stats.part_id && p.element_id == best_elem) {
                    duplicate = true;
                    break;
                }
            }
            if (!duplicate) {
                peaks.push_back({best_elem, part_stats.part_id, "peak_min_principal", best_val, best_time});
            }
        }
    }

    if (peaks.empty()) return;

    // Build element_id → internal_index mapping for fast lookup
    // (reuse existing elem_id_to_index_)

    // Extract tensor history for each peak element across all states
    size_t num_states = all_states.size();
    for (const auto& peak : peaks) {
        auto it = elem_id_to_index_.find(peak.element_id);
        if (it == elem_id_to_index_.end()) continue;

        size_t elem_idx = it->second;
        ElementTensorHistory hist;
        hist.element_id = peak.element_id;
        hist.part_id = peak.part_id;
        hist.reason = peak.reason;
        hist.peak_value = peak.peak_value;
        hist.peak_time = peak.peak_time;

        hist.time.reserve(num_states);
        hist.sxx.reserve(num_states);
        hist.syy.reserve(num_states);
        hist.szz.reserve(num_states);
        hist.sxy.reserve(num_states);
        hist.syz.reserve(num_states);
        hist.szx.reserve(num_states);

        for (size_t si = 0; si < num_states; ++si) {
            const auto& solid_data = all_states[si].solid_data;
            size_t base = elem_idx * nv3d_;
            if (base + 6 > solid_data.size()) {
                hist.time.push_back(all_states[si].time);
                hist.sxx.push_back(0.0);
                hist.syy.push_back(0.0);
                hist.szz.push_back(0.0);
                hist.sxy.push_back(0.0);
                hist.syz.push_back(0.0);
                hist.szx.push_back(0.0);
            } else {
                hist.time.push_back(all_states[si].time);
                hist.sxx.push_back(solid_data[base + 0]);
                hist.syy.push_back(solid_data[base + 1]);
                hist.szz.push_back(solid_data[base + 2]);
                hist.sxy.push_back(solid_data[base + 3]);
                hist.syz.push_back(solid_data[base + 4]);
                hist.szx.push_back(solid_data[base + 5]);
            }
        }

        result.peak_element_tensors.push_back(std::move(hist));
    }

    std::cout << "[SinglePassAnalyzer] Extracted tensor history for "
              << result.peak_element_tensors.size() << " peak elements across "
              << num_states << " states\n";
}

// ========================================
// Result building
// ========================================

AnalysisResult SinglePassAnalyzer::buildResult(const AnalysisConfig& config) {
    AnalysisResult result;

    // Fill metadata
    fillMetadata(result, config);

    // Move results
    result.stress_history = std::move(stress_results_);
    result.strain_history = std::move(strain_results_);
    result.max_principal_history = std::move(max_principal_results_);
    result.min_principal_history = std::move(min_principal_results_);
    result.max_principal_strain_history = std::move(max_principal_strain_results_);
    result.min_principal_strain_history = std::move(min_principal_strain_results_);
    result.surface_analysis = std::move(surface_results_);

    // Save outputs if requested
    if (!config.output_json_path.empty()) {
        result.saveToFile(config.output_json_path);
    }

    if (!config.output_csv_prefix.empty()) {
        if (!result.stress_history.empty()) {
            result.exportStressToCSV(config.output_csv_prefix + "_stress.csv");
        }
        if (!result.strain_history.empty()) {
            result.exportStrainToCSV(config.output_csv_prefix + "_strain.csv");
        }
        if (!result.surface_analysis.empty()) {
            result.exportSurfaceToCSV(config.output_csv_prefix + "_surface.csv");
        }
    }

    return result;
}

void SinglePassAnalyzer::fillMetadata(
    AnalysisResult& result,
    const AnalysisConfig& config
) {
    result.metadata.d3plot_path = config.d3plot_path;
    result.metadata.setCurrentDate();
    result.metadata.kood3plot_version = Version::get_version_string();
    result.metadata.num_states = static_cast<int32_t>(num_states_);

    // Get time range from stored results
    if (!stress_results_.empty() && !stress_results_[0].data.empty()) {
        result.metadata.start_time = stress_results_[0].data.front().time;
        result.metadata.end_time = stress_results_[0].data.back().time;
    } else if (!strain_results_.empty() && !strain_results_[0].data.empty()) {
        result.metadata.start_time = strain_results_[0].data.front().time;
        result.metadata.end_time = strain_results_[0].data.back().time;
    }

    // Analyzed parts
    result.metadata.analyzed_parts = part_ids_;
}

} // namespace analysis
} // namespace kood3plot
