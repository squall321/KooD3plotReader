/**
 * @file SurfaceExtractor.hpp
 * @brief Extract exterior surfaces from solid/shell elements
 * @author KooD3plot Development Team
 * @date 2024-12-04
 * @version 1.0.0
 *
 * Provides functionality to:
 * - Identify exterior (boundary) faces of solid elements
 * - Calculate face normals and centroids
 * - Filter faces by orientation relative to a reference direction
 */

#pragma once

#include "VectorMath.hpp"
#include "kood3plot/D3plotReader.hpp"
#include "kood3plot/data/Mesh.hpp"
#include "kood3plot/data/StateData.hpp"
#include <vector>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <algorithm>
#include <memory>

namespace kood3plot {
namespace analysis {

/**
 * @brief Element type enumeration for surface extraction
 */
enum class SurfaceElementType {
    SOLID,       ///< 8-node hexahedron (6 faces)
    SHELL,       ///< 4-node shell (1 or 2 faces)
    TSHELL,      ///< Thick shell
    UNKNOWN
};

/**
 * @brief Single face (quad or triangle) information
 */
struct Face {
    int32_t element_id = 0;          ///< Parent element ID (internal 0-based index)
    int32_t element_real_id = 0;     ///< Parent element real ID (from NARBS)
    int32_t part_id = 0;             ///< Part ID
    SurfaceElementType element_type = SurfaceElementType::UNKNOWN;

    std::vector<int32_t> node_indices;  ///< Node indices (internal 0-based)
    std::vector<int32_t> node_real_ids; ///< Node real IDs (from NARBS)

    Vec3 normal;                     ///< Face normal vector (unit, outward)
    Vec3 centroid;                   ///< Face centroid
    double area = 0.0;               ///< Face area

    int face_local_index = 0;        ///< Local face index within element (0-5 for hexa)

    /**
     * @brief Check if this face shares the same nodes as another (ignoring order)
     */
    bool hasSameNodes(const Face& other) const {
        if (node_indices.size() != other.node_indices.size()) return false;

        std::vector<int32_t> sorted1 = node_indices;
        std::vector<int32_t> sorted2 = other.node_indices;
        std::sort(sorted1.begin(), sorted1.end());
        std::sort(sorted2.begin(), sorted2.end());

        return sorted1 == sorted2;
    }
};

/**
 * @brief Result of surface extraction
 */
struct SurfaceExtractionResult {
    std::vector<Face> faces;                    ///< All exterior faces
    int32_t total_solid_elements = 0;           ///< Total solid elements processed
    int32_t total_shell_elements = 0;           ///< Total shell elements processed
    int32_t total_exterior_faces = 0;           ///< Number of exterior faces found
    std::vector<int32_t> parts_included;        ///< Parts included in extraction
};

/**
 * @brief Exterior surface extractor
 *
 * Extracts exterior (boundary) surfaces from solid and shell elements.
 * For solid elements, a face is exterior if it's not shared with another element.
 * For shell elements, both top and bottom faces can be considered exterior.
 *
 * Usage:
 * @code
 * D3plotReader reader("d3plot");
 * reader.open();
 *
 * SurfaceExtractor extractor(reader);
 *
 * // Extract all exterior surfaces
 * auto result = extractor.extractExteriorSurfaces();
 *
 * // Filter by direction (e.g., bottom-facing surfaces)
 * Vec3 down(0, 0, -1);
 * auto bottom_faces = SurfaceExtractor::filterByDirection(result.faces, down, 30.0);
 *
 * std::cout << "Found " << bottom_faces.size() << " bottom-facing faces\n";
 * @endcode
 */
class SurfaceExtractor {
public:
    /**
     * @brief Constructor
     * @param reader D3plotReader reference (must be opened)
     */
    explicit SurfaceExtractor(D3plotReader& reader);

    /**
     * @brief Destructor
     */
    ~SurfaceExtractor() = default;

    /**
     * @brief Initialize the extractor (reads mesh data)
     * @return true if successful
     */
    bool initialize();

    /**
     * @brief Check if initialized
     */
    bool isInitialized() const { return initialized_; }

    // ============================================================
    // Surface Extraction
    // ============================================================

    /**
     * @brief Extract all exterior surfaces from the model
     * @return Extraction result with all exterior faces
     */
    SurfaceExtractionResult extractExteriorSurfaces();

    /**
     * @brief Extract exterior surfaces from specific parts
     * @param part_ids List of part IDs to include
     * @return Extraction result with exterior faces from specified parts
     */
    SurfaceExtractionResult extractExteriorSurfaces(const std::vector<int32_t>& part_ids);

    /**
     * @brief Extract exterior surfaces from solid elements only
     * @param part_ids Optional list of part IDs (empty = all parts)
     * @return Extraction result
     */
    SurfaceExtractionResult extractSolidExteriorSurfaces(const std::vector<int32_t>& part_ids = {});

    /**
     * @brief Extract shell element surfaces
     * @param part_ids Optional list of part IDs (empty = all parts)
     * @param include_bottom Include bottom faces of shells
     * @return Extraction result
     */
    SurfaceExtractionResult extractShellSurfaces(
        const std::vector<int32_t>& part_ids = {},
        bool include_bottom = false
    );

    // ============================================================
    // Direction Filtering
    // ============================================================

    /**
     * @brief Filter faces by orientation relative to reference direction
     * @param faces Input faces
     * @param reference_direction Reference direction vector (will be normalized)
     * @param angle_threshold_degrees Maximum angle from reference (0-180)
     * @return Filtered faces whose normals are within angle threshold of reference
     */
    static std::vector<Face> filterByDirection(
        const std::vector<Face>& faces,
        const Vec3& reference_direction,
        double angle_threshold_degrees
    );

    /**
     * @brief Filter faces by part ID
     * @param faces Input faces
     * @param part_ids Part IDs to include
     * @return Filtered faces
     */
    static std::vector<Face> filterByPart(
        const std::vector<Face>& faces,
        const std::vector<int32_t>& part_ids
    );

    // ============================================================
    // Normal Update (for deformed configurations)
    // ============================================================

    /**
     * @brief Update face normals and centroids for a specific state
     * @param faces Faces to update (modified in place)
     * @param state_index State index
     *
     * This updates the normals and centroids based on the deformed node positions.
     */
    void updateNormalsForState(std::vector<Face>& faces, size_t state_index);

    // ============================================================
    // Utility Functions
    // ============================================================

    /**
     * @brief Calculate face normal from node positions
     * @param p0, p1, p2, p3 Node positions (quad face)
     * @return Unit normal vector
     */
    static Vec3 calculateQuadNormal(const Vec3& p0, const Vec3& p1,
                                     const Vec3& p2, const Vec3& p3);

    /**
     * @brief Calculate face centroid from node positions
     * @param p0, p1, p2, p3 Node positions (quad face)
     * @return Centroid position
     */
    static Vec3 calculateQuadCentroid(const Vec3& p0, const Vec3& p1,
                                       const Vec3& p2, const Vec3& p3);

    /**
     * @brief Calculate face area from node positions
     * @param p0, p1, p2, p3 Node positions (quad face)
     * @return Area
     */
    static double calculateQuadArea(const Vec3& p0, const Vec3& p1,
                                    const Vec3& p2, const Vec3& p3);

    /**
     * @brief Get last error message
     */
    const std::string& getLastError() const { return last_error_; }

private:
    D3plotReader& reader_;
    data::Mesh mesh_;
    bool initialized_ = false;
    std::string last_error_;

    // ============================================================
    // Hexa element face definitions (8-node hexahedron)
    // ============================================================
    // Node numbering (LS-DYNA convention):
    //
    //       7-------6
    //      /|      /|
    //     / |     / |
    //    4-------5  |
    //    |  3----|--2
    //    | /     | /
    //    |/      |/
    //    0-------1
    //
    // Faces (outward normals, right-hand rule):
    // Face 0: 0,3,2,1 (Z- / bottom)
    // Face 1: 4,5,6,7 (Z+ / top)
    // Face 2: 0,1,5,4 (Y- / front)
    // Face 3: 2,3,7,6 (Y+ / back)
    // Face 4: 0,4,7,3 (X- / left)
    // Face 5: 1,2,6,5 (X+ / right)

    static const int HEXA_FACE_NODES[6][4];

    /**
     * @brief Generate a hash key for a face (node indices sorted)
     */
    static std::string generateFaceHash(const std::vector<int32_t>& node_indices);

    /**
     * @brief Build face from node indices
     */
    Face buildFace(int32_t elem_index, int face_local_idx,
                   const std::vector<int32_t>& node_indices,
                   int32_t part_id, SurfaceElementType elem_type);

    /**
     * @brief Get node position from mesh
     */
    Vec3 getNodePosition(int32_t node_index) const;

    /**
     * @brief Get node position from state (deformed)
     */
    Vec3 getNodePositionFromState(int32_t node_index, const data::StateData& state) const;
};

} // namespace analysis
} // namespace kood3plot
