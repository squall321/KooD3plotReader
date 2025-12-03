/**
 * @file LSPrePostRenderer.cpp
 * @brief Implementation of LSPrePost external renderer
 * @author KooD3plot Development Team
 * @date 2025-11-24
 * @version 3.1.0
 */

#include "kood3plot/render/LSPrePostRenderer.h"
#include <fstream>
#include <sstream>
#include <cstdlib>
#include <cmath>
#include <filesystem>

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

struct LSPrePostRenderer::Impl {
    std::string lsprepost_path = "lsprepost";
    std::string last_error;
    std::string last_output;
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

    // Open d3plot file (correct command is "open d3plot" not "opend")
    script << "open d3plot \"" << d3plot_path << "\"\n";
    script << "ac\n\n";

    // Part filtering (Phase 8) - Apply BEFORE section planes
    if (options.part_id > 0) {
        script << "$# Filter to show specific part\n";
        script << "ponly " << options.part_id << "\n";
        script << "ac\n\n";
    }

    // Apply section planes BEFORE fringe/view settings
    if (!options.section_planes.empty()) {
        script << "$# Apply section planes (" << options.section_planes.size() << " planes)\n";

        // Handle multiple section planes
        for (size_t i = 0; i < options.section_planes.size(); ++i) {
            const auto& plane = options.section_planes[i];

            if (i == 0) {
                script << "splane linewidth 1\n";
            }

            script << "splane dep0 "
                   << plane.point[0] << " " << plane.point[1] << " " << plane.point[2] << " "
                   << plane.normal[0] << " " << plane.normal[1] << " " << plane.normal[2] << "\n";
            script << "splane drawcut\n";
        }
        script << "ac\n\n";
    }

    // Set fringe type (use numeric codes)
    script << "$# Fringe type mapping:\n";
    script << "$ 1: x-stress, 2: y-stress, 3: z-stress\n";
    script << "$ 4: xy-stress, 5: yz-stress, 6: zx-stress\n";
    script << "$ 7: effective plastic strain\n";
    script << "$ 8: pressure, 9: Von Mises stress\n";
    int fringe_code = fringeTypeToCode(options.fringe_type);
    script << "fringe " << fringe_code << "\n";
    script << "pfringe\n";

    // Set fringe range
    if (!options.auto_fringe_range) {
        script << "range userdef " << options.fringe_min << " " << options.fringe_max << ";\n";
    }
    script << "\n";

    // Set view orientation
    script << "$# Set view orientation\n";
    std::string view_str = viewOrientationToString(options.view);
    script << view_str << "\n";
    script << "ac\n";

    // Zoom controls (Phase 8)
    if (options.use_auto_fit) {
        script << "fit\n";
    }

    if (options.zoom_factor != 1.0) {
        script << "zoom " << options.zoom_factor << "\n";
    }

    script << "\n";

    // Generate animation (LSPrePost batch mode only supports movie output, not single images)
    script << "$# Generate movie output\n";
    script << "anim forward\n";

    // Determine output format and file extension
    std::string full_output = output_path;
    std::string movie_format = "MP4/H264";

    if (options.create_animation) {
        // Animation: use requested format
        std::string video_ext = videoFormatToExtension(options.video_format);
        if (full_output.rfind(video_ext) != full_output.length() - video_ext.length()) {
            full_output += video_ext;
        }

        if (options.video_format == VideoFormat::AVI) {
            movie_format = "AVI";
        } else if (options.video_format == VideoFormat::WMV) {
            movie_format = "WMV";
        }
    } else {
        // Single "image": generate 1-frame MP4 since batch mode doesn't support PNG/JPG export
        if (full_output.rfind(".mp4") == std::string::npos &&
            full_output.rfind(".avi") == std::string::npos) {
            full_output += ".mp4";
        }
        movie_format = "MP4/H264";
    }

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
    // Build command
    std::ostringstream cmd;
    cmd << "\"" << pImpl->lsprepost_path << "\" -nographics c=\"" << script_path << "\"";

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

        // Execute LSPrePost (Mesa wrapper handles all environment setup)
        execl("/bin/sh", "sh", "-c", cmd.str().c_str(), nullptr);
        _exit(1);  // exec failed
    }

    // Parent process - wait for child
    int status;
    waitpid(pid, &status, 0);

    return WIFEXITED(status) && WEXITSTATUS(status) == 0;
#endif
}

std::string LSPrePostRenderer::getLastError() const {
    return pImpl->last_error;
}

std::string LSPrePostRenderer::getLastOutput() const {
    return pImpl->last_output;
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
