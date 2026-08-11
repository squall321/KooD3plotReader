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

    // 변형률 텐서 가용 여부. SinglePassAnalyzer 와 같은 판정식을 쓴다
    // (ISTRN != 0 이고 solid 워드가 6응력+1소성+6변형률 = 13 이상).
    const auto& control = reader_.get_control_data();
    has_strain_tensor_ = (control.ISTRN != 0 && control.NV3D >= 13);
    const std::string note = has_strain_tensor_
        ? std::string()
        : "d3plot 에 변형률 텐서 없음 (ISTRN=" + std::to_string(control.ISTRN) +
          ", NV3D=" + std::to_string(control.NV3D) +
          "). *DATABASE_EXTENT_BINARY 의 STRFLG=1 로 다시 풀어야 "
          "수직/전단·주변형률·ε_vm 이 나온다. 유효소성변형률만 유효.";

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
        results_[i].has_strain_tensor = has_strain_tensor_;
        results_[i].note = note;
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

    const auto& control = reader_.get_control_data();
    const int nv3d = control.NV3D;
    if (nv3d <= 6 || state.solid_data.empty()) {
        return;
    }

    // solid 레이아웃: sxx,syy,szz,sxy,syz,szx, eff_plastic, [exx,eyy,ezz,exy,eyz,ezx], ...
    // 변형률 텐서는 STRFLG 로 켰을 때만 7번째 워드부터 6성분이 실린다.
    const size_t total_solids = state.solid_data.size() / static_cast<size_t>(nv3d);

    // --- 축적기: 실제 텐서 기반 ---
    double normal_max = -std::numeric_limits<double>::max();
    double normal_min = std::numeric_limits<double>::max();
    double normal_sum = 0.0;
    int32_t normal_max_elem_id = 0;

    double shear_max = -std::numeric_limits<double>::max();
    double shear_sum = 0.0;
    int32_t shear_max_elem_id = 0;

    double e1_max = -std::numeric_limits<double>::max();
    double e1_min = std::numeric_limits<double>::max();
    double e1_sum = 0.0;
    int32_t e1_max_elem_id = 0;

    double e3_max = -std::numeric_limits<double>::max();
    double e3_min = std::numeric_limits<double>::max();
    double e3_sum = 0.0;
    int32_t e3_min_elem_id = 0;

    double evm_max = -std::numeric_limits<double>::max();
    double evm_min = std::numeric_limits<double>::max();
    double evm_sum = 0.0;
    int32_t evm_max_elem_id = 0;

    size_t tensor_count = 0;

    // --- 축적기: 유효소성변형률 (텐서 유무와 무관하게 항상) ---
    double eps_max = -std::numeric_limits<double>::max();
    double eps_min = std::numeric_limits<double>::max();
    double eps_sum = 0.0;
    int32_t eps_max_elem_id = 0;
    size_t eps_count = 0;

    for (const auto& face : faces) {
        const size_t elem_idx = static_cast<size_t>(face.element_id);
        if (elem_idx >= total_solids) {
            continue;
        }
        const size_t base = elem_idx * static_cast<size_t>(nv3d);

        // 유효소성변형률 (7번째 워드)
        const double eps = state.solid_data[base + 6];
        if (eps > eps_max) {
            eps_max = eps;
            eps_max_elem_id = face.element_real_id;
        }
        if (eps < eps_min) eps_min = eps;
        eps_sum += eps;
        eps_count++;

        if (!has_strain_tensor_) {
            continue;
        }

        const StressTensor e(
            state.solid_data[base + 7],   // exx
            state.solid_data[base + 8],   // eyy
            state.solid_data[base + 9],   // ezz
            state.solid_data[base + 10],  // exy
            state.solid_data[base + 11],  // eyz
            state.solid_data[base + 12]   // ezx
        );

        // 면 법선 기준 수직/전단 변형률 — 응력과 동일한 텐서 사영식을 쓴다.
        const double en = e.normalStress(face.normal);
        const double es = e.shearStress(face.normal);

        if (en > normal_max) {
            normal_max = en;
            normal_max_elem_id = face.element_real_id;
        }
        if (en < normal_min) normal_min = en;
        normal_sum += en;

        if (es > shear_max) {
            shear_max = es;
            shear_max_elem_id = face.element_real_id;
        }
        shear_sum += es;

        const auto principals = e.principalStresses();
        const double e1 = principals[0];
        const double e3 = principals[2];

        if (e1 > e1_max) {
            e1_max = e1;
            e1_max_elem_id = face.element_real_id;
        }
        if (e1 < e1_min) e1_min = e1;
        e1_sum += e1;

        // ε3 은 압축측이라 **최소값**에 대표 요소를 붙인다.
        if (e3 < e3_min) {
            e3_min = e3;
            e3_min_elem_id = face.element_real_id;
        }
        if (e3 > e3_max) e3_max = e3;
        e3_sum += e3;

        const double em = (e.xx + e.yy + e.zz) / 3.0;
        const double dxx = e.xx - em, dyy = e.yy - em, dzz = e.zz - em;
        const double evm = std::sqrt(2.0 / 3.0 * (dxx * dxx + dyy * dyy + dzz * dzz +
                                                  2.0 * (e.xy * e.xy + e.yz * e.yz + e.zx * e.zx)));
        if (evm > evm_max) {
            evm_max = evm;
            evm_max_elem_id = face.element_real_id;
        }
        if (evm < evm_min) evm_min = evm;
        evm_sum += evm;

        tensor_count++;
    }

    if (eps_count > 0) {
        const double n = static_cast<double>(eps_count);
        point.eff_plastic_strain_max = eps_max;
        point.eff_plastic_strain_min = eps_min;
        point.eff_plastic_strain_avg = eps_sum / n;
        point.eff_plastic_strain_max_element_id = eps_max_elem_id;
    }

    if (tensor_count > 0) {
        const double n = static_cast<double>(tensor_count);
        point.normal_strain_max = normal_max;
        point.normal_strain_min = normal_min;
        point.normal_strain_avg = normal_sum / n;
        point.normal_strain_max_element_id = normal_max_elem_id;

        point.shear_strain_max = shear_max;
        point.shear_strain_avg = shear_sum / n;
        point.shear_strain_max_element_id = shear_max_elem_id;

        point.max_principal_strain_max = e1_max;
        point.max_principal_strain_min = e1_min;
        point.max_principal_strain_avg = e1_sum / n;
        point.max_principal_strain_max_element_id = e1_max_elem_id;

        point.min_principal_strain_max = e3_max;
        point.min_principal_strain_min = e3_min;
        point.min_principal_strain_avg = e3_sum / n;
        point.min_principal_strain_min_element_id = e3_min_elem_id;

        point.vm_strain_max = evm_max;
        point.vm_strain_min = evm_min;
        point.vm_strain_avg = evm_sum / n;
        point.vm_strain_max_element_id = evm_max_elem_id;
    }
}

std::vector<SurfaceStrainStats> SurfaceStrainAnalyzer::getResults() {
    // 헤더(ISTRN/NV3D)상 텐서 슬롯이 있어도 솔버가 0 만 써 놓는 경우가 있다
    // (STRFLG=10 으로 푼 덱에서 실측). 그대로 두면 '변형률 0' 으로 오독되므로
    // 전 스텝·전 성분이 정확히 0 이면 미계측으로 강등하고 사유를 남긴다.
    // 본체(SinglePassAnalyzer)의 all-zero 가드와 같은 판정이다.
    if (has_strain_tensor_) {
        bool all_zero = true;
        for (const auto& s : results_) {
            for (const auto& tp : s.data) {
                if (tp.normal_strain_max != 0.0 || tp.normal_strain_min != 0.0 ||
                    tp.shear_strain_max != 0.0 ||
                    tp.max_principal_strain_max != 0.0 ||
                    tp.min_principal_strain_min != 0.0 ||
                    tp.vm_strain_max != 0.0) {
                    all_zero = false;
                    break;
                }
            }
            if (!all_zero) break;
        }
        if (all_zero) {
            for (auto& s : results_) {
                s.has_strain_tensor = false;
                s.note = "변형률 텐서가 전 스텝 0 — 솔버가 기록하지 않은 것으로 판단 "
                         "(*DATABASE_EXTENT_BINARY STRFLG=1 필요). 유효소성변형률만 유효.";
            }
        }
    }
    return results_;
}

void SurfaceStrainAnalyzer::reset() {
    results_.clear();
    extracted_surfaces_.clear();
    initialized_ = false;
}

} // namespace analysis
} // namespace kood3plot
