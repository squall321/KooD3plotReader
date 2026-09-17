// ExtendedAnalysisResult::toExtendedJSON 의 수치 표기·비유한값·미산출 표기를 검증하는 시험
/**
 * @file test_extended_json.cpp
 * @brief analysis_result.json 확장 섹션(motion/element_quality/beam/set_reports/
 *        surface_strain) 의 JSON 유효성과 자릿수 시험
 *
 * 빌드 (tests/hotspot/README.md 관례):
 *   g++ -std=c++17 -O2 -I include tests/test_extended_json.cpp \
 *       -o /tmp/t_extended_json && /tmp/t_extended_json
 */
#include "kood3plot/analysis/AnalysisTypes.hpp"

#include <cmath>
#include <cstdlib>
#include <iostream>
#include <limits>
#include <string>
#include <vector>

using namespace kood3plot;
using namespace kood3plot::analysis;

static int g_fails = 0;

static void chk(const std::string& name, bool ok, const std::string& detail = "") {
    if (!ok) {
        ++g_fails;
        std::cout << "  NG  " << name;
        if (!detail.empty()) std::cout << "  (" << detail << ")";
        std::cout << "\n";
    } else {
        std::cout << "  OK  " << name << "\n";
    }
}

static bool has(const std::string& hay, const std::string& needle) {
    return hay.find(needle) != std::string::npos;
}

/// "키": 다음에 오는 값 토큰을 그대로 꺼낸다 (콤마/중괄호/대괄호 앞까지).
static std::string valueOf(const std::string& json, const std::string& key, size_t from = 0) {
    const std::string k = "\"" + key + "\": ";
    size_t p = json.find(k, from);
    if (p == std::string::npos) return "<없음>";
    p += k.size();
    size_t e = json.find_first_of(",}]\n", p);
    return json.substr(p, e - p);
}

/// JSON 문법 최소 검사 — 파이썬 json.load 가 거부하는 맨 nan/inf 토큰이 있는지.
static bool hasBareNonFinite(const std::string& json) {
    static const char* toks[] = {": nan", ": -nan", ": inf", ": -inf",
                                 "[nan", "[-nan", "[inf", "[-inf",
                                 ",nan", ",-nan", ",inf", ",-inf"};
    for (const char* t : toks) {
        if (has(json, t)) return true;
    }
    return false;
}

static const double kNaN = std::numeric_limits<double>::quiet_NaN();
static const double kInf = std::numeric_limits<double>::infinity();

// ============================================================
// 유한값 — 자릿수가 살아 있어야 한다
// ============================================================

static ExtendedAnalysisResult makeFiniteResult() {
    ExtendedAnalysisResult r;
    r.metadata.d3plot_path = "/tmp/d3plot";
    r.metadata.num_states = 2;

    PartMotionStats m;
    m.part_id = 17;
    m.part_name = "impactor";
    m.peak_velocity_magnitude = 1.9e-07;   // SI(m/s) 덱
    m.peak_acceleration_magnitude = 3e-09;
    m.max_displacement_magnitude = 1.066e-05;
    m.data.resize(2);
    r.motion_analysis.push_back(m);

    ElementQualityStats q;
    q.part_id = 4;
    q.element_type = "solid";
    q.num_elements = 100;
    q.jacobian_measured = true;
    q.min_jacobian = 0.812345678;
    q.aspect_measured = true;
    q.peak_aspect_ratio = 3.25;
    for (double t : {1.4e-07, 1.5e-07}) {
        ElementQualityTimePoint tp;
        tp.time = t;
        tp.jacobian_measured = true;
        tp.jacobian_min = 0.812345678;
        tp.jacobian_avg = 0.912345678;
        q.data.push_back(tp);
    }
    r.element_quality.push_back(q);

    PartTimeSeriesStats b;
    b.part_id = 9;
    b.quantity = "axial_force";
    {
        TimePointStats tp;
        tp.time = 3.02e-06;
        tp.max_value = 4.5e-07;
        tp.min_value = -4.5e-07;
        b.data.push_back(tp);
    }
    r.beam_analysis.push_back(b);

    SetReportResult sr;
    sr.name = "PKG";
    sr.set_type = "part";
    sr.set_id = 5;
    {
        SetFieldResult f;
        f.field = "eff_plastic_strain";
        f.measured = true;
        f.peak = 9.5e-07;
        f.peak_time = 5.05e-06;
        sr.fields.push_back(f);
    }
    r.set_report_results.push_back(sr);

    SurfaceStrainStats s;
    s.description = "Bottom_-Z";
    s.has_strain_tensor = true;
    {
        SurfaceStrainTimePoint tp;
        tp.time = 1.4e-07;
        tp.normal_strain_avg = 1.7e-07;
        tp.max_principal_strain_max = 4.2e-09;
        tp.vm_strain_max = 9.5e-07;
        s.data.push_back(tp);
    }
    r.surface_strain_analysis.push_back(s);

    return r;
}

static void test_finite_precision() {
    std::cout << "유한값 자릿수:\n";
    const std::string json = makeFiniteResult().toExtendedJSON();

    chk("motion peak_velocity 1.9e-07 보존",
        std::stod(valueOf(json, "peak_velocity")) == 1.9e-07, valueOf(json, "peak_velocity"));
    chk("motion peak_acceleration 3e-09 가 0 이 아니다",
        std::stod(valueOf(json, "peak_acceleration")) != 0.0, valueOf(json, "peak_acceleration"));
    chk("motion max_displacement 1.066e-05 보존",
        std::stod(valueOf(json, "max_displacement")) == 1.066e-05, valueOf(json, "max_displacement"));

    chk("quality peak_aspect_ratio 3.25 보존",
        std::stod(valueOf(json, "peak_aspect_ratio")) == 3.25, valueOf(json, "peak_aspect_ratio"));
    chk("quality min_jacobian 0.812345678 보존",
        std::stod(valueOf(json, "min_jacobian")) == 0.812345678, valueOf(json, "min_jacobian"));
    // 근접 시각이 같은 문자열로 뭉개지면 그래프 x축이 무너진다
    const std::string t0 = valueOf(json, "time", json.find("\"data\": [{\"time\""));
    chk("quality 시각 1.4e-07 보존", std::stod(t0) == 1.4e-07, t0);

    chk("beam peak_max 4.5e-07 보존",
        std::stod(valueOf(json, "peak_max")) == 4.5e-07, valueOf(json, "peak_max"));
    chk("beam peak_max_time 3.02e-06 보존",
        std::stod(valueOf(json, "peak_max_time")) == 3.02e-06, valueOf(json, "peak_max_time"));

    chk("set_reports peak 9.5e-07 보존",
        std::stod(valueOf(json, "peak")) == 9.5e-07, valueOf(json, "peak"));
    chk("set_reports peak_time 5.05e-06 보존",
        std::stod(valueOf(json, "peak_time")) == 5.05e-06, valueOf(json, "peak_time"));

    chk("surface_strain normal_avg 1.7e-07 보존",
        std::stod(valueOf(json, "normal_avg")) == 1.7e-07, valueOf(json, "normal_avg"));
    chk("surface_strain e1_max 4.2e-09 가 0 이 아니다",
        std::stod(valueOf(json, "e1_max")) != 0.0, valueOf(json, "e1_max"));
    chk("surface_strain evm_max 9.5e-07 보존",
        std::stod(valueOf(json, "evm_max")) == 9.5e-07, valueOf(json, "evm_max"));
}

// ============================================================
// 비유한값 — nan/inf 는 JSON 이 아니다. null 로 나가야 한다
// ============================================================

static void test_non_finite_becomes_null() {
    std::cout << "비유한값 → null:\n";
    ExtendedAnalysisResult r = makeFiniteResult();
    r.motion_analysis[0].peak_velocity_magnitude = kNaN;
    r.motion_analysis[0].max_displacement_magnitude = kInf;
    r.element_quality[0].min_jacobian = kNaN;
    r.beam_analysis[0].data[0].max_value = kNaN;
    r.set_report_results[0].fields[0].peak = kInf;
    r.surface_strain_analysis[0].data[0].vm_strain_max = kNaN;

    const std::string json = r.toExtendedJSON();
    chk("맨 nan/inf 토큰이 없다 (python json.load 가 거부한다)", !hasBareNonFinite(json));
    chk("motion peak_velocity NaN → null", valueOf(json, "peak_velocity") == "null",
        valueOf(json, "peak_velocity"));
    chk("motion max_displacement inf → null", valueOf(json, "max_displacement") == "null",
        valueOf(json, "max_displacement"));
    chk("quality min_jacobian NaN → null", valueOf(json, "min_jacobian") == "null",
        valueOf(json, "min_jacobian"));
    chk("beam peak_max NaN → null", valueOf(json, "peak_max") == "null",
        valueOf(json, "peak_max"));
    chk("set_reports peak inf → null", valueOf(json, "peak") == "null",
        valueOf(json, "peak"));
    chk("surface_strain evm_max NaN → null", valueOf(json, "evm_max") == "null",
        valueOf(json, "evm_max"));
}

int main() {
    std::cout << "========================================\n";
    std::cout << "toExtendedJSON 시험\n";
    std::cout << "========================================\n\n";

    test_finite_precision();
    test_non_finite_becomes_null();

    std::cout << "\n========================================\n";
    if (g_fails) {
        std::cout << "[FAIL] 실패 " << g_fails << " 건\n";
    } else {
        std::cout << "[PASS] 실패 0 건\n";
    }
    std::cout << "========================================\n";
    return g_fails > 0 ? 1 : 0;
}
