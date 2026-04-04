#include "app/SphereReportApp.hpp"
#include <imgui.h>
#include <algorithm>
#include <vector>

void SphereReportApp::renderFailureTab() {
    ImGui::TextColored(COL_DIM,
        "Failure prediction based on yield stress and strain limits.\n"
        "Parts exceeding material limits are flagged by direction.");
    ImGui::Spacing();

    if (data_.yield_stress <= 0) {
        ImGui::TextColored(COL_YELLOW, "No yield stress specified. Cannot perform failure analysis.");
        ImGui::TextColored(COL_DIM, "Set yield stress in koo_sphere_report: --yield-stress <MPa>");
        return;
    }

    ImGui::TextColored(COL_ACCENT, "  Safety Factor by Part (Global Worst Angle)");
    ImGui::Separator();
    ImGui::Spacing();

    struct PartFailure {
        int pid; std::string name, worst_angle;
        double worst_stress, safety_factor;
    };
    std::vector<PartFailure> failures;

    for (auto& [pid, pi] : data_.parts) {
        double worst = 0; std::string worstAngle;
        for (int ri = 0; ri < (int)data_.results.size(); ++ri) {
            auto it = data_.results[ri].parts.find(pid);
            if (it != data_.results[ri].parts.end() && it->second.peak_stress > worst) {
                worst = it->second.peak_stress;
                worstAngle = data_.results[ri].angle.name;
            }
        }
        double sf = worst > 0 ? data_.yield_stress / worst : 999;
        failures.push_back({pid, pi.name, worstAngle, worst, sf});
    }
    std::sort(failures.begin(), failures.end(), [](auto& a, auto& b) { return a.safety_factor < b.safety_factor; });

    if (ImGui::BeginTable("##FailureTable", 5,
            ImGuiTableFlags_RowBg | ImGuiTableFlags_ScrollY |
            ImGuiTableFlags_SizingStretchProp | ImGuiTableFlags_BordersInnerV)) {
        ImGui::TableSetupScrollFreeze(0, 1);
        ImGui::TableSetupColumn("Part");
        ImGui::TableSetupColumn("Name");
        ImGui::TableSetupColumn("Peak Stress (MPa)");
        ImGui::TableSetupColumn("Worst Angle");
        ImGui::TableSetupColumn("Safety Factor");
        ImGui::TableHeadersRow();

        for (auto& f : failures) {
            ImGui::TableNextRow();
            ImGui::TableSetColumnIndex(0); ImGui::Text("%d", f.pid);
            ImGui::TableSetColumnIndex(1); ImGui::TextUnformatted(f.name.c_str());
            ImGui::TableSetColumnIndex(2); ImGui::Text("%.1f", f.worst_stress);
            ImGui::TableSetColumnIndex(3); ImGui::TextColored(COL_ACCENT, "%s", f.worst_angle.c_str());
            ImGui::TableSetColumnIndex(4);
            ImVec4 sfCol = f.safety_factor >= 1.5 ? COL_ACCENT :
                           f.safety_factor >= 1.0 ? COL_YELLOW : COL_RED;
            ImGui::TextColored(sfCol, "%.3f%s", f.safety_factor,
                f.safety_factor < 1.0 ? " FAIL" : f.safety_factor < 1.5 ? " LOW" : "");
        }
        ImGui::EndTable();
    }

    int nFail = 0, nLow = 0;
    for (auto& f : failures) {
        if (f.safety_factor < 1.0)      nFail++;
        else if (f.safety_factor < 1.5) nLow++;
    }
    ImGui::Spacing();
    if (nFail > 0) ImGui::TextColored(COL_RED,    "!! %d parts EXCEED yield stress (SF < 1.0)", nFail);
    if (nLow  > 0) ImGui::TextColored(COL_YELLOW, "! %d parts have LOW safety margin (SF < 1.5)", nLow);
    if (nFail == 0 && nLow == 0)
        ImGui::TextColored(COL_ACCENT, "All parts within acceptable safety margins (SF >= 1.5)");
}
