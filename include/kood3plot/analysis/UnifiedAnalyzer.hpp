/**
 * @file UnifiedAnalyzer.hpp
 * @brief Unified job-based analyzer for d3plot files
 * @author KooD3plot Development Team
 * @date 2025-12-04
 *
 * Provides unified analysis based on YAML configuration with analysis_jobs.
 * Uses SinglePassAnalyzer approach for efficient processing.
 *
 * Features:
 * - Job-based analysis configuration
 * - Von Mises stress, effective plastic strain
 * - Motion analysis (displacement, velocity, acceleration)
 * - Surface stress and strain analysis
 * - Comprehensive multi-quantity analysis
 * - Single-pass optimization
 *
 * Usage:
 * @code
 * UnifiedConfig config;
 * UnifiedConfigParser::loadFromYAML("config.yaml", config);
 *
 * UnifiedAnalyzer analyzer;
 * auto result = analyzer.analyze(config, [](const std::string& msg) {
 *     std::cout << msg << std::endl;
 * });
 * @endcode
 */

#pragma once

#include "kood3plot/D3plotReader.hpp"
#include "kood3plot/analysis/AnalysisTypes.hpp"
#include "kood3plot/analysis/MotionAnalyzer.hpp"
#include "kood3plot/analysis/SurfaceStrainAnalyzer.hpp"
#include "kood3plot/analysis/SinglePassAnalyzer.hpp"
#include <functional>
#include <string>
#include <vector>
#include <memory>

namespace kood3plot {
namespace analysis {

/**
 * @brief Progress callback type
 */
using UnifiedProgressCallback = std::function<void(const std::string& message)>;

/**
 * @brief Unified job-based analyzer
 *
 * Processes analysis_jobs from UnifiedConfig and produces ExtendedAnalysisResult.
 */
class UnifiedAnalyzer {
public:
    /**
     * @brief Constructor
     */
    UnifiedAnalyzer() = default;

    /**
     * @brief Destructor
     */
    ~UnifiedAnalyzer() = default;

    /**
     * @brief Run analysis based on configuration
     * @param config Unified configuration
     * @return Extended analysis result
     */
    ExtendedAnalysisResult analyze(const UnifiedConfig& config);

    /**
     * @brief Run analysis with progress callback
     * @param config Unified configuration
     * @param callback Progress callback function
     * @return Extended analysis result
     */
    ExtendedAnalysisResult analyze(const UnifiedConfig& config, UnifiedProgressCallback callback);

    /**
     * @brief Get last error message
     */
    const std::string& getLastError() const { return last_error_; }

    /**
     * @brief Check if last analysis was successful
     */
    bool wasSuccessful() const { return success_; }

    /** @brief True if section views were already processed inside analyze() */
    bool sectionViewsDone() const { return section_views_done_; }

private:
    std::string last_error_;
    bool success_ = false;
    bool section_views_done_ = false;

    // Internal analysis methods

    /** @brief Single-pass solid element analysis (stress + strain + principal in one loop) */
    void processSolidJobs(
        D3plotReader& reader,
        const std::vector<AnalysisJob>& stress_jobs,
        const std::vector<AnalysisJob>& strain_jobs,
        const std::vector<data::StateData>& all_states,
        ExtendedAnalysisResult& result,
        UnifiedProgressCallback callback
    );

    void processMotionJobs(
        D3plotReader& reader,
        const std::vector<AnalysisJob>& jobs,
        const std::vector<data::StateData>& all_states,
        ExtendedAnalysisResult& result,
        UnifiedProgressCallback callback
    );

    void processSurfaceStressJobs(
        D3plotReader& reader,
        const std::vector<AnalysisJob>& jobs,
        const std::vector<data::StateData>& all_states,
        ExtendedAnalysisResult& result,
        UnifiedProgressCallback callback
    );

    void processSurfaceStrainJobs(
        D3plotReader& reader,
        const std::vector<AnalysisJob>& jobs,
        const std::vector<data::StateData>& all_states,
        ExtendedAnalysisResult& result,
        UnifiedProgressCallback callback
    );

    void processElementQualityJobs(
        D3plotReader& reader,
        const std::vector<AnalysisJob>& jobs,
        const std::vector<data::StateData>& all_states,
        ExtendedAnalysisResult& result,
        UnifiedProgressCallback callback
    );

    /**
     * @brief Fill metadata in result
     */
    void fillMetadata(
        D3plotReader& reader,
        const UnifiedConfig& config,
        const std::vector<data::StateData>& all_states,
        ExtendedAnalysisResult& result
    );

public:
    /**
     * @brief Process render jobs
     * @param reader D3plot reader
     * @param config Unified configuration with render_jobs
     * @param callback Progress callback
     * @return true if all render jobs succeeded
     *
     * Note: This is public because render jobs can be run separately
     * from analysis jobs, and requires separate reader instance.
     */
    bool processRenderJobs(
        D3plotReader& reader,
        const UnifiedConfig& config,
        UnifiedProgressCallback callback
    );

    /**
     * @brief Run all section_views jobs (software rasterizer, no LSPrePost).
     *
     * Real implementation lives in UnifiedAnalyzerSectionRender.cpp and is
     * compiled only when KOOD3PLOT_HAS_SECTION_RENDER is defined.
     * A no-op stub is compiled when the module is disabled.
     */
    bool processSectionViews(
        D3plotReader& reader,
        const UnifiedConfig& config,
        UnifiedProgressCallback callback
    );

    /**
     * @brief Run section_views with pre-loaded state data (zero-copy shared).
     *
     * Uses pre-loaded mesh/ctrl/states from the analysis phase — avoids
     * re-reading d3plot files. Multiple section view specs run in parallel
     * threads, each sharing the same const state data.
     */
    bool processSectionViews(
        D3plotReader& reader,
        const UnifiedConfig& config,
        const std::vector<data::StateData>& all_states,
        UnifiedProgressCallback callback
    );
};

} // namespace analysis
} // namespace kood3plot
