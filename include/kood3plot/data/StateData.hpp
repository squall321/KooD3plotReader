#pragma once

#include "kood3plot/Types.hpp"
#include <vector>

namespace kood3plot {
namespace data {

/**
 * @brief State data for a single time step
 */
struct StateData {
    double time;                              ///< Simulation time
    std::vector<double> global_vars;          ///< Global variables

    // Nodal data
    std::vector<double> node_temperatures;    ///< Node temperatures (if IT=1)
    std::vector<double> node_displacements;   ///< Node displacements (if IU=1): Ux,Uy,Uz per node
    std::vector<double> node_velocities;      ///< Node velocities (if IV=1): Vx,Vy,Vz per node
    std::vector<double> node_accelerations;   ///< Node accelerations (if IA=1): Ax,Ay,Az per node

    // Element data (in order: solids, thick shells, beams, shells)
    std::vector<double> solid_data;           ///< Solid element data
    std::vector<double> thick_shell_data;     ///< Thick shell element data
    std::vector<double> beam_data;            ///< Beam element data
    std::vector<double> shell_data;           ///< Shell element data

    // Deletion flags
    std::vector<int32_t> deleted_nodes;       ///< Deleted node IDs
    std::vector<int32_t> deleted_solids;      ///< Deleted solid element IDs
    std::vector<int32_t> deleted_beams;       ///< Deleted beam element IDs
    std::vector<int32_t> deleted_shells;      ///< Deleted shell element IDs
    std::vector<int32_t> deleted_thick_shells; ///< Deleted thick shell element IDs

    /**
     * @brief Constructor
     */
    StateData();

    /**
     * @brief Check if this state has valid data
     */
    bool is_valid() const { return time >= 0.0; }
};

} // namespace data
} // namespace kood3plot
