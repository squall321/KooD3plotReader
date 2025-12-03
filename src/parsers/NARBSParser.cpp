#include "kood3plot/parsers/NARBSParser.hpp"
#include <iostream>

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

    // 1. Node IDs (NSORT = NUMNP)
    int numnp = control_data_.NUMNP;
    if (numnp > 0) {
        node_ids_.reserve(numnp);
        for (int i = 0; i < numnp; ++i) {
            int32_t node_id = reader_->read_int(offset++);
            node_ids_.push_back(node_id);
            node_id_to_index_[node_id] = i;
        }
        std::cerr << "  Node IDs: " << node_ids_.size() << std::endl;
    }

    // 2. Solid element IDs (NSORT8 = abs(NEL8))
    int num_solids = std::abs(control_data_.NEL8);
    if (num_solids > 0) {
        solid_ids_.reserve(num_solids);
        for (int i = 0; i < num_solids; ++i) {
            int32_t elem_id = reader_->read_int(offset++);
            solid_ids_.push_back(elem_id);
            solid_id_to_index_[elem_id] = i;
        }
        std::cerr << "  Solid element IDs: " << solid_ids_.size() << std::endl;
    }

    // 3. Thick shell element IDs (NSORTT = NELT)
    int num_thick_shells = control_data_.NELT;
    if (num_thick_shells > 0) {
        thick_shell_ids_.reserve(num_thick_shells);
        for (int i = 0; i < num_thick_shells; ++i) {
            int32_t elem_id = reader_->read_int(offset++);
            thick_shell_ids_.push_back(elem_id);
            thick_shell_id_to_index_[elem_id] = i;
        }
        std::cerr << "  Thick shell element IDs: " << thick_shell_ids_.size() << std::endl;
    }

    // 4. Beam element IDs (NSORT2 = NEL2)
    int num_beams = control_data_.NEL2;
    if (num_beams > 0) {
        beam_ids_.reserve(num_beams);
        for (int i = 0; i < num_beams; ++i) {
            int32_t elem_id = reader_->read_int(offset++);
            beam_ids_.push_back(elem_id);
            beam_id_to_index_[elem_id] = i;
        }
        std::cerr << "  Beam element IDs: " << beam_ids_.size() << std::endl;
    }

    // 5. Shell element IDs (NSORT4 = NEL4)
    int num_shells = control_data_.NEL4;
    if (num_shells > 0) {
        shell_ids_.reserve(num_shells);
        for (int i = 0; i < num_shells; ++i) {
            int32_t elem_id = reader_->read_int(offset++);
            shell_ids_.push_back(elem_id);
            shell_id_to_index_[elem_id] = i;
        }
        std::cerr << "  Shell element IDs: " << shell_ids_.size() << std::endl;
    }

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
    size_t total_read = node_ids_.size() + solid_ids_.size() + thick_shell_ids_.size()
                      + beam_ids_.size() + shell_ids_.size() + 3 * nmmat;
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
