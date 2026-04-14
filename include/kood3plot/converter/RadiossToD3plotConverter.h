/**
 * @file RadiossToD3plotConverter.h
 * @brief Direct OpenRadioss animation (A00/A01) → LS-DYNA d3plot converter
 *
 * Bypasses VTK intermediate format for better performance.
 * Maps RadiossReader output directly to D3plotWriter input.
 */

#pragma once

#include "kood3plot/converter/RadiossReader.h"
#include "kood3plot/data/ControlData.hpp"
#include "kood3plot/data/Mesh.hpp"
#include "kood3plot/data/StateData.hpp"
#include "kood3plot/writer/D3plotWriter.h"
#include <string>
#include <vector>
#include <functional>

namespace kood3plot {
namespace converter {

/**
 * @brief Conversion options for Radioss → D3plot
 */
struct RadiossConversionOptions {
    std::string title = "Radioss Converted";
    Precision precision = Precision::SINGLE;
    Endian endian = Endian::LITTLE;
    size_t max_file_size = 2ULL * 1024 * 1024 * 1024;  // 2GB
    bool verbose = false;
    size_t max_states = 0;  // 0 = all
};

/**
 * @brief Conversion result
 */
struct RadiossConversionResult {
    bool success = false;
    std::string error_message;

    size_t num_nodes = 0;
    size_t num_solids = 0;
    size_t num_shells = 0;
    size_t num_beams = 0;
    size_t num_states = 0;
    size_t bytes_written = 0;
    std::vector<std::string> output_files;
};

using RadiossConversionCallback = std::function<void(const std::string&)>;

/**
 * @brief Direct Radioss → D3plot converter (no VTK intermediate)
 *
 * Usage:
 * @code
 * RadiossToD3plotConverter converter;
 * RadiossConversionOptions opts;
 * opts.title = "My Simulation";
 * auto result = converter.convert("simA000", "output.d3plot", opts);
 * @endcode
 */
class RadiossToD3plotConverter {
public:
    RadiossToD3plotConverter() = default;
    ~RadiossToD3plotConverter() = default;

    /**
     * @brief Convert Radioss A00 + state files → d3plot
     * @param a00_path Path to Radioss A00 file
     * @param d3plot_path Output d3plot path
     * @param options Conversion options
     * @param callback Progress callback
     * @return Conversion result
     */
    RadiossConversionResult convert(
        const std::string& a00_path,
        const std::string& d3plot_path,
        const RadiossConversionOptions& options = {},
        RadiossConversionCallback callback = nullptr);

private:
    /**
     * @brief Map RadiossMesh → d3plot Mesh + ControlData
     */
    void mapMesh(const RadiossMesh& src, const RadiossHeader& header,
                 data::Mesh& dst_mesh, data::ControlData& dst_control,
                 const RadiossConversionOptions& options);

    /**
     * @brief Map RadiossState → d3plot StateData
     *
     * @param dst_mesh Destination mesh (used to convert displacement deltas
     *                 back into absolute current coordinates — required by the
     *                 LS-DYNA d3plot spec, which stores current coordinates in
     *                 the IU=1 field, not deltas).
     */
    data::StateData mapState(const RadiossState& src,
                             const RadiossHeader& header,
                             const data::ControlData& control,
                             const data::Mesh& dst_mesh);
};

} // namespace converter
} // namespace kood3plot
