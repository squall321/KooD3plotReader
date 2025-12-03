#pragma once

#include "kood3plot/D3plotReader.hpp"
#include "kood3plot/data/Mesh.hpp"
#include "kood3plot/data/StateData.hpp"
#include "kood3plot/data/ControlData.hpp"
#include <vector>
#include <string>
#include <unordered_map>
#include <functional>
#include <memory>

namespace kood3plot {
namespace analysis {

/**
 * @brief Stress/Strain component type for extraction
 */
enum class StressComponent {
    // Stress components (words 0-5)
    XX = 0,          ///< Normal stress in X direction
    YY = 1,          ///< Normal stress in Y direction
    ZZ = 2,          ///< Normal stress in Z direction
    XY = 3,          ///< Shear stress XY
    YZ = 4,          ///< Shear stress YZ
    ZX = 5,          ///< Shear stress ZX

    // Derived stress quantities
    VON_MISES = 6,   ///< Von Mises equivalent stress
    PRESSURE = 7,    ///< Hydrostatic pressure (negative mean stress)

    // Effective plastic strain (word 6)
    EFF_PLASTIC = 8, ///< Effective plastic strain

    // Strain components (words 7-12, only when ISTRN != 0)
    STRAIN_XX = 9,   ///< Normal strain in X direction
    STRAIN_YY = 10,  ///< Normal strain in Y direction
    STRAIN_ZZ = 11,  ///< Normal strain in Z direction
    STRAIN_XY = 12,  ///< Shear strain XY
    STRAIN_YZ = 13,  ///< Shear strain YZ
    STRAIN_ZX = 14   ///< Shear strain ZX
};

/**
 * @brief Statistics for a single part at a single time step
 */
struct PartStats {
    int32_t part_id;         ///< Part ID
    double time;             ///< Time value

    // Stress statistics
    double stress_max;       ///< Maximum stress
    double stress_min;       ///< Minimum stress
    double stress_avg;       ///< Average stress
    double stress_rms;       ///< RMS stress

    // Element info
    int32_t max_element_id;  ///< Element ID with max stress
    int32_t min_element_id;  ///< Element ID with min stress
    size_t num_elements;     ///< Number of elements in part

    PartStats() : part_id(0), time(0), stress_max(0), stress_min(0),
                  stress_avg(0), stress_rms(0), max_element_id(0),
                  min_element_id(0), num_elements(0) {}
};

/**
 * @brief Time history data for a part
 */
struct PartTimeHistory {
    int32_t part_id;                    ///< Part ID
    std::string part_name;              ///< Part name (if available)
    std::vector<double> times;          ///< Time values
    std::vector<double> max_values;     ///< Max stress at each time
    std::vector<double> min_values;     ///< Min stress at each time
    std::vector<double> avg_values;     ///< Average stress at each time
    std::vector<int32_t> max_elem_ids;  ///< Element ID of max at each time
};

/**
 * @brief Part information structure
 */
struct PartInfo {
    int32_t part_id;                    ///< Part ID
    std::string name;                   ///< Part name
    ElementType element_type;           ///< Primary element type
    size_t num_elements;                ///< Number of elements
    std::vector<size_t> element_indices; ///< Internal element indices
};

/**
 * @brief Part-based time series analysis
 *
 * Provides analysis capabilities for stress/strain data per part:
 * - Max/Min/Avg stress time history per part
 * - Von Mises stress calculation
 * - CSV export for time series data
 *
 * Usage:
 * @code
 * D3plotReader reader("d3plot");
 * reader.open();
 *
 * PartAnalyzer analyzer(reader);
 *
 * // Analyze all parts
 * auto histories = analyzer.analyze_all_parts(StressComponent::VON_MISES);
 *
 * // Export to CSV
 * analyzer.export_to_csv(histories, "part_stress.csv");
 * @endcode
 */
class PartAnalyzer {
public:
    /**
     * @brief Constructor
     * @param reader D3plotReader reference (must be opened)
     */
    explicit PartAnalyzer(D3plotReader& reader);

    /**
     * @brief Destructor
     */
    ~PartAnalyzer();

    /**
     * @brief Initialize analyzer (reads mesh and builds part map)
     * @return true if successful
     */
    bool initialize();

    /**
     * @brief Get list of all parts
     * @return Vector of PartInfo structures
     */
    const std::vector<PartInfo>& get_parts() const { return parts_; }

    /**
     * @brief Get number of parts
     */
    size_t get_num_parts() const { return parts_.size(); }

    /**
     * @brief Get part info by ID
     * @param part_id Part ID
     * @return Pointer to PartInfo or nullptr if not found
     */
    const PartInfo* get_part_by_id(int32_t part_id) const;

    /**
     * @brief Analyze single state for a specific part
     * @param part_id Part ID to analyze
     * @param state State data
     * @param component Stress component to analyze
     * @return PartStats structure with statistics
     */
    PartStats analyze_state(int32_t part_id, const data::StateData& state,
                            StressComponent component = StressComponent::VON_MISES);

    /**
     * @brief Analyze all states for a specific part
     * @param part_id Part ID to analyze
     * @param component Stress component to analyze
     * @return PartTimeHistory with time series data
     */
    PartTimeHistory analyze_part(int32_t part_id,
                                  StressComponent component = StressComponent::VON_MISES);

    /**
     * @brief Analyze all parts for all states
     * @param component Stress component to analyze
     * @return Vector of PartTimeHistory for each part
     */
    std::vector<PartTimeHistory> analyze_all_parts(
        StressComponent component = StressComponent::VON_MISES);

    /**
     * @brief Analyze with progress callback
     * @param component Stress component to analyze
     * @param callback Progress callback (current, total, message)
     * @return Vector of PartTimeHistory for each part
     */
    std::vector<PartTimeHistory> analyze_all_parts_with_progress(
        StressComponent component,
        std::function<void(size_t, size_t, const std::string&)> callback);

    /**
     * @brief Export time history to CSV
     * @param history Single part history
     * @param filepath Output CSV file path
     * @return true if successful
     */
    bool export_to_csv(const PartTimeHistory& history, const std::string& filepath);

    /**
     * @brief Export all histories to CSV
     * @param histories Vector of part histories
     * @param filepath Output CSV file path
     * @return true if successful
     */
    bool export_to_csv(const std::vector<PartTimeHistory>& histories,
                       const std::string& filepath);

    /**
     * @brief Export summary statistics to CSV
     * @param histories Vector of part histories
     * @param filepath Output CSV file path
     * @return true if successful
     */
    bool export_summary_csv(const std::vector<PartTimeHistory>& histories,
                            const std::string& filepath);

    /**
     * @brief Get last error message
     */
    const std::string& get_last_error() const { return last_error_; }

    /**
     * @brief Calculate Von Mises stress from components
     * @param sxx Normal stress XX
     * @param syy Normal stress YY
     * @param szz Normal stress ZZ
     * @param sxy Shear stress XY
     * @param syz Shear stress YZ
     * @param szx Shear stress ZX
     * @return Von Mises equivalent stress
     */
    static double calculate_von_mises(double sxx, double syy, double szz,
                                       double sxy, double syz, double szx);

    /**
     * @brief Calculate hydrostatic pressure from stress components
     */
    static double calculate_pressure(double sxx, double syy, double szz);

private:
    D3plotReader& reader_;
    data::Mesh mesh_;
    data::ControlData control_data_;

    std::vector<PartInfo> parts_;
    std::unordered_map<int32_t, size_t> part_id_to_index_;

    bool initialized_;
    std::string last_error_;

    /**
     * @brief Build part information from mesh
     */
    void build_part_map();

    /**
     * @brief Extract stress value for an element
     * @param solid_data Raw solid element data
     * @param elem_index Element internal index
     * @param component Stress component to extract
     * @return Stress value
     */
    double extract_stress(const std::vector<double>& solid_data,
                          size_t elem_index, StressComponent component);

    /**
     * @brief Get number of values per solid element (NV3D)
     */
    int get_nv3d() const;
};

/**
 * @brief Convert StressComponent enum to string name
 */
inline std::string stress_component_name(StressComponent comp) {
    switch (comp) {
        case StressComponent::XX: return "Stress_XX";
        case StressComponent::YY: return "Stress_YY";
        case StressComponent::ZZ: return "Stress_ZZ";
        case StressComponent::XY: return "Stress_XY";
        case StressComponent::YZ: return "Stress_YZ";
        case StressComponent::ZX: return "Stress_ZX";
        case StressComponent::VON_MISES: return "Von_Mises";
        case StressComponent::PRESSURE: return "Pressure";
        case StressComponent::EFF_PLASTIC: return "Eff_Plastic_Strain";
        case StressComponent::STRAIN_XX: return "Strain_XX";
        case StressComponent::STRAIN_YY: return "Strain_YY";
        case StressComponent::STRAIN_ZZ: return "Strain_ZZ";
        case StressComponent::STRAIN_XY: return "Strain_XY";
        case StressComponent::STRAIN_YZ: return "Strain_YZ";
        case StressComponent::STRAIN_ZX: return "Strain_ZX";
        default: return "Unknown";
    }
}

} // namespace analysis
} // namespace kood3plot
