// d3plot 최외곽 요소로 근사 STL + 보고서 임베드용 경량 JSON 메시를 만드는 도구
/**
 * @file make_stl.cpp
 * @brief 모델 외곽면 → STL / JSON (자세 미리보기용)
 *
 * 전각도 낙하 보고서에서 "지금 이 각도가 어떤 자세인지"를 실제 기하로
 * 보여주기 위한 대략적 형상이 목적이다. 정밀 메시가 아니라 실루엣이면
 * 충분하므로 정점 격자 클러스터링(vertex clustering)으로 데시메이션한다.
 *
 * 사용:
 *   ./make_stl <d3plot> <out_prefix> [target_tris=6000]
 * 산출:
 *   <out_prefix>.stl   이진 STL (CAD/뷰어용)
 *   <out_prefix>.json  {"v":[x,y,z...], "f":[i,j,k...], "bbox":[...]}
 *                      — 보고서가 직접 임베드하는 경량 메시
 */

#include "kood3plot/D3plotReader.hpp"
#include "kood3plot/parsers/KeywordMeshParser.hpp"
#include "kood3plot/analysis/SurfaceExtractor.hpp"

#include <iterator>
#include <cstdlib>
#include <filesystem>
#include <cctype>
#include <cerrno>
#include <cstdio>
#include <cstdint>
#include <cstring>
#include <cmath>
#include <fstream>
#include <map>
#include <unordered_map>
#include <tuple>
#include <vector>

using namespace kood3plot;
using namespace kood3plot::analysis;

namespace {

struct V3 { double x = 0, y = 0, z = 0; };

struct MeshOut {
    std::vector<V3> verts;
    std::vector<std::array<int32_t, 3>> tris;
    std::vector<int32_t> tri_pid;   // 삼각형별 파트 ID (보고서 파트별 색용)
};


/// 파트별 bbox (device 모드 환경 파트 제외용)
struct PartBB {
    double lo[3] = {1e300, 1e300, 1e300}, hi[3] = {-1e300, -1e300, -1e300};
    bool any = false;
    void add(double x, double y, double z) {
        const double c[3] = {x, y, z};
        for (int a = 0; a < 3; ++a) { lo[a] = std::min(lo[a], c[a]); hi[a] = std::max(hi[a], c[a]); }
        any = true;
    }
};

/// 자세 미리보기는 '기기'만 보여야 한다. 낙하 덱의 바닥/벽 플레이트는 이름이
/// 없는 경우가 많아(실측: Test_006 파트 23 무명) 기하로 거른다 —
/// 혼자서 나머지 전체(합집합)보다 두 축 이상에서 1.5배 크면 환경으로 본다.
/// (기기 하우징은 합집합을 '정의'하는 쪽이라 1.5배를 넘지 못한다.)
/// 원본 키워드 파일(바닥 생성 이전)을 쓰면 보통 제외 대상이 없다.
bool selectDeviceParts(const std::map<int32_t, PartBB>& bbs, std::vector<int32_t>& only_parts) {
    only_parts.clear();
    size_t excluded = 0;
    for (const auto& [pid, b] : bbs) {
        if (!b.any) continue;
        double olo[3] = {1e300, 1e300, 1e300}, ohi[3] = {-1e300, -1e300, -1e300};
        bool others = false;
        for (const auto& [q, ob] : bbs) {
            if (q == pid || !ob.any) continue;
            others = true;
            for (int a = 0; a < 3; ++a) { olo[a] = std::min(olo[a], ob.lo[a]); ohi[a] = std::max(ohi[a], ob.hi[a]); }
        }
        if (!others) { only_parts.push_back(pid); continue; }
        int bigger = 0;
        for (int a = 0; a < 3; ++a) {
            const double mine = b.hi[a] - b.lo[a], rest = std::max(1e-9, ohi[a] - olo[a]);
            if (mine > 1.5 * rest) ++bigger;
        }
        if (bigger >= 2) {
            ++excluded;
            std::printf("환경 파트 제외: %d (%.0f x %.0f x %.0f — 나머지 합집합보다 %d축에서 1.5배 초과)\n",
                        pid, b.hi[0] - b.lo[0], b.hi[1] - b.lo[1], b.hi[2] - b.lo[2], bigger);
        } else {
            only_parts.push_back(pid);
        }
    }
    if (only_parts.empty()) {
        std::printf("device 모드: 남는 파트가 없음 — 중단\n");
        return false;
    }
    if (excluded == 0) std::printf("device 모드: 환경 파트 없음 (전 파트 %zu개 사용)\n", only_parts.size());
    return true;
}

/// 격자 해상도 res 로 정점 클러스터링 데시메이션.
MeshOut clusterDecimate(const std::vector<V3>& pts,
                        const std::vector<std::array<int32_t, 3>>& tris,
                        const std::vector<int32_t>& tri_pid,
                        const V3& bmin, const V3& bmax, int res) {
    const double ex = std::max(1e-9, bmax.x - bmin.x);
    const double ey = std::max(1e-9, bmax.y - bmin.y);
    const double ez = std::max(1e-9, bmax.z - bmin.z);
    // 등방 셀(최장축/res) — 축별 res 등분이면 얇은 기기의 두께 방향만 과분해되고
    // 넓은 면은 거칠어진다 (실측: 71×147×9 기기가 res=11 로 끝나 902 정점)
    const double cell = std::max({ex, ey, ez}) / res;

    auto cellOf = [&](const V3& p) {
        int ix = (int)((p.x - bmin.x) / cell);
        int iy = (int)((p.y - bmin.y) / cell);
        int iz = (int)((p.z - bmin.z) / cell);
        return std::tuple<int, int, int>(ix, iy, iz);
    };

    std::map<std::tuple<int, int, int>, int32_t> cell_id;
    std::vector<V3> cell_sum;
    std::vector<int> cell_cnt;
    std::vector<int32_t> remap(pts.size());

    for (size_t i = 0; i < pts.size(); ++i) {
        auto key = cellOf(pts[i]);
        auto it = cell_id.find(key);
        int32_t id;
        if (it == cell_id.end()) {
            id = (int32_t)cell_sum.size();
            cell_id[key] = id;
            cell_sum.push_back({0, 0, 0});
            cell_cnt.push_back(0);
        } else {
            id = it->second;
        }
        cell_sum[id].x += pts[i].x;
        cell_sum[id].y += pts[i].y;
        cell_sum[id].z += pts[i].z;
        cell_cnt[id]++;
        remap[i] = id;
    }

    MeshOut out;
    out.verts.resize(cell_sum.size());
    for (size_t i = 0; i < cell_sum.size(); ++i) {
        out.verts[i] = {cell_sum[i].x / cell_cnt[i],
                        cell_sum[i].y / cell_cnt[i],
                        cell_sum[i].z / cell_cnt[i]};
    }
    // 평균점은 곡면 안쪽으로 파고든다 (구가 우둘투둘해짐) — 셀 평균에
    // 가장 가까운 **원본 절점**으로 스냅해 정점을 표면 위에 유지한다.
    {
        std::vector<double> best(out.verts.size(), 1e30);
        std::vector<V3> snap(out.verts.size());
        for (size_t i = 0; i < pts.size(); ++i) {
            const int32_t id = remap[i];
            const double dx = pts[i].x - out.verts[id].x;
            const double dy = pts[i].y - out.verts[id].y;
            const double dz = pts[i].z - out.verts[id].z;
            const double d = dx * dx + dy * dy + dz * dz;
            if (d < best[id]) { best[id] = d; snap[id] = pts[i]; }
        }
        out.verts = snap;
    }
    // 겹친 삼각형 제거 (정렬 키로 중복 제거 + 축퇴 스킵)
    std::map<std::tuple<int32_t, int32_t, int32_t>, bool> seen;
    for (size_t ti = 0; ti < tris.size(); ++ti) {
        const auto& t = tris[ti];
        int32_t a = remap[t[0]], b = remap[t[1]], c = remap[t[2]];
        if (a == b || b == c || a == c) continue;
        int32_t k0 = std::min({a, b, c});
        int32_t k2 = std::max({a, b, c});
        int32_t k1 = a + b + c - k0 - k2;
        auto key = std::make_tuple(k0, k1, k2);
        if (seen.count(key)) continue;
        seen[key] = true;
        out.tris.push_back({a, b, c});
        out.tri_pid.push_back(ti < tri_pid.size() ? tri_pid[ti] : 0);
    }
    return out;
}

}  // namespace

// parts_csv 로 요청한 파트가 모델에 없으면 조용히 무시하지 않고 알린다.
// (전부 없으면 뒤에서 '외곽면이 없음' 으로 걸리지만, 일부만 없을 때가 위험하다)
static void warnMissingParts(const std::map<int32_t, PartBB>& part_bbs,
                             const std::vector<int32_t>& only_parts, bool device_mode) {
    if (device_mode || only_parts.empty()) return;
    std::vector<int32_t> missing;
    for (int32_t pid : only_parts)
        if (part_bbs.find(pid) == part_bbs.end()) missing.push_back(pid);
    if (missing.empty()) return;
    std::printf("경고: parts_csv 의 파트 ID 가 모델에 없음 —");
    for (size_t i = 0; i < missing.size(); ++i) std::printf("%s %d", i ? "," : "", missing[i]);
    std::printf(" (모델 파트 %zu개, 나머지만 추출)\n", part_bbs.size());
}

int main(int argc, char** argv) {
    if (argc < 3) {
        std::printf("사용: %s <d3plot|model.k> <out_prefix> [target_tris=6000] [voxel_res=128] [parts_csv | device]\n", argv[0]);
        return 2;
    }
    const std::string d3 = argv[1];
    const std::string prefix = argv[2];
    // atoi 는 오버플로·후행 문자를 조용히 삼켜 요청값을 다른 수로 둔갑시킨다.
    // strtol 로 전체 토큰 소비와 범위를 확인한다.
    auto parseInt = [](const char* tok, const char* what, long lo, long hi, long& out) -> bool {
        errno = 0;
        char* end = nullptr;
        const long v = std::strtol(tok, &end, 10);
        // strtol 은 선행 공백을 조용히 건너뛴다. ' 6000' 은 통과하고 '6000 ' 은
        // 거부되던 비대칭을 없앤다 — 양쪽 다 거부한다.
        if (tok[0] == '\0' || std::isspace((unsigned char)tok[0]) ||
            end == tok || (end && *end != '\0')) {
            std::printf("%s 가 비정상: '%s' (정수만 허용 — 후행 문자 불가)\n", what, tok);
            return false;
        }
        if (errno == ERANGE || v < lo || v > hi) {
            std::printf("%s 가 비정상: '%s' (%ld~%ld 필요)\n", what, tok, lo, hi);
            return false;
        }
        out = v;
        return true;
    };
    long target_l = 6000;
    if (argc > 3 && !parseInt(argv[3], "target_tris", 1, 100000000L, target_l)) return 2;
    const int target = (int)target_l;
    // 복셀 해상도: 0 이면 cellIx 0 나눗셈, 과대값이면 VR^3 할당 폭발 — 범위 검증
    long vr_l = 128;
    if (argc > 4 && !parseInt(argv[4], "voxel_res", 2, 1024, vr_l)) return 2;
    // 5번째 인자: 파트 ID CSV — 지정하면 그 파트들만 (예: 임팩터 형상 추출)
    // 파싱 불가 토큰을 삼키면 빈 필터 = 전체 모델로 둔갑하므로 정직하게 거부한다.
    std::vector<int32_t> only_parts;
    bool device_mode = false;   // 환경 파트(바닥/벽) 자동 제외
    if (argc > 5 && std::string(argv[5]) == "device") {
        device_mode = true;
    } else if (argc > 5) {
        std::string csv = argv[5];
        size_t pos = 0;
        bool bad = false;
        while (pos < csv.size()) {
            size_t comma = csv.find(',', pos);
            if (comma == std::string::npos) comma = csv.size();
            const std::string tok = csv.substr(pos, comma - pos);
            if (!tok.empty()) {
                try {
                    size_t used = 0;
                    const int v = std::stoi(tok, &used);
                    if (used != tok.size()) throw std::invalid_argument(tok);
                    only_parts.push_back(v);
                } catch (...) {
                    std::printf("parts_csv 토큰 파싱 실패: '%s'\n", tok.c_str());
                    bad = true;
                }
            }
            pos = comma + 1;
        }
        if (bad || only_parts.empty()) {
            std::printf("parts_csv 가 비정상: '%s' — 전체 모델로 위장하지 않고 중단\n", csv.c_str());
            return 2;
        }
    }

    // 공통 기하 컨테이너 — 입력이 .k 든 d3plot 이든 여기로 모인다
    std::vector<V3> pts;
    std::vector<std::array<int32_t, 3>> tris;
    std::vector<int32_t> tri_pid;          // 삼각형별 파트 ID
    std::map<int32_t, PartBB> part_bbs;    // 전 파트 bbox (내부 파트 고스트용)
    V3 bmin{}, bmax{};

    auto lower = [](std::string v) { for (auto& c : v) c = (char)std::tolower((unsigned char)c); return v; };
    const std::string dl = lower(d3);
    auto endsWith = [&](const std::string& suf) {
        return dl.size() >= suf.size() && dl.compare(dl.size() - suf.size(), suf.size(), suf) == 0;
    };
    const bool is_keyword = endsWith(".k") || endsWith(".key") || endsWith(".dyn");

    if (is_keyword) {
        // ---- 원본 키워드 파일 경로 (바닥/임팩터 생성 이전의 모델) ----
        auto km = parsers::parseKeywordMesh(d3);
        for (const auto& w : km.warnings) std::printf("  [k] %s\n", w.c_str());
        if (!km.ok) {
            std::printf("키워드 메시 읽기 실패: %s\n", km.error.c_str());
            return 1;
        }
        std::printf("키워드 메시: 절점 %zu, 솔리드 %zu, 셸 %zu, 두께셸 %zu\n",
                    km.nodes.size(), km.solids.size(), km.shells.size(), km.tshells.size());
        std::unordered_map<int32_t, int32_t> idx;
        idx.reserve(km.nodes.size() * 2);
        pts.reserve(km.nodes.size());
        for (const auto& n : km.nodes) {
            idx[n.id] = (int32_t)pts.size();
            pts.push_back({n.x, n.y, n.z});
        }
        {
            auto scanE = [&](const std::vector<parsers::KeywordMesh::Elem>& els) {
                for (const auto& e : els)
                    for (int k = 0; k < e.nn; ++k) {
                        auto it = idx.find(e.n[k]);
                        if (it != idx.end()) part_bbs[e.pid].add(pts[it->second].x, pts[it->second].y, pts[it->second].z);
                    }
            };
            scanE(km.solids); scanE(km.shells); scanE(km.tshells);
            if (device_mode && !selectDeviceParts(part_bbs, only_parts)) return 2;
            warnMissingParts(part_bbs, only_parts, device_mode);
        }
        auto keep = [&](int32_t pid) {
            return only_parts.empty() ||
                   std::find(only_parts.begin(), only_parts.end(), pid) != only_parts.end();
        };
        // 외곽면: 요소 공유 기준 (한 번만 등장하는 면). 축퇴면(서로 다른 절점 <3)은 버린다.
        static const int HF[6][4] = {{0,3,2,1},{4,5,6,7},{0,1,5,4},{2,3,7,6},{0,4,7,3},{1,2,6,5}};
        std::unordered_map<std::string, int> cnt;
        std::unordered_map<std::string, std::pair<std::array<int32_t, 4>, int32_t>> first;
        auto faceKey = [&](const std::array<int32_t, 4>& f, int& distinct) {
            std::array<int32_t, 4> s2 = f;
            std::sort(s2.begin(), s2.end());
            std::string key;
            distinct = 0;
            for (int k = 0; k < 4; ++k) {
                if (k > 0 && s2[k] == s2[k - 1]) continue;
                ++distinct;
                key += std::to_string(s2[k]) + ",";
            }
            return key;
        };
        auto addHexFaces = [&](const parsers::KeywordMesh::Elem& e) {
            if (!keep(e.pid) || e.nn < 8) return;
            int32_t ni[8];
            for (int k = 0; k < 8; ++k) {
                auto it = idx.find(e.n[k]);
                if (it == idx.end()) return;
                ni[k] = it->second;
            }
            for (const auto& hf : HF) {
                std::array<int32_t, 4> f = {ni[hf[0]], ni[hf[1]], ni[hf[2]], ni[hf[3]]};
                int distinct;
                const std::string key = faceKey(f, distinct);
                if (distinct < 3) continue;
                if (++cnt[key] == 1) first[key] = {f, e.pid};
            }
        };
        for (const auto& e : km.solids) addHexFaces(e);
        for (const auto& e : km.tshells) addHexFaces(e);
        size_t n_ext = 0;
        auto emitQuad = [&](const std::array<int32_t, 4>& f, int32_t pid) {
            // 중복 절점 제거 후 삼각화
            std::vector<int32_t> u;
            for (int32_t v : f) if (u.empty() || std::find(u.begin(), u.end(), v) == u.end()) u.push_back(v);
            if (u.size() < 3) return;
            tris.push_back({u[0], u[1], u[2]}); tri_pid.push_back(pid);
            if (u.size() == 4) { tris.push_back({u[0], u[2], u[3]}); tri_pid.push_back(pid); }
        };
        for (const auto& [key, c] : cnt) {
            if (c == 1) { emitQuad(first[key].first, first[key].second); ++n_ext; }
        }
        for (const auto& e : km.shells) {
            if (!keep(e.pid)) continue;
            std::array<int32_t, 4> f = {0, 0, 0, 0};
            bool okf = true;
            for (int k = 0; k < e.nn && k < 4; ++k) {
                auto it = idx.find(e.n[k]);
                if (it == idx.end()) { okf = false; break; }
                f[k] = it->second;
            }
            if (!okf) continue;
            if (e.nn == 3) f[3] = f[2];
            emitQuad(f, e.pid);
            ++n_ext;
        }
        if (tris.empty()) {
            std::printf("외곽면이 없음\n");
            return 1;
        }
        bmin = pts.empty() ? V3{} : pts[0]; bmax = bmin;
        for (const auto& p2 : pts) {
            bmin.x = std::min(bmin.x, p2.x); bmax.x = std::max(bmax.x, p2.x);
            bmin.y = std::min(bmin.y, p2.y); bmax.y = std::max(bmax.y, p2.y);
            bmin.z = std::min(bmin.z, p2.z); bmax.z = std::max(bmax.z, p2.z);
        }
    } else {
        D3plotReader reader(d3);
        if (reader.open() != ErrorCode::SUCCESS) {
            std::printf("d3plot 열기 실패: %s\n", d3.c_str());
            return 1;
        }
        auto mesh = reader.read_mesh();

        {
            auto scan = [&](const std::vector<Element>& els, const std::vector<int32_t>& parts) {
                for (size_t i = 0; i < els.size(); ++i) {
                    const int32_t pid = (i < parts.size()) ? parts[i] : 0;
                    for (int nid : els[i].node_ids) {
                        const size_t k = (size_t)(nid - 1);
                        if (k < mesh.nodes.size())
                            part_bbs[pid].add(mesh.nodes[k].x, mesh.nodes[k].y, mesh.nodes[k].z);
                    }
                }
            };
            scan(mesh.solids, mesh.solid_parts);
            scan(mesh.shells, mesh.shell_parts);
            scan(mesh.thick_shells, mesh.thick_shell_parts);
            if (device_mode && !selectDeviceParts(part_bbs, only_parts)) return 2;
            warnMissingParts(part_bbs, only_parts, device_mode);
        }

        SurfaceExtractor ex(reader);
        if (!ex.initialize()) {
            std::printf("외곽면 추출 실패: %s\n", ex.getLastError().c_str());
            return 1;
        }
        auto surf = only_parts.empty() ? ex.extractExteriorSurfaces()
                                       : ex.extractExteriorSurfaces(only_parts);
        if (surf.faces.empty()) {
            std::printf("외곽면이 없음\n");
            return 1;
        }

        // 삼각화 + 좌표 수집 (기하 섹션 = 원본 자세)
        pts.assign(mesh.nodes.size(), V3{});
        for (size_t i = 0; i < mesh.nodes.size(); ++i) {
            pts[i] = {mesh.nodes[i].x, mesh.nodes[i].y, mesh.nodes[i].z};
        }
        bmin = pts.empty() ? V3{} : pts[0]; bmax = bmin;
        for (const auto& p : pts) {
            bmin.x = std::min(bmin.x, p.x); bmax.x = std::max(bmax.x, p.x);
            bmin.y = std::min(bmin.y, p.y); bmax.y = std::max(bmax.y, p.y);
            bmin.z = std::min(bmin.z, p.z); bmax.z = std::max(bmax.z, p.z);
        }

        for (const auto& f : surf.faces) {
            const auto& n = f.node_indices;
            if (n.size() < 3) continue;
            auto ok = [&](int32_t idx) { return idx >= 0 && (size_t)idx < pts.size(); };
            if (!ok(n[0]) || !ok(n[1]) || !ok(n[2])) continue;
            tris.push_back({n[0], n[1], n[2]}); tri_pid.push_back(f.part_id);
            if (n.size() >= 4 && ok(n[3]) && n[3] != n[2]) {
                tris.push_back({n[0], n[2], n[3]}); tri_pid.push_back(f.part_id);
            }
        }
    }

    std::printf("외곽 삼각형 %zu개 (내부 파트 표면 포함)\n", tris.size());

    // 사용 정점만 남기고 압축 — 파트 필터 시 미사용 절점이 bbox·복셀격자·
    // 데시메이션에 섞여 미리보기가 전체 모델 크기로 잡히는 것을 막는다.
    {
        std::vector<int32_t> remap(pts.size(), -1);
        std::vector<V3> used;
        for (auto& t : tris) {
            for (auto& idx : t) {
                if (remap[idx] < 0) {
                    remap[idx] = (int32_t)used.size();
                    used.push_back(pts[idx]);
                }
                idx = remap[idx];
            }
        }
        pts.swap(used);
        bmin = pts.empty() ? V3{} : pts[0]; bmax = bmin;
        for (const auto& p2 : pts) {
            bmin.x = std::min(bmin.x, p2.x); bmax.x = std::max(bmax.x, p2.x);
            bmin.y = std::min(bmin.y, p2.y); bmax.y = std::max(bmax.y, p2.y);
            bmin.z = std::min(bmin.z, p2.z); bmax.z = std::max(bmax.z, p2.z);
        }
    }

    // ---- 가시 외피만 남기기 (복셀 플러드필) ----
    //
    // 요소 공유 기준의 '외곽면' 은 노드가 안 붙은 **내부 부품**(PCB·칩 등)의
    // 표면까지 전부 포함한다 — 자세 미리보기에는 겉껍데기만 있으면 된다.
    // 방법: 복셀 격자에 삼각형을 마킹 → 바깥 공기에서 6-연결 플러드필 →
    // 외기와 접한 복셀에 걸린 삼각형만 유지. 하우징이 막힌 한 내부 표면은
    // 도달 불가라 떨어져 나간다. (통풍구 급 큰 구멍이 있으면 일부 새어
    // 들어올 수 있다 — 근사 목적상 허용.)
    {
        const int VR = (int)vr_l;   // 최장축 셀 수 (위에서 strtol 로 2~1024 검증)
        // 실측(Test_006 스윕 24~256): 너무 낮으면 셀이 굵어 내부 셀까지
        // 바깥과 면접해 아무것도 안 걸러지고, 너무 높으면 미세 틈으로
        // 공기가 새어 들어간다. 128 이 최대 제거(27%) + 데시메이션 품질
        // 최고였다. 개방 조립(보드 위 부품)은 원래 대부분 외기 가시라
        // 제거량이 작은 게 정상 — 밀폐 하우징 모델에서 진가가 나온다.
        //
        // 셀은 **등방**(최장축/VR)으로 잡는다. 축별로 VR 등분하면 얇은
        // 기기(147×71×9)의 두께 방향 셀이 0.07mm 가 되어 플러드필이 새고
        // 내부 제거가 0 이 된다 (실측).
        const double ex = std::max(1e-9, bmax.x - bmin.x);
        const double ey = std::max(1e-9, bmax.y - bmin.y);
        const double ez = std::max(1e-9, bmax.z - bmin.z);
        const double cell = std::max({ex, ey, ez}) / VR;
        const int NX = std::max(1, (int)std::ceil(ex / cell));
        const int NY = std::max(1, (int)std::ceil(ey / cell));
        const int NZ = std::max(1, (int)std::ceil(ez / cell));
        auto cellIx = [&](double v, double lo, int n) {
            int i = (int)((v - lo) / cell);
            return std::min(n - 1, std::max(0, i));
        };
        auto cellId = [&](int ix, int iy, int iz) {
            return (ix * NY + iy) * NZ + iz;
        };
        const size_t NCELL = (size_t)NX * NY * NZ;

        std::vector<uint8_t> solid(NCELL, 0);
        std::vector<std::vector<int32_t>> cell_of_tri(tris.size());

        for (size_t t = 0; t < tris.size(); ++t) {
            // 삼각형을 몇 개 샘플점으로 근사 마킹 (꼭짓점 + 변 중점 + 무게중심)
            const V3& a = pts[tris[t][0]];
            const V3& b = pts[tris[t][1]];
            const V3& c = pts[tris[t][2]];
            const V3 samples[7] = {
                a, b, c,
                {(a.x + b.x) / 2, (a.y + b.y) / 2, (a.z + b.z) / 2},
                {(b.x + c.x) / 2, (b.y + c.y) / 2, (b.z + c.z) / 2},
                {(c.x + a.x) / 2, (c.y + a.y) / 2, (c.z + a.z) / 2},
                {(a.x + b.x + c.x) / 3, (a.y + b.y + c.y) / 3, (a.z + b.z + c.z) / 3},
            };
            for (const V3& sp : samples) {
                const int id = cellId(cellIx(sp.x, bmin.x, NX),
                                      cellIx(sp.y, bmin.y, NY),
                                      cellIx(sp.z, bmin.z, NZ));
                if (!solid[id] || cell_of_tri[t].empty() ||
                    cell_of_tri[t].back() != id) {
                    cell_of_tri[t].push_back(id);
                }
                solid[id] = 1;
            }
        }

        // 바깥 공기 플러드필 (경계 셀에서 시작)
        std::vector<uint8_t> air(NCELL, 0);
        std::vector<int32_t> stack;
        auto push = [&](int ix, int iy, int iz) {
            if (ix < 0 || iy < 0 || iz < 0 || ix >= NX || iy >= NY || iz >= NZ) return;
            const int id = cellId(ix, iy, iz);
            if (air[id] || solid[id]) return;
            air[id] = 1;
            stack.push_back(id);
        };
        for (int i = 0; i < NY; ++i) for (int j = 0; j < NZ; ++j) { push(0, i, j); push(NX - 1, i, j); }
        for (int i = 0; i < NX; ++i) for (int j = 0; j < NZ; ++j) { push(i, 0, j); push(i, NY - 1, j); }
        for (int i = 0; i < NX; ++i) for (int j = 0; j < NY; ++j) { push(i, j, 0); push(i, j, NZ - 1); }
        auto decode = [&](int id, int& ix, int& iy, int& iz) {
            iz = id % NZ; iy = (id / NZ) % NY; ix = id / (NZ * NY);
        };
        while (!stack.empty()) {
            const int id = stack.back(); stack.pop_back();
            int ix, iy, iz; decode(id, ix, iy, iz);
            push(ix + 1, iy, iz); push(ix - 1, iy, iz);
            push(ix, iy + 1, iz); push(ix, iy - 1, iz);
            push(ix, iy, iz + 1); push(ix, iy, iz - 1);
        }

        // 외기와 면접한 복셀에 걸린 삼각형만 유지
        auto touchesAir = [&](int id) {
            int ix, iy, iz; decode(id, ix, iy, iz);
            const int di[6][3] = {{1,0,0},{-1,0,0},{0,1,0},{0,-1,0},{0,0,1},{0,0,-1}};
            for (const auto& d : di) {
                const int jx = ix + d[0], jy = iy + d[1], jz = iz + d[2];
                if (jx < 0 || jy < 0 || jz < 0 || jx >= NX || jy >= NY || jz >= NZ)
                    return true;                     // 격자 경계 = 바깥
                if (air[cellId(jx, jy, jz)]) return true;
            }
            return false;
        };
        std::vector<std::array<int32_t, 3>> visible;
        std::vector<int32_t> visible_pid;
        visible.reserve(tris.size());
        for (size_t t = 0; t < tris.size(); ++t) {
            for (int id : cell_of_tri[t]) {
                if (touchesAir(id)) { visible.push_back(tris[t]); visible_pid.push_back(tri_pid[t]); break; }
            }
        }
        std::printf("가시 외피 필터: %zu → %zu 삼각형 (내부 표면 제거, 격자 %dx%dx%d)\n",
                    tris.size(), visible.size(), NX, NY, NZ);
        tris = std::move(visible);
        tri_pid = std::move(visible_pid);
    }

    std::printf("데시메이션 목표 %d\n", target);

    // 데시메이션: 해상도를 낮춰가며 목표 이하로
    MeshOut out;
    int res = 128;
    while (true) {
        out = clusterDecimate(pts, tris, tri_pid, bmin, bmax, res);
        if ((int)out.tris.size() <= target || res <= 8) break;
        res = (int)(res * 0.82);
    }
    std::printf("데시메이션: res=%d → 정점 %zu, 삼각형 %zu\n",
                res, out.verts.size(), out.tris.size());

    // ---- 이진 STL ----
    unsigned long long expect_stl = 0;
    // 실패로 끝날 때 절단된 산출물을 남기지 않는다 — 남기면 다음 실행이
    // '파일이 있으니 정상' 으로 오인한다.
    auto drop_partial = [&]() {
        std::error_code ec;
        std::filesystem::remove(prefix + ".stl", ec);
        std::filesystem::remove(prefix + ".json", ec);
    };
    {
        std::ofstream f(prefix + ".stl", std::ios::binary);
        if (!f) {
            std::printf("STL 열기 실패: %s.stl (경로/권한 확인)\n", prefix.c_str());
            return 1;
        }
        char header[80] = "KooD3plotReader approximate exterior";
        f.write(header, 80);
        uint32_t n = (uint32_t)out.tris.size();
        f.write((char*)&n, 4);
        for (const auto& t : out.tris) {
            const V3& a = out.verts[t[0]];
            const V3& b = out.verts[t[1]];
            const V3& c = out.verts[t[2]];
            const double ux = b.x - a.x, uy = b.y - a.y, uz = b.z - a.z;
            const double vx = c.x - a.x, vy = c.y - a.y, vz = c.z - a.z;
            double nx = uy * vz - uz * vy, ny = uz * vx - ux * vz, nz = ux * vy - uy * vx;
            const double L = std::sqrt(nx * nx + ny * ny + nz * nz);
            if (L > 1e-20) { nx /= L; ny /= L; nz /= L; }
            float rec[12] = {(float)nx, (float)ny, (float)nz,
                             (float)a.x, (float)a.y, (float)a.z,
                             (float)b.x, (float)b.y, (float)b.z,
                             (float)c.x, (float)c.y, (float)c.z};
            f.write((char*)rec, 48);
            uint16_t attr = 0;
            f.write((char*)&attr, 2);
        }
        // 디스크 풀(ENOSPC)·쿼터에서 write 는 실패하는데 소멸자는 조용하다.
        // 명시적으로 닫고 스트림 상태를 본다.
        f.close();
        if (f.fail()) {
            std::printf("STL 쓰기 실패: %s.stl (디스크 여유·쿼터 확인)\n", prefix.c_str());
            f.close(); drop_partial();
            return 1;
        }
        expect_stl = 84 + 50ull * (unsigned long long)out.tris.size();
    }
    // 데시메이션이 전부 축퇴시켜 삼각형이 0개면 84바이트 빈 STL 이 나온다.
    // '출력 성공' 으로 위장하면 미리보기가 조용히 사라진다 — 정직하게 실패한다.
    if (out.tris.empty()) {
        std::printf("삼각형이 0개입니다 — 데시메이션(res=%d)이 형상을 모두 축퇴시켰습니다. "
                    "voxel_res 를 낮추거나 target_tris 를 조정하세요\n", res);
        drop_partial();
        return 1;
    }

    // ---- 경량 JSON (보고서 임베드용) ----
    {
        std::ofstream f(prefix + ".json");
        if (!f) {
            std::printf("JSON 열기 실패: %s.json (경로/권한 확인)\n", prefix.c_str());
            return 1;
        }
        f << "{\"v\":[";
        f.setf(std::ios::fixed);
        f.precision(2);
        for (size_t i = 0; i < out.verts.size(); ++i) {
            if (i) f << ",";
            f << out.verts[i].x << "," << out.verts[i].y << "," << out.verts[i].z;
        }
        f << "],\"f\":[";
        for (size_t i = 0; i < out.tris.size(); ++i) {
            if (i) f << ",";
            f << out.tris[i][0] << "," << out.tris[i][1] << "," << out.tris[i][2];
        }
        f.precision(3);
        // bbox 는 실제 실린 정점(데시메이션 후) 기준 — 파일 안에서 자기모순이 없게 한다
        V3 obmin = out.verts.empty() ? V3{} : out.verts[0], obmax = obmin;
        for (const auto& p2 : out.verts) {
            obmin.x = std::min(obmin.x, p2.x); obmax.x = std::max(obmax.x, p2.x);
            obmin.y = std::min(obmin.y, p2.y); obmax.y = std::max(obmax.y, p2.y);
            obmin.z = std::min(obmin.z, p2.z); obmax.z = std::max(obmax.z, p2.z);
        }
        f << "],\"bbox\":[" << obmin.x << "," << obmin.y << "," << obmin.z << ","
          << obmax.x << "," << obmax.y << "," << obmax.z << "]";
        // 삼각형별 파트 ID — 보고서의 파트/그룹별 색칠
        f << ",\"p\":[";
        for (size_t i = 0; i < out.tri_pid.size(); ++i) {
            if (i) f << ",";
            f << out.tri_pid[i];
        }
        // 전 파트 bbox — 외피에 안 보이는 내부 파트의 위치 고스트용
        f << "],\"parts\":{";
        bool firstp = true;
        f.precision(2);
        for (const auto& [pid, b] : part_bbs) {
            if (!b.any) continue;
            // 파트 필터/device 모드가 걸려 있으면 제외 파트(바닥 등)의 bbox 는 싣지 않는다 —
            // 보고서가 그 파트를 '내부 파트' 로 오인해 거대한 고스트를 그리는 것을 막는다
            if (!only_parts.empty() &&
                std::find(only_parts.begin(), only_parts.end(), pid) == only_parts.end()) continue;
            if (!firstp) f << ",";
            firstp = false;
            f << "\"" << pid << "\":[" << b.lo[0] << "," << b.lo[1] << "," << b.lo[2] << ","
              << b.hi[0] << "," << b.hi[1] << "," << b.hi[2] << "]";
        }
        f << "}}";
        f.close();
        if (f.fail()) {
            std::printf("JSON 쓰기 실패: %s.json (디스크 여유·쿼터 확인)\n", prefix.c_str());
            f.close(); drop_partial();
            return 1;
        }
    }

    // 쓰기 실패(디스크 풀·권한)를 성공으로 위장하지 않는다.
    // 존재 확인만으로는 절단된 파일을 잡지 못한다 — 기대 바이트 수와 대조한다.
    {
        std::ifstream chk_s(prefix + ".stl", std::ios::binary | std::ios::ate);
        std::ifstream chk_j(prefix + ".json", std::ios::binary | std::ios::ate);
        if (!chk_s || !chk_j) {
            std::printf("출력 파일 검증 실패: %s.{stl,json} 이 생성되지 않음\n", prefix.c_str());
            drop_partial();
            return 1;
        }
        const long long got_s = (long long)chk_s.tellg();
        const long long got_j = (long long)chk_j.tellg();
        if (got_s != (long long)expect_stl) {
            std::printf("STL 이 절단됨: %s.stl — 기대 %llu 바이트, 실제 %lld 바이트 "
                        "(디스크 여유·쿼터 확인). 부분 산출물은 삭제했습니다\n",
                        prefix.c_str(), expect_stl, got_s);
            chk_s.close(); chk_j.close();
            drop_partial();
            return 1;
        }
        // JSON 은 최소한 닫는 괄호까지 있어야 한다
        chk_j.seekg(0);
        std::string all((std::istreambuf_iterator<char>(chk_j)), std::istreambuf_iterator<char>());
        if (got_j <= 0 || all.size() < 2 || all.back() != '}') {
            std::printf("JSON 이 절단됨: %s.json — %lld 바이트, 끝이 '}' 가 아님 "
                        "(디스크 여유·쿼터 확인). 부분 산출물은 삭제했습니다\n",
                        prefix.c_str(), got_j);
            chk_s.close(); chk_j.close();
            drop_partial();
            return 1;
        }
    }
    std::printf("출력: %s.stl / %s.json\n", prefix.c_str(), prefix.c_str());
    return 0;
}
