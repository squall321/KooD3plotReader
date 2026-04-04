#include "app/SphereReportApp.hpp"
#include <imgui.h>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>
#include <algorithm>
#include <fstream>
#include <iostream>

// Export a self-contained HTML report.
// Contains: summary KPIs, inline SVG Mollweide map, worst angles table,
// part failure/safety table, and automated findings.
// No external dependencies — single .html file, opens in any browser.

static std::string htmlEscape(const std::string& s) {
    std::string out;
    out.reserve(s.size());
    for (char c : s) {
        switch (c) {
            case '&':  out += "&amp;";  break;
            case '<':  out += "&lt;";   break;
            case '>':  out += "&gt;";   break;
            case '"':  out += "&quot;"; break;
            default:   out += c;        break;
        }
    }
    return out;
}

// Mollweide → SVG coordinate (centred at cx,cy, half-widths rx,ry)
static void mollweideSVG(double lon, double lat,
                          double cx, double cy, double rx, double ry,
                          double& sx, double& sy) {
    double lonR = lon * M_PI / 180.0, latR = lat * M_PI / 180.0;
    double theta = latR;
    for (int i = 0; i < 20; ++i) {
        double f  = 2*theta + std::sin(2*theta) - M_PI*std::sin(latR);
        double fp = 2 + 2*std::cos(2*theta);
        if (std::abs(fp) < 1e-12) break;
        double dt = f / fp;
        if (std::abs(dt) > 0.3) dt = dt > 0 ? 0.3 : -0.3;
        theta -= dt;
        if (std::abs(dt) < 1e-7) break;
    }
    double mx = (2.0*std::sqrt(2.0)/M_PI) * lonR * std::cos(theta);
    double my = std::sqrt(2.0) * std::sin(theta);
    sx = cx + mx / (2.0*std::sqrt(2.0)) * rx;
    sy = cy - my / std::sqrt(2.0) * ry;
}

// Jet colourmap → hex string
static std::string jetHex(double norm) {
    norm = std::max(0.0, std::min(1.0, norm));
    double r, g, b;
    if      (norm < 0.25) { r = 0;              g = norm/0.25;        b = 1; }
    else if (norm < 0.5)  { r = 0;              g = 1;                b = 1-(norm-0.25)/0.25; }
    else if (norm < 0.75) { r = (norm-0.5)/0.25; g = 1;               b = 0; }
    else                  { r = 1;              g = 1-(norm-0.75)/0.25; b = 0; }
    char buf[16];
    snprintf(buf, sizeof(buf), "#%02x%02x%02x",
             (int)(r*255), (int)(g*255), (int)(b*255));
    return buf;
}

static std::string safetyColor(double sf) {
    if (sf < 1.0) return "#f7768e";
    if (sf < 1.5) return "#e0af68";
    return "#9ece6a";
}

void SphereReportApp::exportHTMLReport() {
    std::string filename = data_.project_name.empty()
        ? "sphere_report.html"
        : data_.project_name + "_sphere_report.html";

    // Replace spaces with underscores
    for (char& c : filename) if (c == ' ') c = '_';

    std::ofstream f(filename);
    if (!f.is_open()) {
        std::cerr << "[Export] Failed to open: " << filename << "\n";
        return;
    }

    // Pre-compute value range
    double vmin = 1e30, vmax = -1e30;
    for (int ri = 0; ri < (int)data_.results.size(); ++ri) {
        for (auto& [pid, pd] : data_.results[ri].parts)
            vmax = std::max(vmax, pd.peak_stress);
    }
    vmin = 0;
    double vrange = std::max(vmax - vmin, 1e-10);

    // SVG dimensions
    const double svgW = 700, svgH = 350;
    const double cx = svgW/2, cy = svgH/2;
    const double rx = svgW*0.44, ry = svgH*0.44;

    // ---- Top 20 worst angles ----
    std::vector<std::pair<double,int>> ranked;
    ranked.reserve(data_.results.size());
    for (int ri = 0; ri < (int)data_.results.size(); ++ri) {
        double worst = 0;
        for (auto& [pid, pd] : data_.results[ri].parts)
            worst = std::max(worst, pd.peak_stress);
        ranked.push_back({worst, ri});
    }
    std::sort(ranked.begin(), ranked.end(), [](auto& a, auto& b){ return a.first > b.first; });

    // ---- Part safety factors ----
    struct PartSF { int pid; std::string name; double worstStress; double sf; std::string worstAngle; };
    std::vector<PartSF> partSFs;
    for (auto& [pid, pi] : data_.parts) {
        double worst = 0; std::string wAngle;
        for (int ri = 0; ri < (int)data_.results.size(); ++ri) {
            auto it = data_.results[ri].parts.find(pid);
            if (it != data_.results[ri].parts.end() && it->second.peak_stress > worst) {
                worst = it->second.peak_stress;
                wAngle = data_.results[ri].angle.name;
            }
        }
        double sf = worst > 0 && data_.yield_stress > 0 ? data_.yield_stress / worst : 999;
        partSFs.push_back({pid, pi.name, worst, sf, wAngle});
    }
    std::sort(partSFs.begin(), partSFs.end(), [](auto& a, auto& b){ return a.sf < b.sf; });

    // ============================================================
    // Write HTML
    // ============================================================
    f << R"(<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Sphere Report — )" << htmlEscape(data_.project_name) << R"(</title>
<style>
  body{background:#0e1017;color:#c0c5d0;font-family:Consolas,'Courier New',monospace;margin:0;padding:20px}
  h1{color:#7dcfb6;margin-bottom:4px}
  h2{color:#7aa2f7;border-bottom:1px solid #2a2d3e;padding-bottom:4px;margin-top:30px}
  .kpi-row{display:flex;gap:16px;flex-wrap:wrap;margin:16px 0}
  .kpi{background:#12141f;border:1px solid #2a2d3e;border-radius:8px;padding:12px 20px;min-width:120px}
  .kpi .label{font-size:11px;color:#565f89;text-transform:uppercase;letter-spacing:1px}
  .kpi .value{font-size:26px;font-weight:bold;margin:4px 0}
  .kpi .unit{font-size:11px;color:#565f89}
  table{width:100%;border-collapse:collapse;margin-top:10px;font-size:13px}
  th{background:#12141f;color:#7aa2f7;padding:8px 12px;text-align:left;border-bottom:1px solid #2a2d3e}
  td{padding:6px 12px;border-bottom:1px solid #1a1d2e}
  tr:hover td{background:#12141f}
  .accent{color:#7dcfb6} .dim{color:#565f89} .red{color:#f7768e} .yellow{color:#e0af68}
  .bar{display:inline-block;height:10px;border-radius:3px;vertical-align:middle;margin-right:6px}
  svg{display:block;margin:0 auto;border-radius:8px;background:#0d0f1a}
  .finding{background:#12141f;border-left:4px solid;border-radius:0 6px 6px 0;padding:10px 16px;margin:8px 0}
  .find-ok{border-color:#9ece6a} .find-warn{border-color:#e0af68} .find-crit{border-color:#f7768e} .find-info{border-color:#7aa2f7}
  footer{margin-top:40px;color:#565f89;font-size:11px;text-align:center}
</style>
</head>
<body>
)";

    f << "<h1>Sphere Drop Test Report</h1>\n";
    f << "<p class='dim'>Project: <span class='accent'>" << htmlEscape(data_.project_name) << "</span>"
      << "  &nbsp;|&nbsp;  DOE: " << htmlEscape(data_.doe_strategy)
      << "  &nbsp;|&nbsp;  Generated by KooViewer</p>\n";

    // KPI row
    f << "<div class='kpi-row'>\n";
    auto kpi = [&](const char* label, const std::string& value, const char* unit, const char* col){
        f << "<div class='kpi'><div class='label'>" << label << "</div>"
          << "<div class='value' style='color:" << col << "'>" << htmlEscape(value) << "</div>"
          << "<div class='unit'>" << unit << "</div></div>\n";
    };
    char buf[64];
    snprintf(buf, sizeof(buf), "%d / %d", data_.successful_runs, data_.total_runs);
    kpi("Cases",        buf,                    data_.doe_strategy.c_str(), "#7dcfb6");
    snprintf(buf, sizeof(buf), "%.1f", data_.worst_stress);
    kpi("Worst Stress", buf,                    "MPa",   "#f7768e");
    snprintf(buf, sizeof(buf), "%.1f°", data_.angular_spacing);
    kpi("Spacing",      buf,                    "",      "#7aa2f7");
    snprintf(buf, sizeof(buf), "%.0f%%", data_.sphere_coverage * 100);
    kpi("Coverage",     buf,                    "",      "#bb9af7");
    if (data_.yield_stress > 0 && data_.worst_stress > 0) {
        double gsf = data_.yield_stress / data_.worst_stress;
        snprintf(buf, sizeof(buf), "%.3f", gsf);
        kpi("Global SF",  buf,                  gsf < 1 ? "FAIL" : gsf < 1.5 ? "LOW" : "OK",
            gsf < 1 ? "#f7768e" : gsf < 1.5 ? "#e0af68" : "#9ece6a");
    }
    snprintf(buf, sizeof(buf), "%d", (int)data_.parts.size());
    kpi("Parts",        buf,                    "",      "#565f89");
    f << "</div>\n";

    // Mollweide SVG
    f << "<h2>Impact Direction Map (Stress)</h2>\n";
    f << "<svg width='" << (int)svgW << "' height='" << (int)svgH << "' xmlns='http://www.w3.org/2000/svg'>\n";
    // Ellipse background
    f << "<ellipse cx='" << cx << "' cy='" << cy
      << "' rx='" << rx << "' ry='" << ry
      << "' fill='#0d0f1a' stroke='#2a2d3e' stroke-width='1.5'/>\n";
    // Grid lines
    for (int lat = -60; lat <= 60; lat += 30) {
        f << "<polyline fill='none' stroke='#2a2d3e' stroke-width='0.5' points='";
        for (int lon = -180; lon <= 180; lon += 5) {
            double sx, sy;
            mollweideSVG(lon, lat, cx, cy, rx, ry, sx, sy);
            f << sx << "," << sy << " ";
        }
        f << "'/>\n";
    }
    // Data dots
    for (int ri = 0; ri < (int)data_.results.size(); ++ri) {
        auto& r = data_.results[ri];
        double worst = 0;
        for (auto& [pid, pd] : r.parts) worst = std::max(worst, pd.peak_stress);
        double norm = (worst - vmin) / vrange;
        double sx, sy;
        mollweideSVG(r.angle.lon, r.angle.lat, cx, cy, rx, ry, sx, sy);
        float radius = 4.0f + (float)norm * 4.0f;
        f << "<circle cx='" << (int)sx << "' cy='" << (int)sy
          << "' r='" << radius << "' fill='" << jetHex(norm)
          << "' opacity='0.85'>\n"
          << "<title>" << htmlEscape(r.angle.name) << ": " << (int)worst << " MPa</title></circle>\n";
    }
    // Colorbar
    {
        double cbX = svgW - 40, cbY = 20, cbH = svgH - 40;
        for (int i = 0; i < (int)cbH; ++i) {
            double norm = 1.0 - (double)i / cbH;
            f << "<line x1='" << cbX << "' y1='" << (cbY+i)
              << "' x2='" << (cbX+14) << "' y2='" << (cbY+i)
              << "' stroke='" << jetHex(norm) << "'/>\n";
        }
        f << "<text x='" << (cbX-4) << "' y='" << (cbY+12) << "' fill='#c0c5d0' font-size='11' text-anchor='end'>"
          << (int)vmax << " MPa</text>\n";
        f << "<text x='" << (cbX-4) << "' y='" << (cbY+cbH) << "' fill='#c0c5d0' font-size='11' text-anchor='end'>"
          << (int)vmin << "</text>\n";
    }
    f << "</svg>\n";

    // Top 20 worst angles table
    f << "<h2>Top 20 Worst Impact Directions</h2>\n";
    f << "<table><tr><th>#</th><th>Direction</th><th>Category</th>"
      << "<th>Roll</th><th>Pitch</th><th>Peak Stress (MPa)</th><th>Bar</th></tr>\n";
    int nShow = std::min(20, (int)ranked.size());
    for (int i = 0; i < nShow; ++i) {
        auto& [val, ri] = ranked[i];
        auto& r = data_.results[ri];
        double norm = (val - vmin) / vrange;
        int barW = (int)(norm * 200);
        f << "<tr><td class='dim'>" << (i+1) << "</td>"
          << "<td class='accent'>" << htmlEscape(r.angle.name) << "</td>"
          << "<td class='dim'>" << htmlEscape(r.angle.category) << "</td>"
          << "<td>" << (int)r.angle.roll << "</td>"
          << "<td>" << (int)r.angle.pitch << "</td>"
          << "<td>" << (int)val << "</td>"
          << "<td><span class='bar' style='width:" << barW << "px;background:" << jetHex(norm) << "'></span></td>"
          << "</tr>\n";
    }
    f << "</table>\n";

    // Part safety factor table
    if (!partSFs.empty()) {
        f << "<h2>Part Safety Factors</h2>\n";
        f << "<table><tr><th>Part ID</th><th>Name</th><th>Peak Stress (MPa)</th>"
          << "<th>Worst Angle</th><th>Safety Factor</th><th>Status</th></tr>\n";
        for (auto& p : partSFs) {
            std::string sfStr = p.sf >= 999 ? "—" : [&]{ char b[32]; snprintf(b,sizeof(b),"%.3f",p.sf); return std::string(b); }();
            std::string status = p.sf >= 999 ? "—" : p.sf < 1.0 ? "FAIL" : p.sf < 1.5 ? "LOW" : "OK";
            std::string col    = safetyColor(p.sf >= 999 ? 2.0 : p.sf);
            f << "<tr><td class='dim'>" << p.pid << "</td>"
              << "<td>" << htmlEscape(p.name) << "</td>"
              << "<td>" << (int)p.worstStress << "</td>"
              << "<td class='accent'>" << htmlEscape(p.worstAngle) << "</td>"
              << "<td style='color:" << col << ";font-weight:bold'>" << sfStr << "</td>"
              << "<td style='color:" << col << "'>" << status << "</td></tr>\n";
        }
        f << "</table>\n";
    }

    // Findings
    f << "<h2>Automated Findings</h2>\n";
    auto finding = [&](const char* cls, const char* level, const char* title, const std::string& detail){
        f << "<div class='finding " << cls << "'>"
          << "<strong>" << level << " &mdash; " << title << "</strong><br>"
          << "<span class='dim'>" << htmlEscape(detail) << "</span></div>\n";
    };

    snprintf(buf, sizeof(buf), "%d/%d runs completed. DOE: %s, Spacing: %.1f°, Coverage: %.0f%%",
             data_.successful_runs, data_.total_runs, data_.doe_strategy.c_str(),
             data_.angular_spacing, data_.sphere_coverage * 100);
    finding(data_.sphere_coverage >= 0.9 ? "find-ok" : "find-warn", "INFO", "Simulation Coverage", buf);

    if (data_.worst_stress_angle >= 0) {
        auto& wr = data_.results[data_.worst_stress_angle];
        snprintf(buf, sizeof(buf), "Peak stress %.1f MPa at direction %s (Roll=%.1f, Pitch=%.1f)",
                 data_.worst_stress, wr.angle.name.c_str(), wr.angle.roll, wr.angle.pitch);
        bool exceed = data_.yield_stress > 0 && data_.worst_stress > data_.yield_stress;
        finding(exceed ? "find-crit" : "find-warn", exceed ? "CRITICAL" : "WARNING", "Worst Case Stress", buf);
    }

    if (data_.yield_stress > 0 && data_.worst_stress > 0) {
        double sf = data_.yield_stress / data_.worst_stress;
        snprintf(buf, sizeof(buf), "Global SF = %.3f (Yield=%.0f / Peak=%.0f MPa) — %s",
                 sf, data_.yield_stress, data_.worst_stress,
                 sf < 1.0 ? "EXCEEDS YIELD" : sf < 1.5 ? "Low margin" : "Acceptable");
        finding(sf < 1.0 ? "find-crit" : sf < 1.5 ? "find-warn" : "find-ok",
                sf < 1.0 ? "CRITICAL" : sf < 1.5 ? "WARNING" : "OK",
                "Safety Factor Assessment", buf);
    }

    snprintf(buf, sizeof(buf), "%d parts analyzed across %d directions = %d data points.",
             (int)data_.parts.size(), (int)data_.results.size(),
             (int)(data_.parts.size() * data_.results.size()));
    finding("find-info", "INFO", "Analysis Scope", buf);

    f << "<footer>Generated by KooViewer &mdash; KooD3plotReader &mdash; "
      << htmlEscape(data_.project_name) << "</footer>\n";
    f << "</body></html>\n";

    f.close();
    std::cout << "[Export] HTML report saved: " << filename << "\n";
}
