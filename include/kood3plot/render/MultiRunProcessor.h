/**
 * @file MultiRunProcessor.h
 * @brief Parallel processing and comparison analysis for multiple simulation runs
 *
 * Based on MultiRunProcessor from KooDynaPostProcessor
 */

#pragma once

#include "LSPrePostRenderer.h"
#include "RenderConfig.h"
#include "ProgressMonitor.h"
#include <string>
#include <vector>
#include <map>
#include <mutex>
#include <thread>
#include <queue>
#include <functional>
#include <future>
#include <condition_variable>
#include <memory>
#include <chrono>

namespace kood3plot {

// Forward declaration
class D3plotReader;

namespace render {

// ============================================================
// Thread Pool
// ============================================================

/**
 * @brief Thread pool for parallel processing
 */
class ThreadPool {
public:
    explicit ThreadPool(size_t numThreads);
    ~ThreadPool();

    /**
     * @brief Enqueue a task for execution
     */
    template<class F, class... Args>
    auto enqueue(F&& f, Args&&... args)
        -> std::future<typename std::result_of<F(Args...)>::type>;

    /**
     * @brief Wait for all tasks to complete
     */
    void wait();

    /**
     * @brief Get number of active tasks
     */
    size_t getActiveTaskCount() const;

    /**
     * @brief Get number of queued tasks
     */
    size_t getQueuedTaskCount() const;

private:
    std::vector<std::thread> workers_;
    std::queue<std::function<void()>> tasks_;
    mutable std::mutex queueMutex_;
    std::condition_variable condition_;
    std::condition_variable waitCondition_;
    bool stop_;
    size_t activeTaskCount_;
};

// ============================================================
// Data Structures
// ============================================================

/**
 * @brief Run data structure
 */
struct RunData {
    std::string run_id;           ///< Run identifier
    std::string d3plot_path;      ///< Path to d3plot file
    std::string output_dir;       ///< Output directory for this run
    RenderConfig config;          ///< Render configuration
};

/**
 * @brief Run result structure
 */
struct RunResult {
    std::string run_id;
    bool success;
    std::string error_message;
    double processing_time_sec;
    std::vector<std::string> generated_files;

    RunResult() : success(false), processing_time_sec(0.0) {}
};

/**
 * @brief Multi-run progress status
 */
struct MultiRunProgressStatus {
    size_t total_runs;
    size_t completed_runs;
    size_t failed_runs;
    double percent_complete;
    std::string current_run;
    std::vector<std::string> completed_run_ids;
    std::vector<std::string> failed_run_ids;

    MultiRunProgressStatus() :
        total_runs(0),
        completed_runs(0),
        failed_runs(0),
        percent_complete(0.0)
    {}
};

/**
 * @brief Multi-run progress callback function type
 */
using MultiRunProgressCallback = std::function<void(const MultiRunProgressStatus&)>;

/**
 * @brief Comparison data for multiple runs
 */
struct ComparisonData {
    std::string section_label;              ///< Section identifier
    std::map<std::string, RunResult> results;  ///< Results by run_id
    std::map<std::string, double> statistics;  ///< Statistical data
};

// ============================================================
// Multi-Run Progress Monitor
// ============================================================

/**
 * @brief Progress monitor for tracking run completion
 */
class MultiRunProgressMonitor {
public:
    MultiRunProgressMonitor();

    /**
     * @brief Update progress for a run
     */
    void update(const std::string& run_id, double progress);

    /**
     * @brief Mark run as completed
     */
    void markCompleted(const std::string& run_id, bool success);

    /**
     * @brief Display progress to console
     */
    void displayConsole() const;

    /**
     * @brief Get progress bar string
     */
    std::string getProgressBar(double percentage, int width = 50) const;

    /**
     * @brief Get current status
     */
    MultiRunProgressStatus getStatus() const;

    /**
     * @brief Reset monitor
     */
    void reset(size_t total_runs);

private:
    MultiRunProgressStatus status_;
    std::map<std::string, double> run_progress_;
    mutable std::mutex mutex_;
};

// ============================================================
// Multi-Run Processor
// ============================================================

/**
 * @brief Options for multi-run processor
 */
struct ProcessorOptions {
    bool enable_parallel;       ///< Enable parallel processing
    size_t max_threads;         ///< Maximum number of threads
    bool verbose;               ///< Verbose output

    ProcessorOptions() :
        enable_parallel(true),
        max_threads(8),
        verbose(true)
    {}
};

/**
 * @brief Multi-run processor for parallel section analysis
 *
 * This class processes multiple simulation runs in parallel and generates
 * comparison reports. It uses a thread pool for efficient parallel processing.
 */
class MultiRunProcessor {
public:
    /**
     * @brief Constructor
     * @param lsprepost_path Path to LSPrePost executable
     * @param max_threads Maximum number of threads for parallel processing
     */
    explicit MultiRunProcessor(
        const std::string& lsprepost_path,
        size_t max_threads = 8
    );
    ~MultiRunProcessor();

    // ============================================================
    // Run Management
    // ============================================================

    /**
     * @brief Add a run to process
     */
    void addRun(RunData&& run_data);

    /**
     * @brief Clear all runs
     */
    void clearRuns();

    /**
     * @brief Get number of runs
     */
    size_t getRunCount() const;

    // ============================================================
    // Processing
    // ============================================================

    /**
     * @brief Process all runs in parallel
     * @param progress_callback Optional callback for progress updates
     */
    void processInParallel(MultiRunProgressCallback progress_callback = nullptr);

    /**
     * @brief Process all runs sequentially
     * @param progress_callback Optional callback for progress updates
     */
    void processSequentially(MultiRunProgressCallback progress_callback = nullptr);

    // ============================================================
    // Progress Monitoring
    // ============================================================

    /**
     * @brief Get current progress
     */
    MultiRunProgressStatus getProgress() const;

    /**
     * @brief Set progress callback
     */
    void setProgressCallback(MultiRunProgressCallback callback);

    // ============================================================
    // Results
    // ============================================================

    /**
     * @brief Get all results
     */
    std::map<std::string, RunResult> getResults() const;

    /**
     * @brief Get result for a specific run
     */
    RunResult getResult(const std::string& run_id) const;

    /**
     * @brief Check if any errors occurred
     */
    bool hasErrors() const;

    /**
     * @brief Get error messages
     */
    std::map<std::string, std::string> getErrors() const;

    // ============================================================
    // Comparison & Reporting
    // ============================================================

    /**
     * @brief Generate comparison data for all runs
     */
    std::vector<ComparisonData> generateComparisons();

    /**
     * @brief Save comparison report to text file
     */
    void saveComparisonReport(const std::string& output_path);

    /**
     * @brief Save results to CSV
     */
    void saveResultsCSV(const std::string& output_path);

    // ============================================================
    // Options
    // ============================================================

    /**
     * @brief Set processor options
     */
    void setOptions(const ProcessorOptions& options);

    /**
     * @brief Get current options
     */
    ProcessorOptions getOptions() const { return options_; }

private:
    // Member variables
    std::string lsprepost_path_;
    std::vector<RunData> runs_;
    std::map<std::string, RunResult> results_;
    ProcessorOptions options_;
    std::unique_ptr<ThreadPool> thread_pool_;
    std::unique_ptr<MultiRunProgressMonitor> progress_monitor_;
    MultiRunProgressCallback progress_callback_;

    // Thread safety
    mutable std::mutex runs_mutex_;
    mutable std::mutex results_mutex_;

    // ============================================================
    // Private Methods
    // ============================================================

    /**
     * @brief Process a single run
     */
    void processRun(const RunData& run);

    /**
     * @brief Update progress callback if set
     */
    void updateProgress();
};

// ============================================================
// Template Implementation for ThreadPool::enqueue
// ============================================================

template<class F, class... Args>
auto ThreadPool::enqueue(F&& f, Args&&... args)
    -> std::future<typename std::result_of<F(Args...)>::type>
{
    using return_type = typename std::result_of<F(Args...)>::type;

    auto task = std::make_shared<std::packaged_task<return_type()>>(
        std::bind(std::forward<F>(f), std::forward<Args>(args)...)
    );

    std::future<return_type> res = task->get_future();

    {
        std::unique_lock<std::mutex> lock(queueMutex_);

        if (stop_) {
            throw std::runtime_error("enqueue on stopped ThreadPool");
        }

        tasks_.emplace([task]() { (*task)(); });
    }

    condition_.notify_one();
    return res;
}

} // namespace render
} // namespace kood3plot
