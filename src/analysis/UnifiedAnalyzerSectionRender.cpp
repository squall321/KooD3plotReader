/**
 * @file UnifiedAnalyzerSectionRender.cpp
 * @brief processSectionViews() — real implementation compiled only when
 *        KOOD3PLOT_HAS_SECTION_RENDER is defined (KOOD3PLOT_BUILD_SECTION_RENDER=ON).
 *
 * This file is listed in the target_sources() of kood3plot_section_render so
 * it is compiled into that target (and therefore into unified_analyzer when the
 * option is ON). The stub in UnifiedAnalyzer.cpp is compiled only when this
 * define is absent.
 */

#ifdef KOOD3PLOT_HAS_SECTION_RENDER

#include "kood3plot/analysis/UnifiedAnalyzer.hpp"
#include "kood3plot/section_render/SectionViewConfig.hpp"
#include "kood3plot/section_render/SectionViewRenderer.hpp"

#include <atomic>
#include <mutex>
#include <thread>
#include <vector>

namespace kood3plot {
namespace analysis {

// ============================================================
// processSectionViews — reader-only (legacy, reads states internally)
// ============================================================

bool UnifiedAnalyzer::processSectionViews(
    D3plotReader& reader,
    const UnifiedConfig& config,
    UnifiedProgressCallback callback)
{
    if (config.section_views.empty()) return true;

    bool all_ok = true;

    for (const auto& spec : config.section_views) {
        if (!spec.enabled) {
            if (callback) callback("  [section_view] Skipping (disabled): " + spec.name);
            continue;
        }

        if (callback) callback("  [section_view] Starting: " + spec.name);

        section_render::SectionViewConfig sv_config;
        if (!sv_config.loadFromString(spec.yaml_block)) {
            if (callback) callback("  [section_view] YAML parse error: " + spec.name);
            all_ok = false;
            continue;
        }

        section_render::SectionViewRenderer renderer;
        std::string err = renderer.render(reader, sv_config);

        if (err.empty()) {
            if (callback) callback("  [section_view] Done: " + spec.name
                                   + " → " + sv_config.output_dir);
        } else {
            if (callback) callback("  [section_view] Error (" + spec.name + "): " + err);
            all_ok = false;
        }
    }

    return all_ok;
}

// ============================================================
// processSectionViews — pre-loaded states (parallel, zero-copy)
// ============================================================

bool UnifiedAnalyzer::processSectionViews(
    D3plotReader& reader,
    const UnifiedConfig& config,
    const std::vector<data::StateData>& all_states,
    UnifiedProgressCallback callback)
{
    if (config.section_views.empty()) return true;

    // Pre-load mesh and control data (shared across all jobs)
    data::Mesh mesh = reader.read_mesh();
    const data::ControlData& ctrl = reader.get_control_data();

    // Collect enabled jobs
    struct SvJob {
        std::string name;
        section_render::SectionViewConfig sv_config;
    };
    std::vector<SvJob> jobs;

    for (const auto& spec : config.section_views) {
        if (!spec.enabled) {
            if (callback) callback("  [section_view] Skipping (disabled): " + spec.name);
            continue;
        }

        SvJob job;
        job.name = spec.name;
        if (!job.sv_config.loadFromString(spec.yaml_block)) {
            if (callback) callback("  [section_view] YAML parse error: " + spec.name);
            continue;
        }
        jobs.push_back(std::move(job));
    }

    if (jobs.empty()) return true;

    // Single job → run directly (no thread overhead)
    if (jobs.size() == 1) {
        if (callback) callback("  [section_view] Starting: " + jobs[0].name);

        section_render::SectionViewRenderer renderer;
        std::string err = renderer.render(mesh, ctrl, all_states, jobs[0].sv_config);

        if (err.empty()) {
            if (callback) callback("  [section_view] Done: " + jobs[0].name
                                   + " → " + jobs[0].sv_config.output_dir);
            return true;
        } else {
            if (callback) callback("  [section_view] Error (" + jobs[0].name + "): " + err);
            return false;
        }
    }

    // Multiple jobs → run in parallel with thread pool (bounded concurrency)
    // Each worker gets its own renderer but shares mesh, ctrl, all_states (const&)
    size_t max_concurrent = std::max(1, config.sv_threads);
    if (max_concurrent > jobs.size()) max_concurrent = jobs.size();

    if (callback) callback("  [section_view] Running " + std::to_string(jobs.size())
                           + " section views (" + std::to_string(max_concurrent)
                           + " concurrent)...");

    std::vector<std::string> errors(jobs.size());
    std::mutex cb_mutex;

    // Work queue: atomic index for next job
    std::atomic<size_t> next_job{0};

    auto worker = [&]() {
        while (true) {
            size_t i = next_job.fetch_add(1);
            if (i >= jobs.size()) break;

            {
                std::lock_guard<std::mutex> lk(cb_mutex);
                if (callback) callback("  [section_view] Starting: " + jobs[i].name
                                       + " (" + std::to_string(i + 1) + "/"
                                       + std::to_string(jobs.size()) + ")");
            }

            section_render::SectionViewRenderer renderer;
            errors[i] = renderer.render(mesh, ctrl, all_states, jobs[i].sv_config);

            {
                std::lock_guard<std::mutex> lk(cb_mutex);
                if (errors[i].empty()) {
                    if (callback) callback("  [section_view] Done: " + jobs[i].name
                                           + " → " + jobs[i].sv_config.output_dir);
                } else {
                    if (callback) callback("  [section_view] Error (" + jobs[i].name
                                           + "): " + errors[i]);
                }
            }
        }
    };

    std::vector<std::thread> threads;
    threads.reserve(max_concurrent);
    for (size_t t = 0; t < max_concurrent; ++t)
        threads.emplace_back(worker);

    for (auto& t : threads)
        t.join();

    bool all_ok = true;
    for (const auto& e : errors) {
        if (!e.empty()) all_ok = false;
    }

    return all_ok;
}

} // namespace analysis
} // namespace kood3plot

#endif // KOOD3PLOT_HAS_SECTION_RENDER
