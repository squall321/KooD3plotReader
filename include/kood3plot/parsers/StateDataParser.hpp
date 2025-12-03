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
     * @brief Parse all state data from file
     * @return Vector of state data for each time step
     */
    std::vector<data::StateData> parse_all();

    /**
     * @brief Parse single state at given offset
     * @param offset Word offset to state data
     * @return Parsed state data
     */
    data::StateData parse_state(size_t offset);

private:
    std::shared_ptr<core::BinaryReader> reader_;
    const data::ControlData& control_data_;
    bool is_family_file_;  ///< True if this is a family file (starts at offset 0)

    /**
     * @brief Find offset to first state data
     */
    size_t find_state_offset();

    /**
     * @brief Parse global variables for a state
     */
    void parse_global_vars(data::StateData& state, size_t& offset);

    /**
     * @brief Parse nodal data for a state
     */
    void parse_nodal_data(data::StateData& state, size_t& offset);

    /**
     * @brief Parse element data for a state
     */
    void parse_element_data(data::StateData& state, size_t& offset);

    /**
     * @brief Parse element deletion data
     */
    void parse_deletion_data(data::StateData& state, size_t& offset);
};

} // namespace parsers
} // namespace kood3plot
