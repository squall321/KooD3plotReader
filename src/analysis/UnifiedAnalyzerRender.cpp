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
#include <filesystem>

#ifdef KOOD3PLOT_HAS_RENDER
#include "kood3plot/render/LSPrePostRenderer.h"
#include "kood3plot/render/GeometryAnalyzer.h"
#include "kood3plot/render/RenderConfig.h"
#endif

namespace kood3plot {
namespace analysis {

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

    render::LSPrePostRenderer renderer(lsprepost_path);

    // Check if LSPrePost is available
    if (!renderer.isAvailable()) {
        if (callback) callback("  WARNING: LSPrePost not found at: " + lsprepost_path);
        if (callback) callback("  Set lsprepost_path in YAML or install LSPrePost");
        return false;
    }

    bool all_success = true;

    for (const auto& job : config.render_jobs) {
        if (callback) callback("  Render: " + job.name);

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

        // Calculate bounding box for section positioning
        render::BoundingBox bbox;
        if (target_parts.empty()) {
            bbox = render::GeometryAnalyzer::calculateModelBounds(reader, 0);
        } else {
            // Calculate combined bounding box for all target parts
            bbox = render::GeometryAnalyzer::calculatePartBounds(reader, target_parts[0], 0);
            for (size_t i = 1; i < target_parts.size(); ++i) {
                auto part_bbox = render::GeometryAnalyzer::calculatePartBounds(reader, target_parts[i], 0);
                // Expand bbox
                for (int a = 0; a < 3; ++a) {
                    bbox.min[a] = std::min(bbox.min[a], part_bbox.min[a]);
                    bbox.max[a] = std::max(bbox.max[a], part_bbox.max[a]);
                }
            }
            // Update center
            for (int a = 0; a < 3; ++a) {
                bbox.center[a] = (bbox.min[a] + bbox.max[a]) / 2.0;
            }
        }

        if (callback) {
            callback("    Bounding box: [" +
                     std::to_string(bbox.min[0]) + ", " + std::to_string(bbox.min[1]) + ", " + std::to_string(bbox.min[2]) + "] to [" +
                     std::to_string(bbox.max[0]) + ", " + std::to_string(bbox.max[1]) + ", " + std::to_string(bbox.max[2]) + "]");
        }

        // Create output directory if needed
        if (!job.output.directory.empty()) {
            try {
                fs::create_directories(job.output.directory);
            } catch (const std::exception& e) {
                if (callback) callback("    Failed to create directory: " + std::string(e.what()));
            }
        }

        // Process each section specification
        for (const auto& section_spec : job.sections) {
            // Determine axis index (0=X, 1=Y, 2=Z)
            int axis = 2;  // default Z
            if (section_spec.axis == 'x' || section_spec.axis == 'X') axis = 0;
            else if (section_spec.axis == 'y' || section_spec.axis == 'Y') axis = 1;

            // Calculate absolute section position from normalized position
            double abs_position = bbox.min[axis] + section_spec.position * (bbox.max[axis] - bbox.min[axis]);

            // Create section plane
            render::SectionPlane plane;
            plane.point = bbox.center;
            plane.point[axis] = abs_position;
            plane.normal = {0, 0, 0};
            plane.normal[axis] = 1.0;
            plane.visible = true;

            // Set up render options
            render::RenderOptions options;
            options.section_planes.push_back(plane);

            // Set output format and animation settings
            if (job.output.format == RenderOutputFormat::MP4) {
                options.create_animation = true;
                options.video_format = render::VideoFormat::MP4;
                options.fps = job.output.fps;
            } else if (job.output.format == RenderOutputFormat::GIF) {
                options.create_animation = true;
                options.video_format = render::VideoFormat::AVI;  // Convert to GIF later
            } else {
                options.create_animation = false;
                if (job.output.format == RenderOutputFormat::PNG) {
                    options.image_format = render::ImageFormat::PNG;
                } else if (job.output.format == RenderOutputFormat::JPG) {
                    options.image_format = render::ImageFormat::JPG;
                }
            }

            // Set resolution
            options.image_width = job.output.resolution[0];
            options.image_height = job.output.resolution[1];

            // Parse fringe type
            if (!job.fringe_type.empty()) {
                if (job.fringe_type == "von_mises") {
                    options.fringe_type = render::FringeType::VON_MISES;
                } else if (job.fringe_type == "eff_plastic_strain") {
                    options.fringe_type = render::FringeType::EFFECTIVE_PLASTIC_STRAIN;
                } else if (job.fringe_type == "displacement") {
                    options.fringe_type = render::FringeType::DISPLACEMENT;
                } else if (job.fringe_type == "velocity") {
                    options.fringe_type = render::FringeType::VELOCITY;
                } else if (job.fringe_type == "acceleration") {
                    options.fringe_type = render::FringeType::ACCELERATION;
                }
            }

            // Set fringe range
            if (!job.fringe_range.is_auto()) {
                options.auto_fringe_range = false;
                options.fringe_min = job.fringe_range.min;
                options.fringe_max = job.fringe_range.max;
            }

            // Build output filename
            std::string pos_str = section_spec.position_auto.empty() ?
                                  std::to_string(static_cast<int>(section_spec.position * 100)) + "pct" :
                                  section_spec.position_auto;
            // Clean up position string for filename
            std::replace(pos_str.begin(), pos_str.end(), '%', 'p');

            std::string output_file = job.output.filename;
            if (output_file.empty()) {
                std::string axis_str(1, section_spec.axis);
                output_file = job.name + "_" + axis_str + "_" + pos_str;
                // Note: Don't add extension here - LSPrePostRenderer adds it automatically
            }

            // Clean filename (replace spaces)
            std::replace(output_file.begin(), output_file.end(), ' ', '_');

            if (!job.output.directory.empty()) {
                output_file = job.output.directory + "/" + output_file;
            }

            if (callback) {
                callback("    Section " + std::string(1, section_spec.axis) + " at " + pos_str +
                         " (abs: " + std::to_string(abs_position) + ")");
            }

            // Render
            bool success;
            if (options.create_animation) {
                success = renderer.renderAnimation(config.d3plot_path, output_file, options);
            } else {
                success = renderer.renderSectionView(config.d3plot_path, output_file, plane, options);
            }

            if (!success) {
                if (callback) callback("    FAILED: " + renderer.getLastError());
                all_success = false;
            } else {
                if (callback) callback("    Created: " + output_file);
            }
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
