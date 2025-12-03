#include "kood3plot/data/ControlData.hpp"
#include <cstring>

namespace kood3plot {
namespace data {

ControlData::ControlData()
    : NDIM(0)
    , NUMNP(0)
    , ICODE(0)
    , NGLBV(0)
    , IT(0)
    , IU(0)
    , IV(0)
    , IA(0)
    , NEL8(0)
    , NUMMAT8(0)
    , NUMDS(0)
    , NUMST(0)
    , NV3D(0)
    , NEL2(0)
    , NUMMAT2(0)
    , NV1D(0)
    , NEL4(0)
    , NUMMAT4(0)
    , NV2D(0)
    , NEIPH(0)
    , NEIPS(0)
    , MAXINT(0)
    , EDLOPT(0)
    , NMSPH(0)
    , NGPSPH(0)
    , NARBS(0)
    , NELT(0)
    , NUMMATT(0)
    , NV3DT(0)
    , IALEMAT(0)
    , DT(0.0)
    , EXTRA(0)
    , MDLOPT(0)
    , ISTRN(0)
    , NND(0)
    , ENN(0)
    , DELNN(0)
    , NMMAT(0)
    , IDTDT(0) {

    // Initialize arrays
    for (int i = 0; i < 4; ++i) {
        IOSHL[i] = 0;
    }
    for (int i = 0; i < 2; ++i) {
        IOSOL[i] = 0;
    }
}

void ControlData::compute_derived_values() {
    // Compute MDLOPT from MAXINT sign (ls-dyna_database.txt lines 312-320)
    if (MAXINT >= 0) {
        MDLOPT = 0;
        // MAXINT stays as is
    } else if (MAXINT < -10000) {
        MDLOPT = 2;
        MAXINT = std::abs(MAXINT) - 10000;
    } else { // MAXINT < 0 but >= -10000
        MDLOPT = 1;
        MAXINT = std::abs(MAXINT);
    }

    // Compute ISTRN (ls-dyna_database.txt lines 432-450)
    if (IDTDT >= 100) {
        // Extract digit from IDTDT
        ISTRN = (IDTDT / 10000) % 10;
    } else {
        // ISTRN must be computed
        ISTRN = 0;

        // Check based on NV2D
        if (NV2D > 0) {
            int computed = NV2D - MAXINT * (6 * IOSHL[0] + IOSHL[1] + NEIPS)
                          - 8 * IOSHL[2] - 4 * IOSHL[3];
            if (computed / 12 == 1) {
                ISTRN = 1;
            }
        }
        // Also check based on NV3D
        else if (NV3D > 0 && NV3DT != 0 && NEIPH >= 6) {
            ISTRN = 1;
        }
    }

    // Compute NND (ls-dyna_database.txt line 1838)
    // NND = ((IT+N)+NDIM*(IU+IV+IA))*NUMNP
    // where N depends on IT value
    int N = 0;
    if (IT == 2) {
        N = 2;  // node temperature and flux
    } else if (IT == 3) {
        N = 3;  // 3 temperatures per node
    } else if (IT / 10 == 1) {
        N = 1;  // mass scaling
    }

    // ls-dyna_database.txt lines 230-231:
    // "If 4 then element connectivities are unpacked in the DYNA3D database and NDIM is reset to 3."
    // NDIM=4 means unpacked connectivity format, but actual dimensions is 3
    // NDIM=5,7 means MATTYP array present, actual dimensions is still 3
    int effective_ndim = NDIM;
    if (NDIM == 4 || NDIM == 5 || NDIM == 7) {
        effective_ndim = 3;
    }

    NND = ((IT + N) + effective_ndim * (IU + IV + IA)) * NUMNP;

    // Compute ENN (ls-dyna_database.txt lines 1868-1869)
    // ENN = NEL8*NV3D + NELT*NV3DT + NEL2*NV1D + NEL4*NV2D + NMSPH*NUM_SPH_VARS
    // Note: NUM_SPH_VARS is typically 0 for standard d3plot
    int num_sph_vars = 0;  // SPH variables (not commonly used)
    ENN = std::abs(NEL8) * NV3D + NELT * NV3DT + NEL2 * NV1D + NEL4 * NV2D + NMSPH * num_sph_vars;

    // Compute DELNN (ls-dyna_database.txt lines 2076-2082)
    // Element deletion data: if MDLOPT > 0
    // MDLOPT=1: NUMNP floating point values
    // MDLOPT=2: (NEL8 + NELT + NEL4 + NEL2) floating point values
    DELNN = 0;
    if (MDLOPT == 1) {
        DELNN = NUMNP;
    } else if (MDLOPT == 2) {
        DELNN = std::abs(NEL8) + NELT + NEL4 + NEL2;
    }
}

} // namespace data
} // namespace kood3plot
