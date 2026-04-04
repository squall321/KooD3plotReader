#include "app/SphereReportApp.hpp"
#include <imgui.h>
#include <cmath>
#include <algorithm>
#include <cstdio>

void SphereReportApp::renderMollweide() {
    // Device shape controls
    if (ImGui::TreeNode("Device Shape")) {
        ImGui::TextColored(COL_DIM, "Aspect ratio (W:H:D) or load STL file");
        ImGui::SetNextItemWidth(60); ImGui::InputFloat("W##asp", &deviceAspect_[0], 0, 0, "%.2f"); ImGui::SameLine();
        ImGui::SetNextItemWidth(60); ImGui::InputFloat("H##asp", &deviceAspect_[1], 0, 0, "%.2f"); ImGui::SameLine();
        ImGui::SetNextItemWidth(60); ImGui::InputFloat("D##asp", &deviceAspect_[2], 0, 0, "%.2f");

        static char stlPath[256] = "";
        ImGui::SetNextItemWidth(200);
        ImGui::InputTextWithHint("##stl", "STL file path...", stlPath, sizeof(stlPath));
        ImGui::SameLine();
        if (ImGui::Button("Load STL")) {
            StlMesh mesh;
            if (mesh.loadFile(stlPath)) { stlMesh_ = std::move(mesh); stlLoaded_ = true; }
        }
        if (stlLoaded_) {
            ImGui::SameLine();
            ImGui::TextColored(COL_ACCENT, "%d tris", (int)stlMesh_.triangles.size());
            ImGui::SameLine();
            if (ImGui::SmallButton("Clear STL")) { stlLoaded_ = false; stlMesh_.triangles.clear(); }
        }
        ImGui::TreePop();
    }

    const char* qtyNames[] = {"Stress (MPa)", "Strain", "G-Force", "Displacement (mm)"};
    ImGui::SetNextItemWidth(200);
    ImGui::Combo("Quantity", &quantity_, qtyNames, 4);
    ImGui::SameLine();
    ImGui::Text("Part:");
    ImGui::SameLine();
    ImGui::SetNextItemWidth(200);
    if (ImGui::BeginCombo("##partSel",
        (data_.parts.count(selectedPartId_) ?
         ("Part " + std::to_string(selectedPartId_) + " " + data_.parts[selectedPartId_].name) :
         "Select").c_str())) {
        for (auto& [pid, pi] : data_.parts) {
            char label[128];
            snprintf(label, sizeof(label), "Part %d — %s", pid, pi.name.c_str());
            if (ImGui::Selectable(label, selectedPartId_ == pid)) selectedPartId_ = pid;
        }
        ImGui::EndCombo();
    }

    ImGui::SameLine();
    if (ImGui::Checkbox("Swap R/P", &swapRP_)) {
        for (auto& r : data_.results) {
            double roll  = swapRP_ ? r.angle.pitch : r.angle.roll;
            double pitch = swapRP_ ? r.angle.roll  : r.angle.pitch;
            eulerToLonLat(roll, pitch, r.angle.yaw, r.angle.name, r.angle.lon, r.angle.lat);
        }
    }
    ImGui::SameLine(); ImGui::Checkbox("Contour", &contourMode_);
    ImGui::SameLine(); ImGui::Checkbox("Manual Scale", &manualScale_);
    if (manualScale_) {
        ImGui::SameLine(); ImGui::SetNextItemWidth(80); ImGui::InputFloat("Min", &scaleMin_, 0, 0, "%.0f");
        ImGui::SameLine(); ImGui::SetNextItemWidth(80); ImGui::InputFloat("Max", &scaleMax_, 0, 0, "%.0f");
    }
    ImGui::TextColored(COL_DIM, "Click to select/deselect angles. Selected: %d", (int)selectedAngles_.size());
    ImGui::Spacing();

    ImVec2 avail  = ImGui::GetContentRegionAvail();
    float  mapW   = avail.x;
    float  mapH   = std::max(200.0f, avail.y - 10);
    ImVec2 mapPos = ImGui::GetCursorScreenPos();
    ImGui::InvisibleButton("##mollMap", ImVec2(mapW, mapH));
    bool mapHovered = ImGui::IsItemHovered();

    ImDrawList* dl = ImGui::GetWindowDrawList();
    float cx    = mapPos.x + mapW * 0.5f;
    float cy    = mapPos.y + mapH * 0.5f;
    float scale = std::min(mapW / (4.0f * std::sqrt(2.0f)), mapH / (2.0f * std::sqrt(2.0f))) * 0.9f;
    float rx    = 2.0f * std::sqrt(2.0f) * scale;
    float ry    = std::sqrt(2.0f) * scale;

    dl->AddRectFilled(mapPos, ImVec2(mapPos.x + mapW, mapPos.y + mapH), IM_COL32(15, 17, 26, 255), 6);
    dl->AddEllipse(ImVec2(cx, cy), ImVec2(rx, ry), IM_COL32(120,125,160,200), 0, 64, 1.5f);

    // Grid lines
    for (int lat = -60; lat <= 60; lat += 30)
        for (int lon = -175; lon <= 175; lon += 5) {
            double x1, y1, x2, y2;
            mollweideProject(lon, lat, x1, y1);
            mollweideProject(lon+5, lat, x2, y2);
            dl->AddLine(ImVec2(cx+x1*scale, cy-y1*scale), ImVec2(cx+x2*scale, cy-y2*scale), IM_COL32(50,55,75,80), 0.5f);
        }
    for (int lon = -150; lon <= 150; lon += 30)
        for (int lat = -88; lat <= 88; lat += 2) {
            double x1, y1, x2, y2;
            mollweideProject(lon, lat, x1, y1);
            mollweideProject(lon, lat+2, x2, y2);
            dl->AddLine(ImVec2(cx+x1*scale, cy-y1*scale), ImVec2(cx+x2*scale, cy-y2*scale), IM_COL32(50,55,75,80), 0.5f);
        }

    // Value range
    double vmin = 1e30, vmax = -1e30;
    for (int ri = 0; ri < (int)data_.results.size(); ++ri) {
        double v = getAngleValue(ri, selectedPartId_, quantity_);
        vmin = std::min(vmin, v); vmax = std::max(vmax, v);
    }
    if (manualScale_ && scaleMax_ > scaleMin_) { vmin = scaleMin_; vmax = scaleMax_; }
    double vrange = std::max(vmax - vmin, 1e-10);

    // IDW Contour
    if (contourMode_) {
        int gridStep = data_.results.size() > 200 ? 6 : 4;
        for (int py = 0; py < (int)mapH; py += gridStep) {
            for (int px = 0; px < (int)mapW; px += gridStep) {
                float sx = mapPos.x + px, sy = mapPos.y + py;
                double qx = ((double)px - mapW*0.5) / scale;
                double qy = (mapH*0.5 - (double)py) / scale;
                double ex = qx / (2.0*std::sqrt(2.0)), ey = qy / std::sqrt(2.0);
                if (ex*ex + ey*ey > 1.0) continue;
                double wsum = 0, vsum = 0;
                for (int ri = 0; ri < (int)data_.results.size(); ++ri) {
                    double mx, my;
                    mollweideProject(data_.results[ri].angle.lon, data_.results[ri].angle.lat, mx, my);
                    double dx = qx-mx, dy = qy-my;
                    double dist = std::sqrt(dx*dx + dy*dy);
                    if (dist < 0.05) { vsum = getAngleValue(ri, selectedPartId_, quantity_); wsum = 1; break; }
                    double w = 1.0 / (dist*dist*dist);
                    wsum += w; vsum += w * getAngleValue(ri, selectedPartId_, quantity_);
                }
                if (wsum > 0) {
                    double norm = (vsum/wsum - vmin) / vrange;
                    dl->AddRectFilled(ImVec2(sx, sy), ImVec2(sx+gridStep, sy+gridStep), valueToColor(norm));
                }
            }
        }
        dl->AddEllipse(ImVec2(cx, cy), ImVec2(rx, ry), IM_COL32(120,125,160,200), 0, 64, 1.5f);
    }

    // Data points
    hoveredAngle_ = -1;
    ImVec2 mousePos = ImGui::GetMousePos();
    double minDist = 1e30;
    int nPts = (int)data_.results.size();
    float baseR = nPts > 500 ? 3 : nPts > 200 ? 4 : nPts > 50 ? 6 : 8;

    for (int ri = 0; ri < nPts; ++ri) {
        auto& r = data_.results[ri];
        double mx, my;
        mollweideProject(r.angle.lon, r.angle.lat, mx, my);
        float sx = cx + (float)mx*scale, sy = cy - (float)my*scale;

        double norm = (getAngleValue(ri, selectedPartId_, quantity_) - vmin) / vrange;
        ImU32 col = valueToColor(norm);
        bool isSelected = selectedAngles_.count(ri);
        float radius = baseR + (float)norm * baseR * 0.5f + (isSelected ? 2 : 0);

        dl->AddCircleFilled(ImVec2(sx, sy), radius, col);
        if (isSelected) dl->AddCircle(ImVec2(sx, sy), radius+2, IM_COL32(255,255,255,200), 0, 2);

        float dx = mousePos.x-sx, dy = mousePos.y-sy, dist = dx*dx+dy*dy;
        if (dist < minDist && dist < 400) { minDist = dist; hoveredAngle_ = ri; }
    }

    if (mapHovered && ImGui::IsMouseClicked(0) && hoveredAngle_ >= 0) {
        if (selectedAngles_.count(hoveredAngle_)) selectedAngles_.erase(hoveredAngle_);
        else                                       selectedAngles_.insert(hoveredAngle_);
    }

    if (hoveredAngle_ >= 0) {
        auto& r = data_.results[hoveredAngle_];
        ImGui::BeginTooltip();
        ImGui::Text("%s", r.angle.name.c_str());
        ImGui::Text("Roll: %.1f  Pitch: %.1f", r.angle.roll, r.angle.pitch);
        ImGui::Text("Value: %.2f", getAngleValue(hoveredAngle_, selectedPartId_, quantity_));
        ImGui::EndTooltip();

        double mx, my;
        mollweideProject(r.angle.lon, r.angle.lat, mx, my);
        dl->AddCircle(ImVec2(cx+(float)mx*scale, cy-(float)my*scale), baseR+6, IM_COL32(255,255,255,255), 0, 2.5f);

        float cubeSize = 150;
        drawOrientationDevice(dl,
            ImVec2(mapPos.x + mapW - cubeSize - 40, mapPos.y + mapH - cubeSize - 5),
            cubeSize, r.angle.roll, r.angle.pitch);
    }

    // Colorbar
    float cbX = mapPos.x + mapW - 30, cbY = mapPos.y + 20, cbH = mapH - 40;
    for (int i = 0; i < (int)cbH; ++i)
        dl->AddLine(ImVec2(cbX, cbY+i), ImVec2(cbX+16, cbY+i), valueToColor(1.0f - (float)i/cbH));
    char vminS[32], vmaxS[32];
    snprintf(vmaxS, sizeof(vmaxS), "%.1f", vmax);
    snprintf(vminS, sizeof(vminS), "%.1f", vmin);
    dl->AddText(ImVec2(cbX-40, cbY-2),      IM_COL32(200,200,210,255), vmaxS);
    dl->AddText(ImVec2(cbX-40, cbY+cbH-10), IM_COL32(200,200,210,255), vminS);
}
