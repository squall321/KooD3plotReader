// 솔리드 요소 워드의 적분점 배치를 머리말에서 읽고, 요소마다 값이 실린 적분점 자리를 고르는 도우미
#pragma once

#include "kood3plot/data/ControlData.hpp"

#include <cstddef>
#include <cstring>

namespace kood3plot {
namespace data {

/**
 * @brief 솔리드 요소 블록의 적분점 배치
 *
 * *DATABASE_EXTENT_BINARY 의 NINTSLD 가 8 이면 솔리드 하나에 적분점 블록 여덟 개가 연달아 실린다 —
 * NV3D = 8 × (6·IOSOL(1) + IOSOL(2) + NEIPH). 머리말에 NINTSLD 자리는 따로 없어서 NV3D 가 이 식과
 * 정확히 맞을 때만 여덟 자리로 읽고, 그 밖에는 요소 블록 전체를 적분점 하나로 본다(종전 그대로).
 * 변형률 6성분은 적분점 블록마다 이력 변수의 마지막 여섯 워드다.
 *
 * 실덱 확인(2026-11-21, 솔리드가 있는 d3plot 폴더 2,741개) — 한 자리 2,479 · 여덟 자리 159 · 솔리드 워드 없음 103,
 * 어느 쪽에도 들지 않는 덱은 없었다.
 */
struct SolidIpLayout {
    int nv = 0;          ///< 요소 하나의 워드 수(NV3D)
    int nip = 1;         ///< 적분점 자리 수 — 1 또는 8
    int stride = 0;      ///< 적분점 하나의 워드 수(nip 이 1 이면 nv)
    int strain_off = -1; ///< 적분점 블록 안 변형률 6성분의 시작(없으면 -1)

    static SolidIpLayout from(const ControlData& c) {
        SolidIpLayout L;
        L.nv = c.NV3D;
        L.stride = c.NV3D;
        const int per_ip = 6 * c.IOSOL[0] + c.IOSOL[1] + c.NEIPH;
        if (per_ip >= 7 && c.NV3D == 8 * per_ip) {
            L.nip = 8;
            L.stride = per_ip;
        }
        if (c.ISTRN != 0 && L.stride >= 13) L.strain_off = L.stride - 6;
        return L;
    }
};

/// 요소 하나에서 값이 실린 적분점 자리(0부터). n 은 1 이상이다.
struct SolidIpSet {
    int n = 1;
    int ip[8] = {0, 0, 0, 0, 0, 0, 0, 0};
};

/**
 * @brief 요소 블록(blk — L.nv 워드)에서 값이 실린 적분점 자리를 고른다
 *
 * - 사면체 · 오면체는 적분점이 여덟보다 적어 남는 자리가 0 으로 실린다. 앞 7 워드(응력 6 · ε_p)가 전부 정확히
 *   0 인 자리는 뺀다 — 넣으면 인장만 걸린 요소의 σ3 최소 · 압축만 걸린 요소의 σ1 최대가 가짜 0 이 되고
 *   평균이 묽어진다.
 * - 쓰인 자리가 워드까지 전부 같으면(1점 적분 요소를 여덟 번 적은 덱) 자리 하나만 돌려준다 — 결과가
 *   한 자리 덱과 비트까지 같다.
 * - 쓰인 자리가 없으면(초기 상태처럼 전부 0) 자리 0 하나.
 *
 * 한 자리 덱(L.nip == 1)이면 워드를 읽지 않고 자리 0 을 돌려준다.
 */
inline SolidIpSet solidIps(const double* blk, const SolidIpLayout& L) {
    SolidIpSet s;
    if (L.nip <= 1) return s;

    int n = 0;
    for (int i = 0; i < L.nip; ++i) {
        const double* p = blk + static_cast<std::ptrdiff_t>(i) * L.stride;
        bool used = false;
        for (int w = 0; w < 7; ++w) {
            if (p[w] != 0.0) { used = true; break; }
        }
        if (used) s.ip[n++] = i;
    }
    if (n == 0) {
        s.ip[0] = 0;
        return s;
    }

    const double* p0 = blk + static_cast<std::ptrdiff_t>(s.ip[0]) * L.stride;
    const std::size_t bytes = sizeof(double) * static_cast<std::size_t>(L.stride);
    bool same = true;
    for (int k = 1; k < n && same; ++k) {
        same = std::memcmp(p0, blk + static_cast<std::ptrdiff_t>(s.ip[k]) * L.stride, bytes) == 0;
    }
    s.n = same ? 1 : n;
    return s;
}

/**
 * @brief 쓰인 자리들의 워드 평균 — out[w] = 적분점 블록의 (off + w) 번째 워드의 평균 (w < count)
 *
 * 첫 자리 값에서 벗어난 만큼만 평균해 더한다 — 자리 값이 전부 같으면 반올림 없이 그 값이 그대로 나온다.
 */
inline void solidIpMean(const double* blk, const SolidIpLayout& L, const SolidIpSet& set,
                        int off, int count, double* out) {
    const double* p0 = blk + static_cast<std::ptrdiff_t>(set.ip[0]) * L.stride + off;
    for (int w = 0; w < count; ++w) out[w] = p0[w];
    if (set.n <= 1) return;
    for (int w = 0; w < count; ++w) {
        double dev = 0.0;
        for (int k = 1; k < set.n; ++k) {
            dev += blk[static_cast<std::ptrdiff_t>(set.ip[k]) * L.stride + off + w] - p0[w];
        }
        out[w] = p0[w] + dev / static_cast<double>(set.n);
    }
}

} // namespace data
} // namespace kood3plot
