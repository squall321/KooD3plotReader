#include "app/SphereReportApp.hpp"
#include <imgui.h>
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <vector>

// A/B Delta tab — shows per-angle delta (A - B) on a Mollweide map
// and a table with A, B, delta, and improvement/worsening columns.

void SphereReportApp::renderCompareABTab() {
    if (!hasDataB_) {
        ImGui::TextColored(COL_DIM, "Drop a second JSON file to enable A/B comparison.");
        return;
    }

    ImGui::TextColored(COL_DIM,
        "Delta map: A - B per angle. Blue = improved (lower in B), Red = worsened (higher in B).\n"
        "Angles matched by name. Unmatched angles shown as grey.");
    ImGui::Spacing();

    const char* qtyNames[] = {"Stress (MPa)", "Strain", "G-Force", "Disp (mm)"};
    ImGui::Text("Quantity:");
    ImGui::SameLine();
    for (int q = 0; q < 4; ++q) {
        if (q) ImGui::SameLine();
        if (ImGui::RadioButton(qtyNames[q], quantity_ == q)) quantity_ = q;
    }
    ImGui::Spacing();

    // Build lookup: angle name → B index
    std::map<std::string, int> bIdx;
    for (int ri = 0; ri < (int)dataB_.results.size(); ++ri)
        bIdx[dataB_.results[ri].angle.name] = ri;

    // Collect deltas for colour range
    struct DeltaEntry {
        int   riA;
        int   riB;   // -1 if no match
        double valA, valB, delta;
        std::string name, category;
        double lon, lat;
    };
    std::vector<DeltaEntry> entries;
    entries.reserve(data_.results.size());

    double dmin = 1e18, dmax = -1e18;
    for (int ri = 0; ri < (int)data_.results.size(); ++ri) {
        auto& r = data_.results[ri];
        if (!passesFilter(r.angle.category)) continue;
        double vA = 0;
        for (auto& [pid, pd] : r.parts) {
            double v = 0;
            switch (quantity_) {
                case 0: v = pd.peak_stress; break;
                case 1: v = pd.peak_strain; break;
                case 2: v = pd.peak_g;      break;
                case 3: v = pd.peak_disp;   break;
            }
            vA = std::max(vA, v);
        }
        DeltaEntry e;
        e.riA  = ri;
        e.name = r.angle.name;
        e.category = r.angle.category;
        e.lon  = r.angle.lon;
        e.lat  = r.angle.lat;
        e.valA = vA;

        auto it = bIdx.find(r.angle.name);
        if (it != bIdx.end()) {
            int rb = it->second;
            double vB = 0;
            for (auto& [pid, pd] : dataB_.results[rb].parts) {
                double v = 0;
                switch (quantity_) {
                    case 0: v = pd.peak_stress; break;
                    case 1: v = pd.peak_strain; break;
                    case 2: v = pd.peak_g;      break;
                    case 3: v = pd.peak_disp;   break;
                }
                vB = std::max(vB, v);
            }
            e.riB   = rb;
            e.valB  = vB;
            e.delta = vA - vB;   // positive = worsened in A, negative = improved in A
            dmin = std::min(dmin, e.delta);
            dmax = std::max(dmax, e.delta);
        } else {
            e.riB  = -1;
            e.valB = 0;
            e.delta = 0;
        }
        entries.push_back(e);
    }

    double absMax = std::max(std::abs(dmin), std::abs(dmax));
    if (absMax < 1e-9) absMax = 1.0;

    // ---- Mollweide delta map ----
    ImVec2 avail = ImGui::GetContentRegionAvail();
    float mapW = avail.x;
    float mapH = std::min(avail.y * 0.45f, 260.0f);
    ImVec2 origin = ImGui::GetCursorScreenPos();
    ImDrawList* dl = ImGui::GetWindowDrawList();

    // Background
    dl->AddRectFilled(origin, ImVec2(origin.x + mapW, origin.y + mapH),
                      IM_COL32(18, 20, 32, 255), 6);

    // Mollweide ellipse outline
    float cx = origin.x + mapW * 0.5f, cy = origin.y + mapH * 0.5f;
    float rx = mapW * 0.46f, ry = mapH * 0.46f;
    dl->AddEllipse(ImVec2(cx, cy), ImVec2(rx, ry), IM_COL32(60, 65, 90, 255), 0, 64, 1.5f);

    auto toScreen = [&](double lon, double lat, float& sx, float& sy) {
        double mx, my;
        mollweideProject(lon, lat, mx, my);
        sx = cx + (float)(mx / 2.828f) * rx;
        sy = cy - (float)(my / 1.414f) * ry;
    };

    // Draw dots coloured by delta
    for (auto& e : entries) {
        float sx, sy;
        toScreen(e.lon, e.lat, sx, sy);

        ImU32 col;
        if (e.riB < 0) {
            col = IM_COL32(80, 80, 90, 160);  // grey = no match in B
        } else {
            float t = (float)(e.delta / absMax);  // [-1, +1]
            // positive (A worse) → red, negative (A better) → blue
            if (t >= 0) col = IM_COL32((int)(t*220+35), (int)(35*(1-t)), (int)(35*(1-t)), 220);
            else        col = IM_COL32((int)(35*(1+t)), (int)(35*(1+t)), (int)(-t*220+35), 220);
        }
        dl->AddCircleFilled(ImVec2(sx, sy), 5.5f, col);
        dl->AddCircle(ImVec2(sx, sy), 5.5f, IM_COL32(255,255,255,40), 0, 0.8f);
    }

    // Colour legend
    {
        float lx = origin.x + 8, ly = origin.y + mapH - 28;
        for (int i = 0; i <= 40; ++i) {
            float t = (i - 20) / 20.0f;
            ImU32 c;
            if (t >= 0) c = IM_COL32((int)(t*220+35), 35, 35, 255);
            else        c = IM_COL32(35, 35, (int)(-t*220+35), 255);
            dl->AddRectFilled(ImVec2(lx+i*4, ly), ImVec2(lx+i*4+4, ly+12), c);
        }
        dl->AddText(ImVec2(lx,     ly+14), IM_COL32(100,120,255,255), "Better");
        dl->AddText(ImVec2(lx+130, ly+14), IM_COL32(255,80,80,255),   "Worse");
    }

    ImGui::Dummy(ImVec2(mapW, mapH));
    ImGui::Spacing();

    // ---- Summary stats ----
    int nImproved = 0, nWorsened = 0, nMissing = 0;
    double totalDelta = 0;
    for (auto& e : entries) {
        if (e.riB < 0) { nMissing++; continue; }
        totalDelta += e.delta;
        if (e.delta < -0.01) nImproved++;
        else if (e.delta > 0.01) nWorsened++;
    }
    ImGui::TextColored(COL_ACCENT, "  A vs B — %s", qtyNames[quantity_]);
    ImGui::Separator();
    ImGui::Text("  Matched: %d angles   Improved: ", (int)(entries.size() - nMissing));
    ImGui::SameLine();
    ImGui::TextColored(COL_BLUE, "%d", nImproved);
    ImGui::SameLine();
    ImGui::Text("  Worsened: ");
    ImGui::SameLine();
    ImGui::TextColored(COL_RED, "%d", nWorsened);
    ImGui::SameLine();
    ImGui::Text("  Unmatched: %d   Avg delta: %.2f", nMissing, (int)(entries.size()-nMissing) > 0 ? totalDelta/(entries.size()-nMissing) : 0.0);
    ImGui::Spacing();

    // ---- Delta table (top 30 by abs delta) ----
    std::vector<DeltaEntry*> sorted;
    sorted.reserve(entries.size());
    for (auto& e : entries) if (e.riB >= 0) sorted.push_back(&e);
    std::sort(sorted.begin(), sorted.end(), [](auto* a, auto* b) {
        return std::abs(a->delta) > std::abs(b->delta);
    });

    if (ImGui::BeginTable("##ABDelta", 6,
            ImGuiTableFlags_RowBg | ImGuiTableFlags_ScrollY |
            ImGuiTableFlags_SizingStretchProp | ImGuiTableFlags_BordersInnerV)) {
        ImGui::TableSetupScrollFreeze(0, 1);
        ImGui::TableSetupColumn("Direction");
        ImGui::TableSetupColumn("Cat");
        ImGui::TableSetupColumn("A");
        ImGui::TableSetupColumn("B");
        ImGui::TableSetupColumn("Delta");
        ImGui::TableSetupColumn("Change");
        ImGui::TableHeadersRow();

        for (auto* e : sorted) {
            ImGui::TableNextRow();
            ImGui::TableSetColumnIndex(0); ImGui::TextColored(COL_ACCENT, "%s", e->name.c_str());
            ImGui::TableSetColumnIndex(1); ImGui::TextColored(COL_DIM,    "%s", e->category.c_str());
            ImGui::TableSetColumnIndex(2); ImGui::Text("%.2f", e->valA);
            ImGui::TableSetColumnIndex(3); ImGui::Text("%.2f", e->valB);
            ImGui::TableSetColumnIndex(4);
            ImVec4 dc = e->delta > 0 ? COL_RED : COL_BLUE;
            ImGui::TextColored(dc, "%+.2f", e->delta);
            ImGui::TableSetColumnIndex(5);
            double pct = e->valB > 1e-9 ? e->delta / e->valB * 100.0 : 0.0;
            ImGui::TextColored(dc, "%+.1f%%", pct);
        }
        ImGui::EndTable();
    }
}
