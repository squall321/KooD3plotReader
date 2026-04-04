#include "app/DeepReportApp.hpp"
#include "app/DeepReportColors.hpp"
#include <imgui.h>
#include <algorithm>
#include <functional>
#include <cstdio>

// ============================================================
// Overview — bar chart ranking
// ============================================================
void DeepReportApp::renderOverview() {
    if (data_.parts.empty()) {
        ImGui::TextColored(COL_DIM, "No data loaded");
        return;
    }

    renderWarnings();

    ImGui::TextColored(COL_DIM,
        "Von Mises stress: combined multiaxial stress state.\n"
        "\xcf\x83\xe2\x82\x81 = max tension, \xcf\x83\xe2\x82\x83 = max compression. \xce\xb5\xe2\x82\x81/\xce\xb5\xe2\x82\x83 = principal strains.\n"
        "Red = critical (exceeds limit), Yellow = warning, Green = OK.");
    ImGui::Spacing();

    // Filter indicator
    bool hasFilter = !selectedParts_.empty() || globalFilter_[0] != '\0';
    if (hasFilter) {
        ImGui::PushStyleColor(ImGuiCol_ChildBg, ImVec4(0.15f, 0.28f, 0.18f, 0.4f));
        ImGui::BeginChild("##ovFilterBadge", ImVec2(-1, 24), true);
        if (!selectedParts_.empty())
            ImGui::TextColored(COL_ACCENT, "  Filtered: %d / %d parts selected  \xe2\x80\x94  clear in Parts panel to show all",
                (int)selectedParts_.size(), (int)data_.parts.size());
        else
            ImGui::TextColored(COL_ACCENT, "  Keyword filter active: \"%s\"  \xe2\x80\x94  clear in filter bar above to show all", globalFilter_);
        ImGui::EndChild();
        ImGui::PopStyleColor();
        ImGui::Spacing();
    }

    // Collect filtered parts
    auto collectParts = [&]() {
        std::vector<std::pair<int, const PartSummary*>> v;
        for (const auto& [pid, ps] : data_.parts) {
            if (!partPassesFilter(pid, ps.name)) continue;
            if (!selectedParts_.empty() && !selectedParts_.count(pid)) continue;
            v.push_back({pid, &ps});
        }
        return v;
    };

    // Generic ranking renderer
    auto drawRanking = [&](const char* title, ImVec4 titleCol,
                            const std::vector<std::pair<int, const PartSummary*>>& items,
                            std::function<double(const PartSummary*)> valGetter,
                            std::function<std::string(double)> fmtVal,
                            std::function<ImVec4(const PartSummary*)> colorGetter,
                            bool skipZero = false)
    {
        std::vector<std::pair<int, const PartSummary*>> sorted = items;
        std::sort(sorted.begin(), sorted.end(),
            [&](const auto& a, const auto& b) {
                return std::abs(valGetter(a.second)) > std::abs(valGetter(b.second));
            });
        if (skipZero)
            sorted.erase(std::remove_if(sorted.begin(), sorted.end(),
                [&](const auto& x) { return valGetter(x.second) == 0.0; }), sorted.end());
        if (sorted.empty()) return;

        double maxVal = std::max(std::abs(valGetter(sorted[0].second)), 1e-10);
        int showN = (int)std::min(sorted.size(), (size_t)10);
        ImGui::TextColored(titleCol, "  %s  (Top %d)", title, showN);
        ImGui::Separator();
        ImGui::Spacing();

        for (int i = 0; i < showN; ++i) {
            auto& [pid, ps] = sorted[i];
            double val = valGetter(ps);
            float pct = static_cast<float>(std::abs(val) / maxVal);
            char lbl[128];
            snprintf(lbl, sizeof(lbl), "P%d  %s", pid,
                ps->name.size() > 18 ? (ps->name.substr(0,17) + "\xe2\x80\xa6").c_str() : ps->name.c_str());
            ImGui::Text("%-24s", lbl);
            ImGui::SameLine(220);
            ImGui::PushStyleColor(ImGuiCol_PlotHistogram, colorGetter(ps));
            std::string ovStr = fmtVal(val);
            ImGui::ProgressBar(pct, ImVec2(-1, 20), ovStr.c_str());
            ImGui::PopStyleColor();
            if (ImGui::IsItemClicked()) { deepDivePartId_ = pid; navigateToDeepDive_ = true; }
            if (ImGui::IsItemHovered()) { ImGui::SetMouseCursor(ImGuiMouseCursor_Hand); ImGui::SetTooltip("P%d  %s\nClick \xe2\x86\x92 Deep Dive", pid, ps->name.c_str()); }
        }
        ImGui::Spacing();
    };

    // Color helpers
    auto stressCol = [](const PartSummary* ps) -> ImVec4 {
        if (ps->stress_warning == "crit") return COL_RED;
        if (ps->stress_warning == "warn") return COL_YELLOW;
        return COL_ACCENT;
    };
    auto strainCol = [](const PartSummary* ps) -> ImVec4 {
        if (ps->strain_warning == "crit") return COL_RED;
        if (ps->strain_warning == "warn") return COL_YELLOW;
        return COL_YELLOW;
    };
    auto constCol = [](ImVec4 c) {
        return [c](const PartSummary*) -> ImVec4 { return c; };
    };

    auto parts = collectParts();

    // Von Mises
    drawRanking("Von Mises Stress", COL_ACCENT, parts,
        [](const PartSummary* p) { return p->peak_stress; },
        [](double v) { char b[32]; snprintf(b,sizeof(b),"%.1f MPa", v); return std::string(b); },
        stressCol, true);

    // Displacement
    if (std::any_of(parts.begin(), parts.end(), [](const auto& kv){ return kv.second->peak_disp > 0; })) {
        ImGui::Spacing();
        drawRanking("Peak Displacement", COL_PURPLE, parts,
            [](const PartSummary* p) { return p->peak_disp; },
            [](double v) { char b[32]; snprintf(b,sizeof(b),"%.2f mm", v); return std::string(b); },
            constCol(COL_PURPLE), true);
    }

    // Max Principal Stress σ₁
    if (std::any_of(parts.begin(), parts.end(), [](const auto& kv){ return kv.second->peak_max_principal != 0; })) {
        ImGui::Spacing();
        drawRanking("Max Principal Stress \xcf\x83\xe2\x82\x81 (Tension)", ImVec4(0.97f,0.56f,0.27f,1), parts,
            [](const PartSummary* p) { return p->peak_max_principal; },
            [](double v) { char b[32]; snprintf(b,sizeof(b),"%.1f MPa", v); return std::string(b); },
            constCol(ImVec4(0.97f,0.56f,0.27f,1)), true);
    }

    // Min Principal Stress σ₃ (most compressive)
    if (std::any_of(parts.begin(), parts.end(), [](const auto& kv){ return kv.second->peak_min_principal != 0; })) {
        ImGui::Spacing();
        std::vector<std::pair<int, const PartSummary*>> sorted = parts;
        std::sort(sorted.begin(), sorted.end(),
            [](const auto& a, const auto& b){ return a.second->peak_min_principal < b.second->peak_min_principal; });
        sorted.erase(std::remove_if(sorted.begin(), sorted.end(),
            [](const auto& x){ return x.second->peak_min_principal == 0; }), sorted.end());
        if (!sorted.empty()) {
            double maxAbs = std::max(std::abs(sorted[0].second->peak_min_principal), 1e-10);
            int showN = (int)std::min(sorted.size(), (size_t)10);
            { char h[64]; snprintf(h,sizeof(h),"Min Principal Stress \xcf\x83\xe2\x82\x83 (Compression)  (Top %d)",showN); SectionHeader(h, COL_PURPLE); }
            for (int i = 0; i < showN; ++i) {
                auto& [pid, ps] = sorted[i];
                float pct = (float)(std::abs(ps->peak_min_principal) / maxAbs);
                char lbl[128]; snprintf(lbl,sizeof(lbl),"P%d  %s",pid, ps->name.size()>18?(ps->name.substr(0,17)+"\xe2\x80\xa6").c_str():ps->name.c_str());
                ImGui::Text("%-24s", lbl); ImGui::SameLine(220);
                ImGui::PushStyleColor(ImGuiCol_PlotHistogram, COL_PURPLE);
                char ov[32]; snprintf(ov,sizeof(ov),"%.1f MPa",ps->peak_min_principal);
                ImGui::ProgressBar(pct, ImVec2(-1,20), ov);
                ImGui::PopStyleColor();
                if (ImGui::IsItemClicked()) { deepDivePartId_=pid; navigateToDeepDive_=true; }
                if (ImGui::IsItemHovered()) { ImGui::SetMouseCursor(ImGuiMouseCursor_Hand); ImGui::SetTooltip("P%d  %s\nClick \xe2\x86\x92 Deep Dive",pid,ps->name.c_str()); }
            }
            ImGui::Spacing();
        }
    }

    // Eff. Plastic Strain
    if (std::any_of(parts.begin(), parts.end(), [](const auto& kv){ return kv.second->peak_strain > 0; })) {
        ImGui::Spacing();
        drawRanking("Eff. Plastic Strain", COL_YELLOW, parts,
            [](const PartSummary* p) { return p->peak_strain; },
            [](double v) { char b[32]; snprintf(b,sizeof(b),"%.4f", v); return std::string(b); },
            strainCol, true);
    }

    // Max Principal Strain ε₁
    if (std::any_of(parts.begin(), parts.end(), [](const auto& kv){ return kv.second->peak_max_principal_strain != 0; })) {
        ImGui::Spacing();
        drawRanking("Max Principal Strain \xce\xb5\xe2\x82\x81", ImVec4(0.15f,0.75f,0.45f,1), parts,
            [](const PartSummary* p) { return p->peak_max_principal_strain; },
            [](double v) { char b[32]; snprintf(b,sizeof(b),"%.4f", v); return std::string(b); },
            constCol(ImVec4(0.15f,0.75f,0.45f,1)), true);
    }

    // Min Principal Strain ε₃ (most compressive)
    if (std::any_of(parts.begin(), parts.end(), [](const auto& kv){ return kv.second->peak_min_principal_strain != 0; })) {
        ImGui::Spacing();
        std::vector<std::pair<int, const PartSummary*>> sorted = parts;
        std::sort(sorted.begin(), sorted.end(),
            [](const auto& a, const auto& b){ return a.second->peak_min_principal_strain < b.second->peak_min_principal_strain; });
        sorted.erase(std::remove_if(sorted.begin(), sorted.end(),
            [](const auto& x){ return x.second->peak_min_principal_strain == 0; }), sorted.end());
        if (!sorted.empty()) {
            double maxAbs = std::max(std::abs(sorted[0].second->peak_min_principal_strain), 1e-10);
            int showN = (int)std::min(sorted.size(), (size_t)10);
            { char h[64]; snprintf(h,sizeof(h),"Min Principal Strain \xce\xb5\xe2\x82\x83 (Compression)  (Top %d)",showN); SectionHeader(h, ImVec4(0.35f,0.45f,0.75f,1)); }
            for (int i = 0; i < showN; ++i) {
                auto& [pid, ps] = sorted[i];
                float pct = (float)(std::abs(ps->peak_min_principal_strain) / maxAbs);
                char lbl[128]; snprintf(lbl,sizeof(lbl),"P%d  %s",pid, ps->name.size()>18?(ps->name.substr(0,17)+"\xe2\x80\xa6").c_str():ps->name.c_str());
                ImGui::Text("%-24s", lbl); ImGui::SameLine(220);
                ImGui::PushStyleColor(ImGuiCol_PlotHistogram, ImVec4(0.35f,0.45f,0.75f,1));
                char ov[32]; snprintf(ov,sizeof(ov),"%.4f",ps->peak_min_principal_strain);
                ImGui::ProgressBar(pct, ImVec2(-1,20), ov);
                ImGui::PopStyleColor();
                if (ImGui::IsItemClicked()) { deepDivePartId_=pid; navigateToDeepDive_=true; }
                if (ImGui::IsItemHovered()) { ImGui::SetMouseCursor(ImGuiMouseCursor_Hand); ImGui::SetTooltip("P%d  %s\nClick \xe2\x86\x92 Deep Dive",pid,ps->name.c_str()); }
            }
            ImGui::Spacing();
        }
    }

    // Safety Factor (ascending = lowest SF = most critical)
    if (std::any_of(parts.begin(), parts.end(), [](const auto& kv){ return kv.second->safety_factor > 0; })) {
        ImGui::Spacing();
        std::vector<std::pair<int, const PartSummary*>> sorted = parts;
        std::sort(sorted.begin(), sorted.end(),
            [](const auto& a, const auto& b){ return a.second->safety_factor < b.second->safety_factor; });
        sorted.erase(std::remove_if(sorted.begin(), sorted.end(),
            [](const auto& x){ return x.second->safety_factor <= 0; }), sorted.end());
        if (!sorted.empty()) {
            double maxSF = std::max(sorted.back().second->safety_factor, 1e-10);
            int showN = (int)std::min(sorted.size(), (size_t)10);
            { char h[64]; snprintf(h,sizeof(h),"Safety Factor  (Lowest First, Top %d)",showN); SectionHeader(h, ImVec4(0.86f,0.86f,0.30f,1)); }
            for (int i = 0; i < showN; ++i) {
                auto& [pid, ps] = sorted[i];
                float pct = (float)(ps->safety_factor / maxSF);
                char lbl[128]; snprintf(lbl,sizeof(lbl),"P%d  %s",pid, ps->name.size()>18?(ps->name.substr(0,17)+"\xe2\x80\xa6").c_str():ps->name.c_str());
                ImGui::Text("%-24s", lbl); ImGui::SameLine(220);
                ImVec4 sfC = ps->safety_factor>=1.0 ? COL_ACCENT : ps->safety_factor>=0.85 ? COL_YELLOW : COL_RED;
                ImGui::PushStyleColor(ImGuiCol_PlotHistogram, sfC);
                char ov[32]; snprintf(ov,sizeof(ov),"SF=%.3f",ps->safety_factor);
                ImGui::ProgressBar(pct, ImVec2(-1,20), ov);
                ImGui::PopStyleColor();
                if (ImGui::IsItemClicked()) { deepDivePartId_=pid; navigateToDeepDive_=true; }
                if (ImGui::IsItemHovered()) { ImGui::SetMouseCursor(ImGuiMouseCursor_Hand); ImGui::SetTooltip("P%d  %s\nClick \xe2\x86\x92 Deep Dive",pid,ps->name.c_str()); }
            }
            ImGui::Spacing();
        }
    }
}
