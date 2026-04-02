#include "app/DeepReportApp.hpp"

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
// Color constants (matching HTML report theme)
// ============================================================
static const ImVec4 COL_BG       = {0.10f, 0.10f, 0.18f, 1.0f};
static const ImVec4 COL_CARD     = {0.12f, 0.16f, 0.27f, 1.0f};
static const ImVec4 COL_ACCENT   = {0.31f, 0.80f, 0.64f, 1.0f};  // #4ecca3
static const ImVec4 COL_RED      = {0.91f, 0.27f, 0.38f, 1.0f};  // #e94560
static const ImVec4 COL_YELLOW   = {0.96f, 0.65f, 0.14f, 1.0f};  // #f5a623
static const ImVec4 COL_BLUE     = {0.31f, 0.56f, 1.00f, 1.0f};
static const ImVec4 COL_PURPLE   = {0.48f, 0.41f, 0.93f, 1.0f};
static const ImVec4 COL_DIM      = {0.63f, 0.63f, 0.69f, 1.0f};

static const ImVec4 CHART_COLORS[] = {
    {0.31f,0.80f,0.64f,1}, {0.91f,0.27f,0.38f,1}, {0.96f,0.65f,0.14f,1},
    {0.48f,0.41f,0.93f,1}, {0.00f,0.74f,0.83f,1}, {1.00f,0.60f,0.00f,1},
    {0.61f,0.15f,0.69f,1}, {0.30f,0.69f,0.31f,1}, {0.94f,0.50f,0.50f,1},
    {0.40f,0.73f,0.92f,1}, {0.80f,0.80f,0.20f,1}, {0.70f,0.40f,0.70f,1},
};
static constexpr int NUM_CHART_COLORS = sizeof(CHART_COLORS) / sizeof(CHART_COLORS[0]);

// ============================================================
// Helpers
// ============================================================
static const char* fmtStress(double v, char* buf, size_t sz) {
    if (std::abs(v) >= 1e6) snprintf(buf, sz, "%.2e", v);
    else snprintf(buf, sz, "%.1f", v);
    return buf;
}

static ImVec4 warningColor(const std::string& w) {
    if (w == "crit") return COL_RED;
    if (w == "warn") return COL_YELLOW;
    return COL_ACCENT;
}

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
            if (ImGui::IsKeyPressed(ImGuiKey_F11)) {
                // Toggle fullscreen (not implemented — maximize only)
                static bool maximized = true;
                if (maximized) glfwRestoreWindow(window_);
                else glfwMaximizeWindow(window_);
                maximized = !maximized;
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
        renderPartTable();

        // Main analysis panel with tabs
        ImGui::Begin("Analysis");
        if (ImGui::BeginTabBar("AnalysisTabs")) {
            if (ImGui::BeginTabItem("Overview"))  { renderOverview(); ImGui::EndTabItem(); }
            if (ImGui::BeginTabItem("Stress"))    { renderStressTab(); ImGui::EndTabItem(); }
            if (ImGui::BeginTabItem("Tensor"))    { renderTensorTab(); ImGui::EndTabItem(); }
            if (ImGui::BeginTabItem("Motion"))    { renderMotionTab(); ImGui::EndTabItem(); }
            if (ImGui::BeginTabItem("Energy"))    { renderEnergyTab(); ImGui::EndTabItem(); }
            if (ImGui::BeginTabItem("Deep Dive")) { renderDeepDiveTab(); ImGui::EndTabItem(); }
            if (!data_.element_quality.empty()) {
                if (ImGui::BeginTabItem("Quality")) { renderQualityTab(); ImGui::EndTabItem(); }
            }
            if (!data_.rcforc.empty() || !data_.sleout.empty()) {
                if (ImGui::BeginTabItem("Contact")) { renderContactTab(); ImGui::EndTabItem(); }
            }
            if (ImGui::BeginTabItem("3D View"))   { render3DTab(); ImGui::EndTabItem(); }
            if (ImGui::BeginTabItem("Renders"))   { renderRenderGalleryTab(); ImGui::EndTabItem(); }
            if (ImGui::BeginTabItem("SysInfo"))   { renderSysInfoTab(); ImGui::EndTabItem(); }
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

    auto kpi = [&](const char* label, const char* value, const char* unit, ImVec4 col) {
        ImGui::BeginGroup();
        ImGui::PushStyleColor(ImGuiCol_Text, COL_DIM);
        ImGui::SmallButton(label);  // label as pseudo-badge
        ImGui::PopStyleColor();
        ImGui::PushStyleColor(ImGuiCol_Text, col);
        ImGui::SetWindowFontScale(1.5f);
        ImGui::TextUnformatted(value);
        ImGui::SetWindowFontScale(1.0f);
        ImGui::PopStyleColor();
        ImGui::PushStyleColor(ImGuiCol_Text, COL_DIM);
        ImGui::TextUnformatted(unit);
        ImGui::PopStyleColor();
        ImGui::EndGroup();
    };

    // Determine column count based on available data
    int ncols = 5;
    bool hasSF = (data_.yield_stress > 0 && data_.peak_stress_global > 0);
    if (hasSF) ncols = 6;

    ImGui::Columns(ncols, nullptr, false);

    // Termination status
    if (data_.normal_termination)
        kpi("STATUS", "Normal", "termination", COL_ACCENT);
    else
        kpi("STATUS", "ERROR", "termination", COL_RED);
    ImGui::NextColumn();

    kpi("PEAK STRESS", fmtStress(data_.peak_stress_global, buf, sizeof(buf)), "MPa", COL_ACCENT);
    ImGui::NextColumn();
    snprintf(buf, sizeof(buf), "%.4f", data_.peak_strain_global);
    kpi("PEAK STRAIN", buf, "", COL_YELLOW);
    ImGui::NextColumn();
    snprintf(buf, sizeof(buf), "%.2f", data_.peak_disp_global);
    kpi("PEAK DISP", buf, "mm", COL_PURPLE);
    ImGui::NextColumn();

    if (hasSF) {
        double sf = data_.yield_stress / data_.peak_stress_global;
        snprintf(buf, sizeof(buf), "%.3f", sf);
        ImVec4 sfCol = sf >= 1.0 ? COL_ACCENT : sf >= 0.85 ? COL_YELLOW : COL_RED;
        kpi("SAFETY FACTOR", buf, (std::string("Yield=") + std::to_string((int)data_.yield_stress) + "MPa").c_str(), sfCol);
        ImGui::NextColumn();
    }

    snprintf(buf, sizeof(buf), "%.4f", data_.energy_ratio_min);
    ImVec4 erCol = data_.energy_ratio_min > 1.1 ? COL_RED : data_.energy_ratio_min > 1.05 ? COL_YELLOW : COL_ACCENT;
    kpi("ENERGY RATIO", buf, "min", erCol);
    ImGui::Columns(1);

    ImGui::End();
}

// ============================================================
// Overview — bar chart ranking
// ============================================================
void DeepReportApp::renderOverview() {
    if (data_.parts.empty()) {
        ImGui::TextColored(COL_DIM, "No data loaded");
        return;
    }

    // Warnings at top
    renderWarnings();

    // Guide text
    ImGui::TextColored(COL_DIM,
        "Von Mises stress indicates combined multiaxial stress state.\n"
        "Values approaching yield stress require attention.\n"
        "Eff. plastic strain > 0 means permanent deformation has occurred.");
    ImGui::Spacing();

    // Sort parts by peak stress
    std::vector<std::pair<int, const PartSummary*>> sorted;
    for (const auto& [pid, ps] : data_.parts) sorted.push_back({pid, &ps});
    std::sort(sorted.begin(), sorted.end(),
              [](const auto& a, const auto& b) { return a.second->peak_stress > b.second->peak_stress; });

    double maxStress = sorted.empty() ? 1.0 : std::max(sorted[0].second->peak_stress, 1.0);

    ImGui::TextColored(COL_ACCENT, "  Stress Ranking (Top %d)", (int)std::min(sorted.size(), (size_t)10));
    ImGui::Separator();
    ImGui::Spacing();

    for (size_t i = 0; i < std::min(sorted.size(), (size_t)10); ++i) {
        auto& [pid, ps] = sorted[i];
        float pct = static_cast<float>(ps->peak_stress / maxStress);

        char label[128];
        snprintf(label, sizeof(label), "Part %d %s", pid, ps->name.c_str());

        ImGui::Text("%-20s", label);
        ImGui::SameLine(200);

        // Progress bar as horizontal bar chart
        ImVec4 barCol = (ps->stress_warning == "crit") ? COL_RED :
                        (ps->stress_warning == "warn") ? COL_YELLOW : COL_ACCENT;
        ImGui::PushStyleColor(ImGuiCol_PlotHistogram, barCol);
        char overlay[64];
        snprintf(overlay, sizeof(overlay), "%.1f MPa", ps->peak_stress);
        ImGui::ProgressBar(pct, ImVec2(-1, 18), overlay);
        ImGui::PopStyleColor();
    }

    // Strain ranking
    auto strainSorted = sorted;
    std::sort(strainSorted.begin(), strainSorted.end(),
              [](const auto& a, const auto& b) { return a.second->peak_strain > b.second->peak_strain; });
    double maxStrain = strainSorted.empty() ? 1.0 : std::max(strainSorted[0].second->peak_strain, 1e-10);

    ImGui::Spacing();
    ImGui::Spacing();
    ImGui::TextColored(COL_YELLOW, "  Strain Ranking (Top %d)", (int)std::min(strainSorted.size(), (size_t)10));
    ImGui::Separator();
    ImGui::Spacing();

    for (size_t i = 0; i < std::min(strainSorted.size(), (size_t)10); ++i) {
        auto& [pid, ps] = strainSorted[i];
        if (ps->peak_strain <= 0) break;
        float pct = static_cast<float>(ps->peak_strain / maxStrain);

        char label[128];
        snprintf(label, sizeof(label), "Part %d %s", pid, ps->name.c_str());
        ImGui::Text("%-20s", label);
        ImGui::SameLine(200);

        ImGui::PushStyleColor(ImGuiCol_PlotHistogram, COL_YELLOW);
        char overlay[64];
        snprintf(overlay, sizeof(overlay), "%.4f", ps->peak_strain);
        ImGui::ProgressBar(pct, ImVec2(-1, 18), overlay);
        ImGui::PopStyleColor();
    }
}

// ============================================================
// Part Table
// ============================================================
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

    if (ImGui::BeginTable("##PartTable", 8,
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

        static int sortCol = 0;
        static bool sortAsc = true;

        if (ImGuiTableSortSpecs* specs = ImGui::TableGetSortSpecs()) {
            if (specs->SpecsDirty && specs->SpecsCount > 0) {
                sortCol = specs->Specs[0].ColumnIndex;
                sortAsc = (specs->Specs[0].SortDirection == ImGuiSortDirection_Ascending);
                specs->SpecsDirty = false;
            }
        }

        // Always sort based on current sort state
        std::sort(sorted.begin(), sorted.end(), [](const auto& a, const auto& b) {
            // default: by ID ascending — overridden below
            return a.first < b.first;
        });
        std::sort(sorted.begin(), sorted.end(), [sortCol, sortAsc](const auto& a, const auto& b) {
            double va = 0, vb = 0;
            switch (sortCol) {
                case 0: va = a.first; vb = b.first; break;
                case 1: return sortAsc ? a.second->name < b.second->name : a.second->name > b.second->name;
                case 2: return sortAsc ? a.second->mat_type < b.second->mat_type : a.second->mat_type > b.second->mat_type;
                case 3: va = a.second->peak_stress; vb = b.second->peak_stress; break;
                case 4: va = a.second->peak_strain; vb = b.second->peak_strain; break;
                case 5: va = a.second->peak_disp; vb = b.second->peak_disp; break;
                case 6: va = a.second->safety_factor; vb = b.second->safety_factor; break;
                default: return false;
            }
            return sortAsc ? va < vb : va > vb;
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
                std::string worst = ps->stress_warning;
                if (ps->strain_warning == "crit" || (ps->strain_warning == "warn" && worst == "ok")) worst = ps->strain_warning;
                ImGui::TextColored(warningColor(worst), "%s",
                    worst == "crit" ? "CRIT" : worst == "warn" ? "WARN" : "OK");
            }
        }

        ImGui::EndTable();
    }

    ImGui::End();
}

// ============================================================
// Stress Chart
// ============================================================
// ============================================================
// Helper: draw horizontal bar ranking
// ============================================================
void DeepReportApp::drawBarRanking(const char* title, const std::vector<std::pair<int, double>>& items, ImVec4 color, const char* unit, int decimals) {
    if (items.empty()) return;
    ImGui::TextColored(COL_ACCENT, "  %s", title);
    ImGui::Separator();
    ImGui::Spacing();

    double maxVal = std::max(items[0].second, 1e-10);
    for (size_t i = 0; i < std::min(items.size(), (size_t)10); ++i) {
        auto& [pid, val] = items[i];
        float pct = static_cast<float>(std::abs(val) / std::abs(maxVal));
        auto it = data_.parts.find(pid);
        std::string name = it != data_.parts.end() ? it->second.name : "";

        char label[128];
        snprintf(label, sizeof(label), "Part %d %s", pid, name.c_str());
        ImGui::Text("%-22s", label);
        ImGui::SameLine(220);

        ImGui::PushStyleColor(ImGuiCol_PlotHistogram, color);
        char overlay[64];
        if (decimals <= 1)
            snprintf(overlay, sizeof(overlay), "%.1f %s", val, unit);
        else
            snprintf(overlay, sizeof(overlay), "%.*f %s", decimals, val, unit);
        ImGui::ProgressBar(pct, ImVec2(-1, 16), overlay);
        ImGui::PopStyleColor();
    }
    ImGui::Spacing();
}

// ============================================================
// Helper: draw time series plot for selected parts
// ============================================================
void DeepReportApp::drawTimeSeriesPlot(const char* id, const char* yLabel, const std::vector<PartTimeSeries>& series, bool showAvg) {
    ImVec2 sz(ImGui::GetContentRegionAvail().x, std::max(250.0f, ImGui::GetContentRegionAvail().y * 0.45f));
    if (ImPlot::BeginPlot(id, sz)) {
        ImPlot::SetupAxes("Time", yLabel);
        for (const auto& ts : series) {
            if (ts.data.empty()) continue;
            bool show = selectedParts_.empty() || selectedParts_.count(ts.part_id);
            if (!show) continue;

            std::vector<double> t(ts.data.size()), vmax(ts.data.size()), vavg(ts.data.size());
            for (size_t i = 0; i < ts.data.size(); ++i) {
                t[i] = ts.data[i].time;
                vmax[i] = ts.data[i].max_value;
                vavg[i] = ts.data[i].avg_value;
            }

            char label[64];
            snprintf(label, sizeof(label), "P%d %s", ts.part_id, ts.part_name.c_str());
            ImPlot::PlotLine(label, t.data(), vmax.data(), (int)t.size());
            if (showAvg) {
                char avgLabel[64];
                snprintf(avgLabel, sizeof(avgLabel), "P%d avg", ts.part_id);
                ImPlot::PlotLine(avgLabel, t.data(), vavg.data(), (int)t.size());
            }
        }
        ImPlot::EndPlot();
    }
}

// ============================================================
// Warnings box
// ============================================================
void DeepReportApp::renderWarnings() {
    if (data_.warnings.empty()) return;

    for (const auto& w : data_.warnings) {
        ImVec4 col = (w.level == "crit") ? COL_RED : (w.level == "warn") ? COL_YELLOW : COL_BLUE;
        ImVec4 bg = col; bg.w = 0.15f;
        ImGui::PushStyleColor(ImGuiCol_ChildBg, bg);
        ImGui::BeginChild(("##warn" + w.message).c_str(), ImVec2(-1, 28), true);
        ImGui::TextColored(col, "%s  %s", w.level == "crit" ? "!!" : "!", w.message.c_str());
        ImGui::EndChild();
        ImGui::PopStyleColor();
        ImGui::Spacing();
    }
}

// ============================================================
// Stress Tab: bar rankings + time series overlay + per-part detail
// ============================================================
void DeepReportApp::renderStressTab() {
    renderWarnings();

    ImGui::TextColored(COL_DIM,
        "Von Mises: equivalent uniaxial stress from multiaxial state. SF = yield / peak.\n"
        "Principal stress: eigenvalues of stress tensor. S1 (max tension), S3 (max compression).\n"
        "Eff. plastic strain: accumulated irreversible deformation (0 = elastic only).");
    ImGui::Spacing();

    // Von Mises ranking
    {
        std::vector<std::pair<int, double>> items;
        for (const auto& [pid, ps] : data_.parts) items.push_back({pid, ps.peak_stress});
        std::sort(items.begin(), items.end(), [](const auto& a, const auto& b) { return a.second > b.second; });
        drawBarRanking("Von Mises Stress Ranking", items, COL_ACCENT, "MPa");
    }

    // Strain ranking
    {
        std::vector<std::pair<int, double>> items;
        for (const auto& [pid, ps] : data_.parts) if (ps.peak_strain > 0) items.push_back({pid, ps.peak_strain});
        std::sort(items.begin(), items.end(), [](const auto& a, const auto& b) { return a.second > b.second; });
        drawBarRanking("Eff. Plastic Strain Ranking", items, COL_YELLOW, "", 4);
    }

    // Time series: stress overlay (with yield line)
    ImGui::TextColored(COL_ACCENT, "  Stress Time History");
    ImGui::Separator();
    {
        ImVec2 sz(ImGui::GetContentRegionAvail().x, std::max(250.0f, ImGui::GetContentRegionAvail().y * 0.3f));
        if (ImPlot::BeginPlot("##StressTS", sz)) {
            ImPlot::SetupAxes("Time", "Von Mises (MPa)");
            for (const auto& ts : data_.stress) {
                if (ts.data.empty()) continue;
                bool show = selectedParts_.empty() || selectedParts_.count(ts.part_id);
                if (!show) continue;
                std::vector<double> t(ts.data.size()), v(ts.data.size());
                for (size_t i = 0; i < ts.data.size(); ++i) { t[i] = ts.data[i].time; v[i] = ts.data[i].max_value; }
                char label[64]; snprintf(label, sizeof(label), "P%d %s", ts.part_id, ts.part_name.c_str());
                ImPlot::PlotLine(label, t.data(), v.data(), (int)t.size());
            }
            // Yield stress horizontal line
            if (data_.yield_stress > 0) {
                double xt[] = {data_.start_time, data_.end_time};
                double yt[] = {data_.yield_stress, data_.yield_stress};
                ImPlot::PlotLine("Yield", xt, yt, 2);
            }
            ImPlot::EndPlot();
        }
    }

    // Time series: strain overlay
    if (!data_.strain.empty()) {
        ImGui::TextColored(COL_YELLOW, "  Strain Time History");
        ImGui::Separator();
        drawTimeSeriesPlot("##StrainTS", "Eff. Plastic Strain", data_.strain, false);
    }

    // Stress detail: max + avg for selected parts
    ImGui::TextColored(COL_ACCENT, "  Stress Detail (Max + Avg)");
    ImGui::Separator();
    drawTimeSeriesPlot("##StressDetail", "Von Mises (MPa)", data_.stress, true);

    // Principal stress
    if (!data_.max_principal.empty()) {
        ImGui::TextColored(COL_BLUE, "  Max Principal Stress (sigma_1)");
        ImGui::Separator();
        drawTimeSeriesPlot("##MaxPrinTS", "sigma_1 (MPa)", data_.max_principal, false);
    }
    if (!data_.min_principal.empty()) {
        ImGui::TextColored(COL_PURPLE, "  Min Principal Stress (sigma_3)");
        ImGui::Separator();
        drawTimeSeriesPlot("##MinPrinTS", "sigma_3 (MPa)", data_.min_principal, false);
    }

    // Principal strain
    if (!data_.max_principal_strain.empty()) {
        ImGui::TextColored(ImVec4(0.15f, 0.68f, 0.38f, 1.0f), "  Max Principal Strain (eps_1)");
        ImGui::Separator();
        drawTimeSeriesPlot("##MaxPSTS", "eps_1", data_.max_principal_strain, false);
    }
    if (!data_.min_principal_strain.empty()) {
        ImGui::TextColored(ImVec4(0.17f, 0.24f, 0.31f, 1.0f), "  Min Principal Strain (eps_3)");
        ImGui::Separator();
        drawTimeSeriesPlot("##MinPSTS", "eps_3", data_.min_principal_strain, false);
    }
}

// ============================================================
// Tensor Tab: peak element 6-component tensor history
// ============================================================
// Principal stress from 3x3 symmetric tensor (Lode angle method)
static void eigenvalues3x3(double sxx, double syy, double szz,
                            double sxy, double syz, double szx,
                            double& s1, double& s2, double& s3) {
    double I1 = sxx + syy + szz;
    double mean = I1 / 3.0;
    double dxx = sxx - mean, dyy = syy - mean, dzz = szz - mean;
    double J2 = 0.5*(dxx*dxx + dyy*dyy + dzz*dzz + 2*(sxy*sxy + syz*syz + szx*szx));
    if (J2 < 1e-20) { s1 = s2 = s3 = mean; return; }
    double J3 = dxx*(dyy*dzz - syz*syz) - sxy*(sxy*dzz - syz*szx) + szx*(sxy*syz - dyy*szx);
    double r = std::sqrt(J2 / 3.0);
    double cos3t = J3 / (2.0*r*r*r);
    cos3t = std::max(-1.0, std::min(1.0, cos3t));
    double theta = std::acos(cos3t) / 3.0;
    s1 = mean + 2*r*std::cos(theta);
    s2 = mean + 2*r*std::cos(theta - 2*M_PI/3);
    s3 = mean + 2*r*std::cos(theta + 2*M_PI/3);
    // Sort descending
    if (s2 > s1) std::swap(s1, s2);
    if (s3 > s1) std::swap(s1, s3);
    if (s3 > s2) std::swap(s2, s3);
}

void DeepReportApp::renderTensorTab() {
    if (data_.tensors.empty()) {
        ImGui::TextColored(COL_DIM, "No peak element tensor data");
        return;
    }

    static int selectedTensor = 0;
    static int tensorTimeIdx = 0;
    if (selectedTensor >= (int)data_.tensors.size()) selectedTensor = 0;

    // Selector
    ImGui::Text("Peak Element:");
    ImGui::SameLine();
    ImGui::SetNextItemWidth(400);
    if (ImGui::BeginCombo("##tensorSel", ("Elem " + std::to_string(data_.tensors[selectedTensor].element_id) +
        " Part " + std::to_string(data_.tensors[selectedTensor].part_id) +
        " [" + data_.tensors[selectedTensor].reason + "]").c_str())) {
        for (int i = 0; i < (int)data_.tensors.size(); ++i) {
            auto& t = data_.tensors[i];
            char label[128];
            snprintf(label, sizeof(label), "Elem %d — Part %d [%s] peak=%.1f", t.element_id, t.part_id, t.reason.c_str(), t.peak_value);
            if (ImGui::Selectable(label, selectedTensor == i)) {
                selectedTensor = i;
                tensorTimeIdx = 0;
            }
        }
        ImGui::EndCombo();
    }

    auto& tens = data_.tensors[selectedTensor];
    int n = (int)tens.time.size();
    if (n == 0) return;

    ImGui::TextColored(COL_DIM,
        "6-component stress tensor (Sxx,Syy,Szz,Sxy,Syz,Szx) at the peak element.\n"
        "Mohr's circles show shear-normal stress relationship. Larger circle = higher shear.\n"
        "Stress ellipsoid: 3D shape defined by principal stress magnitudes.");
    ImGui::Spacing();
    ImGui::Text("Peak: %.2f MPa at t=%.6f", tens.peak_value, tens.peak_time);

    // Compute principal stresses for all time steps
    std::vector<double> p1(n), p2(n), p3(n), vm(n);
    int peakVmIdx = 0;
    for (int i = 0; i < n; ++i) {
        eigenvalues3x3(tens.sxx[i], tens.syy[i], tens.szz[i],
                       tens.sxy[i], tens.syz[i], tens.szx[i],
                       p1[i], p2[i], p3[i]);
        double d1 = p1[i]-p2[i], d2 = p2[i]-p3[i], d3 = p3[i]-p1[i];
        vm[i] = std::sqrt(0.5*(d1*d1 + d2*d2 + d3*d3));
        if (vm[i] > vm[peakVmIdx]) peakVmIdx = i;
    }

    // Time slider + Jump to Peak button
    ImGui::SameLine(300);
    if (ImGui::Button("Jump to Peak")) tensorTimeIdx = peakVmIdx;
    ImGui::SetNextItemWidth(-1);
    ImGui::SliderInt("##tensorTime", &tensorTimeIdx, 0, n - 1);
    if (tensorTimeIdx >= n) tensorTimeIdx = n - 1;
    ImGui::Text("t=%.6f | S1=%.1f  S2=%.1f  S3=%.1f  VM=%.1f",
        tens.time[tensorTimeIdx], p1[tensorTimeIdx], p2[tensorTimeIdx], p3[tensorTimeIdx], vm[tensorTimeIdx]);
    ImGui::Spacing();

    // Layout: left = charts, right = Mohr + Ellipsoid
    float halfW = ImGui::GetContentRegionAvail().x * 0.5f;

    // ── Left: 6-component + principal stress charts ──
    ImGui::BeginChild("##TensorCharts", ImVec2(halfW - 5, -1));

    // 6-component chart
    ImGui::TextColored(COL_ACCENT, "  6-Component Tensor");
    float ch = std::max(150.0f, (ImGui::GetContentRegionAvail().y - 40) * 0.45f);
    if (ImPlot::BeginPlot("##TensorComp", ImVec2(-1, ch))) {
        ImPlot::SetupAxes("Time", "Stress (MPa)");
        if ((int)tens.sxx.size() == n) ImPlot::PlotLine("Sxx", tens.time.data(), tens.sxx.data(), n);
        if ((int)tens.syy.size() == n) ImPlot::PlotLine("Syy", tens.time.data(), tens.syy.data(), n);
        if ((int)tens.szz.size() == n) ImPlot::PlotLine("Szz", tens.time.data(), tens.szz.data(), n);
        if ((int)tens.sxy.size() == n) ImPlot::PlotLine("Sxy", tens.time.data(), tens.sxy.data(), n);
        if ((int)tens.syz.size() == n) ImPlot::PlotLine("Syz", tens.time.data(), tens.syz.data(), n);
        if ((int)tens.szx.size() == n) ImPlot::PlotLine("Szx", tens.time.data(), tens.szx.data(), n);
        // Vertical line at current time
        double ct = tens.time[tensorTimeIdx];
        ImPlot::PlotInfLines("##t", &ct, 1);
        ImPlot::EndPlot();
    }

    // Principal stress + Von Mises chart
    ImGui::TextColored(COL_BLUE, "  Principal Stresses + Von Mises");
    float ch2 = std::max(150.0f, ImGui::GetContentRegionAvail().y - 5);
    if (ImPlot::BeginPlot("##PrincipalTS", ImVec2(-1, ch2))) {
        ImPlot::SetupAxes("Time", "Stress (MPa)");
        ImPlot::PlotLine("S1 (max)", tens.time.data(), p1.data(), n);
        ImPlot::PlotLine("S2 (mid)", tens.time.data(), p2.data(), n);
        ImPlot::PlotLine("S3 (min)", tens.time.data(), p3.data(), n);
        ImPlot::PlotLine("Von Mises", tens.time.data(), vm.data(), n);
        double ct = tens.time[tensorTimeIdx];
        ImPlot::PlotInfLines("##t2", &ct, 1);
        ImPlot::EndPlot();
    }

    ImGui::EndChild();
    ImGui::SameLine();

    // ── Right: Mohr's Circle + Stress Ellipsoid ──
    ImGui::BeginChild("##MohrEllipsoid", ImVec2(-1, -1));

    double s1 = p1[tensorTimeIdx], s2 = p2[tensorTimeIdx], s3 = p3[tensorTimeIdx];

    // Mohr's Circles (2D)
    ImGui::TextColored(COL_RED, "  Mohr's Circles");
    float mohrH = std::max(200.0f, (ImGui::GetContentRegionAvail().y - 40) * 0.5f);
    if (ImPlot::BeginPlot("##Mohr", ImVec2(-1, mohrH), ImPlotFlags_Equal)) {
        ImPlot::SetupAxes("Normal Stress (MPa)", "Shear Stress (MPa)");

        // Draw 3 circles
        auto drawCircle = [](const char* name, double sa, double sb, int nPts = 100) {
            double center = (sa + sb) / 2.0;
            double radius = std::abs(sa - sb) / 2.0;
            std::vector<double> cx(nPts+1), cy(nPts+1);
            for (int i = 0; i <= nPts; ++i) {
                double angle = 2.0 * M_PI * i / nPts;
                cx[i] = center + radius * std::cos(angle);
                cy[i] = radius * std::sin(angle);
            }
            ImPlot::PlotLine(name, cx.data(), cy.data(), nPts+1);
        };

        drawCircle("S1-S2", s1, s2);
        drawCircle("S2-S3", s2, s3);
        drawCircle("S1-S3", s1, s3);

        // Principal stress markers on sigma axis
        double pts[] = {s1, s2, s3};
        double zeros[] = {0, 0, 0};
        ImPlot::PlotScatter("Principals", pts, zeros, 3);

        ImPlot::EndPlot();
    }

    // Stress Ellipsoid (wireframe projection via ImDrawList)
    ImGui::TextColored(COL_PURPLE, "  Stress Ellipsoid");
    float ellH = std::max(200.0f, ImGui::GetContentRegionAvail().y - 5);
    ImVec2 ellPos = ImGui::GetCursorScreenPos();
    ImVec2 ellSize(-1, ellH);
    ImGui::InvisibleButton("##ell", ImVec2(ImGui::GetContentRegionAvail().x, ellH));
    float ellW = ImGui::GetContentRegionAvail().x;

    ImDrawList* dl = ImGui::GetWindowDrawList();
    float ecx = ellPos.x + ellW * 0.5f;
    float ecy = ellPos.y + ellH * 0.5f;
    float maxP = std::max({std::abs(s1), std::abs(s2), std::abs(s3), 1.0});
    float scale = std::min(ellW, ellH) * 0.35f / (float)maxP;

    // Background
    dl->AddRectFilled(ellPos, ImVec2(ellPos.x + ellW, ellPos.y + ellH), IM_COL32(15, 15, 25, 255), 4);

    // Axis lines
    dl->AddLine(ImVec2(ecx - ellW*0.4f, ecy), ImVec2(ecx + ellW*0.4f, ecy), IM_COL32(100,100,120,100), 1);
    dl->AddLine(ImVec2(ecx, ecy - ellH*0.4f), ImVec2(ecx, ecy + ellH*0.4f), IM_COL32(100,100,120,100), 1);

    // Draw ellipse (isometric projection: x=S1, y=S2, perspective compress S3)
    float a = std::abs((float)s1) * scale;
    float b = std::abs((float)s2) * scale;
    float c = std::abs((float)s3) * scale;
    if (a < 2) a = 2; if (b < 2) b = 2; if (c < 2) c = 2;

    // Draw 3 orthogonal ellipse wireframes (XY, XZ, YZ planes)
    auto drawEllipseWire = [&](float ra, float rb, float rotDeg, ImU32 col) {
        int N = 64;
        float cosR = std::cos(rotDeg * M_PI / 180.0f);
        float sinR = std::sin(rotDeg * M_PI / 180.0f);
        for (int i = 0; i < N; ++i) {
            float t0 = 2.0f * M_PI * i / N;
            float t1 = 2.0f * M_PI * (i+1) / N;
            float x0 = ra*std::cos(t0), y0 = rb*std::sin(t0);
            float x1 = ra*std::cos(t1), y1 = rb*std::sin(t1);
            // Rotate
            float rx0 = x0*cosR - y0*sinR, ry0 = x0*sinR + y0*cosR;
            float rx1 = x1*cosR - y1*sinR, ry1 = x1*sinR + y1*cosR;
            dl->AddLine(ImVec2(ecx + rx0, ecy - ry0), ImVec2(ecx + rx1, ecy - ry1), col, 1.5f);
        }
    };

    // XY plane (S1-S2)
    drawEllipseWire(a, b, 0, IM_COL32(231, 76, 60, 200));
    // XZ plane (S1-S3) rotated 90 deg conceptually shown tilted
    drawEllipseWire(a, c * 0.7f, 0, IM_COL32(52, 152, 219, 150));
    // YZ plane (S2-S3)
    drawEllipseWire(b * 0.7f, c, 90, IM_COL32(46, 204, 113, 150));

    // Labels
    char s1l[32], s2l[32], s3l[32];
    snprintf(s1l, sizeof(s1l), "S1=%.1f", s1);
    snprintf(s2l, sizeof(s2l), "S2=%.1f", s2);
    snprintf(s3l, sizeof(s3l), "S3=%.1f", s3);
    dl->AddText(ImVec2(ecx + a + 5, ecy - 10), IM_COL32(231,76,60,255), s1l);
    dl->AddText(ImVec2(ecx - 20, ecy - b - 15), IM_COL32(46,204,113,255), s2l);
    dl->AddText(ImVec2(ecx + 5, ecy + c*0.7f + 5), IM_COL32(52,152,219,255), s3l);

    ImGui::EndChild();
}

// ============================================================
// Motion Tab: displacement/velocity/acceleration with XYZ
// ============================================================
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

    static int motionQty = 0;
    static bool showXYZ = false;
    ImGui::RadioButton("Displacement", &motionQty, 0); ImGui::SameLine();
    ImGui::RadioButton("Velocity", &motionQty, 1); ImGui::SameLine();
    ImGui::RadioButton("Acceleration", &motionQty, 2); ImGui::SameLine();
    ImGui::Checkbox("Show XYZ", &showXYZ);

    const char* yLabels[] = {"Displacement (mm)", "Velocity (mm/s)", "Acceleration (mm/s^2)"};

    ImVec2 sz(ImGui::GetContentRegionAvail().x, std::max(250.0f, ImGui::GetContentRegionAvail().y - 40.0f));
    if (ImPlot::BeginPlot("##Motion", sz)) {
        ImPlot::SetupAxes("Time", yLabels[motionQty]);

        for (const auto& ms : data_.motion) {
            if (ms.t.empty()) continue;
            bool show = selectedParts_.empty() || selectedParts_.count(ms.part_id);
            if (!show) continue;

            int n = (int)ms.t.size();
            char label[64];

            // Magnitude
            const std::vector<double>* mag = nullptr;
            switch (motionQty) {
                case 0: mag = &ms.disp_mag; break;
                case 1: mag = &ms.vel_mag; break;
                case 2: mag = &ms.acc_mag; break;
            }
            if (mag && (int)mag->size() == n) {
                snprintf(label, sizeof(label), "P%d avg", ms.part_id);
                ImPlot::PlotLine(label, ms.t.data(), mag->data(), n);
            }

            // Max displacement (node with largest disp)
            if (motionQty == 0 && !ms.max_disp_mag.empty() && (int)ms.max_disp_mag.size() == n) {
                snprintf(label, sizeof(label), "P%d max", ms.part_id);
                ImPlot::PlotLine(label, ms.t.data(), ms.max_disp_mag.data(), n);
            }

            // XYZ components
            if (showXYZ) {
                const std::vector<double>*cx=nullptr, *cy=nullptr, *cz=nullptr;
                switch (motionQty) {
                    case 0: cx=&ms.disp_x; cy=&ms.disp_y; cz=&ms.disp_z; break;
                    case 1: cx=&ms.vel_x; cy=&ms.vel_y; cz=&ms.vel_z; break;
                    case 2: cx=&ms.acc_x; cy=&ms.acc_y; cz=&ms.acc_z; break;
                }
                if (cx && (int)cx->size() == n) { snprintf(label, sizeof(label), "P%d X", ms.part_id); ImPlot::PlotLine(label, ms.t.data(), cx->data(), n); }
                if (cy && (int)cy->size() == n) { snprintf(label, sizeof(label), "P%d Y", ms.part_id); ImPlot::PlotLine(label, ms.t.data(), cy->data(), n); }
                if (cz && (int)cz->size() == n) { snprintf(label, sizeof(label), "P%d Z", ms.part_id); ImPlot::PlotLine(label, ms.t.data(), cz->data(), n); }
            }
        }

        ImPlot::EndPlot();
    }
}

// ============================================================
// Energy Tab: energy balance + ratio + warnings
// ============================================================
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
        if ((int)g.kinetic_energy.size() == n)  ImPlot::PlotLine("Kinetic", g.t.data(), g.kinetic_energy.data(), n);
        if ((int)g.internal_energy.size() == n) ImPlot::PlotLine("Internal", g.t.data(), g.internal_energy.data(), n);
        if ((int)g.total_energy.size() == n)    ImPlot::PlotLine("Total", g.t.data(), g.total_energy.data(), n);
        if ((int)g.hourglass_energy.size() == n) ImPlot::PlotLine("Hourglass", g.t.data(), g.hourglass_energy.data(), n);
        ImPlot::EndPlot();
    }

    // Energy ratio chart
    if (!g.energy_ratio.empty() && (int)g.energy_ratio.size() == n) {
        ImGui::TextColored(COL_DIM, "Energy Ratio (internal/total)");
        ImVec2 sz2(ImGui::GetContentRegionAvail().x, std::max(80.0f, (ImGui::GetContentRegionAvail().y - 60.0f) * 0.5f));
        if (ImPlot::BeginPlot("##EnergyRatio", sz2)) {
            ImPlot::SetupAxes("Time", "Ratio");
            ImPlot::PlotLine("E_ratio", g.t.data(), g.energy_ratio.data(), n);
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
void DeepReportApp::renderQualityTab() {
    if (data_.element_quality.empty()) {
        ImGui::TextColored(COL_DIM, "No element quality data");
        return;
    }

    ImGui::TextColored(COL_DIM,
        "Aspect Ratio: edge length ratio (>10 = poor). Jacobian: element shape quality (1.0 = ideal, <0.5 = poor).\n"
        "Warpage: out-of-plane angle for quads (deg). Skewness: deviation from ideal shape (0 = ideal, 1 = degenerate).");
    ImGui::Spacing();

    ImGui::TextColored(COL_ACCENT, "  Element Quality Metrics");
    ImGui::Separator();
    ImGui::Spacing();

    if (ImGui::BeginTable("##QualTable", 7,
            ImGuiTableFlags_RowBg | ImGuiTableFlags_Sortable |
            ImGuiTableFlags_ScrollY | ImGuiTableFlags_SizingStretchProp |
            ImGuiTableFlags_BordersInnerV)) {

        ImGui::TableSetupScrollFreeze(0, 1);
        ImGui::TableSetupColumn("Part", ImGuiTableColumnFlags_WidthFixed, 50);
        ImGui::TableSetupColumn("Name", ImGuiTableColumnFlags_WidthStretch);
        ImGui::TableSetupColumn("Elements", ImGuiTableColumnFlags_WidthFixed, 70);
        ImGui::TableSetupColumn("Aspect Ratio", ImGuiTableColumnFlags_WidthFixed, 90);
        ImGui::TableSetupColumn("Jacobian", ImGuiTableColumnFlags_WidthFixed, 70);
        ImGui::TableSetupColumn("Warpage", ImGuiTableColumnFlags_WidthFixed, 70);
        ImGui::TableSetupColumn("Skewness", ImGuiTableColumnFlags_WidthFixed, 70);
        ImGui::TableHeadersRow();

        for (const auto& q : data_.element_quality) {
            ImGui::TableNextRow();
            ImGui::TableSetColumnIndex(0); ImGui::Text("%d", q.part_id);
            ImGui::TableSetColumnIndex(1); ImGui::TextUnformatted(q.part_name.c_str());
            ImGui::TableSetColumnIndex(2); ImGui::Text("%d", q.num_elements);
            ImGui::TableSetColumnIndex(3);
            ImGui::TextColored(q.peak_aspect_ratio > 10 ? COL_RED : q.peak_aspect_ratio > 5 ? COL_YELLOW : COL_ACCENT, "%.1f", q.peak_aspect_ratio);
            ImGui::TableSetColumnIndex(4);
            ImGui::TextColored(q.min_jacobian < 0.5 ? COL_RED : q.min_jacobian < 0.7 ? COL_YELLOW : COL_ACCENT, "%.3f", q.min_jacobian);
            ImGui::TableSetColumnIndex(5); ImGui::Text("%.1f", q.peak_warpage);
            ImGui::TableSetColumnIndex(6); ImGui::Text("%.3f", q.peak_skewness);
        }

        ImGui::EndTable();
    }
}

// ============================================================
// Render Gallery
// ============================================================
// Helper: parse section view folder name
static std::string parseSectionLabel(const std::string& folder) {
    // section_view_part_10_z → "Part 10 — Z"
    // section_view_z → "Overview — Z"
    size_t pp = folder.find("part_");
    size_t lu = folder.rfind('_');
    if (pp != std::string::npos && lu > pp + 5) {
        std::string pid = folder.substr(pp + 5, lu - pp - 5);
        std::string axis = folder.substr(lu + 1);
        for (auto& c : axis) c = toupper(c);
        return "Part " + pid + " — " + axis;
    }
    if (lu != std::string::npos && lu > 0) {
        std::string axis = folder.substr(lu + 1);
        for (auto& c : axis) c = toupper(c);
        return "Overview — " + axis;
    }
    return folder;
}

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

void DeepReportApp::renderRenderGalleryTab() {
    // Check fullscreen first
    if (videoFullscreen_) renderVideoFullscreen();

    if (data_.render_files.empty()) {
        ImGui::TextColored(COL_DIM, "No render files found");
        return;
    }

    // ── Top: horizontal scrollable card strip ──
    ImGui::TextColored(COL_ACCENT, "Section View Renders");
    ImGui::Spacing();

    float cardH = 36;
    ImGui::BeginChild("RenderStrip", ImVec2(-1, cardH + 8), false, ImGuiWindowFlags_HorizontalScrollbar);

    int idx = 0;
    for (const auto& f : data_.render_files) {
        namespace fs = std::filesystem;
        std::string folder = fs::path(f).parent_path().filename().string();
        std::string label = parseSectionLabel(folder);
        bool isActive = (activeVideo_ == f);

        ImGui::PushID(idx++);
        if (isActive) {
            ImGui::PushStyleColor(ImGuiCol_Button, ImVec4(0.15f, 0.30f, 0.50f, 1.0f));
            ImGui::PushStyleColor(ImGuiCol_ButtonHovered, ImVec4(0.20f, 0.35f, 0.55f, 1.0f));
        } else {
            ImGui::PushStyleColor(ImGuiCol_Button, COL_CARD);
            ImGui::PushStyleColor(ImGuiCol_ButtonHovered, ImVec4(0.15f, 0.20f, 0.32f, 1.0f));
        }

        if (ImGui::Button(label.c_str(), ImVec2(0, cardH))) {
            if (activeVideo_ != f) {
                activeVideo_ = f;
                if (players_.find(f) == players_.end()) {
                    auto vp = std::make_unique<VideoPlayer>();
                    if (vp->open(f)) {
                        vp->play();
                        players_[f] = std::move(vp);
                    }
                } else {
                    players_[f]->setFrame(0);
                    players_[f]->play();
                }
            }
        }
        ImGui::PopStyleColor(2);
        ImGui::SameLine();
        ImGui::PopID();
    }

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

    ImGui::Text("Part:"); ImGui::SameLine();
    ImGui::SetNextItemWidth(300);
    auto it = data_.parts.find(deepDivePartId_);
    std::string currentLabel = it != data_.parts.end()
        ? ("Part " + std::to_string(deepDivePartId_) + " — " + it->second.name) : "Select";
    if (ImGui::BeginCombo("##ddPart", currentLabel.c_str())) {
        for (auto& [pid, ps] : data_.parts) {
            char label[128]; snprintf(label, sizeof(label), "Part %d — %s", pid, ps.name.c_str());
            if (ImGui::Selectable(label, deepDivePartId_ == pid))
                deepDivePartId_ = pid;
        }
        ImGui::EndCombo();
    }

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

    // Additional info
    if (ps.time_of_peak_stress > 0)
        ImGui::Text("  Peak stress at t=%.6f, Element #%d", ps.time_of_peak_stress, ps.peak_element_id);
    if (ps.peak_max_principal != 0)
        ImGui::Text("  Principal: S1=%.1f  S3=%.1f MPa", ps.peak_max_principal, ps.peak_min_principal);
    if (ps.peak_max_principal_strain != 0)
        ImGui::Text("  Principal Strain: e1=%.4f  e3=%.4f", ps.peak_max_principal_strain, ps.peak_min_principal_strain);

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
            if (data_.yield_stress > 0) {
                double xt[] = {t.front(), t.back()}, yt[] = {data_.yield_stress, data_.yield_stress};
                ImPlot::PlotLine("Yield", xt, yt, 2);
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
            ImPlot::EndPlot();
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

        // Velocity
        if (!motion->vel_mag.empty()) {
            if (ImPlot::BeginPlot("##DDVel", ImVec2(-1, 160))) {
                ImPlot::SetupAxes("Time", "Velocity (mm/s)");
                ImPlot::PlotLine("|V|", motion->t.data(), motion->vel_mag.data(), n);
                ImPlot::EndPlot();
            }
        }

        // Acceleration
        if (!motion->acc_mag.empty()) {
            if (ImPlot::BeginPlot("##DDAcc", ImVec2(-1, 160))) {
                ImPlot::SetupAxes("Time", "Acceleration");
                ImPlot::PlotLine("|A|", motion->t.data(), motion->acc_mag.data(), n);
                ImPlot::EndPlot();
            }
        }
    }
}

// ============================================================
// Contact Tab
// ============================================================
void DeepReportApp::renderContactTab() {
    ImGui::TextColored(COL_DIM,
        "Contact interface forces from binout. Peak force indicates maximum contact load.\n"
        "Sliding energy shows energy dissipated by friction at each interface.");
    ImGui::Spacing();

    // rcforc: contact force time histories
    if (!data_.rcforc.empty()) {
        ImGui::TextColored(COL_ACCENT, "  Contact Forces (rcforc)");
        ImGui::Separator();

        // Peak force ranking
        for (const auto& ci : data_.rcforc) {
            char label[128];
            snprintf(label, sizeof(label), "  Interface %d: %s — Peak: %.1f N", ci.id, ci.name.c_str(), ci.peak_fmag);
            ImGui::TextUnformatted(label);
        }
        ImGui::Spacing();

        // Force magnitude chart
        if (!data_.rcforc.empty() && !data_.rcforc[0].t.empty()) {
            ImVec2 sz(ImGui::GetContentRegionAvail().x, std::max(200.0f, ImGui::GetContentRegionAvail().y * 0.4f));
            if (ImPlot::BeginPlot("##ContactForce", sz)) {
                ImPlot::SetupAxes("Time", "Force Magnitude (N)");
                for (const auto& ci : data_.rcforc) {
                    if (ci.fmag.empty()) continue;
                    char label[64]; snprintf(label, sizeof(label), "Ifc %d %s", ci.id, ci.name.c_str());
                    ImPlot::PlotLine(label, ci.t.data(), ci.fmag.data(), (int)ci.t.size());
                }
                ImPlot::EndPlot();
            }
        }
    }

    // sleout: sliding energy
    if (!data_.sleout.empty()) {
        ImGui::TextColored(COL_YELLOW, "  Sliding Energy (sleout)");
        ImGui::Separator();

        if (!data_.sleout[0].t.empty()) {
            ImVec2 sz(ImGui::GetContentRegionAvail().x, std::max(150.0f, ImGui::GetContentRegionAvail().y - 10));
            if (ImPlot::BeginPlot("##SlidingEnergy", sz)) {
                ImPlot::SetupAxes("Time", "Energy");
                for (const auto& se : data_.sleout) {
                    if (se.total_energy.empty()) continue;
                    char label[64]; snprintf(label, sizeof(label), "Ifc %d total", se.id);
                    ImPlot::PlotLine(label, se.t.data(), se.total_energy.data(), (int)se.t.size());
                    if (!se.friction_energy.empty()) {
                        snprintf(label, sizeof(label), "Ifc %d friction", se.id);
                        ImPlot::PlotLine(label, se.t.data(), se.friction_energy.data(), (int)se.t.size());
                    }
                }
                ImPlot::EndPlot();
            }
        }
    }
}

// ============================================================
// SysInfo Tab
// ============================================================
void DeepReportApp::renderSysInfoTab() {
    ImGui::TextColored(COL_ACCENT, "  Simulation Information");
    ImGui::Separator();
    ImGui::Spacing();

    auto infoRow = [](const char* label, const char* value) {
        ImGui::Text("  %-24s", label);
        ImGui::SameLine(220);
        ImGui::TextColored(ImVec4(0.85f,0.85f,0.90f,1), "%s", value);
    };

    char buf[256];
    infoRow("Label:", data_.label.c_str());
    snprintf(buf, sizeof(buf), "Tier %d", data_.tier);
    infoRow("Tier:", buf);
    infoRow("D3plot Path:", data_.d3plot_path.c_str());
    snprintf(buf, sizeof(buf), "%d", data_.num_states);
    infoRow("States:", buf);
    snprintf(buf, sizeof(buf), "%.6f — %.6f", data_.start_time, data_.end_time);
    infoRow("Time Range:", buf);
    snprintf(buf, sizeof(buf), "%d", (int)data_.parts.size());
    infoRow("Parts:", buf);
    infoRow("Termination:", data_.normal_termination ? "Normal" : "ERROR");
    infoRow("Termination Source:", data_.termination_source.c_str());
    if (data_.yield_stress > 0) {
        snprintf(buf, sizeof(buf), "%.1f MPa", data_.yield_stress);
        infoRow("Yield Stress:", buf);
    }

    ImGui::Spacing();
    ImGui::TextColored(COL_ACCENT, "  Data Files");
    ImGui::Separator();
    ImGui::Spacing();

    auto fileRow = [](const char* name, bool present) {
        ImGui::Text("  %-20s", name);
        ImGui::SameLine(200);
        if (present)
            ImGui::TextColored(ImVec4(0.31f,0.80f,0.64f,1), "Present");
        else
            ImGui::TextColored(ImVec4(0.55f,0.55f,0.62f,1), "Not found");
    };

    fileRow("analysis_result.json", !data_.stress.empty());
    fileRow("result.json", !data_.parts.empty() || !data_.glstat.t.empty());
    fileRow("motion/ CSVs", !data_.motion.empty());
    fileRow("renders/", !data_.render_files.empty());
    fileRow("binout (rcforc)", !data_.rcforc.empty());
    fileRow("binout (sleout)", !data_.sleout.empty());
    fileRow("element_quality", !data_.element_quality.empty());
    fileRow("tensors", !data_.tensors.empty());

    ImGui::Spacing();
    ImGui::TextColored(COL_ACCENT, "  Analysis Summary");
    ImGui::Separator();
    ImGui::Spacing();
    snprintf(buf, sizeof(buf), "%d stress + %d strain + %d principal + %d tensor + %d motion",
        (int)data_.stress.size(), (int)data_.strain.size(),
        (int)data_.max_principal.size(), (int)data_.tensors.size(),
        (int)data_.motion.size());
    infoRow("Time Series:", buf);
    snprintf(buf, sizeof(buf), "%d rcforc + %d sleout", (int)data_.rcforc.size(), (int)data_.sleout.size());
    infoRow("Contact:", buf);
    snprintf(buf, sizeof(buf), "%d render files", (int)data_.render_files.size());
    infoRow("Renders:", buf);
}

// ============================================================
// 3D Viewer — shaders
// ============================================================
static const char* VERT3D = R"(
#version 330 core
layout(location=0) in vec3 aPos;
layout(location=1) in vec3 aNorm;
layout(location=2) in float aFringe;
uniform mat4 uMVP;
uniform mat3 uNormalMat;
out vec3 vNorm;
out float vFringe;
void main() {
    gl_Position = uMVP * vec4(aPos, 1.0);
    vNorm = normalize(uNormalMat * aNorm);
    vFringe = aFringe;
}
)";

static const char* FRAG3D = R"(
#version 330 core
in vec3 vNorm;
in float vFringe;
uniform sampler1D uColormap;
uniform vec3 uLightDir;
uniform float uAmbient;
uniform int uUseFringe;
uniform vec3 uFlatColor;
out vec4 fragColor;
void main() {
    vec3 color;
    if (uUseFringe == 1)
        color = texture(uColormap, clamp(vFringe, 0.0, 1.0)).rgb;
    else
        color = uFlatColor;
    vec3 N = normalize(vNorm);
    float diff = abs(dot(N, uLightDir));
    color *= uAmbient + (1.0 - uAmbient) * diff;
    fragColor = vec4(color, 1.0);
}
)";

static void buildJetColormap(unsigned char* data) {
    for (int i = 0; i < 256; ++i) {
        float t = i / 255.0f;
        float r, g, b;
        if (t < 0.25f) { r = 0; g = t/0.25f; b = 1; }
        else if (t < 0.5f) { r = 0; g = 1; b = 1-(t-0.25f)/0.25f; }
        else if (t < 0.75f) { r = (t-0.5f)/0.25f; g = 1; b = 0; }
        else { r = 1; g = 1-(t-0.75f)/0.25f; b = 0; }
        data[i*3+0] = (unsigned char)(r*255);
        data[i*3+1] = (unsigned char)(g*255);
        data[i*3+2] = (unsigned char)(b*255);
    }
}

void DeepReportApp::init3DViewer() {
    if (data_.d3plot_path.empty()) return;
    if (!sim3d_.loadMesh(data_.d3plot_path)) {
        std::cout << "[3D] Failed to load mesh: " << sim3d_.loadError << "\n";
        return;
    }
    std::cout << "[3D] Mesh: " << sim3d_.mesh.nodes.size() << " nodes, "
              << sim3d_.extFaces.size() << " exterior faces\n";

    sim3d_.loadStatesAsync(data_.d3plot_path, 4);

    shader3d_.loadFromString(VERT3D, FRAG3D);

    // Colormap texture
    glGenTextures(1, &colormapTex_);
    glBindTexture(GL_TEXTURE_1D, colormapTex_);
    unsigned char cmapData[256*3];
    buildJetColormap(cmapData);
    glTexImage1D(GL_TEXTURE_1D, 0, GL_RGB, 256, 0, GL_RGB, GL_UNSIGNED_BYTE, cmapData);
    glTexParameteri(GL_TEXTURE_1D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
    glTexParameteri(GL_TEXTURE_1D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
    glTexParameteri(GL_TEXTURE_1D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);

    auto gpuFaces = sim3d_.buildGPUFaces();
    meshGPU_.build(sim3d_.initialCoords, gpuFaces);

    camera3d_.fitTo(meshGPU_.bboxMin[0], meshGPU_.bboxMin[1], meshGPU_.bboxMin[2],
                    meshGPU_.bboxMax[0], meshGPU_.bboxMax[1], meshGPU_.bboxMax[2]);

    mesh3dReady_ = true;
}

void DeepReportApp::ensureFBO(int w, int h) {
    if (w == fboW_ && h == fboH_ && fbo3d_) return;
    if (fbo3d_) { glDeleteFramebuffers(1, &fbo3d_); glDeleteTextures(1, &fboTex3d_); glDeleteRenderbuffers(1, &fboDepth3d_); }

    fboW_ = w; fboH_ = h;
    glGenFramebuffers(1, &fbo3d_);
    glBindFramebuffer(GL_FRAMEBUFFER, fbo3d_);

    glGenTextures(1, &fboTex3d_);
    glBindTexture(GL_TEXTURE_2D, fboTex3d_);
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, w, h, 0, GL_RGBA, GL_UNSIGNED_BYTE, nullptr);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
    glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, fboTex3d_, 0);

    glGenRenderbuffers(1, &fboDepth3d_);
    glBindRenderbuffer(GL_RENDERBUFFER, fboDepth3d_);
    glRenderbufferStorage(GL_RENDERBUFFER, GL_DEPTH24_STENCIL8, w, h);
    glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_DEPTH_STENCIL_ATTACHMENT, GL_RENDERBUFFER, fboDepth3d_);

    glBindFramebuffer(GL_FRAMEBUFFER, 0);
}

void DeepReportApp::setPresetView(int axis) {
    camera3d_.fitTo(meshGPU_.bboxMin[0], meshGPU_.bboxMin[1], meshGPU_.bboxMin[2],
                    meshGPU_.bboxMax[0], meshGPU_.bboxMax[1], meshGPU_.bboxMax[2]);
    constexpr float PI = 3.14159265f;
    switch (axis) {
        case 0: camera3d_.yaw = 0;       camera3d_.pitch = 0;      break;  // Front (-Z)
        case 1: camera3d_.yaw = PI;      camera3d_.pitch = 0;      break;  // Back (+Z)
        case 2: camera3d_.yaw = PI/2;    camera3d_.pitch = 0;      break;  // Right (+X)
        case 3: camera3d_.yaw = -PI/2;   camera3d_.pitch = 0;      break;  // Left (-X)
        case 4: camera3d_.yaw = 0;       camera3d_.pitch = PI/2-0.01f; break; // Top (+Y)
        case 5: camera3d_.yaw = 0;       camera3d_.pitch = -PI/2+0.01f; break; // Bottom (-Y)
    }
}

void DeepReportApp::render3DTab() {
    // Lazy init
    if (!mesh3dReady_ && !data_.d3plot_path.empty()) {
        static bool initAttempted = false;
        if (!initAttempted) {
            initAttempted = true;
            init3DViewer();
        }
    }

    if (!mesh3dReady_) {
        ImGui::TextColored(COL_DIM, "No d3plot path in result data (need result.json with d3plot_path)");
        ImGui::TextColored(COL_DIM, "Path: %s", data_.d3plot_path.c_str());
        return;
    }

    // Controls row
    const char* viewNames[] = {"Front", "Back", "Right", "Left", "Top", "Bottom"};
    for (int i = 0; i < 6; ++i) {
        if (i > 0) ImGui::SameLine();
        if (ImGui::Button(viewNames[i])) setPresetView(i);
    }
    ImGui::SameLine();
    ImGui::Checkbox("Fringe", &show3DFringe_);
    ImGui::SameLine();
    ImGui::Checkbox("Wire", &wireframe3d_);

    if (sim3d_.statesLoaded && sim3d_.numStates() > 0) {
        ImGui::SameLine();
        if (ImGui::Button(playing3d_ ? "Pause" : "Play")) playing3d_ = !playing3d_;
        ImGui::SameLine();
        ImGui::SetNextItemWidth(200);
        ImGui::SliderInt("##state3d", &current3DState_, 0, sim3d_.numStates() - 1);
        ImGui::SameLine();
        ImGui::Text("t=%.6f", sim3d_.stateTime(current3DState_));

        // Playback
        if (playing3d_) {
            playTimer3d_ += ImGui::GetIO().DeltaTime;
            if (playTimer3d_ > 1.0f / 30.0f) {
                playTimer3d_ = 0;
                current3DState_ = (current3DState_ + 1) % sim3d_.numStates();
            }
        }

        // Update mesh
        auto coords = sim3d_.getDeformedCoords(current3DState_);
        std::vector<float> fringe;
        if (show3DFringe_) fringe = sim3d_.getVonMisesFringe(current3DState_);
        meshGPU_.updatePositions(coords, fringe);
    } else if (!sim3d_.statesLoaded) {
        ImGui::SameLine();
        ImGui::TextColored(COL_DIM, "Loading states...");
    }

    // Render to FBO
    ImVec2 avail = ImGui::GetContentRegionAvail();
    int vpW = std::max(100, (int)avail.x);
    int vpH = std::max(100, (int)avail.y);
    ensureFBO(vpW, vpH);

    // Mouse interaction on viewport
    ImVec2 vpPos = ImGui::GetCursorScreenPos();
    ImGui::InvisibleButton("##3dvp", avail);
    bool vpHovered = ImGui::IsItemHovered();

    if (vpHovered) {
        ImGuiIO& io = ImGui::GetIO();
        if (ImGui::IsMouseDragging(ImGuiMouseButton_Left)) {
            ImVec2 d = io.MouseDelta;
            camera3d_.orbit(-d.x * 0.005f, -d.y * 0.005f);
        }
        if (ImGui::IsMouseDragging(ImGuiMouseButton_Middle)) {
            ImVec2 d = io.MouseDelta;
            camera3d_.pan(-d.x, d.y);
        }
        if (io.MouseWheel != 0)
            camera3d_.zoom(io.MouseWheel > 0 ? 0.9f : 1.1f);
    }

    camera3d_.aspect = (float)vpW / vpH;
    camera3d_.update();

    // Render to FBO
    glBindFramebuffer(GL_FRAMEBUFFER, fbo3d_);
    glViewport(0, 0, vpW, vpH);
    glClearColor(0.08f, 0.08f, 0.14f, 1.0f);
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT);
    glEnable(GL_DEPTH_TEST);

    if (wireframe3d_) glPolygonMode(GL_FRONT_AND_BACK, GL_LINE);

    shader3d_.use();
    shader3d_.setMat4("uMVP", camera3d_.mvp);
    shader3d_.setMat3("uNormalMat", camera3d_.normalMat);
    shader3d_.setVec3("uLightDir", 0.3f, 0.8f, 0.5f);
    shader3d_.setFloat("uAmbient", 0.3f);
    shader3d_.setInt("uUseFringe", show3DFringe_ ? 1 : 0);

    glActiveTexture(GL_TEXTURE0);
    glBindTexture(GL_TEXTURE_1D, colormapTex_);
    shader3d_.setInt("uColormap", 0);

    for (size_t i = 0; i < meshGPU_.partCount(); ++i) {
        const auto& p = meshGPU_.part(i);
        if (!p.visible) continue;
        if (!show3DFringe_)
            shader3d_.setVec3("uFlatColor", p.color[0], p.color[1], p.color[2]);
        glBindVertexArray(p.vao);
        glDrawElements(GL_TRIANGLES, p.indexCount, GL_UNSIGNED_INT, nullptr);
    }

    if (wireframe3d_) glPolygonMode(GL_FRONT_AND_BACK, GL_FILL);
    glBindFramebuffer(GL_FRAMEBUFFER, 0);

    // Draw FBO texture as ImGui image
    ImGui::SetCursorScreenPos(vpPos);
    ImGui::Image((ImTextureID)(intptr_t)fboTex3d_, avail, ImVec2(0,1), ImVec2(1,0));
}
