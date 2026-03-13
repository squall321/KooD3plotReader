#pragma once
/**
 * @file NodalAverager.hpp
 * @brief Averages element-centroid stress/strain values onto nodes
 *
 * LS-DYNA d3plot stores scalar field data per element (e.g. von Mises stress).
 * For smooth contour rendering (Gouraud shading), we need values at nodes.
 *
 * Algorithm:
 *   For each element, distribute its scalar value to connected nodes (accumulate).
 *   After all elements, divide each node's accumulated value by its element count.
 *
 * Deleted elements (from StateData::deleted_solids/shells/thick_shells) are skipped.
 *
 * Usage:
 *   NodalAverager averager(mesh, control);
 *   averager.compute(state, field_selector, target_parts);
 *   double val = averager.nodeValue(node_index);
 */

#include "kood3plot/section_render/SectionTypes.hpp"
#include "kood3plot/data/Mesh.hpp"
#include "kood3plot/data/StateData.hpp"
#include "kood3plot/data/ControlData.hpp"
#include "kood3plot/section_render/PartMatcher.hpp"
#include <vector>
#include <unordered_map>
#include <unordered_set>

namespace kood3plot {
namespace section_render {

/**
 * @brief Selects which scalar field to extract from element data
 */
enum class FieldSelector {
    VonMises,           ///< Effective (von Mises) stress
    EffectivePlasticStrain,  ///< EPS (effective plastic strain)
    DisplacementMagnitude,   ///< |u| from node_displacements
    PressureStress,          ///< Hydrostatic pressure
    MaxShearStress,          ///< Maximum shear stress
};

class NodalAverager {
public:
    NodalAverager(const data::Mesh& mesh, const data::ControlData& control);

    /**
     * @brief Compute nodal-averaged scalar values for a single state
     *
     * @param state     Time-step data (element + nodal arrays)
     * @param field     Which scalar field to extract
     * @param target    Parts to include (empty PartMatcher = include all)
     */
    void compute(const data::StateData& state,
                 FieldSelector field,
                 const PartMatcher& target);

    /**
     * @brief Get averaged scalar value at a node (by node array index)
     *
     * Returns 0.0 if the node has no contributing elements.
     */
    double nodeValue(int32_t node_index) const;

    /**
     * @brief Global min/max of all averaged values (after compute())
     */
    double globalMin() const { return global_min_; }
    double globalMax() const { return global_max_; }

private:
    const data::Mesh&        mesh_;
    const data::ControlData& control_;

    std::vector<double>  node_sum_;    ///< Averaged scalar values per node (after compute)
    std::vector<int32_t> node_count_;  ///< Number of contributing elements per node

    double global_min_ = 0.0;
    double global_max_ = 1.0;

    /// O(1) node-ID → 0-based node array index (only built when real_node_ids non-empty)
    std::unordered_map<int32_t, int32_t> node_id_to_index_;

    /// Convert a node ID (1-based external) to 0-based node array index
    int32_t nodeIndex(int32_t node_id) const;

    // Extraction helpers
    double extractSolidValue(const data::StateData& state,
                              int32_t elem_index,
                              FieldSelector field) const;
    double extractShellValue(const data::StateData& state,
                              int32_t elem_index,
                              FieldSelector field) const;
    double extractThickShellValue(const data::StateData& state,
                                   int32_t elem_index,
                                   FieldSelector field) const;
};

} // namespace section_render
} // namespace kood3plot
