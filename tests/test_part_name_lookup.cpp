// 파트 이름 조회(.k 선택 · *INCLUDE 추적 · *PART 변형)가 맞는지 확인하는 시험.
//
// 빌드·실행:
//   cmake --build build -j4 --target unified_analyzer
//   g++ -std=c++17 -O2 -I include tests/test_part_name_lookup.cpp \
//       build/libkood3plot.a -fopenmp -lz -o /tmp/t_partname && /tmp/t_partname
//
// 실덱: /data/battery_study/case_01_phase1_stacked_tier-1
//   *PART 카드 34개가 02_mesh_stacked_tier-1.k 에 있고, 01_main 이 *INCLUDE 로 끌어온다.
//   디렉토리 순회 첫 .k 만 읽으면 이름을 하나도 못 찾는다.
#include "kood3plot/D3plotReader.hpp"
#include "kood3plot/analysis/UnifiedAnalyzer.hpp"
#include "kood3plot/analysis/UnifiedConfigParser.hpp"
#include <cstdio>
#include <filesystem>
#include <fstream>
#include <set>
#include <string>
#include <vector>

using namespace kood3plot;
using namespace kood3plot::analysis;

namespace fs = std::filesystem;

static int fails = 0;

static void chk(const char* name, bool ok, const std::string& detail) {
    if (!ok) ++fails;
    printf("  %s %-52s %s\n", ok ? "OK " : "NG ", name, detail.c_str());
}

static std::string listOf(const std::vector<int32_t>& v) {
    std::string s = "{";
    for (size_t i = 0; i < v.size(); ++i) {
        if (i) s += ",";
        s += std::to_string(v[i]);
    }
    return s + "}";
}

int main(int argc, char** argv) {
    const std::string deck = (argc > 1)
        ? argv[1]
        : "/data/battery_study/case_01_phase1_stacked_tier-1/d3plot";

    printf("[A] 실덱 — *PART 가 *INCLUDE 안에 있어도 이름을 찾아야 한다\n");
    std::vector<int32_t> mesh_pids;
    {
        D3plotReader reader(deck);
        if (reader.open() != ErrorCode::SUCCESS) {
            printf("[SKIP] 덱을 열 수 없음: %s\n", deck.c_str());
            return 0;
        }
        auto mesh = reader.read_mesh();
        std::set<int32_t> uniq;
        for (int32_t p : mesh.solid_parts) uniq.insert(p);
        for (int32_t p : mesh.shell_parts) uniq.insert(p);
        for (int32_t p : mesh.thick_shell_parts) uniq.insert(p);
        for (int32_t p : mesh.beam_parts) uniq.insert(p);
        mesh_pids.assign(uniq.begin(), uniq.end());

        auto pouch = UnifiedConfigParser::filterPartsByPattern(reader, "Pouch*");
        chk("'Pouch*' → 파트 10,11,12", pouch == std::vector<int32_t>({10, 11, 12}),
            listOf(pouch));

        auto impactor = UnifiedConfigParser::filterPartsByPattern(reader, "Impactor*");
        chk("'Impactor*' → 파트 100", impactor == std::vector<int32_t>({100}),
            listOf(impactor));

        auto nothing = UnifiedConfigParser::filterPartsByPattern(reader, "존재하지않는이름*");
        chk("없는 이름 → 0개 (전체로 번지지 않음)", nothing.empty(), listOf(nothing));
    }

    printf("\n[B] 합성 덱 — *INCLUDE 추적 · 한 블록 다중 *PART · *PART_ 변형\n");
    if (mesh_pids.size() < 3) {
        printf("[SKIP] 파트가 3개 미만\n");
    } else {
        const fs::path dir = fs::temp_directory_path() / "kood3plot_part_name_test";
        std::error_code ec;
        fs::remove_all(dir, ec);
        fs::create_directories(dir, ec);
        fs::copy_file(deck, dir / "d3plot", fs::copy_options::overwrite_existing, ec);
        if (ec) {
            printf("[SKIP] 임시 덱 복사 실패: %s\n", ec.message().c_str());
        } else {
            const int32_t p0 = mesh_pids[0], p1 = mesh_pids[1], p2 = mesh_pids[2];

            {   // 루트 덱 — 이름은 여기 없고 *INCLUDE 안에 있다
                std::ofstream f(dir / "main.k");
                f << "*KEYWORD\n"
                  << "$ 이름은 전부 include 안에 있다\n"
                  << "*INCLUDE\n"
                  << "sub_mesh.k\n"
                  << "*CONTROL_TERMINATION\n"
                  << "     0.001\n"
                  << "*END\n";
            }
            {   // 포함 파일 — 한 *PART 블록에 파트 2개 + *PART_COMPOSITE 1개
                std::ofstream f(dir / "sub_mesh.k");
                f << "*KEYWORD\n"
                  << "*PART\n"
                  << "AlphaOne_Blk\n"
                  << "  " << p0 << "         1         1\n"
                  << "BetaTwo_Blk\n"
                  << "  " << p1 << "         1         1\n"
                  << "*PART_COMPOSITE\n"
                  << "GammaComp_Blk\n"
                  << "  " << p2 << "         2       1.0         0\n"
                  << "         1     0.100       0.0         0\n"
                  << "         2     0.100      90.0         0\n"
                  << "*END\n";
            }

            D3plotReader r2((dir / "d3plot").string());
            if (r2.open() != ErrorCode::SUCCESS) {
                printf("[SKIP] 임시 덱을 열 수 없음\n");
            } else {
                auto a = UnifiedConfigParser::filterPartsByPattern(r2, "AlphaOne*");
                chk("*INCLUDE 안의 첫 *PART", a == std::vector<int32_t>({p0}), listOf(a));

                auto b = UnifiedConfigParser::filterPartsByPattern(r2, "BetaTwo*");
                chk("한 *PART 블록의 두 번째 파트", b == std::vector<int32_t>({p1}), listOf(b));

                auto c = UnifiedConfigParser::filterPartsByPattern(r2, "GammaComp*");
                chk("*PART_COMPOSITE", c == std::vector<int32_t>({p2}), listOf(c));

                auto blk = UnifiedConfigParser::filterPartsByPattern(r2, "*_Blk");
                chk("적층 카드가 가짜 파트를 만들지 않음", blk.size() == 3,
                    listOf(blk));
            }
        }
        fs::remove_all(dir, ec);
    }

    printf("\n[C] 0매치 이름 패턴이 '전체 모델' 로 번지지 않는지 (표면 응력 잡)\n");
    {
        UnifiedConfig cfg;
        cfg.d3plot_path = deck;
        cfg.surface_defaults = false;
        cfg.verbose = false;

        AnalysisJob miss;
        miss.name = "없는파트 하면";
        miss.type = AnalysisJobType::SURFACE_STRESS;
        miss.part_pattern = "존재하지않는파트*";
        miss.surface.direction = Vec3(0, 0, -1);
        miss.surface.angle = 45.0;
        cfg.analysis_jobs.push_back(miss);

        AnalysisJob hit;
        hit.name = "Impactor 하면";
        hit.type = AnalysisJobType::SURFACE_STRESS;
        hit.part_pattern = "Impactor*";
        hit.surface.direction = Vec3(0, 0, -1);
        hit.surface.angle = 45.0;
        cfg.analysis_jobs.push_back(hit);

        UnifiedAnalyzer analyzer;
        auto res = analyzer.analyze(cfg);

        bool has_miss = false, has_hit = false;
        for (const auto& s : res.surface_analysis) {
            if (s.description == miss.name) has_miss = true;
            if (s.description == hit.name) has_hit = true;
        }
        chk("0매치 잡은 산출물을 만들지 않음", !has_miss,
            "surface_analysis " + std::to_string(res.surface_analysis.size()) + "건");
        chk("매치되는 잡은 그대로 나옴", has_hit,
            std::string(has_hit ? "있음" : "없음"));
    }

    printf("\n%s  실패 %d 건\n", fails ? "[FAIL]" : "[PASS]", fails);
    return fails ? 1 : 0;
}
