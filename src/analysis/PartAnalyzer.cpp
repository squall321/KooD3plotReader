#include "kood3plot/analysis/PartAnalyzer.hpp"
#include <fstream>
#include <iomanip>
#include <algorithm>
#include <cmath>
#include <numeric>
#include <sstream>
#include <limits>

namespace kood3plot {
namespace analysis {

PartAnalyzer::PartAnalyzer(D3plotReader& reader)
    : reader_(reader)
    , initialized_(false)
{
}

PartAnalyzer::~PartAnalyzer() = default;

bool PartAnalyzer::initialize() {
    if (initialized_) {
        return true;
    }

    if (!reader_.is_open()) {
        last_error_ = "D3plotReader is not open";
        return false;
    }

    // Read mesh and control data
    mesh_ = reader_.read_mesh();
    control_data_ = reader_.get_control_data();

    // Build part map
    build_part_map();

    if (parts_.empty()) {
        last_error_ = "No parts found in mesh";
        return false;
    }

    initialized_ = true;
    return true;
}

void PartAnalyzer::build_part_map() {
    parts_.clear();
    part_id_to_index_.clear();

    // Build from solid elements
    std::unordered_map<int32_t, std::vector<size_t>> part_elements;

    size_t num_solids = mesh_.solids.size();
    for (size_t i = 0; i < num_solids; ++i) {
        int32_t part_id;
        if (!mesh_.solid_parts.empty() && i < mesh_.solid_parts.size()) {
            part_id = mesh_.solid_parts[i];
        } else if (!mesh_.solid_materials.empty() && i < mesh_.solid_materials.size()) {
            part_id = mesh_.solid_materials[i];
        } else {
            continue;
        }

        part_elements[part_id].push_back(i);
    }

    // Create PartInfo for each unique part
    for (const auto& [part_id, elem_indices] : part_elements) {
        PartInfo info;
        info.part_id = part_id;
        info.name = "Part_" + std::to_string(part_id);
        info.element_type = ElementType::SOLID;
        info.num_elements = elem_indices.size();
        info.element_indices = elem_indices;

        part_id_to_index_[part_id] = parts_.size();
        parts_.push_back(std::move(info));
    }

    // Sort parts by ID for consistent ordering
    std::sort(parts_.begin(), parts_.end(),
              [](const PartInfo& a, const PartInfo& b) {
                  return a.part_id < b.part_id;
              });

    // Rebuild index map after sorting
    for (size_t i = 0; i < parts_.size(); ++i) {
        part_id_to_index_[parts_[i].part_id] = i;
    }
}

const PartInfo* PartAnalyzer::get_part_by_id(int32_t part_id) const {
    auto it = part_id_to_index_.find(part_id);
    if (it == part_id_to_index_.end()) {
        return nullptr;
    }
    return &parts_[it->second];
}

int PartAnalyzer::get_nv3d() const {
    // Calculate NV3D from control data
    // ls-dyna_database.txt: NV3D = 13 for stress tensor + plastic strain
    // This is the number of values per solid element per state
    int istrn = control_data_.ISTRN;
    int nv3d = 7;  // Base: 6 stress components + effective plastic strain

    // If ISTRN != 0, add 6 strain components
    if (istrn != 0) {
        nv3d += 6;
    }

    return nv3d;
}

double PartAnalyzer::extract_stress(const std::vector<double>& solid_data,
                                     size_t elem_index, StressComponent component) {
    int nv3d = get_nv3d();
    size_t base = elem_index * nv3d;

    if (base + 6 > solid_data.size()) {
        return 0.0;  // Out of bounds
    }

    // Solid element data layout (ls-dyna_database.txt):
    // Word 0: Sigma-xx
    // Word 1: Sigma-yy
    // Word 2: Sigma-zz
    // Word 3: Sigma-xy
    // Word 4: Sigma-yz
    // Word 5: Sigma-zx
    // Word 6: Effective plastic strain
    // Word 7-12: Strain components (only if ISTRN != 0)

    double sxx = solid_data[base + 0];
    double syy = solid_data[base + 1];
    double szz = solid_data[base + 2];
    double sxy = solid_data[base + 3];
    double syz = solid_data[base + 4];
    double szx = solid_data[base + 5];

    switch (component) {
        case StressComponent::XX:
            return sxx;
        case StressComponent::YY:
            return syy;
        case StressComponent::ZZ:
            return szz;
        case StressComponent::XY:
            return sxy;
        case StressComponent::YZ:
            return syz;
        case StressComponent::ZX:
            return szx;
        case StressComponent::VON_MISES:
            return calculate_von_mises(sxx, syy, szz, sxy, syz, szx);
        case StressComponent::PRESSURE:
            return calculate_pressure(sxx, syy, szz);
        case StressComponent::EFF_PLASTIC:
            return solid_data[base + 6];

        // Strain components (only available when ISTRN != 0)
        case StressComponent::STRAIN_XX:
            return (control_data_.ISTRN != 0 && base + 7 < solid_data.size()) ? solid_data[base + 7] : 0.0;
        case StressComponent::STRAIN_YY:
            return (control_data_.ISTRN != 0 && base + 8 < solid_data.size()) ? solid_data[base + 8] : 0.0;
        case StressComponent::STRAIN_ZZ:
            return (control_data_.ISTRN != 0 && base + 9 < solid_data.size()) ? solid_data[base + 9] : 0.0;
        case StressComponent::STRAIN_XY:
            return (control_data_.ISTRN != 0 && base + 10 < solid_data.size()) ? solid_data[base + 10] : 0.0;
        case StressComponent::STRAIN_YZ:
            return (control_data_.ISTRN != 0 && base + 11 < solid_data.size()) ? solid_data[base + 11] : 0.0;
        case StressComponent::STRAIN_ZX:
            return (control_data_.ISTRN != 0 && base + 12 < solid_data.size()) ? solid_data[base + 12] : 0.0;

        default:
            return 0.0;
    }
}

double PartAnalyzer::calculate_von_mises(double sxx, double syy, double szz,
                                          double sxy, double syz, double szx) {
    // Von Mises stress formula:
    // σ_vm = sqrt(0.5 * [(σxx-σyy)² + (σyy-σzz)² + (σzz-σxx)² + 6*(τxy² + τyz² + τzx²)])
    double d1 = sxx - syy;
    double d2 = syy - szz;
    double d3 = szz - sxx;

    double vm_sq = 0.5 * (d1*d1 + d2*d2 + d3*d3) + 3.0 * (sxy*sxy + syz*syz + szx*szx);

    return std::sqrt(vm_sq);
}

double PartAnalyzer::calculate_pressure(double sxx, double syy, double szz) {
    // Hydrostatic pressure = -1/3 * (σxx + σyy + σzz)
    return -(sxx + syy + szz) / 3.0;
}

PartStats PartAnalyzer::analyze_state(int32_t part_id, const data::StateData& state,
                                       StressComponent component) {
    PartStats stats;
    stats.part_id = part_id;
    stats.time = state.time;

    const PartInfo* part = get_part_by_id(part_id);
    if (!part) {
        last_error_ = "Part ID " + std::to_string(part_id) + " not found";
        return stats;
    }

    if (state.solid_data.empty()) {
        last_error_ = "No solid data in state";
        return stats;
    }

    stats.num_elements = part->num_elements;

    double sum = 0.0;
    double sum_sq = 0.0;
    double max_val = -std::numeric_limits<double>::max();
    double min_val = std::numeric_limits<double>::max();
    int32_t max_elem = 0;
    int32_t min_elem = 0;

    for (size_t elem_idx : part->element_indices) {
        double val = extract_stress(state.solid_data, elem_idx, component);

        sum += val;
        sum_sq += val * val;

        if (val > max_val) {
            max_val = val;
            max_elem = mesh_.real_solid_ids.empty() ?
                       static_cast<int32_t>(elem_idx + 1) :
                       mesh_.real_solid_ids[elem_idx];
        }
        if (val < min_val) {
            min_val = val;
            min_elem = mesh_.real_solid_ids.empty() ?
                       static_cast<int32_t>(elem_idx + 1) :
                       mesh_.real_solid_ids[elem_idx];
        }
    }

    if (stats.num_elements > 0) {
        stats.stress_max = max_val;
        stats.stress_min = min_val;
        stats.stress_avg = sum / stats.num_elements;
        stats.stress_rms = std::sqrt(sum_sq / stats.num_elements);
        stats.max_element_id = max_elem;
        stats.min_element_id = min_elem;
    }

    return stats;
}

PartTimeHistory PartAnalyzer::analyze_part(int32_t part_id, StressComponent component) {
    PartTimeHistory history;
    history.part_id = part_id;

    if (!initialized_ && !initialize()) {
        return history;
    }

    const PartInfo* part = get_part_by_id(part_id);
    if (!part) {
        last_error_ = "Part ID " + std::to_string(part_id) + " not found";
        return history;
    }

    history.part_name = part->name;

    // Read all states (parallel for performance)
    auto states = reader_.read_all_states_parallel();

    history.times.reserve(states.size());
    history.max_values.reserve(states.size());
    history.min_values.reserve(states.size());
    history.avg_values.reserve(states.size());
    history.max_elem_ids.reserve(states.size());

    for (const auto& state : states) {
        auto stats = analyze_state(part_id, state, component);

        history.times.push_back(state.time);
        history.max_values.push_back(stats.stress_max);
        history.min_values.push_back(stats.stress_min);
        history.avg_values.push_back(stats.stress_avg);
        history.max_elem_ids.push_back(stats.max_element_id);
    }

    return history;
}

std::vector<PartTimeHistory> PartAnalyzer::analyze_all_parts(StressComponent component) {
    return analyze_all_parts_with_progress(component, nullptr);
}

std::vector<PartTimeHistory> PartAnalyzer::analyze_all_parts_with_progress(
    StressComponent component,
    std::function<void(size_t, size_t, const std::string&)> callback)
{
    std::vector<PartTimeHistory> histories;

    if (!initialized_ && !initialize()) {
        return histories;
    }

    // Read all states once (parallel for performance)
    if (callback) callback(0, parts_.size(), "Loading states...");
    auto states = reader_.read_all_states_parallel();

    histories.resize(parts_.size());
    size_t num_states = states.size();

    // Initialize all histories
    for (size_t p = 0; p < parts_.size(); ++p) {
        histories[p].part_id = parts_[p].part_id;
        histories[p].part_name = parts_[p].name;
        histories[p].times.reserve(num_states);
        histories[p].max_values.reserve(num_states);
        histories[p].min_values.reserve(num_states);
        histories[p].avg_values.reserve(num_states);
        histories[p].max_elem_ids.reserve(num_states);
    }

    // Process each state
    for (size_t s = 0; s < num_states; ++s) {
        const auto& state = states[s];

        if (callback && s % 10 == 0) {
            callback(s, num_states, "Processing state " + std::to_string(s));
        }

        // Analyze each part for this state
        for (size_t p = 0; p < parts_.size(); ++p) {
            auto stats = analyze_state(parts_[p].part_id, state, component);

            histories[p].times.push_back(state.time);
            histories[p].max_values.push_back(stats.stress_max);
            histories[p].min_values.push_back(stats.stress_min);
            histories[p].avg_values.push_back(stats.stress_avg);
            histories[p].max_elem_ids.push_back(stats.max_element_id);
        }
    }

    if (callback) callback(num_states, num_states, "Analysis complete");

    return histories;
}

std::vector<PartTimeHistory> PartAnalyzer::analyze_with_states(
    const std::vector<data::StateData>& states,
    StressComponent component)
{
    return analyze_with_states_progress(states, component, nullptr);
}

std::vector<PartTimeHistory> PartAnalyzer::analyze_with_states_progress(
    const std::vector<data::StateData>& states,
    StressComponent component,
    std::function<void(size_t, size_t, const std::string&)> callback)
{
    std::vector<PartTimeHistory> histories;

    if (!initialized_ && !initialize()) {
        return histories;
    }

    if (states.empty()) {
        last_error_ = "No states provided";
        return histories;
    }

    histories.resize(parts_.size());
    size_t num_states = states.size();

    // Initialize all histories
    for (size_t p = 0; p < parts_.size(); ++p) {
        histories[p].part_id = parts_[p].part_id;
        histories[p].part_name = parts_[p].name;
        histories[p].times.reserve(num_states);
        histories[p].max_values.reserve(num_states);
        histories[p].min_values.reserve(num_states);
        histories[p].avg_values.reserve(num_states);
        histories[p].max_elem_ids.reserve(num_states);
    }

    // Process each state (using pre-loaded data - no file I/O!)
    for (size_t s = 0; s < num_states; ++s) {
        const auto& state = states[s];

        if (callback && s % 100 == 0) {
            callback(s, num_states, "Processing state " + std::to_string(s));
        }

        // Analyze each part for this state
        for (size_t p = 0; p < parts_.size(); ++p) {
            auto stats = analyze_state(parts_[p].part_id, state, component);

            histories[p].times.push_back(state.time);
            histories[p].max_values.push_back(stats.stress_max);
            histories[p].min_values.push_back(stats.stress_min);
            histories[p].avg_values.push_back(stats.stress_avg);
            histories[p].max_elem_ids.push_back(stats.max_element_id);
        }
    }

    if (callback) callback(num_states, num_states, "Analysis complete");

    return histories;
}

bool PartAnalyzer::export_to_csv(const PartTimeHistory& history, const std::string& filepath) {
    std::ofstream ofs(filepath);
    if (!ofs.is_open()) {
        last_error_ = "Failed to open file: " + filepath;
        return false;
    }

    // Write header
    ofs << "Time,Max,Min,Avg,MaxElementID\n";

    // Write data
    for (size_t i = 0; i < history.times.size(); ++i) {
        ofs << std::scientific << std::setprecision(6)
            << history.times[i] << ","
            << history.max_values[i] << ","
            << history.min_values[i] << ","
            << history.avg_values[i] << ","
            << history.max_elem_ids[i] << "\n";
    }

    return true;
}

bool PartAnalyzer::export_to_csv(const std::vector<PartTimeHistory>& histories,
                                  const std::string& filepath) {
    if (histories.empty()) {
        last_error_ = "No histories to export";
        return false;
    }

    std::ofstream ofs(filepath);
    if (!ofs.is_open()) {
        last_error_ = "Failed to open file: " + filepath;
        return false;
    }

    // Write header with part IDs
    ofs << "Time";
    for (const auto& h : histories) {
        ofs << ",Part" << h.part_id << "_Max"
            << ",Part" << h.part_id << "_Min"
            << ",Part" << h.part_id << "_Avg";
    }
    ofs << "\n";

    // Write data (assume all histories have same time values)
    size_t num_steps = histories[0].times.size();
    for (size_t i = 0; i < num_steps; ++i) {
        ofs << std::scientific << std::setprecision(6) << histories[0].times[i];
        for (const auto& h : histories) {
            if (i < h.max_values.size()) {
                ofs << "," << h.max_values[i]
                    << "," << h.min_values[i]
                    << "," << h.avg_values[i];
            } else {
                ofs << ",,,";
            }
        }
        ofs << "\n";
    }

    return true;
}

bool PartAnalyzer::export_summary_csv(const std::vector<PartTimeHistory>& histories,
                                       const std::string& filepath) {
    if (histories.empty()) {
        last_error_ = "No histories to export";
        return false;
    }

    std::ofstream ofs(filepath);
    if (!ofs.is_open()) {
        last_error_ = "Failed to open file: " + filepath;
        return false;
    }

    // Write header
    ofs << "PartID,PartName,GlobalMax,GlobalMin,GlobalAvg,TimeOfMax,TimeOfMin\n";

    // Calculate summary for each part
    for (const auto& h : histories) {
        if (h.max_values.empty()) continue;

        // Find global max/min
        auto max_it = std::max_element(h.max_values.begin(), h.max_values.end());
        auto min_it = std::min_element(h.min_values.begin(), h.min_values.end());

        size_t max_idx = std::distance(h.max_values.begin(), max_it);
        size_t min_idx = std::distance(h.min_values.begin(), min_it);

        double global_avg = 0.0;
        for (double v : h.avg_values) {
            global_avg += v;
        }
        global_avg /= h.avg_values.size();

        ofs << h.part_id << ","
            << h.part_name << ","
            << std::scientific << std::setprecision(6)
            << *max_it << ","
            << *min_it << ","
            << global_avg << ","
            << h.times[max_idx] << ","
            << h.times[min_idx] << "\n";
    }

    return true;
}

} // namespace analysis
} // namespace kood3plot
