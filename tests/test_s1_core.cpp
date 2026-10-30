// S1 기하 핵심 시험 — StepForge 겉면 규칙 이식·바깥 방향·von Mises·고유벡터·바닥 평면
//
// S1 경량 추출본(DynaForge 계약 C-3)의 겉면은 StepForge core/deck_surface.py 와 같은 꼴이어야
// StepForge 가 집합 대조로 쓸 수 있다. 실덱으로는 축퇴 꼴·뒤집힌 요소를 골라 볼 수 없어
// 작은 메시를 손으로 짓는다.
//
// Run:
//   cmake --build build -j4 --target kood3plot
//   g++ -std=c++17 -O2 -I include tests/test_s1_core.cpp build/libkood3plot.a -fopenmp -lz -o .work/t_s1_core
//   .work/t_s1_core
//
// ctest 에 등록되어 있으므로 `ctest -R S1Core` 로도 돌릴 수 있다.

#include "kood3plot/s1/S1Core.hpp"

#include <cmath>
#include <cstdio>
#include <stdexcept>
#include <string>

using namespace kood3plot;
using namespace kood3plot::s1;

namespace {

int g_failed = 0;

void checkTrue(const std::string& what, bool cond) {
    if (!cond) ++g_failed;
    std::printf("  %s %s\n", cond ? "[OK]  " : "[FAIL]", what.c_str());
}

bool throws(const std::array<int32_t, 8>& c) {
    try {
        solidForm(c);
    } catch (const std::runtime_error&) {
        return true;
    }
    return false;
}

// nx×ny×nz 단위 정육면체 격자 (절점 (nx+1)(ny+1)(nz+1))
data::Mesh grid(int nx, int ny, int nz) {
    data::Mesh m;
    auto nid = [&](int i, int j, int k) { return (k * (ny + 1) + j) * (nx + 1) + i; };
    for (int k = 0; k <= nz; ++k)
        for (int j = 0; j <= ny; ++j)
            for (int i = 0; i <= nx; ++i) m.nodes.push_back({nid(i, j, k) + 1, double(i), double(j), double(k)});
    return m;
}

void addHex(data::Mesh& m, std::array<int32_t, 8> c0, int32_t part) {
    data::Element e;
    e.id = static_cast<int32_t>(m.solids.size()) + 1;
    e.type = ElementType::SOLID;
    e.material_id = part;
    for (int32_t v : c0) e.node_ids.push_back(v + 1);  // 1-based 내부 순번
    m.solids.push_back(e);
    m.solid_parts.push_back(part);
}

// 격자 칸 (i,j,k) 의 육면체 절점 (0-based, 양의 야코비안 차례)
std::array<int32_t, 8> cell(int nx, int ny, int i, int j, int k) {
    auto n = [&](int a, int b, int c) { return (c * (ny + 1) + b) * (nx + 1) + a; };
    return {n(i, j, k), n(i + 1, j, k), n(i + 1, j + 1, k), n(i, j + 1, k),
            n(i, j, k + 1), n(i + 1, j, k + 1), n(i + 1, j + 1, k + 1), n(i, j + 1, k + 1)};
}

// 겉면이 전부 메시 중심에서 바깥을 보나 (볼록한 블록에서만 쓴다)
bool allOutward(const data::Mesh& m, const Surface& s) {
    double cx = 0, cy = 0, cz = 0;
    for (const auto& n : m.nodes) {
        cx += n.x;
        cy += n.y;
        cz += n.z;
    }
    cx /= m.nodes.size();
    cy /= m.nodes.size();
    cz /= m.nodes.size();
    for (const auto& f : s.faces) {
        const auto& a = m.nodes[f.nodes[0]];
        const auto& b = m.nodes[f.nodes[1]];
        const auto& c = m.nodes[f.nodes[2]];
        const double ux = b.x - a.x, uy = b.y - a.y, uz = b.z - a.z;
        const double vx = c.x - a.x, vy = c.y - a.y, vz = c.z - a.z;
        const double nx = uy * vz - uz * vy, ny = uz * vx - ux * vz, nz = ux * vy - uy * vx;
        const double fx = (a.x + b.x + c.x) / 3 - cx, fy = (a.y + b.y + c.y) / 3 - cy, fz = (a.z + b.z + c.z) / 3 - cz;
        if (nx * fx + ny * fy + nz * fz <= 0) return false;
    }
    return true;
}

}  // namespace

int main() {
    std::printf("[1] 요소 꼴 판정 (StepForge solid_form)\n");
    checkTrue("육면체", solidForm({0, 1, 2, 3, 4, 5, 6, 7}) == SolidForm::Hex);
    checkTrue("사면체 n4=n5~n8", solidForm({0, 1, 2, 3, 3, 3, 3, 3}) == SolidForm::Tet);
    checkTrue("사면체 다른 배치(고유 넷)", solidForm({0, 1, 2, 2, 3, 3, 3, 3}) == SolidForm::Tet);
    checkTrue("쐐기 n3=n4·n7=n8", solidForm({0, 1, 2, 2, 3, 4, 5, 5}) == SolidForm::Wedge);
    checkTrue("피라미드 n5=n6~n8", solidForm({0, 1, 2, 3, 4, 4, 4, 4}) == SolidForm::Pyramid);
    checkTrue("누운 쐐기 n5=n6·n7=n8 (D-644)", solidForm({0, 1, 2, 3, 4, 4, 5, 5}) == SolidForm::Wedge);
    checkTrue("모르는 꼴은 실패", throws({0, 1, 0, 1, 2, 3, 4, 5}));

    std::printf("[2] 사면체 면은 삼각 넷 — 육면체 규칙에 축퇴만 지우면 밑면이 가짜 사변형이 된다\n");
    {
        const auto f = solidFaces({0, 1, 2, 3, 3, 3, 3, 3});
        bool tri = f.size() == 4;
        for (const auto& r : f) tri = tri && r.size() == 3;
        checkTrue("면 4장 모두 삼각", tri);
    }

    std::printf("[3] 육면체 2×1×1 블록 — 공유 면은 속면, 겉면 10장, 모두 바깥\n");
    {
        auto m = grid(2, 1, 1);
        addHex(m, cell(2, 1, 0, 0, 0), 1);
        addHex(m, cell(2, 1, 1, 0, 0), 1);
        const auto s = extractSurface(m, {});
        checkTrue("겉면 10장 (got " + std::to_string(s.faces.size()) + ")", s.faces.size() == 10);
        checkTrue("바깥 방향", allOutward(m, s));
        checkTrue("뒤집은 요소 0", s.n_flipped_elems == 0);
        checkTrue("대상 절점 12", s.device_nodes.size() == 12);
    }

    std::printf("[4] 뒤집힌 요소(음의 야코비안) 도 바깥으로 맞춘다\n");
    {
        auto m = grid(1, 1, 1);
        auto c = cell(1, 1, 0, 0, 0);
        std::swap(c[0], c[4]);  // 위아래 바꿔 뒤집는다
        std::swap(c[1], c[5]);
        std::swap(c[2], c[6]);
        std::swap(c[3], c[7]);
        addHex(m, c, 1);
        const auto s = extractSurface(m, {});
        checkTrue("뒤집은 요소 1", s.n_flipped_elems == 1);
        checkTrue("겉면 6장 바깥", s.faces.size() == 6 && allOutward(m, s));
    }

    std::printf("[5] 정육면체를 사면체 6개로 — 겉면은 삼각 12장, 모두 바깥\n");
    {
        auto m = grid(1, 1, 1);
        // 정육면체 대각 0–7 (절점 = i + 2j + 4k) 을 공유하는 6분할. 넷째는 일부러 뒤집어
        // (둘째·셋째 절점을 바꿈) 부피 부호로 바깥을 맞추는지도 본다.
        const int T[6][4] = {{0, 1, 3, 7}, {0, 3, 2, 7}, {0, 2, 6, 7}, {0, 4, 6, 7}, {0, 4, 5, 7}, {0, 5, 1, 7}};
        for (const auto& t : T) addHex(m, {t[0], t[1], t[2], t[3], t[3], t[3], t[3], t[3]}, 1);
        const auto s = extractSurface(m, {});
        bool tri = true;
        for (const auto& f : s.faces) tri = tri && f.nodes[3] == -1;
        checkTrue("겉면 12장 (got " + std::to_string(s.faces.size()) + ")", s.faces.size() == 12);
        checkTrue("모두 삼각", tri);
        checkTrue("뒤집은 사면체 1", s.n_flipped_elems == 1);
        checkTrue("바깥 방향", allOutward(m, s));
    }

    std::printf("[6] 제외 파트·파트 사이 공유 면\n");
    {
        auto m = grid(2, 1, 1);
        addHex(m, cell(2, 1, 0, 0, 0), 1);
        addHex(m, cell(2, 1, 1, 0, 0), 2);
        const auto both = extractSurface(m, {});
        checkTrue("두 파트가 면 하나를 공유 → n_inter_part_shared_faces 1", both.n_inter_part_shared_faces == 1);
        const auto one = extractSurface(m, {2});
        checkTrue("파트 2 를 빼면 파트 1 의 6면 모두 겉면", one.faces.size() == 6 && one.n_device_elems == 1);
    }

    std::printf("[7] 비다양체(면 하나를 요소 셋이 공유)는 실패\n");
    {
        auto m = grid(2, 1, 1);
        addHex(m, cell(2, 1, 0, 0, 0), 1);
        addHex(m, cell(2, 1, 1, 0, 0), 1);
        addHex(m, cell(2, 1, 1, 0, 0), 1);  // 같은 칸을 한 번 더 — 면 공유가 셋이 된다
        bool threw = false;
        try {
            extractSurface(m, {});
        } catch (const std::runtime_error&) {
            threw = true;
        }
        checkTrue("std::runtime_error", threw);
    }

    std::printf("[8] von Mises — 단축 인장·순수 전단\n");
    {
        data::StateData st;
        st.solid_data = {100, 0, 0, 0, 0, 0, 0, /* 둘째 요소 */ 0, 0, 0, 10, 0, 0, 0};
        checkTrue("σxx=100 → 100", std::abs(solidVonMises(st, 0, 7) - 100.0) < 1e-9);
        checkTrue("τxy=10 → 10√3", std::abs(solidVonMises(st, 1, 7) - 10.0 * std::sqrt(3.0)) < 1e-9);
    }

    std::printf("[9] 가장 작은 고윳값의 고유벡터 — A·v = λ·v\n");
    {
        const double A[3][3] = {{4, 1, 0.5}, {1, 3, 0.2}, {0.5, 0.2, 1}};
        const V3 v = smallestEigenvector(A);
        const double Av[3] = {A[0][0] * v.x + A[0][1] * v.y + A[0][2] * v.z,
                              A[1][0] * v.x + A[1][1] * v.y + A[1][2] * v.z,
                              A[2][0] * v.x + A[2][1] * v.y + A[2][2] * v.z};
        const double lam = Av[0] * v.x + Av[1] * v.y + Av[2] * v.z;
        const double res = std::abs(Av[0] - lam * v.x) + std::abs(Av[1] - lam * v.y) + std::abs(Av[2] - lam * v.z);
        // 이 행렬의 고윳값(독립 계산, numpy.linalg.eigvalsh): 0.91807052 · 2.38764693 · 4.69428255
        checkTrue("잔차 < 1e-9 (got " + std::to_string(res) + ")", res < 1e-9);
        checkTrue("가장 작은 고윳값 0.91807052", std::abs(lam - 0.91807052) < 1e-7);
    }

    std::printf("[10] 기운 3층 바닥판 — 기기 쪽 층·법선·평평함\n");
    {
        // 법선 n = (0, sin a, cos a) 로 기운 판, 층 간격 1, 기기는 n 쪽 위에
        const double a = 0.3, ny = std::sin(a), nz = std::cos(a);
        std::vector<V3> pts;
        for (int layer = 0; layer < 3; ++layer)
            for (int i = 0; i < 11; ++i)
                for (int j = 0; j < 11; ++j) {
                    const double u = i - 5.0, w = j - 5.0, h = -2.0 + layer;  // 맨 위 층 h = 0
                    pts.push_back({u, w * nz + h * ny, -w * ny + h * nz});
                }
        const FloorPlane fp = fitFloorPlane(pts, {0, 10 * ny, 10 * nz});
        checkTrue("법선 ≈ (0, sin a, cos a)",
                  std::abs(fp.normal.x) < 1e-9 && std::abs(fp.normal.y - ny) < 1e-9 && std::abs(fp.normal.z - nz) < 1e-9);
        checkTrue("기기 쪽 층(121 절점)", fp.n_layer_nodes == 121);
        checkTrue("점이 맨 위 층 (원점)", std::abs(fp.point.x) + std::abs(fp.point.y) + std::abs(fp.point.z) < 1e-9);
        checkTrue("평평함 ≈ 0", fp.flatness < 1e-9);
    }

    std::printf("\n%s (%d failed)\n", g_failed ? "FAILED" : "PASSED", g_failed);
    return g_failed ? 1 : 0;
}
