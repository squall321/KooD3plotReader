#include "app/SphereReportApp.hpp"
#include <imgui.h>
#include <implot.h>
#include <algorithm>
#include <cmath>
#include <vector>

void SphereReportApp::renderStatistics() {
    ImGui::TextColored(COL_DIM,
        "Distribution of peak values across all impact directions.\n"
        "Histogram shows how many angles fall into each value bin.");
    ImGui::Spacing();

    std::vector<double> vals;
    vals.reserve(data_.results.size());
    for (int ri = 0; ri < (int)data_.results.size(); ++ri) {
        if (!passesFilter(data_.results[ri].angle.category)) continue;
        vals.push_back(getAngleValue(ri, selectedPartId_, quantity_));
    }
    if (vals.empty()) return;

    double vmin = *std::min_element(vals.begin(), vals.end());
    double vmax = *std::max_element(vals.begin(), vals.end());
    double avg = 0, stddev = 0;
    for (double v : vals) avg += v;
    avg /= vals.size();
    for (double v : vals) stddev += (v-avg)*(v-avg);
    stddev = std::sqrt(stddev / vals.size());

    ImGui::TextColored(COL_ACCENT, "  Summary Statistics");
    ImGui::Separator();
    ImGui::Text("  Count: %d    Min: %.2f    Max: %.2f    Mean: %.2f    StdDev: %.2f",
        (int)vals.size(), vmin, vmax, avg, stddev);
    ImGui::Spacing();

    const int nBins = 20;
    double binW = std::max((vmax - vmin) / nBins, 1e-10);
    std::vector<double> bins(nBins, 0), binCenters(nBins);
    for (int i = 0; i < nBins; ++i) binCenters[i] = vmin + (i+0.5)*binW;
    for (double v : vals) {
        int bi = std::min((int)((v-vmin)/binW), nBins-1);
        if (bi >= 0) bins[bi]++;
    }

    const char* qtyNames[] = {"Stress (MPa)", "Strain", "G-Force", "Disp (mm)"};
    ImVec2 plotSz(ImGui::GetContentRegionAvail().x, std::max(250.0f, ImGui::GetContentRegionAvail().y - 10));
    if (ImPlot::BeginPlot("##Histogram", plotSz)) {
        ImPlot::SetupAxes(qtyNames[quantity_], "Count");
        ImPlot::PlotBars("Distribution", binCenters.data(), bins.data(), nBins, binW*0.8);
        ImPlot::PlotInfLines("Mean", &avg, 1);
        ImPlot::EndPlot();
    }
}
