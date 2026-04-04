#include "app/SphereReportApp.hpp"
#include <imgui.h>

void SphereReportApp::renderHelpOverlay() {
    ImGuiIO& io = ImGui::GetIO();
    ImVec2 center(io.DisplaySize.x * 0.5f, io.DisplaySize.y * 0.5f);
    ImGui::SetNextWindowPos(center, ImGuiCond_Always, ImVec2(0.5f, 0.5f));
    ImGui::SetNextWindowSize(ImVec2(520, 420), ImGuiCond_Always);
    ImGui::SetNextWindowBgAlpha(0.92f);

    if (ImGui::Begin("##HelpOverlay", &showHelp_,
            ImGuiWindowFlags_NoResize | ImGuiWindowFlags_NoCollapse |
            ImGuiWindowFlags_NoMove | ImGuiWindowFlags_NoDocking)) {

        ImGui::TextColored(COL_ACCENT, "  KooViewer — Sphere Report  |  Keyboard & Mouse Guide");
        ImGui::Separator();
        ImGui::Spacing();

        auto row = [](const char* key, const char* desc) {
            ImGui::TableSetColumnIndex(0);
            ImGui::TextColored(ImVec4(0.9f,0.75f,0.3f,1), "%s", key);
            ImGui::TableSetColumnIndex(1);
            ImGui::TextUnformatted(desc);
        };

        if (ImGui::BeginTable("##HelpTable", 2,
                ImGuiTableFlags_SizingStretchProp | ImGuiTableFlags_BordersInnerH)) {
            ImGui::TableSetupColumn("Key / Action", ImGuiTableColumnFlags_WidthFixed, 180);
            ImGui::TableSetupColumn("Description");
            ImGui::TableHeadersRow();

            ImGui::TableNextRow(); row("?  (Shift+/)",       "Toggle this help overlay");
            ImGui::TableNextRow(); row("Ctrl+S",             "Save screenshot → screenshot_sphere.ppm");
            ImGui::TableNextRow(); row("EN / KO button",     "Toggle UI language");
            ImGui::TableNextRow(); row("", "");
            ImGui::TableNextRow(); row("--- Drag & Drop ---", "");
            ImGui::TableNextRow(); row("Drop JSON (1st)",    "Load primary dataset (A)");
            ImGui::TableNextRow(); row("Drop JSON (2nd)",    "Load compare dataset (B) → A/B Delta tab appears");
            ImGui::TableNextRow(); row("Drop JSON (3rd)",    "Replace A, clear B");
            ImGui::TableNextRow(); row("Drop .stl / .STL",  "Load device 3D model for orientation widget");
            ImGui::TableNextRow(); row("", "");
            ImGui::TableNextRow(); row("--- Mollweide Map ---", "");
            ImGui::TableNextRow(); row("Click dot",          "Select / deselect angle (highlighted in table)");
            ImGui::TableNextRow(); row("Quantity radio",     "Switch between Stress / Strain / G / Disp");
            ImGui::TableNextRow(); row("IDW toggle",         "Smooth contour interpolation on map");
            ImGui::TableNextRow(); row("Manual scale",       "Override colour range min/max");
            ImGui::TableNextRow(); row("", "");
            ImGui::TableNextRow(); row("--- 3D Globe ---",   "");
            ImGui::TableNextRow(); row("Drag (left button)", "Rotate globe");
            ImGui::TableNextRow(); row("Auto Rotate toggle", "Start/stop auto-spin");
            ImGui::TableNextRow(); row("Record button",      "Export globe frames as PPM sequence");
            ImGui::TableNextRow(); row("", "");
            ImGui::TableNextRow(); row("--- Category Filter ---", "");
            ImGui::TableNextRow(); row("Face/Edge/Corner/Fib toggles", "Show/hide angle categories in map & table");
            ImGui::EndTable();
        }

        ImGui::Spacing();
        ImGui::TextColored(COL_DIM, "Press ? again or click X to close.");
    }
    ImGui::End();
}
