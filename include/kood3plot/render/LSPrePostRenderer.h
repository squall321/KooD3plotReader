/**
 * @file LSPrePostRenderer.h
 * @brief LSPrePost external renderer for section views and animations
 * @author KooD3plot Development Team
 * @date 2025-11-24
 * @version 3.1.0
 *
 * Provides automated LSPrePost rendering capabilities for:
 * - Section views (cutting planes)
 * - Stress/displacement visualization
 * - Image and video export
 * - Animation generation
 */

#pragma once

#include <string>
#include <vector>
#include <memory>
#include <array>

namespace kood3plot {
namespace render {

/**
 * @brief 3D point type
 */
using Point3D = std::array<double, 3>;

/**
 * @brief View orientation for rendering
 */
enum class ViewOrientation {
    TOP,           ///< Top view (Z+)
    BOTTOM,        ///< Bottom view (Z-)
    LEFT,          ///< Left view (X+)
    RIGHT,         ///< Right view (X-)
    FRONT,         ///< Front view (Y+)
    BACK,          ///< Back view (Y-)
    ISOMETRIC,     ///< Isometric view
    CUSTOM         ///< Custom view direction
};

/**
 * @brief Fringe (colormap) quantity type
 */
enum class FringeType {
    // Stress components (LSPrePost IDs: 1-6)
    STRESS_XX,              ///< X stress (LSPrePost ID: 1)
    STRESS_YY,              ///< Y stress (LSPrePost ID: 2)
    STRESS_ZZ,              ///< Z stress (LSPrePost ID: 3)
    STRESS_XY,              ///< XY stress (LSPrePost ID: 4)
    STRESS_YZ,              ///< YZ stress (LSPrePost ID: 5)
    STRESS_XZ,              ///< XZ/ZX stress (LSPrePost ID: 6)

    // Plastic strain (LSPrePost ID: 7)
    EFFECTIVE_PLASTIC_STRAIN,  ///< Effective plastic strain (LSPrePost ID: 7)

    // Pressure (LSPrePost ID: 8)
    PRESSURE,               ///< Pressure (LSPrePost ID: 8)

    // Von Mises stress (LSPrePost ID: 9)
    VON_MISES,              ///< Von Mises stress (LSPrePost ID: 9)

    // Shear stress (LSPrePost ID: 13)
    MAX_SHEAR_STRESS,       ///< Max shear stress (LSPrePost ID: 13)

    // Principal stresses (LSPrePost IDs: 14-16)
    PRINCIPAL_STRESS_1,     ///< Principal stress 1 (LSPrePost ID: 14)
    PRINCIPAL_STRESS_2,     ///< Principal stress 2 (LSPrePost ID: 15)
    PRINCIPAL_STRESS_3,     ///< Principal stress 3 (LSPrePost ID: 16)

    // Displacement components (LSPrePost IDs: 17-20)
    DISPLACEMENT_X,         ///< X displacement (LSPrePost ID: 17)
    DISPLACEMENT_Y,         ///< Y displacement (LSPrePost ID: 18)
    DISPLACEMENT_Z,         ///< Z displacement (LSPrePost ID: 19)
    DISPLACEMENT,           ///< Resultant displacement (LSPrePost ID: 20)

    // Velocity and Acceleration (LSPrePost IDs: 23-24)
    ACCELERATION,           ///< Resultant acceleration (LSPrePost ID: 23)
    VELOCITY,               ///< Resultant velocity (LSPrePost ID: 24)

    // Energy (LSPrePost ID: 43)
    HOURGLASS_ENERGY_DENSITY,  ///< Hourglass energy density (LSPrePost ID: 43)

    // Strain components (LSPrePost IDs: 57-62)
    STRAIN_XX,              ///< X strain (LSPrePost ID: 57)
    STRAIN_YY,              ///< Y strain (LSPrePost ID: 58)
    STRAIN_ZZ,              ///< Z strain (LSPrePost ID: 59)
    STRAIN_XY,              ///< XY strain (LSPrePost ID: 60)
    STRAIN_YZ,              ///< YZ strain (LSPrePost ID: 61)
    STRAIN_XZ,              ///< XZ/ZX strain (LSPrePost ID: 62)

    // Shell properties (LSPrePost ID: 67)
    SHELL_THICKNESS,        ///< Shell thickness (LSPrePost ID: 67)

    // Principal strains (LSPrePost IDs: 77-79)
    PRINCIPAL_STRAIN_1,     ///< Principal strain 1 (LSPrePost ID: 77)
    PRINCIPAL_STRAIN_2,     ///< Principal strain 2 (LSPrePost ID: 78)
    PRINCIPAL_STRAIN_3,     ///< Principal strain 3 (LSPrePost ID: 79)

    // Effective strain (LSPrePost ID: 80)
    EFFECTIVE_STRAIN,       ///< Effective strain (LSPrePost ID: 80)

    // Advanced properties (LSPrePost IDs: 520-530)
    TRIAXIALITY,            ///< Triaxiality (LSPrePost ID: 520)
    NORMALIZED_MEAN_STRESS, ///< Normalized mean stress (LSPrePost ID: 521)
    STRAIN_ENERGY_DENSITY,  ///< Strain energy density (LSPrePost ID: 524)
    VOLUMETRIC_STRAIN,      ///< Volumetric strain (LSPrePost ID: 529)
    SIGNED_VON_MISES        ///< Signed von Mises (LSPrePost ID: 530)
};

/**
 * @brief Output image format
 */
enum class ImageFormat {
    PNG,
    JPG,
    BMP,
    TIFF
};

/**
 * @brief Output video format
 */
enum class VideoFormat {
    AVI,
    MP4,
    WMV
};

/**
 * @brief Section plane definition
 */
struct SectionPlane {
    Point3D point;      ///< Point on plane
    Point3D normal;     ///< Normal vector
    bool visible;       ///< Show section plane

    // Default constructor
    SectionPlane() : point{0, 0, 0}, normal{0, 0, 1}, visible(true) {}

    // Parameterized constructor
    SectionPlane(const Point3D& pt, const Point3D& n, bool vis = true)
        : point(pt), normal(n), visible(vis) {}
};

/**
 * @brief Rendering options for LSPrePost
 */
struct RenderOptions {
    // View settings
    ViewOrientation view = ViewOrientation::ISOMETRIC;
    Point3D custom_view_direction = {1, 1, 1};

    // Zoom/View controls (Phase 8)
    double zoom_factor = 1.0;           ///< Zoom factor (>1.0 = zoom out, <1.0 = zoom in)
    bool use_auto_fit = true;           ///< Use automatic fit before applying zoom
    std::array<double, 4> zoom_coords = {-4.0, -4.0, 5.0, 5.0};  ///< Custom zoom coordinates

    // Fringe settings
    FringeType fringe_type = FringeType::VON_MISES;
    double fringe_min = 0.0;
    double fringe_max = 0.0;
    bool auto_fringe_range = true;

    // Part filtering (Phase 8)
    int part_id = -1;                   ///< Part ID to show (-1 = all parts)
    std::string part_name = "";         ///< Part name to show (empty = all parts)

    // Section settings
    std::vector<SectionPlane> section_planes;

    // Output settings
    std::string output_prefix = "output";
    ImageFormat image_format = ImageFormat::PNG;
    int image_width = 1920;
    int image_height = 1080;

    // Output mode (Phase 8)
    bool generate_images = false;       ///< Generate individual images
    bool generate_movie = true;         ///< Generate movie/animation

    // Animation settings
    bool create_animation = false;
    VideoFormat video_format = VideoFormat::MP4;
    int fps = 30;
    int start_state = 0;
    int end_state = -1;  // -1 = last state
    int state_step = 1;

    // Display settings
    bool show_mesh = true;
    bool show_undeformed = false;
    double deformation_scale = 1.0;
};

/**
 * @brief LSPrePost external renderer
 *
 * Automates LSPrePost for section view rendering and animation export.
 * Uses batch mode (lsprepost -nographics c=script.cfile) to generate
 * images and videos from d3plot files.
 */
class LSPrePostRenderer {
public:
    /**
     * @brief Constructor
     * @param lsprepost_path Path to lsprepost executable
     */
    explicit LSPrePostRenderer(const std::string& lsprepost_path = "lsprepost");

    /**
     * @brief Destructor
     */
    ~LSPrePostRenderer();

    // ============================================================
    // Configuration
    // ============================================================

    /**
     * @brief Set LSPrePost executable path
     * @param path Path to lsprepost executable
     */
    void setLSPrePostPath(const std::string& path);

    /**
     * @brief Get LSPrePost executable path
     * @return Path to lsprepost executable
     */
    std::string getLSPrePostPath() const;

    /**
     * @brief Check if LSPrePost is available
     * @return true if lsprepost executable exists and is accessible
     */
    bool isAvailable() const;

    // ============================================================
    // Rendering
    // ============================================================

    /**
     * @brief Render single image from d3plot
     * @param d3plot_path Path to d3plot file
     * @param output_path Output image path (without extension)
     * @param options Rendering options
     * @return true on success
     */
    bool renderImage(
        const std::string& d3plot_path,
        const std::string& output_path,
        const RenderOptions& options = RenderOptions()
    );

    /**
     * @brief Render animation from d3plot
     * @param d3plot_path Path to d3plot file
     * @param output_path Output video path (without extension)
     * @param options Rendering options (create_animation must be true)
     * @return true on success
     */
    bool renderAnimation(
        const std::string& d3plot_path,
        const std::string& output_path,
        const RenderOptions& options
    );

    /**
     * @brief Render section view with cutting plane
     * @param d3plot_path Path to d3plot file
     * @param output_path Output image/video path
     * @param plane Section plane definition
     * @param options Rendering options
     * @return true on success
     */
    bool renderSectionView(
        const std::string& d3plot_path,
        const std::string& output_path,
        const SectionPlane& plane,
        const RenderOptions& options = RenderOptions()
    );

    /**
     * @brief Render multiple section views
     * @param d3plot_path Path to d3plot file
     * @param output_prefix Output file prefix
     * @param planes Section plane definitions
     * @param options Rendering options
     * @return Number of successful renders
     */
    int renderMultipleSections(
        const std::string& d3plot_path,
        const std::string& output_prefix,
        const std::vector<SectionPlane>& planes,
        const RenderOptions& options = RenderOptions()
    );

    // ============================================================
    // Script Generation
    // ============================================================

    /**
     * @brief Generate LSPrePost command file (.cfile)
     * @param d3plot_path Path to d3plot file
     * @param output_path Output image/video path
     * @param options Rendering options
     * @return Generated script content
     */
    std::string generateScript(
        const std::string& d3plot_path,
        const std::string& output_path,
        const RenderOptions& options
    ) const;

    /**
     * @brief Save script to file
     * @param script Script content
     * @param script_path Output .cfile path
     * @return true on success
     */
    bool saveScript(const std::string& script, const std::string& script_path) const;

    // ============================================================
    // Execution
    // ============================================================

    /**
     * @brief Execute LSPrePost with script file
     * @param script_path Path to .cfile script
     * @param working_dir Working directory (empty = current)
     * @return true on success
     */
    bool executeLSPrePost(
        const std::string& script_path,
        const std::string& working_dir = ""
    );

    /**
     * @brief Get last error message
     * @return Error message
     */
    std::string getLastError() const;

    /**
     * @brief Get last execution output
     * @return Execution output
     */
    std::string getLastOutput() const;

private:
    struct Impl;
    std::unique_ptr<Impl> pImpl;

    // Helper methods
    int fringeTypeToCode(FringeType type) const;
    std::string fringeTypeToString(FringeType type) const;
    std::string viewOrientationToString(ViewOrientation view) const;
    std::string imageFormatToExtension(ImageFormat format) const;
    std::string videoFormatToExtension(VideoFormat format) const;
};

// ============================================================
// Helper Functions
// ============================================================

/**
 * @brief Create standard section planes (X, Y, Z)
 * @param center Center point for planes
 * @return Vector of 3 section planes (X=0, Y=0, Z=0 through center)
 */
std::vector<SectionPlane> createStandardSectionPlanes(const Point3D& center);

/**
 * @brief Create section plane from 3 points
 * @param p1 First point on plane
 * @param p2 Second point on plane
 * @param p3 Third point on plane
 * @return Section plane
 */
SectionPlane createSectionPlaneFromPoints(
    const Point3D& p1,
    const Point3D& p2,
    const Point3D& p3
);

} // namespace render
} // namespace kood3plot
