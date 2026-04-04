#include "app/DeepReportApp.hpp"
#include "app/DeepReportColors.hpp"
#include <imgui.h>
#include <implot.h>
#include <algorithm>
#include <cstdio>
#include <cmath>
#include <string>
#include <filesystem>

void DeepReportApp::renderVideoFullscreen() {
    if (!videoFullscreen_ || activeVideo_.empty() || !players_.count(activeVideo_)) return;
        auto& vp = players_[activeVideo_];
        ImGuiIO& io = ImGui::GetIO();
        vp->update(io.DeltaTime);

        ImGui::SetNextWindowPos(ImVec2(0, 0));
        ImGui::SetNextWindowSize(io.DisplaySize);
        ImGui::Begin("##VideoFullscreen", nullptr,
            ImGuiWindowFlags_NoTitleBar | ImGuiWindowFlags_NoResize |
            ImGuiWindowFlags_NoMove | ImGuiWindowFlags_NoScrollbar |
            ImGuiWindowFlags_NoDocking);

        // Top bar: title + close
        namespace fs = std::filesystem;
        std::string folder = fs::path(activeVideo_).parent_path().filename().string();
        ImGui::TextColored(COL_ACCENT, "%s", parseSectionLabel(folder).c_str());
        ImGui::SameLine(ImGui::GetWindowWidth() - 100);
        if (ImGui::Button("Exit Fullscreen") || ImGui::IsKeyPressed(ImGuiKey_Escape)) {
            videoFullscreen_ = false;
        }

        // Controls
        if (vp->isPlaying()) {
            if (ImGui::Button("  Pause  ")) vp->pause();
        } else {
            if (ImGui::Button("  Play   ")) vp->play();
        }
        ImGui::SameLine();
        int frame = vp->currentFrame();
        ImGui::SetNextItemWidth(ImGui::GetContentRegionAvail().x - 120);
        if (ImGui::SliderInt("##fframe", &frame, 0, vp->frameCount() - 1)) {
            vp->setFrame(frame);
            vp->pause();
        }
        ImGui::SameLine();
        ImGui::Text("%d / %d", frame + 1, vp->frameCount());

        // Video — fill remaining space
        ImVec2 avail = ImGui::GetContentRegionAvail();
        float aspect = (float)vp->width() / (float)vp->height();
        float dispW = avail.x;
        float dispH = dispW / aspect;
        if (dispH > avail.y) { dispH = avail.y; dispW = dispH * aspect; }
        float offsetX = (avail.x - dispW) * 0.5f;
        if (offsetX > 0) ImGui::SetCursorPosX(ImGui::GetCursorPosX() + offsetX);
        ImGui::Image((ImTextureID)(intptr_t)vp->texture(), ImVec2(dispW, dispH));

        ImGui::End();
}

// ============================================================
// Section View Config Panel
// ============================================================
void DeepReportApp::renderSectionViewConfig() {
    ImGui::SetNextItemOpen(svCfgConfigOpen_, ImGuiCond_Once);
    svCfgConfigOpen_ = ImGui::CollapsingHeader("  Section View Config  (generate renders)");
    if (!svCfgConfigOpen_) return;

    ImGui::PushStyleColor(ImGuiCol_ChildBg, ImVec4(0.09f,0.10f,0.17f,0.7f));
    ImGui::BeginChild("##svCfg", ImVec2(-1, 0), true, ImGuiWindowFlags_AlwaysAutoResize);

    // Row 1: Axes
    ImGui::TextColored(COL_DIM, "Axes:");
    ImGui::SameLine(70); ImGui::Checkbox("X##ax", &svCfgAxX_);
    ImGui::SameLine();   ImGui::Checkbox("Y##ax", &svCfgAxY_);
    ImGui::SameLine();   ImGui::Checkbox("Z##ax", &svCfgAxZ_);

    // Row 2: Scalar fields
    ImGui::TextColored(COL_DIM, "Fields:");
    ImGui::SameLine(70); ImGui::Checkbox("Von Mises##fld", &svCfgFieldVM_);
    ImGui::SameLine();   ImGui::Checkbox("Strain##fld", &svCfgFieldStrain_);
    ImGui::SameLine();   ImGui::Checkbox("Displacement##fld", &svCfgFieldDisp_);
    ImGui::SameLine();   ImGui::Checkbox("Pressure##fld", &svCfgFieldPressure_);
    ImGui::SameLine();   ImGui::Checkbox("Max Shear##fld", &svCfgFieldMaxShear_);

    // Row 3: Target part IDs + fade
    ImGui::TextColored(COL_DIM, "Part IDs:");
    ImGui::SameLine(70); ImGui::SetNextItemWidth(220);
    ImGui::InputText("##svpids", svCfgTargetIds_, sizeof(svCfgTargetIds_));
    if (ImGui::IsItemHovered())
        ImGui::SetTooltip("Comma-separated part IDs (e.g. 4,10,15). Empty = all parts.");
    ImGui::SameLine();
    ImGui::TextColored(COL_DIM, "Fade:");
    ImGui::SameLine(); ImGui::SetNextItemWidth(80);
    ImGui::SliderFloat("##svfade", &svCfgFade_, 0.0f, 5.0f, "%.1f");
    if (ImGui::IsItemHovered())
        ImGui::SetTooltip("0 = solid model. >0 = distance-based opacity fade.");
    ImGui::SameLine();
    ImGui::Checkbox("Per-Part##svpp", &svCfgPerPart_);
    if (ImGui::IsItemHovered())
        ImGui::SetTooltip("Generate a separate render for each target part.");

    ImGui::Spacing();

    // Generate YAML / CLI
    auto buildAxes = [&]() {
        std::string s;
        if (svCfgAxX_) s += "x ";
        if (svCfgAxY_) s += "y ";
        if (svCfgAxZ_) s += "z ";
        if (!s.empty()) s.pop_back();
        return s;
    };
    auto buildFields = [&]() {
        std::string s;
        if (svCfgFieldVM_)       s += "von_mises ";
        if (svCfgFieldStrain_)   s += "strain ";
        if (svCfgFieldDisp_)     s += "displacement ";
        if (svCfgFieldPressure_) s += "pressure ";
        if (svCfgFieldMaxShear_) s += "max_shear ";
        if (!s.empty()) s.pop_back();
        return s;
    };

    std::string axes  = buildAxes();
    std::string fields = buildFields();
    std::string pids(svCfgTargetIds_);

    // CLI string
    std::string cli = "koo_deep_report --section-view";
    if (!axes.empty())   cli += " --section-view-axes " + axes;
    if (!fields.empty()) cli += " --section-view-fields " + fields;
    if (!pids.empty())   cli += " --section-view-target-ids " + pids;
    if (svCfgFade_ > 0)  { char buf[16]; snprintf(buf,sizeof(buf),"%.1f",svCfgFade_); cli += " --section-view-fade " + std::string(buf); }
    if (svCfgPerPart_)   cli += " --section-view-per-part";
    cli += " <d3plot_path>";

    // YAML block
    std::string yaml = "section_views:\n";
    const bool axFlags[3] = {svCfgAxX_, svCfgAxY_, svCfgAxZ_};
    const char axChars[3] = {'x', 'y', 'z'};
    const bool fldFlags[5] = {svCfgFieldVM_, svCfgFieldStrain_, svCfgFieldDisp_, svCfgFieldPressure_, svCfgFieldMaxShear_};
    const char* fldNames[5] = {"von_mises", "strain", "displacement", "pressure", "max_shear"};
    for (int ai = 0; ai < 3; ++ai) {
        if (!axFlags[ai]) continue;
        char axc = axChars[ai];
        for (int fi = 0; fi < 5; ++fi) {
            if (!fldFlags[fi]) continue;
            yaml += std::string("  - axis: ") + axc + "\n";
            yaml += std::string("    field: ") + fldNames[fi] + "\n";
            if (!pids.empty())    yaml += "    target_ids: [" + pids + "]\n";
            if (svCfgFade_ > 0) { char buf[16]; snprintf(buf,sizeof(buf),"%.1f",svCfgFade_); yaml += "    fade: " + std::string(buf) + "\n"; }
            if (svCfgPerPart_)   yaml += "    per_part: true\n";
        }
    }

    // Display panels side by side
    float halfW = (ImGui::GetContentRegionAvail().x - 8) * 0.5f;

    ImGui::BeginChild("##svCli", ImVec2(halfW, 54), true);
    ImGui::TextColored(COL_DIM, "CLI Command:");
    ImGui::TextColored(ImVec4(0.7f,1.0f,0.7f,1.0f), "%s", cli.c_str());
    ImGui::EndChild();
    ImGui::SameLine();
    if (ImGui::Button("Copy CLI")) ImGui::SetClipboardText(cli.c_str());

    ImGui::BeginChild("##svYaml", ImVec2(halfW, 120), true);
    ImGui::TextColored(COL_DIM, "YAML:");
    ImGui::TextColored(COL_ACCENT, "%s", yaml.c_str());
    ImGui::EndChild();
    ImGui::SameLine();
    if (ImGui::Button("Copy YAML")) ImGui::SetClipboardText(yaml.c_str());

    ImGui::Spacing();
    ImGui::EndChild();
    ImGui::PopStyleColor();
}

void DeepReportApp::renderRenderGalleryTab() {
    // Check fullscreen first
    if (videoFullscreen_) renderVideoFullscreen();

    // Section View config panel (collapsible)
    renderSectionViewConfig();
    ImGui::Spacing();

    if (data_.render_files.empty()) {
        ImGui::TextColored(COL_DIM, "No render files found");
        return;
    }

    // ── Top: accordion grouped by folder ──
    ImGui::TextColored(COL_ACCENT, "Section View Renders");
    ImGui::Spacing();

    namespace fs = std::filesystem;

    // Build folder → files map (preserve insertion order)
    std::vector<std::string> folderOrder;
    std::map<std::string, std::vector<std::string>> folderFiles;
    for (const auto& f : data_.render_files) {
        std::string folder = fs::path(f).parent_path().filename().string();
        if (!folderFiles.count(folder)) folderOrder.push_back(folder);
        folderFiles[folder].push_back(f);
    }

    // Helper: classify folder to axis label
    auto axisTag = [](const std::string& folder) -> std::string {
        size_t lu = folder.rfind('_');
        if (lu == std::string::npos) return "";
        std::string ax = folder.substr(lu + 1);
        if (ax == "x" || ax == "X") return "[X]";
        if (ax == "y" || ax == "Y") return "[Y]";
        if (ax == "z" || ax == "Z") return "[Z]";
        return "[" + ax + "]";
    };

    // Auto-open first group
    static bool galleryFirstRun = true;
    std::string firstFolder = folderOrder.empty() ? "" : folderOrder[0];

    float accordionH = std::min((float)folderOrder.size() * 80.0f + 40.0f,
                                ImGui::GetContentRegionAvail().y * 0.35f);
    ImGui::BeginChild("RenderAccordion", ImVec2(-1, std::max(60.0f, accordionH)), false);

    int gidx = 0;
    for (const auto& folder : folderOrder) {
        std::string label = parseSectionLabel(folder);
        std::string axTag = axisTag(folder);
        bool hasActive = false;
        for (const auto& f : folderFiles[folder]) if (f == activeVideo_) hasActive = true;

        // Header color highlight if active
        if (hasActive) ImGui::PushStyleColor(ImGuiCol_Header, ImVec4(0.15f,0.30f,0.50f,1.0f));

        bool defaultOpen = galleryFirstRun ? (folder == firstFolder) : hasActive;
        ImGui::SetNextItemOpen(defaultOpen, galleryFirstRun ? ImGuiCond_Once : ImGuiCond_None);
        bool open = ImGui::CollapsingHeader(("  " + label + "  " + axTag + "##grp" + std::to_string(gidx)).c_str());

        if (hasActive) ImGui::PopStyleColor();

        if (open) {
            ImGui::Indent(12.0f);
            for (const auto& f : folderFiles[folder]) {
                std::string fname = fs::path(f).filename().string();
                bool isActive = (f == activeVideo_);
                ImGui::PushID(gidx * 100 + (int)(&f - &folderFiles[folder][0]));
                if (isActive) {
                    ImGui::PushStyleColor(ImGuiCol_Button, ImVec4(0.15f,0.30f,0.50f,1.0f));
                    ImGui::PushStyleColor(ImGuiCol_ButtonHovered, ImVec4(0.20f,0.35f,0.55f,1.0f));
                } else {
                    ImGui::PushStyleColor(ImGuiCol_Button, COL_CARD);
                    ImGui::PushStyleColor(ImGuiCol_ButtonHovered, ImVec4(0.15f,0.20f,0.32f,1.0f));
                }
                if (ImGui::Button(("  Play  " + fname + "  ").c_str())) {
                    if (activeVideo_ != f) {
                        activeVideo_ = f;
                        if (!players_.count(f)) {
                            auto vp = std::make_unique<VideoPlayer>();
                            if (vp->open(f)) { vp->play(); players_[f] = std::move(vp); }
                        } else {
                            players_[f]->setFrame(0); players_[f]->play();
                        }
                    }
                }
                ImGui::PopStyleColor(2);
                if (isActive) { ImGui::SameLine(); ImGui::TextColored(ImVec4(0.4f,0.8f,1.0f,1.0f), "<<"); }
                ImGui::PopID();
            }
            ImGui::Unindent(12.0f);
        }
        ++gidx;
    }
    galleryFirstRun = false;

    ImGui::EndChild();
    ImGui::Separator();

    // ── Bottom: video player ──
    if (!activeVideo_.empty() && players_.count(activeVideo_)) {
        auto& vp = players_[activeVideo_];
        ImGuiIO& io = ImGui::GetIO();
        vp->update(io.DeltaTime);

        if (vp->isLoaded()) {
            // Controls row
            if (vp->isPlaying()) {
                if (ImGui::Button("  Pause  ")) vp->pause();
            } else {
                if (ImGui::Button("  Play   ")) vp->play();
            }
            ImGui::SameLine();
            if (ImGui::Button("Stop")) vp->stop();
            ImGui::SameLine();

            int frame = vp->currentFrame();
            ImGui::SetNextItemWidth(ImGui::GetContentRegionAvail().x - 200);
            if (ImGui::SliderInt("##nframe", &frame, 0, vp->frameCount() - 1)) {
                vp->setFrame(frame);
                vp->pause();
            }
            ImGui::SameLine();
            ImGui::Text("%d/%d", frame + 1, vp->frameCount());
            ImGui::SameLine();
            if (ImGui::Button("Fullscreen")) {
                videoFullscreen_ = true;
            }

            // Video display — fill remaining space, centered
            ImVec2 avail = ImGui::GetContentRegionAvail();
            float aspect = (float)vp->width() / (float)vp->height();
            float dispW = avail.x;
            float dispH = dispW / aspect;
            if (dispH > avail.y) { dispH = avail.y; dispW = dispH * aspect; }
            float offsetX = (avail.x - dispW) * 0.5f;
            if (offsetX > 0) ImGui::SetCursorPosX(ImGui::GetCursorPosX() + offsetX);

            ImGui::Image((ImTextureID)(intptr_t)vp->texture(), ImVec2(dispW, dispH));

            // Double-click → fullscreen
            if (ImGui::IsItemHovered() && ImGui::IsMouseDoubleClicked(0)) {
                videoFullscreen_ = true;
            }
        } else {
            ImGui::TextColored(COL_DIM, "Decoding...");
        }
    } else {
        ImVec2 avail = ImGui::GetContentRegionAvail();
        ImVec2 textSize = ImGui::CalcTextSize("Click a section view above to preview");
        ImGui::SetCursorPos(ImVec2(
            (avail.x - textSize.x) * 0.5f + ImGui::GetCursorPosX(),
            (avail.y - textSize.y) * 0.5f + ImGui::GetCursorPosY()));
        ImGui::TextColored(COL_DIM, "Click a section view above to preview");
    }
}

// ============================================================
// 3D Viewer — shaders
// ============================================================
// ============================================================
// Deep Dive Tab — per-part comprehensive view
// ============================================================

