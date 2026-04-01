#pragma once
#include <string>
#include <vector>
#include <map>

struct AngleInfo {
    std::string name;
    double roll = 0, pitch = 0, yaw = 0;
    std::string category;  // face, edge, corner, fibonacci
    double lon = 0, lat = 0;  // Mollweide coordinates
};

struct TimeSeries {
    std::vector<double> t;
    std::vector<double> values;
};

struct AnglePartData {
    double peak_stress = 0;
    double peak_strain = 0;
    double peak_g = 0;
    double peak_disp = 0;
    TimeSeries stress_ts;
    TimeSeries strain_ts;
    TimeSeries g_ts;
    TimeSeries disp_ts;
};

struct AngleResult {
    std::string run_folder;
    AngleInfo angle;
    int num_states = 0;
    std::map<int, AnglePartData> parts;  // part_id -> data
};

struct SpherePartInfo {
    int part_id;
    std::string name;
    std::string group;
};

struct SphereData {
    std::string project_name;
    std::string doe_strategy;
    int total_runs = 0;
    int successful_runs = 0;
    int failed_runs = 0;
    double angular_spacing = 0;
    double sphere_coverage = 0;
    double yield_stress = 0;

    std::map<int, SpherePartInfo> parts;
    std::vector<AngleResult> results;

    // Derived
    double worst_stress = 0;
    int worst_stress_angle = -1;
    double worst_g = 0;
    int worst_g_angle = -1;

    bool loaded = false;
    std::string error;
};

bool loadSphereData(const std::string& jsonPath, SphereData& out);

// Euler angles -> lon/lat for Mollweide projection
void eulerToLonLat(double roll, double pitch, double yaw,
                    const std::string& angleName, double& lon, double& lat);
