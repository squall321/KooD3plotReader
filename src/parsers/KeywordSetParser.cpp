// *SET_PART/NODE/SEGMENT 키워드 파싱 구현
/**
 * @file KeywordSetParser.cpp
 * @brief LS-DYNA *SET_ 계열 파서 구현
 */

#include "kood3plot/parsers/KeywordSetParser.hpp"

#include <algorithm>
#include <cctype>
#include <cmath>
#include <cstdlib>
#include <fstream>
#include <sstream>
#include <unordered_set>

namespace kood3plot {
namespace parsers {

namespace {

/// GENERATE 범위 전개 상한 — 이 이상은 오타/파일 손상으로 보고 경고 후 스킵
constexpr int64_t kMaxGenerateSpan = 5'000'000;

std::string upper(std::string s) {
    std::transform(s.begin(), s.end(), s.begin(),
                   [](unsigned char c) { return static_cast<char>(std::toupper(c)); });
    return s;
}

std::string trim(const std::string& s) {
    const auto b = s.find_first_not_of(" \t\r\n");
    if (b == std::string::npos) return "";
    const auto e = s.find_last_not_of(" \t\r\n");
    return s.substr(b, e - b + 1);
}

/// 콤마·공백 혼용 토큰화. 세트 카드의 필드는 공백을 품지 않으므로 안전하다.
std::vector<std::string> tokenize(const std::string& line) {
    std::vector<std::string> out;
    std::string cur;
    for (char c : line) {
        if (c == ',' || c == ' ' || c == '\t' || c == '\r' || c == '\n') {
            if (!cur.empty()) { out.push_back(cur); cur.clear(); }
        } else {
            cur.push_back(c);
        }
    }
    if (!cur.empty()) out.push_back(cur);
    return out;
}

/// 정수 파싱. LS-DYNA 카드는 "1.0" 처럼 실수 표기의 정수도 허용한다.
bool parseInt(const std::string& tok, int32_t& out) {
    if (tok.empty()) return false;
    char* end = nullptr;
    const double v = std::strtod(tok.c_str(), &end);
    if (end == tok.c_str() || *end != '\0') return false;
    const double r = std::llround(v);
    if (r != v && std::abs(r - v) > 1e-9) return false;   // 진짜 소수는 ID 가 아니다
    out = static_cast<int32_t>(r);
    return true;
}

struct Variant {
    KeywordSet::Kind kind;
    bool title = false;
    bool generate = false;
    bool general = false;
    bool column = false;
    bool add = false;
};

/// "*SET_..." 헤더 해석. 지원 대상이 아니면 false.
bool parseHeader(const std::string& kw_upper, Variant& v, std::string& unsupported_reason) {
    if (kw_upper.rfind("*SET_", 0) != 0) return false;
    const std::string rest = kw_upper.substr(5);

    if (rest.rfind("PART", 0) == 0) v.kind = KeywordSet::Kind::PART;
    else if (rest.rfind("NODE", 0) == 0) v.kind = KeywordSet::Kind::NODE;
    else if (rest.rfind("SEGMENT", 0) == 0) v.kind = KeywordSet::Kind::SEGMENT;
    else { unsupported_reason = "지원하지 않는 세트 종류"; return false; }

    v.title = rest.find("TITLE") != std::string::npos;
    v.generate = rest.find("GENERATE") != std::string::npos;
    v.general = rest.find("GENERAL") != std::string::npos && !v.generate;
    v.column = rest.find("COLUMN") != std::string::npos;
    v.add = rest.find("ADD") != std::string::npos;

    if (v.add) { unsupported_reason = "_ADD(세트의 세트) 는 아직 미지원"; return false; }
    if (v.kind == KeywordSet::Kind::SEGMENT && (v.generate || v.general)) {
        unsupported_reason = "SEGMENT 의 GENERATE/GENERAL 변형은 미지원";
        return false;
    }
    return true;
}

void pushUnique(std::vector<int32_t>& ids, std::unordered_set<int32_t>& seen, int32_t id) {
    if (id == 0) return;                       // 빈 필드/패딩
    if (seen.insert(id).second) ids.push_back(id);
}

}  // namespace

const char* setKindName(KeywordSet::Kind k) {
    switch (k) {
        case KeywordSet::Kind::PART: return "part";
        case KeywordSet::Kind::NODE: return "node";
        case KeywordSet::Kind::SEGMENT: return "segment";
    }
    return "unknown";
}

bool setKindFromString(const std::string& s, KeywordSet::Kind& out) {
    const std::string u = upper(trim(s));
    if (u == "PART" || u == "PART_SET" || u == "PARTSET") { out = KeywordSet::Kind::PART; return true; }
    if (u == "NODE" || u == "NODE_SET" || u == "NODESET") { out = KeywordSet::Kind::NODE; return true; }
    if (u == "SEGMENT" || u == "SEGMENT_SET" || u == "SEGMENTSET") { out = KeywordSet::Kind::SEGMENT; return true; }
    return false;
}

KeywordSetParseResult parseKeywordSetFile(const std::string& path) {
    KeywordSetParseResult res;

    std::ifstream in(path);
    if (!in) {
        res.error = "세트 파일을 열 수 없음: " + path;
        return res;
    }

    // 상태 기계: 현재 열려 있는 세트와 그 변형
    bool in_set = false;
    Variant var{};
    KeywordSet cur;
    bool need_title = false;   // _TITLE: 다음 비주석 줄이 제목
    bool need_sid = false;     // 제목 다음(또는 헤더 다음) 줄이 카드 1
    std::unordered_set<int32_t> seen;

    auto flush = [&]() {
        if (in_set) {
            if (cur.sid <= 0) {
                // 헤더만 있고 SID 카드가 없던 절단 세트 — sid=0 팬텀으로
                // '세트 N개 로드' 집계를 부풀리지 않는다
                res.warnings.push_back("SID 없이 끝난 *SET_ 헤더 — 세트 버림");
            } else {
                bool dup = false;
                for (const auto& prev : res.sets) {
                    if (prev.sid == cur.sid && prev.kind == cur.kind) { dup = true; break; }
                }
                if (dup) {
                    res.warnings.push_back("SID " + std::to_string(cur.sid) +
                                           " 중복 정의 — 첫 정의를 유지, 이후 정의 무시");
                } else {
                    res.sets.push_back(cur);
                }
            }
            cur = KeywordSet{};
            seen.clear();
            in_set = false;
        }
    };

    std::string line;
    size_t line_no = 0;
    while (std::getline(in, line)) {
        ++line_no;
        const std::string t = trim(line);
        if (t.empty() || t[0] == '$') continue;

        if (t[0] == '*') {
            const std::string kw = upper(t);
            if (kw.rfind("*END", 0) == 0) break;   // *END 이후는 무시
            flush();

            if (kw.rfind("*INCLUDE", 0) == 0) {
                res.warnings.push_back("*INCLUDE 는 따라가지 않음 (line " +
                                       std::to_string(line_no) + ")");
                continue;
            }
            if (kw.rfind("*SET_", 0) == 0) {
                Variant v{};
                std::string why;
                if (parseHeader(kw, v, why)) {
                    in_set = true;
                    var = v;
                    cur = KeywordSet{};
                    cur.kind = v.kind;
                    seen.clear();
                    need_title = v.title;
                    need_sid = true;
                } else {
                    res.warnings.push_back(kw + " 스킵 — " + why +
                                           " (line " + std::to_string(line_no) + ")");
                }
            }
            continue;   // 그 밖의 키워드는 다음 *SET_ 까지 무시
        }

        if (!in_set) continue;

        if (need_title) {
            cur.title = t;               // 제목 카드는 통째로 (토큰화 금지)
            need_title = false;
            continue;
        }

        auto toks = tokenize(t);
        if (toks.empty()) continue;

        if (need_sid) {
            int32_t sid = 0;
            if (!parseInt(toks[0], sid)) {
                res.warnings.push_back("카드 1 의 SID 파싱 실패, 세트 스킵 (line " +
                                       std::to_string(line_no) + ")");
                in_set = false;
                continue;
            }
            cur.sid = sid;
            need_sid = false;
            continue;   // DA1..DA4 등 나머지 필드는 무시
        }

        // ---- 데이터 카드 ----
        if (var.general) {
            // GENERAL: 첫 토큰이 옵션 단어. NODE 만 지원, 나머지는 경고.
            int32_t probe = 0;
            if (!parseInt(toks[0], probe)) {
                const std::string opt = upper(toks[0]);
                if (opt == "NODE") {
                    for (size_t i = 1; i < toks.size(); ++i) {
                        int32_t id;
                        if (parseInt(toks[i], id)) pushUnique(cur.ids, seen, id);
                    }
                } else {
                    res.warnings.push_back("SET_" + std::string(setKindName(cur.kind)) +
                                           "_GENERAL 의 '" + toks[0] +
                                           "' 옵션 미지원, 해당 행 스킵 (line " +
                                           std::to_string(line_no) + ")");
                }
                continue;
            }
            // 옵션 없이 숫자로 시작하면 그냥 ID 목록으로 취급
            for (const auto& tok : toks) {
                int32_t id;
                if (parseInt(tok, id)) pushUnique(cur.ids, seen, id);
            }
            continue;
        }

        if (cur.kind == KeywordSet::Kind::SEGMENT) {
            // 카드 하나 = 세그먼트 하나 (N1..N4, 이후 A1.. 은 무시)
            KeywordSet::Segment seg;
            int got = 0;
            for (size_t i = 0; i < toks.size() && got < 4; ++i) {
                int32_t id;
                if (parseInt(toks[i], id)) seg.n[got++] = id;
            }
            if (got >= 3) {
                if (seg.n[3] == 0) seg.n[3] = seg.n[2];   // 삼각형 관례
                cur.segments.push_back(seg);
            } else {
                res.warnings.push_back("세그먼트 카드에 절점이 3개 미만, 스킵 (line " +
                                       std::to_string(line_no) + ")");
            }
            continue;
        }

        if (var.generate) {
            // (BBEG, BEND) 쌍으로 소비
            std::vector<int32_t> nums;
            for (const auto& tok : toks) {
                int32_t id;
                if (parseInt(tok, id) && id != 0) nums.push_back(id);
            }
            for (size_t i = 0; i + 1 < nums.size(); i += 2) {
                const int64_t b = nums[i], e = nums[i + 1];
                if (e < b || (e - b) > kMaxGenerateSpan) {
                    res.warnings.push_back("GENERATE 범위 비정상 [" + std::to_string(b) +
                                           ", " + std::to_string(e) + "], 스킵 (line " +
                                           std::to_string(line_no) + ")");
                    continue;
                }
                for (int64_t v = b; v <= e; ++v) {
                    pushUnique(cur.ids, seen, static_cast<int32_t>(v));
                }
            }
            if (nums.size() % 2 == 1) {
                res.warnings.push_back("GENERATE 카드의 필드 수가 홀수 (line " +
                                       std::to_string(line_no) + ")");
            }
            continue;
        }

        if (var.column) {
            // 한 줄에 항목 하나: 첫 토큰만 ID
            int32_t id;
            if (parseInt(toks[0], id)) pushUnique(cur.ids, seen, id);
            continue;
        }

        // LIST (기본): 모든 토큰이 ID. 파싱 불가 토큰은 무음 폐기 대신 경고 —
        // 오타('1O3' 등)가 조용히 사라지면 세트가 부분만 실린다.
        {
            int skipped = 0;
            for (const auto& tok : toks) {
                int32_t id;
                if (parseInt(tok, id)) {
                    pushUnique(cur.ids, seen, id);
                } else {
                    ++skipped;
                }
            }
            if (skipped > 0) {
                res.warnings.push_back("ID 로 해석 불가한 토큰 " + std::to_string(skipped) +
                                       "개 무시 (line " + std::to_string(line_no) + ")");
            }
        }
    }

    flush();
    res.ok = true;
    return res;
}

} // namespace parsers
} // namespace kood3plot
