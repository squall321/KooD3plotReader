/**
 * @file SoftwareRasterizer.cpp
 * @brief CPU software rasterizer (full implementation)
 *
 * Polygon rendering: fan-triangulate the polygon (v0, vi, vi+1), then
 * for each triangle run a scanline rasterizer with barycentric interpolation.
 *
 * Edge rendering: Xiaolin Wu thick-line approximation (integer Bresenham
 * with per-pixel circle stamp for thickness).
 *
 * PNG output: libpng RGBA write (linked via PNG::PNG in CMakeLists).
 */

#include "kood3plot/section_render/SoftwareRasterizer.hpp"
#include <png.h>
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <stdexcept>

namespace kood3plot {
namespace section_render {

// ============================================================
// Constructor / clear / pixel ops (already existed, kept as-is)
// ============================================================

SoftwareRasterizer::SoftwareRasterizer(int32_t width, int32_t height, int32_t ss_factor)
    : width_(width), height_(height), ss_factor_(ss_factor)
    , ss_width_(width * ss_factor), ss_height_(height * ss_factor)
{
    buffer_.assign(static_cast<size_t>(ss_width_) * ss_height_ * 4, 0);
}

void SoftwareRasterizer::clear(RGBA color)
{
    for (int32_t y = 0; y < ss_height_; ++y)
        for (int32_t x = 0; x < ss_width_; ++x)
            setPixel(x, y, color);
}

void SoftwareRasterizer::setPixel(int32_t x, int32_t y, RGBA color)
{
    if (x < 0 || x >= ss_width_ || y < 0 || y >= ss_height_) return;
    size_t idx = (static_cast<size_t>(y) * ss_width_ + x) * 4;
    buffer_[idx+0] = color.r; buffer_[idx+1] = color.g;
    buffer_[idx+2] = color.b; buffer_[idx+3] = color.a;
}

RGBA SoftwareRasterizer::getPixel(int32_t x, int32_t y) const
{
    if (x < 0 || x >= ss_width_ || y < 0 || y >= ss_height_) return {};
    size_t idx = (static_cast<size_t>(y) * ss_width_ + x) * 4;
    return { buffer_[idx], buffer_[idx+1], buffer_[idx+2], buffer_[idx+3] };
}

// ============================================================
// Triangle rasterizer (used by both contour and flat fills)
// ============================================================

namespace {

// Barycentric weights for point P inside triangle (v0,v1,v2)
// Returns false if area is degenerate
bool baryWeights(double px, double py,
                  double x0, double y0,
                  double x1, double y1,
                  double x2, double y2,
                  double& l0, double& l1, double& l2)
{
    double denom = (y1-y2)*(x0-x2) + (x2-x1)*(y0-y2);
    if (std::abs(denom) < 1e-9) return false;
    l0 = ((y1-y2)*(px-x2) + (x2-x1)*(py-y2)) / denom;
    l1 = ((y2-y0)*(px-x2) + (x0-x2)*(py-y2)) / denom;
    l2 = 1.0 - l0 - l1;
    return true;
}

void rasterizeTriangle(
    double ax, double ay, RGBA ca,
    double bx, double by, RGBA cb,
    double cx, double cy, RGBA cc,
    std::vector<uint8_t>& buf, int32_t W, int32_t H)
{
    int xmin = std::max(0,   static_cast<int>(std::min({ax,bx,cx})));
    int xmax = std::min(W-1, static_cast<int>(std::max({ax,bx,cx})) + 1);
    int ymin = std::max(0,   static_cast<int>(std::min({ay,by,cy})));
    int ymax = std::min(H-1, static_cast<int>(std::max({ay,by,cy})) + 1);

    for (int y = ymin; y <= ymax; ++y) {
        for (int x = xmin; x <= xmax; ++x) {
            double l0, l1, l2;
            if (!baryWeights(x+0.5, y+0.5, ax,ay, bx,by, cx,cy, l0,l1,l2)) continue;
            if (l0 < 0 || l1 < 0 || l2 < 0) continue;

            RGBA color{
                static_cast<uint8_t>(l0*ca.r + l1*cb.r + l2*cc.r),
                static_cast<uint8_t>(l0*ca.g + l1*cb.g + l2*cc.g),
                static_cast<uint8_t>(l0*ca.b + l1*cb.b + l2*cc.b),
                255
            };
            size_t idx = (static_cast<size_t>(y)*W + x)*4;
            buf[idx+0] = color.r; buf[idx+1] = color.g;
            buf[idx+2] = color.b; buf[idx+3] = color.a;
        }
    }
}

/// Alpha-blending variant: src_color over existing pixel
void rasterizeTriangleAlpha(
    double ax, double ay,
    double bx, double by,
    double cx, double cy,
    RGBA flat_color, float alpha,
    std::vector<uint8_t>& buf, int32_t W, int32_t H)
{
    if (alpha <= 0.0f) return;
    if (alpha >= 1.0f) {
        rasterizeTriangle(ax,ay,flat_color, bx,by,flat_color, cx,cy,flat_color, buf,W,H);
        return;
    }
    int xmin = std::max(0,   static_cast<int>(std::min({ax,bx,cx})));
    int xmax = std::min(W-1, static_cast<int>(std::max({ax,bx,cx})) + 1);
    int ymin = std::max(0,   static_cast<int>(std::min({ay,by,cy})));
    int ymax = std::min(H-1, static_cast<int>(std::max({ay,by,cy})) + 1);

    for (int y = ymin; y <= ymax; ++y) {
        for (int x = xmin; x <= xmax; ++x) {
            double l0, l1, l2;
            if (!baryWeights(x+0.5, y+0.5, ax,ay, bx,by, cx,cy, l0,l1,l2)) continue;
            if (l0 < 0 || l1 < 0 || l2 < 0) continue;

            size_t idx = (static_cast<size_t>(y)*W + x)*4;
            float inv = 1.0f - alpha;
            buf[idx+0] = static_cast<uint8_t>(alpha*flat_color.r + inv*buf[idx+0]);
            buf[idx+1] = static_cast<uint8_t>(alpha*flat_color.g + inv*buf[idx+1]);
            buf[idx+2] = static_cast<uint8_t>(alpha*flat_color.b + inv*buf[idx+2]);
            buf[idx+3] = 255;
        }
    }
}

} // anonymous namespace

// ============================================================
// drawPolygonContour — Gouraud shading via fan triangulation
// ============================================================

void SoftwareRasterizer::drawPolygonContour(const ClipPolygon& polygon,
                                             const ColorMap& cmap,
                                             const SectionCamera& camera)
{
    if (polygon.size() < 3) return;

    // Project vertices and look up per-vertex color
    int n = static_cast<int>(polygon.size());
    std::vector<double> sx(n), sy(n);
    std::vector<RGBA>   sc(n);
    for (int i = 0; i < n; ++i) {
        Vec2 p = camera.project(polygon[i].position);
        // Scale to supersampled resolution
        sx[i] = p.x * ss_factor_;
        sy[i] = p.y * ss_factor_;
        sc[i] = cmap.map(polygon[i].value);
    }

    // Fan triangulation: (0, i, i+1) for i in [1, n-2]
    for (int i = 1; i < n-1; ++i) {
        rasterizeTriangle(
            sx[0], sy[0], sc[0],
            sx[i], sy[i], sc[i],
            sx[i+1], sy[i+1], sc[i+1],
            buffer_, ss_width_, ss_height_);
    }
}

// ============================================================
// drawPolygonFlat — uniform color fill
// ============================================================

void SoftwareRasterizer::drawPolygonFlat(const ClipPolygon& polygon,
                                          RGBA color,
                                          const SectionCamera& camera,
                                          float alpha)
{
    if (polygon.size() < 3) return;

    int n = static_cast<int>(polygon.size());
    std::vector<double> sx(n), sy(n);
    for (int i = 0; i < n; ++i) {
        Vec2 p = camera.project(polygon[i].position);
        sx[i] = p.x * ss_factor_;
        sy[i] = p.y * ss_factor_;
    }

    for (int i = 1; i < n-1; ++i) {
        rasterizeTriangleAlpha(
            sx[0], sy[0],
            sx[i], sy[i],
            sx[i+1], sy[i+1],
            color, alpha,
            buffer_, ss_width_, ss_height_);
    }
}

// ============================================================
// drawEdge — thick line segment (shell cross-sections)
// ============================================================

void SoftwareRasterizer::drawEdge(const ClipPolygon& segment,
                                   const ColorMap& cmap,
                                   const SectionCamera& camera,
                                   int32_t thickness)
{
    if (segment.size() != 2) return;

    Vec2 a = camera.project(segment[0].position);
    Vec2 b = camera.project(segment[1].position);

    double ax = a.x * ss_factor_, ay = a.y * ss_factor_;
    double bx = b.x * ss_factor_, by = b.y * ss_factor_;

    RGBA ca = cmap.map(segment[0].value);
    RGBA cb = cmap.map(segment[1].value);

    double dx = bx - ax, dy = by - ay;
    double len = std::sqrt(dx*dx + dy*dy);
    if (len < 0.5) return;

    int steps = static_cast<int>(len) + 1;
    int half_t = thickness / 2;

    for (int s = 0; s <= steps; ++s) {
        double t = static_cast<double>(s) / static_cast<double>(steps);
        double px = ax + t*dx;
        double py = ay + t*dy;
        // Interpolate color
        RGBA c{
            static_cast<uint8_t>((1-t)*ca.r + t*cb.r),
            static_cast<uint8_t>((1-t)*ca.g + t*cb.g),
            static_cast<uint8_t>((1-t)*ca.b + t*cb.b),
            255
        };
        // Stamp a small circle of radius = half_t for thickness
        for (int ty = -half_t; ty <= half_t; ++ty)
            for (int tx = -half_t; tx <= half_t; ++tx)
                if (tx*tx + ty*ty <= half_t*half_t)
                    setPixel(static_cast<int32_t>(px)+tx, static_cast<int32_t>(py)+ty, c);
    }
}

// ============================================================
// drawEdgeFlat — flat color variant
// ============================================================

void SoftwareRasterizer::drawEdgeFlat(const ClipPolygon& segment,
                                       RGBA color,
                                       const SectionCamera& camera,
                                       int32_t thickness)
{
    if (segment.size() != 2) return;

    Vec2 a = camera.project(segment[0].position);
    Vec2 b = camera.project(segment[1].position);

    double ax = a.x * ss_factor_, ay = a.y * ss_factor_;
    double bx = b.x * ss_factor_, by = b.y * ss_factor_;

    double dx = bx - ax, dy = by - ay;
    double len = std::sqrt(dx*dx + dy*dy);
    if (len < 0.5) return;

    int steps = static_cast<int>(len) + 1;
    int half_t = thickness / 2;

    for (int s = 0; s <= steps; ++s) {
        double t = static_cast<double>(s) / static_cast<double>(steps);
        double px = ax + t*dx;
        double py = ay + t*dy;
        for (int ty = -half_t; ty <= half_t; ++ty)
            for (int tx = -half_t; tx <= half_t; ++tx)
                if (tx*tx + ty*ty <= half_t*half_t)
                    setPixel(static_cast<int32_t>(px)+tx, static_cast<int32_t>(py)+ty, color);
    }
}

// ============================================================
// downsample
// ============================================================

std::vector<uint8_t> SoftwareRasterizer::downsample() const
{
    std::vector<uint8_t> out(static_cast<size_t>(width_) * height_ * 4, 0);
    for (int32_t y = 0; y < height_; ++y) {
        for (int32_t x = 0; x < width_; ++x) {
            uint32_t r=0, g=0, b=0, a=0;
            for (int32_t dy = 0; dy < ss_factor_; ++dy)
                for (int32_t dx = 0; dx < ss_factor_; ++dx) {
                    RGBA p = getPixel(x*ss_factor_+dx, y*ss_factor_+dy);
                    r+=p.r; g+=p.g; b+=p.b; a+=p.a;
                }
            int32_t n = ss_factor_ * ss_factor_;
            size_t idx = (static_cast<size_t>(y)*width_+x)*4;
            out[idx+0] = static_cast<uint8_t>(r/n);
            out[idx+1] = static_cast<uint8_t>(g/n);
            out[idx+2] = static_cast<uint8_t>(b/n);
            out[idx+3] = static_cast<uint8_t>(a/n);
        }
    }
    return out;
}

// ============================================================
// savePng — libpng RGBA write
// ============================================================

std::string SoftwareRasterizer::savePng(const std::string& filepath) const
{
    std::vector<uint8_t> pixels = downsample();

    FILE* fp = fopen(filepath.c_str(), "wb");
    if (!fp) return "Cannot open file: " + filepath;

    png_structp png = png_create_write_struct(PNG_LIBPNG_VER_STRING, nullptr, nullptr, nullptr);
    if (!png) { fclose(fp); return "png_create_write_struct failed"; }

    png_infop info = png_create_info_struct(png);
    if (!info) {
        png_destroy_write_struct(&png, nullptr);
        fclose(fp);
        return "png_create_info_struct failed";
    }

    if (setjmp(png_jmpbuf(png))) {
        png_destroy_write_struct(&png, &info);
        fclose(fp);
        return "libpng error writing: " + filepath;
    }

    png_init_io(png, fp);
    png_set_IHDR(png, info,
                  static_cast<png_uint_32>(width_),
                  static_cast<png_uint_32>(height_),
                  8,                      // bit depth
                  PNG_COLOR_TYPE_RGBA,
                  PNG_INTERLACE_NONE,
                  PNG_COMPRESSION_TYPE_DEFAULT,
                  PNG_FILTER_TYPE_DEFAULT);
    png_write_info(png, info);

    // Write row by row
    for (int32_t y = 0; y < height_; ++y) {
        png_bytep row = const_cast<png_bytep>(pixels.data() + static_cast<size_t>(y)*width_*4);
        png_write_row(png, row);
    }

    png_write_end(png, nullptr);
    png_destroy_write_struct(&png, &info);
    fclose(fp);
    return "";  // success
}

// ============================================================
// Legacy stubs (kept for interface compatibility)
// ============================================================

void SoftwareRasterizer::scanlineFill(const std::vector<Vec2>& /*verts*/,
                                       const std::vector<RGBA>& /*colors*/)
{}

RGBA SoftwareRasterizer::interpolateColor(const std::vector<Vec2>& /*verts*/,
                                           const std::vector<RGBA>& /*colors*/,
                                           double /*px*/, double /*py*/) const
{ return {}; }

} // namespace section_render
} // namespace kood3plot
