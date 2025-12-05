/**
 * @file MotionAnalyzer.hpp
 * @brief Part motion analysis (displacement, velocity, acceleration)
 * @author KooD3plot Development Team
 * @date 2025-12-04
 *
 * Provides motion analysis for parts:
 * - Average displacement (center of mass motion)
 * - Average velocity (numerical differentiation)
 * - Average acceleration (numerical differentiation)
 * - Maximum displacement tracking
 *
 * Usage:
 * @code
 * D3plotReader reader("d3plot");
 * reader.read_geometry();
 *
 * MotionAnalyzer analyzer(reader);
 * analyzer.setParts({1, 2, 3});  // or empty for all parts
 *
 * auto states = reader.read_all_states();
 * for (const auto& state : states) {
 *     analyzer.processState(state);
 * }
 *
 * auto results = analyzer.getResults();
 * @endcode
 */

#pragma once

#include "kood3plot/D3plotReader.hpp"
#include "kood3plot/analysis/AnalysisTypes.hpp"
#include "kood3plot/analysis/VectorMath.hpp"
#include <vector>
#include <unordered_map>
#include <unordered_set>

namespace kood3plot {
namespace analysis {

/**
 * @brief Part motion analyzer
 *
 * Analyzes motion of parts by computing:
 * - Average displacement from initial position
 * - Average velocity (d(displacement)/dt)
 * - Average acceleration (d(velocity)/dt)
 * - Maximum displacement node tracking
 */
class MotionAnalyzer {
public:
    /**
     * @brief Constructor
     * @param reader D3plotReader (must have geometry already read)
     */
    explicit MotionAnalyzer(D3plotReader& reader);

    /**
     * @brief Destructor
     */
    ~MotionAnalyzer() = default;

    /**
     * @brief Set parts to analyze
     * @param part_ids Part IDs (empty = all parts)
     */
    void setParts(const std::vector<int32_t>& part_ids);

    /**
     * @brief Initialize analyzer (call before processing states)
     * @return true if successful
     */
    bool initialize();

    /**
     * @brief Process a single state
     * @param state State data from d3plot
     */
    void processState(const data::StateData& state);

    /**
     * @brief Get results after processing all states
     * @return Vector of motion statistics per part
     */
    std::vector<PartMotionStats> getResults();

    /**
     * @brief Get last error message
     */
    const std::string& getLastError() const { return last_error_; }

    /**
     * @brief Check if analyzer was successfully initialized
     */
    bool isInitialized() const { return initialized_; }

    /**
     * @brief Reset analyzer state (clear results)
     */
    void reset();

private:
    D3plotReader& reader_;
    std::string last_error_;
    bool initialized_ = false;

    // Configuration
    std::vector<int32_t> part_ids_;  // Parts to analyze (empty = all)

    // Geometry data (cached from reader)
    data::Mesh mesh_;                    // Mesh data
    std::vector<double> initial_coords_; // Initial node coordinates
    size_t num_nodes_ = 0;

    // Node to part mapping
    std::unordered_map<int32_t, std::unordered_set<size_t>> part_node_indices_;

    // Part information
    std::vector<int32_t> active_parts_;  // Parts actually being analyzed
    std::unordered_map<int32_t, size_t> part_id_to_result_index_;

    // Results storage
    std::vector<PartMotionStats> results_;

    // Previous state data for velocity/acceleration calculation
    std::vector<Vec3> prev_avg_displacements_;  // Per part
    std::vector<Vec3> prev_avg_velocities_;     // Per part
    double prev_time_ = 0.0;
    double prev_prev_time_ = 0.0;
    size_t state_count_ = 0;

    // Internal methods
    void buildNodeToPartMapping();
    Vec3 computeAverageDisplacement(int32_t part_id, const std::vector<double>& displacements);
    std::pair<double, int32_t> computeMaxDisplacement(int32_t part_id, const std::vector<double>& displacements);
};

} // namespace analysis
} // namespace kood3plot
