#pragma once

/**
 * @file QueryTemplate.h
 * @brief Reusable query templates for common analysis patterns
 * @author KooD3plot V3 Development Team
 * @date 2025-11-22
 * @version 3.0.0
 *
 * QueryTemplate provides pre-defined query configurations for common
 * automotive crash analysis workflows. Templates can be customized
 * with parameters and saved/loaded from files.
 *
 * Example usage:
 * @code
 * // Load a built-in template
 * auto tmpl = QueryTemplate::maxStressHistory();
 *
 * // Customize parameters
 * tmpl.setParameter("parts", {"Hood", "Fender"});
 * tmpl.setParameter("stress_type", "von_mises");
 *
 * // Execute
 * auto query = tmpl.createQuery(reader);
 * query.writeCSV("max_stress.csv");
 * @endcode
 */

#include "D3plotQuery.h"
#include "PartSelector.h"
#include "QuantitySelector.h"
#include "TimeSelector.h"
#include "ValueFilter.h"
#include "OutputSpec.h"
#include <string>
#include <vector>
#include <map>
#include <memory>
#include <variant>
#include <functional>

namespace kood3plot {
namespace query {

/**
 * @brief Parameter value type (can be string, number, or list)
 */
using ParameterValue = std::variant<
    std::string,
    double,
    int32_t,
    bool,
    std::vector<std::string>,
    std::vector<int32_t>,
    std::vector<double>
>;

/**
 * @brief Template parameter definition
 */
struct TemplateParameter {
    std::string name;           ///< Parameter name
    std::string description;    ///< Human-readable description
    std::string type;           ///< Type: "string", "number", "bool", "string_list", "int_list"
    ParameterValue default_value;  ///< Default value
    bool required;              ///< Whether parameter is required
};

/**
 * @class QueryTemplate
 * @brief Reusable query template with parameterization
 *
 * Templates encapsulate common query patterns and allow
 * customization through parameters without rebuilding queries.
 */
class QueryTemplate {
public:
    // ============================================================
    // Constructors
    // ============================================================

    /**
     * @brief Default constructor
     */
    QueryTemplate();

    /**
     * @brief Construct with name and description
     * @param name Template name
     * @param description Template description
     */
    QueryTemplate(const std::string& name, const std::string& description);

    /**
     * @brief Copy constructor
     */
    QueryTemplate(const QueryTemplate& other);

    /**
     * @brief Move constructor
     */
    QueryTemplate(QueryTemplate&& other) noexcept;

    /**
     * @brief Assignment operator
     */
    QueryTemplate& operator=(const QueryTemplate& other);

    /**
     * @brief Move assignment operator
     */
    QueryTemplate& operator=(QueryTemplate&& other) noexcept;

    /**
     * @brief Destructor
     */
    ~QueryTemplate();

    // ============================================================
    // Template Definition
    // ============================================================

    /**
     * @brief Set template name
     * @param name Template name
     * @return Reference for chaining
     */
    QueryTemplate& setName(const std::string& name);

    /**
     * @brief Set template description
     * @param description Template description
     * @return Reference for chaining
     */
    QueryTemplate& setDescription(const std::string& description);

    /**
     * @brief Set template category
     * @param category Category (e.g., "stress", "strain", "displacement")
     * @return Reference for chaining
     */
    QueryTemplate& setCategory(const std::string& category);

    /**
     * @brief Add parameter definition
     * @param param Parameter definition
     * @return Reference for chaining
     */
    QueryTemplate& addParameter(const TemplateParameter& param);

    /**
     * @brief Add parameter with simpler interface
     * @param name Parameter name
     * @param description Description
     * @param default_value Default value
     * @param required Whether required
     * @return Reference for chaining
     */
    QueryTemplate& addParameter(const std::string& name,
                                const std::string& description,
                                const ParameterValue& default_value,
                                bool required = false);

    // ============================================================
    // Query Configuration
    // ============================================================

    /**
     * @brief Set part selector configuration
     * @param selector Part selector
     * @return Reference for chaining
     */
    QueryTemplate& setParts(const PartSelector& selector);

    /**
     * @brief Set quantity selector configuration
     * @param selector Quantity selector
     * @return Reference for chaining
     */
    QueryTemplate& setQuantities(const QuantitySelector& selector);

    /**
     * @brief Set time selector configuration
     * @param selector Time selector
     * @return Reference for chaining
     */
    QueryTemplate& setTime(const TimeSelector& selector);

    /**
     * @brief Set value filter configuration
     * @param filter Value filter
     * @return Reference for chaining
     */
    QueryTemplate& setFilter(const ValueFilter& filter);

    /**
     * @brief Set output specification
     * @param spec Output spec
     * @return Reference for chaining
     */
    QueryTemplate& setOutput(const OutputSpec& spec);

    // ============================================================
    // Parameter Values
    // ============================================================

    /**
     * @brief Set parameter value
     * @param name Parameter name
     * @param value Parameter value
     * @return Reference for chaining
     */
    QueryTemplate& setParameter(const std::string& name, const ParameterValue& value);

    /**
     * @brief Set string parameter
     */
    QueryTemplate& setParameter(const std::string& name, const std::string& value);

    /**
     * @brief Set numeric parameter
     */
    QueryTemplate& setParameter(const std::string& name, double value);

    /**
     * @brief Set integer parameter
     */
    QueryTemplate& setParameter(const std::string& name, int32_t value);

    /**
     * @brief Set boolean parameter
     */
    QueryTemplate& setParameter(const std::string& name, bool value);

    /**
     * @brief Set string list parameter
     */
    QueryTemplate& setParameter(const std::string& name, const std::vector<std::string>& value);

    /**
     * @brief Set integer list parameter
     */
    QueryTemplate& setParameter(const std::string& name, const std::vector<int32_t>& value);

    /**
     * @brief Get parameter value
     * @param name Parameter name
     * @return Parameter value
     */
    ParameterValue getParameter(const std::string& name) const;

    /**
     * @brief Check if parameter is set
     * @param name Parameter name
     * @return true if parameter has a value
     */
    bool hasParameter(const std::string& name) const;

    // ============================================================
    // Query Creation
    // ============================================================

    /**
     * @brief Create query from template
     * @param reader D3plot reader
     * @return Configured D3plotQuery
     *
     * Creates a D3plotQuery with all template settings applied.
     * Parameters are substituted into the query configuration.
     */
    D3plotQuery createQuery(const D3plotReader& reader) const;

    /**
     * @brief Validate template configuration
     * @return true if valid
     */
    bool validate() const;

    /**
     * @brief Get validation errors
     * @return Vector of error messages
     */
    std::vector<std::string> getValidationErrors() const;

    // ============================================================
    // Introspection
    // ============================================================

    /**
     * @brief Get template name
     */
    std::string getName() const;

    /**
     * @brief Get template description
     */
    std::string getDescription() const;

    /**
     * @brief Get template category
     */
    std::string getCategory() const;

    /**
     * @brief Get all parameter definitions
     */
    std::vector<TemplateParameter> getParameters() const;

    /**
     * @brief Get human-readable summary
     */
    std::string getSummary() const;

    // ============================================================
    // Serialization
    // ============================================================

    /**
     * @brief Save template to YAML file
     * @param filename Output file path
     */
    void saveToYAML(const std::string& filename) const;

    /**
     * @brief Save template to JSON file
     * @param filename Output file path
     */
    void saveToJSON(const std::string& filename) const;

    /**
     * @brief Load template from YAML file
     * @param filename Input file path
     * @return Loaded template
     */
    static QueryTemplate loadFromYAML(const std::string& filename);

    /**
     * @brief Load template from JSON file
     * @param filename Input file path
     * @return Loaded template
     */
    static QueryTemplate loadFromJSON(const std::string& filename);

    // ============================================================
    // Built-in Templates (Static Factory Methods)
    // ============================================================

    /**
     * @brief Maximum stress history template
     *
     * Tracks maximum von Mises stress over time for selected parts.
     * Parameters: parts (string_list), stress_type (string)
     */
    static QueryTemplate maxStressHistory();

    /**
     * @brief Maximum strain history template
     *
     * Tracks maximum effective strain over time for selected parts.
     * Parameters: parts (string_list), strain_type (string)
     */
    static QueryTemplate maxStrainHistory();

    /**
     * @brief Final state analysis template
     *
     * Extracts all quantities at the final timestep.
     * Parameters: parts (string_list), quantities (string_list)
     */
    static QueryTemplate finalStateAnalysis();

    /**
     * @brief Critical zone identification template
     *
     * Identifies elements exceeding stress/strain thresholds.
     * Parameters: parts, stress_threshold, strain_threshold
     */
    static QueryTemplate criticalZones();

    /**
     * @brief Element time history template
     *
     * Extracts complete time history for specific elements.
     * Parameters: element_ids (int_list), quantities (string_list)
     */
    static QueryTemplate elementHistory();

    /**
     * @brief Part comparison template
     *
     * Compares statistics across multiple parts.
     * Parameters: parts (string_list), quantity (string)
     */
    static QueryTemplate partComparison();

    /**
     * @brief Displacement envelope template
     *
     * Computes maximum displacement envelope.
     * Parameters: parts (string_list), direction (string)
     */
    static QueryTemplate displacementEnvelope();

    /**
     * @brief Energy balance template
     *
     * Extracts energy quantities for balance checking.
     * Parameters: parts (string_list)
     */
    static QueryTemplate energyBalance();

    /**
     * @brief Contact force history template
     *
     * Tracks contact forces between parts.
     * Parameters: contact_ids (int_list)
     */
    static QueryTemplate contactForceHistory();

    /**
     * @brief Failure analysis template
     *
     * Identifies failed elements and failure progression.
     * Parameters: parts (string_list), failure_criterion (string)
     */
    static QueryTemplate failureAnalysis();

private:
    struct Impl;
    std::unique_ptr<Impl> pImpl;
};

} // namespace query
} // namespace kood3plot
