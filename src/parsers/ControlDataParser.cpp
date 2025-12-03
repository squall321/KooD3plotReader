#include "kood3plot/parsers/ControlDataParser.hpp"
#include <stdexcept>
#include <cmath>

namespace kood3plot {
namespace parsers {

ControlDataParser::ControlDataParser(std::shared_ptr<core::BinaryReader> reader)
    : reader_(reader) {
}

data::ControlData ControlDataParser::parse() {
    if (!reader_ || !reader_->is_open()) {
        throw std::runtime_error("BinaryReader not initialized or file not open");
    }

    data::ControlData cd;

    // Read 64 base control words (ls-dyna_database.txt lines 199-438)
    // DISK ADDRESS is already 0-indexed word address

    // Words 0-9: TITLE (not stored in ControlData for now)
    // Words 10+: Control data
    cd.NDIM = reader_->read_int(15);       // DISK ADDRESS 15
    cd.NUMNP = reader_->read_int(16);      // DISK ADDRESS 16
    cd.ICODE = reader_->read_int(17);      // DISK ADDRESS 17
    cd.NGLBV = reader_->read_int(18);      // DISK ADDRESS 18

    cd.IT = reader_->read_int(19);         // DISK ADDRESS 19
    cd.IU = reader_->read_int(20);         // DISK ADDRESS 20
    cd.IV = reader_->read_int(21);         // DISK ADDRESS 21
    cd.IA = reader_->read_int(22);         // DISK ADDRESS 22

    // Element and material counts
    cd.NEL8 = reader_->read_int(23);       // DISK ADDRESS 23
    cd.NUMMAT8 = reader_->read_int(24);    // DISK ADDRESS 24
    cd.NUMDS = reader_->read_int(25);      // DISK ADDRESS 25
    cd.NUMST = reader_->read_int(26);      // DISK ADDRESS 26
    cd.NV3D = reader_->read_int(27);       // DISK ADDRESS 27
    cd.NEL2 = reader_->read_int(28);       // DISK ADDRESS 28
    cd.NUMMAT2 = reader_->read_int(29);    // DISK ADDRESS 29
    cd.NV1D = reader_->read_int(30);       // DISK ADDRESS 30
    cd.NEL4 = reader_->read_int(31);       // DISK ADDRESS 31
    cd.NUMMAT4 = reader_->read_int(32);    // DISK ADDRESS 32
    cd.NV2D = reader_->read_int(33);       // DISK ADDRESS 33

    cd.NEIPH = reader_->read_int(34);      // DISK ADDRESS 34
    cd.NEIPS = reader_->read_int(35);      // DISK ADDRESS 35
    cd.MAXINT = reader_->read_int(36);     // DISK ADDRESS 36 (will be modified by compute_derived_values)
    cd.EDLOPT = reader_->read_int(37);     // DISK ADDRESS 37 (or NMSPH)
    cd.NMSPH = cd.EDLOPT;                  // Same location
    cd.NGPSPH = reader_->read_int(38);     // DISK ADDRESS 38

    cd.NARBS = reader_->read_int(39);      // DISK ADDRESS 39
    cd.NELT = reader_->read_int(40);       // DISK ADDRESS 40
    cd.NUMMATT = reader_->read_int(41);    // DISK ADDRESS 41
    cd.NV3DT = reader_->read_int(42);      // DISK ADDRESS 42

    // IOSHL raw values (ls-dyna_database.txt lines 344-356)
    int ioshl_raw[4];
    for (int i = 0; i < 4; ++i) {
        ioshl_raw[i] = reader_->read_int(43 + i);  // DISK ADDRESS 43-46
    }

    // Convert IOSHL/IOSOL flags (ls-dyna_database.txt lines 344-352)
    compute_IOSHL(cd, ioshl_raw);
    compute_IOSOL(cd, ioshl_raw);

    cd.IALEMAT = reader_->read_int(47);    // DISK ADDRESS 47

    // NMMAT - Total number of materials/parts (ls-dyna_database.txt line 373)
    cd.NMMAT = reader_->read_int(51);      // DISK ADDRESS 51

    // Other fields...
    cd.DT = reader_->read_double(55);      // DISK ADDRESS 55 - time step

    // IDTDT (ls-dyna_database.txt lines 398-434)
    cd.IDTDT = reader_->read_int(56);      // DISK ADDRESS 56

    // EXTRA - number of extended words (ls-dyna_database.txt line 436)
    cd.EXTRA = reader_->read_int(57);      // DISK ADDRESS 57 (NOT 64!)

    // If EXTRA > 0, read extended control words (words 65+)
    // For now, we skip them but could add specific ones if needed

    // Compute derived values (MDLOPT, ISTRN, NND, ENN)
    cd.compute_derived_values();

    return cd;
}

void ControlDataParser::compute_IOSOL(data::ControlData& cd, const int ioshl_raw[4]) {
    // ls-dyna_database.txt lines 344-352
    // IOSHL(1): if 1000 → IOSOL(1)=1, if 999 → IOSOL(1)=1, else → IOSOL(1)=0
    // IOSHL(2): if 1000 → IOSOL(2)=1, if 999 → IOSOL(2)=1, else → IOSOL(2)=0

    for (int i = 0; i < 2; ++i) {
        if (ioshl_raw[i] == 1000 || ioshl_raw[i] == 999) {
            cd.IOSOL[i] = 1;
        } else {
            cd.IOSOL[i] = 0;
        }
    }
}

void ControlDataParser::compute_IOSHL(data::ControlData& cd, const int ioshl_raw[4]) {
    // ls-dyna_database.txt lines 344-356
    // IOSHL(1), IOSHL(2): if 1000 → 1, else → 0
    // IOSHL(3), IOSHL(4): if 1000 → 1, else → 0

    for (int i = 0; i < 4; ++i) {
        if (ioshl_raw[i] == 1000) {
            cd.IOSHL[i] = 1;
        } else {
            cd.IOSHL[i] = 0;
        }
    }
}

} // namespace parsers
} // namespace kood3plot
