#pragma once

#include "kood3plot/Types.hpp"
#include "kood3plot/data/ControlData.hpp"
#include "kood3plot/data/StateData.hpp"
#include "kood3plot/core/BinaryReader.hpp"
#include <memory>
#include <vector>

namespace kood3plot {
namespace parsers {

/**
 * @brief Parser for state data section
 *
 * Supports two parsing modes:
 * - Fast mode (default): Uses bulk array reads for performance
 * - Legacy mode: Uses individual word reads (slower but more debuggable)
 */
class StateDataParser {
public:
    /**
     * @brief Constructor
     * @param reader Binary file reader
     * @param control_data Control data structure
     * @param is_family_file If true, this is a family file (d3plot01, etc.)
     *                       which contains only state data starting at offset 0
     */
    StateDataParser(std::shared_ptr<core::BinaryReader> reader,
                    const data::ControlData& control_data,
                    bool is_family_file = false);

    /**
     * @brief Parse all state data from file (uses fast mode by default)
     * @return Vector of state data for each time step
     */
    std::vector<data::StateData> parse_all();

    /**
     * @brief Parse single state at given offset (uses fast mode by default)
     * @param offset Word offset to state data
     * @return Parsed state data
     */
    data::StateData parse_state(size_t offset);

    /**
     * @brief Enable or disable fast bulk read mode
     * @param enable true for fast mode (default), false for legacy mode
     */
    void set_fast_mode(bool enable) { use_fast_mode_ = enable; }

    /**
     * @brief Check if fast mode is enabled
     */
    bool is_fast_mode() const { return use_fast_mode_; }

    // ============ Legacy API (individual word reads) ============

    /**
     * @brief Parse all states using legacy individual word reads
     * @return Vector of state data
     * @note Slower than parse_all() but useful for debugging
     */
    std::vector<data::StateData> parse_all_legacy();

    /**
     * @brief Parse single state using legacy individual word reads
     * @param offset Word offset to state data
     * @return Parsed state data
     */
    data::StateData parse_state_legacy(size_t offset);

private:
    std::shared_ptr<core::BinaryReader> reader_;
    const data::ControlData& control_data_;
    bool is_family_file_;  ///< True if this is a family file (starts at offset 0)
    bool use_fast_mode_ = true;  ///< Use bulk read mode by default

    /**
     * @brief Find offset to first state data
     */
    size_t find_state_offset();

    // ============ Fast mode parsing (bulk reads) ============

    /**
     * @brief Parse state using bulk array reads (fast)
     */
    data::StateData parse_state_fast(size_t offset);

    /**
     * @brief Parse global variables using bulk read
     */
    void parse_global_vars_fast(data::StateData& state, size_t& offset);

    /**
     * @brief Parse nodal data using bulk read
     */
    void parse_nodal_data_fast(data::StateData& state, size_t& offset);

    /**
     * @brief Parse element data using bulk read
     */
    void parse_element_data_fast(data::StateData& state, size_t& offset);

    // ============ Legacy mode parsing (individual reads) ============

    /**
     * @brief Parse global variables (legacy individual reads)
     */
    void parse_global_vars_legacy(data::StateData& state, size_t& offset);

    /**
     * @brief Parse nodal data (legacy individual reads)
     */
    void parse_nodal_data_legacy(data::StateData& state, size_t& offset);

    /**
     * @brief Parse element data (legacy individual reads)
     */
    void parse_element_data_legacy(data::StateData& state, size_t& offset);

    /**
     * @brief Parse element deletion data
     */
    void parse_deletion_data(data::StateData& state, size_t& offset);
};

} // namespace parsers
} // namespace kood3plot
