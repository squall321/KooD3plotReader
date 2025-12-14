#pragma once

#include <string>
#include <memory>
#include <vector>
#include <kood3plot/data/Mesh.hpp>
#include <kood3plot/data/StateData.hpp>

// Forward declaration for HDF5 types to avoid including H5Cpp.h in header
namespace H5 {
    class H5File;
    class Group;
}

namespace kood3plot {
namespace hdf5 {

/**
 * @brief Compression options for HDF5 export
 */
struct CompressionOptions {
    bool use_quantization = true;     ///< Use 16-bit quantization for floats
    bool use_delta_compression = true; ///< Use temporal delta compression
    int gzip_level = 6;               ///< gzip compression level (0-9, 0=none)
    double displacement_threshold = 0.01;  ///< Displacement precision (mm)
    double stress_threshold = 0.1;    ///< Von Mises stress threshold (MPa)
    double strain_threshold = 0.0001; ///< Strain precision (absolute)

    static CompressionOptions none() {
        CompressionOptions opt;
        opt.use_quantization = false;
        opt.use_delta_compression = false;
        opt.gzip_level = 0;
        return opt;
    }

    static CompressionOptions lossless() {
        CompressionOptions opt;
        opt.use_quantization = false;
        opt.use_delta_compression = false;
        opt.gzip_level = 6;
        return opt;
    }

    static CompressionOptions balanced() {
        return CompressionOptions();  // Default values
    }

    static CompressionOptions maximum() {
        CompressionOptions opt;
        opt.use_quantization = true;
        opt.use_delta_compression = true;
        opt.gzip_level = 9;
        return opt;
    }
};

/**
 * @brief HDF5Writer - Writes D3plot data to HDF5 format with quantization
 *
 * This class handles writing mesh and state data to HDF5 files with:
 * - Physical quantity-based quantization
 * - Temporal delta compression (t>0 as int8 deltas)
 * - Transparent metadata for automatic reconstruction
 *
 * Week 1 Goal: Basic file creation and mesh writing
 * Week 3 Goal: Temporal delta compression for timestep data
 */
class HDF5Writer {
public:
    /**
     * @brief Constructor - Creates or opens HDF5 file
     * @param filename Path to HDF5 file to create
     * @param options Compression options (default: balanced)
     * @throws std::runtime_error if file cannot be created
     */
    explicit HDF5Writer(const std::string& filename,
                        const CompressionOptions& options = CompressionOptions::balanced());

    /**
     * @brief Destructor - Ensures file is properly closed
     */
    ~HDF5Writer();

    // Delete copy/move to ensure single file ownership
    HDF5Writer(const HDF5Writer&) = delete;
    HDF5Writer& operator=(const HDF5Writer&) = delete;
    HDF5Writer(HDF5Writer&&) = delete;
    HDF5Writer& operator=(HDF5Writer&&) = delete;

    /**
     * @brief Write mesh data (nodes, elements) to HDF5
     * @param mesh Mesh data from D3plotReader
     *
     * Week 1 Milestone: Successfully write 100k node mesh
     */
    void write_mesh(const data::Mesh& mesh);

    /**
     * @brief Write state data for a timestep
     * @param timestep Timestep number (0, 1, 2, ...)
     * @param state State data (displacement, stress, etc.)
     *
     * Week 3: Implements temporal delta compression
     * - First timestep: stores full quantized data
     * - Subsequent timesteps: stores deltas from previous
     */
    void write_timestep(int timestep, const data::StateData& state);

    /**
     * @brief Close the HDF5 file
     */
    void close();

    /**
     * @brief Check if file is open
     */
    bool is_open() const { return is_open_; }

    /**
     * @brief Get current compression options
     */
    const CompressionOptions& get_options() const { return options_; }

private:
    // HDF5 file handle (using pimpl idiom to hide HDF5 types)
    std::unique_ptr<H5::H5File> file_;

    // HDF5 group handles
    std::unique_ptr<H5::Group> mesh_group_;
    std::unique_ptr<H5::Group> states_group_;

    // File state
    bool is_open_;
    std::string filename_;
    CompressionOptions options_;

    // State tracking for delta compression
    int last_timestep_ = -1;
    std::vector<uint16_t> prev_displacement_quantized_;
    std::vector<uint16_t> prev_velocity_quantized_;

    // Calibration data for quantizers (set from first timestep)
    double disp_min_[3] = {0, 0, 0};
    double disp_max_[3] = {0, 0, 0};
    double vel_min_[3] = {0, 0, 0};
    double vel_max_[3] = {0, 0, 0};
    bool calibrated_ = false;

    // Helper methods for mesh writing
    void write_nodes(const data::Mesh& mesh);
    void write_solids(const data::Mesh& mesh);
    void write_shells(const data::Mesh& mesh);
    void write_beams(const data::Mesh& mesh);

    // Helper methods for state writing
    void write_displacement_data(int timestep, const std::vector<double>& displacements);
    void write_velocity_data(int timestep, const std::vector<double>& velocities);
    void write_timestep_metadata(int timestep, double time);
    void calibrate_quantizers(const data::StateData& state);

    // Helper methods for metadata
    void write_mesh_metadata(const data::Mesh& mesh);
    void write_compression_metadata();
    void create_groups();
};

} // namespace hdf5
} // namespace kood3plot
