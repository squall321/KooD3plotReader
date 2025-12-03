/**
 * @file RenderConfig.h
 * @brief JSON/YAML configuration parser for render settings
 * @author KooD3plot Development Team
 * @date 2025-11-25
 * @version 1.0.0
 *
 * Phase 10: Configuration management
 */

#pragma once

#include "LSPrePostRenderer.h"
#include <string>
#include <vector>
#include <map>
#include <memory>

namespace kood3plot {

// Forward declaration
class D3plotReader;

namespace render {

/**
 * @brief LSPrePost executable configuration
 */
struct LSPrePostConfig {
    std::string executable = "lspp412_mesa";
    std::string options = "-nographics";
    int timeout = 3600;  // seconds
};

/**
 * @brief Analysis configuration
 */
struct AnalysisConfig {
    std::vector<std::string> run_ids;
    std::string data_path;
    std::string output_path;
    std::string cache_path = "./cache";
    LSPrePostConfig lsprepost;
};

/**
 * @brief Part configuration for section rendering
 */
struct PartConfig {
    std::string name;
    int id = -1;
};

/**
 * @brief Auto-section generation mode
 */
enum class AutoSectionMode {
    MANUAL,          ///< Manual plane specification
    SINGLE,          ///< Single plane at specified position
    EVEN_SPACED,     ///< Multiple evenly-spaced sections
    UNIFORM_SPACING, ///< Sections with uniform spacing
    STANDARD_3,      ///< Standard 3-section (25%, 50%, 75%)
    OFFSET_EDGES     ///< Offset from edges
};

/**
 * @brief Auto-section parameters
 */
struct AutoSectionParams {
    std::string orientation = "Z";      ///< "X", "Y", or "Z"
    std::string position = "center";    ///< "center", "quarter_1", "quarter_3", "edge_min", "edge_max", "custom"
    double custom_ratio = 0.5;          ///< Custom ratio (0.0-1.0) for position="custom"
    int count = 1;                      ///< Number of sections for EVEN_SPACED mode
    double spacing = 0.0;               ///< Spacing for UNIFORM_SPACING mode
    double offset_percent = 10.0;       ///< Offset percentage for OFFSET_EDGES mode
};

/**
 * @brief Orientation configuration with multiple positions
 */
struct OrientationConfig {
    std::string direction;  // "X", "Y", "Z", or "custom"
    std::vector<std::string> positions;  // ["center", "quarter_1", etc.]

    // For custom orientations
    std::vector<double> base_point;  // [x, y, z]
    std::vector<double> normal_vector;  // [nx, ny, nz]
};

/**
 * @brief Per-section fringe override
 */
struct SectionFringeConfig {
    std::string type = "";  // Empty means use global fringe
    double min = 0.0;
    double max = 0.0;
    std::string colormap = "";
};

/**
 * @brief Per-section output override
 */
struct SectionOutputConfig {
    std::string prefix = "";  // Output file prefix
    std::vector<std::string> formats;  // ["movie", "images", "data"]
};

/**
 * @brief Section configuration
 */
struct SectionConfig {
    PartConfig part;

    // Manual plane specification
    std::vector<SectionPlane> planes;

    // Auto-generation mode
    AutoSectionMode auto_mode = AutoSectionMode::MANUAL;
    AutoSectionParams auto_params;

    // Comprehensive: multiple orientations with positions
    std::vector<OrientationConfig> orientations;

    // Per-section overrides
    SectionFringeConfig fringe_override;
    SectionOutputConfig output_override;
};

/**
 * @brief Fringe configuration
 */
struct FringeConfig {
    std::string type;  // "von_mises", "displacement", "effective_plastic_strain", etc.
    double min = 0.0;
    double max = 0.0;
    bool auto_range = true;
    std::string colormap = "rainbow";  // "rainbow", "jet", "grayscale"
};

/**
 * @brief Image output configuration
 */
struct ImageOutputConfig {
    bool enabled = false;
    std::string format = "png";  // "png", "jpg", "bmp"
    int width = 1920;
    int height = 1080;
    std::string timesteps = "all";  // "all" or specific list
};

/**
 * @brief Movie output configuration
 */
struct MovieOutputConfig {
    bool enabled = true;
    int width = 1920;
    int height = 1080;
    int fps = 30;
    std::string codec = "h264";  // "h264", "wmv", "avi"
};

/**
 * @brief Data extraction configuration
 */
struct DataOutputConfig {
    bool enabled = false;
    std::string format = "json";  // "json", "csv", "hdf5"
    std::vector<std::string> include;  // "stress", "strain", "displacement"
};

/**
 * @brief Comparison output configuration
 */
struct ComparisonConfig {
    bool enabled = false;
    std::string baseline = "";
    bool generate_html = true;
    bool generate_csv = true;
    bool include_plots = true;
};

/**
 * @brief Output configuration
 */
struct OutputConfig {
    bool movie = true;
    bool images = false;
    int width = 1920;
    int height = 1080;
    int fps = 30;
    std::string format = "MP4/H264";  // "MP4/H264", "WMV", "AVI"

    // Comprehensive output settings
    MovieOutputConfig movie_settings;
    ImageOutputConfig image_settings;
    DataOutputConfig data_settings;
    ComparisonConfig comparison;
};

/**
 * @brief View configuration
 */
struct ViewConfig {
    std::string orientation = "front";  // "front", "back", "left", "right", "top", "bottom", "iso"
    double zoom_factor = 1.0;
    bool auto_fit = true;
};

/**
 * @brief Parallel processing configuration
 */
struct ParallelConfig {
    bool enabled = true;
    int max_threads = 8;
};

/**
 * @brief Cache configuration
 */
struct CacheConfig {
    bool enabled = true;
    bool cache_bounding_boxes = true;
    bool cache_sections = true;
};

/**
 * @brief Memory configuration
 */
struct MemoryConfig {
    int max_memory_mb = 16384;  // 16 GB
    int chunk_size = 1000000;   // nodes per chunk
    double cleanup_threshold = 0.8;
};

/**
 * @brief Retry configuration
 */
struct RetryConfig {
    bool enabled = true;
    int max_attempts = 3;
    int delay_seconds = 5;
};

/**
 * @brief Processing configuration
 */
struct ProcessingConfig {
    ParallelConfig parallel;
    CacheConfig cache;
    MemoryConfig memory;
    RetryConfig retry;
};

/**
 * @brief Logging configuration
 */
struct LoggingConfig {
    std::string level = "INFO";  // "DEBUG", "INFO", "WARNING", "ERROR"
    std::string file = "";
    bool console = true;
};

/**
 * @brief Email notification configuration
 */
struct EmailConfig {
    bool enabled = false;
    std::vector<std::string> recipients;
    std::vector<std::string> on;  // "completion", "error"
};

/**
 * @brief Slack notification configuration
 */
struct SlackConfig {
    bool enabled = false;
    std::string webhook_url = "";
};

/**
 * @brief Notification configuration
 */
struct NotificationConfig {
    EmailConfig email;
    SlackConfig slack;
};

/**
 * @brief Complete render configuration
 */
struct RenderConfigData {
    AnalysisConfig analysis;
    std::vector<SectionConfig> sections;
    FringeConfig fringe;
    OutputConfig output;
    ViewConfig view;

    // Comprehensive configuration
    ProcessingConfig processing;
    LoggingConfig logging;
    NotificationConfig notification;
};

/**
 * @brief Configuration parser and manager
 *
 * Supports JSON and YAML configuration files for render settings
 */
class RenderConfig {
public:
    /**
     * @brief Constructor
     */
    RenderConfig();

    /**
     * @brief Destructor
     */
    ~RenderConfig();

    /**
     * @brief Move constructor
     */
    RenderConfig(RenderConfig&& other) noexcept;

    /**
     * @brief Move assignment operator
     */
    RenderConfig& operator=(RenderConfig&& other) noexcept;

    // Delete copy operations (non-copyable due to pImpl)
    RenderConfig(const RenderConfig&) = delete;
    RenderConfig& operator=(const RenderConfig&) = delete;

    // ============================================================
    // Loading
    // ============================================================

    /**
     * @brief Load configuration from JSON file
     * @param file_path Path to JSON file
     * @return true if successful
     */
    bool loadFromJSON(const std::string& file_path);

    /**
     * @brief Load configuration from JSON string
     * @param json_str JSON string
     * @return true if successful
     */
    bool loadFromJSONString(const std::string& json_str);

    /**
     * @brief Load configuration from YAML file
     * @param file_path Path to YAML file
     * @return true if successful
     */
    bool loadFromYAML(const std::string& file_path);

    // ============================================================
    // Saving
    // ============================================================

    /**
     * @brief Save configuration to JSON file
     * @param file_path Path to JSON file
     * @param pretty Pretty print (default: true)
     * @return true if successful
     */
    bool saveToJSON(const std::string& file_path, bool pretty = true) const;

    /**
     * @brief Get configuration as JSON string
     * @param pretty Pretty print (default: true)
     * @return JSON string
     */
    std::string toJSONString(bool pretty = true) const;

    /**
     * @brief Save configuration to YAML file
     * @param file_path Path to YAML file
     * @return true if successful
     */
    bool saveToYAML(const std::string& file_path) const;

    // ============================================================
    // Auto-Section Generation
    // ============================================================

    /**
     * @brief Generate auto-section planes from configuration
     * @param reader D3plot reader (needed for bounding box calculation)
     * @param state_index State/timestep index (default: 0)
     *
     * This method processes all sections with auto_mode != MANUAL and generates
     * the section planes automatically based on the configured parameters.
     * The generated planes are stored in the section.planes vector.
     */
    void generateAutoSections(D3plotReader& reader, size_t state_index = 0);

    // ============================================================
    // Conversion
    // ============================================================

    /**
     * @brief Convert to RenderOptions
     * @param section_index Section index to convert (-1 for first, or specific index)
     * @return RenderOptions structure
     */
    RenderOptions toRenderOptions(int section_index = 0) const;

    /**
     * @brief Get all RenderOptions (one per section)
     * @return Vector of RenderOptions
     */
    std::vector<RenderOptions> toAllRenderOptions() const;

    /**
     * @brief Create batch jobs from configuration
     * @return Vector of job parameters (d3plot_path, output_path, options)
     */
    std::vector<std::tuple<std::string, std::string, RenderOptions>> createBatchJobs() const;

    // ============================================================
    // Access
    // ============================================================

    /**
     * @brief Get configuration data
     * @return Configuration data
     */
    const RenderConfigData& getData() const;

    /**
     * @brief Set configuration data
     * @param data Configuration data
     */
    void setData(const RenderConfigData& data);

    /**
     * @brief Get last error message
     * @return Error message
     */
    std::string getLastError() const;

    /**
     * @brief Validate configuration
     * @return true if valid
     */
    bool validate() const;

    // ============================================================
    // String Conversion (Public for testing)
    // ============================================================

    /**
     * @brief Convert string to FringeType enum
     * @param type String representation (e.g., "von_mises", "principal_1")
     * @return FringeType enum value
     */
    FringeType stringToFringeType(const std::string& type) const;

    /**
     * @brief Convert FringeType enum to string
     * @param type FringeType enum value
     * @return String representation
     */
    std::string fringeTypeToString(FringeType type) const;

private:
    struct Impl;
    std::unique_ptr<Impl> pImpl;

    // Helper methods
    ViewOrientation stringToViewOrientation(const std::string& orientation) const;
    std::string viewOrientationToString(ViewOrientation orientation) const;
    VideoFormat stringToVideoFormat(const std::string& format) const;
    std::string videoFormatToString(VideoFormat format) const;
    AutoSectionMode stringToAutoSectionMode(const std::string& mode) const;
    std::string autoSectionModeToString(AutoSectionMode mode) const;
};

} // namespace render
} // namespace kood3plot
