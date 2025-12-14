#pragma once

#include <string>
#include <vector>
#include <memory>
#include <optional>
#include <kood3plot/data/Mesh.hpp>
#include <kood3plot/data/StateData.hpp>

// Forward declaration for HDF5 types
namespace H5 {
    class H5File;
    class Group;
}

namespace kood3plot {
namespace hdf5 {

/**
 * @brief HDF5 file metadata
 */
struct HDF5FileInfo {
    std::string format_version;
    int num_nodes = 0;
    int num_solids = 0;
    int num_shells = 0;
    int num_beams = 0;
    int num_timesteps = 0;
    size_t file_size_bytes = 0;
    size_t uncompressed_estimate = 0;
    double compression_ratio = 0.0;
};

/**
 * @brief Validation result
 */
struct ValidationResult {
    bool passed = true;
    std::string message;
    double max_error = 0.0;
    double mean_error = 0.0;
    double rms_error = 0.0;
    double max_relative_error = 0.0;
    int min_significant_digits = 0;
    double significant_digit_ratio = 0.0;
};

/**
 * @brief HDF5Reader - Read D3plot data from HDF5 files
 */
class HDF5Reader {
public:
    explicit HDF5Reader(const std::string& filename);
    ~HDF5Reader();

    HDF5Reader(const HDF5Reader&) = delete;
    HDF5Reader& operator=(const HDF5Reader&) = delete;
    HDF5Reader(HDF5Reader&&) = delete;
    HDF5Reader& operator=(HDF5Reader&&) = delete;

    HDF5FileInfo get_file_info() const;
    data::Mesh read_mesh();
    std::vector<data::Node> read_nodes();
    std::optional<data::StateData> read_state(int timestep);

    /**
     * @brief Get list of available timesteps
     */
    std::vector<int> get_timestep_list() const;

    /**
     * @brief Get time value for a specific timestep
     */
    double get_timestep_time(int timestep) const;

    void close();
    bool is_open() const { return is_open_; }

    // Validation functions
    ValidationResult validate_nodes(const std::vector<data::Node>& original, double tolerance = 1e-10);
    ValidationResult validate_solids(const std::vector<data::Element>& original);
    ValidationResult validate_shells(const std::vector<data::Element>& original);
    static ValidationResult analyze_significant_digits(
        const std::vector<double>& original,
        const std::vector<double>& loaded,
        int required_digits = 6
    );

private:
    std::unique_ptr<H5::H5File> file_;
    std::unique_ptr<H5::Group> mesh_group_;
    std::unique_ptr<H5::Group> states_group_;
    bool is_open_;
    std::string filename_;
    HDF5FileInfo file_info_;

    // Compression metadata (loaded from file)
    bool use_quantization_ = false;
    bool use_delta_compression_ = false;
    double disp_min_[3] = {0, 0, 0};
    double disp_max_[3] = {0, 0, 0};
    double vel_min_[3] = {0, 0, 0};
    double vel_max_[3] = {0, 0, 0};

    // State cache for delta decompression
    mutable int last_read_timestep_ = -1;
    mutable std::vector<uint16_t> cached_displacement_quantized_;
    mutable std::vector<uint16_t> cached_velocity_quantized_;

    void read_file_info();
    void open_groups();
    void load_compression_metadata();

    // Helper functions for state reading
    std::vector<double> read_displacement_data(int timestep) const;
    std::vector<double> read_velocity_data(int timestep) const;
};

} // namespace hdf5
} // namespace kood3plot
