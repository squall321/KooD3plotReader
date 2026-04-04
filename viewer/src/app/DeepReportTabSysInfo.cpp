#include "app/DeepReportApp.hpp"
#include "app/DeepReportColors.hpp"
#include <imgui.h>
#include <implot.h>
#include <algorithm>
#include <cstdio>
#include <cmath>
#include <string>

void DeepReportApp::renderSysInfoTab() {
    SectionHeader("Simulation Information", COL_ACCENT);
    ImGui::Spacing();

    auto infoRow = [](const char* label, const char* value) {
        ImGui::Text("  %-24s", label);
        ImGui::SameLine(220);
        ImGui::TextColored(ImVec4(0.85f,0.85f,0.90f,1), "%s", value);
    };

    char buf[256];
    infoRow("Label:", data_.label.c_str());
    snprintf(buf, sizeof(buf), "Tier %d", data_.tier);
    infoRow("Tier:", buf);
    infoRow("D3plot Path:", data_.d3plot_path.c_str());
    ImGui::SameLine();
    if (ImGui::SmallButton("Copy##dp")) ImGui::SetClipboardText(data_.d3plot_path.c_str());
    snprintf(buf, sizeof(buf), "%d", data_.num_states);
    infoRow("States:", buf);
    snprintf(buf, sizeof(buf), "%.6f — %.6f", data_.start_time, data_.end_time);
    infoRow("Time Range:", buf);
    snprintf(buf, sizeof(buf), "%d", (int)data_.parts.size());
    infoRow("Parts:", buf);
    infoRow("Termination:", data_.normal_termination ? "Normal" : "ERROR");
    infoRow("Termination Source:", data_.termination_source.c_str());
    if (data_.yield_stress > 0) {
        snprintf(buf, sizeof(buf), "%.1f MPa", data_.yield_stress);
        infoRow("Yield Stress:", buf);
    }

    ImGui::Spacing();
    SectionHeader("Data Files", COL_ACCENT);
    ImGui::Spacing();

    auto fileRow = [](const char* name, bool present) {
        ImGui::Text("  %-20s", name);
        ImGui::SameLine(200);
        if (present)
            ImGui::TextColored(ImVec4(0.31f,0.80f,0.64f,1), "Present");
        else
            ImGui::TextColored(ImVec4(0.55f,0.55f,0.62f,1), "Not found");
    };

    fileRow("analysis_result.json", !data_.stress.empty());
    fileRow("result.json", !data_.parts.empty() || !data_.glstat.t.empty());
    fileRow("motion/ CSVs", !data_.motion.empty());
    fileRow("renders/", !data_.render_files.empty());
    fileRow("binout (rcforc)", !data_.rcforc.empty());
    fileRow("binout (sleout)", !data_.sleout.empty());
    fileRow("binout (matsum)", !data_.matsum.empty());
    fileRow("element_quality", !data_.element_quality.empty());
    fileRow("tensors", !data_.tensors.empty());

    ImGui::Spacing();
    SectionHeader("Analysis Summary", COL_ACCENT);
    ImGui::Spacing();
    snprintf(buf, sizeof(buf), "%d stress + %d strain + %d principal + %d tensor + %d motion",
        (int)data_.stress.size(), (int)data_.strain.size(),
        (int)data_.max_principal.size(), (int)data_.tensors.size(),
        (int)data_.motion.size());
    infoRow("Time Series:", buf);
    snprintf(buf, sizeof(buf), "%d rcforc + %d sleout", (int)data_.rcforc.size(), (int)data_.sleout.size());
    infoRow("Contact:", buf);
    snprintf(buf, sizeof(buf), "%d render files", (int)data_.render_files.size());
    infoRow("Renders:", buf);
}


