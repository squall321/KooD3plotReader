#pragma once
// ============================================================
// Shared color constants and inline UI helpers for DeepReportApp tabs.
// Include this in every DeepReportTab*.cpp file.
// ============================================================

#include <imgui.h>
#include <cstdio>
#include <cmath>
#include <string>

// --------------- Color palette (matches HTML report theme) ---------------

inline const ImVec4 COL_BG       = {0.10f, 0.10f, 0.18f, 1.0f};
inline const ImVec4 COL_CARD     = {0.12f, 0.16f, 0.27f, 1.0f};
inline const ImVec4 COL_ACCENT   = {0.31f, 0.80f, 0.64f, 1.0f};  // #4ecca3
inline const ImVec4 COL_RED      = {0.91f, 0.27f, 0.38f, 1.0f};  // #e94560
inline const ImVec4 COL_YELLOW   = {0.96f, 0.65f, 0.14f, 1.0f};  // #f5a623
inline const ImVec4 COL_BLUE     = {0.31f, 0.56f, 1.00f, 1.0f};
inline const ImVec4 COL_PURPLE   = {0.48f, 0.41f, 0.93f, 1.0f};
inline const ImVec4 COL_DIM      = {0.63f, 0.63f, 0.69f, 1.0f};

inline const ImVec4 CHART_COLORS[] = {
    {0.31f,0.80f,0.64f,1}, {0.91f,0.27f,0.38f,1}, {0.96f,0.65f,0.14f,1},
    {0.48f,0.41f,0.93f,1}, {0.00f,0.74f,0.83f,1}, {1.00f,0.60f,0.00f,1},
    {0.61f,0.15f,0.69f,1}, {0.30f,0.69f,0.31f,1}, {0.94f,0.50f,0.50f,1},
    {0.40f,0.73f,0.92f,1}, {0.80f,0.80f,0.20f,1}, {0.70f,0.40f,0.70f,1},
};
static constexpr int NUM_CHART_COLORS =
    static_cast<int>(sizeof(CHART_COLORS) / sizeof(CHART_COLORS[0]));

// --------------- Inline helpers ---------------

inline const char* fmtStress(double v, char* buf, size_t sz) {
    if (std::abs(v) >= 1e6) snprintf(buf, sz, "%.2e", v);
    else                     snprintf(buf, sz, "%.1f", v);
    return buf;
}

inline ImVec4 warningColor(const std::string& w) {
    if (w == "crit") return COL_RED;
    if (w == "warn") return COL_YELLOW;
    return COL_ACCENT;
}

// Left-accent-bar section header.
// level 0 = primary (4px bar, full alpha)
// level 1 = secondary (3px, 70%)
// level 2 = sub (2px, 45%)
// Compute principal stresses (eigenvalues) of symmetric 3x3 stress tensor.
// Returns s1 >= s2 >= s3 (descending).
inline void eigenvalues3x3(double sxx, double syy, double szz,
                            double sxy, double syz, double szx,
                            double& s1, double& s2, double& s3) {
    double I1   = sxx + syy + szz;
    double mean = I1 / 3.0;
    double dxx  = sxx - mean, dyy = syy - mean, dzz = szz - mean;
    double J2   = 0.5*(dxx*dxx + dyy*dyy + dzz*dzz
                       + 2.0*(sxy*sxy + syz*syz + szx*szx));
    if (J2 < 1e-20) { s1 = s2 = s3 = mean; return; }
    double J3   = dxx*(dyy*dzz - syz*syz)
                - sxy*(sxy*dzz - syz*szx)
                + szx*(sxy*syz - dyy*szx);
    double r    = std::sqrt(J2 / 3.0);
    double c3t  = std::max(-1.0, std::min(1.0, J3 / (2.0*r*r*r)));
    double theta = std::acos(c3t) / 3.0;
    s1 = mean + 2.0*r*std::cos(theta);
    s2 = mean + 2.0*r*std::cos(theta - 2.0*M_PI/3.0);
    s3 = mean + 2.0*r*std::cos(theta + 2.0*M_PI/3.0);
    if (s2 > s1) std::swap(s1, s2);
    if (s3 > s1) std::swap(s1, s3);
    if (s3 > s2) std::swap(s2, s3);
}

// Parse section-view folder name → human readable label.
// "section_view_part_10_z" → "Part 10 — Z"
// "section_view_z"         → "Overview — Z"
inline std::string parseSectionLabel(const std::string& folder) {
    size_t pp = folder.find("part_");
    size_t lu = folder.rfind('_');
    if (pp != std::string::npos && lu > pp + 5) {
        std::string pid  = folder.substr(pp + 5, lu - pp - 5);
        std::string axis = folder.substr(lu + 1);
        for (auto& c : axis) c = (char)toupper((unsigned char)c);
        return "Part " + pid + " \xe2\x80\x94 " + axis;
    }
    if (lu != std::string::npos && lu > 0) {
        std::string axis = folder.substr(lu + 1);
        for (auto& c : axis) c = (char)toupper((unsigned char)c);
        return "Overview \xe2\x80\x94 " + axis;
    }
    return folder;
}

inline void SectionHeader(const char* title,
                          ImVec4 col = {0.31f, 0.80f, 0.64f, 1.0f},
                          int level = 0)
{
    ImDrawList* dl = ImGui::GetWindowDrawList();
    ImVec2 p = ImGui::GetCursorScreenPos();
    float barW = (level == 0) ? 4.0f : (level == 1) ? 3.0f : 2.0f;
    float barH = ImGui::GetTextLineHeightWithSpacing() + 2.0f;
    float alpha = (level == 0) ? 1.0f : (level == 1) ? 0.7f : 0.45f;
    ImVec4 bc = col; bc.w = alpha;
    dl->AddRectFilled(p, ImVec2(p.x + barW, p.y + barH),
                      ImGui::ColorConvertFloat4ToU32(bc));
    ImGui::SetCursorPosX(ImGui::GetCursorPosX() + barW + 6.0f);
    ImGui::TextColored(col, "%s", title);
    ImGui::Separator();
    ImGui::Spacing();
}
