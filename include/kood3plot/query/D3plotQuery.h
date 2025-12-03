#pragma once

/**
 * @file D3plotQuery.h
 * @brief Main query builder interface for the KooD3plot Query System
 * @author KooD3plot V3 Development Team
 * @date 2025-11-21
 * @version 3.0.0
 *
 * D3plotQuery is the primary user-facing class for the KooD3plot Query System.
 * It implements the builder pattern to construct and execute queries on d3plot
 * files in a declarative, SQL-like manner.
 *
 * Core Philosophy:
 * - Declarative: Specify WHAT you want, not HOW to get it
 * - Composable: Chain methods to build complex queries
 * - Type-safe: Compile-time checking where possible
 * - Efficient: Only load data that's actually needed
 *
 * Example usage:
 * @code
 * D3plotReader reader("crash.d3plot");
 *
 * D3plotQuery(reader)
 *     .selectParts(PartSelector().byName("Hood"))
 *     .selectQuantities(QuantitySelector::commonCrash())
 *     .selectTime(TimeSelector::lastState())
 *     .whereValue(ValueFilter().greaterThan(500.0))
 *     .writeCSV("output.csv");
 * @endcode
 */

#include "PartSelector.h"
#include "QuantitySelector.h"
#include "TimeSelector.h"
#include "ValueFilter.h"
#include "OutputSpec.h"
#include "QueryTypes.h"
#include "QueryResult.h"
#include "../D3plotReader.hpp"
#include <string>
#include <memory>

namespace kood3plot {
namespace query {

/**
 * @class D3plotQuery
 * @brief Main builder class for constructing and executing d3plot queries
 *
 * This class provides a fluent interface for:
 * - Selecting parts (which parts to analyze)
 * - Selecting quantities (what physical values to extract)
 * - Selecting time (which timesteps to include)
 * - Filtering values (condition-based filtering)
 * - Specifying output format and options
 * - Executing the query
 * - Writing results to files
 */
class D3plotQuery {
public:
    // ============================================================
    // Constructors
    // ============================================================

    /**
     * @brief Construct query for a d3plot reader
     * @param reader D3plot reader instance
     *
     * Example:
     * @code
     * D3plotReader reader("crash.d3plot");
     * D3plotQuery query(reader);
     * @endcode
     */
    explicit D3plotQuery(const D3plotReader& reader);

    /**
     * @brief Copy constructor
     */
    D3plotQuery(const D3plotQuery& other);

    /**
     * @brief Move constructor
     */
    D3plotQuery(D3plotQuery&& other) noexcept;

    /**
     * @brief Assignment operator
     */
    D3plotQuery& operator=(const D3plotQuery& other);

    /**
     * @brief Move assignment operator
     */
    D3plotQuery& operator=(D3plotQuery&& other) noexcept;

    /**
     * @brief Destructor
     */
    ~D3plotQuery();

    // ============================================================
    // Selection Methods
    // ============================================================

    /**
     * @brief Select parts to query
     * @param selector Part selector
     * @return Reference to this query for method chaining
     *
     * Example:
     * @code
     * query.selectParts(PartSelector().byName("Hood"));
     * query.selectParts(PartSelector().byPattern("Door_*"));
     * @endcode
     */
    D3plotQuery& selectParts(const PartSelector& selector);

    /**
     * @brief Select parts by ID list
     * @param part_ids Vector of part IDs
     * @return Reference to this query
     *
     * Convenience method for simple ID-based selection.
     *
     * Example:
     * @code
     * query.selectParts({1, 2, 3, 100});
     * @endcode
     */
    D3plotQuery& selectParts(const std::vector<int32_t>& part_ids);

    /**
     * @brief Select parts by name list
     * @param part_names Vector of part names
     * @return Reference to this query
     *
     * Example:
     * @code
     * query.selectParts({"Hood", "Roof", "Door_LF"});
     * @endcode
     */
    D3plotQuery& selectParts(const std::vector<std::string>& part_names);

    /**
     * @brief Select all parts
     * @return Reference to this query
     */
    D3plotQuery& selectAllParts();

    /**
     * @brief Select quantities to extract
     * @param selector Quantity selector
     * @return Reference to this query
     *
     * Example:
     * @code
     * query.selectQuantities(QuantitySelector::vonMises());
     * query.selectQuantities(QuantitySelector().addStressAll());
     * @endcode
     */
    D3plotQuery& selectQuantities(const QuantitySelector& selector);

    /**
     * @brief Select quantities by name list
     * @param quantity_names Vector of quantity names
     * @return Reference to this query
     *
     * Example:
     * @code
     * query.selectQuantities({"von_mises", "effective_strain"});
     * @endcode
     */
    D3plotQuery& selectQuantities(const std::vector<std::string>& quantity_names);

    /**
     * @brief Select timesteps to include
     * @param selector Time selector
     * @return Reference to this query
     *
     * Example:
     * @code
     * query.selectTime(TimeSelector::lastState());
     * query.selectTime(TimeSelector().addTimeRange(0.0, 10.0));
     * @endcode
     */
    D3plotQuery& selectTime(const TimeSelector& selector);

    /**
     * @brief Select time by state indices
     * @param state_indices Vector of state indices
     * @return Reference to this query
     *
     * Example:
     * @code
     * query.selectTime({0, -1});  // First and last
     * @endcode
     */
    D3plotQuery& selectTime(const std::vector<int>& state_indices);

    // ============================================================
    // Filtering Methods
    // ============================================================

    /**
     * @brief Add value filter condition
     * @param filter Value filter
     * @return Reference to this query
     *
     * Example:
     * @code
     * query.whereValue(ValueFilter().greaterThan(500.0));
     * query.whereValue(ValueFilter().inRange(100.0, 1000.0));
     * @endcode
     */
    D3plotQuery& whereValue(const ValueFilter& filter);

    /**
     * @brief Filter values greater than threshold
     * @param threshold Threshold value
     * @return Reference to this query
     *
     * Convenience method.
     */
    D3plotQuery& whereGreaterThan(double threshold);

    /**
     * @brief Filter values in range
     * @param min Minimum value
     * @param max Maximum value
     * @return Reference to this query
     *
     * Convenience method.
     */
    D3plotQuery& whereInRange(double min, double max);

    // ============================================================
    // Output Specification
    // ============================================================

    /**
     * @brief Set output specification
     * @param spec Output specification
     * @return Reference to this query
     *
     * Example:
     * @code
     * query.output(OutputSpec::csv().precision(8));
     * @endcode
     */
    D3plotQuery& output(const OutputSpec& spec);

    /**
     * @brief Set output format
     * @param format Output format
     * @return Reference to this query
     *
     * Convenience method.
     */
    D3plotQuery& outputFormat(OutputFormat format);

    // ============================================================
    // Execution Methods
    // ============================================================

    /**
     * @brief Execute query and return results in memory
     * @return QueryResult containing extracted data
     *
     * This loads all matching data into memory. For large datasets,
     * consider using write methods directly to avoid memory overhead.
     *
     * Example:
     * @code
     * auto result = query.execute();
     * std::cout << "Extracted " << result.size() << " values\n";
     * @endcode
     */
    QueryResult execute();

    /**
     * @brief Execute query and write to CSV file
     * @param filename Output file path
     *
     * Example:
     * @code
     * query.writeCSV("output.csv");
     * @endcode
     */
    void writeCSV(const std::string& filename);

    /**
     * @brief Execute query and write to JSON file
     * @param filename Output file path
     */
    void writeJSON(const std::string& filename);

    /**
     * @brief Execute query and write to HDF5 file
     * @param filename Output file path
     */
    void writeHDF5(const std::string& filename);

    /**
     * @brief Execute query and write using output spec
     * @param filename Output file path
     *
     * Format is determined by OutputSpec configuration.
     */
    void write(const std::string& filename);

    // ============================================================
    // Query Introspection
    // ============================================================

    /**
     * @brief Get description of query (for debugging/logging)
     * @return String describing the query
     *
     * Example output:
     * "Query: Parts[Hood], Quantities[von_mises, effective_strain], Time[last], Filter[value > 500]"
     */
    std::string getDescription() const;

    /**
     * @brief Estimate number of data points to be extracted
     * @return Estimated number of values
     *
     * Useful for checking query size before execution.
     */
    size_t estimateSize() const;

    /**
     * @brief Check if query is valid
     * @return true if query can be executed
     */
    bool validate() const;

    /**
     * @brief Get validation errors
     * @return Vector of error messages (empty if valid)
     */
    std::vector<std::string> getValidationErrors() const;

    // ============================================================
    // Static Factory Methods
    // ============================================================

    /**
     * @brief Create query for extracting maximum von mises stress
     * @param reader D3plot reader
     * @param part_ids Part IDs to analyze (empty = all parts)
     * @return Configured query
     *
     * Example:
     * @code
     * auto max_vm = D3plotQuery::maxVonMises(reader, {1, 2, 3});
     * max_vm.writeCSV("max_stress.csv");
     * @endcode
     */
    static D3plotQuery maxVonMises(const D3plotReader& reader,
                                   const std::vector<int32_t>& part_ids = {});

    /**
     * @brief Create query for extracting maximum effective strain
     * @param reader D3plot reader
     * @param part_ids Part IDs to analyze (empty = all parts)
     * @return Configured query
     */
    static D3plotQuery maxEffectiveStrain(const D3plotReader& reader,
                                          const std::vector<int32_t>& part_ids = {});

    /**
     * @brief Create query for final state analysis
     * @param reader D3plot reader
     * @return Configured query for last timestep
     */
    static D3plotQuery finalState(const D3plotReader& reader);

    /**
     * @brief Create query for time history
     * @param reader D3plot reader
     * @param part_id Part ID to track
     * @param element_id Element ID to track
     * @return Configured query for time history
     */
    static D3plotQuery timeHistory(const D3plotReader& reader,
                                   int32_t part_id,
                                   int32_t element_id);

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
     * @brief Execute query core logic
     */
    void executeQuery();

    /**
     * @brief Write results to file with specified format
     */
    void writeToFile(const std::string& filename, OutputFormat format);
};

} // namespace query
} // namespace kood3plot
