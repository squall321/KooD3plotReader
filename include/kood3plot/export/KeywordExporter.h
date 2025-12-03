#pragma once

/**
 * @file KeywordExporter.h
 * @brief Export d3plot data to LS-DYNA keyword format (.k files)
 */

#include "kood3plot/Types.hpp"
#include "kood3plot/data/Mesh.hpp"
#include "kood3plot/data/StateData.hpp"

#include <string>
#include <vector>
#include <fstream>

namespace kood3plot {
namespace export_utils {

/**
 * @brief Export format options for keyword files
 */
enum class KeywordFormat {
    NODE_DEFORMED,         ///< *NODE with deformed coordinates (original + displacement)
    NODE_DISPLACEMENT,     ///< *NODE with displacement as coordinates
    INITIAL_VELOCITY,      ///< *INITIAL_VELOCITY_NODE format
    INCLUDE_TRANSFORM,     ///< *INCLUDE_TRANSFORM format
    INITIAL_STRESS_SOLID,  ///< *INITIAL_STRESS_SOLID format (element stress)
    ELEMENT_STRESS_CSV     ///< CSV format with element stresses
};

/**
 * @brief Options for keyword export
 */
struct KeywordExportOptions {
    KeywordFormat format = KeywordFormat::NODE_DEFORMED;
    bool include_header = true;      ///< Include *KEYWORD at start
    bool include_end = true;         ///< Include *END at end
    int precision = 7;               ///< Decimal precision for coordinates
    bool use_scientific = false;     ///< Use scientific notation
    std::string title = "";          ///< Title for output file
    bool all_states = true;          ///< Export all states or specific ones
    std::vector<int> state_indices;  ///< Specific state indices to export (if all_states=false)
    int32_t IU = 1;                  ///< IU flag: 1=coordinates in state, 2=displacements
    int32_t NV3D = 7;                ///< Number of variables per solid element (for stress export)
    size_t num_solids = 0;           ///< Number of solid elements (for stress export)
};

/**
 * @brief Exporter for LS-DYNA keyword format
 */
class KeywordExporter {
public:
    /**
     * @brief Constructor
     * @param mesh Reference to mesh data (for original coordinates and node IDs)
     */
    explicit KeywordExporter(const data::Mesh& mesh);

    /**
     * @brief Export single state to keyword file
     * @param state State data to export
     * @param filename Output filename
     * @param options Export options
     * @return true if successful
     */
    bool exportState(const data::StateData& state,
                     const std::string& filename,
                     const KeywordExportOptions& options = KeywordExportOptions());

    /**
     * @brief Export all states to separate keyword files
     * @param states Vector of state data
     * @param base_filename Base filename (will append _001, _002, etc.)
     * @param options Export options
     * @return Number of files successfully exported
     */
    int exportAllStates(const std::vector<data::StateData>& states,
                        const std::string& base_filename,
                        const KeywordExportOptions& options = KeywordExportOptions());

    /**
     * @brief Export to a single combined file with time markers
     * @param states Vector of state data
     * @param filename Output filename
     * @param options Export options
     * @return true if successful
     */
    bool exportCombined(const std::vector<data::StateData>& states,
                        const std::string& filename,
                        const KeywordExportOptions& options = KeywordExportOptions());

    /**
     * @brief Get last error message
     */
    const std::string& getLastError() const { return last_error_; }

private:
    const data::Mesh& mesh_;
    std::string last_error_;

    /**
     * @brief Write keyword file header
     */
    void writeHeader(std::ofstream& ofs, const KeywordExportOptions& options,
                     double time = -1.0);

    /**
     * @brief Write *NODE section with deformed coordinates
     */
    void writeNodeDeformed(std::ofstream& ofs, const data::StateData& state,
                           const KeywordExportOptions& options);

    /**
     * @brief Write *NODE section with displacement values
     */
    void writeNodeDisplacement(std::ofstream& ofs, const data::StateData& state,
                               const KeywordExportOptions& options);

    /**
     * @brief Write *INITIAL_VELOCITY_NODE section
     */
    void writeInitialVelocity(std::ofstream& ofs, const data::StateData& state,
                              const KeywordExportOptions& options);

    /**
     * @brief Write *INITIAL_STRESS_SOLID section for solid element stress
     */
    void writeInitialStressSolid(std::ofstream& ofs, const data::StateData& state,
                                  const KeywordExportOptions& options);

    /**
     * @brief Write CSV format for element stress
     */
    void writeElementStressCSV(std::ofstream& ofs, const data::StateData& state,
                                const KeywordExportOptions& options);

    /**
     * @brief Format a number for keyword file output
     */
    std::string formatNumber(double value, int width, int precision, bool scientific) const;

    /**
     * @brief Get real node ID for internal index
     */
    int32_t getRealNodeId(size_t index) const;

    /**
     * @brief Get real solid element ID for internal index
     */
    int32_t getRealSolidId(size_t index) const;
};

} // namespace export_utils
} // namespace kood3plot
