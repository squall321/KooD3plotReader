/**
 * @file SinglePassAnalyzer.hpp
 * @brief High-performance single-pass analysis for d3plot files
 * @author KooD3plot Development Team
 * @date 2024-12-04
 *
 * This analyzer reads each state only once and performs all analyses
 * (stress, strain, surface stress) in a single pass, achieving ~47x
 * speedup compared to the naive multi-pass approach.
 *
 * Performance comparison:
 * - Multi-pass: ~46,624 state reads for 992 states, 23 parts
 * - Single-pass: 992 state reads (one per state)
 */

#pragma once

#include "kood3plot/D3plotReader.hpp"
#include "kood3plot/analysis/AnalysisResult.hpp"
#include "kood3plot/analysis/SurfaceExtractor.hpp"
#include "kood3plot/analysis/VectorMath.hpp"
#include <vector>
#include <unordered_map>
#include <functional>
#include <atomic>

#ifdef _OPENMP
#include <omp.h>
#endif

namespace kood3plot {
namespace analysis {

// Forward declarations (defined in TimeHistoryAnalyzer.hpp)
struct SurfaceAnalysisSpec;
struct AnalysisConfig;

/**
 * @brief Thread-local statistics accumulator for a part
 */
struct PartStateStats {
    double stress_max = -std::numeric_limits<double>::max();
    double stress_min = std::numeric_limits<double>::max();
    double stress_sum = 0.0;
    int32_t stress_max_elem = 0;
    int32_t stress_min_elem = 0;
    size_t stress_count = 0;

    double strain_max = -std::numeric_limits<double>::max();
    double strain_min = std::numeric_limits<double>::max();
    double strain_sum = 0.0;
    int32_t strain_max_elem = 0;
    size_t strain_count = 0;

    void reset() {
        stress_max = -std::numeric_limits<double>::max();
        stress_min = std::numeric_limits<double>::max();
        stress_sum = 0.0;
        stress_max_elem = 0;
        stress_min_elem = 0;
        stress_count = 0;

        strain_max = -std::numeric_limits<double>::max();
        strain_min = std::numeric_limits<double>::max();
        strain_sum = 0.0;
        strain_max_elem = 0;
        strain_count = 0;
    }

    void merge(const PartStateStats& other) {
        if (other.stress_max > stress_max) {
            stress_max = other.stress_max;
            stress_max_elem = other.stress_max_elem;
        }
        if (other.stress_min < stress_min) {
            stress_min = other.stress_min;
            stress_min_elem = other.stress_min_elem;
        }
        stress_sum += other.stress_sum;
        stress_count += other.stress_count;

        if (other.strain_max > strain_max) {
            strain_max = other.strain_max;
            strain_max_elem = other.strain_max_elem;
        }
        if (other.strain_min < strain_min) {
            strain_min = other.strain_min;
        }
        strain_sum += other.strain_sum;
        strain_count += other.strain_count;
    }
};

/**
 * @brief Surface stress accumulator for a single state
 */
struct SurfaceStateStats {
    double von_mises_max = -std::numeric_limits<double>::max();
    double von_mises_min = std::numeric_limits<double>::max();
    double von_mises_sum = 0.0;
    int32_t von_mises_max_elem = 0;

    double normal_max = -std::numeric_limits<double>::max();
    double normal_min = std::numeric_limits<double>::max();
    double normal_sum = 0.0;
    int32_t normal_max_elem = 0;

    double shear_max = -std::numeric_limits<double>::max();
    double shear_min = std::numeric_limits<double>::max();
    double shear_sum = 0.0;
    int32_t shear_max_elem = 0;

    size_t count = 0;

    void reset() {
        von_mises_max = -std::numeric_limits<double>::max();
        von_mises_min = std::numeric_limits<double>::max();
        von_mises_sum = 0.0;
        von_mises_max_elem = 0;
        normal_max = -std::numeric_limits<double>::max();
        normal_min = std::numeric_limits<double>::max();
        normal_sum = 0.0;
        normal_max_elem = 0;
        shear_max = -std::numeric_limits<double>::max();
        shear_min = std::numeric_limits<double>::max();
        shear_sum = 0.0;
        shear_max_elem = 0;
        count = 0;
    }

    void merge(const SurfaceStateStats& other) {
        if (other.von_mises_max > von_mises_max) {
            von_mises_max = other.von_mises_max;
            von_mises_max_elem = other.von_mises_max_elem;
        }
        if (other.von_mises_min < von_mises_min) {
            von_mises_min = other.von_mises_min;
        }
        von_mises_sum += other.von_mises_sum;

        if (other.normal_max > normal_max) {
            normal_max = other.normal_max;
            normal_max_elem = other.normal_max_elem;
        }
        if (other.normal_min < normal_min) {
            normal_min = other.normal_min;
        }
        normal_sum += other.normal_sum;

        if (other.shear_max > shear_max) {
            shear_max = other.shear_max;
            shear_max_elem = other.shear_max_elem;
        }
        if (other.shear_min < shear_min) {
            shear_min = other.shear_min;
        }
        shear_sum += other.shear_sum;

        count += other.count;
    }
};

/**
 * @brief Progress callback type
 */
using SinglePassProgressCallback = std::function<void(
    size_t current_state,
    size_t total_states,
    const std::string& message
)>;

/**
 * @brief High-performance single-pass analyzer
 *
 * Reads each state only once and performs all analyses simultaneously.
 * Uses OpenMP for parallel processing of elements within each state.
 */
class SinglePassAnalyzer {
public:
    /**
     * @brief Constructor
     * @param reader D3plotReader reference (must be opened)
     */
    explicit SinglePassAnalyzer(D3plotReader& reader);

    /**
     * @brief Destructor
     */
    ~SinglePassAnalyzer() = default;

    /**
     * @brief Run complete analysis in single pass (auto-selects best method)
     * @param config Analysis configuration
     * @return AnalysisResult containing all data
     */
    AnalysisResult analyze(const AnalysisConfig& config);

    /**
     * @brief Run analysis with progress callback (auto-selects best method)
     * @param config Analysis configuration
     * @param callback Progress callback
     * @return AnalysisResult containing all data
     */
    AnalysisResult analyze(const AnalysisConfig& config,
                           SinglePassProgressCallback callback);

    /**
     * @brief Run analysis with state-level parallelization (optimized)
     *
     * This method parallelizes the outer state loop instead of the inner
     * element loop, reducing OpenMP overhead from O(num_states) to O(1).
     *
     * Performance: ~2-4x faster than element-level parallelization for
     * large numbers of states (>100) with many parts.
     *
     * @param config Analysis configuration
     * @return AnalysisResult containing all data
     */
    AnalysisResult analyzeParallel(const AnalysisConfig& config);

    /**
     * @brief Run analysis with state-level parallelization with callback
     * @param config Analysis configuration
     * @param callback Progress callback
     * @return AnalysisResult containing all data
     */
    AnalysisResult analyzeParallel(const AnalysisConfig& config,
                                   SinglePassProgressCallback callback);

    /**
     * @brief Run analysis with element-level parallelization (legacy)
     *
     * This is the original implementation that parallelizes the inner
     * element loop. Kept for compatibility and comparison purposes.
     *
     * @param config Analysis configuration
     * @return AnalysisResult containing all data
     */
    AnalysisResult analyzeLegacy(const AnalysisConfig& config);

    /**
     * @brief Run analysis with element-level parallelization with callback
     * @param config Analysis configuration
     * @param callback Progress callback
     * @return AnalysisResult containing all data
     */
    AnalysisResult analyzeLegacy(const AnalysisConfig& config,
                                 SinglePassProgressCallback callback);

    /**
     * @brief Set whether to use state-level parallelization by default
     * @param enable true to use state-level (new), false for element-level (legacy)
     */
    void setUseStateLevelParallel(bool enable) { use_state_level_parallel_ = enable; }

    /**
     * @brief Check if state-level parallelization is enabled
     */
    bool isStateLevelParallel() const { return use_state_level_parallel_; }

    /**
     * @brief Get last error message
     */
    const std::string& getLastError() const { return last_error_; }

    /**
     * @brief Check if analysis was successful
     */
    bool wasSuccessful() const { return success_; }

private:
    D3plotReader& reader_;
    std::string last_error_;
    bool success_ = false;
    bool use_state_level_parallel_ = true;  // Default to optimized state-level parallelization

    // Geometry data (read once)
    data::Mesh mesh_;
    int32_t nv3d_ = 0;  // Values per solid element
    size_t num_solid_elements_ = 0;
    size_t num_states_ = 0;  // Number of states (set after read_all_states)

    // Element to part mapping
    std::vector<int32_t> elem_to_part_;  // elem_index -> part_id
    std::unordered_map<int32_t, size_t> elem_id_to_index_;

    // Part information
    std::vector<int32_t> part_ids_;  // Unique part IDs
    std::unordered_map<int32_t, size_t> part_id_to_result_index_;

    // Surface data (for surface stress analysis)
    std::vector<std::vector<Face>> surface_faces_;  // Per surface spec
    std::vector<SurfaceAnalysisSpec> surface_specs_;

    // Results storage
    std::vector<PartTimeSeriesStats> stress_results_;
    std::vector<PartTimeSeriesStats> strain_results_;
    std::vector<SurfaceAnalysisStats> surface_results_;

    // ========================================
    // Initialization
    // ========================================

    /**
     * @brief Initialize analyzer (read mesh, build mappings)
     */
    bool initialize(const AnalysisConfig& config);

    /**
     * @brief Build element to part mapping
     */
    void buildElementMapping();

    /**
     * @brief Initialize result storage
     */
    void initializeResults(size_t num_states, const AnalysisConfig& config);

    /**
     * @brief Extract surfaces for surface stress analysis
     */
    void extractSurfaces(const AnalysisConfig& config);

    // ========================================
    // Single-pass analysis
    // ========================================

    /**
     * @brief Process a single state (all analyses)
     * @param state_idx State index
     * @param state State data
     * @param config Analysis configuration
     */
    void processState(size_t state_idx,
                      const data::StateData& state,
                      const AnalysisConfig& config);

    /**
     * @brief Analyze all parts for stress/strain (OpenMP element-level parallel - legacy)
     */
    void analyzePartStats(size_t state_idx,
                          const data::StateData& state,
                          bool analyze_stress,
                          bool analyze_strain);

    /**
     * @brief Analyze all parts for stress/strain (sequential - for state-level parallel)
     */
    void analyzePartStatsSequential(size_t state_idx,
                                    const data::StateData& state,
                                    bool analyze_stress,
                                    bool analyze_strain);

    /**
     * @brief Analyze surface stress for all surface specs (OpenMP element-level parallel - legacy)
     */
    void analyzeSurfaceStats(size_t state_idx,
                             const data::StateData& state);

    /**
     * @brief Analyze surface stress for all surface specs (sequential - for state-level parallel)
     */
    void analyzeSurfaceStatsSequential(size_t state_idx,
                                       const data::StateData& state);

    // ========================================
    // Stress/Strain extraction
    // ========================================

    /**
     * @brief Extract Von Mises stress for an element
     */
    double extractVonMises(const std::vector<double>& solid_data, size_t elem_idx);

    /**
     * @brief Extract effective plastic strain for an element
     */
    double extractEffPlasticStrain(const std::vector<double>& solid_data, size_t elem_idx);

    /**
     * @brief Extract stress tensor for an element
     */
    StressTensor extractStressTensor(const std::vector<double>& solid_data, size_t elem_idx);

    // ========================================
    // Result finalization
    // ========================================

    /**
     * @brief Build final AnalysisResult from accumulated data
     */
    AnalysisResult buildResult(const AnalysisConfig& config);

    /**
     * @brief Fill metadata in result
     */
    void fillMetadata(AnalysisResult& result, const AnalysisConfig& config);
};

} // namespace analysis
} // namespace kood3plot
