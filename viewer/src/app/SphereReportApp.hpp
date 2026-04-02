#pragma once
#include "data/SphereData.hpp"
#include "data/StlLoader.hpp"
#include <imgui.h>
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

    // Orientation device (box or STL)
    StlMesh stlMesh_;
    bool stlLoaded_ = false;
    float deviceAspect_[3] = {0.48f, 1.0f, 0.08f};  // Galaxy S25 default (W:H:D)

    void drawOrientationDevice(ImDrawList* dl, ImVec2 pos, float size, double roll, double pitch);
    void drawOrientationCube(ImDrawList* dl, ImVec2 pos, float size, double roll, double pitch);
    void drawOrientationSTL(ImDrawList* dl, ImVec2 pos, float size, double roll, double pitch);

    // Helpers
    double getAngleValue(int ri, int partId, int qty) const;
    void mollweideProject(double lonDeg, double latDeg, double& x, double& y) const;
    ImU32 valueToColor(double norm) const;
    void projectGlobe(double lon, double lat, float vLon, float vLat,
                       float R, float& sx, float& sy, float& sz) const;
};
