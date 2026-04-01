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

// Colors
static const ImVec4 COL_ACCENT = {0.31f, 0.80f, 0.64f, 1.0f};
static const ImVec4 COL_RED    = {0.91f, 0.27f, 0.38f, 1.0f};
static const ImVec4 COL_YELLOW = {0.96f, 0.65f, 0.14f, 1.0f};
static const ImVec4 COL_BLUE   = {0.31f, 0.56f, 1.00f, 1.0f};
static const ImVec4 COL_PURPLE = {0.48f, 0.41f, 0.93f, 1.0f};
static const ImVec4 COL_DIM    = {0.55f, 0.55f, 0.62f, 1.0f};

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

    // Same polished theme as Deep mode
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

    // Font
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

    // Default to first part
    if (!data_.parts.empty()) selectedPartId_ = data_.parts.begin()->first;

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

        // Keyboard shortcuts
        if (!ImGui::GetIO().WantCaptureKeyboard) {
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

        // Left: Mollweide + Globe
        ImGui::Begin("Mollweide");
        if (ImGui::BeginTabBar("MapTabs")) {
            if (ImGui::BeginTabItem("Mollweide")) { renderMollweide(); ImGui::EndTabItem(); }
            if (ImGui::BeginTabItem("3D Globe"))  { renderGlobe(); ImGui::EndTabItem(); }
            ImGui::EndTabBar();
        }
        ImGui::End();

        // Right: tabbed analysis
        ImGui::Begin("Analysis");
        if (ImGui::BeginTabBar("SphereTabs")) {
            if (ImGui::BeginTabItem("Angle Table"))  { renderAngleTable(); ImGui::EndTabItem(); }
            if (ImGui::BeginTabItem("Part Risk"))    { renderPartRisk(); ImGui::EndTabItem(); }
            if (ImGui::BeginTabItem("Heatmap"))      { renderHeatmapTab(); ImGui::EndTabItem(); }
            if (ImGui::BeginTabItem("Directional"))  { renderDirectional(); ImGui::EndTabItem(); }
            if (ImGui::BeginTabItem("Failure"))      { renderFailureTab(); ImGui::EndTabItem(); }
            if (ImGui::BeginTabItem("Statistics"))   { renderStatistics(); ImGui::EndTabItem(); }
            if (ImGui::BeginTabItem("Findings"))     { renderFindings(); ImGui::EndTabItem(); }
            if (ImGui::BeginTabItem("Selected"))     { renderCompareInfo(); ImGui::EndTabItem(); }
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
// Helpers
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
        double f = 2*theta + std::sin(2*theta) - M_PI*std::sin(lat);
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
    if (norm < 0.25f) { r = 0; g = norm/0.25f; b = 1; }
    else if (norm < 0.5f) { r = 0; g = 1; b = 1-(norm-0.25f)/0.25f; }
    else if (norm < 0.75f) { r = (norm-0.5f)/0.25f; g = 1; b = 0; }
    else { r = 1; g = 1-(norm-0.75f)/0.25f; b = 0; }
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
    else snprintf(buf, sizeof(buf), "--");
    kpi("WORST ANGLE", buf, "", COL_YELLOW);
    ImGui::NextColumn();
    snprintf(buf, sizeof(buf), "%d", (int)data_.parts.size());
    kpi("PARTS", buf, "", COL_DIM);
    ImGui::Columns(1);

    ImGui::End();
}

// ============================================================
// Mollweide Projection Map
// ============================================================
void SphereReportApp::renderMollweide() {
    // Controls
    const char* qtyNames[] = {"Stress (MPa)", "Strain", "G-Force", "Displacement (mm)"};
    ImGui::SetNextItemWidth(200);
    ImGui::Combo("Quantity", &quantity_, qtyNames, 4);
    ImGui::SameLine();
    ImGui::Text("Part:");
    ImGui::SameLine();
    ImGui::SetNextItemWidth(200);
    if (ImGui::BeginCombo("##partSel",
        (data_.parts.count(selectedPartId_) ?
         ("Part " + std::to_string(selectedPartId_) + " " + data_.parts[selectedPartId_].name) :
         "Select").c_str())) {
        for (auto& [pid, pi] : data_.parts) {
            char label[128];
            snprintf(label, sizeof(label), "Part %d — %s", pid, pi.name.c_str());
            if (ImGui::Selectable(label, selectedPartId_ == pid))
                selectedPartId_ = pid;
        }
        ImGui::EndCombo();
    }

    ImGui::SameLine();
    if (ImGui::Checkbox("Swap R/P", &swapRP_)) {
        for (auto& r : data_.results) {
            double roll = swapRP_ ? r.angle.pitch : r.angle.roll;
            double pitch = swapRP_ ? r.angle.roll : r.angle.pitch;
            eulerToLonLat(roll, pitch, r.angle.yaw, r.angle.name, r.angle.lon, r.angle.lat);
        }
    }
    ImGui::SameLine();
    ImGui::Checkbox("Contour", &contourMode_);
    ImGui::SameLine();
    ImGui::Checkbox("Manual Scale", &manualScale_);
    if (manualScale_) {
        ImGui::SameLine();
        ImGui::SetNextItemWidth(80);
        ImGui::InputFloat("Min", &scaleMin_, 0, 0, "%.0f");
        ImGui::SameLine();
        ImGui::SetNextItemWidth(80);
        ImGui::InputFloat("Max", &scaleMax_, 0, 0, "%.0f");
    }
    ImGui::TextColored(COL_DIM, "Click to select/deselect angles. Selected: %d", (int)selectedAngles_.size());
    ImGui::Spacing();

    // Draw Mollweide map
    ImVec2 avail = ImGui::GetContentRegionAvail();
    float mapW = avail.x;
    float mapH = std::max(200.0f, avail.y - 10);
    ImVec2 mapPos = ImGui::GetCursorScreenPos();
    ImGui::InvisibleButton("##mollMap", ImVec2(mapW, mapH));
    bool mapHovered = ImGui::IsItemHovered();

    ImDrawList* dl = ImGui::GetWindowDrawList();
    float cx = mapPos.x + mapW * 0.5f;
    float cy = mapPos.y + mapH * 0.5f;
    float scale = std::min(mapW / (4.0f * std::sqrt(2.0f)), mapH / (2.0f * std::sqrt(2.0f))) * 0.9f;
    float rx = 2.0f * std::sqrt(2.0f) * scale;
    float ry = std::sqrt(2.0f) * scale;

    // Background
    dl->AddRectFilled(mapPos, ImVec2(mapPos.x + mapW, mapPos.y + mapH), IM_COL32(15, 17, 26, 255), 6);

    // Ellipse outline
    dl->AddEllipse(ImVec2(cx, cy), ImVec2(rx, ry), IM_COL32(120,125,160,200), 0, 64, 1.5f);

    // Grid lines
    for (int lat = -60; lat <= 60; lat += 30) {
        for (int lon = -175; lon <= 175; lon += 5) {
            double x1, y1, x2, y2;
            mollweideProject(lon, lat, x1, y1);
            mollweideProject(lon + 5, lat, x2, y2);
            dl->AddLine(ImVec2(cx + x1*scale, cy - y1*scale),
                       ImVec2(cx + x2*scale, cy - y2*scale), IM_COL32(50, 55, 75, 80), 0.5f);
        }
    }
    for (int lon = -150; lon <= 150; lon += 30) {
        for (int lat = -88; lat <= 88; lat += 2) {
            double x1, y1, x2, y2;
            mollweideProject(lon, lat, x1, y1);
            mollweideProject(lon, lat + 2, x2, y2);
            dl->AddLine(ImVec2(cx + x1*scale, cy - y1*scale),
                       ImVec2(cx + x2*scale, cy - y2*scale), IM_COL32(50, 55, 75, 80), 0.5f);
        }
    }

    // Compute value range
    double vmin = 1e30, vmax = -1e30;
    for (int ri = 0; ri < (int)data_.results.size(); ++ri) {
        double v = getAngleValue(ri, selectedPartId_, quantity_);
        vmin = std::min(vmin, v); vmax = std::max(vmax, v);
    }
    if (manualScale_ && scaleMax_ > scaleMin_) { vmin = scaleMin_; vmax = scaleMax_; }
    double vrange = std::max(vmax - vmin, 1e-10);

    // IDW Contour mode
    if (contourMode_) {
        int gridStep = data_.results.size() > 200 ? 6 : 4;
        for (int py = 0; py < (int)mapH; py += gridStep) {
            for (int px = 0; px < (int)mapW; px += gridStep) {
                float sx = mapPos.x + px, sy = mapPos.y + py;
                double qx = ((double)px - mapW*0.5) / scale;
                double qy = (mapH*0.5 - (double)py) / scale;
                // Check inside ellipse
                double ex = qx / (2.0*std::sqrt(2.0)), ey = qy / std::sqrt(2.0);
                if (ex*ex + ey*ey > 1.0) continue;

                // IDW interpolation (spherical distance)
                double wsum = 0, vsum = 0;
                for (int ri = 0; ri < (int)data_.results.size(); ++ri) {
                    double mx, my;
                    mollweideProject(data_.results[ri].angle.lon, data_.results[ri].angle.lat, mx, my);
                    double dx = qx - mx, dy = qy - my;
                    double dist = std::sqrt(dx*dx + dy*dy);
                    if (dist < 0.05) { vsum = getAngleValue(ri, selectedPartId_, quantity_); wsum = 1; break; }
                    double w = 1.0 / (dist * dist * dist);
                    wsum += w;
                    vsum += w * getAngleValue(ri, selectedPartId_, quantity_);
                }
                if (wsum > 0) {
                    double val = vsum / wsum;
                    double norm = (val - vmin) / vrange;
                    ImU32 col = valueToColor(norm);
                    dl->AddRectFilled(ImVec2(sx, sy), ImVec2(sx + gridStep, sy + gridStep), col);
                }
            }
        }
        // Re-draw ellipse outline on top
        dl->AddEllipse(ImVec2(cx, cy), ImVec2(rx, ry), IM_COL32(120,125,160,200), 0, 64, 1.5f);
    }

    // Find hovered point
    hoveredAngle_ = -1;
    ImVec2 mousePos = ImGui::GetMousePos();
    double minDist = 1e30;

    int nPts = (int)data_.results.size();
    float baseR = nPts > 500 ? 3 : nPts > 200 ? 4 : nPts > 50 ? 6 : 8;

    for (int ri = 0; ri < nPts; ++ri) {
        auto& r = data_.results[ri];
        double mx, my;
        mollweideProject(r.angle.lon, r.angle.lat, mx, my);
        float sx = cx + (float)mx * scale;
        float sy = cy - (float)my * scale;

        double v = getAngleValue(ri, selectedPartId_, quantity_);
        double norm = (v - vmin) / vrange;
        ImU32 col = valueToColor(norm);

        bool isSelected = selectedAngles_.count(ri);
        float radius = baseR + (float)norm * baseR * 0.5f;
        if (isSelected) radius += 2;

        dl->AddCircleFilled(ImVec2(sx, sy), radius, col);
        if (isSelected)
            dl->AddCircle(ImVec2(sx, sy), radius + 2, IM_COL32(255,255,255,200), 0, 2);

        // Hit test
        float dx = mousePos.x - sx, dy = mousePos.y - sy;
        float dist = dx*dx + dy*dy;
        if (dist < minDist && dist < 400) { minDist = dist; hoveredAngle_ = ri; }
    }

    // Click to select
    if (mapHovered && ImGui::IsMouseClicked(0) && hoveredAngle_ >= 0) {
        if (selectedAngles_.count(hoveredAngle_))
            selectedAngles_.erase(hoveredAngle_);
        else
            selectedAngles_.insert(hoveredAngle_);
    }

    // Tooltip
    if (hoveredAngle_ >= 0) {
        auto& r = data_.results[hoveredAngle_];
        double v = getAngleValue(hoveredAngle_, selectedPartId_, quantity_);
        ImGui::BeginTooltip();
        ImGui::Text("%s", r.angle.name.c_str());
        ImGui::Text("Roll: %.1f  Pitch: %.1f", r.angle.roll, r.angle.pitch);
        ImGui::Text("Value: %.2f", v);
        ImGui::EndTooltip();

        // Highlight on map
        double mx, my;
        mollweideProject(r.angle.lon, r.angle.lat, mx, my);
        float sx = cx + (float)mx * scale, sy = cy - (float)my * scale;
        dl->AddCircle(ImVec2(sx, sy), baseR + 6, IM_COL32(255,255,255,255), 0, 2.5f);
    }

    // Orientation cube (bottom-left corner)
    if (hoveredAngle_ >= 0) {
        drawOrientationCube(dl, ImVec2(mapPos.x + 10, mapPos.y + mapH - 90),
                            80, data_.results[hoveredAngle_].angle.roll,
                            data_.results[hoveredAngle_].angle.pitch);
    }

    // Colorbar
    float cbX = mapPos.x + mapW - 30;
    float cbY = mapPos.y + 20;
    float cbH = mapH - 40;
    for (int i = 0; i < (int)cbH; ++i) {
        float t = 1.0f - (float)i / cbH;
        dl->AddLine(ImVec2(cbX, cbY + i), ImVec2(cbX + 16, cbY + i), valueToColor(t));
    }
    char vminS[32], vmaxS[32];
    snprintf(vmaxS, sizeof(vmaxS), "%.1f", vmax);
    snprintf(vminS, sizeof(vminS), "%.1f", vmin);
    dl->AddText(ImVec2(cbX - 40, cbY - 2), IM_COL32(200,200,210,255), vmaxS);
    dl->AddText(ImVec2(cbX - 40, cbY + cbH - 10), IM_COL32(200,200,210,255), vminS);
}

// ============================================================
// Angle Table
// ============================================================
void SphereReportApp::renderAngleTable() {
    ImGui::TextColored(COL_DIM,
        "Sorted by selected quantity. Click row to select/deselect on Mollweide map.");
    ImGui::Spacing();

    const char* qtyNames[] = {"Stress", "Strain", "G-Force", "Disp"};

    if (ImGui::BeginTable("##AngleTable", 7,
            ImGuiTableFlags_Sortable | ImGuiTableFlags_RowBg |
            ImGuiTableFlags_ScrollY | ImGuiTableFlags_SizingStretchProp |
            ImGuiTableFlags_BordersInnerV)) {

        ImGui::TableSetupScrollFreeze(0, 1);
        ImGui::TableSetupColumn("#", ImGuiTableColumnFlags_WidthFixed, 30);
        ImGui::TableSetupColumn("Direction", ImGuiTableColumnFlags_WidthStretch);
        ImGui::TableSetupColumn("Category", ImGuiTableColumnFlags_WidthFixed, 70);
        ImGui::TableSetupColumn("Roll", ImGuiTableColumnFlags_WidthFixed, 55);
        ImGui::TableSetupColumn("Pitch", ImGuiTableColumnFlags_WidthFixed, 55);
        ImGui::TableSetupColumn(qtyNames[quantity_], ImGuiTableColumnFlags_DefaultSort | ImGuiTableColumnFlags_WidthFixed, 80);
        ImGui::TableSetupColumn("Sel", ImGuiTableColumnFlags_WidthFixed, 25);
        ImGui::TableHeadersRow();

        // Sort by value descending
        std::vector<std::pair<int, double>> sorted;
        for (int ri = 0; ri < (int)data_.results.size(); ++ri) {
            sorted.push_back({ri, getAngleValue(ri, selectedPartId_, quantity_)});
        }
        std::sort(sorted.begin(), sorted.end(), [](const auto& a, const auto& b) { return a.second > b.second; });

        ImGuiListClipper clipper;
        clipper.Begin((int)sorted.size());
        while (clipper.Step()) {
            for (int i = clipper.DisplayStart; i < clipper.DisplayEnd; ++i) {
                int ri = sorted[i].first;
                auto& r = data_.results[ri];
                bool isSelected = selectedAngles_.count(ri);

                ImGui::TableNextRow();
                ImGui::TableSetColumnIndex(0);
                char label[16]; snprintf(label, sizeof(label), "%d", i + 1);
                if (ImGui::Selectable(label, isSelected, ImGuiSelectableFlags_SpanAllColumns)) {
                    if (isSelected) selectedAngles_.erase(ri);
                    else selectedAngles_.insert(ri);
                }
                ImGui::TableSetColumnIndex(1);
                ImGui::TextColored(COL_ACCENT, "%s", r.angle.name.c_str());
                ImGui::TableSetColumnIndex(2);
                ImGui::TextColored(COL_DIM, "%s", r.angle.category.c_str());
                ImGui::TableSetColumnIndex(3);
                ImGui::Text("%.1f", r.angle.roll);
                ImGui::TableSetColumnIndex(4);
                ImGui::Text("%.1f", r.angle.pitch);
                ImGui::TableSetColumnIndex(5);
                ImGui::Text("%.2f", sorted[i].second);
                ImGui::TableSetColumnIndex(6);
                ImGui::TextColored(isSelected ? COL_ACCENT : COL_DIM, isSelected ? "V" : "");
            }
        }
        ImGui::EndTable();
    }
}

// ============================================================
// Part Risk Matrix
// ============================================================
void SphereReportApp::renderPartRisk() {
    ImGui::TextColored(COL_DIM,
        "Part x Angle matrix. Color intensity = relative value. Red = high risk.");
    ImGui::Spacing();

    if (data_.results.empty() || data_.parts.empty()) return;

    // Top 20 angles by worst stress
    std::vector<int> topAngles;
    {
        std::vector<std::pair<int, double>> sorted;
        for (int ri = 0; ri < (int)data_.results.size(); ++ri) {
            double maxV = 0;
            for (auto& [pid, pd] : data_.results[ri].parts)
                maxV = std::max(maxV, pd.peak_stress);
            sorted.push_back({ri, maxV});
        }
        std::sort(sorted.begin(), sorted.end(), [](auto& a, auto& b) { return a.second > b.second; });
        for (int i = 0; i < std::min(20, (int)sorted.size()); ++i)
            topAngles.push_back(sorted[i].first);
    }

    int ncols = 2 + (int)topAngles.size();
    if (ImGui::BeginTable("##PartRisk", ncols,
            ImGuiTableFlags_ScrollX | ImGuiTableFlags_ScrollY |
            ImGuiTableFlags_RowBg | ImGuiTableFlags_BordersInnerV |
            ImGuiTableFlags_SizingFixedFit)) {

        ImGui::TableSetupScrollFreeze(2, 1);
        ImGui::TableSetupColumn("Part", 0, 40);
        ImGui::TableSetupColumn("Name", 0, 100);
        for (int ai : topAngles) {
            ImGui::TableSetupColumn(data_.results[ai].angle.name.c_str(), 0, 55);
        }
        ImGui::TableHeadersRow();

        // Find global max for color normalization
        double globalMax = 1;
        for (auto& [pid, pi] : data_.parts) {
            for (int ai : topAngles) {
                double v = getAngleValue(ai, pid, quantity_);
                globalMax = std::max(globalMax, v);
            }
        }

        for (auto& [pid, pi] : data_.parts) {
            ImGui::TableNextRow();
            ImGui::TableSetColumnIndex(0);
            ImGui::Text("%d", pid);
            ImGui::TableSetColumnIndex(1);
            ImGui::TextUnformatted(pi.name.c_str());

            for (int ci = 0; ci < (int)topAngles.size(); ++ci) {
                ImGui::TableSetColumnIndex(ci + 2);
                double v = getAngleValue(topAngles[ci], pid, quantity_);
                double norm = v / globalMax;
                ImU32 bgCol = valueToColor(norm);
                // Dim the color for background
                int r = (bgCol >> 0) & 0xFF, g = (bgCol >> 8) & 0xFF, b = (bgCol >> 16) & 0xFF;
                ImGui::TableSetBgColor(ImGuiTableBgTarget_CellBg, IM_COL32(r/3, g/3, b/3, 180));
                ImGui::Text("%.0f", v);
            }
        }

        ImGui::EndTable();
    }
}

// ============================================================
// Selected Angles Comparison
// ============================================================
void SphereReportApp::renderCompareInfo() {
    if (selectedAngles_.empty()) {
        ImGui::TextColored(COL_DIM, "Click angles on Mollweide map or table to compare");
        return;
    }

    ImGui::TextColored(COL_ACCENT, "Selected Angles (%d):", (int)selectedAngles_.size());

    // Tags
    std::vector<int> toRemove;
    for (int ri : selectedAngles_) {
        ImGui::SameLine();
        char tag[64];
        snprintf(tag, sizeof(tag), "%s X##%d", data_.results[ri].angle.name.c_str(), ri);
        if (ImGui::SmallButton(tag)) toRemove.push_back(ri);
    }
    for (int ri : toRemove) selectedAngles_.erase(ri);
    ImGui::Spacing();

    // Comparison table
    if (ImGui::BeginTable("##Compare", 6,
            ImGuiTableFlags_RowBg | ImGuiTableFlags_BordersInnerV |
            ImGuiTableFlags_SizingStretchProp)) {
        ImGui::TableSetupColumn("Direction");
        ImGui::TableSetupColumn("Category");
        ImGui::TableSetupColumn("Peak Stress");
        ImGui::TableSetupColumn("Peak Strain");
        ImGui::TableSetupColumn("Peak G");
        ImGui::TableSetupColumn("Peak Disp");
        ImGui::TableHeadersRow();

        for (int ri : selectedAngles_) {
            auto& r = data_.results[ri];
            auto it = r.parts.find(selectedPartId_);
            if (it == r.parts.end()) continue;
            auto& pd = it->second;

            ImGui::TableNextRow();
            ImGui::TableSetColumnIndex(0);
            ImGui::TextColored(COL_ACCENT, "%s", r.angle.name.c_str());
            ImGui::TableSetColumnIndex(1); ImGui::Text("%s", r.angle.category.c_str());
            ImGui::TableSetColumnIndex(2); ImGui::Text("%.1f", pd.peak_stress);
            ImGui::TableSetColumnIndex(3); ImGui::Text("%.4f", pd.peak_strain);
            ImGui::TableSetColumnIndex(4); ImGui::Text("%.1f", pd.peak_g);
            ImGui::TableSetColumnIndex(5); ImGui::Text("%.2f", pd.peak_disp);
        }
        ImGui::EndTable();
    }

    // Time history overlay chart for selected angles
    ImGui::Spacing();
    ImGui::TextColored(COL_ACCENT, "  Time History Overlay");
    ImGui::Separator();

    bool hasTS = false;
    for (int ri : selectedAngles_) {
        auto it = data_.results[ri].parts.find(selectedPartId_);
        if (it != data_.results[ri].parts.end() && !it->second.stress_ts.t.empty()) {
            hasTS = true; break;
        }
    }

    if (!hasTS) {
        ImGui::TextColored(COL_DIM, "No time series data in report.json. Regenerate with: koo_sphere_report --format json");
    } else {
        const char* tsQtyNames[] = {"Stress (MPa)", "Strain", "G-Force (MG)", "Displacement (mm)"};
        static int tsQty = 0;
        ImGui::RadioButton("Stress##ts", &tsQty, 0); ImGui::SameLine();
        ImGui::RadioButton("Strain##ts", &tsQty, 1); ImGui::SameLine();
        ImGui::RadioButton("G-Force##ts", &tsQty, 2); ImGui::SameLine();
        ImGui::RadioButton("Disp##ts", &tsQty, 3);

        ImVec2 sz(ImGui::GetContentRegionAvail().x, std::max(200.0f, ImGui::GetContentRegionAvail().y - 10));
        if (ImPlot::BeginPlot("##TimeHistOverlay", sz)) {
            ImPlot::SetupAxes("Time", tsQtyNames[tsQty]);

            for (int ri : selectedAngles_) {
                auto it = data_.results[ri].parts.find(selectedPartId_);
                if (it == data_.results[ri].parts.end()) continue;
                auto& pd = it->second;

                const TimeSeries* ts = nullptr;
                switch (tsQty) {
                    case 0: ts = &pd.stress_ts; break;
                    case 1: ts = &pd.strain_ts; break;
                    case 2: ts = &pd.g_ts; break;
                    case 3: ts = &pd.disp_ts; break;
                }
                if (!ts || ts->t.empty() || ts->values.empty()) continue;

                int n = std::min((int)ts->t.size(), (int)ts->values.size());
                char label[64];
                snprintf(label, sizeof(label), "%s", data_.results[ri].angle.name.c_str());
                ImPlot::PlotLine(label, ts->t.data(), ts->values.data(), n);
            }

            ImPlot::EndPlot();
        }
    }
}

// ============================================================
// 3D Globe (ImDrawList wireframe sphere with data points)
// ============================================================
void SphereReportApp::projectGlobe(double lonDeg, double latDeg, float vLon, float vLat,
                                     float R, float& sx, float& sy, float& sz) const {
    double lon = lonDeg * M_PI / 180.0, lat = latDeg * M_PI / 180.0;
    double x = std::cos(lat) * std::sin(lon);
    double y = std::sin(lat);
    double z = std::cos(lat) * std::cos(lon);

    // Rotate by view angles
    double vl = vLon * M_PI / 180.0, va = vLat * M_PI / 180.0;
    double x1 = x * std::cos(vl) - z * std::sin(vl);
    double z1 = x * std::sin(vl) + z * std::cos(vl);
    double y1 = y * std::cos(va) - z1 * std::sin(va);
    double z2 = y * std::sin(va) + z1 * std::cos(va);

    sx = (float)(x1 * R);
    sy = (float)(y1 * R);
    sz = (float)z2;
}

void SphereReportApp::renderGlobe() {
    ImGui::Checkbox("Auto Rotate", &globeAutoRotate_);
    if (globeAutoRotate_) {
        globeYaw_ += ImGui::GetIO().DeltaTime * 20.0f;
        if (globeYaw_ > 360) globeYaw_ -= 360;
    }

    ImVec2 avail = ImGui::GetContentRegionAvail();
    float sz = std::min(avail.x, avail.y) - 20;
    if (sz < 100) sz = 200;
    ImVec2 pos = ImGui::GetCursorScreenPos();
    ImGui::InvisibleButton("##globe", ImVec2(sz, sz));
    bool hovered = ImGui::IsItemHovered();

    if (hovered) {
        if (ImGui::IsMouseDragging(ImGuiMouseButton_Left)) {
            ImVec2 d = ImGui::GetIO().MouseDelta;
            globeYaw_ += d.x * 0.5f;
            globePitch_ = std::clamp(globePitch_ - d.y * 0.005f, -1.4f, 1.4f);
            globeAutoRotate_ = false;
        }
    }

    ImDrawList* dl = ImGui::GetWindowDrawList();
    float cx = pos.x + sz * 0.5f, cy = pos.y + sz * 0.5f;
    float R = sz * 0.42f;
    float vLon = globeYaw_, vLat = globePitch_ * 180.0f / M_PI;

    // Background
    dl->AddRectFilled(pos, ImVec2(pos.x + sz, pos.y + sz), IM_COL32(15, 17, 26, 255), 6);

    // Grid lines (front hemisphere only)
    for (int lon = -180; lon <= 150; lon += 30) {
        for (int lat = -87; lat <= 87; lat += 3) {
            float sx1, sy1, sz1, sx2, sy2, sz2;
            projectGlobe(lon, lat, vLon, vLat, R, sx1, sy1, sz1);
            projectGlobe(lon, lat+3, vLon, vLat, R, sx2, sy2, sz2);
            if (sz1 > 0 && sz2 > 0)
                dl->AddLine(ImVec2(cx+sx1, cy-sy1), ImVec2(cx+sx2, cy-sy2), IM_COL32(60,65,80,60), 0.5f);
        }
    }
    for (int lat = -60; lat <= 60; lat += 30) {
        for (int lon = -180; lon <= 177; lon += 3) {
            float sx1, sy1, sz1, sx2, sy2, sz2;
            projectGlobe(lon, lat, vLon, vLat, R, sx1, sy1, sz1);
            projectGlobe(lon+3, lat, vLon, vLat, R, sx2, sy2, sz2);
            if (sz1 > 0 && sz2 > 0)
                dl->AddLine(ImVec2(cx+sx1, cy-sy1), ImVec2(cx+sx2, cy-sy2), IM_COL32(60,65,80,60), 0.5f);
        }
    }

    // Outline
    dl->AddCircle(ImVec2(cx, cy), R, IM_COL32(120,125,160,180), 64, 1.5f);

    // Data points (sorted back-to-front)
    struct ProjPt { float sx, sy, sz; int ri; ImU32 col; };
    std::vector<ProjPt> pts;
    double vmin = 1e30, vmax = -1e30;
    for (int ri = 0; ri < (int)data_.results.size(); ++ri) {
        double v = getAngleValue(ri, selectedPartId_, quantity_);
        vmin = std::min(vmin, v); vmax = std::max(vmax, v);
    }
    double vrange = std::max(vmax - vmin, 1e-10);

    for (int ri = 0; ri < (int)data_.results.size(); ++ri) {
        auto& r = data_.results[ri];
        float sx, sy, szp;
        projectGlobe(r.angle.lon, r.angle.lat, vLon, vLat, R, sx, sy, szp);
        double v = getAngleValue(ri, selectedPartId_, quantity_);
        double norm = (v - vmin) / vrange;
        pts.push_back({sx, sy, szp, ri, valueToColor(norm)});
    }
    std::sort(pts.begin(), pts.end(), [](const auto& a, const auto& b) { return a.sz < b.sz; });

    int nPts = (int)pts.size();
    float baseR = nPts > 500 ? 2 : nPts > 200 ? 3 : 4;
    for (auto& p : pts) {
        float px = cx + p.sx, py = cy - p.sy;
        if (p.sz > 0) {
            bool sel = selectedAngles_.count(p.ri);
            dl->AddCircleFilled(ImVec2(px, py), sel ? baseR + 2 : baseR, p.col);
            if (sel) dl->AddCircle(ImVec2(px, py), baseR + 4, IM_COL32(255,255,255,200), 0, 1.5f);
        } else {
            dl->AddCircleFilled(ImVec2(px, py), baseR * 0.6f, IM_COL32((p.col&0xFF)/4, ((p.col>>8)&0xFF)/4, ((p.col>>16)&0xFF)/4, 150));
        }
    }
}

// ============================================================
// Directional Analysis
// ============================================================
void SphereReportApp::renderDirectional() {
    ImGui::TextColored(COL_DIM,
        "Ranking of impact directions by peak value.\n"
        "Shows which directions are most critical for the selected part and quantity.");
    ImGui::Spacing();

    // Top 20 worst directions
    std::vector<std::pair<int, double>> ranked;
    for (int ri = 0; ri < (int)data_.results.size(); ++ri)
        ranked.push_back({ri, getAngleValue(ri, selectedPartId_, quantity_)});
    std::sort(ranked.begin(), ranked.end(), [](auto& a, auto& b) { return a.second > b.second; });

    const char* qtyNames[] = {"Stress (MPa)", "Strain", "G-Force", "Disp (mm)"};
    ImGui::TextColored(COL_ACCENT, "  Top 20 Worst Directions — %s", qtyNames[quantity_]);
    ImGui::Separator();

    double maxV = ranked.empty() ? 1.0 : std::max(ranked[0].second, 1e-10);
    for (int i = 0; i < std::min(20, (int)ranked.size()); ++i) {
        int ri = ranked[i].first;
        auto& r = data_.results[ri];
        float pct = (float)(ranked[i].second / maxV);

        char label[128];
        snprintf(label, sizeof(label), "%2d. %-15s [%s]", i+1, r.angle.name.c_str(), r.angle.category.c_str());
        ImGui::Text("%s", label);
        ImGui::SameLine(250);
        ImGui::PushStyleColor(ImGuiCol_PlotHistogram, ImVec4(0.31f+pct*0.6f, 0.2f, 0.2f, 1));
        char ov[32]; snprintf(ov, sizeof(ov), "%.1f", ranked[i].second);
        ImGui::ProgressBar(pct, ImVec2(-1, 16), ov);
        ImGui::PopStyleColor();
    }

    // Category breakdown
    ImGui::Spacing();
    ImGui::TextColored(COL_BLUE, "  Category Breakdown");
    ImGui::Separator();
    std::map<std::string, std::vector<double>> catVals;
    for (int ri = 0; ri < (int)data_.results.size(); ++ri) {
        catVals[data_.results[ri].angle.category].push_back(
            getAngleValue(ri, selectedPartId_, quantity_));
    }
    for (auto& [cat, vals] : catVals) {
        double avg = 0, maxC = 0;
        for (double v : vals) { avg += v; maxC = std::max(maxC, v); }
        avg /= vals.size();
        ImGui::Text("  %-12s  count=%d  avg=%.1f  max=%.1f", cat.c_str(), (int)vals.size(), avg, maxC);
    }
}

// ============================================================
// Statistics
// ============================================================
void SphereReportApp::renderStatistics() {
    ImGui::TextColored(COL_DIM,
        "Distribution of peak values across all impact directions.\n"
        "Histogram shows how many angles fall into each value bin.");
    ImGui::Spacing();

    std::vector<double> vals;
    for (int ri = 0; ri < (int)data_.results.size(); ++ri)
        vals.push_back(getAngleValue(ri, selectedPartId_, quantity_));

    if (vals.empty()) return;

    double vmin = *std::min_element(vals.begin(), vals.end());
    double vmax = *std::max_element(vals.begin(), vals.end());
    double avg = 0, stddev = 0;
    for (double v : vals) avg += v;
    avg /= vals.size();
    for (double v : vals) stddev += (v - avg) * (v - avg);
    stddev = std::sqrt(stddev / vals.size());

    // Summary stats
    ImGui::TextColored(COL_ACCENT, "  Summary Statistics");
    ImGui::Separator();
    ImGui::Text("  Count: %d    Min: %.2f    Max: %.2f    Mean: %.2f    StdDev: %.2f",
        (int)vals.size(), vmin, vmax, avg, stddev);
    ImGui::Spacing();

    // Histogram
    int nBins = 20;
    double binW = std::max((vmax - vmin) / nBins, 1e-10);
    std::vector<double> bins(nBins, 0);
    std::vector<double> binCenters(nBins);
    for (int i = 0; i < nBins; ++i)
        binCenters[i] = vmin + (i + 0.5) * binW;
    for (double v : vals) {
        int bi = std::min((int)((v - vmin) / binW), nBins - 1);
        if (bi >= 0) bins[bi]++;
    }

    const char* qtyNames[] = {"Stress (MPa)", "Strain", "G-Force", "Disp (mm)"};
    ImVec2 plotSz(ImGui::GetContentRegionAvail().x, std::max(250.0f, ImGui::GetContentRegionAvail().y - 10));
    if (ImPlot::BeginPlot("##Histogram", plotSz)) {
        ImPlot::SetupAxes(qtyNames[quantity_], "Count");
        ImPlot::PlotBars("Distribution", binCenters.data(), bins.data(), nBins, binW * 0.8);
        // Mean line
        ImPlot::PlotInfLines("Mean", &avg, 1);
        ImPlot::EndPlot();
    }
}

// ============================================================
// Findings (auto-generated recommendations)
// ============================================================
void SphereReportApp::renderFindings() {
    ImGui::TextColored(COL_ACCENT, "  Automated Findings & Recommendations");
    ImGui::Separator();
    ImGui::Spacing();

    auto finding = [](ImDrawList* dl, ImVec2 pos, const char* level, const char* title, const char* detail, ImVec4 col) {
        ImVec4 bg = col; bg.w = 0.12f;
        ImGui::PushStyleColor(ImGuiCol_ChildBg, bg);
        ImGui::BeginChild(title, ImVec2(-1, 70), true);
        ImGui::TextColored(col, "%s  %s", level, title);
        ImGui::TextColored(COL_DIM, "%s", detail);
        ImGui::EndChild();
        ImGui::PopStyleColor();
        ImGui::Spacing();
    };

    // Generate findings
    char buf[256];

    // 1. Coverage
    snprintf(buf, sizeof(buf), "%d/%d simulations completed. DOE: %s, Angular spacing: %.1f deg, Coverage: %.0f%%",
        data_.successful_runs, data_.total_runs, data_.doe_strategy.c_str(), data_.angular_spacing, data_.sphere_coverage * 100);
    finding(nullptr, ImVec2(0,0), "INFO", "Simulation Coverage", buf,
        data_.sphere_coverage >= 0.9 ? COL_ACCENT : COL_YELLOW);

    // 2. Worst stress
    if (data_.worst_stress_angle >= 0) {
        auto& wr = data_.results[data_.worst_stress_angle];
        snprintf(buf, sizeof(buf), "Peak stress %.1f MPa at direction %s (Roll=%.1f, Pitch=%.1f)",
            data_.worst_stress, wr.angle.name.c_str(), wr.angle.roll, wr.angle.pitch);
        ImVec4 col = (data_.yield_stress > 0 && data_.worst_stress > data_.yield_stress) ? COL_RED : COL_YELLOW;
        finding(nullptr, ImVec2(0,0), data_.worst_stress > data_.yield_stress ? "CRITICAL" : "WARNING",
            "Worst Case Stress", buf, col);
    }

    // 3. Safety factor
    if (data_.yield_stress > 0 && data_.worst_stress > 0) {
        double sf = data_.yield_stress / data_.worst_stress;
        snprintf(buf, sizeof(buf), "Global Safety Factor = %.3f (Yield = %.0f MPa / Peak = %.0f MPa)%s",
            sf, data_.yield_stress, data_.worst_stress,
            sf < 1.0 ? " — EXCEEDS YIELD" : sf < 1.5 ? " — Low margin" : " — Acceptable");
        finding(nullptr, ImVec2(0,0), sf < 1.0 ? "CRITICAL" : sf < 1.5 ? "WARNING" : "OK",
            "Safety Factor Assessment", buf, sf < 1.0 ? COL_RED : sf < 1.5 ? COL_YELLOW : COL_ACCENT);
    }

    // 4. Directional sensitivity
    {
        std::vector<double> vals;
        for (auto& r : data_.results)
            for (auto& [pid, pd] : r.parts)
                vals.push_back(pd.peak_stress);
        if (!vals.empty()) {
            double vmin = *std::min_element(vals.begin(), vals.end());
            double vmax = *std::max_element(vals.begin(), vals.end());
            double ratio = vmax > 1e-6 ? vmin / vmax : 1;
            snprintf(buf, sizeof(buf), "Min/Max stress ratio = %.2f. %s",
                ratio, ratio < 0.3 ? "High directional sensitivity — some angles much worse than others."
                     : ratio < 0.7 ? "Moderate directional dependence."
                     : "Relatively uniform across directions.");
            finding(nullptr, ImVec2(0,0), ratio < 0.3 ? "WARNING" : "INFO",
                "Directional Sensitivity", buf, ratio < 0.3 ? COL_YELLOW : COL_BLUE);
        }
    }

    // 5. Part count
    snprintf(buf, sizeof(buf), "%d parts analyzed across %d impact directions = %d data points total.",
        (int)data_.parts.size(), (int)data_.results.size(),
        (int)(data_.parts.size() * data_.results.size()));
    finding(nullptr, ImVec2(0,0), "INFO", "Analysis Scope", buf, COL_BLUE);
}

// ============================================================
// Heatmap: Part x All Angles (color coded grid)
// ============================================================
void SphereReportApp::renderHeatmapTab() {
    ImGui::TextColored(COL_DIM,
        "Full part-by-angle heatmap. Each cell shows the selected quantity value.\n"
        "Color intensity proportional to value. Scroll horizontally for all angles.");
    ImGui::Spacing();

    if (data_.results.empty() || data_.parts.empty()) return;

    // Sort angles by worst value descending
    std::vector<int> angleOrder;
    for (int ri = 0; ri < (int)data_.results.size(); ++ri) angleOrder.push_back(ri);
    std::sort(angleOrder.begin(), angleOrder.end(), [&](int a, int b) {
        double va = 0, vb = 0;
        for (auto& [pid, pd] : data_.results[a].parts) {
            double v = 0;
            switch (quantity_) { case 0: v=pd.peak_stress; break; case 1: v=pd.peak_strain; break; case 2: v=pd.peak_g; break; case 3: v=pd.peak_disp; break; }
            va = std::max(va, v);
        }
        for (auto& [pid, pd] : data_.results[b].parts) {
            double v = 0;
            switch (quantity_) { case 0: v=pd.peak_stress; break; case 1: v=pd.peak_strain; break; case 2: v=pd.peak_g; break; case 3: v=pd.peak_disp; break; }
            vb = std::max(vb, v);
        }
        return va > vb;
    });

    int nAngles = std::min(50, (int)angleOrder.size());  // Limit columns for performance
    int ncols = 2 + nAngles;

    if (ImGui::BeginTable("##FullHeatmap", ncols,
            ImGuiTableFlags_ScrollX | ImGuiTableFlags_ScrollY |
            ImGuiTableFlags_RowBg | ImGuiTableFlags_BordersInnerV |
            ImGuiTableFlags_SizingFixedFit)) {

        ImGui::TableSetupScrollFreeze(2, 1);
        ImGui::TableSetupColumn("Part", 0, 35);
        ImGui::TableSetupColumn("Name", 0, 90);
        for (int i = 0; i < nAngles; ++i) {
            ImGui::TableSetupColumn(data_.results[angleOrder[i]].angle.name.c_str(), 0, 50);
        }
        ImGui::TableHeadersRow();

        // Global max for normalization
        double gmax = 1;
        for (auto& [pid, pi] : data_.parts)
            for (int i = 0; i < nAngles; ++i)
                gmax = std::max(gmax, getAngleValue(angleOrder[i], pid, quantity_));

        for (auto& [pid, pi] : data_.parts) {
            ImGui::TableNextRow();
            ImGui::TableSetColumnIndex(0); ImGui::Text("%d", pid);
            ImGui::TableSetColumnIndex(1); ImGui::TextUnformatted(pi.name.c_str());
            for (int i = 0; i < nAngles; ++i) {
                ImGui::TableSetColumnIndex(i + 2);
                double v = getAngleValue(angleOrder[i], pid, quantity_);
                double norm = v / gmax;
                ImU32 bg = valueToColor(norm);
                int r = (bg >> 0) & 0xFF, g = (bg >> 8) & 0xFF, b = (bg >> 16) & 0xFF;
                ImGui::TableSetBgColor(ImGuiTableBgTarget_CellBg, IM_COL32(r/3, g/3, b/3, 200));
                ImGui::Text("%.0f", v);
            }
        }
        ImGui::EndTable();
    }

    if ((int)angleOrder.size() > nAngles) {
        ImGui::TextColored(COL_DIM, "Showing top %d of %d angles (sorted by worst value)", nAngles, (int)angleOrder.size());
    }
}

// ============================================================
// Failure Analysis Tab
// ============================================================
void SphereReportApp::renderFailureTab() {
    ImGui::TextColored(COL_DIM,
        "Failure prediction based on yield stress and strain limits.\n"
        "Parts exceeding material limits are flagged by direction.");
    ImGui::Spacing();

    if (data_.yield_stress <= 0) {
        ImGui::TextColored(COL_YELLOW, "No yield stress specified. Cannot perform failure analysis.");
        ImGui::TextColored(COL_DIM, "Set yield stress in koo_sphere_report: --yield-stress <MPa>");
        return;
    }

    ImGui::TextColored(COL_ACCENT, "  Safety Factor by Part (Global Worst Angle)");
    ImGui::Separator();
    ImGui::Spacing();

    struct PartFailure {
        int pid;
        std::string name;
        double worst_stress;
        double safety_factor;
        std::string worst_angle;
    };
    std::vector<PartFailure> failures;

    for (auto& [pid, pi] : data_.parts) {
        double worst = 0;
        std::string worstAngle;
        for (int ri = 0; ri < (int)data_.results.size(); ++ri) {
            auto it = data_.results[ri].parts.find(pid);
            if (it != data_.results[ri].parts.end() && it->second.peak_stress > worst) {
                worst = it->second.peak_stress;
                worstAngle = data_.results[ri].angle.name;
            }
        }
        double sf = worst > 0 ? data_.yield_stress / worst : 999;
        failures.push_back({pid, pi.name, worst, sf, worstAngle});
    }
    std::sort(failures.begin(), failures.end(), [](auto& a, auto& b) { return a.safety_factor < b.safety_factor; });

    if (ImGui::BeginTable("##FailureTable", 5,
            ImGuiTableFlags_RowBg | ImGuiTableFlags_ScrollY |
            ImGuiTableFlags_SizingStretchProp | ImGuiTableFlags_BordersInnerV)) {

        ImGui::TableSetupScrollFreeze(0, 1);
        ImGui::TableSetupColumn("Part");
        ImGui::TableSetupColumn("Name");
        ImGui::TableSetupColumn("Peak Stress (MPa)");
        ImGui::TableSetupColumn("Worst Angle");
        ImGui::TableSetupColumn("Safety Factor");
        ImGui::TableHeadersRow();

        for (auto& f : failures) {
            ImGui::TableNextRow();
            ImGui::TableSetColumnIndex(0); ImGui::Text("%d", f.pid);
            ImGui::TableSetColumnIndex(1); ImGui::TextUnformatted(f.name.c_str());
            ImGui::TableSetColumnIndex(2); ImGui::Text("%.1f", f.worst_stress);
            ImGui::TableSetColumnIndex(3); ImGui::TextColored(COL_ACCENT, "%s", f.worst_angle.c_str());
            ImGui::TableSetColumnIndex(4);
            ImVec4 sfCol = f.safety_factor >= 1.5 ? COL_ACCENT :
                           f.safety_factor >= 1.0 ? COL_YELLOW : COL_RED;
            ImGui::TextColored(sfCol, "%.3f%s", f.safety_factor,
                f.safety_factor < 1.0 ? " FAIL" : f.safety_factor < 1.5 ? " LOW" : "");
        }
        ImGui::EndTable();
    }

    // Count failures
    int nFail = 0, nLow = 0;
    for (auto& f : failures) {
        if (f.safety_factor < 1.0) nFail++;
        else if (f.safety_factor < 1.5) nLow++;
    }
    ImGui::Spacing();
    if (nFail > 0)
        ImGui::TextColored(COL_RED, "!! %d parts EXCEED yield stress (SF < 1.0)", nFail);
    if (nLow > 0)
        ImGui::TextColored(COL_YELLOW, "! %d parts have LOW safety margin (SF < 1.5)", nLow);
    if (nFail == 0 && nLow == 0)
        ImGui::TextColored(COL_ACCENT, "All parts within acceptable safety margins (SF >= 1.5)");
}

// ============================================================
// Orientation Cube — shows device direction for hovered angle
// ============================================================
void SphereReportApp::drawOrientationCube(ImDrawList* dl, ImVec2 pos, float size,
                                           double rollDeg, double pitchDeg) {
    float cx = pos.x + size * 0.5f, cy = pos.y + size * 0.5f;
    float s = size * 0.35f;

    double r = rollDeg * M_PI / 180.0, p = pitchDeg * M_PI / 180.0;
    float cr = (float)std::cos(r), sr = (float)std::sin(r);
    float cp = (float)std::cos(p), sp = (float)std::sin(p);

    // 3D cube vertices (unit cube centered at origin)
    float verts[8][3] = {
        {-1,-1,-1},{1,-1,-1},{1,1,-1},{-1,1,-1},
        {-1,-1,1},{1,-1,1},{1,1,1},{-1,1,1}
    };

    // Rotate by roll (around X) then pitch (around Y)
    auto rotate = [&](float x, float y, float z, float& ox, float& oy) {
        // Rx(roll)
        float y1 = y*cr - z*sr, z1 = y*sr + z*cr;
        // Ry(pitch)
        float x2 = x*cp + z1*sp, z2 = -x*sp + z1*cp;
        // Isometric projection
        ox = (x2 - y1) * 0.707f;
        oy = -(x2 + y1) * 0.408f - z2 * 0.816f;
    };

    float proj[8][2];
    for (int i = 0; i < 8; ++i) {
        rotate(verts[i][0], verts[i][1], verts[i][2], proj[i][0], proj[i][1]);
        proj[i][0] = cx + proj[i][0] * s;
        proj[i][1] = cy + proj[i][1] * s;
    }

    // Background
    dl->AddRectFilled(pos, ImVec2(pos.x + size, pos.y + size), IM_COL32(20, 22, 35, 200), 6);

    // Draw edges
    int edges[][2] = {{0,1},{1,2},{2,3},{3,0},{4,5},{5,6},{6,7},{7,4},{0,4},{1,5},{2,6},{3,7}};
    for (auto& e : edges) {
        dl->AddLine(ImVec2(proj[e[0]][0], proj[e[0]][1]),
                    ImVec2(proj[e[1]][0], proj[e[1]][1]),
                    IM_COL32(150, 155, 180, 150), 1.2f);
    }

    // Face labels (approximate center of top face)
    // Top face = verts 4,5,6,7 (Z+)
    float topCx = (proj[4][0]+proj[5][0]+proj[6][0]+proj[7][0])/4;
    float topCy = (proj[4][1]+proj[5][1]+proj[6][1]+proj[7][1])/4;
    dl->AddText(ImVec2(topCx-4, topCy-6), IM_COL32(78,204,163,255), "T");

    // Front face = verts 0,1,5,4 (Y-)
    float frCx = (proj[0][0]+proj[1][0]+proj[5][0]+proj[4][0])/4;
    float frCy = (proj[0][1]+proj[1][1]+proj[5][1]+proj[4][1])/4;
    dl->AddText(ImVec2(frCx-4, frCy-6), IM_COL32(233,69,96,255), "F");

    // Right face = verts 1,2,6,5 (X+)
    float rtCx = (proj[1][0]+proj[2][0]+proj[6][0]+proj[5][0])/4;
    float rtCy = (proj[1][1]+proj[2][1]+proj[6][1]+proj[5][1])/4;
    dl->AddText(ImVec2(rtCx-4, rtCy-6), IM_COL32(79,192,255,255), "R");

    // Roll/Pitch label
    char label[64];
    snprintf(label, sizeof(label), "R:%.0f P:%.0f", rollDeg, pitchDeg);
    dl->AddText(ImVec2(pos.x + 4, pos.y + size - 14), IM_COL32(150,155,180,200), label);
}
