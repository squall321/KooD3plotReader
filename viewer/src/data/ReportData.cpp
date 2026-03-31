#include "data/ReportData.hpp"
#include <nlohmann/json.hpp>
#include <fstream>
#include <filesystem>
#include <iostream>
#include <sstream>
#include <algorithm>

namespace fs = std::filesystem;
using json = nlohmann::json;

static PartTimeSeries parseTimeSeries(const json& j) {
    PartTimeSeries ts;
    ts.part_id = j.value("part_id", 0);
    ts.part_name = j.value("part_name", "");
    ts.quantity = j.value("quantity", "");
    ts.unit = j.value("unit", "");
    ts.global_max = j.value("global_max", 0.0);
    ts.global_min = j.value("global_min", 0.0);
    ts.time_of_max = j.value("time_of_max", 0.0);

    if (j.contains("data") && j["data"].is_array()) {
        for (const auto& d : j["data"]) {
            TimePoint tp;
            tp.time = d.value("time", 0.0);
            tp.max_value = d.value("max_value", d.value("max", 0.0));
            tp.min_value = d.value("min_value", d.value("min", 0.0));
            tp.avg_value = d.value("avg_value", d.value("avg", 0.0));
            tp.max_element_id = d.value("max_element_id", 0);
            ts.data.push_back(tp);
        }
    }

    // Also support t/max_vals/avg_vals format (HTML inline)
    if (j.contains("t") && j["t"].is_array()) {
        auto t = j["t"].get<std::vector<double>>();
        auto maxv = j.value("max_vals", std::vector<double>{});
        auto avgv = j.value("avg_vals", std::vector<double>{});
        for (size_t i = 0; i < t.size(); ++i) {
            TimePoint tp;
            tp.time = t[i];
            tp.max_value = (i < maxv.size()) ? maxv[i] : 0.0;
            tp.avg_value = (i < avgv.size()) ? avgv[i] : 0.0;
            tp.min_value = 0.0;
            tp.max_element_id = 0;
            ts.data.push_back(tp);
        }
    }

    return ts;
}

static void parseMotionCSV(const std::string& path, DeepReportData::MotionSeries& ms) {
    std::ifstream f(path);
    if (!f) return;

    std::string line;
    std::getline(f, line);  // skip header

    while (std::getline(f, line)) {
        std::istringstream ss(line);
        std::string cell;
        std::vector<double> vals;
        while (std::getline(ss, cell, ',')) {
            try { vals.push_back(std::stod(cell)); } catch (...) { vals.push_back(0.0); }
        }
        if (vals.size() >= 14) {
            ms.t.push_back(vals[0]);
            ms.disp_mag.push_back(vals[4]);   // Avg_Disp_Mag
            ms.vel_mag.push_back(vals[8]);     // Avg_Vel_Mag
            ms.acc_mag.push_back(vals[12]);    // Avg_Acc_Mag
        }
    }
}

bool loadDeepReport(const std::string& outputDir, DeepReportData& out) {
    fs::path dir(outputDir);

    // 1. Load analysis_result.json
    fs::path arPath = dir / "analysis_result.json";
    if (fs::exists(arPath)) {
        try {
            std::ifstream f(arPath);
            json j = json::parse(f);

            // Metadata
            if (j.contains("metadata")) {
                auto& m = j["metadata"];
                out.d3plot_path = m.value("d3plot_path", "");
                out.num_states = m.value("num_states", 0);
                out.start_time = m.value("start_time", 0.0);
                out.end_time = m.value("end_time", 0.0);
            }

            // Stress history
            if (j.contains("stress_history")) {
                for (const auto& s : j["stress_history"]) {
                    out.stress.push_back(parseTimeSeries(s));
                }
            }

            // Strain history
            if (j.contains("strain_history")) {
                for (const auto& s : j["strain_history"]) {
                    out.strain.push_back(parseTimeSeries(s));
                }
            }

            // Principal stress
            if (j.contains("max_principal_history")) {
                for (const auto& s : j["max_principal_history"]) {
                    out.max_principal.push_back(parseTimeSeries(s));
                }
            }
            if (j.contains("min_principal_history")) {
                for (const auto& s : j["min_principal_history"]) {
                    out.min_principal.push_back(parseTimeSeries(s));
                }
            }

            // Peak element tensors
            if (j.contains("peak_element_tensors")) {
                for (const auto& t : j["peak_element_tensors"]) {
                    ElementTensorHistory eth;
                    eth.element_id = t.value("element_id", 0);
                    eth.part_id = t.value("part_id", 0);
                    eth.reason = t.value("reason", "");
                    eth.peak_value = t.value("peak_value", 0.0);
                    eth.peak_time = t.value("peak_time", 0.0);
                    eth.time = t.value("time", std::vector<double>{});
                    eth.sxx = t.value("sxx", std::vector<double>{});
                    eth.syy = t.value("syy", std::vector<double>{});
                    eth.szz = t.value("szz", std::vector<double>{});
                    eth.sxy = t.value("sxy", std::vector<double>{});
                    eth.syz = t.value("syz", std::vector<double>{});
                    eth.szx = t.value("szx", std::vector<double>{});
                    out.tensors.push_back(std::move(eth));
                }
            }

        } catch (const std::exception& e) {
            out.error = std::string("Failed to parse analysis_result.json: ") + e.what();
            return false;
        }
    }

    // 2. Load result.json (summary + glstat)
    fs::path rjPath = dir / "result.json";
    if (fs::exists(rjPath)) {
        try {
            std::ifstream f(rjPath);
            json j = json::parse(f);

            out.label = j.value("label", "");
            out.tier = j.value("tier", 0);

            if (j.contains("summary")) {
                auto& s = j["summary"];
                out.peak_stress_global = s.value("peak_stress_global", 0.0);
                out.peak_stress_part_id = s.value("peak_stress_part_id", 0);
                out.peak_strain_global = s.value("peak_strain_global", 0.0);
                out.peak_disp_global = s.value("peak_disp_global", 0.0);
                out.energy_ratio_min = s.value("energy_ratio_min", 1.0);
            }

            if (j.contains("parts")) {
                for (auto& [key, val] : j["parts"].items()) {
                    int pid = std::stoi(key);
                    PartSummary ps;
                    ps.part_id = pid;
                    ps.name = val.value("name", "Part " + key);
                    ps.peak_stress = val.value("peak_stress", 0.0);
                    ps.peak_strain = val.value("peak_strain", 0.0);
                    ps.peak_disp = val.value("peak_disp_mag", 0.0);
                    ps.peak_vel = val.value("peak_vel_mag", 0.0);
                    ps.peak_acc = val.value("peak_acc_mag", 0.0);
                    ps.safety_factor = val.value("safety_factor", 0.0);
                    ps.stress_warning = val.value("stress_warning", "ok");
                    ps.strain_warning = val.value("strain_warning", "ok");
                    out.parts[pid] = ps;
                }
            }

            if (j.contains("glstat") && !j["glstat"].is_null()) {
                auto& g = j["glstat"];
                out.glstat.t = g.value("t", std::vector<double>{});
                out.glstat.total_energy = g.value("total_energy", std::vector<double>{});
                out.glstat.kinetic_energy = g.value("kinetic_energy", std::vector<double>{});
                out.glstat.internal_energy = g.value("internal_energy", std::vector<double>{});
                out.glstat.hourglass_energy = g.value("hourglass_energy", std::vector<double>{});
                out.glstat.energy_ratio = g.value("energy_ratio", std::vector<double>{});
                out.glstat.energy_ratio_min = g.value("energy_ratio_min", 1.0);
                out.glstat.normal_termination = g.value("normal_termination", true);
            }

        } catch (const std::exception& e) {
            // result.json is optional, continue without it
        }
    }

    // 3. Load motion CSVs
    fs::path motionDir = dir / "motion";
    if (fs::exists(motionDir)) {
        for (const auto& entry : fs::directory_iterator(motionDir)) {
            if (entry.path().extension() == ".csv" &&
                entry.path().filename().string().find("part_") == 0) {
                DeepReportData::MotionSeries ms;
                // Extract part ID from filename: part_1_motion.csv
                std::string fname = entry.path().stem().string();
                size_t p1 = fname.find('_');
                size_t p2 = fname.find('_', p1 + 1);
                if (p1 != std::string::npos && p2 != std::string::npos) {
                    try { ms.part_id = std::stoi(fname.substr(p1+1, p2-p1-1)); } catch (...) {}
                }
                parseMotionCSV(entry.path().string(), ms);
                if (!ms.t.empty()) {
                    // Find part name
                    auto it = out.parts.find(ms.part_id);
                    if (it != out.parts.end()) ms.part_name = it->second.name;
                    out.motion.push_back(std::move(ms));
                }
            }
        }
        std::sort(out.motion.begin(), out.motion.end(),
                  [](const auto& a, const auto& b) { return a.part_id < b.part_id; });
    }

    // 4. Scan render files
    fs::path rendersDir = dir / "renders";
    if (fs::exists(rendersDir)) {
        for (const auto& entry : fs::recursive_directory_iterator(rendersDir)) {
            auto ext = entry.path().extension().string();
            if (ext == ".mp4" || ext == ".gif") {
                out.render_files.push_back(entry.path().string());
            } else if (ext == ".png" && entry.path().filename().string().find("frame_") == std::string::npos) {
                out.render_files.push_back(entry.path().string());
            }
        }
        std::sort(out.render_files.begin(), out.render_files.end());
    }

    out.loaded = !out.stress.empty() || !out.parts.empty();
    return out.loaded;
}
