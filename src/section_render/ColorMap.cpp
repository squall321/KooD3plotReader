/**
 * @file ColorMap.cpp
 * @brief Implementation of ColorMap
 */

#include "kood3plot/section_render/ColorMap.hpp"
#include <algorithm>
#include <cctype>
#include <cmath>
#include <stdexcept>

namespace kood3plot {
namespace section_render {

// ============================================================
// Helpers
// ============================================================

uint8_t ColorMap::clamp255(double v)
{
    if (v <= 0.0) return 0;
    if (v >= 1.0) return 255;
    return static_cast<uint8_t>(v * 255.0 + 0.5);
}

// ============================================================
// Constructor
// ============================================================

ColorMap::ColorMap(ColorMapType type)
    : type_(type), vmin_(0.0), vmax_(1.0)
{}

// ============================================================
// Range control
// ============================================================

void ColorMap::setRange(double vmin, double vmax)
{
    vmin_ = vmin;
    // Ensure a non-degenerate range
    vmax_ = (vmax > vmin + 1e-12) ? vmax : vmin + 1.0;
}

void ColorMap::setAutoRange(const double* values, int count)
{
    if (!values || count <= 0) { vmin_ = 0.0; vmax_ = 1.0; return; }
    double mn = values[0], mx = values[0];
    for (int i = 1; i < count; ++i) {
        if (values[i] < mn) mn = values[i];
        if (values[i] > mx) mx = values[i];
    }
    setRange(mn, mx);
}

void ColorMap::setGlobalRange(double vmin, double vmax)
{
    setRange(vmin, vmax);
}

// ============================================================
// map()
// ============================================================

RGBA ColorMap::map(double value) const
{
    // Normalise to [0, 1]
    double t = (value - vmin_) / (vmax_ - vmin_);
    t = std::max(0.0, std::min(1.0, t));

    switch (type_) {
        case ColorMapType::Rainbow:   return mapRainbow(t);
        case ColorMapType::Jet:       return mapJet(t);
        case ColorMapType::CoolWarm:  return mapCoolWarm(t);
        case ColorMapType::Grayscale: return mapGrayscale(t);
        case ColorMapType::Fringe:    return mapFringe(t);
    }
    return mapFringe(t);
}

// ============================================================
// Individual colormap implementations
// ============================================================

// HSV-based rainbow: H goes from 240° (blue) to 0° (red)
RGBA ColorMap::mapRainbow(double t) const
{
    // H in [240, 0] degrees as t goes [0, 1]
    double h = (1.0 - t) * 240.0;
    double s = 1.0, v = 1.0;

    // HSV to RGB
    double c  = v * s;
    double h6 = h / 60.0;
    double x  = c * (1.0 - std::abs(std::fmod(h6, 2.0) - 1.0));

    double r = 0, g = 0, b = 0;
    int sect = static_cast<int>(h6);
    switch (sect) {
        case 0: r=c; g=x; break;
        case 1: r=x; g=c; break;
        case 2: g=c; b=x; break;
        case 3: g=x; b=c; break;
        case 4: r=x; b=c; break;
        default: r=c; b=x; break;
    }
    double m = v - c;
    return { clamp255(r+m), clamp255(g+m), clamp255(b+m) };
}

// Jet: blue → cyan → green → yellow → red
RGBA ColorMap::mapJet(double t) const
{
    auto lerp = [](double a, double b, double u) { return a + (b-a)*u; };
    auto seg  = [&](double lo, double hi) {
        return std::max(0.0, std::min(1.0, (t - lo) / (hi - lo)));
    };

    double r = std::max(0.0, std::min(1.0, lerp(1.5, 0.5, std::abs(t - 0.75) / 0.25)));
    double g = std::max(0.0, std::min(1.0, 1.0 - 4.0 * std::abs(t - 0.5)));
    double b = std::max(0.0, std::min(1.0, lerp(0.5, -0.5, std::abs(t - 0.25) / 0.25)));

    // Simpler piecewise version that is faithful to classic jet
    r = clamp255(std::max(0.0, std::min(1.0, 1.5 - std::abs(4.0*t - 3.0))));
    g = clamp255(std::max(0.0, std::min(1.0, 1.5 - std::abs(4.0*t - 2.0))));
    b = clamp255(std::max(0.0, std::min(1.0, 1.5 - std::abs(4.0*t - 1.0))));
    (void)seg;  // suppress unused warning

    return { static_cast<uint8_t>(r),
             static_cast<uint8_t>(g),
             static_cast<uint8_t>(b) };
}

// CoolWarm diverging: blue → white → red
RGBA ColorMap::mapCoolWarm(double t) const
{
    // Blue endpoint: (59, 76, 192), White: (255,255,255), Red: (180, 4, 38)
    // Two-segment linear interpolation
    double r, g, b;
    if (t < 0.5) {
        double u = t * 2.0;
        r = 59.0  + (255.0 - 59.0)  * u;
        g = 76.0  + (255.0 - 76.0)  * u;
        b = 192.0 + (255.0 - 192.0) * u;
    } else {
        double u = (t - 0.5) * 2.0;
        r = 255.0 + (180.0 - 255.0) * u;
        g = 255.0 + (4.0   - 255.0) * u;
        b = 255.0 + (38.0  - 255.0) * u;
    }
    return { clamp255(r/255.0), clamp255(g/255.0), clamp255(b/255.0) };
}

RGBA ColorMap::mapGrayscale(double t) const
{
    uint8_t v = clamp255(t);
    return { v, v, v };
}

// LSPrePost-style 16-level discrete fringe colormap
// Piecewise-linear through 16 control points with sharp band boundaries
RGBA ColorMap::mapFringe(double t) const
{
    // 16-level color table matching LSPrePost's default stress fringe
    // Each level spans 1/16 of [0,1] with interpolation between adjacent stops
    static const uint8_t LUT[16][3] = {
        {  0,   0, 170},  //  0: dark blue
        {  0,   0, 255},  //  1: blue
        {  0,  85, 255},  //  2: blue-cyan
        {  0, 170, 255},  //  3: cyan-blue
        {  0, 255, 255},  //  4: cyan
        {  0, 255, 170},  //  5: cyan-green
        {  0, 255,  85},  //  6: green-cyan
        {  0, 255,   0},  //  7: green
        { 85, 255,   0},  //  8: green-yellow
        {170, 255,   0},  //  9: yellow-green
        {255, 255,   0},  // 10: yellow
        {255, 200,   0},  // 11: yellow-orange
        {255, 140,   0},  // 12: orange
        {255,  80,   0},  // 13: red-orange
        {255,   0,   0},  // 14: red
        {170,   0,   0},  // 15: dark red
    };
    constexpr int N = 16;

    // Map t to float index in [0, N-1]
    double fi = t * (N - 1);
    int lo = static_cast<int>(fi);
    if (lo < 0) lo = 0;
    if (lo >= N - 1) return {LUT[N-1][0], LUT[N-1][1], LUT[N-1][2]};
    double f = fi - lo;

    return {
        static_cast<uint8_t>(LUT[lo][0] + f * (LUT[lo+1][0] - LUT[lo][0]) + 0.5),
        static_cast<uint8_t>(LUT[lo][1] + f * (LUT[lo+1][1] - LUT[lo][1]) + 0.5),
        static_cast<uint8_t>(LUT[lo][2] + f * (LUT[lo+1][2] - LUT[lo][2]) + 0.5)
    };
}

// ============================================================
// partColor — categorical color palette
// ============================================================

RGBA ColorMap::partColor(int32_t part_id)
{
    // 20-color qualitative palette (Tableau 20-like, darkened slightly)
    static const RGBA palette[] = {
        { 31, 119, 180}, {174, 199, 232}, { 44, 160,  44}, {152, 223, 138},
        {214,  39,  40}, {255, 152, 150}, {148, 103, 189}, {197, 176, 213},
        {140,  86,  75}, {196, 156, 148}, {227, 119, 194}, {247, 182, 210},
        {127, 127, 127}, {199, 199, 199}, {188, 189,  34}, {219, 219, 141},
        { 23, 190, 207}, {158, 218, 229}, {255, 127,  14}, {255, 187, 120},
    };
    constexpr int PALETTE_SIZE = static_cast<int>(sizeof(palette)/sizeof(palette[0]));

    // Deterministic mapping: use absolute value of part_id modulo palette size
    int idx = static_cast<int>(static_cast<uint32_t>(part_id)) % PALETTE_SIZE;
    return palette[idx];
}

// ============================================================
// parseType
// ============================================================

ColorMapType ColorMap::parseType(const std::string& name)
{
    std::string lower(name.size(), '\0');
    std::transform(name.begin(), name.end(), lower.begin(),
                   [](unsigned char c){ return static_cast<char>(std::tolower(c)); });

    if (lower == "rainbow")                          return ColorMapType::Rainbow;
    if (lower == "jet")                              return ColorMapType::Jet;
    if (lower == "coolwarm" || lower == "cool_warm") return ColorMapType::CoolWarm;
    if (lower == "grayscale" || lower == "gray")     return ColorMapType::Grayscale;
    if (lower == "fringe" || lower == "lsprepost")   return ColorMapType::Fringe;

    return ColorMapType::Fringe;  // default — matches LSPrePost
}

} // namespace section_render
} // namespace kood3plot
