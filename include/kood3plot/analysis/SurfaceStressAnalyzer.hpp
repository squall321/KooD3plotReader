/**
 * @file SurfaceStressAnalyzer.hpp
 * @brief Surface stress analysis for exterior element faces
 * @author KooD3plot Development Team
 * @date 2024-12-04
 *
 * Analyzes stress on exterior surfaces of solid elements:
 * - Extracts stress tensor from element data
 * - Calculates normal stress (perpendicular to surface)
 * - Calculates shear stress (tangential to surface)
 * - Computes Von Mises, principal stresses
 * - Provides time history statistics
 */

#pragma once

#include "kood3plot/analysis/SurfaceExtractor.hpp"
#include "kood3plot/analysis/VectorMath.hpp"
#include "kood3plot/analysis/AnalysisResult.hpp"
#include "kood3plot/D3plotReader.hpp"
#include "kood3plot/data/StateData.hpp"
#include <vector>
#include <functional>
#include <string>

namespace kood3plot {
namespace analysis {

/**
 * @brief Stress results for a single face at a single time step
 */
struct FaceStressResult {
    int32_t element_id;       ///< Element ID
    int32_t part_id;          ///< Part ID
    double time;              ///< Time value

    // Raw stress tensor components
    double sxx, syy, szz;     ///< Normal stress components
    double sxy, syz, szx;     ///< Shear stress components

    // Derived stress values
    double von_mises;         ///< Von Mises equivalent stress
    double normal_stress;     ///< Normal stress on face (σ_n)
    double shear_stress;      ///< Shear stress on face (τ)
    double max_principal;     ///< Maximum principal stress
    double min_principal;     ///< Minimum principal stress

    // Face information
    Vec3 face_normal;         ///< Face normal vector
    Vec3 face_centroid;       ///< Face centroid
};

/**
 * @brief Statistics for a group of faces at a single time step
 */
struct SurfaceStressStats {
    double time;              ///< Time value
    size_t num_faces;         ///< Number of faces analyzed

    // Von Mises statistics
    double von_mises_max;
    double von_mises_min;
    double von_mises_avg;
    int32_t von_mises_max_element;

    // Normal stress statistics
    double normal_stress_max;
    double normal_stress_min;
    double normal_stress_avg;
    int32_t normal_stress_max_element;

    // Shear stress statistics
    double shear_stress_max;
    double shear_stress_min;
    double shear_stress_avg;
    int32_t shear_stress_max_element;

    SurfaceStressStats()
        : time(0), num_faces(0),
          von_mises_max(0), von_mises_min(0), von_mises_avg(0), von_mises_max_element(0),
          normal_stress_max(0), normal_stress_min(0), normal_stress_avg(0), normal_stress_max_element(0),
          shear_stress_max(0), shear_stress_min(0), shear_stress_avg(0), shear_stress_max_element(0) {}
};

/**
 * @brief Time history of surface stress analysis
 */
struct SurfaceStressHistory {
    Vec3 reference_direction;         ///< Reference direction for filtering
    double angle_threshold_degrees;   ///< Angle threshold for filtering
    std::vector<int32_t> part_ids;    ///< Parts analyzed (empty = all parts)

    std::vector<SurfaceStressStats> time_history;  ///< Stats for each time step

    // Global extremes across all time steps
    double global_von_mises_max;
    double global_normal_stress_max;
    double global_shear_stress_max;
    double time_of_max_von_mises;
    double time_of_max_normal_stress;
    double time_of_max_shear_stress;

    SurfaceStressHistory()
        : angle_threshold_degrees(0),
          global_von_mises_max(0), global_normal_stress_max(0), global_shear_stress_max(0),
          time_of_max_von_mises(0), time_of_max_normal_stress(0), time_of_max_shear_stress(0) {}
};

/**
 * @brief Progress callback type
 * @param current Current step (0 to total-1)
 * @param total Total number of steps
 * @param message Status message
 */
using ProgressCallback = std::function<void(size_t current, size_t total, const std::string& message)>;

/**
 * @brief Surface stress analyzer for exterior element faces
 *
 * This class analyzes stress on the exterior surfaces of solid elements:
 * - Extracts stress tensors from solid element data
 * - Calculates normal and shear stresses on each face
 * - Provides time history with max/min/avg statistics
 * - Supports direction-based filtering
 *
 * Usage:
 * @code
 * D3plotReader reader("d3plot");
 * reader.open();
 *
 * SurfaceExtractor extractor(reader);
 * auto surfaces = extractor.extractExteriorSurfaces();
 *
 * // Filter for faces pointing in +Z direction
 * Vec3 up(0, 0, 1);
 * auto top_faces = SurfaceExtractor::filterByDirection(surfaces.faces, up, 45.0);
 *
 * SurfaceStressAnalyzer analyzer(reader);
 * auto history = analyzer.analyzeAllStates(top_faces);
 * @endcode
 */
class SurfaceStressAnalyzer {
public:
    /**
     * @brief Constructor
     * @param reader D3plotReader reference (must be opened)
     */
    explicit SurfaceStressAnalyzer(D3plotReader& reader);

    /**
     * @brief Destructor
     */
    ~SurfaceStressAnalyzer() = default;

    // ============================================================
    // Single State Analysis
    // ============================================================

    /**
     * @brief Analyze a single face for a given state
     * @param face Face to analyze
     * @param state State data
     * @return FaceStressResult with stress values
     */
    FaceStressResult analyzeFace(const Face& face, const data::StateData& state);

    /**
     * @brief Analyze multiple faces for a single state
     * @param faces Vector of faces to analyze
     * @param state State data
     * @return Vector of FaceStressResult
     */
    std::vector<FaceStressResult> analyzeFaces(
        const std::vector<Face>& faces,
        const data::StateData& state
    );

    /**
     * @brief Get statistics for a group of faces at a single state
     * @param faces Faces to analyze
     * @param state State data
     * @return SurfaceStressStats with statistics
     */
    SurfaceStressStats analyzeState(
        const std::vector<Face>& faces,
        const data::StateData& state
    );

    // ============================================================
    // Time History Analysis
    // ============================================================

    /**
     * @brief Analyze all states for a group of faces
     * @param faces Faces to analyze
     * @param reference_direction Reference direction for documentation
     * @param angle_threshold Angle threshold for documentation
     * @return SurfaceStressHistory with time series
     */
    SurfaceStressHistory analyzeAllStates(
        const std::vector<Face>& faces,
        const Vec3& reference_direction = Vec3(0, 0, 1),
        double angle_threshold = 90.0
    );

    /**
     * @brief Analyze all states with progress callback
     * @param faces Faces to analyze
     * @param reference_direction Reference direction
     * @param angle_threshold Angle threshold
     * @param callback Progress callback
     * @return SurfaceStressHistory with time series
     */
    SurfaceStressHistory analyzeAllStates(
        const std::vector<Face>& faces,
        const Vec3& reference_direction,
        double angle_threshold,
        ProgressCallback callback
    );

    // ============================================================
    // Stress Extraction
    // ============================================================

    /**
     * @brief Extract stress tensor for a solid element from state data
     * @param state State data
     * @param elem_internal_index Internal element index (0-based)
     * @return StressTensor object
     */
    StressTensor extractStressTensor(
        const data::StateData& state,
        size_t elem_internal_index
    );

    /**
     * @brief Get number of values per solid element (NV3D)
     * @return Number of values per solid element
     */
    int getNV3D() const { return nv3d_; }

    // ============================================================
    // Export Functions
    // ============================================================

    /**
     * @brief Export history to CSV
     * @param history Surface stress history
     * @param filepath Output file path
     * @return true if successful
     */
    static bool exportToCSV(
        const SurfaceStressHistory& history,
        const std::string& filepath
    );

    /**
     * @brief Convert to SurfaceAnalysisStats for JSON output
     * @param history Surface stress history
     * @return SurfaceAnalysisStats structure
     */
    static SurfaceAnalysisStats toAnalysisStats(
        const SurfaceStressHistory& history
    );

    /**
     * @brief Get last error message
     */
    const std::string& getLastError() const { return last_error_; }

private:
    D3plotReader& reader_;
    int nv3d_;                    ///< Number of values per solid element
    int num_solid_elements_;      ///< Total number of solid elements
    std::string last_error_;

    /**
     * @brief Initialize analyzer (read control data)
     */
    bool initialize();

    /**
     * @brief Build element ID to internal index mapping
     */
    void buildElementIndexMap();

    std::unordered_map<int32_t, size_t> elem_id_to_index_;
};

} // namespace analysis
} // namespace kood3plot
