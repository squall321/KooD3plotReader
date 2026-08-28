// LS-DYNA 키워드 메시 파서 구현 — 자세 미리보기용 절점/요소 읽기
#include "kood3plot/parsers/KeywordMeshParser.hpp"

#include <fstream>
#include <sstream>
#include <algorithm>
#include <cctype>
#include <filesystem>

namespace kood3plot {
namespace parsers {

namespace {

std::string trim(const std::string& s) {
    size_t a = 0, b = s.size();
    while (a < b && std::isspace(static_cast<unsigned char>(s[a]))) ++a;
    while (b > a && std::isspace(static_cast<unsigned char>(s[b - 1]))) --b;
    return s.substr(a, b - a);
}

std::string upper(std::string s) {
    for (auto& c : s) c = static_cast<char>(std::toupper(static_cast<unsigned char>(c)));
    return s;
}

/// 콤마 형식이면 콤마로, 아니면 고정폭(width)으로 자른다. 빈 필드는 "" 로 남긴다.
std::vector<std::string> fields(const std::string& line, int width) {
    std::vector<std::string> out;
    if (line.find(',') != std::string::npos) {
        std::stringstream ss(line);
        std::string tok;
        while (std::getline(ss, tok, ',')) out.push_back(trim(tok));
        return out;
    }
    for (size_t pos = 0; pos < line.size(); pos += static_cast<size_t>(width)) {
        out.push_back(trim(line.substr(pos, static_cast<size_t>(width))));
    }
    return out;
}

bool toInt(const std::string& s, int32_t& v) {
    if (s.empty()) return false;
    try {
        size_t used = 0;
        long x = std::stol(s, &used);
        if (used != s.size()) return false;
        v = static_cast<int32_t>(x);
        return true;
    } catch (...) { return false; }
}

bool toDouble(const std::string& s, double& v) {
    if (s.empty()) return false;
    try {
        size_t used = 0;
        v = std::stod(s, &used);
        return used == s.size();
    } catch (...) { return false; }
}

struct Ctx {
    KeywordMesh& m;
    int depth;
};

void parseFile(const std::string& path, Ctx& ctx);

void parseStream(std::istream& in, const std::string& self_path, Ctx& ctx) {
    enum Block { NONE, NODE, SOLID, SHELL, TSHELL, INCLUDE, OTHER };
    Block blk = NONE;
    bool long_fmt = false;      // *KEYWORD LONG=Y 또는 카드 헤더 '+'
    int iw = 8, fw = 16;        // 정수/실수 필드 폭
    std::string line;
    size_t line_no = 0;
    // 2줄형 솔리드: 첫 줄 (eid,pid) 후 둘째 줄 절점
    bool pending = false;
    KeywordMesh::Elem pend{};
    // 고차 요소(카드2 에 절점 9개 이상) 보류 — 10절점 사면체와 20절점 헥사를
    // 구분하려면 다음 줄이 연속 카드인지 봐야 한다. 한 줄 예견으로 판정한다.
    bool hi_pending = false;
    KeywordMesh::Elem hi_e{};
    int32_t hi_raw[10] = {0};
    int hi_rn = 0;
    Block hi_blk = SOLID;
    size_t hi_line = 0;

    auto setWidths = [&](bool lf) {
        iw = lf ? 10 : 8;
        fw = lf ? 20 : 16;
    };

    // 보류된 고차 요소를 확정한다. is_cont=true 면 뒤에 연속 카드가 더 있다는
    // 뜻이라 20절점 헥사 계열 — 앞 8개가 진짜 코너다. false 면 카드2 로 끝나는
    // 10절점 사면체 — 앞 4개만 코너이고 5~10 은 중간절점이라 버려야 한다.
    // (앞 8개를 헥사로 읽으면 표면 체적이 8배 틀어진다)
    auto flushHi = [&](bool is_cont) {
        if (!hi_pending) return;
        hi_pending = false;
        if (!is_cont && hi_rn == 10) {
            for (int k = 0; k < 4; ++k) hi_e.n[k] = hi_raw[k];
            for (int k = 4; k < 8; ++k) hi_e.n[k] = hi_raw[3];
            hi_e.nn = 8;
            ctx.m.warnings.push_back("10절점 사면체를 코너 4절점으로 축약 (" +
                                     self_path + ":" + std::to_string(hi_line) + ")");
        } else {
            for (int k = 0; k < 8; ++k) hi_e.n[k] = hi_raw[k];
            hi_e.nn = 8;
            ctx.m.warnings.push_back("고차 솔리드의 앞 8절점을 코너로 사용 (" +
                                     self_path + ":" + std::to_string(hi_line) + ")");
        }
        (hi_blk == SOLID ? ctx.m.solids : ctx.m.tshells).push_back(hi_e);
    };

    while (std::getline(in, line)) {
        ++line_no;
        if (!line.empty() && line.back() == '\r') line.pop_back();
        const std::string t = trim(line);
        if (t.empty() || t[0] == '$') continue;

        if (hi_pending) {
            bool is_cont = false;
            if (t[0] != '*') {
                auto fc = fields(line, iw);
                while (!fc.empty() && fc.back().empty()) fc.pop_back();
                int cnt = 0;
                for (const auto& x : fc) { int32_t v; if (toInt(x, v) && v > 0) ++cnt; }
                is_cont = (cnt >= 3);   // 새 요소의 카드1 은 (eid,pid) 2개뿐이다
            }
            flushHi(is_cont);
            if (is_cont) continue;      // 연속 카드는 소비하고 넘어간다
        }

        if (t[0] == '*') {
            const std::string kw = upper(t);
            pending = false;
            if (kw.rfind("*END", 0) == 0) break;
            if (kw.rfind("*KEYWORD", 0) == 0) {
                if (kw.find("LONG=Y") != std::string::npos) { long_fmt = true; setWidths(true); }
                blk = NONE;
                continue;
            }
            const bool plus = (!kw.empty() && kw.back() == '+');
            setWidths(long_fmt || plus);
            if (kw.rfind("*NODE", 0) == 0)              blk = NODE;
            else if (kw.rfind("*ELEMENT_SOLID", 0) == 0) blk = SOLID;
            else if (kw.rfind("*ELEMENT_TSHELL", 0) == 0) blk = TSHELL;
            else if (kw.rfind("*ELEMENT_SHELL", 0) == 0) blk = SHELL;
            else if (kw.rfind("*INCLUDE", 0) == 0)       blk = INCLUDE;
            else blk = OTHER;
            continue;
        }

        switch (blk) {
        case NODE: {
            // nid(iw) x(fw) y(fw) z(fw) — 콤마 형식이면 순서만 같음
            std::vector<std::string> f;
            if (line.find(',') != std::string::npos) {
                f = fields(line, iw);
            } else {
                f.push_back(trim(line.substr(0, static_cast<size_t>(iw))));
                for (int k = 0; k < 3; ++k) {
                    const size_t pos = static_cast<size_t>(iw + k * fw);
                    f.push_back(pos < line.size() ? trim(line.substr(pos, static_cast<size_t>(fw))) : "");
                }
            }
            KeywordMesh::Node n{};
            if (f.size() < 4 || !toInt(f[0], n.id) || !toDouble(f[1], n.x) ||
                !toDouble(f[2], n.y) || !toDouble(f[3], n.z)) {
                ctx.m.warnings.push_back("*NODE 파싱 실패 (" + self_path + ":" + std::to_string(line_no) + ")");
                continue;
            }
            ctx.m.nodes.push_back(n);
            break;
        }
        case SOLID:
        case TSHELL:
        case SHELL: {
            auto f = fields(line, iw);
            // 뒤쪽 빈 필드 제거
            while (!f.empty() && f.back().empty()) f.pop_back();
            if (pending) {
                // 2줄형 둘째 줄: LS-DYNA 는 여기에 절점을 최대 10개까지 담는다.
                // 앞 8개만 읽으면 10절점 사면체(코너4+중간6)를 헥사로 오해해
                // 표면 체적이 8배 틀어진다 — 10개까지 읽고 차수를 판정한다.
                int32_t raw[10] = {0};
                int rn = 0;
                for (size_t k = 0; k < f.size() && rn < 10; ++k) {
                    int32_t v;
                    if (toInt(f[k], v) && v > 0) raw[rn++] = v;
                }
                if (rn > 8) {
                    hi_e = pend; hi_rn = rn; hi_blk = blk; hi_line = line_no;
                    for (int k = 0; k < rn && k < 10; ++k) hi_raw[k] = raw[k];
                    hi_pending = true;
                    pending = false;
                    break;                  // 다음 줄을 보고 차수를 판정한다
                }
                int nn = 0;
                for (int k = 0; k < rn; ++k) pend.n[nn++] = raw[k];
                pend.nn = nn;
                if (nn >= 4) (blk == SOLID ? ctx.m.solids : ctx.m.tshells).push_back(pend);
                else ctx.m.warnings.push_back("2줄형 요소의 절점 부족 (" + self_path + ":" + std::to_string(line_no) + ")");
                pending = false;
                break;
            }
            KeywordMesh::Elem e{};
            e.n.fill(0);
            int32_t eid, pid;
            if (f.size() < 2 || !toInt(f[0], eid) || !toInt(f[1], pid)) {
                ctx.m.warnings.push_back("*ELEMENT 파싱 실패 (" + self_path + ":" + std::to_string(line_no) + ")");
                break;
            }
            e.id = eid; e.pid = pid;
            if (f.size() == 2 && blk != SHELL) {
                // 2줄형 (eid pid / n1..n8)
                pend = e;
                pending = true;
                break;
            }
            int nn = 0;
            const int maxn = (blk == SHELL) ? 4 : 8;
            for (size_t k = 2; k < f.size() && nn < maxn; ++k) {
                int32_t v;
                if (!toInt(f[k], v)) break;
                if (v > 0) e.n[nn++] = v;
            }
            e.nn = nn;
            if (blk == SHELL) {
                if (nn >= 3) ctx.m.shells.push_back(e);
            } else {
                if (nn >= 4) (blk == SOLID ? ctx.m.solids : ctx.m.tshells).push_back(e);
            }
            break;
        }
        case INCLUDE: {
            if (ctx.depth >= 8) {
                ctx.m.warnings.push_back("*INCLUDE 깊이 초과, 무시: " + t);
                break;
            }
            namespace fs = std::filesystem;
            fs::path inc(t);
            if (inc.is_relative()) inc = fs::path(self_path).parent_path() / inc;
            if (!fs::exists(inc)) {
                ctx.m.warnings.push_back("*INCLUDE 파일 없음: " + inc.string());
                break;
            }
            Ctx sub{ctx.m, ctx.depth + 1};
            parseFile(inc.string(), sub);
            break;
        }
        default:
            break;
        }
    }
    flushHi(false);   // 파일 끝(또는 *END)에 걸린 보류 요소 확정
}

void parseFile(const std::string& path, Ctx& ctx) {
    std::ifstream in(path);
    if (!in) {
        ctx.m.warnings.push_back("파일 열기 실패: " + path);
        return;
    }
    parseStream(in, path, ctx);
}

}  // namespace

KeywordMesh parseKeywordMesh(const std::string& path) {
    KeywordMesh m;
    std::ifstream probe(path);
    if (!probe) {
        m.error = "파일 열기 실패: " + path;
        return m;
    }
    probe.close();
    Ctx ctx{m, 0};
    parseFile(path, ctx);
    if (m.nodes.empty()) {
        m.error = "*NODE 가 없음: " + path;
        return m;
    }
    if (m.solids.empty() && m.shells.empty() && m.tshells.empty()) {
        m.error = "*ELEMENT_SOLID/SHELL/TSHELL 이 없음: " + path;
        return m;
    }
    m.ok = true;
    return m;
}

}  // namespace parsers
}  // namespace kood3plot
