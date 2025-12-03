#pragma once

/**
 * @file QueryResult.h
 * @brief Query result container for extracted d3plot data
 * @author KooD3plot V3 Development Team
 * @date 2025-11-21
 * @version 3.0.0
 *
 * QueryResult stores the results of a D3plotQuery execution, providing:
 * - Access to individual data points
 * - Iteration over results
 * - Aggregation and statistics
 * - Filtering capabilities
 */

#include "kood3plot/query/QueryTypes.h"
#include <string>
#include <vector>
#include <map>
#include <memory>
#include <optional>
#include <functional>

namespace kood3plot {
namespace query {

// ============================================================
// Data Point Structures
// ============================================================

/**
 * @brief Single data point from query result
 *
 * Represents one element at one timestep with all selected quantities
 */
struct ResultDataPoint {
    int32_t element_id;             ///< Element ID (real ID from NARBS)
    int32_t part_id;                ///< Part ID
    int32_t state_index;            ///< State index (0-based)
    double time;                    ///< Simulation time

    /// Quantity values: quantity_name -> value
    std::map<std::string, double> values;

    /**
     * @brief Get value for a specific quantity
     * @param quantity_name Name of quantity (e.g., "von_mises")
     * @return Optional value (empty if quantity not present)
     */
    std::optional<double> getValue(const std::string& quantity_name) const {
        auto it = values.find(quantity_name);
        if (it != values.end()) {
            return it->second;
        }
        return std::nullopt;
    }

    /**
     * @brief Get value with default fallback
     * @param quantity_name Name of quantity
     * @param default_value Value to return if quantity not present
     * @return Quantity value or default
     */
    double getValueOr(const std::string& quantity_name, double default_value = 0.0) const {
        auto it = values.find(quantity_name);
        return (it != values.end()) ? it->second : default_value;
    }
};

/**
 * @brief Statistics for a quantity
 */
struct QuantityStatistics {
    std::string quantity_name;      ///< Name of the quantity
    double min_value;               ///< Minimum value
    double max_value;               ///< Maximum value
    double mean_value;              ///< Mean (average) value
    double std_dev;                 ///< Standard deviation
    double sum;                     ///< Sum of all values
    double range;                   ///< Range (max - min)
    double median;                  ///< Median value
    size_t count;                   ///< Number of data points

    // Location of extrema
    int32_t min_element_id;         ///< Element ID with minimum value
    int32_t max_element_id;         ///< Element ID with maximum value
    int32_t min_state_index;        ///< State index of minimum value
    int32_t max_state_index;        ///< State index of maximum value
    double min_time;                ///< Time of minimum value
    double max_time;                ///< Time of maximum value
};

/**
 * @brief Aggregated result for a single element across all timesteps
 */
struct ElementAggregation {
    int32_t element_id;             ///< Element ID
    int32_t part_id;                ///< Part ID

    /// Aggregated values: quantity_name -> (aggregation_type -> value)
    std::map<std::string, std::map<AggregationType, double>> aggregated_values;

    /// Time of maximum for each quantity
    std::map<std::string, double> time_of_max;

    /// Time of minimum for each quantity
    std::map<std::string, double> time_of_min;
};

/**
 * @brief Time history for a single element
 */
struct ElementTimeHistory {
    int32_t element_id;             ///< Element ID
    int32_t part_id;                ///< Part ID

    std::vector<double> times;      ///< Time values
    std::vector<int32_t> state_indices;  ///< State indices

    /// Quantity time histories: quantity_name -> values (same length as times)
    std::map<std::string, std::vector<double>> quantity_histories;
};

// ============================================================
// QueryResult Class
// ============================================================

/**
 * @brief Container for query execution results
 *
 * QueryResult stores the data extracted from a D3plotQuery execution.
 * It provides multiple ways to access and analyze the data:
 * - Iteration over all data points
 * - Access by element ID, part ID, or timestep
 * - Statistical analysis
 * - Aggregation
 *
 * Example usage:
 * @code
 * QueryResult result = query.execute();
 *
 * // Iterate over all data points
 * for (const auto& point : result) {
 *     std::cout << "Element " << point.element_id
 *               << " at t=" << point.time
 *               << " von_mises=" << point.getValueOr("von_mises") << std::endl;
 * }
 *
 * // Get statistics
 * auto stats = result.getStatistics("von_mises");
 * std::cout << "Max von Mises: " << stats.max_value
 *           << " at element " << stats.max_element_id << std::endl;
 *
 * // Get time history for an element
 * auto history = result.getElementHistory(12345);
 * @endcode
 */
class QueryResult {
public:
    // ============================================================
    // Constructors and Destructor
    // ============================================================

    /**
     * @brief Default constructor (empty result)
     */
    QueryResult();

    /**
     * @brief Copy constructor
     */
    QueryResult(const QueryResult& other);

    /**
     * @brief Move constructor
     */
    QueryResult(QueryResult&& other) noexcept;

    /**
     * @brief Copy assignment
     */
    QueryResult& operator=(const QueryResult& other);

    /**
     * @brief Move assignment
     */
    QueryResult& operator=(QueryResult&& other) noexcept;

    /**
     * @brief Destructor
     */
    ~QueryResult();

    // ============================================================
    // Data Point Access
    // ============================================================

    /**
     * @brief Get number of data points
     */
    size_t size() const;

    /**
     * @brief Check if result is empty
     */
    bool empty() const;

    /**
     * @brief Get all data points
     */
    const std::vector<ResultDataPoint>& getDataPoints() const;

    /**
     * @brief Get data point by index
     * @param index Index of data point
     * @return Reference to data point
     * @throw std::out_of_range if index is invalid
     */
    const ResultDataPoint& at(size_t index) const;

    /**
     * @brief Get data point by index (operator)
     */
    const ResultDataPoint& operator[](size_t index) const;

    // ============================================================
    // Iteration Support
    // ============================================================

    using iterator = std::vector<ResultDataPoint>::iterator;
    using const_iterator = std::vector<ResultDataPoint>::const_iterator;

    iterator begin();
    iterator end();
    const_iterator begin() const;
    const_iterator end() const;
    const_iterator cbegin() const;
    const_iterator cend() const;

    // ============================================================
    // Filtering
    // ============================================================

    /**
     * @brief Get data points for a specific part
     * @param part_id Part ID to filter by
     * @return New QueryResult with filtered data
     */
    QueryResult filterByPart(int32_t part_id) const;

    /**
     * @brief Get data points for specific parts
     * @param part_ids Part IDs to filter by
     * @return New QueryResult with filtered data
     */
    QueryResult filterByParts(const std::vector<int32_t>& part_ids) const;

    /**
     * @brief Get data points for a specific element
     * @param element_id Element ID to filter by
     * @return New QueryResult with filtered data
     */
    QueryResult filterByElement(int32_t element_id) const;

    /**
     * @brief Get data points for a specific state
     * @param state_index State index to filter by
     * @return New QueryResult with filtered data
     */
    QueryResult filterByState(int32_t state_index) const;

    /**
     * @brief Get data points in a time range
     * @param min_time Minimum time (inclusive)
     * @param max_time Maximum time (inclusive)
     * @return New QueryResult with filtered data
     */
    QueryResult filterByTimeRange(double min_time, double max_time) const;

    /**
     * @brief Filter by custom predicate
     * @param predicate Function that returns true for points to keep
     * @return New QueryResult with filtered data
     */
    QueryResult filter(std::function<bool(const ResultDataPoint&)> predicate) const;

    // ============================================================
    // Statistics
    // ============================================================

    /**
     * @brief Get statistics for a quantity
     * @param quantity_name Name of quantity to analyze
     * @return Statistics structure
     */
    QuantityStatistics getStatistics(const std::string& quantity_name) const;

    /**
     * @brief Get statistics for all quantities
     * @return Map of quantity name to statistics
     */
    std::map<std::string, QuantityStatistics> getAllStatistics() const;

    /**
     * @brief Get list of available quantities
     */
    std::vector<std::string> getQuantityNames() const;

    /**
     * @brief Get list of unique part IDs
     */
    std::vector<int32_t> getPartIds() const;

    /**
     * @brief Get list of unique element IDs
     */
    std::vector<int32_t> getElementIds() const;

    /**
     * @brief Get list of unique state indices
     */
    std::vector<int32_t> getStateIndices() const;

    /**
     * @brief Get list of unique time values
     */
    std::vector<double> getTimeValues() const;

    // ============================================================
    // Aggregation
    // ============================================================

    /**
     * @brief Aggregate results by element (across all timesteps)
     * @param agg_type Aggregation type (MAX, MIN, MEAN, etc.)
     * @return Map of element_id to aggregated result
     */
    std::map<int32_t, ElementAggregation> aggregateByElement(AggregationType agg_type) const;

    /**
     * @brief Get time history for an element
     * @param element_id Element ID to get history for
     * @return Time history structure
     */
    ElementTimeHistory getElementHistory(int32_t element_id) const;

    /**
     * @brief Aggregate all values for a quantity using specified aggregation
     * @param quantity_name Quantity name
     * @param agg_type Aggregation type (SUM, COUNT, MEAN, etc.)
     * @return Aggregated value
     */
    double aggregate(const std::string& quantity_name, AggregationType agg_type) const;

    /**
     * @brief Get sum of all values for a quantity
     * @param quantity_name Quantity name
     * @return Sum of all values
     */
    double sum(const std::string& quantity_name) const;

    /**
     * @brief Get count of data points for a quantity
     * @param quantity_name Quantity name
     * @return Number of data points
     */
    size_t count(const std::string& quantity_name) const;

    /**
     * @brief Get range (max - min) for a quantity
     * @param quantity_name Quantity name
     * @return Range of values
     */
    double range(const std::string& quantity_name) const;

    /**
     * @brief Get all values for a quantity
     * @param quantity_name Quantity name
     * @return Vector of values (in order of data points)
     */
    std::vector<double> getValues(const std::string& quantity_name) const;

    /**
     * @brief Find data point with maximum value for a quantity
     * @param quantity_name Quantity name
     * @return Optional data point (empty if no data)
     */
    std::optional<ResultDataPoint> findMax(const std::string& quantity_name) const;

    /**
     * @brief Find data point with minimum value for a quantity
     * @param quantity_name Quantity name
     * @return Optional data point (empty if no data)
     */
    std::optional<ResultDataPoint> findMin(const std::string& quantity_name) const;

    // ============================================================
    // Metadata
    // ============================================================

    /**
     * @brief Get query description
     */
    std::string getQueryDescription() const;

    /**
     * @brief Set query description
     */
    void setQueryDescription(const std::string& description);

    /**
     * @brief Get source filename
     */
    std::string getSourceFile() const;

    /**
     * @brief Set source filename
     */
    void setSourceFile(const std::string& filename);

    /**
     * @brief Get custom metadata value
     */
    std::optional<std::string> getMetadata(const std::string& key) const;

    /**
     * @brief Set custom metadata value
     */
    void setMetadata(const std::string& key, const std::string& value);

    /**
     * @brief Get all metadata
     */
    std::map<std::string, std::string> getAllMetadata() const;

    // ============================================================
    // Modification (for building results)
    // ============================================================

    /**
     * @brief Add a data point
     * @param point Data point to add
     */
    void addDataPoint(const ResultDataPoint& point);

    /**
     * @brief Add a data point (move)
     */
    void addDataPoint(ResultDataPoint&& point);

    /**
     * @brief Reserve capacity for data points
     * @param capacity Number of data points to reserve space for
     */
    void reserve(size_t capacity);

    /**
     * @brief Clear all data points
     */
    void clear();

    /**
     * @brief Sort data points by a custom comparator
     */
    void sort(std::function<bool(const ResultDataPoint&, const ResultDataPoint&)> comparator);

    /**
     * @brief Sort by element ID, then by state index
     */
    void sortByElement();

    /**
     * @brief Sort by state index (time), then by element ID
     */
    void sortByTime();

    /**
     * @brief Sort by part ID, then by element ID, then by state index
     */
    void sortByPart();

    // ============================================================
    // Summary and Output
    // ============================================================

    /**
     * @brief Get human-readable summary of results
     */
    std::string getSummary() const;

    /**
     * @brief Get formatted table view (limited rows)
     * @param max_rows Maximum rows to display (0 = all)
     */
    std::string toTable(size_t max_rows = 20) const;

private:
    struct Impl;
    std::unique_ptr<Impl> pImpl;
};

} // namespace query
} // namespace kood3plot
