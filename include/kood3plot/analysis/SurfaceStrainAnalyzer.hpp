/**
 * @file SurfaceStrainAnalyzer.hpp
 * @brief Direction-based surface strain analysis
 * @author KooD3plot Development Team
 * @date 2025-12-04
 *
 * Provides direction-based surface strain analysis:
 * - Extracts faces with normals aligned to a reference direction
 * - Computes normal strain and shear strain on those faces
 *
 * Similar to SurfaceStressAnalyzer but for strain data.
 */

#pragma once

#include "kood3plot/D3plotReader.hpp"
#include "kood3plot/analysis/AnalysisTypes.hpp"
#include "kood3plot/analysis/SurfaceExtractor.hpp"
#include "kood3plot/analysis/VectorMath.hpp"
#include <vector>
#include <string>

namespace kood3plot {
namespace analysis {

/**
 * @brief Surface strain analyzer
 *
 * Analyzes strain on surfaces defined by direction and angle threshold.
 */
class SurfaceStrainAnalyzer {
public:
    /**
     * @brief Constructor
     * @param reader D3plotReader (must have geometry already read)
     */
    explicit SurfaceStrainAnalyzer(D3plotReader& reader);

    /**
     * @brief Destructor
     */
    ~SurfaceStrainAnalyzer() = default;

    /**
     * @brief Add a surface specification
     * @param description Surface description
     * @param direction Reference direction
     * @param angle_degrees Maximum angle from reference direction
     * @param part_ids Parts to include (empty = all)
     */
    void addSurface(const std::string& description,
                    const Vec3& direction,
                    double angle_degrees = 45.0,
                    const std::vector<int32_t>& part_ids = {});

    /**
     * @brief Initialize analyzer (extract surfaces)
     * @return true if successful
     */
    bool initialize();

    /**
     * @brief Process a single state
     * @param state State data from d3plot
     */
    void processState(const data::StateData& state);

    /**
     * @brief Get results after processing all states
     * @return Vector of surface strain statistics
     */
    std::vector<SurfaceStrainStats> getResults();

    /**
     * @brief Get last error message
     */
    const std::string& getLastError() const { return last_error_; }

    /**
     * @brief Check if analyzer was successfully initialized
     */
    bool isInitialized() const { return initialized_; }

    /**
     * @brief Reset analyzer state
     */
    void reset();

private:
    D3plotReader& reader_;
    std::string last_error_;
    bool initialized_ = false;

    // Surface specifications
    struct SurfaceSpec {
        std::string description;
        Vec3 direction;
        double angle_degrees;
        std::vector<int32_t> part_ids;
    };
    std::vector<SurfaceSpec> surface_specs_;

    // Extracted surfaces (Face objects from SurfaceExtractor)
    std::vector<std::vector<Face>> extracted_surfaces_;

    // Results storage
    std::vector<SurfaceStrainStats> results_;

    // Internal methods
    void extractSurfaces();
    void processStrainForSurface(size_t surface_idx,
                                  const data::StateData& state,
                                  SurfaceStrainTimePoint& point);
};

} // namespace analysis
} // namespace kood3plot
