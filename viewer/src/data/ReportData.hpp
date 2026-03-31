#pragma once
#include <string>
#include <vector>
#include <map>

// ============================================================
// Deep Report data structures (from analysis_result.json)
// ============================================================

struct TimePoint {
    double time;
    double max_value;
    double min_value;
    double avg_value;
    int max_element_id;
};

struct PartTimeSeries {
    int part_id;
    std::string part_name;
    std::string quantity;
    std::string unit;
    double global_max;
    double global_min;
    double time_of_max;
    std::vector<TimePoint> data;
};

struct ElementTensorHistory {
    int element_id;
    int part_id;
    std::string reason;
    double peak_value;
    double peak_time;
    std::vector<double> time;
    std::vector<double> sxx, syy, szz, sxy, syz, szx;
};

struct PartSummary {
    int part_id;
    std::string name;
    double peak_stress;
    double peak_strain;
    double peak_disp;
    double peak_vel;
    double peak_acc;
    double safety_factor;
    std::string stress_warning;  // "ok", "warn", "crit"
    std::string strain_warning;
};

struct GlstatData {
    std::vector<double> t;
    std::vector<double> total_energy;
    std::vector<double> kinetic_energy;
    std::vector<double> internal_energy;
    std::vector<double> hourglass_energy;
    std::vector<double> energy_ratio;
    double energy_ratio_min;
    bool normal_termination;
};

struct DeepReportData {
    // Metadata
    std::string d3plot_path;
    std::string label;
    int num_states;
    double start_time;
    double end_time;
    int tier;

    // KPI summary
    double peak_stress_global;
    int peak_stress_part_id;
    double peak_strain_global;
    double peak_disp_global;
    double energy_ratio_min;

    // Time series
    std::vector<PartTimeSeries> stress;
    std::vector<PartTimeSeries> strain;
    std::vector<PartTimeSeries> max_principal;
    std::vector<PartTimeSeries> min_principal;
    std::vector<ElementTensorHistory> tensors;

    // Parts
    std::map<int, PartSummary> parts;

    // Energy
    GlstatData glstat;

    // Motion (per part: time, disp_mag, vel_mag, acc_mag)
    struct MotionSeries {
        int part_id;
        std::string part_name;
        std::vector<double> t;
        std::vector<double> disp_mag;
        std::vector<double> vel_mag;
        std::vector<double> acc_mag;
    };
    std::vector<MotionSeries> motion;

    // Render files
    std::vector<std::string> render_files;

    bool loaded = false;
    std::string error;
};

// Load from output directory (reads analysis_result.json + result.json + motion CSVs)
bool loadDeepReport(const std::string& outputDir, DeepReportData& out);
