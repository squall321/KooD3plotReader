// *SET_ 파서를 손으로 만든 픽스처와 대조하는 테스트 (변형·포맷 관용·경고 경로)
/**
 * @file test_keyword_set_parser.cpp
 * @brief KeywordSetParser 검증
 *
 * Run: ./test_keyword_set_parser
 */

#include "kood3plot/parsers/KeywordSetParser.hpp"

#include <cstdio>
#include <filesystem>
#include <fstream>
#include <string>

using namespace kood3plot::parsers;

namespace {

int g_failed = 0;

void check(const char* what, long got, long want) {
    const bool ok = (got == want);
    if (!ok) ++g_failed;
    std::printf("  %s %-46s got=%ld want=%ld\n", ok ? "[OK]  " : "[FAIL]", what, got, want);
}

void checkTrue(const char* what, bool cond) {
    if (!cond) ++g_failed;
    std::printf("  %s %s\n", cond ? "[OK]  " : "[FAIL]", what);
}

const char* kFixture = R"(*KEYWORD
$ 주석은 무시되어야 한다
*SET_PART_LIST_TITLE
PKG 파트들
         1
         2         3         5         0
         3
*SET_PART_LIST
        10
       100       200
*set_node_list_generate
        20
         1        10        50        52
*SET_SEGMENT_TITLE
bottom faces
        30
         1         2         3         4
         5         6         7
*SET_NODE_LIST
40
7, 8, 9
*SET_PART_ADD
        77
         1         2
*SET_NODE_GENERAL
        60
NODE         11        12
BOX           1
*SET_PART_COLUMN
        70
       501       1.0       2.0
       502       1.0       2.0
*END
*SET_PART_LIST
        99
         9
)";

}  // namespace

int main() {
    std::printf("=== KeywordSetParser 검증 ===\n\n");

    namespace fs = std::filesystem;
    const fs::path dir = fs::temp_directory_path() / "kood3plot_set_test";
    fs::create_directories(dir);
    const std::string path = (dir / "sets.k").string();
    {
        std::ofstream f(path);
        f << kFixture;
    }

    auto r = parseKeywordSetFile(path);
    checkTrue("파일 파싱 ok", r.ok);
    // 유효 세트 = 1, 10, 20, 30, 40, 60, 70 의 7개 (_ADD 77 스킵, *END 뒤 99 제외)
    check("세트 수", static_cast<long>(r.sets.size()), 7);

    // 1) PART_LIST_TITLE — 제목, 중복 제거, 0 패딩 무시
    const auto* s1 = r.find(KeywordSet::Kind::PART, 1);
    checkTrue("SET_PART 1 존재", s1 != nullptr);
    if (s1) {
        checkTrue("제목 = 'PKG 파트들'", s1->title == "PKG 파트들");
        check("PART 1 멤버 수 (2,3,5 — 중복 3 제거)", static_cast<long>(s1->ids.size()), 3);
        checkTrue("멤버 순서 [2,3,5]",
                  s1->ids.size() == 3 && s1->ids[0] == 2 && s1->ids[1] == 3 && s1->ids[2] == 5);
    }

    // 2) 무제 PART_LIST
    const auto* s10 = r.find(KeywordSet::Kind::PART, 10);
    checkTrue("SET_PART 10 존재", s10 != nullptr);
    if (s10) {
        checkTrue("제목 없음", s10->title.empty());
        checkTrue("멤버 [100,200]",
                  s10->ids.size() == 2 && s10->ids[0] == 100 && s10->ids[1] == 200);
    }

    // 3) NODE GENERATE (소문자 키워드) — 1..10 + 50..52
    const auto* s20 = r.find(KeywordSet::Kind::NODE, 20);
    checkTrue("SET_NODE 20 존재 (소문자 키워드)", s20 != nullptr);
    if (s20) {
        check("GENERATE 전개 수 (10+3)", static_cast<long>(s20->ids.size()), 13);
        checkTrue("첫/끝 = 1, 52", s20->ids.front() == 1 && s20->ids.back() == 52);
    }

    // 4) SEGMENT — 두 번째는 3절점 카드 → n4=n3 삼각형 관례
    const auto* s30 = r.find(KeywordSet::Kind::SEGMENT, 30);
    checkTrue("SET_SEGMENT 30 존재", s30 != nullptr);
    if (s30) {
        check("세그먼트 수", static_cast<long>(s30->segments.size()), 2);
        if (s30->segments.size() == 2) {
            const auto& a = s30->segments[0];
            const auto& b = s30->segments[1];
            checkTrue("seg0 = 1,2,3,4", a.n[0] == 1 && a.n[1] == 2 && a.n[2] == 3 && a.n[3] == 4);
            checkTrue("seg1 삼각형 n4==n3 (=7)", b.n[2] == 7 && b.n[3] == 7);
        }
    }

    // 5) 콤마 자유 포맷
    const auto* s40 = r.find(KeywordSet::Kind::NODE, 40);
    checkTrue("SET_NODE 40 존재 (콤마 포맷)", s40 != nullptr);
    if (s40) {
        checkTrue("멤버 [7,8,9]",
                  s40->ids.size() == 3 && s40->ids[0] == 7 && s40->ids[2] == 9);
    }

    // 6) GENERAL — NODE 행은 읽고 BOX 행은 경고
    const auto* s60 = r.find(KeywordSet::Kind::NODE, 60);
    checkTrue("SET_NODE_GENERAL 60 존재", s60 != nullptr);
    if (s60) {
        checkTrue("NODE 행 멤버 [11,12]",
                  s60->ids.size() == 2 && s60->ids[0] == 11 && s60->ids[1] == 12);
    }

    // 7) COLUMN — 줄당 첫 토큰만
    const auto* s70 = r.find(KeywordSet::Kind::PART, 70);
    checkTrue("SET_PART_COLUMN 70 존재", s70 != nullptr);
    if (s70) {
        checkTrue("멤버 [501,502] (뒤 실수 컬럼 무시)",
                  s70->ids.size() == 2 && s70->ids[0] == 501 && s70->ids[1] == 502);
    }

    // 8) 미지원(_ADD)·GENERAL BOX 는 무음이 아니라 경고
    bool warn_add = false, warn_box = false;
    for (const auto& w : r.warnings) {
        if (w.find("_ADD") != std::string::npos) warn_add = true;
        if (w.find("BOX") != std::string::npos) warn_box = true;
    }
    checkTrue("_ADD 스킵 경고 존재", warn_add);
    checkTrue("GENERAL BOX 스킵 경고 존재", warn_box);

    // 9) *END 이후는 무시
    checkTrue("SID 99 (＊END 뒤) 는 없음", r.find(KeywordSet::Kind::PART, 99) == nullptr);

    // 10) 없는 파일은 ok=false + 사유
    auto bad = parseKeywordSetFile((dir / "no_such.k").string());
    checkTrue("없는 파일 ok=false", !bad.ok);
    checkTrue("사유 존재", !bad.error.empty());

    fs::remove_all(dir);

    std::printf("\n");
    if (g_failed) {
        std::printf("%d건 실패\n", g_failed);
        return 1;
    }
    std::printf("전부 통과\n");
    return 0;
}
