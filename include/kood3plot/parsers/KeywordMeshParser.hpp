// LS-DYNA 키워드(.k) 파일에서 절점·요소(솔리드/셸/두께셸)만 읽는 경량 메시 파서
#pragma once

#include <cstdint>
#include <string>
#include <vector>
#include <array>

namespace kood3plot {
namespace parsers {

/// 키워드 파일에서 읽은 기하 — 자세 미리보기(STL) 용도. 재료·경계조건은 읽지 않는다.
struct KeywordMesh {
    struct Node { int32_t id; double x, y, z; };
    struct Elem { int32_t id; int32_t pid; std::array<int32_t, 8> n; int nn; };  // nn = 유효 절점 수

    std::vector<Node> nodes;
    std::vector<Elem> solids;     // 8절점 (축퇴 허용)
    std::vector<Elem> shells;     // 3/4절점
    std::vector<Elem> tshells;    // 8절점
    std::vector<std::string> warnings;
    bool ok = false;
    std::string error;
};

/// *NODE / *ELEMENT_SOLID / *ELEMENT_SHELL / *ELEMENT_TSHELL / *INCLUDE 를 읽는다.
/// 콤마·고정폭(표준/LONG) 모두 지원. *INCLUDE 는 파일 기준 상대경로로 따라간다(깊이 8).
KeywordMesh parseKeywordMesh(const std::string& path);

}  // namespace parsers
}  // namespace kood3plot
