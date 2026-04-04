#include "app/DeepReportApp.hpp"
#include "app/DeepReportColors.hpp"
#include <imgui.h>
#include <implot.h>
#include <algorithm>
#include <cstdio>
#include <cmath>
#include <string>

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

    // Time slider + animation controls
    static bool tensorPlaying = false;
    static float tensorPlayTimer = 0;
    static float tensorFPS = 30.0f;

    ImGuiIO& tio = ImGui::GetIO();
    if (tensorPlaying) {
        tensorPlayTimer += tio.DeltaTime * tensorFPS;
        if (tensorPlayTimer >= 1.0f) {
            int steps = (int)tensorPlayTimer;
            tensorPlayTimer -= (float)steps;
            tensorTimeIdx += steps;
            if (tensorTimeIdx >= n) { tensorTimeIdx = 0; }  // loop
        }
    }

    ImGui::SameLine(300);
    if (ImGui::Button("Jump to Peak")) { tensorTimeIdx = peakVmIdx; tensorPlaying = false; }
    ImGui::SameLine();
    if (tensorPlaying) {
        if (ImGui::Button("  Pause  ")) tensorPlaying = false;
    } else {
        if (ImGui::Button("  Play   ")) { tensorPlaying = true; tensorPlayTimer = 0; }
    }
    ImGui::SameLine();
    ImGui::SetNextItemWidth(80);
    ImGui::SliderFloat("FPS##tf", &tensorFPS, 1.0f, 120.0f, "%.0f");

    ImGui::SetNextItemWidth(-1);
    ImGui::SliderInt("##tensorTime", &tensorTimeIdx, 0, n - 1);
    if (tensorTimeIdx >= n) tensorTimeIdx = n - 1;
    ImGui::Text("t=%.6f | S1=%.1f  S2=%.1f  S3=%.1f  VM=%.1f  [%d/%d]",
        tens.time[tensorTimeIdx], p1[tensorTimeIdx], p2[tensorTimeIdx], p3[tensorTimeIdx],
        vm[tensorTimeIdx], tensorTimeIdx + 1, n);

    // 3×3 stress matrix + derived stress-state indicators
    {
        int ti = tensorTimeIdx;
        double sxx = tens.sxx[ti], syy = tens.syy[ti], szz = tens.szz[ti];
        double sxy = tens.sxy[ti], syz = tens.syz[ti], szx = tens.szx[ti];

        // Derived quantities at current time step
        double s1t = p1[ti], s2t = p2[ti], s3t = p3[ti], vmt = vm[ti];
        double sigma_m  = (s1t + s2t + s3t) / 3.0;              // hydrostatic
        double tau_max  = (s1t - s3t) / 2.0;                     // max shear
        double triax    = (vmt > 1e-10) ? sigma_m / vmt : 0.0;  // triaxiality
        double xi_lode  = (std::abs(s1t - s3t) > 1e-10)         // Lode param ξ
                        ? (2.0*s2t - s1t - s3t) / (s1t - s3t) : 0.0;

        // Left: 3×3 matrix
        ImGui::PushStyleColor(ImGuiCol_ChildBg, ImVec4(0.07f,0.08f,0.14f,0.8f));
        ImGui::BeginChild("##TensorMat", ImVec2(340, 64), true);
        ImGui::SetWindowFontScale(0.88f);
        ImGui::TextColored(COL_DIM, "σ =");  ImGui::SameLine(30);
        ImGui::TextColored(COL_ACCENT,
            "[ %8.2f  %8.2f  %8.2f ]\n"
            "    [ %8.2f  %8.2f  %8.2f ]\n"
            "    [ %8.2f  %8.2f  %8.2f ]",
            sxx, sxy, szx,
            sxy, syy, syz,
            szx, syz, szz);
        ImGui::SetWindowFontScale(1.0f);
        ImGui::EndChild();

        // Right: derived indicators table
        ImGui::SameLine();
        ImGui::PushStyleColor(ImGuiCol_ChildBg, ImVec4(0.07f,0.08f,0.14f,0.8f));
        ImGui::BeginChild("##TensorDerived", ImVec2(320, 64), true);
        ImGui::SetWindowFontScale(0.88f);
        // Row 1: σm and τmax
        ImGui::TextColored(COL_DIM, "σm (hydro)");
        ImGui::SameLine(105); ImGui::TextColored(COL_ACCENT, "%8.2f MPa", sigma_m);
        ImGui::SameLine(230); ImGui::TextColored(COL_DIM, "τmax");
        ImGui::SameLine(265); ImGui::TextColored(COL_RED,  "%8.2f MPa", tau_max);
        // Row 2: triaxiality and Lode
        ImGui::TextColored(COL_DIM, "Triaxiality");
        ImGui::SameLine(105);
        ImVec4 txCol = (triax >  0.66) ? COL_RED :
                       (triax >  0.33) ? COL_YELLOW :
                       (triax < -0.33) ? COL_BLUE : COL_ACCENT;
        ImGui::TextColored(txCol, "%8.3f", triax);
        ImGui::SameLine(230); ImGui::TextColored(COL_DIM, "Lode ξ");
        ImGui::SameLine(265);
        ImVec4 lodCol = (std::abs(xi_lode) < 0.2f) ? COL_YELLOW : COL_ACCENT;
        ImGui::TextColored(lodCol, "%8.3f", xi_lode);
        ImGui::SetWindowFontScale(1.0f);
        ImGui::EndChild();
        ImGui::PopStyleColor(2);
    }
    ImGui::Spacing();

    // Layout: left = charts, right = Mohr + Ellipsoid
    float halfW = ImGui::GetContentRegionAvail().x * 0.5f;

    // ── Left: 6-component + principal stress charts ──
    ImGui::BeginChild("##TensorCharts", ImVec2(halfW - 5, -1));

    // 6-component chart
    SectionHeader("6-Component Tensor", COL_ACCENT, 1);
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
    SectionHeader("Principal Stresses + Von Mises", COL_BLUE, 1);
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
    SectionHeader("Mohr's Circles", COL_RED, 1);
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
    SectionHeader("Stress Ellipsoid", COL_PURPLE, 1);
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
    if (a < 2) a = 2;
    if (b < 2) b = 2;
    if (c < 2) c = 2;

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

