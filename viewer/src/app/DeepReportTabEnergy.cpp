#include "app/DeepReportApp.hpp"
#include "app/DeepReportColors.hpp"
#include <imgui.h>
#include <implot.h>
#include <algorithm>
#include <cstdio>
#include <cmath>
#include <string>

void DeepReportApp::renderEnergyTab() {
    if (data_.glstat.t.empty()) {
        ImGui::TextColored(COL_DIM, "No energy data (no result.json with glstat)");
        return;
    }

    ImGui::TextColored(COL_DIM,
        "Energy balance: KE + IE + HG should equal Total. Ratio = IE/Total.\n"
        "Ratio > 1.05 warns of energy generation (numerical instability).\n"
        "Ratio < 1.0 is normal (dissipation from plasticity, damping, etc.).\n"
        "Mass increase = mass scaling activated (check timestep stability).");
    ImGui::Spacing();

    // Energy ratio warning
    if (data_.energy_ratio_min > 1.05) {
        ImVec4 col = data_.energy_ratio_min > 1.1 ? COL_RED : COL_YELLOW;
        ImVec4 bg = col; bg.w = 0.15f;
        ImGui::PushStyleColor(ImGuiCol_ChildBg, bg);
        ImGui::BeginChild("##erWarn", ImVec2(-1, 30), true);
        char msg[128];
        snprintf(msg, sizeof(msg), "Energy ratio min = %.4f (threshold: 1.05)", data_.energy_ratio_min);
        ImGui::TextColored(col, "  !! %s", msg);
        ImGui::EndChild();
        ImGui::PopStyleColor();
        ImGui::Spacing();
    }

    auto& g = data_.glstat;
    int n = (int)g.t.size();

    // Energy balance chart
    ImVec2 sz1(ImGui::GetContentRegionAvail().x, std::max(200.0f, ImGui::GetContentRegionAvail().y * 0.55f));
    if (ImPlot::BeginPlot("##Energy", sz1)) {
        ImPlot::SetupAxes("Time", "Energy");
        // Shaded fills first (drawn below lines)
        if ((int)g.kinetic_energy.size() == n) {
            ImPlot::PlotShaded("Kinetic##s", g.t.data(), g.kinetic_energy.data(), n, 0.0,
                ImPlotSpec(ImPlotProp_FillAlpha, 0.18f));
        }
        if ((int)g.internal_energy.size() == n) {
            ImPlot::PlotShaded("Internal##s", g.t.data(), g.internal_energy.data(), n, 0.0,
                ImPlotSpec(ImPlotProp_FillAlpha, 0.18f));
        }
        // Lines on top
        if ((int)g.kinetic_energy.size() == n)  ImPlot::PlotLine("Kinetic", g.t.data(), g.kinetic_energy.data(), n);
        if ((int)g.internal_energy.size() == n) ImPlot::PlotLine("Internal", g.t.data(), g.internal_energy.data(), n);
        if ((int)g.total_energy.size() == n)    ImPlot::PlotLine("Total", g.t.data(), g.total_energy.data(), n);
        if ((int)g.hourglass_energy.size() == n) ImPlot::PlotLine("Hourglass", g.t.data(), g.hourglass_energy.data(), n);
        ImPlot::EndPlot();
    }

    // Hourglass % annotation
    if (!g.hourglass_energy.empty() && !g.total_energy.empty() && (int)g.hourglass_energy.size() == n) {
        double hgMax = *std::max_element(g.hourglass_energy.begin(), g.hourglass_energy.end());
        double totEnd = g.total_energy.back();
        if (totEnd > 1e-20 && hgMax > 0) {
            double hgPct = hgMax / std::abs(totEnd) * 100.0;
            ImVec4 hgCol = hgPct > 5.0 ? COL_RED : hgPct > 2.0 ? COL_YELLOW : COL_ACCENT;
            ImGui::SameLine();
            ImGui::TextColored(hgCol, "  Hourglass max = %.2f%% of total", hgPct);
            if (hgPct > 5.0) {
                ImGui::SameLine();
                ImGui::TextColored(COL_RED, "  !! Excessive hourglass");
            }
        }
    }

    // Energy ratio chart
    if (!g.energy_ratio.empty() && (int)g.energy_ratio.size() == n) {
        ImGui::TextColored(COL_DIM, "Energy Ratio (internal/total)");
        ImVec2 sz2(ImGui::GetContentRegionAvail().x, std::max(80.0f, (ImGui::GetContentRegionAvail().y - 60.0f) * 0.5f));
        if (ImPlot::BeginPlot("##EnergyRatio", sz2)) {
            ImPlot::SetupAxes("Time", "Ratio");
            ImPlot::PlotLine("E_ratio", g.t.data(), g.energy_ratio.data(), n);
            // Reference lines
            double tRange[] = {g.t.front(), g.t.back()};
            double y10[] = {1.0, 1.0};
            double y105[] = {1.05, 1.05};
            ImPlot::PlotLine("1.0 (ideal)", tRange, y10, 2,
                ImPlotSpec(ImPlotProp_LineColor, ImVec4(0.4f,0.9f,0.4f,0.5f), ImPlotProp_LineWeight, 1.0f));
            ImPlot::PlotLine("1.05 (warn)", tRange, y105, 2,
                ImPlotSpec(ImPlotProp_LineColor, ImVec4(1.0f,0.75f,0.1f,0.6f), ImPlotProp_LineWeight, 1.0f));
            ImPlot::EndPlot();
        }
    }

    // Mass chart (if mass scaling detected)
    if (!g.mass.empty() && (int)g.mass.size() == n) {
        if (g.has_mass_added) {
            ImVec4 bg = COL_YELLOW; bg.w = 0.15f;
            ImGui::PushStyleColor(ImGuiCol_ChildBg, bg);
            ImGui::BeginChild("##massWarn", ImVec2(-1, 26), true);
            ImGui::TextColored(COL_YELLOW, "  ! Mass scaling detected — check mass history");
            ImGui::EndChild();
            ImGui::PopStyleColor();
        }
        ImGui::TextColored(COL_DIM, "Total Mass");
        ImVec2 sz3(ImGui::GetContentRegionAvail().x, std::max(60.0f, ImGui::GetContentRegionAvail().y - 5.0f));
        if (ImPlot::BeginPlot("##Mass", sz3)) {
            ImPlot::SetupAxes("Time", "Mass");
            ImPlot::PlotLine("Mass", g.t.data(), g.mass.data(), n);
            ImPlot::EndPlot();
        }
    }

    // Final values summary + pie chart
    if (!g.t.empty()) {
        ImGui::Spacing();
        ImGui::TextColored(COL_ACCENT, "  Final Energy Balance (t=%.4f)", g.t.back());
        ImGui::Separator();
        ImGui::Spacing();

        double totE  = g.total_energy.empty()    ? 0 : std::abs(g.total_energy.back());
        double kinE  = g.kinetic_energy.empty()  ? 0 : std::abs(g.kinetic_energy.back());
        double intE  = g.internal_energy.empty() ? 0 : std::abs(g.internal_energy.back());
        double hgE   = g.hourglass_energy.empty()? 0 : std::abs(g.hourglass_energy.back());
        double otherE = std::max(0.0, totE - kinE - intE - hgE);

        // Pie chart (left) + stats (right)
        ImGui::Columns(2, nullptr, false);

        // Left: ImPlot pie chart
        float pieSize = std::min(180.0f, ImGui::GetContentRegionAvail().y - 20);
        if (totE > 1e-20 && pieSize > 60) {
            static const char* pieLabels[] = {"KE", "IE", "HG", "Other"};
            double pieVals[4] = {kinE/totE*100, intE/totE*100, hgE/totE*100, otherE/totE*100};
            // Filter out near-zero slices
            int nSlices = 0;
            const char* activeLabels[4]; double activeVals[4];
            for (int i = 0; i < 4; ++i) {
                if (pieVals[i] > 0.5) {
                    activeLabels[nSlices] = pieLabels[i];
                    activeVals[nSlices]   = pieVals[i];
                    nSlices++;
                }
            }
            if (nSlices > 0) {
                ImPlot::PushColormap(ImPlotColormap_Cool);
                if (ImPlot::BeginPlot("##EnergyPie", ImVec2(pieSize, pieSize),
                        ImPlotFlags_Equal | ImPlotFlags_NoMouseText |
                        ImPlotFlags_NoFrame | ImPlotFlags_NoLegend)) {
                    ImPlot::SetupAxes(nullptr, nullptr,
                        ImPlotAxisFlags_NoDecorations, ImPlotAxisFlags_NoDecorations);
                    ImPlot::SetupAxesLimits(0, 1, 0, 1);
                    ImPlot::PlotPieChart(activeLabels, activeVals, nSlices,
                        0.5, 0.5, 0.4, "%.1f%%");
                    ImPlot::EndPlot();
                }
                ImPlot::PopColormap();
            }
        }
        ImGui::NextColumn();

        // Right: text values + warnings
        ImGui::Spacing();
        auto eRow = [&](const char* label, double val, double pct, ImVec4 col) {
            ImGui::TextColored(COL_DIM, "%-10s", label);
            ImGui::SameLine(110);
            ImGui::TextColored(col, "%.4g", val);
            if (totE > 1e-20) {
                ImGui::SameLine(210);
                ImGui::TextColored(COL_DIM, "(%.1f%%)", pct);
            }
        };
        eRow("Total",    totE,  100.0,           COL_ACCENT);
        eRow("Kinetic",  kinE,  kinE/totE*100,   COL_BLUE);
        eRow("Internal", intE,  intE/totE*100,   COL_YELLOW);
        eRow("Hourglass",hgE,   hgE/totE*100,    hgE/totE > 0.1 ? COL_RED : COL_DIM);
        if (otherE > 1e-20)
            eRow("Other", otherE, otherE/totE*100, COL_DIM);

        ImGui::Spacing();
        // Hourglass quality warning
        if (totE > 1e-20 && hgE > 0) {
            double hgPct = hgE / totE * 100.0;
            if (hgPct > 10.0)
                ImGui::TextColored(COL_RED,    "!! HG > 10%% — poor mesh quality / underintegration");
            else if (hgPct > 5.0)
                ImGui::TextColored(COL_YELLOW, "!  HG > 5%% — check element formulation");
            else
                ImGui::TextColored(COL_ACCENT, "Hourglass < 5%% — acceptable");
        }

        ImGui::Columns(1);
    }

    // Termination status
    ImGui::Spacing();
    if (g.normal_termination)
        ImGui::TextColored(COL_ACCENT, "Termination: Normal");
    else
        ImGui::TextColored(COL_RED, "Termination: ERROR");
}

// ============================================================
// Quality Tab: element quality metrics
// ============================================================

