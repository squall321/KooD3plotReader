#include "app/DeepReportApp.hpp"
#include "app/DeepReportColors.hpp"
#include <imgui.h>
#include <implot.h>
#include <algorithm>
#include <cstdio>
#include <cmath>
#include <string>

void DeepReportApp::renderContactTab() {
    ImGui::TextColored(COL_DIM,
        "Contact interface forces from binout (master side, side=0).\n"
        "|F| = resultant magnitude.  Fx/Fy/Fz = directional components.\n"
        "Sliding energy = frictional work dissipated per interface.");
    ImGui::Spacing();

    // ── rcforc section ──────────────────────────────────────
    if (!data_.rcforc.empty()) {
        // Collect master-side entries (side == 0)
        std::vector<const DeepReportData::ContactInterface*> masters;
        for (const auto& ci : data_.rcforc)
            if (ci.side == 0) masters.push_back(&ci);
        // Fallback: if no side=0 entries exist, show all
        if (masters.empty())
            for (const auto& ci : data_.rcforc) masters.push_back(&ci);

        // ── Interface selector ─────────────────────────────
        int& selIfcIdx = contactIfcIdx_;
        if (selIfcIdx >= (int)masters.size()) selIfcIdx = 0;

        SectionHeader("Contact Forces (rcforc)", COL_ACCENT);
        ImGui::Spacing();

        // Peak force summary cards
        {
            int cols = std::min((int)masters.size(), 4);
            ImGui::Columns(cols, nullptr, false);
            for (auto* ci : masters) {
                bool isSel = (ci == masters[selIfcIdx]);
                ImGui::PushStyleColor(ImGuiCol_ChildBg,
                    isSel ? ImVec4(0.12f,0.28f,0.45f,0.6f) : ImVec4(0.10f,0.13f,0.20f,0.5f));
                std::string cid = "##cfcard" + std::to_string(ci->id);
                ImGui::BeginChild(cid.c_str(), ImVec2(-1, 58), true);
                ImGui::TextColored(COL_DIM, "Ifc %d", ci->id);
                if (!ci->name.empty()) {
                    ImGui::SameLine();
                    ImGui::TextColored(isSel ? COL_ACCENT : COL_DIM, " %s", ci->name.c_str());
                }
                ImGui::TextColored(isSel ? COL_ACCENT : ImVec4(0.85f,0.85f,0.90f,1),
                    "Peak |F|: %.1f N", ci->peak_fmag);
                ImGui::EndChild();
                ImGui::PopStyleColor();

                // Click card to select
                if (ImGui::IsItemClicked()) {
                    for (int i = 0; i < (int)masters.size(); ++i)
                        if (masters[i] == ci) { selIfcIdx = i; break; }
                }
                ImGui::NextColumn();
            }
            ImGui::Columns(1);
        }

        // Dropdown (shown when >4 interfaces)
        if ((int)masters.size() > 4) {
            ImGui::Spacing();
            ImGui::Text("Interface:"); ImGui::SameLine();
            ImGui::SetNextItemWidth(300);
            auto* cur = masters[selIfcIdx];
            char curLbl[128]; snprintf(curLbl, sizeof(curLbl), "Ifc %d  %s", cur->id, cur->name.c_str());
            if (ImGui::BeginCombo("##ifcSel", curLbl)) {
                for (int i = 0; i < (int)masters.size(); ++i) {
                    char lbl[128]; snprintf(lbl, sizeof(lbl), "Ifc %d  %s  Peak: %.1f N",
                        masters[i]->id, masters[i]->name.c_str(), masters[i]->peak_fmag);
                    if (ImGui::Selectable(lbl, selIfcIdx == i)) selIfcIdx = i;
                }
                ImGui::EndCombo();
            }
        }

        ImGui::Spacing();

        // ── Combined |F| + Fx/Fy/Fz chart ─────────────────
        auto* ci = masters[selIfcIdx];
        if (!ci->t.empty()) {
            int n = (int)ci->t.size();
            float chartH = std::max(220.0f, ImGui::GetContentRegionAvail().y * 0.42f);
            ImVec2 sz(ImGui::GetContentRegionAvail().x, chartH);

            char plotId[64]; snprintf(plotId, sizeof(plotId), "##CForce%d", ci->id);
            if (ImPlot::BeginPlot(plotId, sz)) {
                ImPlot::SetupAxes("Time", "Force (N)");
                static const ImVec4 cMag(0.31f,0.80f,0.64f,1.0f);  // accent green
                static const ImVec4 cX  (0.91f,0.27f,0.38f,1.0f);  // red
                static const ImVec4 cY  (0.15f,0.75f,0.45f,1.0f);  // green
                static const ImVec4 cZ  (0.31f,0.56f,1.00f,1.0f);  // blue
                // |F| bold
                if (!ci->fmag.empty())
                    ImPlot::PlotLine("|F| mag", ci->t.data(), ci->fmag.data(), n,
                        ImPlotSpec(ImPlotProp_LineColor, cMag, ImPlotProp_LineWeight, 2.0f));
                // XYZ thin
                if (!ci->fx.empty())
                    ImPlot::PlotLine("Fx", ci->t.data(), ci->fx.data(), n,
                        ImPlotSpec(ImPlotProp_LineColor, cX, ImPlotProp_LineWeight, 1.2f));
                if (!ci->fy.empty())
                    ImPlot::PlotLine("Fy", ci->t.data(), ci->fy.data(), n,
                        ImPlotSpec(ImPlotProp_LineColor, cY, ImPlotProp_LineWeight, 1.2f));
                if (!ci->fz.empty())
                    ImPlot::PlotLine("Fz", ci->t.data(), ci->fz.data(), n,
                        ImPlotSpec(ImPlotProp_LineColor, cZ, ImPlotProp_LineWeight, 1.2f));
                ImPlot::EndPlot();
            }
        }
    } else if (data_.sleout.empty()) {
        ImGui::TextColored(COL_DIM, "No contact data (no binout rcforc)");
    }

    // ── sleout section ──────────────────────────────────────
    if (!data_.sleout.empty()) {
        ImGui::Spacing();
        SectionHeader("Sliding Energy (sleout)", COL_YELLOW);

        // Dropdown for sleout interface
        int& selSleIdx = contactSleIdx_;
        if (selSleIdx >= (int)data_.sleout.size()) selSleIdx = 0;

        if (data_.sleout.size() > 1) {
            ImGui::Text("Interface:"); ImGui::SameLine();
            ImGui::SetNextItemWidth(280);
            auto& curSl = data_.sleout[selSleIdx];
            char curLbl[96]; snprintf(curLbl, sizeof(curLbl), "Ifc %d  %s", curSl.id, curSl.name.c_str());
            if (ImGui::BeginCombo("##sleSel", curLbl)) {
                for (int i = 0; i < (int)data_.sleout.size(); ++i) {
                    char lbl[96]; snprintf(lbl, sizeof(lbl), "Ifc %d  %s", data_.sleout[i].id, data_.sleout[i].name.c_str());
                    if (ImGui::Selectable(lbl, selSleIdx == i)) selSleIdx = i;
                }
                ImGui::EndCombo();
            }
            ImGui::Spacing();
        }

        auto& se = data_.sleout[selSleIdx];
        if (!se.t.empty()) {
            float sleH = std::max(160.0f, ImGui::GetContentRegionAvail().y - 8.0f);
            char sleId[64]; snprintf(sleId, sizeof(sleId), "##Sle%d", se.id);
            if (ImPlot::BeginPlot(sleId, ImVec2(-1, sleH))) {
                ImPlot::SetupAxes("Time", "Energy");
                if (!se.total_energy.empty())
                    ImPlot::PlotLine("Total sliding", se.t.data(), se.total_energy.data(), (int)se.t.size());
                if (!se.friction_energy.empty()) {
                    ImVec4 dimC(0.96f,0.65f,0.14f,0.7f);
                    ImPlot::PlotLine("Friction", se.t.data(), se.friction_energy.data(), (int)se.t.size(),
                        ImPlotSpec(ImPlotProp_LineColor, dimC, ImPlotProp_LineWeight, 1.2f));
                }
                ImPlot::EndPlot();
            }
        }
    }

    // ── MATSUM: per-part material energy ────────────────────
    if (!data_.matsum.empty()) {
        ImGui::Spacing();
        SectionHeader("Material Energy per Part (matsum)", COL_BLUE);
        ImGui::Spacing();

        int& selMatsumIdx = contactMatsumIdx_;
        if (selMatsumIdx >= (int)data_.matsum.size()) selMatsumIdx = 0;

        // Part selector
        if (data_.matsum.size() > 1) {
            ImGui::Text("Part:"); ImGui::SameLine();
            ImGui::SetNextItemWidth(340);
            auto& cm = data_.matsum[selMatsumIdx];
            char curLbl[128]; snprintf(curLbl, sizeof(curLbl), "P%d  %s", cm.part_id, cm.part_name.c_str());
            if (ImGui::BeginCombo("##matsumSel", curLbl)) {
                for (int i = 0; i < (int)data_.matsum.size(); ++i) {
                    auto& mm = data_.matsum[i];
                    char lbl[128]; snprintf(lbl, sizeof(lbl), "P%d  %s", mm.part_id, mm.part_name.c_str());
                    if (ImGui::Selectable(lbl, selMatsumIdx == i)) selMatsumIdx = i;
                }
                ImGui::EndCombo();
            }
            ImGui::Spacing();
        }

        auto& me = data_.matsum[selMatsumIdx];
        if (!me.t.empty()) {
            float msH = std::max(160.0f, ImGui::GetContentRegionAvail().y - 8.0f);
            char msId[64]; snprintf(msId, sizeof(msId), "##Matsum%d", me.part_id);
            if (ImPlot::BeginPlot(msId, ImVec2(-1, msH))) {
                ImPlot::SetupAxes("Time", "Energy");
                if (!me.internal_energy.empty())
                    ImPlot::PlotLine("Internal", me.t.data(), me.internal_energy.data(), (int)me.t.size(),
                        ImPlotSpec(ImPlotProp_LineColor, COL_YELLOW, ImPlotProp_LineWeight, 1.8f));
                if (!me.kinetic_energy.empty()) {
                    ImVec4 kc = COL_BLUE; kc.w = 0.85f;
                    ImPlot::PlotLine("Kinetic", me.t.data(), me.kinetic_energy.data(), (int)me.t.size(),
                        ImPlotSpec(ImPlotProp_LineColor, kc, ImPlotProp_LineWeight, 1.4f));
                }
                ImPlot::EndPlot();
            }
        }
    }
}

// ============================================================
// SysInfo Tab
// ============================================================

