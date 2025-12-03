#pragma once

/**
 * @file QueryTypes.h
 * @brief Common type definitions for the KooD3plot Query System
 * @author KooD3plot V3 Development Team
 * @date 2025-11-21
 * @version 3.0.0
 *
 * This file contains fundamental types, enums, and structures used
 * throughout the query system. All query components depend on these definitions.
 */

#include <string>
#include <vector>
#include <array>
#include <map>
#include <optional>
#include <functional>
#include <memory>
#include <cstdint>

namespace kood3plot {

// Forward declaration of D3plotReader from core namespace
class D3plotReader;

namespace query {

// ============================================================
// Forward Declarations
// ============================================================

// Note: D3plotReader is in kood3plot namespace (not kood3plot::query)
class PartSelector;
class QuantitySelector;
class TimeSelector;
class SpatialSelector;
class ValueFilter;
class OutputSpec;
class D3plotQuery;
class QueryResult;

// ============================================================
// Enumerations
// ============================================================

/**
 * @brief Pattern matching type for part selection
 */
enum class PatternType {
    GLOB,       ///< Glob-style pattern matching (*, ?)
    REGEX       ///< Regular expression pattern matching
};

/**
 * @brief Physical quantity types available in d3plot
 */
enum class QuantityType {
    // ===== Stress Components (9 types) =====
    STRESS_X = 1,           ///< X-direction stress
    STRESS_Y = 2,           ///< Y-direction stress
    STRESS_Z = 3,           ///< Z-direction stress
    STRESS_XY = 4,          ///< XY shear stress
    STRESS_YZ = 5,          ///< YZ shear stress
    STRESS_ZX = 6,          ///< ZX shear stress
    STRESS_VON_MISES = 9,   ///< Von Mises stress
    STRESS_PRESSURE = 8,    ///< Pressure
    STRESS_MAX_SHEAR = 13,  ///< Maximum shear stress

    // ===== Principal Stresses (3 types) =====
    STRESS_PRINCIPAL_1 = 14, ///< 1st principal stress
    STRESS_PRINCIPAL_2 = 15, ///< 2nd principal stress
    STRESS_PRINCIPAL_3 = 16, ///< 3rd principal stress

    // ===== Advanced Stress (1 type) =====
    STRESS_SIGNED_VON_MISES = 530, ///< Signed Von Mises stress

    // ===== Strain Components (6 types) =====
    STRAIN_X = 57,          ///< X-direction strain
    STRAIN_Y = 58,          ///< Y-direction strain
    STRAIN_Z = 59,          ///< Z-direction strain
    STRAIN_XY = 60,         ///< XY shear strain
    STRAIN_YZ = 61,         ///< YZ shear strain
    STRAIN_ZX = 62,         ///< ZX shear strain

    // ===== Effective Strains (2 types) =====
    STRAIN_EFFECTIVE_PLASTIC = 7,  ///< Effective plastic strain
    STRAIN_EFFECTIVE = 80,          ///< Effective strain

    // ===== Principal Strains (3 types) =====
    STRAIN_PRINCIPAL_1 = 77, ///< 1st principal strain
    STRAIN_PRINCIPAL_2 = 78, ///< 2nd principal strain
    STRAIN_PRINCIPAL_3 = 79, ///< 3rd principal strain

    // ===== Special Strains (1 type) =====
    STRAIN_VOLUMETRIC = 529, ///< Volumetric strain

    // ===== Displacement Components (4 types) =====
    DISPLACEMENT_X = 17,     ///< X-direction displacement
    DISPLACEMENT_Y = 18,     ///< Y-direction displacement
    DISPLACEMENT_Z = 19,     ///< Z-direction displacement
    DISPLACEMENT_MAGNITUDE = 20, ///< Resultant displacement

    // ===== Velocity & Acceleration (2 types) =====
    VELOCITY_MAGNITUDE = 24,     ///< Resultant velocity
    ACCELERATION_MAGNITUDE = 23, ///< Resultant acceleration

    // ===== Energy (2 types) =====
    ENERGY_HOURGLASS_DENSITY = 43,  ///< Hourglass energy density
    ENERGY_STRAIN_DENSITY = 524,    ///< Strain energy density

    // ===== Other (3 types) =====
    SHELL_THICKNESS = 67,           ///< Shell thickness
    TRIAXIALITY = 520,              ///< Triaxiality
    NORMALIZED_MEAN_STRESS = 521    ///< Normalized mean stress
};

/**
 * @brief Output format types
 */
enum class OutputFormat {
    CSV,        ///< Comma-separated values
    JSON,       ///< JavaScript Object Notation
    HDF5,       ///< Hierarchical Data Format 5
    PARQUET,    ///< Apache Parquet (columnar)
    BINARY,     ///< Binary format (custom)
    XML         ///< Extensible Markup Language
};

/**
 * @brief Aggregation methods for query results
 */
enum class AggregationType {
    NONE,           ///< No aggregation - all data
    MAX,            ///< Maximum value only
    MIN,            ///< Minimum value only
    MEAN,           ///< Mean (average) value
    MEDIAN,         ///< Median value
    STDDEV,         ///< Standard deviation
    SUM,            ///< Sum of all values
    COUNT,          ///< Count of values
    RANGE,          ///< Range (max - min)
    HISTORY,        ///< Time history (time vs value)
    SPATIAL_MAX,    ///< Spatial maximum at each timestep
    CUSTOM          ///< User-defined aggregation
};

/**
 * @brief Unit system types
 */
enum class UnitSystem {
    SI,             ///< International System (m, kg, s)
    MM_TON_S,       ///< Millimeter, Ton, Second (LS-DYNA default)
    MM_KG_MS,       ///< Millimeter, Kilogram, Millisecond
    IN_LBF_S,       ///< Inch, Pound-force, Second
    CUSTOM          ///< User-defined units
};

/**
 * @brief Coordinate system types
 */
enum class CoordinateSystem {
    GLOBAL,         ///< Global coordinate system
    LOCAL,          ///< Element local coordinate system
    PART_LOCAL      ///< Part local coordinate system
};

/**
 * @brief Comparison operators for filtering
 */
enum class ComparisonOperator {
    EQUAL,              ///< ==
    NOT_EQUAL,          ///< !=
    LESS_THAN,          ///< <
    LESS_EQUAL,         ///< <=
    GREATER_THAN,       ///< >
    GREATER_EQUAL       ///< >=
};

// ============================================================
// Structure Definitions
// ============================================================

/**
 * @brief 3D Bounding box representation
 */
struct BoundingBox {
    std::array<double, 3> min;      ///< Minimum coordinates (x, y, z)
    std::array<double, 3> max;      ///< Maximum coordinates (x, y, z)

    /**
     * @brief Get center point of bounding box
     * @return Center coordinates
     */
    std::array<double, 3> center() const {
        return {
            (min[0] + max[0]) / 2.0,
            (min[1] + max[1]) / 2.0,
            (min[2] + max[2]) / 2.0
        };
    }

    /**
     * @brief Get size (dimensions) of bounding box
     * @return Size in each direction
     */
    std::array<double, 3> size() const {
        return {
            max[0] - min[0],
            max[1] - min[1],
            max[2] - min[2]
        };
    }

    /**
     * @brief Check if bounding box contains a point
     * @param point Point coordinates
     * @return true if point is inside bounding box
     */
    bool contains(const std::array<double, 3>& point) const {
        return point[0] >= min[0] && point[0] <= max[0] &&
               point[1] >= min[1] && point[1] <= max[1] &&
               point[2] >= min[2] && point[2] <= max[2];
    }
};

/**
 * @brief Section plane definition
 */
struct SectionPlane {
    std::array<double, 3> base_point;    ///< Base point on the plane
    std::array<double, 3> normal;        ///< Normal vector of the plane
    std::string orientation;             ///< Orientation ("X", "Y", "Z")
    std::string position_type;           ///< Position type ("center", "quarter_1", etc.)

    /**
     * @brief Calculate distance from point to plane
     * @param point Point coordinates
     * @return Signed distance (positive = in normal direction)
     */
    double distanceToPoint(const std::array<double, 3>& point) const {
        // d = (point - base_point) · normal
        double dx = point[0] - base_point[0];
        double dy = point[1] - base_point[1];
        double dz = point[2] - base_point[2];
        return dx * normal[0] + dy * normal[1] + dz * normal[2];
    }
};

/**
 * @brief Cylinder region definition (for spatial selection)
 */
struct Cylinder {
    std::array<double, 3> base_point;    ///< Center of base circle
    std::array<double, 3> axis;          ///< Cylinder axis direction
    double radius;                       ///< Cylinder radius
    double height;                       ///< Cylinder height
};

/**
 * @brief Sphere region definition (for spatial selection)
 */
struct Sphere {
    std::array<double, 3> center;        ///< Sphere center
    double radius;                       ///< Sphere radius

    /**
     * @brief Check if point is inside sphere
     * @param point Point coordinates
     * @return true if point is inside sphere
     */
    bool contains(const std::array<double, 3>& point) const {
        double dx = point[0] - center[0];
        double dy = point[1] - center[1];
        double dz = point[2] - center[2];
        double dist_sq = dx*dx + dy*dy + dz*dz;
        return dist_sq <= radius * radius;
    }
};

/**
 * @brief Property filter for part selection
 */
struct PropertyFilter {
    std::optional<double> min_volume;            ///< Minimum volume
    std::optional<double> max_volume;            ///< Maximum volume
    std::optional<double> min_mass;              ///< Minimum mass
    std::optional<double> max_mass;              ///< Maximum mass
    std::optional<std::array<double, 3>> centroid_near;  ///< Near centroid location
    std::optional<double> centroid_tolerance;    ///< Tolerance for centroid matching
};

/**
 * @brief Value range for filtering
 */
struct ValueRange {
    std::optional<double> min;  ///< Minimum value (inclusive)
    std::optional<double> max;  ///< Maximum value (inclusive)

    /**
     * @brief Check if value is within range
     * @param value Value to check
     * @return true if value is within range
     */
    bool contains(double value) const {
        if (min.has_value() && value < min.value()) return false;
        if (max.has_value() && value > max.value()) return false;
        return true;
    }
};

// ============================================================
// Type Aliases
// ============================================================

/// Callback function for progress reporting: (current, total, message) -> void
using ProgressCallback = std::function<void(int, int, const std::string&)>;

/// Custom aggregation function: (vector of values) -> aggregated value
using CustomAggregationFunc = std::function<double(const std::vector<double>&)>;

/// Custom filter function: (value) -> true if passes filter
using CustomFilterFunc = std::function<bool(double)>;

// ============================================================
// Constants
// ============================================================

/// Mapping from quantity type to LS-PrePost fringe component ID
const std::map<QuantityType, int> FRINGE_COMPONENT_IDS = {
    // Stress
    {QuantityType::STRESS_X, 1},
    {QuantityType::STRESS_Y, 2},
    {QuantityType::STRESS_Z, 3},
    {QuantityType::STRESS_XY, 4},
    {QuantityType::STRESS_YZ, 5},
    {QuantityType::STRESS_ZX, 6},
    {QuantityType::STRESS_VON_MISES, 9},
    {QuantityType::STRESS_PRESSURE, 8},
    {QuantityType::STRESS_MAX_SHEAR, 13},
    {QuantityType::STRESS_PRINCIPAL_1, 14},
    {QuantityType::STRESS_PRINCIPAL_2, 15},
    {QuantityType::STRESS_PRINCIPAL_3, 16},
    {QuantityType::STRESS_SIGNED_VON_MISES, 530},

    // Strain
    {QuantityType::STRAIN_X, 57},
    {QuantityType::STRAIN_Y, 58},
    {QuantityType::STRAIN_Z, 59},
    {QuantityType::STRAIN_XY, 60},
    {QuantityType::STRAIN_YZ, 61},
    {QuantityType::STRAIN_ZX, 62},
    {QuantityType::STRAIN_EFFECTIVE_PLASTIC, 7},
    {QuantityType::STRAIN_EFFECTIVE, 80},
    {QuantityType::STRAIN_PRINCIPAL_1, 77},
    {QuantityType::STRAIN_PRINCIPAL_2, 78},
    {QuantityType::STRAIN_PRINCIPAL_3, 79},
    {QuantityType::STRAIN_VOLUMETRIC, 529},

    // Displacement
    {QuantityType::DISPLACEMENT_X, 17},
    {QuantityType::DISPLACEMENT_Y, 18},
    {QuantityType::DISPLACEMENT_Z, 19},
    {QuantityType::DISPLACEMENT_MAGNITUDE, 20},

    // Velocity & Acceleration
    {QuantityType::VELOCITY_MAGNITUDE, 24},
    {QuantityType::ACCELERATION_MAGNITUDE, 23},

    // Energy
    {QuantityType::ENERGY_HOURGLASS_DENSITY, 43},
    {QuantityType::ENERGY_STRAIN_DENSITY, 524},

    // Other
    {QuantityType::SHELL_THICKNESS, 67},
    {QuantityType::TRIAXIALITY, 520},
    {QuantityType::NORMALIZED_MEAN_STRESS, 521}
};

/// Mapping from quantity name string to QuantityType enum
const std::map<std::string, QuantityType> QUANTITY_NAME_MAP = {
    // Stress
    {"x_stress", QuantityType::STRESS_X},
    {"y_stress", QuantityType::STRESS_Y},
    {"z_stress", QuantityType::STRESS_Z},
    {"xy_stress", QuantityType::STRESS_XY},
    {"yz_stress", QuantityType::STRESS_YZ},
    {"zx_stress", QuantityType::STRESS_ZX},
    {"von_mises", QuantityType::STRESS_VON_MISES},
    {"pressure", QuantityType::STRESS_PRESSURE},
    {"max_shear_stress", QuantityType::STRESS_MAX_SHEAR},
    {"principal_stress_1", QuantityType::STRESS_PRINCIPAL_1},
    {"principal_stress_2", QuantityType::STRESS_PRINCIPAL_2},
    {"principal_stress_3", QuantityType::STRESS_PRINCIPAL_3},
    {"signed_von_mises", QuantityType::STRESS_SIGNED_VON_MISES},

    // Strain
    {"x_strain", QuantityType::STRAIN_X},
    {"y_strain", QuantityType::STRAIN_Y},
    {"z_strain", QuantityType::STRAIN_Z},
    {"xy_strain", QuantityType::STRAIN_XY},
    {"yz_strain", QuantityType::STRAIN_YZ},
    {"zx_strain", QuantityType::STRAIN_ZX},
    {"effective_plastic_strain", QuantityType::STRAIN_EFFECTIVE_PLASTIC},
    {"plastic_strain", QuantityType::STRAIN_EFFECTIVE_PLASTIC},  // Alias
    {"effective_strain", QuantityType::STRAIN_EFFECTIVE},
    {"principal_strain_1", QuantityType::STRAIN_PRINCIPAL_1},
    {"principal_strain_2", QuantityType::STRAIN_PRINCIPAL_2},
    {"principal_strain_3", QuantityType::STRAIN_PRINCIPAL_3},
    {"volumetric_strain", QuantityType::STRAIN_VOLUMETRIC},

    // Displacement
    {"x_displacement", QuantityType::DISPLACEMENT_X},
    {"y_displacement", QuantityType::DISPLACEMENT_Y},
    {"z_displacement", QuantityType::DISPLACEMENT_Z},
    {"displacement_magnitude", QuantityType::DISPLACEMENT_MAGNITUDE},
    {"displacement", QuantityType::DISPLACEMENT_MAGNITUDE},  // Alias

    // Velocity & Acceleration
    {"velocity_magnitude", QuantityType::VELOCITY_MAGNITUDE},
    {"velocity", QuantityType::VELOCITY_MAGNITUDE},  // Alias
    {"acceleration_magnitude", QuantityType::ACCELERATION_MAGNITUDE},
    {"acceleration", QuantityType::ACCELERATION_MAGNITUDE},  // Alias

    // Energy
    {"hourglass_energy_density", QuantityType::ENERGY_HOURGLASS_DENSITY},
    {"strain_energy_density", QuantityType::ENERGY_STRAIN_DENSITY},
    {"energy_density", QuantityType::ENERGY_STRAIN_DENSITY},  // Alias

    // Other
    {"shell_thickness", QuantityType::SHELL_THICKNESS},
    {"thickness", QuantityType::SHELL_THICKNESS},  // Alias
    {"triaxiality", QuantityType::TRIAXIALITY},
    {"normalized_mean_stress", QuantityType::NORMALIZED_MEAN_STRESS}
};

// ============================================================
// Utility Functions
// ============================================================

/**
 * @brief Get fringe component ID from quantity type
 * @param type Quantity type enum
 * @return Fringe component ID for LS-PrePost
 */
inline int getFringeComponentId(QuantityType type) {
    auto it = FRINGE_COMPONENT_IDS.find(type);
    return (it != FRINGE_COMPONENT_IDS.end()) ? it->second : -1;
}

/**
 * @brief Get quantity type from name string
 * @param name Quantity name (e.g., "von_mises")
 * @return Optional quantity type (empty if not found)
 */
inline std::optional<QuantityType> getQuantityType(const std::string& name) {
    auto it = QUANTITY_NAME_MAP.find(name);
    if (it != QUANTITY_NAME_MAP.end()) {
        return it->second;
    }
    return std::nullopt;
}

/**
 * @brief Get quantity name from type enum
 * @param type Quantity type enum
 * @return Quantity name string
 */
inline std::string getQuantityName(QuantityType type) {
    for (const auto& pair : QUANTITY_NAME_MAP) {
        if (pair.second == type) {
            return pair.first;
        }
    }
    return "unknown";
}

} // namespace query
} // namespace kood3plot
