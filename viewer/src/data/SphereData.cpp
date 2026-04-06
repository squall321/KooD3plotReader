#include "data/SphereData.hpp"
#include <nlohmann/json.hpp>
#include <fstream>
#include <iostream>
#include <cmath>
#include <algorithm>

using json = nlohmann::json;

// Try to decode direction from angle name (cube geometry: faces/edges/corners)
static bool angleNameToDirection(const std::string& name, double& x, double& y, double& z) {
    x = y = z = 0;
    std::string n = name;
    for (auto& c : n) c = toupper(c);

    if (n.find("RIGHT") != std::string::npos) x = 1;
    if (n.find("LEFT") != std::string::npos) x = -1;
    if (n.find("TOP") != std::string::npos) y = 1;
    if (n.find("BOTTOM") != std::string::npos) y = -1;
    if (n.find("BACK") != std::string::npos) z = -1;
    if (n.find("FRONT") != std::string::npos) z = 1;

    double mag = std::sqrt(x*x + y*y + z*z);
    if (mag > 0.01) { x /= mag; y /= mag; z /= mag; return true; }
    return false;
}

static void directionToLonLat(double x, double y, double z, double& lon, double& lat) {
    lon = std::atan2(x, -z) * 180.0 / M_PI;
    lat = std::asin(std::max(-1.0, std::min(1.0, y))) * 180.0 / M_PI;
    lat = std::max(-85.0, std::min(85.0, lat));
}

void eulerToLonLat(double rollDeg, double pitchDeg, double yawDeg,
                    const std::string& name, double& lon, double& lat) {
    // 1. Try name-based decoding first (correct for cube faces/edges/corners)
    double dx, dy, dz;
    if (angleNameToDirection(name, dx, dy, dz)) {
        directionToLonLat(dx, dy, dz, lon, lat);
        return;
    }

    // 2. Euler-based: Ry(pitch) * Rx(roll) * [0, 0, -1] → impact direction
    double r = rollDeg * M_PI / 180.0;
    double p = pitchDeg * M_PI / 180.0;

    double y1 = std::sin(r);
    double z1 = -std::cos(r);

    double x2 = z1 * std::sin(p);
    double y2 = y1;
    double z2 = z1 * std::cos(p);

    lon = std::atan2(x2, -z2) * 180.0 / M_PI;
    lat = std::asin(std::max(-1.0, std::min(1.0, y2))) * 180.0 / M_PI;
    lat = std::max(-85.0, std::min(85.0, lat));
}

bool loadSphereData(const std::string& jsonPath, SphereData& out) {
    try {
        std::ifstream f(jsonPath);
        if (!f) {
            out.error = "Cannot open: " + jsonPath;
            return false;
        }
        json j = json::parse(f);

        auto sd = [](const json& j, const char* k, double def = 0.0) -> double {
            return j.contains(k) && j[k].is_number() ? j[k].get<double>() : def;
        };
        auto ss = [](const json& j, const char* k, const std::string& def = "") -> std::string {
            return j.contains(k) && j[k].is_string() ? j[k].get<std::string>() : def;
        };
        auto si = [](const json& j, const char* k, int def = 0) -> int {
            return j.contains(k) && j[k].is_number() ? j[k].get<int>() : def;
        };

        out.project_name = ss(j, "project_name");
        out.doe_strategy = ss(j, "doe_strategy");
        out.total_runs = si(j, "total_runs");
        out.successful_runs = si(j, "successful_runs");
        out.failed_runs = si(j, "failed_runs");
        out.angular_spacing = sd(j, "angular_spacing_deg");
        out.sphere_coverage = sd(j, "sphere_coverage");
        out.yield_stress = sd(j, "yield_stress");
        out.test_dir = ss(j, "test_dir");

        // Parts info
        if (j.contains("parts") && j["parts"].is_object()) {
            for (auto& [key, val] : j["parts"].items()) {
                int pid = std::stoi(key);
                SpherePartInfo pi;
                pi.part_id = pid;
                pi.name = ss(val, "part_name", ss(val, "name", "Part " + key));
                pi.group = ss(val, "group");
                out.parts[pid] = pi;
            }
        }

        // Results
        const char* resultsKey = j.contains("results_summary") ? "results_summary" : "results";
        if (j.contains(resultsKey) && j[resultsKey].is_array()) {
            for (const auto& r : j[resultsKey]) {
                AngleResult ar;
                ar.run_folder = ss(r, "run_folder");
                ar.num_states = si(r, "num_states");

                if (r.contains("angle") && r["angle"].is_object()) {
                    auto& a = r["angle"];
                    ar.angle.name = ss(a, "name");
                    ar.angle.roll = sd(a, "roll");
                    ar.angle.pitch = sd(a, "pitch");
                    ar.angle.yaw = sd(a, "yaw");
                    ar.angle.category = ss(a, "category");
                }

                // Compute lon/lat
                eulerToLonLat(ar.angle.roll, ar.angle.pitch, ar.angle.yaw,
                              ar.angle.name, ar.angle.lon, ar.angle.lat);

                auto parseTS = [](const json& j, const char* tKey, const char* vKey, TimeSeries& ts) {
                    if (j.contains(tKey) && j[tKey].is_object()) {
                        auto& obj = j[tKey];
                        if (obj.contains("t") && obj["t"].is_array())
                            ts.t = obj["t"].get<std::vector<double>>();
                        if (obj.contains(vKey) && obj[vKey].is_array())
                            ts.values = obj[vKey].get<std::vector<double>>();
                    }
                };

                if (r.contains("parts") && r["parts"].is_object()) {
                    for (auto& [pk, pv] : r["parts"].items()) {
                        int pid = std::stoi(pk);
                        AnglePartData pd;
                        pd.peak_stress = sd(pv, "peak_stress");
                        pd.peak_strain = sd(pv, "peak_strain");
                        pd.peak_g = sd(pv, "peak_g");
                        pd.peak_disp = sd(pv, "peak_disp");
                        parseTS(pv, "stress_ts", "max", pd.stress_ts);
                        parseTS(pv, "strain_ts", "max", pd.strain_ts);
                        parseTS(pv, "g_ts", "g", pd.g_ts);
                        parseTS(pv, "disp_ts", "mag", pd.disp_ts);
                        ar.parts[pid] = pd;
                    }
                }

                out.results.push_back(std::move(ar));
            }
        }

        // Compute worst cases
        for (int ri = 0; ri < (int)out.results.size(); ++ri) {
            for (auto& [pid, pd] : out.results[ri].parts) {
                if (pd.peak_stress > out.worst_stress) {
                    out.worst_stress = pd.peak_stress;
                    out.worst_stress_angle = ri;
                }
                if (pd.peak_g > out.worst_g) {
                    out.worst_g = pd.peak_g;
                    out.worst_g_angle = ri;
                }
            }
        }

        out.loaded = !out.results.empty();
        return out.loaded;

    } catch (const std::exception& e) {
        out.error = std::string("JSON parse error: ") + e.what();
        return false;
    }
}
