#pragma once
#include "data/ReportData.hpp"
#include <string>

struct GLFWwindow;

class DeepReportApp {
public:
    bool init(int width, int height);
    void run(const std::string& outputDir);
    void shutdown();

private:
    GLFWwindow* window_ = nullptr;
    DeepReportData data_;
    int selectedPartIdx_ = -1;
    int activeTab_ = 0;

    void renderKPIBar();
    void renderPartTable();
    void renderStressChart();
    void renderStrainChart();
    void renderMotionChart();
    void renderEnergyChart();
    void renderRenderGallery();
};
