#include "kood3plot/analysis/BoundingBox.hpp"
#include <algorithm>
#include <unordered_set>

namespace kood3plot {
namespace analysis {

BoundingBox::BoundingBox() {
    reset();
}

BoundingBox::BoundingBox(const data::Mesh& mesh) {
    reset();
    compute_from_mesh(mesh, nullptr);
}

BoundingBox::BoundingBox(const data::Mesh& mesh, const data::StateData& state) {
    reset();
    compute_from_mesh(mesh, &state);
}

BoundingBox::BoundingBox(const Point3D& min_pt, const Point3D& max_pt)
    : min_(min_pt), max_(max_pt) {
}

Point3D BoundingBox::center() const {
    return Point3D(
        (min_.x + max_.x) * 0.5,
        (min_.y + max_.y) * 0.5,
        (min_.z + max_.z) * 0.5
    );
}

Point3D BoundingBox::size() const {
    return Point3D(
        max_.x - min_.x,
        max_.y - min_.y,
        max_.z - min_.z
    );
}

double BoundingBox::diagonal() const {
    Point3D s = size();
    return std::sqrt(s.x * s.x + s.y * s.y + s.z * s.z);
}

double BoundingBox::extent() const {
    Point3D s = size();
    return std::max({s.x, s.y, s.z});
}

bool BoundingBox::is_valid() const {
    return min_.x <= max_.x && min_.y <= max_.y && min_.z <= max_.z;
}

void BoundingBox::expand(const Point3D& point) {
    min_.x = std::min(min_.x, point.x);
    min_.y = std::min(min_.y, point.y);
    min_.z = std::min(min_.z, point.z);
    max_.x = std::max(max_.x, point.x);
    max_.y = std::max(max_.y, point.y);
    max_.z = std::max(max_.z, point.z);
}

void BoundingBox::expand(const BoundingBox& other) {
    if (!other.is_valid()) return;
    expand(other.min_);
    expand(other.max_);
}

void BoundingBox::reset() {
    constexpr double inf = std::numeric_limits<double>::infinity();
    min_ = Point3D(inf, inf, inf);
    max_ = Point3D(-inf, -inf, -inf);
}

std::array<Point3D, 8> BoundingBox::corners() const {
    return {{
        Point3D(min_.x, min_.y, min_.z),
        Point3D(max_.x, min_.y, min_.z),
        Point3D(min_.x, max_.y, min_.z),
        Point3D(max_.x, max_.y, min_.z),
        Point3D(min_.x, min_.y, max_.z),
        Point3D(max_.x, min_.y, max_.z),
        Point3D(min_.x, max_.y, max_.z),
        Point3D(max_.x, max_.y, max_.z)
    }};
}

void BoundingBox::compute_from_mesh(const data::Mesh& mesh, const data::StateData* state) {
    size_t num_nodes = mesh.nodes.size();
    if (num_nodes == 0) return;

    bool has_disp = state && !state->node_displacements.empty();

    for (size_t i = 0; i < num_nodes; ++i) {
        double x = mesh.nodes[i].x;
        double y = mesh.nodes[i].y;
        double z = mesh.nodes[i].z;

        // Add displacement if available
        if (has_disp && i * 3 + 2 < state->node_displacements.size()) {
            x += state->node_displacements[i * 3 + 0];
            y += state->node_displacements[i * 3 + 1];
            z += state->node_displacements[i * 3 + 2];
        }

        expand(Point3D(x, y, z));
    }
}

BoundingBox BoundingBox::from_parts(
    const data::Mesh& mesh,
    const std::vector<int32_t>& part_ids,
    const data::StateData* state)
{
    BoundingBox bbox;

    if (part_ids.empty()) {
        // All parts - use full mesh
        bbox.compute_from_mesh(mesh, state);
        return bbox;
    }

    // Create set for fast lookup
    std::unordered_set<int32_t> part_set(part_ids.begin(), part_ids.end());

    // Collect node indices used by elements in specified parts
    std::unordered_set<size_t> node_indices;

    // Check solid elements
    if (!mesh.solid_parts.empty()) {
        for (size_t i = 0; i < mesh.solids.size(); ++i) {
            if (i < mesh.solid_parts.size() && part_set.count(mesh.solid_parts[i])) {
                // Add all nodes of this element
                for (int32_t nid : mesh.solids[i].node_ids) {
                    // Convert node ID to index (0-based)
                    // Node IDs are 1-based in the original model
                    if (mesh.real_node_ids.empty()) {
                        node_indices.insert(static_cast<size_t>(nid - 1));
                    } else {
                        // Search for node with this ID
                        for (size_t j = 0; j < mesh.real_node_ids.size(); ++j) {
                            if (mesh.real_node_ids[j] == nid) {
                                node_indices.insert(j);
                                break;
                            }
                        }
                    }
                }
            }
        }
    }

    // Check shell elements
    if (!mesh.shell_materials.empty()) {
        for (size_t i = 0; i < mesh.shells.size(); ++i) {
            // Note: shell_parts would be needed here, currently using materials
            if (i < mesh.shell_materials.size()) {
                // Add all nodes of this element
                for (int32_t nid : mesh.shells[i].node_ids) {
                    if (mesh.real_node_ids.empty()) {
                        node_indices.insert(static_cast<size_t>(nid - 1));
                    } else {
                        for (size_t j = 0; j < mesh.real_node_ids.size(); ++j) {
                            if (mesh.real_node_ids[j] == nid) {
                                node_indices.insert(j);
                                break;
                            }
                        }
                    }
                }
            }
        }
    }

    // Convert to vector and compute bbox
    std::vector<size_t> indices(node_indices.begin(), node_indices.end());
    return from_nodes(mesh, indices, state);
}

BoundingBox BoundingBox::from_nodes(
    const data::Mesh& mesh,
    const std::vector<size_t>& node_indices,
    const data::StateData* state)
{
    BoundingBox bbox;

    if (node_indices.empty()) {
        return bbox;
    }

    bool has_disp = state && !state->node_displacements.empty();

    for (size_t idx : node_indices) {
        if (idx >= mesh.nodes.size()) continue;

        double x = mesh.nodes[idx].x;
        double y = mesh.nodes[idx].y;
        double z = mesh.nodes[idx].z;

        if (has_disp && idx * 3 + 2 < state->node_displacements.size()) {
            x += state->node_displacements[idx * 3 + 0];
            y += state->node_displacements[idx * 3 + 1];
            z += state->node_displacements[idx * 3 + 2];
        }

        bbox.expand(Point3D(x, y, z));
    }

    return bbox;
}

} // namespace analysis
} // namespace kood3plot