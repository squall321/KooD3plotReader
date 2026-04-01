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
    double peak_stress = 0;
    double time_of_peak_stress = 0;
    int peak_element_id = 0;
    double peak_strain = 0;
    double peak_max_principal = 0;
    double peak_min_principal = 0;
    double peak_max_principal_strain = 0;
    double peak_min_principal_strain = 0;
    double peak_disp = 0;
    double peak_vel = 0;
    double peak_acc = 0;
    double safety_factor = 0;
    std::string mat_type;
    double stress_limit = 0;
    std::string stress_source;
    double strain_limit = 0;
    std::string strain_source;
    double stress_ratio = 0;
    double strain_ratio = 0;
    std::string stress_warning = "ok";
    std::string strain_warning = "ok";
};

struct GlstatData {
    std::vector<double> t;
    std::vector<double> total_energy;
    std::vector<double> kinetic_energy;
    std::vector<double> internal_energy;
    std::vector<double> hourglass_energy;
    std::vector<double> energy_ratio;
    std::vector<double> mass;
    double energy_ratio_min = 1.0;
    double energy_ratio_max = 1.0;
    bool has_mass_added = false;
    bool normal_termination = true;
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
    double peak_stress_global = 0;
    int peak_stress_part_id = 0;
    double peak_strain_global = 0;
    double peak_disp_global = 0;
    double energy_ratio_min = 1.0;
    double yield_stress = 0;
    bool normal_termination = true;
    std::string termination_source;

    // Max principal strain series
    std::vector<PartTimeSeries> max_principal_strain;
    std::vector<PartTimeSeries> min_principal_strain;

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

    // Motion (per part: time, disp/vel/acc with XYZ components)
    struct MotionSeries {
        int part_id;
        std::string part_name;
        std::vector<double> t;
        std::vector<double> disp_x, disp_y, disp_z, disp_mag;
        std::vector<double> vel_x, vel_y, vel_z, vel_mag;
        std::vector<double> acc_x, acc_y, acc_z, acc_mag;
        std::vector<double> max_disp_mag;
    };
    std::vector<MotionSeries> motion;

    // Contact data (from binout)
    struct ContactInterface {
        int id = 0;
        std::string name;
        std::string side;
        std::vector<double> t;
        std::vector<double> fx, fy, fz, fmag;
        double peak_fmag = 0;
    };
    struct ContactEnergy {
        int id = 0;
        std::string name;
        std::vector<double> t;
        std::vector<double> total_energy;
        std::vector<double> friction_energy;
    };
    std::vector<ContactInterface> rcforc;
    std::vector<ContactEnergy> sleout;

    // Element quality
    struct ElemQuality {
        int part_id;
        std::string part_name;
        std::string element_type;
        int num_elements;
        double peak_aspect_ratio;
        double min_jacobian;
        double peak_warpage;
        double peak_skewness;
    };
    std::vector<ElemQuality> element_quality;

    // Render files
    std::vector<std::string> render_files;

    // Warnings (auto-generated)
    struct Warning {
        std::string level;   // "warn", "crit", "info"
        std::string message;
    };
    std::vector<Warning> warnings;

    bool loaded = false;
    std::string error;
};

// Load from output directory (reads analysis_result.json + result.json + motion CSVs)
bool loadDeepReport(const std::string& outputDir, DeepReportData& out);
