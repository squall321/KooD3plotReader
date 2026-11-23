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

/// LS-DYNA 고정폭(10칸) 카드 — LS-PrePost 가 쓰는 꼴. 첫 카드의 DA1..DA4 가 칸 사이 공백 없이 붙는다(erode7 DropSet.k).
/// 칸에 맞지 않게 공백 · 탭으로만 나눈 옛 꼴도 계속 받는다.
const char* kFixedFixture =
    "*KEYWORD\n"
    "*SET_NODE_LIST\n"
    "$$     NID       da1       da2       da3       da4    SOLVER       ITS\n"
    "         10.0000e+000.0000e+000.0000e+000.0000e+00      MECH         0\n"
    "$$    NIDi    NIDi+1    NIDi+2    NIDi+3    NIDi+4    NIDi+5    NIDi+6    NIDi+7\n"
    "     11946     11947     11948\n"
    "*SET_PART_LIST\n"
    "        500.0000e+000.0000e+000.0000e+000.0000e+00\n"
    "         7         8\n"
    "*SET_SEGMENT_TITLE\n"
    "                                                                     SegmentSet3\n"
    "         30.0000e+000.0000e+000.0000e+000.0000e+00      MECH         0\n"
    "        21        22        23        24\n"
    "*SET_NODE_LIST\n"
    "        61\n"
    "10000000011000000002\n"
    "*SET_NODE_LIST\n"
    "80\n"
    "1 2 3 4\n"
    "*SET_NODE_LIST\n"
    "        81\n"
    "5\t6\t7\n"
    "*END\n";

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

    // 11) 고정폭 카드 — 칸 사이 공백 없이 붙은 첫 카드 · 10자리 ID 가 붙은 줄, 그리고 칸에 맞지 않는 공백 · 탭 구분
    {
        const std::string fixed = (dir / "fixed.k").string();
        {
            std::ofstream f(fixed);
            f << kFixedFixture;
        }
        auto q = parseKeywordSetFile(fixed);
        checkTrue("고정폭 파일 파싱 ok", q.ok);
        const auto* n1 = q.find(KeywordSet::Kind::NODE, 1);
        checkTrue("SET_NODE 1 존재 (첫 카드가 붙어 있다)", n1 != nullptr);
        if (n1) {
            checkTrue("멤버 [11946,11947,11948]",
                      n1->ids.size() == 3 && n1->ids[0] == 11946 && n1->ids[2] == 11948);
        }
        const auto* p50 = q.find(KeywordSet::Kind::PART, 50);
        checkTrue("SET_PART 50 존재 (첫 카드가 붙어 있다)", p50 != nullptr);
        if (p50) checkTrue("멤버 [7,8]", p50->ids.size() == 2 && p50->ids[0] == 7 && p50->ids[1] == 8);
        const auto* g3 = q.find(KeywordSet::Kind::SEGMENT, 3);
        checkTrue("SET_SEGMENT 3 존재 (제목 다음 첫 카드가 붙어 있다)", g3 != nullptr);
        if (g3) {
            checkTrue("제목 = 'SegmentSet3'", g3->title == "SegmentSet3");
            checkTrue("세그먼트 21,22,23,24", g3->segments.size() == 1 && g3->segments[0].n[0] == 21 &&
                                                   g3->segments[0].n[3] == 24);
        }
        const auto* n61 = q.find(KeywordSet::Kind::NODE, 61);
        checkTrue("SET_NODE 61 — 10자리 ID 두 칸이 붙은 줄", n61 != nullptr && n61->ids.size() == 2 &&
                                                               n61->ids[0] == 1000000001 && n61->ids[1] == 1000000002);
        const auto* n80 = q.find(KeywordSet::Kind::NODE, 80);
        checkTrue("SET_NODE 80 — 칸에 맞지 않는 공백 구분 [1,2,3,4]",
                  n80 != nullptr && n80->ids.size() == 4 && n80->ids[0] == 1 && n80->ids[3] == 4);
        const auto* n81 = q.find(KeywordSet::Kind::NODE, 81);
        checkTrue("SET_NODE 81 — 탭 구분 [5,6,7]",
                  n81 != nullptr && n81->ids.size() == 3 && n81->ids[0] == 5 && n81->ids[2] == 7);
        bool sid_warn = false;
        for (const auto& w : q.warnings) sid_warn = sid_warn || w.find("SID 파싱 실패") != std::string::npos;
        checkTrue("SID 파싱 실패 경고 없음", !sid_warn);
    }

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
