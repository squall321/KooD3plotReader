#pragma once

#include "kood3plot/Types.hpp"
#include "kood3plot/data/ControlData.hpp"
#include "kood3plot/data/StateData.hpp"
#include "kood3plot/core/BinaryReader.hpp"
#include <functional>
#include <memory>
#include <vector>

namespace kood3plot {
namespace parsers {

/**
 * @brief Parser for state data section
 *
 * Supports two parsing modes:
 * - Fast mode (default): Uses bulk array reads for performance
 * - Legacy mode: Uses individual word reads (slower but more debuggable)
 */
class StateDataParser {
public:
    /**
     * @brief Constructor
     * @param reader Binary file reader
     * @param control_data Control data structure
     * @param is_family_file If true, this is a family file (d3plot01, etc.)
     *                       which contains only state data starting at offset 0
     */
    StateDataParser(std::shared_ptr<core::BinaryReader> reader,
                    const data::ControlData& control_data,
                    bool is_family_file = false);

    /**
     * @brief Parse all state data from file (uses fast mode by default)
     * @return Vector of state data for each time step
     */
    std::vector<data::StateData> parse_all();

    /**
     * @brief 상태를 하나씩 visit 에 넘긴다 — 파일 하나의 상태를 다 올리지 않는다.
     * @param want  있으면 want(i) 가 false 인 상태는 풀지 않고 건너뛴다(시간 워드만 본다)
     * @param visit (이 파일 안 순번, 상태)
     * @return 이 파일의 상태 수(건너뛴 것 포함). 멈춤 규칙 · stop_reason() 은 parse_all() 과 같다.
     */
    size_t for_each(const std::function<bool(size_t)>& want,
                    const std::function<void(size_t, data::StateData&&)>& visit);

    /**
     * @brief Parse single state at given offset (uses fast mode by default)
     * @param offset Word offset to state data
     * @return Parsed state data
     */
    data::StateData parse_state(size_t offset);

    /**
     * @brief Enable or disable fast bulk read mode
     * @param enable true for fast mode (default), false for legacy mode
     */
    void set_fast_mode(bool enable) { use_fast_mode_ = enable; }

    /**
     * @brief Check if fast mode is enabled
     */
    bool is_fast_mode() const { return use_fast_mode_; }

    // ============ Legacy API (individual word reads) ============

    /**
     * @brief Parse time values only (lightweight scan without loading full data)
     * @return Vector of time values for each state
     * @note Much faster than parse_all() for just counting states
     */
    std::vector<double> parse_time_values_only();

    /**
     * @brief Parse all states using legacy individual word reads
     * @return Vector of state data
     * @note Slower than parse_all() but useful for debugging
     */
    std::vector<data::StateData> parse_all_legacy();

    /**
     * @brief Parse single state using legacy individual word reads
     * @param offset Word offset to state data
     * @return Parsed state data
     */
    data::StateData parse_state_legacy(size_t offset);

    /// parse_all() · parse_time_values_only() 가 멈춘 까닭 — 파일이 잘렸는지
    /// 판정하는 데 쓴다(판정은 파일 위치를 아는 D3plotReader 가 한다).
    enum class StopReason {
        EOF_MARKER,   ///< 다음 상태 자리에 -999999.0 — 정상 끝
        OUT_OF_DATA   ///< 남은 워드가 상태 하나에 못 미침 — 패딩이거나 덜 써진 상태
    };
    StopReason stop_reason() const { return stop_reason_; }
    /// 마지막으로 읽은 상태 다음부터 파일 끝까지 남은 워드 수
    size_t trailing_words() const { return trailing_words_; }

private:
    std::shared_ptr<core::BinaryReader> reader_;
    const data::ControlData& control_data_;
    bool is_family_file_;  ///< True if this is a family file (starts at offset 0)
    bool use_fast_mode_ = true;  ///< Use bulk read mode by default
    StopReason stop_reason_ = StopReason::OUT_OF_DATA;
    size_t trailing_words_ = 0;

    /**
     * @brief Find offset to first state data
     */
    size_t find_state_offset();

    // ============ Fast mode parsing (bulk reads) ============

    /**
     * @brief Parse state using bulk array reads (fast)
     */
    data::StateData parse_state_fast(size_t offset);

    /**
     * @brief Parse global variables using bulk read
     */
    void parse_global_vars_fast(data::StateData& state, size_t& offset);

    /**
     * @brief Parse nodal data using bulk read
     */
    void parse_nodal_data_fast(data::StateData& state, size_t& offset);

    /**
     * @brief Parse element data using bulk read
     */
    void parse_element_data_fast(data::StateData& state, size_t& offset);

    // ============ Legacy mode parsing (individual reads) ============

    /**
     * @brief Parse global variables (legacy individual reads)
     */
    void parse_global_vars_legacy(data::StateData& state, size_t& offset);

    /**
     * @brief Parse nodal data (legacy individual reads)
     */
    void parse_nodal_data_legacy(data::StateData& state, size_t& offset);

    /**
     * @brief Parse element data (legacy individual reads)
     */
    void parse_element_data_legacy(data::StateData& state, size_t& offset);

    /**
     * @brief Parse element deletion data
     */
    void parse_deletion_data(data::StateData& state, size_t& offset);
};

} // namespace parsers
} // namespace kood3plot
