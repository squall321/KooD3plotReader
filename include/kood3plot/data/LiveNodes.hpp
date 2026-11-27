// 상태마다 산 요소에 하나라도 속한 절점을 가리는 표 — 침식 덱에서 지운 요소에만 속해 떨어져 나간 절점을 운동 지표에서 뺀다
#pragma once
/**
 * @file LiveNodes.hpp
 * @brief 침식(요소 삭제) 덱의 「떨어져 나간 절점」 표
 *
 * 지운 요소에만 속한 절점은 해석기가 더 붙잡지 않아 좌표 · 속도가 발산한다. 값이 유한할 수도 있어
 * (erode7 상태 490 — 좌표 ~1e21) isfinite 로는 못 거른다. LS-PrePost 도 지운 요소를 그리지 않는다.
 * 그 상태에서 산 요소(솔리드 · 두꺼운 셸 · 셸 · 빔)에 하나도 속하지 않는 절점을 떨어진 절점으로 본다.
 * 요소에 하나도 안 속한 절점(질량 절점 등)은 산 것으로 둔다. MDLOPT 1 덱은 상태의 절점 표(deleted_nodes)를 쓴다.
 * 요소 연결성은 내부 1-based 절점 순번이고, 삭제 목록은 그 종류 배열 안 1-based 순번이다.
 */

#include "kood3plot/data/Mesh.hpp"
#include "kood3plot/data/StateData.hpp"

#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <vector>

namespace kood3plot {
namespace data {

class LiveNodes {
public:
    explicit LiveNodes(const Mesh& mesh) : num_nodes_(mesh.nodes.size()), base_(mesh.nodes.size(), 0) {
        add(mesh.solids, solid_);
        add(mesh.thick_shells, tshell_);
        add(mesh.shells, shell_);
        add(mesh.beams, beam_);
    }

    /// 그 상태의 산 절점 표(0부터 절점 순번, 1 = 산 것). 지운 것이 하나도 없으면 nullptr — 모두 산 것이다.
    const std::vector<char>* forState(const StateData& st) {
        if (st.deleted_solids.empty() && st.deleted_thick_shells.empty() && st.deleted_shells.empty() &&
            st.deleted_beams.empty() && st.deleted_nodes.empty()) {
            return nullptr;
        }
        count_ = base_;
        drop(solid_, st.deleted_solids);
        drop(tshell_, st.deleted_thick_shells);
        drop(shell_, st.deleted_shells);
        drop(beam_, st.deleted_beams);
        alive_.assign(num_nodes_, 1);
        for (size_t n = 0; n < num_nodes_; ++n) {
            if (base_[n] > 0 && count_[n] <= 0) alive_[n] = 0;
        }
        for (int32_t n1 : st.deleted_nodes) {
            if (n1 >= 1 && static_cast<size_t>(n1) <= num_nodes_) alive_[static_cast<size_t>(n1 - 1)] = 0;
        }
        return &alive_;
    }

private:
    /// 요소마다 고유 절점(0부터) — 사면체 (a,b,c,d,d,d,d,d) 처럼 겹쳐 적힌 절점은 한 번만 센다
    template <typename E>
    void add(const std::vector<E>& els, std::vector<std::vector<int32_t>>& out) {
        out.resize(els.size());
        for (size_t e = 0; e < els.size(); ++e) {
            std::vector<int32_t>& v = out[e];
            for (int32_t n1 : els[e].node_ids) {
                if (n1 >= 1 && static_cast<size_t>(n1) <= num_nodes_) v.push_back(n1 - 1);
            }
            std::sort(v.begin(), v.end());
            v.erase(std::unique(v.begin(), v.end()), v.end());
            for (int32_t n : v) ++base_[static_cast<size_t>(n)];
        }
    }

    void drop(const std::vector<std::vector<int32_t>>& els, const std::vector<int32_t>& deleted) {
        for (int32_t ord : deleted) {
            if (ord < 1 || static_cast<size_t>(ord) > els.size()) continue;
            for (int32_t n : els[static_cast<size_t>(ord - 1)]) --count_[static_cast<size_t>(n)];
        }
    }

    size_t num_nodes_;
    std::vector<int32_t> base_;     // 절점마다 그 절점을 쓰는 요소 수(요소마다 한 번)
    std::vector<std::vector<int32_t>> solid_, tshell_, shell_, beam_;
    std::vector<int32_t> count_;
    std::vector<char> alive_;
};

}  // namespace data
}  // namespace kood3plot
