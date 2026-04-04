#include "app/SphereReportApp.hpp"
#include <imgui.h>
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <vector>

void SphereReportApp::drawOrientationDevice(ImDrawList* dl, ImVec2 pos, float size,
                                             double rollDeg, double pitchDeg) {
    if (stlLoaded_ && !stlMesh_.triangles.empty())
        drawOrientationSTL(dl, pos, size, rollDeg, pitchDeg);
    else
        drawOrientationCube(dl, pos, size, rollDeg, pitchDeg);
}

void SphereReportApp::drawOrientationSTL(ImDrawList* dl, ImVec2 pos, float size,
                                          double rollDeg, double pitchDeg) {
    float cx = pos.x + size * 0.5f, cy = pos.y + size * 0.5f;
    float sc = size * 0.35f / stlMesh_.maxExtent;

    double r = rollDeg * M_PI / 180.0, p = pitchDeg * M_PI / 180.0;
    float cr = (float)std::cos(r), sr = (float)std::sin(r);
    float cp = (float)std::cos(p), sp = (float)std::sin(p);

    auto project = [&](float x, float y, float z, float& ox, float& oy, float& oz) {
        x -= stlMesh_.center[0]; y -= stlMesh_.center[1]; z -= stlMesh_.center[2];
        float y1 = y*cr - z*sr, z1 = y*sr + z*cr;
        float x2 = x*cp + z1*sp; oz = -x*sp + z1*cp;
        ox = (x2 - y1) * 0.707f;
        oy = -(x2 + y1) * 0.408f - oz * 0.816f;
    };

    // Background
    dl->AddRectFilled(pos, ImVec2(pos.x + size, pos.y + size), IM_COL32(20, 22, 35, 220), 6);

    // Sort triangles by average Z (painter's algorithm)
    struct TriProj { float pts[3][2]; float avgZ; float lightVal; };
    std::vector<TriProj> tris(stlMesh_.triangles.size());

    for (size_t i = 0; i < stlMesh_.triangles.size(); ++i) {
        auto& t = stlMesh_.triangles[i];
        float sumZ = 0;
        for (int vi = 0; vi < 3; ++vi) {
            float oz;
            project(t.v[vi][0], t.v[vi][1], t.v[vi][2],
                    tris[i].pts[vi][0], tris[i].pts[vi][1], oz);
            tris[i].pts[vi][0] = cx + tris[i].pts[vi][0] * sc;
            tris[i].pts[vi][1] = cy + tris[i].pts[vi][1] * sc;
            sumZ += oz;
        }
        tris[i].avgZ = sumZ / 3.0f;

        // Simple lighting from face normal
        float nx, ny, nz;
        project(t.normal[0] + stlMesh_.center[0], t.normal[1] + stlMesh_.center[1],
                t.normal[2] + stlMesh_.center[2], nx, ny, nz);
        tris[i].lightVal = std::max(0.2f, std::abs(nz));
    }

    std::sort(tris.begin(), tris.end(), [](const auto& a, const auto& b) { return a.avgZ < b.avgZ; });

    for (auto& t : tris) {
        ImVec2 pts[3] = {{t.pts[0][0], t.pts[0][1]}, {t.pts[1][0], t.pts[1][1]}, {t.pts[2][0], t.pts[2][1]}};
        int gray = (int)(t.lightVal * 180 + 40);
        dl->AddConvexPolyFilled(pts, 3, IM_COL32(gray/2, gray/2+20, gray, 200));
        dl->AddPolyline(pts, 3, IM_COL32(100, 105, 130, 100), ImDrawFlags_Closed, 0.5f);
    }

    dl->AddRectFilled(ImVec2(pos.x + 5, pos.y + size - 18),
                      ImVec2(pos.x + size - 5, pos.y + size - 4),
                      IM_COL32(86,95,137,40), 2);
    dl->AddText(ImVec2(pos.x + size/2 - 18, pos.y + size - 17),
                IM_COL32(121,130,169,180), "GROUND");

    char label[64];
    snprintf(label, sizeof(label), "R:%.0f P:%.0f [STL:%d]", rollDeg, pitchDeg, (int)stlMesh_.triangles.size());
    dl->AddText(ImVec2(pos.x + 4, pos.y + 2), IM_COL32(150,155,180,200), label);
}

void SphereReportApp::drawOrientationCube(ImDrawList* dl, ImVec2 pos, float size,
                                           double rollDeg, double pitchDeg) {
    float cx = pos.x + size * 0.5f, cy = pos.y + size * 0.5f;
    float sc = size * 0.25f;

    double r = rollDeg * M_PI / 180.0, p = pitchDeg * M_PI / 180.0;
    float cr = (float)std::cos(r), sr = (float)std::sin(r);
    float cp = (float)std::cos(p), sp = (float)std::sin(p);

    float hw = deviceAspect_[0], hh = deviceAspect_[1], hd = deviceAspect_[2];

    float verts[8][3] = {
        {-hw,-hh,-hd},{hw,-hh,-hd},{hw,hh,-hd},{-hw,hh,-hd},
        {-hw,-hh,hd},{hw,-hh,hd},{hw,hh,hd},{-hw,hh,hd}
    };

    auto project = [&](float x, float y, float z, float& ox, float& oy, float& oz) {
        float y1 = y*cr - z*sr, z1 = y*sr + z*cr;
        float x2 = x*cp + z1*sp; oz = -x*sp + z1*cp;
        ox = (x2 - y1) * 0.707f;
        oy = -(x2 + y1) * 0.408f - oz * 0.816f;
    };

    float proj[8][2], projZ[8];
    for (int i = 0; i < 8; ++i) {
        project(verts[i][0], verts[i][1], verts[i][2], proj[i][0], proj[i][1], projZ[i]);
        proj[i][0] = cx + proj[i][0] * sc;
        proj[i][1] = cy + proj[i][1] * sc;
    }

    dl->AddRectFilled(pos, ImVec2(pos.x + size, pos.y + size), IM_COL32(20, 22, 35, 220), 6);

    struct FaceDef { int vi[4]; ImU32 fill; ImU32 border; const char* label; };
    FaceDef faces[] = {
        {{4,5,6,7}, IM_COL32(247,118,142,100), IM_COL32(247,118,142,200), "Display"},
        {{0,3,2,1}, IM_COL32(86,95,137,80),    IM_COL32(121,130,169,180), "Back"},
        {{1,2,6,5}, IM_COL32(255,158,100,90),  IM_COL32(255,158,100,200), "R"},
        {{0,4,7,3}, IM_COL32(187,154,247,90),  IM_COL32(187,154,247,200), "L"},
        {{3,7,6,2}, IM_COL32(122,162,247,100), IM_COL32(122,162,247,200), "Top"},
        {{0,1,5,4}, IM_COL32(158,206,106,90),  IM_COL32(158,206,106,200), "Btm"},
    };

    struct FaceSort { int idx; float avgZ; };
    FaceSort faceOrder[6];
    for (int f = 0; f < 6; ++f) {
        faceOrder[f].idx = f;
        faceOrder[f].avgZ = (projZ[faces[f].vi[0]] + projZ[faces[f].vi[1]] +
                              projZ[faces[f].vi[2]] + projZ[faces[f].vi[3]]) / 4.0f;
    }
    std::sort(faceOrder, faceOrder + 6, [](const FaceSort& a, const FaceSort& b) { return a.avgZ < b.avgZ; });

    for (int fi = 0; fi < 6; ++fi) {
        auto& face = faces[faceOrder[fi].idx];
        ImVec2 pts[4];
        for (int j = 0; j < 4; ++j) pts[j] = ImVec2(proj[face.vi[j]][0], proj[face.vi[j]][1]);

        dl->AddConvexPolyFilled(pts, 4, face.fill);
        for (int j = 0; j < 4; ++j)
            dl->AddLine(pts[j], pts[(j+1)%4], face.border, 1.2f);

        float fcx = (pts[0].x+pts[1].x+pts[2].x+pts[3].x)/4;
        float fcy = (pts[0].y+pts[1].y+pts[2].y+pts[3].y)/4;
        dl->AddText(ImVec2(fcx - 6, fcy - 5), IM_COL32(255,255,255,220), face.label);
    }

    dl->AddRectFilled(ImVec2(pos.x + 5, pos.y + size - 18),
                      ImVec2(pos.x + size - 5, pos.y + size - 4),
                      IM_COL32(86,95,137,40), 2);
    dl->AddText(ImVec2(pos.x + size/2 - 18, pos.y + size - 17),
                IM_COL32(121,130,169,180), "GROUND");

    char label[64];
    snprintf(label, sizeof(label), "R:%.0f P:%.0f", rollDeg, pitchDeg);
    dl->AddText(ImVec2(pos.x + 4, pos.y + 2), IM_COL32(150,155,180,200), label);

    const char* legendItems[] = {"Display", "Back", "Right", "Left", "Top", "Bottom"};
    ImU32 legendCols[] = {IM_COL32(247,118,142,255), IM_COL32(121,130,169,255),
                          IM_COL32(255,158,100,255), IM_COL32(187,154,247,255),
                          IM_COL32(122,162,247,255), IM_COL32(158,206,106,255)};
    float ly = pos.y + 16;
    for (int i = 0; i < 6; ++i) {
        dl->AddRectFilled(ImVec2(pos.x + 4, ly), ImVec2(pos.x + 12, ly + 8), legendCols[i], 1);
        dl->AddText(ImVec2(pos.x + 15, ly - 2), IM_COL32(150,155,180,200), legendItems[i]);
        ly += 11;
    }
}
