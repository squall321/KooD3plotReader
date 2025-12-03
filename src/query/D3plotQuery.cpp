/**
 * @file D3plotQuery.cpp
 * @brief Implementation of D3plotQuery class
 * @author KooD3plot V3 Development Team
 * @date 2025-11-21
 * @version 3.0.0
 */

#include "kood3plot/query/D3plotQuery.h"
#include "kood3plot/query/QueryResult.h"
#include "kood3plot/D3plotReader.hpp"
#include "writers/JSONWriter.h"
#include <sstream>
#include <stdexcept>
#include <cmath>
#include <fstream>
#include <iomanip>
#include <map>
#include <set>

namespace kood3plot {
namespace query {

// ============================================================
// Physical Quantity Calculation Helpers
// ============================================================

namespace {

/**
 * @brief Calculate Von Mises stress from 6 stress components
 *
 * Formula: σ_vm = sqrt(0.5 * ((σx-σy)² + (σy-σz)² + (σz-σx)²) + 3*(τxy² + τyz² + τzx²))
 *
 * @param sx X-stress (σx)
 * @param sy Y-stress (σy)
 * @param sz Z-stress (σz)
 * @param txy XY-shear (τxy)
 * @param tyz YZ-shear (τyz)
 * @param tzx ZX-shear (τzx)
 * @return Von Mises stress value
 */
double calculateVonMises(double sx, double sy, double sz,
                        double txy, double tyz, double tzx) {
    double d1 = sx - sy;
    double d2 = sy - sz;
    double d3 = sz - sx;
    return std::sqrt(0.5 * (d1*d1 + d2*d2 + d3*d3) + 3.0 * (txy*txy + tyz*tyz + tzx*tzx));
}

/**
 * @brief Calculate hydrostatic pressure from stress components
 *
 * Formula: p = -(σx + σy + σz) / 3
 */
double calculatePressure(double sx, double sy, double sz) {
    return -(sx + sy + sz) / 3.0;
}

/**
 * @brief Calculate displacement magnitude from components
 */
double calculateMagnitude(double x, double y, double z) {
    return std::sqrt(x*x + y*y + z*z);
}

/**
 * @brief Get part ID for an element index from mesh
 */
int32_t getPartIdForElement(const data::Mesh& mesh, size_t solid_idx, size_t shell_idx,
                           bool is_solid) {
    if (is_solid && solid_idx < mesh.solid_parts.size()) {
        return mesh.solid_parts[solid_idx];
    } else if (!is_solid && shell_idx < mesh.shell_parts.size()) {
        return mesh.shell_parts[shell_idx];
    }
    return -1;
}

/**
 * @brief Get real element ID from mesh
 */
int32_t getRealElementId(const data::Mesh& mesh, size_t solid_idx, size_t shell_idx,
                        bool is_solid) {
    if (is_solid) {
        if (solid_idx < mesh.real_solid_ids.size()) {
            return mesh.real_solid_ids[solid_idx];
        } else if (solid_idx < mesh.solids.size()) {
            return mesh.solids[solid_idx].id;
        }
    } else {
        if (shell_idx < mesh.real_shell_ids.size()) {
            return mesh.real_shell_ids[shell_idx];
        } else if (shell_idx < mesh.shells.size()) {
            return mesh.shells[shell_idx].id;
        }
    }
    return static_cast<int32_t>(is_solid ? solid_idx : shell_idx) + 1;
}

} // anonymous namespace

// ============================================================
// PIMPL Implementation Struct
// ============================================================

/**
 * @brief Implementation details for D3plotQuery
 */
struct D3plotQuery::Impl {
    /// Reference to D3plot reader
    const D3plotReader& reader;

    /// Part selector
    PartSelector part_selector;

    /// Quantity selector
    QuantitySelector quantity_selector;

    /// Time selector
    TimeSelector time_selector;

    /// Value filter
    ValueFilter value_filter;

    /// Output specification
    OutputSpec output_spec;

    /**
     * @brief Constructor
     */
    explicit Impl(const D3plotReader& r)
        : reader(r)
    {
        // Set default: all parts, common quantities, last state
        part_selector = PartSelector::all();
        quantity_selector = QuantitySelector::commonCrash();
        time_selector = TimeSelector::lastState();
        output_spec = OutputSpec::csv();
    }
};

// ============================================================
// Constructors and Destructor
// ============================================================

D3plotQuery::D3plotQuery(const D3plotReader& reader)
    : pImpl(std::make_unique<Impl>(reader))
{
}

D3plotQuery::D3plotQuery(const D3plotQuery& other)
    : pImpl(std::make_unique<Impl>(*other.pImpl))
{
}

D3plotQuery::D3plotQuery(D3plotQuery&& other) noexcept
    : pImpl(std::move(other.pImpl))
{
}

D3plotQuery& D3plotQuery::operator=(const D3plotQuery& other) {
    if (this != &other) {
        pImpl = std::make_unique<Impl>(*other.pImpl);
    }
    return *this;
}

D3plotQuery& D3plotQuery::operator=(D3plotQuery&& other) noexcept {
    if (this != &other) {
        pImpl = std::move(other.pImpl);
    }
    return *this;
}

D3plotQuery::~D3plotQuery() = default;

// ============================================================
// Selection Methods
// ============================================================

D3plotQuery& D3plotQuery::selectParts(const PartSelector& selector) {
    pImpl->part_selector = selector;
    return *this;
}

D3plotQuery& D3plotQuery::selectParts(const std::vector<int32_t>& part_ids) {
    pImpl->part_selector = PartSelector().byId(part_ids);
    return *this;
}

D3plotQuery& D3plotQuery::selectParts(const std::vector<std::string>& part_names) {
    pImpl->part_selector = PartSelector().byName(part_names);
    return *this;
}

D3plotQuery& D3plotQuery::selectAllParts() {
    pImpl->part_selector = PartSelector::all();
    return *this;
}

D3plotQuery& D3plotQuery::selectQuantities(const QuantitySelector& selector) {
    pImpl->quantity_selector = selector;
    return *this;
}

D3plotQuery& D3plotQuery::selectQuantities(const std::vector<std::string>& quantity_names) {
    pImpl->quantity_selector = QuantitySelector().add(quantity_names);
    return *this;
}

D3plotQuery& D3plotQuery::selectTime(const TimeSelector& selector) {
    pImpl->time_selector = selector;
    return *this;
}

D3plotQuery& D3plotQuery::selectTime(const std::vector<int>& state_indices) {
    pImpl->time_selector = TimeSelector().addSteps(state_indices);
    return *this;
}

// ============================================================
// Filtering Methods
// ============================================================

D3plotQuery& D3plotQuery::whereValue(const ValueFilter& filter) {
    pImpl->value_filter = filter;
    return *this;
}

D3plotQuery& D3plotQuery::whereGreaterThan(double threshold) {
    pImpl->value_filter = ValueFilter().greaterThan(threshold);
    return *this;
}

D3plotQuery& D3plotQuery::whereInRange(double min, double max) {
    pImpl->value_filter = ValueFilter().inRange(min, max);
    return *this;
}

// ============================================================
// Output Specification
// ============================================================

D3plotQuery& D3plotQuery::output(const OutputSpec& spec) {
    pImpl->output_spec = spec;
    return *this;
}

D3plotQuery& D3plotQuery::outputFormat(OutputFormat format) {
    pImpl->output_spec.format(format);
    return *this;
}

// ============================================================
// Execution Methods
// ============================================================

void D3plotQuery::writeCSV(const std::string& filename) {
    pImpl->output_spec.format(OutputFormat::CSV);
    writeToFile(filename, OutputFormat::CSV);
}

void D3plotQuery::writeJSON(const std::string& filename) {
    pImpl->output_spec.format(OutputFormat::JSON);
    writeToFile(filename, OutputFormat::JSON);
}

void D3plotQuery::writeHDF5(const std::string& filename) {
    pImpl->output_spec.format(OutputFormat::HDF5);
    writeToFile(filename, OutputFormat::HDF5);
}

void D3plotQuery::write(const std::string& filename) {
    writeToFile(filename, pImpl->output_spec.getFormat());
}

// ============================================================
// Query Introspection
// ============================================================

std::string D3plotQuery::getDescription() const {
    std::ostringstream oss;

    oss << "D3plot Query:\n";
    oss << "  Reader: " << "d3plot file\n";  // TODO: Get actual filename from reader
    oss << "  Parts: " << pImpl->part_selector.getDescription() << "\n";
    oss << "  Quantities: " << pImpl->quantity_selector.getDescription() << "\n";
    oss << "  Time: " << pImpl->time_selector.getDescription() << "\n";

    if (!pImpl->value_filter.isEmpty()) {
        oss << "  Filter: " << pImpl->value_filter.getDescription() << "\n";
    }

    oss << "  Output: " << pImpl->output_spec.getDescription();

    return oss.str();
}

size_t D3plotQuery::estimateSize() const {
    // Estimate number of data points
    // Formula: num_parts * num_elements_per_part * num_quantities * num_timesteps

    // Get selected parts
    auto part_ids = pImpl->part_selector.evaluate(pImpl->reader);
    size_t num_parts = part_ids.size();

    // Estimate elements (rough average: 100 elements per part)
    // TODO: Get actual element count from reader
    size_t num_elements = num_parts * 100;

    // Get selected quantities
    auto quantities = pImpl->quantity_selector.getQuantities();
    size_t num_quantities = quantities.size();

    // Get selected timesteps
    auto states = pImpl->time_selector.evaluate(pImpl->reader);
    size_t num_states = states.size();

    // Total data points
    size_t total = num_elements * num_quantities * num_states;

    return total;
}

bool D3plotQuery::validate() const {
    return getValidationErrors().empty();
}

std::vector<std::string> D3plotQuery::getValidationErrors() const {
    std::vector<std::string> errors;

    // Check if quantities are selected
    if (pImpl->quantity_selector.isEmpty()) {
        errors.push_back("No quantities selected");
    }

    // Check if parts are selected
    auto part_ids = pImpl->part_selector.evaluate(pImpl->reader);
    if (part_ids.empty()) {
        errors.push_back("No parts match selection criteria");
    }

    // Check if timesteps are selected
    auto states = pImpl->time_selector.evaluate(pImpl->reader);
    if (states.empty()) {
        errors.push_back("No timesteps match selection criteria");
    }

    // Validate output spec
    auto output_errors = pImpl->output_spec.getValidationErrors();
    errors.insert(errors.end(), output_errors.begin(), output_errors.end());

    return errors;
}

// ============================================================
// Static Factory Methods
// ============================================================

D3plotQuery D3plotQuery::maxVonMises(const D3plotReader& reader,
                                     const std::vector<int32_t>& part_ids) {
    D3plotQuery query(reader);

    if (part_ids.empty()) {
        query.selectAllParts();
    } else {
        query.selectParts(part_ids);
    }

    query.selectQuantities(QuantitySelector::vonMises())
         .selectTime(TimeSelector::allStates())
         .output(OutputSpec::csv()
                 .aggregation(AggregationType::MAX)
                 .fields({"part_id", "element_id", "max_von_mises"}));

    return query;
}

D3plotQuery D3plotQuery::maxEffectiveStrain(const D3plotReader& reader,
                                            const std::vector<int32_t>& part_ids) {
    D3plotQuery query(reader);

    if (part_ids.empty()) {
        query.selectAllParts();
    } else {
        query.selectParts(part_ids);
    }

    query.selectQuantities(QuantitySelector::effectiveStrain())
         .selectTime(TimeSelector::allStates())
         .output(OutputSpec::csv()
                 .aggregation(AggregationType::MAX)
                 .fields({"part_id", "element_id", "max_effective_strain"}));

    return query;
}

D3plotQuery D3plotQuery::finalState(const D3plotReader& reader) {
    D3plotQuery query(reader);

    query.selectAllParts()
         .selectQuantities(QuantitySelector::commonCrash())
         .selectTime(TimeSelector::lastState())
         .output(OutputSpec::csv()
                 .fields({"part_id", "element_id", "von_mises", "effective_strain", "displacement"}));

    return query;
}

D3plotQuery D3plotQuery::timeHistory(const D3plotReader& reader,
                                     int32_t part_id,
                                     int32_t element_id) {
    D3plotQuery query(reader);

    query.selectParts(std::vector<int32_t>{part_id})
         .selectQuantities(QuantitySelector::commonCrash())
         .selectTime(TimeSelector::allStates())
         .output(OutputSpec::csv()
                 .fields({"time", "von_mises", "effective_strain", "displacement"})
                 .addMetadata("part_id", std::to_string(part_id))
                 .addMetadata("element_id", std::to_string(element_id)));

    return query;
}

// ============================================================
// Private Helper Methods
// ============================================================

void D3plotQuery::executeQuery() {
    // Implementation is now in writeToFile for direct output
}

QueryResult D3plotQuery::execute() {
    QueryResult result;

    // Get mutable reader reference (required for read operations)
    auto& mutable_reader = const_cast<D3plotReader&>(pImpl->reader);

    // 1. Get mesh and part information
    auto mesh = mutable_reader.read_mesh();
    auto control = mutable_reader.get_control_data();

    // 2. Evaluate selectors
    auto selected_parts = pImpl->part_selector.evaluate(pImpl->reader);
    auto selected_states = pImpl->time_selector.evaluate(pImpl->reader);
    auto selected_quantities = pImpl->quantity_selector.getQuantities();
    auto time_values = mutable_reader.get_time_values();

    // Convert selected parts to set for faster lookup
    std::set<int32_t> part_set(selected_parts.begin(), selected_parts.end());

    // Reserve estimated capacity
    size_t estimated_size = mesh.num_solids + mesh.num_shells;
    estimated_size *= selected_states.size();
    result.reserve(estimated_size);

    // 3. Process each selected state
    for (int state_idx : selected_states) {
        if (state_idx < 0 || static_cast<size_t>(state_idx) >= time_values.size()) {
            continue;
        }

        auto state_data = mutable_reader.read_state(static_cast<size_t>(state_idx));
        double current_time = state_data.time;

        // Process solid elements
        size_t nv3d = static_cast<size_t>(control.NV3D);
        if (nv3d > 0 && !state_data.solid_data.empty()) {
            size_t num_solids = state_data.solid_data.size() / nv3d;

            for (size_t i = 0; i < num_solids; ++i) {
                int32_t part_id = getPartIdForElement(mesh, i, 0, true);

                // Skip if part not selected
                if (!part_set.empty() && part_set.find(part_id) == part_set.end()) {
                    continue;
                }

                int32_t elem_id = getRealElementId(mesh, i, 0, true);
                size_t base_offset = i * nv3d;

                ResultDataPoint point;
                point.element_id = elem_id;
                point.part_id = part_id;
                point.state_index = state_idx;
                point.time = current_time;

                // Extract stress components (standard LS-DYNA layout: sx, sy, sz, txy, tyz, tzx, eps)
                if (nv3d >= 7) {
                    double sx = state_data.solid_data[base_offset + 0];
                    double sy = state_data.solid_data[base_offset + 1];
                    double sz = state_data.solid_data[base_offset + 2];
                    double txy = state_data.solid_data[base_offset + 3];
                    double tyz = state_data.solid_data[base_offset + 4];
                    double tzx = state_data.solid_data[base_offset + 5];
                    double eps = state_data.solid_data[base_offset + 6];  // Effective plastic strain

                    // Calculate and store requested quantities
                    for (auto qty : selected_quantities) {
                        switch (qty) {
                            case QuantityType::STRESS_X:
                                point.values["x_stress"] = sx;
                                break;
                            case QuantityType::STRESS_Y:
                                point.values["y_stress"] = sy;
                                break;
                            case QuantityType::STRESS_Z:
                                point.values["z_stress"] = sz;
                                break;
                            case QuantityType::STRESS_XY:
                                point.values["xy_stress"] = txy;
                                break;
                            case QuantityType::STRESS_YZ:
                                point.values["yz_stress"] = tyz;
                                break;
                            case QuantityType::STRESS_ZX:
                                point.values["zx_stress"] = tzx;
                                break;
                            case QuantityType::STRESS_VON_MISES:
                                point.values["von_mises"] = calculateVonMises(sx, sy, sz, txy, tyz, tzx);
                                break;
                            case QuantityType::STRESS_PRESSURE:
                                point.values["pressure"] = calculatePressure(sx, sy, sz);
                                break;
                            case QuantityType::STRAIN_EFFECTIVE_PLASTIC:
                                point.values["plastic_strain"] = eps;
                                break;
                            default:
                                break;
                        }
                    }
                }

                // Add point if it has values and passes filter
                if (!point.values.empty()) {
                    if (pImpl->value_filter.isEmpty() || pImpl->value_filter.evaluate(point.values)) {
                        result.addDataPoint(std::move(point));
                    }
                }
            }
        }

        // Process shell elements
        size_t nv2d = static_cast<size_t>(control.NV2D);
        if (nv2d > 0 && !state_data.shell_data.empty()) {
            size_t num_shells = state_data.shell_data.size() / nv2d;

            for (size_t i = 0; i < num_shells; ++i) {
                int32_t part_id = getPartIdForElement(mesh, 0, i, false);

                // Skip if part not selected
                if (!part_set.empty() && part_set.find(part_id) == part_set.end()) {
                    continue;
                }

                int32_t elem_id = getRealElementId(mesh, 0, i, false);
                size_t base_offset = i * nv2d;

                ResultDataPoint point;
                point.element_id = elem_id;
                point.part_id = part_id;
                point.state_index = state_idx;
                point.time = current_time;

                // Shell data layout varies, but typically includes stress at integration points
                if (nv2d >= 7) {
                    double sx = state_data.shell_data[base_offset + 0];
                    double sy = state_data.shell_data[base_offset + 1];
                    double sz = state_data.shell_data[base_offset + 2];
                    double txy = state_data.shell_data[base_offset + 3];
                    double tyz = state_data.shell_data[base_offset + 4];
                    double tzx = state_data.shell_data[base_offset + 5];
                    double eps = state_data.shell_data[base_offset + 6];

                    for (auto qty : selected_quantities) {
                        switch (qty) {
                            case QuantityType::STRESS_X:
                                point.values["x_stress"] = sx;
                                break;
                            case QuantityType::STRESS_Y:
                                point.values["y_stress"] = sy;
                                break;
                            case QuantityType::STRESS_Z:
                                point.values["z_stress"] = sz;
                                break;
                            case QuantityType::STRESS_XY:
                                point.values["xy_stress"] = txy;
                                break;
                            case QuantityType::STRESS_YZ:
                                point.values["yz_stress"] = tyz;
                                break;
                            case QuantityType::STRESS_ZX:
                                point.values["zx_stress"] = tzx;
                                break;
                            case QuantityType::STRESS_VON_MISES:
                                point.values["von_mises"] = calculateVonMises(sx, sy, sz, txy, tyz, tzx);
                                break;
                            case QuantityType::STRESS_PRESSURE:
                                point.values["pressure"] = calculatePressure(sx, sy, sz);
                                break;
                            case QuantityType::STRAIN_EFFECTIVE_PLASTIC:
                                point.values["plastic_strain"] = eps;
                                break;
                            default:
                                break;
                        }
                    }
                }

                if (!point.values.empty()) {
                    if (pImpl->value_filter.isEmpty() || pImpl->value_filter.evaluate(point.values)) {
                        result.addDataPoint(std::move(point));
                    }
                }
            }
        }

        // Process nodal displacements if requested
        bool need_displacement = false;
        for (auto qty : selected_quantities) {
            if (qty == QuantityType::DISPLACEMENT_X ||
                qty == QuantityType::DISPLACEMENT_Y ||
                qty == QuantityType::DISPLACEMENT_Z ||
                qty == QuantityType::DISPLACEMENT_MAGNITUDE) {
                need_displacement = true;
                break;
            }
        }

        if (need_displacement && !state_data.node_displacements.empty()) {
            size_t num_nodes = state_data.node_displacements.size() / 3;
            for (size_t n = 0; n < num_nodes; ++n) {
                double ux = state_data.node_displacements[n * 3 + 0];
                double uy = state_data.node_displacements[n * 3 + 1];
                double uz = state_data.node_displacements[n * 3 + 2];

                // For node data, element_id represents node_id
                int32_t node_id = (n < mesh.real_node_ids.size()) ?
                                  mesh.real_node_ids[n] : static_cast<int32_t>(n + 1);

                ResultDataPoint point;
                point.element_id = node_id;
                point.part_id = 0;  // Nodes don't have part IDs
                point.state_index = state_idx;
                point.time = current_time;

                for (auto qty : selected_quantities) {
                    switch (qty) {
                        case QuantityType::DISPLACEMENT_X:
                            point.values["x_displacement"] = ux;
                            break;
                        case QuantityType::DISPLACEMENT_Y:
                            point.values["y_displacement"] = uy;
                            break;
                        case QuantityType::DISPLACEMENT_Z:
                            point.values["z_displacement"] = uz;
                            break;
                        case QuantityType::DISPLACEMENT_MAGNITUDE:
                            point.values["displacement"] = calculateMagnitude(ux, uy, uz);
                            break;
                        default:
                            break;
                    }
                }

                if (!point.values.empty()) {
                    result.addDataPoint(std::move(point));
                }
            }
        }
    }

    result.setQueryDescription(getDescription());
    return result;
}

void D3plotQuery::writeToFile(const std::string& filename, OutputFormat format) {
    // Validate query first
    if (!validate()) {
        std::ostringstream oss;
        oss << "Query validation failed:\n";
        for (const auto& error : getValidationErrors()) {
            oss << "  - " << error << "\n";
        }
        throw std::runtime_error(oss.str());
    }

    switch (format) {
        case OutputFormat::CSV: {
            // Execute query and write CSV
            auto result = execute();

            std::ofstream file(filename);
            if (!file.is_open()) {
                throw std::runtime_error("Failed to open file: " + filename);
            }

            // Write header
            auto qty_names = result.getQuantityNames();
            file << "element_id,part_id,state,time";
            for (const auto& name : qty_names) {
                file << "," << name;
            }
            file << "\n";

            // Write data rows
            file << std::fixed << std::setprecision(6);
            for (const auto& point : result) {
                file << point.element_id << ","
                     << point.part_id << ","
                     << point.state_index << ","
                     << point.time;

                for (const auto& name : qty_names) {
                    file << ",";
                    auto it = point.values.find(name);
                    if (it != point.values.end()) {
                        file << it->second;
                    }
                }
                file << "\n";
            }

            file.close();
            break;
        }

        case OutputFormat::JSON: {
            // Execute query and write JSON
            auto result = execute();

            writers::JSONWriter writer(filename);
            writer.setSpec(pImpl->output_spec);
            writer.write(result);
            writer.close();
            break;
        }

        case OutputFormat::HDF5:
            throw std::runtime_error("HDF5 writer not yet implemented");

        case OutputFormat::PARQUET:
            throw std::runtime_error("Parquet writer not yet implemented (Phase 4)");

        default:
            throw std::runtime_error("Unsupported output format");
    }
}

} // namespace query
} // namespace kood3plot
