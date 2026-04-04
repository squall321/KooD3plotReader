#include "app/DeepReportApp.hpp"
#include "app/DeepReportColors.hpp"
#include <imgui.h>
#include <implot.h>
#include <algorithm>
#include <cstdio>
#include <cmath>
#include <string>

void DeepReportApp::renderStressTab() {
    renderWarnings();

    ImGui::TextColored(COL_DIM,
        "Von Mises: equivalent uniaxial stress from multiaxial state. SF = yield / peak.\n"
        "Principal stress: eigenvalues of stress tensor. S1 (max tension), S3 (max compression).\n"
        "Eff. plastic strain: accumulated irreversible deformation (0 = elastic only).");
    ImGui::Spacing();

    // Von Mises ranking (bars colored by warning status)
    {
        struct Entry { int pid; double val; std::string warn; std::string name; };
        std::vector<Entry> items;
        for (const auto& [pid, ps] : data_.parts)
            if (partPassesFilter(pid, ps.name))
                items.push_back({pid, ps.peak_stress, ps.stress_warning, ps.name});
        std::sort(items.begin(), items.end(), [](const auto& a, const auto& b) { return a.val > b.val; });
        items.erase(std::remove_if(items.begin(), items.end(), [](const auto& x){ return x.val <= 0; }), items.end());
        if (!items.empty()) {
            SectionHeader("Von Mises Stress Ranking", COL_ACCENT);
            double mx = std::max(items[0].val, 1e-10);
            int showN = (int)std::min(items.size(), (size_t)10);
            for (int i = 0; i < showN; ++i) {
                auto& e = items[i];
                ImVec4 bc = (e.warn == "crit") ? COL_RED : (e.warn == "warn") ? COL_YELLOW : COL_ACCENT;
                float pct = (float)(e.val / mx);
                char lbl[96]; snprintf(lbl, sizeof(lbl), "P%d  %s", e.pid,
                    e.name.size() > 18 ? (e.name.substr(0,17) + "\xe2\x80\xa6").c_str() : e.name.c_str());
                ImGui::Text("%-24s", lbl); ImGui::SameLine(220);
                ImGui::PushStyleColor(ImGuiCol_PlotHistogram, bc);
                char ov[32]; snprintf(ov, sizeof(ov), "%.1f MPa", e.val);
                ImGui::ProgressBar(pct, ImVec2(-1, 20), ov);
                ImGui::PopStyleColor();
                if (ImGui::IsItemClicked()) { deepDivePartId_ = e.pid; navigateToDeepDive_ = true; }
                if (ImGui::IsItemHovered()) { ImGui::SetMouseCursor(ImGuiMouseCursor_Hand); ImGui::SetTooltip("P%d  %s\nClick → Deep Dive", e.pid, e.name.c_str()); }
            }
            ImGui::Spacing();
        }
    }

    // Strain ranking (bars colored by warning)
    {
        struct Entry { int pid; double val; std::string warn; std::string name; };
        std::vector<Entry> items;
        for (const auto& [pid, ps] : data_.parts)
            if (ps.peak_strain > 0 && partPassesFilter(pid, ps.name))
                items.push_back({pid, ps.peak_strain, ps.strain_warning, ps.name});
        std::sort(items.begin(), items.end(), [](const auto& a, const auto& b) { return a.val > b.val; });
        if (!items.empty()) {
            SectionHeader("Eff. Plastic Strain Ranking", COL_YELLOW);
            double mx = std::max(items[0].val, 1e-10);
            int showN = (int)std::min(items.size(), (size_t)10);
            for (int i = 0; i < showN; ++i) {
                auto& e = items[i];
                ImVec4 bc = (e.warn == "crit") ? COL_RED : (e.warn == "warn") ? COL_YELLOW : ImVec4(0.96f,0.65f,0.14f,0.8f);
                float pct = (float)(e.val / mx);
                char lbl[96]; snprintf(lbl, sizeof(lbl), "P%d  %s", e.pid,
                    e.name.size() > 18 ? (e.name.substr(0,17) + "…").c_str() : e.name.c_str());
                ImGui::Text("%-24s", lbl); ImGui::SameLine(220);
                ImGui::PushStyleColor(ImGuiCol_PlotHistogram, bc);
                char ov[32]; snprintf(ov, sizeof(ov), "%.4f", e.val);
                ImGui::ProgressBar(pct, ImVec2(-1, 20), ov);
                ImGui::PopStyleColor();
                if (ImGui::IsItemClicked()) { deepDivePartId_ = e.pid; navigateToDeepDive_ = true; }
                if (ImGui::IsItemHovered()) { ImGui::SetMouseCursor(ImGuiMouseCursor_Hand); ImGui::SetTooltip("P%d  %s\nClick → Deep Dive", e.pid, e.name.c_str()); }
            }
            ImGui::Spacing();
        }
    }

    // ε₁ ranking (max principal strain)
    {
        struct Entry { int pid; double val; std::string name; };
        std::vector<Entry> items;
        for (const auto& [pid, ps] : data_.parts)
            if (ps.peak_max_principal_strain != 0 && partPassesFilter(pid, ps.name))
                items.push_back({pid, ps.peak_max_principal_strain, ps.name});
        std::sort(items.begin(), items.end(), [](const auto& a, const auto& b){ return a.val > b.val; });
        if (!items.empty()) {
            ImGui::Spacing();
            SectionHeader("Max Principal Strain  \xce\xb5\xe2\x82\x81  Ranking", ImVec4(0.15f,0.75f,0.45f,1));
            double mx = std::max(items[0].val, 1e-10);
            int showN = (int)std::min(items.size(), (size_t)10);
            for (int i = 0; i < showN; ++i) {
                auto& e = items[i];
                float pct = (float)(e.val / mx);
                char lbl[96]; snprintf(lbl, sizeof(lbl), "P%d  %s", e.pid,
                    e.name.size() > 18 ? (e.name.substr(0,17) + "…").c_str() : e.name.c_str());
                ImGui::Text("%-24s", lbl); ImGui::SameLine(220);
                ImGui::PushStyleColor(ImGuiCol_PlotHistogram, ImVec4(0.15f,0.75f,0.45f,0.85f));
                char ov[32]; snprintf(ov, sizeof(ov), "%.4f", e.val);
                ImGui::ProgressBar(pct, ImVec2(-1, 20), ov);
                ImGui::PopStyleColor();
                if (ImGui::IsItemClicked()) { deepDivePartId_ = e.pid; navigateToDeepDive_ = true; }
                if (ImGui::IsItemHovered()) { ImGui::SetMouseCursor(ImGuiMouseCursor_Hand); ImGui::SetTooltip("P%d  %s\nClick → Deep Dive", e.pid, e.name.c_str()); }
            }
            ImGui::Spacing();
        }
    }

    // ε₃ ranking (min principal strain — most compressive)
    {
        struct Entry { int pid; double val; std::string name; };
        std::vector<Entry> items;
        for (const auto& [pid, ps] : data_.parts)
            if (ps.peak_min_principal_strain != 0 && partPassesFilter(pid, ps.name))
                items.push_back({pid, ps.peak_min_principal_strain, ps.name});
        std::sort(items.begin(), items.end(), [](const auto& a, const auto& b){ return a.val < b.val; });
        if (!items.empty()) {
            ImGui::Spacing();
            SectionHeader("Min Principal Strain  \xce\xb5\xe2\x82\x83  Ranking  (Compression)", ImVec4(0.35f,0.45f,0.75f,1));
            double mx = std::max(std::abs(items[0].val), 1e-10);
            int showN = (int)std::min(items.size(), (size_t)10);
            for (int i = 0; i < showN; ++i) {
                auto& e = items[i];
                float pct = (float)(std::abs(e.val) / mx);
                char lbl[96]; snprintf(lbl, sizeof(lbl), "P%d  %s", e.pid,
                    e.name.size() > 18 ? (e.name.substr(0,17) + "…").c_str() : e.name.c_str());
                ImGui::Text("%-24s", lbl); ImGui::SameLine(220);
                ImGui::PushStyleColor(ImGuiCol_PlotHistogram, ImVec4(0.35f,0.45f,0.75f,0.85f));
                char ov[32]; snprintf(ov, sizeof(ov), "%.4f", e.val);
                ImGui::ProgressBar(pct, ImVec2(-1, 20), ov);
                ImGui::PopStyleColor();
                if (ImGui::IsItemClicked()) { deepDivePartId_ = e.pid; navigateToDeepDive_ = true; }
                if (ImGui::IsItemHovered()) { ImGui::SetMouseCursor(ImGuiMouseCursor_Hand); ImGui::SetTooltip("P%d  %s\nClick → Deep Dive", e.pid, e.name.c_str()); }
            }
            ImGui::Spacing();
        }
    }

    // Time series: stress overlay (with yield line)
    SectionHeader("Stress Time History", COL_ACCENT);
    {
        ImVec2 sz(ImGui::GetContentRegionAvail().x, std::max(250.0f, ImGui::GetContentRegionAvail().y * 0.3f));
        if (ImPlot::BeginPlot("##StressTS", sz)) {
            ImPlot::SetupAxes("Time", "Von Mises (MPa)");
            int colorIdx = 0;
            for (const auto& ts : data_.stress) {
                if (ts.data.empty()) continue;
                if (!partPassesFilter(ts.part_id, ts.part_name)) continue;
                bool show = selectedParts_.empty() || selectedParts_.count(ts.part_id);
                if (!show) continue;
                std::vector<double> t(ts.data.size()), vmax(ts.data.size()), vavg(ts.data.size());
                for (size_t i = 0; i < ts.data.size(); ++i) {
                    t[i] = ts.data[i].time;
                    vmax[i] = ts.data[i].max_value;
                    vavg[i] = ts.data[i].avg_value;
                }
                // Max line — color by warning status
                char label[64]; snprintf(label, sizeof(label), "P%d %s max", ts.part_id, ts.part_name.c_str());
                auto partIt = data_.parts.find(ts.part_id);
                ImVec4 lineCol(0, 0, 0, 0);  // auto if zero alpha
                if (partIt != data_.parts.end()) {
                    const auto& sw = partIt->second.stress_warning;
                    if (sw == "crit") lineCol = COL_RED;
                    else if (sw == "warn") { lineCol = COL_YELLOW; lineCol.w = 0.9f; }
                }
                if (lineCol.w > 0)
                    ImPlot::PlotLine(label, t.data(), vmax.data(), (int)t.size(),
                        ImPlotSpec(ImPlotProp_LineColor, lineCol, ImPlotProp_LineWeight, 1.8f));
                else
                    ImPlot::PlotLine(label, t.data(), vmax.data(), (int)t.size());
                // Avg line (same color, thinner + dimmed)
                ImVec4 col = ImPlot::GetLastItemColor();
                col.w = 0.45f;
                char avgLabel[64]; snprintf(avgLabel, sizeof(avgLabel), "P%d avg", ts.part_id);
                ImPlot::PlotLine(avgLabel, t.data(), vavg.data(), (int)t.size(),
                    ImPlotSpec(ImPlotProp_LineColor, col, ImPlotProp_LineWeight, 1.0f));
                ++colorIdx;
            }
            // Yield stress horizontal line
            if (data_.yield_stress > 0) {
                double xt[] = {data_.start_time, data_.end_time};
                double yt[] = {data_.yield_stress, data_.yield_stress};
                ImVec4 yieldCol(1.0f, 0.3f, 0.3f, 0.9f);
                ImPlot::PlotLine("Yield", xt, yt, 2,
                    ImPlotSpec(ImPlotProp_LineColor, yieldCol, ImPlotProp_LineWeight, 1.5f));
            }
            // Peak time vertical markers (one per shown part)
            for (const auto& ts : data_.stress) {
                if (!partPassesFilter(ts.part_id, ts.part_name)) continue;
                bool show = selectedParts_.empty() || selectedParts_.count(ts.part_id);
                if (!show) continue;
                auto it2 = data_.parts.find(ts.part_id);
                if (it2 == data_.parts.end()) continue;
                double tpeak = it2->second.time_of_peak_stress;
                if (tpeak <= 0) continue;
                ImPlot::PlotInfLines(("##pk" + std::to_string(ts.part_id)).c_str(), &tpeak, 1);
            }
            ImPlot::EndPlot();
        }
    }

    // Time series: strain overlay
    if (!data_.strain.empty()) {
        SectionHeader("Strain Time History", COL_YELLOW);
        drawTimeSeriesPlot("##StrainTS", "Eff. Plastic Strain", data_.strain, false);
    }

    // Principal stress
    if (!data_.max_principal.empty()) {
        SectionHeader("Max Principal Stress (\xcf\x83" "1)", COL_BLUE);
        drawTimeSeriesPlot("##MaxPrinTS", "sigma_1 (MPa)", data_.max_principal, false);
    }
    if (!data_.min_principal.empty()) {
        SectionHeader("Min Principal Stress (\xcf\x83" "3)", COL_PURPLE);
        drawTimeSeriesPlot("##MinPrinTS", "sigma_3 (MPa)", data_.min_principal, false);
    }

    // Principal strain
    if (!data_.max_principal_strain.empty()) {
        SectionHeader("Max Principal Strain (\xce\xb5" "1)", ImVec4(0.15f,0.68f,0.38f,1.0f));
        drawTimeSeriesPlot("##MaxPSTS", "eps_1", data_.max_principal_strain, false);
    }
    if (!data_.min_principal_strain.empty()) {
        SectionHeader("Min Principal Strain (\xce\xb5" "3)", ImVec4(0.35f,0.45f,0.75f,1.0f));
        drawTimeSeriesPlot("##MinPSTS", "eps_3", data_.min_principal_strain, false);
    }
}


