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
#include <filesystem>
#include <algorithm>

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

// ============================================================
// processSetViews — Custom Report 세트 뷰 (3면 탑뷰 영상 + 피크 스냅샷)
// ============================================================
//
// 세트마다 planes × {von_mises, eff_plastic_strain} 조합으로 PartTopView 를
// 렌더한다. 스냅샷 상태는 finalizeSetReports 가 구한 피크 상태 인덱스 —
// C++ 이 피크를 알고 있으므로 Python 오케스트레이션 없이 정확한 시각을 찍는다.
// 산출물 규약 (per-run):
//   <output>/set_reports/<safe_name>/view_<plane>_<field>.mp4
//   <output>/set_reports/<safe_name>/peak_<plane>_<field>.png

void UnifiedAnalyzer::processSetViews(
    D3plotReader& reader,
    const UnifiedConfig& config,
    const std::vector<data::StateData>& all_states,
    ExtendedAnalysisResult& result,
    UnifiedProgressCallback callback)
{
    namespace fs = std::filesystem;
    (void)reader;

    if (config.output_directory.empty()) {
        for (auto& sr : result.set_report_results) {
            if (!sr.resolved_parts.empty()) {
                sr.notes.push_back("세트 뷰 미생성 — output.directory 미지정");
            }
        }
        return;
    }

    auto mesh = reader.read_mesh();
    const auto& ctrl = reader.get_control_data();

    // 뷰 대상 필드 — 렌더러(FieldSelector)가 지원하는 것만
    struct ViewField {
        const char* name;
        section_render::FieldSelector sel;
    };
    const ViewField kViewFields[] = {
        {"von_mises",          section_render::FieldSelector::VonMises},
        {"eff_plastic_strain", section_render::FieldSelector::EffectivePlasticStrain},
    };

    auto planeAxis = [](const std::string& plane) -> char {
        if (plane == "xy") return 'z';
        if (plane == "yz") return 'x';
        return 'y';   // zx
    };

    for (size_t si = 0; si < result.set_report_results.size(); ++si) {
        auto& sr = result.set_report_results[si];
        if (sr.resolved_parts.empty()) continue;   // 사유는 이미 notes 에

        const SetReportSpec spec = (si < config.set_reports.size())
                                   ? config.set_reports[si]
                                   : SetReportSpec{};
        if (!spec.video && !spec.peak_snapshot) continue;

        const std::string set_dir = config.output_directory + "/set_reports/" +
                                    sanitizeSetName(sr.name);
        std::error_code ec;
        fs::create_directories(set_dir, ec);

        for (const auto& vf : kViewFields) {
            // 요청 필드 필터 (비우면 전부)
            if (!spec.fields.empty() &&
                std::find(spec.fields.begin(), spec.fields.end(),
                          std::string(vf.name)) == spec.fields.end()) {
                continue;
            }

            // 이 필드의 피크 상태 (지표에서)
            int32_t peak_state = -1;
            for (const auto& fr : sr.fields) {
                if (fr.field == vf.name && fr.measured) { peak_state = fr.peak_state; break; }
            }

            for (const auto& plane : spec.planes) {
                if (callback) {
                    callback("  Set view [" + sr.name + "] " + plane + "/" + vf.name + "...");
                }

                section_render::SectionViewConfig sv;
                sv.view_mode = section_render::SectionViewMode::PartTopView;
                sv.use_axis = true;
                sv.axis = planeAxis(plane);
                sv.field = vf.sel;
                sv.width = spec.width;
                sv.height = spec.height;
                sv.global_range = true;          // 영상·스냅샷 컬러바 통일
                sv.mp4 = spec.video;
                sv.png_frames = false;
                sv.snapshot_state = spec.peak_snapshot ? peak_state : -1;
                sv.max_frames = spec.max_frames;
                for (int32_t pid : sr.resolved_parts) sv.target_parts.addById(pid);

                // 임시 하위 폴더에 렌더 후 규약 이름으로 옮긴다
                const std::string tmp_dir = set_dir + "/_render_" + plane + "_" + vf.name;
                sv.output_dir = tmp_dir;

                section_render::SectionViewRenderer renderer;
                const std::string err = renderer.render(mesh, ctrl, all_states, sv);
                if (!err.empty()) {
                    sr.notes.push_back("뷰 실패 [" + plane + "/" + vf.name + "]: " + err);
                    fs::remove_all(tmp_dir, ec);
                    continue;
                }

                if (spec.video) {
                    fs::rename(tmp_dir + "/section_view.mp4",
                               set_dir + "/view_" + plane + "_" + vf.name + ".mp4", ec);
                    if (ec) sr.notes.push_back("뷰 이동 실패 [" + plane + "/" + vf.name + "]");
                }
                if (spec.peak_snapshot && peak_state >= 0) {
                    fs::rename(tmp_dir + "/snapshot.png",
                               set_dir + "/peak_" + plane + "_" + vf.name + ".png", ec);
                    if (ec) sr.notes.push_back("스냅샷 이동 실패 [" + plane + "/" + vf.name + "]");
                } else if (spec.peak_snapshot && peak_state < 0) {
                    sr.notes.push_back("스냅샷 생략 [" + plane + "/" + vf.name +
                                       "] — 피크 상태 미산출");
                }
                fs::remove_all(tmp_dir, ec);
            }
        }
    }
}

} // namespace analysis
} // namespace kood3plot

#endif // KOOD3PLOT_HAS_SECTION_RENDER
