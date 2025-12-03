#include "kood3plot/parsers/GeometryParser.hpp"
#include "kood3plot/parsers/NARBSParser.hpp"
#include <stdexcept>
#include <cmath>

namespace kood3plot {
namespace parsers {

GeometryParser::GeometryParser(std::shared_ptr<core::BinaryReader> reader,
                               const data::ControlData& control_data)
    : reader_(reader)
    , control_data_(control_data) {
}

data::Mesh GeometryParser::parse() {
    if (!reader_ || !reader_->is_open()) {
        throw std::runtime_error("BinaryReader not initialized or file not open");
    }

    data::Mesh mesh;

    // Geometry section starts at word address: 64 + EXTRA
    // (ls-dyna_database.txt lines 626-663)
    size_t offset = 64 + control_data_.EXTRA;

    // Parse in order: Nodes → Solids → Thick Shells → Beams → Shells → NARBS
    parse_nodes(mesh, offset);
    parse_solids(mesh, offset);
    parse_thick_shells(mesh, offset);
    parse_beams(mesh, offset);
    parse_shells(mesh, offset);
    parse_narbs(mesh, offset);

    return mesh;
}

void GeometryParser::parse_nodes(data::Mesh& mesh, size_t& offset) {
    // ls-dyna_database.txt lines 637-638
    // X(3,1): 3*NUMNP Array of nodal coordinates X1,Y1,Z1, X2,Y2,Z2, ...
    //
    // IMPORTANT: ls-dyna_database.txt lines 227-234
    // NDIM=4: element connectivities are unpacked, NDIM is reset to 3
    // NDIM=5 or 7: NDIM is reset to 3
    // So for geometry, we always read 3 coordinates per node!

    int numnp = control_data_.NUMNP;
    int ndim = control_data_.NDIM;

    if (numnp <= 0) {
        return;  // No nodes to parse
    }

    // Calculate effective ndim for coordinates (always 3 for standard 3D models)
    // ls-dyna_database.txt line 230-231: "If 4 then ... NDIM is reset to 3"
    int effective_ndim = ndim;
    if (ndim == 4 || ndim == 5 || ndim == 7) {
        effective_ndim = 3;
    }

    mesh.nodes.reserve(numnp);

    // Read coordinates - effective_ndim values per node
    for (int i = 0; i < numnp; ++i) {
        Node node;
        node.id = i + 1;  // Internal node numbering (1-indexed)

        if (effective_ndim >= 1) {
            node.x = reader_->read_double(offset++);
        }
        if (effective_ndim >= 2) {
            node.y = reader_->read_double(offset++);
        }
        if (effective_ndim >= 3) {
            node.z = reader_->read_double(offset++);
        }

        mesh.nodes.push_back(node);
    }
}

void GeometryParser::parse_solids(data::Mesh& mesh, size_t& offset) {
    // ls-dyna_database.txt lines 639-643
    // IX8(9,1): 9*NEL8 - Connectivity and material number for each 8 node solid element
    // Format: node1, node2, ..., node8, material_id (9 words per element)

    int nel8 = control_data_.NEL8;
    int num_solids = std::abs(nel8);

    if (num_solids == 0) {
        mesh.num_solids = 0;
        return;
    }

    mesh.solids.reserve(num_solids);
    mesh.solid_materials.reserve(num_solids);

    for (int i = 0; i < num_solids; ++i) {
        Element elem;
        elem.id = i + 1;  // Internal element numbering
        elem.type = ElementType::SOLID;
        elem.node_ids.resize(8);

        // Read 8 node IDs
        for (int n = 0; n < 8; ++n) {
            elem.node_ids[n] = reader_->read_int(offset++);
        }

        // Read material ID (9th word)
        int material_id = reader_->read_int(offset++);

        mesh.solids.push_back(elem);
        mesh.solid_materials.push_back(material_id);
    }

    mesh.num_solids = num_solids;

    // If NEL8 < 0, skip extra nodes for 10-node solids (ls-dyna_database.txt line 643)
    if (nel8 < 0) {
        // Extra nodes: 2*abs(NEL8) words
        offset += 2 * num_solids;
    }
}

void GeometryParser::parse_thick_shells(data::Mesh& mesh, size_t& offset) {
    // ls-dyna_database.txt lines 644-645
    // IXT(9,1): 9*NELT - Connectivity and material number for each 8 node thick shell element

    int nelt = control_data_.NELT;

    if (nelt == 0) {
        mesh.num_thick_shells = 0;
        return;
    }

    mesh.thick_shells.reserve(nelt);
    mesh.thick_shell_materials.reserve(nelt);

    for (int i = 0; i < nelt; ++i) {
        Element elem;
        elem.id = i + 1;
        elem.type = ElementType::THICK_SHELL;
        elem.node_ids.resize(8);

        // Read 8 node IDs
        for (int n = 0; n < 8; ++n) {
            elem.node_ids[n] = reader_->read_int(offset++);
        }

        // Read material ID (9th word)
        int material_id = reader_->read_int(offset++);

        mesh.thick_shells.push_back(elem);
        mesh.thick_shell_materials.push_back(material_id);
    }

    mesh.num_thick_shells = nelt;
}

void GeometryParser::parse_beams(data::Mesh& mesh, size_t& offset) {
    // ls-dyna_database.txt lines 646-656
    // IX2(6,1): 6*NEL2 - Connectivity, orientation node, two null entries, and material number
    // Format: node1, node2, orientation_node, null1, null2, material_id (6 words per element)

    int nel2 = control_data_.NEL2;

    if (nel2 == 0) {
        mesh.num_beams = 0;
        return;
    }

    mesh.beams.reserve(nel2);
    mesh.beam_materials.reserve(nel2);

    for (int i = 0; i < nel2; ++i) {
        Element elem;
        elem.id = i + 1;
        elem.type = ElementType::BEAM;
        elem.node_ids.resize(2);

        // Read 2 node IDs
        elem.node_ids[0] = reader_->read_int(offset++);
        elem.node_ids[1] = reader_->read_int(offset++);

        // Skip orientation node (word 3)
        offset++;

        // Skip two null entries (words 4-5)
        offset += 2;

        // Read material ID (6th word)
        int material_id = reader_->read_int(offset++);

        mesh.beams.push_back(elem);
        mesh.beam_materials.push_back(material_id);
    }

    mesh.num_beams = nel2;
}

void GeometryParser::parse_shells(data::Mesh& mesh, size_t& offset) {
    // ls-dyna_database.txt lines 657-658
    // IX4(5,1): 5*NEL4 - Connectivity and material number for each 4 node shell element
    // Format: node1, node2, node3, node4, material_id (5 words per element)

    int nel4 = control_data_.NEL4;

    if (nel4 == 0) {
        mesh.num_shells = 0;
        return;
    }

    mesh.shells.reserve(nel4);
    mesh.shell_materials.reserve(nel4);

    for (int i = 0; i < nel4; ++i) {
        Element elem;
        elem.id = i + 1;
        elem.type = ElementType::SHELL;
        elem.node_ids.resize(4);

        // Read 4 node IDs
        for (int n = 0; n < 4; ++n) {
            elem.node_ids[n] = reader_->read_int(offset++);
        }

        // Read material ID (5th word)
        int material_id = reader_->read_int(offset++);

        mesh.shells.push_back(elem);
        mesh.shell_materials.push_back(material_id);
    }

    mesh.num_shells = nel4;
}

void GeometryParser::parse_narbs(data::Mesh& mesh, size_t& offset) {
    // ls-dyna_database.txt lines 656-674
    // NARBS section contains arbitrary node and element numbering

    if (control_data_.NARBS == 0) {
        // No arbitrary numbering - use sequential IDs
        return;
    }

    // Use NARBSParser to parse the section
    NARBSParser narbs_parser(reader_, control_data_);
    narbs_parser.parse(offset);

    // Copy parsed IDs into mesh structure
    int numnp = control_data_.NUMNP;
    if (numnp > 0) {
        mesh.real_node_ids.resize(numnp);
        for (int i = 0; i < numnp; ++i) {
            mesh.real_node_ids[i] = narbs_parser.get_real_node_id(i);
            // Also update the node ID in the nodes vector
            if (i < static_cast<int>(mesh.nodes.size())) {
                mesh.nodes[i].id = mesh.real_node_ids[i];
            }
        }
    }

    int num_solids = std::abs(control_data_.NEL8);
    if (num_solids > 0) {
        mesh.real_solid_ids.resize(num_solids);
        for (int i = 0; i < num_solids; ++i) {
            mesh.real_solid_ids[i] = narbs_parser.get_real_element_id(ElementType::SOLID, i);
            // Update element ID
            if (i < static_cast<int>(mesh.solids.size())) {
                mesh.solids[i].id = mesh.real_solid_ids[i];
            }
        }

        // Populate solid_parts from material indices using Part ID mapping
        if (!mesh.solid_materials.empty()) {
            mesh.solid_parts.resize(num_solids);
            for (int i = 0; i < num_solids; ++i) {
                int32_t mat_index = mesh.solid_materials[i];
                mesh.solid_parts[i] = narbs_parser.get_real_part_id(mat_index);
            }
        }
    }

    int num_beams = control_data_.NEL2;
    if (num_beams > 0) {
        mesh.real_beam_ids.resize(num_beams);
        for (int i = 0; i < num_beams; ++i) {
            mesh.real_beam_ids[i] = narbs_parser.get_real_element_id(ElementType::BEAM, i);
            if (i < static_cast<int>(mesh.beams.size())) {
                mesh.beams[i].id = mesh.real_beam_ids[i];
            }
        }
    }

    int num_shells = control_data_.NEL4;
    if (num_shells > 0) {
        mesh.real_shell_ids.resize(num_shells);
        for (int i = 0; i < num_shells; ++i) {
            mesh.real_shell_ids[i] = narbs_parser.get_real_element_id(ElementType::SHELL, i);
            if (i < static_cast<int>(mesh.shells.size())) {
                mesh.shells[i].id = mesh.real_shell_ids[i];
            }
        }
    }

    int num_thick_shells = control_data_.NELT;
    if (num_thick_shells > 0) {
        mesh.real_thick_shell_ids.resize(num_thick_shells);
        for (int i = 0; i < num_thick_shells; ++i) {
            mesh.real_thick_shell_ids[i] = narbs_parser.get_real_element_id(ElementType::THICK_SHELL, i);
            if (i < static_cast<int>(mesh.thick_shells.size())) {
                mesh.thick_shells[i].id = mesh.real_thick_shell_ids[i];
            }
        }
    }

    // Copy material types
    mesh.material_types = narbs_parser.get_material_types();
}

} // namespace parsers
} // namespace kood3plot
