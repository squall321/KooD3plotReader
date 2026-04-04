#include "app/SphereReportApp.hpp"
#include <imgui.h>
#include <cmath>
#include <algorithm>
#include <iostream>

void SphereReportApp::projectGlobe(double lonDeg, double latDeg, float vLon, float vLat,
                                    float R, float& sx, float& sy, float& sz) const {
    double lon = lonDeg * M_PI / 180.0, lat = latDeg * M_PI / 180.0;
    double x = std::cos(lat) * std::sin(lon);
    double y = std::sin(lat);
    double z = std::cos(lat) * std::cos(lon);

    double vl = vLon * M_PI / 180.0, va = vLat * M_PI / 180.0;
    double x1 = x * std::cos(vl) - z * std::sin(vl);
    double z1 = x * std::sin(vl) + z * std::cos(vl);
    double y1 = y * std::cos(va) - z1 * std::sin(va);
    double z2 = y * std::sin(va) + z1 * std::cos(va);

    sx = (float)(x1 * R);
    sy = (float)(y1 * R);
    sz = (float)z2;
}

void SphereReportApp::renderGlobe() {
    ImGui::Checkbox("Auto Rotate", &globeAutoRotate_);
    ImGui::SameLine();
    if (!globeRecording_) {
        if (ImGui::Button("Record 360")) {
            globeRecording_ = true;
            globeRecFrame_ = 0;
            globeAutoRotate_ = false;
            std::cout << "[Globe] Recording 360 frames...\n";
        }
    } else {
        ImGui::TextColored(COL_RED, "Recording %d/360", globeRecFrame_);
    }

    if (globeAutoRotate_) {
        globeYaw_ += ImGui::GetIO().DeltaTime * 20.0f;
        if (globeYaw_ > 360) globeYaw_ -= 360;
    }

    if (globeRecording_) {
        globeYaw_ = (float)globeRecFrame_++;
        if (globeRecFrame_ >= 360) {
            globeRecording_ = false;
            std::cout << "[Globe] Recording done. 360 PPM frames saved.\n";
        }
    }

    ImVec2 avail = ImGui::GetContentRegionAvail();
    float sz = std::min(avail.x, avail.y) - 20;
    if (sz < 100) sz = 200;
    ImVec2 pos = ImGui::GetCursorScreenPos();
    ImGui::InvisibleButton("##globe", ImVec2(sz, sz));

    if (ImGui::IsItemHovered() && ImGui::IsMouseDragging(ImGuiMouseButton_Left)) {
        ImVec2 d = ImGui::GetIO().MouseDelta;
        globeYaw_ += d.x * 0.5f;
        globePitch_ = std::clamp(globePitch_ - d.y * 0.005f, -1.4f, 1.4f);
        globeAutoRotate_ = false;
    }

    ImDrawList* dl = ImGui::GetWindowDrawList();
    float cx = pos.x + sz*0.5f, cy = pos.y + sz*0.5f;
    float R = sz * 0.42f;
    float vLon = globeYaw_, vLat = globePitch_ * 180.0f / (float)M_PI;

    dl->AddRectFilled(pos, ImVec2(pos.x+sz, pos.y+sz), IM_COL32(15,17,26,255), 6);

    // Grid
    for (int lon = -180; lon <= 150; lon += 30)
        for (int lat = -87; lat <= 87; lat += 3) {
            float sx1, sy1, sz1, sx2, sy2, sz2;
            projectGlobe(lon,  lat,  vLon, vLat, R, sx1, sy1, sz1);
            projectGlobe(lon,  lat+3, vLon, vLat, R, sx2, sy2, sz2);
            if (sz1 > 0 && sz2 > 0)
                dl->AddLine(ImVec2(cx+sx1, cy-sy1), ImVec2(cx+sx2, cy-sy2), IM_COL32(60,65,80,60), 0.5f);
        }
    for (int lat = -60; lat <= 60; lat += 30)
        for (int lon = -180; lon <= 177; lon += 3) {
            float sx1, sy1, sz1, sx2, sy2, sz2;
            projectGlobe(lon,  lat, vLon, vLat, R, sx1, sy1, sz1);
            projectGlobe(lon+3, lat, vLon, vLat, R, sx2, sy2, sz2);
            if (sz1 > 0 && sz2 > 0)
                dl->AddLine(ImVec2(cx+sx1, cy-sy1), ImVec2(cx+sx2, cy-sy2), IM_COL32(60,65,80,60), 0.5f);
        }

    dl->AddCircle(ImVec2(cx, cy), R, IM_COL32(120,125,160,180), 64, 1.5f);

    // Data points
    struct ProjPt { float sx, sy, sz; int ri; ImU32 col; };
    std::vector<ProjPt> pts;
    double vmin = 1e30, vmax = -1e30;
    for (int ri = 0; ri < (int)data_.results.size(); ++ri) {
        double v = getAngleValue(ri, selectedPartId_, quantity_);
        vmin = std::min(vmin, v); vmax = std::max(vmax, v);
    }
    double vrange = std::max(vmax - vmin, 1e-10);

    for (int ri = 0; ri < (int)data_.results.size(); ++ri) {
        auto& r = data_.results[ri];
        float psx, psy, psz;
        projectGlobe(r.angle.lon, r.angle.lat, vLon, vLat, R, psx, psy, psz);
        double norm = (getAngleValue(ri, selectedPartId_, quantity_) - vmin) / vrange;
        pts.push_back({psx, psy, psz, ri, valueToColor(norm)});
    }
    std::sort(pts.begin(), pts.end(), [](const auto& a, const auto& b) { return a.sz < b.sz; });

    int nPts = (int)pts.size();
    float baseR = nPts > 500 ? 2 : nPts > 200 ? 3 : 4;
    for (auto& p : pts) {
        float px = cx + p.sx, py = cy - p.sy;
        bool sel = selectedAngles_.count(p.ri);
        if (p.sz > 0) {
            dl->AddCircleFilled(ImVec2(px, py), sel ? baseR+2 : baseR, p.col);
            if (sel) dl->AddCircle(ImVec2(px, py), baseR+4, IM_COL32(255,255,255,200), 0, 1.5f);
        } else {
            ImU32 dimCol = IM_COL32((p.col&0xFF)/4, ((p.col>>8)&0xFF)/4, ((p.col>>16)&0xFF)/4, 150);
            dl->AddCircleFilled(ImVec2(px, py), baseR*0.6f, dimCol);
        }
    }
}
