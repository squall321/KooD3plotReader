/**
 * @file MotionAnalyzer.cpp
 * @brief Part motion analysis implementation
 */

#include "kood3plot/analysis/MotionAnalyzer.hpp"
#include <cmath>
#include <algorithm>
#include <iostream>

namespace kood3plot {
namespace analysis {

MotionAnalyzer::MotionAnalyzer(D3plotReader& reader)
    : reader_(reader)
{
}

void MotionAnalyzer::setParts(const std::vector<int32_t>& part_ids) {
    part_ids_ = part_ids;
}

bool MotionAnalyzer::initialize() {
    initialized_ = false;

    // Get mesh data
    mesh_ = reader_.read_mesh();
    if (mesh_.nodes.empty()) {
        last_error_ = "No nodes in mesh";
        return false;
    }

    // Store initial coordinates and count nodes
    num_nodes_ = mesh_.nodes.size();
    initial_coords_.resize(num_nodes_ * 3);
    for (size_t i = 0; i < num_nodes_; ++i) {
        initial_coords_[i * 3 + 0] = mesh_.nodes[i].x;
        initial_coords_[i * 3 + 1] = mesh_.nodes[i].y;
        initial_coords_[i * 3 + 2] = mesh_.nodes[i].z;
    }

    // Build node to part mapping
    buildNodeToPartMapping();

    // Determine active parts
    if (part_ids_.empty()) {
        // Use all parts that have nodes
        for (const auto& kv : part_node_indices_) {
            active_parts_.push_back(kv.first);
        }
        std::sort(active_parts_.begin(), active_parts_.end());
    } else {
        active_parts_ = part_ids_;
    }

    if (active_parts_.empty()) {
        last_error_ = "No parts to analyze";
        return false;
    }

    // Initialize results storage
    results_.clear();
    results_.resize(active_parts_.size());
    for (size_t i = 0; i < active_parts_.size(); ++i) {
        results_[i].part_id = active_parts_[i];
        part_id_to_result_index_[active_parts_[i]] = i;
    }

    // Initialize previous state buffers
    prev_avg_displacements_.resize(active_parts_.size(), Vec3(0, 0, 0));
    prev_avg_velocities_.resize(active_parts_.size(), Vec3(0, 0, 0));
    prev_time_ = 0.0;
    prev_prev_time_ = 0.0;
    state_count_ = 0;

    initialized_ = true;
    return true;
}

void MotionAnalyzer::buildNodeToPartMapping() {
    part_node_indices_.clear();

    // Build node to part mapping from solid elements
    for (size_t elem_idx = 0; elem_idx < mesh_.solids.size(); ++elem_idx) {
        const auto& elem = mesh_.solids[elem_idx];
        int32_t part_id = mesh_.solid_parts.empty() ? 1 :
                         (elem_idx < mesh_.solid_parts.size() ? mesh_.solid_parts[elem_idx] : 1);

        // Add all nodes of this element to the part
        for (int32_t node_id : elem.node_ids) {
            if (node_id > 0) {
                // Convert to 0-based index
                size_t node_idx = static_cast<size_t>(node_id - 1);
                if (node_idx < num_nodes_) {
                    part_node_indices_[part_id].insert(node_idx);
                }
            }
        }
    }

    // Also check shell elements if available
    for (size_t elem_idx = 0; elem_idx < mesh_.shells.size(); ++elem_idx) {
        const auto& elem = mesh_.shells[elem_idx];
        int32_t part_id = mesh_.shell_parts.empty() ? 1 :
                         (elem_idx < mesh_.shell_parts.size() ? mesh_.shell_parts[elem_idx] : 1);

        for (int32_t node_id : elem.node_ids) {
            if (node_id > 0) {
                size_t node_idx = static_cast<size_t>(node_id - 1);
                if (node_idx < num_nodes_) {
                    part_node_indices_[part_id].insert(node_idx);
                }
            }
        }
    }
}

Vec3 MotionAnalyzer::computeAverageDisplacement(int32_t part_id, const std::vector<double>& displacements) {
    auto it = part_node_indices_.find(part_id);
    if (it == part_node_indices_.end() || it->second.empty()) {
        return Vec3(0, 0, 0);
    }

    Vec3 sum(0, 0, 0);
    size_t count = 0;

    for (size_t node_idx : it->second) {
        if (node_idx * 3 + 2 < displacements.size()) {
            // Displacements are already Ux, Uy, Uz
            sum.x += displacements[node_idx * 3 + 0];
            sum.y += displacements[node_idx * 3 + 1];
            sum.z += displacements[node_idx * 3 + 2];
            count++;
        }
    }

    if (count > 0) {
        sum.x /= static_cast<double>(count);
        sum.y /= static_cast<double>(count);
        sum.z /= static_cast<double>(count);
    }

    return sum;
}

std::pair<double, int32_t> MotionAnalyzer::computeMaxDisplacement(int32_t part_id, const std::vector<double>& displacements) {
    auto it = part_node_indices_.find(part_id);
    if (it == part_node_indices_.end() || it->second.empty()) {
        return {0.0, 0};
    }

    double max_disp = 0.0;
    int32_t max_node_id = 0;

    for (size_t node_idx : it->second) {
        if (node_idx * 3 + 2 < displacements.size()) {
            // Displacements are already Ux, Uy, Uz
            double dx = displacements[node_idx * 3 + 0];
            double dy = displacements[node_idx * 3 + 1];
            double dz = displacements[node_idx * 3 + 2];
            double disp = std::sqrt(dx*dx + dy*dy + dz*dz);

            if (disp > max_disp) {
                max_disp = disp;
                max_node_id = static_cast<int32_t>(node_idx + 1);  // 1-based
            }
        }
    }

    return {max_disp, max_node_id};
}

void MotionAnalyzer::processState(const data::StateData& state) {
    if (!initialized_) {
        return;
    }

    double current_time = state.time;
    double dt = (state_count_ > 0) ? (current_time - prev_time_) : 0.0;

    // Get displacements from state data
    const auto& displacements = state.node_displacements;
    if (displacements.empty()) {
        return;
    }

    // Process each part
    for (size_t i = 0; i < active_parts_.size(); ++i) {
        int32_t part_id = active_parts_[i];
        auto& stats = results_[i];

        MotionTimePoint point;
        point.time = current_time;

        // Compute average displacement
        point.avg_displacement = computeAverageDisplacement(part_id, displacements);
        point.avg_displacement_magnitude = point.avg_displacement.magnitude();

        // Compute maximum displacement
        auto [max_disp, max_node_id] = computeMaxDisplacement(part_id, displacements);
        point.max_displacement_magnitude = max_disp;
        point.max_displacement_node_id = max_node_id;

        // Compute velocity (numerical differentiation)
        if (state_count_ > 0 && dt > 0) {
            Vec3 disp_diff = point.avg_displacement - prev_avg_displacements_[i];
            point.avg_velocity.x = disp_diff.x / dt;
            point.avg_velocity.y = disp_diff.y / dt;
            point.avg_velocity.z = disp_diff.z / dt;
            point.avg_velocity_magnitude = point.avg_velocity.magnitude();
        }

        // Compute acceleration (numerical differentiation of velocity)
        if (state_count_ > 1 && dt > 0) {
            Vec3 vel_diff = point.avg_velocity - prev_avg_velocities_[i];
            point.avg_acceleration.x = vel_diff.x / dt;
            point.avg_acceleration.y = vel_diff.y / dt;
            point.avg_acceleration.z = vel_diff.z / dt;
            point.avg_acceleration_magnitude = point.avg_acceleration.magnitude();
        }

        // Store this point
        stats.data.push_back(point);

        // Update previous values
        prev_avg_displacements_[i] = point.avg_displacement;
        prev_avg_velocities_[i] = point.avg_velocity;
    }

    // Update time tracking
    prev_prev_time_ = prev_time_;
    prev_time_ = current_time;
    state_count_++;
}

std::vector<PartMotionStats> MotionAnalyzer::getResults() {
    // Compute global statistics for each part
    for (auto& stats : results_) {
        stats.computeGlobalStats();
    }
    return results_;
}

void MotionAnalyzer::reset() {
    results_.clear();
    prev_avg_displacements_.clear();
    prev_avg_velocities_.clear();
    prev_time_ = 0.0;
    prev_prev_time_ = 0.0;
    state_count_ = 0;
    initialized_ = false;
}

} // namespace analysis
} // namespace kood3plot
