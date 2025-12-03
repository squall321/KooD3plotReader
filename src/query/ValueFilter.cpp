/**
 * @file ValueFilter.cpp
 * @brief Implementation of ValueFilter class
 * @author KooD3plot V3 Development Team
 * @date 2025-11-21
 * @version 3.0.0
 */

#include "kood3plot/query/ValueFilter.h"
#include <algorithm>
#include <cmath>
#include <numeric>
#include <sstream>
#include <limits>
#include <set>

namespace kood3plot {
namespace query {

// ============================================================
// Internal Implementation Details (Anonymous Namespace)
// ============================================================

namespace {

/**
 * @brief Filter condition types (internal use only)
 */
enum class ConditionType {
    RANGE,              // value in [min, max]
    OUTSIDE_RANGE,      // value outside [min, max]
    GREATER_THAN,       // value > threshold
    GREATER_EQUAL,      // value >= threshold
    LESS_THAN,          // value < threshold
    LESS_EQUAL,         // value <= threshold
    EQUAL,              // |value - target| < tolerance
    NOT_EQUAL,          // |value - target| >= tolerance
    TOP_PERCENTILE,     // value in top N%
    BOTTOM_PERCENTILE,  // value in bottom N%
    PERCENTILE_RANGE,   // value between percentiles
    REMOVE_OUTLIERS,    // IQR-based outlier removal
    WITHIN_STD,         // within N std dev
    OUTSIDE_STD,        // outside N std dev
    TOP_N,              // top N values
    BOTTOM_N,           // bottom N values
    CUSTOM_PREDICATE,   // custom function
    ACCEPT_ALL,         // always true
    REJECT_ALL,         // always false
    AND,                // logical AND
    OR,                 // logical OR
    NOT                 // logical NOT
};

/**
 * @brief Single filter condition (internal use only)
 */
struct FilterCondition {
    ConditionType type;

    // Parameters (usage depends on type)
    double param1 = 0.0;  // min, threshold, percentile, n_std, tolerance
    double param2 = 0.0;  // max, upper_percentile

    // Custom predicate
    std::function<bool(double)> predicate;

    // Child filters (for AND/OR/NOT) - using shared_ptr to allow copying
    std::shared_ptr<ValueFilter> child1;
    std::shared_ptr<ValueFilter> child2;

    FilterCondition(ConditionType t, double p1 = 0.0, double p2 = 0.0)
        : type(t), param1(p1), param2(p2) {}
};

} // anonymous namespace

// ============================================================
// PIMPL Implementation Struct
// ============================================================

/**
 * @brief Implementation details for ValueFilter
 */
struct ValueFilter::Impl {
    /// List of filter conditions (applied with AND logic by default)
    std::vector<FilterCondition> conditions;

    /**
     * @brief Clear all conditions
     */
    void clear() {
        conditions.clear();
    }

    /**
     * @brief Check if empty
     */
    bool isEmpty() const {
        return conditions.empty();
    }

    /**
     * @brief Check if requires statistics
     */
    bool requiresStatistics() const {
        for (const auto& cond : conditions) {
            if (cond.type == ConditionType::TOP_PERCENTILE ||
                cond.type == ConditionType::BOTTOM_PERCENTILE ||
                cond.type == ConditionType::PERCENTILE_RANGE ||
                cond.type == ConditionType::REMOVE_OUTLIERS ||
                cond.type == ConditionType::WITHIN_STD ||
                cond.type == ConditionType::OUTSIDE_STD ||
                cond.type == ConditionType::TOP_N ||
                cond.type == ConditionType::BOTTOM_N) {
                return true;
            }
        }
        return false;
    }
};

// ============================================================
// Constructors and Destructor
// ============================================================

ValueFilter::ValueFilter()
    : pImpl(std::make_unique<Impl>())
{
}

ValueFilter::ValueFilter(const ValueFilter& other)
    : pImpl(std::make_unique<Impl>(*other.pImpl))
{
}

ValueFilter::ValueFilter(ValueFilter&& other) noexcept
    : pImpl(std::move(other.pImpl))
{
}

ValueFilter& ValueFilter::operator=(const ValueFilter& other) {
    if (this != &other) {
        pImpl = std::make_unique<Impl>(*other.pImpl);
    }
    return *this;
}

ValueFilter& ValueFilter::operator=(ValueFilter&& other) noexcept {
    if (this != &other) {
        pImpl = std::move(other.pImpl);
    }
    return *this;
}

ValueFilter::~ValueFilter() = default;

// ============================================================
// Range Filtering
// ============================================================

ValueFilter& ValueFilter::inRange(double min, double max) {
    FilterCondition cond(ConditionType::RANGE, min, max);
    pImpl->conditions.push_back(cond);
    return *this;
}

ValueFilter& ValueFilter::outsideRange(double min, double max) {
    FilterCondition cond(ConditionType::OUTSIDE_RANGE, min, max);
    pImpl->conditions.push_back(cond);
    return *this;
}

// ============================================================
// Comparison Filtering
// ============================================================

ValueFilter& ValueFilter::greaterThan(double threshold) {
    FilterCondition cond(ConditionType::GREATER_THAN, threshold);
    pImpl->conditions.push_back(cond);
    return *this;
}

ValueFilter& ValueFilter::greaterThanOrEqual(double threshold) {
    FilterCondition cond(ConditionType::GREATER_EQUAL, threshold);
    pImpl->conditions.push_back(cond);
    return *this;
}

ValueFilter& ValueFilter::lessThan(double threshold) {
    FilterCondition cond(ConditionType::LESS_THAN, threshold);
    pImpl->conditions.push_back(cond);
    return *this;
}

ValueFilter& ValueFilter::lessThanOrEqual(double threshold) {
    FilterCondition cond(ConditionType::LESS_EQUAL, threshold);
    pImpl->conditions.push_back(cond);
    return *this;
}

ValueFilter& ValueFilter::equalTo(double value, double tolerance) {
    FilterCondition cond(ConditionType::EQUAL, value, tolerance);
    pImpl->conditions.push_back(cond);
    return *this;
}

ValueFilter& ValueFilter::notEqualTo(double value, double tolerance) {
    FilterCondition cond(ConditionType::NOT_EQUAL, value, tolerance);
    pImpl->conditions.push_back(cond);
    return *this;
}

// ============================================================
// Percentile Filtering
// ============================================================

ValueFilter& ValueFilter::inTopPercentile(double percentile) {
    FilterCondition cond(ConditionType::TOP_PERCENTILE, percentile);
    pImpl->conditions.push_back(cond);
    return *this;
}

ValueFilter& ValueFilter::inBottomPercentile(double percentile) {
    FilterCondition cond(ConditionType::BOTTOM_PERCENTILE, percentile);
    pImpl->conditions.push_back(cond);
    return *this;
}

ValueFilter& ValueFilter::betweenPercentiles(double lower_percentile, double upper_percentile) {
    FilterCondition cond(ConditionType::PERCENTILE_RANGE, lower_percentile, upper_percentile);
    pImpl->conditions.push_back(cond);
    return *this;
}

// ============================================================
// Statistical Filtering
// ============================================================

ValueFilter& ValueFilter::removeOutliers(double iqr_multiplier) {
    FilterCondition cond(ConditionType::REMOVE_OUTLIERS, iqr_multiplier);
    pImpl->conditions.push_back(cond);
    return *this;
}

ValueFilter& ValueFilter::withinStdDev(double n_std) {
    FilterCondition cond(ConditionType::WITHIN_STD, n_std);
    pImpl->conditions.push_back(cond);
    return *this;
}

ValueFilter& ValueFilter::outsideStdDev(double n_std) {
    FilterCondition cond(ConditionType::OUTSIDE_STD, n_std);
    pImpl->conditions.push_back(cond);
    return *this;
}

// ============================================================
// Logical Operations
// ============================================================

ValueFilter ValueFilter::operator&&(const ValueFilter& other) const {
    ValueFilter result;
    FilterCondition cond(ConditionType::AND);
    cond.child1 = std::make_shared<ValueFilter>(*this);
    cond.child2 = std::make_shared<ValueFilter>(other);
    result.pImpl->conditions.push_back(std::move(cond));
    return result;
}

ValueFilter ValueFilter::operator||(const ValueFilter& other) const {
    ValueFilter result;
    FilterCondition cond(ConditionType::OR);
    cond.child1 = std::make_shared<ValueFilter>(*this);
    cond.child2 = std::make_shared<ValueFilter>(other);
    result.pImpl->conditions.push_back(std::move(cond));
    return result;
}

ValueFilter ValueFilter::operator!() const {
    ValueFilter result;
    FilterCondition cond(ConditionType::NOT);
    cond.child1 = std::make_shared<ValueFilter>(*this);
    result.pImpl->conditions.push_back(std::move(cond));
    return result;
}

ValueFilter& ValueFilter::andFilter(const ValueFilter& other) {
    // Append other's conditions to this filter (AND logic)
    pImpl->conditions.insert(
        pImpl->conditions.end(),
        other.pImpl->conditions.begin(),
        other.pImpl->conditions.end()
    );
    return *this;
}

ValueFilter& ValueFilter::orFilter(const ValueFilter& other) {
    // Create OR condition
    FilterCondition cond(ConditionType::OR);
    cond.child1 = std::make_shared<ValueFilter>(*this);
    cond.child2 = std::make_shared<ValueFilter>(other);
    pImpl->clear();
    pImpl->conditions.push_back(std::move(cond));
    return *this;
}

ValueFilter& ValueFilter::negate() {
    // Wrap current filter in NOT
    FilterCondition cond(ConditionType::NOT);
    cond.child1 = std::make_shared<ValueFilter>(*this);
    pImpl->clear();
    pImpl->conditions.push_back(std::move(cond));
    return *this;
}

// ============================================================
// Custom Filtering
// ============================================================

ValueFilter& ValueFilter::addPredicate(std::function<bool(double)> predicate) {
    FilterCondition cond(ConditionType::CUSTOM_PREDICATE);
    cond.predicate = predicate;
    pImpl->conditions.push_back(cond);
    return *this;
}

// ============================================================
// Evaluation Methods
// ============================================================

bool ValueFilter::test(double value) const {
    // Empty filter accepts all values
    if (pImpl->isEmpty()) {
        return true;
    }

    // All conditions must pass (AND logic)
    for (const auto& cond : pImpl->conditions) {
        bool passes = false;

        switch (cond.type) {
            case ConditionType::RANGE:
                passes = (value >= cond.param1 && value <= cond.param2);
                break;

            case ConditionType::OUTSIDE_RANGE:
                passes = (value < cond.param1 || value > cond.param2);
                break;

            case ConditionType::GREATER_THAN:
                passes = (value > cond.param1);
                break;

            case ConditionType::GREATER_EQUAL:
                passes = (value >= cond.param1);
                break;

            case ConditionType::LESS_THAN:
                passes = (value < cond.param1);
                break;

            case ConditionType::LESS_EQUAL:
                passes = (value <= cond.param1);
                break;

            case ConditionType::EQUAL:
                passes = (std::abs(value - cond.param1) < cond.param2);
                break;

            case ConditionType::NOT_EQUAL:
                passes = (std::abs(value - cond.param1) >= cond.param2);
                break;

            case ConditionType::CUSTOM_PREDICATE:
                passes = cond.predicate(value);
                break;

            case ConditionType::ACCEPT_ALL:
                passes = true;
                break;

            case ConditionType::REJECT_ALL:
                passes = false;
                break;

            case ConditionType::AND:
                passes = cond.child1->test(value) && cond.child2->test(value);
                break;

            case ConditionType::OR:
                passes = cond.child1->test(value) || cond.child2->test(value);
                break;

            case ConditionType::NOT:
                passes = !cond.child1->test(value);
                break;

            // Statistical conditions require full dataset
            // For single value test, we can't evaluate these
            case ConditionType::TOP_PERCENTILE:
            case ConditionType::BOTTOM_PERCENTILE:
            case ConditionType::PERCENTILE_RANGE:
            case ConditionType::REMOVE_OUTLIERS:
            case ConditionType::WITHIN_STD:
            case ConditionType::OUTSIDE_STD:
            case ConditionType::TOP_N:
            case ConditionType::BOTTOM_N:
                // These require context from full dataset
                // Return true for single value test (can't evaluate)
                passes = true;
                break;
        }

        if (!passes) {
            return false;
        }
    }

    return true;
}

std::vector<double> ValueFilter::apply(const std::vector<double>& values) const {
    auto indices = getPassingIndices(values);
    std::vector<double> result;
    result.reserve(indices.size());

    for (size_t idx : indices) {
        result.push_back(values[idx]);
    }

    return result;
}

std::vector<size_t> ValueFilter::getPassingIndices(const std::vector<double>& values) const {
    std::vector<size_t> indices;

    if (values.empty()) {
        return indices;
    }

    // Empty filter passes all indices
    if (pImpl->isEmpty()) {
        indices.resize(values.size());
        std::iota(indices.begin(), indices.end(), 0);
        return indices;
    }

    // Pre-compute statistics if needed
    std::vector<double> sorted_values;
    double mean = 0.0;
    double std_dev = 0.0;
    double q1 = 0.0, q3 = 0.0, iqr = 0.0;

    if (requiresStatistics()) {
        sorted_values = values;
        std::sort(sorted_values.begin(), sorted_values.end());

        auto [m, s] = computeMeanStdDev(values);
        mean = m;
        std_dev = s;

        iqr = computeIQR(sorted_values);
        q1 = computePercentile(sorted_values, 25.0);
        q3 = computePercentile(sorted_values, 75.0);
    }

    // Test each value
    for (size_t i = 0; i < values.size(); ++i) {
        double value = values[i];
        bool passes = true;

        // Check all conditions
        for (const auto& cond : pImpl->conditions) {
            bool cond_passes = false;

            switch (cond.type) {
                case ConditionType::RANGE:
                    cond_passes = (value >= cond.param1 && value <= cond.param2);
                    break;

                case ConditionType::OUTSIDE_RANGE:
                    cond_passes = (value < cond.param1 || value > cond.param2);
                    break;

                case ConditionType::GREATER_THAN:
                    cond_passes = (value > cond.param1);
                    break;

                case ConditionType::GREATER_EQUAL:
                    cond_passes = (value >= cond.param1);
                    break;

                case ConditionType::LESS_THAN:
                    cond_passes = (value < cond.param1);
                    break;

                case ConditionType::LESS_EQUAL:
                    cond_passes = (value <= cond.param1);
                    break;

                case ConditionType::EQUAL:
                    cond_passes = (std::abs(value - cond.param1) < cond.param2);
                    break;

                case ConditionType::NOT_EQUAL:
                    cond_passes = (std::abs(value - cond.param1) >= cond.param2);
                    break;

                case ConditionType::TOP_PERCENTILE: {
                    double threshold = computePercentile(sorted_values, 100.0 - cond.param1);
                    cond_passes = (value >= threshold);
                    break;
                }

                case ConditionType::BOTTOM_PERCENTILE: {
                    double threshold = computePercentile(sorted_values, cond.param1);
                    cond_passes = (value <= threshold);
                    break;
                }

                case ConditionType::PERCENTILE_RANGE: {
                    double lower = computePercentile(sorted_values, cond.param1);
                    double upper = computePercentile(sorted_values, cond.param2);
                    cond_passes = (value >= lower && value <= upper);
                    break;
                }

                case ConditionType::REMOVE_OUTLIERS: {
                    double lower_bound = q1 - cond.param1 * iqr;
                    double upper_bound = q3 + cond.param1 * iqr;
                    cond_passes = (value >= lower_bound && value <= upper_bound);
                    break;
                }

                case ConditionType::WITHIN_STD: {
                    double lower = mean - cond.param1 * std_dev;
                    double upper = mean + cond.param1 * std_dev;
                    cond_passes = (value >= lower && value <= upper);
                    break;
                }

                case ConditionType::OUTSIDE_STD: {
                    double lower = mean - cond.param1 * std_dev;
                    double upper = mean + cond.param1 * std_dev;
                    cond_passes = (value < lower || value > upper);
                    break;
                }

                case ConditionType::TOP_N: {
                    // Get threshold for top N values
                    size_t n = static_cast<size_t>(cond.param1);
                    if (n >= sorted_values.size()) {
                        cond_passes = true;  // All values pass if N >= total count
                    } else {
                        double threshold = sorted_values[sorted_values.size() - n];
                        cond_passes = (value >= threshold);
                    }
                    break;
                }

                case ConditionType::BOTTOM_N: {
                    // Get threshold for bottom N values
                    size_t n = static_cast<size_t>(cond.param1);
                    if (n >= sorted_values.size()) {
                        cond_passes = true;  // All values pass if N >= total count
                    } else {
                        double threshold = sorted_values[n - 1];
                        cond_passes = (value <= threshold);
                    }
                    break;
                }

                case ConditionType::CUSTOM_PREDICATE:
                    cond_passes = cond.predicate(value);
                    break;

                case ConditionType::ACCEPT_ALL:
                    cond_passes = true;
                    break;

                case ConditionType::REJECT_ALL:
                    cond_passes = false;
                    break;

                case ConditionType::AND: {
                    // For AND, we need to check both children
                    // If child requires statistics, use the full dataset context
                    bool pass1, pass2;
                    if (cond.child1->requiresStatistics()) {
                        // Get the indices from child1 using full dataset
                        auto indices = cond.child1->getPassingIndices(values);
                        std::set<size_t> idx_set(indices.begin(), indices.end());
                        pass1 = idx_set.count(i) > 0;
                    } else {
                        pass1 = cond.child1->test(value);
                    }
                    if (cond.child2->requiresStatistics()) {
                        auto indices = cond.child2->getPassingIndices(values);
                        std::set<size_t> idx_set(indices.begin(), indices.end());
                        pass2 = idx_set.count(i) > 0;
                    } else {
                        pass2 = cond.child2->test(value);
                    }
                    cond_passes = pass1 && pass2;
                    break;
                }

                case ConditionType::OR: {
                    bool pass1, pass2;
                    if (cond.child1->requiresStatistics()) {
                        auto indices = cond.child1->getPassingIndices(values);
                        std::set<size_t> idx_set(indices.begin(), indices.end());
                        pass1 = idx_set.count(i) > 0;
                    } else {
                        pass1 = cond.child1->test(value);
                    }
                    if (cond.child2->requiresStatistics()) {
                        auto indices = cond.child2->getPassingIndices(values);
                        std::set<size_t> idx_set(indices.begin(), indices.end());
                        pass2 = idx_set.count(i) > 0;
                    } else {
                        pass2 = cond.child2->test(value);
                    }
                    cond_passes = pass1 || pass2;
                    break;
                }

                case ConditionType::NOT: {
                    bool pass1;
                    if (cond.child1->requiresStatistics()) {
                        auto indices = cond.child1->getPassingIndices(values);
                        std::set<size_t> idx_set(indices.begin(), indices.end());
                        pass1 = idx_set.count(i) > 0;
                    } else {
                        pass1 = cond.child1->test(value);
                    }
                    cond_passes = !pass1;
                    break;
                }
            }

            if (!cond_passes) {
                passes = false;
                break;
            }
        }

        if (passes) {
            indices.push_back(i);
        }
    }

    return indices;
}

size_t ValueFilter::count(const std::vector<double>& values) const {
    return getPassingIndices(values).size();
}

double ValueFilter::getPassingRate(const std::vector<double>& values) const {
    if (values.empty()) {
        return 0.0;
    }
    return static_cast<double>(count(values)) / values.size();
}

bool ValueFilter::evaluate(const std::map<std::string, double>& values) const {
    // If filter is empty, accept all
    if (pImpl->isEmpty()) {
        return true;
    }

    // Test if ANY value in the map passes the filter (OR logic)
    for (const auto& [name, value] : values) {
        if (test(value)) {
            return true;
        }
    }

    return false;
}

// ============================================================
// Query State
// ============================================================

bool ValueFilter::isEmpty() const {
    return pImpl->isEmpty();
}

bool ValueFilter::requiresStatistics() const {
    return pImpl->requiresStatistics();
}

std::string ValueFilter::getDescription() const {
    if (pImpl->isEmpty()) {
        return "No filter (accept all)";
    }

    std::ostringstream oss;
    bool first = true;

    for (const auto& cond : pImpl->conditions) {
        if (!first) oss << " AND ";

        switch (cond.type) {
            case ConditionType::RANGE:
                oss << cond.param1 << " <= value <= " << cond.param2;
                break;
            case ConditionType::OUTSIDE_RANGE:
                oss << "(value < " << cond.param1 << " OR value > " << cond.param2 << ")";
                break;
            case ConditionType::GREATER_THAN:
                oss << "value > " << cond.param1;
                break;
            case ConditionType::GREATER_EQUAL:
                oss << "value >= " << cond.param1;
                break;
            case ConditionType::LESS_THAN:
                oss << "value < " << cond.param1;
                break;
            case ConditionType::LESS_EQUAL:
                oss << "value <= " << cond.param1;
                break;
            case ConditionType::EQUAL:
                oss << "value == " << cond.param1 << " (±" << cond.param2 << ")";
                break;
            case ConditionType::NOT_EQUAL:
                oss << "value != " << cond.param1;
                break;
            case ConditionType::TOP_PERCENTILE:
                oss << "top " << cond.param1 << "%";
                break;
            case ConditionType::BOTTOM_PERCENTILE:
                oss << "bottom " << cond.param1 << "%";
                break;
            case ConditionType::PERCENTILE_RANGE:
                oss << "percentile [" << cond.param1 << ", " << cond.param2 << "]";
                break;
            case ConditionType::REMOVE_OUTLIERS:
                oss << "remove outliers (IQR*" << cond.param1 << ")";
                break;
            case ConditionType::WITHIN_STD:
                oss << "within " << cond.param1 << "σ";
                break;
            case ConditionType::OUTSIDE_STD:
                oss << "outside " << cond.param1 << "σ";
                break;
            case ConditionType::TOP_N:
                oss << "top " << static_cast<size_t>(cond.param1) << " values";
                break;
            case ConditionType::BOTTOM_N:
                oss << "bottom " << static_cast<size_t>(cond.param1) << " values";
                break;
            case ConditionType::CUSTOM_PREDICATE:
                oss << "custom predicate";
                break;
            case ConditionType::ACCEPT_ALL:
                oss << "accept all";
                break;
            case ConditionType::REJECT_ALL:
                oss << "reject all";
                break;
            case ConditionType::AND:
                oss << "(" << cond.child1->getDescription() << " AND "
                    << cond.child2->getDescription() << ")";
                break;
            case ConditionType::OR:
                oss << "(" << cond.child1->getDescription() << " OR "
                    << cond.child2->getDescription() << ")";
                break;
            case ConditionType::NOT:
                oss << "NOT (" << cond.child1->getDescription() << ")";
                break;
        }

        first = false;
    }

    return oss.str();
}

// ============================================================
// Clear and Reset
// ============================================================

ValueFilter& ValueFilter::clear() {
    pImpl->clear();
    return *this;
}

// ============================================================
// Static Factory Methods
// ============================================================

ValueFilter ValueFilter::acceptAll() {
    ValueFilter filter;
    FilterCondition cond(ConditionType::ACCEPT_ALL);
    filter.pImpl->conditions.push_back(cond);
    return filter;
}

ValueFilter ValueFilter::rejectAll() {
    ValueFilter filter;
    FilterCondition cond(ConditionType::REJECT_ALL);
    filter.pImpl->conditions.push_back(cond);
    return filter;
}

ValueFilter ValueFilter::positiveOnly() {
    ValueFilter filter;
    filter.greaterThan(0.0);
    return filter;
}

ValueFilter ValueFilter::negativeOnly() {
    ValueFilter filter;
    filter.lessThan(0.0);
    return filter;
}

ValueFilter ValueFilter::nonZero(double tolerance) {
    ValueFilter filter;
    filter.notEqualTo(0.0, tolerance);
    return filter;
}

ValueFilter ValueFilter::topN(size_t n) {
    ValueFilter filter;
    FilterCondition cond(ConditionType::TOP_N, static_cast<double>(n));
    filter.pImpl->conditions.push_back(cond);
    return filter;
}

ValueFilter ValueFilter::bottomN(size_t n) {
    ValueFilter filter;
    FilterCondition cond(ConditionType::BOTTOM_N, static_cast<double>(n));
    filter.pImpl->conditions.push_back(cond);
    return filter;
}

// ============================================================
// Private Helper Methods
// ============================================================

double ValueFilter::computePercentile(const std::vector<double>& values, double percentile) const {
    if (values.empty()) {
        return 0.0;
    }

    // Assume values are already sorted
    double index = (percentile / 100.0) * (values.size() - 1);
    size_t lower = static_cast<size_t>(std::floor(index));
    size_t upper = static_cast<size_t>(std::ceil(index));

    if (lower == upper) {
        return values[lower];
    }

    // Linear interpolation
    double fraction = index - lower;
    return values[lower] * (1.0 - fraction) + values[upper] * fraction;
}

std::pair<double, double> ValueFilter::computeMeanStdDev(const std::vector<double>& values) const {
    if (values.empty()) {
        return {0.0, 0.0};
    }

    // Compute mean
    double sum = std::accumulate(values.begin(), values.end(), 0.0);
    double mean = sum / values.size();

    // Compute standard deviation
    double sq_sum = 0.0;
    for (double v : values) {
        double diff = v - mean;
        sq_sum += diff * diff;
    }
    double variance = sq_sum / values.size();
    double std_dev = std::sqrt(variance);

    return {mean, std_dev};
}

double ValueFilter::computeIQR(const std::vector<double>& values) const {
    if (values.empty()) {
        return 0.0;
    }

    // Assume values are already sorted
    double q1 = computePercentile(values, 25.0);
    double q3 = computePercentile(values, 75.0);

    return q3 - q1;
}

} // namespace query
} // namespace kood3plot
