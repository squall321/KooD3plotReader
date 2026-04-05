#include "app/SphereReportApp.hpp"
#include <imgui.h>
#include <algorithm>
#include <vector>

void SphereReportApp::renderAngleTable() {
    ImGui::TextColored(COL_DIM,
        "Sorted by selected quantity. Click row to select/deselect on Mollweide map.");
    ImGui::Spacing();

    const char* qtyNames[] = {"Stress", "Strain", "G-Force", "Disp"};

    if (ImGui::BeginTable("##AngleTable", 7,
            ImGuiTableFlags_Sortable | ImGuiTableFlags_RowBg |
            ImGuiTableFlags_ScrollY | ImGuiTableFlags_SizingStretchProp |
            ImGuiTableFlags_BordersInnerV)) {

        ImGui::TableSetupScrollFreeze(0, 1);
        ImGui::TableSetupColumn("#",         ImGuiTableColumnFlags_WidthFixed,   30);
        ImGui::TableSetupColumn("Direction", ImGuiTableColumnFlags_WidthStretch);
        ImGui::TableSetupColumn("Category", ImGuiTableColumnFlags_WidthFixed,   70);
        ImGui::TableSetupColumn("Roll",      ImGuiTableColumnFlags_WidthFixed,   55);
        ImGui::TableSetupColumn("Pitch",     ImGuiTableColumnFlags_WidthFixed,   55);
        ImGui::TableSetupColumn(qtyNames[quantity_],
            ImGuiTableColumnFlags_DefaultSort | ImGuiTableColumnFlags_WidthFixed, 80);
        ImGui::TableSetupColumn("Sel", ImGuiTableColumnFlags_WidthFixed, 25);
        ImGui::TableHeadersRow();

        std::vector<std::pair<int,double>> sorted;
        sorted.reserve(data_.results.size());
        for (int ri = 0; ri < (int)data_.results.size(); ++ri) {
            if (!passesFilter(data_.results[ri].angle.category)) continue;
            sorted.push_back({ri, getAngleValue(ri, selectedPartId_, quantity_)});
        }
        std::sort(sorted.begin(), sorted.end(), [](const auto& a, const auto& b) { return a.second > b.second; });

        ImGuiListClipper clipper;
        clipper.Begin((int)sorted.size());
        while (clipper.Step()) {
            for (int i = clipper.DisplayStart; i < clipper.DisplayEnd; ++i) {
                int ri = sorted[i].first;
                auto& r = data_.results[ri];
                bool isSelected = selectedAngles_.count(ri);

                ImGui::TableNextRow();
                ImGui::TableSetColumnIndex(0);
                char label[16]; snprintf(label, sizeof(label), "%d", i+1);
                if (ImGui::Selectable(label, isSelected, ImGuiSelectableFlags_SpanAllColumns)) {
                    if (isSelected) selectedAngles_.erase(ri);
                    else            selectedAngles_.insert(ri);
                }
                ImGui::TableSetColumnIndex(1); ImGui::TextColored(COL_ACCENT, "%s", r.angle.name.c_str());
                ImGui::TableSetColumnIndex(2); ImGui::TextColored(COL_DIM, "%s", r.angle.category.c_str());
                ImGui::TableSetColumnIndex(3); ImGui::Text("%.1f", r.angle.roll);
                ImGui::TableSetColumnIndex(4); ImGui::Text("%.1f", r.angle.pitch);
                ImGui::TableSetColumnIndex(5); ImGui::Text("%.2f", sorted[i].second);
                ImGui::TableSetColumnIndex(6);
                ImGui::TextColored(isSelected ? COL_ACCENT : COL_DIM, isSelected ? "V" : "");
            }
        }
        ImGui::EndTable();
    }
}
