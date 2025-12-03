/**
 * @file 05_comprehensive_example.cpp
 * @brief V3 Query System Comprehensive Example
 * @date 2025-11-22
 *
 * This example demonstrates ALL V3 Query System features:
 *
 * Phase 1-2: Core Query System
 *   - D3plotQuery builder pattern
 *   - PartSelector (by ID, name, pattern)
 *   - QuantitySelector (stress, strain, displacement)
 *   - TimeSelector (first, last, range, all)
 *   - QueryResult and statistics
 *
 * Phase 3: Advanced Filtering & Aggregation
 *   - ValueFilter (threshold, range, percentile)
 *   - Statistical filtering (IQR, StdDev, TopN/BottomN)
 *   - Advanced aggregation (SUM, COUNT, RANGE, MEDIAN)
 *
 * Phase 4: Output Formats
 *   - CSV output with customization
 *   - JSON output with statistics and metadata
 *   - OutputSpec configuration
 *
 * Phase 5: Template System
 *   - QueryTemplate creation and usage
 *   - TemplateManager for template registry
 *   - Built-in templates
 *
 * Usage:
 *   ./v3_comprehensive_example [d3plot_path]
 */

#include <iostream>
#include <iomanip>
#include <fstream>
#include <sstream>

// Core V3 Query System headers
#include "kood3plot/D3plotReader.hpp"
#include "kood3plot/query/D3plotQuery.h"
#include "kood3plot/query/PartSelector.h"
#include "kood3plot/query/QuantitySelector.h"
#include "kood3plot/query/TimeSelector.h"
#include "kood3plot/query/ValueFilter.h"
#include "kood3plot/query/OutputSpec.h"
#include "kood3plot/query/QueryResult.h"
#include "kood3plot/query/QueryTypes.h"

// Phase 5: Template System
#include "kood3plot/query/QueryTemplate.h"
#include "kood3plot/query/TemplateManager.h"

using namespace kood3plot;
using namespace kood3plot::query;

void printSeparator(const std::string& title) {
    std::cout << "\n";
    std::cout << "╔════════════════════════════════════════════════════════════╗\n";
    std::cout << "║ " << std::left << std::setw(58) << title << " ║\n";
    std::cout << "╚════════════════════════════════════════════════════════════╝\n\n";
}

void printSubSection(const std::string& title) {
    std::cout << "\n--- " << title << " ---\n\n";
}

// ============================================================
// Example 1: Basic Query Builder Pattern
// ============================================================
void example1_BasicQuery(const D3plotReader& reader) {
    printSeparator("Example 1: Basic Query Builder Pattern");

    std::cout << "The V3 Query System uses a fluent builder pattern:\n\n";

    std::cout << R"(
    D3plotQuery(reader)
        .selectAllParts()                              // Select parts
        .selectQuantities(QuantitySelector::vonMises()) // Select quantities
        .selectTime(TimeSelector::lastState())          // Select time
        .writeCSV("output.csv");                       // Output
    )" << "\n";

    // Actually execute
    D3plotQuery query(reader);
    query.selectAllParts()
         .selectQuantities(QuantitySelector::vonMises())
         .selectTime(TimeSelector::lastState());

    std::cout << "Query description: " << query.getDescription() << "\n";
    std::cout << "Estimated size: " << query.estimateSize() << " data points\n";
}

// ============================================================
// Example 2: Part Selection Methods
// ============================================================
void example2_PartSelection() {
    printSeparator("Example 2: Part Selection Methods");

    std::cout << "PartSelector provides multiple ways to select parts:\n\n";

    // By ID
    PartSelector by_id = PartSelector().byId({1, 2, 3, 100});
    std::cout << "By ID: " << by_id.getDescription() << "\n";

    // By name
    PartSelector by_name = PartSelector().byName({"Hood", "Fender", "Door_LF"});
    std::cout << "By name: " << by_name.getDescription() << "\n";

    // By pattern (glob)
    PartSelector by_pattern = PartSelector().byPattern("Door_*");
    std::cout << "By pattern: " << by_pattern.getDescription() << "\n";

    // By material
    PartSelector by_material = PartSelector().byMaterial({10, 11, 12});
    std::cout << "By material: " << by_material.getDescription() << "\n";

    // Combination with logical operators
    PartSelector combined = PartSelector().byPattern("Body_*") || PartSelector().byMaterial({10});
    std::cout << "Combined (OR): " << combined.getDescription() << "\n";

    // Static convenience methods
    std::cout << "\nStatic methods:\n";
    std::cout << "  PartSelector::all() - Select all parts\n";
    std::cout << "  PartSelector::none() - Select no parts (for building)\n";
}

// ============================================================
// Example 3: Quantity Selection
// ============================================================
void example3_QuantitySelection() {
    printSeparator("Example 3: Quantity Selection");

    std::cout << "QuantitySelector provides preset and custom quantity selections:\n\n";

    std::cout << "Preset selections:\n";
    std::cout << "  vonMises()      - Von Mises stress\n";
    std::cout << "  effectiveStrain() - Effective plastic strain\n";
    std::cout << "  displacement()  - Displacement (x, y, z, magnitude)\n";
    std::cout << "  allStress()     - All stress components\n";
    std::cout << "  allStrain()     - All strain components\n";
    std::cout << "  commonCrash()   - Common crash analysis quantities\n\n";

    // Show descriptions
    std::cout << "Examples:\n";
    std::cout << "  " << QuantitySelector::vonMises().getDescription() << "\n";
    std::cout << "  " << QuantitySelector::commonCrash().getDescription() << "\n";
}

// ============================================================
// Example 4: Time Selection
// ============================================================
void example4_TimeSelection() {
    printSeparator("Example 4: Time Selection");

    std::cout << "TimeSelector provides flexible time/state selection:\n\n";

    std::cout << "Methods:\n";
    std::cout << "  firstState()    - First timestep only\n";
    std::cout << "  lastState()     - Last timestep only\n";
    std::cout << "  allStates()     - All timesteps\n";
    std::cout << "  stateRange(0, 10) - States 0 to 10\n";
    std::cout << "  stateRange(0, -1, 5) - Every 5th state\n";
    std::cout << "  timeRange(0.0, 0.05) - Time 0 to 0.05\n";
    std::cout << "  specificStates({0, 5, 10, -1}) - Specific states\n\n";

    // Show descriptions
    std::cout << "Examples:\n";
    std::cout << "  " << TimeSelector::lastState().getDescription() << "\n";
    std::cout << "  " << TimeSelector::everyNth(10).getDescription() << "\n";
}

// ============================================================
// Example 5: Value Filtering (Phase 3)
// ============================================================
void example5_ValueFiltering() {
    printSeparator("Example 5: Value Filtering (Phase 3)");

    std::cout << "ValueFilter provides powerful filtering capabilities:\n\n";

    printSubSection("Basic Filters");
    std::cout << "  greaterThan(500)    - Values > 500\n";
    std::cout << "  lessThan(100)       - Values < 100\n";
    std::cout << "  inRange(100, 500)   - Values between 100 and 500\n";
    std::cout << "  equalTo(0.0)        - Values equal to 0\n\n";

    printSubSection("Statistical Filters");
    std::cout << "  inTopPercentile(10)     - Top 10% of values\n";
    std::cout << "  inBottomPercentile(5)   - Bottom 5% of values\n";
    std::cout << "  betweenPercentiles(25, 75) - Middle 50%\n";
    std::cout << "  withinStdDev(2.0)       - Within 2 standard deviations\n";
    std::cout << "  outsideStdDev(3.0)      - Outliers (> 3 sigma)\n";
    std::cout << "  removeOutliers(1.5)     - Remove IQR outliers\n\n";

    printSubSection("TopN/BottomN Filters");
    std::cout << "  ValueFilter::topN(10)     - Top 10 values\n";
    std::cout << "  ValueFilter::bottomN(5)   - Bottom 5 values\n\n";

    printSubSection("Logical Combinations");
    std::cout << "  filter1 && filter2  - AND combination\n";
    std::cout << "  filter1 || filter2  - OR combination\n";
    std::cout << "  !filter1            - NOT (invert)\n\n";

    // Demo
    std::cout << "Demo with synthetic data [1-100]:\n";
    std::vector<double> data;
    for (int i = 1; i <= 100; ++i) data.push_back(i);

    auto top10 = ValueFilter::topN(10).apply(data);
    std::cout << "  Top 10: " << top10.size() << " values (";
    for (size_t i = 0; i < std::min(size_t(5), top10.size()); ++i) {
        if (i > 0) std::cout << ", ";
        std::cout << top10[i];
    }
    std::cout << "...)\n";

    auto percentile = ValueFilter().inTopPercentile(20).apply(data);
    std::cout << "  Top 20%: " << percentile.size() << " values\n";
}

// ============================================================
// Example 6: Advanced Aggregation (Phase 3)
// ============================================================
void example6_Aggregation() {
    printSeparator("Example 6: Advanced Aggregation (Phase 3)");

    std::cout << "QueryResult provides aggregation functions:\n\n";

    // Create sample result
    QueryResult result;
    for (int i = 1; i <= 10; ++i) {
        ResultDataPoint pt;
        pt.element_id = i;
        pt.part_id = 1;
        pt.state_index = 0;
        pt.time = 0.001 * i;
        pt.values["stress"] = i * 10.0;  // 10, 20, ..., 100
        result.addDataPoint(pt);
    }

    std::cout << "Sample data: stress = [10, 20, 30, ..., 100]\n\n";

    std::cout << "Aggregation methods:\n";
    std::cout << "  sum(\"stress\"):   " << result.sum("stress") << "\n";
    std::cout << "  count(\"stress\"): " << result.count("stress") << "\n";
    std::cout << "  range(\"stress\"): " << result.range("stress") << "\n";

    std::cout << "\nUsing aggregate() with AggregationType:\n";
    std::cout << "  MAX:    " << result.aggregate("stress", AggregationType::MAX) << "\n";
    std::cout << "  MIN:    " << result.aggregate("stress", AggregationType::MIN) << "\n";
    std::cout << "  MEAN:   " << result.aggregate("stress", AggregationType::MEAN) << "\n";
    std::cout << "  MEDIAN: " << result.aggregate("stress", AggregationType::MEDIAN) << "\n";

    std::cout << "\nFull statistics:\n";
    auto stats = result.getStatistics("stress");
    std::cout << "  Min: " << stats.min_value << " (elem " << stats.min_element_id << ")\n";
    std::cout << "  Max: " << stats.max_value << " (elem " << stats.max_element_id << ")\n";
    std::cout << "  Mean: " << stats.mean_value << "\n";
    std::cout << "  StdDev: " << stats.std_dev << "\n";
    std::cout << "  Sum: " << stats.sum << "\n";
    std::cout << "  Range: " << stats.range << "\n";
    std::cout << "  Median: " << stats.median << "\n";
}

// ============================================================
// Example 7: Output Formats (Phase 4)
// ============================================================
void example7_OutputFormats() {
    printSeparator("Example 7: Output Formats (Phase 4)");

    std::cout << "OutputSpec configures output format and options:\n\n";

    printSubSection("CSV Output");
    std::cout << R"(
    OutputSpec::csv()
        .fields({"part_id", "element_id", "time", "von_mises"})
        .precision(6)
        .delimiter(',')
        .includeHeader(true)
    )" << "\n";

    printSubSection("JSON Output");
    std::cout << R"(
    OutputSpec::json()
        .fields({"part_id", "element_id", "time", "von_mises"})
        .precision(4)
        .includeMetadata(true)
        .addMetadata("analysis_type", "crash")
        .includeStatisticsSection(true)
    )" << "\n";

    // Demo JSON output
    QueryResult result;
    for (int i = 1; i <= 3; ++i) {
        ResultDataPoint pt;
        pt.element_id = 100 + i;
        pt.part_id = 1;
        pt.state_index = 0;
        pt.time = 0.001 * i;
        pt.values["von_mises"] = 100.0 + i * 10.0;
        result.addDataPoint(pt);
    }

    std::cout << "\nSample JSON output structure:\n";
    std::cout << R"({
  "metadata": { "data_points": "3", "generated_at": "..." },
  "statistics": {
    "von_mises": { "min": 110, "max": 130, "mean": 120, ... }
  },
  "data": [
    {"element_id": 101, "part_id": 1, "von_mises": 110.0},
    ...
  ]
})" << "\n";
}

// ============================================================
// Example 8: Template System (Phase 5)
// ============================================================
void example8_TemplateSystem() {
    printSeparator("Example 8: Template System (Phase 5)");

    std::cout << "QueryTemplate provides reusable query configurations:\n\n";

    printSubSection("Built-in Templates");
    auto& manager = TemplateManager::instance();

    std::cout << "Available templates:\n";
    for (const auto& name : manager.listTemplates()) {
        auto tmpl = manager.get(name);
        std::cout << "  " << name << "\n";
        std::cout << "    " << tmpl.getDescription() << "\n";
    }

    printSubSection("Using Templates");
    std::cout << R"(
    // Get template by name or alias
    auto tmpl = TemplateManager::instance().getByAlias("stress");

    // Set parameters
    tmpl.setParameter("parts", {"Hood", "Fender"});
    tmpl.setParameter("stress_type", "von_mises");

    // Create and execute query
    auto query = tmpl.createQuery(reader);
    query.writeCSV("output.csv");
    )" << "\n";

    printSubSection("Template Aliases");
    std::cout << "Quick access aliases:\n";
    auto aliases = manager.getAliases();
    for (const auto& [alias, target] : aliases) {
        std::cout << "  " << alias << " -> " << target << "\n";
    }

    printSubSection("Custom Templates");
    std::cout << R"(
    QueryTemplate myTemplate("my_analysis", "Custom analysis template");
    myTemplate.setCategory("custom")
              .addParameter("threshold", "Stress threshold", 500.0, false)
              .setQuantities(QuantitySelector::vonMises())
              .setTime(TimeSelector::allStates());

    // Save for reuse
    myTemplate.saveToYAML("my_template.yaml");
    )" << "\n";
}

// ============================================================
// Example 9: Complete Workflow
// ============================================================
void example9_CompleteWorkflow() {
    printSeparator("Example 9: Complete Analysis Workflow");

    std::cout << "Typical crash analysis workflow:\n\n";

    std::cout << R"(
    // 1. Open d3plot file
    D3plotReader reader("crash.d3plot");
    reader.open();

    // 2. Create query for maximum stress analysis
    D3plotQuery(reader)
        .selectParts(PartSelector().byPattern("Body_*"))  // Body panels
        .selectQuantities(QuantitySelector::vonMises())   // Von Mises stress
        .selectTime(TimeSelector::allStates())            // All timesteps
        .whereValue(ValueFilter().inTopPercentile(5))     // Top 5% only
        .output(OutputSpec::json()
            .precision(4)
            .includeStatisticsSection(true))
        .write("critical_stress.json");

    // 3. Extract time history for critical elements
    auto result = D3plotQuery(reader)
        .selectAllParts()
        .selectQuantities(QuantitySelector::commonCrash())
        .selectTime(TimeSelector::allStates())
        .execute();

    // 4. Analyze results
    auto stats = result.getStatistics("von_mises");
    std::cout << "Max stress: " << stats.max_value
              << " at element " << stats.max_element_id << std::endl;

    // 5. Get element history
    auto history = result.getElementHistory(stats.max_element_id);
    for (size_t i = 0; i < history.times.size(); ++i) {
        std::cout << "t=" << history.times[i]
                  << " stress=" << history.quantity_histories["von_mises"][i]
                  << std::endl;
    }

    reader.close();
    )" << "\n";
}

// ============================================================
// Main
// ============================================================
int main(int argc, char* argv[]) {
    std::cout << R"(
╔══════════════════════════════════════════════════════════════════════╗
║                                                                      ║
║             KooD3plot V3 Query System - Comprehensive Guide          ║
║                                                                      ║
║  Phase 1-2: Core Query System                                        ║
║  Phase 3:   Advanced Filtering & Aggregation                         ║
║  Phase 4:   Output Formats (CSV, JSON)                               ║
║  Phase 5:   Template System                                          ║
║  Phase 6:   Optimization & Documentation                             ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝
)" << "\n";

    // Run examples (without actual d3plot file)
    example2_PartSelection();
    example3_QuantitySelection();
    example4_TimeSelection();
    example5_ValueFiltering();
    example6_Aggregation();
    example7_OutputFormats();
    example8_TemplateSystem();
    example9_CompleteWorkflow();

    // If d3plot file provided, run actual query
    if (argc > 1) {
        std::string filepath = argv[1];
        std::cout << "\n";
        printSeparator("Running with actual d3plot file");
        std::cout << "File: " << filepath << "\n\n";

        try {
            D3plotReader reader(filepath);
            auto err = reader.open();
            if (err == ErrorCode::SUCCESS) {
                example1_BasicQuery(reader);
                reader.close();
            } else {
                std::cerr << "Failed to open file: " << error_to_string(err) << "\n";
            }
        } catch (const std::exception& e) {
            std::cerr << "Error: " << e.what() << "\n";
        }
    }

    std::cout << "\n";
    printSeparator("Guide Complete");
    std::cout << "For more information, see:\n";
    std::cout << "  - V3_QUICKREF.md (Quick Reference)\n";
    std::cout << "  - KOOD3PLOT_V3_MASTER_PLAN.md (Full Design)\n";
    std::cout << "  - examples/v3_query/ (Example Programs)\n";

    return 0;
}
