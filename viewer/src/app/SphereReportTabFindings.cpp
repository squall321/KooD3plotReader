#include "app/SphereReportApp.hpp"
#include <imgui.h>
#include <algorithm>
#include <cstdio>

void SphereReportApp::renderFindings() {
    ImGui::TextColored(COL_ACCENT, "  Automated Findings & Recommendations");
    ImGui::Separator();
    ImGui::Spacing();

    // Fixed: removed unused dl/pos parameters from lambda
    auto finding = [](const char* level, const char* title, const char* detail, ImVec4 col) {
        ImVec4 bg = col; bg.w = 0.12f;
        ImGui::PushStyleColor(ImGuiCol_ChildBg, bg);
        ImGui::BeginChild(title, ImVec2(-1, 70), true);
        ImGui::TextColored(col, "%s  %s", level, title);
        ImGui::TextColored(COL_DIM, "%s", detail);
        ImGui::EndChild();
        ImGui::PopStyleColor();
        ImGui::Spacing();
    };

    char buf[256];

    // 1. Coverage
    snprintf(buf, sizeof(buf), "%d/%d simulations completed. DOE: %s, Angular spacing: %.1f deg, Coverage: %.0f%%",
        data_.successful_runs, data_.total_runs, data_.doe_strategy.c_str(),
        data_.angular_spacing, data_.sphere_coverage * 100);
    finding("INFO", "Simulation Coverage", buf,
        data_.sphere_coverage >= 0.9 ? COL_ACCENT : COL_YELLOW);

    // 2. Worst stress
    if (data_.worst_stress_angle >= 0) {
        auto& wr = data_.results[data_.worst_stress_angle];
        snprintf(buf, sizeof(buf), "Peak stress %.1f MPa at direction %s (Roll=%.1f, Pitch=%.1f)",
            data_.worst_stress, wr.angle.name.c_str(), wr.angle.roll, wr.angle.pitch);
        bool exceed = data_.yield_stress > 0 && data_.worst_stress > data_.yield_stress;
        finding(exceed ? "CRITICAL" : "WARNING", "Worst Case Stress", buf,
            exceed ? COL_RED : COL_YELLOW);
    }

    // 3. Safety factor
    if (data_.yield_stress > 0 && data_.worst_stress > 0) {
        double sf = data_.yield_stress / data_.worst_stress;
        snprintf(buf, sizeof(buf), "Global Safety Factor = %.3f (Yield = %.0f MPa / Peak = %.0f MPa)%s",
            sf, data_.yield_stress, data_.worst_stress,
            sf < 1.0 ? " — EXCEEDS YIELD" : sf < 1.5 ? " — Low margin" : " — Acceptable");
        finding(sf < 1.0 ? "CRITICAL" : sf < 1.5 ? "WARNING" : "OK",
            "Safety Factor Assessment", buf,
            sf < 1.0 ? COL_RED : sf < 1.5 ? COL_YELLOW : COL_ACCENT);
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
            snprintf(buf, sizeof(buf), "Min/Max stress ratio = %.2f. %s", ratio,
                ratio < 0.3 ? "High directional sensitivity — some angles much worse than others."
              : ratio < 0.7 ? "Moderate directional dependence."
              :               "Relatively uniform across directions.");
            finding(ratio < 0.3 ? "WARNING" : "INFO",
                "Directional Sensitivity", buf,
                ratio < 0.3 ? COL_YELLOW : COL_BLUE);
        }
    }

    // 5. Analysis scope
    snprintf(buf, sizeof(buf), "%d parts analyzed across %d impact directions = %d data points total.",
        (int)data_.parts.size(), (int)data_.results.size(),
        (int)(data_.parts.size() * data_.results.size()));
    finding("INFO", "Analysis Scope", buf, COL_BLUE);
}
