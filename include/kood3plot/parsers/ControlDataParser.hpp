#pragma once

#include "kood3plot/Types.hpp"
#include "kood3plot/data/ControlData.hpp"
#include "kood3plot/core/BinaryReader.hpp"
#include <memory>

namespace kood3plot {
namespace parsers {

/**
 * @brief Parser for control data section
 */
class ControlDataParser {
public:
    /**
     * @brief Constructor
     * @param reader Binary file reader
     */
    explicit ControlDataParser(std::shared_ptr<core::BinaryReader> reader);

    /**
     * @brief Parse control data from file
     * @return Parsed control data structure
     */
    data::ControlData parse();

private:
    std::shared_ptr<core::BinaryReader> reader_;

    /**
     * @brief Compute IOSOL flags from raw IOSHL values
     */
    void compute_IOSOL(data::ControlData& cd, const int ioshl_raw[4]);

    /**
     * @brief Compute IOSHL flags from raw values
     */
    void compute_IOSHL(data::ControlData& cd, const int ioshl_raw[4]);
};

} // namespace parsers
} // namespace kood3plot
