#include "app/SphereReportApp.hpp"
#include <imgui.h>
#include <algorithm>
#include <vector>

void SphereReportApp::renderPartRisk() {
    ImGui::TextColored(COL_DIM,
        "Part x Angle matrix. Color intensity = relative value. Red = high risk.");
    ImGui::Spacing();

    if (data_.results.empty() || data_.parts.empty()) return;

    // Top 20 angles by worst stress
    std::vector<std::pair<int,double>> sorted;
    for (int ri = 0; ri < (int)data_.results.size(); ++ri) {
        double maxV = 0;
        for (auto& [pid, pd] : data_.results[ri].parts)
            maxV = std::max(maxV, pd.peak_stress);
        sorted.push_back({ri, maxV});
    }
    std::sort(sorted.begin(), sorted.end(), [](auto& a, auto& b) { return a.second > b.second; });

    std::vector<int> topAngles;
    for (int i = 0; i < std::min(20, (int)sorted.size()); ++i)
        topAngles.push_back(sorted[i].first);

    int ncols = 2 + (int)topAngles.size();
    if (ImGui::BeginTable("##PartRisk", ncols,
            ImGuiTableFlags_ScrollX | ImGuiTableFlags_ScrollY |
            ImGuiTableFlags_RowBg | ImGuiTableFlags_BordersInnerV |
            ImGuiTableFlags_SizingFixedFit)) {

        ImGui::TableSetupScrollFreeze(2, 1);
        ImGui::TableSetupColumn("Part", 0, 40);
        ImGui::TableSetupColumn("Name", 0, 100);
        for (int ai : topAngles)
            ImGui::TableSetupColumn(data_.results[ai].angle.name.c_str(), 0, 55);
        ImGui::TableHeadersRow();

        double globalMax = 1;
        for (auto& [pid, pi] : data_.parts)
            for (int ai : topAngles)
                globalMax = std::max(globalMax, getAngleValue(ai, pid, quantity_));

        for (auto& [pid, pi] : data_.parts) {
            ImGui::TableNextRow();
            ImGui::TableSetColumnIndex(0); ImGui::Text("%d", pid);
            ImGui::TableSetColumnIndex(1); ImGui::TextUnformatted(pi.name.c_str());
            for (int ci = 0; ci < (int)topAngles.size(); ++ci) {
                ImGui::TableSetColumnIndex(ci + 2);
                double v    = getAngleValue(topAngles[ci], pid, quantity_);
                ImU32  bg   = valueToColor(v / globalMax);
                int r = (bg>>0)&0xFF, g = (bg>>8)&0xFF, b = (bg>>16)&0xFF;
                ImGui::TableSetBgColor(ImGuiTableBgTarget_CellBg, IM_COL32(r/3, g/3, b/3, 180));
                ImGui::Text("%.0f", v);
            }
        }
        ImGui::EndTable();
    }
}
