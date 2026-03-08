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
#include <cmath>
#include <filesystem>
#include <future>
#include <mutex>
#include <set>
#include <thread>

#ifdef KOOD3PLOT_HAS_RENDER
#include "kood3plot/render/LSPrePostRenderer.h"
#include "kood3plot/render/GeometryAnalyzer.h"
#include "kood3plot/render/RenderConfig.h"
#endif

namespace kood3plot {
namespace analysis {

#ifdef KOOD3PLOT_HAS_RENDER
namespace {

/// Compute von_mises stress range for target parts by sampling a few states.
/// Returns {min, max}. Reads only ~5 evenly spaced states for speed.
std::pair<double, double> computePartFringeRange(
    D3plotReader& reader,
    const std::vector<int32_t>& target_parts,
    size_t total_states)
{
    if (target_parts.empty() || total_states == 0) return {0.0, 0.0};

    auto mesh = reader.read_mesh();
    const auto& ctrl = reader.get_control_data();
    int nv3d = ctrl.NV3D;
    int nv2d = ctrl.NV2D;

    // Build element index sets for target parts (solids + shells)
    std::set<int32_t> target_set(target_parts.begin(), target_parts.end());
    std::vector<size_t> solid_indices, shell_indices;

    for (size_t i = 0; i < mesh.solid_materials.size(); ++i) {
        if (target_set.count(mesh.solid_materials[i])) solid_indices.push_back(i);
    }
    for (size_t i = 0; i < mesh.shell_materials.size(); ++i) {
        if (target_set.count(mesh.shell_materials[i])) shell_indices.push_back(i);
    }

    if (solid_indices.empty() && shell_indices.empty()) return {0.0, 0.0};

    // Sample ~5 evenly spaced states (including last)
    std::vector<size_t> sample_states;
    if (total_states <= 5) {
        for (size_t i = 0; i < total_states; ++i) sample_states.push_back(i);
    } else {
        for (int k = 0; k < 5; ++k) {
            sample_states.push_back(k * (total_states - 1) / 4);
        }
    }

    double range_min = std::numeric_limits<double>::max();
    double range_max = 0.0;

    auto calc_vm = [](double sxx, double syy, double szz,
                      double sxy, double syz, double szx) -> double {
        double d1 = sxx - syy, d2 = syy - szz, d3 = szz - sxx;
        return std::sqrt(0.5 * (d1*d1 + d2*d2 + d3*d3) + 3.0 * (sxy*sxy + syz*syz + szx*szx));
    };

    for (size_t si : sample_states) {
        auto state = reader.read_state(si);

        // Solid elements
        if (nv3d >= 7) {
            for (size_t ei : solid_indices) {
                size_t base = ei * nv3d;
                if (base + 6 > state.solid_data.size()) continue;
                double vm = calc_vm(state.solid_data[base], state.solid_data[base+1],
                                    state.solid_data[base+2], state.solid_data[base+3],
                                    state.solid_data[base+4], state.solid_data[base+5]);
                if (vm > range_max) range_max = vm;
                if (vm < range_min) range_min = vm;
            }
        }

        // Shell elements (mid-surface stress: first integration point)
        if (nv2d >= 7) {
            for (size_t ei : shell_indices) {
                size_t base = ei * nv2d;
                if (base + 6 > state.shell_data.size()) continue;
                double vm = calc_vm(state.shell_data[base], state.shell_data[base+1],
                                    state.shell_data[base+2], state.shell_data[base+3],
                                    state.shell_data[base+4], state.shell_data[base+5]);
                if (vm > range_max) range_max = vm;
                if (vm < range_min) range_min = vm;
            }
        }
    }

    if (range_max <= 0.0) return {0.0, 0.0};
    return {0.0, range_max};  // min=0 for von_mises (always >= 0)
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
            if (callback && !pattern_parts.empty()) {
                callback("    Pattern '" + job.part_pattern + "' matched " +
                         std::to_string(pattern_parts.size()) + " parts");
            }
        }

        // Calculate bounding boxes
        render::BoundingBox model_bbox = render::GeometryAnalyzer::calculateModelBounds(reader, 0);
        render::BoundingBox bbox;

        if (target_parts.empty()) {
            bbox = model_bbox;
        } else {
            bbox = render::GeometryAnalyzer::calculatePartBounds(reader, target_parts[0], 0);
            for (size_t i = 1; i < target_parts.size(); ++i) {
                auto part_bbox = render::GeometryAnalyzer::calculatePartBounds(reader, target_parts[i], 0);
                for (int a = 0; a < 3; ++a) {
                    bbox.min[a] = std::min(bbox.min[a], part_bbox.min[a]);
                    bbox.max[a] = std::max(bbox.max[a], part_bbox.max[a]);
                }
            }
            for (int a = 0; a < 3; ++a) {
                bbox.center[a] = (bbox.min[a] + bbox.max[a]) / 2.0;
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
        }

        // Full-model render (no sections): render once with the specified view
        if (job.sections.empty()) {
            RenderTask task;
            task.name = job.name;
            task.is_animation = (job.output.format == RenderOutputFormat::MP4);

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

            if (!job.fringe_type.empty()) {
                if (job.fringe_type == "von_mises")
                    task.options.fringe_type = render::FringeType::VON_MISES;
                else if (job.fringe_type == "eff_plastic_strain")
                    task.options.fringe_type = render::FringeType::EFFECTIVE_PLASTIC_STRAIN;
                else if (job.fringe_type == "displacement")
                    task.options.fringe_type = render::FringeType::DISPLACEMENT;
            }

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

            RenderTask task;
            task.plane.point = bbox.center;
            task.plane.point[axis] = abs_position;
            task.plane.normal = {0, 0, 0};
            task.plane.normal[axis] = 1.0;
            task.plane.visible = true;

            task.options.section_planes.push_back(task.plane);

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
                task.options.view = render::ViewOrientation::TOP;
            }

            task.options.image_width = job.output.resolution[0];
            task.options.image_height = job.output.resolution[1];

            if (!job.fringe_type.empty()) {
                if (job.fringe_type == "von_mises")
                    task.options.fringe_type = render::FringeType::VON_MISES;
                else if (job.fringe_type == "eff_plastic_strain")
                    task.options.fringe_type = render::FringeType::EFFECTIVE_PLASTIC_STRAIN;
                else if (job.fringe_type == "displacement")
                    task.options.fringe_type = render::FringeType::DISPLACEMENT;
                else if (job.fringe_type == "velocity")
                    task.options.fringe_type = render::FringeType::VELOCITY;
                else if (job.fringe_type == "acceleration")
                    task.options.fringe_type = render::FringeType::ACCELERATION;
            }

            if (!job.fringe_range.is_auto()) {
                task.options.auto_fringe_range = false;
                task.options.fringe_min = job.fringe_range.min;
                task.options.fringe_max = job.fringe_range.max;
            }

            if (!target_parts.empty()) {
                task.options.highlight_parts = std::vector<int>(target_parts.begin(), target_parts.end());
                task.options.context_parts = context_parts;

                bool is_z_axis = (axis == 2);
                if (!is_z_axis && task.options.auto_fringe_range) {
                    size_t total_states = reader.get_num_states();
                    auto [fmin, fmax] = computePartFringeRange(reader, target_parts, total_states);
                    if (fmax > 0.0) {
                        task.options.auto_fringe_range = false;
                        task.options.fringe_min = fmin;
                        task.options.fringe_max = fmax;
                        if (callback) {
                            callback("    Per-part fringe range: " +
                                     std::to_string(fmin) + " ~ " + std::to_string(fmax));
                        }
                    }
                }
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

} // namespace analysis
} // namespace kood3plot
