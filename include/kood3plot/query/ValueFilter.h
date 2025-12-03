#pragma once

/**
 * @file ValueFilter.h
 * @brief Value filtering interface for the KooD3plot Query System
 * @author KooD3plot V3 Development Team
 * @date 2025-11-21
 * @version 3.0.0
 *
 * ValueFilter provides flexible methods to filter query results by value:
 * - Range filtering (min/max values)
 * - Conditional filtering (>, <, ==, !=, >=, <=)
 * - Percentile filtering (top 10%, bottom 5%, etc.)
 * - Logical combinations (AND, OR, NOT)
 * - Special filters (peak detection, threshold crossing)
 *
 * Example usage:
 * @code
 * ValueFilter filter;
 * filter.greaterThan(500.0)          // von_mises > 500 MPa
 *       .lessThan(1000.0)            // AND von_mises < 1000 MPa
 *       .orFilter(
 *           ValueFilter().inTopPercentile(10)  // OR in top 10%
 *       );
 * @endcode
 */

#include "QueryTypes.h"
#include <vector>
#include <optional>
#include <functional>

namespace kood3plot {
namespace query {

/**
 * @class ValueFilter
 * @brief Filters query results based on value conditions
 *
 * This class implements filtering of numerical values extracted from
 * d3plot results. It supports:
 * - Range-based filtering (min/max)
 * - Comparison operations (>, <, ==, etc.)
 * - Statistical filtering (percentiles, outliers)
 * - Logical combinations (AND, OR, NOT)
 * - Custom predicates
 */
class ValueFilter {
public:
    // ============================================================
    // Constructors
    // ============================================================

    /**
     * @brief Default constructor (no filtering)
     */
    ValueFilter();

    /**
     * @brief Copy constructor
     */
    ValueFilter(const ValueFilter& other);

    /**
     * @brief Move constructor
     */
    ValueFilter(ValueFilter&& other) noexcept;

    /**
     * @brief Assignment operator
     */
    ValueFilter& operator=(const ValueFilter& other);

    /**
     * @brief Move assignment operator
     */
    ValueFilter& operator=(ValueFilter&& other) noexcept;

    /**
     * @brief Destructor
     */
    ~ValueFilter();

    // ============================================================
    // Range Filtering
    // ============================================================

    /**
     * @brief Filter values within a range
     * @param min Minimum value (inclusive)
     * @param max Maximum value (inclusive)
     * @return Reference to this filter for method chaining
     *
     * Example:
     * @code
     * filter.inRange(100.0, 500.0);  // 100 <= value <= 500
     * @endcode
     */
    ValueFilter& inRange(double min, double max);

    /**
     * @brief Filter values outside a range
     * @param min Lower bound (exclusive)
     * @param max Upper bound (exclusive)
     * @return Reference to this filter
     *
     * Example:
     * @code
     * filter.outsideRange(100.0, 500.0);  // value < 100 OR value > 500
     * @endcode
     */
    ValueFilter& outsideRange(double min, double max);

    // ============================================================
    // Comparison Filtering
    // ============================================================

    /**
     * @brief Filter values greater than threshold
     * @param threshold Threshold value
     * @return Reference to this filter
     *
     * Example:
     * @code
     * filter.greaterThan(500.0);  // value > 500
     * @endcode
     */
    ValueFilter& greaterThan(double threshold);

    /**
     * @brief Filter values greater than or equal to threshold
     * @param threshold Threshold value
     * @return Reference to this filter
     */
    ValueFilter& greaterThanOrEqual(double threshold);

    /**
     * @brief Filter values less than threshold
     * @param threshold Threshold value
     * @return Reference to this filter
     */
    ValueFilter& lessThan(double threshold);

    /**
     * @brief Filter values less than or equal to threshold
     * @param threshold Threshold value
     * @return Reference to this filter
     */
    ValueFilter& lessThanOrEqual(double threshold);

    /**
     * @brief Filter values equal to target
     * @param value Target value
     * @param tolerance Absolute tolerance for floating-point comparison
     * @return Reference to this filter
     *
     * Example:
     * @code
     * filter.equalTo(0.0, 1e-6);  // |value - 0.0| < 1e-6
     * @endcode
     */
    ValueFilter& equalTo(double value, double tolerance = 1e-9);

    /**
     * @brief Filter values not equal to target
     * @param value Target value
     * @param tolerance Absolute tolerance for floating-point comparison
     * @return Reference to this filter
     */
    ValueFilter& notEqualTo(double value, double tolerance = 1e-9);

    // ============================================================
    // Percentile Filtering
    // ============================================================

    /**
     * @brief Filter values in top N percentile
     * @param percentile Percentile value (0-100)
     * @return Reference to this filter
     *
     * Example:
     * @code
     * filter.inTopPercentile(10);  // Top 10% of values
     * @endcode
     */
    ValueFilter& inTopPercentile(double percentile);

    /**
     * @brief Filter values in bottom N percentile
     * @param percentile Percentile value (0-100)
     * @return Reference to this filter
     *
     * Example:
     * @code
     * filter.inBottomPercentile(5);  // Bottom 5% of values
     * @endcode
     */
    ValueFilter& inBottomPercentile(double percentile);

    /**
     * @brief Filter values between two percentiles
     * @param lower_percentile Lower percentile (0-100)
     * @param upper_percentile Upper percentile (0-100)
     * @return Reference to this filter
     *
     * Example:
     * @code
     * filter.betweenPercentiles(25, 75);  // Middle 50% (interquartile range)
     * @endcode
     */
    ValueFilter& betweenPercentiles(double lower_percentile, double upper_percentile);

    // ============================================================
    // Statistical Filtering
    // ============================================================

    /**
     * @brief Filter outliers using IQR method
     * @param iqr_multiplier IQR multiplier (default 1.5)
     * @return Reference to this filter
     *
     * Outliers are defined as values outside:
     * [Q1 - iqr_multiplier*IQR, Q3 + iqr_multiplier*IQR]
     *
     * Example:
     * @code
     * filter.removeOutliers();      // Standard outlier removal (1.5*IQR)
     * filter.removeOutliers(3.0);   // More conservative (3*IQR)
     * @endcode
     */
    ValueFilter& removeOutliers(double iqr_multiplier = 1.5);

    /**
     * @brief Filter values within N standard deviations from mean
     * @param n_std Number of standard deviations
     * @return Reference to this filter
     *
     * Example:
     * @code
     * filter.withinStdDev(2.0);  // Within ±2σ of mean
     * @endcode
     */
    ValueFilter& withinStdDev(double n_std);

    /**
     * @brief Filter values outside N standard deviations from mean
     * @param n_std Number of standard deviations
     * @return Reference to this filter
     */
    ValueFilter& outsideStdDev(double n_std);

    // ============================================================
    // Logical Operations
    // ============================================================

    /**
     * @brief Combine with another filter using AND logic
     * @param other Another value filter
     * @return New filter with both conditions
     *
     * Example:
     * @code
     * auto combined = filter1 && filter2;  // Both must pass
     * @endcode
     */
    ValueFilter operator&&(const ValueFilter& other) const;

    /**
     * @brief Combine with another filter using OR logic
     * @param other Another value filter
     * @return New filter with either condition
     *
     * Example:
     * @code
     * auto combined = filter1 || filter2;  // Either can pass
     * @endcode
     */
    ValueFilter operator||(const ValueFilter& other) const;

    /**
     * @brief Invert filter (NOT logic)
     * @return New filter with inverted condition
     *
     * Example:
     * @code
     * auto inverted = !filter;  // Negate all conditions
     * @endcode
     */
    ValueFilter operator!() const;

    /**
     * @brief Combine with another filter using AND logic (method form)
     * @param other Another value filter
     * @return Reference to this filter
     */
    ValueFilter& andFilter(const ValueFilter& other);

    /**
     * @brief Combine with another filter using OR logic (method form)
     * @param other Another value filter
     * @return Reference to this filter
     */
    ValueFilter& orFilter(const ValueFilter& other);

    /**
     * @brief Invert all conditions in this filter
     * @return Reference to this filter
     */
    ValueFilter& negate();

    // ============================================================
    // Custom Filtering
    // ============================================================

    /**
     * @brief Add custom predicate function
     * @param predicate Function that takes a value and returns true if it passes
     * @return Reference to this filter
     *
     * Example:
     * @code
     * filter.addPredicate([](double v) {
     *     return std::fmod(v, 10.0) == 0.0;  // Only multiples of 10
     * });
     * @endcode
     */
    ValueFilter& addPredicate(std::function<bool(double)> predicate);

    // ============================================================
    // Evaluation Methods
    // ============================================================

    /**
     * @brief Test if a single value passes the filter
     * @param value Value to test
     * @return true if value passes all filter conditions
     *
     * Example:
     * @code
     * if (filter.test(525.0)) {
     *     // Value passes filter
     * }
     * @endcode
     */
    bool test(double value) const;

    /**
     * @brief Filter a vector of values
     * @param values Input values
     * @return Vector of values that pass the filter
     *
     * Example:
     * @code
     * std::vector<double> data = {100, 200, 300, 400, 500};
     * auto filtered = filter.apply(data);
     * @endcode
     */
    std::vector<double> apply(const std::vector<double>& values) const;

    /**
     * @brief Get indices of values that pass the filter
     * @param values Input values
     * @return Vector of indices (0-based) of passing values
     *
     * Example:
     * @code
     * std::vector<double> data = {100, 200, 300, 400, 500};
     * auto indices = filter.getPassingIndices(data);
     * // indices might be {2, 3, 4} if filter is greaterThan(250)
     * @endcode
     */
    std::vector<size_t> getPassingIndices(const std::vector<double>& values) const;

    /**
     * @brief Count how many values pass the filter
     * @param values Input values
     * @return Number of values that pass
     */
    size_t count(const std::vector<double>& values) const;

    /**
     * @brief Get passing rate (fraction of values that pass)
     * @param values Input values
     * @return Fraction of values that pass (0.0 to 1.0)
     */
    double getPassingRate(const std::vector<double>& values) const;

    /**
     * @brief Evaluate filter against a map of named values
     * @param values Map of quantity_name -> value
     * @return true if any value in the map passes the filter (OR logic)
     *
     * Used by query system to filter data points with multiple quantities.
     */
    bool evaluate(const std::map<std::string, double>& values) const;

    // ============================================================
    // Query State
    // ============================================================

    /**
     * @brief Check if filter is empty (no conditions)
     * @return true if no filter conditions specified
     */
    bool isEmpty() const;

    /**
     * @brief Check if filter requires statistics
     * @return true if filter uses percentiles or std dev
     *
     * This indicates that the filter needs to see all data values
     * before it can be applied (for computing percentiles, mean, etc.)
     */
    bool requiresStatistics() const;

    /**
     * @brief Get description of filter conditions (for debugging)
     * @return String describing the filter
     *
     * Example output: "value > 500.0 AND value < 1000.0"
     */
    std::string getDescription() const;

    // ============================================================
    // Clear and Reset
    // ============================================================

    /**
     * @brief Clear all filter conditions
     * @return Reference to this filter
     */
    ValueFilter& clear();

    // ============================================================
    // Static Factory Methods
    // ============================================================

    /**
     * @brief Create filter that accepts all values
     * @return ValueFilter with no conditions
     */
    static ValueFilter acceptAll();

    /**
     * @brief Create filter that rejects all values
     * @return ValueFilter that always returns false
     */
    static ValueFilter rejectAll();

    /**
     * @brief Create filter for positive values only
     * @return ValueFilter with value > 0
     */
    static ValueFilter positiveOnly();

    /**
     * @brief Create filter for negative values only
     * @return ValueFilter with value < 0
     */
    static ValueFilter negativeOnly();

    /**
     * @brief Create filter for non-zero values
     * @param tolerance Absolute tolerance
     * @return ValueFilter excluding values near zero
     */
    static ValueFilter nonZero(double tolerance = 1e-9);

    /**
     * @brief Create filter for top N values
     * @param n Number of top values to keep
     * @return ValueFilter configured for top N
     */
    static ValueFilter topN(size_t n);

    /**
     * @brief Create filter for bottom N values
     * @param n Number of bottom values to keep
     * @return ValueFilter configured for bottom N
     */
    static ValueFilter bottomN(size_t n);

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
     * @brief Compute percentile value from data
     */
    double computePercentile(const std::vector<double>& values, double percentile) const;

    /**
     * @brief Compute mean and standard deviation
     */
    std::pair<double, double> computeMeanStdDev(const std::vector<double>& values) const;

    /**
     * @brief Compute interquartile range
     */
    double computeIQR(const std::vector<double>& values) const;
};

} // namespace query
} // namespace kood3plot
