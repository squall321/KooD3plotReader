#include "app/SphereReportApp.hpp"
#include <imgui.h>
#include <algorithm>
#include <map>
#include <vector>
#include <string>
#include <cmath>
#include <cstdio>

void SphereReportApp::renderDirectional() {
    ImGui::TextColored(COL_DIM,
        "Ranking of impact directions by peak value.\n"
        "Shows which directions are most critical for the selected part and quantity.");
    ImGui::Spacing();

    std::vector<std::pair<int,double>> ranked;
    ranked.reserve(data_.results.size());
    for (int ri = 0; ri < (int)data_.results.size(); ++ri)
        ranked.push_back({ri, getAngleValue(ri, selectedPartId_, quantity_)});
    std::sort(ranked.begin(), ranked.end(), [](auto& a, auto& b) { return a.second > b.second; });

    const char* qtyNames[] = {"Stress (MPa)", "Strain", "G-Force", "Disp (mm)"};
    ImGui::TextColored(COL_ACCENT, "  Top 20 Worst Directions — %s", qtyNames[quantity_]);
    ImGui::Separator();

    double maxV = ranked.empty() ? 1.0 : std::max(ranked[0].second, 1e-10);
    for (int i = 0; i < std::min(20, (int)ranked.size()); ++i) {
        int ri = ranked[i].first;
        auto& r = data_.results[ri];
        float pct = (float)(ranked[i].second / maxV);
        char label[128];
        snprintf(label, sizeof(label), "%2d. %-15s [%s]", i+1, r.angle.name.c_str(), r.angle.category.c_str());
        ImGui::Text("%s", label);
        ImGui::SameLine(250);
        ImGui::PushStyleColor(ImGuiCol_PlotHistogram, ImVec4(0.31f+pct*0.6f, 0.2f, 0.2f, 1));
        char ov[32]; snprintf(ov, sizeof(ov), "%.1f", ranked[i].second);
        ImGui::ProgressBar(pct, ImVec2(-1, 16), ov);
        ImGui::PopStyleColor();
    }

    ImGui::Spacing();
    ImGui::TextColored(COL_BLUE, "  Category Breakdown");
    ImGui::Separator();

    // Collect per-category stats
    std::map<std::string, std::vector<double>> catVals;
    for (int ri = 0; ri < (int)data_.results.size(); ++ri) {
        if (!passesFilter(data_.results[ri].angle.category)) continue;
        catVals[data_.results[ri].angle.category].push_back(
            getAngleValue(ri, selectedPartId_, quantity_));
    }

    // A/B compare per-category
    std::map<std::string, std::vector<double>> catValsB;
    if (hasDataB_) {
        for (int ri = 0; ri < (int)dataB_.results.size(); ++ri) {
            auto it2 = dataB_.results[ri].parts.find(selectedPartId_);
            double v = 0;
            if (it2 != dataB_.results[ri].parts.end()) {
                switch (quantity_) {
                    case 0: v = it2->second.peak_stress; break;
                    case 1: v = it2->second.peak_strain; break;
                    case 2: v = it2->second.peak_g;      break;
                    case 3: v = it2->second.peak_disp;   break;
                }
            }
            catValsB[dataB_.results[ri].angle.category].push_back(v);
        }
    }

    struct CatStat { std::string name; double avg, max, avgB, maxB; int count; };
    std::vector<CatStat> cats;
    for (auto& [cat, vals] : catVals) {
        double avg = 0, maxC = 0;
        for (double v : vals) { avg += v; maxC = std::max(maxC, v); }
        avg /= vals.size();
        double avgB = 0, maxB = 0;
        if (hasDataB_ && catValsB.count(cat)) {
            for (double v : catValsB[cat]) { avgB += v; maxB = std::max(maxB, v); }
            if (!catValsB[cat].empty()) avgB /= catValsB[cat].size();
        }
        cats.push_back({cat, avg, maxC, avgB, maxB, (int)vals.size()});
    }

    // Text table
    for (auto& c : cats) {
        ImGui::Text("  %-12s  count=%d  avg=%.1f  max=%.1f",
            c.name.c_str(), c.count, c.avg, c.max);
        if (hasDataB_) {
            ImGui::SameLine(340);
            double delta = c.avg - c.avgB;
            ImGui::TextColored(delta > 0 ? COL_RED : COL_BLUE,
                "B avg=%.1f  Δ%+.1f", c.avgB, delta);
        }
    }

    if (cats.size() < 2) return;

    // ── Radar chart ──────────────────────────────────────────────────
    ImGui::Spacing();
    ImGui::TextColored(COL_ACCENT, "  Directional Sensitivity Radar");
    ImGui::Separator();
    ImGui::Spacing();

    int  n      = (int)cats.size();
    float avail = ImGui::GetContentRegionAvail().x;
    float sz    = std::min(avail * 0.6f, 260.0f);
    ImVec2 origin = ImGui::GetCursorScreenPos();

    // Center in a box
    float cx = origin.x + sz * 0.5f;
    float cy = origin.y + sz * 0.5f;
    float R  = sz * 0.40f;

    ImDrawList* dl = ImGui::GetWindowDrawList();

    // Background
    dl->AddRectFilled(origin, ImVec2(origin.x + sz, origin.y + sz),
                      IM_COL32(14, 16, 26, 220), 6);

    // Global max for normalisation
    double gmax = 1e-10;
    for (auto& c : cats) gmax = std::max(gmax, c.max);

    const float PI2 = 6.28318530f;
    auto axisAngle = [&](int i) { return -3.14159265f/2 + PI2 * i / n; };
    auto axisPoint = [&](int i, float r) -> ImVec2 {
        float a = axisAngle(i);
        return ImVec2(cx + r * std::cos(a), cy + r * std::sin(a));
    };

    // Concentric rings at 25%, 50%, 75%, 100%
    for (int ring = 1; ring <= 4; ++ring) {
        float rr = R * ring / 4.0f;
        std::vector<ImVec2> pts(n);
        for (int i = 0; i < n; ++i) pts[i] = axisPoint(i, rr);
        dl->AddPolyline(pts.data(), n, IM_COL32(60,65,90,120), ImDrawFlags_Closed, 0.8f);
        // Label at top axis
        char lbl[8]; snprintf(lbl, sizeof(lbl), "%.0f%%", ring*25.0f);
        dl->AddText(ImVec2(cx - 14, cy - rr - 10), IM_COL32(80,85,110,200), lbl);
    }

    // Axis spokes + labels
    for (int i = 0; i < n; ++i) {
        ImVec2 tip = axisPoint(i, R * 1.05f);
        dl->AddLine(ImVec2(cx, cy), tip, IM_COL32(60,65,90,180), 1.0f);
        // Label (push out a bit more)
        ImVec2 labelPos = axisPoint(i, R * 1.25f);
        float a = axisAngle(i);
        float lw = (float)cats[i].name.size() * 6.5f;
        if (std::cos(a) < -0.1f) labelPos.x -= lw;
        else if (std::cos(a) < 0.1f) labelPos.x -= lw * 0.5f;
        dl->AddText(labelPos, IM_COL32(160,165,190,230), cats[i].name.c_str());
    }

    // Fan-fill helper: center-to-edge triangles (works for any star-shaped polygon)
    auto fanFill = [&](const std::vector<ImVec2>& pts, ImU32 col) {
        ImVec2 center(cx, cy);
        for (int i = 0; i < (int)pts.size(); ++i)
            dl->AddTriangleFilled(center, pts[i], pts[(i+1) % pts.size()], col);
    };

    // A polygon (avg values)
    {
        std::vector<ImVec2> pts(n);
        for (int i = 0; i < n; ++i) {
            float norm = (float)(cats[i].avg / gmax);
            pts[i] = axisPoint(i, R * norm);
        }
        fanFill(pts, IM_COL32(122,162,247,50));
        dl->AddPolyline(pts.data(), n, IM_COL32(122,162,247,220), ImDrawFlags_Closed, 2.0f);
        for (auto& p : pts) dl->AddCircleFilled(p, 3.5f, IM_COL32(122,162,247,255));
    }

    // B polygon (if compare mode)
    if (hasDataB_) {
        std::vector<ImVec2> pts(n);
        for (int i = 0; i < n; ++i) {
            float norm = (float)(cats[i].avgB / gmax);
            pts[i] = axisPoint(i, R * std::min(norm, 1.1f));
        }
        fanFill(pts, IM_COL32(247,118,142,40));
        dl->AddPolyline(pts.data(), n, IM_COL32(247,118,142,200), ImDrawFlags_Closed, 1.5f);
        for (auto& p : pts) dl->AddCircleFilled(p, 3.0f, IM_COL32(247,118,142,255));
    }

    // Max dots (peak, not avg)
    {
        std::vector<ImVec2> pts(n);
        for (int i = 0; i < n; ++i) {
            float norm = (float)(cats[i].max / gmax);
            pts[i] = axisPoint(i, R * norm);
        }
        dl->AddPolyline(pts.data(), n, IM_COL32(255,200,80,100), ImDrawFlags_Closed, 1.0f);
        for (auto& p : pts) dl->AddCircleFilled(p, 2.5f, IM_COL32(255,200,80,200));
    }

    // Legend
    float lx = origin.x + sz + 8, ly = origin.y + 8;
    dl->AddCircleFilled(ImVec2(lx+5, ly+5), 4, IM_COL32(122,162,247,255));
    dl->AddText(ImVec2(lx+12, ly), IM_COL32(160,165,190,230), "Avg (A)");
    ly += 16;
    dl->AddCircleFilled(ImVec2(lx+5, ly+5), 3, IM_COL32(255,200,80,220));
    dl->AddText(ImVec2(lx+12, ly), IM_COL32(160,165,190,230), "Max (A)");
    if (hasDataB_) {
        ly += 16;
        dl->AddCircleFilled(ImVec2(lx+5, ly+5), 4, IM_COL32(247,118,142,255));
        dl->AddText(ImVec2(lx+12, ly), IM_COL32(160,165,190,230), "Avg (B)");
    }

    ImGui::Dummy(ImVec2(sz, sz));
}
