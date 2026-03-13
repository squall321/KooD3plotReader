#pragma once
/**
 * @file SectionClipper.hpp
 * @brief Clips mesh elements against a section plane to produce ClipPolygons
 *
 * For each element intersected by the plane, produces a ClipPolygon:
 *   size()==0  — no intersection (element on one side or deleted)
 *   size()==2  — shell element cross-section (line segment): use drawEdge()
 *   size()>=3  — solid/thick-shell cross-section polygon:   use drawPolygonContour()
 *
 * Hex8 (solid/thick-shell) intersection:
 *   Iterate all 12 edges, collect edge-plane crossing points, radial-sort by atan2
 *   on the plane's 2D basis to form a convex polygon.
 *
 * Shell quad/tri intersection:
 *   Two crossing edges → exactly one line segment (size==2).
 *
 * Nodal values at intersection points are linearly interpolated from the
 * NodalAverager output at the two endpoint nodes of each crossed edge.
 *
 * Deleted elements (from StateData) are skipped.
 */

#include "kood3plot/section_render/SectionTypes.hpp"
#include "kood3plot/section_render/SectionPlane.hpp"
#include "kood3plot/section_render/NodalAverager.hpp"
#include "kood3plot/section_render/PartMatcher.hpp"
#include "kood3plot/data/Mesh.hpp"
#include "kood3plot/data/StateData.hpp"
#include "kood3plot/data/ControlData.hpp"
#include <unordered_map>
#include <vector>

namespace kood3plot {
namespace section_render {

class SectionClipper {
public:
    SectionClipper(const data::Mesh& mesh,
                   const data::ControlData& control,
                   const SectionPlane& plane,
                   double slab_thickness = 0.0);

    /**
     * @brief Clip all elements and produce ClipPolygons for one time step
     *
     * @param state          State data (node positions after displacement)
     * @param averager       Pre-computed nodal scalar values
     * @param target         Target parts (contour rendering)
     * @param background     Background parts (flat color rendering)
     * @param target_result  Output polygons for target parts
     * @param bg_result      Output polygons for background parts
     */
    void clip(const data::StateData& state,
              const NodalAverager& averager,
              const PartMatcher& target,
              const PartMatcher& background,
              std::vector<ClipPolygon>& target_result,
              std::vector<ClipPolygon>& bg_result,
              std::vector<float>& bg_alphas,
              double fade_distance = 0.0);

private:
    const data::Mesh&        mesh_;
    const data::ControlData& control_;
    const SectionPlane&      plane_;

    // Clip helpers
    ClipPolygon clipSolid     (const data::StateData& state,
                                const NodalAverager& averager,
                                int32_t elem_index, int32_t part_id) const;
    ClipPolygon clipShell     (const data::StateData& state,
                                const NodalAverager& averager,
                                int32_t elem_index, int32_t part_id) const;
    ClipPolygon clipThickShell(const data::StateData& state,
                                const NodalAverager& averager,
                                int32_t elem_index, int32_t part_id) const;

    /** Radial sort of intersection points on the plane (for hex8 convex polygon) */
    void radialSort(std::vector<ClipVertex>& verts) const;

    /** Get deformed node position using 0-based node array index */
    Vec3 nodePos(const data::StateData& state, int32_t node_index) const;

    /** Convert element node_id (1-based external) to 0-based node array index */
    int32_t nodeIndex(int32_t node_id) const;

    double slab_half_ = 0.0;  ///< half of slab_thickness; nodes within [-slab_half_, +slab_half_] treated as on-plane

    /// O(1) lookup built in constructor (only when real_node_ids non-empty)
    std::unordered_map<int32_t, int32_t> node_id_to_index_;

    /** Clip a hex8 element (shared by solid and thick-shell) */
    ClipPolygon clipHex8(const std::vector<int32_t>& node_ids,
                          const data::StateData& state,
                          const NodalAverager& averager,
                          int32_t part_id) const;

    /** Project hex8 nodes onto the plane (for fade-mode near-plane elements) */
    ClipPolygon projectHex8(const Vec3 pos[8], const double dist[8],
                             const double val[8], int32_t part_id) const;

    /** Project shell nodes onto the plane (for fade-mode near-plane elements) */
    ClipPolygon projectShell(const Vec3* pos, const double* dist,
                              const double* val, int nc, int32_t part_id) const;
};

} // namespace section_render
} // namespace kood3plot
