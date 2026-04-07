#include "app/SphereReportApp.hpp"

#include <glad/glad.h>
#include <GLFW/glfw3.h>
#include <imgui.h>
#include <imgui_internal.h>
#include <imgui_impl_glfw.h>
#include <imgui_impl_opengl3.h>
#include <implot.h>

#include <iostream>
#include <cmath>
#include <algorithm>
#include <filesystem>

bool SphereReportApp::init(int width, int height) {
    if (!glfwInit()) return false;
    glfwWindowHint(GLFW_CONTEXT_VERSION_MAJOR, 3);
    glfwWindowHint(GLFW_CONTEXT_VERSION_MINOR, 3);
    glfwWindowHint(GLFW_OPENGL_PROFILE, GLFW_OPENGL_CORE_PROFILE);

    window_ = glfwCreateWindow(width, height, "KooViewer — Sphere Report", nullptr, nullptr);
    if (!window_) { glfwTerminate(); return false; }
    glfwMakeContextCurrent(window_);
    glfwMaximizeWindow(window_);
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

    ImGui::StyleColorsDark();
    auto& s = ImGui::GetStyle();
    s.WindowRounding = 8; s.FrameRounding = 6; s.TabRounding = 6;
    s.GrabRounding = 4; s.ScrollbarRounding = 6; s.ChildRounding = 6;
    s.WindowBorderSize = 1; s.ItemSpacing = ImVec2(10,7); s.WindowPadding = ImVec2(14,12);
    s.FramePadding = ImVec2(8,5);
    s.Colors[ImGuiCol_WindowBg]       = {0.067f,0.071f,0.106f,1};
    s.Colors[ImGuiCol_ChildBg]        = {0.082f,0.086f,0.125f,1};
    s.Colors[ImGuiCol_Border]         = {0.18f,0.19f,0.28f,0.6f};
    s.Colors[ImGuiCol_FrameBg]        = {0.11f,0.12f,0.18f,1};
    s.Colors[ImGuiCol_Tab]            = {0.09f,0.10f,0.15f,1};
    s.Colors[ImGuiCol_TabSelected]    = {0.16f,0.22f,0.38f,1};
    s.Colors[ImGuiCol_TableHeaderBg]  = {0.08f,0.14f,0.24f,1};
    s.Colors[ImGuiCol_SliderGrab]     = {0.31f,0.80f,0.64f,0.8f};
    s.Colors[ImGuiCol_CheckMark]      = {0.31f,0.80f,0.64f,1};

    const char* fontPaths[] = {
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Medium.ttc",
        "C:\\Windows\\Fonts\\malgun.ttf", nullptr
    };
    for (int i = 0; fontPaths[i]; ++i) {
        if (std::filesystem::exists(fontPaths[i])) {
            io.Fonts->AddFontFromFileTTF(fontPaths[i], 16.0f, nullptr, io.Fonts->GetGlyphRangesKorean());
            break;
        }
    }

    ImPlot::StyleColorsDark();
    ImGui_ImplGlfw_InitForOpenGL(window_, true);
    ImGui_ImplOpenGL3_Init("#version 330");
    return true;
}

void SphereReportApp::run(const std::string& jsonPath) {
    std::cout << "[Sphere] Loading: " << jsonPath << "\n";
    if (!loadSphereData(jsonPath, data_)) {
        std::cerr << "[Sphere] Failed: " << data_.error << "\n";
    }
    std::cout << "[Sphere] Loaded: " << data_.results.size() << " angles, " << data_.parts.size() << " parts\n";

    if (!data_.parts.empty()) selectedPartId_ = data_.parts.begin()->first;

    glfwSetWindowUserPointer(window_, this);
    glfwSetDropCallback(window_, [](GLFWwindow* w, int count, const char** paths) {
        auto* app = (SphereReportApp*)glfwGetWindowUserPointer(w);
        for (int i = 0; i < count; ++i) {
            std::string p = paths[i];
            if (p.size() > 4 && (p.substr(p.size()-4) == ".stl" || p.substr(p.size()-4) == ".STL")) {
                StlMesh mesh;
                if (mesh.loadFile(p)) {
                    app->stlMesh_ = std::move(mesh);
                    app->stlLoaded_ = true;
                    std::cout << "[Drop] Loaded STL: " << p << "\n";
                }
            } else if (p.size() > 5 && p.substr(p.size()-5) == ".json") {
                if (!app->data_.loaded) {
                    // No primary data yet — load as A
                    SphereData newData;
                    if (loadSphereData(p, newData)) {
                        app->data_ = std::move(newData);
                        if (!app->data_.parts.empty())
                            app->selectedPartId_ = app->data_.parts.begin()->first;
                        std::cout << "[Drop] Loaded A JSON: " << p << "\n";
                    }
                } else if (!app->hasDataB_) {
                    // A loaded — second JSON → B (compare mode)
                    SphereData newData;
                    if (loadSphereData(p, newData)) {
                        app->dataB_ = std::move(newData);
                        app->hasDataB_ = true;
                        std::cout << "[Drop] Loaded B JSON (compare): " << p << "\n";
                    }
                } else {
                    // Both loaded — replace A, clear B
                    SphereData newData;
                    if (loadSphereData(p, newData)) {
                        app->data_ = std::move(newData);
                        app->hasDataB_ = false;
                        if (!app->data_.parts.empty())
                            app->selectedPartId_ = app->data_.parts.begin()->first;
                        std::cout << "[Drop] Replaced A JSON: " << p << "\n";
                    }
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
        static bool firstFrame = true;
        if (firstFrame) {
            firstFrame = false;
            ImGui::DockBuilderRemoveNode(dsId);
            ImGui::DockBuilderAddNode(dsId, ImGuiDockNodeFlags_DockSpace);
            int fw, fh; glfwGetWindowSize(window_, &fw, &fh);
            ImGui::DockBuilderSetNodeSize(dsId, ImVec2((float)fw, (float)fh));

            ImGuiID top, rest;
            ImGui::DockBuilderSplitNode(dsId, ImGuiDir_Up, 0.10f, &top, &rest);
            ImGuiID left, right;
            ImGui::DockBuilderSplitNode(rest, ImGuiDir_Left, 0.40f, &left, &right);

            ImGui::DockBuilderDockWindow("##SphereKPI", top);
            ImGui::DockBuilderDockWindow("Mollweide", left);
            ImGui::DockBuilderDockWindow("Analysis", right);
            ImGui::DockBuilderFinish(dsId);
        }

        if (!ImGui::GetIO().WantCaptureKeyboard) {
            if (ImGui::IsKeyPressed(ImGuiKey_Slash) && ImGui::GetIO().KeyShift)
                showHelp_ = !showHelp_;  // ? = Shift+/
            if (ImGui::IsKeyPressed(ImGuiKey_F11)) {
                if (glfwGetWindowAttrib(window_, GLFW_MAXIMIZED))
                    glfwRestoreWindow(window_);
                else
                    glfwMaximizeWindow(window_);
            }
            if (ImGui::GetIO().KeyCtrl && ImGui::IsKeyPressed(ImGuiKey_E))
                exportHTMLReport();
            if (ImGui::GetIO().KeyCtrl && ImGui::IsKeyPressed(ImGuiKey_S)) {
                int w, h;
                glfwGetFramebufferSize(window_, &w, &h);
                std::vector<unsigned char> pixels(w * h * 3);
                glReadPixels(0, 0, w, h, GL_RGB, GL_UNSIGNED_BYTE, pixels.data());
                std::string path = "screenshot_sphere.ppm";
                FILE* fp = fopen(path.c_str(), "wb");
                if (fp) {
                    fprintf(fp, "P6\n%d %d\n255\n", w, h);
                    for (int y = h - 1; y >= 0; --y)
                        fwrite(pixels.data() + y * w * 3, 1, w * 3, fp);
                    fclose(fp);
                    std::cout << "[Screenshot] Saved: " << path << "\n";
                }
            }
        }

        renderKPIBar();
        if (showHelp_) renderHelpOverlay();

        ImGui::Begin("Mollweide");
        if (ImGui::BeginTabBar("MapTabs")) {
            if (ImGui::BeginTabItem("Mollweide")) { renderMollweide(); ImGui::EndTabItem(); }
            if (ImGui::BeginTabItem("3D Globe"))  { renderGlobe(); ImGui::EndTabItem(); }
            if (hasDataB_) {
                if (ImGui::BeginTabItem("A/B Delta")) { renderCompareABTab(); ImGui::EndTabItem(); }
            }
            ImGui::EndTabBar();
        }
        ImGui::End();

        ImGui::Begin("Analysis");
        if (ImGui::BeginTabBar("SphereTabs")) {
            auto tabFlags = [&](int idx) -> ImGuiTabItemFlags {
                return (analysisTabToSelect_ == idx) ? ImGuiTabItemFlags_SetSelected : 0;
            };
            if (ImGui::BeginTabItem("Angle Table",  nullptr, tabFlags(0))) { renderAngleTable(); ImGui::EndTabItem(); }
            if (ImGui::BeginTabItem("Part Risk",    nullptr, tabFlags(1))) { renderPartRisk(); ImGui::EndTabItem(); }
            if (ImGui::BeginTabItem("Heatmap",      nullptr, tabFlags(2))) { renderHeatmapTab(); ImGui::EndTabItem(); }
            if (ImGui::BeginTabItem("Directional",  nullptr, tabFlags(3))) { renderDirectional(); ImGui::EndTabItem(); }
            if (ImGui::BeginTabItem("Failure",      nullptr, tabFlags(4))) { renderFailureTab(); ImGui::EndTabItem(); }
            if (ImGui::BeginTabItem("Statistics",   nullptr, tabFlags(5))) { renderStatistics(); ImGui::EndTabItem(); }
            if (ImGui::BeginTabItem("Findings",     nullptr, tabFlags(6))) { renderFindings(); ImGui::EndTabItem(); }
            if (ImGui::BeginTabItem("Selected",     nullptr, tabFlags(7))) { renderCompareInfo(); ImGui::EndTabItem(); }
            if (ImGui::BeginTabItem("Angle Detail", nullptr, tabFlags(8))) { renderAngleDetail(); ImGui::EndTabItem(); }
            analysisTabToSelect_ = -1;  // consume after one frame
            ImGui::EndTabBar();
        }
        ImGui::End();

        ImGui::Render();
        int fbW, fbH; glfwGetFramebufferSize(window_, &fbW, &fbH);
        glViewport(0, 0, fbW, fbH);
        glClearColor(0.067f, 0.071f, 0.106f, 1.0f);
        glClear(GL_COLOR_BUFFER_BIT);
        ImGui_ImplOpenGL3_RenderDrawData(ImGui::GetDrawData());
        glfwSwapBuffers(window_);
    }
}

void SphereReportApp::shutdown() {
    ImPlot::DestroyContext();
    ImGui_ImplOpenGL3_Shutdown();
    ImGui_ImplGlfw_Shutdown();
    ImGui::DestroyContext();
    if (window_) glfwDestroyWindow(window_);
    glfwTerminate();
}

// ============================================================
// Category filter helper
// ============================================================
bool SphereReportApp::passesFilter(const std::string& category) const {
    // catFilter_[0]=face, [1]=edge, [2]=corner, [3]=fibonacci
    static const char* cats[] = {"face", "edge", "corner", "fibonacci"};
    for (int i = 0; i < 4; ++i)
        if (category == cats[i]) return catFilter_[i];
    return true;  // unknown categories always pass
}

// ============================================================
// Shared helpers (used by multiple tabs)
// ============================================================
double SphereReportApp::getAngleValue(int ri, int partId, int qty) const {
    auto it = data_.results[ri].parts.find(partId);
    if (it == data_.results[ri].parts.end()) return 0;
    switch (qty) {
        case 0: return it->second.peak_stress;
        case 1: return it->second.peak_strain;
        case 2: return it->second.peak_g;
        case 3: return it->second.peak_disp;
    }
    return 0;
}

void SphereReportApp::mollweideProject(double lonDeg, double latDeg, double& x, double& y) const {
    double lon = lonDeg * M_PI / 180.0;
    double lat = latDeg * M_PI / 180.0;
    double theta = lat;
    for (int i = 0; i < 20; ++i) {
        double f  = 2*theta + std::sin(2*theta) - M_PI*std::sin(lat);
        double fp = 2 + 2*std::cos(2*theta);
        if (std::abs(fp) < 1e-12) break;
        double dt = f / fp;
        if (std::abs(dt) > 0.3) dt = dt > 0 ? 0.3 : -0.3;
        theta -= dt;
        if (std::abs(dt) < 1e-7) break;
    }
    x = (2.0*std::sqrt(2.0)/M_PI) * lon * std::cos(theta);
    y = std::sqrt(2.0) * std::sin(theta);
}

ImU32 SphereReportApp::valueToColor(double norm) const {
    norm = std::max(0.0, std::min(1.0, norm));
    float r, g, b;
    if      (norm < 0.25) { r = 0;                       g = (float)(norm/0.25);        b = 1; }
    else if (norm < 0.5)  { r = 0;                       g = 1;                         b = (float)(1-(norm-0.25)/0.25); }
    else if (norm < 0.75) { r = (float)((norm-0.5)/0.25); g = 1;                        b = 0; }
    else                  { r = 1;                        g = (float)(1-(norm-0.75)/0.25); b = 0; }
    return IM_COL32((int)(r*255), (int)(g*255), (int)(b*255), 255);
}

// ============================================================
// KPI Bar
// ============================================================
void SphereReportApp::renderKPIBar() {
    ImGui::SetNextWindowSizeConstraints(ImVec2(0, 80), ImVec2(FLT_MAX, 110));
    ImGui::Begin("##SphereKPI", nullptr, ImGuiWindowFlags_NoTitleBar | ImGuiWindowFlags_NoScrollbar);

    char buf[64];
    auto kpi = [&](const char* label, const char* value, const char* unit, ImVec4 col) {
        ImGui::BeginGroup();
        ImGui::SmallButton(label);
        ImGui::PushStyleColor(ImGuiCol_Text, col);
        ImGui::SetWindowFontScale(1.4f);
        ImGui::TextUnformatted(value);
        ImGui::SetWindowFontScale(1.0f);
        ImGui::PopStyleColor();
        ImGui::PushStyleColor(ImGuiCol_Text, COL_DIM);
        ImGui::TextUnformatted(unit);
        ImGui::PopStyleColor();
        ImGui::EndGroup();
    };

    // Top-right controls: lang toggle + compare status + help hint
    float rightX = ImGui::GetWindowWidth() - 180;
    ImGui::SameLine(rightX);
    if (hasDataB_) {
        ImGui::PushStyleColor(ImGuiCol_Text, COL_BLUE);
        ImGui::Text("B: %s", dataB_.project_name.empty() ? "loaded" : dataB_.project_name.c_str());
        ImGui::PopStyleColor();
        ImGui::SameLine();
        if (ImGui::SmallButton("X##clearB")) hasDataB_ = false;
        ImGui::SameLine();
    } else {
        ImGui::TextColored(COL_DIM, "Drop 2nd JSON=Compare");
        ImGui::SameLine();
    }
    if (ImGui::SmallButton(langKo_ ? "EN" : "KO")) langKo_ = !langKo_;
    ImGui::SameLine();
    ImGui::TextColored(COL_DIM, "[?]");

    ImGui::Columns(6, nullptr, false);
    snprintf(buf, sizeof(buf), "%d / %d", data_.successful_runs, data_.total_runs);
    kpi("CASES", buf, data_.doe_strategy.c_str(), COL_ACCENT);
    ImGui::NextColumn();
    snprintf(buf, sizeof(buf), "%.1f", data_.worst_stress);
    kpi("WORST STRESS", buf, "MPa", COL_RED);
    ImGui::NextColumn();
    snprintf(buf, sizeof(buf), "%.1f deg", data_.angular_spacing);
    kpi("SPACING", buf, "", COL_BLUE);
    ImGui::NextColumn();
    snprintf(buf, sizeof(buf), "%.0f%%", data_.sphere_coverage * 100);
    kpi("COVERAGE", buf, "", COL_PURPLE);
    ImGui::NextColumn();
    if (data_.worst_stress_angle >= 0)
        snprintf(buf, sizeof(buf), "%s", data_.results[data_.worst_stress_angle].angle.name.c_str());
    else
        snprintf(buf, sizeof(buf), "--");
    kpi("WORST ANGLE", buf, "", COL_YELLOW);
    ImGui::NextColumn();
    snprintf(buf, sizeof(buf), "%d", (int)data_.parts.size());
    kpi("PARTS", buf, "", COL_DIM);
    ImGui::Columns(1);

    // Category filter row
    ImGui::Spacing();
    ImGui::TextColored(COL_DIM, "Filter:");
    ImGui::SameLine();
    static const char* catLabels[] = {"Face", "Edge", "Corner", "Fibonacci"};
    static ImVec4 catCols[] = {
        {0.48f,0.80f,0.64f,1}, {0.61f,0.48f,0.80f,1},
        {0.80f,0.61f,0.30f,1}, {0.35f,0.65f,0.95f,1}
    };
    for (int i = 0; i < 4; ++i) {
        ImGui::PushStyleColor(ImGuiCol_Text,
            catFilter_[i] ? catCols[i] : ImVec4(0.35f,0.35f,0.40f,1));
        if (ImGui::Checkbox(catLabels[i], &catFilter_[i])) {}
        ImGui::PopStyleColor();
        ImGui::SameLine();
    }

    ImGui::End();
}
