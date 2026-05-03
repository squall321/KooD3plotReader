/**
 * @file LSPrePostRenderer.cpp
 * @brief Implementation of LSPrePost external renderer
 * @author KooD3plot Development Team
 * @date 2025-11-24
 * @version 3.1.0
 */

#include "kood3plot/render/LSPrePostRenderer.h"
#include "kood3plot/render/GeometryAnalyzer.h"
#include "kood3plot/D3plotReader.hpp"
#include <fstream>
#include <sstream>
#include <iostream>
#include <cstdlib>
#include <cmath>
#include <filesystem>
#include <set>
#include <map>
#include <atomic>
#include <iomanip>
#ifdef _WIN32
#include <windows.h>
#else
#include <unistd.h>
#include <sys/wait.h>
#endif

namespace kood3plot {
namespace render {

// ============================================================
// PIMPL Implementation
// ============================================================

// Global counter for unique worker IDs (thread-safe)
static std::atomic<int> g_worker_counter{0};

struct LSPrePostRenderer::Impl {
    std::string lsprepost_path = "lsprepost";
    std::string last_error;
    std::string last_output;
    int worker_id = g_worker_counter.fetch_add(1);  // unique per instance
};

// ============================================================
// Constructor/Destructor
// ============================================================

LSPrePostRenderer::LSPrePostRenderer(const std::string& lsprepost_path)
    : pImpl(std::make_unique<Impl>())
{
    // Convert to absolute path for reliable execution
    std::filesystem::path exe_path(lsprepost_path);
    if (!exe_path.is_absolute()) {
        exe_path = std::filesystem::absolute(exe_path);
    }
    pImpl->lsprepost_path = exe_path.string();

    // On Linux, automatically use Mesa wrapper if available
    #ifndef _WIN32
    std::filesystem::path mesa_wrapper = exe_path.parent_path() / "lspp412_mesa";

    if (std::filesystem::exists(mesa_wrapper)) {
        pImpl->lsprepost_path = std::filesystem::absolute(mesa_wrapper).string();
    }
    #endif
}

LSPrePostRenderer::~LSPrePostRenderer() = default;

// ============================================================
// Configuration
// ============================================================

void LSPrePostRenderer::setLSPrePostPath(const std::string& path) {
    pImpl->lsprepost_path = path;

    // On Linux, automatically use Mesa wrapper if available
    #ifndef _WIN32
    std::filesystem::path exe_path(path);
    std::filesystem::path mesa_wrapper = exe_path.parent_path() / "lspp412_mesa";

    if (std::filesystem::exists(mesa_wrapper)) {
        pImpl->lsprepost_path = mesa_wrapper.string();
    }
    #endif
}

std::string LSPrePostRenderer::getLSPrePostPath() const {
    return pImpl->lsprepost_path;
}

bool LSPrePostRenderer::isAvailable() const {
    // Check if lsprepost executable exists
    std::filesystem::path exe_path(pImpl->lsprepost_path);

    if (std::filesystem::exists(exe_path)) {
        return true;
    }

    // Try to find in PATH
#ifdef _WIN32
    std::string cmd = "where " + pImpl->lsprepost_path + " >nul 2>&1";
#else
    std::string cmd = "which " + pImpl->lsprepost_path + " >/dev/null 2>&1";
#endif

    return std::system(cmd.c_str()) == 0;
}

// ============================================================
// Rendering
// ============================================================

bool LSPrePostRenderer::renderImage(
    const std::string& d3plot_path,
    const std::string& output_path,
    const RenderOptions& options)
{
    // Convert to absolute paths
    std::filesystem::path abs_d3plot = std::filesystem::absolute(d3plot_path);
    std::filesystem::path abs_output = std::filesystem::absolute(output_path);

    // Generate script with absolute paths
    std::string script = generateScript(abs_d3plot.string(), abs_output.string(), options);

    // Save script to temporary file (in same directory as output)
    std::filesystem::path script_path = abs_output.parent_path() / (abs_output.filename().string() + "_temp.cfile");
    if (!saveScript(script, script_path.string())) {
        pImpl->last_error = "Failed to save script to: " + script_path.string();
        return false;
    }

    // Execute LSPrePost (working dir is d3plot directory)
    std::filesystem::path d3plot_dir = abs_d3plot.parent_path();
    std::string working_dir = d3plot_dir.string();

    bool success = executeLSPrePost(script_path.string(), working_dir);

    if (!success) {
        // Keep failed script for debugging
        std::filesystem::path fail_cfile = "/tmp/last_failed_render.cfile";
        std::error_code ec;
        std::filesystem::copy_file(script_path, fail_cfile,
            std::filesystem::copy_options::overwrite_existing, ec);
    }
    // Clean up temporary script
    std::filesystem::remove(script_path);

    return success;
}

bool LSPrePostRenderer::renderAnimation(
    const std::string& d3plot_path,
    const std::string& output_path,
    const RenderOptions& options)
{
    if (!options.create_animation) {
        pImpl->last_error = "create_animation must be true for renderAnimation";
        return false;
    }

    return renderImage(d3plot_path, output_path, options);
}

bool LSPrePostRenderer::renderSectionView(
    const std::string& d3plot_path,
    const std::string& output_path,
    const SectionPlane& plane,
    const RenderOptions& options)
{
    RenderOptions opts = options;
    opts.section_planes.clear();
    opts.section_planes.push_back(plane);

    return renderImage(d3plot_path, output_path, opts);
}

int LSPrePostRenderer::renderMultipleSections(
    const std::string& d3plot_path,
    const std::string& output_prefix,
    const std::vector<SectionPlane>& planes,
    const RenderOptions& options)
{
    int success_count = 0;

    for (size_t i = 0; i < planes.size(); ++i) {
        std::string output_path = output_prefix + "_section" + std::to_string(i);

        RenderOptions opts = options;
        opts.section_planes.clear();
        opts.section_planes.push_back(planes[i]);

        if (renderImage(d3plot_path, output_path, opts)) {
            success_count++;
        }
    }

    return success_count;
}

// ============================================================
// Script Generation
// ============================================================

std::string LSPrePostRenderer::generateScript(
    const std::string& d3plot_path,
    const std::string& output_path,
    const RenderOptions& options) const
{
    std::ostringstream script;
    script << std::fixed << std::setprecision(6);

    // Header
    script << "$# LS-PrePost command file generated by KooD3plotReader\n";
    script << "$# D3plot: " << d3plot_path << "\n\n";

    // Open d3plot file
    script << "bgstyle fade\n";
    script << "open d3plot \"" << d3plot_path << "\"\n";
    script << "ac\n";
    script << "mesh off\n\n";

    int fringe_code = fringeTypeToCode(options.fringe_type);

    // Per-part fringe isolation via genselect+reverse technique:
    // Target part gets fringe colormap, rest shows as original part colors.
    // Sequence: remove target → reverse → fringe/pfringe → all on
    bool has_target = !options.highlight_parts.empty();
    if (has_target) {
        script << "$# Isolate target part(s) for fringe\n";
        script << "genselect target part\n";
        script << "selectpart select 1\n";
        for (int pid : options.highlight_parts) {
            script << "genselect part remove part " << pid << "/0\n";
        }
        script << "selectpart reverse\n";
        script << "selectpart select 0\n";
        script << "fringe " << fringe_code << "\n";
        script << "pfringe\n\n";

        // Restore all parts visible
        script << "$# Restore all parts\n";
        script << "genselect target part\n";
        script << "selectpart select 1\n";
        script << "selectpart all on\n";
        script << "selectpart select 0\n\n";
    } else {
        // No target isolation — fringe on all parts
        script << "fringe " << fringe_code << "\n";
        script << "pfringe\n";
        if (!options.auto_fringe_range) {
            script << "range userdef " << options.fringe_min << " " << options.fringe_max << ";\n";
        }
        script << "\n";
    }

    // Set view orientation (view commands reset camera position)
    script << "$# Set view orientation\n";
    std::string view_str = viewOrientationToString(options.view);
    script << view_str << "\n";
    script << "ac\n\n";

    // Apply section planes
    // drawcut + projectview: smooth cut on ALL axes (X/Y/Z) via Xvfb
    if (!options.section_planes.empty()) {
        script << "$# Apply section planes (" << options.section_planes.size() << " planes)\n";
        for (size_t i = 0; i < options.section_planes.size(); ++i) {
            const auto& plane = options.section_planes[i];
            script << "splane dep0 "
                   << plane.point[0] << " " << plane.point[1] << " " << plane.point[2] << " "
                   << plane.normal[0] << " " << plane.normal[1] << " " << plane.normal[2] << "\n";
            script << "splane projectview\n";
            script << "splane drawcut\n";
        }
        script << "ac\n\n";
    }

    // Generate animation (LSPrePost batch mode only supports movie output, not single images)
    script << "$# Generate movie output\n";
    script << "anim forward\n";

    // LSPrePost appends the extension automatically to the filename given in the movie command.
    // Do NOT add the extension here; pass the bare filename so we get exactly one extension.
    std::string full_output = output_path;
    std::string movie_format = "MP4/H264";

    if (options.create_animation) {
        if (options.video_format == VideoFormat::AVI) {
            movie_format = "AVI";
        } else if (options.video_format == VideoFormat::WMV) {
            movie_format = "WMV";
        }
    }
    // For both animation and single-frame the movie command format stays MP4/H264 (default).

    // CRITICAL: movie mt 0 is required before the movie command (movie type initialization)
    script << "movie mt 0\n";
    script << "movie " << movie_format << " "
           << options.image_width << "x" << options.image_height
           << " \"" << full_output << "\" " << options.fps << "\n\n";

    // Clean up section plane if used
    if (!options.section_planes.empty()) {
        script << "splane done\n\n";
    }

    // Exit
    script << "exit\n";

    return script.str();
}

bool LSPrePostRenderer::saveScript(const std::string& script, const std::string& script_path) const {
    std::ofstream file(script_path);
    if (!file.is_open()) {
        return false;
    }

    file << script;
    file.close();

    return true;
}

// ============================================================
// Execution
// ============================================================

bool LSPrePostRenderer::executeLSPrePost(
    const std::string& script_path,
    const std::string& working_dir)
{
    // LSPrePost needs a real X11 display for proper view control (drawcut, projectview).
    // Strategy: start a dedicated Xvfb on a per-worker display, run LSPrePost against it,
    // then kill the Xvfb. This is more reliable than xvfb-run -a for section views.
    std::ostringstream cmd;
#ifndef _WIN32
    // Dedicated Xvfb display per worker (avoids conflicts in parallel rendering)
    int display_num = 10 + pImpl->worker_id;  // :10, :11, :12, ...
    cmd << "Xvfb :" << display_num << " -ac -screen 0 1600x1200x24 &"
        << " XVFB_PID=$!; sleep 0.5;"
        << " DISPLAY=:" << display_num << ".0"
        << " \"" << pImpl->lsprepost_path << "\" c=\"" << script_path << "\";"
        << " kill $XVFB_PID 2>/dev/null; wait $XVFB_PID 2>/dev/null";
#else
    cmd << "\"" << pImpl->lsprepost_path << "\" -nographics c=\"" << script_path << "\"";
#endif

#ifdef _WIN32
    // Windows execution
    STARTUPINFO si = {sizeof(STARTUPINFO)};
    PROCESS_INFORMATION pi;

    std::string cmd_str = cmd.str();

    // Change to working directory if specified
    const char* work_dir = working_dir.empty() ? nullptr : working_dir.c_str();

    BOOL success = CreateProcess(
        nullptr,
        const_cast<char*>(cmd_str.c_str()),
        nullptr,
        nullptr,
        FALSE,
        CREATE_NO_WINDOW,
        nullptr,
        work_dir,
        &si,
        &pi
    );

    if (!success) {
        pImpl->last_error = "Failed to execute LSPrePost";
        return false;
    }

    // Wait for completion
    WaitForSingleObject(pi.hProcess, INFINITE);

    DWORD exit_code;
    GetExitCodeProcess(pi.hProcess, &exit_code);

    CloseHandle(pi.hProcess);
    CloseHandle(pi.hThread);

    return exit_code == 0;
#else
    // Unix execution
    pid_t pid = fork();

    if (pid == -1) {
        pImpl->last_error = "Failed to fork process";
        return false;
    }

    if (pid == 0) {
        // Child process
        if (!working_dir.empty()) {
            chdir(working_dir.c_str());
        }

        // Isolate $HOME per worker to prevent lsppconf write conflicts
        // when multiple LSPrePost instances run in parallel
        std::string fake_home = "/tmp/lspp_worker_" + std::to_string(pImpl->worker_id);
        std::filesystem::create_directories(fake_home);
        setenv("HOME", fake_home.c_str(), 1);

        // Execute LSPrePost (Mesa wrapper handles all environment setup)
        execl("/bin/sh", "sh", "-c", cmd.str().c_str(), nullptr);
        _exit(1);  // exec failed
    }

    // Parent process - wait for child
    int status;
    waitpid(pid, &status, 0);

    if (!WIFEXITED(status)) {
        pImpl->last_error = "LSPrePost process terminated abnormally (signal)";
        return false;
    }
    int exit_code = WEXITSTATUS(status);
    if (exit_code != 0) {
        pImpl->last_error = "LSPrePost exited with code " + std::to_string(exit_code)
                          + " (cmd: " + cmd.str().substr(0, 200) + ")";
        return false;
    }
    return true;
#endif
}

std::string LSPrePostRenderer::getLastError() const {
    return pImpl->last_error;
}

std::string LSPrePostRenderer::getLastOutput() const {
    return pImpl->last_output;
}

// ============================================================
// ffmpeg re-encode helper
// ============================================================

static bool reencodeMP4(const std::string& path, int crf) {
    namespace fs = std::filesystem;
    if (crf <= 0) return true;  // skip
    std::string mp4 = path + ".mp4";
    if (!fs::exists(mp4)) return false;

    std::string tmp = path + "_tmp.mp4";
    std::ostringstream cmd;
    cmd << "ffmpeg -y -i \"" << mp4 << "\" -c:v libx264 -crf " << crf
        << " -preset medium -an \"" << tmp << "\" >/dev/null 2>&1";

    if (std::system(cmd.str().c_str()) == 0 && fs::exists(tmp)) {
        fs::rename(tmp, mp4);
        return true;
    }
    fs::remove(tmp);  // cleanup on failure
    return false;
}

// ============================================================
// All-Part Section View Batch Rendering
// ============================================================

int LSPrePostRenderer::renderAllPartSections(
    const std::string& d3plot_path,
    D3plotReader& reader,
    const std::string& output_dir,
    const std::vector<int>& part_ids,
    const std::map<int, std::string>& part_names,
    const RenderOptions& options,
    const PartSectionOptions& section_opts)
{
    namespace fs = std::filesystem;
    fs::path abs_d3plot = fs::absolute(d3plot_path);
    fs::path abs_output = fs::absolute(output_dir);
    fs::create_directories(abs_output);

    const double normals[][3] = {{1,0,0}, {0,1,0}, {0,0,1}};
    int fringe_code = fringeTypeToCode(options.fringe_type);

    // Axis char → index
    auto axisIndex = [](char c) -> int {
        if (c == 'x' || c == 'X') return 0;
        if (c == 'y' || c == 'Y') return 1;
        return 2;
    };

    // Parse "x"/"+x"/"-x"/... into (axis_index, sign)
    auto parseSignedAxis = [&](const std::string& s) -> std::pair<int,int> {
        int sign = 1;
        size_t p = 0;
        if (!s.empty() && (s[0] == '+' || s[0] == '-')) {
            sign = (s[0] == '-') ? -1 : 1;
            p = 1;
        }
        if (p >= s.size()) return {2, 1};  // fallback
        return {axisIndex(s[p]), sign};
    };

    // Iso clip view: rotation per axis
    // X-section: front → ry+45 → rx+35, clipplane +
    // Y-section: front → ry-45 → rx+35, clipplane -
    // Z-section: top  → ry+45 → rx-35, clipplane -
    struct IsoViewDef {
        const char* base_view;
        int ry_angle, rx_angle;
        const char* clip_sign;
    };
    // We keep ONE iso view per axis (camera position unchanged). axis_sign
    // only flips the cut normal and the clipplane side. This keeps the
    // viewer oriented to the same scene; "+y" and "-y" differ only in which
    // half of the part is cut away (and therefore in the slice progression).
    const IsoViewDef iso_views_base[3] = {
        {"front",  45,  35, "+"},  // X
        {"front", -45,  35, "-"},  // Y
        {"top",    45, -35, "-"},  // Z
    };

    int sliding_count = 0;
    if (section_opts.sliding_view) {
        if (section_opts.sliding_section_style) sliding_count++;
        if (section_opts.sliding_iso_style)     sliding_count++;
    }
    int views_per_axis = (section_opts.section_view ? 1 : 0)
                       + (section_opts.iso_clip_view ? 1 : 0)
                       + sliding_count;
    int total = (int)part_ids.size() * (int)section_opts.axes.size() * views_per_axis;
    int success = 0, current = 0;

    for (int pid : part_ids) {
        std::string pname;
        auto it = part_names.find(pid);
        if (it != part_names.end() && !it->second.empty()) {
            pname = it->second;
            for (char& c : pname) {
                if (c == '/' || c == '\\' || c == ' ' || c == ':') c = '_';
            }
        }
        std::string folder = "part_" + std::to_string(pid);
        if (!pname.empty()) folder += "_" + pname;

        fs::path part_dir = abs_output / folder;
        fs::create_directories(part_dir);

        auto part_bbox = GeometryAnalyzer::calculatePartBounds(reader, pid, 0);
        double pos = section_opts.section_position;
        double sp[3] = {
            part_bbox.min[0] + pos * (part_bbox.max[0] - part_bbox.min[0]),
            part_bbox.min[1] + pos * (part_bbox.max[1] - part_bbox.min[1]),
            part_bbox.min[2] + pos * (part_bbox.max[2] - part_bbox.min[2]),
        };

        // Helper: generate common fringe isolation block
        auto writeFringeIsolation = [&](std::ostringstream& s) {
            s << "genselect target part\n";
            s << "selectpart select 1\n";
            s << "genselect part remove part " << pid << "/0\n";
            s << "selectpart reverse\n";
            s << "selectpart select 0\n";
            s << "fringe " << fringe_code << "\n";
            s << "pfringe\n\n";
        };

        auto writeRestoreAll = [&](std::ostringstream& s) {
            s << "genselect target part\n";
            s << "selectpart select 1\n";
            s << "selectpart all on\n";
            s << "selectpart select 0\n\n";
        };

        auto writeTargetOnly = [&](std::ostringstream& s) {
            s << "genselect target part\n";
            s << "selectpart select 1\n";
            s << "selectpart all off\n";
            s << "selectpart part " << pid << " on\n";
            s << "selectpart select 0\n";
        };

        for (const std::string& axis_str : section_opts.axes) {
            auto [ai, axis_sign] = parseSignedAxis(axis_str);
            char axis_char = "xyz"[ai];
            // Output folder/file label: keep "x"/"y"/"z" for unsigned, use
            // "x_neg"/"y_neg"/"z_neg" for negative sign so default behaviour
            // is unchanged for users not using signed axes.
            std::string axis_name(1, axis_char);
            if (axis_sign < 0) axis_name += "_neg";
            // Effective normal vector with sign applied
            double eff_normal[3] = {
                normals[ai][0] * axis_sign,
                normals[ai][1] * axis_sign,
                normals[ai][2] * axis_sign,
            };

            // ── (A) Section view: projectview + drawcut ──
            if (section_opts.section_view) {
                current++;
                fs::path out_path = part_dir / ("section_" + axis_name);
                std::cout << "[SectionView] (" << current << "/" << total << ") "
                          << "Part " << pid << " section-" << axis_name
                          << " pos=" << (int)(pos*100) << "%"
                          << (pname.empty() ? "" : " (" + pname + ")") << "\n";

                double sm = section_opts.section_margin;
                std::ostringstream script;
                script << std::fixed << std::setprecision(6);
                script << "bgstyle fade\n"
                       << "open d3plot \"" << abs_d3plot.string() << "\"\n"
                       << "ac\nmesh off\n"
                       << "edgelwidth " << section_opts.edge_width << "\n\n";

                writeFringeIsolation(script);
                writeTargetOnly(script);

                script << "splane dep0 " << sp[0] << " " << sp[1] << " " << sp[2] << " "
                       << eff_normal[0] << " " << eff_normal[1] << " " << eff_normal[2] << "\n"
                       << "splane projectview\nsplane drawcut\nac\n"
                       << "zin " << sm << " " << sm << " " << (1.0-sm) << " " << (1.0-sm) << "\n\n";

                writeRestoreAll(script);

                script << "anim forward\nmovie mt 0\n"
                       << "movie MP4/H264 " << options.image_width << "x" << options.image_height
                       << " \"" << out_path.string() << "\" " << options.fps << "\n\n"
                       << "splane done\nexit\n";

                fs::path cfile = part_dir / ("section_" + axis_name + ".cfile");
                if (saveScript(script.str(), cfile.string())) {
                    if (executeLSPrePost(cfile.string(), abs_d3plot.parent_path().string())) {
                        reencodeMP4(out_path.string(), section_opts.crf);
                        success++;
                    } else {
                        std::cerr << "[SectionView] FAILED: Part " << pid << " section-" << axis_name << "\n";
                    }
                    fs::remove(cfile);
                }
            }

            // ── (B) Iso clip view: isometric + drawcut + clipplane ──
            // Same pattern as sliding_iso (drawcut renders the smooth section
            // surface, clipplane removes one side). axis_sign flips the
            // effective normal so clipplane "-" cuts the correct physical side.
            if (section_opts.iso_clip_view) {
                current++;
                fs::path out_path = part_dir / ("iso_clip_" + axis_name);
                const auto& iv = iso_views_base[ai];
                double im = section_opts.iso_clip_margin;
                std::cout << "[SectionView] (" << current << "/" << total << ") "
                          << "Part " << pid << " iso_clip-" << axis_name
                          << " pos=" << (int)(pos*100) << "%"
                          << (pname.empty() ? "" : " (" + pname + ")") << "\n";

                std::ostringstream script;
                script << std::fixed << std::setprecision(6);
                script << "bgstyle fade\n"
                       << "open d3plot \"" << abs_d3plot.string() << "\"\n"
                       << "ac\nmesh off\nshademode 1\n"
                       << "edgelwidth " << section_opts.edge_width << "\n\n";

                writeFringeIsolation(script);
                writeRestoreAll(script);

                // Part fit
                script << "selectpart all off\n"
                       << "selectpart part " << pid << " on\n"
                       << "vauto\n"
                       << "selectpart all on\n";

                // Iso view orientation
                script << iv.base_view << "\n"
                       << "rotang " << iv.ry_angle << "\nry\n"
                       << "rotang " << iv.rx_angle << "\nrx\n";

                // drawcut + clipplane combo (smooth section + one side clipped)
                script << "splane dep0 " << sp[0] << " " << sp[1] << " " << sp[2] << " "
                       << eff_normal[0] << " " << eff_normal[1] << " " << eff_normal[2] << "\n"
                       << "splane drawcut\n"
                       << "splane clipplane -\nac\n"
                       << "zin " << im << " " << im << " " << (1.0-im) << " " << (1.0-im) << "\n\n";

                script << "anim forward\nmovie mt 0\n"
                       << "movie MP4/H264 " << options.image_width << "x" << options.image_height
                       << " \"" << out_path.string() << "\" " << options.fps << "\n\n"
                       << "splane done\nexit\n";

                fs::path cfile = part_dir / ("iso_clip_" + axis_name + ".cfile");
                if (saveScript(script.str(), cfile.string())) {
                    if (executeLSPrePost(cfile.string(), abs_d3plot.parent_path().string())) {
                        reencodeMP4(out_path.string(), section_opts.crf);
                        success++;
                    } else {
                        std::cerr << "[SectionView] FAILED: Part " << pid << " iso_clip-" << axis_name << "\n";
                    }
                    fs::remove(cfile);
                }
            }

            // ── (C) Sliding section view (section style) ──
            if (section_opts.sliding_view && section_opts.sliding_section_style) {
                current++;
                std::cout << "[SectionView] (" << current << "/" << total << ") "
                          << "Part " << pid << " sliding-section-" << axis_name
                          << " (" << section_opts.sliding_steps << " steps)"
                          << (pname.empty() ? "" : " (" + pname + ")") << "\n";
                int rc = renderSlidingSection(
                    abs_d3plot.string(), reader, part_dir.string(),
                    pid, axis_char, axis_sign, SlidingStyle::SECTION,
                    options, section_opts);
                if (rc) success++;
            }

            // ── (D) Sliding iso view ──
            if (section_opts.sliding_view && section_opts.sliding_iso_style) {
                current++;
                std::cout << "[SectionView] (" << current << "/" << total << ") "
                          << "Part " << pid << " sliding-iso-" << axis_name
                          << " (" << section_opts.sliding_steps << " steps)"
                          << (pname.empty() ? "" : " (" + pname + ")") << "\n";
                int rc = renderSlidingSection(
                    abs_d3plot.string(), reader, part_dir.string(),
                    pid, axis_char, axis_sign, SlidingStyle::ISO,
                    options, section_opts);
                if (rc) success++;
            }
        }
    }

    std::cout << "[SectionView] Completed: " << success << "/" << total << " renders\n";
    return success;
}

// ============================================================
// renderSlidingSection — sliding cut plane animation along an axis
// ============================================================

int LSPrePostRenderer::renderSlidingSection(
    const std::string& d3plot_path,
    D3plotReader& reader,
    const std::string& part_dir_str,
    int part_id,
    char axis_char,
    int axis_sign,
    SlidingStyle style,
    const RenderOptions& options,
    const PartSectionOptions& section_opts)
{
    bool is_iso = (style == SlidingStyle::ISO);
    std::string style_tag = is_iso ? "iso" : "section";
    if (axis_sign == 0) axis_sign = 1;
    namespace fs = std::filesystem;
    fs::path abs_d3plot = fs::absolute(d3plot_path);
    fs::path part_dir = fs::absolute(part_dir_str);
    fs::create_directories(part_dir);

    auto axisIndex = [](char c) -> int {
        if (c == 'x' || c == 'X') return 0;
        if (c == 'y' || c == 'Y') return 1;
        return 2;
    };
    int ai = axisIndex(axis_char);
    std::string axis_name(1, axis_char);
    if (axis_sign < 0) axis_name += "_neg";

    int N = std::max(2, section_opts.sliding_steps);
    int fringe_code = fringeTypeToCode(options.fringe_type);

    // Part bbox along the chosen axis
    auto part_bbox = GeometryAnalyzer::calculatePartBounds(reader, part_id, 0);
    double extent = part_bbox.max[ai] - part_bbox.min[ai];
    double pad = section_opts.sliding_pad * std::max(extent, 1e-6);
    double a_min = part_bbox.min[ai] - pad;
    double a_max = part_bbox.max[ai] + pad;

    // Center the plane in the other two axes (use part bbox center)
    double center[3] = {
        (part_bbox.min[0] + part_bbox.max[0]) * 0.5,
        (part_bbox.min[1] + part_bbox.max[1]) * 0.5,
        (part_bbox.min[2] + part_bbox.max[2]) * 0.5,
    };

    const double normals[][3] = {{1,0,0}, {0,1,0}, {0,0,1}};

    // Effective normal (axis_sign applied)
    double eff_normal[3] = {
        normals[ai][0] * axis_sign,
        normals[ai][1] * axis_sign,
        normals[ai][2] * axis_sign,
    };

    // Helpers (mirror renderAllPartSections)
    auto writeFringeIsolation = [&](std::ostringstream& s) {
        s << "genselect target part\n";
        s << "selectpart select 1\n";
        s << "genselect part remove part " << part_id << "/0\n";
        s << "selectpart reverse\n";
        s << "selectpart select 0\n";
        s << "fringe " << fringe_code << "\n";
        s << "pfringe\n\n";
    };
    auto writeRestoreAll = [&](std::ostringstream& s) {
        s << "genselect target part\n";
        s << "selectpart select 1\n";
        s << "selectpart all on\n";
        s << "selectpart select 0\n\n";
    };

    // Compute N step positions (camera-near → far if requested).
    // projectview/iso camera sits on the side the (signed) normal points to:
    //   axis_sign=+1: camera is on +axis side, so "near"=a_max, "far"=a_min
    //   axis_sign=-1: camera is on -axis side, so "near"=a_min, "far"=a_max
    bool from_max = (section_opts.sliding_near_to_far ? (axis_sign > 0)
                                                       : (axis_sign < 0));
    std::vector<double> positions(N);
    for (int i = 0; i < N; ++i) {
        double frac = static_cast<double>(i) / (N - 1);
        double pos;
        if (from_max) {
            pos = a_max - frac * (a_max - a_min);
        } else {
            pos = a_min + frac * (a_max - a_min);
        }
        positions[i] = pos;
    }

    // ── Iso style config (only used when style==ISO) ──
    // Single iso view per axis (camera unchanged). axis_sign and reverse_cut
    // both flip the clipplane side. This matches the iso_clip_view (X% fixed)
    // behaviour: with reverse_cut=true the camera-near side is clipped so the
    // section + far-side mesh stay visible — i.e. the user always sees the
    // interior cross-section, regardless of where the plane is along the slide.
    struct IsoViewDef { const char* base_view; int ry, rx; const char* clip_sign; };
    const IsoViewDef iso_views_base[3] = {
        {"front",  45,  35, "+"},  // X
        {"front", -45,  35, "-"},  // Y
        {"top",    45, -35, "-"},  // Z
    };
    const IsoViewDef& iv = iso_views_base[ai];

    const char* sign = iv.clip_sign;
    if (axis_sign < 0) sign = (sign[0] == '+') ? "-" : "+";
    if (section_opts.reverse_cut) sign = (sign[0] == '+') ? "-" : "+";

    // Generate N cfiles, each producing a full-length mp4 with cut at positions[i]
    std::vector<fs::path> step_mp4s(N);
    for (int i = 0; i < N; ++i) {
        std::ostringstream script;
        script << std::fixed << std::setprecision(6);
        script << "bgstyle fade\n"
               << "open d3plot \"" << abs_d3plot.string() << "\"\n"
               << "ac\nmesh off\n";
        if (is_iso) script << "shademode 1\n";
        script << "edgelwidth " << section_opts.edge_width << "\n\n";
        writeFringeIsolation(script);
        writeRestoreAll(script);

        double sp[3] = {center[0], center[1], center[2]};
        sp[ai] = positions[i];

        if (is_iso) {
            // ISO style: isometric camera + splane drawcut + splane clipplane.
            //   Verified pattern (matches user-supplied working cfile):
            //     splane dep0 X Y Z nx ny nz
            //     splane drawcut         ← draws the smooth section surface
            //     splane clipplane -     ← clips one side; sign of normal
            //                              (controlled by axis_sign) chooses
            //                              which physical side gets removed
            //   Why both: drawcut alone (without projectview) yields a blank
            //   screen; clipplane alone removes a side but draws no surface;
            //   together they give a smooth visible slice with one half cut.
            //   axis_sign already flips eff_normal[], which automatically
            //   reverses what "clipplane -" cuts away — so user can pick the
            //   visible side via "+y" vs "-y".
            double im = section_opts.iso_clip_margin;
            script << "selectpart all off\n"
                   << "selectpart part " << part_id << " on\n"
                   << "vauto\n"
                   << "selectpart all on\n";
            script << iv.base_view << "\n"
                   << "rotang " << iv.ry << "\nry\n"
                   << "rotang " << iv.rx << "\nrx\n";
            script << "splane dep0 " << sp[0] << " " << sp[1] << " " << sp[2] << " "
                   << eff_normal[0] << " " << eff_normal[1] << " " << eff_normal[2] << "\n"
                   << "splane drawcut\n"
                   << "splane clipplane -\nac\n"
                   << "zin " << im << " " << im << " " << (1.0-im) << " " << (1.0-im) << "\n\n";
        } else {
            // SECTION style: projectview + drawcut (2D slice plate)
            double sm = section_opts.section_margin;
            script << "splane dep0 " << sp[0] << " " << sp[1] << " " << sp[2] << " "
                   << eff_normal[0] << " " << eff_normal[1] << " " << eff_normal[2] << "\n"
                   << "splane projectview\nsplane drawcut\nac\n"
                   << "zin " << sm << " " << sm << " " << (1.0-sm) << " " << (1.0-sm) << "\n\n";
        }

        char namebuf[64];
        std::snprintf(namebuf, sizeof(namebuf), "sliding_%s_%s_step%03d",
                      style_tag.c_str(), axis_name.c_str(), i);
        fs::path step_path = part_dir / namebuf;
        step_mp4s[i] = part_dir / (std::string(namebuf) + ".mp4");

        script << "movie mt 0\n"
               << "movie MP4/H264 " << options.image_width << "x" << options.image_height
               << " \"" << step_path.string() << "\" " << options.fps << "\n\n"
               << "splane done\nexit\n";

        fs::path cfile = part_dir / (std::string(namebuf) + ".cfile");
        if (!saveScript(script.str(), cfile.string())) {
            std::cerr << "[Sliding] Failed to write cfile " << cfile << "\n";
            return 0;
        }
        if (!executeLSPrePost(cfile.string(), abs_d3plot.parent_path().string())) {
            std::cerr << "[Sliding] FAILED step " << i << " (Part " << part_id
                      << " axis " << axis_name << ")\n";
            // Continue producing remaining steps; ffmpeg will work with what exists
        }
        fs::remove(cfile);
    }

    // Probe duration from the first existing mp4
    double total_sec = 0.0;
    fs::path probe_src;
    for (auto& p : step_mp4s) {
        if (fs::exists(p) && fs::file_size(p) > 1024) { probe_src = p; break; }
    }
    if (probe_src.empty()) {
        std::cerr << "[Sliding] All step mp4s missing/empty for part " << part_id << "\n";
        return 0;
    }
    {
        std::string probe_cmd = "ffprobe -v error -show_entries format=duration "
                                "-of default=nw=1:nk=1 \"" + probe_src.string() + "\" 2>/dev/null";
        FILE* f = popen(probe_cmd.c_str(), "r");
        if (f) {
            char buf[64] = {0};
            if (fgets(buf, sizeof(buf), f)) total_sec = std::atof(buf);
            pclose(f);
        }
    }
    if (total_sec <= 0.01) total_sec = 6.0;  // fallback
    double slice_sec = total_sec / N;
    bool keep_debug = std::getenv("KOOD3PLOT_DEBUG_SLIDING") != nullptr;

    // ── Frozen-time mode: extract one frame at peak_time from each step mp4
    //    and stitch into an image-sequence video. Time stays fixed; only the
    //    cut plane sweeps through the part frame-by-frame.
    if (section_opts.sliding_freeze_time) {
        double peak_time = section_opts.sliding_peak_time;
        if (peak_time < 0) peak_time = total_sec * 0.95;  // default: near end
        if (peak_time > total_sec) peak_time = total_sec * 0.99;

        fs::path frames_dir = part_dir / ("sliding_" + style_tag + "_" + axis_name + "_frames");
        std::error_code ec_mk;
        fs::create_directories(frames_dir, ec_mk);

        int captured = 0;
        for (int i = 0; i < N; ++i) {
            if (!fs::exists(step_mp4s[i]) || fs::file_size(step_mp4s[i]) < 1024) continue;
            char fname[64];
            std::snprintf(fname, sizeof(fname), "frame_%03d.png", i);
            fs::path fpath = frames_dir / fname;
            std::ostringstream cmd;
            cmd << "ffmpeg -y -loglevel error "
                << "-ss " << std::fixed << std::setprecision(4) << peak_time
                << " -i \"" << step_mp4s[i].string() << "\" "
                << "-frames:v 1 -q:v 2 \"" << fpath.string() << "\" 2>/dev/null";
            if (std::system(cmd.str().c_str()) == 0 && fs::exists(fpath)) captured++;
        }
        if (captured == 0) {
            std::cerr << "[Sliding] freeze_time: no frames captured at t=" << peak_time << "\n";
            return 0;
        }

        fs::path final_path = part_dir / ("sliding_" + style_tag + "_" + axis_name + ".mp4");
        {
            std::ostringstream cmd;
            cmd << "ffmpeg -y -loglevel error "
                << "-framerate " << options.fps << " "
                << "-i \"" << (frames_dir / "frame_%03d.png").string() << "\" "
                << "-c:v libx264 -preset fast -crf " << section_opts.crf << " "
                << "-pix_fmt yuv420p "
                << "\"" << final_path.string() << "\" 2>/dev/null";
            std::system(cmd.str().c_str());
        }

        if (!keep_debug) {
            std::error_code ec; fs::remove_all(frames_dir, ec);
            for (auto& p : step_mp4s) { std::error_code ec2; fs::remove(p, ec2); }
        } else {
            std::cout << "[Sliding] DEBUG: kept frames in " << frames_dir << "\n";
        }

        if (fs::exists(final_path) && fs::file_size(final_path) > 1024) {
            std::cout << "[Sliding] Created (frozen t=" << std::fixed << std::setprecision(4)
                      << peak_time << "): " << final_path << " (" << captured
                      << " positions, " << options.fps << " fps)\n";
            return 1;
        }
        std::cerr << "[Sliding] freeze_time: image2 mp4 build failed\n";
        return 0;
    }

    // Trim each step mp4 to its time slice and re-encode (concat-safe)
    std::vector<fs::path> trimmed_mp4s;
    for (int i = 0; i < N; ++i) {
        if (!fs::exists(step_mp4s[i]) || fs::file_size(step_mp4s[i]) < 1024) continue;
        double start = i * slice_sec;
        char tname[64];
        std::snprintf(tname, sizeof(tname), "sliding_%s_%s_trim%03d.mp4",
                      style_tag.c_str(), axis_name.c_str(), i);
        fs::path tpath = part_dir / tname;
        std::ostringstream cmd;
        cmd << "ffmpeg -y -loglevel error "
            << "-ss " << std::fixed << std::setprecision(4) << start
            << " -t " << slice_sec
            << " -i \"" << step_mp4s[i].string() << "\" "
            << "-c:v libx264 -preset fast -crf " << section_opts.crf << " "
            << "\"" << tpath.string() << "\"";
        if (std::system(cmd.str().c_str()) == 0 && fs::exists(tpath)) {
            trimmed_mp4s.push_back(tpath);
        }
    }
    if (trimmed_mp4s.empty()) {
        std::cerr << "[Sliding] No trimmed clips produced\n";
        return 0;
    }

    // Write concat list
    fs::path list_txt = part_dir / ("sliding_" + style_tag + "_" + axis_name + "_concat.txt");
    {
        std::ofstream of(list_txt);
        for (auto& p : trimmed_mp4s) {
            of << "file '" << p.string() << "'\n";
        }
    }
    fs::path final_path = part_dir / ("sliding_" + style_tag + "_" + axis_name + ".mp4");
    {
        std::ostringstream cmd;
        cmd << "ffmpeg -y -loglevel error -f concat -safe 0 "
            << "-i \"" << list_txt.string() << "\" -c copy "
            << "\"" << final_path.string() << "\"";
        std::system(cmd.str().c_str());
    }

    // Cleanup intermediates (skip when KOOD3PLOT_DEBUG_SLIDING is set)
    if (!keep_debug) {
        for (auto& p : step_mp4s) {
            std::error_code ec; fs::remove(p, ec);
        }
        for (auto& p : trimmed_mp4s) {
            std::error_code ec; fs::remove(p, ec);
        }
        std::error_code ec; fs::remove(list_txt, ec);
    } else {
        std::cout << "[Sliding] DEBUG: kept intermediates in " << part_dir << "\n";
    }

    if (fs::exists(final_path) && fs::file_size(final_path) > 1024) {
        std::cout << "[Sliding] Created: " << final_path << " (" << N << " steps, "
                  << std::fixed << std::setprecision(2) << total_sec << "s)\n";
        return 1;
    }
    std::cerr << "[Sliding] Concat failed for part " << part_id << " axis " << axis_name << "\n";
    return 0;
}

// ============================================================
// Helper Methods
// ============================================================

int LSPrePostRenderer::fringeTypeToCode(FringeType type) const {
    // LSPrePost numeric fringe codes (from KooDynaPostProcessor mapping)
    switch (type) {
        // Stress components (IDs: 1-6)
        case FringeType::STRESS_XX: return 1;
        case FringeType::STRESS_YY: return 2;
        case FringeType::STRESS_ZZ: return 3;
        case FringeType::STRESS_XY: return 4;
        case FringeType::STRESS_YZ: return 5;
        case FringeType::STRESS_XZ: return 6;

        // Plastic strain (ID: 7)
        case FringeType::EFFECTIVE_PLASTIC_STRAIN: return 7;

        // Pressure (ID: 8)
        case FringeType::PRESSURE: return 8;

        // Von Mises stress (ID: 9)
        case FringeType::VON_MISES: return 9;

        // Max shear stress (ID: 13)
        case FringeType::MAX_SHEAR_STRESS: return 13;

        // Principal stresses (IDs: 14-16)
        case FringeType::PRINCIPAL_STRESS_1: return 14;
        case FringeType::PRINCIPAL_STRESS_2: return 15;
        case FringeType::PRINCIPAL_STRESS_3: return 16;

        // Displacement components (IDs: 17-20)
        case FringeType::DISPLACEMENT_X: return 17;
        case FringeType::DISPLACEMENT_Y: return 18;
        case FringeType::DISPLACEMENT_Z: return 19;
        case FringeType::DISPLACEMENT: return 20;

        // Velocity and Acceleration (IDs: 23-24)
        case FringeType::ACCELERATION: return 23;
        case FringeType::VELOCITY: return 24;

        // Energy (ID: 43)
        case FringeType::HOURGLASS_ENERGY_DENSITY: return 43;

        // Strain components (IDs: 57-62)
        case FringeType::STRAIN_XX: return 57;
        case FringeType::STRAIN_YY: return 58;
        case FringeType::STRAIN_ZZ: return 59;
        case FringeType::STRAIN_XY: return 60;
        case FringeType::STRAIN_YZ: return 61;
        case FringeType::STRAIN_XZ: return 62;

        // Shell properties (ID: 67)
        case FringeType::SHELL_THICKNESS: return 67;

        // Principal strains (IDs: 77-79)
        case FringeType::PRINCIPAL_STRAIN_1: return 77;
        case FringeType::PRINCIPAL_STRAIN_2: return 78;
        case FringeType::PRINCIPAL_STRAIN_3: return 79;

        // Effective strain (ID: 80)
        case FringeType::EFFECTIVE_STRAIN: return 80;

        // Advanced properties (IDs: 520-530)
        case FringeType::TRIAXIALITY: return 520;
        case FringeType::NORMALIZED_MEAN_STRESS: return 521;
        case FringeType::STRAIN_ENERGY_DENSITY: return 524;
        case FringeType::VOLUMETRIC_STRAIN: return 529;
        case FringeType::SIGNED_VON_MISES: return 530;

        default: return 9;  // default to Von Mises
    }
}

std::string LSPrePostRenderer::fringeTypeToString(FringeType type) const {
    switch (type) {
        // Stress components
        case FringeType::STRESS_XX: return "stress_xx";
        case FringeType::STRESS_YY: return "stress_yy";
        case FringeType::STRESS_ZZ: return "stress_zz";
        case FringeType::STRESS_XY: return "stress_xy";
        case FringeType::STRESS_YZ: return "stress_yz";
        case FringeType::STRESS_XZ: return "stress_xz";

        // Plastic strain
        case FringeType::EFFECTIVE_PLASTIC_STRAIN: return "plastic_strain";

        // Pressure
        case FringeType::PRESSURE: return "pressure";

        // Von Mises stress
        case FringeType::VON_MISES: return "von_mises";

        // Max shear stress
        case FringeType::MAX_SHEAR_STRESS: return "max_shear_stress";

        // Principal stresses
        case FringeType::PRINCIPAL_STRESS_1: return "principal_stress_1";
        case FringeType::PRINCIPAL_STRESS_2: return "principal_stress_2";
        case FringeType::PRINCIPAL_STRESS_3: return "principal_stress_3";

        // Displacement components
        case FringeType::DISPLACEMENT_X: return "displacement_x";
        case FringeType::DISPLACEMENT_Y: return "displacement_y";
        case FringeType::DISPLACEMENT_Z: return "displacement_z";
        case FringeType::DISPLACEMENT: return "displacement";

        // Velocity and Acceleration
        case FringeType::ACCELERATION: return "acceleration";
        case FringeType::VELOCITY: return "velocity";

        // Energy
        case FringeType::HOURGLASS_ENERGY_DENSITY: return "hourglass_energy_density";

        // Strain components
        case FringeType::STRAIN_XX: return "strain_xx";
        case FringeType::STRAIN_YY: return "strain_yy";
        case FringeType::STRAIN_ZZ: return "strain_zz";
        case FringeType::STRAIN_XY: return "strain_xy";
        case FringeType::STRAIN_YZ: return "strain_yz";
        case FringeType::STRAIN_XZ: return "strain_xz";

        // Shell properties
        case FringeType::SHELL_THICKNESS: return "shell_thickness";

        // Principal strains
        case FringeType::PRINCIPAL_STRAIN_1: return "principal_strain_1";
        case FringeType::PRINCIPAL_STRAIN_2: return "principal_strain_2";
        case FringeType::PRINCIPAL_STRAIN_3: return "principal_strain_3";

        // Effective strain
        case FringeType::EFFECTIVE_STRAIN: return "effective_strain";

        // Advanced properties
        case FringeType::TRIAXIALITY: return "triaxiality";
        case FringeType::NORMALIZED_MEAN_STRESS: return "normalized_mean_stress";
        case FringeType::STRAIN_ENERGY_DENSITY: return "strain_energy_density";
        case FringeType::VOLUMETRIC_STRAIN: return "volumetric_strain";
        case FringeType::SIGNED_VON_MISES: return "signed_von_mises";

        default: return "von_mises";
    }
}

std::string LSPrePostRenderer::viewOrientationToString(ViewOrientation view) const {
    // LSPrePost uses direct view commands (not "view <orientation>")
    switch (view) {
        case ViewOrientation::TOP: return "top";
        case ViewOrientation::BOTTOM: return "bottom";
        case ViewOrientation::LEFT: return "left";
        case ViewOrientation::RIGHT: return "right";
        case ViewOrientation::FRONT: return "front";
        case ViewOrientation::BACK: return "back";
        case ViewOrientation::ISOMETRIC: return "iso";
        case ViewOrientation::CUSTOM: return "iso";  // Custom not supported, use iso
        default: return "iso";
    }
}

std::string LSPrePostRenderer::imageFormatToExtension(ImageFormat format) const {
    switch (format) {
        case ImageFormat::PNG: return ".png";
        case ImageFormat::JPG: return ".jpg";
        case ImageFormat::BMP: return ".bmp";
        case ImageFormat::TIFF: return ".tiff";
        default: return ".png";
    }
}

std::string LSPrePostRenderer::videoFormatToExtension(VideoFormat format) const {
    switch (format) {
        case VideoFormat::AVI: return ".avi";
        case VideoFormat::MP4: return ".mp4";
        case VideoFormat::WMV: return ".wmv";
        default: return ".avi";
    }
}

// ============================================================
// Helper Functions
// ============================================================

std::vector<SectionPlane> createStandardSectionPlanes(const Point3D& center) {
    std::vector<SectionPlane> planes;

    // X plane (YZ plane)
    planes.emplace_back(center, Point3D{1, 0, 0});

    // Y plane (XZ plane)
    planes.emplace_back(center, Point3D{0, 1, 0});

    // Z plane (XY plane)
    planes.emplace_back(center, Point3D{0, 0, 1});

    return planes;
}

SectionPlane createSectionPlaneFromPoints(
    const Point3D& p1,
    const Point3D& p2,
    const Point3D& p3)
{
    // Calculate normal vector from 3 points
    // v1 = p2 - p1
    Point3D v1 = {p2[0] - p1[0], p2[1] - p1[1], p2[2] - p1[2]};

    // v2 = p3 - p1
    Point3D v2 = {p3[0] - p1[0], p3[1] - p1[1], p3[2] - p1[2]};

    // normal = v1 × v2
    Point3D normal = {
        v1[1] * v2[2] - v1[2] * v2[1],
        v1[2] * v2[0] - v1[0] * v2[2],
        v1[0] * v2[1] - v1[1] * v2[0]
    };

    // Normalize
    double len = std::sqrt(normal[0]*normal[0] + normal[1]*normal[1] + normal[2]*normal[2]);
    if (len > 1e-10) {
        normal[0] /= len;
        normal[1] /= len;
        normal[2] /= len;
    }

    return SectionPlane(p1, normal);
}

} // namespace render
} // namespace kood3plot
