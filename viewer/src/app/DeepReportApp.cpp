#include "app/DeepReportApp.hpp"
#include "app/DeepReportColors.hpp"

#include <glad/glad.h>
#include <GLFW/glfw3.h>
#include <imgui.h>
#include <imgui_internal.h>
#include <imgui_impl_glfw.h>
#include <imgui_impl_opengl3.h>
#include <implot.h>

#include <iostream>
#include <cstdio>
#include <algorithm>
#include <cmath>
#include <filesystem>
#include <map>

// ============================================================
// Init
// ============================================================
bool DeepReportApp::init(int width, int height) {
    if (!glfwInit()) return false;

    glfwWindowHint(GLFW_CONTEXT_VERSION_MAJOR, 3);
    glfwWindowHint(GLFW_CONTEXT_VERSION_MINOR, 3);
    glfwWindowHint(GLFW_OPENGL_PROFILE, GLFW_OPENGL_CORE_PROFILE);

    // Maximize window on start
    window_ = glfwCreateWindow(width, height, "KooViewer — Deep Report", nullptr, nullptr);
    glfwMaximizeWindow(window_);
    if (!window_) { glfwTerminate(); return false; }
    glfwMakeContextCurrent(window_);
    glfwSwapInterval(1);

    if (!gladLoadGLLoader((GLADloadproc)glfwGetProcAddress)) return false;

    IMGUI_CHECKVERSION();
    ImGui::CreateContext();
    ImPlot::CreateContext();

    ImGuiIO& io = ImGui::GetIO();
    io.ConfigFlags |= ImGuiConfigFlags_DockingEnable;
    io.ConfigErrorRecoveryEnableAssert = false;
    io.ConfigErrorRecoveryEnableDebugLog = false;
    io.ConfigErrorRecoveryEnableTooltip = false;

    // Refined dark theme — inspired by modern CAE tools
    ImGui::StyleColorsDark();
    auto& s = ImGui::GetStyle();
    s.WindowRounding = 8.0f;
    s.FrameRounding = 6.0f;
    s.TabRounding = 6.0f;
    s.GrabRounding = 4.0f;
    s.ScrollbarRounding = 6.0f;
    s.ChildRounding = 6.0f;
    s.PopupRounding = 6.0f;
    s.WindowBorderSize = 1.0f;
    s.FrameBorderSize = 0.0f;
    s.TabBorderSize = 0.0f;
    s.ItemSpacing = ImVec2(10, 7);
    s.ItemInnerSpacing = ImVec2(8, 5);
    s.WindowPadding = ImVec2(14, 12);
    s.FramePadding = ImVec2(8, 5);
    s.TabBarBorderSize = 1.0f;
    s.IndentSpacing = 18;
    s.ScrollbarSize = 12;
    s.GrabMinSize = 10;
    s.SeparatorTextBorderSize = 2;

    // Deep blue-gray palette
    s.Colors[ImGuiCol_WindowBg]       = {0.067f, 0.071f, 0.106f, 1.0f};  // #111224
    s.Colors[ImGuiCol_ChildBg]        = {0.082f, 0.086f, 0.125f, 1.0f};
    s.Colors[ImGuiCol_PopupBg]        = {0.090f, 0.094f, 0.137f, 0.97f};
    s.Colors[ImGuiCol_Border]         = {0.18f, 0.19f, 0.28f, 0.6f};
    s.Colors[ImGuiCol_FrameBg]        = {0.11f, 0.12f, 0.18f, 1.0f};
    s.Colors[ImGuiCol_FrameBgHovered] = {0.14f, 0.15f, 0.24f, 1.0f};
    s.Colors[ImGuiCol_FrameBgActive]  = {0.18f, 0.20f, 0.32f, 1.0f};
    s.Colors[ImGuiCol_TitleBg]        = {0.067f, 0.071f, 0.106f, 1.0f};
    s.Colors[ImGuiCol_TitleBgActive]  = {0.09f, 0.10f, 0.16f, 1.0f};
    s.Colors[ImGuiCol_Tab]            = {0.09f, 0.10f, 0.15f, 1.0f};
    s.Colors[ImGuiCol_TabSelected]    = {0.16f, 0.22f, 0.38f, 1.0f};
    s.Colors[ImGuiCol_TabHovered]     = {0.22f, 0.28f, 0.44f, 1.0f};
    s.Colors[ImGuiCol_Header]         = {0.14f, 0.18f, 0.30f, 1.0f};
    s.Colors[ImGuiCol_HeaderHovered]  = {0.18f, 0.24f, 0.40f, 1.0f};
    s.Colors[ImGuiCol_HeaderActive]   = {0.22f, 0.30f, 0.50f, 1.0f};
    s.Colors[ImGuiCol_Button]         = {0.13f, 0.15f, 0.24f, 1.0f};
    s.Colors[ImGuiCol_ButtonHovered]  = {0.18f, 0.22f, 0.34f, 1.0f};
    s.Colors[ImGuiCol_ButtonActive]   = {0.24f, 0.30f, 0.46f, 1.0f};
    s.Colors[ImGuiCol_SliderGrab]     = {0.31f, 0.80f, 0.64f, 0.8f};
    s.Colors[ImGuiCol_SliderGrabActive] = {0.31f, 0.80f, 0.64f, 1.0f};
    s.Colors[ImGuiCol_CheckMark]      = {0.31f, 0.80f, 0.64f, 1.0f};
    s.Colors[ImGuiCol_TableHeaderBg]  = {0.08f, 0.14f, 0.24f, 1.0f};
    s.Colors[ImGuiCol_TableRowBg]     = {0.0f, 0.0f, 0.0f, 0.0f};
    s.Colors[ImGuiCol_TableRowBgAlt]  = {0.07f, 0.08f, 0.12f, 0.5f};
    s.Colors[ImGuiCol_TableBorderLight] = {0.15f, 0.16f, 0.24f, 0.4f};
    s.Colors[ImGuiCol_ScrollbarBg]    = {0.06f, 0.06f, 0.10f, 0.5f};
    s.Colors[ImGuiCol_ScrollbarGrab]  = {0.20f, 0.22f, 0.32f, 1.0f};
    s.Colors[ImGuiCol_ScrollbarGrabHovered] = {0.28f, 0.30f, 0.42f, 1.0f};
    s.Colors[ImGuiCol_Separator]      = {0.18f, 0.19f, 0.28f, 0.6f};
    s.Colors[ImGuiCol_ResizeGrip]     = {0.31f, 0.80f, 0.64f, 0.2f};
    s.Colors[ImGuiCol_ResizeGripHovered] = {0.31f, 0.80f, 0.64f, 0.5f};

    // ImPlot style
    ImPlot::StyleColorsDark();
    auto& ps = ImPlot::GetStyle();
    ps.MinorAlpha = 0.15f;

    ImGui_ImplGlfw_InitForOpenGL(window_, true);
    ImGui_ImplOpenGL3_Init("#version 330");

    // Load CJK font — larger size for readability
    {
        const char* fontPaths[] = {
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Medium.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-DemiLight.ttc",
            "C:\\Windows\\Fonts\\malgun.ttf",
            nullptr
        };
        bool fontLoaded = false;
        for (int i = 0; fontPaths[i]; ++i) {
            if (std::filesystem::exists(fontPaths[i])) {
                io.Fonts->AddFontFromFileTTF(fontPaths[i], 16.0f, nullptr,
                    io.Fonts->GetGlyphRangesKorean());
                std::cout << "[DeepReport] Loaded font: " << fontPaths[i] << "\n";
                fontLoaded = true;
                break;
            }
        }
        if (!fontLoaded) {
            // Fallback: scale default font slightly larger
            ImFontConfig cfg;
            cfg.SizePixels = 16.0f;
            io.Fonts->AddFontDefault(&cfg);
        }
    }

    return true;
}

// ============================================================
// Main loop
// ============================================================
void DeepReportApp::run(const std::string& outputDir) {
    std::cout << "[DeepReport] Loading: " << outputDir << "\n";
    loadDeepReport(outputDir, data_);
    std::cout << "[DeepReport] Loaded: " << data_.stress.size() << " stress, "
              << data_.parts.size() << " parts, " << data_.motion.size() << " motion\n";

    // Drag & drop
    glfwSetWindowUserPointer(window_, this);
    glfwSetDropCallback(window_, [](GLFWwindow* w, int count, const char** paths) {
        auto* app = (DeepReportApp*)glfwGetWindowUserPointer(w);
        for (int i = 0; i < count; ++i) {
            std::string p = paths[i];
            namespace fs = std::filesystem;
            // If directory dropped, reload
            if (fs::is_directory(p)) {
                DeepReportData newData;
                if (loadDeepReport(p, newData)) {
                    app->data_ = std::move(newData);
                    std::cout << "[Drop] Reloaded: " << p << "\n";
                }
            }
        }
    });

    while (!glfwWindowShouldClose(window_)) {
        glfwPollEvents();

        ImGui_ImplOpenGL3_NewFrame();
        ImGui_ImplGlfw_NewFrame();
        ImGui::NewFrame();

        ImGuiID dsId = ImGui::DockSpaceOverViewport(0, ImGui::GetMainViewport());

        // First-frame layout
        static bool firstFrame = true;
        if (firstFrame) {
            firstFrame = false;
            ImGui::DockBuilderRemoveNode(dsId);
            ImGui::DockBuilderAddNode(dsId, ImGuiDockNodeFlags_DockSpace);
            int fw, fh;
            glfwGetWindowSize(window_, &fw, &fh);
            ImGui::DockBuilderSetNodeSize(dsId, ImVec2((float)fw, (float)fh));

            ImGuiID top, rest;
            ImGui::DockBuilderSplitNode(dsId, ImGuiDir_Up, 0.12f, &top, &rest);
            ImGuiID left, right;
            ImGui::DockBuilderSplitNode(rest, ImGuiDir_Left, 0.20f, &left, &right);

            ImGui::DockBuilderDockWindow("##Summary", top);
            ImGui::DockBuilderDockWindow("Parts", left);
            ImGui::DockBuilderDockWindow("Analysis", right);
            ImGui::DockBuilderFinish(dsId);
        }

        // Keyboard shortcuts
        if (!ImGui::GetIO().WantCaptureKeyboard) {
            // Alt+1..9,0 to switch tabs
            if (ImGui::GetIO().KeyAlt) {
                static const ImGuiKey numKeys[] = {
                    ImGuiKey_1, ImGuiKey_2, ImGuiKey_3, ImGuiKey_4, ImGuiKey_5,
                    ImGuiKey_6, ImGuiKey_7, ImGuiKey_8, ImGuiKey_9, ImGuiKey_0
                };
                for (int k = 0; k < 10; ++k) {
                    if (ImGui::IsKeyPressed(numKeys[k])) {
                        tabToSelect_ = k;
                        break;
                    }
                }
            }
            if (ImGui::IsKeyPressed(ImGuiKey_Slash) && ImGui::GetIO().KeyShift)
                showHelp_ = !showHelp_;  // ? = Shift+/
            if (ImGui::IsKeyPressed(ImGuiKey_F11)) {
                if (glfwGetWindowAttrib(window_, GLFW_MAXIMIZED))
                    glfwRestoreWindow(window_);
                else
                    glfwMaximizeWindow(window_);
            }
            // Ctrl+S screenshot
            if (ImGui::GetIO().KeyCtrl && ImGui::IsKeyPressed(ImGuiKey_S)) {
                int w, h;
                glfwGetFramebufferSize(window_, &w, &h);
                std::vector<unsigned char> pixels(w * h * 3);
                glReadPixels(0, 0, w, h, GL_RGB, GL_UNSIGNED_BYTE, pixels.data());
                // Flip vertically and save as PPM
                std::string path = "screenshot.ppm";
                FILE* fp = fopen(path.c_str(), "wb");
                if (fp) {
                    fprintf(fp, "P6\n%d %d\n255\n", w, h);
                    for (int y = h - 1; y >= 0; --y)
                        fwrite(pixels.data() + y * w * 3, 1, w * 3, fp);
                    fclose(fp);
                    std::cout << "[Screenshot] Saved: " << path << " (" << w << "x" << h << ")\n";
                }
            }
        }

        renderKPIBar();
        if (showHelp_) renderDeepHelpOverlay();
        renderPartTable();

        // Main analysis panel with tabs
        ImGui::Begin("Analysis");

        // Global part filter bar
        {
            ImGui::PushStyleColor(ImGuiCol_FrameBg, ImVec4(0.12f, 0.14f, 0.22f, 1.0f));
            float fw = std::min(360.0f, ImGui::GetContentRegionAvail().x * 0.45f);
            ImGui::SetNextItemWidth(fw);
            ImGui::InputTextWithHint("##gfilter", "파트 필터 (쉼표 구분: PKG, PCB ...)", globalFilter_, sizeof(globalFilter_));
            ImGui::PopStyleColor();
            ImGui::SameLine();
            if (ImGui::SmallButton("X##cfilt")) globalFilter_[0] = '\0';
            if (globalFilter_[0] != '\0') {
                int total = (int)data_.parts.size(), shown = 0;
                for (const auto& [pid, ps] : data_.parts)
                    if (partPassesFilter(pid, ps.name)) ++shown;
                ImGui::SameLine();
                char cnt[40]; snprintf(cnt, sizeof(cnt), "%d / %d parts", shown, total);
                ImGui::TextColored(ImVec4(0.6f, 0.6f, 0.7f, 1.0f), "%s", cnt);
            }
            ImGui::Separator();
        }

        // Pre-compute badge counts
        int badgeStress = 0, badgeWarn = 0, badgeEnergy = 0, badgeQuality = 0;
        for (const auto& [pid, ps] : data_.parts) {
            if (ps.stress_warning == "crit" || ps.strain_warning == "crit") ++badgeStress;
            else if (ps.stress_warning == "warn" || ps.strain_warning == "warn") ++badgeStress;
        }
        for (const auto& w : data_.warnings) {
            if (w.level == "crit") ++badgeWarn;
        }
        if (data_.glstat.energy_ratio_max > 1.1 || data_.glstat.energy_ratio_min < 0.9) ++badgeEnergy;
        for (const auto& eq : data_.element_quality)
            if (eq.min_jacobian < 0 || eq.max_negative_jacobian_count > 0) ++badgeQuality;

        // Draws a badge dot at a pre-saved tab rect position.
        // rect must be captured RIGHT after BeginTabItem, before any content renders.
        auto drawBadge = [&](ImVec2 tabMin, ImVec2 tabMax, int count, bool critical) {
            if (count <= 0) return;
            float cx = tabMax.x - 5.5f;
            float cy = tabMin.y + 5.5f;
            float r = 4.5f;
            ImVec4 bc = critical ? COL_RED : COL_YELLOW;
            ImU32 col = ImGui::ColorConvertFloat4ToU32(ImVec4(bc.x, bc.y, bc.z, 0.95f));
            ImDrawList* dl = ImGui::GetWindowDrawList();
            dl->AddCircleFilled(ImVec2(cx, cy), r, col);
            // For count > 9 show a "+" ring instead of a plain dot
            if (count > 9) {
                ImU32 rim = ImGui::ColorConvertFloat4ToU32(ImVec4(1,1,1,0.6f));
                dl->AddCircle(ImVec2(cx, cy), r, rim, 0, 1.2f);
            }
        };

        if (ImGui::BeginTabBar("AnalysisTabs")) {
            // Helper: select tab if tabToSelect_ matches its index
            int _ti = 0;
            auto tabFlags = [&](int /*unused*/) -> ImGuiTabItemFlags {
                ImGuiTabItemFlags f = (tabToSelect_ == _ti) ? ImGuiTabItemFlags_SetSelected : 0;
                ++_ti;
                return f;
            };

            // Pre-check for stress critical
            bool stressCrit = false;
            for (const auto& [p,s] : data_.parts)
                if (s.stress_warning=="crit" || s.strain_warning=="crit") { stressCrit = true; break; }

            // Each tab: call BeginTabItem, immediately save rect, then render content
            {
                bool open = ImGui::BeginTabItem("\xe2\x96\xa3 Overview", nullptr, tabFlags(0));
                ImVec2 tMin = ImGui::GetItemRectMin(), tMax = ImGui::GetItemRectMax();
                if (open) { renderOverview(); ImGui::EndTabItem(); }
                drawBadge(tMin, tMax, badgeWarn, true);
            }
            {
                bool open = ImGui::BeginTabItem("\xe2\x9a\xa1 Stress", nullptr, tabFlags(1));
                ImVec2 tMin = ImGui::GetItemRectMin(), tMax = ImGui::GetItemRectMax();
                if (open) { renderStressTab(); ImGui::EndTabItem(); }
                drawBadge(tMin, tMax, badgeStress, stressCrit);
            }
            {
                bool open = ImGui::BeginTabItem("\xf0\x9f\x94\xa9 Tensor", nullptr, tabFlags(2));
                if (open) { renderTensorTab(); ImGui::EndTabItem(); }
            }
            {
                bool open = ImGui::BeginTabItem("\xe2\x86\x95 Motion", nullptr, tabFlags(3));
                if (open) { renderMotionTab(); ImGui::EndTabItem(); }
            }
            {
                bool open = ImGui::BeginTabItem("\xe2\x9a\xa1 Energy", nullptr, tabFlags(4));
                ImVec2 tMin = ImGui::GetItemRectMin(), tMax = ImGui::GetItemRectMax();
                if (open) { renderEnergyTab(); ImGui::EndTabItem(); }
                drawBadge(tMin, tMax, badgeEnergy,
                    data_.energy_ratio_min < 0.85 || data_.glstat.energy_ratio_max > 1.15);
            }
            {
                ImGuiTabItemFlags ddFlags = tabFlags(5);
                if (navigateToDeepDive_) ddFlags |= ImGuiTabItemFlags_SetSelected;
                bool open = ImGui::BeginTabItem("\xf0\x9f\x94\x8d Deep Dive", nullptr, ddFlags);
                if (open) { navigateToDeepDive_ = false; renderDeepDiveTab(); ImGui::EndTabItem(); }
            }
            if (!data_.element_quality.empty()) {
                bool open = ImGui::BeginTabItem("\xf0\x9f\x9f\xa5 Quality", nullptr, tabFlags(6));
                ImVec2 tMin = ImGui::GetItemRectMin(), tMax = ImGui::GetItemRectMax();
                if (open) { renderQualityTab(); ImGui::EndTabItem(); }
                drawBadge(tMin, tMax, badgeQuality, badgeQuality > 0);
            } else { tabFlags(6); }
            if (!data_.rcforc.empty() || !data_.sleout.empty()) {
                bool open = ImGui::BeginTabItem("\xf0\x9f\x94\x97 Contact", nullptr, tabFlags(7));
                if (open) { renderContactTab(); ImGui::EndTabItem(); }
            } else { tabFlags(7); }
            {
                bool open = ImGui::BeginTabItem("\xf0\x9f\x9f\xa6 3D View", nullptr, tabFlags(8));
                if (open) { render3DTab(); ImGui::EndTabItem(); }
            }
            {
                bool open = ImGui::BeginTabItem("\xf0\x9f\x8e\xac Renders", nullptr, tabFlags(9));
                if (open) { renderRenderGalleryTab(); ImGui::EndTabItem(); }
            }
            {
                bool open = ImGui::BeginTabItem("\xe2\x84\xb9 SysInfo", nullptr, tabFlags(10));
                if (open) { renderSysInfoTab(); ImGui::EndTabItem(); }
            }

            tabToSelect_ = -1;
            ImGui::EndTabBar();
        }
        ImGui::End();

        ImGui::Render();
        int fbW, fbH;
        glfwGetFramebufferSize(window_, &fbW, &fbH);
        glViewport(0, 0, fbW, fbH);
        glClearColor(0.08f, 0.08f, 0.14f, 1.0f);
        glClear(GL_COLOR_BUFFER_BIT);
        ImGui_ImplOpenGL3_RenderDrawData(ImGui::GetDrawData());
        glfwSwapBuffers(window_);
    }
}

void DeepReportApp::shutdown() {
    ImPlot::DestroyContext();
    ImGui_ImplOpenGL3_Shutdown();
    ImGui_ImplGlfw_Shutdown();
    ImGui::DestroyContext();
    if (window_) glfwDestroyWindow(window_);
    glfwTerminate();
}

// ============================================================
// KPI Summary Bar
// ============================================================
void DeepReportApp::renderKPIBar() {
    ImGui::SetNextWindowSizeConstraints(ImVec2(0, 80), ImVec2(FLT_MAX, 100));
    ImGui::Begin("##Summary", nullptr, ImGuiWindowFlags_NoTitleBar | ImGuiWindowFlags_NoScrollbar | ImGuiWindowFlags_NoScrollWithMouse);

    char buf[64];
    float cardH = ImGui::GetContentRegionAvail().y;

    // Card width computed after we know nCards — forward declaration via pointer.
    float cw = 0.0f;  // set below after nCards is known

    // KPI card: individual styled card with colored accent bar at top
    auto kpi = [&](const char* label, const char* value, const char* unit, ImVec4 col, bool glow = false) {
        ImVec4 bg = glow
            ? ImVec4(col.x*0.35f, col.y*0.35f, col.z*0.35f, 0.45f)
            : ImVec4(0.12f, 0.14f, 0.22f, 0.8f);
        ImGui::PushStyleColor(ImGuiCol_ChildBg, bg);
        ImGui::PushStyleColor(ImGuiCol_Border, glow ? ImVec4(col.x, col.y, col.z, 0.6f) : ImVec4(0.2f,0.2f,0.3f,0.5f));
        ImGui::BeginChild(label, ImVec2(cw, cardH), true);
        // Accent bar at top
        ImDrawList* dl = ImGui::GetWindowDrawList();
        ImVec2 p = ImGui::GetWindowPos();
        ImVec2 sz = ImGui::GetWindowSize();
        ImVec4 bc = col; bc.w = glow ? 0.9f : 0.6f;
        dl->AddRectFilled(p, ImVec2(p.x + sz.x, p.y + 3.0f), ImGui::ColorConvertFloat4ToU32(bc));
        ImGui::SetCursorPosY(ImGui::GetCursorPosY() + 5.0f);
        ImGui::PushStyleColor(ImGuiCol_Text, COL_DIM);
        ImGui::SetWindowFontScale(0.72f);
        ImGui::TextUnformatted(label);
        ImGui::SetWindowFontScale(1.0f);
        ImGui::PopStyleColor();
        ImGui::PushStyleColor(ImGuiCol_Text, col);
        ImGui::SetWindowFontScale(1.35f);
        ImGui::TextUnformatted(value);
        ImGui::SetWindowFontScale(1.0f);
        ImGui::PopStyleColor();
        if (unit && unit[0]) {
            ImGui::PushStyleColor(ImGuiCol_Text, COL_DIM);
            ImGui::SetWindowFontScale(0.78f);
            ImGui::TextUnformatted(unit);
            ImGui::SetWindowFontScale(1.0f);
            ImGui::PopStyleColor();
        }
        ImGui::EndChild();
        ImGui::PopStyleColor(2);
        ImGui::SameLine();
    };

    // Count critical/warn parts
    int nCrit = 0, nWarn = 0;
    for (const auto& [pid, ps] : data_.parts) {
        if (ps.stress_warning == "crit" || ps.strain_warning == "crit") ++nCrit;
        else if (ps.stress_warning == "warn" || ps.strain_warning == "warn") ++nWarn;
    }
    bool hasWarn = (nCrit > 0 || nWarn > 0);

    bool hasSF = (data_.yield_stress > 0 && data_.peak_stress_global > 0);

    // Card width: fill evenly
    int nCards = 5 + (hasSF?1:0) + (hasWarn?1:0);
    float totalSpacing = (float)(nCards - 1) * ImGui::GetStyle().ItemSpacing.x;
    cw = (ImGui::GetContentRegionAvail().x - totalSpacing) / (float)nCards;
    ImGui::PushStyleVar(ImGuiStyleVar_ChildRounding, 4.0f);
    ImGui::PushStyleVar(ImGuiStyleVar_ChildBorderSize, 1.0f);

    // Termination
    if (data_.normal_termination)
        kpi("STATUS", "Normal", "termination", COL_ACCENT);
    else
        kpi("STATUS##k", "ERROR", "termination", COL_RED, true);

    // Peak Stress
    kpi("PEAK STRESS##k", fmtStress(data_.peak_stress_global, buf, sizeof(buf)), "MPa",
        nCrit > 0 ? COL_RED : COL_ACCENT, nCrit > 0);

    // Peak Strain
    snprintf(buf, sizeof(buf), "%.4f", data_.peak_strain_global);
    kpi("PEAK STRAIN##k", buf, "", COL_YELLOW);

    // Peak Disp
    snprintf(buf, sizeof(buf), "%.2f", data_.peak_disp_global);
    kpi("PEAK DISP##k", buf, "mm", COL_PURPLE);

    // Safety Factor
    if (hasSF) {
        double sf = data_.yield_stress / data_.peak_stress_global;
        snprintf(buf, sizeof(buf), "%.3f", sf);
        ImVec4 sfCol = sf >= 1.0 ? COL_ACCENT : sf >= 0.85 ? COL_YELLOW : COL_RED;
        char sfUnit[32]; snprintf(sfUnit, sizeof(sfUnit), "Yield=%.0fMPa", data_.yield_stress);
        kpi("SAFETY FACTOR##k", buf, sfUnit, sfCol, sf < 1.0);
    }

    // Energy Ratio
    snprintf(buf, sizeof(buf), "%.4f", data_.energy_ratio_min);
    ImVec4 erCol = data_.energy_ratio_min > 1.1 ? COL_RED : data_.energy_ratio_min > 1.05 ? COL_YELLOW : COL_ACCENT;
    kpi("ENERGY RATIO##k", buf, "min", erCol, data_.energy_ratio_min > 1.1);

    // Warnings
    if (hasWarn) {
        if (nCrit > 0) {
            snprintf(buf, sizeof(buf), "%d CRIT", nCrit);
            char wUnit[32]; snprintf(wUnit, sizeof(wUnit), "%s", nWarn > 0 ? (std::to_string(nWarn)+" warn").c_str() : "parts");
            kpi("WARNINGS##k", buf, wUnit, COL_RED, true);
        } else {
            snprintf(buf, sizeof(buf), "%d warn", nWarn);
            kpi("WARNINGS##k", buf, "parts", COL_YELLOW);
        }
    }

    ImGui::PopStyleVar(2);
    ImGui::End();
}

void DeepReportApp::renderPartTable() {
    ImGui::Begin("Parts");

    static char filterBuf[128] = "";
    ImGui::SetNextItemWidth(-1);
    ImGui::InputTextWithHint("##filter", "Filter parts...", filterBuf, sizeof(filterBuf));

    // Selection info + buttons
    if (!selectedParts_.empty()) {
        ImGui::TextColored(COL_ACCENT, "%d selected", (int)selectedParts_.size());
        ImGui::SameLine();
        if (ImGui::SmallButton("Clear")) selectedParts_.clear();
    } else {
        ImGui::TextColored(COL_DIM, "Click to select (Ctrl+click multi)");
    }
    if (ImGui::SmallButton("All")) {
        for (const auto& [pid, ps] : data_.parts) selectedParts_.insert(pid);
    }
    ImGui::SameLine();
    if (ImGui::SmallButton("None")) selectedParts_.clear();
    ImGui::Spacing();

    if (ImGui::BeginTable("##PartTable", 9,
            ImGuiTableFlags_Sortable | ImGuiTableFlags_RowBg |
            ImGuiTableFlags_ScrollY | ImGuiTableFlags_Resizable |
            ImGuiTableFlags_SizingStretchProp | ImGuiTableFlags_BordersInnerV)) {

        ImGui::TableSetupScrollFreeze(0, 1);
        ImGui::TableSetupColumn("ID", ImGuiTableColumnFlags_DefaultSort | ImGuiTableColumnFlags_WidthFixed, 30);
        ImGui::TableSetupColumn("Name", ImGuiTableColumnFlags_WidthStretch);
        ImGui::TableSetupColumn("Mat", ImGuiTableColumnFlags_WidthFixed, 50);
        ImGui::TableSetupColumn("Stress", ImGuiTableColumnFlags_DefaultSort | ImGuiTableColumnFlags_WidthFixed, 60);
        ImGui::TableSetupColumn("Strain", ImGuiTableColumnFlags_WidthFixed, 55);
        ImGui::TableSetupColumn("Disp", ImGuiTableColumnFlags_WidthFixed, 45);
        ImGui::TableSetupColumn("SF", ImGuiTableColumnFlags_WidthFixed, 35);
        ImGui::TableSetupColumn("Util%", ImGuiTableColumnFlags_WidthFixed, 42);
        ImGui::TableSetupColumn("Status", ImGuiTableColumnFlags_WidthFixed, 40);
        ImGui::TableHeadersRow();

        // Filter + sort
        std::vector<std::pair<int, const PartSummary*>> sorted;
        std::string filter(filterBuf);
        std::transform(filter.begin(), filter.end(), filter.begin(), ::tolower);

        for (const auto& [pid, ps] : data_.parts) {
            if (!filter.empty()) {
                std::string lower = ps.name + " " + std::to_string(pid);
                std::transform(lower.begin(), lower.end(), lower.begin(), ::tolower);
                if (lower.find(filter) == std::string::npos) continue;
            }
            sorted.push_back({pid, &ps});
        }

        static int sortColS = 0;
        static bool sortAscS = true;

        if (ImGuiTableSortSpecs* specs = ImGui::TableGetSortSpecs()) {
            if (specs->SpecsDirty && specs->SpecsCount > 0) {
                sortColS = specs->Specs[0].ColumnIndex;
                sortAscS = (specs->Specs[0].SortDirection == ImGuiSortDirection_Ascending);
                specs->SpecsDirty = false;
            }
        }

        // Copy to non-static locals so lambda can capture by value without warning
        const int  sc = sortColS;
        const bool sa = sortAscS;
        std::sort(sorted.begin(), sorted.end(), [sc, sa](const auto& a, const auto& b) {
            double va = 0, vb = 0;
            switch (sc) {
                case 0: va = a.first; vb = b.first; break;
                case 1: return sa ? a.second->name < b.second->name : a.second->name > b.second->name;
                case 2: return sa ? a.second->mat_type < b.second->mat_type : a.second->mat_type > b.second->mat_type;
                case 3: va = a.second->peak_stress; vb = b.second->peak_stress; break;
                case 4: va = a.second->peak_strain; vb = b.second->peak_strain; break;
                case 5: va = a.second->peak_disp; vb = b.second->peak_disp; break;
                case 6: va = a.second->safety_factor; vb = b.second->safety_factor; break;
                case 7: va = std::max(a.second->stress_ratio, a.second->strain_ratio);
                        vb = std::max(b.second->stress_ratio, b.second->strain_ratio); break;
                default: return false;
            }
            return sa ? va < vb : va > vb;
        });

        ImGuiListClipper clipper;
        clipper.Begin(static_cast<int>(sorted.size()));
        while (clipper.Step()) {
            for (int i = clipper.DisplayStart; i < clipper.DisplayEnd; ++i) {
                auto& [pid, ps] = sorted[i];
                ImGui::TableNextRow();
                bool isSelected = selectedParts_.count(pid) > 0;

                ImGui::TableSetColumnIndex(0);
                char label[32];
                snprintf(label, sizeof(label), "%d", pid);
                if (ImGui::Selectable(label, isSelected, ImGuiSelectableFlags_SpanAllColumns)) {
                    // Always toggle individual part
                    if (isSelected) selectedParts_.erase(pid);
                    else selectedParts_.insert(pid);
                }
                // Hover → highlight in 3D; double-click → Deep Dive
                if (ImGui::IsItemHovered()) {
                    ImGui::SetMouseCursor(ImGuiMouseCursor_Hand);
                    ImGui::SetTooltip("Hover=3D highlight  |  Double-click \xe2\x86\x92 Deep Dive");
                    highlightPartId_ = pid;
                    if (ImGui::IsMouseDoubleClicked(0)) {
                        deepDivePartId_ = pid;
                        navigateToDeepDive_ = true;
                    }
                }

                ImGui::TableSetColumnIndex(1);
                ImGui::TextUnformatted(ps->name.c_str());

                ImGui::TableSetColumnIndex(2);
                ImGui::TextColored(COL_DIM, "%s", ps->mat_type.empty() ? "--" : ps->mat_type.c_str());

                ImGui::TableSetColumnIndex(3);
                ImGui::TextColored(warningColor(ps->stress_warning), "%.1f", ps->peak_stress);

                ImGui::TableSetColumnIndex(4);
                ImGui::TextColored(warningColor(ps->strain_warning), "%.4f", ps->peak_strain);

                ImGui::TableSetColumnIndex(5);
                ImGui::Text("%.2f", ps->peak_disp);

                ImGui::TableSetColumnIndex(6);
                if (ps->safety_factor > 0) {
                    ImVec4 sfCol = ps->safety_factor >= 1.0 ? COL_ACCENT :
                                   ps->safety_factor >= 0.85 ? COL_YELLOW : COL_RED;
                    ImGui::TextColored(sfCol, "%.2f", ps->safety_factor);
                } else {
                    ImGui::TextColored(COL_DIM, "--");
                }

                ImGui::TableSetColumnIndex(7);
                {
                    double util = std::max(ps->stress_ratio, ps->strain_ratio) * 100.0;
                    if (util > 0) {
                        ImVec4 uc = util > 100 ? COL_RED : util > 85 ? COL_YELLOW : COL_ACCENT;
                        ImGui::TextColored(uc, "%.0f%%", util);
                        if (ImGui::IsItemHovered() && (ps->stress_ratio > 0 || ps->strain_ratio > 0)) {
                            ImGui::SetTooltip("Stress: %.0f%%  Strain: %.0f%%",
                                ps->stress_ratio * 100, ps->strain_ratio * 100);
                        }
                    } else {
                        ImGui::TextColored(COL_DIM, "--");
                    }
                }

                ImGui::TableSetColumnIndex(8);
                {
                    std::string worst = ps->stress_warning;
                    if (ps->strain_warning == "crit" || (ps->strain_warning == "warn" && worst == "ok")) worst = ps->strain_warning;
                    ImVec4 bc = warningColor(worst);
                    ImVec4 bg = bc; bg.w = 0.25f;
                    const char* label = worst == "crit" ? "\xe2\x97\x8f CRIT" : worst == "warn" ? "\xe2\x97\x8f WARN" : "\xe2\x9c\x93 OK";
                    ImGui::PushStyleColor(ImGuiCol_Button,        bg);
                    ImGui::PushStyleColor(ImGuiCol_ButtonHovered, bg);
                    ImGui::PushStyleColor(ImGuiCol_ButtonActive,  bg);
                    ImGui::PushStyleColor(ImGuiCol_Text,          bc);
                    ImGui::SmallButton(label);
                    ImGui::PopStyleColor(4);
                }
            }
        }

        ImGui::EndTable();
    }

    ImGui::End();
}


// ============================================================
// Global part filter helper
// ============================================================
bool DeepReportApp::partPassesFilter(int pid, const std::string& name) const {
    if (globalFilter_[0] == '\0') return true;
    std::string h = "part " + std::to_string(pid) + " " + name;
    for (auto& c : h) c = (char)tolower((unsigned char)c);
    std::string filter(globalFilter_);
    size_t start = 0;
    while (start <= filter.size()) {
        size_t comma = filter.find(',', start);
        if (comma == std::string::npos) comma = filter.size();
        std::string kw = filter.substr(start, comma - start);
        while (!kw.empty() && kw.front() == ' ') kw.erase(kw.begin());
        while (!kw.empty() && kw.back() == ' ') kw.pop_back();
        for (auto& c : kw) c = (char)tolower((unsigned char)c);
        if (!kw.empty() && h.find(kw) == std::string::npos) return false;
        if (comma == filter.size()) break;
        start = comma + 1;
    }
    return true;
}

// ============================================================
// Helper: draw time series plot for selected parts
// ============================================================
void DeepReportApp::drawTimeSeriesPlot(const char* id, const char* yLabel, const std::vector<PartTimeSeries>& series, bool showAvg) {
    ImVec2 sz(ImGui::GetContentRegionAvail().x, std::max(250.0f, ImGui::GetContentRegionAvail().y * 0.45f));
    if (ImPlot::BeginPlot(id, sz, ImPlotFlags_Crosshairs)) {
        ImPlot::SetupAxes("Time", yLabel);

        // Reusable per-call buffers — static avoids heap realloc after first frame.
        // Safe: function is called sequentially (not re-entrant).
        struct VisibleSeries { char label[64]; std::vector<double> t, v; };
        static std::vector<VisibleSeries> visible;
        static std::vector<double> avgBuf;
        visible.clear();

        for (const auto& ts : series) {
            if (ts.data.empty()) continue;
            if (!partPassesFilter(ts.part_id, ts.part_name)) continue;
            if (!selectedParts_.empty() && !selectedParts_.count(ts.part_id)) continue;

            const int n = (int)ts.data.size();
            visible.emplace_back();
            auto& vs = visible.back();
            snprintf(vs.label, sizeof(vs.label), "P%d %s", ts.part_id, ts.part_name.c_str());
            vs.t.resize(n);
            vs.v.resize(n);

            if (showAvg) avgBuf.resize(n);
            for (int i = 0; i < n; ++i) {
                vs.t[i] = ts.data[i].time;
                vs.v[i] = ts.data[i].max_value;
                if (showAvg) avgBuf[i] = ts.data[i].avg_value;
            }

            ImPlot::PlotLine(vs.label, vs.t.data(), vs.v.data(), n);
            if (showAvg) {
                char avgLabel[64];
                snprintf(avgLabel, sizeof(avgLabel), "P%d avg", ts.part_id);
                ImPlot::PlotLine(avgLabel, vs.t.data(), avgBuf.data(), n);
            }
        }

        // Hover tooltip: binary-search nearest time index per series
        if (ImPlot::IsPlotHovered() && !visible.empty()) {
            double hoverT = ImPlot::GetPlotMousePos().x;
            ImGui::BeginTooltip();
            ImGui::TextColored(COL_DIM, "t = %.4f", hoverT);
            ImGui::Separator();
            for (const auto& vs : visible) {
                const int n = (int)vs.t.size();
                if (n == 0) continue;
                int lo = 0, hi = n - 1;
                while (lo < hi) {
                    int mid = (lo + hi) / 2;
                    if (vs.t[mid] < hoverT) lo = mid + 1; else hi = mid;
                }
                if (lo > 0 && std::abs(vs.t[lo-1] - hoverT) < std::abs(vs.t[lo] - hoverT))
                    --lo;
                ImGui::TextColored(COL_ACCENT, "%-28s", vs.label);
                ImGui::SameLine();
                ImGui::Text("%.4f", vs.v[lo]);
            }
            ImGui::EndTooltip();
        }

        ImPlot::EndPlot();
    }
}

// ============================================================
// Warnings box
// ============================================================
void DeepReportApp::renderWarnings() {
    if (data_.warnings.empty()) return;

    // Sort: crit first, then warn, then info
    std::vector<const DeepReportData::Warning*> sorted;
    for (const auto& w : data_.warnings) sorted.push_back(&w);
    std::sort(sorted.begin(), sorted.end(), [](const auto* a, const auto* b) {
        auto rank = [](const std::string& lv) {
            return lv == "crit" ? 0 : lv == "warn" ? 1 : 2;
        };
        return rank(a->level) < rank(b->level);
    });

    // Group headers
    int nCrit = (int)std::count_if(sorted.begin(), sorted.end(), [](const auto* w){ return w->level == "crit"; });
    int nWarn = (int)std::count_if(sorted.begin(), sorted.end(), [](const auto* w){ return w->level == "warn"; });
    int nInfo = (int)std::count_if(sorted.begin(), sorted.end(), [](const auto* w){ return w->level == "info"; });

    std::string curGroup;
    for (const auto* w : sorted) {
        std::string group = w->level;
        if (group != curGroup) {
            curGroup = group;
            ImGui::Spacing();
            const char* icon  = (group == "crit") ? "\xe2\x9a\xa0 " : (group == "warn") ? "\xe2\x9a\xa0 " : "\xe2\x84\xb9 ";
            ImVec4 hcol = (group == "crit") ? COL_RED : (group == "warn") ? COL_YELLOW : COL_BLUE;
            int cnt = (group == "crit") ? nCrit : (group == "warn") ? nWarn : nInfo;
            char hdr[64]; snprintf(hdr, sizeof(hdr), "%s%s  (%d)",
                icon,
                group == "crit" ? "Critical" : group == "warn" ? "Warning" : "Info",
                cnt);
            ImGui::TextColored(hcol, "%s", hdr);
            ImGui::Separator();
        }

        ImVec4 col = (w->level == "crit") ? COL_RED : (w->level == "warn") ? COL_YELLOW : COL_BLUE;
        ImVec4 bg = col; bg.w = (w->level == "crit") ? 0.28f : 0.18f;
        ImGui::PushStyleColor(ImGuiCol_ChildBg, bg);
        float rowH = (w->level == "crit") ? 30.0f : 26.0f;
        ImGui::BeginChild(("##warn" + w->message).c_str(), ImVec2(-1, rowH), false);
        ImGui::SetCursorPosY(ImGui::GetCursorPosY() + (rowH - ImGui::GetTextLineHeight()) * 0.5f - 1.0f);
        const char* prefix = (w->level == "crit") ? " \xe2\x97\x8f  " : (w->level == "warn") ? " \xe2\x97\x8f  " : " \xe2\x84\xb9  ";
        ImGui::TextColored(col, "%s%s", prefix, w->message.c_str());
        ImGui::EndChild();
        ImGui::PopStyleColor();
        ImGui::Spacing();
    }
    ImGui::Spacing();
}

// ============================================================
// Stress Tab: bar rankings + time series overlay + per-part detail
// ============================================================
