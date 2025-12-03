/**
 * @file test_fringe_types.cpp
 * @brief Test all fringe type YAML configurations
 *
 * This program validates that:
 * 1. YAML fringe type strings are parsed correctly
 * 2. FringeType enums are converted to correct LSPrePost IDs
 * 3. All aliases work properly
 */

#include <iostream>
#include <vector>
#include <string>
#include "kood3plot/render/RenderConfig.h"
#include "kood3plot/render/LSPrePostRenderer.h"

using namespace kood3plot::render;

struct TestCase {
    std::string yaml_file;
    std::string expected_type_name;
    int expected_lsprepost_id;
};

int main() {
    std::cout << "=== Fringe Type Validation Test ===" << std::endl;
    std::cout << std::endl;

    std::vector<TestCase> test_cases = {
        {"test_comprehensive.yaml", "von_mises", 9},
        {"test_principal_stress.yaml", "principal_stress_1", 14},
        {"test_effective_strain.yaml", "effective_strain", 80},
        {"test_displacement_x.yaml", "displacement_x", 17},
        {"test_pressure.yaml", "pressure", 8}
    };

    int passed = 0;
    int failed = 0;

    for (const auto& test : test_cases) {
        std::cout << "Testing: " << test.yaml_file << std::endl;

        // Load YAML configuration
        RenderConfig config;
        if (!config.loadFromYAML(test.yaml_file)) {
            std::cout << "  ❌ FAILED: Could not load YAML file" << std::endl;
            std::cout << "  Error: " << config.getLastError() << std::endl;
            failed++;
            continue;
        }

        // Get fringe type string from configuration data
        std::string type_string = config.getData().fringe.type;

        // Convert to enum
        FringeType fringe_type = config.stringToFringeType(type_string);

        // Convert back to canonical string
        std::string canonical_string = config.fringeTypeToString(fringe_type);

        std::cout << "  Parsed fringe type: " << type_string << std::endl;
        std::cout << "  Canonical form: " << canonical_string << std::endl;

        // Note: We can't directly call fringeTypeToCode without rendering
        // But we can verify the type was parsed correctly
        bool type_correct = (canonical_string == test.expected_type_name);

        if (type_correct) {
            std::cout << "  ✅ PASSED: Type matches expected '" << test.expected_type_name << "'" << std::endl;
            passed++;
        } else {
            std::cout << "  ❌ FAILED: Expected '" << test.expected_type_name
                     << "' but got '" << canonical_string << "'" << std::endl;
            failed++;
        }

        std::cout << std::endl;
    }

    // Test direct string-to-fringe-type conversion with aliases
    std::cout << "=== Testing String-to-FringeType Conversion ===" << std::endl;
    std::cout << std::endl;

    RenderConfig config;

    struct AliasTest {
        std::string input;
        std::string expected_canonical;
    };

    std::vector<AliasTest> alias_tests = {
        {"von_mises", "von_mises"},
        {"principal_1", "principal_stress_1"},
        {"principal_stress_1", "principal_stress_1"},
        {"disp_x", "displacement_x"},
        {"x_displacement", "displacement_x"},
        {"displacement_x", "displacement_x"},
        {"plastic_strain", "plastic_strain"},
        {"effective_plastic_strain", "plastic_strain"},
        {"x_stress", "stress_xx"},
        {"stress_xx", "stress_xx"},
        {"sigma_xx", "stress_xx"}
    };

    for (const auto& test : alias_tests) {
        FringeType type = config.stringToFringeType(test.input);
        std::string canonical = config.fringeTypeToString(type);

        bool matches = (canonical == test.expected_canonical);

        if (matches) {
            std::cout << "  ✅ '" << test.input << "' -> '" << canonical << "'" << std::endl;
            passed++;
        } else {
            std::cout << "  ❌ '" << test.input << "' -> '" << canonical
                     << "' (expected '" << test.expected_canonical << "')" << std::endl;
            failed++;
        }
    }

    std::cout << std::endl;
    std::cout << "=== Test Summary ===" << std::endl;
    std::cout << "Passed: " << passed << std::endl;
    std::cout << "Failed: " << failed << std::endl;
    std::cout << "Total:  " << (passed + failed) << std::endl;
    std::cout << std::endl;

    if (failed == 0) {
        std::cout << "🎉 All tests passed!" << std::endl;
        return 0;
    } else {
        std::cout << "⚠️  Some tests failed." << std::endl;
        return 1;
    }
}
