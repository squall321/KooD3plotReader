/**
 * @file TimeSelector.cpp
 * @brief Implementation of TimeSelector class
 * @author KooD3plot V3 Development Team
 * @date 2025-11-21
 * @version 3.0.0
 */

#include "kood3plot/query/TimeSelector.h"
#include <algorithm>
#include <cmath>
#include <sstream>
#include <limits>
#include <set>

namespace kood3plot {
namespace query {

// ============================================================
// Internal Implementation Details (File-local structures)
// ============================================================

/**
 * @brief Time range specification (internal use only)
 * Note: Defined in .cpp only, not visible outside this translation unit
 */
struct TimeRange {
    double start_time;
    double end_time;
    double time_step;  // -1.0 means all states in range

    TimeRange(double start, double end, double step = -1.0)
        : start_time(start), end_time(end), time_step(step) {}
};

/**
 * @brief State range specification (internal use only)
 * Note: Defined in .cpp only, not visible outside this translation unit
 */
struct StateRange {
    int start_index;
    int end_index;
    int step;

    StateRange(int start, int end, int s = 1)
        : start_index(start), end_index(end), step(s) {}
};

/**
 * @brief Event-based selection criterion (internal use only)
 * Note: Defined in .cpp only, not visible outside this translation unit
 */
struct EventCriterion {
    enum class Type {
        MAX_VALUE,
        MIN_VALUE,
        VALUE_EXCEEDS
    };

    Type type;
    QuantityType quantity;
    int32_t part_id;
    int32_t element_id;
    double threshold;  // Used for VALUE_EXCEEDS

    EventCriterion(Type t, QuantityType q, int32_t p = -1, int32_t e = -1, double th = 0.0)
        : type(t), quantity(q), part_id(p), element_id(e), threshold(th) {}
};

// ============================================================
// Time Value Helper Functions
// ============================================================

/**
 * @brief Get time value for specific state index
 *
 * Retrieves the simulation time for a given state index by calling
 * the reader's get_time_values() method.
 *
 * @param reader D3plot reader
 * @param state_index State index (0-based)
 * @return Time value for the state
 */
inline double getTimeForState(const kood3plot::D3plotReader& reader, size_t state_index) {
    // Note: get_time_values() is non-const, but logically const for our purposes
    auto& mutable_reader = const_cast<kood3plot::D3plotReader&>(reader);
    auto time_values = mutable_reader.get_time_values();

    if (state_index < time_values.size()) {
        return time_values[state_index];
    }
    return 0.0;  // Return 0 if index is out of range
}

// ============================================================
// PIMPL Implementation Struct
// ============================================================

/**
 * @brief Implementation details for TimeSelector
 */
struct TimeSelector::Impl {
    /// Explicit state indices to include
    std::set<int> explicit_states;

    /// Explicit time values to find
    std::set<double> explicit_times;

    /// Time ranges to include
    std::vector<TimeRange> time_ranges;

    /// State ranges to include
    std::vector<StateRange> state_ranges;

    /// Event-based criteria
    std::vector<EventCriterion> event_criteria;

    /// Flag for "select all states" mode
    bool select_all = false;

    /**
     * @brief Clear all selections
     */
    void clear() {
        explicit_states.clear();
        explicit_times.clear();
        time_ranges.clear();
        state_ranges.clear();
        event_criteria.clear();
        select_all = false;
    }

    /**
     * @brief Check if selector is empty
     */
    bool isEmpty() const {
        return explicit_states.empty() &&
               explicit_times.empty() &&
               time_ranges.empty() &&
               state_ranges.empty() &&
               event_criteria.empty() &&
               !select_all;
    }
};

// ============================================================
// Constructors and Destructor
// ============================================================

TimeSelector::TimeSelector()
    : pImpl(std::make_unique<Impl>())
{
}

TimeSelector::TimeSelector(const TimeSelector& other)
    : pImpl(std::make_unique<Impl>(*other.pImpl))
{
}

TimeSelector::TimeSelector(TimeSelector&& other) noexcept
    : pImpl(std::move(other.pImpl))
{
}

TimeSelector& TimeSelector::operator=(const TimeSelector& other) {
    if (this != &other) {
        pImpl = std::make_unique<Impl>(*other.pImpl);
    }
    return *this;
}

TimeSelector& TimeSelector::operator=(TimeSelector&& other) noexcept {
    if (this != &other) {
        pImpl = std::move(other.pImpl);
    }
    return *this;
}

TimeSelector::~TimeSelector() = default;

// ============================================================
// Selection by State Index
// ============================================================

TimeSelector& TimeSelector::addStep(int state_index) {
    pImpl->explicit_states.insert(state_index);
    return *this;
}

TimeSelector& TimeSelector::addSteps(const std::vector<int>& state_indices) {
    pImpl->explicit_states.insert(state_indices.begin(), state_indices.end());
    return *this;
}

// ============================================================
// Selection by Time Value
// ============================================================

TimeSelector& TimeSelector::addTime(double time) {
    pImpl->explicit_times.insert(time);
    return *this;
}

TimeSelector& TimeSelector::addTimes(const std::vector<double>& times) {
    pImpl->explicit_times.insert(times.begin(), times.end());
    return *this;
}

// ============================================================
// Selection by Time Range
// ============================================================

TimeSelector& TimeSelector::addTimeRange(double start_time,
                                        double end_time,
                                        double time_step) {
    pImpl->time_ranges.emplace_back(start_time, end_time, time_step);
    return *this;
}

// ============================================================
// Selection by State Range
// ============================================================

TimeSelector& TimeSelector::addStateRange(int start_index,
                                         int end_index,
                                         int step) {
    pImpl->state_ranges.emplace_back(start_index, end_index, step);
    return *this;
}

// ============================================================
// Special Selectors
// ============================================================

TimeSelector& TimeSelector::first() {
    pImpl->explicit_states.insert(0);
    return *this;
}

TimeSelector& TimeSelector::last() {
    pImpl->explicit_states.insert(-1);
    return *this;
}

TimeSelector& TimeSelector::all() {
    pImpl->select_all = true;
    return *this;
}

TimeSelector& TimeSelector::every(int n) {
    pImpl->state_ranges.emplace_back(0, -1, n);
    return *this;
}

TimeSelector& TimeSelector::firstN(int n) {
    if (n > 0) {
        pImpl->state_ranges.emplace_back(0, n - 1, 1);
    }
    return *this;
}

TimeSelector& TimeSelector::lastN(int n) {
    if (n > 0) {
        pImpl->state_ranges.emplace_back(-n, -1, 1);
    }
    return *this;
}

// ============================================================
// Event-Based Selection
// ============================================================

TimeSelector& TimeSelector::atMaxValue(QuantityType quantity,
                                      int32_t part_id,
                                      int32_t element_id) {
    pImpl->event_criteria.emplace_back(
        EventCriterion::Type::MAX_VALUE,
        quantity,
        part_id,
        element_id
    );
    return *this;
}

TimeSelector& TimeSelector::atMinValue(QuantityType quantity,
                                      int32_t part_id,
                                      int32_t element_id) {
    pImpl->event_criteria.emplace_back(
        EventCriterion::Type::MIN_VALUE,
        quantity,
        part_id,
        element_id
    );
    return *this;
}

TimeSelector& TimeSelector::whereValueExceeds(QuantityType quantity,
                                             double threshold,
                                             int32_t part_id) {
    pImpl->event_criteria.emplace_back(
        EventCriterion::Type::VALUE_EXCEEDS,
        quantity,
        part_id,
        -1,
        threshold
    );
    return *this;
}

// ============================================================
// Query Methods
// ============================================================

std::vector<int> TimeSelector::evaluate(const D3plotReader& reader) const {
    std::set<int> result_states;

    int total_states = reader.get_num_states();
    if (total_states == 0) {
        return {};
    }

    // Handle "select all" mode
    if (pImpl->select_all) {
        for (int i = 0; i < total_states; ++i) {
            result_states.insert(i);
        }
        return std::vector<int>(result_states.begin(), result_states.end());
    }

    // Handle explicit state indices
    for (int index : pImpl->explicit_states) {
        int resolved = resolveNegativeIndex(index, total_states);
        if (resolved >= 0 && resolved < total_states) {
            result_states.insert(resolved);
        }
    }

    // Handle explicit time values
    for (double time : pImpl->explicit_times) {
        int state = findClosestState(reader, time);
        if (state >= 0) {
            result_states.insert(state);
        }
    }

    // Handle time ranges
    for (const auto& range : pImpl->time_ranges) {
        auto states = getStatesInTimeRange(reader,
                                          range.start_time,
                                          range.end_time,
                                          range.time_step);
        result_states.insert(states.begin(), states.end());
    }

    // Handle state ranges
    for (const auto& range : pImpl->state_ranges) {
        auto states = getStatesInIndexRange(total_states,
                                           range.start_index,
                                           range.end_index,
                                           range.step);
        result_states.insert(states.begin(), states.end());
    }

    // Handle event-based criteria
    // NOTE: This requires reading actual state data, which is complex
    // For V3 Phase 1, we'll implement a simplified version
    // Full implementation will come in Phase 2
    for (const auto& criterion : pImpl->event_criteria) {
        // TODO: Implement event-based selection in Phase 2
        // For now, this is a placeholder that would require:
        // 1. Reading all states
        // 2. Computing the specified quantity
        // 3. Finding max/min/threshold crossings
        // This is intentionally left as a TODO marker
    }

    return std::vector<int>(result_states.begin(), result_states.end());
}

std::vector<double> TimeSelector::evaluateTimes(const D3plotReader& reader) const {
    auto state_indices = evaluate(reader);
    std::vector<double> times;
    times.reserve(state_indices.size());

    for (int state : state_indices) {
        double time = getTimeForState(reader,state);
        times.push_back(time);
    }

    return times;
}

size_t TimeSelector::count(const D3plotReader& reader) const {
    return evaluate(reader).size();
}

bool TimeSelector::hasMatches(const D3plotReader& reader) const {
    return count(reader) > 0;
}

// ============================================================
// Query State
// ============================================================

bool TimeSelector::isEmpty() const {
    return pImpl->isEmpty();
}

bool TimeSelector::isAll() const {
    return pImpl->select_all;
}

std::string TimeSelector::getDescription() const {
    if (pImpl->isEmpty()) {
        return "No states selected";
    }

    if (pImpl->select_all) {
        return "All states";
    }

    std::ostringstream oss;
    bool has_content = false;

    // Explicit states
    if (!pImpl->explicit_states.empty()) {
        oss << "States: [";
        bool first = true;
        for (int s : pImpl->explicit_states) {
            if (!first) oss << ", ";
            oss << s;
            first = false;
        }
        oss << "]";
        has_content = true;
    }

    // Explicit times
    if (!pImpl->explicit_times.empty()) {
        if (has_content) oss << ", ";
        oss << "Times: [";
        bool first = true;
        for (double t : pImpl->explicit_times) {
            if (!first) oss << ", ";
            oss << t;
            first = false;
        }
        oss << "]";
        has_content = true;
    }

    // Time ranges
    if (!pImpl->time_ranges.empty()) {
        if (has_content) oss << ", ";
        oss << "Time ranges: [";
        bool first = true;
        for (const auto& r : pImpl->time_ranges) {
            if (!first) oss << ", ";
            oss << r.start_time << "-" << r.end_time;
            if (r.time_step > 0) {
                oss << " step " << r.time_step;
            }
            first = false;
        }
        oss << "]";
        has_content = true;
    }

    // State ranges
    if (!pImpl->state_ranges.empty()) {
        if (has_content) oss << ", ";
        oss << "State ranges: [";
        bool first = true;
        for (const auto& r : pImpl->state_ranges) {
            if (!first) oss << ", ";
            oss << r.start_index << "-" << r.end_index;
            if (r.step > 1) {
                oss << " step " << r.step;
            }
            first = false;
        }
        oss << "]";
        has_content = true;
    }

    // Event criteria
    if (!pImpl->event_criteria.empty()) {
        if (has_content) oss << ", ";
        oss << "Events: " << pImpl->event_criteria.size() << " criteria";
    }

    return oss.str();
}

// ============================================================
// Removal Methods
// ============================================================

TimeSelector& TimeSelector::clear() {
    pImpl->clear();
    return *this;
}

// ============================================================
// Static Factory Methods
// ============================================================

TimeSelector TimeSelector::firstState() {
    TimeSelector selector;
    selector.first();
    return selector;
}

TimeSelector TimeSelector::lastState() {
    TimeSelector selector;
    selector.last();
    return selector;
}

TimeSelector TimeSelector::allStates() {
    TimeSelector selector;
    selector.all();
    return selector;
}

TimeSelector TimeSelector::endpoints() {
    TimeSelector selector;
    selector.first().last();
    return selector;
}

TimeSelector TimeSelector::everyNth(int n) {
    TimeSelector selector;
    selector.every(n);
    return selector;
}

// ============================================================
// Private Helper Methods
// ============================================================

int TimeSelector::findClosestState(const D3plotReader& reader, double time) const {
    int total_states = reader.get_num_states();
    if (total_states == 0) {
        return -1;
    }

    int closest_state = 0;
    double min_diff = std::abs(getTimeForState(reader,0) - time);

    for (int i = 1; i < total_states; ++i) {
        double diff = std::abs(getTimeForState(reader,i) - time);
        if (diff < min_diff) {
            min_diff = diff;
            closest_state = i;
        }
    }

    return closest_state;
}

int TimeSelector::resolveNegativeIndex(int index, int total_states) const {
    if (index >= 0) {
        return index;
    }

    // Negative indices count from end: -1 = last, -2 = second-to-last, etc.
    return total_states + index;
}

std::vector<int> TimeSelector::getStatesInTimeRange(
    const D3plotReader& reader,
    double start_time,
    double end_time,
    double time_step) const
{
    std::vector<int> states;
    int total_states = reader.get_num_states();

    if (time_step <= 0.0) {
        // Include all states in time range
        for (int i = 0; i < total_states; ++i) {
            double t = getTimeForState(reader,i);
            if (t >= start_time && t <= end_time) {
                states.push_back(i);
            }
        }
    } else {
        // Include states at regular time intervals
        double current_time = start_time;
        while (current_time <= end_time) {
            int state = findClosestState(reader, current_time);
            if (state >= 0) {
                // Check if we haven't already added this state
                // (can happen if time_step is very small)
                if (states.empty() || states.back() != state) {
                    states.push_back(state);
                }
            }
            current_time += time_step;
        }
    }

    return states;
}

std::vector<int> TimeSelector::getStatesInIndexRange(
    int total_states,
    int start_index,
    int end_index,
    int step) const
{
    std::vector<int> states;

    // Resolve negative indices
    int start = resolveNegativeIndex(start_index, total_states);
    int end = resolveNegativeIndex(end_index, total_states);

    // Clamp to valid range
    start = std::max(0, std::min(start, total_states - 1));
    end = std::max(0, std::min(end, total_states - 1));

    // Generate range
    if (step > 0) {
        for (int i = start; i <= end; i += step) {
            states.push_back(i);
        }
    } else if (step < 0) {
        // Reverse iteration
        for (int i = end; i >= start; i += step) {
            states.push_back(i);
        }
    }

    return states;
}

} // namespace query
} // namespace kood3plot
