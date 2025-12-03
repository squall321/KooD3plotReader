#pragma once

#include "kood3plot/Types.hpp"
#include "kood3plot/Config.hpp"
#include "kood3plot/Version.hpp"
#include "kood3plot/data/ControlData.hpp"
#include "kood3plot/data/Mesh.hpp"
#include "kood3plot/data/StateData.hpp"
#include "kood3plot/core/BinaryReader.hpp"
#include "kood3plot/core/FileFamily.hpp"

#include <string>
#include <memory>
#include <vector>

namespace kood3plot {

/**
 * @brief Main public API for reading LS-DYNA d3plot files
 *
 * Example usage:
 * @code
 * kood3plot::D3plotReader reader("path/to/d3plot");
 * auto mesh = reader.read_mesh();
 * auto states = reader.read_all_states();
 * @endcode
 */
class D3plotReader {
public:
    /**
     * @brief Constructor
     * @param filepath Path to d3plot file (base file if multi-file family)
     */
    explicit D3plotReader(const std::string& filepath);

    /**
     * @brief Destructor
     */
    ~D3plotReader();

    // Delete copy constructor and assignment
    D3plotReader(const D3plotReader&) = delete;
    D3plotReader& operator=(const D3plotReader&) = delete;

    /**
     * @brief Open and initialize the d3plot file
     * @return ErrorCode indicating success or failure
     */
    ErrorCode open();

    /**
     * @brief Close the file
     */
    void close();

    /**
     * @brief Check if file is successfully opened
     */
    bool is_open() const;

    /**
     * @brief Get file format information
     */
    FileFormat get_file_format() const;

    /**
     * @brief Get control data
     */
    const data::ControlData& get_control_data() const;

    /**
     * @brief Read mesh geometry
     * @return Mesh structure with nodes and element connectivity
     */
    data::Mesh read_mesh();

    /**
     * @brief Read all state data (sequential)
     * @return Vector of state data for each time step
     */
    std::vector<data::StateData> read_all_states();

    /**
     * @brief Read all state data in parallel
     * @param num_threads Number of threads to use (0 = auto-detect hardware concurrency)
     * @return Vector of state data for each time step
     *
     * This function reads multiple d3plot family files in parallel,
     * significantly improving performance for large datasets.
     * Recommended for datasets with many d3plot files (d3plot, d3plot01, etc.)
     */
    std::vector<data::StateData> read_all_states_parallel(size_t num_threads = 0);

    /**
     * @brief Read single state by index
     * @param state_index Index of state to read (0-based)
     * @return State data for the specified time step
     */
    data::StateData read_state(size_t state_index);

    /**
     * @brief Get number of time states available
     */
    size_t get_num_states() const;

    /**
     * @brief Get time values for all states
     */
    std::vector<double> get_time_values();

    /**
     * @brief Get the file path
     * @return Path to d3plot file
     */
    const std::string& getFilePath() const { return filepath_; }

private:
    std::string filepath_;
    std::shared_ptr<core::BinaryReader> reader_;
    std::unique_ptr<core::FileFamily> file_family_;

    data::ControlData control_data_;
    FileFormat file_format_;
    bool is_open_;

    /**
     * @brief Initialize control data
     */
    void init_control_data();
};

} // namespace kood3plot
