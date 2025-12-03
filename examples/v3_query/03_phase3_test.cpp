/**
 * @file 03_phase3_test.cpp
 * @brief V3 Query System Phase 3 Feature Test
 * @date 2025-11-21
 *
 * Tests Phase 3 features:
 * - Percentile filtering (top/bottom percentile)
 * - Statistical filtering (IQR, StdDev)
 * - TopN/BottomN filtering
 * - Advanced aggregation (SUM, COUNT, RANGE, MEDIAN)
 */

#include <iostream>
#include <iomanip>
#include <vector>
#include <cmath>
#include <fstream>
#include <sstream>

#include "kood3plot/query/ValueFilter.h"
#include "kood3plot/query/QueryResult.h"
#include "kood3plot/query/QueryTypes.h"
#include "kood3plot/query/OutputSpec.h"
#include "../../src/query/writers/JSONWriter.h"
#include "../../src/query/writers/CSVWriter.h"

using namespace kood3plot::query;

// Test data
std::vector<double> generateTestData() {
    // Generate test data: 100 values ranging from 1 to 100
    std::vector<double> data;
    for (int i = 1; i <= 100; ++i) {
        data.push_back(static_cast<double>(i));
    }
    return data;
}

void testPercentileFiltering() {
    std::cout << "===========================================\n";
    std::cout << "Test 1: Percentile Filtering\n";
    std::cout << "===========================================\n\n";

    auto data = generateTestData();  // 1 to 100

    // Test top 10 percentile
    ValueFilter top10 = ValueFilter().inTopPercentile(10);
    auto top10_result = top10.apply(data);
    std::cout << "Top 10%: " << top10_result.size() << " values\n";
    std::cout << "  Expected: ~10 values (91-100)\n";
    std::cout << "  First: " << top10_result.front() << ", Last: " << top10_result.back() << "\n";

    // Test bottom 5 percentile
    ValueFilter bottom5 = ValueFilter().inBottomPercentile(5);
    auto bottom5_result = bottom5.apply(data);
    std::cout << "\nBottom 5%: " << bottom5_result.size() << " values\n";
    std::cout << "  Expected: ~5 values (1-5)\n";
    std::cout << "  First: " << bottom5_result.front() << ", Last: " << bottom5_result.back() << "\n";

    // Test between percentiles (middle 50%)
    ValueFilter middle50 = ValueFilter().betweenPercentiles(25, 75);
    auto middle50_result = middle50.apply(data);
    std::cout << "\nMiddle 50% (25-75 percentile): " << middle50_result.size() << " values\n";
    std::cout << "  Expected: ~50 values (26-75)\n";
    std::cout << "  First: " << middle50_result.front() << ", Last: " << middle50_result.back() << "\n\n";
}

void testStatisticalFiltering() {
    std::cout << "===========================================\n";
    std::cout << "Test 2: Statistical Filtering\n";
    std::cout << "===========================================\n\n";

    auto data = generateTestData();  // 1 to 100
    // Mean = 50.5, StdDev = ~29.01

    // Test within 1 standard deviation
    ValueFilter within1std = ValueFilter().withinStdDev(1.0);
    auto within1std_result = within1std.apply(data);
    std::cout << "Within 1 StdDev: " << within1std_result.size() << " values\n";
    std::cout << "  (Data mean=50.5, stddev=~29)\n";
    std::cout << "  Expected: ~68% of values (~68 values)\n";

    // Test outside 1 standard deviation
    ValueFilter outside1std = ValueFilter().outsideStdDev(1.0);
    auto outside1std_result = outside1std.apply(data);
    std::cout << "\nOutside 1 StdDev: " << outside1std_result.size() << " values\n";
    std::cout << "  Expected: ~32% of values (~32 values)\n";

    // Test remove outliers (IQR method)
    // For uniform data 1-100, IQR = Q3-Q1 = 75-25 = 50
    // Lower bound = Q1 - 1.5*IQR = 25 - 75 = -50
    // Upper bound = Q3 + 1.5*IQR = 75 + 75 = 150
    // All data should pass (no outliers in uniform data)
    ValueFilter noOutliers = ValueFilter().removeOutliers(1.5);
    auto noOutliers_result = noOutliers.apply(data);
    std::cout << "\nRemove Outliers (IQR*1.5): " << noOutliers_result.size() << " values\n";
    std::cout << "  Expected: 100 values (uniform data has no outliers)\n\n";
}

void testTopNBottomN() {
    std::cout << "===========================================\n";
    std::cout << "Test 3: TopN/BottomN Filtering\n";
    std::cout << "===========================================\n\n";

    auto data = generateTestData();  // 1 to 100

    // Test top 10 values
    ValueFilter top10 = ValueFilter::topN(10);
    auto top10_result = top10.apply(data);
    std::cout << "Top 10 values: " << top10_result.size() << " values\n";
    std::cout << "  Expected: 10 values (91-100)\n";
    if (!top10_result.empty()) {
        std::cout << "  Values: ";
        for (size_t i = 0; i < std::min(top10_result.size(), size_t(5)); ++i) {
            std::cout << top10_result[i] << " ";
        }
        std::cout << "...\n";
    }

    // Test bottom 5 values
    ValueFilter bottom5 = ValueFilter::bottomN(5);
    auto bottom5_result = bottom5.apply(data);
    std::cout << "\nBottom 5 values: " << bottom5_result.size() << " values\n";
    std::cout << "  Expected: 5 values (1-5)\n";
    if (!bottom5_result.empty()) {
        std::cout << "  Values: ";
        for (auto v : bottom5_result) {
            std::cout << v << " ";
        }
        std::cout << "\n\n";
    }
}

void testAdvancedAggregation() {
    std::cout << "===========================================\n";
    std::cout << "Test 4: Advanced Aggregation\n";
    std::cout << "===========================================\n\n";

    // Create QueryResult with test data
    QueryResult result;
    for (int i = 1; i <= 10; ++i) {
        ResultDataPoint pt;
        pt.element_id = i;
        pt.part_id = 1;
        pt.state_index = 0;
        pt.time = 0.0;
        pt.values["test_value"] = static_cast<double>(i);  // 1 to 10
        result.addDataPoint(pt);
    }

    // Test aggregation functions
    std::cout << "Data: 1, 2, 3, ..., 10\n\n";

    double sum_val = result.sum("test_value");
    std::cout << "SUM: " << sum_val << " (expected: 55)\n";

    size_t count_val = result.count("test_value");
    std::cout << "COUNT: " << count_val << " (expected: 10)\n";

    double range_val = result.range("test_value");
    std::cout << "RANGE: " << range_val << " (expected: 9)\n";

    double mean_val = result.aggregate("test_value", AggregationType::MEAN);
    std::cout << "MEAN: " << mean_val << " (expected: 5.5)\n";

    double median_val = result.aggregate("test_value", AggregationType::MEDIAN);
    std::cout << "MEDIAN: " << median_val << " (expected: 5.5)\n";

    double max_val = result.aggregate("test_value", AggregationType::MAX);
    std::cout << "MAX: " << max_val << " (expected: 10)\n";

    double min_val = result.aggregate("test_value", AggregationType::MIN);
    std::cout << "MIN: " << min_val << " (expected: 1)\n";

    // Test getStatistics
    auto stats = result.getStatistics("test_value");
    std::cout << "\nFull Statistics:\n";
    std::cout << "  Sum: " << stats.sum << "\n";
    std::cout << "  Range: " << stats.range << "\n";
    std::cout << "  Median: " << stats.median << "\n";
    std::cout << "  Mean: " << stats.mean_value << "\n";
    std::cout << "  StdDev: " << stats.std_dev << "\n\n";
}

void testCombinedFilters() {
    std::cout << "===========================================\n";
    std::cout << "Test 5: Combined Filters\n";
    std::cout << "===========================================\n\n";

    auto data = generateTestData();  // 1 to 100

    // Test AND: top 20% AND greater than 85
    ValueFilter top20 = ValueFilter().inTopPercentile(20);
    ValueFilter gt85 = ValueFilter().greaterThan(85);
    auto combined = top20 && gt85;
    auto combined_result = combined.apply(data);
    std::cout << "Top 20% AND > 85: " << combined_result.size() << " values\n";
    std::cout << "  Top 20%: values >= 81\n";
    std::cout << "  > 85: values >= 86\n";
    std::cout << "  Combined: values >= 86 (14 values)\n";

    // Test filter descriptions
    std::cout << "\nFilter descriptions:\n";
    std::cout << "  Top 10%: " << ValueFilter().inTopPercentile(10).getDescription() << "\n";
    std::cout << "  Within 2 StdDev: " << ValueFilter().withinStdDev(2).getDescription() << "\n";
    std::cout << "  Top 5 values: " << ValueFilter::topN(5).getDescription() << "\n";
    std::cout << "  Bottom 3 values: " << ValueFilter::bottomN(3).getDescription() << "\n";
}

void testJSONOutput() {
    std::cout << "===========================================\n";
    std::cout << "Test 6: JSON Output (Phase 4)\n";
    std::cout << "===========================================\n\n";

    // Create QueryResult with test data
    QueryResult result;
    for (int i = 1; i <= 5; ++i) {
        ResultDataPoint pt;
        pt.element_id = 100 + i;
        pt.part_id = 1;
        pt.state_index = 0;
        pt.time = 0.001 * i;
        pt.values["von_mises"] = 100.0 + i * 10.0;
        pt.values["plastic_strain"] = 0.001 * i;
        result.addDataPoint(pt);
    }

    // Create output spec for JSON
    OutputSpec spec = OutputSpec::json()
        .fields({"part_id", "element_id", "time", "von_mises", "plastic_strain"})
        .precision(4)
        .includeMetadata(true)
        .addMetadata("test_name", "Phase 4 JSON Test")
        .includeStatisticsSection(true);

    std::cout << "OutputSpec description:\n" << spec.getDescription() << "\n\n";

    // Test JSON writer
    std::string json_file = "/tmp/v3_phase4_test.json";
    {
        writers::JSONWriter writer(json_file);
        writer.setSpec(spec);
        writer.write(result);
        writer.close();
    }

    // Read and display the JSON file
    std::ifstream ifs(json_file);
    if (ifs.is_open()) {
        std::cout << "Generated JSON output:\n";
        std::cout << "------------------------\n";
        std::stringstream buffer;
        buffer << ifs.rdbuf();
        std::cout << buffer.str() << "\n";
        ifs.close();
    } else {
        std::cout << "ERROR: Could not open JSON file for reading\n";
    }

    // Test CSV writer for comparison (using write(QueryResult) method)
    std::string csv_file = "/tmp/v3_phase4_test.csv";
    {
        writers::CSVWriter writer(csv_file);
        writer.setPrecision(4);
        writer.write(result);  // Use new write(QueryResult) method
        writer.close();
    }

    std::ifstream ifs2(csv_file);
    if (ifs2.is_open()) {
        std::cout << "\nGenerated CSV output:\n";
        std::cout << "------------------------\n";
        std::stringstream buffer;
        buffer << ifs2.rdbuf();
        std::cout << buffer.str() << "\n";
        ifs2.close();
    }

    std::cout << "JSON and CSV output test completed!\n\n";
}

int main() {
    std::cout << "===========================================\n";
    std::cout << "V3 Query System - Phase 3 Feature Test\n";
    std::cout << "===========================================\n\n";

    testPercentileFiltering();
    testStatisticalFiltering();
    testTopNBottomN();
    testAdvancedAggregation();
    testCombinedFilters();
    testJSONOutput();

    std::cout << "===========================================\n";
    std::cout << "All Phase 3 & Phase 4 tests completed!\n";
    std::cout << "===========================================\n";

    return 0;
}
