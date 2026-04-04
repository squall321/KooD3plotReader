#include "app/DeepReportApp.hpp"
#include "app/DeepReportColors.hpp"
#include <imgui.h>
#include <implot.h>
#include <algorithm>
#include <cstdio>
#include <cmath>
#include <string>
#include <filesystem>

void DeepReportApp::renderDeepDiveTab() {
    if (data_.parts.empty()) {
        ImGui::TextColored(COL_DIM, "No parts data");
        return;
    }

    ImGui::TextColored(COL_DIM,
        "Select a part to see all analysis results in one page.\n"
        "Includes KPI summary, stress/strain time history, displacement XYZ, velocity, acceleration.");
    ImGui::Spacing();

    // Part selector
    if (deepDivePartId_ == 0 && !data_.parts.empty())
        deepDivePartId_ = data_.parts.begin()->first;

    // Build ordered part ID list for prev/next
    std::vector<int> partIds;
    for (const auto& [pid, ps] : data_.parts) partIds.push_back(pid);
    int ddIdx = 0;
    for (int i = 0; i < (int)partIds.size(); ++i) if (partIds[i] == deepDivePartId_) { ddIdx = i; break; }

    // Prev / Next buttons
    if (ImGui::Button("< ##ddPrev")) {
        ddIdx = (ddIdx - 1 + (int)partIds.size()) % (int)partIds.size();
        deepDivePartId_ = partIds[ddIdx];
    }
    if (ImGui::IsItemHovered()) ImGui::SetMouseCursor(ImGuiMouseCursor_Hand);
    ImGui::SameLine();

    // Searchable combo
    auto it = data_.parts.find(deepDivePartId_);
    std::string currentLabel = it != data_.parts.end()
        ? ("Part " + std::to_string(deepDivePartId_) + " \xe2\x80\x94 " + it->second.name) : "Select";
    ImGui::SetNextItemWidth(360);
    if (ImGui::BeginCombo("##ddPart", currentLabel.c_str())) {
        // Search filter inside combo popup
        static char ddSearch[128] = "";
        ImGui::SetNextItemWidth(-1);
        if (ImGui::IsWindowAppearing()) {
            ImGui::SetKeyboardFocusHere();
            ddSearch[0] = '\0';
        }
        ImGui::InputTextWithHint("##ddSearch", "\xf0\x9f\x94\x8d  파트명 / ID 검색...", ddSearch, sizeof(ddSearch));
        ImGui::Separator();

        // Build lower-case filter
        std::string flt = ddSearch;
        for (auto& c : flt) c = (char)tolower((unsigned char)c);

        int matchCount = 0;
        for (auto& [pid, ps] : data_.parts) {
            // Filter check
            if (flt.size() > 0) {
                std::string h = "part " + std::to_string(pid) + " " + ps.name;
                for (auto& c : h) c = (char)tolower((unsigned char)c);
                if (h.find(flt) == std::string::npos) continue;
            }
            ++matchCount;
            char label[128]; snprintf(label, sizeof(label), "Part %d \xe2\x80\x94 %s", pid, ps.name.c_str());
            bool sel = (deepDivePartId_ == pid);
            if (ImGui::Selectable(label, sel)) {
                deepDivePartId_ = pid;
                ddSearch[0] = '\0';
                ImGui::CloseCurrentPopup();
            }
            if (sel) ImGui::SetItemDefaultFocus();
        }
        if (matchCount == 0)
            ImGui::TextColored(COL_DIM, "  (검색 결과 없음)");
        ImGui::EndCombo();
    }
    ImGui::SameLine();

    if (ImGui::Button("> ##ddNext")) {
        ddIdx = (ddIdx + 1) % (int)partIds.size();
        deepDivePartId_ = partIds[ddIdx];
    }
    if (ImGui::IsItemHovered()) ImGui::SetMouseCursor(ImGuiMouseCursor_Hand);
    ImGui::SameLine();
    ImGui::TextColored(COL_DIM, "%d / %d", ddIdx + 1, (int)partIds.size());

    auto pit = data_.parts.find(deepDivePartId_);
    if (pit == data_.parts.end()) return;
    auto& ps = pit->second;

    ImGui::Spacing();

    // KPI cards
    ImGui::Columns(5, nullptr, false);
    char buf[64];

    auto ddKpi = [&](const char* label, double val, const char* fmt, const char* unit, ImVec4 col) {
        ImGui::BeginGroup();
        ImGui::TextColored(COL_DIM, "%s", label);
        snprintf(buf, sizeof(buf), fmt, val);
        ImGui::TextColored(col, "%s", buf);
        ImGui::TextColored(COL_DIM, "%s", unit);
        ImGui::EndGroup();
        ImGui::NextColumn();
    };

    ddKpi("Peak Stress", ps.peak_stress, "%.1f", "MPa", COL_ACCENT);
    ddKpi("Peak Strain", ps.peak_strain, "%.4f", "", COL_YELLOW);
    ddKpi("Peak Disp", ps.peak_disp, "%.2f", "mm", COL_PURPLE);
    ddKpi("Safety Factor", ps.safety_factor, "%.3f", "",
          ps.safety_factor >= 1.0 ? COL_ACCENT : ps.safety_factor > 0 ? COL_RED : COL_DIM);
    if (!ps.mat_type.empty())
        ddKpi("Material", 0, "%s", ps.mat_type.c_str(), COL_BLUE);
    else
        ImGui::NextColumn();
    ImGui::Columns(1);

    // Second row: vel / acc / utilization (shown only if data available)
    bool hasVel = ps.peak_vel > 0;
    bool hasAcc = ps.peak_acc > 0;
    bool hasUtil = ps.stress_ratio > 0 || ps.strain_ratio > 0;
    if (hasVel || hasAcc || hasUtil) {
        int ncols2 = (hasVel ? 1 : 0) + (hasAcc ? 1 : 0) + (hasUtil ? 1 : 0);
        if (ncols2 > 0) {
            ImGui::Spacing();
            ImGui::Columns(ncols2, nullptr, false);
            if (hasVel) { ddKpi("Peak Vel", ps.peak_vel, "%.2f", "mm/s", COL_ACCENT); }
            if (hasAcc) { ddKpi("Peak Acc", ps.peak_acc, "%.2f", "mm/s²", COL_YELLOW); }
            if (hasUtil) {
                double util = std::max(ps.stress_ratio, ps.strain_ratio) * 100.0;
                ImVec4 uc = util > 100 ? COL_RED : util > 85 ? COL_YELLOW : COL_ACCENT;
                ddKpi("Utilization", util, "%.1f", "%", uc);
            }
            ImGui::Columns(1);
        }
    }

    // Additional info
    if (ps.time_of_peak_stress > 0)
        ImGui::Text("  Peak stress at t=%.6f, Element #%d", ps.time_of_peak_stress, ps.peak_element_id);
    if (ps.peak_max_principal != 0)
        ImGui::Text("  Principal: S1=%.1f  S3=%.1f MPa", ps.peak_max_principal, ps.peak_min_principal);
    if (ps.peak_max_principal_strain != 0)
        ImGui::Text("  Principal Strain: e1=%.4f  e3=%.4f", ps.peak_max_principal_strain, ps.peak_min_principal_strain);
    if (ps.peak_vel > 0 || ps.peak_acc > 0)
        ImGui::Text("  Peak Vel: %.2f mm/s  |  Peak Acc: %.2f mm/s²", ps.peak_vel, ps.peak_acc);

    // Stress/Strain limit info + utilization
    if (ps.stress_limit > 0) {
        ImVec4 ratioCol = ps.stress_ratio > 1.0 ? COL_RED : ps.stress_ratio > 0.85 ? COL_YELLOW : COL_ACCENT;
        ImGui::Text("  Stress limit: %.1f MPa", ps.stress_limit);
        if (!ps.stress_source.empty()) { ImGui::SameLine(); ImGui::TextColored(COL_DIM, "(%s)", ps.stress_source.c_str()); }
        ImGui::SameLine(350);
        ImGui::Text("Utilization:"); ImGui::SameLine();
        ImGui::TextColored(ratioCol, "%.1f%%", ps.stress_ratio * 100.0);
    }
    if (ps.strain_limit > 0) {
        ImVec4 ratioCol = ps.strain_ratio > 1.0 ? COL_RED : ps.strain_ratio > 0.85 ? COL_YELLOW : COL_ACCENT;
        ImGui::Text("  Strain limit: %.4f", ps.strain_limit);
        if (!ps.strain_source.empty()) { ImGui::SameLine(); ImGui::TextColored(COL_DIM, "(%s)", ps.strain_source.c_str()); }
        ImGui::SameLine(350);
        ImGui::Text("Utilization:"); ImGui::SameLine();
        ImGui::TextColored(ratioCol, "%.1f%%", ps.strain_ratio * 100.0);
    }

    ImGui::Spacing();
    ImGui::Separator();

    // Stress chart (max + avg)
    auto* stressTS = ([&]() -> const PartTimeSeries* {
        for (auto& s : data_.stress) if (s.part_id == deepDivePartId_) return &s;
        return nullptr;
    })();

    if (stressTS && !stressTS->data.empty()) {
        int n = (int)stressTS->data.size();
        std::vector<double> t(n), vmax(n), vavg(n);
        for (int i = 0; i < n; ++i) { t[i] = stressTS->data[i].time; vmax[i] = stressTS->data[i].max_value; vavg[i] = stressTS->data[i].avg_value; }

        if (ImPlot::BeginPlot("##DDStress", ImVec2(-1, 200))) {
            ImPlot::SetupAxes("Time", "Von Mises (MPa)");
            ImPlot::PlotLine("Max", t.data(), vmax.data(), n);
            ImPlot::PlotLine("Avg", t.data(), vavg.data(), n);
            // Yield line (global)
            if (data_.yield_stress > 0) {
                double xt[] = {t.front(), t.back()}, yt[] = {data_.yield_stress, data_.yield_stress};
                ImVec4 yc(1.0f,0.3f,0.3f,0.7f);
                ImPlot::PlotLine("Yield", xt, yt, 2, ImPlotSpec(ImPlotProp_LineColor, yc, ImPlotProp_LineWeight, 1.5f));
            }
            // Per-part stress limit line
            if (ps.stress_limit > 0 && ps.stress_limit != data_.yield_stress) {
                double xt[] = {t.front(), t.back()}, yt[] = {ps.stress_limit, ps.stress_limit};
                ImVec4 lc(1.0f,0.65f,0.0f,0.7f);
                ImPlot::PlotLine("Limit", xt, yt, 2, ImPlotSpec(ImPlotProp_LineColor, lc, ImPlotProp_LineWeight, 1.2f));
            }
            ImPlot::EndPlot();
        }
    }

    // Strain chart
    auto* strainTS = ([&]() -> const PartTimeSeries* {
        for (auto& s : data_.strain) if (s.part_id == deepDivePartId_) return &s;
        return nullptr;
    })();

    if (strainTS && !strainTS->data.empty()) {
        int n = (int)strainTS->data.size();
        std::vector<double> t(n), v(n);
        for (int i = 0; i < n; ++i) { t[i] = strainTS->data[i].time; v[i] = strainTS->data[i].max_value; }
        if (ImPlot::BeginPlot("##DDStrain", ImVec2(-1, 180))) {
            ImPlot::SetupAxes("Time", "Eff. Plastic Strain");
            ImPlot::PlotLine("Strain", t.data(), v.data(), n);
            if (ps.strain_limit > 0) {
                double xt[] = {t.front(), t.back()}, yt[] = {ps.strain_limit, ps.strain_limit};
                ImVec4 lc(1.0f,0.65f,0.0f,0.7f);
                ImPlot::PlotLine("Limit", xt, yt, 2, ImPlotSpec(ImPlotProp_LineColor, lc, ImPlotProp_LineWeight, 1.2f));
            }
            ImPlot::EndPlot();
        }
    }

    // Principal Stress σ₁ / σ₃
    {
        auto* p1 = ([&]() -> const PartTimeSeries* {
            for (auto& s : data_.max_principal) if (s.part_id == deepDivePartId_) return &s;
            return nullptr; })();
        auto* p3 = ([&]() -> const PartTimeSeries* {
            for (auto& s : data_.min_principal) if (s.part_id == deepDivePartId_) return &s;
            return nullptr; })();

        if ((p1 && !p1->data.empty()) || (p3 && !p3->data.empty())) {
            // Combine both into one chart for compactness
            if (ImPlot::BeginPlot("##DDPrinStress", ImVec2(-1, 170))) {
                ImPlot::SetupAxes("Time", "Principal Stress (MPa)");
                if (p1 && !p1->data.empty()) {
                    int n = (int)p1->data.size();
                    std::vector<double> t(n), v(n);
                    for (int i = 0; i < n; ++i) { t[i] = p1->data[i].time; v[i] = p1->data[i].max_value; }
                    ImPlot::PlotLine("σ₁ max", t.data(), v.data(), n,
                        ImPlotSpec(ImPlotProp_LineColor, COL_BLUE));
                }
                if (p3 && !p3->data.empty()) {
                    int n = (int)p3->data.size();
                    std::vector<double> t(n), v(n);
                    for (int i = 0; i < n; ++i) { t[i] = p3->data[i].time; v[i] = p3->data[i].min_value; }
                    ImPlot::PlotLine("σ₃ min", t.data(), v.data(), n,
                        ImPlotSpec(ImPlotProp_LineColor, COL_PURPLE));
                }
                ImPlot::EndPlot();
            }
        }
    }

    // Principal Strain ε₁ / ε₃
    {
        auto* e1 = ([&]() -> const PartTimeSeries* {
            for (auto& s : data_.max_principal_strain) if (s.part_id == deepDivePartId_) return &s;
            return nullptr; })();
        auto* e3 = ([&]() -> const PartTimeSeries* {
            for (auto& s : data_.min_principal_strain) if (s.part_id == deepDivePartId_) return &s;
            return nullptr; })();

        if ((e1 && !e1->data.empty()) || (e3 && !e3->data.empty())) {
            if (ImPlot::BeginPlot("##DDPrinStrain", ImVec2(-1, 160))) {
                ImPlot::SetupAxes("Time", "Principal Strain");
                if (e1 && !e1->data.empty()) {
                    int n = (int)e1->data.size();
                    std::vector<double> t(n), v(n);
                    for (int i = 0; i < n; ++i) { t[i] = e1->data[i].time; v[i] = e1->data[i].max_value; }
                    ImPlot::PlotLine("ε₁ max", t.data(), v.data(), n,
                        ImPlotSpec(ImPlotProp_LineColor, ImVec4(0.15f,0.68f,0.38f,1)));
                }
                if (e3 && !e3->data.empty()) {
                    int n = (int)e3->data.size();
                    std::vector<double> t(n), v(n);
                    for (int i = 0; i < n; ++i) { t[i] = e3->data[i].time; v[i] = e3->data[i].min_value; }
                    ImPlot::PlotLine("ε₃ min", t.data(), v.data(), n,
                        ImPlotSpec(ImPlotProp_LineColor, ImVec4(0.25f,0.35f,0.55f,1)));
                }
                ImPlot::EndPlot();
            }
        }
    }

    // Motion charts
    auto* motion = ([&]() -> const DeepReportData::MotionSeries* {
        for (auto& m : data_.motion) if (m.part_id == deepDivePartId_) return &m;
        return nullptr;
    })();

    if (motion && !motion->t.empty()) {
        int n = (int)motion->t.size();

        // Displacement magnitude + max
        if (ImPlot::BeginPlot("##DDDisp", ImVec2(-1, 180))) {
            ImPlot::SetupAxes("Time", "Displacement (mm)");
            ImPlot::PlotLine("Avg |U|", motion->t.data(), motion->disp_mag.data(), n);
            if (!motion->max_disp_mag.empty())
                ImPlot::PlotLine("Max |U|", motion->t.data(), motion->max_disp_mag.data(), n);
            ImPlot::EndPlot();
        }

        // Displacement XYZ
        if (!motion->disp_x.empty()) {
            if (ImPlot::BeginPlot("##DDDispXYZ", ImVec2(-1, 170))) {
                ImPlot::SetupAxes("Time", "Displacement XYZ (mm)");
                ImPlot::PlotLine("Ux", motion->t.data(), motion->disp_x.data(), n);
                ImPlot::PlotLine("Uy", motion->t.data(), motion->disp_y.data(), n);
                ImPlot::PlotLine("Uz", motion->t.data(), motion->disp_z.data(), n);
                ImPlot::EndPlot();
            }
        }

        // Velocity magnitude + XYZ
        if (!motion->vel_mag.empty()) {
            static const ImVec4 cX(0.91f,0.27f,0.38f,1), cY(0.15f,0.75f,0.45f,1), cZ(0.31f,0.56f,1.0f,1);
            if (ImPlot::BeginPlot("##DDVel", ImVec2(-1, 150))) {
                ImPlot::SetupAxes("Time", "Velocity (mm/s)");
                ImPlot::PlotLine("|V|", motion->t.data(), motion->vel_mag.data(), n);
                if (!motion->vel_x.empty() && (int)motion->vel_x.size() == n) {
                    ImPlot::PlotLine("Vx", motion->t.data(), motion->vel_x.data(), n,
                        ImPlotSpec(ImPlotProp_LineColor, cX, ImPlotProp_LineWeight, 1.0f));
                    ImPlot::PlotLine("Vy", motion->t.data(), motion->vel_y.data(), n,
                        ImPlotSpec(ImPlotProp_LineColor, cY, ImPlotProp_LineWeight, 1.0f));
                    ImPlot::PlotLine("Vz", motion->t.data(), motion->vel_z.data(), n,
                        ImPlotSpec(ImPlotProp_LineColor, cZ, ImPlotProp_LineWeight, 1.0f));
                }
                ImPlot::EndPlot();
            }
        }

        // Acceleration magnitude + XYZ
        if (!motion->acc_mag.empty()) {
            static const ImVec4 cX2(0.91f,0.27f,0.38f,1), cY2(0.15f,0.75f,0.45f,1), cZ2(0.31f,0.56f,1.0f,1);
            if (ImPlot::BeginPlot("##DDAcc", ImVec2(-1, 150))) {
                ImPlot::SetupAxes("Time", "Acceleration");
                ImPlot::PlotLine("|A|", motion->t.data(), motion->acc_mag.data(), n);
                if (!motion->acc_x.empty() && (int)motion->acc_x.size() == n) {
                    ImPlot::PlotLine("Ax", motion->t.data(), motion->acc_x.data(), n,
                        ImPlotSpec(ImPlotProp_LineColor, cX2, ImPlotProp_LineWeight, 1.0f));
                    ImPlot::PlotLine("Ay", motion->t.data(), motion->acc_y.data(), n,
                        ImPlotSpec(ImPlotProp_LineColor, cY2, ImPlotProp_LineWeight, 1.0f));
                    ImPlot::PlotLine("Az", motion->t.data(), motion->acc_z.data(), n,
                        ImPlotSpec(ImPlotProp_LineColor, cZ2, ImPlotProp_LineWeight, 1.0f));
                }
                ImPlot::EndPlot();
            }
        }
    }

    // ── Part renders: files matching part_{pid}/ or part{pid}_ ──
    if (!data_.render_files.empty()) {
        namespace fs = std::filesystem;
        // Collect render files that belong to this part
        std::string pidStr = std::to_string(deepDivePartId_);
        std::string patA = "part_" + pidStr + "/";   // folder: part_10/
        std::string patB = "part_" + pidStr + "_";   // filename prefix: part_10_z.mp4
        std::vector<std::string> partRenders;
        for (const auto& f : data_.render_files) {
            bool matchA = f.find(patA) != std::string::npos;
            bool matchB = f.find(patB) != std::string::npos;
            if (matchA || matchB) partRenders.push_back(f);
        }

        if (!partRenders.empty()) {
            ImGui::Spacing();
            SectionHeader("Part Renders", COL_ACCENT);
            ImGui::Spacing();

            // Horizontal thumbnail row — one button per file
            for (const auto& rf : partRenders) {
                std::string fname = fs::path(rf).filename().string();
                // Axis tag from filename/folder suffix
                std::string axTag;
                for (char ax : {'x','y','z','X','Y','Z'}) {
                    if (fname.size() >= 5 && fname[fname.size()-5] == ax) { axTag = std::string(1,ax); break; }
                    if (fname.size() >= 6 && fname[fname.size()-6] == ax) { axTag = std::string(1,ax); break; }
                }

                bool isActive = (rf == activeVideo_);
                ImGui::PushID(rf.c_str());
                if (isActive) ImGui::PushStyleColor(ImGuiCol_Button, ImVec4(0.15f,0.30f,0.50f,1.0f));
                else ImGui::PushStyleColor(ImGuiCol_Button, ImVec4(0.12f,0.15f,0.24f,1.0f));

                std::string btnLabel = (axTag.empty() ? fname : axTag + "-axis  " + fname);
                if (ImGui::Button(("  " + btnLabel + "  ").c_str())) {
                    if (activeVideo_ != rf) {
                        activeVideo_ = rf;
                        if (!players_.count(rf)) {
                            auto vp = std::make_unique<VideoPlayer>();
                            if (vp->open(rf)) { vp->play(); players_[rf] = std::move(vp); }
                        } else {
                            players_[rf]->setFrame(0); players_[rf]->play();
                        }
                    }
                }
                ImGui::PopStyleColor();
                if (isActive) { ImGui::SameLine(); ImGui::TextColored(ImVec4(0.4f,0.8f,1.0f,1.0f), "<<"); }
                ImGui::PopID();
                ImGui::SameLine();
            }
            ImGui::NewLine();

            // Inline player for active video if it belongs to this part
            bool activeIsPartRender = false;
            for (const auto& rf : partRenders) if (rf == activeVideo_) { activeIsPartRender = true; break; }

            if (activeIsPartRender && players_.count(activeVideo_)) {
                auto& vp = players_[activeVideo_];
                vp->update(ImGui::GetIO().DeltaTime);
                if (vp->isLoaded()) {
                    // Controls
                    if (vp->isPlaying()) { if (ImGui::Button("Pause##dd")) vp->pause(); }
                    else                 { if (ImGui::Button("Play##dd"))  vp->play();  }
                    ImGui::SameLine();
                    int fr = vp->currentFrame();
                    ImGui::SetNextItemWidth(ImGui::GetContentRegionAvail().x - 120);
                    if (ImGui::SliderInt("##ddvf", &fr, 0, vp->frameCount()-1))
                        { vp->setFrame(fr); vp->pause(); }
                    ImGui::SameLine(); ImGui::Text("%d/%d", fr+1, vp->frameCount());

                    // Video display
                    ImVec2 avail = ImGui::GetContentRegionAvail();
                    float aspect = (float)vp->width() / (float)vp->height();
                    float dw = avail.x, dh = dw / aspect;
                    if (dh > avail.y) { dh = avail.y; dw = dh * aspect; }
                    float ox = (avail.x - dw) * 0.5f;
                    if (ox > 0) ImGui::SetCursorPosX(ImGui::GetCursorPosX() + ox);
                    ImGui::Image((ImTextureID)(intptr_t)vp->texture(), ImVec2(dw, dh));
                    if (ImGui::IsItemHovered() && ImGui::IsMouseDoubleClicked(0))
                        videoFullscreen_ = true;
                }
            }
        }
    }
}

// ============================================================
// Contact Tab
// ============================================================

