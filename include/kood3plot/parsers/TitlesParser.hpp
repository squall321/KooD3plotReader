#pragma once

#include "kood3plot/Types.hpp"
#include "kood3plot/data/ControlData.hpp"
#include "kood3plot/core/BinaryReader.hpp"
#include <memory>
#include <string>

namespace kood3plot {
namespace parsers {

/**
 * @brief Parser for titles section
 */
class TitlesParser {
public:
    /**
     * @brief Constructor
     * @param reader Binary file reader
     * @param control_data Control data structure
     */
    TitlesParser(std::shared_ptr<core::BinaryReader> reader,
                 const data::ControlData& control_data);

    /**
     * @brief Parse title string from file
     * @return Title string (80 characters)
     */
    std::string parse();

private:
    std::shared_ptr<core::BinaryReader> reader_;
    const data::ControlData& control_data_;

    /**
     * @brief Find EOF marker (-999999.0) and titles offset
     */
    size_t find_titles_offset();
};

} // namespace parsers
} // namespace kood3plot
