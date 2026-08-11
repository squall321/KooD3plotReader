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
    /// 절점 좌표/변위 3성분 배열. **이름과 달리 의미가 소스에 따라 다르다.**
    ///
    ///  - d3plot 에서 읽은 경우 (IU=1): **현재 절대 좌표**다. 변위가 아니다.
    ///    t=0 에서 mesh.nodes 와 값이 완전히 같은 것으로 실측 확인.
    ///    → mesh.nodes 에 더하면 2·X0 + u 가 되어 조용히 틀린다.
    ///  - RadiossReader 가 채운 경우: 초기 위치를 뺀 **델타**다
    ///    (RadiossReader.cpp:519). RadiossToD3plotConverter 가 다시 더해서
    ///    d3plot 규약(절대좌표)으로 내보낸다.
    ///
    /// 그래서 d3plot 소비자는 IU!=0 이면 이 값을 **그대로** 좌표로 써야 한다.
    /// 직접 인덱싱하지 말고 data/NodeKinematics.hpp 의
    /// nodePosition() / nodeDisplacement() 를 쓸 것.
    std::vector<double> node_displacements;
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
