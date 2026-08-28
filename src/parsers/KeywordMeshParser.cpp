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

    auto setWidths = [&](bool lf) {
        iw = lf ? 10 : 8;
        fw = lf ? 20 : 16;
    };

    while (std::getline(in, line)) {
        ++line_no;
        if (!line.empty() && line.back() == '\r') line.pop_back();
        const std::string t = trim(line);
        if (t.empty() || t[0] == '$') continue;

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
                int nn = 0;
                if (rn > 8) {
                    // 10절점 사면체: 코너 4개만 쓰고 축퇴 헥사로 접는다 (중간절점은 형상에 불필요)
                    for (int k = 0; k < 4; ++k) pend.n[k] = raw[k];
                    for (int k = 4; k < 8; ++k) pend.n[k] = raw[3];
                    nn = 8;
                    ctx.m.warnings.push_back("10절점 솔리드를 코너 4절점 사면체로 축약 (" +
                                             self_path + ":" + std::to_string(line_no) + ")");
                } else {
                    for (int k = 0; k < rn; ++k) pend.n[nn++] = raw[k];
                }
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
