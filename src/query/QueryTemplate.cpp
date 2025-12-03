/**
 * @file QueryTemplate.cpp
 * @brief Implementation of QueryTemplate class
 * @author KooD3plot V3 Development Team
 * @date 2025-11-22
 * @version 3.0.0
 */

#include "kood3plot/query/QueryTemplate.h"
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <algorithm>

namespace kood3plot {
namespace query {

// ============================================================
// PIMPL Implementation Struct
// ============================================================

struct QueryTemplate::Impl {
    std::string name;
    std::string description;
    std::string category;

    // Parameter definitions
    std::vector<TemplateParameter> param_defs;

    // Current parameter values
    std::map<std::string, ParameterValue> param_values;

    // Query configuration (stored as optional)
    std::optional<PartSelector> part_selector;
    std::optional<QuantitySelector> quantity_selector;
    std::optional<TimeSelector> time_selector;
    std::optional<ValueFilter> value_filter;
    std::optional<OutputSpec> output_spec;

    // Helper to get string from variant
    std::string getStringParam(const std::string& name, const std::string& default_val = "") const {
        auto it = param_values.find(name);
        if (it == param_values.end()) {
            // Check default from param_defs
            for (const auto& def : param_defs) {
                if (def.name == name && std::holds_alternative<std::string>(def.default_value)) {
                    return std::get<std::string>(def.default_value);
                }
            }
            return default_val;
        }
        if (std::holds_alternative<std::string>(it->second)) {
            return std::get<std::string>(it->second);
        }
        return default_val;
    }

    double getDoubleParam(const std::string& name, double default_val = 0.0) const {
        auto it = param_values.find(name);
        if (it == param_values.end()) {
            for (const auto& def : param_defs) {
                if (def.name == name && std::holds_alternative<double>(def.default_value)) {
                    return std::get<double>(def.default_value);
                }
            }
            return default_val;
        }
        if (std::holds_alternative<double>(it->second)) {
            return std::get<double>(it->second);
        }
        if (std::holds_alternative<int32_t>(it->second)) {
            return static_cast<double>(std::get<int32_t>(it->second));
        }
        return default_val;
    }

    int32_t getIntParam(const std::string& name, int32_t default_val = 0) const {
        auto it = param_values.find(name);
        if (it == param_values.end()) {
            for (const auto& def : param_defs) {
                if (def.name == name && std::holds_alternative<int32_t>(def.default_value)) {
                    return std::get<int32_t>(def.default_value);
                }
            }
            return default_val;
        }
        if (std::holds_alternative<int32_t>(it->second)) {
            return std::get<int32_t>(it->second);
        }
        return default_val;
    }

    bool getBoolParam(const std::string& name, bool default_val = false) const {
        auto it = param_values.find(name);
        if (it == param_values.end()) {
            for (const auto& def : param_defs) {
                if (def.name == name && std::holds_alternative<bool>(def.default_value)) {
                    return std::get<bool>(def.default_value);
                }
            }
            return default_val;
        }
        if (std::holds_alternative<bool>(it->second)) {
            return std::get<bool>(it->second);
        }
        return default_val;
    }

    std::vector<std::string> getStringListParam(const std::string& name) const {
        auto it = param_values.find(name);
        if (it == param_values.end()) {
            for (const auto& def : param_defs) {
                if (def.name == name && std::holds_alternative<std::vector<std::string>>(def.default_value)) {
                    return std::get<std::vector<std::string>>(def.default_value);
                }
            }
            return {};
        }
        if (std::holds_alternative<std::vector<std::string>>(it->second)) {
            return std::get<std::vector<std::string>>(it->second);
        }
        return {};
    }

    std::vector<int32_t> getIntListParam(const std::string& name) const {
        auto it = param_values.find(name);
        if (it == param_values.end()) {
            for (const auto& def : param_defs) {
                if (def.name == name && std::holds_alternative<std::vector<int32_t>>(def.default_value)) {
                    return std::get<std::vector<int32_t>>(def.default_value);
                }
            }
            return {};
        }
        if (std::holds_alternative<std::vector<int32_t>>(it->second)) {
            return std::get<std::vector<int32_t>>(it->second);
        }
        return {};
    }
};

// ============================================================
// Constructors and Destructor
// ============================================================

QueryTemplate::QueryTemplate()
    : pImpl(std::make_unique<Impl>())
{
}

QueryTemplate::QueryTemplate(const std::string& name, const std::string& description)
    : pImpl(std::make_unique<Impl>())
{
    pImpl->name = name;
    pImpl->description = description;
}

QueryTemplate::QueryTemplate(const QueryTemplate& other)
    : pImpl(std::make_unique<Impl>(*other.pImpl))
{
}

QueryTemplate::QueryTemplate(QueryTemplate&& other) noexcept = default;

QueryTemplate& QueryTemplate::operator=(const QueryTemplate& other) {
    if (this != &other) {
        pImpl = std::make_unique<Impl>(*other.pImpl);
    }
    return *this;
}

QueryTemplate& QueryTemplate::operator=(QueryTemplate&& other) noexcept = default;

QueryTemplate::~QueryTemplate() = default;

// ============================================================
// Template Definition
// ============================================================

QueryTemplate& QueryTemplate::setName(const std::string& name) {
    pImpl->name = name;
    return *this;
}

QueryTemplate& QueryTemplate::setDescription(const std::string& description) {
    pImpl->description = description;
    return *this;
}

QueryTemplate& QueryTemplate::setCategory(const std::string& category) {
    pImpl->category = category;
    return *this;
}

QueryTemplate& QueryTemplate::addParameter(const TemplateParameter& param) {
    pImpl->param_defs.push_back(param);
    return *this;
}

QueryTemplate& QueryTemplate::addParameter(const std::string& name,
                                           const std::string& description,
                                           const ParameterValue& default_value,
                                           bool required) {
    TemplateParameter param;
    param.name = name;
    param.description = description;
    param.default_value = default_value;
    param.required = required;

    // Determine type from default value
    if (std::holds_alternative<std::string>(default_value)) {
        param.type = "string";
    } else if (std::holds_alternative<double>(default_value)) {
        param.type = "number";
    } else if (std::holds_alternative<int32_t>(default_value)) {
        param.type = "integer";
    } else if (std::holds_alternative<bool>(default_value)) {
        param.type = "bool";
    } else if (std::holds_alternative<std::vector<std::string>>(default_value)) {
        param.type = "string_list";
    } else if (std::holds_alternative<std::vector<int32_t>>(default_value)) {
        param.type = "int_list";
    } else if (std::holds_alternative<std::vector<double>>(default_value)) {
        param.type = "double_list";
    }

    pImpl->param_defs.push_back(param);
    return *this;
}

// ============================================================
// Query Configuration
// ============================================================

QueryTemplate& QueryTemplate::setParts(const PartSelector& selector) {
    pImpl->part_selector = selector;
    return *this;
}

QueryTemplate& QueryTemplate::setQuantities(const QuantitySelector& selector) {
    pImpl->quantity_selector = selector;
    return *this;
}

QueryTemplate& QueryTemplate::setTime(const TimeSelector& selector) {
    pImpl->time_selector = selector;
    return *this;
}

QueryTemplate& QueryTemplate::setFilter(const ValueFilter& filter) {
    pImpl->value_filter = filter;
    return *this;
}

QueryTemplate& QueryTemplate::setOutput(const OutputSpec& spec) {
    pImpl->output_spec = spec;
    return *this;
}

// ============================================================
// Parameter Values
// ============================================================

QueryTemplate& QueryTemplate::setParameter(const std::string& name, const ParameterValue& value) {
    pImpl->param_values[name] = value;
    return *this;
}

QueryTemplate& QueryTemplate::setParameter(const std::string& name, const std::string& value) {
    pImpl->param_values[name] = value;
    return *this;
}

QueryTemplate& QueryTemplate::setParameter(const std::string& name, double value) {
    pImpl->param_values[name] = value;
    return *this;
}

QueryTemplate& QueryTemplate::setParameter(const std::string& name, int32_t value) {
    pImpl->param_values[name] = value;
    return *this;
}

QueryTemplate& QueryTemplate::setParameter(const std::string& name, bool value) {
    pImpl->param_values[name] = value;
    return *this;
}

QueryTemplate& QueryTemplate::setParameter(const std::string& name, const std::vector<std::string>& value) {
    pImpl->param_values[name] = value;
    return *this;
}

QueryTemplate& QueryTemplate::setParameter(const std::string& name, const std::vector<int32_t>& value) {
    pImpl->param_values[name] = value;
    return *this;
}

ParameterValue QueryTemplate::getParameter(const std::string& name) const {
    auto it = pImpl->param_values.find(name);
    if (it != pImpl->param_values.end()) {
        return it->second;
    }

    // Return default value from param_defs
    for (const auto& def : pImpl->param_defs) {
        if (def.name == name) {
            return def.default_value;
        }
    }

    throw std::runtime_error("Parameter not found: " + name);
}

bool QueryTemplate::hasParameter(const std::string& name) const {
    return pImpl->param_values.find(name) != pImpl->param_values.end();
}

// ============================================================
// Query Creation
// ============================================================

D3plotQuery QueryTemplate::createQuery(const D3plotReader& reader) const {
    D3plotQuery query(reader);

    // Apply part selector
    if (pImpl->part_selector.has_value()) {
        query.selectParts(pImpl->part_selector.value());
    } else {
        // Check for parts parameter
        auto parts = pImpl->getStringListParam("parts");
        if (!parts.empty()) {
            query.selectParts(parts);
        } else {
            auto part_ids = pImpl->getIntListParam("part_ids");
            if (!part_ids.empty()) {
                query.selectParts(part_ids);
            } else {
                query.selectAllParts();
            }
        }
    }

    // Apply quantity selector
    if (pImpl->quantity_selector.has_value()) {
        query.selectQuantities(pImpl->quantity_selector.value());
    } else {
        // Check for stress_type parameter
        std::string stress_type = pImpl->getStringParam("stress_type", "");
        if (!stress_type.empty()) {
            if (stress_type == "von_mises") {
                query.selectQuantities(QuantitySelector::vonMises());
            } else if (stress_type == "all") {
                query.selectQuantities(QuantitySelector::allStress());
            } else {
                query.selectQuantities(QuantitySelector::vonMises());
            }
        }

        std::string strain_type = pImpl->getStringParam("strain_type", "");
        if (!strain_type.empty()) {
            if (strain_type == "effective" || strain_type == "plastic") {
                query.selectQuantities(QuantitySelector::effectiveStrain());
            } else if (strain_type == "all") {
                query.selectQuantities(QuantitySelector::allStrain());
            } else {
                query.selectQuantities(QuantitySelector::effectiveStrain());
            }
        }

        // Check for quantities parameter - use common crash as default
        auto quantities = pImpl->getStringListParam("quantities");
        if (!quantities.empty()) {
            // For now, use common crash quantities
            // TODO: Add quantity selection by name
            query.selectQuantities(QuantitySelector::commonCrash());
        }
    }

    // Apply time selector
    if (pImpl->time_selector.has_value()) {
        query.selectTime(pImpl->time_selector.value());
    } else {
        // Check for time parameters
        std::string time_mode = pImpl->getStringParam("time_mode", "all");
        if (time_mode == "last" || time_mode == "final") {
            query.selectTime(TimeSelector::lastState());
        } else if (time_mode == "first") {
            query.selectTime(TimeSelector::firstState());
        } else {
            query.selectTime(TimeSelector::allStates());
        }
    }

    // Apply value filter
    if (pImpl->value_filter.has_value()) {
        query.whereValue(pImpl->value_filter.value());
    } else {
        // Check for threshold parameters
        double stress_threshold = pImpl->getDoubleParam("stress_threshold", 0.0);
        if (stress_threshold > 0.0) {
            query.whereGreaterThan(stress_threshold);
        }
    }

    // Apply output spec
    if (pImpl->output_spec.has_value()) {
        query.output(pImpl->output_spec.value());
    }

    return query;
}

bool QueryTemplate::validate() const {
    return getValidationErrors().empty();
}

std::vector<std::string> QueryTemplate::getValidationErrors() const {
    std::vector<std::string> errors;

    // Check required parameters
    for (const auto& def : pImpl->param_defs) {
        if (def.required) {
            auto it = pImpl->param_values.find(def.name);
            if (it == pImpl->param_values.end()) {
                errors.push_back("Required parameter missing: " + def.name);
            }
        }
    }

    if (pImpl->name.empty()) {
        errors.push_back("Template name is empty");
    }

    return errors;
}

// ============================================================
// Introspection
// ============================================================

std::string QueryTemplate::getName() const {
    return pImpl->name;
}

std::string QueryTemplate::getDescription() const {
    return pImpl->description;
}

std::string QueryTemplate::getCategory() const {
    return pImpl->category;
}

std::vector<TemplateParameter> QueryTemplate::getParameters() const {
    return pImpl->param_defs;
}

std::string QueryTemplate::getSummary() const {
    std::ostringstream oss;
    oss << "Template: " << pImpl->name << "\n";
    oss << "Category: " << (pImpl->category.empty() ? "general" : pImpl->category) << "\n";
    oss << "Description: " << pImpl->description << "\n";
    oss << "Parameters:\n";

    for (const auto& param : pImpl->param_defs) {
        oss << "  - " << param.name << " (" << param.type << ")";
        if (param.required) {
            oss << " [required]";
        }
        oss << ": " << param.description << "\n";
    }

    return oss.str();
}

// ============================================================
// Serialization
// ============================================================

void QueryTemplate::saveToYAML(const std::string& filename) const {
    std::ofstream file(filename);
    if (!file.is_open()) {
        throw std::runtime_error("Failed to open file for writing: " + filename);
    }

    file << "# KooD3plot Query Template\n";
    file << "name: " << pImpl->name << "\n";
    file << "description: " << pImpl->description << "\n";
    file << "category: " << pImpl->category << "\n";
    file << "\nparameters:\n";

    for (const auto& param : pImpl->param_defs) {
        file << "  - name: " << param.name << "\n";
        file << "    description: " << param.description << "\n";
        file << "    type: " << param.type << "\n";
        file << "    required: " << (param.required ? "true" : "false") << "\n";
    }

    file.close();
}

void QueryTemplate::saveToJSON(const std::string& filename) const {
    std::ofstream file(filename);
    if (!file.is_open()) {
        throw std::runtime_error("Failed to open file for writing: " + filename);
    }

    file << "{\n";
    file << "  \"name\": \"" << pImpl->name << "\",\n";
    file << "  \"description\": \"" << pImpl->description << "\",\n";
    file << "  \"category\": \"" << pImpl->category << "\",\n";
    file << "  \"parameters\": [\n";

    for (size_t i = 0; i < pImpl->param_defs.size(); ++i) {
        const auto& param = pImpl->param_defs[i];
        file << "    {\n";
        file << "      \"name\": \"" << param.name << "\",\n";
        file << "      \"description\": \"" << param.description << "\",\n";
        file << "      \"type\": \"" << param.type << "\",\n";
        file << "      \"required\": " << (param.required ? "true" : "false") << "\n";
        file << "    }";
        if (i < pImpl->param_defs.size() - 1) {
            file << ",";
        }
        file << "\n";
    }

    file << "  ]\n";
    file << "}\n";
    file.close();
}

QueryTemplate QueryTemplate::loadFromYAML(const std::string& filename) {
    // Simple YAML parsing (for production, use a proper YAML library)
    std::ifstream file(filename);
    if (!file.is_open()) {
        throw std::runtime_error("Failed to open file: " + filename);
    }

    QueryTemplate tmpl;
    std::string line;

    while (std::getline(file, line)) {
        // Skip comments and empty lines
        if (line.empty() || line[0] == '#') continue;

        // Simple key-value parsing
        auto pos = line.find(':');
        if (pos != std::string::npos) {
            std::string key = line.substr(0, pos);
            std::string value = line.substr(pos + 1);

            // Trim whitespace
            key.erase(0, key.find_first_not_of(" \t"));
            key.erase(key.find_last_not_of(" \t") + 1);
            value.erase(0, value.find_first_not_of(" \t"));
            value.erase(value.find_last_not_of(" \t") + 1);

            if (key == "name") {
                tmpl.setName(value);
            } else if (key == "description") {
                tmpl.setDescription(value);
            } else if (key == "category") {
                tmpl.setCategory(value);
            }
        }
    }

    return tmpl;
}

QueryTemplate QueryTemplate::loadFromJSON(const std::string& filename) {
    // Simple JSON parsing (for production, use a proper JSON library)
    std::ifstream file(filename);
    if (!file.is_open()) {
        throw std::runtime_error("Failed to open file: " + filename);
    }

    QueryTemplate tmpl;
    std::string content((std::istreambuf_iterator<char>(file)),
                        std::istreambuf_iterator<char>());

    // Extract name
    auto name_pos = content.find("\"name\"");
    if (name_pos != std::string::npos) {
        auto start = content.find('\"', name_pos + 7) + 1;
        auto end = content.find('\"', start);
        tmpl.setName(content.substr(start, end - start));
    }

    // Extract description
    auto desc_pos = content.find("\"description\"");
    if (desc_pos != std::string::npos) {
        auto start = content.find('\"', desc_pos + 14) + 1;
        auto end = content.find('\"', start);
        tmpl.setDescription(content.substr(start, end - start));
    }

    return tmpl;
}

// ============================================================
// Built-in Templates
// ============================================================

QueryTemplate QueryTemplate::maxStressHistory() {
    QueryTemplate tmpl("max_stress_history", "Track maximum stress over time for selected parts");
    tmpl.setCategory("stress");

    tmpl.addParameter("parts", "Part names to analyze", std::vector<std::string>{}, false);
    tmpl.addParameter("part_ids", "Part IDs to analyze", std::vector<int32_t>{}, false);
    tmpl.addParameter("stress_type", "Type of stress (von_mises, principal, x, y, z)", std::string("von_mises"), false);

    tmpl.setQuantities(QuantitySelector::vonMises());
    tmpl.setTime(TimeSelector::allStates());
    tmpl.setOutput(OutputSpec::csv()
        .fields({"time", "part_id", "element_id", "von_mises"})
        .precision(6));

    return tmpl;
}

QueryTemplate QueryTemplate::maxStrainHistory() {
    QueryTemplate tmpl("max_strain_history", "Track maximum strain over time for selected parts");
    tmpl.setCategory("strain");

    tmpl.addParameter("parts", "Part names to analyze", std::vector<std::string>{}, false);
    tmpl.addParameter("strain_type", "Type of strain (effective, plastic, x, y, z)", std::string("effective"), false);

    tmpl.setQuantities(QuantitySelector::effectiveStrain());
    tmpl.setTime(TimeSelector::allStates());
    tmpl.setOutput(OutputSpec::csv()
        .fields({"time", "part_id", "element_id", "effective_strain"})
        .precision(6));

    return tmpl;
}

QueryTemplate QueryTemplate::finalStateAnalysis() {
    QueryTemplate tmpl("final_state", "Extract all quantities at the final timestep");
    tmpl.setCategory("general");

    tmpl.addParameter("parts", "Part names to analyze", std::vector<std::string>{}, false);
    tmpl.addParameter("quantities", "Quantities to extract", std::vector<std::string>{"von_mises", "effective_strain"}, false);

    tmpl.setQuantities(QuantitySelector::commonCrash());
    tmpl.setTime(TimeSelector::lastState());
    tmpl.setOutput(OutputSpec::csv().precision(6));

    return tmpl;
}

QueryTemplate QueryTemplate::criticalZones() {
    QueryTemplate tmpl("critical_zones", "Identify elements exceeding stress/strain thresholds");
    tmpl.setCategory("analysis");

    tmpl.addParameter("parts", "Part names to analyze", std::vector<std::string>{}, false);
    tmpl.addParameter("stress_threshold", "Stress threshold (MPa)", 500.0, false);
    tmpl.addParameter("strain_threshold", "Strain threshold", 0.2, false);

    tmpl.setQuantities(QuantitySelector::commonCrash());
    tmpl.setTime(TimeSelector::lastState());
    tmpl.setFilter(ValueFilter().greaterThan(500.0));
    tmpl.setOutput(OutputSpec::csv()
        .fields({"part_id", "element_id", "von_mises", "effective_strain"})
        .precision(6));

    return tmpl;
}

QueryTemplate QueryTemplate::elementHistory() {
    QueryTemplate tmpl("element_history", "Extract complete time history for specific elements");
    tmpl.setCategory("history");

    tmpl.addParameter("element_ids", "Element IDs to track", std::vector<int32_t>{}, true);
    tmpl.addParameter("quantities", "Quantities to extract", std::vector<std::string>{"von_mises"}, false);

    tmpl.setTime(TimeSelector::allStates());
    tmpl.setOutput(OutputSpec::csv()
        .fields({"time", "element_id", "von_mises"})
        .precision(8));

    return tmpl;
}

QueryTemplate QueryTemplate::partComparison() {
    QueryTemplate tmpl("part_comparison", "Compare statistics across multiple parts");
    tmpl.setCategory("comparison");

    tmpl.addParameter("parts", "Part names to compare", std::vector<std::string>{}, true);
    tmpl.addParameter("quantity", "Quantity to compare", std::string("von_mises"), false);

    tmpl.setQuantities(QuantitySelector::vonMises());
    tmpl.setTime(TimeSelector::allStates());
    tmpl.setOutput(OutputSpec::csv().precision(6));

    return tmpl;
}

QueryTemplate QueryTemplate::displacementEnvelope() {
    QueryTemplate tmpl("displacement_envelope", "Compute maximum displacement envelope");
    tmpl.setCategory("displacement");

    tmpl.addParameter("parts", "Part names to analyze", std::vector<std::string>{}, false);
    tmpl.addParameter("direction", "Direction (x, y, z, magnitude)", std::string("magnitude"), false);

    tmpl.setQuantities(QuantitySelector::displacement());
    tmpl.setTime(TimeSelector::allStates());
    tmpl.setOutput(OutputSpec::csv()
        .fields({"time", "part_id", "node_id", "disp_x", "disp_y", "disp_z", "disp_mag"})
        .precision(6));

    return tmpl;
}

QueryTemplate QueryTemplate::energyBalance() {
    QueryTemplate tmpl("energy_balance", "Extract energy quantities for balance checking");
    tmpl.setCategory("energy");

    tmpl.addParameter("parts", "Part names to analyze", std::vector<std::string>{}, false);

    tmpl.setTime(TimeSelector::allStates());
    tmpl.setOutput(OutputSpec::csv()
        .fields({"time", "kinetic_energy", "internal_energy", "total_energy"})
        .precision(8));

    return tmpl;
}

QueryTemplate QueryTemplate::contactForceHistory() {
    QueryTemplate tmpl("contact_force_history", "Track contact forces between parts");
    tmpl.setCategory("contact");

    tmpl.addParameter("contact_ids", "Contact interface IDs", std::vector<int32_t>{}, false);

    tmpl.setTime(TimeSelector::allStates());
    tmpl.setOutput(OutputSpec::csv()
        .fields({"time", "contact_id", "force_x", "force_y", "force_z", "force_mag"})
        .precision(6));

    return tmpl;
}

QueryTemplate QueryTemplate::failureAnalysis() {
    QueryTemplate tmpl("failure_analysis", "Identify failed elements and failure progression");
    tmpl.setCategory("failure");

    tmpl.addParameter("parts", "Part names to analyze", std::vector<std::string>{}, false);
    tmpl.addParameter("failure_criterion", "Failure criterion (strain, damage)", std::string("strain"), false);
    tmpl.addParameter("failure_threshold", "Failure threshold value", 0.3, false);

    tmpl.setQuantities(QuantitySelector::effectiveStrain());
    tmpl.setTime(TimeSelector::allStates());
    tmpl.setFilter(ValueFilter().greaterThan(0.3));
    tmpl.setOutput(OutputSpec::csv()
        .fields({"time", "part_id", "element_id", "effective_strain"})
        .precision(6));

    return tmpl;
}

} // namespace query
} // namespace kood3plot
