#pragma once

/**
 * @file TimeSelector.h
 * @brief Time/state selection interface for the KooD3plot Query System
 * @author KooD3plot V3 Development Team
 * @date 2025-11-21
 * @version 3.0.0
 *
 * TimeSelector provides flexible methods to select timesteps from d3plot results:
 * - By state index (0-based)
 * - By simulation time value
 * - By time range (with optional stepping)
 * - By state range (with optional stepping)
 * - Special selectors (first, last, all, every nth)
 * - Event-based selection (at maximum/minimum values)
 *
 * Example usage:
 * @code
 * TimeSelector selector;
 * selector.addStep(0)           // First state
 *         .addStep(-1)          // Last state
 *         .addTimeRange(0.0, 10.0, 1.0);  // Times 0-10ms, every 1ms
 * auto states = selector.evaluate(reader);
 * @endcode
 */

#include "QueryTypes.h"
#include "../D3plotReader.hpp"
#include <vector>
#include <optional>

namespace kood3plot {
namespace query {

/**
 * @class TimeSelector
 * @brief Selects timesteps/states from d3plot results
 *
 * This class manages selection of timesteps (states) that should be included
 * in query results. It supports:
 * - Individual state selection by index
 * - Time-based selection by simulation time
 * - Range-based selection (time or state ranges)
 * - Special patterns (first, last, all, every nth)
 * - Event-based selection (at peak values)
 */
class TimeSelector {
public:
    // ============================================================
    // Constructors
    // ============================================================

    /**
     * @brief Default constructor
     */
    TimeSelector();

    /**
     * @brief Copy constructor
     */
    TimeSelector(const TimeSelector& other);

    /**
     * @brief Move constructor
     */
    TimeSelector(TimeSelector&& other) noexcept;

    /**
     * @brief Assignment operator
     */
    TimeSelector& operator=(const TimeSelector& other);

    /**
     * @brief Move assignment operator
     */
    TimeSelector& operator=(TimeSelector&& other) noexcept;

    /**
     * @brief Destructor
     */
    ~TimeSelector();

    // ============================================================
    // Selection by State Index
    // ============================================================

    /**
     * @brief Add single state by index
     * @param state_index State index (0-based, -1 for last state)
     * @return Reference to this selector for method chaining
     *
     * State indices are 0-based. Use -1 to select the last state,
     * -2 for second-to-last, etc.
     *
     * Example:
     * @code
     * selector.addStep(0);    // First state
     * selector.addStep(-1);   // Last state
     * selector.addStep(10);   // 11th state (0-based)
     * @endcode
     */
    TimeSelector& addStep(int state_index);

    /**
     * @brief Add multiple states by indices
     * @param state_indices Vector of state indices
     * @return Reference to this selector for method chaining
     *
     * Example:
     * @code
     * selector.addStep({0, 10, 20, -1});  // First, 11th, 21st, and last
     * @endcode
     */
    TimeSelector& addSteps(const std::vector<int>& state_indices);

    // ============================================================
    // Selection by Time Value
    // ============================================================

    /**
     * @brief Add state closest to specified time
     * @param time Simulation time value
     * @return Reference to this selector for method chaining
     *
     * Finds the state with timestamp closest to the specified time.
     *
     * Example:
     * @code
     * selector.addTime(0.0);    // State at time=0
     * selector.addTime(5.5);    // State closest to 5.5ms
     * @endcode
     */
    TimeSelector& addTime(double time);

    /**
     * @brief Add states closest to specified times
     * @param times Vector of simulation time values
     * @return Reference to this selector for method chaining
     *
     * Example:
     * @code
     * selector.addTime({0.0, 1.0, 2.0, 5.0});
     * @endcode
     */
    TimeSelector& addTimes(const std::vector<double>& times);

    // ============================================================
    // Selection by Time Range
    // ============================================================

    /**
     * @brief Add states in time range
     * @param start_time Start time (inclusive)
     * @param end_time End time (inclusive)
     * @param time_step Time step (optional, -1.0 for all states)
     * @return Reference to this selector for method chaining
     *
     * Selects all states within the time range [start_time, end_time].
     * If time_step is specified, selects states at regular intervals.
     *
     * Example:
     * @code
     * selector.addTimeRange(0.0, 10.0);         // All states between 0-10ms
     * selector.addTimeRange(0.0, 10.0, 1.0);    // Every 1ms between 0-10ms
     * selector.addTimeRange(5.0, 15.0, 0.5);    // Every 0.5ms between 5-15ms
     * @endcode
     */
    TimeSelector& addTimeRange(double start_time,
                               double end_time,
                               double time_step = -1.0);

    // ============================================================
    // Selection by State Range
    // ============================================================

    /**
     * @brief Add states in index range
     * @param start_index Start state index (inclusive, 0-based)
     * @param end_index End state index (inclusive, -1 for last)
     * @param step Step size (default: 1, every state)
     * @return Reference to this selector for method chaining
     *
     * Selects states by index range. Negative indices count from end.
     *
     * Example:
     * @code
     * selector.addStateRange(0, 10);        // States 0-10
     * selector.addStateRange(0, -1);        // All states
     * selector.addStateRange(0, -1, 5);     // Every 5th state
     * selector.addStateRange(10, 20, 2);    // States 10, 12, 14, 16, 18, 20
     * @endcode
     */
    TimeSelector& addStateRange(int start_index,
                                int end_index,
                                int step = 1);

    // ============================================================
    // Special Selectors
    // ============================================================

    /**
     * @brief Select first state only
     * @return Reference to this selector
     *
     * Example:
     * @code
     * selector.first();  // Equivalent to addStep(0)
     * @endcode
     */
    TimeSelector& first();

    /**
     * @brief Select last state only
     * @return Reference to this selector
     *
     * Example:
     * @code
     * selector.last();   // Equivalent to addStep(-1)
     * @endcode
     */
    TimeSelector& last();

    /**
     * @brief Select all states
     * @return Reference to this selector
     *
     * Example:
     * @code
     * selector.all();    // Equivalent to addStateRange(0, -1)
     * @endcode
     */
    TimeSelector& all();

    /**
     * @brief Select every nth state
     * @param n Step interval (e.g., 5 = every 5th state)
     * @return Reference to this selector
     *
     * Example:
     * @code
     * selector.every(10);  // States 0, 10, 20, 30, ...
     * selector.every(5);   // States 0, 5, 10, 15, 20, ...
     * @endcode
     */
    TimeSelector& every(int n);

    /**
     * @brief Select first N states
     * @param n Number of states to select from beginning
     * @return Reference to this selector
     *
     * Example:
     * @code
     * selector.firstN(10);  // First 10 states (0-9)
     * @endcode
     */
    TimeSelector& firstN(int n);

    /**
     * @brief Select last N states
     * @param n Number of states to select from end
     * @return Reference to this selector
     *
     * Example:
     * @code
     * selector.lastN(10);   // Last 10 states
     * @endcode
     */
    TimeSelector& lastN(int n);

    // ============================================================
    // Event-Based Selection
    // ============================================================

    /**
     * @brief Select state at maximum value of a quantity
     * @param quantity Quantity type to monitor
     * @param part_id Part ID to monitor (-1 for global maximum)
     * @param element_id Element ID to monitor (-1 for part maximum)
     * @return Reference to this selector
     *
     * Finds the timestep where the specified quantity reaches its
     * maximum value. Useful for crash analysis (peak stress, etc.)
     *
     * Example:
     * @code
     * // State with maximum von mises stress globally
     * selector.atMaxValue(QuantityType::STRESS_VON_MISES);
     *
     * // State with maximum displacement in part 100
     * selector.atMaxValue(QuantityType::DISPLACEMENT_MAGNITUDE, 100);
     *
     * // State with maximum effective strain in element 5000 of part 100
     * selector.atMaxValue(QuantityType::STRAIN_EFFECTIVE, 100, 5000);
     * @endcode
     */
    TimeSelector& atMaxValue(QuantityType quantity,
                            int32_t part_id = -1,
                            int32_t element_id = -1);

    /**
     * @brief Select state at minimum value of a quantity
     * @param quantity Quantity type to monitor
     * @param part_id Part ID to monitor (-1 for global minimum)
     * @param element_id Element ID to monitor (-1 for part minimum)
     * @return Reference to this selector
     *
     * Example:
     * @code
     * // State with minimum pressure globally
     * selector.atMinValue(QuantityType::STRESS_PRESSURE);
     * @endcode
     */
    TimeSelector& atMinValue(QuantityType quantity,
                            int32_t part_id = -1,
                            int32_t element_id = -1);

    /**
     * @brief Select states where value exceeds threshold
     * @param quantity Quantity type to monitor
     * @param threshold Threshold value
     * @param part_id Part ID to monitor (-1 for any part)
     * @return Reference to this selector
     *
     * Selects all states where the quantity value exceeds the threshold.
     *
     * Example:
     * @code
     * // States where von mises > 500 MPa anywhere
     * selector.whereValueExceeds(QuantityType::STRESS_VON_MISES, 500.0);
     *
     * // States where effective strain > 0.3 in part 100
     * selector.whereValueExceeds(QuantityType::STRAIN_EFFECTIVE, 0.3, 100);
     * @endcode
     */
    TimeSelector& whereValueExceeds(QuantityType quantity,
                                   double threshold,
                                   int32_t part_id = -1);

    // ============================================================
    // Query Methods
    // ============================================================

    /**
     * @brief Evaluate selector against d3plot reader
     * @param reader D3plot reader instance
     * @return Vector of selected state indices (sorted, unique)
     *
     * This method processes all selection criteria and returns
     * the final list of state indices to include in results.
     *
     * Example:
     * @code
     * D3plotReader reader("crash.d3plot");
     * TimeSelector selector;
     * selector.addStep(0).addStep(-1).addTimeRange(5.0, 10.0, 1.0);
     * auto states = selector.evaluate(reader);
     * // states = [0, 5, 6, 7, 8, 9, 10, 99] (if last state is 99)
     * @endcode
     */
    std::vector<int> evaluate(const D3plotReader& reader) const;

    /**
     * @brief Get simulation times for selected states
     * @param reader D3plot reader instance
     * @return Vector of simulation time values
     *
     * Example:
     * @code
     * auto times = selector.evaluateTimes(reader);
     * // times = [0.0, 5.0, 6.0, 7.0, ..., 20.5]
     * @endcode
     */
    std::vector<double> evaluateTimes(const D3plotReader& reader) const;

    /**
     * @brief Count how many states match the selection
     * @param reader D3plot reader instance
     * @return Number of matching states
     */
    size_t count(const D3plotReader& reader) const;

    /**
     * @brief Check if any states match the selection
     * @param reader D3plot reader instance
     * @return true if at least one state matches
     */
    bool hasMatches(const D3plotReader& reader) const;

    // ============================================================
    // Query State
    // ============================================================

    /**
     * @brief Check if selector is empty (no selection criteria)
     * @return true if no criteria specified
     */
    bool isEmpty() const;

    /**
     * @brief Check if selector will select all states
     * @return true if configured to select all states
     */
    bool isAll() const;

    /**
     * @brief Get description of selection criteria (for debugging)
     * @return String describing the selection
     *
     * Example output: "States: [0, -1], Time ranges: [5.0-10.0 step 1.0]"
     */
    std::string getDescription() const;

    // ============================================================
    // Removal Methods
    // ============================================================

    /**
     * @brief Clear all selection criteria
     * @return Reference to this selector
     */
    TimeSelector& clear();

    // ============================================================
    // Static Factory Methods
    // ============================================================

    /**
     * @brief Create selector for first state only
     * @return TimeSelector configured for first state
     *
     * Example:
     * @code
     * auto selector = TimeSelector::firstState();
     * @endcode
     */
    static TimeSelector firstState();

    /**
     * @brief Create selector for last state only
     * @return TimeSelector configured for last state
     *
     * Example:
     * @code
     * auto selector = TimeSelector::lastState();
     * @endcode
     */
    static TimeSelector lastState();

    /**
     * @brief Create selector for all states
     * @return TimeSelector configured for all states
     *
     * Example:
     * @code
     * auto selector = TimeSelector::allStates();
     * @endcode
     */
    static TimeSelector allStates();

    /**
     * @brief Create selector for first and last states
     * @return TimeSelector configured for first and last
     *
     * Example:
     * @code
     * auto selector = TimeSelector::endpoints();
     * @endcode
     */
    static TimeSelector endpoints();

    /**
     * @brief Create selector for every nth state
     * @param n Step interval
     * @return TimeSelector configured for every nth state
     *
     * Example:
     * @code
     * auto selector = TimeSelector::everyNth(10);  // Every 10th state
     * @endcode
     */
    static TimeSelector everyNth(int n);

private:
    // ============================================================
    // Private Implementation
    // ============================================================

    /**
     * @brief Implementation struct (PIMPL pattern)
     */
    struct Impl;
    std::unique_ptr<Impl> pImpl;

    // ============================================================
    // Private Helper Methods
    // ============================================================

    /**
     * @brief Find state index closest to specified time
     */
    int findClosestState(const D3plotReader& reader, double time) const;

    /**
     * @brief Convert negative index to positive (e.g., -1 -> last)
     */
    int resolveNegativeIndex(int index, int total_states) const;

    /**
     * @brief Get states in time range with stepping
     */
    std::vector<int> getStatesInTimeRange(const D3plotReader& reader,
                                         double start_time,
                                         double end_time,
                                         double time_step) const;

    /**
     * @brief Get states in index range with stepping
     */
    std::vector<int> getStatesInIndexRange(int total_states,
                                          int start_index,
                                          int end_index,
                                          int step) const;
};

} // namespace query
} // namespace kood3plot
