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
    ts.part_id = j.contains("part_id") ? j["part_id"].get<int>() : 0;
    ts.part_name = j.contains("part_name") && j["part_name"].is_string() ? j["part_name"].get<std::string>() : "";
    ts.quantity = j.contains("quantity") && j["quantity"].is_string() ? j["quantity"].get<std::string>() : "";
    ts.unit = j.contains("unit") && j["unit"].is_string() ? j["unit"].get<std::string>() : "";
    ts.global_max = j.contains("global_max") ? j["global_max"].get<double>() : 0.0;
    ts.global_min = j.contains("global_min") ? j["global_min"].get<double>() : 0.0;
    ts.time_of_max = j.contains("time_of_max") ? j["time_of_max"].get<double>() : 0.0;

    if (j.contains("data") && j["data"].is_array()) {
        for (const auto& d : j["data"]) {
            TimePoint tp;
            tp.time = d.contains("time") ? d["time"].get<double>() : 0.0;
            tp.max_value = d.contains("max_value") ? d["max_value"].get<double>() :
                           d.contains("max") ? d["max"].get<double>() : 0.0;
            tp.min_value = d.contains("min_value") ? d["min_value"].get<double>() :
                           d.contains("min") ? d["min"].get<double>() : 0.0;
            tp.avg_value = d.contains("avg_value") ? d["avg_value"].get<double>() :
                           d.contains("avg") ? d["avg"].get<double>() : 0.0;
            tp.max_element_id = d.contains("max_element_id") ? d["max_element_id"].get<int>() : 0;
            ts.data.push_back(tp);
        }
    }

    // Also support t/max_vals/avg_vals format (HTML inline)
    if (j.contains("t") && j["t"].is_array()) {
        auto t = j["t"].get<std::vector<double>>();
        auto maxv = j.contains("max_vals") ? j["max_vals"].get<std::vector<double>>() : std::vector<double>{};
        auto avgv = j.contains("avg_vals") ? j["avg_vals"].get<std::vector<double>>() : std::vector<double>{};
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
    // Header: Time,Avg_Disp_X,Avg_Disp_Y,Avg_Disp_Z,Avg_Disp_Mag,
    //         Avg_Vel_X,Avg_Vel_Y,Avg_Vel_Z,Avg_Vel_Mag,
    //         Avg_Acc_X,Avg_Acc_Y,Avg_Acc_Z,Avg_Acc_Mag,Max_Disp_Mag,Max_Disp_Node_ID

    while (std::getline(f, line)) {
        std::istringstream ss(line);
        std::string cell;
        std::vector<double> v;
        while (std::getline(ss, cell, ',')) {
            try { v.push_back(std::stod(cell)); } catch (...) { v.push_back(0.0); }
        }
        if (v.size() >= 14) {
            ms.t.push_back(v[0]);
            ms.disp_x.push_back(v[1]); ms.disp_y.push_back(v[2]); ms.disp_z.push_back(v[3]);
            ms.disp_mag.push_back(v[4]);
            ms.vel_x.push_back(v[5]); ms.vel_y.push_back(v[6]); ms.vel_z.push_back(v[7]);
            ms.vel_mag.push_back(v[8]);
            ms.acc_x.push_back(v[9]); ms.acc_y.push_back(v[10]); ms.acc_z.push_back(v[11]);
            ms.acc_mag.push_back(v[12]);
            ms.max_disp_mag.push_back(v[13]);
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
            if (j.contains("metadata") && j["metadata"].is_object()) {
                auto& m = j["metadata"];
                if (m.contains("d3plot_path") && m["d3plot_path"].is_string())
                    out.d3plot_path = m["d3plot_path"].get<std::string>();
                if (m.contains("num_states") && m["num_states"].is_number())
                    out.num_states = m["num_states"].get<int>();
                if (m.contains("start_time") && m["start_time"].is_number())
                    out.start_time = m["start_time"].get<double>();
                if (m.contains("end_time") && m["end_time"].is_number())
                    out.end_time = m["end_time"].get<double>();
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

            // Max/min principal strain
            if (j.contains("max_principal_strain_history")) {
                for (const auto& s : j["max_principal_strain_history"])
                    out.max_principal_strain.push_back(parseTimeSeries(s));
            }
            if (j.contains("min_principal_strain_history")) {
                for (const auto& s : j["min_principal_strain_history"])
                    out.min_principal_strain.push_back(parseTimeSeries(s));
            }

            // Peak element tensors
            if (j.contains("peak_element_tensors")) {
                for (const auto& t : j["peak_element_tensors"]) {
                    ElementTensorHistory eth;
                    eth.element_id = t.contains("element_id") ? t["element_id"].get<int>() : 0;
                    eth.part_id = t.contains("part_id") ? t["part_id"].get<int>() : 0;
                    eth.reason = t.contains("reason") && t["reason"].is_string() ? t["reason"].get<std::string>() : "";
                    eth.peak_value = t.contains("peak_value") ? t["peak_value"].get<double>() : 0.0;
                    eth.peak_time = t.contains("peak_time") ? t["peak_time"].get<double>() : 0.0;
                    auto getVec = [](const json& j, const char* key) -> std::vector<double> {
                        return j.contains(key) && j[key].is_array() ? j[key].get<std::vector<double>>() : std::vector<double>{};
                    };
                    eth.time = getVec(t, "time");
                    eth.sxx = getVec(t, "sxx"); eth.syy = getVec(t, "syy"); eth.szz = getVec(t, "szz");
                    eth.sxy = getVec(t, "sxy"); eth.syz = getVec(t, "syz"); eth.szx = getVec(t, "szx");
                    out.tensors.push_back(std::move(eth));
                }
            }

            // Element quality
            if (j.contains("element_quality") && j["element_quality"].is_array()) {
                for (const auto& eq : j["element_quality"]) {
                    DeepReportData::ElemQuality q;
                    auto eqd = [&eq](const char* k, double def = 0.0) {
                        return eq.contains(k) && eq[k].is_number() ? eq[k].get<double>() : def;
                    };
                    q.part_id = eq.contains("part_id") ? eq["part_id"].get<int>() : 0;
                    q.part_name = eq.contains("part_name") && eq["part_name"].is_string() ? eq["part_name"].get<std::string>() : "";
                    q.element_type = eq.contains("element_type") && eq["element_type"].is_string() ? eq["element_type"].get<std::string>() : "";
                    q.num_elements = eq.contains("num_elements") ? eq["num_elements"].get<int>() : 0;
                    q.peak_aspect_ratio = eqd("peak_aspect_ratio");
                    q.min_jacobian = eqd("min_jacobian", 1.0);
                    q.peak_warpage = eqd("peak_warpage");
                    q.peak_skewness = eqd("peak_skewness");
                    q.max_volume_change = eqd("max_volume_change");
                    q.max_negative_jacobian_count = eq.contains("max_negative_jacobian_count") ? eq["max_negative_jacobian_count"].get<int>() : 0;
                    // Time series
                    if (eq.contains("data") && eq["data"].is_array()) {
                        for (const auto& d : eq["data"]) {
                            DeepReportData::QualityTimePoint qtp;
                            auto dd = [&d](const char* k, double def = 0.0) {
                                return d.contains(k) && d[k].is_number() ? d[k].get<double>() : def;
                            };
                            qtp.time = dd("time");
                            qtp.ar_max = dd("ar_max");
                            qtp.ar_avg = dd("ar_avg");
                            qtp.vol_min = dd("vol_min", 1.0);
                            qtp.vol_max = dd("vol_max", 1.0);
                            qtp.warp_max = dd("warp_max");
                            qtp.skew_max = dd("skew_max");
                            q.time_series.push_back(qtp);
                        }
                    }
                    out.element_quality.push_back(q);
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

            out.label = j.contains("label") && j["label"].is_string() ? j["label"].get<std::string>() : "";
            out.tier = j.contains("tier") && j["tier"].is_number() ? j["tier"].get<int>() : 0;

            if (j.contains("summary") && j["summary"].is_object()) {
                auto& s = j["summary"];
                auto sd = [&s](const char* k, double def = 0.0) {
                    return s.contains(k) && s[k].is_number() ? s[k].get<double>() : def;
                };
                out.peak_stress_global = sd("peak_stress_global");
                out.peak_stress_part_id = s.contains("peak_stress_part_id") && s["peak_stress_part_id"].is_number()
                    ? s["peak_stress_part_id"].get<int>() : 0;
                out.peak_strain_global = sd("peak_strain_global");
                out.peak_disp_global = sd("peak_disp_global");
                out.energy_ratio_min = sd("energy_ratio_min", 1.0);
            }

            // Safe getter: returns default for missing or null values
            auto safeDouble = [](const json& j, const char* key, double def = 0.0) -> double {
                return j.contains(key) && j[key].is_number() ? j[key].get<double>() : def;
            };
            auto safeStr = [](const json& j, const char* key, const std::string& def = "") -> std::string {
                return j.contains(key) && j[key].is_string() ? j[key].get<std::string>() : def;
            };

            out.yield_stress = j.contains("yield_stress") && j["yield_stress"].is_number() ? j["yield_stress"].get<double>() : 0;

            if (j.contains("metadata") && j["metadata"].is_object()) {
                auto& rm = j["metadata"];
                out.normal_termination = rm.contains("normal_termination") && rm["normal_termination"].is_boolean()
                    ? rm["normal_termination"].get<bool>() : true;
                out.termination_source = rm.contains("termination_source") && rm["termination_source"].is_string()
                    ? rm["termination_source"].get<std::string>() : "";
            }

            if (j.contains("parts")) {
                for (auto& [key, val] : j["parts"].items()) {
                    int pid = std::stoi(key);
                    PartSummary ps;
                    ps.part_id = pid;
                    ps.name = safeStr(val, "name", "Part " + key);
                    ps.peak_stress = safeDouble(val, "peak_stress");
                    ps.time_of_peak_stress = safeDouble(val, "time_of_peak_stress");
                    ps.peak_element_id = val.contains("peak_element_id") && val["peak_element_id"].is_number()
                        ? val["peak_element_id"].get<int>() : 0;
                    ps.peak_strain = safeDouble(val, "peak_strain");
                    ps.peak_max_principal = safeDouble(val, "peak_max_principal");
                    ps.peak_min_principal = safeDouble(val, "peak_min_principal");
                    ps.peak_max_principal_strain = safeDouble(val, "peak_max_principal_strain");
                    ps.peak_min_principal_strain = safeDouble(val, "peak_min_principal_strain");
                    ps.peak_disp = safeDouble(val, "peak_disp_mag");
                    ps.peak_vel = safeDouble(val, "peak_vel_mag");
                    ps.peak_acc = safeDouble(val, "peak_acc_mag");
                    ps.safety_factor = safeDouble(val, "safety_factor");
                    ps.mat_type = safeStr(val, "mat_type");
                    ps.stress_limit = safeDouble(val, "stress_limit");
                    ps.stress_source = safeStr(val, "stress_source");
                    ps.strain_limit = safeDouble(val, "strain_limit");
                    ps.strain_source = safeStr(val, "strain_source");
                    ps.stress_ratio = safeDouble(val, "stress_ratio");
                    ps.strain_ratio = safeDouble(val, "strain_ratio");
                    ps.stress_warning = safeStr(val, "stress_warning", "ok");
                    ps.strain_warning = safeStr(val, "strain_warning", "ok");
                    out.parts[pid] = ps;
                }
            }

            if (j.contains("glstat") && !j["glstat"].is_null()) {
                auto& g = j["glstat"];
                auto gv = [](const json& j, const char* key) -> std::vector<double> {
                    return j.contains(key) && j[key].is_array() ? j[key].get<std::vector<double>>() : std::vector<double>{};
                };
                out.glstat.t = gv(g, "t");
                out.glstat.total_energy = gv(g, "total_energy");
                out.glstat.kinetic_energy = gv(g, "kinetic_energy");
                out.glstat.internal_energy = gv(g, "internal_energy");
                out.glstat.hourglass_energy = gv(g, "hourglass_energy");
                out.glstat.energy_ratio = gv(g, "energy_ratio");
                out.glstat.mass = gv(g, "mass");
                out.glstat.energy_ratio_min = g.contains("energy_ratio_min") && g["energy_ratio_min"].is_number() ? g["energy_ratio_min"].get<double>() : 1.0;
                out.glstat.energy_ratio_max = g.contains("energy_ratio_max") && g["energy_ratio_max"].is_number() ? g["energy_ratio_max"].get<double>() : 1.0;
                out.glstat.has_mass_added = g.contains("has_mass_added") && g["has_mass_added"].is_boolean() ? g["has_mass_added"].get<bool>() : false;
                out.glstat.normal_termination = g.contains("normal_termination") && g["normal_termination"].is_boolean() ? g["normal_termination"].get<bool>() : true;
            }

            // Binout data (rcforc, sleout)
            if (j.contains("binout") && j["binout"].is_object()) {
                auto& bn = j["binout"];
                if (bn.contains("rcforc") && bn["rcforc"].is_array()) {
                    for (const auto& ifc : bn["rcforc"]) {
                        DeepReportData::ContactInterface ci;
                        ci.id = ifc.contains("id") && ifc["id"].is_number() ? ifc["id"].get<int>() : 0;
                        ci.name = ifc.contains("name") && ifc["name"].is_string() ? ifc["name"].get<std::string>() : "";
                        if (ifc.contains("side")) {
                            if (ifc["side"].is_number()) ci.side = ifc["side"].get<int>();
                            else if (ifc["side"].is_string()) {
                                auto s = ifc["side"].get<std::string>();
                                ci.side = (s == "0" || s == "m" || s == "master") ? 0 : 1;
                            }
                        }
                        auto gvb = [](const json& j, const char* key) -> std::vector<double> {
                            return j.contains(key) && j[key].is_array() ? j[key].get<std::vector<double>>() : std::vector<double>{};
                        };
                        ci.t = gvb(ifc, "t");
                        ci.fx = gvb(ifc, "fx"); ci.fy = gvb(ifc, "fy"); ci.fz = gvb(ifc, "fz");
                        ci.fmag = gvb(ifc, "fmag");
                        ci.peak_fmag = ifc.contains("peak_fmag") && ifc["peak_fmag"].is_number() ? ifc["peak_fmag"].get<double>() : 0;
                        out.rcforc.push_back(std::move(ci));
                    }
                }
                if (bn.contains("sleout") && bn["sleout"].is_array()) {
                    for (const auto& sl : bn["sleout"]) {
                        DeepReportData::ContactEnergy ce;
                        ce.id = sl.contains("id") && sl["id"].is_number() ? sl["id"].get<int>() : 0;
                        ce.name = sl.contains("name") && sl["name"].is_string() ? sl["name"].get<std::string>() : "";
                        auto gvb = [](const json& j, const char* key) -> std::vector<double> {
                            return j.contains(key) && j[key].is_array() ? j[key].get<std::vector<double>>() : std::vector<double>{};
                        };
                        ce.t = gvb(sl, "t");
                        ce.total_energy = gvb(sl, "total_energy");
                        ce.friction_energy = gvb(sl, "friction_energy");
                        out.sleout.push_back(std::move(ce));
                    }
                }
                if (bn.contains("matsum") && bn["matsum"].is_object()) {
                    auto& ms = bn["matsum"];
                    auto gvb = [](const json& j, const char* key) -> std::vector<double> {
                        return j.contains(key) && j[key].is_array() ? j[key].get<std::vector<double>>() : std::vector<double>{};
                    };
                    std::vector<double> t_ms = gvb(ms, "t");
                    std::vector<int> ids;
                    if (ms.contains("part_ids") && ms["part_ids"].is_array())
                        ids = ms["part_ids"].get<std::vector<int>>();
                    std::vector<std::string> names;
                    if (ms.contains("part_names") && ms["part_names"].is_array())
                        names = ms["part_names"].get<std::vector<std::string>>();
                    std::vector<std::vector<double>> ie_all, ke_all;
                    if (ms.contains("internal_energy") && ms["internal_energy"].is_array())
                        ie_all = ms["internal_energy"].get<std::vector<std::vector<double>>>();
                    if (ms.contains("kinetic_energy") && ms["kinetic_energy"].is_array())
                        ke_all = ms["kinetic_energy"].get<std::vector<std::vector<double>>>();
                    for (int i = 0; i < (int)ids.size(); ++i) {
                        DeepReportData::MatSumEntry e;
                        e.part_id   = ids[i];
                        e.part_name = (i < (int)names.size()) ? names[i] : "";
                        e.t         = t_ms;
                        if (i < (int)ie_all.size()) e.internal_energy = ie_all[i];
                        if (i < (int)ke_all.size()) e.kinetic_energy  = ke_all[i];
                        out.matsum.push_back(std::move(e));
                    }
                }
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

    // 5. Fallback: if no result.json, build parts from stress_history
    if (out.parts.empty()) {
        double globalMax = 0;
        int globalMaxPid = 0;
        for (const auto& ts : out.stress) {
            PartSummary ps;
            ps.part_id = ts.part_id;
            ps.name = ts.part_name.empty() ? ("Part " + std::to_string(ts.part_id)) : ts.part_name;
            ps.peak_stress = ts.global_max;
            ps.stress_warning = "ok";
            ps.strain_warning = "ok";
            if (ts.global_max > globalMax) { globalMax = ts.global_max; globalMaxPid = ts.part_id; }
            out.parts[ts.part_id] = ps;
        }
        for (const auto& ts : out.strain) {
            auto it = out.parts.find(ts.part_id);
            if (it != out.parts.end()) {
                it->second.peak_strain = ts.global_max;
            }
        }
        out.peak_stress_global = globalMax;
        out.peak_stress_part_id = globalMaxPid;
    }

    // 6. Auto-generate warnings
    if (out.energy_ratio_min > 1.1)
        out.warnings.push_back({"crit", "Energy ratio > 1.10 (" + std::to_string(out.energy_ratio_min) + ") — energy generation detected"});
    else if (out.energy_ratio_min > 1.05)
        out.warnings.push_back({"warn", "Energy ratio > 1.05 (" + std::to_string(out.energy_ratio_min) + ")"});

    for (const auto& [pid, ps] : out.parts) {
        if (ps.stress_warning == "crit")
            out.warnings.push_back({"crit", "Part " + std::to_string(pid) + " (" + ps.name + "): stress exceeds limit (" + std::to_string(ps.peak_stress) + " MPa)"});
        if (ps.strain_warning == "crit")
            out.warnings.push_back({"crit", "Part " + std::to_string(pid) + " (" + ps.name + "): strain exceeds limit (" + std::to_string(ps.peak_strain) + ")"});
    }

    out.loaded = !out.stress.empty() || !out.parts.empty();
    return out.loaded;
}
