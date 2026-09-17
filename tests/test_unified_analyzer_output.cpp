// unified_analyzer 의 CSV 작성기와 재귀 배치 경로(폴더 이름·완료 판정·스캔)를 검증하는 시험
/**
 * @file test_unified_analyzer_output.cpp
 * @brief unified_analyzer.cpp 출력 경로 단위 시험
 *
 * 빌드 (이 저장소 관례 — tests/hotspot/README.md 참고):
 *   cmake -S . -B build -DCMAKE_BUILD_TYPE=Release \
 *         -DKOOD3PLOT_BUILD_V4_RENDER=OFF -DKOOD3PLOT_BUILD_TESTS=OFF > /dev/null
 *   cmake --build build -j4 --target unified_analyzer
 *   g++ -std=c++17 -O2 -I include tests/test_unified_analyzer_output.cpp \
 *       build/libkood3plot.a -fopenmp -lz -o /tmp/t_ua_output && /tmp/t_ua_output
 *
 * unified_analyzer.cpp 의 CSV 작성기·재귀 헬퍼는 라이브러리가 아니라 실행 파일
 * 안에 있다. main 만 이름을 바꿔 원본을 통째로 가져온다 (복사본을 두면 원본이
 * 바뀌어도 시험은 옛 코드를 검사하게 된다).
 */
#define main kood3plot_unified_analyzer_main
#include "../examples/unified_analyzer.cpp"
#undef main

#include <cmath>
#include <cstdio>
#include <sstream>
#include <string>
#include <unistd.h>
#include <vector>

namespace uatest {

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

/// CSV 를 [행][열] 문자열로 읽는다. '#' 로 시작하는 머리말 주석은 건너뛴다.
static std::vector<std::vector<std::string>> readCSV(const std::string& path) {
    std::vector<std::vector<std::string>> rows;
    std::ifstream ifs(path);
    std::string line;
    while (std::getline(ifs, line)) {
        if (!line.empty() && line[0] == '#') continue;
        std::vector<std::string> cols;
        std::stringstream ss(line);
        std::string cell;
        while (std::getline(ss, cell, ',')) cols.push_back(cell);
        rows.push_back(cols);
    }
    return rows;
}

/// Python 소비처(loader.py 의 float())가 그대로 읽는지 — std::stod 로 흉내낸다.
static bool parsesAsFloat(const std::string& s, double& out) {
    if (s.empty()) return false;
    try {
        size_t used = 0;
        out = std::stod(s, &used);
        return used == s.size();
    } catch (...) {
        return false;
    }
}

static bool relClose(double got, double want, double rel) {
    if (want == 0.0) return std::fabs(got) <= rel;
    return std::fabs(got - want) <= rel * std::fabs(want);
}

static std::string tmpDir() {
    static std::string dir;
    if (dir.empty()) {
        dir = (fs::temp_directory_path() / ("ua_output_test_" + std::to_string(::getpid()))).string();
        fs::create_directories(dir);
    }
    return dir;
}

// ============================================================
// CSV 수치 정밀도 — std::fixed<<setprecision(6) 은 µs 시각과 1e-7 변형률을 뭉갠다
// ============================================================

// 실제 덱에서 나온 값들 (Test_Impact_A / Test_hs_shell_e2e)
static const double kTimes[]  = {3.02e-06, 5.05e-06, 1.4e-07, 1.5e-07, 0.00500000, 0.00500002};
static const double kValues[] = {3e-09,    1.9e-07,  9.5e-07, 1.066e-05, 0.0863,   -2.8e-07};
static const size_t kN = 6;

static void test_part_csv_precision() {
    std::cout << "writePartCSV 정밀도:\n";
    PartTimeSeriesStats stats;
    stats.part_id = 19;
    stats.part_name = "PKG";
    stats.quantity = "eff_plastic_strain";
    stats.unit = "-";
    for (size_t i = 0; i < kN; ++i) {
        TimePointStats tp;
        tp.time = kTimes[i];
        tp.max_value = kValues[i];
        tp.min_value = -kValues[i];
        tp.avg_value = kValues[i] * 0.5;
        tp.max_element_id = static_cast<int32_t>(100 + i);
        tp.min_element_id = static_cast<int32_t>(200 + i);
        stats.data.push_back(tp);
    }

    const std::string path = tmpDir() + "/part.csv";
    writePartCSV(path, stats);
    auto rows = readCSV(path);
    chk("행 수 = 머리말 1 + 상태 6", rows.size() == kN + 1,
        "rows=" + std::to_string(rows.size()));
    if (rows.size() != kN + 1) return;

    for (size_t i = 0; i < kN; ++i) {
        const auto& r = rows[i + 1];
        double t = 0, mx = 0, mn = 0, av = 0;
        chk("행 " + std::to_string(i) + " 이 float 로 읽힌다",
            parsesAsFloat(r[0], t) && parsesAsFloat(r[1], mx) &&
            parsesAsFloat(r[2], mn) && parsesAsFloat(r[3], av),
            r[0] + "," + r[1]);
        chk("시각 " + std::to_string(kTimes[i]) + " 왕복", relClose(t, kTimes[i], 1e-9), r[0]);
        chk("최대값 " + std::to_string(kValues[i]) + " 왕복", relClose(mx, kValues[i], 1e-9), r[1]);
        chk("최소값 왕복", relClose(mn, -kValues[i], 1e-9), r[2]);
        chk("평균 왕복", relClose(av, kValues[i] * 0.5, 1e-9), r[3]);
    }
    // 시나리오 그대로: 3e-9 는 '진짜 0' 과 구분돼야 한다
    chk("3e-9 가 0 으로 사라지지 않는다", rows[1][1] != "0.000000" && std::stod(rows[1][1]) != 0.0,
        rows[1][1]);
    // 1.4e-7 과 1.5e-7 은 서로 다른 시각이다
    chk("1.4e-7 ≠ 1.5e-7 (시각 중복 없음)", rows[3][0] != rows[4][0],
        rows[3][0] + " vs " + rows[4][0]);
    // 0.00500000 과 0.00500002 도 마찬가지
    chk("0.005 ≠ 0.00500002 (시각 중복 없음)", rows[5][0] != rows[6][0],
        rows[5][0] + " vs " + rows[6][0]);
    chk("요소 ID 는 정수 그대로", rows[1][4] == "100" && rows[1][5] == "200",
        rows[1][4] + "/" + rows[1][5]);
}

static void test_motion_csv_precision() {
    std::cout << "writeMotionCSV 정밀도:\n";
    PartMotionStats stats;
    stats.part_id = 17;
    stats.part_name = "impactor";
    for (size_t i = 0; i < kN; ++i) {
        MotionTimePoint mp;
        mp.time = kTimes[i];
        mp.avg_displacement = Vec3{kValues[i], -kValues[i], 2 * kValues[i]};
        mp.avg_displacement_magnitude = kValues[i];
        mp.avg_velocity = Vec3{kValues[i], 0, 0};
        mp.avg_velocity_magnitude = kValues[i];
        mp.avg_acceleration = Vec3{0, kValues[i], 0};
        mp.avg_acceleration_magnitude = kValues[i];
        mp.max_displacement_magnitude = kValues[i] * 2;
        mp.max_displacement_node_id = static_cast<int32_t>(7000 + i);
        stats.data.push_back(mp);
    }

    const std::string path = tmpDir() + "/motion.csv";
    writeMotionCSV(path, stats);
    auto rows = readCSV(path);
    chk("행 수", rows.size() == kN + 1, "rows=" + std::to_string(rows.size()));
    if (rows.size() != kN + 1) return;

    for (size_t i = 0; i < kN; ++i) {
        double t = 0, d = 0;
        chk("motion 행 " + std::to_string(i) + " float 파싱",
            parsesAsFloat(rows[i + 1][0], t) && parsesAsFloat(rows[i + 1][4], d), rows[i + 1][0]);
        chk("motion 시각 왕복", relClose(t, kTimes[i], 1e-9), rows[i + 1][0]);
        chk("motion 변위 왕복", relClose(d, kValues[i], 1e-9), rows[i + 1][4]);
    }
    // FFT/SRS 가 np.diff(t) 로 샘플링 주파수를 구한다 — 시각이 겹치면 dt=0 이 된다
    chk("motion 시각에 중복 없음 (1.4e-7/1.5e-7)", rows[3][0] != rows[4][0],
        rows[3][0] + " vs " + rows[4][0]);
    chk("SI 덱 변위 1.9e-7 m 가 0 이 아니다", std::stod(rows[2][4]) != 0.0, rows[2][4]);
}

static void test_surface_csv_precision() {
    std::cout << "writeSurfaceCSV 정밀도:\n";
    SurfaceAnalysisStats stats;
    stats.description = "Bottom_-Z";
    stats.reference_direction = Vec3{0, 0, -1};
    stats.angle_threshold_degrees = 30.0;
    stats.num_faces = 10;
    for (size_t i = 0; i < kN; ++i) {
        SurfaceTimePointStats tp;
        tp.time = kTimes[i];
        tp.normal_stress_max = kValues[i];
        tp.von_mises_max = kValues[i];
        stats.data.push_back(tp);
    }

    const std::string path = tmpDir() + "/surface.csv";
    writeSurfaceCSV(path, stats);
    auto rows = readCSV(path);
    chk("행 수", rows.size() == kN + 1, "rows=" + std::to_string(rows.size()));
    if (rows.size() != kN + 1) return;
    for (size_t i = 0; i < kN; ++i) {
        double t = 0, n = 0;
        chk("surface 행 " + std::to_string(i) + " float 파싱",
            parsesAsFloat(rows[i + 1][0], t) && parsesAsFloat(rows[i + 1][1], n), rows[i + 1][0]);
        chk("surface 시각 왕복", relClose(t, kTimes[i], 1e-9), rows[i + 1][0]);
        chk("surface 수직응력 왕복", relClose(n, kValues[i], 1e-9), rows[i + 1][1]);
    }
}

static void test_quality_csv_time() {
    std::cout << "writeQualityCSV 시각·빈칸:\n";
    ElementQualityStats stats;
    stats.part_id = 4;
    stats.element_type = "solid";
    stats.num_elements = 100;
    stats.jacobian_measured = true;   // 나머지는 미산출 (축퇴 솔리드뿐인 파트)
    for (size_t i = 0; i < kN; ++i) {
        ElementQualityTimePoint tp;
        tp.time = kTimes[i];
        tp.jacobian_measured = true;
        tp.jacobian_min = 0.812345678;
        tp.jacobian_avg = 0.912345678;
        stats.data.push_back(tp);
    }

    const std::string path = tmpDir() + "/quality.csv";
    writeQualityCSV(path, stats);
    auto rows = readCSV(path);
    chk("행 수", rows.size() == kN + 1, "rows=" + std::to_string(rows.size()));
    if (rows.size() != kN + 1) return;
    for (size_t i = 0; i < kN; ++i) {
        double t = 0;
        chk("quality 시각 왕복 " + std::to_string(i),
            parsesAsFloat(rows[i + 1][0], t) && relClose(t, kTimes[i], 1e-9), rows[i + 1][0]);
    }
    // 회귀 방지 — 미산출 지표는 빈 칸이어야 한다 (0 으로 채우면 '완벽한 메시')
    chk("미산출 AspectRatio 는 빈 칸", rows[1][1].empty() && rows[1][2].empty(),
        "[" + rows[1][1] + "][" + rows[1][2] + "]");
    double jac = 0;
    chk("Jacobian 은 값이 있고 유효숫자가 남는다",
        parsesAsFloat(rows[1][3], jac) && relClose(jac, 0.812345678, 1e-9), rows[1][3]);
}

static void test_tensor_csv_precision() {
    std::cout << "exportResults 텐서 CSV 정밀도:\n";
    ExtendedAnalysisResult result;
    ElementTensorHistory hist;
    hist.element_id = 12345;
    hist.part_id = 7;
    hist.reason = "peak_vm";
    for (size_t i = 0; i < kN; ++i) {
        hist.time.push_back(kTimes[i]);
        hist.sxx.push_back(kValues[i]);
        hist.syy.push_back(-kValues[i]);
        hist.szz.push_back(kValues[i] * 2);
        hist.sxy.push_back(0.0);
        hist.syz.push_back(0.0);
        hist.szx.push_back(0.0);
    }
    result.peak_element_tensors.push_back(hist);

    UnifiedConfig cfg;
    cfg.output_directory = tmpDir() + "/export";
    cfg.output_csv = true;
    cfg.output_json = false;
    exportResults(result, cfg);

    const std::string path = cfg.output_directory +
        "/stress/tensor/part_7_elem_12345_peak_vm.csv";
    auto rows = readCSV(path);
    chk("텐서 CSV 행 수", rows.size() == kN + 1, "rows=" + std::to_string(rows.size()));
    if (rows.size() != kN + 1) return;
    for (size_t i = 0; i < kN; ++i) {
        double t = 0, sxx = 0;
        chk("텐서 행 " + std::to_string(i) + " float 파싱",
            parsesAsFloat(rows[i + 1][0], t) && parsesAsFloat(rows[i + 1][1], sxx), rows[i + 1][0]);
        chk("텐서 시각 왕복", relClose(t, kTimes[i], 1e-9), rows[i + 1][0]);
        chk("텐서 sxx 왕복", relClose(sxx, kValues[i], 1e-9), rows[i + 1][1]);
    }
}

// ============================================================
// 재귀 배치 — 스캔·결과 폴더 이름·완료 판정
// ============================================================

/// 시험용 트리를 새로 만든다.
static fs::path makeTree() {
    const fs::path base = fs::path(tmpDir()) / "tree";
    fs::remove_all(base);
    fs::create_directories(base);
    return base;
}

static void writeFile(const fs::path& p, const std::string& s) {
    fs::create_directories(p.parent_path());
    std::ofstream(p) << s;
}

static void test_scan_survives_symlink_cycle() {
    std::cout << "findD3plotDirectories 심링크 순환·중복:\n";
    const fs::path base = makeTree();
    for (const char* r : {"Run_1", "Run_2", "Run_3"}) {
        writeFile(base / "output" / r / "d3plot", "x");
    }
    // 순환 링크 하나로 예전 스캔은 ELOOP 로 끊겨 Run_2·Run_3 을 통째로 잃었다
    fs::create_symlink("..", base / "output" / "Run_2" / "parent_link");

    std::vector<std::string> unreadable;
    auto dirs = findD3plotDirectories(base / "output", &unreadable);
    chk("d3plot 폴더 3개를 모두 찾는다", dirs.size() == 3,
        "size=" + std::to_string(dirs.size()));
    std::vector<std::string> names;
    for (const auto& d : dirs) names.push_back(d.filename().string());
    std::sort(names.begin(), names.end());
    chk("Run_1/Run_2/Run_3 각각 한 번씩",
        names == std::vector<std::string>({"Run_1", "Run_2", "Run_3"}),
        names.empty() ? "" : names.front() + ".." + names.back());
    chk("순환은 오류가 아니라 '이미 본 폴더' 로 끊긴다", unreadable.empty(),
        unreadable.empty() ? "" : unreadable.front());
}

static void test_scan_reports_unreadable() {
    std::cout << "findD3plotDirectories 못 읽은 폴더 보고:\n";
    const fs::path base = makeTree();
    writeFile(base / "output" / "Run_1" / "d3plot", "x");
    writeFile(base / "output" / "locked" / "Run_2" / "d3plot", "x");
    fs::permissions(base / "output" / "locked", fs::perms::none);

    std::vector<std::string> unreadable;
    auto dirs = findD3plotDirectories(base / "output", &unreadable);
    fs::permissions(base / "output" / "locked", fs::perms::owner_all);  // 정리용
    chk("읽을 수 있는 폴더는 그대로 찾는다", dirs.size() == 1,
        "size=" + std::to_string(dirs.size()));
    chk("못 읽은 폴더가 사유와 함께 보고된다", unreadable.size() == 1,
        unreadable.empty() ? "(없음)" : unreadable.front());
}

static void test_result_folder_name_stays_inside_root() {
    std::cout << "generateResultFolderName 루트 이탈:\n";
    const fs::path base = makeTree();
    writeFile(base / "elsewhere" / "sims" / "Run_A" / "d3plot", "x");
    fs::create_directories(base / "output");
    fs::create_symlink(base / "elsewhere" / "sims" / "Run_A", base / "output" / "Run_A");

    const std::string name = generateResultFolderName(base / "output" / "Run_A", base / "output");
    chk("이름에 '..' 가 없다", name.find("..") == std::string::npos, name);
    const fs::path out_root = base / "analysis_results";
    const std::string full = (out_root / name).lexically_normal().string();
    chk("결과 경로가 output_root 안에 있다",
        full.rfind(out_root.string() + "/", 0) == 0, full);

    // 보통 런은 이름이 그대로여야 한다 (회귀 방지)
    writeFile(base / "output" / "Run_B" / "d3plot", "x");
    chk("보통 런 이름은 그대로",
        generateResultFolderName(base / "output" / "Run_B", base / "output") == "Run_B",
        generateResultFolderName(base / "output" / "Run_B", base / "output"));
    writeFile(base / "output" / "sub" / "Run_C" / "d3plot", "x");
    chk("하위 폴더 구조도 그대로",
        generateResultFolderName(base / "output" / "sub" / "Run_C", base / "output")
            == "sub/Run_C",
        generateResultFolderName(base / "output" / "sub" / "Run_C", base / "output"));
}

static void test_result_folder_collision_detected() {
    std::cout << "결과 폴더 이름 충돌 탐지:\n";
    const fs::path base = makeTree();
    writeFile(base / "output" / "case 1" / "d3plot", "x");   // 공백 → '_'
    writeFile(base / "output" / "case_1" / "d3plot", "x");
    writeFile(base / "output" / "case_2" / "d3plot", "x");

    const std::vector<fs::path> dirs = {base / "output" / "case 1",
                                        base / "output" / "case_1",
                                        base / "output" / "case_2"};
    auto collided = findCollidingResultFolders(dirs, base / "output");
    chk("'case 1' 과 'case_1' 충돌 1건을 잡는다", collided.size() == 1,
        "n=" + std::to_string(collided.size()));
    chk("뒤에 온 쪽이 충돌로 표시된다", collided.size() == 1 && collided[0] == 1,
        collided.empty() ? "" : std::to_string(collided[0]));
    chk("겹치지 않는 런은 충돌이 아니다",
        findCollidingResultFolders({dirs[0], dirs[2]}, base / "output").empty());
}

static void test_completion_marker() {
    std::cout << "--skip-existing 완료 판정:\n";
    const fs::path base = makeTree();
    const fs::path d3plot = base / "output" / "Run_1" / "d3plot";
    writeFile(d3plot, "x");
    const fs::path rd = base / "analysis_results" / "Run_1";
    fs::create_directories(rd);

    chk("결과가 아예 없으면 미완료", !isAnalysisCompleted(rd, d3plot));

    // 렌더 도중 죽은 경우: JSON 만 (심지어 0바이트) 남는다
    writeFile(rd / "analysis_result.json", "");
    chk("0바이트 JSON 만 있으면 미완료", !isAnalysisCompleted(rd, d3plot));

    writeFile(rd / "analysis_result.json", "{\"metadata\": {}}");
    chk("완료 표시가 없으면 미완료 (옛 판 결과 포함)", !isAnalysisCompleted(rd, d3plot));

    saveAnalysisMetadata(rd, d3plot, "cfg.yaml");
    chk("끝까지 돈 결과는 완료", isAnalysisCompleted(rd, d3plot));

    // 덱을 다시 돌렸다 → 옛 결과를 건너뛰면 안 된다
    fs::last_write_time(d3plot, fs::last_write_time(d3plot) + std::chrono::hours(1));
    chk("d3plot 이 새로 쓰이면 미완료", !isAnalysisCompleted(rd, d3plot));

    // 분석기가 바뀌었다 → 옛 결과를 건너뛰면 안 된다
    saveAnalysisMetadata(rd, d3plot, "cfg.yaml");
    {
        std::ifstream in(rd / ".analysis_info");
        std::string all((std::istreambuf_iterator<char>(in)), std::istreambuf_iterator<char>());
        in.close();
        const std::string k = "tool_version: ";
        const size_t p = all.find(k);
        all.replace(p + k.size(), all.find('\n', p) - p - k.size(), "older-build");
        writeFile(rd / ".analysis_info", all);
    }
    chk("분석기 버전이 다르면 미완료", !isAnalysisCompleted(rd, d3plot));
}

/// 재귀 배치 종료코드 — 스캔 불완전은 분석 실패와 구분돼야 한다.
/// scripts/analyze_and_report.sh 는 `set -e` 아래에서 --recursive 를 부르므로,
/// 읽기 권한 없는 폴더 하나로 1 을 내면 분석이 다 끝났는데도 보고서 단계가
/// 통째로 막힌다.
static void test_recursive_exit_code() {
    std::cout << "재귀 배치 종료코드:\n";
    const fs::path base = makeTree();
    const fs::path root = base / "output";
    fs::create_directories(root / "locked");
    fs::permissions(root / "locked", fs::perms::none);

    UnifiedConfig cfg;
    cfg.verbose = false;
    const int rc = runRecursiveAnalysis(root, base / "analysis_results", cfg,
                                        "cfg.yaml", /*analysis_only=*/true,
                                        /*skip_existing=*/false);
    fs::permissions(root / "locked", fs::perms::owner_all);   // 정리용

    chk("분석 실패가 없으면 1 이 아니다", rc != 1, "rc=" + std::to_string(rc));
    chk("스캔 불완전은 별도 코드 2 로 알린다", rc == 2, "rc=" + std::to_string(rc));
}

}  // namespace uatest

int main() {
    std::cout << "========================================\n";
    std::cout << "unified_analyzer 출력 경로 시험\n";
    std::cout << "========================================\n\n";

    uatest::test_part_csv_precision();
    uatest::test_motion_csv_precision();
    uatest::test_surface_csv_precision();
    uatest::test_quality_csv_time();
    uatest::test_tensor_csv_precision();
    uatest::test_scan_survives_symlink_cycle();
    uatest::test_scan_reports_unreadable();
    uatest::test_result_folder_name_stays_inside_root();
    uatest::test_result_folder_collision_detected();
    uatest::test_completion_marker();
    uatest::test_recursive_exit_code();

    std::cout << "\n========================================\n";
    if (uatest::g_fails) {
        std::cout << "[FAIL] 실패 " << uatest::g_fails << " 건\n";
    } else {
        std::cout << "[PASS] 실패 0 건\n";
    }
    std::cout << "========================================\n";
    fs::remove_all(uatest::tmpDir());
    return uatest::g_fails > 0 ? 1 : 0;
}
