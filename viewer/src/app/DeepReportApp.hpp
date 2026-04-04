#pragma once
#include "data/ReportData.hpp"
#include "data/SimData.hpp"
#include "gpu/MeshGPU.hpp"
#include "gpu/Shader.hpp"
#include "scene/Camera.hpp"
#include "widgets/VideoPlayer.hpp"
#include <imgui.h>
#include <glad/glad.h>
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

    // 3D viewer
    SimData sim3d_;
    MeshGPU meshGPU_;
    Shader shader3d_;
    Camera camera3d_;
    GLuint colormapTex_ = 0;
    GLuint fbo3d_ = 0, fboTex3d_ = 0, fboDepth3d_ = 0;
    int fboW_ = 0, fboH_ = 0;
    int current3DState_ = 0;
    bool show3DFringe_ = false;
    bool wireframe3d_ = false;
    bool playing3d_ = false;
    float playTimer3d_ = 0;
    int fringeType_ = 0;  // 0=vonMises, 1=strain, 2=displacement
    bool mesh3dReady_ = false;

    void renderKPIBar();
    void renderWarnings();
    void renderOverview();
    void renderPartTable();
    void renderStressTab();
    void renderTensorTab();
    void renderMotionTab();
    void renderEnergyTab();
    void renderQualityTab();
    void renderContactTab();
    void renderDeepDiveTab();
    void renderSysInfoTab();
    int deepDivePartId_ = 0;
    bool navigateToDeepDive_ = false;
    int tabToSelect_ = -1;  // -1 = no pending switch; 0..N = select that tab index
    void renderRenderGalleryTab();
    void renderVideoFullscreen();
    void renderSectionViewConfig();  // collapsible config panel in gallery tab

    // Section view config state
    bool svCfgAxX_ = true, svCfgAxY_ = false, svCfgAxZ_ = true;
    bool svCfgFieldVM_ = true, svCfgFieldStrain_ = false, svCfgFieldDisp_ = false;
    bool svCfgFieldPressure_ = false, svCfgFieldMaxShear_ = false;
    bool svCfgPerPart_ = false;
    float svCfgFade_ = 0.0f;
    char svCfgTargetIds_[128] = "";  // comma-separated part IDs
    bool svCfgConfigOpen_ = true;

    // Global part filter (keyword text, comma-separated, applied across all tabs)
    char globalFilter_[128] = "";
    bool partPassesFilter(int pid, const std::string& name) const;

    // Helpers
    void drawTimeSeriesPlot(const char* id, const char* yLabel, const std::vector<PartTimeSeries>& series, bool showAvg = false);

    // 3D viewer
    void render3DTab();
    void init3DViewer();
    void ensureFBO(int w, int h);
    void setPresetView(int axis);  // 0=front,1=back,2=left,3=right,4=top,5=bottom
};
