/**
 * @file TimeHistoryAnalyzer.cpp
 * @brief Implementation of unified time history analysis
 *
 * This implementation uses SinglePassAnalyzer for ~47x performance improvement.
 * Each state is read only once, and all analyses are performed in a single pass.
 */

#include "kood3plot/analysis/TimeHistoryAnalyzer.hpp"
#include "kood3plot/analysis/SinglePassAnalyzer.hpp"
#include "kood3plot/Version.hpp"
#include <iostream>

namespace kood3plot {
namespace analysis {

AnalysisResult TimeHistoryAnalyzer::analyze(const AnalysisConfig& config) {
    return analyze(config, nullptr);
}

AnalysisResult TimeHistoryAnalyzer::analyze(
    const AnalysisConfig& config,
    AnalysisProgressCallback callback
) {
    success_ = false;
    last_error_.clear();

    // Open d3plot file
    D3plotReader reader(config.d3plot_path);
    if (reader.open() != ErrorCode::SUCCESS) {
        last_error_ = "Failed to open d3plot file: " + config.d3plot_path;
        return AnalysisResult();
    }

    if (config.verbose) {
        std::cout << "Using SinglePassAnalyzer for optimized performance...\n";
    }

    // Use SinglePassAnalyzer for high performance
    SinglePassAnalyzer single_pass(reader);

    // Convert callback format
    SinglePassProgressCallback sp_callback = nullptr;
    if (callback) {
        sp_callback = [&callback](size_t current, size_t total, const std::string& msg) {
            callback("SinglePass", current, total, msg);
        };
    }

    // Run analysis
    AnalysisResult result = single_pass.analyze(config, sp_callback);

    if (!single_pass.wasSuccessful()) {
        last_error_ = single_pass.getLastError();
        return result;
    }

    if (callback) {
        callback("Complete", 1, 1, "Analysis complete");
    }

    success_ = true;
    return result;
}

// ========================================
// Legacy methods (kept for compatibility but not used)
// ========================================

void TimeHistoryAnalyzer::fillMetadata(
    D3plotReader& reader,
    const AnalysisConfig& config,
    AnalysisResult& result
) {
    // Now handled by SinglePassAnalyzer
}

void TimeHistoryAnalyzer::analyzeStressHistory(
    D3plotReader& reader,
    PartAnalyzer& part_analyzer,
    const AnalysisConfig& config,
    AnalysisResult& result,
    AnalysisProgressCallback callback
) {
    // Now handled by SinglePassAnalyzer
}

void TimeHistoryAnalyzer::analyzeStrainHistory(
    D3plotReader& reader,
    PartAnalyzer& part_analyzer,
    const AnalysisConfig& config,
    AnalysisResult& result,
    AnalysisProgressCallback callback
) {
    // Now handled by SinglePassAnalyzer
}

void TimeHistoryAnalyzer::analyzeAccelerationHistory(
    D3plotReader& reader,
    const AnalysisConfig& config,
    AnalysisResult& result,
    AnalysisProgressCallback callback
) {
    // Not yet implemented
}

void TimeHistoryAnalyzer::analyzeSurfaceStress(
    D3plotReader& reader,
    const AnalysisConfig& config,
    AnalysisResult& result,
    AnalysisProgressCallback callback
) {
    // Now handled by SinglePassAnalyzer
}

PartTimeSeriesStats TimeHistoryAnalyzer::convertToStats(
    const PartTimeHistory& history,
    const std::string& quantity,
    const std::string& unit
) {
    PartTimeSeriesStats stats;
    stats.part_id = history.part_id;
    stats.part_name = history.part_name;
    stats.quantity = quantity;
    stats.unit = unit;

    size_t n = history.times.size();
    stats.data.resize(n);

    for (size_t i = 0; i < n; ++i) {
        stats.data[i].time = history.times[i];
        stats.data[i].max_value = history.max_values[i];
        stats.data[i].min_value = history.min_values[i];
        stats.data[i].avg_value = history.avg_values[i];
        stats.data[i].max_element_id = history.max_elem_ids[i];
        stats.data[i].min_element_id = 0;
    }

    return stats;
}

} // namespace analysis
} // namespace kood3plot
