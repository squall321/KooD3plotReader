#include "app/DeepReportApp.hpp"

#include <glad/glad.h>
#include <GLFW/glfw3.h>
#include <imgui.h>
#include <imgui_impl_glfw.h>
#include <imgui_impl_opengl3.h>
#include <implot.h>

#include <iostream>
#include <cstdio>
#include <algorithm>

bool DeepReportApp::init(int width, int height) {
    if (!glfwInit()) return false;

    glfwWindowHint(GLFW_CONTEXT_VERSION_MAJOR, 3);
    glfwWindowHint(GLFW_CONTEXT_VERSION_MINOR, 3);
    glfwWindowHint(GLFW_OPENGL_PROFILE, GLFW_OPENGL_CORE_PROFILE);

    window_ = glfwCreateWindow(width, height, "KooViewer — Deep Report", nullptr, nullptr);
    if (!window_) { glfwTerminate(); return false; }
    glfwMakeContextCurrent(window_);
    glfwSwapInterval(1);

    if (!gladLoadGLLoader((GLADloadproc)glfwGetProcAddress)) return false;

    IMGUI_CHECKVERSION();
    ImGui::CreateContext();
    ImPlot::CreateContext();

    ImGuiIO& io = ImGui::GetIO();
    io.ConfigFlags |= ImGuiConfigFlags_DockingEnable;

    // Dark theme
    ImGui::StyleColorsDark();
    auto& style = ImGui::GetStyle();
    style.WindowRounding = 6.0f;
    style.FrameRounding = 4.0f;
    style.TabRounding = 4.0f;
    style.GrabRounding = 3.0f;
    style.Colors[ImGuiCol_WindowBg] = ImVec4(0.06f, 0.07f, 0.09f, 1.0f);
    style.Colors[ImGuiCol_Tab] = ImVec4(0.10f, 0.11f, 0.14f, 1.0f);
    style.Colors[ImGuiCol_TabSelected] = ImVec4(0.20f, 0.25f, 0.35f, 1.0f);
    style.Colors[ImGuiCol_TitleBg] = ImVec4(0.08f, 0.09f, 0.12f, 1.0f);
    style.Colors[ImGuiCol_TitleBgActive] = ImVec4(0.12f, 0.14f, 0.20f, 1.0f);

    ImPlot::StyleColorsDark();

    ImGui_ImplGlfw_InitForOpenGL(window_, true);
    ImGui_ImplOpenGL3_Init("#version 330");

    return true;
}

void DeepReportApp::run(const std::string& outputDir) {
    std::cout << "[DeepReport] Loading: " << outputDir << "\n";
    if (!loadDeepReport(outputDir, data_)) {
        std::cerr << "[DeepReport] Failed: " << data_.error << "\n";
        // Still show the window with error message
    }

    std::cout << "[DeepReport] Loaded: " << data_.stress.size() << " stress series, "
              << data_.parts.size() << " parts, "
              << data_.motion.size() << " motion series\n";

    while (!glfwWindowShouldClose(window_)) {
        glfwPollEvents();

        ImGui_ImplOpenGL3_NewFrame();
        ImGui_ImplGlfw_NewFrame();
        ImGui::NewFrame();

        // Full-window dockspace
        ImGui::DockSpaceOverViewport(0, ImGui::GetMainViewport());

        // KPI bar
        renderKPIBar();

        // Part table (left panel)
        renderPartTable();

        // Chart panel (main area with tabs)
        ImGui::Begin("Charts");
        if (ImGui::BeginTabBar("ChartTabs")) {
            if (ImGui::BeginTabItem("Stress")) { renderStressChart(); ImGui::EndTabItem(); }
            if (ImGui::BeginTabItem("Strain")) { renderStrainChart(); ImGui::EndTabItem(); }
            if (ImGui::BeginTabItem("Motion")) { renderMotionChart(); ImGui::EndTabItem(); }
            if (ImGui::BeginTabItem("Energy")) { renderEnergyChart(); ImGui::EndTabItem(); }
            ImGui::EndTabBar();
        }
        ImGui::End();

        // Render gallery
        renderRenderGallery();

        ImGui::Render();

        int fbW, fbH;
        glfwGetFramebufferSize(window_, &fbW, &fbH);
        glViewport(0, 0, fbW, fbH);
        glClearColor(0.06f, 0.07f, 0.09f, 1.0f);
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
// KPI Bar
// ============================================================
void DeepReportApp::renderKPIBar() {
    ImGui::Begin("Summary", nullptr, ImGuiWindowFlags_NoScrollbar);

    auto kpiCard = [](const char* label, const char* fmt, double value, ImVec4 color) {
        ImGui::BeginGroup();
        ImGui::TextColored(ImVec4(0.55f, 0.58f, 0.65f, 1.0f), "%s", label);
        ImGui::TextColored(color, fmt, value);
        ImGui::EndGroup();
    };

    float w = ImGui::GetContentRegionAvail().x;
    float cardW = w / 5.0f - 8.0f;

    ImGui::Columns(5, nullptr, false);
    kpiCard("Peak Stress", "%.1f MPa", data_.peak_stress_global, ImVec4(0.48f, 0.81f, 1.0f, 1.0f));
    ImGui::NextColumn();
    kpiCard("Peak Strain", "%.4f", data_.peak_strain_global, ImVec4(0.49f, 0.81f, 0.50f, 1.0f));
    ImGui::NextColumn();
    kpiCard("Peak Disp", "%.2f mm", data_.peak_disp_global, ImVec4(0.82f, 0.63f, 1.0f, 1.0f));
    ImGui::NextColumn();
    kpiCard("Energy Ratio", "%.4f", data_.energy_ratio_min,
            data_.energy_ratio_min > 1.05 ? ImVec4(0.97f, 0.32f, 0.29f, 1.0f) : ImVec4(0.48f, 0.81f, 1.0f, 1.0f));
    ImGui::NextColumn();
    kpiCard("States", "%.0f", (double)data_.num_states, ImVec4(0.85f, 0.85f, 0.90f, 1.0f));
    ImGui::Columns(1);

    ImGui::End();
}

// ============================================================
// Part Table
// ============================================================
void DeepReportApp::renderPartTable() {
    ImGui::Begin("Parts");

    static char filterBuf[128] = "";
    ImGui::InputText("Filter", filterBuf, sizeof(filterBuf));
    ImGui::Separator();

    if (ImGui::BeginTable("PartTable", 5,
            ImGuiTableFlags_Sortable | ImGuiTableFlags_RowBg |
            ImGuiTableFlags_ScrollY | ImGuiTableFlags_Resizable)) {

        ImGui::TableSetupColumn("ID", ImGuiTableColumnFlags_DefaultSort, 40);
        ImGui::TableSetupColumn("Name", 0, 120);
        ImGui::TableSetupColumn("Stress", ImGuiTableColumnFlags_DefaultSort, 80);
        ImGui::TableSetupColumn("Strain", 0, 70);
        ImGui::TableSetupColumn("Disp", 0, 60);
        ImGui::TableHeadersRow();

        // Sort
        std::vector<std::pair<int, const PartSummary*>> sorted;
        std::string filter(filterBuf);
        std::transform(filter.begin(), filter.end(), filter.begin(), ::tolower);

        for (const auto& [pid, ps] : data_.parts) {
            if (!filter.empty()) {
                std::string lower = ps.name;
                std::transform(lower.begin(), lower.end(), lower.begin(), ::tolower);
                if (lower.find(filter) == std::string::npos) continue;
            }
            sorted.push_back({pid, &ps});
        }

        if (ImGuiTableSortSpecs* specs = ImGui::TableGetSortSpecs()) {
            if (specs->SpecsDirty && specs->SpecsCount > 0) {
                int col = specs->Specs[0].ColumnIndex;
                bool asc = (specs->Specs[0].SortDirection == ImGuiSortDirection_Ascending);
                std::sort(sorted.begin(), sorted.end(), [col, asc](const auto& a, const auto& b) {
                    double va = 0, vb = 0;
                    switch (col) {
                        case 0: va = a.first; vb = b.first; break;
                        case 2: va = a.second->peak_stress; vb = b.second->peak_stress; break;
                        case 3: va = a.second->peak_strain; vb = b.second->peak_strain; break;
                        case 4: va = a.second->peak_disp; vb = b.second->peak_disp; break;
                        default: return false;
                    }
                    return asc ? va < vb : va > vb;
                });
                specs->SpecsDirty = false;
            }
        }

        ImGuiListClipper clipper;
        clipper.Begin(static_cast<int>(sorted.size()));
        while (clipper.Step()) {
            for (int i = clipper.DisplayStart; i < clipper.DisplayEnd; ++i) {
                auto& [pid, ps] = sorted[i];
                ImGui::TableNextRow();

                bool isSelected = (selectedPartIdx_ == pid);
                ImGui::TableSetColumnIndex(0);
                char label[32];
                snprintf(label, sizeof(label), "%d", pid);
                if (ImGui::Selectable(label, isSelected, ImGuiSelectableFlags_SpanAllColumns)) {
                    selectedPartIdx_ = pid;
                }

                ImGui::TableSetColumnIndex(1);
                ImGui::Text("%s", ps->name.c_str());

                ImGui::TableSetColumnIndex(2);
                if (ps->stress_warning == "crit")
                    ImGui::TextColored(ImVec4(0.97f,0.32f,0.29f,1), "%.1f", ps->peak_stress);
                else if (ps->stress_warning == "warn")
                    ImGui::TextColored(ImVec4(0.88f,0.68f,0.26f,1), "%.1f", ps->peak_stress);
                else
                    ImGui::Text("%.1f", ps->peak_stress);

                ImGui::TableSetColumnIndex(3);
                ImGui::Text("%.4f", ps->peak_strain);

                ImGui::TableSetColumnIndex(4);
                ImGui::Text("%.2f", ps->peak_disp);
            }
        }

        ImGui::EndTable();
    }

    ImGui::End();
}

// ============================================================
// Charts
// ============================================================
void DeepReportApp::renderStressChart() {
    if (data_.stress.empty()) {
        ImGui::TextColored(ImVec4(0.5f,0.5f,0.5f,1), "No stress data");
        return;
    }

    if (ImPlot::BeginPlot("Von Mises Stress", ImVec2(-1, -1))) {
        ImPlot::SetupAxes("Time", "Stress (MPa)");

        for (const auto& ts : data_.stress) {
            if (ts.data.empty()) continue;

            std::vector<double> t(ts.data.size()), v(ts.data.size());
            for (size_t i = 0; i < ts.data.size(); ++i) {
                t[i] = ts.data[i].time;
                v[i] = ts.data[i].max_value;
            }

            bool highlight = (selectedPartIdx_ == ts.part_id || selectedPartIdx_ < 0);
            if (!highlight) continue;  // only show selected part (or all if none selected)

            char label[64];
            snprintf(label, sizeof(label), "Part %d %s", ts.part_id, ts.part_name.c_str());
            ImPlot::PlotLine(label, t.data(), v.data(), static_cast<int>(t.size()));
        }

        ImPlot::EndPlot();
    }
}

void DeepReportApp::renderStrainChart() {
    if (data_.strain.empty()) {
        ImGui::TextColored(ImVec4(0.5f,0.5f,0.5f,1), "No strain data");
        return;
    }

    if (ImPlot::BeginPlot("Effective Plastic Strain", ImVec2(-1, -1))) {
        ImPlot::SetupAxes("Time", "Strain");

        for (const auto& ts : data_.strain) {
            if (ts.data.empty()) continue;

            std::vector<double> t(ts.data.size()), v(ts.data.size());
            for (size_t i = 0; i < ts.data.size(); ++i) {
                t[i] = ts.data[i].time;
                v[i] = ts.data[i].max_value;
            }

            bool highlight = (selectedPartIdx_ == ts.part_id || selectedPartIdx_ < 0);
            if (!highlight) continue;  // only show selected part (or all if none selected)

            char label[64];
            snprintf(label, sizeof(label), "Part %d", ts.part_id);
            ImPlot::PlotLine(label, t.data(), v.data(), static_cast<int>(t.size()));
        }

        ImPlot::EndPlot();
    }
}

void DeepReportApp::renderMotionChart() {
    if (data_.motion.empty()) {
        ImGui::TextColored(ImVec4(0.5f,0.5f,0.5f,1), "No motion data");
        return;
    }

    static int motionQty = 0;  // 0=disp, 1=vel, 2=acc
    ImGui::RadioButton("Displacement", &motionQty, 0); ImGui::SameLine();
    ImGui::RadioButton("Velocity", &motionQty, 1); ImGui::SameLine();
    ImGui::RadioButton("Acceleration", &motionQty, 2);

    const char* yLabel[] = {"Displacement (mm)", "Velocity (mm/s)", "Acceleration (mm/s^2)"};

    if (ImPlot::BeginPlot("Motion", ImVec2(-1, -1))) {
        ImPlot::SetupAxes("Time", yLabel[motionQty]);

        for (const auto& ms : data_.motion) {
            if (ms.t.empty()) continue;

            const std::vector<double>* vals = nullptr;
            switch (motionQty) {
                case 0: vals = &ms.disp_mag; break;
                case 1: vals = &ms.vel_mag; break;
                case 2: vals = &ms.acc_mag; break;
            }
            if (!vals || vals->empty()) continue;

            bool highlight = (selectedPartIdx_ == ms.part_id || selectedPartIdx_ < 0);
            if (!highlight) continue;  // only show selected part (or all if none selected)

            char label[64];
            snprintf(label, sizeof(label), "Part %d", ms.part_id);
            ImPlot::PlotLine(label, ms.t.data(), vals->data(), static_cast<int>(ms.t.size()));
        }

        ImPlot::EndPlot();
    }
}

void DeepReportApp::renderEnergyChart() {
    if (data_.glstat.t.empty()) {
        ImGui::TextColored(ImVec4(0.5f,0.5f,0.5f,1), "No energy data (glstat)");
        return;
    }

    auto& g = data_.glstat;
    int n = static_cast<int>(g.t.size());

    if (ImPlot::BeginPlot("Energy Balance", ImVec2(-1, -1))) {
        ImPlot::SetupAxes("Time", "Energy");

        if (!g.kinetic_energy.empty())
            ImPlot::PlotLine("Kinetic", g.t.data(), g.kinetic_energy.data(), n);
        if (!g.internal_energy.empty())
            ImPlot::PlotLine("Internal", g.t.data(), g.internal_energy.data(), n);
        if (!g.total_energy.empty())
            ImPlot::PlotLine("Total", g.t.data(), g.total_energy.data(), n);
        if (!g.hourglass_energy.empty())
            ImPlot::PlotLine("Hourglass", g.t.data(), g.hourglass_energy.data(), n);

        ImPlot::EndPlot();
    }

    // Energy ratio subplot
    if (!g.energy_ratio.empty()) {
        if (ImPlot::BeginPlot("Energy Ratio", ImVec2(-1, 150))) {
            ImPlot::SetupAxes("Time", "Ratio");
            ImPlot::PlotLine("E_ratio", g.t.data(), g.energy_ratio.data(), n);
            ImPlot::EndPlot();
        }
    }
}

// ============================================================
// Render Gallery (placeholder — shows file list)
// ============================================================
void DeepReportApp::renderRenderGallery() {
    ImGui::Begin("Renders");

    if (data_.render_files.empty()) {
        ImGui::TextColored(ImVec4(0.5f,0.5f,0.5f,1), "No render files");
    } else {
        ImGui::Text("%zu render file(s):", data_.render_files.size());
        for (const auto& f : data_.render_files) {
            ImGui::BulletText("%s", f.c_str());
        }
    }

    ImGui::End();
}
