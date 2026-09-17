// 헤더 안 CSV 작성기들이 std::fixed 로 µs 시각·미소 변형률을 뭉개지 않는지 보는 시험.
//
// unified_analyzer.cpp 는 이미 csvnum(defaultfloat·유효숫자 10)으로 바뀌었는데
// 같은 산출물 계층의 헤더 쪽 작성기 4곳이 std::fixed(8) 그대로였다. 절대 8자리
// 고정은 1e-8 미만을 "0.00000000" 으로 지워 진짜 0 과 구분되지 않게 만들고,
// 한 번 건 std::fixed 는 같은 스트림의 뒤 열 전부에 계속 걸린다.
//
// 빌드·실행:
//   g++ -std=c++17 -O2 -I include tests/test_csv_notation.cpp \
//       -o .work/t_csvnote && .work/t_csvnote
#include "kood3plot/analysis/AnalysisTypes.hpp"

#include <cmath>
#include <cstdio>
#include <fstream>
#include <filesystem>
#include <sstream>
#include <string>
#include <vector>

using namespace kood3plot::analysis;

namespace fs = std::filesystem;

namespace {

int g_failed = 0;

void chk(const char* what, bool ok, const std::string& detail) {
    if (!ok) ++g_failed;
    std::printf("  %s %-52s %s\n", ok ? "OK " : "NG ", what, detail.c_str());
}

std::vector<std::string> firstDataRow(const std::string& path) {
    std::ifstream in(path);
    std::string line;
    std::getline(in, line);   // 머리말
    std::getline(in, line);
    std::vector<std::string> cols;
    std::stringstream ss(line);
    std::string cell;
    while (std::getline(ss, cell, ',')) cols.push_back(cell);
    return cols;
}

/// Python 소비처의 float() 가 그대로 읽는지 — std::stod 로 흉내낸다.
bool parsesAsDouble(const std::string& s, double& out) {
    if (s.empty()) return false;
    try {
        size_t used = 0;
        out = std::stod(s, &used);
        return used == s.size();
    } catch (...) {
        return false;
    }
}

// 실덱에서 나온 값들 — dt 는 µs 급, 변형률은 1e-9 급
const double kTime = 1.000817633e-06;
const double kTiny = 3.0e-09;

}  // namespace

int main(int argc, char** argv) {
    const fs::path dir = (argc > 1) ? fs::path(argv[1]) : fs::path(".work") / "csv_notation_test";
    std::error_code ec;
    fs::create_directories(dir, ec);

    std::printf("[A] exportStressToCSV (AnalysisResult::exportPartStatsToCSV)\n");
    {
        ExtendedAnalysisResult r;
        PartTimeSeriesStats ps;
        ps.part_id = 19;
        ps.quantity = "eff_plastic_strain";
        TimePointStats tp;
        tp.time = kTime;
        tp.max_value = kTiny;
        tp.min_value = -kTiny;
        tp.avg_value = kTiny * 0.5;
        ps.data.push_back(tp);
        r.stress_history.push_back(ps);

        const std::string path = (dir / "stress.csv").string();
        chk("파일이 쓰인다", r.exportStressToCSV(path), path);
        const auto row = firstDataRow(path);
        chk("열 수 = 1 + 3", row.size() == 4, "n=" + std::to_string(row.size()));
        if (row.size() == 4) {
            double t = 0, v = 0;
            chk("시각이 숫자로 읽힌다", parsesAsDouble(row[0], t), row[0]);
            chk("시각 유효숫자가 남는다", std::abs(t - kTime) <= 1e-15 * kTime, row[0]);
            chk("값이 숫자로 읽힌다", parsesAsDouble(row[1], v), row[1]);
            chk("1e-9 값이 0 으로 지워지지 않는다", v != 0.0 && std::abs(v - kTiny) <= 1e-12 * kTiny,
                row[1]);
        }
    }

    std::printf("\n[B] exportSurfaceToCSV\n");
    {
        ExtendedAnalysisResult r;
        SurfaceAnalysisStats ss;
        ss.description = "Bottom";
        ss.num_faces = 1;
        SurfaceTimePointStats tp;
        tp.time = kTime;
        tp.normal_stress_max = kTiny;
        tp.normal_stress_avg = kTiny;
        tp.shear_stress_max = kTiny;
        tp.shear_stress_avg = kTiny;
        ss.data.push_back(tp);
        r.surface_analysis.push_back(ss);

        const std::string path = (dir / "surface.csv").string();
        chk("파일이 쓰인다", r.exportSurfaceToCSV(path), path);
        const auto row = firstDataRow(path);
        chk("열 수 = 1 + 4", row.size() == 5, "n=" + std::to_string(row.size()));
        if (row.size() == 5) {
            double t = 0, v = 0;
            chk("시각 유효숫자가 남는다",
                parsesAsDouble(row[0], t) && std::abs(t - kTime) <= 1e-15 * kTime, row[0]);
            chk("1e-9 값이 0 으로 지워지지 않는다",
                parsesAsDouble(row[1], v) && v != 0.0, row[1]);
        }
    }

    std::printf("\n[C] exportMotionToCSV (ExtendedAnalysisResult)\n");
    {
        ExtendedAnalysisResult r;
        PartMotionStats ms;
        ms.part_id = 3;
        MotionTimePoint tp;
        tp.time = kTime;
        tp.avg_displacement = Vec3(kTiny, 0, 0);
        tp.avg_displacement_magnitude = kTiny;
        ms.data.push_back(tp);
        r.motion_analysis.push_back(ms);

        const std::string path = (dir / "motion.csv").string();
        chk("파일이 쓰인다", r.exportMotionToCSV(path), path);
        const auto row = firstDataRow(path);
        chk("열이 있다", row.size() >= 2, "n=" + std::to_string(row.size()));
        if (row.size() >= 2) {
            double t = 0;
            chk("시각 유효숫자가 남는다",
                parsesAsDouble(row[0], t) && std::abs(t - kTime) <= 1e-15 * kTime, row[0]);
        }
    }

    std::printf("\n[D] exportSurfaceStrainToCSV (ExtendedAnalysisResult)\n");
    {
        ExtendedAnalysisResult r;
        SurfaceStrainStats st;
        st.description = "Bottom";
        st.has_strain_tensor = true;
        SurfaceStrainTimePoint tp;
        tp.time = kTime;
        tp.normal_strain_max = kTiny;
        st.data.push_back(tp);
        r.surface_strain_analysis.push_back(st);

        const std::string path = (dir / "strain.csv").string();
        chk("파일이 쓰인다", r.exportSurfaceStrainToCSV(path), path);
        const auto row = firstDataRow(path);
        chk("열이 있다", row.size() >= 2, "n=" + std::to_string(row.size()));
        if (row.size() >= 2) {
            double t = 0, v = 0;
            chk("시각 유효숫자가 남는다",
                parsesAsDouble(row[0], t) && std::abs(t - kTime) <= 1e-15 * kTime, row[0]);
            chk("1e-9 값이 0 으로 지워지지 않는다",
                parsesAsDouble(row[1], v) && v != 0.0, row[1]);
        }
    }

    fs::remove_all(dir, ec);
    std::printf("\n%s  실패 %d 건\n", g_failed ? "[FAIL]" : "[PASS]", g_failed);
    return g_failed ? 1 : 0;
}
