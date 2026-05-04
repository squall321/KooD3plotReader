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
 * 3D mode: Z-buffered triangle rasterizer for half-model section views.
 *
 * PNG output: libpng RGBA write (linked via PNG::PNG in CMakeLists).
 */

#include "kood3plot/section_render/SoftwareRasterizer.hpp"
#include <png.h>
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <limits>
#include <stdexcept>

namespace kood3plot {
namespace section_render {

// ============================================================
// Constructor / clear / pixel ops
// ============================================================

SoftwareRasterizer::SoftwareRasterizer(int32_t width, int32_t height, int32_t ss_factor)
    : width_(width), height_(height), ss_factor_(ss_factor)
    , ss_width_(width * ss_factor), ss_height_(height * ss_factor)
{
    buffer_.assign(static_cast<size_t>(ss_width_) * ss_height_ * 4, 0);
    zbuffer_.assign(static_cast<size_t>(ss_width_) * ss_height_,
                    std::numeric_limits<float>::max());
}

void SoftwareRasterizer::clear(RGBA color)
{
    for (int32_t y = 0; y < ss_height_; ++y)
        for (int32_t x = 0; x < ss_width_; ++x)
            setPixel(x, y, color);

    if (depth_test_) {
        std::fill(zbuffer_.begin(), zbuffer_.end(), std::numeric_limits<float>::max());
    }
}

void SoftwareRasterizer::enableDepthTest(bool enable)
{
    depth_test_ = enable;
    if (enable && zbuffer_.size() != static_cast<size_t>(ss_width_) * ss_height_) {
        zbuffer_.assign(static_cast<size_t>(ss_width_) * ss_height_,
                        std::numeric_limits<float>::max());
    }
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

bool SoftwareRasterizer::testAndSetDepth(int32_t x, int32_t y, float depth)
{
    if (x < 0 || x >= ss_width_ || y < 0 || y >= ss_height_) return false;
    size_t idx = static_cast<size_t>(y) * ss_width_ + x;
    if (depth < zbuffer_[idx]) {
        zbuffer_[idx] = depth;
        return true;
    }
    return false;
}

// ============================================================
// Triangle rasterizer helpers (2D — no depth test)
// ============================================================

namespace {

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

void rasterizeTriangleContourAlpha(
    double ax, double ay, RGBA ca,
    double bx, double by, RGBA cb,
    double cx, double cy, RGBA cc,
    float alpha,
    std::vector<uint8_t>& buf, int32_t W, int32_t H)
{
    if (alpha <= 0.0f) return;
    if (alpha >= 1.0f) {
        rasterizeTriangle(ax,ay,ca, bx,by,cb, cx,cy,cc, buf,W,H);
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

            RGBA src{
                static_cast<uint8_t>(l0*ca.r + l1*cb.r + l2*cc.r),
                static_cast<uint8_t>(l0*ca.g + l1*cb.g + l2*cc.g),
                static_cast<uint8_t>(l0*ca.b + l1*cb.b + l2*cc.b),
                255
            };
            size_t idx = (static_cast<size_t>(y)*W + x)*4;
            float inv = 1.0f - alpha;
            buf[idx+0] = static_cast<uint8_t>(alpha*src.r + inv*buf[idx+0]);
            buf[idx+1] = static_cast<uint8_t>(alpha*src.g + inv*buf[idx+1]);
            buf[idx+2] = static_cast<uint8_t>(alpha*src.b + inv*buf[idx+2]);
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

    int n = static_cast<int>(polygon.size());
    std::vector<double> sx(n), sy(n);
    std::vector<RGBA>   sc(n);
    for (int i = 0; i < n; ++i) {
        Vec2 p = camera.project(polygon[i].position);
        sx[i] = p.x * ss_factor_;
        sy[i] = p.y * ss_factor_;
        sc[i] = cmap.map(polygon[i].value);
    }

    for (int i = 1; i < n-1; ++i) {
        rasterizeTriangle(
            sx[0], sy[0], sc[0],
            sx[i], sy[i], sc[i],
            sx[i+1], sy[i+1], sc[i+1],
            buffer_, ss_width_, ss_height_);
    }
}

// ============================================================
// drawPolygonContourAlpha — Gouraud shading + alpha blending
// ============================================================

void SoftwareRasterizer::drawPolygonContourAlpha(const ClipPolygon& polygon,
                                                   const ColorMap& cmap,
                                                   const SectionCamera& camera,
                                                   float alpha)
{
    if (polygon.size() < 3) return;
    if (alpha >= 1.0f) { drawPolygonContour(polygon, cmap, camera); return; }
    if (alpha <= 0.0f) return;

    int n = static_cast<int>(polygon.size());
    std::vector<double> sx(n), sy(n);
    std::vector<RGBA>   sc(n);
    for (int i = 0; i < n; ++i) {
        Vec2 p = camera.project(polygon[i].position);
        sx[i] = p.x * ss_factor_;
        sy[i] = p.y * ss_factor_;
        sc[i] = cmap.map(polygon[i].value);
    }

    for (int i = 1; i < n-1; ++i) {
        rasterizeTriangleContourAlpha(
            sx[0], sy[0], sc[0],
            sx[i], sy[i], sc[i],
            sx[i+1], sy[i+1], sc[i+1],
            alpha,
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
        RGBA c{
            static_cast<uint8_t>((1-t)*ca.r + t*cb.r),
            static_cast<uint8_t>((1-t)*ca.g + t*cb.g),
            static_cast<uint8_t>((1-t)*ca.b + t*cb.b),
            255
        };
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
// 3D Z-buffered triangle — flat shading
// ============================================================

void SoftwareRasterizer::drawTriangle3D(
    double p0x, double p0y, double z0,
    double p1x, double p1y, double z1,
    double p2x, double p2y, double z2,
    RGBA color)
{
    int xmin = std::max(0,   static_cast<int>(std::min({p0x,p1x,p2x})));
    int xmax = std::min(ss_width_-1,  static_cast<int>(std::max({p0x,p1x,p2x})) + 1);
    int ymin = std::max(0,   static_cast<int>(std::min({p0y,p1y,p2y})));
    int ymax = std::min(ss_height_-1, static_cast<int>(std::max({p0y,p1y,p2y})) + 1);

    for (int y = ymin; y <= ymax; ++y) {
        for (int x = xmin; x <= xmax; ++x) {
            double l0, l1, l2;
            if (!baryWeights(x+0.5, y+0.5, p0x,p0y, p1x,p1y, p2x,p2y, l0,l1,l2)) continue;
            if (l0 < -1e-4 || l1 < -1e-4 || l2 < -1e-4) continue;

            float depth = static_cast<float>(l0*z0 + l1*z1 + l2*z2);
            if (testAndSetDepth(x, y, depth)) {
                setPixel(x, y, color);
            }
        }
    }
}

// ============================================================
// 3D Z-buffered triangle — Gouraud (per-vertex color)
// ============================================================

void SoftwareRasterizer::drawTriangle3DContour(
    double p0x, double p0y, double z0, RGBA c0,
    double p1x, double p1y, double z1, RGBA c1,
    double p2x, double p2y, double z2, RGBA c2)
{
    int xmin = std::max(0,   static_cast<int>(std::min({p0x,p1x,p2x})));
    int xmax = std::min(ss_width_-1,  static_cast<int>(std::max({p0x,p1x,p2x})) + 1);
    int ymin = std::max(0,   static_cast<int>(std::min({p0y,p1y,p2y})));
    int ymax = std::min(ss_height_-1, static_cast<int>(std::max({p0y,p1y,p2y})) + 1);

    for (int y = ymin; y <= ymax; ++y) {
        for (int x = xmin; x <= xmax; ++x) {
            double l0, l1, l2;
            if (!baryWeights(x+0.5, y+0.5, p0x,p0y, p1x,p1y, p2x,p2y, l0,l1,l2)) continue;
            if (l0 < -1e-4 || l1 < -1e-4 || l2 < -1e-4) continue;

            float depth = static_cast<float>(l0*z0 + l1*z1 + l2*z2);
            if (testAndSetDepth(x, y, depth)) {
                RGBA color{
                    static_cast<uint8_t>(std::min(255.0, l0*c0.r + l1*c1.r + l2*c2.r)),
                    static_cast<uint8_t>(std::min(255.0, l0*c0.g + l1*c1.g + l2*c2.g)),
                    static_cast<uint8_t>(std::min(255.0, l0*c0.b + l1*c1.b + l2*c2.b)),
                    255
                };
                setPixel(x, y, color);
            }
        }
    }
}

// ============================================================
// 3D Z-buffered alpha-blended triangle (depth read-only)
// ============================================================

void SoftwareRasterizer::drawTriangle3DAlpha(
    double p0x, double p0y, double z0,
    double p1x, double p1y, double z1,
    double p2x, double p2y, double z2,
    RGBA color, float alpha)
{
    if (alpha <= 0.0f) return;
    if (alpha >= 1.0f) {
        drawTriangle3D(p0x, p0y, z0, p1x, p1y, z1, p2x, p2y, z2, color);
        return;
    }

    int xmin = std::max(0,   static_cast<int>(std::min({p0x,p1x,p2x})));
    int xmax = std::min(ss_width_-1,  static_cast<int>(std::max({p0x,p1x,p2x})) + 1);
    int ymin = std::max(0,   static_cast<int>(std::min({p0y,p1y,p2y})));
    int ymax = std::min(ss_height_-1, static_cast<int>(std::max({p0y,p1y,p2y})) + 1);

    float inv = 1.0f - alpha;
    for (int y = ymin; y <= ymax; ++y) {
        for (int x = xmin; x <= xmax; ++x) {
            double l0, l1, l2;
            if (!baryWeights(x+0.5, y+0.5, p0x,p0y, p1x,p1y, p2x,p2y, l0,l1,l2)) continue;
            if (l0 < -1e-4 || l1 < -1e-4 || l2 < -1e-4) continue;

            // Depth test AND write. Writing depth means subsequent translucent
            // triangles BEHIND this one (same/larger depth) get culled — so
            // each BG part shows only its frontmost surface, blended once.
            // Without depth write, all front-facing triangles of a thick BG
            // part stack alpha layers → over-saturated colors and ghost
            // overlaps from interior side faces.
            float depth = static_cast<float>(l0*z0 + l1*z1 + l2*z2);
            size_t z_idx = static_cast<size_t>(y)*ss_width_ + x;
            if (depth >= zbuffer_[z_idx]) continue;
            zbuffer_[z_idx] = depth;

            size_t idx = (static_cast<size_t>(y) * ss_width_ + x) * 4;
            buffer_[idx+0] = static_cast<uint8_t>(alpha * color.r + inv * buffer_[idx+0]);
            buffer_[idx+1] = static_cast<uint8_t>(alpha * color.g + inv * buffer_[idx+1]);
            buffer_[idx+2] = static_cast<uint8_t>(alpha * color.b + inv * buffer_[idx+2]);
            buffer_[idx+3] = 255;
        }
    }
}

// ============================================================
// Per-part silhouette mask (build coverage)
// ============================================================

void SoftwareRasterizer::rasterizeToPartMask(
    double p0x, double p0y, double z0,
    double p1x, double p1y, double z1,
    double p2x, double p2y, double z2,
    float tri_shade,
    std::vector<uint8_t>& mask,
    std::vector<float>& part_depth,
    std::vector<float>& shade)
{
    int xmin = std::max(0,   static_cast<int>(std::min({p0x,p1x,p2x})));
    int xmax = std::min(ss_width_-1,  static_cast<int>(std::max({p0x,p1x,p2x})) + 1);
    int ymin = std::max(0,   static_cast<int>(std::min({p0y,p1y,p2y})));
    int ymax = std::min(ss_height_-1, static_cast<int>(std::max({p0y,p1y,p2y})) + 1);

    for (int y = ymin; y <= ymax; ++y) {
        for (int x = xmin; x <= xmax; ++x) {
            double l0, l1, l2;
            if (!baryWeights(x+0.5, y+0.5, p0x,p0y, p1x,p1y, p2x,p2y, l0,l1,l2)) continue;
            if (l0 < -1e-4 || l1 < -1e-4 || l2 < -1e-4) continue;

            float depth = static_cast<float>(l0*z0 + l1*z1 + l2*z2);
            size_t idx = static_cast<size_t>(y) * ss_width_ + x;
            // Cull only if STRICTLY behind already-drawn opaque target
            // (small epsilon for contact-surface precision). Equal-depth
            // pixels are kept so the silhouette covers the part's full
            // screen-space outline.
            if (depth > zbuffer_[idx] + 1e-4f) continue;
            mask[idx] = 1;
            // Track the FRONTMOST triangle per pixel — both depth and
            // shade. This way a side face contributing near the
            // silhouette edge stays darker than the top face, giving 3D
            // depth perception (front-vs-back faces no longer share the
            // same brightness through the translucent silhouette).
            if (depth < part_depth[idx]) {
                part_depth[idx] = depth;
                shade[idx]      = tri_shade;
            }
        }
    }
}

// ============================================================
// Per-part silhouette composite (single uniform alpha-blend)
// ============================================================

void SoftwareRasterizer::compositePartSilhouette(
    const std::vector<uint8_t>& mask,
    const std::vector<float>& part_depth,
    const std::vector<float>& shade,
    RGBA color, float alpha)
{
    if (alpha <= 0.0f) return;
    const size_t total = static_cast<size_t>(ss_width_) * ss_height_;
    const float inv = 1.0f - alpha;
    for (size_t i = 0; i < total; ++i) {
        if (!mask[i]) continue;
        // Apply per-pixel shading so silhouette has 3D depth perception:
        // top faces (high shade) read brighter, side faces darker.
        float s = std::min(1.0f, std::max(0.0f, shade[i]));
        uint8_t cr = static_cast<uint8_t>(color.r * s);
        uint8_t cg = static_cast<uint8_t>(color.g * s);
        uint8_t cb = static_cast<uint8_t>(color.b * s);

        size_t b = i * 4;
        if (alpha >= 1.0f) {
            buffer_[b+0] = cr;
            buffer_[b+1] = cg;
            buffer_[b+2] = cb;
        } else {
            buffer_[b+0] = static_cast<uint8_t>(alpha * cr + inv * buffer_[b+0]);
            buffer_[b+1] = static_cast<uint8_t>(alpha * cg + inv * buffer_[b+1]);
            buffer_[b+2] = static_cast<uint8_t>(alpha * cb + inv * buffer_[b+2]);
        }
        buffer_[b+3] = 255;
        zbuffer_[i] = part_depth[i];
    }
}

// ============================================================
// 3D Z-buffered line (mesh edge wireframe)
// ============================================================

void SoftwareRasterizer::drawLine3D(
    double ax, double ay, double az,
    double bx, double by, double bz,
    RGBA color, int32_t thickness)
{
    double dx = bx - ax, dy = by - ay;
    double len = std::sqrt(dx*dx + dy*dy);
    if (len < 0.5) return;

    int steps = static_cast<int>(len) + 1;
    int half_t = thickness / 2;

    for (int s = 0; s <= steps; ++s) {
        double t = static_cast<double>(s) / static_cast<double>(steps);
        double px = ax + t*dx;
        double py = ay + t*dy;
        float depth = static_cast<float>(az + t*(bz - az));

        // Bias depth slightly closer to camera so edges draw on top of faces
        depth -= 0.001f;

        for (int ty = -half_t; ty <= half_t; ++ty)
            for (int tx = -half_t; tx <= half_t; ++tx)
                if (tx*tx + ty*ty <= half_t*half_t) {
                    int32_t ix = static_cast<int32_t>(px) + tx;
                    int32_t iy = static_cast<int32_t>(py) + ty;
                    if (testAndSetDepth(ix, iy, depth)) {
                        setPixel(ix, iy, color);
                    }
                }
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

    for (int32_t y = 0; y < height_; ++y) {
        png_bytep row = const_cast<png_bytep>(pixels.data() + static_cast<size_t>(y)*width_*4);
        png_write_row(png, row);
    }

    png_write_end(png, nullptr);
    png_destroy_write_struct(&png, &info);
    fclose(fp);
    return "";
}

// ============================================================
// Screen-space edge detection (Z-buffer discontinuity)
// ============================================================

void SoftwareRasterizer::applyDepthEdgeDetection(double depth_threshold,
                                                   double darken_factor)
{
    if (!depth_test_) return;

    const float bg_depth = std::numeric_limits<float>::max();

    // Pass 1: compute per-pixel edge strength
    std::vector<float> edge_strength(static_cast<size_t>(ss_width_) * ss_height_, 0.0f);

    for (int32_t y = 1; y < ss_height_ - 1; ++y) {
        for (int32_t x = 1; x < ss_width_ - 1; ++x) {
            size_t idx = static_cast<size_t>(y) * ss_width_ + x;
            float d = zbuffer_[idx];
            if (d >= bg_depth * 0.5f) continue;  // background pixel

            // Sample 4 neighbors
            float dl = zbuffer_[idx - 1];
            float dr = zbuffer_[idx + 1];
            float du = zbuffer_[idx - ss_width_];
            float dd = zbuffer_[idx + ss_width_];

            // Maximum absolute depth difference with neighbors
            float max_diff = 0.0f;
            auto check = [&](float dn) {
                if (dn >= bg_depth * 0.5f) {
                    // Neighbor is background → strong edge (silhouette)
                    max_diff = 1.0f;
                } else {
                    float diff = std::abs(d - dn);
                    if (diff > max_diff) max_diff = diff;
                }
            };
            check(dl); check(dr); check(du); check(dd);

            // Normalize by depth magnitude to get relative difference
            float rel = (max_diff >= 1.0f) ? 1.0f
                        : (std::abs(d) > 1e-6f ? max_diff / std::abs(d) : 0.0f);

            if (rel > static_cast<float>(depth_threshold)) {
                // Clamp edge strength to [0, 1]
                float strength = std::min(1.0f,
                    (rel - static_cast<float>(depth_threshold))
                    / static_cast<float>(depth_threshold) * 2.0f);
                edge_strength[idx] = strength;
            }
        }
    }

    // Pass 2: darken edge pixels
    float df = static_cast<float>(darken_factor);
    for (int32_t y = 0; y < ss_height_; ++y) {
        for (int32_t x = 0; x < ss_width_; ++x) {
            size_t idx = static_cast<size_t>(y) * ss_width_ + x;
            float s = edge_strength[idx];
            if (s <= 0.0f) continue;

            // Blend: pixel *= darken_factor^strength
            float factor = 1.0f - s * (1.0f - df);
            size_t pidx = idx * 4;
            buffer_[pidx + 0] = static_cast<uint8_t>(buffer_[pidx + 0] * factor);
            buffer_[pidx + 1] = static_cast<uint8_t>(buffer_[pidx + 1] * factor);
            buffer_[pidx + 2] = static_cast<uint8_t>(buffer_[pidx + 2] * factor);
        }
    }
}

// ============================================================
// Legacy stubs
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
