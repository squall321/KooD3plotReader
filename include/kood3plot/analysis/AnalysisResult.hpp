/**
 * @file AnalysisResult.hpp
 * @brief Data structures for analysis results and JSON serialization
 * @author KooD3plot Development Team
 * @date 2024-12-04
 * @version 1.0.0
 *
 * Provides structures for storing analysis results and converting to/from JSON format.
 */

#pragma once

#include "VectorMath.hpp"
#include <string>
#include <vector>
#include <map>
#include <fstream>
#include <sstream>
#include <iomanip>
#include <ctime>
#include <stdexcept>
#include "kood3plot/analysis/HotspotClusterAnalyzer.hpp"
#include <cmath>

namespace kood3plot {
namespace analysis {

/// CSV 수치 표기 — **std::fixed 를 쓰면 안 된다**. 아래 jnum() 과 같은 정책
/// (유효숫자 기준)이고, examples/unified_analyzer.cpp 의 csvnum 과도 같다.
/// 절대 8자리 고정은 1e-8 미만을 "0.00000000" 으로 지워 **진짜 0 과 구분되지
/// 않게** 만들고, µs 급 시각 간격을 뭉개 같은 시각이 여러 줄 찍히게 한다
/// (np.diff(t)=0 → FFT/SRS 의 dt 가 깨진다). 게다가 한 번 건 std::fixed 는
/// 같은 스트림의 뒤 열 전부에 계속 걸린다.
inline std::ostream& csvnum(std::ostream& os) {
    return os << std::defaultfloat << std::setprecision(10);
}

// ============================================================
// Time Series Data Structures
// ============================================================

/**
 * @brief Single time point data for statistical quantities
 */
struct TimePointStats {
    double time = 0.0;          ///< Simulation time
    double max_value = 0.0;     ///< Maximum value
    double min_value = 0.0;     ///< Minimum value
    double avg_value = 0.0;     ///< Average value
    double rms_value = 0.0;     ///< RMS value (optional)
    int32_t max_element_id = 0; ///< Element ID with max value
    int32_t min_element_id = 0; ///< Element ID with min value
};

/**
 * @brief Time series statistics for a single part
 */
struct PartTimeSeriesStats {
    int32_t part_id = 0;             ///< Part ID
    std::string part_name;           ///< Part name (if available)
    std::string quantity;            ///< Quantity name (e.g., "von_mises", "eff_plastic_strain")
    std::string unit;                ///< Unit (e.g., "MPa", "mm/s^2")
    std::vector<TimePointStats> data; ///< Time series data

    /**
     * @brief Get number of time points
     */
    size_t size() const { return data.size(); }

    /**
     * @brief Check if empty
     */
    bool empty() const { return data.empty(); }

    /**
     * @brief Get global maximum across all time points
     */
    double globalMax() const {
        double max_val = -std::numeric_limits<double>::infinity();
        for (const auto& tp : data) {
            if (tp.max_value > max_val) max_val = tp.max_value;
        }
        return max_val;
    }

    /**
     * @brief Get global minimum across all time points
     */
    double globalMin() const {
        double min_val = std::numeric_limits<double>::infinity();
        for (const auto& tp : data) {
            if (tp.min_value < min_val) min_val = tp.min_value;
        }
        return min_val;
    }

    /**
     * @brief Get time of global maximum
     */
    double timeOfGlobalMax() const {
        double max_val = -std::numeric_limits<double>::infinity();
        double time_at_max = 0.0;
        for (const auto& tp : data) {
            if (tp.max_value > max_val) {
                max_val = tp.max_value;
                time_at_max = tp.time;
            }
        }
        return time_at_max;
    }
};

/**
 * @brief Single time point data for surface stress analysis
 */
struct SurfaceTimePointStats {
    double time = 0.0;

    // Normal stress statistics
    double normal_stress_max = 0.0;
    double normal_stress_min = 0.0;
    double normal_stress_avg = 0.0;
    int32_t normal_stress_max_element_id = 0;

    // Shear stress statistics
    double shear_stress_max = 0.0;
    double shear_stress_avg = 0.0;
    int32_t shear_stress_max_element_id = 0;

    // von Mises 등가응력 — 항복 판정용
    double von_mises_max = 0.0;
    double von_mises_min = 0.0;
    double von_mises_avg = 0.0;
    int32_t von_mises_max_element_id = 0;

    // 최대 주응력 σ1 (인장 파단)
    double max_principal_max = 0.0;
    double max_principal_min = 0.0;
    double max_principal_avg = 0.0;
    int32_t max_principal_max_element_id = 0;

    // 최소 주응력 σ3 (압축) — 최소값이 worst
    double min_principal_max = 0.0;
    double min_principal_min = 0.0;
    double min_principal_avg = 0.0;
    int32_t min_principal_min_element_id = 0;
};

/**
 * @brief Surface analysis statistics for a specific direction
 */
struct SurfaceAnalysisStats {
    std::string description;              ///< Human-readable description
    Vec3 reference_direction;             ///< Reference direction vector
    double angle_threshold_degrees = 0.0; ///< Angle threshold in degrees
    std::vector<int32_t> part_ids;        ///< Parts included in analysis
    int32_t num_faces = 0;                ///< Number of faces analyzed
    std::vector<SurfaceTimePointStats> data; ///< Time series data

    /**
     * @brief Get number of time points
     */
    size_t size() const { return data.size(); }

    /**
     * @brief Check if empty
     */
    bool empty() const { return data.empty(); }
};

// ============================================================
// Peak Element Tensor History (for stress ellipsoid)
// ============================================================

/**
 * @brief Full stress tensor time history for a single element
 *
 * Stores all 6 stress components across all time states for a peak element.
 * Used to reconstruct stress ellipsoid at any time point.
 */
struct ElementTensorHistory {
    int32_t element_id = 0;          ///< Element ID
    int32_t part_id = 0;             ///< Part ID this element belongs to
    std::string reason;              ///< "peak_von_mises", "peak_max_principal", "peak_min_principal"
    double peak_value = 0.0;         ///< The peak value that identified this element
    double peak_time = 0.0;          ///< Time of the peak

    std::vector<double> time;        ///< Time values
    std::vector<double> sxx;         ///< σxx history
    std::vector<double> syy;         ///< σyy history
    std::vector<double> szz;         ///< σzz history
    std::vector<double> sxy;         ///< σxy history
    std::vector<double> syz;         ///< σyz history
    std::vector<double> szx;         ///< σzx (σxz) history

    size_t size() const { return time.size(); }
    bool empty() const { return time.empty(); }
};

// ============================================================
// Metadata
// ============================================================

/**
 * @brief Analysis metadata
 */
struct AnalysisMetadata {
    std::string d3plot_path;             ///< Path to d3plot file
    std::string analysis_date;           ///< Analysis date/time (ISO 8601)
    std::string kood3plot_version;       ///< Library version (MAJOR.MINOR.PATCH)
    /// 빌드된 git 커밋. kood3plot_version 은 2026년 내내 "1.0.0" 이라 어느 판으로
    /// 돌렸는지 구분하지 못한다 — 산출물만 보고 알 수 있게 따로 싣는다.
    /// 빈 문자열이면 옛 산출물이라 기록이 없는 것이다(0 이나 가짜로 채우지 않는다).
    std::string tool_commit;
    std::string tool_built;              ///< 빌드 시각 (ISO 8601 UTC)
    int32_t num_states = 0;              ///< Number of states analyzed
    double start_time = 0.0;             ///< First state time
    double end_time = 0.0;               ///< Last state time
    std::vector<int32_t> analyzed_parts; ///< List of analyzed part IDs

    /// 설정을 그대로 실행하지 못한 사유(없으면 비어 있고 JSON 에도 키가 안 생긴다).
    /// 예: 이 수제 YAML 파서가 못 읽는 인라인 매핑 때문에 건너뛴 분석 잡.
    /// 로그를 못 보는 소비처가 '이 산출물은 설정대로 나온 것이 아니다' 를 알려면
    /// 산출물 자체에 실려 있어야 한다.
    std::vector<std::string> config_issues;

    /**
     * @brief Set analysis date to current time
     */
    void setCurrentDate() {
        std::time_t now = std::time(nullptr);
        char buf[64];
        std::strftime(buf, sizeof(buf), "%Y-%m-%dT%H:%M:%SZ", std::gmtime(&now));
        analysis_date = buf;
    }
};

// ============================================================
// Main Analysis Result
// ============================================================

/**
 * @brief Complete analysis result container
 *
 * Stores all analysis results and provides JSON serialization/deserialization.
 *
 * Usage:
 * @code
 * AnalysisResult result;
 * result.metadata.d3plot_path = "path/to/d3plot";
 * result.metadata.setCurrentDate();
 *
 * // Add stress history for part 1
 * PartTimeSeriesStats stress;
 * stress.part_id = 1;
 * stress.quantity = "von_mises";
 * // ... fill data ...
 * result.stress_history.push_back(stress);
 *
 * // Save to JSON
 * result.saveToFile("analysis_result.json");
 * @endcode
 */
struct AnalysisResult {
    AnalysisMetadata metadata;

    // Time series data
    std::vector<PartTimeSeriesStats> stress_history;             ///< Von Mises stress history
    std::vector<PartTimeSeriesStats> strain_history;             ///< Effective plastic strain history
    std::vector<PartTimeSeriesStats> acceleration_history;       ///< Average acceleration history
    std::vector<PartTimeSeriesStats> max_principal_history;      ///< Max principal stress (σ1) history
    std::vector<PartTimeSeriesStats> min_principal_history;      ///< Min principal stress (σ3) history
    /// von Mises 등가 변형률 (변형률 텐서가 있는 덱에서만)
    std::vector<PartTimeSeriesStats> vm_strain_history;
    std::vector<PartTimeSeriesStats> max_principal_strain_history; ///< Max principal strain (ε1) history
    std::vector<PartTimeSeriesStats> min_principal_strain_history; ///< Min principal strain (ε3) history

    // Peak element tensor histories (per-part, for stress ellipsoid)
    std::vector<ElementTensorHistory> peak_element_tensors;

    // Surface analysis
    std::vector<SurfaceAnalysisStats> surface_analysis;

    /// 파트별 핫스팟 군집 (config.hotspot_enabled 일 때만 채워진다)
    std::vector<PartHotspotResult> hotspot_clusters;

    // ============================================================
    // JSON Serialization
    // ============================================================

    /**
     * @brief Convert to JSON string
     * @param pretty Use pretty printing (indentation)
     * @return JSON string
     */
    std::string toJSON(bool pretty = true) const {
        std::ostringstream oss;
        std::string indent = pretty ? "  " : "";
        std::string nl = pretty ? "\n" : "";

        oss << "{" << nl;

        // Metadata
        oss << indent << "\"metadata\": {" << nl;
        oss << indent << indent << "\"d3plot_path\": \"" << escapeJSON(metadata.d3plot_path) << "\"," << nl;
        oss << indent << indent << "\"analysis_date\": \"" << metadata.analysis_date << "\"," << nl;
        oss << indent << indent << "\"kood3plot_version\": \"" << metadata.kood3plot_version << "\"," << nl;
        // 기록이 없으면 키를 만들지 않는다 — "unknown" 을 지어내지 않는다
        if (!metadata.tool_commit.empty())
            oss << indent << indent << "\"tool_commit\": \"" << escapeJSON(metadata.tool_commit) << "\"," << nl;
        if (!metadata.tool_built.empty())
            oss << indent << indent << "\"tool_built\": \"" << escapeJSON(metadata.tool_built) << "\"," << nl;
        oss << indent << indent << "\"num_states\": " << metadata.num_states << "," << nl;
        oss << indent << indent << "\"start_time\": " << jnum(metadata.start_time) << "," << nl;
        oss << indent << indent << "\"end_time\": " << jnum(metadata.end_time) << "," << nl;
        oss << indent << indent << "\"analyzed_parts\": " << arrayToJSON(metadata.analyzed_parts);
        // 사유가 없으면 키를 만들지 않는다 — 빈 배열도 '확인했다' 는 뜻이 되어버린다.
        if (!metadata.config_issues.empty()) {
            oss << "," << nl << indent << indent << "\"config_issues\": [";
            for (size_t i = 0; i < metadata.config_issues.size(); ++i) {
                if (i > 0) oss << ", ";
                oss << "\"" << escapeJSON(metadata.config_issues[i]) << "\"";
            }
            oss << "]";
        }
        oss << nl;
        oss << indent << "}," << nl;

        // Stress history
        oss << indent << "\"stress_history\": " << partStatsArrayToJSON(stress_history, pretty, indent) << "," << nl;

        // Strain history
        oss << indent << "\"strain_history\": " << partStatsArrayToJSON(strain_history, pretty, indent) << "," << nl;

        // Principal stress history
        oss << indent << "\"max_principal_history\": " << partStatsArrayToJSON(max_principal_history, pretty, indent) << "," << nl;
        oss << indent << "\"min_principal_history\": " << partStatsArrayToJSON(min_principal_history, pretty, indent) << "," << nl;

        // Principal strain history
        oss << indent << "\"vm_strain_history\": " << partStatsArrayToJSON(vm_strain_history, pretty, indent) << "," << nl;
        oss << indent << "\"max_principal_strain_history\": " << partStatsArrayToJSON(max_principal_strain_history, pretty, indent) << "," << nl;
        oss << indent << "\"min_principal_strain_history\": " << partStatsArrayToJSON(min_principal_strain_history, pretty, indent) << "," << nl;

        // Peak element tensor histories
        oss << indent << "\"peak_element_tensors\": " << tensorArrayToJSON(peak_element_tensors, pretty, indent) << "," << nl;

        // Acceleration history
        oss << indent << "\"acceleration_history\": " << partStatsArrayToJSON(acceleration_history, pretty, indent) << "," << nl;

        // Surface analysis
        oss << indent << "\"surface_analysis\": " << surfaceStatsArrayToJSON(surface_analysis, pretty, indent) << "," << nl;

        // 핫스팟 군집 (비활성이면 빈 배열)
        oss << indent << "\"hotspot_clusters\": " << hotspotArrayToJSON(hotspot_clusters, pretty, indent) << nl;

        oss << "}";

        return oss.str();
    }

    /**
     * @brief Save to JSON file
     * @param filepath Output file path
     * @return true if successful
     */
    bool saveToFile(const std::string& filepath) const {
        std::ofstream file(filepath);
        if (!file) {
            return false;
        }
        file << toJSON(true);
        file.close();
        return true;
    }

    /**
     * @brief Load from JSON file
     * @param filepath Input file path
     * @return AnalysisResult loaded from file
     * @throws std::runtime_error on parse error
     *
     * Note: This is a simplified parser. For production use, consider using
     * a proper JSON library like nlohmann/json.
     */
    static AnalysisResult loadFromFile(const std::string& filepath) {
        std::ifstream file(filepath);
        if (!file) {
            throw std::runtime_error("Cannot open file: " + filepath);
        }

        std::stringstream buffer;
        buffer << file.rdbuf();
        std::string json = buffer.str();

        return parseJSON(json);
    }

    // ============================================================
    // CSV Export (Convenience Methods)
    // ============================================================

    /**
     * @brief Export stress history to CSV
     * @param filepath Output file path
     * @return true if successful
     */
    bool exportStressToCSV(const std::string& filepath) const {
        return exportPartStatsToCSV(stress_history, filepath);
    }

    /**
     * @brief Export strain history to CSV
     * @param filepath Output file path
     * @return true if successful
     */
    bool exportStrainToCSV(const std::string& filepath) const {
        return exportPartStatsToCSV(strain_history, filepath);
    }

    /**
     * @brief Export surface analysis to CSV
     * @param filepath Output file path
     * @return true if successful
     */
    bool exportSurfaceToCSV(const std::string& filepath) const {
        if (surface_analysis.empty()) return false;

        std::ofstream file(filepath);
        if (!file) return false;

        // Header
        file << "Time";
        for (size_t i = 0; i < surface_analysis.size(); ++i) {
            file << ",Surface" << i << "_NormalMax";
            file << ",Surface" << i << "_NormalAvg";
            file << ",Surface" << i << "_ShearMax";
            file << ",Surface" << i << "_ShearAvg";
        }
        file << "\n";

        // Find maximum number of time points
        size_t max_points = 0;
        for (const auto& surf : surface_analysis) {
            if (surf.data.size() > max_points) max_points = surf.data.size();
        }

        // Data rows
        for (size_t t = 0; t < max_points; ++t) {
            bool first = true;
            for (const auto& surf : surface_analysis) {
                if (t < surf.data.size()) {
                    if (first) {
                        file << csvnum << surf.data[t].time;
                        first = false;
                    }
                    file << "," << surf.data[t].normal_stress_max;
                    file << "," << surf.data[t].normal_stress_avg;
                    file << "," << surf.data[t].shear_stress_max;
                    file << "," << surf.data[t].shear_stress_avg;
                } else {
                    file << ",,,,";
                }
            }
            file << "\n";
        }

        return true;
    }

protected:
    // ============================================================
    // JSON Helper Functions
    // ============================================================
    // protected 인 이유 — ExtendedAnalysisResult::toExtendedJSON 이 같은 파일에
    // 같은 규칙(jnum·escapeJSON)으로 써야 한다. 예전에는 쓸 수가 없어 확장
    // 섹션만 std::fixed 와 날 문자열로 나갔고, NaN 하나가 20MB 짜리 결과 전체를
    // 파이썬이 못 읽는 파일로 만들었다.

    static std::string escapeJSON(const std::string& str) {
        std::ostringstream oss;
        for (char c : str) {
            switch (c) {
                case '"': oss << "\\\""; break;
                case '\\': oss << "\\\\"; break;
                case '\n': oss << "\\n"; break;
                case '\r': oss << "\\r"; break;
                case '\t': oss << "\\t"; break;
                default: oss << c;
            }
        }
        return oss.str();
    }

    template<typename T>
    static std::string arrayToJSON(const std::vector<T>& arr) {
        std::ostringstream oss;
        oss << "[";
        for (size_t i = 0; i < arr.size(); ++i) {
            if (i > 0) oss << ", ";
            oss << arr[i];
        }
        oss << "]";
        return oss.str();
    }

    static std::string vec3ToJSON(const Vec3& v) {
        // 성분마다 jnum — std::fixed(6) 은 (1) 같은 방향벡터를 다른 블록과 다른
        // 표기로 내보내고 (2) 비유한 성분을 JSON 이 아닌 nan 토큰으로 써서
        // 파일 전체를 파이썬이 못 읽는 파일로 만든다 (jnum 주석 참조).
        std::ostringstream oss;
        oss << "[" << jnum(v.x) << ", " << jnum(v.y) << ", " << jnum(v.z) << "]";
        return oss.str();
    }

    static std::string timePointToJSON(const TimePointStats& tp, const std::string& indent) {
        std::ostringstream oss;
        // 수치는 jnum — 소수 8자리 고정은 작은 변형률·촘촘한 시각을 뭉갠다 (jnum 주석 참조)
        oss << "{";
        oss << "\"time\": " << jnum(tp.time) << ", ";
        oss << "\"max\": " << jnum(tp.max_value) << ", ";
        oss << "\"min\": " << jnum(tp.min_value) << ", ";
        oss << "\"avg\": " << jnum(tp.avg_value) << ", ";
        oss << "\"max_element_id\": " << tp.max_element_id << ", ";
        oss << "\"min_element_id\": " << tp.min_element_id;
        oss << "}";
        return oss.str();
    }

    static std::string partStatsToJSON(const PartTimeSeriesStats& stats, bool pretty, const std::string& base_indent) {
        std::ostringstream oss;
        std::string nl = pretty ? "\n" : "";
        std::string ind = base_indent;
        std::string ind2 = ind + (pretty ? "  " : "");
        std::string ind3 = ind2 + (pretty ? "  " : "");

        oss << "{" << nl;
        oss << ind2 << "\"part_id\": " << stats.part_id << "," << nl;
        oss << ind2 << "\"part_name\": \"" << escapeJSON(stats.part_name) << "\"," << nl;
        oss << ind2 << "\"quantity\": \"" << stats.quantity << "\"," << nl;
        oss << ind2 << "\"unit\": \"" << stats.unit << "\"," << nl;
        oss << ind2 << "\"num_points\": " << stats.data.size() << "," << nl;

        // 전 상태가 미계측(markUnmeasuredParts 가 넣은 NaN)이면 globalMax()/
        // globalMin() 이 ±inf 를 돌려준다. jnum 은 그걸 null 로 쓰지만, **스칼라**
        // null 은 소비처가 막지 못한다 (배열 원소 null 만 _finite() 로 거른다).
        // 그래서 '값 없음' 은 키를 만들지 않고 사유만 남긴다. time_of_max 도
        // 0.0 초기값이 그대로 나가 진짜 t=0 과 섞이므로 함께 뺀다.
        if (!stats.data.empty()) {
            const double gmax = stats.globalMax();
            const double gmin = stats.globalMin();
            if (std::isfinite(gmax) || std::isfinite(gmin)) {
                oss << ind2 << "\"global_max\": " << jnum(gmax) << "," << nl;
                oss << ind2 << "\"global_min\": " << jnum(gmin) << "," << nl;
                oss << ind2 << "\"time_of_max\": " << jnum(stats.timeOfGlobalMax()) << "," << nl;
            } else {
                oss << ind2 << "\"global_unmeasured\": true," << nl;
                oss << ind2 << "\"global_unmeasured_reason\": "
                    << "\"전 상태에서 이 물리량이 계측되지 않았습니다\"," << nl;
            }
        }

        oss << ind2 << "\"data\": [";

        // 전 상태를 쓴다. 예전엔 "읽기 좋게" 20점 초과 시 앞 10 + 뒤 10 + 문자열만
        // 써서, 보고서 이력 그래프가 사건 구간을 통째로 잃었다 (8f9ea8c → 2026-09 수정).
        const size_t n = stats.data.size();
        for (size_t i = 0; i < n; ++i) {
            if (i > 0) oss << ", ";
            if (pretty) oss << nl << ind3;
            oss << timePointToJSON(stats.data[i], ind3);
        }

        if (pretty && !stats.data.empty()) oss << nl << ind2;
        oss << "]" << nl;
        oss << ind << "}";

        return oss.str();
    }

    static std::string partStatsArrayToJSON(const std::vector<PartTimeSeriesStats>& arr, bool pretty, const std::string& indent) {
        std::ostringstream oss;
        std::string nl = pretty ? "\n" : "";

        oss << "[";
        for (size_t i = 0; i < arr.size(); ++i) {
            if (i > 0) oss << ",";
            if (pretty) oss << nl << indent << "  ";
            oss << partStatsToJSON(arr[i], pretty, indent + "  ");
        }
        if (pretty && !arr.empty()) oss << nl << indent;
        oss << "]";

        return oss.str();
    }

    static std::string surfaceTimePointToJSON(const SurfaceTimePointStats& tp) {
        std::ostringstream oss;
        oss << "{";
        oss << "\"time\": " << jnum(tp.time) << ", ";
        oss << "\"normal_stress\": {";
        oss << "\"max\": " << jnum(tp.normal_stress_max) << ", ";
        oss << "\"min\": " << jnum(tp.normal_stress_min) << ", ";
        oss << "\"avg\": " << jnum(tp.normal_stress_avg) << ", ";
        oss << "\"max_element_id\": " << tp.normal_stress_max_element_id << "}, ";
        oss << "\"shear_stress\": {";
        oss << "\"max\": " << jnum(tp.shear_stress_max) << ", ";
        oss << "\"avg\": " << jnum(tp.shear_stress_avg) << ", ";
        oss << "\"max_element_id\": " << tp.shear_stress_max_element_id << "}, ";
        oss << "\"von_mises\": {";
        oss << "\"max\": " << jnum(tp.von_mises_max) << ", ";
        oss << "\"min\": " << jnum(tp.von_mises_min) << ", ";
        oss << "\"avg\": " << jnum(tp.von_mises_avg) << ", ";
        oss << "\"max_element_id\": " << tp.von_mises_max_element_id << "}, ";
        oss << "\"max_principal\": {";
        oss << "\"max\": " << jnum(tp.max_principal_max) << ", ";
        oss << "\"min\": " << jnum(tp.max_principal_min) << ", ";
        oss << "\"avg\": " << jnum(tp.max_principal_avg) << ", ";
        oss << "\"max_element_id\": " << tp.max_principal_max_element_id << "}, ";
        oss << "\"min_principal\": {";
        oss << "\"max\": " << jnum(tp.min_principal_max) << ", ";
        oss << "\"min\": " << jnum(tp.min_principal_min) << ", ";
        oss << "\"avg\": " << jnum(tp.min_principal_avg) << ", ";
        oss << "\"min_element_id\": " << tp.min_principal_min_element_id << "}";
        oss << "}";
        return oss.str();
    }

    static std::string surfaceStatsToJSON(const SurfaceAnalysisStats& stats, bool pretty, const std::string& base_indent) {
        std::ostringstream oss;
        std::string nl = pretty ? "\n" : "";
        std::string ind = base_indent;
        std::string ind2 = ind + (pretty ? "  " : "");
        std::string ind3 = ind2 + (pretty ? "  " : "");

        oss << "{" << nl;
        oss << ind2 << "\"description\": \"" << escapeJSON(stats.description) << "\"," << nl;
        oss << ind2 << "\"reference_direction\": " << vec3ToJSON(stats.reference_direction) << "," << nl;
        oss << ind2 << "\"angle_threshold_degrees\": " << stats.angle_threshold_degrees << "," << nl;
        oss << ind2 << "\"part_ids\": " << arrayToJSON(stats.part_ids) << "," << nl;
        oss << ind2 << "\"num_faces\": " << stats.num_faces << "," << nl;
        oss << ind2 << "\"data\": [";

        // 전 상태를 쓴다 (partStatsToJSON 과 같은 이유)
        const size_t n = stats.data.size();
        for (size_t i = 0; i < n; ++i) {
            if (i > 0) oss << ", ";
            if (pretty) oss << nl << ind3;
            oss << surfaceTimePointToJSON(stats.data[i]);
        }

        if (pretty && !stats.data.empty()) oss << nl << ind2;
        oss << "]" << nl;
        oss << ind << "}";

        return oss.str();
    }

    static std::string surfaceStatsArrayToJSON(const std::vector<SurfaceAnalysisStats>& arr, bool pretty, const std::string& indent) {
        std::ostringstream oss;
        std::string nl = pretty ? "\n" : "";

        oss << "[";
        for (size_t i = 0; i < arr.size(); ++i) {
            if (i > 0) oss << ",";
            if (pretty) oss << nl << indent << "  ";
            oss << surfaceStatsToJSON(arr[i], pretty, indent + "  ");
        }
        if (pretty && !arr.empty()) oss << nl << indent;
        oss << "]";

        return oss.str();
    }

    static std::string doubleArrayToJSON(const std::vector<double>& arr) {
        std::ostringstream oss;
        oss << "[";
        for (size_t i = 0; i < arr.size(); ++i) {
            if (i > 0) oss << ",";
            oss << jnum(arr[i]);
        }
        oss << "]";
        return oss.str();
    }

    static std::string tensorToJSON(const ElementTensorHistory& t, bool pretty, const std::string& base_indent) {
        std::ostringstream oss;
        std::string nl = pretty ? "\n" : "";
        std::string ind = base_indent;
        std::string ind2 = ind + (pretty ? "  " : "");

        oss << "{" << nl;
        oss << ind2 << "\"element_id\": " << t.element_id << "," << nl;
        oss << ind2 << "\"part_id\": " << t.part_id << "," << nl;
        oss << ind2 << "\"reason\": \"" << t.reason << "\"," << nl;
        oss << ind2 << "\"peak_value\": " << jnum(t.peak_value) << "," << nl;
        oss << ind2 << "\"peak_time\": " << jnum(t.peak_time) << "," << nl;
        oss << ind2 << "\"num_points\": " << t.time.size() << "," << nl;
        oss << ind2 << "\"time\": " << doubleArrayToJSON(t.time) << "," << nl;
        oss << ind2 << "\"sxx\": " << doubleArrayToJSON(t.sxx) << "," << nl;
        oss << ind2 << "\"syy\": " << doubleArrayToJSON(t.syy) << "," << nl;
        oss << ind2 << "\"szz\": " << doubleArrayToJSON(t.szz) << "," << nl;
        oss << ind2 << "\"sxy\": " << doubleArrayToJSON(t.sxy) << "," << nl;
        oss << ind2 << "\"syz\": " << doubleArrayToJSON(t.syz) << "," << nl;
        oss << ind2 << "\"szx\": " << doubleArrayToJSON(t.szx) << nl;
        oss << ind << "}";
        return oss.str();
    }

    /// 유한하지 않은 값은 JSON 을 깨뜨린다(NaN/Infinity 는 JSON 리터럴이 아님).
    /// 0 으로 치환하지 않고 null 로 내보내 "값 없음"과 "0"을 구분한다.
    static std::string jnum(double v) {
        if (!std::isfinite(v)) return "null";
        std::ostringstream oss;
        // 🔴 `std::fixed << setprecision(8)` 을 쓰면 안 된다. 소수점 이하 8자리에서
        //    잘리므로 ε_p(1e-6) 는 유효숫자 3자리만 남고, 소성일 밀도(1e-9)는
        //    "0.00000000" 이 되어 **진짜 0 과 구분되지 않는다** — 값이 조용히 사라진다.
        //    유효숫자 기준(defaultfloat)으로 쓰면 필요할 때 지수 표기가 되고,
        //    지수 표기는 JSON 에서 유효한 숫자다.
        oss << std::setprecision(10) << v;
        return oss.str();
    }

    static std::string hotspotClusterToJSON(const HotspotCluster& c, bool pretty, const std::string& base_indent) {
        std::ostringstream oss;
        std::string nl = pretty ? "\n" : "";
        std::string ind = base_indent;
        std::string ind2 = base_indent + (pretty ? "  " : "");

        oss << "{" << nl;
        oss << ind2 << "\"rank\": " << c.rank << "," << nl;
        oss << ind2 << "\"element_count\": " << c.element_count << "," << nl;
        oss << ind2 << "\"center\": [" << jnum(c.center[0]) << ", "
                                        << jnum(c.center[1]) << ", "
                                        << jnum(c.center[2]) << "]," << nl;
        oss << ind2 << "\"radius_enclosing\": " << jnum(c.radius_enclosing) << "," << nl;
        oss << ind2 << "\"radius_rms\": " << jnum(c.radius_rms) << "," << nl;
        // 셸: area 는 항상, volume(면적×두께)은 두께가 있을 때만. 없는 값을 0 으로 내면
        //     '부피 0' 으로 오독된다.
        if (c.has_area) oss << ind2 << "\"area\": " << jnum(c.area) << "," << nl;
        if (c.volume_valid) oss << ind2 << "\"volume\": " << jnum(c.volume) << "," << nl;
        oss << ind2 << "\"stress_mean\": " << jnum(c.stress_mean) << "," << nl;
        oss << ind2 << "\"stress_max\": " << jnum(c.stress_max) << "," << nl;
        oss << ind2 << "\"strain_available\": " << (c.strain_available ? "true" : "false") << "," << nl;
        if (c.strain_available) {
            oss << ind2 << "\"strain_mean\": " << jnum(c.strain_mean) << "," << nl;
            oss << ind2 << "\"strain_max\": " << jnum(c.strain_max) << "," << nl;
        }
        // 소성일 w_p = ∫σ_vm dε_p. 적분 못 한 덱에서는 키 자체를 안 낸다 —
        // 0 으로 내면 '에너지 0' 과 '계산 못 함' 이 구분되지 않는다.
        // max_t(mean_e) — 계산하지 않았으면 키를 만들지 않는다
        if (c.mean_timemax_available) {
            oss << ind2 << "\"mean_timemax\": " << jnum(c.mean_timemax) << "," << nl;
            oss << ind2 << "\"mean_timemax_time\": " << jnum(c.mean_timemax_time) << "," << nl;
        }
        oss << ind2 << "\"energy_available\": " << (c.energy_available ? "true" : "false") << "," << nl;
        if (c.energy_available) {
            oss << ind2 << "\"energy_mean\": " << jnum(c.energy_mean) << "," << nl;
            oss << ind2 << "\"energy_max\": " << jnum(c.energy_max) << "," << nl;
            // energy_total 은 부피 가중일 때만 에너지 단위다 (면적 가중 셸은 생략)
            if (c.energy_total != 0.0 || c.volume_valid)
                oss << ind2 << "\"energy_total\": " << jnum(c.energy_total) << "," << nl;
        }
        oss << ind2 << "\"peak_element_id\": " << c.peak_element_id << "," << nl;
        if (c.peak_layer >= 0) oss << ind2 << "\"peak_layer\": " << c.peak_layer << "," << nl;
        oss << ind2 << "\"peak_time\": " << jnum(c.peak_time) << nl;
        oss << ind << "}";
        return oss.str();
    }

    static std::string hotspotPartToJSON(const PartHotspotResult& r, bool pretty, const std::string& base_indent) {
        std::ostringstream oss;
        std::string nl = pretty ? "\n" : "";
        std::string ind = base_indent;
        std::string ind2 = base_indent + (pretty ? "  " : "");
        std::string ind3 = ind2 + (pretty ? "  " : "");

        oss << "{" << nl;
        oss << ind2 << "\"part_id\": " << r.part_id << "," << nl;
        oss << ind2 << "\"part_name\": \"" << escapeJSON(r.part_name) << "\"," << nl;
        oss << ind2 << "\"criterion\": \"" << escapeJSON(r.criterion) << "\"," << nl;
        // direction: "max"|"min" — stress_max/threshold_value 가 어느 쪽 극값인지.
        // 구버전 결과(필드 없음)는 전부 von_mises 였으므로 소비자는 없으면 "max" 로 본다.
        oss << ind2 << "\"direction\": \"" << escapeJSON(r.direction.empty() ? "max" : r.direction) << "\"," << nl;
        oss << ind2 << "\"strain_measure\": \"" << escapeJSON(r.strain_measure.empty() ? "equivalent" : r.strain_measure) << "\"," << nl;
        oss << ind2 << "\"element_type\": \"" << escapeJSON(r.element_type.empty() ? "solid" : r.element_type) << "\"," << nl;
        oss << ind2 << "\"weight_measure\": \"" << escapeJSON(r.weight_measure.empty() ? "volume" : r.weight_measure) << "\"," << nl;
        if (!r.layer_scheme.empty())
            oss << ind2 << "\"layer_scheme\": \"" << escapeJSON(r.layer_scheme) << "\"," << nl;
        if (r.bbox_valid) {
            oss << ind2 << "\"bbox_min\": [" << jnum(r.bbox_min[0]) << ", " << jnum(r.bbox_min[1]) << ", " << jnum(r.bbox_min[2]) << "]," << nl;
            oss << ind2 << "\"bbox_max\": [" << jnum(r.bbox_max[0]) << ", " << jnum(r.bbox_max[1]) << ", " << jnum(r.bbox_max[2]) << "]," << nl;
        }
        oss << ind2 << "\"top_percent\": " << jnum(r.top_percent) << "," << nl;
        oss << ind2 << "\"threshold_value\": " << jnum(r.threshold_value) << "," << nl;
        if (r.value_extreme_valid)
            oss << ind2 << "\"value_extreme\": " << jnum(r.value_extreme) << "," << nl;
        oss << ind2 << "\"cut_ties_unselected\": " << r.cut_ties_unselected << "," << nl;
        oss << ind2 << "\"uniform\": " << (r.uniform ? "true" : "false") << "," << nl;
        oss << ind2 << "\"element_size_ref\": " << jnum(r.element_size_ref) << "," << nl;
        oss << ind2 << "\"distance_threshold\": " << jnum(r.distance_threshold) << "," << nl;
        oss << ind2 << "\"element_count_total\": " << r.element_count_total << "," << nl;
        oss << ind2 << "\"element_count_selected\": " << r.element_count_selected << "," << nl;
        oss << ind2 << "\"element_count_clustered\": " << r.element_count_clustered << "," << nl;
        oss << ind2 << "\"strain_available\": " << (r.strain_available ? "true" : "false") << "," << nl;
        // 소성역 절대량 — top_percent 와 무관한 파트 전체 값.
        // 클러스터의 volume·energy_total 은 상위 백분위로 자른 뒤의 값이라 설정을
        // 바꾸면 따라 변한다. 판정에는 이쪽을 쓴다.
        oss << ind2 << "\"vol_total\": " << jnum(r.vol_total) << "," << nl;
        oss << ind2 << "\"plastic_zone_available\": "
            << (r.plastic_zone_available ? "true" : "false") << "," << nl;
        if (r.plastic_zone_available) {
            oss << ind2 << "\"yield_eps_threshold\": " << jnum(r.yield_eps_threshold) << "," << nl;
            oss << ind2 << "\"n_yield\": " << r.n_yield << "," << nl;
            oss << ind2 << "\"vol_yield\": " << jnum(r.vol_yield) << "," << nl;
            oss << ind2 << "\"sum_eps_vol\": " << jnum(r.sum_eps_vol) << "," << nl;
            oss << ind2 << "\"max_eps\": " << jnum(r.max_eps) << "," << nl;
        }
        oss << ind2 << "\"plastic_work_available\": "
            << (r.plastic_work_available ? "true" : "false") << "," << nl;
        if (r.plastic_work_available) {
            oss << ind2 << "\"plastic_work_total\": " << jnum(r.plastic_work_total) << "," << nl;
        }
        oss << ind2 << "\"clusters\": [";
        for (size_t i = 0; i < r.clusters.size(); ++i) {
            if (i > 0) oss << ",";
            if (pretty) oss << nl << ind3;
            oss << hotspotClusterToJSON(r.clusters[i], pretty, ind3);
        }
        if (pretty && !r.clusters.empty()) oss << nl << ind2;
        oss << "]" << nl;
        oss << ind << "}";
        return oss.str();
    }

    static std::string hotspotArrayToJSON(const std::vector<PartHotspotResult>& arr, bool pretty, const std::string& indent) {
        std::ostringstream oss;
        std::string nl = pretty ? "\n" : "";
        oss << "[";
        for (size_t i = 0; i < arr.size(); ++i) {
            if (i > 0) oss << ",";
            if (pretty) oss << nl << indent << "  ";
            oss << hotspotPartToJSON(arr[i], pretty, indent + "  ");
        }
        if (pretty && !arr.empty()) oss << nl << indent;
        oss << "]";
        return oss.str();
    }

    static std::string tensorArrayToJSON(const std::vector<ElementTensorHistory>& arr, bool pretty, const std::string& indent) {
        std::ostringstream oss;
        std::string nl = pretty ? "\n" : "";
        oss << "[";
        for (size_t i = 0; i < arr.size(); ++i) {
            if (i > 0) oss << ",";
            if (pretty) oss << nl << indent << "  ";
            oss << tensorToJSON(arr[i], pretty, indent + "  ");
        }
        if (pretty && !arr.empty()) oss << nl << indent;
        oss << "]";
        return oss.str();
    }

    // CSV export helper
    bool exportPartStatsToCSV(const std::vector<PartTimeSeriesStats>& stats, const std::string& filepath) const {
        if (stats.empty()) return false;

        std::ofstream file(filepath);
        if (!file) return false;

        // Header
        file << "Time";
        for (const auto& part : stats) {
            file << ",Part" << part.part_id << "_Max";
            file << ",Part" << part.part_id << "_Min";
            file << ",Part" << part.part_id << "_Avg";
        }
        file << "\n";

        // Find maximum number of time points
        size_t max_points = 0;
        for (const auto& part : stats) {
            if (part.data.size() > max_points) max_points = part.data.size();
        }

        // Data rows
        for (size_t t = 0; t < max_points; ++t) {
            bool first = true;
            for (const auto& part : stats) {
                if (t < part.data.size()) {
                    if (first) {
                        file << csvnum << part.data[t].time;
                        first = false;
                    }
                    file << "," << part.data[t].max_value;
                    file << "," << part.data[t].min_value;
                    file << "," << part.data[t].avg_value;
                } else {
                    file << ",,,";
                }
            }
            file << "\n";
        }

        return true;
    }

    // Simplified JSON parser (placeholder - use proper library for production)
    static AnalysisResult parseJSON(const std::string& json) {
        // This is a placeholder. For production use, implement a proper parser
        // or use nlohmann/json library.
        AnalysisResult result;
        // TODO: Implement JSON parsing
        (void)json;  // Suppress unused warning
        return result;
    }
};

} // namespace analysis
} // namespace kood3plot
