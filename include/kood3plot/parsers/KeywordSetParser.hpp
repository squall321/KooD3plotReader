// LS-DYNA 키워드 파일의 *SET_PART/NODE/SEGMENT 정의를 읽는 파서 (Custom Report 의 입력)
/**
 * @file KeywordSetParser.hpp
 * @brief *SET_ 계열 키워드 파싱
 *
 * Custom Report 는 d3plot 외에 LS-DYNA 포맷으로 정의된 세트(파트셋·노드셋·
 * 세그먼트셋)를 받아 그 세트 기준으로 후처리한다. 이 파서가 그 입구다.
 *
 * 지원 변형
 *   *SET_PART / _LIST / _LIST_TITLE / _LIST_GENERATE / _COLUMN
 *   *SET_NODE / _LIST / _LIST_TITLE / _LIST_GENERATE / _COLUMN / _GENERAL(NODE 행만)
 *   *SET_SEGMENT / _TITLE
 * 미지원 변형(_ADD, GENERAL 의 BOX/PART 행 등)은 **무음 스킵하지 않고**
 * warnings 에 사유를 남긴다. *INCLUDE 는 따라가지 않는다(warnings 기록).
 *
 * 포맷 관용
 *   · '$' 주석, 대소문자 무시, *END 이후 무시
 *   · 고정 10칸 카드와 콤마 자유 포맷 모두 허용 (콤마/공백 토큰화)
 */

#pragma once

#include <cstdint>
#include <string>
#include <vector>

namespace kood3plot {
namespace parsers {

/// 파싱된 세트 하나
struct KeywordSet {
    enum class Kind { PART, NODE, SEGMENT };

    Kind kind = Kind::PART;
    int32_t sid = 0;          ///< 세트 ID (카드 1 의 첫 필드)
    std::string title;        ///< _TITLE 변형일 때만 채워짐

    /// PART/NODE 세트의 멤버 ID (등장 순서 유지, 중복 제거)
    std::vector<int32_t> ids;

    /// SEGMENT 세트의 세그먼트 (4절점, 삼각형이면 n[3]==n[2])
    struct Segment {
        int32_t n[4] = {0, 0, 0, 0};
    };
    std::vector<Segment> segments;
};

/// 파일 하나의 파싱 결과
struct KeywordSetParseResult {
    bool ok = false;                    ///< 파일을 열어 끝까지 읽었는가
    std::string error;                  ///< ok=false 일 때 사유
    std::vector<KeywordSet> sets;
    std::vector<std::string> warnings;  ///< 미지원 변형·이상 카드 등 (무음 금지)

    /// kind+sid 로 세트 찾기. 없으면 nullptr.
    const KeywordSet* find(KeywordSet::Kind kind, int32_t sid) const {
        for (const auto& s : sets) {
            if (s.kind == kind && s.sid == sid) return &s;
        }
        return nullptr;
    }
};

/// 키워드 파일에서 *SET_ 정의를 전부 읽는다.
KeywordSetParseResult parseKeywordSetFile(const std::string& path);

/// "part"/"node"/"segment" 문자열 → Kind. 실패 시 false.
bool setKindFromString(const std::string& s, KeywordSet::Kind& out);

/// Kind → 표기 문자열
const char* setKindName(KeywordSet::Kind k);

} // namespace parsers
} // namespace kood3plot
