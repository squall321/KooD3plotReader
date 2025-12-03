/**
 * @file GeometryAnalyzer.h
 * @brief Geometry analysis and intelligent section calculation
 *
 * Based on IntelligentSectionCalculator from KooDynaPostProcessor
 */

#pragma once

#include "LSPrePostRenderer.h"
#include <array>
#include <vector>
#include <string>
#include <stdexcept>
#include <cmath>
#include <limits>

namespace kood3plot {

// Forward declaration
class D3plotReader;

namespace render {

/**
 * @brief Bounding box structure
 */
struct BoundingBox {
    Point3D min;      ///< Minimum coordinates [x, y, z]
    Point3D max;      ///< Maximum coordinates [x, y, z]
    Point3D center;   ///< Center coordinates [x, y, z]

    /**
     * @brief Get size along a specific axis
     * @param axis 0=X, 1=Y, 2=Z
     * @return Size along the axis
     */
    double getSize(int axis) const {
        if (axis < 0 || axis > 2) {
            throw std::out_of_range("Axis must be 0 (X), 1 (Y), or 2 (Z)");
        }
        return max[axis] - min[axis];
    }

    /**
     * @brief Get volume of bounding box
     */
    double getVolume() const {
        return (max[0] - min[0]) * (max[1] - min[1]) * (max[2] - min[2]);
    }

    /**
     * @brief Check if bounding box is valid
     */
    bool isValid() const {
        return min[0] <= max[0] && min[1] <= max[1] && min[2] <= max[2];
    }
};

/**
 * @brief Section position types
 */
enum class SectionPosition {
    CENTER,       ///< 50% (middle)
    QUARTER_1,    ///< 25%
    QUARTER_3,    ///< 75%
    EDGE_MIN,     ///< 0% (minimum boundary)
    EDGE_MAX,     ///< 100% (maximum boundary)
    CUSTOM        ///< Custom ratio
};

/**
 * @brief Geometry analyzer for automatic section calculation
 *
 * This class provides intelligent section plane calculation based on
 * model geometry (bounding boxes, part dimensions, etc.)
 */
class GeometryAnalyzer {
public:
    GeometryAnalyzer() = default;
    ~GeometryAnalyzer() = default;

    // ============================================================
    // Bounding Box Calculation
    // ============================================================

    /**
     * @brief Calculate bounding box for entire model
     * @param reader D3plot reader
     * @param state_index State/timestep index (default: 0)
     * @return BoundingBox structure
     */
    static BoundingBox calculateModelBounds(
        D3plotReader& reader,
        size_t state_index = 0
    );

    /**
     * @brief Calculate bounding box for a specific part
     * @param reader D3plot reader
     * @param part_id Part ID (-1 for all parts)
     * @param state_index State/timestep index (default: 0)
     * @return BoundingBox structure
     */
    static BoundingBox calculatePartBounds(
        D3plotReader& reader,
        int part_id,
        size_t state_index = 0
    );

    // ============================================================
    // Section Plane Generation
    // ============================================================

    /**
     * @brief Create section plane at a specific position
     * @param bbox Bounding box
     * @param orientation "X", "Y", or "Z"
     * @param position Position type
     * @param custom_ratio Custom ratio (0.0-1.0), only used if position=CUSTOM
     * @return SectionPlane structure
     */
    static SectionPlane createSectionPlane(
        const BoundingBox& bbox,
        const std::string& orientation,
        SectionPosition position,
        double custom_ratio = 0.5
    );

    /**
     * @brief Generate multiple evenly-spaced sections
     * @param bbox Bounding box
     * @param orientation "X", "Y", or "Z"
     * @param num_sections Number of sections
     * @return Vector of section planes
     */
    static std::vector<SectionPlane> createEvenSections(
        const BoundingBox& bbox,
        const std::string& orientation,
        int num_sections
    );

    /**
     * @brief Generate sections with uniform spacing
     * @param bbox Bounding box
     * @param orientation "X", "Y", or "Z"
     * @param spacing Distance between sections
     * @return Vector of section planes
     */
    static std::vector<SectionPlane> createUniformSections(
        const BoundingBox& bbox,
        const std::string& orientation,
        double spacing
    );

    /**
     * @brief Create standard 3-section layout (25%, 50%, 75%)
     * @param bbox Bounding box
     * @param orientation "X", "Y", or "Z"
     * @return Vector of 3 section planes
     */
    static std::vector<SectionPlane> createStandard3Sections(
        const BoundingBox& bbox,
        const std::string& orientation
    );

    /**
     * @brief Create offset sections from edges
     * @param bbox Bounding box
     * @param orientation "X", "Y", or "Z"
     * @param offset_percent Offset from edges as percentage (e.g., 10.0 for 10%)
     * @return Vector of 2 section planes (one from each edge)
     */
    static std::vector<SectionPlane> createOffsetSections(
        const BoundingBox& bbox,
        const std::string& orientation,
        double offset_percent
    );

    // ============================================================
    // Utility Functions
    // ============================================================

    /**
     * @brief Get ratio value for a position type
     * @param position Position type
     * @return Ratio value (0.0 to 1.0)
     */
    static double getPositionRatio(SectionPosition position);

    /**
     * @brief Get axis index from orientation string
     * @param orientation "X", "Y", or "Z"
     * @return 0 for X, 1 for Y, 2 for Z
     */
    static int getAxisIndex(const std::string& orientation);

    /**
     * @brief Get normal vector for orientation
     * @param orientation "X", "Y", or "Z"
     * @return Normal vector
     */
    static Point3D getNormalVector(const std::string& orientation);

    /**
     * @brief Convert position type to string
     * @param position Position type
     * @return String representation
     */
    static std::string positionToString(SectionPosition position);

    /**
     * @brief Parse position type from string
     * @param str Position string
     * @return Position type
     */
    static SectionPosition stringToPosition(const std::string& str);

    /**
     * @brief Calculate bounding box from node coordinates
     * @param coords Vector of node coordinates
     * @return BoundingBox structure
     */
    static BoundingBox calculateBoundsFromCoords(
        const std::vector<Point3D>& coords
    );

private:
};

} // namespace render
} // namespace kood3plot
