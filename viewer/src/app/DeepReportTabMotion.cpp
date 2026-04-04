#include "app/DeepReportApp.hpp"
#include "app/DeepReportColors.hpp"
#include <imgui.h>
#include <implot.h>
#include <algorithm>
#include <cstdio>
#include <cmath>
#include <string>

void DeepReportApp::renderMotionTab() {
    if (data_.motion.empty()) {
        ImGui::TextColored(COL_DIM, "No motion data (no motion/ CSV files)");
        return;
    }

    ImGui::TextColored(COL_DIM,
        "Displacement: part center-of-mass movement from initial position.\n"
        "Velocity: time derivative of displacement. Acceleration: time derivative of velocity.\n"
        "'avg' = average over all nodes in part. 'max' = node with largest displacement magnitude.");
    ImGui::Spacing();

    // ── Peak ranking ─────────────────────────────────────────
    {
        struct PeakEntry { int part_id; std::string name; double peak_disp, peak_vel, peak_acc; };
        std::vector<PeakEntry> peakList;
        for (const auto& ms : data_.motion) {
            if (!partPassesFilter(ms.part_id, ms.part_name)) continue;
            PeakEntry e; e.part_id = ms.part_id; e.name = ms.part_name;
            e.peak_disp = ms.max_disp_mag.empty() ? 0 :
                *std::max_element(ms.max_disp_mag.begin(), ms.max_disp_mag.end());
            e.peak_vel = ms.vel_mag.empty() ? 0 :
                *std::max_element(ms.vel_mag.begin(), ms.vel_mag.end());
            e.peak_acc = ms.acc_mag.empty() ? 0 :
                *std::max_element(ms.acc_mag.begin(), ms.acc_mag.end());
            peakList.push_back(e);
        }

        float tableH = std::min((float)(peakList.size() + 1) * 22.0f + 10.0f,
                                ImGui::GetContentRegionAvail().y * 0.28f);
        tableH = std::max(tableH, 48.0f);

        if (ImGui::BeginTable("##MotionPeak", 5,
                ImGuiTableFlags_RowBg | ImGuiTableFlags_SizingStretchProp |
                ImGuiTableFlags_BordersInnerV | ImGuiTableFlags_ScrollY, ImVec2(-1, tableH))) {
            ImGui::TableSetupScrollFreeze(0, 1);
            ImGui::TableSetupColumn("Part", ImGuiTableColumnFlags_WidthFixed, 44);
            ImGui::TableSetupColumn("Name", ImGuiTableColumnFlags_WidthStretch);
            ImGui::TableSetupColumn("Peak |U| (mm)", ImGuiTableColumnFlags_WidthFixed, 110);
            ImGui::TableSetupColumn("Peak |V| (mm/s)", ImGuiTableColumnFlags_WidthFixed, 120);
            ImGui::TableSetupColumn("Peak |A|", ImGuiTableColumnFlags_WidthFixed, 90);
            ImGui::TableHeadersRow();

            for (const auto& e : peakList) {
                ImGui::TableNextRow();
                ImGui::TableSetColumnIndex(0); ImGui::Text("%d", e.part_id);
                ImGui::TableSetColumnIndex(1); ImGui::TextUnformatted(e.name.c_str());
                ImGui::TableSetColumnIndex(2);
                ImGui::TextColored(e.peak_disp > 0 ? COL_PURPLE : COL_DIM, "%.2f", e.peak_disp);
                ImGui::TableSetColumnIndex(3);
                ImGui::TextColored(e.peak_vel > 0 ? COL_ACCENT : COL_DIM, "%.2f", e.peak_vel);
                ImGui::TableSetColumnIndex(4);
                ImGui::TextColored(e.peak_acc > 0 ? COL_YELLOW : COL_DIM, "%.2f", e.peak_acc);
            }
            ImGui::EndTable();
        }
        ImGui::Spacing();
    }

    // ── 4 simultaneous charts: |U| mag, U xyz, |V|, |A| ──────
    static const ImVec4 cX(0.91f,0.27f,0.38f,1), cY(0.15f,0.75f,0.45f,1), cZ(0.31f,0.56f,1.0f,1);

    // Pre-check what data exists across all parts
    bool anyXYZ  = std::any_of(data_.motion.begin(), data_.motion.end(),
                    [](const auto& m){ return !m.disp_x.empty(); });
    bool anyVel  = std::any_of(data_.motion.begin(), data_.motion.end(),
                    [](const auto& m){ return !m.vel_mag.empty(); });
    bool anyAcc  = std::any_of(data_.motion.begin(), data_.motion.end(),
                    [](const auto& m){ return !m.acc_mag.empty(); });

    int numCharts = 1 + (anyXYZ?1:0) + (anyVel?1:0) + (anyAcc?1:0);
    float avail = ImGui::GetContentRegionAvail().y;
    float chartH = std::max(120.0f, (avail - 8.0f * numCharts) / numCharts);

    // Helper: plot all parts for a given magnitude vector
    auto plotMag = [&](const char* plotId, const char* yLabel,
                       std::function<const std::vector<double>*(const DeepReportData::MotionSeries&)> getter,
                       std::function<const std::vector<double>*(const DeepReportData::MotionSeries&)> getMax = nullptr)
    {
        if (ImPlot::BeginPlot(plotId, ImVec2(-1, chartH))) {
            ImPlot::SetupAxes("Time", yLabel);
            for (const auto& ms : data_.motion) {
                if (ms.t.empty()) continue;
                if (!partPassesFilter(ms.part_id, ms.part_name)) continue;
                if (!selectedParts_.empty() && !selectedParts_.count(ms.part_id)) continue;
                int n = (int)ms.t.size();
                const auto* mag = getter(ms);
                if (mag && (int)mag->size() == n) {
                    char lbl[48]; snprintf(lbl, sizeof(lbl), "P%d avg", ms.part_id);
                    ImPlot::PlotLine(lbl, ms.t.data(), mag->data(), n);
                }
                if (getMax) {
                    const auto* mx = getMax(ms);
                    if (mx && (int)mx->size() == n) {
                        ImVec4 c = ImPlot::GetLastItemColor(); c.w *= 0.55f;
                        char lbl2[48]; snprintf(lbl2, sizeof(lbl2), "P%d max##%d", ms.part_id, ms.part_id);
                        ImPlot::PlotLine(lbl2, ms.t.data(), mx->data(), n,
                            ImPlotSpec(ImPlotProp_LineColor, c, ImPlotProp_LineWeight, 1.0f));
                    }
                }
            }
            ImPlot::EndPlot();
        }
    };

    // Chart 1: Displacement magnitude (avg + max)
    SectionHeader("Displacement |U|  (mm)", COL_PURPLE, 1);
    plotMag("##MotDisp", "mm",
        [](const auto& m) -> const std::vector<double>* { return &m.disp_mag; },
        [](const auto& m) -> const std::vector<double>* { return m.max_disp_mag.empty() ? nullptr : &m.max_disp_mag; });

    // Chart 2: Displacement XYZ components
    if (anyXYZ) {
        ImGui::Spacing();
        ImGui::TextColored(COL_DIM, "  Displacement XYZ  (mm)");
        if (ImPlot::BeginPlot("##MotDispXYZ", ImVec2(-1, chartH))) {
            ImPlot::SetupAxes("Time", "mm");
            for (const auto& ms : data_.motion) {
                if (ms.t.empty() || ms.disp_x.empty()) continue;
                if (!partPassesFilter(ms.part_id, ms.part_name)) continue;
                if (!selectedParts_.empty() && !selectedParts_.count(ms.part_id)) continue;
                int n = (int)ms.t.size();
                if ((int)ms.disp_x.size() == n) {
                    char lx[48], ly[48], lz[48];
                    snprintf(lx, sizeof(lx), "P%d Ux", ms.part_id);
                    snprintf(ly, sizeof(ly), "P%d Uy", ms.part_id);
                    snprintf(lz, sizeof(lz), "P%d Uz", ms.part_id);
                    ImPlot::PlotLine(lx, ms.t.data(), ms.disp_x.data(), n, ImPlotSpec(ImPlotProp_LineColor, cX));
                    ImPlot::PlotLine(ly, ms.t.data(), ms.disp_y.data(), n, ImPlotSpec(ImPlotProp_LineColor, cY));
                    ImPlot::PlotLine(lz, ms.t.data(), ms.disp_z.data(), n, ImPlotSpec(ImPlotProp_LineColor, cZ));
                }
            }
            ImPlot::EndPlot();
        }
    }

    // Chart 3: Velocity magnitude
    if (anyVel) {
        ImGui::Spacing();
        SectionHeader("Velocity |V|  (mm/s)", COL_ACCENT, 1);
        plotMag("##MotVel", "mm/s",
            [](const auto& m) -> const std::vector<double>* { return m.vel_mag.empty() ? nullptr : &m.vel_mag; });
    }

    // Chart 4: Acceleration magnitude
    if (anyAcc) {
        ImGui::Spacing();
        SectionHeader("Acceleration |A|", COL_YELLOW, 1);
        plotMag("##MotAcc", "mm/s²",
            [](const auto& m) -> const std::vector<double>* { return m.acc_mag.empty() ? nullptr : &m.acc_mag; });
    }
}

// ============================================================
// Energy Tab: energy balance + ratio + warnings
// ============================================================

