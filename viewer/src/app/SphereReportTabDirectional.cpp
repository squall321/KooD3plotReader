#include "app/SphereReportApp.hpp"
#include <imgui.h>
#include <algorithm>
#include <map>
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
    std::map<std::string, std::vector<double>> catVals;
    for (int ri = 0; ri < (int)data_.results.size(); ++ri)
        catVals[data_.results[ri].angle.category].push_back(
            getAngleValue(ri, selectedPartId_, quantity_));
    for (auto& [cat, vals] : catVals) {
        double avg = 0, maxC = 0;
        for (double v : vals) { avg += v; maxC = std::max(maxC, v); }
        avg /= vals.size();
        ImGui::Text("  %-12s  count=%d  avg=%.1f  max=%.1f",
            cat.c_str(), (int)vals.size(), avg, maxC);
    }
}
