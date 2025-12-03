#pragma once

#include "kood3plot/core/BinaryReader.hpp"
#include "kood3plot/data/ControlData.hpp"
#include <memory>
#include <vector>
#include <unordered_map>

namespace kood3plot {
namespace parsers {

/**
 * @brief Parser for NARBS (Arbitrary Numbering) section
 *
 * This section contains the real node and element IDs used in the original
 * LS-DYNA model, as well as material type information.
 */
class NARBSParser {
public:
    /**
     * @brief Construct a new NARBS Parser
     *
     * @param reader Binary reader for the d3plot file
     * @param control_data Control data containing NARBS size and element counts
     */
    NARBSParser(std::shared_ptr<core::BinaryReader> reader,
                const data::ControlData& control_data);

    /**
     * @brief Parse the NARBS section
     *
     * Reads arbitrary node and element numbering from the geometry section.
     * This must be called after reading the geometry data.
     *
     * @param offset Current offset in the file (will be updated)
     */
    void parse(size_t& offset);

    /**
     * @brief Get real node ID from internal index
     *
     * @param internal_index Internal node index (0-based)
     * @return int32_t Real node ID from original model
     */
    int32_t get_real_node_id(size_t internal_index) const;

    /**
     * @brief Get real element ID from internal index
     *
     * @param element_type Type of element (SOLID, BEAM, SHELL, THICK_SHELL)
     * @param internal_index Internal element index (0-based)
     * @return int32_t Real element ID from original model
     */
    int32_t get_real_element_id(ElementType element_type, size_t internal_index) const;

    /**
     * @brief Get internal node index from real ID
     *
     * @param real_id Real node ID
     * @return size_t Internal index (0-based), or -1 if not found
     */
    size_t get_internal_node_index(int32_t real_id) const;

    /**
     * @brief Get internal element index from real ID
     *
     * @param element_type Type of element
     * @param real_id Real element ID
     * @return size_t Internal index (0-based), or -1 if not found
     */
    size_t get_internal_element_index(ElementType element_type, int32_t real_id) const;

    /**
     * @brief Get material type numbers
     *
     * @return const std::vector<int32_t>& Material type list
     */
    const std::vector<int32_t>& get_material_types() const { return material_types_; }

    /**
     * @brief Get real Part IDs (NORDER array)
     *
     * Maps internal material index (1-based) to real Part ID.
     * Usage: real_part_id = part_ids_[material_index - 1]
     *
     * @return const std::vector<int32_t>& Part ID array
     */
    const std::vector<int32_t>& get_part_ids() const { return part_ids_; }

    /**
     * @brief Get real Part ID from internal material index
     *
     * @param material_index Internal material index (1-based, from element data)
     * @return int32_t Real Part ID from NORDER array
     */
    int32_t get_real_part_id(int32_t material_index) const;

    /**
     * @brief Check if NARBS section exists
     *
     * @return true if NARBS > 0
     */
    bool has_narbs() const { return control_data_.NARBS > 0; }

private:
    std::shared_ptr<core::BinaryReader> reader_;
    data::ControlData control_data_;

    // Real IDs from NARBS section
    std::vector<int32_t> node_ids_;           // NSORT = NUMNP
    std::vector<int32_t> solid_ids_;          // NSORT8 = NEL8
    std::vector<int32_t> beam_ids_;           // NSORT2 = NEL2
    std::vector<int32_t> shell_ids_;          // NSORT4 = NEL4
    std::vector<int32_t> thick_shell_ids_;    // NSORTT = NELT
    std::vector<int32_t> material_types_;     // Material types from NARBS
    std::vector<int32_t> part_ids_;           // NORDER - maps material index to Part ID

    // Reverse mapping: real ID -> internal index (for fast lookup)
    std::unordered_map<int32_t, size_t> node_id_to_index_;
    std::unordered_map<int32_t, size_t> solid_id_to_index_;
    std::unordered_map<int32_t, size_t> beam_id_to_index_;
    std::unordered_map<int32_t, size_t> shell_id_to_index_;
    std::unordered_map<int32_t, size_t> thick_shell_id_to_index_;
};

} // namespace parsers
} // namespace kood3plot
