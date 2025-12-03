/**
 * @file BatchRenderer.cpp
 * @brief Batch processing implementation
 */

#include "kood3plot/render/BatchRenderer.h"
#include "kood3plot/render/ProgressMonitor.h"
#include <iostream>
#include <fstream>
#include <sstream>
#include <chrono>
#include <iomanip>

namespace kood3plot {
namespace render {

// ============================================================
// Implementation Structure
// ============================================================

struct BatchRenderer::Impl {
    std::vector<BatchJob> jobs;
    std::unique_ptr<LSPrePostRenderer> renderer;
    ProgressCallback progress_callback;
    size_t completed_count = 0;
    size_t failed_count = 0;
};

// ============================================================
// Constructor / Destructor
// ============================================================

BatchRenderer::BatchRenderer(const std::string& lsprepost_path)
    : pImpl(std::make_unique<Impl>())
{
    pImpl->renderer = std::make_unique<LSPrePostRenderer>(lsprepost_path);
}

BatchRenderer::~BatchRenderer() = default;

// ============================================================
// Job Management
// ============================================================

void BatchRenderer::addJob(const BatchJob& job) {
    pImpl->jobs.push_back(job);
}

void BatchRenderer::addJobs(const std::vector<BatchJob>& jobs) {
    pImpl->jobs.insert(pImpl->jobs.end(), jobs.begin(), jobs.end());
}

void BatchRenderer::clearJobs() {
    pImpl->jobs.clear();
    pImpl->completed_count = 0;
    pImpl->failed_count = 0;
}

size_t BatchRenderer::getJobCount() const {
    return pImpl->jobs.size();
}

// ============================================================
// Processing
// ============================================================

size_t BatchRenderer::processAll() {
    return processAll(nullptr);
}

size_t BatchRenderer::processAll(ProgressCallback callback) {
    pImpl->completed_count = 0;
    pImpl->failed_count = 0;

    auto start_time = std::chrono::high_resolution_clock::now();

    for (size_t i = 0; i < pImpl->jobs.size(); ++i) {
        auto& job = pImpl->jobs[i];

        // Notify progress
        if (callback) {
            double progress = (double)i / pImpl->jobs.size() * 100.0;
            callback(pImpl->completed_count, pImpl->jobs.size(), job.job_id, progress);
        }

        // Process job
        auto job_start = std::chrono::high_resolution_clock::now();

        bool success = false;
        if (job.options.create_animation) {
            success = pImpl->renderer->renderAnimation(
                job.d3plot_path, job.output_path, job.options
            );
        } else {
            success = pImpl->renderer->renderImage(
                job.d3plot_path, job.output_path, job.options
            );
        }

        auto job_end = std::chrono::high_resolution_clock::now();
        job.processing_time = std::chrono::duration<double>(job_end - job_start).count();

        // Update job status
        job.success = success;
        if (!success) {
            job.error_message = pImpl->renderer->getLastError();
            pImpl->failed_count++;
        } else {
            pImpl->completed_count++;
        }
    }

    // Final notification
    if (callback) {
        callback(pImpl->completed_count, pImpl->jobs.size(), "", 100.0);
    }

    return pImpl->completed_count;
}

void BatchRenderer::setProgressCallback(ProgressCallback callback) {
    pImpl->progress_callback = callback;
}

double BatchRenderer::getProgress() const {
    if (pImpl->jobs.empty()) return 0.0;
    size_t processed = pImpl->completed_count + pImpl->failed_count;
    return (double)processed / pImpl->jobs.size();
}

size_t BatchRenderer::getCompletedCount() const {
    return pImpl->completed_count;
}

size_t BatchRenderer::getFailedCount() const {
    return pImpl->failed_count;
}

// ============================================================
// Results
// ============================================================

std::vector<BatchJob> BatchRenderer::getJobs() const {
    return pImpl->jobs;
}

std::vector<BatchJob> BatchRenderer::getSuccessfulJobs() const {
    std::vector<BatchJob> result;
    for (const auto& job : pImpl->jobs) {
        if (job.success) {
            result.push_back(job);
        }
    }
    return result;
}

std::vector<BatchJob> BatchRenderer::getFailedJobs() const {
    std::vector<BatchJob> result;
    for (const auto& job : pImpl->jobs) {
        if (!job.success) {
            result.push_back(job);
        }
    }
    return result;
}

const BatchJob* BatchRenderer::getJob(const std::string& job_id) const {
    for (const auto& job : pImpl->jobs) {
        if (job.job_id == job_id) {
            return &job;
        }
    }
    return nullptr;
}

bool BatchRenderer::hasFailures() const {
    return pImpl->failed_count > 0;
}

std::map<std::string, std::string> BatchRenderer::getErrors() const {
    std::map<std::string, std::string> errors;
    for (const auto& job : pImpl->jobs) {
        if (!job.success && !job.error_message.empty()) {
            errors[job.job_id] = job.error_message;
        }
    }
    return errors;
}

// ============================================================
// Reporting
// ============================================================

std::string BatchRenderer::generateReport() const {
    std::ostringstream report;

    report << "==============================================\n";
    report << "Batch Render Report\n";
    report << "==============================================\n\n";

    report << "Total Jobs: " << pImpl->jobs.size() << "\n";
    report << "Successful: " << pImpl->completed_count << "\n";
    report << "Failed:     " << pImpl->failed_count << "\n\n";

    // Calculate total processing time
    double total_time = 0.0;
    for (const auto& job : pImpl->jobs) {
        total_time += job.processing_time;
    }

    report << "Total Processing Time: " << formatDuration(total_time) << "\n";
    report << "Average Time per Job:  ";
    if (!pImpl->jobs.empty()) {
        report << formatDuration(total_time / pImpl->jobs.size());
    } else {
        report << "N/A";
    }
    report << "\n\n";

    // Job details
    report << "Job Details:\n";
    report << "--------------------------------------------\n";
    for (const auto& job : pImpl->jobs) {
        report << "Job ID: " << job.job_id << "\n";
        report << "  Status: " << (job.success ? "SUCCESS" : "FAILED") << "\n";
        report << "  D3plot: " << job.d3plot_path << "\n";
        report << "  Output: " << job.output_path << "\n";
        report << "  Time:   " << formatDuration(job.processing_time) << "\n";
        if (!job.success && !job.error_message.empty()) {
            report << "  Error:  " << job.error_message << "\n";
        }
        report << "\n";
    }

    return report.str();
}

bool BatchRenderer::saveReport(const std::string& file_path) const {
    std::ofstream ofs(file_path);
    if (!ofs.is_open()) {
        return false;
    }

    ofs << generateReport();
    return true;
}

bool BatchRenderer::exportToCSV(const std::string& file_path) const {
    std::ofstream ofs(file_path);
    if (!ofs.is_open()) {
        return false;
    }

    // CSV Header
    ofs << "job_id,success,d3plot_path,output_path,processing_time,error_message\n";

    // CSV Data
    for (const auto& job : pImpl->jobs) {
        ofs << job.job_id << ","
            << (job.success ? "true" : "false") << ","
            << "\"" << job.d3plot_path << "\","
            << "\"" << job.output_path << "\","
            << job.processing_time << ","
            << "\"" << job.error_message << "\"\n";
    }

    return true;
}

// ============================================================
// Helper Methods
// ============================================================

std::string BatchRenderer::formatDuration(double seconds) const {
    std::ostringstream ss;
    if (seconds < 60) {
        ss << std::fixed << std::setprecision(2) << seconds << "s";
    } else if (seconds < 3600) {
        int minutes = (int)(seconds / 60);
        double secs = seconds - minutes * 60;
        ss << minutes << "m " << std::fixed << std::setprecision(1) << secs << "s";
    } else {
        int hours = (int)(seconds / 3600);
        int minutes = (int)((seconds - hours * 3600) / 60);
        ss << hours << "h " << minutes << "m";
    }
    return ss.str();
}

} // namespace render
} // namespace kood3plot
