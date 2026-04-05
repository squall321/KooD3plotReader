#include "app/SphereReportApp.hpp"
#include <imgui.h>
#include <algorithm>
#include <vector>

void SphereReportApp::renderHeatmapTab() {
    ImGui::TextColored(COL_DIM,
        "Full part-by-angle heatmap. Each cell shows the selected quantity value.\n"
        "Color intensity proportional to value. Scroll horizontally for all angles.");
    ImGui::Spacing();

    if (data_.results.empty() || data_.parts.empty()) return;

    // Helper: extract quantity value from AnglePartData
    auto partQty = [&](const AnglePartData& pd) -> double {
        switch (quantity_) {
            case 0: return pd.peak_stress;
            case 1: return pd.peak_strain;
            case 2: return pd.peak_g;
            case 3: return pd.peak_disp;
        }
        return 0;
    };

    // Sort angles by worst value descending (respects category filter)
    std::vector<int> angleOrder;
    angleOrder.reserve(data_.results.size());
    for (int ri = 0; ri < (int)data_.results.size(); ++ri)
        if (passesFilter(data_.results[ri].angle.category)) angleOrder.push_back(ri);
    std::sort(angleOrder.begin(), angleOrder.end(), [&](int a, int b) {
        double va = 0, vb = 0;
        for (auto& [pid, pd] : data_.results[a].parts) va = std::max(va, partQty(pd));
        for (auto& [pid, pd] : data_.results[b].parts) vb = std::max(vb, partQty(pd));
        return va > vb;
    });

    int nAngles = std::min(50, (int)angleOrder.size());
    int ncols = 2 + nAngles;

    if (ImGui::BeginTable("##FullHeatmap", ncols,
            ImGuiTableFlags_ScrollX | ImGuiTableFlags_ScrollY |
            ImGuiTableFlags_RowBg | ImGuiTableFlags_BordersInnerV |
            ImGuiTableFlags_SizingFixedFit)) {

        ImGui::TableSetupScrollFreeze(2, 1);
        ImGui::TableSetupColumn("Part", 0, 35);
        ImGui::TableSetupColumn("Name", 0, 90);
        for (int i = 0; i < nAngles; ++i)
            ImGui::TableSetupColumn(data_.results[angleOrder[i]].angle.name.c_str(), 0, 50);
        ImGui::TableHeadersRow();

        double gmax = 1;
        for (auto& [pid, pi] : data_.parts)
            for (int i = 0; i < nAngles; ++i)
                gmax = std::max(gmax, getAngleValue(angleOrder[i], pid, quantity_));

        for (auto& [pid, pi] : data_.parts) {
            ImGui::TableNextRow();
            ImGui::TableSetColumnIndex(0); ImGui::Text("%d", pid);
            ImGui::TableSetColumnIndex(1); ImGui::TextUnformatted(pi.name.c_str());
            for (int i = 0; i < nAngles; ++i) {
                ImGui::TableSetColumnIndex(i + 2);
                double v  = getAngleValue(angleOrder[i], pid, quantity_);
                ImU32  bg = valueToColor(v / gmax);
                int r = (bg>>0)&0xFF, g = (bg>>8)&0xFF, b = (bg>>16)&0xFF;
                ImGui::TableSetBgColor(ImGuiTableBgTarget_CellBg, IM_COL32(r/3, g/3, b/3, 200));
                ImGui::Text("%.0f", v);
            }
        }
        ImGui::EndTable();
    }

    if ((int)angleOrder.size() > nAngles)
        ImGui::TextColored(COL_DIM, "Showing top %d of %d angles (sorted by worst value)",
            nAngles, (int)angleOrder.size());
}
