#pragma once

#include "kood3plot/Types.hpp"
#include <vector>
#include <string>

namespace kood3plot {
namespace data {

/**
 * @brief Mesh geometry data structure
 */
struct Mesh {
    // Nodes
    std::vector<Node> nodes;

    // Elements by type
    std::vector<Element> solids;
    std::vector<Element> thick_shells;
    std::vector<Element> beams;
    std::vector<Element> shells;

    // Element counts
    size_t num_solids;
    size_t num_thick_shells;
    size_t num_beams;
    size_t num_shells;

    // Material info
    std::vector<int32_t> solid_materials;
    std::vector<int32_t> thick_shell_materials;
    std::vector<int32_t> beam_materials;
    std::vector<int32_t> shell_materials;

    // Part IDs
    std::vector<int32_t> solid_parts;
    std::vector<int32_t> thick_shell_parts;
    std::vector<int32_t> beam_parts;
    std::vector<int32_t> shell_parts;

    // Real IDs from NARBS (arbitrary numbering)
    std::vector<int32_t> real_node_ids;      // Real node IDs from NARBS
    std::vector<int32_t> real_solid_ids;     // Real solid element IDs
    std::vector<int32_t> real_beam_ids;      // Real beam element IDs
    std::vector<int32_t> real_shell_ids;     // Real shell element IDs
    std::vector<int32_t> real_thick_shell_ids; // Real thick shell element IDs
    std::vector<int32_t> material_types;     // Material type list from NARBS

    /**
     * @brief Constructor with default initialization
     */
    Mesh();

    /**
     * @brief Get total number of nodes
     */
    size_t get_num_nodes() const { return nodes.size(); }

    /**
     * @brief Get total number of elements
     */
    size_t get_num_elements() const {
        return num_solids + num_thick_shells + num_beams + num_shells;
    }
};

} // namespace data
} // namespace kood3plot
