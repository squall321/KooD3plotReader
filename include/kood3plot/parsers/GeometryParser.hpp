#pragma once

#include "kood3plot/Types.hpp"
#include "kood3plot/data/ControlData.hpp"
#include "kood3plot/data/Mesh.hpp"
#include "kood3plot/core/BinaryReader.hpp"
#include <memory>

namespace kood3plot {
namespace parsers {

/**
 * @brief Parser for geometry data section
 */
class GeometryParser {
public:
    /**
     * @brief Constructor
     * @param reader Binary file reader
     * @param control_data Control data structure
     */
    GeometryParser(std::shared_ptr<core::BinaryReader> reader,
                   const data::ControlData& control_data);

    /**
     * @brief Parse geometry data from file
     * @return Parsed mesh structure
     */
    data::Mesh parse();

private:
    std::shared_ptr<core::BinaryReader> reader_;
    const data::ControlData& control_data_;

    /**
     * @brief Parse node coordinates
     */
    void parse_nodes(data::Mesh& mesh, size_t& offset);

    /**
     * @brief Parse solid element connectivity
     */
    void parse_solids(data::Mesh& mesh, size_t& offset);

    /**
     * @brief Parse thick shell element connectivity
     */
    void parse_thick_shells(data::Mesh& mesh, size_t& offset);

    /**
     * @brief Parse beam element connectivity
     */
    void parse_beams(data::Mesh& mesh, size_t& offset);

    /**
     * @brief Parse shell element connectivity
     */
    void parse_shells(data::Mesh& mesh, size_t& offset);

    /**
     * @brief Parse NARBS (arbitrary numbering) section
     */
    void parse_narbs(data::Mesh& mesh, size_t& offset);
};

} // namespace parsers
} // namespace kood3plot
