#include "app/DeepReportApp.hpp"
#include "app/DeepReportColors.hpp"
#include <imgui.h>

void DeepReportApp::renderDeepHelpOverlay() {
    ImGuiIO& io = ImGui::GetIO();
    ImVec2 center(io.DisplaySize.x * 0.5f, io.DisplaySize.y * 0.5f);
    ImGui::SetNextWindowPos(center, ImGuiCond_Always, ImVec2(0.5f, 0.5f));
    ImGui::SetNextWindowSize(ImVec2(560, 460), ImGuiCond_Always);
    ImGui::SetNextWindowBgAlpha(0.92f);

    if (ImGui::Begin("##DeepHelp", &showHelp_,
            ImGuiWindowFlags_NoResize | ImGuiWindowFlags_NoCollapse |
            ImGuiWindowFlags_NoMove | ImGuiWindowFlags_NoDocking)) {

        ImGui::TextColored(COL_ACCENT, "  KooViewer — Deep Report  |  Keyboard & Mouse Guide");
        ImGui::Separator();
        ImGui::Spacing();

        auto row = [](const char* key, const char* desc) {
            ImGui::TableSetColumnIndex(0);
            ImGui::TextColored(ImVec4(0.9f,0.75f,0.3f,1), "%s", key);
            ImGui::TableSetColumnIndex(1);
            ImGui::TextUnformatted(desc);
        };

        if (ImGui::BeginTable("##DeepHelpTable", 2,
                ImGuiTableFlags_SizingStretchProp | ImGuiTableFlags_BordersInnerH)) {
            ImGui::TableSetupColumn("Key / Action", ImGuiTableColumnFlags_WidthFixed, 200);
            ImGui::TableSetupColumn("Description");
            ImGui::TableHeadersRow();

            ImGui::TableNextRow(); row("?  (Shift+/)",        "Toggle this help overlay");
            ImGui::TableNextRow(); row("Ctrl+S",              "Save screenshot → screenshot.ppm");
            ImGui::TableNextRow(); row("Alt+1 … Alt+0",       "Switch to tab 1–10 directly");
            ImGui::TableNextRow(); row("F11",                  "Toggle maximize/restore window");
            ImGui::TableNextRow(); row("", "");
            ImGui::TableNextRow(); row("--- Part Table ---",   "");
            ImGui::TableNextRow(); row("Click row",            "Select / deselect part");
            ImGui::TableNextRow(); row("Hover row",            "Highlight that part yellow in 3D viewer");
            ImGui::TableNextRow(); row("Double-click row",     "Jump to Deep Dive for that part");
            ImGui::TableNextRow(); row("Filter box",           "Search parts by name or ID");
            ImGui::TableNextRow(); row("All / None buttons",   "Select all / deselect all");
            ImGui::TableNextRow(); row("", "");
            ImGui::TableNextRow(); row("--- 3D Viewer ---",   "");
            ImGui::TableNextRow(); row("Left-drag",            "Orbit camera");
            ImGui::TableNextRow(); row("Middle-drag",          "Pan camera");
            ImGui::TableNextRow(); row("Scroll wheel",         "Zoom in/out");
            ImGui::TableNextRow(); row("Front/Back/…buttons",  "Snap to preset view direction");
            ImGui::TableNextRow(); row("Fringe checkbox",      "Toggle von Mises stress colour");
            ImGui::TableNextRow(); row("Wire checkbox",        "Toggle wireframe overlay");
            ImGui::TableNextRow(); row("Play / Pause",         "Animate through time states");
            ImGui::TableNextRow(); row("State slider",         "Scrub to specific time step");
            ImGui::TableNextRow(); row("Section checkbox",     "Enable clip-plane section view");
            ImGui::TableNextRow(); row("X/Y/Z radio + slider", "Choose section axis and position");
            ImGui::TableNextRow(); row("", "");
            ImGui::TableNextRow(); row("--- Drag & Drop ---",  "");
            ImGui::TableNextRow(); row("Drop output_dir",      "Load a new analysis result");
            ImGui::EndTable();
        }

        ImGui::Spacing();
        ImGui::TextColored(COL_DIM, "Press ? again or click X to close.");
    }
    ImGui::End();
}
