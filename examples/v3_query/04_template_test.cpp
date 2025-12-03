/**
 * @file 04_template_test.cpp
 * @brief V3 Query System Phase 5 Template Test
 * @date 2025-11-22
 *
 * Tests Phase 5 features:
 * - QueryTemplate creation and configuration
 * - TemplateManager singleton
 * - Built-in templates (10 templates)
 * - Template parameters
 * - Template serialization
 */

#include <iostream>
#include <iomanip>
#include <fstream>
#include <sstream>

#include "kood3plot/query/QueryTemplate.h"
#include "kood3plot/query/TemplateManager.h"

using namespace kood3plot::query;

void testQueryTemplate() {
    std::cout << "===========================================\n";
    std::cout << "Test 1: QueryTemplate Basic Operations\n";
    std::cout << "===========================================\n\n";

    // Create a custom template
    QueryTemplate tmpl("my_custom_template", "A custom analysis template");
    tmpl.setCategory("custom");

    // Add parameters
    tmpl.addParameter("parts", "Part names to analyze", std::vector<std::string>{}, false);
    tmpl.addParameter("threshold", "Value threshold", 500.0, false);
    tmpl.addParameter("include_history", "Include time history", true, false);

    // Set parameter values
    tmpl.setParameter("parts", std::vector<std::string>{"Hood", "Fender"});
    tmpl.setParameter("threshold", 600.0);

    // Get template info
    std::cout << "Template name: " << tmpl.getName() << "\n";
    std::cout << "Category: " << tmpl.getCategory() << "\n";
    std::cout << "Description: " << tmpl.getDescription() << "\n\n";

    // Print parameters
    std::cout << "Parameters:\n";
    for (const auto& param : tmpl.getParameters()) {
        std::cout << "  - " << param.name << " (" << param.type << ")";
        if (param.required) std::cout << " [required]";
        std::cout << ": " << param.description << "\n";
    }

    // Validate
    if (tmpl.validate()) {
        std::cout << "\nTemplate is valid!\n\n";
    } else {
        std::cout << "\nValidation errors:\n";
        for (const auto& err : tmpl.getValidationErrors()) {
            std::cout << "  - " << err << "\n";
        }
    }
}

void testBuiltinTemplates() {
    std::cout << "===========================================\n";
    std::cout << "Test 2: Built-in Templates\n";
    std::cout << "===========================================\n\n";

    // Test each built-in template
    struct TemplateTest {
        std::string name;
        QueryTemplate (*factory)();
    };

    std::vector<TemplateTest> tests = {
        {"max_stress_history", QueryTemplate::maxStressHistory},
        {"max_strain_history", QueryTemplate::maxStrainHistory},
        {"final_state", QueryTemplate::finalStateAnalysis},
        {"critical_zones", QueryTemplate::criticalZones},
        {"element_history", QueryTemplate::elementHistory},
        {"part_comparison", QueryTemplate::partComparison},
        {"displacement_envelope", QueryTemplate::displacementEnvelope},
        {"energy_balance", QueryTemplate::energyBalance},
        {"contact_force_history", QueryTemplate::contactForceHistory},
        {"failure_analysis", QueryTemplate::failureAnalysis},
    };

    std::cout << "Built-in templates (" << tests.size() << "):\n\n";

    for (const auto& test : tests) {
        auto tmpl = test.factory();
        std::cout << "  " << tmpl.getName() << "\n";
        std::cout << "    Category: " << tmpl.getCategory() << "\n";
        std::cout << "    Description: " << tmpl.getDescription() << "\n";
        std::cout << "    Parameters: " << tmpl.getParameters().size() << "\n";
        std::cout << "\n";
    }
}

void testTemplateManager() {
    std::cout << "===========================================\n";
    std::cout << "Test 3: TemplateManager\n";
    std::cout << "===========================================\n\n";

    // Get singleton instance
    auto& manager = TemplateManager::instance();

    // List all templates
    auto templates = manager.listTemplates();
    std::cout << "Registered templates: " << templates.size() << "\n\n";

    for (const auto& name : templates) {
        std::cout << "  - " << name << "\n";
    }

    // Test categories
    std::cout << "\nCategories:\n";
    auto categories = manager.getCategories();
    for (const auto& cat : categories) {
        std::cout << "  [" << cat.name << "]: ";
        for (size_t i = 0; i < cat.templates.size(); ++i) {
            if (i > 0) std::cout << ", ";
            std::cout << cat.templates[i];
        }
        std::cout << "\n";
    }

    // Test search
    std::cout << "\nSearch for 'stress':\n";
    auto results = manager.searchTemplates("stress");
    for (const auto& name : results) {
        std::cout << "  - " << name << "\n";
    }

    // Test alias
    std::cout << "\nAliases:\n";
    auto aliases = manager.getAliases();
    for (const auto& [alias, target] : aliases) {
        std::cout << "  " << alias << " -> " << target << "\n";
    }

    // Get template by alias
    std::cout << "\nGet template by alias 'stress':\n";
    auto stress_tmpl = manager.getByAlias("stress");
    std::cout << "  Name: " << stress_tmpl.getName() << "\n";
    std::cout << "  Description: " << stress_tmpl.getDescription() << "\n";
}

void testTemplateSerialization() {
    std::cout << "\n===========================================\n";
    std::cout << "Test 4: Template Serialization\n";
    std::cout << "===========================================\n\n";

    // Create template
    QueryTemplate tmpl("serialization_test", "Template for serialization test");
    tmpl.setCategory("test");
    tmpl.addParameter("param1", "First parameter", std::string("default"), false);
    tmpl.addParameter("param2", "Second parameter", 100.0, true);

    // Save to YAML
    std::string yaml_file = "/tmp/v3_template_test.yaml";
    tmpl.saveToYAML(yaml_file);
    std::cout << "Saved to YAML: " << yaml_file << "\n";

    // Read and display YAML
    std::ifstream ifs_yaml(yaml_file);
    if (ifs_yaml.is_open()) {
        std::cout << "\nYAML content:\n";
        std::cout << "-------------\n";
        std::string line;
        while (std::getline(ifs_yaml, line)) {
            std::cout << line << "\n";
        }
        ifs_yaml.close();
    }

    // Save to JSON
    std::string json_file = "/tmp/v3_template_test.json";
    tmpl.saveToJSON(json_file);
    std::cout << "\nSaved to JSON: " << json_file << "\n";

    // Read and display JSON
    std::ifstream ifs_json(json_file);
    if (ifs_json.is_open()) {
        std::cout << "\nJSON content:\n";
        std::cout << "-------------\n";
        std::stringstream buffer;
        buffer << ifs_json.rdbuf();
        std::cout << buffer.str() << "\n";
        ifs_json.close();
    }
}

void testPrintTemplateList() {
    std::cout << "\n===========================================\n";
    std::cout << "Test 5: Print Template List\n";
    std::cout << "===========================================\n\n";

    auto& manager = TemplateManager::instance();
    manager.printTemplateList(std::cout, false);  // Brief list
}

int main() {
    std::cout << "===========================================\n";
    std::cout << "V3 Query System - Phase 5 Template Test\n";
    std::cout << "===========================================\n\n";

    testQueryTemplate();
    testBuiltinTemplates();
    testTemplateManager();
    testTemplateSerialization();
    testPrintTemplateList();

    std::cout << "\n===========================================\n";
    std::cout << "All Phase 5 tests completed!\n";
    std::cout << "===========================================\n";

    return 0;
}
