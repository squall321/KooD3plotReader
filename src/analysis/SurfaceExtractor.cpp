/**
 * @file SurfaceExtractor.cpp
 * @brief Implementation of SurfaceExtractor
 * @author KooD3plot Development Team
 * @date 2024-12-04
 */

#include "kood3plot/analysis/SurfaceExtractor.hpp"
#include <sstream>
#include <algorithm>
#include <cmath>

namespace kood3plot {
namespace analysis {

// ============================================================
// Static Data
// ============================================================

// Hexa face node indices (LS-DYNA convention, outward normals)
const int SurfaceExtractor::HEXA_FACE_NODES[6][4] = {
    {0, 3, 2, 1},  // Face 0: Z- (bottom)
    {4, 5, 6, 7},  // Face 1: Z+ (top)
    {0, 1, 5, 4},  // Face 2: Y- (front)
    {2, 3, 7, 6},  // Face 3: Y+ (back)
    {0, 4, 7, 3},  // Face 4: X- (left)
    {1, 2, 6, 5}   // Face 5: X+ (right)
};

// ============================================================
// Constructor
// ============================================================

SurfaceExtractor::SurfaceExtractor(D3plotReader& reader)
    : reader_(reader), initialized_(false) {
}

// ============================================================
// Initialization
// ============================================================

bool SurfaceExtractor::initialize() {
    if (initialized_) return true;

    try {
        mesh_ = reader_.read_mesh();
        initialized_ = true;
        return true;
    } catch (const std::exception& e) {
        last_error_ = std::string("Failed to read mesh: ") + e.what();
        return false;
    }
}

// ============================================================
// Surface Extraction
// ============================================================

SurfaceExtractionResult SurfaceExtractor::extractExteriorSurfaces() {
    return extractExteriorSurfaces({});  // Empty = all parts
}

SurfaceExtractionResult SurfaceExtractor::extractExteriorSurfaces(
    const std::vector<int32_t>& part_ids) {

    if (!initialize()) {
        return SurfaceExtractionResult();
    }

    SurfaceExtractionResult result;

    // Convert part_ids to set for quick lookup
    std::unordered_set<int32_t> part_set(part_ids.begin(), part_ids.end());
    bool filter_parts = !part_ids.empty();

    // Face count map: hash -> count
    // A face appearing once is exterior, appearing twice is interior
    std::unordered_map<std::string, int> face_count;
    std::unordered_map<std::string, Face> face_map;

    // Process solid elements
    result.total_solid_elements = static_cast<int32_t>(mesh_.num_solids);

    for (size_t elem_idx = 0; elem_idx < mesh_.num_solids; ++elem_idx) {
        const auto& elem = mesh_.solids[elem_idx];

        // Get part ID
        int32_t part_id = 1;
        if (!mesh_.solid_parts.empty() && elem_idx < mesh_.solid_parts.size()) {
            part_id = mesh_.solid_parts[elem_idx];
        }

        // Filter by part if specified
        if (filter_parts && part_set.find(part_id) == part_set.end()) {
            continue;
        }

        // 요소 종류에 맞는 실제 면(삼각형·사각형)
        std::vector<int32_t> conn(8);
        for (int i = 0; i < 8; ++i) {
            conn[i] = elem.node_ids[i] - 1;   // 1-based 내부 번호 → 0-based
        }
        for (auto& face_nodes : solidFaceNodeSets(conn)) {
            std::string hash = generateFaceHash(face_nodes);
            face_count[hash]++;

            // Store face info (only first occurrence)
            if (face_count[hash] == 1) {
                Face face = buildFace(static_cast<int32_t>(elem_idx), 0,
                                      face_nodes, part_id, SurfaceElementType::SOLID);

                // Set real element ID
                if (!mesh_.real_solid_ids.empty() && elem_idx < mesh_.real_solid_ids.size()) {
                    face.element_real_id = mesh_.real_solid_ids[elem_idx];
                } else {
                    face.element_real_id = static_cast<int32_t>(elem_idx + 1);
                }

                face_map[hash] = face;
            }
        }
    }

    // Collect exterior faces (count == 1)
    for (const auto& pair : face_count) {
        if (pair.second == 1) {
            result.faces.push_back(face_map[pair.first]);
        }
    }

    // Process shell elements (each shell is a surface)
    result.total_shell_elements = static_cast<int32_t>(mesh_.num_shells);

    for (size_t elem_idx = 0; elem_idx < mesh_.num_shells; ++elem_idx) {
        const auto& elem = mesh_.shells[elem_idx];

        // Get part ID
        int32_t part_id = 1;
        if (!mesh_.shell_parts.empty() && elem_idx < mesh_.shell_parts.size()) {
            part_id = mesh_.shell_parts[elem_idx];
        }

        // Filter by part if specified
        if (filter_parts && part_set.find(part_id) == part_set.end()) {
            continue;
        }

        // Shell has 4 nodes (quad)
        std::vector<int32_t> face_nodes(4);
        for (int i = 0; i < 4 && i < static_cast<int>(elem.node_ids.size()); ++i) {
            face_nodes[i] = elem.node_ids[i] - 1;  // Convert to 0-based
        }

        Face face = buildFace(static_cast<int32_t>(elem_idx), 0,
                              face_nodes, part_id, SurfaceElementType::SHELL);

        // Set real element ID
        if (!mesh_.real_shell_ids.empty() && elem_idx < mesh_.real_shell_ids.size()) {
            face.element_real_id = mesh_.real_shell_ids[elem_idx];
        } else {
            face.element_real_id = static_cast<int32_t>(elem_idx + 1);
        }

        result.faces.push_back(face);
    }

    result.total_exterior_faces = static_cast<int32_t>(result.faces.size());

    // Collect unique parts
    std::unordered_set<int32_t> unique_parts;
    for (const auto& face : result.faces) {
        unique_parts.insert(face.part_id);
    }
    result.parts_included.assign(unique_parts.begin(), unique_parts.end());
    std::sort(result.parts_included.begin(), result.parts_included.end());

    return result;
}

SurfaceExtractionResult SurfaceExtractor::extractSolidExteriorSurfaces(
    const std::vector<int32_t>& part_ids) {

    if (!initialize()) {
        return SurfaceExtractionResult();
    }

    // Use the main extraction but only process solids
    auto result = extractExteriorSurfaces(part_ids);

    // Remove shell faces
    result.faces.erase(
        std::remove_if(result.faces.begin(), result.faces.end(),
            [](const Face& f) { return f.element_type != SurfaceElementType::SOLID; }),
        result.faces.end()
    );

    result.total_exterior_faces = static_cast<int32_t>(result.faces.size());
    return result;
}

SurfaceExtractionResult SurfaceExtractor::extractShellSurfaces(
    const std::vector<int32_t>& part_ids, bool include_bottom) {

    if (!initialize()) {
        return SurfaceExtractionResult();
    }

    SurfaceExtractionResult result;
    std::unordered_set<int32_t> part_set(part_ids.begin(), part_ids.end());
    bool filter_parts = !part_ids.empty();

    result.total_shell_elements = static_cast<int32_t>(mesh_.num_shells);

    for (size_t elem_idx = 0; elem_idx < mesh_.num_shells; ++elem_idx) {
        const auto& elem = mesh_.shells[elem_idx];

        int32_t part_id = 1;
        if (!mesh_.shell_parts.empty() && elem_idx < mesh_.shell_parts.size()) {
            part_id = mesh_.shell_parts[elem_idx];
        }

        if (filter_parts && part_set.find(part_id) == part_set.end()) {
            continue;
        }

        std::vector<int32_t> face_nodes(4);
        for (int i = 0; i < 4 && i < static_cast<int>(elem.node_ids.size()); ++i) {
            face_nodes[i] = elem.node_ids[i] - 1;
        }

        // Top face
        Face top_face = buildFace(static_cast<int32_t>(elem_idx), 0,
                                   face_nodes, part_id, SurfaceElementType::SHELL);
        if (!mesh_.real_shell_ids.empty() && elem_idx < mesh_.real_shell_ids.size()) {
            top_face.element_real_id = mesh_.real_shell_ids[elem_idx];
        }
        result.faces.push_back(top_face);

        // Bottom face (reversed normal)
        if (include_bottom) {
            std::vector<int32_t> reversed_nodes = {
                face_nodes[0], face_nodes[3], face_nodes[2], face_nodes[1]
            };
            Face bottom_face = buildFace(static_cast<int32_t>(elem_idx), 1,
                                          reversed_nodes, part_id, SurfaceElementType::SHELL);
            bottom_face.element_real_id = top_face.element_real_id;
            result.faces.push_back(bottom_face);
        }
    }

    result.total_exterior_faces = static_cast<int32_t>(result.faces.size());
    return result;
}

// ============================================================
// Direction Filtering
// ============================================================

std::vector<Face> SurfaceExtractor::filterByDirection(
    const std::vector<Face>& faces,
    const Vec3& reference_direction,
    double angle_threshold_degrees) {

    std::vector<Face> filtered;

    // Normalize reference direction
    Vec3 ref_norm = reference_direction.normalizedSafe();
    if (ref_norm.isZero()) {
        return filtered;  // Invalid reference direction
    }

    for (const auto& face : faces) {
        // 넓이 0 인 퇴화 면(절점이 겹친 hex 면)은 법선이 0 벡터다. angleTo 는 0 벡터에
        // 0° 를 돌려주므로 거르지 않으면 +Z·-Z 어느 필터에도 들어간다.
        if (face.normal.isZero()) {
            continue;
        }
        double angle = face.normal.angleToInDegrees(ref_norm);
        if (angle <= angle_threshold_degrees) {
            filtered.push_back(face);
        }
    }

    return filtered;
}

std::vector<Face> SurfaceExtractor::filterByPart(
    const std::vector<Face>& faces,
    const std::vector<int32_t>& part_ids) {

    std::unordered_set<int32_t> part_set(part_ids.begin(), part_ids.end());
    std::vector<Face> filtered;

    for (const auto& face : faces) {
        if (part_set.find(face.part_id) != part_set.end()) {
            filtered.push_back(face);
        }
    }

    return filtered;
}

// ============================================================
// Normal Update
// ============================================================

void SurfaceExtractor::updateNormalsForState(std::vector<Face>& faces, size_t state_index) {
    auto state = reader_.read_state(state_index);

    auto cd = reader_.get_control_data();
    int ndim = (cd.NDIM >= 4) ? 3 : cd.NDIM;

    for (auto& face : faces) {
        if (face.node_indices.size() < 4) continue;

        // Get deformed node positions
        Vec3 p0 = getNodePositionFromState(face.node_indices[0], state);
        Vec3 p1 = getNodePositionFromState(face.node_indices[1], state);
        Vec3 p2 = getNodePositionFromState(face.node_indices[2], state);
        Vec3 p3 = getNodePositionFromState(face.node_indices[3], state);

        // Update normal, centroid, and area
        face.normal = calculateQuadNormal(p0, p1, p2, p3);
        face.centroid = calculateQuadCentroid(p0, p1, p2, p3);
        face.area = calculateQuadArea(p0, p1, p2, p3);
    }
}

// ============================================================
// Utility Functions
// ============================================================

Vec3 SurfaceExtractor::calculateQuadNormal(
    const Vec3& p0, const Vec3& p1, const Vec3& p2, const Vec3& p3) {

    // Use diagonal cross product for potentially non-planar quads
    Vec3 diag1 = p2 - p0;
    Vec3 diag2 = p3 - p1;
    Vec3 normal = diag1.cross(diag2);

    return normal.normalizedSafe();
}

Vec3 SurfaceExtractor::calculateQuadCentroid(
    const Vec3& p0, const Vec3& p1, const Vec3& p2, const Vec3& p3) {

    return (p0 + p1 + p2 + p3) * 0.25;
}

double SurfaceExtractor::calculateQuadArea(
    const Vec3& p0, const Vec3& p1, const Vec3& p2, const Vec3& p3) {

    // Split quad into two triangles and sum areas
    // Triangle 1: p0, p1, p2
    Vec3 v1 = p1 - p0;
    Vec3 v2 = p2 - p0;
    double area1 = 0.5 * v1.cross(v2).magnitude();

    // Triangle 2: p0, p2, p3
    Vec3 v3 = p3 - p0;
    double area2 = 0.5 * v2.cross(v3).magnitude();

    return area1 + area2;
}

std::vector<std::vector<int32_t>> SurfaceExtractor::solidFaceNodeSets(
    const std::vector<int32_t>& n) {

    std::vector<std::vector<int32_t>> faces;
    if (n.size() < 8) return faces;

    // 처음 등장 순서로 고유 절점
    std::vector<int32_t> uniq;
    for (int32_t v : n) {
        if (std::find(uniq.begin(), uniq.end(), v) == uniq.end()) uniq.push_back(v);
    }

    // 사면체: (a,b,c,d,d,d,d,d) — 육면체 면 규약으로는 삼각형 ABC·ACD 가 만들어지지
    // 않고 {a,b,c,d} 짜리 가짜 면이 생긴다. 네 삼각형을 직접 만든다.
    const bool tet_pattern = uniq.size() == 4 &&
                             n[4] == n[3] && n[5] == n[3] && n[6] == n[3] && n[7] == n[3];
    if (tet_pattern) {
        const int tri[4][3] = {{0, 1, 2}, {0, 1, 3}, {0, 2, 3}, {1, 2, 3}};
        for (const auto& t : tri) {
            faces.push_back({uniq[t[0]], uniq[t[1]], uniq[t[2]]});
        }
        return faces;
    }

    // 육면체·쐐기·피라미드: 6면에서 **인접 중복 절점을 접는다**.
    // 쐐기 (a,b,c,d,e,e,f,f) → 사각 3 + 삼각 2, 피라미드 (a,b,c,d,e,e,e,e) → 사각 1 + 삼각 4.
    for (int f = 0; f < 6; ++f) {
        std::vector<int32_t> poly;
        for (int i = 0; i < 4; ++i) {
            int32_t v = n[HEXA_FACE_NODES[f][i]];
            if (std::find(poly.begin(), poly.end(), v) == poly.end()) poly.push_back(v);
        }
        if (poly.size() >= 3) faces.push_back(std::move(poly));   // 2개 이하는 퇴화한 모서리
    }
    return faces;
}

std::string SurfaceExtractor::generateFaceHash(const std::vector<int32_t>& node_indices) {
    // Sort node indices to make hash order-independent
    std::vector<int32_t> sorted = node_indices;
    std::sort(sorted.begin(), sorted.end());

    std::ostringstream oss;
    for (size_t i = 0; i < sorted.size(); ++i) {
        if (i > 0) oss << ",";
        oss << sorted[i];
    }
    return oss.str();
}

Face SurfaceExtractor::buildFace(
    int32_t elem_index, int face_local_idx,
    const std::vector<int32_t>& node_indices,
    int32_t part_id, SurfaceElementType elem_type) {

    Face face;
    face.element_id = elem_index;
    face.part_id = part_id;
    face.element_type = elem_type;
    face.face_local_index = face_local_idx;
    face.node_indices = node_indices;

    // Set real node IDs
    face.node_real_ids.resize(node_indices.size());
    for (size_t i = 0; i < node_indices.size(); ++i) {
        int32_t idx = node_indices[i];
        if (!mesh_.real_node_ids.empty() && idx < static_cast<int32_t>(mesh_.real_node_ids.size())) {
            face.node_real_ids[i] = mesh_.real_node_ids[idx];
        } else {
            face.node_real_ids[i] = idx + 1;  // 1-based fallback
        }
    }

    // Calculate geometry from initial mesh
    if (node_indices.size() >= 3) {
        Vec3 p0 = getNodePosition(node_indices[0]);
        Vec3 p1 = getNodePosition(node_indices[1]);
        Vec3 p2 = getNodePosition(node_indices[2]);
        if (node_indices.size() >= 4) {
            Vec3 p3 = getNodePosition(node_indices[3]);
            face.normal = calculateQuadNormal(p0, p1, p2, p3);
            face.centroid = calculateQuadCentroid(p0, p1, p2, p3);
            face.area = calculateQuadArea(p0, p1, p2, p3);
        } else {
            face.normal = (p1 - p0).cross(p2 - p0).normalizedSafe();
            face.centroid = (p0 + p1 + p2) * (1.0 / 3.0);
            face.area = 0.5 * (p1 - p0).cross(p2 - p0).magnitude();
        }

        // 법선은 절점 순서 규약이 아니라 **요소 중심에서 바깥쪽**으로 정한다.
        // 퇴화 육면체(사면체·쐐기)는 순서 규약이 덱마다 달라 순서만 믿으면 안쪽을 향한다.
        if (elem_type == SurfaceElementType::SOLID && !face.normal.isZero() &&
            elem_index >= 0 && static_cast<size_t>(elem_index) < mesh_.solids.size()) {
            const auto& elem = mesh_.solids[elem_index];
            Vec3 elem_center;
            int counted = 0;
            for (int i = 0; i < 8; ++i) {
                int32_t idx = elem.node_ids[i] - 1;
                if (idx < 0 || idx >= static_cast<int32_t>(mesh_.nodes.size())) continue;
                elem_center = elem_center + getNodePosition(idx);
                ++counted;
            }
            if (counted > 0) {
                elem_center = elem_center * (1.0 / counted);
                if (face.normal.dot(face.centroid - elem_center) < 0.0) {
                    face.normal = face.normal * -1.0;
                }
            }
        }
    }

    return face;
}

Vec3 SurfaceExtractor::getNodePosition(int32_t node_index) const {
    if (node_index < 0 || node_index >= static_cast<int32_t>(mesh_.nodes.size())) {
        return Vec3();
    }
    const auto& node = mesh_.nodes[node_index];
    return Vec3(node.x, node.y, node.z);
}

Vec3 SurfaceExtractor::getNodePositionFromState(
    int32_t node_index, const data::StateData& state) const {

    auto cd = reader_.get_control_data();
    int ndim = (cd.NDIM >= 4) ? 3 : cd.NDIM;

    // Check if displacement data is available
    if (cd.IU != 0 && !state.node_displacements.empty()) {
        size_t idx = node_index * ndim;
        if (idx + 2 < state.node_displacements.size()) {
            // IU=1: node_displacements contains current coordinates
            return Vec3(
                state.node_displacements[idx],
                state.node_displacements[idx + 1],
                state.node_displacements[idx + 2]
            );
        }
    }

    // Fallback to initial position
    return getNodePosition(node_index);
}

} // namespace analysis
} // namespace kood3plot
