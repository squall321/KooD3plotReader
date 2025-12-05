/**
 * @file SurfaceStrainAnalyzer.cpp
 * @brief Direction-based surface strain analysis implementation
 */

#include "kood3plot/analysis/SurfaceStrainAnalyzer.hpp"
#include <cmath>
#include <algorithm>
#include <limits>

namespace kood3plot {
namespace analysis {

SurfaceStrainAnalyzer::SurfaceStrainAnalyzer(D3plotReader& reader)
    : reader_(reader)
{
}

void SurfaceStrainAnalyzer::addSurface(const std::string& description,
                                        const Vec3& direction,
                                        double angle_degrees,
                                        const std::vector<int32_t>& part_ids) {
    SurfaceSpec spec;
    spec.description = description;
    spec.direction = direction.normalized();
    spec.angle_degrees = angle_degrees;
    spec.part_ids = part_ids;
    surface_specs_.push_back(spec);
}

bool SurfaceStrainAnalyzer::initialize() {
    initialized_ = false;

    if (surface_specs_.empty()) {
        last_error_ = "No surface specifications added";
        return false;
    }

    // Extract surfaces
    extractSurfaces();

    // Initialize results storage
    results_.clear();
    results_.resize(surface_specs_.size());
    for (size_t i = 0; i < surface_specs_.size(); ++i) {
        results_[i].description = surface_specs_[i].description;
        results_[i].reference_direction = surface_specs_[i].direction;
        results_[i].angle_threshold_degrees = surface_specs_[i].angle_degrees;
        results_[i].part_ids = surface_specs_[i].part_ids;
        results_[i].num_faces = static_cast<int32_t>(extracted_surfaces_[i].size());
    }

    initialized_ = true;
    return true;
}

void SurfaceStrainAnalyzer::extractSurfaces() {
    extracted_surfaces_.clear();
    extracted_surfaces_.resize(surface_specs_.size());

    // Use SurfaceExtractor to extract exterior surfaces
    SurfaceExtractor extractor(reader_);
    if (!extractor.initialize()) {
        last_error_ = "Failed to initialize SurfaceExtractor: " + extractor.getLastError();
        return;
    }

    for (size_t i = 0; i < surface_specs_.size(); ++i) {
        const auto& spec = surface_specs_[i];

        // Extract exterior faces (optionally for specific parts)
        SurfaceExtractionResult result;
        if (spec.part_ids.empty()) {
            result = extractor.extractExteriorSurfaces();
        } else {
            result = extractor.extractExteriorSurfaces(spec.part_ids);
        }

        // Filter by direction
        auto filtered = SurfaceExtractor::filterByDirection(result.faces, spec.direction, spec.angle_degrees);

        extracted_surfaces_[i] = std::move(filtered);
    }
}

void SurfaceStrainAnalyzer::processState(const data::StateData& state) {
    if (!initialized_) {
        return;
    }

    // Process each surface
    for (size_t i = 0; i < surface_specs_.size(); ++i) {
        SurfaceStrainTimePoint point;
        point.time = state.time;

        processStrainForSurface(i, state, point);

        results_[i].data.push_back(point);
    }
}

void SurfaceStrainAnalyzer::processStrainForSurface(size_t surface_idx,
                                                      const data::StateData& state,
                                                      SurfaceStrainTimePoint& point) {
    const auto& faces = extracted_surfaces_[surface_idx];
    if (faces.empty()) {
        return;
    }

    // Get control data for layout information
    const auto& control = reader_.get_control_data();
    int nv3d = control.NV3D;  // Values per solid element

    // Check if solid data is available
    if (state.solid_data.empty()) {
        return;
    }

    // In d3plot, effective plastic strain is typically stored as the 7th value
    // Layout: sig_xx, sig_yy, sig_zz, sig_xy, sig_yz, sig_zx, eff_plastic_strain, ...

    double normal_max = -std::numeric_limits<double>::max();
    double normal_min = std::numeric_limits<double>::max();
    double normal_sum = 0.0;
    int32_t normal_max_elem_id = 0;

    double shear_max = 0.0;
    double shear_sum = 0.0;
    int32_t shear_max_elem_id = 0;

    size_t count = 0;

    for (const auto& face : faces) {
        // Get strain data for this element
        // Use element_id (internal 0-based index)
        size_t elem_idx = static_cast<size_t>(face.element_id);

        // Validate index
        size_t total_solids = state.solid_data.size() / nv3d;
        if (elem_idx >= total_solids) {
            continue;
        }

        // Calculate base offset for this element
        size_t base_offset = elem_idx * nv3d;

        // Check if we have enough data and if strain is available
        // Effective plastic strain is at index 6 (7th value) if available
        if (nv3d > 6 && base_offset + 6 < state.solid_data.size()) {
            // Get effective plastic strain
            double eff_strain = state.solid_data[base_offset + 6];

            // Use effective plastic strain as proxy for surface strain analysis
            double strain_value = eff_strain;

            // Normal strain contribution (use absolute value for max tracking)
            if (strain_value > normal_max) {
                normal_max = strain_value;
                normal_max_elem_id = face.element_real_id;
            }
            if (strain_value < normal_min) {
                normal_min = strain_value;
            }
            normal_sum += strain_value;

            // Shear strain (approximate as fraction of effective strain)
            double shear_value = strain_value * 0.577;  // ~1/sqrt(3) approximation
            if (shear_value > shear_max) {
                shear_max = shear_value;
                shear_max_elem_id = face.element_real_id;
            }
            shear_sum += shear_value;

            count++;
        }
    }

    if (count > 0) {
        point.normal_strain_max = normal_max;
        point.normal_strain_min = normal_min;
        point.normal_strain_avg = normal_sum / static_cast<double>(count);
        point.normal_strain_max_element_id = normal_max_elem_id;

        point.shear_strain_max = shear_max;
        point.shear_strain_avg = shear_sum / static_cast<double>(count);
        point.shear_strain_max_element_id = shear_max_elem_id;
    }
}

std::vector<SurfaceStrainStats> SurfaceStrainAnalyzer::getResults() {
    return results_;
}

void SurfaceStrainAnalyzer::reset() {
    results_.clear();
    extracted_surfaces_.clear();
    initialized_ = false;
}

} // namespace analysis
} // namespace kood3plot
