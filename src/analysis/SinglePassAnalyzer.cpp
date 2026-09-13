/**
 * @file SinglePassAnalyzer.cpp
 * @brief Implementation of high-performance single-pass analysis
 */

#include "kood3plot/analysis/SinglePassAnalyzer.hpp"
#include "kood3plot/analysis/HotspotClusterAnalyzer.hpp"
#include <limits>
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

    // 요소별 시간축 극값 (핫스팟 군집 입력). 같은 2차 패스 그룹.
    if (config.hotspot_enabled) {
        accumulateElementExtremes(all_states, resolveHotspotCriteria(config.hotspot_criteria));
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

    // 요소별 시간축 극값 (핫스팟 군집 입력). 같은 2차 패스 그룹.
    if (config.hotspot_enabled) {
        accumulateElementExtremes(all_states, resolveHotspotCriteria(config.hotspot_criteria));
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

    // 요소별 시간축 극값 (핫스팟 군집 입력). 같은 2차 패스 그룹.
    if (config.hotspot_enabled) {
        accumulateElementExtremes(all_states, resolveHotspotCriteria(config.hotspot_criteria));
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
    // 🔴 NEL8 < 0 은 10절점 솔리드 표시다(개수 = |NEL8|). 부호째 size_t 에 넣으면
    //    1.8e19 가 되어 아래 resize 에서 죽는다. 형상·상태 파서는 이미 abs 를 쓴다.
    num_solid_elements_ = static_cast<size_t>(std::abs(control_data.NEL8));
    has_strain_tensor_ = (control_data.ISTRN != 0 && nv3d_ >= 13);

    num_shell_elements_ = control_data.NEL4 > 0 ? static_cast<size_t>(control_data.NEL4) : 0;
    num_tshell_elements_ = control_data.NELT > 0 ? static_cast<size_t>(control_data.NELT) : 0;
    nv2d_ = control_data.NV2D;
    nv3dt_ = control_data.NV3DT;
    maxint_ = control_data.MAXINT;      // ControlData 가 MDLOPT 부호를 이미 벗겼다
    neips_ = control_data.NEIPS;
    ndim_ = control_data.NDIM;
    numds_ = control_data.NUMDS;
    for (int i = 0; i < 4; ++i) ioshl_[i] = control_data.IOSHL[i];

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
        vm_strain_results_.resize(num_parts);
        max_principal_strain_results_.resize(num_parts);
        min_principal_strain_results_.resize(num_parts);
        for (size_t i = 0; i < num_parts; ++i) {
            vm_strain_results_[i].part_id = part_ids_[i];
            vm_strain_results_[i].quantity = "von_mises_strain";
            vm_strain_results_[i].unit = "";
            vm_strain_results_[i].data.resize(num_states);

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

                    const double evm = vonMisesStrainOf(etensor);
                    if (evm > stats.vm_strain_max) {
                        stats.vm_strain_max = evm;
                        stats.vm_strain_max_elem = elem_id;
                    }
                    if (evm < stats.vm_strain_min) stats.vm_strain_min = evm;
                    stats.vm_strain_sum += evm;

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

                const double evm = vonMisesStrainOf(etensor);
                if (evm > stats.vm_strain_max) {
                    stats.vm_strain_max = evm;
                    stats.vm_strain_max_elem = elem_id;
                }
                if (evm < stats.vm_strain_min) stats.vm_strain_min = evm;
                stats.vm_strain_sum += evm;

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

            // von Mises 등가 변형률
            if (i < vm_strain_results_.size()) {
                auto& tvm = vm_strain_results_[i].data[state_idx];
                tvm.time = state.time;
                tvm.max_value = stats.vm_strain_max;
                tvm.min_value = stats.vm_strain_min;
                tvm.avg_value = (stats.principal_strain_count > 0) ?
                                stats.vm_strain_sum / stats.principal_strain_count : 0.0;
                tvm.max_element_id = stats.vm_strain_max_elem;
            }

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

                const double evm = vonMisesStrainOf(etensor);
                if (evm > stats.vm_strain_max) {
                    stats.vm_strain_max = evm;
                    stats.vm_strain_max_elem = elem_id;
                }
                if (evm < stats.vm_strain_min) stats.vm_strain_min = evm;
                stats.vm_strain_sum += evm;

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

            // von Mises 등가 변형률 (병렬 집계 경로 — 순차 경로와 같은 값)
            if (i < vm_strain_results_.size()) {
                auto& tvm = vm_strain_results_[i].data[state_idx];
                tvm.time = state.time;
                tvm.max_value = stats.vm_strain_max;
                tvm.min_value = stats.vm_strain_min;
                tvm.avg_value = (stats.principal_strain_count > 0) ?
                                stats.vm_strain_sum / stats.principal_strain_count : 0.0;
                tvm.max_element_id = stats.vm_strain_max_elem;
            }

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
// 🔴 d3plot solid 변형률은 **NEIPH 확장값의 마지막 6개**다. 규격 원문:
//      7.         유효소성변형률
//      8..        NEIPH extra values
//      7+NEIPH-5 .. 7+NEIPH   Epsilon-x .. Epsilon-zx      (1-based)
//    NV3D = 7 + NEIPH 이므로 0-based 시작은 base + NV3D - 6 이다.
//    `base + 7` 은 NEIPH == 6 (NV3D == 13) 일 때만 우연히 맞는다.
//    실덱 확인: /data/battery_study 의 덱 10개가 NV3D 26~30 이라
//    올바른 위치는 base+20~24 인데 base+7 은 이력변수 슬롯을 읽는다.
    if (nv3d_ < 13) return StressTensor(0, 0, 0, 0, 0, 0);
    const size_t base = elem_idx * nv3d_;
    const size_t off = base + static_cast<size_t>(nv3d_) - 6;
    if (off + 6 > solid_data.size()) {
        return StressTensor(0, 0, 0, 0, 0, 0);
    }

    return StressTensor(
        solid_data[off + 0],   // exx
        solid_data[off + 1],   // eyy
        solid_data[off + 2],   // ezz
        solid_data[off + 3],   // exy
        solid_data[off + 4],   // eyz
        solid_data[off + 5]    // ezx
    );
}

// ========================================
// Peak element tensor extraction
// ========================================

const ElementExtremes& SinglePassAnalyzer::elementExtremes(HotspotCriterion c) const {
    return elementExtremes(HotspotElementKind::Solid, c);
}

const ElementExtremes& SinglePassAnalyzer::elementExtremes(HotspotElementKind k, HotspotCriterion c) const {
    static const ElementExtremes kEmpty;
    auto it = elem_extremes_.find(ExtremesKey{k, c});
    return (it == elem_extremes_.end()) ? kEmpty : it->second;
}

std::vector<HotspotCriterion> SinglePassAnalyzer::resolveHotspotCriteria(
    const std::vector<std::string>& names,
    bool warn
) {
    std::vector<std::string> unknown;
    std::vector<HotspotCriterion> crits = parseHotspotCriteria(names, &unknown);
    if (!warn) {
        if (crits.empty()) crits.push_back(HotspotCriterion::VonMises);
        return crits;
    }
    for (const std::string& u : unknown) {
        std::cerr << "  [hotspot] 알 수 없는 기준량 무시 — '" << u
                  << "' (von_mises | max_principal | min_principal)\n";
    }
    if (crits.empty()) {
        // 전부 모르는 이름이거나 비었으면 기존 동작으로. 조용히 아무것도 안 내는 것보다 낫다.
        std::cerr << "  [hotspot] 유효한 기준량이 없어 von_mises 로 진행합니다.\n";
        crits.push_back(HotspotCriterion::VonMises);
    }
    return crits;
}

const std::vector<double>& SinglePassAnalyzer::plasticWorkDensity(
    HotspotElementKind k
) const {
    static const std::vector<double> kEmpty;
    auto it = elem_plastic_work_.find(k);
    return (it == elem_plastic_work_.end()) ? kEmpty : it->second;
}

void SinglePassAnalyzer::accumulateElementExtremes(
    const std::vector<data::StateData>& all_states,
    const std::vector<HotspotCriterion>& criteria
) {
    elem_extremes_.clear();
    shell_thickness_.clear();
    if (all_states.empty() || criteria.empty()) return;

    // 셸 계열 먼저 (솔리드 경로는 아래에서 기존 그대로)
    accumulateLayeredExtremes(all_states, criteria, HotspotElementKind::ThickShell);
    accumulateLayeredExtremes(all_states, criteria, HotspotElementKind::Shell);

    const size_t ne = num_solid_elements_;
    if (ne == 0) return;

    // 요청한 기준을 고정 슬롯(enum 값)으로 — 안쪽 루프에서 map 조회를 피한다.
    bool want[3] = {false, false, false};
    for (HotspotCriterion c : criteria) want[static_cast<int>(c)] = true;
    const bool need_vm = want[0];
    const bool need_pr = want[1] || want[2];

    // 🔴 NaN 으로 초기화한다. 0 이면 '응력 0' 과, −DBL_MAX 면 σ1·σ3 의 정상 음수와
    //    구분이 안 된다. 변형률은 0 으로 두고 아래 전량-0 판정을 그대로 쓴다.
    ElementExtremes* slot[3] = {nullptr, nullptr, nullptr};
    for (int k = 0; k < 3; ++k) {
        if (!want[k]) continue;
        ElementExtremes& ex = elem_extremes_[ExtremesKey{HotspotElementKind::Solid,
                                                          static_cast<HotspotCriterion>(k)}];
        ex.value.assign(ne, hotspotUnrecorded());
        ex.time.assign(ne, 0.0);
        if (has_strain_tensor_) ex.strain.assign(ne, 0.0); else ex.strain.clear();
        slot[k] = &ex;
    }

    const size_t ns = all_states.size();
    const bool strain_ok = has_strain_tensor_ && nv3d_ >= 13;

    // 소성일 밀도 w_p = ∫σ_vm dε_p.
    // ε_p 는 word 6 이라 변형률 텐서(STRFLG)와 무관하게 거의 모든 덱에서 나온다.
    // 상태가 1개뿐이면 증분이 없어 적분이 성립하지 않는다 — 배열을 비워 '미계산' 으로 둔다.
    std::vector<double>& work = elem_plastic_work_[HotspotElementKind::Solid];
    const bool work_ok = (nv3d_ >= 7) && (ns >= 2);
    if (work_ok) work.assign(ne, hotspotUnrecorded()); else work.clear();
    int64_t nonmono_total = 0;

    // 🔴 병렬화 축이 **요소**다. 기본 경로는 상태 루프에 omp 를 걸지만,
    //    요소별 극값은 모든 상태가 같은 elem_idx 를 갱신하므로 그 축으로
    //    병렬화하면 데이터 경쟁이 된다. 여기서는 각 스레드가 자기 요소만
    //    쓰므로 경쟁이 원천적으로 없다(락·원자연산 불필요).
#ifdef _OPENMP
    #pragma omp parallel for schedule(static) reduction(+:nonmono_total)
#endif
    for (int64_t ei = 0; ei < static_cast<int64_t>(ne); ++ei) {
        // k=0 VM(max), k=1 σ1(max), k=2 σ3(min)
        double best[3]   = {-std::numeric_limits<double>::max(),
                            -std::numeric_limits<double>::max(),
                             std::numeric_limits<double>::max()};
        double best_t[3] = {0.0, 0.0, 0.0};
        double best_e[3] = {0.0, 0.0, 0.0};
        bool   seen = false;

        // 소성일 적분용 직전 상태값 (사다리꼴) + 러닝맥스
        double prev_vm = 0.0, prev_ep = 0.0, ep_run_max = 0.0;
        bool   have_prev = false;
        double w_acc = 0.0;
        bool   w_any = false;
        int    nonmono = 0;

        for (size_t si = 0; si < ns; ++si) {
            const auto& sd = all_states[si].solid_data;
            if (sd.empty()) continue;

            const size_t base = static_cast<size_t>(ei) * nv3d_;
            if (base + 6 > sd.size()) continue;   // 이 상태에는 이 요소가 없다
            seen = true;

            const double sxx = sd[base + 0], syy = sd[base + 1], szz = sd[base + 2];
            const double sxy = sd[base + 3], syz = sd[base + 4], szx = sd[base + 5];

            // ── 소성일 누적 — 극값 갱신 여부와 무관하게 **모든 상태**에서 해야 한다 ──
            if (work_ok && base + 7 <= sd.size()) {
                const double vm_now = equivalentStress(sxx, syy, szz, sxy, syz, szx);
                const double ep_now = sd[base + 6];
                if (have_prev) {
                    // ε_p 는 이론상 단조증가지만 실덱에서 오르내리는 경우가 있다
                    // (word 6 을 다른 이력변수로 쓰는 재료, 요소 소거 등).
                    // '음수만 버리기' 는 그 오르내림을 정류해 잡음을 누적한다.
                    // **지금까지의 최댓값을 넘어선 만큼만** 더해 중복 계산을 막는다.
                    const double dep = ep_now - ep_run_max;
                    if (dep > 0.0) { w_acc += 0.5 * (vm_now + prev_vm) * dep; w_any = true; }
                    if (ep_now < prev_ep) ++nonmono;
                }
                if (ep_now > ep_run_max) ep_run_max = ep_now;
                prev_vm = vm_now; prev_ep = ep_now; have_prev = true;
            }

            // 이 상태의 기준값들 — 필요한 것만, 주응력은 한 번만 분해
            double cur[3] = {0.0, 0.0, 0.0};
            if (need_vm) cur[0] = equivalentStress(sxx, syy, szz, sxy, syz, szx);
            if (need_pr) {
                const StressTensor st{sxx, syy, szz, sxy, syz, szx};
                const auto pr = st.principalStresses();   // 내림차순 [σ1, σ2, σ3]
                cur[1] = pr[0];
                cur[2] = pr[2];
            }

            // 갱신이 필요한 기준이 하나라도 있으면 짝 변형률을 그때 계산
            bool upd[3] = {false, false, false};
            if (want[0] && cur[0] > best[0]) upd[0] = true;
            if (want[1] && cur[1] > best[1]) upd[1] = true;
            if (want[2] && cur[2] < best[2]) upd[2] = true;
            if (!(upd[0] || upd[1] || upd[2])) continue;

            double eq_e = 0.0, e1 = 0.0, e3 = 0.0;
            bool have_e = false;
            if (strain_ok) {
                // 변형률 위치는 base + nv3d_ - 6 (NEIPH 확장값의 마지막 6개).
                // extractStrainTensor 와 같은 규약 — 자세한 근거는 그쪽 주석 참조.
                const size_t eo = base + static_cast<size_t>(nv3d_) - 6;
                if (eo + 6 <= sd.size()) {
                    have_e = true;
                    if (upd[0]) {
                        eq_e = equivalentStrain(sd[eo + 0], sd[eo + 1], sd[eo + 2],
                                                sd[eo + 3], sd[eo + 4], sd[eo + 5]);
                    }
                    if (upd[1] || upd[2]) {
                        // d3plot 변형률 성분은 **텐서 성분**이라 고유값이 곧 주변형률이다.
                        const StressTensor et{sd[eo + 0], sd[eo + 1], sd[eo + 2],
                                              sd[eo + 3], sd[eo + 4], sd[eo + 5]};
                        const auto pe = et.principalStresses();
                        e1 = pe[0];
                        e3 = pe[2];
                    }
                }
            }
            const double t = all_states[si].time;
            if (upd[0]) { best[0] = cur[0]; best_t[0] = t; if (have_e) best_e[0] = eq_e; }
            if (upd[1]) { best[1] = cur[1]; best_t[1] = t; if (have_e) best_e[1] = e1; }
            if (upd[2]) { best[2] = cur[2]; best_t[2] = t; if (have_e) best_e[2] = e3; }
        }

        for (int k = 0; k < 3; ++k) {
            if (!slot[k]) continue;
            if (seen) {
                slot[k]->value[ei] = best[k];
                slot[k]->time[ei] = best_t[k];
                if (!slot[k]->strain.empty()) slot[k]->strain[ei] = best_e[k];
            }
            // seen 이 아니면 NaN(미기록) 그대로
        }
        // 증분을 한 번도 못 본 요소는 '적분 못 함'(NaN)으로 남긴다.
        // 소성 증분이 실제로 0 이었던 요소(탄성만)는 w_any 로 구분해 0 을 기록한다.
        if (work_ok && seen && have_prev) work[ei] = w_any ? w_acc : 0.0;
        nonmono_total += nonmono;
    }


    // ε_p 가 오르내리면 word 6 이 유효소성변형률이 아닐 수 있다(다른 이력변수·요소 소거).
    // 조용히 넘어가면 에너지를 실제 손상으로 오독한다 — 비율을 알린다.
    if (work_ok && ne > 0) {
        const int64_t trans = static_cast<int64_t>(ne) * (static_cast<int64_t>(ns) - 1);
        if (trans > 0 && nonmono_total * 10 > trans) {
            std::cerr << "  [hotspot] 소성일: ε_p 가 감소한 전이가 "
                      << (100.0 * static_cast<double>(nonmono_total) / static_cast<double>(trans))
                      << "% — word 6 이 유효소성변형률이 아닐 수 있습니다."
                      << " 누적은 이력 최댓값 초과분만 더합니다.\n";
        }
    }

    // 🔴 변형률 슬롯은 있는데 솔버가 채우지 않은 덱이 있다(예: IDTDT=100).
    //    그대로 두면 핫스팟이 strain_available=true 로 '측정했고 0' 을 보고해,
    //    소비 측이 "소성변형이 전혀 없음" 이라는 반대 결론을 낸다.
    //    같은 파일 buildResult() 가 주변형률에 대해 이미 쓰는 판정을 그대로 적용해
    //    배열을 비운다 — 비면 하류가 변형률 항목을 자연스럽게 건너뛴다.
    //    기준별로 따로 본다 — 기준마다 다른 측도(등가/ε1/ε3)를 담기 때문.
    bool warned = false;
    for (int k = 0; k < 3; ++k) {
        if (!slot[k] || slot[k]->strain.empty()) continue;
        bool all_zero = true;
        for (double v : slot[k]->strain) {
            if (v != 0.0) { all_zero = false; break; }
        }
        if (all_zero) {
            if (!warned) {
                std::cout << "  [hotspot] 변형률 텐서가 전부 0 — 솔버가 기록하지 않은 것으로 "
                             "보고 핫스팟 변형률 통계를 생략합니다 "
                             "(*DATABASE_EXTENT_BINARY STRFLG 확인).\n";
                warned = true;
            }
            slot[k]->strain.clear();
        }
    }
}

void SinglePassAnalyzer::accumulateLayeredExtremes(
    const std::vector<data::StateData>& all_states,
    const std::vector<HotspotCriterion>& criteria,
    HotspotElementKind kind
) {
    const bool is_shell = (kind == HotspotElementKind::Shell);
    const size_t ne = is_shell ? num_shell_elements_ : num_tshell_elements_;
    const int nv = is_shell ? nv2d_ : nv3dt_;
    const char* kname = is_shell ? "셸" : "두꺼운 셸";
    if (ne == 0 || nv <= 0) return;

    if (is_shell && (ndim_ == 5 || ndim_ == 7)) {
        // DCOMP=2: 강체 셸 데이터가 빠진 채 압축돼 요소 인덱스가 어긋난다.
        std::cerr << "  [hotspot] " << kname << ": 강체 셸 압축 덱(NDIM=" << ndim_
                  << ", DCOMP=2) — 요소 인덱스를 신뢰할 수 없어 건너뜁니다.\n";
        return;
    }
    if (ioshl_[0] == 0 || maxint_ <= 0) {
        std::cerr << "  [hotspot] " << kname << ": 응력이 기록되지 않은 덱(IOSHL(1)=" << ioshl_[0]
                  << ", MAXINT=" << maxint_ << ") — 건너뜁니다.\n";
        return;
    }

    // ── 배치 자기 검증 ──
    const int P = 6 * ioshl_[0] + ioshl_[1] + neips_;
    const int lw = maxint_ * P;                    // 층 데이터 워드 수
    int strain_off = -1;                           // 요소 시작 기준, 안쪽 면 6 + 바깥쪽 면 6
    int thick_off = -1;
    if (is_shell) {
        const int fixed = lw + 8 * ioshl_[2] + 4 * ioshl_[3];
        const int rem = nv - fixed;
        if (rem == 12) {
            // 두께·요소변수 2개 뒤, 내부에너지 앞 (규격 30–44 번)
            strain_off = lw + 8 * ioshl_[2] + 3 * ioshl_[3];
        } else if (rem != 0) {
            std::cerr << "  [hotspot] " << kname << ": NV2D=" << nv << " 이 규격 공식("
                      << fixed << " 또는 " << fixed + 12 << ")과 맞지 않아 건너뜁니다.\n";
            return;
        }
        if (ioshl_[3]) thick_off = lw + 8 * ioshl_[2];
    } else {
        const int rem = nv - lw;                   // 12·ISTRN + (TSHENG ? 1 : 0)
        if (rem == 12 || rem == 13) {
            strain_off = lw;
        } else if (rem != 0 && rem != 1) {
            std::cerr << "  [hotspot] " << kname << ": NV3DT=" << nv << " 이 규격 공식("
                      << lw << "+{0,1,12,13})과 맞지 않아 건너뜁니다.\n";
            return;
        }
    }
    const bool mio = (maxint_ >= 3 && numds_ >= 0);   // 0 중립·1 안쪽·2 바깥쪽
    layer_scheme_ = mio ? "mid_inner_outer" : "index";
    const bool strain_ok = (strain_off >= 0);

    bool want[3] = {false, false, false};
    for (HotspotCriterion c : criteria) want[static_cast<int>(c)] = true;
    const bool need_vm = want[0];
    const bool need_pr = want[1] || want[2];

    ElementExtremes* slot[3] = {nullptr, nullptr, nullptr};
    for (int k = 0; k < 3; ++k) {
        if (!want[k]) continue;
        ElementExtremes& ex = elem_extremes_[ExtremesKey{kind, static_cast<HotspotCriterion>(k)}];
        ex.value.assign(ne, hotspotUnrecorded());
        ex.time.assign(ne, 0.0);
        ex.layer.assign(ne, static_cast<int8_t>(-1));
        if (strain_ok) ex.strain.assign(ne, 0.0); else ex.strain.clear();
        slot[k] = &ex;
    }

    // 셸 두께 — 초기 상태(첫 상태)의 두께 워드. 초기 형상 기준 도심과 짝을 맞춘다.
    if (is_shell && thick_off >= 0) {
        const auto& sd0 = all_states.front().shell_data;
        if (sd0.size() >= ne * static_cast<size_t>(nv)) {
            shell_thickness_.assign(ne, 0.0);
            for (size_t e = 0; e < ne; ++e) shell_thickness_[e] = sd0[e * nv + thick_off];
        }
    }

    // 짝 변형률: 극값 층의 면. 중립면이면 두 면 텐서 평균(Kirchhoff 선형 분포),
    // 그 밖이면 두 면 중 기준 방향으로 뜨거운 쪽.
    auto strain_measure = [](int k, const double* t) -> double {
        if (k == 0) return equivalentStrain(t[0], t[1], t[2], t[3], t[4], t[5]);
        const StressTensor et{t[0], t[1], t[2], t[3], t[4], t[5]};
        const auto pe = et.principalStresses();
        return (k == 1) ? pe[0] : pe[2];
    };
    auto paired = [&](int k, int layer, const double* ein, const double* eout) -> double {
        if (mio && layer == 1) return strain_measure(k, ein);
        if (mio && layer == 2) return strain_measure(k, eout);
        if (mio && layer == 0) {
            double m[6];
            for (int q = 0; q < 6; ++q) m[q] = 0.5 * (ein[q] + eout[q]);
            return strain_measure(k, m);
        }
        const double a = strain_measure(k, ein), b = strain_measure(k, eout);
        return hotspotHotter(static_cast<HotspotCriterion>(k), a, b) ? a : b;
    };

    const size_t ns = all_states.size();

    // 소성일 밀도 — 적분점(층) 평균 σ_vm·ε_p 로 두께 방향을 대표시킨다.
    // ε_p 는 층 블록 안에서 응력 6워드 다음(ioshl_[1]) 이다.
    const int ep_off = 6 * ioshl_[0];
    const bool work_ok = (ioshl_[1] != 0) && (ns >= 2) && (P >= ep_off + 1);
    std::vector<double>& work = elem_plastic_work_[kind];
    if (work_ok) work.assign(ne, hotspotUnrecorded()); else work.clear();
    int64_t nonmono_total = 0;

#ifdef _OPENMP
    #pragma omp parallel for schedule(static) reduction(+:nonmono_total)
#endif
    for (int64_t ei = 0; ei < static_cast<int64_t>(ne); ++ei) {
        double best[3]   = {-std::numeric_limits<double>::max(),
                            -std::numeric_limits<double>::max(),
                             std::numeric_limits<double>::max()};
        double best_t[3] = {0.0, 0.0, 0.0};
        double best_e[3] = {0.0, 0.0, 0.0};
        int    best_l[3] = {-1, -1, -1};
        bool   seen = false;
        double prev_vm = 0.0, prev_ep = 0.0, ep_run_max = 0.0;
        bool   have_prev = false;
        double w_acc = 0.0;
        bool   w_any = false;
        int    nonmono = 0;

        for (size_t si = 0; si < ns; ++si) {
            const auto& sd = is_shell ? all_states[si].shell_data : all_states[si].thick_shell_data;
            const size_t base = static_cast<size_t>(ei) * static_cast<size_t>(nv);
            if (sd.empty() || base + static_cast<size_t>(nv) > sd.size()) continue;
            seen = true;

            // 층별 기준값 — 이 상태에서 가장 뜨거운 층
            double cur[3] = {-std::numeric_limits<double>::max(),
                             -std::numeric_limits<double>::max(),
                              std::numeric_limits<double>::max()};
            int cur_l[3] = {-1, -1, -1};
            for (int L = 0; L < maxint_; ++L) {
                const double* s6 = &sd[base + static_cast<size_t>(L) * P];
                if (need_vm) {
                    const double vm = equivalentStress(s6[0], s6[1], s6[2], s6[3], s6[4], s6[5]);
                    if (vm > cur[0]) { cur[0] = vm; cur_l[0] = L; }
                }
                if (need_pr) {
                    const StressTensor st{s6[0], s6[1], s6[2], s6[3], s6[4], s6[5]};
                    const auto pr = st.principalStresses();
                    if (pr[0] > cur[1]) { cur[1] = pr[0]; cur_l[1] = L; }
                    if (pr[2] < cur[2]) { cur[2] = pr[2]; cur_l[2] = L; }
                }
            }

            // ── 소성일 누적 — 극값 갱신과 무관하게 모든 상태에서 ──
            if (work_ok) {
                double vm_sum = 0.0, ep_sum = 0.0;
                for (int L = 0; L < maxint_; ++L) {
                    const double* s6 = &sd[base + static_cast<size_t>(L) * P];
                    vm_sum += equivalentStress(s6[0], s6[1], s6[2], s6[3], s6[4], s6[5]);
                    ep_sum += s6[ep_off];
                }
                const double inv = 1.0 / static_cast<double>(maxint_);
                const double vm_now = vm_sum * inv, ep_now = ep_sum * inv;
                if (have_prev) {
                    // 솔리드와 같은 규칙 — 러닝맥스 초과분만 (정류 잡음 방지)
                    const double dep = ep_now - ep_run_max;
                    if (dep > 0.0) { w_acc += 0.5 * (vm_now + prev_vm) * dep; w_any = true; }
                    if (ep_now < prev_ep) ++nonmono;
                }
                if (ep_now > ep_run_max) ep_run_max = ep_now;
                prev_vm = vm_now; prev_ep = ep_now; have_prev = true;
            }

            bool upd[3] = {false, false, false};
            if (want[0] && cur[0] > best[0]) upd[0] = true;
            if (want[1] && cur[1] > best[1]) upd[1] = true;
            if (want[2] && cur[2] < best[2]) upd[2] = true;
            if (!(upd[0] || upd[1] || upd[2])) continue;

            const double t = all_states[si].time;
            const double* ein = strain_ok ? &sd[base + strain_off] : nullptr;
            const double* eout = strain_ok ? &sd[base + strain_off + 6] : nullptr;
            for (int k = 0; k < 3; ++k) {
                if (!upd[k]) continue;
                best[k] = cur[k]; best_t[k] = t; best_l[k] = cur_l[k];
                if (strain_ok) best_e[k] = paired(k, cur_l[k], ein, eout);
            }
        }

        for (int k = 0; k < 3; ++k) {
            if (!slot[k] || !seen) continue;          // seen 이 아니면 NaN(미기록)
            slot[k]->value[ei] = best[k];
            slot[k]->time[ei] = best_t[k];
            slot[k]->layer[ei] = static_cast<int8_t>(best_l[k]);
            if (!slot[k]->strain.empty()) slot[k]->strain[ei] = best_e[k];
        }
        if (work_ok && seen && have_prev) work[ei] = w_any ? w_acc : 0.0;
        nonmono_total += nonmono;
    }

    // 변형률 슬롯은 있는데 전부 0 → 솔버가 안 채운 것 (솔리드 경로와 같은 판정)
    for (int k = 0; k < 3; ++k) {
        if (!slot[k] || slot[k]->strain.empty()) continue;
        bool all_zero = true;
        for (double v : slot[k]->strain) { if (v != 0.0) { all_zero = false; break; } }
        if (all_zero) slot[k]->strain.clear();
    }
}

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
    result.vm_strain_history = std::move(vm_strain_results_);
    result.max_principal_strain_history = std::move(max_principal_strain_results_);
    result.min_principal_strain_history = std::move(min_principal_strain_results_);

    // 변형률 텐서 슬롯은 있는데 솔버가 채우지 않은 경우가 있다. 그대로 두면
    // "변형률 0" 을 참값처럼 내보내게 된다 — '미기록' 과 '0 이었음' 은 다르다.
    // 전 파트·전 상태가 정확히 0 이면 주변형률 결과를 통째로 버려 downstream
    // 이 그 항목을 자연스럽게 건너뛰게 한다(에러가 아니라 누락).
    // 실측: Test_006 은 IDTDT=100(소성변형률 텐서 별도 기록)이라 NEIPH 쪽
    // element_solid_strain 이 전부 0 이었다(lasso 로 확인).
    {
        auto all_zero = [](const std::vector<PartTimeSeriesStats>& v) {
            for (const auto& s : v) {
                if (s.globalMax() != 0.0 || s.globalMin() != 0.0) return false;
            }
            return true;
        };
        if (!result.max_principal_strain_history.empty()
            && all_zero(result.max_principal_strain_history)
            && all_zero(result.min_principal_strain_history)) {
            std::cout << "  [strain] 주변형률 텐서가 전부 0 — 솔버가 기록하지 않은 "
                         "것으로 보고 주변형률 산출물을 생략합니다 "
                         "(*DATABASE_EXTENT_BINARY STRFLG 확인).\n";
            result.max_principal_strain_history.clear();
            result.min_principal_strain_history.clear();
            result.vm_strain_history.clear();
        }
    }
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
