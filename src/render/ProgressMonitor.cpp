/**
 * @file ProgressMonitor.cpp
 * @brief Progress monitoring implementation
 */

#include "kood3plot/render/ProgressMonitor.h"
#include <iostream>
#include <iomanip>
#include <sstream>

namespace kood3plot {
namespace render {

struct ProgressMonitor::Impl {
    size_t total_tasks;
    size_t completed_tasks;
    size_t failed_tasks;
    std::string current_task_id;
    std::chrono::time_point<std::chrono::high_resolution_clock> start_time;
    bool is_started;
    bool is_finished;
    mutable std::mutex mutex;

    Impl() : total_tasks(0), completed_tasks(0), failed_tasks(0),
             is_started(false), is_finished(false) {}
};

ProgressMonitor::ProgressMonitor(size_t total_tasks)
    : pImpl(std::make_unique<Impl>()) {
    pImpl->total_tasks = total_tasks;
}

ProgressMonitor::~ProgressMonitor() = default;

void ProgressMonitor::reset(size_t total_tasks) {
    std::lock_guard<std::mutex> lock(pImpl->mutex);
    pImpl->total_tasks = total_tasks;
    pImpl->completed_tasks = 0;
    pImpl->failed_tasks = 0;
    pImpl->current_task_id.clear();
    pImpl->is_started = false;
    pImpl->is_finished = false;
}

void ProgressMonitor::setTotalTasks(size_t total) {
    std::lock_guard<std::mutex> lock(pImpl->mutex);
    pImpl->total_tasks = total;
}

void ProgressMonitor::start() {
    std::lock_guard<std::mutex> lock(pImpl->mutex);
    pImpl->start_time = std::chrono::high_resolution_clock::now();
    pImpl->is_started = true;
    pImpl->is_finished = false;
}

void ProgressMonitor::startTask(const std::string& task_id) {
    std::lock_guard<std::mutex> lock(pImpl->mutex);
    if (!pImpl->is_started) {
        pImpl->start_time = std::chrono::high_resolution_clock::now();
        pImpl->is_started = true;
    }
    pImpl->current_task_id = task_id;
}

void ProgressMonitor::completeTask(const std::string& task_id, bool success) {
    std::lock_guard<std::mutex> lock(pImpl->mutex);
    if (success) {
        pImpl->completed_tasks++;
    } else {
        pImpl->failed_tasks++;
    }
    pImpl->current_task_id.clear();
}

void ProgressMonitor::failTask(const std::string& task_id) {
    completeTask(task_id, false);
}

void ProgressMonitor::update(size_t completed, size_t failed) {
    std::lock_guard<std::mutex> lock(pImpl->mutex);
    pImpl->completed_tasks = completed;
    pImpl->failed_tasks = failed;
}

void ProgressMonitor::finish() {
    std::lock_guard<std::mutex> lock(pImpl->mutex);
    pImpl->is_finished = true;
    pImpl->current_task_id.clear();
}

ProgressStatus ProgressMonitor::getStatus() const {
    std::lock_guard<std::mutex> lock(pImpl->mutex);

    ProgressStatus status;
    status.total_tasks = pImpl->total_tasks;
    status.completed_tasks = pImpl->completed_tasks;
    status.failed_tasks = pImpl->failed_tasks;
    status.current_task_id = pImpl->current_task_id;
    status.is_complete = pImpl->is_finished ||
                        (pImpl->completed_tasks + pImpl->failed_tasks >= pImpl->total_tasks);

    if (pImpl->total_tasks > 0) {
        status.percent_complete =
            (double)(pImpl->completed_tasks + pImpl->failed_tasks) / pImpl->total_tasks * 100.0;
    }

    if (pImpl->is_started) {
        auto now = std::chrono::high_resolution_clock::now();
        status.elapsed_time = std::chrono::duration<double>(now - pImpl->start_time).count();

        if (pImpl->completed_tasks > 0) {
            double avg = status.elapsed_time / pImpl->completed_tasks;
            size_t remaining = pImpl->total_tasks - pImpl->completed_tasks - pImpl->failed_tasks;
            status.estimated_remaining = avg * remaining;
        }
    }

    return status;
}

double ProgressMonitor::getPercentComplete() const {
    std::lock_guard<std::mutex> lock(pImpl->mutex);
    if (pImpl->total_tasks == 0) return 0.0;
    return (double)(pImpl->completed_tasks + pImpl->failed_tasks) / pImpl->total_tasks * 100.0;
}

size_t ProgressMonitor::getCompletedCount() const {
    std::lock_guard<std::mutex> lock(pImpl->mutex);
    return pImpl->completed_tasks;
}

size_t ProgressMonitor::getFailedCount() const {
    std::lock_guard<std::mutex> lock(pImpl->mutex);
    return pImpl->failed_tasks;
}

double ProgressMonitor::getElapsedTime() const {
    std::lock_guard<std::mutex> lock(pImpl->mutex);
    if (!pImpl->is_started) return 0.0;
    auto now = std::chrono::high_resolution_clock::now();
    return std::chrono::duration<double>(now - pImpl->start_time).count();
}

double ProgressMonitor::getEstimatedRemaining() const {
    std::lock_guard<std::mutex> lock(pImpl->mutex);
    if (!pImpl->is_started || pImpl->completed_tasks == 0) return -1.0;

    double elapsed = std::chrono::duration<double>(
        std::chrono::high_resolution_clock::now() - pImpl->start_time).count();
    double avg = elapsed / pImpl->completed_tasks;
    size_t remaining = pImpl->total_tasks - pImpl->completed_tasks - pImpl->failed_tasks;
    return avg * remaining;
}

bool ProgressMonitor::isComplete() const {
    std::lock_guard<std::mutex> lock(pImpl->mutex);
    return pImpl->is_finished ||
           (pImpl->completed_tasks + pImpl->failed_tasks >= pImpl->total_tasks);
}

std::string ProgressMonitor::getProgressBar(int width) const {
    std::lock_guard<std::mutex> lock(pImpl->mutex);
    if (width < 10) width = 10;

    double progress = 0.0;
    if (pImpl->total_tasks > 0) {
        progress = (double)(pImpl->completed_tasks + pImpl->failed_tasks) / pImpl->total_tasks;
    }

    int filled = (int)(progress * width);
    std::ostringstream bar;
    bar << "[";
    for (int i = 0; i < filled; ++i) bar << "=";
    if (filled < width) bar << ">";
    for (int i = filled + 1; i < width; ++i) bar << " ";
    bar << "] " << std::fixed << std::setprecision(1) << (progress * 100.0) << "%";

    return bar.str();
}

std::string ProgressMonitor::getStatusString() const {
    std::lock_guard<std::mutex> lock(pImpl->mutex);

    std::ostringstream ss;
    ss << "Progress: " << (pImpl->completed_tasks + pImpl->failed_tasks)
       << "/" << pImpl->total_tasks;

    if (pImpl->total_tasks > 0) {
        double pct = (double)(pImpl->completed_tasks + pImpl->failed_tasks) /
                     pImpl->total_tasks * 100.0;
        ss << " (" << std::fixed << std::setprecision(1) << pct << "%)";
    }

    if (pImpl->completed_tasks > 0) {
        ss << " | Success: " << pImpl->completed_tasks;
    }
    if (pImpl->failed_tasks > 0) {
        ss << " | Failed: " << pImpl->failed_tasks;
    }

    if (pImpl->is_started) {
        double elapsed = std::chrono::duration<double>(
            std::chrono::high_resolution_clock::now() - pImpl->start_time).count();
        ss << " | Time: " << formatTime(elapsed);

        if (pImpl->completed_tasks > 0 && !pImpl->is_finished) {
            double avg = elapsed / pImpl->completed_tasks;
            size_t remaining = pImpl->total_tasks - pImpl->completed_tasks - pImpl->failed_tasks;
            ss << " | ETA: " << formatTime(avg * remaining);
        }
    }

    if (!pImpl->current_task_id.empty()) {
        ss << " | Current: " << pImpl->current_task_id;
    }

    return ss.str();
}

void ProgressMonitor::displayConsole() const {
    std::cout << "\r" << getProgressBar(50) << " " << getStatusString() << std::flush;
}

std::string ProgressMonitor::formatTime(double seconds) const {
    if (seconds < 0) return "N/A";

    std::ostringstream ss;
    if (seconds < 60) {
        ss << std::fixed << std::setprecision(1) << seconds << "s";
    } else if (seconds < 3600) {
        int min = (int)(seconds / 60);
        int sec = (int)seconds % 60;
        ss << min << "m " << sec << "s";
    } else {
        int hr = (int)(seconds / 3600);
        int min = (int)((seconds - hr * 3600) / 60);
        ss << hr << "h " << min << "m";
    }
    return ss.str();
}

} // namespace render
} // namespace kood3plot
