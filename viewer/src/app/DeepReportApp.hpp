#pragma once
#include "data/ReportData.hpp"
#include "widgets/VideoPlayer.hpp"
#include <imgui.h>
#include <string>
#include <memory>
#include <map>
#include <set>

struct GLFWwindow;

class DeepReportApp {
public:
    bool init(int width, int height);
    void run(const std::string& outputDir);
    void shutdown();

private:
    GLFWwindow* window_ = nullptr;
    DeepReportData data_;
    std::set<int> selectedParts_;  // multi-select
    int activeTab_ = 0;

    // Video players (keyed by file path)
    std::map<std::string, std::unique_ptr<VideoPlayer>> players_;
    std::string activeVideo_;
    bool videoFullscreen_ = false;

    void renderKPIBar();
    void renderWarnings();
    void renderOverview();
    void renderPartTable();
    void renderStressTab();
    void renderTensorTab();
    void renderMotionTab();
    void renderEnergyTab();
    void renderQualityTab();
    void renderRenderGalleryTab();
    void renderVideoFullscreen();

    // Helpers
    void drawBarRanking(const char* title, const std::vector<std::pair<int, double>>& items, ImVec4 color, const char* unit, int decimals = 1);
    void drawTimeSeriesPlot(const char* id, const char* yLabel, const std::vector<PartTimeSeries>& series, bool showAvg = false);
};
