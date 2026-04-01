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

    // Custom dark theme
    ImGui::StyleColorsDark();
    auto& s = ImGui::GetStyle();
    s.WindowRounding = 6.0f;
    s.FrameRounding = 4.0f;
    s.TabRounding = 4.0f;
    s.GrabRounding = 3.0f;
    s.WindowBorderSize = 0.0f;
    s.FrameBorderSize = 0.0f;
    s.ItemSpacing = ImVec2(10, 6);
    s.WindowPadding = ImVec2(12, 10);

    s.Colors[ImGuiCol_WindowBg]       = {0.08f, 0.08f, 0.14f, 1.0f};
    s.Colors[ImGuiCol_ChildBg]        = {0.10f, 0.10f, 0.18f, 1.0f};
    s.Colors[ImGuiCol_PopupBg]        = {0.10f, 0.10f, 0.18f, 0.95f};
    s.Colors[ImGuiCol_Border]         = {0.17f, 0.17f, 0.29f, 1.0f};
    s.Colors[ImGuiCol_FrameBg]        = {0.12f, 0.12f, 0.22f, 1.0f};
    s.Colors[ImGuiCol_FrameBgHovered] = {0.16f, 0.16f, 0.28f, 1.0f};
    s.Colors[ImGuiCol_FrameBgActive]  = {0.20f, 0.20f, 0.35f, 1.0f};
    s.Colors[ImGuiCol_TitleBg]        = {0.08f, 0.08f, 0.14f, 1.0f};
    s.Colors[ImGuiCol_TitleBgActive]  = {0.10f, 0.12f, 0.22f, 1.0f};
    s.Colors[ImGuiCol_Tab]            = {0.10f, 0.10f, 0.18f, 1.0f};
    s.Colors[ImGuiCol_TabSelected]    = {0.15f, 0.20f, 0.35f, 1.0f};
    s.Colors[ImGuiCol_TabHovered]     = {0.20f, 0.25f, 0.40f, 1.0f};
    s.Colors[ImGuiCol_Header]         = {0.15f, 0.20f, 0.35f, 1.0f};
    s.Colors[ImGuiCol_HeaderHovered]  = {0.20f, 0.25f, 0.42f, 1.0f};
    s.Colors[ImGuiCol_HeaderActive]   = {0.25f, 0.30f, 0.50f, 1.0f};
    s.Colors[ImGuiCol_TableHeaderBg]  = {0.06f, 0.21f, 0.37f, 1.0f};
    s.Colors[ImGuiCol_TableRowBg]     = {0.0f, 0.0f, 0.0f, 0.0f};
    s.Colors[ImGuiCol_TableRowBgAlt]  = {0.10f, 0.10f, 0.18f, 0.5f};

    // ImPlot style
    ImPlot::StyleColorsDark();
    auto& ps = ImPlot::GetStyle();
    ps.MinorAlpha = 0.15f;

    ImGui_ImplGlfw_InitForOpenGL(window_, true);
    ImGui_ImplOpenGL3_Init("#version 330");

    // Load CJK font for Korean text
    {
        const char* fontPaths[] = {
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Medium.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-DemiLight.ttc",
            "C:\\Windows\\Fonts\\malgun.ttf",  // Windows fallback
            nullptr
        };
        for (int i = 0; fontPaths[i]; ++i) {
            if (std::filesystem::exists(fontPaths[i])) {
                io.Fonts->AddFontFromFileTTF(fontPaths[i], 15.0f, nullptr,
                    io.Fonts->GetGlyphRangesKorean());
                std::cout << "[DeepReport] Loaded font: " << fontPaths[i] << "\n";
                break;
            }
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
            if (!data_.element_quality.empty()) {
                if (ImGui::BeginTabItem("Quality")) { renderQualityTab(); ImGui::EndTabItem(); }
            }
            if (ImGui::BeginTabItem("Renders"))   { renderRenderGalleryTab(); ImGui::EndTabItem(); }
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

    // Time series: stress overlay
    ImGui::TextColored(COL_ACCENT, "  Stress Time History");
    ImGui::Separator();
    drawTimeSeriesPlot("##StressTS", "Von Mises (MPa)", data_.stress, false);

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
void DeepReportApp::renderTensorTab() {
    if (data_.tensors.empty()) {
        ImGui::TextColored(COL_DIM, "No peak element tensor data");
        return;
    }

    static int selectedTensor = 0;
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
            if (ImGui::Selectable(label, selectedTensor == i)) selectedTensor = i;
        }
        ImGui::EndCombo();
    }

    auto& t = data_.tensors[selectedTensor];
    int n = (int)t.time.size();
    if (n == 0) return;

    ImGui::Text("Peak: %.2f MPa at t=%.6f", t.peak_value, t.peak_time);
    ImGui::Spacing();

    // 6-component chart
    ImVec2 sz(ImGui::GetContentRegionAvail().x, std::max(250.0f, ImGui::GetContentRegionAvail().y * 0.45f));
    if (ImPlot::BeginPlot("##TensorComponents", sz)) {
        ImPlot::SetupAxes("Time", "Stress (MPa)");
        if ((int)t.sxx.size() == n) ImPlot::PlotLine("Sxx", t.time.data(), t.sxx.data(), n);
        if ((int)t.syy.size() == n) ImPlot::PlotLine("Syy", t.time.data(), t.syy.data(), n);
        if ((int)t.szz.size() == n) ImPlot::PlotLine("Szz", t.time.data(), t.szz.data(), n);
        if ((int)t.sxy.size() == n) ImPlot::PlotLine("Sxy", t.time.data(), t.sxy.data(), n);
        if ((int)t.syz.size() == n) ImPlot::PlotLine("Syz", t.time.data(), t.syz.data(), n);
        if ((int)t.szx.size() == n) ImPlot::PlotLine("Szx", t.time.data(), t.szx.data(), n);
        ImPlot::EndPlot();
    }
}

// ============================================================
// Motion Tab: displacement/velocity/acceleration with XYZ
// ============================================================
void DeepReportApp::renderMotionTab() {
    if (data_.motion.empty()) {
        ImGui::TextColored(COL_DIM, "No motion data (no motion/ CSV files)");
        return;
    }

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
