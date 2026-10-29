// d3plot 가족 파일 읽기 무결성 시험 — 잘림·누락·열기 실패를 '성공' 으로 넘기지 않는가
//
// 2026-10-28 DynaForge 보고 K-2·K-3 (ROADMAP 1-3·1-5). 예전 코드는
//   - 파싱 예외(bad_alloc 포함)를 삼키고 그 파일에서 읽은 만큼을 성공으로 돌려줬다
//     (12 GiB 상한 아래 4,952 상태 중 1,546 만 읽고 rc 0).
//   - 가족 파일 열기 실패·번호 구멍에서 멈추고 앞부분만 돌려줬다.
//   - 가족 파일마다 스레드를 띄워 스레드 생성 실패(std::system_error)로 죽었다.
// 실덱으로는 이런 상태를 만들 수 없어 D3plotWriter 로 가족 파일 5개짜리 덱을 만들고
// 파일을 자르거나 지워 본다.
//
// 검증 항목
//   1. 온전한 덱 — 순차·병렬(스레드 1·2·기본)·상태 수 훑기가 모두 12 상태, 시간 순서
//   2. 중간 가족 파일이 상태 도중 잘림 → 세 경로 모두 예외
//   3. 마지막 가족 파일이 상태 도중 잘림 → 예외 없이 앞 상태만(경고)
//   4. 중간 가족 파일 누락(번호 구멍) → 예외
//   5. 중간 가족 파일을 열 수 없음 → 예외 (root 면 권한이 안 막혀 건너뜀)
//   6. 스레드를 하나도 더 못 띄우는 환경(RLIMIT_NPROC=1) → 호출 스레드만으로 다 읽음
//
// Run:
//   cmake --build build -j4 --target kood3plot kood3plot_writer
//   g++ -std=c++17 -O2 -I include tests/test_family_read_integrity.cpp \
//       build/libkood3plot.a build/libkood3plot_writer.a -fopenmp -lz -lpthread -o .work/t_family
//   .work/t_family
//
// ctest 에 등록되어 있으므로 `ctest -R FamilyReadIntegrity` 로도 돌릴 수 있다.

#include "kood3plot/D3plotReader.hpp"
#include "kood3plot/writer/D3plotWriter.h"

#include <sys/resource.h>
#include <sys/wait.h>
#include <unistd.h>

#include <cmath>
#include <cstdio>
#include <filesystem>
#include <functional>
#include <string>
#include <vector>

using namespace kood3plot;
namespace fs = std::filesystem;

namespace {

int g_failed = 0;

void checkTrue(const std::string& what, bool cond) {
    if (!cond) ++g_failed;
    std::printf("  %s %s\n", cond ? "[OK]  " : "[FAIL]", what.c_str());
}

// hex 25개(절점 200개). 상태 크기 1 + 6 + 600 + 175 = 782 워드 — 패딩 한계 512 보다
// 커야 '상태 도중 잘림' 을 패딩과 구분할 수 있다.
constexpr int kNumHex = 25;
constexpr int kNumNodes = kNumHex * 8;
constexpr int kNumStates = 12;
constexpr size_t kStateWords = 1 + 6 + 3 * kNumNodes + kNumHex * 7;

bool writeDeck(const std::string& path) {
    data::ControlData control;
    control.NDIM = 4;
    control.NUMNP = kNumNodes;
    control.NEL8 = kNumHex;
    control.NELT = 0;
    control.NEL4 = 0;
    control.NEL2 = 0;
    control.NV3D = 7;
    control.NV1D = 0;
    control.NV2D = 0;
    control.NUMMAT8 = 1;
    control.NMMAT = 1;
    control.IU = 1;
    control.IV = 0;
    control.IA = 0;
    control.IT = 0;
    control.NGLBV = 6;
    control.ENN = control.NEL8 * control.NV3D;
    control.NND = 3 * control.NUMNP;
    control.NARBS = 10 + control.NUMNP + control.NEL8 + 4 * control.NMMAT;

    data::Mesh mesh;
    mesh.nodes.resize(kNumNodes);
    mesh.real_node_ids.resize(kNumNodes);
    for (int i = 0; i < kNumNodes; ++i) {
        mesh.nodes[i] = {i + 1, static_cast<double>(i % 2),
                         static_cast<double>((i / 2) % 2), static_cast<double>(i / 4)};
        mesh.real_node_ids[i] = i + 1;
    }
    mesh.solids.resize(kNumHex);
    mesh.solid_parts.assign(kNumHex, 1);
    mesh.solid_materials.assign(kNumHex, 1);
    mesh.real_solid_ids.resize(kNumHex);
    for (int e = 0; e < kNumHex; ++e) {
        mesh.solids[e].id = 101 + e;
        mesh.solids[e].type = ElementType::SOLID;
        mesh.solids[e].material_id = 1;
        mesh.solids[e].node_ids.resize(8);
        for (int k = 0; k < 8; ++k) mesh.solids[e].node_ids[k] = e * 8 + k + 1;
        mesh.real_solid_ids[e] = 101 + e;
    }
    mesh.num_solids = kNumHex;
    mesh.num_shells = 0;
    mesh.num_beams = 0;
    mesh.num_thick_shells = 0;

    std::vector<data::StateData> states;
    for (int s = 0; s < kNumStates; ++s) {
        data::StateData st;
        st.time = 1e-3 * s;
        st.global_vars.assign(control.NGLBV, 0.0);
        st.node_displacements.resize(kNumNodes * 3);
        for (int i = 0; i < kNumNodes; ++i) {
            st.node_displacements[i * 3 + 0] = mesh.nodes[i].x;
            st.node_displacements[i * 3 + 1] = mesh.nodes[i].y;
            st.node_displacements[i * 3 + 2] = mesh.nodes[i].z - 0.01 * s;
        }
        st.solid_data.assign(static_cast<size_t>(control.NEL8) * control.NV3D, 0.0);
        states.push_back(std::move(st));
    }

    writer::D3plotWriter w(path);
    writer::WriterOptions opt;
    // 가족 파일 하나에 상태 3개 — 기본 파일(형상+상태 1) + d3plot01..03(3씩) + d3plot04(2)
    opt.max_file_size = 3 * kStateWords * 4 + 64;
    w.setOptions(opt);
    w.setControlData(control);
    w.setMesh(mesh);
    w.setStates(states);
    return w.write() == ErrorCode::SUCCESS;
}

size_t fileWords(const fs::path& p) { return fs::file_size(p) / 4; }

// 결과가 0,1e-3,2e-3... 순서인가
bool timesInOrder(const std::vector<double>& t) {
    for (size_t i = 0; i < t.size(); ++i)
        if (std::abs(t[i] - 1e-3 * i) > 1e-9) return false;
    return true;
}

std::vector<double> timesOf(const std::vector<data::StateData>& states) {
    std::vector<double> t;
    for (const auto& s : states) t.push_back(s.time);
    return t;
}

// 세 경로(순차·병렬·상태 수 훑기)를 같은 기대값으로 본다.
// expect_states < 0 이면 예외를 기대한다.
void checkAllPaths(const std::string& label, const std::string& d3plot, int expect_states) {
    struct Path {
        const char* name;
        std::function<std::vector<double>(D3plotReader&)> run;
    };
    const std::vector<Path> paths = {
        {"순차", [](D3plotReader& r) { return timesOf(r.read_all_states()); }},
        {"병렬(1)", [](D3plotReader& r) { return timesOf(r.read_all_states_parallel(1)); }},
        {"병렬(2)", [](D3plotReader& r) { return timesOf(r.read_all_states_parallel(2)); }},
        {"병렬(기본)", [](D3plotReader& r) { return timesOf(r.read_all_states_parallel()); }},
        {"상태 수 훑기", [](D3plotReader& r) { return r.get_time_values(); }},
        {"하나씩(for_each_state)", [](D3plotReader& r) {
             std::vector<double> t;
             r.for_each_state([&](size_t, const data::StateData& s) { t.push_back(s.time); });
             return t;
         }},
    };
    for (const auto& p : paths) {
        D3plotReader reader(d3plot);
        if (reader.open() != ErrorCode::SUCCESS) {
            checkTrue(label + " / " + p.name + ": open", false);
            continue;
        }
        std::string err;
        std::vector<double> t;
        try {
            t = p.run(reader);
        } catch (const std::exception& e) {
            err = e.what();
        }
        if (expect_states < 0) {
            checkTrue(label + " / " + p.name + ": 예외 (" +
                          (err.empty() ? "없음 — " + std::to_string(t.size()) + " 상태를 성공으로 돌려줌"
                                       : err.substr(0, 90)) + ")",
                      !err.empty());
        } else {
            checkTrue(label + " / " + p.name + ": " + std::to_string(expect_states) +
                          " 상태, 시간 순서 (got " + std::to_string(t.size()) +
                          (err.empty() ? "" : ", 예외 " + err.substr(0, 60)) + ")",
                      err.empty() && static_cast<int>(t.size()) == expect_states && timesInOrder(t));
        }
    }
}

fs::path freshCopy(const fs::path& src_dir, const fs::path& root, const std::string& name) {
    fs::path dst = root / name;
    fs::remove_all(dst);
    fs::create_directories(dst);
    for (const auto& e : fs::directory_iterator(src_dir))
        fs::copy_file(e.path(), dst / e.path().filename());
    return dst;
}

}  // namespace

int main() {
    const fs::path root = fs::temp_directory_path() / ("kood3plot_family_test_" + std::to_string(getpid()));
    fs::remove_all(root);
    fs::create_directories(root / "src");
    const std::string base = (root / "src" / "d3plot").string();
    if (!writeDeck(base)) {
        std::printf("[FAIL] 합성 덱을 쓰지 못했다\n");
        return 1;
    }

    // 전제: 가족 파일 5개(d3plot + 01..04), 중간 파일은 상태 3개 꼭 맞게
    std::printf("[전제] 합성 덱 구성\n");
    checkTrue("d3plot04 까지 있고 05 는 없다",
              fs::exists(base + "04") && !fs::exists(base + "05"));
    checkTrue("d3plot02 가 상태 3개 꼭 맞는 크기",
              fileWords(base + "02") == 3 * kStateWords);

    std::printf("[1] 온전한 덱\n");
    checkAllPaths("온전", base, kNumStates);

    std::printf("[1b] 하나씩 읽기 솎기 — 3개마다(파일 경계를 넘는다)\n");
    {
        D3plotReader reader(base);
        reader.open();
        std::vector<size_t> idx;
        std::vector<double> t;
        const size_t total = reader.for_each_state(
            [&](size_t i, const data::StateData& s) { idx.push_back(i); t.push_back(s.time); },
            [](size_t i) { return i % 3 == 0; });
        bool ok = total == kNumStates && idx == std::vector<size_t>{0, 3, 6, 9};
        for (size_t k = 0; ok && k < idx.size(); ++k) ok = std::abs(t[k] - 1e-3 * idx[k]) < 1e-9;
        checkTrue("전체 12, 고른 번호 0·3·6·9 와 그 시각", ok);
    }

    std::printf("[2] 중간 가족 파일(d3plot02) 이 상태 도중 잘림\n");
    {
        fs::path d = freshCopy(root / "src", root, "trunc_mid");
        fs::resize_file(d / "d3plot02", (2 * kStateWords + 600) * 4);
        checkAllPaths("중간 잘림", (d / "d3plot").string(), -1);
    }

    std::printf("[3] 마지막 가족 파일(d3plot04) 이 상태 도중 잘림 — 앞 상태는 온전\n");
    {
        fs::path d = freshCopy(root / "src", root, "trunc_last");
        fs::resize_file(d / "d3plot04", (1 * kStateWords + 600) * 4);
        checkAllPaths("마지막 잘림", (d / "d3plot").string(), kNumStates - 1);
    }

    std::printf("[4] 중간 가족 파일(d3plot02) 누락 — 번호 구멍\n");
    {
        fs::path d = freshCopy(root / "src", root, "gap");
        fs::remove(d / "d3plot02");
        checkAllPaths("구멍", (d / "d3plot").string(), -1);
    }

    std::printf("[5] 중간 가족 파일(d3plot03) 을 열 수 없음\n");
    {
        fs::path d = freshCopy(root / "src", root, "noperm");
        fs::permissions(d / "d3plot03", fs::perms::none);
        if (FILE* f = std::fopen((d / "d3plot03").c_str(), "rb")) {
            std::fclose(f);
            std::printf("  [SKIP] 권한을 막아도 열린다(root?) — 건너뜀\n");
        } else {
            checkAllPaths("열기 실패", (d / "d3plot").string(), -1);
        }
        fs::permissions(d / "d3plot03", fs::perms::owner_all);
    }

    std::printf("[6] 스레드를 더 띄울 수 없는 환경 (RLIMIT_NPROC=1) — 병렬 읽기\n");
    {
        std::fflush(stdout);   // 자식이 버퍼를 물려받아 앞 출력을 한 번 더 찍지 않게
        pid_t pid = fork();
        if (pid == 0) {
            struct rlimit rl{1, 1};
            setrlimit(RLIMIT_NPROC, &rl);
            int code = 0;
            try {
                D3plotReader reader(base);
                if (reader.open() != ErrorCode::SUCCESS) _exit(3);
                auto t = timesOf(reader.read_all_states_parallel(4));
                code = (static_cast<int>(t.size()) == kNumStates && timesInOrder(t)) ? 0 : 1;
            } catch (const std::exception& e) {
                std::printf("  자식: 예외 %s\n", e.what());
                code = 2;
            }
            std::fflush(stdout);
            _exit(code);
        }
        int status = 0;
        waitpid(pid, &status, 0);
        const bool ok = WIFEXITED(status) && WEXITSTATUS(status) == 0;
        checkTrue(std::string("호출 스레드만으로 12 상태를 다 읽음 (자식 종료 ") +
                      (WIFEXITED(status) ? "코드 " + std::to_string(WEXITSTATUS(status))
                                         : "신호 " + std::to_string(WTERMSIG(status))) + ")",
                  ok);
    }

    fs::remove_all(root);
    std::printf("\n%s (%d failed)\n", g_failed ? "FAILED" : "PASSED", g_failed);
    return g_failed ? 1 : 0;
}
