/**
 * @file UnifiedAnalyzerRender.cpp
 * @brief Render job processing for UnifiedAnalyzer (requires kood3plot_render)
 *
 * This file is separated from UnifiedAnalyzer.cpp to avoid circular dependency.
 * It should be compiled only when linking with kood3plot_render.
 */

#include "kood3plot/analysis/UnifiedAnalyzer.hpp"
#include "kood3plot/analysis/UnifiedConfigParser.hpp"
#include <algorithm>
#include <atomic>
#include <cmath>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <future>
#include <limits>
#include <mutex>
#include <optional>
#include <set>
#include <thread>

#ifdef _WIN32
#include <process.h>
#define getpid _getpid
#else
#include <unistd.h>
#endif

namespace {
std::string tmpDir() {
#ifdef _WIN32
    const char* t = std::getenv("TEMP");
    if (!t) t = std::getenv("TMP");
    return t ? std::string(t) : "C:\\Temp";
#else
    return "/tmp";
#endif
}
} // anon

#ifdef KOOD3PLOT_HAS_RENDER
#include "kood3plot/render/LSPrePostRenderer.h"
#include "kood3plot/render/GeometryAnalyzer.h"
#include "kood3plot/render/RenderConfig.h"
#endif

namespace kood3plot {
namespace analysis {

#ifdef KOOD3PLOT_HAS_RENDER
namespace {

/// 렌더 잡의 fringe 이름 → LS-PrePost fringe. 모르는 이름은 von Mises 로 그리되 경고 줄을 남긴다(예전에는 말없이 그렸다).
render::FringeType fringeForJob(const std::string& name, const std::string& job, const UnifiedProgressCallback& callback)
{
    bool known = false;
    const render::FringeType t = render::fringeTypeFromName(name, &known);
    if (!known && callback) {
        callback("  WARNING: [" + job + "] 알 수 없는 fringe '" + name + "' — von Mises 로 그린다");
    }
    return t;
}

/// Pixel bounding box detected from a rendered frame
struct PixelBBox { int x1, y1, x2, y2; };

/// Detect the model rendering area in pixel coordinates by analyzing the first frame.
/// Uses background gradient interpolation from corners to find non-background pixels.
/// Excludes legend (right 20%), title (top 7%), and axes indicator (bottom-left 12%).
static std::optional<PixelBBox> detectModelPixelBBox(const std::string& video_path) {
    namespace fs = std::filesystem;

    // Extract first frame as PPM (simple binary format, easy to parse)
    std::string tmp_ppm = tmpDir() + "/kood3plot_detect_" + std::to_string(getpid()) + ".ppm";
    {
        std::ostringstream cmd;
        cmd << "ffmpeg -y -i \"" << video_path << "\" -vframes 1 \""
            << tmp_ppm << "\" >/dev/null 2>&1";
        if (std::system(cmd.str().c_str()) != 0) return std::nullopt;
    }

    // Read PPM P6 binary format
    std::ifstream f(tmp_ppm, std::ios::binary);
    if (!f) return std::nullopt;

    std::string magic;
    f >> magic;
    // Skip comment lines
    while (f.peek() == '\n' || f.peek() == '\r') f.get();
    while (f.peek() == '#') {
        f.ignore(std::numeric_limits<std::streamsize>::max(), '\n');
    }
    int W, H, maxval;
    f >> W >> H >> maxval;
    f.get(); // consume single whitespace after maxval

    if (magic != "P6" || W < 100 || H < 100) {
        std::remove(tmp_ppm.c_str());
        return std::nullopt;
    }

    std::vector<uint8_t> pixels(W * H * 3);
    f.read(reinterpret_cast<char*>(pixels.data()), pixels.size());
    f.close();
    std::remove(tmp_ppm.c_str());

    auto getPixel = [&](int x, int y) -> std::array<double,3> {
        size_t idx = ((size_t)y * W + x) * 3;
        return {(double)pixels[idx], (double)pixels[idx+1], (double)pixels[idx+2]};
    };

    // Background gradient reference: interpolate between top-left and bottom-left corners
    // (LSPrePost "fade" bgstyle = vertical gradient)
    auto bg_tl = getPixel(3, 3);
    auto bg_bl = getPixel(3, H - 4);

    // Exclusion zones
    int ex_right = W * 20 / 100;   // legend area
    int ex_top   = H * 7 / 100;    // title area
    int axes_w   = W * 12 / 100;   // axes indicator
    int axes_h   = H * 12 / 100;
    double threshold = 30.0;

    int x1 = W, y1 = H, x2 = 0, y2 = 0;

    for (int y = ex_top; y < H; y += 2) {
        // Interpolate background color for this row
        double t = (double)y / (H - 1);
        double bg_r = bg_tl[0] + (bg_bl[0] - bg_tl[0]) * t;
        double bg_g = bg_tl[1] + (bg_bl[1] - bg_tl[1]) * t;
        double bg_b = bg_tl[2] + (bg_bl[2] - bg_tl[2]) * t;

        for (int x = 0; x < W - ex_right; x += 2) {
            // Skip axes indicator in bottom-left corner
            if (x < axes_w && y > H - axes_h) continue;

            auto px = getPixel(x, y);
            double dr = px[0] - bg_r;
            double dg = px[1] - bg_g;
            double db = px[2] - bg_b;
            double dist = std::sqrt(dr*dr + dg*dg + db*db);

            if (dist > threshold) {
                if (x < x1) x1 = x;
                if (y < y1) y1 = y;
                if (x > x2) x2 = x;
                if (y > y2) y2 = y;
            }
        }
    }

    if (x2 <= x1 || y2 <= y1) return std::nullopt;
    return PixelBBox{x1, y1, x2, y2};
}

/// Detect "warm" fringe pixels (non-blue fringe colors: red/orange/yellow/green/cyan).
/// Used to locate the target part when per-part fringe range makes it stand out.
/// Falls back to full model bbox if no warm pixels found.
static std::optional<PixelBBox> detectFringePixelBBox(const std::string& video_path) {
    namespace fs = std::filesystem;

    // Extract a frame at ~10% into the animation (not first frame which may be undeformed)
    static std::atomic<int> s_fringe_counter{0};
    std::string tmp_ppm = tmpDir() + "/kood3plot_fringe_" + std::to_string(getpid()) + "_" +
                          std::to_string(s_fringe_counter.fetch_add(1)) + ".ppm";
    {
        std::ostringstream cmd;
        // Use select filter to pick frame 50 (or last if shorter)
        cmd << "ffmpeg -y -i \"" << video_path << "\" -vf \"select=eq(n\\,50)\" -frames:v 1 \""
            << tmp_ppm << "\" >/dev/null 2>&1";
        if (std::system(cmd.str().c_str()) != 0) {
            // Fallback: just use first frame
            std::ostringstream cmd2;
            cmd2 << "ffmpeg -y -i \"" << video_path << "\" -vframes 1 \""
                 << tmp_ppm << "\" >/dev/null 2>&1";
            if (std::system(cmd2.str().c_str()) != 0) return std::nullopt;
        }
    }

    std::ifstream f(tmp_ppm, std::ios::binary);
    if (!f) return std::nullopt;

    std::string magic;
    f >> magic;
    while (f.peek() == '\n' || f.peek() == '\r') f.get();
    while (f.peek() == '#') {
        f.ignore(std::numeric_limits<std::streamsize>::max(), '\n');
    }
    int W, H, maxval;
    f >> W >> H >> maxval;
    f.get();

    if (magic != "P6" || W < 100 || H < 100) {
        std::remove(tmp_ppm.c_str());
        return std::nullopt;
    }

    std::vector<uint8_t> pixels(W * H * 3);
    f.read(reinterpret_cast<char*>(pixels.data()), pixels.size());
    f.close();
    std::remove(tmp_ppm.c_str());

    // Exclusion zones (same as detectModelPixelBBox)
    int ex_right = W * 20 / 100;
    int ex_top   = H * 7 / 100;
    int axes_w   = W * 12 / 100;
    int axes_h   = H * 12 / 100;

    // Background gradient reference
    auto bg_tl = std::array<double,3>{(double)pixels[9], (double)pixels[10], (double)pixels[11]};
    size_t bl_idx = ((size_t)(H-4) * W + 3) * 3;
    auto bg_bl = std::array<double,3>{(double)pixels[bl_idx], (double)pixels[bl_idx+1], (double)pixels[bl_idx+2]};

    int x1 = W, y1 = H, x2 = 0, y2 = 0;

    for (int y = ex_top; y < H; y += 2) {
        double t = (double)y / (H - 1);
        double bg_r = bg_tl[0] + (bg_bl[0] - bg_tl[0]) * t;
        double bg_g = bg_tl[1] + (bg_bl[1] - bg_tl[1]) * t;
        double bg_b = bg_tl[2] + (bg_bl[2] - bg_tl[2]) * t;

        for (int x = 0; x < W - ex_right; x += 2) {
            if (x < axes_w && y > H - axes_h) continue;

            size_t idx = ((size_t)y * W + x) * 3;
            double r = pixels[idx], g = pixels[idx+1], b = pixels[idx+2];

            // Check if this pixel is background
            double dr = r - bg_r, dg = g - bg_g, db = b - bg_b;
            if (std::sqrt(dr*dr + dg*dg + db*db) < 30.0) continue;

            // Check if this pixel is a "warm" fringe color (not pure dark blue).
            // In rainbow colormap: blue(0,0,255) → cyan(0,255,255) → green(0,255,0)
            //   → yellow(255,255,0) → red(255,0,0)
            // Dark blue (bottom of range) is similar to background; skip it.
            // We want pixels where R > 30 OR G > 100 (cyan/green/yellow/red region)
            bool is_warm = (r > 50) || (g > 120 && b < 200);
            if (is_warm) {
                if (x < x1) x1 = x;
                if (y < y1) y1 = y;
                if (x > x2) x2 = x;
                if (y > y2) y2 = y;
            }
        }
    }

    if (x2 <= x1 || y2 <= y1) return std::nullopt;
    return PixelBBox{x1, y1, x2, y2};
}

// 숨길 파트를 뺀 나머지 파트의 상자 — 숨길 것이 없으면 전체 모델 상자. 전체 상자는 바닥이 크면 단면
// 위치(가운데)가 바닥 한가운데를 잡고, LS-PrePost 의 ac 가 맞추는 범위와도 어긋난다(_zoom 자르기 대응).
// 메시의 모든 파트 ID(중복 없이, 오름차순). Mesh::*_parts 는 요소마다의 파트 배열이다.
std::vector<int> meshPartIds(const data::Mesh& mesh) {
    std::set<int> ids;
    for (const auto* lst : {&mesh.solid_parts, &mesh.shell_parts, &mesh.thick_shell_parts, &mesh.beam_parts})
        ids.insert(lst->begin(), lst->end());
    return {ids.begin(), ids.end()};
}

// 숨길 파트마다 요소 형식 — 'H' 솔리드 · 'S' 셸 · 'T' 두꺼운 셸, 0 = 모름(LS-PrePost `-M S21` 꼴에 쓴다)
std::vector<char> partKinds(const data::Mesh& mesh, const std::vector<int32_t>& hidden) {
    auto has = [](const std::vector<int32_t>& per_elem, int32_t pid) {
        return std::find(per_elem.begin(), per_elem.end(), pid) != per_elem.end();
    };
    std::vector<char> out;
    for (int32_t pid : hidden) {
        out.push_back(has(mesh.solid_parts, pid) ? 'H' : has(mesh.shell_parts, pid) ? 'S'
                      : has(mesh.thick_shell_parts, pid) ? 'T' : 0);
    }
    return out;
}

render::BoundingBox visibleModelBounds(D3plotReader& reader, const std::vector<int32_t>& hidden,
                                       std::vector<char>* kinds = nullptr) {
    if (hidden.empty()) return render::GeometryAnalyzer::calculateModelBounds(reader, 0);
    const auto mesh = reader.read_mesh();
    if (kinds) *kinds = partKinds(mesh, hidden);
    render::BoundingBox box{};
    bool any = false;
    for (int pid : meshPartIds(mesh)) {
        if (std::find(hidden.begin(), hidden.end(), pid) != hidden.end()) continue;
        auto pb = render::GeometryAnalyzer::calculatePartBounds(reader, pid, 0);
        for (int a = 0; a < 3; ++a) {
            box.min[a] = any ? std::min(box.min[a], pb.min[a]) : pb.min[a];
            box.max[a] = any ? std::max(box.max[a], pb.max[a]) : pb.max[a];
        }
        any = true;
    }
    if (!any) return render::GeometryAnalyzer::calculateModelBounds(reader, 0);
    for (int a = 0; a < 3; ++a) box.center[a] = (box.min[a] + box.max[a]) / 2.0;
    return box;
}

} // anonymous namespace
#endif

bool UnifiedAnalyzer::processRenderJobs(
    D3plotReader& reader,
    const UnifiedConfig& config,
    UnifiedProgressCallback callback
) {
    if (config.render_jobs.empty()) {
        return true;  // No render jobs to process
    }

    if (callback) callback("Processing render jobs...");

#ifdef KOOD3PLOT_HAS_RENDER
    namespace fs = std::filesystem;

    // Determine LSPrePost path with fallback logic
    std::string lsprepost_path = config.lsprepost_path;

    if (lsprepost_path.empty()) {
        // Try to find lsprepost relative to executable
        try {
            // Get executable path
            fs::path exe_path = fs::read_symlink("/proc/self/exe");
            fs::path exe_dir = exe_path.parent_path();

#ifdef _WIN32
            // Windows: {exe_dir}/../lsprepost/lspp412_win64.exe
            fs::path win_path = exe_dir / ".." / "lsprepost" / "lspp412_win64.exe";
            if (fs::exists(win_path)) {
                lsprepost_path = fs::canonical(win_path).string();
            }
#else
            // Linux: {exe_dir}/../lsprepost/lsprepost
            fs::path linux_path = exe_dir / ".." / "lsprepost" / "lsprepost";
            if (fs::exists(linux_path)) {
                lsprepost_path = fs::canonical(linux_path).string();
            }
#endif
        } catch (...) {
            // Fallback if path resolution fails
        }
    }

    // Final fallback to system PATH
    if (lsprepost_path.empty()) {
        lsprepost_path = "lsprepost";
    }

    if (callback) callback("  Using LSPrePost: " + lsprepost_path);

    // Check if LSPrePost is available (use a temporary renderer to check)
    {
        render::LSPrePostRenderer check_renderer(lsprepost_path);
        if (!check_renderer.isAvailable()) {
            if (callback) callback("  WARNING: LSPrePost not found at: " + lsprepost_path);
            if (callback) callback("  Set lsprepost_path in YAML or install LSPrePost");
            return false;
        }
    }

    // Helper: parse view_str into ViewOrientation
    auto parseView = [](const std::string& v) -> render::ViewOrientation {
        if (v == "right")   return render::ViewOrientation::RIGHT;
        if (v == "left")    return render::ViewOrientation::LEFT;
        if (v == "front")   return render::ViewOrientation::FRONT;
        if (v == "back")    return render::ViewOrientation::BACK;
        if (v == "top")     return render::ViewOrientation::TOP;
        if (v == "bottom")  return render::ViewOrientation::BOTTOM;
        return render::ViewOrientation::ISOMETRIC;
    };

    // ── Phase 1: Build all render tasks (sequential, uses reader) ──
    struct RenderTask {
        std::string name;           // For logging
        std::string output_file;
        render::RenderOptions options;
        render::SectionPlane plane;  // Used for non-animation section view
        bool is_animation;
        // For ffmpeg post-crop (camera centering alternative)
        render::BoundingBox model_bbox;
        render::BoundingBox part_bbox;
        bool need_crop = false;     // true when highlight_parts is set
    };
    std::vector<RenderTask> tasks;

    for (const auto& job : config.render_jobs) {
        if (callback) callback("  Preparing: " + job.name);

        // Collect target part IDs
        std::vector<int32_t> target_parts = job.parts;
        if (!job.part_pattern.empty()) {
            auto pattern_parts = UnifiedConfigParser::filterPartsByPattern(reader, job.part_pattern);
            for (int32_t pid : pattern_parts) {
                if (std::find(target_parts.begin(), target_parts.end(), pid) == target_parts.end()) {
                    target_parts.push_back(pid);
                }
            }
            if (callback) {
                if (pattern_parts.empty()) {
                    // 무음 금지 — 0개 매칭은 '전체 모델, 하이라이트 없음' 으로 번진다.
                    callback("    Pattern '" + job.part_pattern + "' 에 맞는 파트 0개 — "
                             "하이라이트 없이 전체 모델을 렌더합니다");
                } else {
                    callback("    Pattern '" + job.part_pattern + "' matched " +
                             std::to_string(pattern_parts.size()) + " parts");
                }
            }
        }

        // Calculate bounding boxes
        std::vector<char> hide_kinds;
        render::BoundingBox model_bbox = visibleModelBounds(reader, job.hide_part_ids, &hide_kinds);
        render::BoundingBox bbox = model_bbox;

        // 단면 위치 상자 — 면이 있고 숨기지 않은 타겟만 합친다. 빔 · 질량 · 없는 번호 · 숨긴 타겟이 섞이면
        // 상자가 모델 전체로 커져 단면이 타겟을 비켜 갔다. 넣을 타겟이 없으면 보이는 모델 상자.
        if (!target_parts.empty()) {
            const std::vector<int32_t> box_targets =
                render::GeometryAnalyzer::boxTargets(reader.read_mesh(), target_parts, job.hide_part_ids);
            if (box_targets.size() < target_parts.size() && callback) {
                std::string left_out;
                for (int32_t pid : target_parts) {
                    if (std::find(box_targets.begin(), box_targets.end(), pid) == box_targets.end())
                        left_out += (left_out.empty() ? "" : ", ") + std::to_string(pid);
                }
                callback("    Section box: 타겟 파트 " + left_out + " 은 면이 없거나 숨김 대상이라 단면 위치 상자에서 뺍니다" +
                         (box_targets.empty() ? " — 보이는 모델 상자를 씁니다" : ""));
            }
            for (size_t i = 0; i < box_targets.size(); ++i) {
                const auto part_bbox = render::GeometryAnalyzer::calculatePartBounds(reader, box_targets[i], 0);
                for (int a = 0; a < 3; ++a) {
                    bbox.min[a] = i ? std::min(bbox.min[a], part_bbox.min[a]) : part_bbox.min[a];
                    bbox.max[a] = i ? std::max(bbox.max[a], part_bbox.max[a]) : part_bbox.max[a];
                }
            }
            if (!box_targets.empty()) {
                for (int a = 0; a < 3; ++a) bbox.center[a] = (bbox.min[a] + bbox.max[a]) / 2.0;
            }
        }

        // Resolve effective output directory: job-level → config-level fallback
        std::string eff_output_dir = job.output.directory.empty()
                                     ? config.output_directory
                                     : job.output.directory;

        // Create output directory if needed
        if (!eff_output_dir.empty()) {
            try {
                fs::create_directories(eff_output_dir);
            } catch (const std::exception& e) {
                if (callback) callback("    Failed to create directory: " + std::string(e.what()));
            }
        }

        // Collect context parts once per job (for highlight mode)
        std::vector<int> context_parts;
        int fit_visible_targets = 0;  // 모델에 있고 숨김 대상이 아닌 타겟 수(view_fit: target 일 때만 센다)
        if (!target_parts.empty()) {
            auto mesh = reader.read_mesh();
            std::set<int32_t> highlight_set(target_parts.begin(), target_parts.end());
            std::set<int> seen;
            auto add_ctx = [&](int32_t pid) {
                if (!highlight_set.count(pid) && !seen.count(pid)) {
                    seen.insert(pid);
                    context_parts.push_back(static_cast<int>(pid));
                }
            };
            for (int32_t pid : mesh.solid_parts)      add_ctx(pid);
            for (int32_t pid : mesh.shell_parts)      add_ctx(pid);
            for (int32_t pid : mesh.thick_shell_parts) add_ctx(pid);

            if (job.view_fit_target) {
                for (int pid : meshPartIds(mesh)) {
                    if (highlight_set.count(pid) && std::find(job.hide_part_ids.begin(), job.hide_part_ids.end(),
                                                              pid) == job.hide_part_ids.end()) {
                        ++fit_visible_targets;
                    }
                }
            }
        }

        // 카메라 타겟 맞춤(view_fit: target) — 화면은 단면을 넣는 순간 보이는 파트에 맞는다. 그래서 단면이 있고,
        // 보이는 타겟(모델에 있고 숨김 대상이 아닌 것)이 하나라도 있을 때만 건다. 보이는 타겟이 없는데 걸면
        // 영상이 통째로 빈 화면이다(2026-11-20 실측 — 타겟이 전부 숨김 대상일 때 · 모델에 없는 번호일 때).
        bool fit_target = false;
        if (job.view_fit_target) {
            const char* why_not = job.sections.empty() ? "단면이 없는 작업이다"
                                : target_parts.empty() ? "타겟 파트가 없다"
                                : fit_visible_targets == 0 ? "보이는 타겟이 없다(모두 숨김 대상이거나 모델에 없는 번호)"
                                : nullptr;
            fit_target = (why_not == nullptr);
            if (callback) {
                if (fit_target) {
                    std::ostringstream msg;
                    msg << "    View fit: 타겟 파트 " << fit_visible_targets << "개에 카메라를 맞춥니다(여백 "
                        << job.view_margin << ")";
                    callback(msg.str());
                } else {
                    // deep 이 이 줄을 건져 보고서에 싣는다(d3plot_reader._view_fit_declined) — 머리 · 꼬리 문구를 바꾸면 같이 바꾼다
                    callback(std::string("    View fit: ") + why_not + " — 보이는 모델 전체에 맞춥니다");
                }
            }
        }

        // Full-model render (no sections): render once with the specified view
        if (job.sections.empty()) {
            RenderTask task;
            task.name = job.name;
            task.is_animation = (job.output.format == RenderOutputFormat::MP4);
            task.options.hidden_parts.assign(job.hide_part_ids.begin(), job.hide_part_ids.end());
            task.options.hidden_kinds = hide_kinds;

            if (task.is_animation) {
                task.options.create_animation = true;
                task.options.video_format = render::VideoFormat::MP4;
                task.options.fps = job.output.fps;
            } else {
                task.options.create_animation = false;
                if (job.output.format == RenderOutputFormat::PNG)
                    task.options.image_format = render::ImageFormat::PNG;
                else if (job.output.format == RenderOutputFormat::JPG)
                    task.options.image_format = render::ImageFormat::JPG;
            }

            task.options.view = job.view_str.empty()
                        ? render::ViewOrientation::ISOMETRIC
                        : parseView(job.view_str);
            task.options.image_width  = job.output.resolution[0];
            task.options.image_height = job.output.resolution[1];

            if (!job.fringe_type.empty())
                task.options.fringe_type = fringeForJob(job.fringe_type, job.name, callback);

            task.output_file = job.output.filename.empty() ? job.name : job.output.filename;
            if (!eff_output_dir.empty())
                task.output_file = eff_output_dir + "/" + task.output_file;

            tasks.push_back(std::move(task));
            continue;
        }

        // Process each section specification
        for (const auto& section_spec : job.sections) {
            int axis = 2;
            if (section_spec.axis == 'x' || section_spec.axis == 'X') axis = 0;
            else if (section_spec.axis == 'y' || section_spec.axis == 'Y') axis = 1;

            double abs_position = bbox.min[axis] + section_spec.position * (bbox.max[axis] - bbox.min[axis]);

            // (debug bbox removed - confirmed working)

            RenderTask task;
            task.plane.point = bbox.center;
            task.plane.point[axis] = abs_position;
            task.plane.normal = {0, 0, 0};
            task.plane.normal[axis] = 1.0;
            task.plane.visible = true;

            task.options.section_planes.push_back(task.plane);
            task.options.hidden_parts.assign(job.hide_part_ids.begin(), job.hide_part_ids.end());
            task.options.hidden_kinds = hide_kinds;

            if (job.output.format == RenderOutputFormat::MP4) {
                task.options.create_animation = true;
                task.options.video_format = render::VideoFormat::MP4;
                task.options.fps = job.output.fps;
                task.is_animation = true;
            } else if (job.output.format == RenderOutputFormat::GIF) {
                task.options.create_animation = true;
                task.options.video_format = render::VideoFormat::AVI;
                task.is_animation = true;
            } else {
                task.options.create_animation = false;
                task.is_animation = false;
                if (job.output.format == RenderOutputFormat::PNG)
                    task.options.image_format = render::ImageFormat::PNG;
                else if (job.output.format == RenderOutputFormat::JPG)
                    task.options.image_format = render::ImageFormat::JPG;
            }

            if (!job.view_str.empty()) {
                task.options.view = parseView(job.view_str);
            } else {
                // Auto-select view based on section axis:
                // X-section (normal=1,0,0) → view from RIGHT
                // Y-section (normal=0,1,0) → view from FRONT
                // Z-section (normal=0,0,1) → view from TOP
                if (axis == 0)      task.options.view = render::ViewOrientation::RIGHT;
                else if (axis == 1) task.options.view = render::ViewOrientation::FRONT;
                else                task.options.view = render::ViewOrientation::TOP;
            }

            task.options.state_step = job.state_step;
            task.options.image_width = job.output.resolution[0];
            task.options.image_height = job.output.resolution[1];

            if (!job.fringe_type.empty())
                task.options.fringe_type = fringeForJob(job.fringe_type, job.name, callback);

            if (!job.fringe_range.is_auto()) {
                task.options.auto_fringe_range = false;
                task.options.fringe_min = job.fringe_range.min;
                task.options.fringe_max = job.fringe_range.max;
            }

            if (!target_parts.empty()) {
                task.options.highlight_parts = std::vector<int>(target_parts.begin(), target_parts.end());
                task.options.context_parts = context_parts;

                // Store bbox info for ffmpeg post-crop (단면 영상 잡은 zoom_crop: false 로 끈다)
                task.model_bbox = model_bbox;
                task.part_bbox = bbox;
                // 타겟에 맞춘 영상은 그 자체가 확대본이다 — `_zoom` 을 한 벌 더 만들지 않는다
                task.need_crop = job.zoom_crop && !fit_target;
                task.options.fit_highlight = fit_target;
                task.options.fit_margin = job.view_margin;

                // 색 범위는 잡의 fringe_range 를 준 경우만 건다(위). 자동이면 LS-PrePost 자동 범위다 —
                // 예전에 여기서 낸 「파트별 범위」(첫 적분점 · 첫 층의 von Mises, 다섯 상태 표본)는 7d33676 이후
                // 스크립트에 한 번도 실리지 않은 채 로그에만 찍혔다.
            }

            // Build output filename
            std::string pos_str = section_spec.position_auto.empty() ?
                                  std::to_string(static_cast<int>(section_spec.position * 100)) + "pct" :
                                  section_spec.position_auto;
            std::replace(pos_str.begin(), pos_str.end(), '%', 'p');

            std::string output_file = job.output.filename;
            if (output_file.empty()) {
                std::string axis_str(1, section_spec.axis);
                output_file = job.name + "_" + axis_str + "_" + pos_str;
            } else {
                for (const auto& ext : {".mp4", ".avi", ".wmv", ".png", ".jpg", ".jpeg", ".bmp"}) {
                    std::string s = ext;
                    if (output_file.size() > s.size() &&
                        output_file.substr(output_file.size() - s.size()) == s) {
                        output_file = output_file.substr(0, output_file.size() - s.size());
                        break;
                    }
                }
            }
            std::replace(output_file.begin(), output_file.end(), ' ', '_');
            if (!eff_output_dir.empty())
                output_file = eff_output_dir + "/" + output_file;

            task.name = job.name + " [" + std::string(1, section_spec.axis) + " " + pos_str + "]";
            task.output_file = output_file;

            tasks.push_back(std::move(task));
        }
    }

    // ── Phase 2: Execute render tasks (sequential or parallel) ──
    int render_threads = std::max(1, config.render_threads);
#ifndef _WIN32
    // If xvfb-run is not available, force single-thread to avoid segfaults
    // from concurrent Mesa/LSPrePost instances sharing global state
    if (render_threads > 1 && std::system("which xvfb-run >/dev/null 2>&1") != 0) {
        if (callback) callback("  WARNING: xvfb-run not found, forcing render_threads=1");
        render_threads = 1;
    }
#endif
    bool all_success = true;
    std::mutex mtx;

    if (callback) {
        callback("  Render tasks: " + std::to_string(tasks.size()) +
                 " (threads: " + std::to_string(render_threads) + ")");
    }

    auto execute_task = [&](size_t idx) -> bool {
        const auto& task = tasks[idx];
        render::LSPrePostRenderer renderer(lsprepost_path);

        {
            std::lock_guard<std::mutex> lock(mtx);
            if (callback) callback("    [" + std::to_string(idx + 1) + "/" +
                                   std::to_string(tasks.size()) + "] " + task.name);
        }

        bool success;
        if (task.is_animation) {
            success = renderer.renderAnimation(config.d3plot_path, task.output_file, task.options);
        } else if (!task.options.section_planes.empty()) {
            success = renderer.renderSectionView(config.d3plot_path, task.output_file,
                                                  task.plane, task.options);
        } else {
            success = renderer.renderImage(config.d3plot_path, task.output_file, task.options);
        }

        {
            std::lock_guard<std::mutex> lock(mtx);
            if (!success) {
                if (callback) callback("    FAILED: " + task.name + " - " + renderer.getLastError());
            } else {
                if (callback) callback("    Created: " + task.output_file);
            }
        }

        // Post-process: ffmpeg crop for per-part zoom
        // Uses image-based fringe color detection (camera-angle independent)
        if (success && task.need_crop) {
            int W = task.options.image_width;
            int H = task.options.image_height;

            // Find rendered video file (LSPrePost adds extension)
            std::string src_file = task.output_file;
            for (const auto& ext : {".mp4", ".avi"}) {
                if (fs::exists(src_file + ext)) {
                    src_file = src_file + ext;
                    break;
                }
            }
            if (!fs::exists(src_file)) goto skip_crop;

            {
                // Output file: add "_zoom" suffix — 점은 파일 이름 안에서만 찾는다. 전체 경로에서 찾으면 폴더 이름의 점
                // (`.work/`, `v1.2/` 등)에 끼워 `/src/_zoom.work/...` 같은 없는 경로가 되어 ffmpeg 가 조용히 실패했다(11-06 실측).
                std::string zoomed_file = task.output_file;
                auto dot = zoomed_file.rfind('.');
                auto slash = zoomed_file.find_last_of("/\\");
                if (dot != std::string::npos && slash != std::string::npos && dot < slash) dot = std::string::npos;
                if (dot == std::string::npos) {
                    zoomed_file += "_zoom";
                    auto sdot = src_file.rfind('.');
                    if (sdot != std::string::npos) zoomed_file += src_file.substr(sdot);
                } else {
                    zoomed_file.insert(dot, "_zoom");
                }

                // Detect target part via fringe color pixels (warm colors in rainbow map)
                auto fringe_bbox = detectFringePixelBBox(src_file);
                double px, py;
                int fringe_w = 0, fringe_h = 0;

                if (fringe_bbox) {
                    px = (fringe_bbox->x1 + fringe_bbox->x2) / 2.0;
                    py = (fringe_bbox->y1 + fringe_bbox->y2) / 2.0;
                    fringe_w = fringe_bbox->x2 - fringe_bbox->x1;
                    fringe_h = fringe_bbox->y2 - fringe_bbox->y1;
                } else {
                    // Fallback: use full model bbox detection and center
                    auto model_pbbox = detectModelPixelBBox(src_file);
                    if (model_pbbox) {
                        px = (model_pbbox->x1 + model_pbbox->x2) / 2.0;
                        py = (model_pbbox->y1 + model_pbbox->y2) / 2.0;
                    } else {
                        px = W / 2.0;
                        py = H / 2.0;
                    }
                }

                // Crop size: 1.3x fringe extent, min W/5, max W*2/3
                int fringe_max = std::max(fringe_w, fringe_h);
                int crop_from_fringe = std::max(1, (int)(fringe_max * 1.3));
                int min_crop = W / 5;
                int max_crop = W * 2 / 3;
                int crop_px = std::max(min_crop, std::min(max_crop, crop_from_fringe));
                crop_px = (crop_px / 2) * 2;
                int crop_py = (int)(crop_px * ((double)H / W));
                crop_py = (crop_py / 2) * 2;

                // Clamp crop center to video bounds
                int cx = std::max(crop_px / 2, std::min(W - crop_px / 2, (int)px));
                int cy = std::max(crop_py / 2, std::min(H - crop_py / 2, (int)py));

                std::ostringstream cmd;
                cmd << "ffmpeg -y -i \"" << src_file << "\" -vf \"crop="
                    << crop_px << ":" << crop_py << ":"
                    << (cx - crop_px / 2) << ":" << (cy - crop_py / 2)
                    << "\" -c:v libx264 -crf 18 \""
                    << zoomed_file << "\" >/dev/null 2>&1";

                int ret = std::system(cmd.str().c_str());
                {
                    std::lock_guard<std::mutex> lock(mtx);
                    if (ret == 0 && callback) {
                        callback("    Cropped: " + zoomed_file +
                                 " (crop=" + std::to_string(crop_px) + "x" + std::to_string(crop_py) +
                                 " at " + std::to_string(cx - crop_px / 2) + "," +
                                 std::to_string(cy - crop_py / 2) + ")");
                    }
                }
            }
            skip_crop:;
        }

        return success;
    };

    if (render_threads == 1) {
        // Sequential execution
        for (size_t i = 0; i < tasks.size(); ++i) {
            if (!execute_task(i)) all_success = false;
        }
    } else {
        // Parallel execution with thread pool
        std::vector<std::future<bool>> futures;
        size_t next_task = 0;
        std::mutex queue_mtx;

        auto worker = [&]() {
            while (true) {
                size_t idx;
                {
                    std::lock_guard<std::mutex> lock(queue_mtx);
                    if (next_task >= tasks.size()) return;
                    idx = next_task++;
                }
                if (!execute_task(idx)) {
                    std::lock_guard<std::mutex> lock(mtx);
                    all_success = false;
                }
            }
        };

        std::vector<std::thread> threads;
        int n_workers = std::min(render_threads, static_cast<int>(tasks.size()));
        for (int t = 0; t < n_workers; ++t) {
            threads.emplace_back(worker);
        }
        for (auto& t : threads) {
            t.join();
        }
    }

    return all_success;

#else
    // Render module not available
    if (callback) callback("  Render jobs skipped: LSPrePost renderer not available");
    if (callback) callback("  Build with KOOD3PLOT_BUILD_V4_RENDER=ON to enable rendering");
    return false;
#endif
}

// ============================================================
// processPartSectionRenders — uses LSPrePostRenderer::renderAllPartSections
// ============================================================

bool UnifiedAnalyzer::processPartSectionRenders(
    D3plotReader& reader,
    const UnifiedConfig& config,
    const std::vector<int32_t>& analysis_result_part_ids,
    UnifiedProgressCallback callback
) {
    if (config.part_section_renders.empty()) return true;

    if (callback) callback("Processing part section renders...");

#ifdef KOOD3PLOT_HAS_RENDER
    namespace fs = std::filesystem;

    // Resolve LSPrePost path (same fallback chain as processRenderJobs).
    std::string lsprepost_path = config.lsprepost_path;
    if (lsprepost_path.empty()) {
        try {
            fs::path exe_path = fs::read_symlink("/proc/self/exe");
            fs::path exe_dir = exe_path.parent_path();
#ifdef _WIN32
            fs::path p = exe_dir / ".." / "lsprepost" / "lspp412_win64.exe";
            if (fs::exists(p)) lsprepost_path = fs::canonical(p).string();
#else
            fs::path p = exe_dir / ".." / "lsprepost" / "lsprepost";
            if (fs::exists(p)) lsprepost_path = fs::canonical(p).string();
#endif
        } catch (...) { /* fallback below */ }
    }
    if (lsprepost_path.empty()) lsprepost_path = "lsprepost";

    if (callback) callback("  Using LSPrePost: " + lsprepost_path);

    // Probe availability
    {
        render::LSPrePostRenderer probe(lsprepost_path);
        if (!probe.isAvailable()) {
            if (callback) callback("  WARNING: LSPrePost not found at: " + lsprepost_path);
            return false;
        }
    }

    // 폴더 이름 — 덱 *PART 제목(deep 의 파트별 단면 키워드가 맞추는 이름과 같은 출처). 덱이 없으면 PID 표식.
    // 예전에는 「d3plot 에는 이름이 없다」 며 늘 Part<id> 라 폴더를 보고 키워드를 고르면 헛쳤다(2026-11-08 v50 판정).
    auto mesh = reader.read_mesh();
    const auto deck_names = UnifiedConfigParser::loadPartNames(reader.getFilePath());
    std::map<int, std::string> part_names;
    auto add_pname = [&](int32_t pid) {
        auto it = deck_names.find(pid);
        part_names[static_cast<int>(pid)] = (it != deck_names.end() && !it->second.empty())
            ? it->second : "Part" + std::to_string(pid);
    };
    for (auto pid : mesh.solid_parts)        add_pname(pid);
    for (auto pid : mesh.shell_parts)        add_pname(pid);
    for (auto pid : mesh.thick_shell_parts)  add_pname(pid);

    bool all_success = true;
    for (const auto& job : config.part_section_renders) {
        if (!job.enabled) continue;

        // Determine part_ids: explicit > analysis result > all mesh parts
        std::vector<int> part_ids;
        if (!job.part_ids.empty()) {
            part_ids.assign(job.part_ids.begin(), job.part_ids.end());
        } else if (!analysis_result_part_ids.empty()) {
            part_ids.assign(analysis_result_part_ids.begin(),
                            analysis_result_part_ids.end());
        } else {
            for (auto pid : mesh.solid_parts)        part_ids.push_back(pid);
            for (auto pid : mesh.shell_parts)        part_ids.push_back(pid);
            for (auto pid : mesh.thick_shell_parts)  part_ids.push_back(pid);
        }
        // 숨길 파트(바닥 등)는 파트별 영상도 만들지 않는다
        part_ids.erase(std::remove_if(part_ids.begin(), part_ids.end(), [&](int pid) {
            return std::find(job.hide_part_ids.begin(), job.hide_part_ids.end(), pid) != job.hide_part_ids.end();
        }), part_ids.end());
        if (part_ids.empty()) {
            if (callback) callback("  [" + job.name + "] No parts to render — skipped");
            continue;
        }

        // Resolve output dir (relative paths joined to config.output_directory).
        fs::path out_root = job.output_directory;
        if (!out_root.is_absolute()) {
            fs::path base = config.output_directory.empty()
                            ? fs::current_path()
                            : fs::path(config.output_directory);
            out_root = base / out_root;
        }
        try { fs::create_directories(out_root); } catch (...) {}

        if (callback) {
            callback("  [" + job.name + "] " +
                     std::to_string(part_ids.size()) + " parts × " +
                     std::to_string(job.axes.size()) + " axes" +
                     (job.section_view ? " + section_view" : "") +
                     (job.iso_clip_view ? " + iso_clip" : ""));
        }

        // Build options
        render::RenderOptions ropts;
        ropts.fringe_type = fringeForJob(job.fringe_type, job.name, callback);
        ropts.image_width  = job.resolution.size() > 0 ? job.resolution[0] : 1280;
        ropts.image_height = job.resolution.size() > 1 ? job.resolution[1] : 720;
        ropts.fps = job.fps;
        ropts.state_step = job.state_step;
        ropts.create_animation = true;
        ropts.video_format = render::VideoFormat::MP4;
        ropts.hidden_parts.assign(job.hide_part_ids.begin(), job.hide_part_ids.end());
        ropts.hidden_kinds = partKinds(mesh, job.hide_part_ids);

        render::PartSectionOptions psopts;
        psopts.section_view     = job.section_view;
        psopts.iso_clip_view    = job.iso_clip_view;
        psopts.axes.assign(job.axes.begin(), job.axes.end());
        psopts.section_position = job.section_position;
        psopts.section_margin   = job.section_margin;
        psopts.iso_clip_margin  = job.iso_clip_margin;
        psopts.edge_width       = job.edge_width;
        psopts.crf              = job.crf;
        psopts.reverse_cut      = job.reverse_cut;
        psopts.sliding_view           = job.sliding_view;
        psopts.sliding_section_style  = job.sliding_section_style;
        psopts.sliding_iso_style      = job.sliding_iso_style;
        psopts.sliding_steps          = job.sliding_steps;
        psopts.sliding_near_to_far    = job.sliding_near_to_far;
        psopts.sliding_pad            = job.sliding_pad;
        psopts.sliding_freeze_time    = job.sliding_freeze_time;
        psopts.sliding_peak_time      = job.sliding_peak_time;

        render::LSPrePostRenderer renderer(lsprepost_path);
        int n_success = renderer.renderAllPartSections(
            config.d3plot_path,
            reader,
            out_root.string(),
            part_ids,
            part_names,
            ropts,
            psopts
        );
        int total_views = static_cast<int>(part_ids.size()) *
                          static_cast<int>(job.axes.size()) *
                          ((job.section_view ? 1 : 0) + (job.iso_clip_view ? 1 : 0));

        if (callback) {
            callback("  [" + job.name + "] Done: " +
                     std::to_string(n_success) + "/" +
                     std::to_string(total_views) + " renders");
        }
        if (n_success < total_views) all_success = false;
    }

    return all_success;
#else
    if (callback) callback("  Part section renders skipped: render module disabled");
    return false;
#endif
}

} // namespace analysis
} // namespace kood3plot
