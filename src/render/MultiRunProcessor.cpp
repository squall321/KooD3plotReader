/**
 * @file MultiRunProcessor.cpp
 * @brief Implementation of parallel processing and comparison analysis
 */

#include "kood3plot/render/MultiRunProcessor.h"
#include "kood3plot/D3plotReader.hpp"
#include <iostream>
#include <fstream>
#include <sstream>
#include <iomanip>
#include <algorithm>
#include <filesystem>

namespace kood3plot {
namespace render {

// ============================================================
// ThreadPool Implementation
// ============================================================

ThreadPool::ThreadPool(size_t numThreads)
    : stop_(false), activeTaskCount_(0)
{
    for (size_t i = 0; i < numThreads; ++i) {
        workers_.emplace_back([this] {
            while (true) {
                std::function<void()> task;
                {
                    std::unique_lock<std::mutex> lock(this->queueMutex_);
                    this->condition_.wait(lock, [this] {
                        return this->stop_ || !this->tasks_.empty();
                    });

                    if (this->stop_ && this->tasks_.empty()) {
                        return;
                    }

                    task = std::move(this->tasks_.front());
                    this->tasks_.pop();
                    ++this->activeTaskCount_;
                }

                task();

                {
                    std::unique_lock<std::mutex> lock(this->queueMutex_);
                    --this->activeTaskCount_;
                    if (this->activeTaskCount_ == 0 && this->tasks_.empty()) {
                        this->waitCondition_.notify_all();
                    }
                }
            }
        });
    }
}

ThreadPool::~ThreadPool()
{
    {
        std::unique_lock<std::mutex> lock(queueMutex_);
        stop_ = true;
    }
    condition_.notify_all();
    for (std::thread& worker : workers_) {
        if (worker.joinable()) {
            worker.join();
        }
    }
}

void ThreadPool::wait()
{
    std::unique_lock<std::mutex> lock(queueMutex_);
    waitCondition_.wait(lock, [this] {
        return this->tasks_.empty() && this->activeTaskCount_ == 0;
    });
}

size_t ThreadPool::getActiveTaskCount() const
{
    std::lock_guard<std::mutex> lock(queueMutex_);
    return activeTaskCount_;
}

size_t ThreadPool::getQueuedTaskCount() const
{
    std::lock_guard<std::mutex> lock(queueMutex_);
    return tasks_.size();
}

// ============================================================
// MultiRunProgressMonitor Implementation
// ============================================================

MultiRunProgressMonitor::MultiRunProgressMonitor()
{
}

void MultiRunProgressMonitor::update(const std::string& run_id, double progress)
{
    std::lock_guard<std::mutex> lock(mutex_);
    run_progress_[run_id] = progress;
    status_.current_run = run_id;
}

void MultiRunProgressMonitor::markCompleted(const std::string& run_id, bool success)
{
    std::lock_guard<std::mutex> lock(mutex_);

    ++status_.completed_runs;

    if (success) {
        status_.completed_run_ids.push_back(run_id);
    } else {
        status_.failed_run_ids.push_back(run_id);
        ++status_.failed_runs;
    }

    status_.percent_complete =
        (static_cast<double>(status_.completed_runs) / status_.total_runs) * 100.0;
}

void MultiRunProgressMonitor::displayConsole() const
{
    std::lock_guard<std::mutex> lock(mutex_);

    std::cout << "\r";  // Carriage return to overwrite line
    std::cout << getProgressBar(status_.percent_complete)
              << " " << std::fixed << std::setprecision(1)
              << status_.percent_complete << "% "
              << "(" << status_.completed_runs << "/" << status_.total_runs << ") "
              << std::flush;
}

std::string MultiRunProgressMonitor::getProgressBar(double percentage, int width) const
{
    int filled = static_cast<int>((percentage / 100.0) * width);
    std::string bar = "[";
    for (int i = 0; i < width; ++i) {
        if (i < filled) {
            bar += "=";
        } else if (i == filled) {
            bar += ">";
        } else {
            bar += " ";
        }
    }
    bar += "]";
    return bar;
}

MultiRunProgressStatus MultiRunProgressMonitor::getStatus() const
{
    std::lock_guard<std::mutex> lock(mutex_);
    return status_;
}

void MultiRunProgressMonitor::reset(size_t total_runs)
{
    std::lock_guard<std::mutex> lock(mutex_);
    status_ = MultiRunProgressStatus();
    status_.total_runs = total_runs;
    run_progress_.clear();
}

// ============================================================
// MultiRunProcessor Implementation
// ============================================================

MultiRunProcessor::MultiRunProcessor(
    const std::string& lsprepost_path,
    size_t max_threads)
    : lsprepost_path_(lsprepost_path)
{
    options_.max_threads = max_threads;
    options_.enable_parallel = true;

    thread_pool_ = std::make_unique<ThreadPool>(max_threads);
    progress_monitor_ = std::make_unique<MultiRunProgressMonitor>();
}

MultiRunProcessor::~MultiRunProcessor()
{
}

// ============================================================
// Run Management
// ============================================================

void MultiRunProcessor::addRun(RunData&& run_data)
{
    std::lock_guard<std::mutex> lock(runs_mutex_);
    runs_.push_back(std::move(run_data));
}

void MultiRunProcessor::clearRuns()
{
    std::lock_guard<std::mutex> lock(runs_mutex_);
    runs_.clear();

    std::lock_guard<std::mutex> result_lock(results_mutex_);
    results_.clear();
}

size_t MultiRunProcessor::getRunCount() const
{
    std::lock_guard<std::mutex> lock(runs_mutex_);
    return runs_.size();
}

// ============================================================
// Processing
// ============================================================

void MultiRunProcessor::processInParallel(MultiRunProgressCallback progress_callback)
{
    progress_callback_ = progress_callback;

    size_t num_runs;
    {
        std::lock_guard<std::mutex> lock(runs_mutex_);
        num_runs = runs_.size();
    }

    if (num_runs == 0) {
        std::cerr << "No runs to process\n";
        return;
    }

    progress_monitor_->reset(num_runs);

    if (options_.verbose) {
        std::cout << "Processing " << num_runs << " runs in parallel with "
                  << options_.max_threads << " threads...\n";
    }

    std::vector<std::future<void>> futures;

    for (size_t i = 0; i < num_runs; ++i) {
        auto future = thread_pool_->enqueue([this, i]() {
            std::lock_guard<std::mutex> lock(this->runs_mutex_);
            if (i < this->runs_.size()) {
                const RunData& run = this->runs_[i];
                this->processRun(run);
            }
        });
        futures.push_back(std::move(future));
    }

    // Wait for all tasks to complete
    for (auto& future : futures) {
        future.get();
    }

    thread_pool_->wait();

    if (options_.verbose) {
        std::cout << "\n";  // New line after progress bar
        std::cout << "All runs completed!\n";

        auto status = progress_monitor_->getStatus();
        std::cout << "  Success: " << (status.completed_runs - status.failed_runs) << "\n";
        std::cout << "  Failed:  " << status.failed_runs << "\n";
    }
}

void MultiRunProcessor::processSequentially(MultiRunProgressCallback progress_callback)
{
    progress_callback_ = progress_callback;

    size_t num_runs;
    {
        std::lock_guard<std::mutex> lock(runs_mutex_);
        num_runs = runs_.size();
    }

    if (num_runs == 0) {
        std::cerr << "No runs to process\n";
        return;
    }

    progress_monitor_->reset(num_runs);

    if (options_.verbose) {
        std::cout << "Processing " << num_runs << " runs sequentially...\n";
    }

    for (size_t i = 0; i < num_runs; ++i) {
        std::lock_guard<std::mutex> lock(runs_mutex_);
        if (i < runs_.size()) {
            const RunData& run = runs_[i];
            processRun(run);
        }
    }

    if (options_.verbose) {
        std::cout << "All runs completed!\n";

        auto status = progress_monitor_->getStatus();
        std::cout << "  Success: " << (status.completed_runs - status.failed_runs) << "\n";
        std::cout << "  Failed:  " << status.failed_runs << "\n";
    }
}

void MultiRunProcessor::processRun(const RunData& run)
{
    auto start_time = std::chrono::high_resolution_clock::now();

    RunResult result;
    result.run_id = run.run_id;

    try {
        if (options_.verbose) {
            std::cout << "[" << run.run_id << "] Starting...\n";
        }

        // Create output directory
        std::filesystem::create_directories(run.output_dir);

        // Open d3plot reader
        D3plotReader reader(run.d3plot_path);
        auto err = reader.open();
        if (err != ErrorCode::SUCCESS) {
            throw std::runtime_error("Failed to open d3plot file: " + run.d3plot_path);
        }

        // Generate auto-sections if needed (modify the run's config in-place)
        const_cast<RunData&>(run).config.generateAutoSections(reader, 0);
        const RenderConfig& config = run.config;

        // Create renderer
        LSPrePostRenderer renderer(lsprepost_path_);

        // Process each section
        for (size_t i = 0; i < config.getData().sections.size(); ++i) {
            auto render_opts = config.toRenderOptions(i);

            std::string output_file = run.output_dir + "/section_" +
                                      std::to_string(i) + ".mp4";

            bool success = renderer.renderAnimation(
                run.d3plot_path,
                output_file,
                render_opts
            );

            if (success) {
                result.generated_files.push_back(output_file);
            } else {
                throw std::runtime_error("Rendering failed for section " + std::to_string(i));
            }
        }

        result.success = true;

        if (options_.verbose) {
            std::cout << "[" << run.run_id << "] Completed successfully!\n";
        }

    } catch (const std::exception& e) {
        result.success = false;
        result.error_message = e.what();

        if (options_.verbose) {
            std::cerr << "[" << run.run_id << "] Failed: " << e.what() << "\n";
        }
    }

    auto end_time = std::chrono::high_resolution_clock::now();
    std::chrono::duration<double> elapsed = end_time - start_time;
    result.processing_time_sec = elapsed.count();

    // Store result
    {
        std::lock_guard<std::mutex> lock(results_mutex_);
        results_[run.run_id] = result;
    }

    // Update progress
    progress_monitor_->markCompleted(run.run_id, result.success);

    if (options_.verbose) {
        progress_monitor_->displayConsole();
    }

    if (progress_callback_) {
        progress_callback_(progress_monitor_->getStatus());
    }
}

// ============================================================
// Progress Monitoring
// ============================================================

MultiRunProgressStatus MultiRunProcessor::getProgress() const
{
    return progress_monitor_->getStatus();
}

void MultiRunProcessor::setProgressCallback(MultiRunProgressCallback callback)
{
    progress_callback_ = callback;
}

// ============================================================
// Results
// ============================================================

std::map<std::string, RunResult> MultiRunProcessor::getResults() const
{
    std::lock_guard<std::mutex> lock(results_mutex_);
    return results_;
}

RunResult MultiRunProcessor::getResult(const std::string& run_id) const
{
    std::lock_guard<std::mutex> lock(results_mutex_);
    auto it = results_.find(run_id);
    if (it != results_.end()) {
        return it->second;
    }
    return RunResult();  // Return empty result if not found
}

bool MultiRunProcessor::hasErrors() const
{
    std::lock_guard<std::mutex> lock(results_mutex_);
    for (const auto& pair : results_) {
        if (!pair.second.success) {
            return true;
        }
    }
    return false;
}

std::map<std::string, std::string> MultiRunProcessor::getErrors() const
{
    std::map<std::string, std::string> errors;

    std::lock_guard<std::mutex> lock(results_mutex_);
    for (const auto& pair : results_) {
        if (!pair.second.success) {
            errors[pair.first] = pair.second.error_message;
        }
    }

    return errors;
}

// ============================================================
// Comparison & Reporting
// ============================================================

std::vector<ComparisonData> MultiRunProcessor::generateComparisons()
{
    std::vector<ComparisonData> comparisons;

    std::lock_guard<std::mutex> lock(results_mutex_);

    if (results_.empty()) {
        return comparisons;
    }

    // Group results by section
    std::map<size_t, ComparisonData> section_map;

    for (const auto& pair : results_) {
        const std::string& run_id = pair.first;
        const RunResult& result = pair.second;

        if (!result.success) {
            continue;
        }

        for (size_t i = 0; i < result.generated_files.size(); ++i) {
            ComparisonData& comp = section_map[i];
            comp.section_label = "Section_" + std::to_string(i);
            comp.results[run_id] = result;
        }
    }

    // Convert to vector
    for (const auto& pair : section_map) {
        comparisons.push_back(pair.second);
    }

    return comparisons;
}

void MultiRunProcessor::saveComparisonReport(const std::string& output_path)
{
    auto comparisons = generateComparisons();

    std::ofstream file(output_path);
    if (!file.is_open()) {
        throw std::runtime_error("Failed to open output file: " + output_path);
    }

    file << "==============================================\n";
    file << "  Multi-Run Comparison Report\n";
    file << "==============================================\n\n";

    auto results = getResults();
    file << "Total Runs: " << results.size() << "\n";

    size_t success_count = 0;
    for (const auto& pair : results) {
        if (pair.second.success) {
            ++success_count;
        }
    }

    file << "Successful: " << success_count << "\n";
    file << "Failed: " << (results.size() - success_count) << "\n\n";

    file << "----------------------------------------------\n";
    file << "Run Details:\n";
    file << "----------------------------------------------\n\n";

    for (const auto& pair : results) {
        const std::string& run_id = pair.first;
        const RunResult& result = pair.second;

        file << "Run ID: " << run_id << "\n";
        file << "  Status: " << (result.success ? "SUCCESS" : "FAILED") << "\n";
        file << "  Time: " << std::fixed << std::setprecision(2)
             << result.processing_time_sec << " seconds\n";

        if (!result.success) {
            file << "  Error: " << result.error_message << "\n";
        } else {
            file << "  Generated Files: " << result.generated_files.size() << "\n";
            for (const auto& f : result.generated_files) {
                file << "    - " << f << "\n";
            }
        }
        file << "\n";
    }

    file << "----------------------------------------------\n";
    file << "Comparison Summary:\n";
    file << "----------------------------------------------\n\n";

    for (const auto& comp : comparisons) {
        file << comp.section_label << ":\n";
        file << "  Runs with this section: " << comp.results.size() << "\n";
        file << "\n";
    }

    file.close();
}

void MultiRunProcessor::saveResultsCSV(const std::string& output_path)
{
    std::ofstream file(output_path);
    if (!file.is_open()) {
        throw std::runtime_error("Failed to open output file: " + output_path);
    }

    // Header
    file << "run_id,success,processing_time_sec,num_files,error_message\n";

    // Data
    auto results = getResults();
    for (const auto& pair : results) {
        const std::string& run_id = pair.first;
        const RunResult& result = pair.second;

        file << run_id << ","
             << (result.success ? "true" : "false") << ","
             << std::fixed << std::setprecision(2) << result.processing_time_sec << ","
             << result.generated_files.size() << ","
             << "\"" << result.error_message << "\"\n";
    }

    file.close();
}

// ============================================================
// Options
// ============================================================

void MultiRunProcessor::setOptions(const ProcessorOptions& options)
{
    options_ = options;

    // Recreate thread pool with new thread count
    if (options_.enable_parallel) {
        thread_pool_ = std::make_unique<ThreadPool>(options_.max_threads);
    }
}

void MultiRunProcessor::updateProgress()
{
    if (progress_callback_) {
        progress_callback_(progress_monitor_->getStatus());
    }
}

} // namespace render
} // namespace kood3plot
