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

    // Iso clip view: rotation per axis
    // X-section: front → ry+45 → rx+35, clipplane +
    // Y-section: front → ry-45 → rx+35, clipplane -
    // Z-section: top  → ry+45 → rx-35, clipplane -
    struct IsoViewDef {
        const char* base_view;
        int ry_angle, rx_angle;
        const char* clip_sign;
    };
    const IsoViewDef iso_views[3] = {
        {"front",  45,  35, "+"},  // X
        {"front", -45,  35, "-"},  // Y
        {"top",    45, -35, "-"},  // Z
    };

    int views_per_axis = (section_opts.section_view ? 1 : 0) + (section_opts.iso_clip_view ? 1 : 0);
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

        for (char axis_char : section_opts.axes) {
            int ai = axisIndex(axis_char);
            std::string axis_name(1, axis_char);

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
                       << normals[ai][0] << " " << normals[ai][1] << " " << normals[ai][2] << "\n"
                       << "splane projectview\nsplane drawcut\nac\n"
                       << "zin " << sm << " " << sm << " " << (1.0-sm) << " " << (1.0-sm) << "\n\n";

                writeRestoreAll(script);

                script << "anim forward\nmovie mt 0\n"
                       << "movie MP4/H264 " << options.image_width << "x" << options.image_height
                       << " \"" << out_path.string() << "\" " << options.fps << "\n\n"
                       << "splane done\nexit\n";

                fs::path cfile = part_dir / ("section_" + axis_name + ".cfile");
                if (saveScript(script.str(), cfile.string())) {
                    if (executeLSPrePost(cfile.string(), abs_d3plot.parent_path().string()))
                        success++;
                    else
                        std::cerr << "[SectionView] FAILED: Part " << pid << " section-" << axis_name << "\n";
                    fs::remove(cfile);
                }
            }

            // ── (B) Iso clip view: isometric + clipplane ──
            if (section_opts.iso_clip_view) {
                current++;
                fs::path out_path = part_dir / ("iso_clip_" + axis_name);
                const auto& iv = iso_views[ai];
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

                script << iv.base_view << "\n"
                       << "rotang " << iv.ry_angle << "\nry\n"
                       << "rotang " << iv.rx_angle << "\nrx\n";

                writeTargetOnly(script);
                script << "ac\n";
                writeRestoreAll(script);

                script << "splane dep0 " << sp[0] << " " << sp[1] << " " << sp[2] << " "
                       << normals[ai][0] << " " << normals[ai][1] << " " << normals[ai][2] << "\n"
                       << "splane clipplane " << iv.clip_sign << "\n"
                       << "zin " << im << " " << im << " " << (1.0-im) << " " << (1.0-im) << "\n\n";

                script << "anim forward\nmovie mt 0\n"
                       << "movie MP4/H264 " << options.image_width << "x" << options.image_height
                       << " \"" << out_path.string() << "\" " << options.fps << "\n\n"
                       << "splane done\nexit\n";

                fs::path cfile = part_dir / ("iso_clip_" + axis_name + ".cfile");
                if (saveScript(script.str(), cfile.string())) {
                    if (executeLSPrePost(cfile.string(), abs_d3plot.parent_path().string()))
                        success++;
                    else
                        std::cerr << "[SectionView] FAILED: Part " << pid << " iso_clip-" << axis_name << "\n";
                    fs::remove(cfile);
                }
            }
        }
    }

    std::cout << "[SectionView] Completed: " << success << "/" << total << " renders\n";
    return success;
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
