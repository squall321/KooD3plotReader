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
#include "kood3plot/analysis/SurfaceExtractor.hpp"

#include <cstdio>
#include <cstdint>
#include <cstring>
#include <cmath>
#include <fstream>
#include <map>
#include <tuple>
#include <vector>

using namespace kood3plot;
using namespace kood3plot::analysis;

namespace {

struct V3 { double x = 0, y = 0, z = 0; };

struct MeshOut {
    std::vector<V3> verts;
    std::vector<std::array<int32_t, 3>> tris;
};

/// 격자 해상도 res 로 정점 클러스터링 데시메이션.
MeshOut clusterDecimate(const std::vector<V3>& pts,
                        const std::vector<std::array<int32_t, 3>>& tris,
                        const V3& bmin, const V3& bmax, int res) {
    const double ex = std::max(1e-9, bmax.x - bmin.x);
    const double ey = std::max(1e-9, bmax.y - bmin.y);
    const double ez = std::max(1e-9, bmax.z - bmin.z);

    auto cellOf = [&](const V3& p) {
        int ix = (int)((p.x - bmin.x) / ex * res); ix = std::min(res - 1, std::max(0, ix));
        int iy = (int)((p.y - bmin.y) / ey * res); iy = std::min(res - 1, std::max(0, iy));
        int iz = (int)((p.z - bmin.z) / ez * res); iz = std::min(res - 1, std::max(0, iz));
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
    // 겹친 삼각형 제거 (정렬 키로 중복 제거 + 축퇴 스킵)
    std::map<std::tuple<int32_t, int32_t, int32_t>, bool> seen;
    for (const auto& t : tris) {
        int32_t a = remap[t[0]], b = remap[t[1]], c = remap[t[2]];
        if (a == b || b == c || a == c) continue;
        int32_t k0 = std::min({a, b, c});
        int32_t k2 = std::max({a, b, c});
        int32_t k1 = a + b + c - k0 - k2;
        auto key = std::make_tuple(k0, k1, k2);
        if (seen.count(key)) continue;
        seen[key] = true;
        out.tris.push_back({a, b, c});
    }
    return out;
}

}  // namespace

int main(int argc, char** argv) {
    if (argc < 3) {
        std::printf("사용: %s <d3plot> <out_prefix> [target_tris=6000]\n", argv[0]);
        return 2;
    }
    const std::string d3 = argv[1];
    const std::string prefix = argv[2];
    const int target = (argc > 3) ? std::atoi(argv[3]) : 6000;

    D3plotReader reader(d3);
    if (reader.open() != ErrorCode::SUCCESS) {
        std::printf("d3plot 열기 실패: %s\n", d3.c_str());
        return 1;
    }
    auto mesh = reader.read_mesh();

    SurfaceExtractor ex(reader);
    if (!ex.initialize()) {
        std::printf("외곽면 추출 실패: %s\n", ex.getLastError().c_str());
        return 1;
    }
    auto surf = ex.extractExteriorSurfaces();
    if (surf.faces.empty()) {
        std::printf("외곽면이 없음\n");
        return 1;
    }

    // 삼각화 + 좌표 수집 (기하 섹션 = 원본 자세)
    std::vector<V3> pts(mesh.nodes.size());
    for (size_t i = 0; i < mesh.nodes.size(); ++i) {
        pts[i] = {mesh.nodes[i].x, mesh.nodes[i].y, mesh.nodes[i].z};
    }
    V3 bmin = pts.empty() ? V3{} : pts[0], bmax = bmin;
    for (const auto& p : pts) {
        bmin.x = std::min(bmin.x, p.x); bmax.x = std::max(bmax.x, p.x);
        bmin.y = std::min(bmin.y, p.y); bmax.y = std::max(bmax.y, p.y);
        bmin.z = std::min(bmin.z, p.z); bmax.z = std::max(bmax.z, p.z);
    }

    std::vector<std::array<int32_t, 3>> tris;
    for (const auto& f : surf.faces) {
        const auto& n = f.node_indices;
        if (n.size() < 3) continue;
        auto ok = [&](int32_t idx) { return idx >= 0 && (size_t)idx < pts.size(); };
        if (!ok(n[0]) || !ok(n[1]) || !ok(n[2])) continue;
        tris.push_back({n[0], n[1], n[2]});
        if (n.size() >= 4 && ok(n[3]) && n[3] != n[2]) {
            tris.push_back({n[0], n[2], n[3]});
        }
    }
    std::printf("외곽 삼각형 %zu개 → 목표 %d\n", tris.size(), target);

    // 데시메이션: 해상도를 낮춰가며 목표 이하로
    MeshOut out;
    int res = 128;
    while (true) {
        out = clusterDecimate(pts, tris, bmin, bmax, res);
        if ((int)out.tris.size() <= target || res <= 8) break;
        res = (int)(res * 0.82);
    }
    std::printf("데시메이션: res=%d → 정점 %zu, 삼각형 %zu\n",
                res, out.verts.size(), out.tris.size());

    // ---- 이진 STL ----
    {
        std::ofstream f(prefix + ".stl", std::ios::binary);
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
    }

    // ---- 경량 JSON (보고서 임베드용) ----
    {
        std::ofstream f(prefix + ".json");
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
        f << "],\"bbox\":[" << bmin.x << "," << bmin.y << "," << bmin.z << ","
          << bmax.x << "," << bmax.y << "," << bmax.z << "]}";
    }

    std::printf("출력: %s.stl / %s.json\n", prefix.c_str(), prefix.c_str());
    return 0;
}
