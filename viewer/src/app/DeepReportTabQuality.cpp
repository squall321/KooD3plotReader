#include "app/DeepReportApp.hpp"
#include "app/DeepReportColors.hpp"
#include <imgui.h>
#include <implot.h>
#include <algorithm>
#include <cstdio>
#include <cmath>
#include <string>

void DeepReportApp::renderQualityTab() {
    if (data_.element_quality.empty()) {
        ImGui::TextColored(COL_DIM, "No element quality data");
        return;
    }

    ImGui::TextColored(COL_DIM,
        "Aspect Ratio: edge ratio (>10 = poor).  Jacobian: shape quality (1.0 = ideal, <0.5 = poor, <0 = inverted).\n"
        "Vol/Area: volume or area ratio vs initial (1.0 = no change).  Warpage: quad out-of-plane angle (deg).");
    ImGui::Spacing();

    // ── Summary table ──────────────────────────────────────
    SectionHeader("Element Quality Summary", COL_ACCENT);
    ImGui::Spacing();

    // Table height: enough for all rows but not more than 30% of window
    float tableH = std::min((float)(data_.element_quality.size() + 1) * 22.0f + 10.0f,
                            ImGui::GetContentRegionAvail().y * 0.30f);
    tableH = std::max(tableH, 60.0f);

    if (ImGui::BeginTable("##QualTable", 9,
            ImGuiTableFlags_RowBg | ImGuiTableFlags_Sortable |
            ImGuiTableFlags_ScrollY | ImGuiTableFlags_SizingStretchProp |
            ImGuiTableFlags_BordersInnerV, ImVec2(-1, tableH))) {

        ImGui::TableSetupScrollFreeze(0, 1);
        ImGui::TableSetupColumn("Part",   ImGuiTableColumnFlags_WidthFixed,   44);
        ImGui::TableSetupColumn("Name",   ImGuiTableColumnFlags_WidthStretch);
        ImGui::TableSetupColumn("Type",   ImGuiTableColumnFlags_WidthFixed,   42);
        ImGui::TableSetupColumn("Elems",  ImGuiTableColumnFlags_WidthFixed,   52);
        ImGui::TableSetupColumn("AR max", ImGuiTableColumnFlags_WidthFixed,   60);
        ImGui::TableSetupColumn("Jac min",ImGuiTableColumnFlags_WidthFixed,   60);
        ImGui::TableSetupColumn("NegJac", ImGuiTableColumnFlags_WidthFixed,   52);
        ImGui::TableSetupColumn("Warp°",  ImGuiTableColumnFlags_WidthFixed,   54);
        ImGui::TableSetupColumn("Skew",   ImGuiTableColumnFlags_WidthFixed,   50);
        ImGui::TableHeadersRow();

        for (const auto& q : data_.element_quality) {
            ImGui::TableNextRow();
            ImGui::TableSetColumnIndex(0);
            char qsel[16]; snprintf(qsel, sizeof(qsel), "%d##q%d", q.part_id, q.part_id);
            if (ImGui::Selectable(qsel, false, ImGuiSelectableFlags_SpanAllColumns | ImGuiSelectableFlags_DontClosePopups)) {
                if (data_.parts.count(q.part_id)) { deepDivePartId_ = q.part_id; navigateToDeepDive_ = true; }
            }
            if (ImGui::IsItemHovered()) { ImGui::SetMouseCursor(ImGuiMouseCursor_Hand); ImGui::SetTooltip("Click \xe2\x86\x92 Deep Dive  P%d  %s", q.part_id, q.part_name.c_str()); }
            ImGui::TableSetColumnIndex(1); ImGui::TextUnformatted(q.part_name.c_str());
            ImGui::TableSetColumnIndex(2); ImGui::TextColored(COL_DIM, "%s", q.element_type.c_str());
            ImGui::TableSetColumnIndex(3); ImGui::Text("%d", q.num_elements);
            ImGui::TableSetColumnIndex(4);
            ImGui::TextColored(q.peak_aspect_ratio > 10 ? COL_RED :
                               q.peak_aspect_ratio > 5  ? COL_YELLOW : COL_ACCENT,
                               "%.1f", q.peak_aspect_ratio);
            ImGui::TableSetColumnIndex(5);
            ImGui::TextColored(q.min_jacobian < 0   ? COL_RED :
                               q.min_jacobian < 0.5 ? COL_RED :
                               q.min_jacobian < 0.7 ? COL_YELLOW : COL_ACCENT,
                               "%.3f", q.min_jacobian);
            ImGui::TableSetColumnIndex(6);
            ImGui::TextColored(q.max_negative_jacobian_count > 0 ? COL_RED : COL_ACCENT,
                               "%d", q.max_negative_jacobian_count);
            ImGui::TableSetColumnIndex(7);
            ImGui::TextColored(q.peak_warpage > 15 ? COL_RED :
                               q.peak_warpage > 5  ? COL_YELLOW : COL_ACCENT,
                               "%.1f", q.peak_warpage);
            ImGui::TableSetColumnIndex(8);
            ImGui::TextColored(q.peak_skewness > 0.8 ? COL_RED :
                               q.peak_skewness > 0.5 ? COL_YELLOW : COL_ACCENT,
                               "%.3f", q.peak_skewness);
        }
        ImGui::EndTable();
    }

    // ── Per-part time series ───────────────────────────────
    bool anyTS = std::any_of(data_.element_quality.begin(), data_.element_quality.end(),
        [](const auto& q){ return q.time_series.size() >= 2; });

    if (!anyTS) return;

    ImGui::Spacing();
    SectionHeader("Quality Time History", COL_ACCENT);
    ImGui::Spacing();

    // Part selector
    static int selQualIdx = 0;
    // Build list of parts that have time series
    std::vector<int> qIdx;
    for (int i = 0; i < (int)data_.element_quality.size(); ++i)
        if (data_.element_quality[i].time_series.size() >= 2) qIdx.push_back(i);
    if (selQualIdx >= (int)qIdx.size()) selQualIdx = 0;

    if (qIdx.size() > 1) {
        ImGui::Text("Part:"); ImGui::SameLine();
        ImGui::SetNextItemWidth(320);
        auto& cq = data_.element_quality[qIdx[selQualIdx]];
        char curLbl[128]; snprintf(curLbl, sizeof(curLbl), "P%d  %s  (%s)",
            cq.part_id, cq.part_name.c_str(), cq.element_type.c_str());
        if (ImGui::BeginCombo("##qualSel", curLbl)) {
            for (int i = 0; i < (int)qIdx.size(); ++i) {
                auto& qq = data_.element_quality[qIdx[i]];
                char lbl[128]; snprintf(lbl, sizeof(lbl), "P%d  %s  (%s)",
                    qq.part_id, qq.part_name.c_str(), qq.element_type.c_str());
                if (ImGui::Selectable(lbl, selQualIdx == i)) selQualIdx = i;
            }
            ImGui::EndCombo();
        }
        ImGui::Spacing();
    }

    auto& q = data_.element_quality[qIdx[selQualIdx]];
    auto& ts = q.time_series;
    int n = (int)ts.size();

    // Flatten time series for plotting
    std::vector<double> t(n), arMax(n), arAvg(n), volMin(n), volMax(n), warpMax(n), skewMax(n);
    for (int i = 0; i < n; ++i) {
        t[i] = ts[i].time;
        arMax[i] = ts[i].ar_max;   arAvg[i] = ts[i].ar_avg;
        volMin[i] = ts[i].vol_min; volMax[i] = ts[i].vol_max;
        warpMax[i] = ts[i].warp_max; skewMax[i] = ts[i].skew_max;
    }

    float avail = ImGui::GetContentRegionAvail().y;
    bool isShell = (q.element_type == "shell");
    int numCharts = isShell ? 4 : 2;
    float chartH = std::max(140.0f, (avail - 12.0f * numCharts) / numCharts);

    // Aspect Ratio
    ImGui::TextColored(COL_DIM, "Aspect Ratio");
    char arId[32]; snprintf(arId, sizeof(arId), "##AR%d", q.part_id);
    if (ImPlot::BeginPlot(arId, ImVec2(-1, chartH))) {
        ImPlot::SetupAxes("Time", "AR");
        ImPlot::PlotLine("Max", t.data(), arMax.data(), n,
            ImPlotSpec(ImPlotProp_LineColor, COL_RED));
        ImVec4 arAvgC = COL_ACCENT; arAvgC.w = 0.65f;
        ImPlot::PlotLine("Avg", t.data(), arAvg.data(), n,
            ImPlotSpec(ImPlotProp_LineColor, arAvgC, ImPlotProp_LineWeight, 1.0f));
        // Threshold line at AR=10
        double xr[] = {t.front(), t.back()}, yr[] = {10.0, 10.0};
        ImVec4 thrC(1,0.3f,0.3f,0.4f);
        ImPlot::PlotLine("limit=10", xr, yr, 2,
            ImPlotSpec(ImPlotProp_LineColor, thrC, ImPlotProp_LineWeight, 1.0f));
        ImPlot::EndPlot();
    }

    // Volume / Area ratio
    ImGui::Spacing();
    ImGui::TextColored(COL_DIM, isShell ? "Area Change Ratio" : "Volume Change Ratio");
    char volId[32]; snprintf(volId, sizeof(volId), "##Vol%d", q.part_id);
    if (ImPlot::BeginPlot(volId, ImVec2(-1, chartH))) {
        ImPlot::SetupAxes("Time", "Ratio");
        ImPlot::PlotLine("Min (compressed)", t.data(), volMin.data(), n,
            ImPlotSpec(ImPlotProp_LineColor, COL_RED));
        ImPlot::PlotLine("Max (expanded)",   t.data(), volMax.data(), n,
            ImPlotSpec(ImPlotProp_LineColor, COL_ACCENT));
        // Reference line at 1.0
        double xr[] = {t.front(), t.back()}, yr[] = {1.0, 1.0};
        ImVec4 refC(0.6f,0.6f,0.6f,0.4f);
        ImPlot::PlotLine("ref=1", xr, yr, 2,
            ImPlotSpec(ImPlotProp_LineColor, refC, ImPlotProp_LineWeight, 1.0f));
        ImPlot::EndPlot();
    }

    if (isShell) {
        // Warpage
        ImGui::Spacing();
        ImGui::TextColored(COL_DIM, "Warpage Angle (°)");
        char warpId[32]; snprintf(warpId, sizeof(warpId), "##Warp%d", q.part_id);
        if (ImPlot::BeginPlot(warpId, ImVec2(-1, chartH))) {
            ImPlot::SetupAxes("Time", "Warpage (°)");
            ImPlot::PlotLine("Max warpage", t.data(), warpMax.data(), n,
                ImPlotSpec(ImPlotProp_LineColor, COL_YELLOW));
            double xr[] = {t.front(), t.back()}, yr[] = {15.0, 15.0};
            ImVec4 thrC(1,0.3f,0.3f,0.4f);
            ImPlot::PlotLine("limit=15°", xr, yr, 2,
                ImPlotSpec(ImPlotProp_LineColor, thrC, ImPlotProp_LineWeight, 1.0f));
            ImPlot::EndPlot();
        }

        // Skewness
        ImGui::Spacing();
        ImGui::TextColored(COL_DIM, "Skewness");
        char skewId[32]; snprintf(skewId, sizeof(skewId), "##Skew%d", q.part_id);
        if (ImPlot::BeginPlot(skewId, ImVec2(-1, chartH))) {
            ImPlot::SetupAxes("Time", "Skewness");
            ImPlot::PlotLine("Max skewness", t.data(), skewMax.data(), n,
                ImPlotSpec(ImPlotProp_LineColor, COL_PURPLE));
            double xr[] = {t.front(), t.back()}, yr[] = {0.8, 0.8};
            ImVec4 thrC(1,0.3f,0.3f,0.4f);
            ImPlot::PlotLine("limit=0.8", xr, yr, 2,
                ImPlotSpec(ImPlotProp_LineColor, thrC, ImPlotProp_LineWeight, 1.0f));
            ImPlot::EndPlot();
        }
    }
}


