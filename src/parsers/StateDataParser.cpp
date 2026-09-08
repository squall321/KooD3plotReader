#include <cstdlib>
#include "kood3plot/parsers/StateDataParser.hpp"
#include <stdexcept>
#include <cmath>
#include <iostream>

namespace kood3plot {
namespace parsers {

StateDataParser::StateDataParser(std::shared_ptr<core::BinaryReader> reader,
                                 const data::ControlData& control_data,
                                 bool is_family_file)
    : reader_(reader)
    , control_data_(control_data)
    , is_family_file_(is_family_file) {
}

// ============================================================================
// Main API - delegates to fast or legacy based on mode
// ============================================================================

std::vector<data::StateData> StateDataParser::parse_all() {
    if (!reader_ || !reader_->is_open()) {
        throw std::runtime_error("BinaryReader not initialized or file not open");
    }

    std::vector<data::StateData> states;

    // Find offset to first state
    size_t offset = find_state_offset();

    // Calculate state data size per state
    // State size = 1 (TIME) + NGLBV (globals) + NND (nodal) + ENN (element) + DELNN (deletion)
    size_t state_size = 1 + control_data_.NGLBV + control_data_.NND + control_data_.ENN + control_data_.DELNN;

    // Get file size in words for boundary checking
    size_t file_size_words = reader_->get_file_size_words();

    // Read states until we hit EOF or invalid time
    bool done = false;
    while (!done) {
        // Check if we have enough data for at least the time word
        if (offset >= file_size_words) {
            done = true;
            continue;
        }

        // Check if we have enough data for a full state
        if (offset + state_size > file_size_words) {
            done = true;
            continue;
        }

        try {
            // Try to read time word
            double time = reader_->read_double(offset);

            // Check for EOF marker (-999999.0)
            if (std::abs(time + 999999.0) < 1e-6) {
                done = true;
            } else {
                // Parse this state (fast or legacy based on mode)
                data::StateData state = parse_state(offset);
                states.push_back(std::move(state));

                // Move to next state
                offset += state_size;
            }
        } catch (const std::exception& e) {
            done = true;
        }
    }

    return states;
}

data::StateData StateDataParser::parse_state(size_t offset) {
    if (use_fast_mode_) {
        return parse_state_fast(offset);
    } else {
        return parse_state_legacy(offset);
    }
}

// ============================================================================
// Legacy API - parse_all_legacy uses parse_state_legacy
// ============================================================================

std::vector<data::StateData> StateDataParser::parse_all_legacy() {
    bool saved_mode = use_fast_mode_;
    use_fast_mode_ = false;
    auto result = parse_all();
    use_fast_mode_ = saved_mode;
    return result;
}

std::vector<double> StateDataParser::parse_time_values_only() {
    if (!reader_ || !reader_->is_open()) {
        throw std::runtime_error("BinaryReader not initialized or file not open");
    }

    std::vector<double> time_values;

    // Find offset to first state
    size_t offset = find_state_offset();

    // Calculate state data size per state
    size_t state_size = 1 + control_data_.NGLBV + control_data_.NND + control_data_.ENN + control_data_.DELNN;

    // Get file size in words for boundary checking
    size_t file_size_words = reader_->get_file_size_words();

    // Scan states - only read time values, skip the rest
    bool done = false;
    while (!done) {
        if (offset >= file_size_words) {
            done = true;
            continue;
        }

        if (offset + state_size > file_size_words) {
            done = true;
            continue;
        }

        try {
            double time = reader_->read_double(offset);

            // Check for EOF marker (-999999.0)
            if (std::abs(time + 999999.0) < 1e-6) {
                done = true;
            } else {
                time_values.push_back(time);
                // Skip to next state (don't read the actual data)
                offset += state_size;
            }
        } catch (const std::exception&) {
            done = true;
        }
    }

    return time_values;
}

data::StateData StateDataParser::parse_state_legacy(size_t offset) {
    if (!reader_ || !reader_->is_open()) {
        throw std::runtime_error("BinaryReader not initialized or file not open");
    }

    data::StateData state;

    // Read TIME word (ls-dyna_database.txt line 1812)
    state.time = reader_->read_double(offset++);

    // Parse using legacy individual reads
    parse_global_vars_legacy(state, offset);
    parse_nodal_data_legacy(state, offset);
    parse_element_data_legacy(state, offset);

    // 삭제(침식) 테이블 — 내용을 읽은 뒤 오프셋을 진행시킨다
    if (control_data_.DELNN > 0) {
        parse_deletion_data(state, offset);
        offset += control_data_.DELNN;
    }

    return state;
}

// ============================================================================
// Fast mode implementation - bulk array reads
// ============================================================================

data::StateData StateDataParser::parse_state_fast(size_t offset) {
    if (!reader_ || !reader_->is_open()) {
        throw std::runtime_error("BinaryReader not initialized or file not open");
    }

    data::StateData state;

    // Read TIME word
    state.time = reader_->read_double(offset++);

    // Parse using bulk reads
    parse_global_vars_fast(state, offset);
    parse_nodal_data_fast(state, offset);
    parse_element_data_fast(state, offset);

    // 삭제(침식) 테이블 — 내용을 읽은 뒤 오프셋을 진행시킨다
    if (control_data_.DELNN > 0) {
        parse_deletion_data(state, offset);
        offset += control_data_.DELNN;
    }

    return state;
}

void StateDataParser::parse_global_vars_fast(data::StateData& state, size_t& offset) {
    int nglbv = control_data_.NGLBV;
    if (nglbv <= 0) {
        return;
    }

    // Bulk read all global variables at once
    state.global_vars = reader_->read_double_array(offset, nglbv);
    offset += nglbv;
}

void StateDataParser::parse_nodal_data_fast(data::StateData& state, size_t& offset) {
    int numnp = control_data_.NUMNP;
    int ndim = control_data_.NDIM;
    int it = control_data_.IT;
    int iu = control_data_.IU;
    int iv = control_data_.IV;
    int ia = control_data_.IA;

    // NDIM=4,5,7 means special formats, actual spatial dimensions is 3
    int effective_ndim = ndim;
    if (ndim == 4 || ndim == 5 || ndim == 7) {
        effective_ndim = 3;
    }

    if (numnp <= 0) {
        return;
    }

    // IT is decimal-encoded: tens=mass-scaling, units=temp mode.
    int temp_code = it % 10;
    int mass_flag = (it / 10) > 0 ? 1 : 0;
    int n_temp_fields = 0;
    if (temp_code == 1) n_temp_fields = 1;
    else if (temp_code == 2) n_temp_fields = 3;
    else if (temp_code == 3) n_temp_fields = 3;

    // CORRECT BINARY ORDER (verified empirically against d3plot01 layout):
    //   1. temperatures (if IT mod 10 > 0)
    //   2. displacements (IU)
    //   3. velocities    (IV)
    //   4. accelerations (IA)
    //   5. mass scaling  (if IT/10 == 1)   ← AFTER kinematics, NOT before
    //
    // Earlier the parser read "(IT+N)" combined fields up front, putting
    // mass scaling words BEFORE displacement. That offsets every read by
    // NUMNP words, mangling displacements / velocities / accelerations and
    // — once the cumulative offset exceeds the per-state stride — also
    // every subsequent state's time word.

    if (n_temp_fields > 0) {
        size_t count = static_cast<size_t>(numnp) * n_temp_fields;
        state.node_temperatures = reader_->read_double_array(offset, count);
        offset += count;
    }

    if (iu > 0) {
        size_t count = static_cast<size_t>(numnp) * effective_ndim;
        state.node_displacements = reader_->read_double_array(offset, count);
        offset += count;
    }

    if (iv > 0) {
        size_t count = static_cast<size_t>(numnp) * effective_ndim;
        state.node_velocities = reader_->read_double_array(offset, count);
        offset += count;
    }

    if (ia > 0) {
        size_t count = static_cast<size_t>(numnp) * effective_ndim;
        state.node_accelerations = reader_->read_double_array(offset, count);
        offset += count;
    }

    if (mass_flag > 0) {
        // Mass scaling values (NUMNP words). Stored — typically unused by
        // visualisation, but advances the offset to keep state alignment.
        offset += static_cast<size_t>(numnp);
    }
}

void StateDataParser::parse_element_data_fast(data::StateData& state, size_t& offset) {
    int nel8 = std::abs(control_data_.NEL8);
    int nv3d = control_data_.NV3D;

    int nelt = control_data_.NELT;
    int nv3dt = control_data_.NV3DT;

    int nel2 = control_data_.NEL2;
    int nv1d = control_data_.NV1D;

    int nel4 = control_data_.NEL4;
    int nv2d = control_data_.NV2D;

    // Read solid element data - bulk read
    if (nel8 > 0 && nv3d > 0) {
        size_t count = static_cast<size_t>(nel8) * nv3d;
        state.solid_data = reader_->read_double_array(offset, count);
        offset += count;
    }

    // Read thick shell element data - bulk read
    if (nelt > 0 && nv3dt > 0) {
        size_t count = static_cast<size_t>(nelt) * nv3dt;
        state.thick_shell_data = reader_->read_double_array(offset, count);
        offset += count;
    }

    // Read beam element data - bulk read
    if (nel2 > 0 && nv1d > 0) {
        size_t count = static_cast<size_t>(nel2) * nv1d;
        state.beam_data = reader_->read_double_array(offset, count);
        offset += count;
    }

    // Read shell element data - bulk read
    if (nel4 > 0 && nv2d > 0) {
        size_t count = static_cast<size_t>(nel4) * nv2d;
        state.shell_data = reader_->read_double_array(offset, count);
        offset += count;
    }
}

// ============================================================================
// Legacy mode implementation - individual word reads (original code)
// ============================================================================

void StateDataParser::parse_global_vars_legacy(data::StateData& state, size_t& offset) {
    // ls-dyna_database.txt lines 1814-1828
    // GLOBAL: NGLBV words

    int nglbv = control_data_.NGLBV;
    if (nglbv <= 0) {
        return;
    }

    state.global_vars.resize(nglbv);
    for (int i = 0; i < nglbv; ++i) {
        state.global_vars[i] = reader_->read_double(offset++);
    }
}

void StateDataParser::parse_nodal_data_legacy(data::StateData& state, size_t& offset) {
    // ls-dyna_database.txt lines 1830-1840
    // NODEDATA: NND words
    // =((IT+N)+NDIM*(IU+IV+IA))*NUMNP

    int numnp = control_data_.NUMNP;
    int ndim = control_data_.NDIM;
    int it = control_data_.IT;
    int iu = control_data_.IU;
    int iv = control_data_.IV;
    int ia = control_data_.IA;

    // ls-dyna_database.txt lines 230-231:
    // "If 4 then element connectivities are unpacked in the DYNA3D database and NDIM is reset to 3."
    // NDIM=4,5,7 means special formats, actual spatial dimensions is 3
    int effective_ndim = ndim;
    if (ndim == 4 || ndim == 5 || ndim == 7) {
        effective_ndim = 3;
    }

    if (numnp <= 0) {
        return;
    }

    // IT is decimal-encoded: tens=mass scaling, units=temp mode.
    int temp_code = it % 10;
    int mass_flag = (it / 10) > 0 ? 1 : 0;
    int n_temp_fields = 0;
    if (temp_code == 1) n_temp_fields = 1;
    else if (temp_code == 2) n_temp_fields = 3;
    else if (temp_code == 3) n_temp_fields = 3;

    // Binary order (legacy slow path): temperatures → disp → vel → accel
    // → mass scaling. Same as the fast path.

    if (n_temp_fields > 0) {
        state.node_temperatures.resize(numnp * n_temp_fields);
        for (int i = 0; i < numnp * n_temp_fields; ++i) {
            state.node_temperatures[i] = reader_->read_double(offset++);
        }
    }

    // Read displacements if IU > 0
    if (iu > 0) {
        state.node_displacements.resize(numnp * effective_ndim);
        for (int i = 0; i < numnp * effective_ndim; ++i) {
            state.node_displacements[i] = reader_->read_double(offset++);
        }
    }

    // Read velocities if IV > 0
    if (iv > 0) {
        state.node_velocities.resize(numnp * effective_ndim);
        for (int i = 0; i < numnp * effective_ndim; ++i) {
            state.node_velocities[i] = reader_->read_double(offset++);
        }
    }

    // Read accelerations if IA > 0
    if (ia > 0) {
        state.node_accelerations.resize(numnp * effective_ndim);
        for (int i = 0; i < numnp * effective_ndim; ++i) {
            state.node_accelerations[i] = reader_->read_double(offset++);
        }
    }

    if (mass_flag > 0) {
        // Mass scaling values come AFTER the kinematics block. Skip
        // (offset advance only — value not used by visualisation).
        offset += static_cast<size_t>(numnp);
    }
}

void StateDataParser::parse_element_data_legacy(data::StateData& state, size_t& offset) {
    // ls-dyna_database.txt lines 1867-2009
    // ELEMDATA: ENN words
    // =NEL8*NV3D + NELT*NV3DT + NEL2*NV1D + NEL4*NV2D + NMSPH*NUM_SPH_VARS
    // Order: Solids → Thick Shells → Beams → Shells

    int nel8 = std::abs(control_data_.NEL8);
    int nv3d = control_data_.NV3D;

    int nelt = control_data_.NELT;
    int nv3dt = control_data_.NV3DT;

    int nel2 = control_data_.NEL2;
    int nv1d = control_data_.NV1D;

    int nel4 = control_data_.NEL4;
    int nv2d = control_data_.NV2D;

    // Read solid element data (ls-dyna_database.txt lines 1887-1919)
    // 7 + NEIPH values per element (or 7 + NEIPH + 6 if ISTRN=1)
    if (nel8 > 0 && nv3d > 0) {
        state.solid_data.resize(nel8 * nv3d);
        for (int i = 0; i < nel8 * nv3d; ++i) {
            state.solid_data[i] = reader_->read_double(offset++);
        }
    }

    // Read thick shell element data (ls-dyna_database.txt lines 1922-1973)
    if (nelt > 0 && nv3dt > 0) {
        state.thick_shell_data.resize(nelt * nv3dt);
        for (int i = 0; i < nelt * nv3dt; ++i) {
            state.thick_shell_data[i] = reader_->read_double(offset++);
        }
    }

    // Read beam element data (ls-dyna_database.txt lines 1975-1998)
    // NV1D = 6 values per element (or 6 + 5*BEAMIP if integration points)
    if (nel2 > 0 && nv1d > 0) {
        state.beam_data.resize(nel2 * nv1d);
        for (int i = 0; i < nel2 * nv1d; ++i) {
            state.beam_data[i] = reader_->read_double(offset++);
        }
    }

    // Read shell element data (ls-dyna_database.txt lines 2001-2009)
    // NV2D = MAXINT*(6*IOSHL(1) + IOSHL(2) + NEIPS) + 8*IOSHL(3) + 4*IOSHL(4) + 12*ISTRN
    if (nel4 > 0 && nv2d > 0) {
        state.shell_data.resize(nel4 * nv2d);
        for (int i = 0; i < nel4 * nv2d; ++i) {
            state.shell_data[i] = reader_->read_double(offset++);
        }
    }
}

// ============================================================================
// Utility functions
// ============================================================================

size_t StateDataParser::find_state_offset() {
    // Family files (d3plot01, d3plot02, etc.) contain ONLY state data
    // starting at offset 0 - no control data or geometry
    if (is_family_file_) {
        return 0;
    }

    // For base file (d3plot): State data starts after geometry section
    // Geometry section starts at word: 64 + EXTRA
    // (ls-dyna_database.txt lines 626-663)

    size_t offset = 64 + control_data_.EXTRA;

    // Skip node coordinates: effective_ndim * NUMNP
    // ls-dyna_database.txt lines 227-234: NDIM=4,5,7 are reset to 3
    int ndim = control_data_.NDIM;
    int effective_ndim = (ndim == 4 || ndim == 5 || ndim == 7) ? 3 : ndim;
    offset += effective_ndim * control_data_.NUMNP;

    // Skip solid elements: 9 * |NEL8|
    int nel8 = control_data_.NEL8;
    int num_solids = std::abs(nel8);
    offset += 9 * num_solids;

    // If NEL8 < 0, skip extra nodes for 10-node solids: 2 * |NEL8|
    if (nel8 < 0) {
        offset += 2 * num_solids;
    }

    // Skip thick shell elements: 9 * NELT
    offset += 9 * control_data_.NELT;

    // Skip beam elements: 6 * NEL2
    offset += 6 * control_data_.NEL2;

    // Skip shell elements: 5 * NEL4
    offset += 5 * control_data_.NEL4;

    // Skip NARBS section if present (ls-dyna_database.txt lines 667-724)
    if (control_data_.NARBS > 0) {
        offset += control_data_.NARBS;
    }

    return offset;
}

void StateDataParser::parse_deletion_data(data::StateData& state, size_t& offset) {
    // 요소 삭제(침식) 테이블. 규격 원문(ls-dyna_database.txt "ELEMENT DELETION OPTION"):
    //
    //   MDLOPT == 0 : 이 절 자체가 없다
    //   MDLOPT == 1 : 길이 NUMNP. 절점이 보이면 1, 안 보이면 0
    //                 (vec-dyna3d 전용 — 요소 삭제 정보가 아니다)
    //   MDLOPT == 2 : 길이 NEL8 + NELT + NEL4 + NEL2, **이 순서**.
    //                 값이 요소의 재질 번호이고, **0 이면 삭제된 요소**다.
    //
    //   "All these numbers are output as floating point values and not integers."
    //   → 정수로 읽으면 안 된다. 실수로 읽고 0 과 비교한다.
    //
    // 🔴 예전에는 이 함수가 비어 있어 deleted_solids 가 **항상 비었다.**
    //    소비처(SectionClipper, NodalAverager)는 그 배열로 침식 요소를 거르므로,
    //    침식이 있는 덱에서 죽은 요소가 살아 있는 것처럼 렌더·평균에 섞였다.
    //    오프셋 자체는 DELNN 이 state_size 에 반영돼 있어 정상이었다(데이터 어긋남 없음).
    //
    // ⚠️ 검증 한계 — 현재 확보한 덱은 전부 MDLOPT=0 이라 이 경로를 실행으로
    //    확인하지 못했다. 침식 덱이 생기면 반드시 실측할 것.
    if (control_data_.DELNN <= 0) {
        return;
    }

    const int mdlopt = control_data_.MDLOPT;

    // 🔴 워드 단위 read_double 로 훑으면 안 된다. 실측(results/d3plot,
    //    DELNN=44,657 × 992 상태): 상태당 2.57 ms → 14.64 ms 로 **5.7 배** 느려졌다.
    //    이 절의 소비처는 SectionClipper·NodalAverager 두 곳뿐인데 전 상태에
    //    그 비용을 물릴 수 없다. 대량 읽기(read_double_array)를 쓴다.
    const std::vector<double> tbl =
        reader_->read_double_array(offset, static_cast<size_t>(control_data_.DELNN));
    if (tbl.size() < static_cast<size_t>(control_data_.DELNN)) {
        return;   // 파일이 짧다 — 조용히 잘못된 목록을 만들지 않는다
    }

    if (mdlopt == 1) {
        // 절점 가시성 목록 — 요소 삭제 정보가 아니므로 절점 쪽에만 기록한다.
        state.deleted_nodes.clear();
        for (int i = 0; i < control_data_.NUMNP; ++i) {
            if (tbl[static_cast<size_t>(i)] == 0.0) {
                state.deleted_nodes.push_back(i + 1);   // 내부 1-based 절점 번호
            }
        }
        return;
    }

    if (mdlopt != 2) {
        return;   // 규격에 없는 값 — 건너뛴다(오프셋은 호출부가 진행시킨다)
    }

    // MDLOPT == 2 : 요소 재질번호 목록. 0 = 삭제.
    // 순서가 NEL8 → NELT → NEL4 → NEL2 로 고정돼 있다.
    const int nel8 = std::abs(control_data_.NEL8);
    const int nelt = control_data_.NELT;
    const int nel4 = control_data_.NEL4;
    const int nel2 = control_data_.NEL2;

    size_t k = 0;
    auto scan = [&](int count, std::vector<int32_t>& out) {
        out.clear();
        for (int i = 0; i < count; ++i, ++k) {
            if (k < tbl.size() && tbl[k] == 0.0) {
                out.push_back(i + 1);   // 해당 배열 내 1-based 순번
            }
        }
    };

    scan(nel8, state.deleted_solids);
    scan(nelt, state.deleted_thick_shells);
    scan(nel4, state.deleted_shells);
    scan(nel2, state.deleted_beams);
}

} // namespace parsers
} // namespace kood3plot
