#include "kood3plot/parsers/TitlesParser.hpp"

namespace kood3plot {
namespace parsers {

TitlesParser::TitlesParser(std::shared_ptr<core::BinaryReader> reader,
                           const data::ControlData& control_data)
    : reader_(reader)
    , control_data_(control_data) {
}

std::string TitlesParser::parse() {
    // TODO: Implement title parsing in Phase 3
    return "Untitled";
}

size_t TitlesParser::find_titles_offset() {
    // TODO: Implement EOF marker search in Phase 3
    // EOF marker is -999999.0 (floating point) before titles section
    return 0;
}

} // namespace parsers
} // namespace kood3plot
