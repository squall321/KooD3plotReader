/**
 * @file SectionPlane.cpp
 * @brief Implementation of SectionPlane
 */

#include "kood3plot/section_render/SectionPlane.hpp"
#include <cmath>
#include <stdexcept>

namespace kood3plot {
namespace section_render {

// ============================================================
// Private constructor
// ============================================================

SectionPlane::SectionPlane(const Vec3& normal, const Vec3& point)
    : point_(point)
{
    // Normalise the input normal
    double len = std::sqrt(normal.x*normal.x + normal.y*normal.y + normal.z*normal.z);
    if (len < 1e-12) {
        throw std::invalid_argument("SectionPlane: zero-length normal vector");
    }
    normal_ = { normal.x/len, normal.y/len, normal.z/len };
    d_ = normal_.x*point_.x + normal_.y*point_.y + normal_.z*point_.z;
}

// ============================================================
// Factories
// ============================================================

SectionPlane SectionPlane::fromAxis(char axis, const Vec3& point)
{
    Vec3 normal{0.0, 0.0, 0.0};
    switch (axis | 0x20) {  // to lower-case
        case 'x': normal.x = 1.0; break;
        case 'y': normal.y = 1.0; break;
        case 'z': normal.z = 1.0; break;
        default:
            throw std::invalid_argument("SectionPlane::fromAxis: axis must be x, y, or z");
    }
    return SectionPlane(normal, point);
}

SectionPlane SectionPlane::fromNormal(const Vec3& normal, const Vec3& point)
{
    return SectionPlane(normal, point);
}

// ============================================================
// Geometry queries
// ============================================================

double SectionPlane::signedDistance(const Vec3& p) const
{
    // distance = normal · p - d
    return normal_.x*p.x + normal_.y*p.y + normal_.z*p.z - d_;
}

bool SectionPlane::edgeIntersection(const Vec3& a, const Vec3& b, double& t) const
{
    double da = signedDistance(a);
    double db = signedDistance(b);
    double denom = da - db;

    // Edge is parallel to the plane (or both on-plane)
    if (std::abs(denom) < 1e-12) return false;

    t = da / denom;  // t∈(0,1) when the edge properly crosses
    return (t > 0.0 && t < 1.0);
}

void SectionPlane::getBasis(Vec3& u, Vec3& v) const
{
    // Choose a reference vector that is not parallel to normal_
    Vec3 ref;
    double absNZ = std::abs(normal_.z);
    double absNY = std::abs(normal_.y);

    if (absNZ < 0.9) {
        ref = {0.0, 0.0, 1.0};
    } else if (absNY < 0.9) {
        ref = {0.0, 1.0, 0.0};
    } else {
        ref = {1.0, 0.0, 0.0};
    }

    // u = normalise(ref - (ref·normal)*normal)   [Gram-Schmidt projection]
    double dot = ref.x*normal_.x + ref.y*normal_.y + ref.z*normal_.z;
    Vec3 proj = { ref.x - dot*normal_.x,
                  ref.y - dot*normal_.y,
                  ref.z - dot*normal_.z };
    double len = std::sqrt(proj.x*proj.x + proj.y*proj.y + proj.z*proj.z);
    u = { proj.x/len, proj.y/len, proj.z/len };

    // v = normal × u  (right-handed frame on the plane)
    v = { normal_.y*u.z - normal_.z*u.y,
          normal_.z*u.x - normal_.x*u.z,
          normal_.x*u.y - normal_.y*u.x };
}

} // namespace section_render
} // namespace kood3plot
