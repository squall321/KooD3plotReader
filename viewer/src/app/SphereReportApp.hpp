#pragma once
#include "data/SphereData.hpp"
#include "data/SimData.hpp"
#include "data/StlLoader.hpp"
#include "gpu/MeshGPU.hpp"
#include "gpu/Shader.hpp"
#include "scene/Camera.hpp"
#include "app/DeepReportColors.hpp"
#include <imgui.h>
#include <glad/glad.h>
#include <string>
#include <set>
#include <vector>

struct GLFWwindow;

class SphereReportApp {
public:
    bool init(int width, int height);
    void run(const std::string& jsonPath);
    void shutdown();

private:
    GLFWwindow* window_ = nullptr;
    SphereData data_;

    // State
    int selectedPartId_ = 0;
    int quantity_ = 0;  // 0=stress, 1=strain, 2=g_force, 3=disp
    std::set<int> selectedAngles_;
    int hoveredAngle_ = -1;

    void renderKPIBar();
    void renderMollweide();
    void renderGlobe();
    void renderAngleTable();
    void renderPartRisk();
    void renderCompareInfo();
    void renderDirectional();
    void renderStatistics();
    void renderFindings();
    void renderHeatmapTab();
    void renderFailureTab();

    // Globe state
    float globeYaw_ = 0, globePitch_ = 0.3f;
    bool globeAutoRotate_ = true;
    bool swapRP_ = false;
    bool langKo_ = true;  // true=Korean, false=English
    bool globeRecording_ = false;
    int globeRecFrame_ = 0;

    // Mollweide options
    bool contourMode_ = false;
    bool manualScale_ = false;
    float scaleMin_ = 0, scaleMax_ = 0;

    // A/B Compare
    SphereData dataB_;
    bool hasDataB_ = false;

    // Category filter (face/edge/corner/fibonacci → all on by default)
    bool catFilter_[4] = {true, true, true, true};  // face, edge, corner, fibonacci

    // Help overlay
    bool showHelp_ = false;

    // Orientation device (box or STL)
    StlMesh stlMesh_;
    bool stlLoaded_ = false;
    float deviceAspect_[3] = {0.48f, 1.0f, 0.08f};  // Galaxy S25 default (W:H:D)

    void drawOrientationDevice(ImDrawList* dl, ImVec2 pos, float size, double roll, double pitch);
    void drawOrientationCube(ImDrawList* dl, ImVec2 pos, float size, double roll, double pitch);
    void drawOrientationSTL(ImDrawList* dl, ImVec2 pos, float size, double roll, double pitch);

    void renderCompareABTab();     // A/B delta Mollweide
    void renderHelpOverlay();      // ? key overlay
    void exportHTMLReport();       // Ctrl+E → .html
    void renderAngleDetail();      // Angle detail: 3D section view + LSPrePost

    // Angle detail state (3D section view for selected angle)
    int detailAngleIdx_ = -1;      // index into data_.results, -1 = none
    bool detailLoaded_ = false;    // d3plot loaded for current angle?
    std::unique_ptr<SimData> detailSim_;  // mesh + fringe (non-moveable due to atomics)
    MeshGPU detailMeshGPU_;
    Shader detailShader_;
    Camera detailCamera_;
    GLuint detailColormapTex_ = 0;
    Shader detailPlaneShader_;
    GLuint detailPlaneVAO_ = 0, detailPlaneVBO_ = 0;
    GLuint detailFBO_ = 0, detailFBOTex_ = 0, detailFBODepth_ = 0;
    int detailFBOW_ = 0, detailFBOH_ = 0;
    int detailState_ = 0;
    bool detailFringe_ = true;
    bool detailPlaying_ = false;
    float detailPlayTimer_ = 0;
    bool detailSection_ = false;   // section cut enabled
    int detailSectionAxis_ = 2;    // 0=X, 1=Y, 2=Z
    float detailSectionPos_ = 0.5f;// normalized 0..1
    int detailPartFilter_ = 0;    // 0=all, else part_id to isolate

    void initDetailViewer();
    void ensureDetailFBO(int w, int h);
    void loadAngleD3plot(int angleIdx);

    // LSPrePost launch
    void launchLSPrePost(int angleIdx);

    // Batch section render
    bool batchRenderActive_ = false;
    int batchRenderAxis_ = 2;       // default Z
    int batchRenderPartId_ = 0;     // target part
    std::string batchRenderStatus_;
    void triggerBatchSectionRender(int angleIdx, int axis, int partId);

    // Helpers
    bool passesFilter(const std::string& category) const;  // category filter check
    double getAngleValue(int ri, int partId, int qty) const;
    void mollweideProject(double lonDeg, double latDeg, double& x, double& y) const;
    ImU32 valueToColor(double norm) const;
    void projectGlobe(double lon, double lat, float vLon, float vLat,
                       float R, float& sx, float& sy, float& sz) const;
    std::string getRunD3plotPath(int angleIdx) const;
    std::string getRunOutputDir(int angleIdx) const;
};
