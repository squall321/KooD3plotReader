#include "kood3plot/parsers/NARBSParser.hpp"
#include <iostream>
#include <algorithm>

namespace kood3plot {
namespace parsers {

NARBSParser::NARBSParser(std::shared_ptr<core::BinaryReader> reader,
                         const data::ControlData& control_data)
    : reader_(reader)
    , control_data_(control_data)
{
}

void NARBSParser::parse(size_t& offset) {
    // ls-dyna_database.txt lines 667-724
    // NARBS section contains arbitrary node and element numbering
    //
    // NARBS section structure:
    // - Header (16 words): counts and offsets
    //   Word 0: NSORT = NUMNP (or -NUMNP if pointer array)
    //   Word 1: NSRH = |NEL8|
    //   Word 2: NSRB = NEL2
    //   Word 3: NSRS = NEL4
    //   Word 4: NSRT = NELT
    //   Word 5: NSORTD = total words for sorting
    //   Word 6: NSRHD = sorted/unsorted data
    //   Word 7: NSRBD = beam data
    //   Word 8: NSRSD = shell data
    //   Word 9: NSRTD = thick shell data
    //   Words 10-15: Additional header data
    // - Data arrays (node IDs, element IDs, etc.)

    if (control_data_.NARBS == 0) {
        // No arbitrary numbering - use sequential IDs
        return;
    }

    std::cerr << "Parsing NARBS section (" << control_data_.NARBS << " words)..." << std::endl;

    // Read NARBS header to determine structure
    int nsort = reader_->read_int(offset);      // Number of nodes (may be negative)
    int nsrh = reader_->read_int(offset + 1);   // Number of solids
    int nsrb = reader_->read_int(offset + 2);   // Number of beams
    int nsrs = reader_->read_int(offset + 3);   // Number of shells
    int nsrt = reader_->read_int(offset + 4);   // Number of thick shells

    // Determine header size based on NSORT value
    // If NSORT < 0, it indicates a pointer array format (16 words header)
    // If NSORT > 0, it's the direct array format (10 words header)
    int header_size = (nsort < 0) ? 16 : 10;

    // Skip header
    offset += header_size;
    const size_t data_base = offset;

    // 블록 순서는 **규격 순서** 로만 읽는다: NUSERN(절점) → NUSERH(솔리드) →
    // NUSERB(빔) → NUSERS(셸) → NUSERT(두꺼운 셸) (ls-dyna_database.txt:728-732).
    // 예전 구현은 두꺼운 셸을 빔·셸보다 먼저 읽어, 셸과 두꺼운 셸이 함께 있는 덱에서
    // 두 배열이 통째로 어긋났다 (배터리 덱: 셸 ID 가 393~12074 여야 하는데 8233~10624).
    const int numnp = control_data_.NUMNP;
    const int num_solids = std::abs(control_data_.NEL8);
    const int num_beams = control_data_.NEL2;
    const int num_shells = control_data_.NEL4;
    const int num_thick_shells = control_data_.NELT;

    size_t pos_node = 0;
    size_t pos_solid = pos_node + static_cast<size_t>(std::max(numnp, 0));
    size_t pos_beam = pos_solid + static_cast<size_t>(std::max(num_solids, 0));
    size_t pos_shell = pos_beam + static_cast<size_t>(std::max(num_beams, 0));
    size_t pos_thick = pos_shell + static_cast<size_t>(std::max(num_shells, 0));
    const size_t pos_after = pos_thick + static_cast<size_t>(std::max(num_thick_shells, 0));

    // 포인터 형식(NSORT < 0)이면 헤더의 1-based 포인터(NSRH/NSRB/NSRS/NSRT)가
    // 각 블록 시작을 직접 가리킨다. 개수로 계산한 위치와 다르면 포인터를 따르고
    // 사유를 남긴다 — 조용히 어긋난 배열을 내보내지 않는다.
    auto use_pointer = [&](int ptr, size_t& pos, const char* name) {
        if (nsort >= 0 || ptr <= 0) return;
        size_t from_ptr = static_cast<size_t>(ptr) - 1;
        if (from_ptr != pos) {
            std::cerr << "  NARBS 경고: " << name << " 블록 위치가 개수 계산("
                      << pos << ")과 헤더 포인터(" << from_ptr << ")에서 다릅니다 — 포인터를 따릅니다"
                      << std::endl;
            pos = from_ptr;
        }
    };
    use_pointer(nsrh, pos_solid, "solid");
    use_pointer(nsrb, pos_beam, "beam");
    use_pointer(nsrs, pos_shell, "shell");
    use_pointer(nsrt, pos_thick, "thick shell");

    auto read_ids = [&](size_t pos, int count, std::vector<int32_t>& ids,
                        std::unordered_map<int32_t, size_t>& index_map, const char* label) {
        if (count <= 0) return;
        ids.reserve(count);
        size_t at = data_base + pos;
        for (int i = 0; i < count; ++i) {
            int32_t id = reader_->read_int(at++);
            ids.push_back(id);
            index_map[id] = static_cast<size_t>(i);
        }
        std::cerr << "  " << label << ": " << ids.size() << std::endl;
    };

    read_ids(pos_node, numnp, node_ids_, node_id_to_index_, "Node IDs");
    read_ids(pos_solid, num_solids, solid_ids_, solid_id_to_index_, "Solid element IDs");
    read_ids(pos_beam, num_beams, beam_ids_, beam_id_to_index_, "Beam element IDs");
    read_ids(pos_shell, num_shells, shell_ids_, shell_id_to_index_, "Shell element IDs");
    read_ids(pos_thick, num_thick_shells, thick_shell_ids_, thick_shell_id_to_index_, "Thick shell element IDs");

    offset = data_base + pos_after;

    // 6. Part ID arrays (NORDER, NSRMU, NSRMP) - 3*NMMAT entries total
    // ls-dyna_database.txt:
    //   NORDER   NMMAT    Ordered array of user defined material (part) ID's
    //   NSRMU    NMMAT    Unordered array of user material (part) ID's
    //   NSRMP    NMMAT    Cross reference array
    int nmmat = control_data_.NMMAT;
    if (nmmat > 0) {
        // Read NORDER - this is the Part ID mapping we need
        part_ids_.reserve(nmmat);
        for (int i = 0; i < nmmat; ++i) {
            int32_t part_id = reader_->read_int(offset++);
            part_ids_.push_back(part_id);
        }
        std::cerr << "  Part IDs (NORDER): " << part_ids_.size() << std::endl;

        // Skip NSRMU and NSRMP (we don't need them for now)
        offset += 2 * nmmat;  // Skip unordered and cross-reference arrays
    }

    // 7. Material type numbers (remaining after Part ID arrays)
    size_t total_read = node_ids_.size() + solid_ids_.size() + beam_ids_.size()
                      + shell_ids_.size() + thick_shell_ids_.size() + 3 * nmmat;
    size_t remaining = control_data_.NARBS - total_read;

    if (remaining > 0 && remaining < 100000) {  // Sanity check
        material_types_.reserve(remaining);
        for (size_t i = 0; i < remaining; ++i) {
            int32_t mat_type = reader_->read_int(offset++);
            material_types_.push_back(mat_type);
        }
        std::cerr << "  Material types: " << material_types_.size() << std::endl;
    }

    std::cerr << "✓ NARBS parsing completed" << std::endl;
}

int32_t NARBSParser::get_real_part_id(int32_t material_index) const {
    // material_index is 1-based (from element data)
    if (part_ids_.empty()) {
        // No NARBS data - material index is Part ID
        return material_index;
    }

    // Convert to 0-based index
    int idx = material_index - 1;
    if (idx < 0 || idx >= static_cast<int>(part_ids_.size())) {
        // Out of range - return the material index as-is
        return material_index;
    }

    return part_ids_[idx];
}

int32_t NARBSParser::get_real_node_id(size_t internal_index) const {
    if (node_ids_.empty() || internal_index >= node_ids_.size()) {
        // No NARBS or out of range - return sequential ID
        return static_cast<int32_t>(internal_index + 1);
    }
    return node_ids_[internal_index];
}

int32_t NARBSParser::get_real_element_id(ElementType element_type, size_t internal_index) const {
    switch (element_type) {
        case ElementType::SOLID:
            if (solid_ids_.empty() || internal_index >= solid_ids_.size()) {
                return static_cast<int32_t>(internal_index + 1);
            }
            return solid_ids_[internal_index];

        case ElementType::BEAM:
            if (beam_ids_.empty() || internal_index >= beam_ids_.size()) {
                return static_cast<int32_t>(internal_index + 1);
            }
            return beam_ids_[internal_index];

        case ElementType::SHELL:
            if (shell_ids_.empty() || internal_index >= shell_ids_.size()) {
                return static_cast<int32_t>(internal_index + 1);
            }
            return shell_ids_[internal_index];

        case ElementType::THICK_SHELL:
            if (thick_shell_ids_.empty() || internal_index >= thick_shell_ids_.size()) {
                return static_cast<int32_t>(internal_index + 1);
            }
            return thick_shell_ids_[internal_index];

        default:
            return static_cast<int32_t>(internal_index + 1);
    }
}

size_t NARBSParser::get_internal_node_index(int32_t real_id) const {
    auto it = node_id_to_index_.find(real_id);
    if (it != node_id_to_index_.end()) {
        return it->second;
    }
    // If not found and no NARBS, assume sequential
    return static_cast<size_t>(real_id - 1);
}

size_t NARBSParser::get_internal_element_index(ElementType element_type, int32_t real_id) const {
    const std::unordered_map<int32_t, size_t>* map_ptr = nullptr;

    switch (element_type) {
        case ElementType::SOLID:
            map_ptr = &solid_id_to_index_;
            break;
        case ElementType::BEAM:
            map_ptr = &beam_id_to_index_;
            break;
        case ElementType::SHELL:
            map_ptr = &shell_id_to_index_;
            break;
        case ElementType::THICK_SHELL:
            map_ptr = &thick_shell_id_to_index_;
            break;
        default:
            return static_cast<size_t>(real_id - 1);
    }

    auto it = map_ptr->find(real_id);
    if (it != map_ptr->end()) {
        return it->second;
    }
    // If not found and no NARBS, assume sequential
    return static_cast<size_t>(real_id - 1);
}

} // namespace parsers
} // namespace kood3plot
