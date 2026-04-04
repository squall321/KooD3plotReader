#include "app/SphereReportApp.hpp"
#include <imgui.h>
#include <implot.h>
#include <algorithm>
#include <vector>
#include <cstdio>

void SphereReportApp::renderCompareInfo() {
    if (selectedAngles_.empty()) {
        ImGui::TextColored(COL_DIM, "Click angles on Mollweide map or table to compare");
        return;
    }

    ImGui::TextColored(COL_ACCENT, "Selected Angles (%d):", (int)selectedAngles_.size());
    std::vector<int> toRemove;
    for (int ri : selectedAngles_) {
        ImGui::SameLine();
        char tag[64];
        snprintf(tag, sizeof(tag), "%s X##%d", data_.results[ri].angle.name.c_str(), ri);
        if (ImGui::SmallButton(tag)) toRemove.push_back(ri);
    }
    for (int ri : toRemove) selectedAngles_.erase(ri);
    ImGui::Spacing();

    if (ImGui::BeginTable("##Compare", 6,
            ImGuiTableFlags_RowBg | ImGuiTableFlags_BordersInnerV |
            ImGuiTableFlags_SizingStretchProp)) {
        ImGui::TableSetupColumn("Direction");
        ImGui::TableSetupColumn("Category");
        ImGui::TableSetupColumn("Peak Stress");
        ImGui::TableSetupColumn("Peak Strain");
        ImGui::TableSetupColumn("Peak G");
        ImGui::TableSetupColumn("Peak Disp");
        ImGui::TableHeadersRow();

        for (int ri : selectedAngles_) {
            auto& r  = data_.results[ri];
            auto  it = r.parts.find(selectedPartId_);
            if (it == r.parts.end()) continue;
            auto& pd = it->second;
            ImGui::TableNextRow();
            ImGui::TableSetColumnIndex(0); ImGui::TextColored(COL_ACCENT, "%s", r.angle.name.c_str());
            ImGui::TableSetColumnIndex(1); ImGui::Text("%s", r.angle.category.c_str());
            ImGui::TableSetColumnIndex(2); ImGui::Text("%.1f",  pd.peak_stress);
            ImGui::TableSetColumnIndex(3); ImGui::Text("%.4f",  pd.peak_strain);
            ImGui::TableSetColumnIndex(4); ImGui::Text("%.1f",  pd.peak_g);
            ImGui::TableSetColumnIndex(5); ImGui::Text("%.2f",  pd.peak_disp);
        }
        ImGui::EndTable();
    }

    // Time history overlay
    ImGui::Spacing();
    ImGui::TextColored(COL_ACCENT, "  Time History Overlay");
    ImGui::Separator();

    bool hasTS = false;
    for (int ri : selectedAngles_) {
        auto it = data_.results[ri].parts.find(selectedPartId_);
        if (it != data_.results[ri].parts.end() && !it->second.stress_ts.t.empty()) {
            hasTS = true; break;
        }
    }

    if (!hasTS) {
        ImGui::TextColored(COL_DIM,
            "No time series data in report.json. Regenerate with: koo_sphere_report --format json");
        return;
    }

    const char* tsQtyNames[] = {"Stress (MPa)", "Strain", "G-Force (MG)", "Displacement (mm)"};
    static int tsQty = 0;
    ImGui::RadioButton("Stress##ts", &tsQty, 0); ImGui::SameLine();
    ImGui::RadioButton("Strain##ts", &tsQty, 1); ImGui::SameLine();
    ImGui::RadioButton("G-Force##ts", &tsQty, 2); ImGui::SameLine();
    ImGui::RadioButton("Disp##ts", &tsQty, 3);

    ImVec2 sz(ImGui::GetContentRegionAvail().x, std::max(200.0f, ImGui::GetContentRegionAvail().y - 10));
    if (ImPlot::BeginPlot("##TimeHistOverlay", sz)) {
        ImPlot::SetupAxes("Time", tsQtyNames[tsQty]);
        for (int ri : selectedAngles_) {
            auto it = data_.results[ri].parts.find(selectedPartId_);
            if (it == data_.results[ri].parts.end()) continue;
            auto& pd = it->second;
            const TimeSeries* ts = nullptr;
            switch (tsQty) { case 0: ts=&pd.stress_ts; break; case 1: ts=&pd.strain_ts; break;
                             case 2: ts=&pd.g_ts;      break; case 3: ts=&pd.disp_ts;   break; }
            if (!ts || ts->t.empty() || ts->values.empty()) continue;
            int n = std::min((int)ts->t.size(), (int)ts->values.size());
            char label[64]; snprintf(label, sizeof(label), "%s", data_.results[ri].angle.name.c_str());
            ImPlot::PlotLine(label, ts->t.data(), ts->values.data(), n);
        }
        ImPlot::EndPlot();
    }
}
