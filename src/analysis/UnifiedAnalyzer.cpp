/**
 * @file UnifiedAnalyzer.cpp
 * @brief Unified job-based analyzer implementation
 *
 * Note: processRenderJobs is implemented in UnifiedAnalyzerRender.cpp
 * to avoid circular dependency with kood3plot_render library.
 */

#include "kood3plot/analysis/UnifiedAnalyzer.hpp"
#include "kood3plot/analysis/UnifiedConfigParser.hpp"
#include "kood3plot/analysis/PartAnalyzer.hpp"
#include "kood3plot/analysis/TimeHistoryAnalyzer.hpp"
#include "kood3plot/analysis/SinglePassAnalyzer.hpp"
#include "kood3plot/analysis/SurfaceStressAnalyzer.hpp"
#include "kood3plot/analysis/SurfaceExtractor.hpp"
#include "kood3plot/analysis/BeamAnalyzer.hpp"
#include "kood3plot/parsers/KeywordSetParser.hpp"
#include "kood3plot/data/NodeKinematics.hpp"
#include "kood3plot/Version.hpp"
#include <algorithm>
#include <cmath>
#include <limits>
#include <map>
#include <tuple>
#include <utility>
#include <filesystem>
#include <set>

#ifdef _OPENMP
#include <omp.h>
#endif

namespace kood3plot {
namespace analysis {

ExtendedAnalysisResult UnifiedAnalyzer::analyze(const UnifiedConfig& config) {
    return analyze(config, nullptr);
}

ExtendedAnalysisResult UnifiedAnalyzer::analyze(const UnifiedConfig& config, UnifiedProgressCallback callback) {
    success_ = false;
    last_error_.clear();
    ExtendedAnalysisResult result;

    // Validate configuration
    if (config.d3plot_path.empty()) {
        last_error_ = "d3plot path is required";
        return result;
    }

    if (config.analysis_jobs.empty() && config.render_jobs.empty() &&
        config.section_views.empty() && config.set_reports.empty()) {
        last_error_ = "No analysis or render jobs defined";
        return result;
    }

    if (callback) callback("Opening d3plot file...");

    // Open d3plot file
    D3plotReader reader(config.d3plot_path);
    ErrorCode err = reader.open();
    if (err != ErrorCode::SUCCESS) {
        last_error_ = "Failed to open d3plot file";
        return result;
    }

    if (callback) callback("Reading all states (parallel)...");

    // Read all states in parallel (family files read concurrently)
    auto all_states = reader.read_all_states_parallel(config.num_threads);
    if (all_states.empty()) {
        last_error_ = "No states found in d3plot";
        return result;
    }

    if (callback) {
        callback("Read " + std::to_string(all_states.size()) + " states");
    }

    // Categorize jobs by type
    std::vector<AnalysisJob> stress_jobs;
    std::vector<AnalysisJob> strain_jobs;
    std::vector<AnalysisJob> motion_jobs;
    std::vector<AnalysisJob> surface_stress_jobs;
    std::vector<AnalysisJob> surface_strain_jobs;
    std::vector<AnalysisJob> beam_jobs;

    for (const auto& job : config.analysis_jobs) {
        switch (job.type) {
            case AnalysisJobType::VON_MISES:
                stress_jobs.push_back(job);
                break;
            case AnalysisJobType::EFF_PLASTIC_STRAIN:
                strain_jobs.push_back(job);
                break;
            case AnalysisJobType::PART_MOTION:
                motion_jobs.push_back(job);
                break;
            case AnalysisJobType::SURFACE_STRESS:
                surface_stress_jobs.push_back(job);
                break;
            case AnalysisJobType::SURFACE_STRAIN:
                surface_strain_jobs.push_back(job);
                break;
            case AnalysisJobType::BEAM_FORCE:
                beam_jobs.push_back(job);
                break;
            case AnalysisJobType::COMPREHENSIVE:
                // Comprehensive jobs get split into multiple categories
                if (job.requiresStress()) {
                    AnalysisJob stress_job = job;
                    stress_job.type = AnalysisJobType::VON_MISES;
                    stress_jobs.push_back(stress_job);
                }
                if (job.requiresStrain()) {
                    AnalysisJob strain_job = job;
                    strain_job.type = AnalysisJobType::EFF_PLASTIC_STRAIN;
                    strain_jobs.push_back(strain_job);
                }
                if (job.requiresDisplacement()) {
                    AnalysisJob motion_job = job;
                    motion_job.type = AnalysisJobType::PART_MOTION;
                    motion_jobs.push_back(motion_job);
                }
                break;
        }
    }

    // 표면 방향 분석 기본값 주입.
    // 사용자가 surface_stress/surface_strain 잡을 하나도 안 적었을 때만 개입한다
    // (하나라도 적었으면 그 의도를 존중해 그대로 둔다). 낙하/충격에서 바닥면
    // -Z 와 상면 +Z 는 사실상 항상 관심 대상이라 기본으로 뽑아 둔다.
    if (config.surface_defaults && surface_stress_jobs.empty() && surface_strain_jobs.empty()) {
        const double ang = config.surface_default_angle;
        const std::pair<Vec3, const char*> defaults[] = {
            {Vec3(0, 0, -1), "Bottom (-Z)"},
            {Vec3(0, 0,  1), "Top (+Z)"},
        };
        for (const auto& d : defaults) {
            AnalysisJob j;
            j.name = d.second;
            j.surface.direction = d.first;
            j.surface.angle = ang;
            j.type = AnalysisJobType::SURFACE_STRESS;
            surface_stress_jobs.push_back(j);
            j.type = AnalysisJobType::SURFACE_STRAIN;
            surface_strain_jobs.push_back(j);
        }
        if (callback) {
            callback("표면 방향 분석 기본값 적용: ±Z 각도 " + std::to_string(static_cast<int>(ang)) +
                     "° (응력·변형률 각 2방향). 끄려면 surface_defaults: false");
        }
    }

    // Custom Report: 세트 해석 + 파트셋 파트를 solid 잡에 주입.
    // 세트 파트가 stress/strain 잡에 없으면 per-part 이력이 안 생겨 집계가
    // 조용히 비므로, 전용 잡을 항상 주입한다 (processSolidJobs 는 잡들의
    // 파트 합집합으로 한 번만 돌기 때문에 중복 비용은 없다).
    {
        std::vector<int32_t> set_parts = prepareSetReports(reader, config, result, callback);
        if (!set_parts.empty()) {
            AnalysisJob j;
            j.name = "__set_report_auto";
            j.part_ids = set_parts;
            j.type = AnalysisJobType::VON_MISES;
            stress_jobs.push_back(j);
            j.type = AnalysisJobType::EFF_PLASTIC_STRAIN;
            strain_jobs.push_back(j);
        }
    }

    // Count total analysis steps for progress reporting
    int total_steps = 0;
    bool has_solid_jobs = !stress_jobs.empty() || !strain_jobs.empty();
    if (has_solid_jobs) total_steps++;  // single pass for stress + strain
    if (!motion_jobs.empty()) total_steps++;
    if (!surface_stress_jobs.empty()) total_steps++;
    if (!surface_strain_jobs.empty()) total_steps++;
    if (!beam_jobs.empty()) total_steps++;

    std::vector<AnalysisJob> quality_jobs;
    for (const auto& job : config.analysis_jobs) {
        if (job.type == AnalysisJobType::ELEMENT_QUALITY) {
            quality_jobs.push_back(job);
        }
    }
    if (!quality_jobs.empty()) total_steps++;
    if (config.hasSectionViews()) total_steps++;
    total_steps++; // metadata

    int current_step = 0;

    // Single-pass solid element analysis: stress + strain + principal in one loop
    if (has_solid_jobs) {
        current_step++;
        if (callback) callback("[Step " + std::to_string(current_step) + "/" + std::to_string(total_steps) + "] Solid analysis (" + std::to_string(all_states.size()) + " states, single pass)...");
        processSolidJobs(reader, stress_jobs, strain_jobs, all_states, result, callback);
    }

    // Custom Report 집계 (solid 이력이 준비된 직후) + 세트 뷰 렌더
    if (!result.set_report_results.empty()) {
        finalizeSetReports(config, result, callback);
        computeDirectSetMetrics(reader, all_states, result, callback);
        processSetViews(reader, config, all_states, result, callback);
    }

    if (!motion_jobs.empty()) {
        current_step++;
        if (callback) callback("[Step " + std::to_string(current_step) + "/" + std::to_string(total_steps) + "] Motion analysis (" + std::to_string(all_states.size()) + " states x " + std::to_string(motion_jobs.size()) + " jobs)...");
        processMotionJobs(reader, motion_jobs, all_states, result, callback);
    }

    if (!surface_stress_jobs.empty()) {
        current_step++;
        if (callback) callback("[Step " + std::to_string(current_step) + "/" + std::to_string(total_steps) + "] Surface stress analysis...");
        processSurfaceStressJobs(reader, surface_stress_jobs, all_states, result, callback);
    }

    if (!surface_strain_jobs.empty()) {
        current_step++;
        if (callback) callback("[Step " + std::to_string(current_step) + "/" + std::to_string(total_steps) + "] Surface strain analysis...");
        processSurfaceStrainJobs(reader, surface_strain_jobs, all_states, result, callback);
    }

    if (!beam_jobs.empty()) {
        current_step++;
        if (callback) callback("[Step " + std::to_string(current_step) + "/" + std::to_string(total_steps) + "] Beam force analysis...");
        processBeamJobs(reader, beam_jobs, all_states, result, callback);
    }

    if (!quality_jobs.empty()) {
        current_step++;
        if (callback) callback("[Step " + std::to_string(current_step) + "/" + std::to_string(total_steps) + "] Element quality analysis...");
        processElementQualityJobs(reader, quality_jobs, all_states, result, callback);
    }

    // Section view jobs — run here to share all_states (no d3plot re-read)
    if (config.hasSectionViews()) {
        current_step++;
        if (callback) callback("[Step " + std::to_string(current_step) + "/" + std::to_string(total_steps) + "] Section view rendering...");
        processSectionViews(reader, config, all_states, callback);
        section_views_done_ = true;
    }

    // Fill metadata
    current_step++;
    if (callback) callback("[Step " + std::to_string(current_step) + "/" + std::to_string(total_steps) + "] Collecting metadata...");
    fillMetadata(reader, config, all_states, result);

    // Note: render jobs are processed separately in unified_analyzer.cpp main,
    // not here, to avoid double-execution.

    success_ = true;
    if (callback) callback("Analysis complete!");

    return result;
}

void UnifiedAnalyzer::processSolidJobs(
    D3plotReader& reader,
    const std::vector<AnalysisJob>& stress_jobs,
    const std::vector<AnalysisJob>& strain_jobs,
    const std::vector<data::StateData>& all_states,
    ExtendedAnalysisResult& result,
    UnifiedProgressCallback callback
) {
    bool do_stress = !stress_jobs.empty();
    bool do_strain = !strain_jobs.empty();

    // Collect requested part IDs from both stress and strain jobs
    std::vector<int32_t> requested_parts;
    bool want_all = false;

    auto collect_parts = [&](const std::vector<AnalysisJob>& jobs) {
        for (const auto& job : jobs) {
            if (job.part_ids.empty() && job.part_pattern.empty()) {
                want_all = true;
                return;
            }
            for (int32_t pid : job.part_ids) {
                if (std::find(requested_parts.begin(), requested_parts.end(), pid) == requested_parts.end()) {
                    requested_parts.push_back(pid);
                }
            }
            if (!job.part_pattern.empty()) {
                auto pattern_parts = UnifiedConfigParser::filterPartsByPattern(reader, job.part_pattern);
                for (int32_t pid : pattern_parts) {
                    if (std::find(requested_parts.begin(), requested_parts.end(), pid) == requested_parts.end()) {
                        requested_parts.push_back(pid);
                    }
                }
            }
        }
    };

    collect_parts(stress_jobs);
    if (!want_all) collect_parts(strain_jobs);

    // Single-pass: Von Mises + Principal stress + Eff. plastic strain + Principal strain
    if (callback) {
        std::string desc;
        if (do_stress && do_strain) desc = "stress + strain";
        else if (do_stress) desc = "stress";
        else desc = "strain";
        callback("  Single-pass solid analysis: " + desc + " (" + std::to_string(all_states.size()) + " states)...");
    }

    SinglePassAnalyzer sp_analyzer(reader);
    AnalysisConfig sp_config;
    sp_config.analyze_stress = do_stress;
    sp_config.analyze_strain = do_strain;
    sp_config.part_ids = want_all ? std::vector<int32_t>{} : requested_parts;

    auto sp_result = sp_analyzer.analyzeWithStates(sp_config, all_states,
        [&callback](size_t current, size_t total, const std::string&) {
            if (callback && (current % 20 == 0 || current == total)) {
                callback("    Solid analysis: state " + std::to_string(current) + "/" + std::to_string(total));
            }
        });

    // Move stress results (Von Mises + principal stress + tensors)
    if (do_stress) {
        result.stress_history = std::move(sp_result.stress_history);
        result.max_principal_history = std::move(sp_result.max_principal_history);
        result.min_principal_history = std::move(sp_result.min_principal_history);
        result.peak_element_tensors = std::move(sp_result.peak_element_tensors);

        if (callback) {
            callback("  Stress: " + std::to_string(result.stress_history.size()) + " parts, " +
                     "Principal: " + std::to_string(result.max_principal_history.size()) + " parts, " +
                     "Tensors: " + std::to_string(result.peak_element_tensors.size()) + " elements");
        }
    }

    // Move strain results (eff. plastic + principal strain)
    if (do_strain) {
        result.strain_history = std::move(sp_result.strain_history);
        result.vm_strain_history = std::move(sp_result.vm_strain_history);
        result.max_principal_strain_history = std::move(sp_result.max_principal_strain_history);
        result.min_principal_strain_history = std::move(sp_result.min_principal_strain_history);

        if (callback) {
            callback("  Strain: " + std::to_string(result.strain_history.size()) + " parts");
        }
    }
}

void UnifiedAnalyzer::processMotionJobs(
    D3plotReader& reader,
    const std::vector<AnalysisJob>& jobs,
    const std::vector<data::StateData>& all_states,
    ExtendedAnalysisResult& result,
    UnifiedProgressCallback callback
) {
    // Collect all part IDs (empty means all, or use part_pattern)
    std::vector<int32_t> all_parts;
    bool want_all = false;
    for (const auto& job : jobs) {
        if (job.part_ids.empty() && job.part_pattern.empty()) {
            want_all = true;
            all_parts.clear();
            break;
        }
        // Add explicit part IDs
        for (int32_t pid : job.part_ids) {
            if (std::find(all_parts.begin(), all_parts.end(), pid) == all_parts.end()) {
                all_parts.push_back(pid);
            }
        }
        // Add parts matching pattern
        if (!job.part_pattern.empty()) {
            auto pattern_parts = UnifiedConfigParser::filterPartsByPattern(reader, job.part_pattern);
            for (int32_t pid : pattern_parts) {
                if (std::find(all_parts.begin(), all_parts.end(), pid) == all_parts.end()) {
                    all_parts.push_back(pid);
                }
            }
        }
    }

    // Use MotionAnalyzer
    MotionAnalyzer analyzer(reader);
    if (!want_all) {
        analyzer.setParts(all_parts);
    }

    if (!analyzer.initialize()) {
        if (callback) callback("  Motion: Failed to initialize - " + analyzer.getLastError());
        return;
    }

    // Process each state
    for (size_t i = 0; i < all_states.size(); ++i) {
        analyzer.processState(all_states[i]);

        if (callback && (i == 0 || i == all_states.size() - 1 || (i + 1) % 20 == 0)) {
            callback("    Motion: state " + std::to_string(i + 1) + "/" + std::to_string(all_states.size()));
        }
    }

    // Get results
    result.motion_analysis = analyzer.getResults();
}

void UnifiedAnalyzer::processSurfaceStressJobs(
    D3plotReader& reader,
    const std::vector<AnalysisJob>& jobs,
    const std::vector<data::StateData>& all_states,
    ExtendedAnalysisResult& result,
    UnifiedProgressCallback callback
) {
    // 표면 응력/변형률은 **솔리드** 요소의 외피에서 뽑는다. 솔리드가 없는
    // 모델(순수 셸)에서는 solid_data 가 비어 있어 전 항목이 0 으로 나가고,
    // 보고서에서는 '응력 0' 으로 읽힌다. 사유를 남기고 산출물을 만들지 않는다.
    if (all_states.empty() || all_states.front().solid_data.empty()) {
        if (callback) {
            callback("  Surface stress: 솔리드 요소 데이터 없음 (순수 셸 모델로 보임) — "
                     "표면 분석은 솔리드 외피 기준이라 건너뜁니다");
        }
        return;
    }

    // Use SurfaceExtractor to get exterior surfaces
    SurfaceExtractor extractor(reader);
    if (!extractor.initialize()) {
        if (callback) callback("  Surface stress: Failed to initialize extractor - " + extractor.getLastError());
        return;
    }

    // Use SurfaceStressAnalyzer for stress calculation
    SurfaceStressAnalyzer surf_analyzer(reader);

    for (const auto& job : jobs) {
        if (callback) callback("  Surface stress: " + job.name);

        // Collect part IDs (empty means all, or use part_pattern)
        std::vector<int32_t> target_parts = job.part_ids;
        if (!job.part_pattern.empty()) {
            auto pattern_parts = UnifiedConfigParser::filterPartsByPattern(reader, job.part_pattern);
            for (int32_t pid : pattern_parts) {
                if (std::find(target_parts.begin(), target_parts.end(), pid) == target_parts.end()) {
                    target_parts.push_back(pid);
                }
            }
        }

        // Extract faces for this surface
        SurfaceExtractionResult extraction;
        if (target_parts.empty()) {
            extraction = extractor.extractExteriorSurfaces();
        } else {
            extraction = extractor.extractExteriorSurfaces(target_parts);
        }

        // Filter by direction
        auto filtered = SurfaceExtractor::filterByDirection(extraction.faces, job.surface.direction, job.surface.angle);

        if (filtered.empty()) {
            // 무음 스킵 금지 — 방향/각도가 아무 면도 못 잡았다는 사실을 남긴다.
            if (callback) {
                callback("  Surface stress [" + job.name + "]: 조건에 맞는 면 0개 "
                         "(방향 " + std::to_string(job.surface.direction.x) + "," +
                         std::to_string(job.surface.direction.y) + "," +
                         std::to_string(job.surface.direction.z) + " / 각도 " +
                         std::to_string(job.surface.angle) + "°) — 건너뜀");
            }
            continue;
        }

        SurfaceAnalysisStats stats;
        stats.description = job.name;
        stats.reference_direction = job.surface.direction;
        stats.angle_threshold_degrees = job.surface.angle;
        stats.part_ids = job.part_ids;
        stats.num_faces = static_cast<int32_t>(filtered.size());

        // Process each state using SurfaceStressAnalyzer
        for (size_t si = 0; si < all_states.size(); ++si) {
            const auto& state = all_states[si];
            // Use the analyzeState method that takes faces and state
            SurfaceStressStats stress_stats = surf_analyzer.analyzeState(filtered, state);

            SurfaceTimePointStats tp;
            tp.time = state.time;
            tp.normal_stress_max = stress_stats.normal_stress_max;
            tp.normal_stress_min = stress_stats.normal_stress_min;
            tp.normal_stress_avg = stress_stats.normal_stress_avg;
            tp.normal_stress_max_element_id = stress_stats.normal_stress_max_element;
            tp.shear_stress_max = stress_stats.shear_stress_max;
            tp.shear_stress_avg = stress_stats.shear_stress_avg;
            tp.shear_stress_max_element_id = stress_stats.shear_stress_max_element;
            tp.von_mises_max = stress_stats.von_mises_max;
            tp.von_mises_min = stress_stats.von_mises_min;
            tp.von_mises_avg = stress_stats.von_mises_avg;
            tp.von_mises_max_element_id = stress_stats.von_mises_max_element;
            tp.max_principal_max = stress_stats.max_principal_max;
            tp.max_principal_min = stress_stats.max_principal_min;
            tp.max_principal_avg = stress_stats.max_principal_avg;
            tp.max_principal_max_element_id = stress_stats.max_principal_max_element;
            tp.min_principal_max = stress_stats.min_principal_max;
            tp.min_principal_min = stress_stats.min_principal_min;
            tp.min_principal_avg = stress_stats.min_principal_avg;
            tp.min_principal_min_element_id = stress_stats.min_principal_min_element;

            stats.data.push_back(tp);

            if (callback && (si == 0 || si == all_states.size() - 1 || (si + 1) % 20 == 0)) {
                callback("    Surface stress [" + job.name + "]: state " + std::to_string(si + 1) + "/" + std::to_string(all_states.size()));
            }
        }

        result.surface_analysis.push_back(stats);
    }
}

void UnifiedAnalyzer::processSurfaceStrainJobs(
    D3plotReader& reader,
    const std::vector<AnalysisJob>& jobs,
    const std::vector<data::StateData>& all_states,
    ExtendedAnalysisResult& result,
    UnifiedProgressCallback callback
) {
    // 표면 응력/변형률은 **솔리드** 요소의 외피에서 뽑는다. 솔리드가 없는
    // 모델(순수 셸)에서는 solid_data 가 비어 있어 전 항목이 0 으로 나가고,
    // 보고서에서는 '응력 0' 으로 읽힌다. 사유를 남기고 산출물을 만들지 않는다.
    if (all_states.empty() || all_states.front().solid_data.empty()) {
        if (callback) {
            callback("  Surface strain: 솔리드 요소 데이터 없음 (순수 셸 모델로 보임) — "
                     "표면 분석은 솔리드 외피 기준이라 건너뜁니다");
        }
        return;
    }

    // Use SurfaceStrainAnalyzer
    SurfaceStrainAnalyzer analyzer(reader);

    // Add all surface specifications
    for (const auto& job : jobs) {
        // Collect part IDs (empty means all, or use part_pattern)
        std::vector<int32_t> target_parts = job.part_ids;
        if (!job.part_pattern.empty()) {
            auto pattern_parts = UnifiedConfigParser::filterPartsByPattern(reader, job.part_pattern);
            for (int32_t pid : pattern_parts) {
                if (std::find(target_parts.begin(), target_parts.end(), pid) == target_parts.end()) {
                    target_parts.push_back(pid);
                }
            }
        }
        analyzer.addSurface(job.name, job.surface.direction, job.surface.angle, target_parts);
    }

    if (!analyzer.initialize()) {
        if (callback) callback("  Surface strain: Failed to initialize - " + analyzer.getLastError());
        return;
    }

    // Process each state
    for (size_t i = 0; i < all_states.size(); ++i) {
        analyzer.processState(all_states[i]);

        if (callback && (i == 0 || i == all_states.size() - 1 || (i + 1) % 20 == 0)) {
            callback("    Surface strain: state " + std::to_string(i + 1) + "/" + std::to_string(all_states.size()));
        }
    }

    // Get results
    result.surface_strain_analysis = analyzer.getResults();
}

// ============================================================
// Element Quality Computation Helpers
// ============================================================

namespace {

struct Vec3Q {
    double x = 0, y = 0, z = 0;
    Vec3Q() = default;
    Vec3Q(double a, double b, double c) : x(a), y(b), z(c) {}
    Vec3Q operator-(const Vec3Q& o) const { return {x-o.x, y-o.y, z-o.z}; }
    Vec3Q operator+(const Vec3Q& o) const { return {x+o.x, y+o.y, z+o.z}; }
    Vec3Q operator*(double s) const { return {x*s, y*s, z*s}; }
    double dot(const Vec3Q& o) const { return x*o.x + y*o.y + z*o.z; }
    Vec3Q cross(const Vec3Q& o) const {
        return {y*o.z - z*o.y, z*o.x - x*o.z, x*o.y - y*o.x};
    }
    double mag() const { return std::sqrt(x*x + y*y + z*z); }
};

// Get current position of node (initial + displacement)
Vec3Q getNodePos(const data::Mesh& mesh, const data::StateData& state, size_t node_idx) {
    // 이름과 달리 state.node_displacements 에는 **현재 좌표**가 들어 있다
    // (IU=1). SurfaceExtractor::getNodePosition 은 원래부터 그렇게 읽는다.
    // 여기서는 초기좌표에 더하고 있어서 실제로는 2·X0 + u 위에서 품질 지표를
    // 계산했다 — t=0 에 체적비가 1.0 이 아니라 2³=8 로 나오던 원인이다.
    if (!state.node_displacements.empty() && node_idx * 3 + 2 < state.node_displacements.size()) {
        return {state.node_displacements[node_idx * 3 + 0],
                state.node_displacements[node_idx * 3 + 1],
                state.node_displacements[node_idx * 3 + 2]};
    }
    return {mesh.nodes[node_idx].x, mesh.nodes[node_idx].y, mesh.nodes[node_idx].z};
}

Vec3Q getNodeInitialPos(const data::Mesh& mesh, size_t node_idx) {
    return {mesh.nodes[node_idx].x, mesh.nodes[node_idx].y, mesh.nodes[node_idx].z};
}

// Aspect ratio: max edge length / min edge length
std::pair<double, bool> computeAspectRatio4(const Vec3Q& p0, const Vec3Q& p1, const Vec3Q& p2, const Vec3Q& p3) {
    double edges[4] = {
        (p1 - p0).mag(), (p2 - p1).mag(), (p3 - p2).mag(), (p0 - p3).mag()
    };
    double mn = edges[0], mx = edges[0];
    for (int i = 1; i < 4; ++i) {
        if (edges[i] < mn) mn = edges[i];
        if (edges[i] > mx) mx = edges[i];
    }
    // 상대 임계값 — computeAspectRatio8 과 같은 이유 (붕괴 요소 제외)
    if (mn <= 1e-20 || mn <= mx * 1e-9) return {0.0, false};
    return {mx / mn, true};
}

// Skewness for quad: max deviation of corner angles from 90 degrees / 90
double computeSkewness4(const Vec3Q& p0, const Vec3Q& p1, const Vec3Q& p2, const Vec3Q& p3) {
    auto angle = [](const Vec3Q& a, const Vec3Q& b, const Vec3Q& c) -> double {
        Vec3Q ba = a - b, bc = c - b;
        double d = ba.dot(bc);
        double m = ba.mag() * bc.mag();
        if (m < 1e-20) return 0;
        double cosA = std::max(-1.0, std::min(1.0, d / m));
        return std::acos(cosA) * 180.0 / 3.14159265358979;
    };
    double angles[4] = {
        angle(p3, p0, p1), angle(p0, p1, p2), angle(p1, p2, p3), angle(p2, p3, p0)
    };
    double max_dev = 0;
    for (int i = 0; i < 4; ++i) {
        double dev = std::abs(angles[i] - 90.0) / 90.0;
        if (dev > max_dev) max_dev = dev;
    }
    return max_dev;
}

// Warpage for quad: angle between normals of two triangles
double computeWarpage4(const Vec3Q& p0, const Vec3Q& p1, const Vec3Q& p2, const Vec3Q& p3) {
    Vec3Q n1 = (p1 - p0).cross(p2 - p0);
    Vec3Q n2 = (p2 - p0).cross(p3 - p0);
    double m1 = n1.mag(), m2 = n2.mag();
    if (m1 < 1e-20 || m2 < 1e-20) return 0;
    double cosA = std::max(-1.0, std::min(1.0, n1.dot(n2) / (m1 * m2)));
    return std::acos(cosA) * 180.0 / 3.14159265358979;
}

// Area of quad (sum of two triangle areas)
double computeArea4(const Vec3Q& p0, const Vec3Q& p1, const Vec3Q& p2, const Vec3Q& p3) {
    return 0.5 * ((p1 - p0).cross(p2 - p0).mag() + (p2 - p0).cross(p3 - p0).mag());
}

// 8절점 hex 의 부호 있는 부피 (5-사면체 분해).
// wedge(6고유) / pyramid(5고유) 축퇴에도 성립한다 — 겹친 절점이 만드는 항이
// 0 이 되어 자연스럽게 3-tet / 2-tet 분해로 떨어진다.
// **단 tet(4고유) 은 성립하지 않는다** → computeSolidVolume 참고.
double computeHexVolume(const Vec3Q* p) {
    // 8-node hex volume via 5-tetrahedron decomposition
    auto tetVol = [](const Vec3Q& a, const Vec3Q& b, const Vec3Q& c, const Vec3Q& d) -> double {
        return (b - a).dot((c - a).cross(d - a)) / 6.0;
    };
    double vol = tetVol(p[0], p[1], p[3], p[4])
               + tetVol(p[1], p[2], p[3], p[6])
               + tetVol(p[1], p[4], p[5], p[6])
               + tetVol(p[3], p[4], p[6], p[7])
               + tetVol(p[1], p[3], p[4], p[6]);
    return vol;
}

// Scaled Jacobian (Verdict 정의) — 8개 코너에서 모서리 3벡터의 정규화 삼중곱의 최소값.
//
// 정육면체 = +1, 찌그러질수록 0 에 접근, 뒤집히면 음수. 예전에는 체적 부호만
// 보고 ±1 을 넣어서 '뒤집힘 여부' 밖에 못 봤고, 보고서의 `< 0.3` 경고 밴드가
// 구조적으로 절대 발동하지 않았다.
//
// 반환: {scaled_jacobian, 유효 코너 존재 여부}. LS-DYNA 는 tet/wedge 를 노드가
// 겹친 hex8 로 싣기 때문에 길이 0 모서리가 생긴다. 그런 코너는 값이 정의되지
// 않으므로 건너뛰고, 유효 코너가 하나도 없으면 false 를 돌려 '미산출' 로 남긴다
// (1.0 으로 채우면 완벽한 요소로 위장된다).
std::pair<double, bool> computeScaledJacobian8(const Vec3Q* p) {
    // 각 코너에서 오른손 방향이 되도록 고른 인접 노드 3개
    static const int adj[8][3] = {
        {1, 3, 4}, {2, 0, 5}, {3, 1, 6}, {0, 2, 7},
        {7, 5, 0}, {4, 6, 1}, {5, 7, 2}, {6, 4, 3}
    };

    double sj_min = 2.0;
    bool any = false;

    for (int c = 0; c < 8; ++c) {
        const Vec3Q a = p[adj[c][0]] - p[c];
        const Vec3Q b = p[adj[c][1]] - p[c];
        const Vec3Q d = p[adj[c][2]] - p[c];

        const double la = a.mag(), lb = b.mag(), ld = d.mag();
        if (la < 1e-20 || lb < 1e-20 || ld < 1e-20) {
            continue;  // 축퇴 코너 — 정의되지 않음
        }

        const double sj = a.cross(b).dot(d) / (la * lb * ld);
        if (sj < sj_min) sj_min = sj;
        any = true;
    }

    if (!any) return {0.0, false};
    return {sj_min, true};
}

// 고유 절점 수에 맞는 부호 있는 부피.
//
// LS-DYNA 는 tet 을 노드가 겹친 hex8 (a,b,c,d,d,d,d,d) 로 싣는데, 이 패턴에서는
// hex 5-사면체 분해의 다섯 항이 **모두** 0 이 되어 부피가 항상 0 으로 나온다.
// 그 결과 뒤집힘 판정(vol < 0)이 tet 에서는 영원히 걸리지 않았다 —
// tet 메시가 아무리 뒤집혀도 보고서엔 "음수 Jac 0개" 로 찍혔다는 뜻이다.
// 4고유일 때만 직접 사면체 부피를 쓰고, 5/6/8 고유는 기존 분해가 성립한다.
double computeSolidVolume(const Vec3Q* p, const std::vector<int32_t>& nid) {
    int uniq[8];
    int nu = 0;
    for (int i = 0; i < 8; ++i) {
        bool dup = false;
        for (int j = 0; j < nu; ++j) {
            if (nid[uniq[j]] == nid[i]) { dup = true; break; }
        }
        if (!dup && nu < 8) uniq[nu++] = i;
    }
    if (nu == 4) {
        const Vec3Q& a = p[uniq[0]];
        const Vec3Q& b = p[uniq[1]];
        const Vec3Q& c = p[uniq[2]];
        const Vec3Q& d = p[uniq[3]];
        return (b - a).dot((c - a).cross(d - a)) / 6.0;
    }
    return computeHexVolume(p);
}

// Aspect ratio for hex: max edge / min edge (12 edges).
// 반환 {값, 정의됨}. 축퇴(길이 0 모서리)면 정의되지 않는다.
std::pair<double, bool> computeAspectRatio8(const Vec3Q* p) {
    int edges[12][2] = {
        {0,1},{1,2},{2,3},{3,0},
        {4,5},{5,6},{6,7},{7,4},
        {0,4},{1,5},{2,6},{3,7}
    };
    double mn = 1e30, mx = 0;
    for (int i = 0; i < 12; ++i) {
        double len = (p[edges[i][1]] - p[edges[i][0]]).mag();
        if (len < mn) mn = len;
        if (len > mx) mx = len;
    }
    // 길이 0 모서리가 있으면 종횡비는 정의되지 않는다. 예전에는 1e6 을 넣었고
    // 그 값이 peak_aspect_ratio 로 올라가 tet 가 섞인 파트는 전부
    // "AR=1000000, > 10 이므로 crit" 이 됐다. 이제 미정의로 돌려준다.
    // 임계값은 **상대** 로 본다. 절대 1e-20 은 붕괴한 요소(실측 case_shell 에서
    // 최소 모서리가 최대의 1e-16 배)를 못 걸러 AR 이 1.3e16 으로 튀었고,
    // 그 값이 파트 최대를 삼켰다. 비율이 1e9 를 넘으면 수치적으로 붕괴다.
    if (mn <= 1e-20 || mn <= mx * 1e-9) return {0.0, false};
    return {mx / mn, true};
}

} // anonymous namespace

namespace {
/// 요소 연결성의 절점 ID → 내부 인덱스.
///
/// real_node_ids 가 있으면 요소가 담은 값은 **실 절점 ID** 이므로 매핑해야
/// 한다. 예전에는 무조건 id-1 로 깎아서, 실 ID 가 1..N 연속이 아닌 모델에서
/// 엉뚱한 좌표를 읽었다 (실측 case_shell: t=0 면적비가 1.0 이어야 하는데
/// [0.0, 1607] 이 나오고 뒤틀림이 158.6° 로 찍혔다).
/// NodalAverager::nodeIndex 와 같은 규칙이다.
struct NodeIndexResolver {
    const data::Mesh& mesh;
    std::map<int32_t, int32_t> id_to_idx;

    explicit NodeIndexResolver(const data::Mesh& m) : mesh(m) {
        for (size_t i = 0; i < mesh.real_node_ids.size(); ++i) {
            id_to_idx[mesh.real_node_ids[i]] = static_cast<int32_t>(i);
        }
    }
    int32_t operator()(int32_t node_id) const {
        if (mesh.real_node_ids.empty()) return node_id - 1;
        auto it = id_to_idx.find(node_id);
        return (it != id_to_idx.end()) ? it->second : -1;
    }
};
} // namespace

namespace {

/// 세트 필드명 → (이력 컨테이너 선택자, 압축측 여부)
struct SetFieldSource {
    const char* name;
    std::vector<PartTimeSeriesStats> AnalysisResult::*member;
    bool compressive;   // true 면 최소값이 worst (σ3/ε3)
};

const SetFieldSource kSetFieldSources[] = {
    {"von_mises",            &AnalysisResult::stress_history,               false},
    {"eff_plastic_strain",   &AnalysisResult::strain_history,               false},
    {"max_principal_stress", &AnalysisResult::max_principal_history,        false},
    {"min_principal_stress", &AnalysisResult::min_principal_history,        true},
    {"vm_strain",            &AnalysisResult::vm_strain_history,            false},
    {"max_principal_strain", &AnalysisResult::max_principal_strain_history, false},
    {"min_principal_strain", &AnalysisResult::min_principal_strain_history, true},
};

}  // namespace

std::vector<int32_t> UnifiedAnalyzer::prepareSetReports(
    D3plotReader& reader,
    const UnifiedConfig& config,
    ExtendedAnalysisResult& result,
    UnifiedProgressCallback callback
) {
    std::vector<int32_t> inject_parts;
    if (config.set_reports.empty()) return inject_parts;

    // 세트 파일 결정: 명시 > d3plot 옆 자동 탐색
    std::string sets_path = config.sets_file;
    // 세트 파일은 이제 **선택**이다 — set_id/하이라이트를 참조하는 항목만
    // 필요하다. parts/part_patterns 로만 고른 항목은 파일 없이도 동작한다.
    const bool need_file = std::any_of(
        config.set_reports.begin(), config.set_reports.end(),
        [](const SetReportSpec& sp) {
            return sp.set_id > 0 || !sp.highlight_segment_sets.empty();
        });

    parsers::KeywordSetParseResult parsed;
    bool have_file = false;
    if (!sets_path.empty()) {
        parsed = parsers::parseKeywordSetFile(sets_path);
        have_file = parsed.ok;
        if (!parsed.ok && need_file && callback) {
            callback("  Set report: " + parsed.error);
        }
        if (parsed.ok && callback) {
            callback("  Set report: " + sets_path + " 에서 세트 " +
                     std::to_string(parsed.sets.size()) + "개 로드" +
                     (parsed.warnings.empty() ? "" :
                      " (경고 " + std::to_string(parsed.warnings.size()) + "건)"));
            for (const auto& w : parsed.warnings) callback("    [set] " + w);
        }
    } else if (need_file && callback) {
        callback("  Set report: 세트 파일 없음 — set_id/하이라이트 참조 항목은 사유 기록");
    }

    // 메시의 실제 파트 ID 집합
    auto mesh = reader.read_mesh();
    std::set<int32_t> mesh_pids;
    for (int32_t p : mesh.solid_parts) mesh_pids.insert(p);
    for (int32_t p : mesh.shell_parts) mesh_pids.insert(p);
    for (int32_t p : mesh.thick_shell_parts) mesh_pids.insert(p);
    for (int32_t p : mesh.beam_parts) mesh_pids.insert(p);

    std::set<int32_t> inject_set;

    for (const auto& spec : config.set_reports) {
        SetReportResult sr;
        sr.name = spec.name;
        sr.set_type = spec.set_type;
        sr.set_id = spec.set_id;

        // ---- 파트 후보 수집: 세트 파일 + 직접 ID + 이름 패턴의 **합집합** ----
        std::vector<int32_t> candidates;
        auto add_candidate = [&](int32_t pid) {
            if (std::find(candidates.begin(), candidates.end(), pid) == candidates.end()) {
                candidates.push_back(pid);
            }
        };

        bool node_or_segment_ref = false;

        if (spec.set_id > 0) {
            parsers::KeywordSet::Kind kind;
            if (!parsers::setKindFromString(spec.set_type, kind)) {
                sr.notes.push_back("알 수 없는 set_type '" + spec.set_type +
                                   "' (part/node/segment 중 하나)");
            } else if (!have_file) {
                sr.notes.push_back("세트 파일이 없어 *SET_" +
                                   std::string(parsers::setKindName(kind)) + " " +
                                   std::to_string(spec.set_id) + " 을 해석하지 못함");
            } else {
                const auto* set = parsed.find(kind, spec.set_id);
                if (!set) {
                    sr.notes.push_back("*SET_" + std::string(parsers::setKindName(kind)) +
                                       " " + std::to_string(spec.set_id) +
                                       " 이 세트 파일에 없음");
                } else {
                    sr.title = set->title;
                    if (kind == parsers::KeywordSet::Kind::PART) {
                        for (int32_t pid : set->ids) add_candidate(pid);
                    } else if (kind == parsers::KeywordSet::Kind::NODE) {
                        // 절점 실 ID → 내부 인덱스 (real_node_ids 있으면 매핑)
                        sr.num_nodes = set->ids.size();
                        sr.metric_source = "nodes";
                        node_or_segment_ref = true;
                        std::map<int32_t, int32_t> nid2idx;
                        for (size_t ni = 0; ni < mesh.real_node_ids.size(); ++ni) {
                            nid2idx[mesh.real_node_ids[ni]] = (int32_t)ni;
                        }
                        size_t miss = 0;
                        for (int32_t nid : set->ids) {
                            int32_t idx = -1;
                            if (!nid2idx.empty()) {
                                auto itn = nid2idx.find(nid);
                                if (itn != nid2idx.end()) idx = itn->second;
                            } else if (nid >= 1 && (size_t)nid <= mesh.nodes.size()) {
                                idx = nid - 1;
                            }
                            if (idx >= 0) sr.resolved_node_idx.push_back(idx);
                            else ++miss;
                        }
                        if (miss) {
                            sr.notes.push_back("메시에 없는 절점 " + std::to_string(miss) +
                                               "개는 제외하고 진행");
                        }
                        if (sr.resolved_node_idx.empty()) {
                            sr.notes.push_back("세트의 절점이 메시에 하나도 없음 — 지표 미산출");
                        }
                    } else {
                        // 세그먼트 → 부모 solid 요소 해석. 지표는 부모 요소의
                        // σ/ε 직접 스윕으로, 뷰는 부모 파트 + 자기 하이라이트로.
                        sr.num_segments = set->segments.size();
                        sr.metric_source = "segments";
                        node_or_segment_ref = true;

                        std::map<int32_t, int32_t> nid2idx;
                        for (size_t ni = 0; ni < mesh.real_node_ids.size(); ++ni) {
                            nid2idx[mesh.real_node_ids[ni]] = (int32_t)ni;
                        }
                        auto ridx = [&](int32_t nid) -> int32_t {
                            if (!nid2idx.empty()) {
                                auto itn = nid2idx.find(nid);
                                return itn != nid2idx.end() ? itn->second : -1;
                            }
                            return (nid >= 1 && (size_t)nid <= mesh.nodes.size()) ? nid - 1 : -1;
                        };

                        // 절점 → solid 요소 역인덱스
                        std::map<int32_t, std::vector<int32_t>> node2elem;
                        for (size_t ei = 0; ei < mesh.solids.size(); ++ei) {
                            for (int32_t nid : mesh.solids[ei].node_ids) {
                                const int32_t ni = ridx(nid);
                                if (ni >= 0) node2elem[ni].push_back((int32_t)ei);
                            }
                        }

                        std::set<int32_t> parents;
                        size_t unresolved = 0;
                        for (const auto& seg : set->segments) {
                            // 세그먼트 절점 3개 이상을 담은 요소 = 부모
                            std::map<int32_t, int> hit;
                            const bool tria = (seg.n[3] == seg.n[2]);
                            const int nn = tria ? 3 : 4;
                            for (int k = 0; k < nn; ++k) {
                                const int32_t ni = ridx(seg.n[k]);
                                if (ni < 0) continue;
                                auto itv = node2elem.find(ni);
                                if (itv == node2elem.end()) continue;
                                for (int32_t ei : itv->second) hit[ei]++;
                            }
                            int32_t best = -1;
                            int best_n = 0;
                            for (const auto& kv2 : hit) {
                                if (kv2.second > best_n) { best_n = kv2.second; best = kv2.first; }
                            }
                            if (best >= 0 && best_n >= 3) parents.insert(best);
                            else ++unresolved;
                        }
                        sr.parent_elem_idx.assign(parents.begin(), parents.end());
                        if (unresolved) {
                            sr.notes.push_back("부모 solid 요소를 못 찾은 세그먼트 " +
                                               std::to_string(unresolved) +
                                               "개 (셸 면이거나 절점 미존재) — 제외");
                        }
                        if (sr.parent_elem_idx.empty()) {
                            sr.notes.push_back("부모 요소가 하나도 없음 — 지표 미산출");
                        } else {
                            // 뷰: 부모 요소들의 파트 + 자기 세그먼트 하이라이트
                            for (int32_t ei : sr.parent_elem_idx) {
                                if ((size_t)ei < mesh.solid_parts.size()) {
                                    add_candidate(mesh.solid_parts[ei]);
                                }
                            }
                            SetReportResult::HighlightSet self;
                            self.sid = spec.set_id;
                            self.title = set->title;
                            for (const auto& seg : set->segments) {
                                self.segments.push_back({seg.n[0], seg.n[1],
                                                         seg.n[2], seg.n[3]});
                            }
                            sr.highlights.push_back(std::move(self));
                        }
                    }
                }
            }
        }

        for (int32_t pid : spec.part_ids) add_candidate(pid);

        // 이름 패턴 (글롭). 정확한 파트 이름도 패턴으로 그대로 동작한다.
        for (const auto& pat : spec.part_patterns) {
            auto matched = UnifiedConfigParser::filterPartsByPattern(reader, pat);
            if (matched.empty()) {
                sr.notes.push_back("이름 패턴 '" + pat + "' 에 맞는 파트 없음");
            }
            for (int32_t pid : matched) add_candidate(pid);
        }

        if (candidates.empty() && !node_or_segment_ref &&
            spec.highlight_segment_sets.empty()) {
            sr.notes.push_back("파트 선택이 비어 있음 — set_id / parts / part_patterns "
                               "중 하나는 필요");
        }

        for (int32_t pid : candidates) {
            if (mesh_pids.count(pid)) {
                sr.resolved_parts.push_back(pid);
                inject_set.insert(pid);
            } else {
                sr.missing_parts.push_back(pid);
            }
        }
        if (!sr.missing_parts.empty()) {
            sr.notes.push_back("메시에 없는 파트 " +
                               std::to_string(sr.missing_parts.size()) +
                               "개는 제외하고 진행");
        }
        if (!candidates.empty() && sr.resolved_parts.empty()) {
            sr.notes.push_back("선택된 파트가 메시에 하나도 없음 — 지표 미산출");
        }

        // ---- 연동 세그먼트 셋 해석 (렌더 하이라이트 + 영역 최대값) ----
        for (int32_t hsid : spec.highlight_segment_sets) {
            if (!have_file) {
                sr.notes.push_back("하이라이트 세그먼트 셋 " + std::to_string(hsid) +
                                   " — 세트 파일이 없어 해석 불가");
                continue;
            }
            const auto* hs = parsed.find(parsers::KeywordSet::Kind::SEGMENT, hsid);
            if (!hs) {
                sr.notes.push_back("하이라이트용 *SET_SEGMENT " + std::to_string(hsid) +
                                   " 이 세트 파일에 없음");
                continue;
            }
            SetReportResult::HighlightSet h;
            h.sid = hsid;
            h.title = hs->title;
            for (const auto& seg : hs->segments) {
                h.segments.push_back({seg.n[0], seg.n[1], seg.n[2], seg.n[3]});
            }
            if (h.segments.empty()) {
                sr.notes.push_back("*SET_SEGMENT " + std::to_string(hsid) +
                                   " 이 비어 있음 — 하이라이트 생략");
                continue;
            }
            sr.highlights.push_back(std::move(h));
        }

        result.set_report_results.push_back(std::move(sr));
    }

    inject_parts.assign(inject_set.begin(), inject_set.end());
    return inject_parts;
}

void UnifiedAnalyzer::finalizeSetReports(
    const UnifiedConfig& config,
    ExtendedAnalysisResult& result,
    UnifiedProgressCallback callback
) {
    for (size_t si = 0; si < result.set_report_results.size(); ++si) {
        auto& sr = result.set_report_results[si];
        if (sr.metric_source != "parts") continue; // node/segment 는 직접 스윕이 채운다
        if (sr.resolved_parts.empty()) continue;   // 사유는 이미 notes 에

        const auto& spec = (si < config.set_reports.size())
                           ? config.set_reports[si]
                           : SetReportSpec{};

        // 요청 필드 (비우면 전부)
        std::vector<std::string> want = spec.fields;
        if (want.empty()) {
            for (const auto& src : kSetFieldSources) want.push_back(src.name);
        }

        for (const auto& fname : want) {
            const SetFieldSource* src = nullptr;
            for (const auto& c : kSetFieldSources) {
                if (fname == c.name) { src = &c; break; }
            }

            SetFieldResult fr;
            fr.field = fname;
            if (!src) {
                fr.note = "알 수 없는 필드";
                sr.fields.push_back(std::move(fr));
                continue;
            }

            // 멤버 파트의 이력 수집
            const auto& hist = result.*(src->member);
            std::vector<const PartTimeSeriesStats*> members;
            for (const auto& h : hist) {
                if (std::find(sr.resolved_parts.begin(), sr.resolved_parts.end(),
                              h.part_id) != sr.resolved_parts.end()) {
                    members.push_back(&h);
                }
            }
            if (members.empty()) {
                fr.note = "이 덱에서 미계측 (이력 없음)";
                sr.fields.push_back(std::move(fr));
                continue;
            }

            const size_t n_state = members.front()->data.size();
            fr.times.reserve(n_state);
            fr.values.reserve(n_state);

            const bool comp = src->compressive;
            double best = comp ? std::numeric_limits<double>::max()
                               : -std::numeric_limits<double>::max();

            for (size_t t = 0; t < n_state; ++t) {
                double v = comp ? std::numeric_limits<double>::max()
                                : -std::numeric_limits<double>::max();
                int32_t elem = 0, part = 0;
                double time = 0.0;
                for (const auto* m : members) {
                    if (t >= m->data.size()) continue;
                    const auto& tp = m->data[t];
                    time = tp.time;
                    // 압축 필드는 min_value 가 worst, 아니면 max_value
                    const double cand = comp ? tp.min_value : tp.max_value;
                    const int32_t cand_elem = comp ? tp.min_element_id : tp.max_element_id;
                    if ((comp && cand < v) || (!comp && cand > v)) {
                        v = cand;
                        elem = cand_elem;
                        part = m->part_id;
                    }
                }
                fr.times.push_back(time);
                fr.values.push_back(v);
                if ((comp && v < best) || (!comp && v > best)) {
                    best = v;
                    fr.peak = v;
                    fr.peak_time = time;
                    fr.peak_state = static_cast<int32_t>(t);
                    fr.peak_element_id = elem;
                    fr.peak_part_id = part;
                }
            }
            fr.measured = true;
            sr.fields.push_back(std::move(fr));
        }

        if (callback) {
            std::string line = "  Set report [" + sr.name + "]: 파트 " +
                               std::to_string(sr.resolved_parts.size()) + "개";
            for (const auto& f : sr.fields) {
                if (f.measured && f.field == "von_mises") {
                    line += ", σ_vm 피크 " + std::to_string(f.peak) +
                            " @ t=" + std::to_string(f.peak_time);
                }
            }
            callback(line);
        }
    }
}

void UnifiedAnalyzer::computeDirectSetMetrics(
    D3plotReader& reader,
    const std::vector<data::StateData>& all_states,
    ExtendedAnalysisResult& result,
    UnifiedProgressCallback callback
) {
    // node/segment 세트의 지표를 상태 직접 스윕으로 채운다.
    // 파트 이력 집계(finalize)를 쓰면 '파트 전체 최대' 가 세트 값으로
    // 위장되므로 여기서 정확한 대상(세트 절점/부모 요소)만 본다.
    bool need = false;
    for (const auto& sr : result.set_report_results) {
        if ((sr.metric_source == "nodes" && !sr.resolved_node_idx.empty()) ||
            (sr.metric_source == "segments" && !sr.parent_elem_idx.empty())) {
            need = true;
            break;
        }
    }
    if (!need || all_states.empty()) return;

    auto mesh = reader.read_mesh();
    const auto& cd = reader.get_control_data();
    const int nv3d = cd.NV3D;
    const size_t n_state = all_states.size();

    for (auto& sr : result.set_report_results) {
        // ---- node 세트: 절점 운동 (변위/속도/가속도 크기의 세트 최대) ----
        if (sr.metric_source == "nodes" && !sr.resolved_node_idx.empty()) {
            struct NF { const char* name; bool available; };
            SetFieldResult f_disp, f_vel, f_acc;
            f_disp.field = "disp_mag";
            f_vel.field = "vel_mag";
            f_acc.field = "acc_mag";

            const bool has_v = !all_states.front().node_velocities.empty();
            const bool has_a = !all_states.front().node_accelerations.empty();

            for (size_t t = 0; t < n_state; ++t) {
                const auto& st = all_states[t];
                double dmax = -1.0, vmax = -1.0, amax = -1.0;
                int32_t d_id = 0, v_id = 0, a_id = 0;
                for (int32_t ni : sr.resolved_node_idx) {
                    const double dm = data::nodeDisplacementMagnitude(mesh, st, (size_t)ni);
                    if (dm > dmax) {
                        dmax = dm;
                        d_id = ((size_t)ni < mesh.nodes.size()) ? mesh.nodes[ni].id : ni + 1;
                    }
                    const size_t b = (size_t)ni * 3;
                    if (has_v && b + 2 < st.node_velocities.size()) {
                        const double vx = st.node_velocities[b], vy = st.node_velocities[b+1],
                                     vz = st.node_velocities[b+2];
                        const double vm = std::sqrt(vx*vx + vy*vy + vz*vz);
                        if (vm > vmax) {
                            vmax = vm;
                            v_id = ((size_t)ni < mesh.nodes.size()) ? mesh.nodes[ni].id : ni + 1;
                        }
                    }
                    if (has_a && b + 2 < st.node_accelerations.size()) {
                        const double ax = st.node_accelerations[b], ay = st.node_accelerations[b+1],
                                     az = st.node_accelerations[b+2];
                        const double am = std::sqrt(ax*ax + ay*ay + az*az);
                        if (am > amax) {
                            amax = am;
                            a_id = ((size_t)ni < mesh.nodes.size()) ? mesh.nodes[ni].id : ni + 1;
                        }
                    }
                }
                auto push = [&](SetFieldResult& f, double v, int32_t id, bool avail) {
                    if (!avail) return;
                    f.times.push_back(st.time);
                    f.values.push_back(v);
                    if (!f.measured || v > f.peak) {
                        f.peak = v;
                        f.peak_time = st.time;
                        f.peak_state = (int32_t)t;
                        f.peak_element_id = id;   // 절점 ID (필드명이 말해준다)
                    }
                    f.measured = true;
                };
                push(f_disp, dmax, d_id, true);
                push(f_vel, vmax, v_id, has_v);
                push(f_acc, amax, a_id, has_a);
            }
            if (!has_v) f_vel.note = "속도 미기록 (IV=0)";
            if (!has_a) f_acc.note = "가속도 미기록 (IA=0)";
            sr.fields.push_back(std::move(f_disp));
            sr.fields.push_back(std::move(f_vel));
            sr.fields.push_back(std::move(f_acc));
            if (callback) {
                callback("  Set report [" + sr.name + "]: 절점 " +
                         std::to_string(sr.resolved_node_idx.size()) +
                         "개, 변위 피크 " + std::to_string(sr.fields[sr.fields.size()-3].peak));
            }
        }

        // ---- segment 세트: 부모 요소 σ_vm / 유효소성변형률 ----
        if (sr.metric_source == "segments" && !sr.parent_elem_idx.empty() && nv3d >= 7) {
            SetFieldResult f_vm, f_eps;
            f_vm.field = "von_mises";
            f_eps.field = "eff_plastic_strain";

            for (size_t t = 0; t < n_state; ++t) {
                const auto& st = all_states[t];
                if (st.solid_data.empty()) continue;
                double smax = -1.0, emax = -1.0;
                int32_t s_id = 0, e_id = 0;
                for (int32_t ei : sr.parent_elem_idx) {
                    const size_t base = (size_t)ei * nv3d;
                    if (base + 6 >= st.solid_data.size()) continue;
                    const StressTensor sig(st.solid_data[base], st.solid_data[base+1],
                                           st.solid_data[base+2], st.solid_data[base+3],
                                           st.solid_data[base+4], st.solid_data[base+5]);
                    const double vm = sig.vonMises();
                    const double ep = st.solid_data[base + 6];
                    const int32_t rid = ((size_t)ei < mesh.solids.size())
                                        ? mesh.solids[ei].id : ei + 1;
                    if (vm > smax) { smax = vm; s_id = rid; }
                    if (ep > emax) { emax = ep; e_id = rid; }
                }
                if (smax < 0) continue;
                auto push = [&](SetFieldResult& f, double v, int32_t id) {
                    f.times.push_back(st.time);
                    f.values.push_back(v);
                    if (!f.measured || v > f.peak) {
                        f.peak = v;
                        f.peak_time = st.time;
                        f.peak_state = (int32_t)t;
                        f.peak_element_id = id;
                        if ((size_t)0 < mesh.solid_parts.size()) {
                            // 대표 파트: 그 요소의 파트
                        }
                    }
                    f.measured = true;
                };
                push(f_vm, smax, s_id);
                push(f_eps, emax, e_id);
            }
            if (!f_vm.measured) f_vm.note = "solid 결과 없음";
            if (!f_eps.measured) f_eps.note = "solid 결과 없음";
            sr.fields.push_back(std::move(f_vm));
            sr.fields.push_back(std::move(f_eps));
            if (callback) {
                callback("  Set report [" + sr.name + "]: 세그먼트 부모 요소 " +
                         std::to_string(sr.parent_elem_idx.size()) +
                         "개, σ_vm 피크 " +
                         std::to_string(sr.fields[sr.fields.size()-2].peak));
            }
        }
    }
}

void UnifiedAnalyzer::processBeamJobs(
    D3plotReader& reader,
    const std::vector<AnalysisJob>& jobs,
    const std::vector<data::StateData>& all_states,
    ExtendedAnalysisResult& result,
    UnifiedProgressCallback callback
) {
    BeamAnalyzer analyzer(reader);
    if (!analyzer.initialize()) {
        // 무음 스킵 금지 — 왜 산출물이 없는지 남긴다.
        if (callback) callback("  Beam force: " + analyzer.getLastError() + " — 건너뜁니다");
        return;
    }

    for (const auto& job : jobs) {
        std::vector<int32_t> target_parts = job.part_ids;
        if (!job.part_pattern.empty()) {
            auto pattern_parts = UnifiedConfigParser::filterPartsByPattern(reader, job.part_pattern);
            for (int32_t pid : pattern_parts) {
                if (std::find(target_parts.begin(), target_parts.end(), pid) == target_parts.end()) {
                    target_parts.push_back(pid);
                }
            }
        }
        analyzer.setTargetParts(target_parts);

        auto stats = analyzer.analyze(all_states);
        if (stats.empty()) {
            if (callback) callback("  Beam force [" + job.name + "]: 대상 파트에 빔 요소 없음 — 건너뜁니다");
            continue;
        }
        if (callback) {
            callback("  Beam force [" + job.name + "]: 빔 " + std::to_string(analyzer.numBeams()) +
                     "개 / 산출물 " + std::to_string(stats.size()) + "건");
        }
        for (auto& st : stats) {
            result.beam_analysis.push_back(std::move(st));
        }
    }
}

void UnifiedAnalyzer::processElementQualityJobs(
    D3plotReader& reader,
    const std::vector<AnalysisJob>& jobs,
    const std::vector<data::StateData>& all_states,
    ExtendedAnalysisResult& result,
    UnifiedProgressCallback callback
) {
    auto mesh = reader.read_mesh();
    const NodeIndexResolver node_index(mesh);

    // Collect target parts
    std::vector<int32_t> target_parts;
    bool want_all = false;
    for (const auto& job : jobs) {
        if (job.part_ids.empty() && job.part_pattern.empty()) {
            want_all = true;
            break;
        }
        for (int32_t pid : job.part_ids) {
            if (std::find(target_parts.begin(), target_parts.end(), pid) == target_parts.end())
                target_parts.push_back(pid);
        }
        if (!job.part_pattern.empty()) {
            auto pparts = UnifiedConfigParser::filterPartsByPattern(reader, job.part_pattern);
            for (int32_t pid : pparts) {
                if (std::find(target_parts.begin(), target_parts.end(), pid) == target_parts.end())
                    target_parts.push_back(pid);
            }
        }
    }

    // Build part → element index maps
    struct ElemInfo {
        size_t idx;          // index in mesh.shells / mesh.solids
        bool is_solid;      ///< true = 8절점(solid/thick shell), false = 4절점 shell
        bool is_tshell = false;  ///< 두께셸이면 mesh.thick_shells 에서 꺼낸다
    };
    std::map<int32_t, std::vector<ElemInfo>> part_elements;
    std::map<int32_t, std::string> part_types;  // "shell" or "solid"

    for (size_t i = 0; i < mesh.shells.size(); ++i) {
        int32_t pid = (i < mesh.shell_parts.size()) ? mesh.shell_parts[i] : 0;
        if (!want_all && std::find(target_parts.begin(), target_parts.end(), pid) == target_parts.end())
            continue;
        part_elements[pid].push_back({i, false, false});
        part_types[pid] = "shell";
    }
    for (size_t i = 0; i < mesh.solids.size(); ++i) {
        int32_t pid = (i < mesh.solid_parts.size()) ? mesh.solid_parts[i] : 0;
        if (!want_all && std::find(target_parts.begin(), target_parts.end(), pid) == target_parts.end())
            continue;
        part_elements[pid].push_back({i, true, false});
        part_types[pid] = "solid";
    }
    // 두께셸 — 8절점이라 hex 와 같은 지표를 그대로 쓸 수 있다.
    // 예전에는 이 루프가 아예 없어서 두께셸 모델은 요소품질 산출물이
    // 통째로 비었고 사유도 안 남았다 (실측: 3750요소 26상태 → 0 파트).
    for (size_t i = 0; i < mesh.thick_shells.size(); ++i) {
        int32_t pid = (i < mesh.thick_shell_parts.size()) ? mesh.thick_shell_parts[i] : 0;
        if (!want_all && std::find(target_parts.begin(), target_parts.end(), pid) == target_parts.end())
            continue;
        part_elements[pid].push_back({i, true, true});
        part_types[pid] = "tshell";
    }

    // 기준 형상 = **첫 출력 상태**. 기하 섹션이 아니다.
    //
    // 체적/면적 변화율은 정의상 t=0 에 정확히 1.0 이어야 한다. 예전에는
    // 기하 섹션(mesh.nodes)을 기준으로 삼았는데, 기하 섹션과 첫 상태가
    // 어긋난 모델에서는 t=0 부터 비율이 깨졌다 (실측 case_shell:
    // t=0 면적비가 [0.000, 1607.09]). 첫 상태를 기준으로 하면 이 불변식이
    // 구조적으로 보장되고, 기하==상태0 인 모델(Test_006)에서는 결과가 같다.
    const auto& ref_state = all_states.front();
    if (callback && !mesh.nodes.empty() && !ref_state.node_displacements.empty()) {
        // 두 좌표계가 어긋나면 그 사실 자체가 진단 정보다 — 조용히 넘기지 않는다.
        double max_d2 = 0.0;
        const size_t n_chk = std::min<size_t>(mesh.nodes.size(),
                                              ref_state.node_displacements.size() / 3);
        for (size_t i = 0; i < n_chk; ++i) {
            const double dx = ref_state.node_displacements[i * 3 + 0] - mesh.nodes[i].x;
            const double dy = ref_state.node_displacements[i * 3 + 1] - mesh.nodes[i].y;
            const double dz = ref_state.node_displacements[i * 3 + 2] - mesh.nodes[i].z;
            max_d2 = std::max(max_d2, dx * dx + dy * dy + dz * dz);
        }
        if (max_d2 > 1e-12) {
            callback("  Quality: 기하 섹션과 첫 상태 좌표가 어긋남 (최대 " +
                     std::to_string(std::sqrt(max_d2)) +
                     ") — 변화율 기준은 첫 상태로 잡습니다");
        }
    }

    // Compute initial volumes/areas for reference
    struct InitialMetric {
        double volume_or_area;
    };
    std::map<int32_t, std::vector<InitialMetric>> initial_metrics;
    for (auto& [pid, elems] : part_elements) {
        auto& metrics = initial_metrics[pid];
        metrics.resize(elems.size());
        for (size_t ei = 0; ei < elems.size(); ++ei) {
            const auto& info = elems[ei];
            if (info.is_solid) {
                const auto& elem = info.is_tshell ? mesh.thick_shells[info.idx]
                                                  : mesh.solids[info.idx];
                if (elem.node_ids.size() >= 8) {
                    Vec3Q p[8];
                    bool ok8 = true;
                    for (int n = 0; n < 8 && ok8; ++n) {
                        const int32_t ni = node_index(elem.node_ids[n]);
                        if (ni < 0 || static_cast<size_t>(ni) >= mesh.nodes.size()) { ok8 = false; break; }
                        p[n] = getNodePos(mesh, ref_state, static_cast<size_t>(ni));
                    }
                    if (!ok8) continue;
                    metrics[ei].volume_or_area = std::abs(computeSolidVolume(p, elem.node_ids));
                }
            } else {
                const auto& elem = mesh.shells[info.idx];
                if (elem.node_ids.size() >= 4) {
                    Vec3Q p[4];
                    bool ok4 = true;
                    for (int n = 0; n < 4 && ok4; ++n) {
                        const int32_t ni = node_index(elem.node_ids[n]);
                        if (ni < 0 || static_cast<size_t>(ni) >= mesh.nodes.size()) { ok4 = false; break; }
                        p[n] = getNodePos(mesh, ref_state, static_cast<size_t>(ni));
                    }
                    if (!ok4) continue;
                    metrics[ei].volume_or_area = computeArea4(p[0], p[1], p[2], p[3]);
                }
            }
        }
    }

    // Sample states (not all — use ~10 evenly spaced states for performance)
    std::vector<size_t> sample_indices;
    size_t n_states = all_states.size();
    size_t n_samples = std::min(n_states, size_t(10));
    if (n_samples <= 1) {
        sample_indices.push_back(0);
        if (n_states > 1) sample_indices.push_back(n_states - 1);
    } else {
        for (size_t i = 0; i < n_samples; ++i) {
            size_t idx = i * (n_states - 1) / (n_samples - 1);
            sample_indices.push_back(idx);
        }
    }

    // Initialize result stats
    std::map<int32_t, ElementQualityStats> stats_map;
    for (auto& [pid, elems] : part_elements) {
        auto& qs = stats_map[pid];
        qs.part_id = pid;
        qs.part_name = "Part_" + std::to_string(pid);
        qs.element_type = part_types[pid];
        qs.num_elements = elems.size();
    }

    // Process sampled states
    for (size_t si = 0; si < sample_indices.size(); ++si) {
        size_t state_idx = sample_indices[si];
        const auto& state = all_states[state_idx];

        if (callback) {
            callback("    Quality: sample " + std::to_string(si + 1) + "/" + std::to_string(sample_indices.size()) +
                     " (state " + std::to_string(state_idx + 1) + "/" + std::to_string(n_states) + ")");
        }

        for (auto& [pid, elems] : part_elements) {
            ElementQualityTimePoint tp;
            tp.time = state.time;

            double ar_sum = 0, sk_sum = 0, wp_sum = 0, jac_sum = 0;
            int count = 0;
            int jac_count = 0;   // scaled Jacobian 이 정의된 요소만 따로 센다
            int ar_count = 0;    // 종횡비가 정의된 요소만 따로 센다
            int sk_count = 0;    // 왜곡도/뒤틀림이 정의된 요소(사각 셸)만

            for (size_t ei = 0; ei < elems.size(); ++ei) {
                const auto& info = elems[ei];
                int32_t elem_id = 0;

                if (info.is_solid) {
                    const auto& elem = info.is_tshell ? mesh.thick_shells[info.idx]
                                                      : mesh.solids[info.idx];
                    elem_id = elem.id;
                    if (elem.node_ids.size() < 8) continue;

                    Vec3Q p[8];
                    bool node_ok = true;
                    for (int n = 0; n < 8 && node_ok; ++n) {
                        const int32_t ni = node_index(elem.node_ids[n]);
                        if (ni < 0 || static_cast<size_t>(ni) >= mesh.nodes.size()) { node_ok = false; break; }
                        p[n] = getNodePos(mesh, state, static_cast<size_t>(ni));
                    }
                    if (!node_ok) continue;

                    auto [ar, ar_ok] = computeAspectRatio8(p);
                    double vol = computeSolidVolume(p, elem.node_ids);
                    double init_vol = initial_metrics[pid][ei].volume_or_area;
                    double vol_ratio = (init_vol > 1e-20) ? std::abs(vol) / init_vol : 1.0;

                    // scaled Jacobian 은 8절점이 모두 서로 다를 때만 의미가 있다.
                    // LS-DYNA 는 tet/wedge 를 노드가 겹친 hex8 로 싣는데, 그 경우
                    // hex 정규화를 적용하면 완벽한 정사면체도 0.707 로 나오고
                    // 절점 순서에 따라 부호까지 뒤집혀 '뒤집힌 요소' 로 오판된다.
                    bool distinct8 = true;
                    for (int a = 0; a < 8 && distinct8; ++a)
                        for (int b = a + 1; b < 8; ++b)
                            if (elem.node_ids[a] == elem.node_ids[b]) { distinct8 = false; break; }

                    if (distinct8) {
                        auto [sj, ok] = computeScaledJacobian8(p);
                        if (ok) {
                            if (!tp.jacobian_measured || sj < tp.jacobian_min) {
                                tp.jacobian_min = sj;
                                tp.worst_jacobian_elem = elem_id;
                            }
                            tp.jacobian_measured = true;
                            if (sj < 0) tp.n_negative_jacobian++;
                            jac_sum += sj;
                            jac_count++;
                        } else {
                            tp.n_jacobian_unavailable++;
                            if (vol < 0) tp.n_negative_jacobian++;
                        }
                    } else {
                        // 축퇴 요소는 scaled Jacobian 값을 못 내지만, 뒤집힘
                        // 자체는 체적 부호로 여전히 잡을 수 있다 — 개수는 센다.
                        tp.n_jacobian_unavailable++;
                        if (vol < 0) tp.n_negative_jacobian++;
                    }

                    if (ar_ok) {
                        if (ar > tp.aspect_ratio_max) { tp.aspect_ratio_max = ar; tp.worst_aspect_ratio_elem = elem_id; }
                        if (ar > 5.0) tp.n_high_aspect++;
                        tp.aspect_measured = true;
                        ar_sum += ar;
                        ar_count++;
                    } else {
                        tp.n_aspect_unavailable++;
                    }
                    if (distinct8 && init_vol > 1e-20) {
                        if (!tp.volume_measured || vol_ratio < tp.volume_change_min) {
                            tp.volume_change_min = vol_ratio;
                            tp.worst_volume_change_elem = elem_id;
                        }
                        if (!tp.volume_measured || vol_ratio > tp.volume_change_max) tp.volume_change_max = vol_ratio;
                        tp.volume_measured = true;
                    }

                    count++;
                } else {
                    const auto& elem = mesh.shells[info.idx];
                    elem_id = elem.id;
                    if (elem.node_ids.size() < 4) continue;

                    // Check for degenerate quad (tria element: node 3 == node 4)
                    bool is_tria = (elem.node_ids[2] == elem.node_ids[3]);

                    Vec3Q p[4];
                    bool node_ok = true;
                    for (int n = 0; n < 4 && node_ok; ++n) {
                        const int32_t ni = node_index(elem.node_ids[n]);
                        if (ni < 0 || static_cast<size_t>(ni) >= mesh.nodes.size()) { node_ok = false; break; }
                        p[n] = getNodePos(mesh, state, static_cast<size_t>(ni));
                    }
                    if (!node_ok) continue;

                    double ar = 0, sk, wp, area;
                    bool ar_ok;
                    if (is_tria) {
                        // Triangle: aspect ratio from 3 edges
                        double e0 = (p[1]-p[0]).mag(), e1 = (p[2]-p[1]).mag(), e2 = (p[0]-p[2]).mag();
                        double mn = std::min({e0,e1,e2}), mx = std::max({e0,e1,e2});
                        ar_ok = (mn > 1e-20);
                        if (ar_ok) ar = mx / mn;
                        sk = 0; wp = 0;
                        area = 0.5 * (p[1]-p[0]).cross(p[2]-p[0]).mag();
                    } else {
                        std::tie(ar, ar_ok) = computeAspectRatio4(p[0], p[1], p[2], p[3]);
                        sk = computeSkewness4(p[0], p[1], p[2], p[3]);
                        wp = computeWarpage4(p[0], p[1], p[2], p[3]);
                        area = computeArea4(p[0], p[1], p[2], p[3]);
                    }

                    double init_area = initial_metrics[pid][ei].volume_or_area;
                    double area_ratio = (init_area > 1e-20) ? area / init_area : 1.0;

                    if (ar_ok) {
                        if (ar > tp.aspect_ratio_max) { tp.aspect_ratio_max = ar; tp.worst_aspect_ratio_elem = elem_id; }
                        if (ar > 5.0) tp.n_high_aspect++;
                        tp.aspect_measured = true;
                        ar_sum += ar;
                        ar_count++;
                    } else {
                        // 붕괴한 요소는 각도 자체가 의미 없다 (왜곡도 1.0,
                        // 뒤틀림 179° 가 나와 파트 최대를 삼킨다). 통째로 제외.
                        tp.n_aspect_unavailable++;
                        count++;
                        continue;
                    }
                    // 삼각형 셸은 왜곡도/뒤틀림이 정의되지 않아 위에서 0 을 넣는다
                    // — 그건 '측정된 0' 이 아니므로 사각형일 때만 measured 로 친다.
                    if (!is_tria) {
                        if (sk > tp.skewness_max) { tp.skewness_max = sk; tp.worst_skewness_elem = elem_id; }
                        if (wp > tp.warpage_max) { tp.warpage_max = wp; tp.worst_warpage_elem = elem_id; }
                        tp.skewness_measured = true;
                        tp.warpage_measured = true;
                        sk_count++;
                    }
                    if (init_area > 1e-20) {
                        if (!tp.volume_measured || area_ratio < tp.volume_change_min) {
                            tp.volume_change_min = area_ratio;
                            tp.worst_volume_change_elem = elem_id;
                        }
                        if (!tp.volume_measured || area_ratio > tp.volume_change_max) tp.volume_change_max = area_ratio;
                        tp.volume_measured = true;
                    }

                    if (!is_tria) { sk_sum += sk; wp_sum += wp; }
                    count++;
                }
            }

            // 왜곡도/뒤틀림 평균도 정의된 요소로만 나눈다. 예전에는 솔리드를
            // 포함한 전체 count 로 나눠서 솔리드 파트가 0.0 을 냈다.
            if (sk_count > 0) {
                tp.skewness_avg = sk_sum / sk_count;
                tp.warpage_avg = wp_sum / sk_count;
            }
            if (ar_count > 0) {
                tp.aspect_ratio_avg = ar_sum / ar_count;
            }
            // Jacobian 평균은 값이 정의된 요소로만 나눈다. 예전에는 셸을 포함한
            // 전체 count 로 나눠서, 셸 파트는 jac_sum=0 / count>0 → 0.0 이 나왔다
            // (완전 축퇴로 읽히는 값). 이제 미측정이면 손대지 않는다.
            if (jac_count > 0) {
                tp.jacobian_avg = jac_sum / jac_count;
            }

            stats_map[pid].data.push_back(tp);
        }
    }

    // Compute global stats and add to result
    for (auto& [pid, qs] : stats_map) {
        qs.computeGlobalStats();
        result.element_quality.push_back(std::move(qs));
    }

    if (callback) callback("  Element quality complete: " + std::to_string(result.element_quality.size()) + " parts");
}

void UnifiedAnalyzer::fillMetadata(
    D3plotReader& reader,
    const UnifiedConfig& config,
    const std::vector<data::StateData>& all_states,
    ExtendedAnalysisResult& result
) {
    result.metadata.d3plot_path = config.d3plot_path;
    result.metadata.setCurrentDate();
    result.metadata.kood3plot_version = Version::get_version_string();
    result.metadata.num_states = static_cast<int32_t>(all_states.size());

    if (!all_states.empty()) {
        result.metadata.start_time = all_states.front().time;
        result.metadata.end_time = all_states.back().time;
    }

    // Collect all analyzed parts
    std::vector<int32_t> all_parts;
    for (const auto& stats : result.stress_history) {
        if (std::find(all_parts.begin(), all_parts.end(), stats.part_id) == all_parts.end()) {
            all_parts.push_back(stats.part_id);
        }
    }
    for (const auto& stats : result.strain_history) {
        if (std::find(all_parts.begin(), all_parts.end(), stats.part_id) == all_parts.end()) {
            all_parts.push_back(stats.part_id);
        }
    }
    for (const auto& stats : result.motion_analysis) {
        if (std::find(all_parts.begin(), all_parts.end(), stats.part_id) == all_parts.end()) {
            all_parts.push_back(stats.part_id);
        }
    }

    std::sort(all_parts.begin(), all_parts.end());
    result.metadata.analyzed_parts = all_parts;
}

// Note: processRenderJobs is implemented in UnifiedAnalyzerRender.cpp
// when KOOD3PLOT_HAS_RENDER is defined. This is a stub for when
// render support is not available.
#ifndef KOOD3PLOT_HAS_RENDER
bool UnifiedAnalyzer::processRenderJobs(
    D3plotReader& /* reader */,
    const UnifiedConfig& config,
    UnifiedProgressCallback callback
) {
    if (config.render_jobs.empty()) {
        return true;  // No render jobs to process
    }

    // Render module not available
    if (callback) callback("  Render jobs skipped: LSPrePost renderer not available");
    if (callback) callback("  Build with KOOD3PLOT_BUILD_V4_RENDER=ON to enable rendering");
    return false;
}

bool UnifiedAnalyzer::processPartSectionRenders(
    D3plotReader& /* reader */,
    const UnifiedConfig& config,
    const std::vector<int32_t>& /* analysis_result_part_ids */,
    UnifiedProgressCallback callback
) {
    if (config.part_section_renders.empty()) return true;
    if (callback) callback("  Part section renders skipped: LSPrePost renderer not available");
    if (callback) callback("  Build with KOOD3PLOT_BUILD_V4_RENDER=ON to enable");
    return false;
}
#endif

#ifndef KOOD3PLOT_HAS_SECTION_RENDER
void UnifiedAnalyzer::processSetViews(
    D3plotReader&, const UnifiedConfig&,
    const std::vector<data::StateData>&,
    ExtendedAnalysisResult& result,
    UnifiedProgressCallback callback)
{
    // 섹션 렌더 빌드가 꺼져 있으면 뷰는 못 만든다 — 지표는 이미 나갔고,
    // 사유를 남긴다 (무음 금지).
    for (auto& sr : result.set_report_results) {
        if (!sr.resolved_parts.empty()) {
            sr.notes.push_back("세트 뷰 미생성 — SECTION_RENDER 빌드 꺼짐");
        }
    }
    if (callback) callback("  Set view: SECTION_RENDER 빌드가 꺼져 있어 뷰 생략");
}
#endif

// Note: processSectionViews is implemented in UnifiedAnalyzerSectionRender.cpp
// when KOOD3PLOT_HAS_SECTION_RENDER is defined.
#ifndef KOOD3PLOT_HAS_SECTION_RENDER
bool UnifiedAnalyzer::processSectionViews(
    D3plotReader& /* reader */,
    const UnifiedConfig& config,
    UnifiedProgressCallback callback
) {
    if (config.section_views.empty()) {
        return true;
    }
    if (callback) callback("  Section view jobs skipped: software renderer not available");
    if (callback) callback("  Build with KOOD3PLOT_BUILD_SECTION_RENDER=ON to enable");
    return false;
}

bool UnifiedAnalyzer::processSectionViews(
    D3plotReader& /* reader */,
    const UnifiedConfig& config,
    const std::vector<data::StateData>& /* all_states */,
    UnifiedProgressCallback callback
) {
    if (config.section_views.empty()) {
        return true;
    }
    if (callback) callback("  Section view jobs skipped: software renderer not available");
    return false;
}
#endif

} // namespace analysis
} // namespace kood3plot
