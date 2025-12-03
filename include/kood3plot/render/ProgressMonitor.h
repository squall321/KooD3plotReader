/**
 * @file ProgressMonitor.h
 * @brief Progress monitoring for long-running render operations
 * @author KooD3plot Development Team
 * @date 2025-11-24
 * @version 1.0.0
 *
 * Phase 9: Progress monitoring
 */

#pragma once

#include <string>
#include <chrono>
#include <mutex>
#include <memory>

namespace kood3plot {
namespace render {

/**
 * @brief Progress status information
 */
struct ProgressStatus {
    size_t total_tasks = 0;             ///< Total number of tasks
    size_t completed_tasks = 0;         ///< Number of completed tasks
    size_t failed_tasks = 0;            ///< Number of failed tasks
    double percent_complete = 0.0;      ///< Progress percentage (0-100)
    std::string current_task_id;        ///< Currently processing task ID
    double elapsed_time = 0.0;          ///< Elapsed time in seconds
    double estimated_remaining = 0.0;   ///< Estimated remaining time in seconds
    bool is_complete = false;           ///< All tasks completed flag

    /**
     * @brief Get progress as 0.0-1.0 value
     * @return Progress value
     */
    double getProgressValue() const {
        return (total_tasks > 0) ? (double)completed_tasks / total_tasks : 0.0;
    }

    /**
     * @brief Get success rate
     * @return Success rate 0.0-1.0
     */
    double getSuccessRate() const {
        size_t processed = completed_tasks + failed_tasks;
        return (processed > 0) ? (double)completed_tasks / processed : 0.0;
    }
};

/**
 * @brief Progress monitor for tracking render operations
 *
 * Thread-safe progress tracking with time estimation
 */
class ProgressMonitor {
public:
    /**
     * @brief Constructor
     * @param total_tasks Total number of tasks to monitor
     */
    explicit ProgressMonitor(size_t total_tasks = 0);

    /**
     * @brief Destructor
     */
    ~ProgressMonitor();

    // ============================================================
    // Configuration
    // ============================================================

    /**
     * @brief Reset monitor with new task count
     * @param total_tasks Total number of tasks
     */
    void reset(size_t total_tasks);

    /**
     * @brief Set total task count
     * @param total Total number of tasks
     */
    void setTotalTasks(size_t total);

    // ============================================================
    // Progress Tracking
    // ============================================================

    /**
     * @brief Start monitoring (begins timer)
     */
    void start();

    /**
     * @brief Mark a task as started
     * @param task_id Task identifier
     */
    void startTask(const std::string& task_id);

    /**
     * @brief Mark a task as completed
     * @param task_id Task identifier
     * @param success true if successful, false if failed
     */
    void completeTask(const std::string& task_id, bool success = true);

    /**
     * @brief Mark current task as failed
     * @param task_id Task identifier
     */
    void failTask(const std::string& task_id);

    /**
     * @brief Update progress manually
     * @param completed Number of completed tasks
     * @param failed Number of failed tasks
     */
    void update(size_t completed, size_t failed = 0);

    /**
     * @brief Finish monitoring
     */
    void finish();

    // ============================================================
    // Status Query
    // ============================================================

    /**
     * @brief Get current progress status
     * @return Status structure
     */
    ProgressStatus getStatus() const;

    /**
     * @brief Get progress percentage (0-100)
     * @return Progress percentage
     */
    double getPercentComplete() const;

    /**
     * @brief Get number of completed tasks
     * @return Completed task count
     */
    size_t getCompletedCount() const;

    /**
     * @brief Get number of failed tasks
     * @return Failed task count
     */
    size_t getFailedCount() const;

    /**
     * @brief Get elapsed time in seconds
     * @return Elapsed time
     */
    double getElapsedTime() const;

    /**
     * @brief Get estimated remaining time in seconds
     * @return Estimated time or -1 if cannot estimate
     */
    double getEstimatedRemaining() const;

    /**
     * @brief Check if monitoring is complete
     * @return true if all tasks processed
     */
    bool isComplete() const;

    // ============================================================
    // Display
    // ============================================================

    /**
     * @brief Get progress bar string
     * @param width Width of progress bar in characters (default 50)
     * @return Progress bar string
     */
    std::string getProgressBar(int width = 50) const;

    /**
     * @brief Get status summary string
     * @return Status summary
     */
    std::string getStatusString() const;

    /**
     * @brief Display progress to console
     */
    void displayConsole() const;

private:
    struct Impl;
    std::unique_ptr<Impl> pImpl;

    // Helper methods
    void updateEstimates();
    std::string formatTime(double seconds) const;
};

} // namespace render
} // namespace kood3plot
