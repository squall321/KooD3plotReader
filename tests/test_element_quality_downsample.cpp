// 요소 품질 시계열 다운샘플이 극값을 잃지 않는지 보는 시험.
//
// 요약값(peak_aspect_ratio·min_jacobian 등)은 전 상태에서 구하되, 산출물에 싣는
// data[] 는 상한을 둔다. 그 과정에서 피크가 사라지면 그래프가 거짓말을 하므로,
// 구간별 극값을 보존하는 방식이어야 한다.
//
// 빌드·실행:
//   g++ -std=c++17 -O2 -I include tests/test_element_quality_downsample.cpp \
//       .work/build/libkood3plot.a -fopenmp -lz -o .work/t_eqds && .work/t_eqds
#include "kood3plot/analysis/AnalysisTypes.hpp"

#include <cmath>
#include <cstdio>
#include <string>
#include <vector>

using namespace kood3plot::analysis;

namespace {

int g_failed = 0;

void chk(const char* what, bool ok, const std::string& detail) {
    if (!ok) ++g_failed;
    std::printf("  %s %-52s %s\n", ok ? "OK " : "NG ", what, detail.c_str());
}

/// 상태 n 개짜리 합성 이력. 극값은 일부러 가운데 홀수 위치에 하나씩 심는다.
ElementQualityStats makeStats(size_t n) {
    ElementQualityStats qs;
    qs.part_id = 7;
    qs.element_type = "solid";
    qs.num_elements = 100;
    for (size_t i = 0; i < n; ++i) {
        ElementQualityTimePoint tp;
        tp.time = 1e-6 * static_cast<double>(i);
        tp.aspect_measured = true;
        tp.aspect_ratio_max = 2.0;
        tp.jacobian_measured = true;
        tp.jacobian_min = 0.9;
        tp.volume_measured = true;
        tp.volume_change_min = 1.0;
        tp.volume_change_max = 1.0;
        qs.data.push_back(tp);
    }
    // 종횡비 피크 / 최악 Jacobian / 뒤집힌 요소 수 피크를 서로 다른 시점에 심는다
    qs.data[1234].aspect_ratio_max = 99.0;
    qs.data[2345].jacobian_min = -0.5;
    qs.data[3456].n_negative_jacobian = 42;
    qs.data[4567].volume_change_min = 0.05;
    return qs;
}

}  // namespace

int main() {
    const size_t kN = 5000;
    const size_t kCap = 500;

    ElementQualityStats full = makeStats(kN);
    full.computeGlobalStats();
    const double want_ar = full.peak_aspect_ratio;
    const double want_jac = full.min_jacobian;
    const int32_t want_neg = full.max_negative_jacobian_count;
    const double want_vol = full.min_volume_change;

    std::printf("[준비] 상태 %zu개, 요약 peak_AR=%.6g min_jac=%.6g neg=%d min_vol=%.6g\n",
                kN, want_ar, want_jac, want_neg, want_vol);

    ElementQualityStats qs = makeStats(kN);
    qs.computeGlobalStats();          // 요약은 전 상태에서
    qs.downsampleData(kCap);          // 시계열만 줄인다

    std::printf("\n[A] 시계열 길이에 상한이 걸린다\n");
    chk("점 개수가 상한 이하", qs.data.size() <= kCap,
        "n=" + std::to_string(qs.data.size()));
    chk("그래도 충분히 남는다 (상한의 절반 이상)", qs.data.size() * 2 >= kCap,
        "n=" + std::to_string(qs.data.size()));
    chk("요약이 본 상태 수가 기록된다", qs.num_states_analyzed == kN,
        "n=" + std::to_string(qs.num_states_analyzed));

    std::printf("\n[B] 요약값은 전 상태 기준 그대로다\n");
    chk("peak_aspect_ratio 불변", qs.peak_aspect_ratio == want_ar,
        std::to_string(qs.peak_aspect_ratio));
    chk("min_jacobian 불변", qs.min_jacobian == want_jac,
        std::to_string(qs.min_jacobian));
    chk("max_negative_jacobian_count 불변", qs.max_negative_jacobian_count == want_neg,
        std::to_string(qs.max_negative_jacobian_count));

    std::printf("\n[C] 남은 시계열이 극값을 그대로 담고 있다\n");
    {
        double got_ar = 0.0, got_jac = 1e300, got_vol = 1e300;
        int32_t got_neg = 0;
        bool has_first = false, has_last = false;
        for (const auto& tp : qs.data) {
            if (tp.aspect_ratio_max > got_ar) got_ar = tp.aspect_ratio_max;
            if (tp.jacobian_measured && tp.jacobian_min < got_jac) got_jac = tp.jacobian_min;
            if (tp.n_negative_jacobian > got_neg) got_neg = tp.n_negative_jacobian;
            if (tp.volume_measured && tp.volume_change_min < got_vol) got_vol = tp.volume_change_min;
            if (tp.time == 0.0) has_first = true;
            if (std::abs(tp.time - 1e-6 * static_cast<double>(kN - 1)) < 1e-18) has_last = true;
        }
        chk("종횡비 피크가 남아 있다", got_ar == want_ar, std::to_string(got_ar));
        chk("최악 Jacobian 이 남아 있다", got_jac == want_jac, std::to_string(got_jac));
        chk("뒤집힌 요소 수 피크가 남아 있다", got_neg == want_neg, std::to_string(got_neg));
        chk("최소 체적비가 남아 있다", got_vol == want_vol, std::to_string(got_vol));
        chk("첫 시점이 남아 있다", has_first, "");
        chk("마지막 시점이 남아 있다", has_last, "");
    }

    std::printf("\n[D] 시각이 오름차순이고 중복이 없다\n");
    {
        bool ordered = true;
        for (size_t i = 1; i < qs.data.size(); ++i) {
            if (!(qs.data[i].time > qs.data[i - 1].time)) { ordered = false; break; }
        }
        chk("시각이 단조 증가", ordered, "n=" + std::to_string(qs.data.size()));
    }

    std::printf("\n[E] 상한보다 짧으면 손대지 않는다\n");
    {
        ElementQualityStats small;
        for (size_t i = 0; i < 12; ++i) {
            ElementQualityTimePoint tp;
            tp.time = 1e-6 * static_cast<double>(i);
            small.data.push_back(tp);
        }
        small.computeGlobalStats();
        small.downsampleData(kCap);
        chk("점 개수 그대로", small.data.size() == 12,
            "n=" + std::to_string(small.data.size()));
        chk("본 상태 수도 12", small.num_states_analyzed == 12,
            "n=" + std::to_string(small.num_states_analyzed));
    }

    std::printf("\n%s  실패 %d 건\n", g_failed ? "[FAIL]" : "[PASS]", g_failed);
    return g_failed ? 1 : 0;
}
