#pragma once

#include "kood3plot/Types.hpp"
#include <string>

namespace kood3plot {
namespace data {

/**
 * @brief Control data structure (64 base words + EXTRA extended words)
 */
struct ControlData {
    // Base control words (addresses 1-64)
    std::string TITLE;      ///< Run title
    int32_t NDIM;           ///< Number of dimensions
    int32_t NUMNP;          ///< Number of nodal points
    int32_t ICODE;          ///< Code version
    int32_t NGLBV;          ///< Number of global variables

    int32_t IT;             ///< Flag for temperatures
    int32_t IU;             ///< Flag for 3 displacement components
    int32_t IV;             ///< Flag for 3 velocity components
    int32_t IA;             ///< Flag for 3 acceleration components
    int32_t NEL8;           ///< Number of 8-node solid elements

    int32_t NUMMAT8;        ///< Number of solid materials
    int32_t NUMDS;          ///< Number of solid datasets
    int32_t NUMST;          ///< Number of solid time steps
    int32_t NV3D;           ///< Number of variables per solid element
    int32_t NEL2;           ///< Number of beam elements

    int32_t NUMMAT2;        ///< Number of beam materials
    int32_t NV1D;           ///< Number of variables per beam element
    int32_t NEL4;           ///< Number of shell elements
    int32_t NUMMAT4;        ///< Number of shell materials
    int32_t NV2D;           ///< Number of variables per shell element

    int32_t NEIPH;          ///< Additional element variables
    int32_t NEIPS;          ///< Additional shell element variables
    int32_t MAXINT;         ///< Maximum integration points (determines MDLOPT)
    int32_t EDLOPT;         ///< Element deletion option
    int32_t NMSPH;          ///< Number of SPH nodes

    int32_t NGPSPH;         ///< Number of SPH particles
    int32_t NARBS;          ///< Number of ALE materials
    int32_t NELT;           ///< Number of thick shell elements
    int32_t NUMMATT;        ///< Number of thick shell materials
    int32_t NV3DT;          ///< Number of variables per thick shell element

    int32_t IOSHL[4];       ///< Shell output flags (converted from raw 999/1000 values)
    int32_t IOSOL[2];       ///< Solid output flags
    int32_t IALEMAT;        ///< ALE material flag

    double DT;              ///< Time step size
    int32_t EXTRA;          ///< Number of extended control words

    // Derived/computed values
    int32_t MDLOPT;         ///< Material numbering option (0, 1, or 2)
    int32_t ISTRN;          ///< Strain tensor output flag
    int32_t NND;            ///< Total nodal data words per time step
    int32_t ENN;            ///< Total element data words per time step
    int32_t DELNN;          ///< Element deletion data words per time step (if MDLOPT > 0)

    // Additional control words
    int32_t NMMAT;          ///< Total number of materials (parts) - word 51

    // Extended control words (if EXTRA > 0)
    int32_t IDTDT;          ///< Delta T flag (used for ISTRN computation)

    /**
     * @brief Initialize with default values
     */
    ControlData();

    /**
     * @brief Compute derived values (MDLOPT, ISTRN, NND, ENN)
     */
    void compute_derived_values();
};

} // namespace data
} // namespace kood3plot
