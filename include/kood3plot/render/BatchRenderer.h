/**
 * @file BatchRenderer.h
 * @brief Batch processing for multiple render operations
 * @author KooD3plot Development Team
 * @date 2025-11-24
 * @version 1.0.0
 *
 * Phase 9: Batch processing and progress monitoring
 */

#pragma once

#include "LSPrePostRenderer.h"
#include "ProgressMonitor.h"
#include <vector>
#include <string>
#include <memory>
#include <functional>
#include <map>

namespace kood3plot {
namespace render {

/**
 * @brief Batch render job definition
 */
struct BatchJob {
    std::string job_id;                 ///< Unique job identifier
    std::string d3plot_path;            ///< Path to d3plot file
    std::string output_path;            ///< Output file path
    RenderOptions options;              ///< Rendering options
    bool success = false;               ///< Job completion status
    std::string error_message;          ///< Error message if failed
    double processing_time = 0.0;       ///< Processing time in seconds

    BatchJob() = default;
    BatchJob(const std::string& id, const std::string& d3plot,
             const std::string& output, const RenderOptions& opts)
        : job_id(id), d3plot_path(d3plot), output_path(output), options(opts) {}
};

/**
 * @brief Progress callback function type
 * @param completed_count Number of completed jobs
 * @param total_count Total number of jobs
 * @param current_job_id ID of currently processing job
 * @param progress_percent Overall progress percentage (0-100)
 */
using ProgressCallback = std::function<void(
    size_t completed_count,
    size_t total_count,
    const std::string& current_job_id,
    double progress_percent
)>;

/**
 * @brief Batch renderer for processing multiple render jobs
 *
 * Features:
 * - Sequential batch processing
 * - Progress monitoring and callbacks
 * - Error handling and reporting
 * - Result tracking
 */
class BatchRenderer {
public:
    /**
     * @brief Constructor
     * @param lsprepost_path Path to LSPrePost executable
     */
    explicit BatchRenderer(const std::string& lsprepost_path = "lsprepost");

    /**
     * @brief Destructor
     */
    ~BatchRenderer();

    // ============================================================
    // Job Management
    // ============================================================

    /**
     * @brief Add a render job to the batch
     * @param job Job definition
     */
    void addJob(const BatchJob& job);

    /**
     * @brief Add multiple jobs
     * @param jobs Vector of job definitions
     */
    void addJobs(const std::vector<BatchJob>& jobs);

    /**
     * @brief Clear all jobs
     */
    void clearJobs();

    /**
     * @brief Get number of jobs
     * @return Total job count
     */
    size_t getJobCount() const;

    // ============================================================
    // Processing
    // ============================================================

    /**
     * @brief Process all jobs sequentially
     * @return Number of successful jobs
     */
    size_t processAll();

    /**
     * @brief Process jobs with progress callback
     * @param callback Progress callback function
     * @return Number of successful jobs
     */
    size_t processAll(ProgressCallback callback);

    // ============================================================
    // Progress Monitoring
    // ============================================================

    /**
     * @brief Set progress callback
     * @param callback Progress callback function
     */
    void setProgressCallback(ProgressCallback callback);

    /**
     * @brief Get current progress (0.0 to 1.0)
     * @return Progress value
     */
    double getProgress() const;

    /**
     * @brief Get number of completed jobs
     * @return Completed job count
     */
    size_t getCompletedCount() const;

    /**
     * @brief Get number of failed jobs
     * @return Failed job count
     */
    size_t getFailedCount() const;

    // ============================================================
    // Results
    // ============================================================

    /**
     * @brief Get all processed jobs
     * @return Vector of jobs with results
     */
    std::vector<BatchJob> getJobs() const;

    /**
     * @brief Get successful jobs
     * @return Vector of successful jobs
     */
    std::vector<BatchJob> getSuccessfulJobs() const;

    /**
     * @brief Get failed jobs
     * @return Vector of failed jobs
     */
    std::vector<BatchJob> getFailedJobs() const;

    /**
     * @brief Get job by ID
     * @param job_id Job identifier
     * @return Job pointer or nullptr if not found
     */
    const BatchJob* getJob(const std::string& job_id) const;

    /**
     * @brief Check if any jobs failed
     * @return true if at least one job failed
     */
    bool hasFailures() const;

    /**
     * @brief Get error messages for failed jobs
     * @return Map of job_id to error message
     */
    std::map<std::string, std::string> getErrors() const;

    // ============================================================
    // Reporting
    // ============================================================

    /**
     * @brief Generate text report of batch results
     * @return Report string
     */
    std::string generateReport() const;

    /**
     * @brief Save report to file
     * @param file_path Output file path
     * @return true on success
     */
    bool saveReport(const std::string& file_path) const;

    /**
     * @brief Export results to CSV
     * @param file_path Output CSV file path
     * @return true on success
     */
    bool exportToCSV(const std::string& file_path) const;

private:
    struct Impl;
    std::unique_ptr<Impl> pImpl;

    // Helper methods
    void notifyProgress();
    std::string formatDuration(double seconds) const;
};

} // namespace render
} // namespace kood3plot
