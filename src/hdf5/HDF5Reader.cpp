#include <kood3plot/hdf5/HDF5Reader.hpp>

#include <H5Cpp.h>

#include <iostream>
#include <stdexcept>
#include <cmath>
#include <algorithm>
#include <filesystem>

namespace fs = std::filesystem;

namespace kood3plot {
namespace hdf5 {

// Constructor
HDF5Reader::HDF5Reader(const std::string& filename)
    : file_(nullptr)
    , mesh_group_(nullptr)
    , states_group_(nullptr)
    , is_open_(false)
    , filename_(filename)
{
    try {
        H5::Exception::dontPrint();

        // Open existing file (read-only)
        file_ = std::make_unique<H5::H5File>(filename, H5F_ACC_RDONLY);
        is_open_ = true;

        // Open groups
        open_groups();

        // Read file info
        read_file_info();

    } catch (const H5::FileIException& e) {
        throw std::runtime_error("Failed to open HDF5 file: " + filename + " - " + e.getDetailMsg());
    } catch (const H5::Exception& e) {
        throw std::runtime_error("HDF5 error: " + e.getDetailMsg());
    }
}

// Destructor
HDF5Reader::~HDF5Reader() {
    close();
}

// Open groups
void HDF5Reader::open_groups() {
    try {
        mesh_group_ = std::make_unique<H5::Group>(file_->openGroup("/mesh"));

        // States group may not exist yet (Week 1 only has mesh)
        try {
            states_group_ = std::make_unique<H5::Group>(file_->openGroup("/states"));
            // Load compression metadata for state reading
            load_compression_metadata();
        } catch (...) {
            // States group doesn't exist yet
        }
    } catch (const H5::Exception& e) {
        throw std::runtime_error("Failed to open HDF5 groups: " + e.getDetailMsg());
    }
}

// Read file info
void HDF5Reader::read_file_info() {
    try {
        // Read format version
        if (file_->attrExists("format")) {
            H5::Attribute attr = file_->openAttribute("format");
            H5::StrType str_type = attr.getStrType();
            attr.read(str_type, file_info_.format_version);
        }

        // Read mesh metadata
        if (mesh_group_->attrExists("num_nodes")) {
            H5::Attribute attr = mesh_group_->openAttribute("num_nodes");
            attr.read(H5::PredType::NATIVE_INT, &file_info_.num_nodes);
        }

        if (mesh_group_->attrExists("num_solids")) {
            H5::Attribute attr = mesh_group_->openAttribute("num_solids");
            attr.read(H5::PredType::NATIVE_INT, &file_info_.num_solids);
        }

        if (mesh_group_->attrExists("num_shells")) {
            H5::Attribute attr = mesh_group_->openAttribute("num_shells");
            attr.read(H5::PredType::NATIVE_INT, &file_info_.num_shells);
        }

        if (mesh_group_->attrExists("num_beams")) {
            H5::Attribute attr = mesh_group_->openAttribute("num_beams");
            attr.read(H5::PredType::NATIVE_INT, &file_info_.num_beams);
        }

        // Calculate file size
        file_info_.file_size_bytes = fs::file_size(filename_);

        // Estimate uncompressed size
        file_info_.uncompressed_estimate =
            static_cast<size_t>(file_info_.num_nodes) * 3 * sizeof(double) +
            static_cast<size_t>(file_info_.num_solids) * 8 * sizeof(int) +
            static_cast<size_t>(file_info_.num_solids) * sizeof(int) +
            static_cast<size_t>(file_info_.num_shells) * 4 * sizeof(int) +
            static_cast<size_t>(file_info_.num_shells) * sizeof(int) +
            static_cast<size_t>(file_info_.num_beams) * 2 * sizeof(int) +
            static_cast<size_t>(file_info_.num_beams) * sizeof(int);

        // Calculate compression ratio
        if (file_info_.uncompressed_estimate > 0) {
            file_info_.compression_ratio = 100.0 *
                static_cast<double>(file_info_.file_size_bytes) /
                static_cast<double>(file_info_.uncompressed_estimate);
        }

    } catch (const H5::Exception& e) {
        // Non-fatal, just log
        std::cerr << "Warning: Could not read all file info: " << e.getDetailMsg() << "\n";
    }
}

// Get file info
HDF5FileInfo HDF5Reader::get_file_info() const {
    return file_info_;
}

// Read nodes
std::vector<data::Node> HDF5Reader::read_nodes() {
    std::vector<data::Node> nodes;

    if (!is_open_ || !mesh_group_) {
        throw std::runtime_error("HDF5 file is not open");
    }

    try {
        // Check if nodes dataset exists
        if (!H5Lexists(mesh_group_->getId(), "nodes", H5P_DEFAULT)) {
            return nodes;
        }

        H5::DataSet dataset = mesh_group_->openDataSet("nodes");
        H5::DataSpace dataspace = dataset.getSpace();

        // Get dimensions
        hsize_t dims[2];
        dataspace.getSimpleExtentDims(dims);

        size_t num_nodes = dims[0];
        nodes.resize(num_nodes);

        // Read data
        std::vector<double> coords(num_nodes * 3);
        dataset.read(coords.data(), H5::PredType::NATIVE_DOUBLE);

        // Convert to Node objects
        for (size_t i = 0; i < num_nodes; ++i) {
            nodes[i].x = coords[i * 3 + 0];
            nodes[i].y = coords[i * 3 + 1];
            nodes[i].z = coords[i * 3 + 2];
        }

    } catch (const H5::Exception& e) {
        throw std::runtime_error("Failed to read nodes: " + e.getDetailMsg());
    }

    return nodes;
}

// Read mesh
data::Mesh HDF5Reader::read_mesh() {
    data::Mesh mesh;

    if (!is_open_ || !mesh_group_) {
        throw std::runtime_error("HDF5 file is not open");
    }

    try {
        // Read nodes
        mesh.nodes = read_nodes();

        // Read solids
        if (H5Lexists(mesh_group_->getId(), "solid_connectivity", H5P_DEFAULT)) {
            H5::DataSet conn_dataset = mesh_group_->openDataSet("solid_connectivity");
            H5::DataSpace conn_space = conn_dataset.getSpace();

            hsize_t dims[2];
            conn_space.getSimpleExtentDims(dims);
            size_t num_solids = dims[0];

            std::vector<int> connectivity(num_solids * 8);
            conn_dataset.read(connectivity.data(), H5::PredType::NATIVE_INT);

            // Read part IDs
            std::vector<int> part_ids(num_solids, 1);
            if (H5Lexists(mesh_group_->getId(), "solid_part_ids", H5P_DEFAULT)) {
                H5::DataSet parts_dataset = mesh_group_->openDataSet("solid_part_ids");
                parts_dataset.read(part_ids.data(), H5::PredType::NATIVE_INT);
            }

            mesh.solids.resize(num_solids);
            for (size_t i = 0; i < num_solids; ++i) {
                mesh.solids[i].node_ids.resize(8);
                for (int j = 0; j < 8; ++j) {
                    mesh.solids[i].node_ids[j] = connectivity[i * 8 + j];
                }
                mesh.solids[i].material_id = part_ids[i];
            }
        }

        // Read shells
        if (H5Lexists(mesh_group_->getId(), "shell_connectivity", H5P_DEFAULT)) {
            H5::DataSet conn_dataset = mesh_group_->openDataSet("shell_connectivity");
            H5::DataSpace conn_space = conn_dataset.getSpace();

            hsize_t dims[2];
            conn_space.getSimpleExtentDims(dims);
            size_t num_shells = dims[0];

            std::vector<int> connectivity(num_shells * 4);
            conn_dataset.read(connectivity.data(), H5::PredType::NATIVE_INT);

            std::vector<int> part_ids(num_shells, 1);
            if (H5Lexists(mesh_group_->getId(), "shell_part_ids", H5P_DEFAULT)) {
                H5::DataSet parts_dataset = mesh_group_->openDataSet("shell_part_ids");
                parts_dataset.read(part_ids.data(), H5::PredType::NATIVE_INT);
            }

            mesh.shells.resize(num_shells);
            for (size_t i = 0; i < num_shells; ++i) {
                mesh.shells[i].node_ids.resize(4);
                for (int j = 0; j < 4; ++j) {
                    mesh.shells[i].node_ids[j] = connectivity[i * 4 + j];
                }
                mesh.shells[i].material_id = part_ids[i];
            }
        }

        // Read beams
        if (H5Lexists(mesh_group_->getId(), "beam_connectivity", H5P_DEFAULT)) {
            H5::DataSet conn_dataset = mesh_group_->openDataSet("beam_connectivity");
            H5::DataSpace conn_space = conn_dataset.getSpace();

            hsize_t dims[2];
            conn_space.getSimpleExtentDims(dims);
            size_t num_beams = dims[0];

            std::vector<int> connectivity(num_beams * 2);
            conn_dataset.read(connectivity.data(), H5::PredType::NATIVE_INT);

            std::vector<int> part_ids(num_beams, 1);
            if (H5Lexists(mesh_group_->getId(), "beam_part_ids", H5P_DEFAULT)) {
                H5::DataSet parts_dataset = mesh_group_->openDataSet("beam_part_ids");
                parts_dataset.read(part_ids.data(), H5::PredType::NATIVE_INT);
            }

            mesh.beams.resize(num_beams);
            for (size_t i = 0; i < num_beams; ++i) {
                mesh.beams[i].node_ids.resize(2);
                mesh.beams[i].node_ids[0] = connectivity[i * 2 + 0];
                mesh.beams[i].node_ids[1] = connectivity[i * 2 + 1];
                mesh.beams[i].material_id = part_ids[i];
            }
        }

    } catch (const H5::Exception& e) {
        throw std::runtime_error("Failed to read mesh: " + e.getDetailMsg());
    }

    return mesh;
}

// Load compression metadata from file
void HDF5Reader::load_compression_metadata() {
    if (!states_group_) return;

    try {
        // Check if metadata group exists
        if (!H5Lexists(states_group_->getId(), "_metadata", H5P_DEFAULT)) {
            return;
        }

        H5::Group meta_group = states_group_->openGroup("_metadata");

        // Read compression flags
        if (meta_group.attrExists("use_quantization")) {
            int val = 0;
            H5::Attribute attr = meta_group.openAttribute("use_quantization");
            attr.read(H5::PredType::NATIVE_INT, &val);
            use_quantization_ = (val != 0);
        }

        if (meta_group.attrExists("use_delta_compression")) {
            int val = 0;
            H5::Attribute attr = meta_group.openAttribute("use_delta_compression");
            attr.read(H5::PredType::NATIVE_INT, &val);
            use_delta_compression_ = (val != 0);
        }

        // Read quantization ranges
        if (use_quantization_) {
            if (H5Lexists(meta_group.getId(), "disp_min", H5P_DEFAULT)) {
                H5::DataSet ds = meta_group.openDataSet("disp_min");
                ds.read(disp_min_, H5::PredType::NATIVE_DOUBLE);
            }
            if (H5Lexists(meta_group.getId(), "disp_max", H5P_DEFAULT)) {
                H5::DataSet ds = meta_group.openDataSet("disp_max");
                ds.read(disp_max_, H5::PredType::NATIVE_DOUBLE);
            }
            if (H5Lexists(meta_group.getId(), "vel_min", H5P_DEFAULT)) {
                H5::DataSet ds = meta_group.openDataSet("vel_min");
                ds.read(vel_min_, H5::PredType::NATIVE_DOUBLE);
            }
            if (H5Lexists(meta_group.getId(), "vel_max", H5P_DEFAULT)) {
                H5::DataSet ds = meta_group.openDataSet("vel_max");
                ds.read(vel_max_, H5::PredType::NATIVE_DOUBLE);
            }
        }
    } catch (const H5::Exception& e) {
        std::cerr << "Warning: Could not load compression metadata: " << e.getDetailMsg() << "\n";
    }
}

// Get list of available timesteps
std::vector<int> HDF5Reader::get_timestep_list() const {
    std::vector<int> timesteps;

    if (!states_group_) return timesteps;

    try {
        hsize_t num_objs = states_group_->getNumObjs();
        for (hsize_t i = 0; i < num_objs; ++i) {
            std::string name = states_group_->getObjnameByIdx(i);
            if (name.find("timestep_") == 0) {
                int ts = std::stoi(name.substr(9));
                timesteps.push_back(ts);
            }
        }
        std::sort(timesteps.begin(), timesteps.end());
    } catch (...) {
        // Ignore errors
    }

    return timesteps;
}

// Get time value for a timestep
double HDF5Reader::get_timestep_time(int timestep) const {
    if (!states_group_) return -1.0;

    try {
        std::string group_name = "timestep_" + std::to_string(timestep);
        if (!H5Lexists(states_group_->getId(), group_name.c_str(), H5P_DEFAULT)) {
            return -1.0;
        }

        H5::Group ts_group = states_group_->openGroup(group_name);
        if (ts_group.attrExists("time")) {
            double time = 0.0;
            H5::Attribute attr = ts_group.openAttribute("time");
            attr.read(H5::PredType::NATIVE_DOUBLE, &time);
            return time;
        }
    } catch (...) {
        // Ignore errors
    }

    return -1.0;
}

// Read displacement data with dequantization and delta reconstruction
std::vector<double> HDF5Reader::read_displacement_data(int timestep) const {
    std::vector<double> result;

    try {
        std::string group_name = "timestep_" + std::to_string(timestep);
        if (!H5Lexists(states_group_->getId(), group_name.c_str(), H5P_DEFAULT)) {
            return result;
        }

        H5::Group ts_group = states_group_->openGroup(group_name);

        // Check what type of data is stored
        bool has_raw = H5Lexists(ts_group.getId(), "displacement", H5P_DEFAULT);
        bool has_quantized = H5Lexists(ts_group.getId(), "displacement_quantized", H5P_DEFAULT);
        bool has_delta = H5Lexists(ts_group.getId(), "displacement_delta", H5P_DEFAULT);

        if (has_raw) {
            // Read raw double data (lossless mode)
            H5::DataSet dataset = ts_group.openDataSet("displacement");
            H5::DataSpace dataspace = dataset.getSpace();

            hsize_t dims[2];
            dataspace.getSimpleExtentDims(dims);
            size_t num_nodes = dims[0];

            result.resize(num_nodes * 3);
            dataset.read(result.data(), H5::PredType::NATIVE_DOUBLE);

        } else if (has_quantized) {
            // Read full quantized data (first timestep)
            H5::DataSet dataset = ts_group.openDataSet("displacement_quantized");
            H5::DataSpace dataspace = dataset.getSpace();

            hsize_t dims[2];
            dataspace.getSimpleExtentDims(dims);
            size_t num_nodes = dims[0];

            std::vector<uint16_t> quantized(num_nodes * 3);
            dataset.read(quantized.data(), H5::PredType::NATIVE_UINT16);

            // Cache for delta reconstruction
            cached_displacement_quantized_ = quantized;
            last_read_timestep_ = timestep;

            // Dequantize
            result.resize(num_nodes * 3);
            const int max_quant = 65535;
            for (size_t i = 0; i < num_nodes; ++i) {
                for (int axis = 0; axis < 3; ++axis) {
                    double normalized = static_cast<double>(quantized[i * 3 + axis]) / max_quant;
                    double range = disp_max_[axis] - disp_min_[axis];
                    result[i * 3 + axis] = disp_min_[axis] + normalized * range;
                }
            }

        } else if (has_delta) {
            // Need to reconstruct from previous timestep
            // First, ensure we have the previous timestep cached
            if (cached_displacement_quantized_.empty() || last_read_timestep_ != timestep - 1) {
                // Read previous timesteps recursively
                for (int t = 0; t <= timestep; ++t) {
                    if (t < timestep) {
                        read_displacement_data(t);  // This will update cache
                    }
                }
            }

            // Read delta data
            H5::DataSet dataset = ts_group.openDataSet("displacement_delta");
            H5::DataSpace dataspace = dataset.getSpace();

            hsize_t dims[2];
            dataspace.getSimpleExtentDims(dims);
            size_t num_nodes = dims[0];

            std::vector<int16_t> deltas(num_nodes * 3);
            dataset.read(deltas.data(), H5::PredType::NATIVE_INT16);

            // Reconstruct quantized values
            std::vector<uint16_t> quantized(num_nodes * 3);
            for (size_t i = 0; i < quantized.size(); ++i) {
                int32_t value = static_cast<int32_t>(cached_displacement_quantized_[i]) +
                               static_cast<int32_t>(deltas[i]);
                quantized[i] = static_cast<uint16_t>(std::clamp(value, 0, 65535));
            }

            // Update cache
            cached_displacement_quantized_ = quantized;
            last_read_timestep_ = timestep;

            // Dequantize
            result.resize(num_nodes * 3);
            const int max_quant = 65535;
            for (size_t i = 0; i < num_nodes; ++i) {
                for (int axis = 0; axis < 3; ++axis) {
                    double normalized = static_cast<double>(quantized[i * 3 + axis]) / max_quant;
                    double range = disp_max_[axis] - disp_min_[axis];
                    result[i * 3 + axis] = disp_min_[axis] + normalized * range;
                }
            }
        }

    } catch (const H5::Exception& e) {
        std::cerr << "Warning: Could not read displacement data: " << e.getDetailMsg() << "\n";
    }

    return result;
}

// Read velocity data with dequantization and delta reconstruction
std::vector<double> HDF5Reader::read_velocity_data(int timestep) const {
    std::vector<double> result;

    try {
        std::string group_name = "timestep_" + std::to_string(timestep);
        if (!H5Lexists(states_group_->getId(), group_name.c_str(), H5P_DEFAULT)) {
            return result;
        }

        H5::Group ts_group = states_group_->openGroup(group_name);

        bool has_raw = H5Lexists(ts_group.getId(), "velocity", H5P_DEFAULT);
        bool has_quantized = H5Lexists(ts_group.getId(), "velocity_quantized", H5P_DEFAULT);
        bool has_delta = H5Lexists(ts_group.getId(), "velocity_delta", H5P_DEFAULT);

        if (has_raw) {
            H5::DataSet dataset = ts_group.openDataSet("velocity");
            H5::DataSpace dataspace = dataset.getSpace();

            hsize_t dims[2];
            dataspace.getSimpleExtentDims(dims);
            size_t num_nodes = dims[0];

            result.resize(num_nodes * 3);
            dataset.read(result.data(), H5::PredType::NATIVE_DOUBLE);

        } else if (has_quantized) {
            H5::DataSet dataset = ts_group.openDataSet("velocity_quantized");
            H5::DataSpace dataspace = dataset.getSpace();

            hsize_t dims[2];
            dataspace.getSimpleExtentDims(dims);
            size_t num_nodes = dims[0];

            std::vector<uint16_t> quantized(num_nodes * 3);
            dataset.read(quantized.data(), H5::PredType::NATIVE_UINT16);

            cached_velocity_quantized_ = quantized;

            result.resize(num_nodes * 3);
            const int max_quant = 65535;
            for (size_t i = 0; i < num_nodes; ++i) {
                for (int axis = 0; axis < 3; ++axis) {
                    double normalized = static_cast<double>(quantized[i * 3 + axis]) / max_quant;
                    double range = vel_max_[axis] - vel_min_[axis];
                    result[i * 3 + axis] = vel_min_[axis] + normalized * range;
                }
            }

        } else if (has_delta) {
            // Read delta data
            H5::DataSet dataset = ts_group.openDataSet("velocity_delta");
            H5::DataSpace dataspace = dataset.getSpace();

            hsize_t dims[2];
            dataspace.getSimpleExtentDims(dims);
            size_t num_nodes = dims[0];

            std::vector<int16_t> deltas(num_nodes * 3);
            dataset.read(deltas.data(), H5::PredType::NATIVE_INT16);

            // Reconstruct
            std::vector<uint16_t> quantized(num_nodes * 3);
            for (size_t i = 0; i < quantized.size(); ++i) {
                int32_t value = static_cast<int32_t>(cached_velocity_quantized_[i]) +
                               static_cast<int32_t>(deltas[i]);
                quantized[i] = static_cast<uint16_t>(std::clamp(value, 0, 65535));
            }

            cached_velocity_quantized_ = quantized;

            result.resize(num_nodes * 3);
            const int max_quant = 65535;
            for (size_t i = 0; i < num_nodes; ++i) {
                for (int axis = 0; axis < 3; ++axis) {
                    double normalized = static_cast<double>(quantized[i * 3 + axis]) / max_quant;
                    double range = vel_max_[axis] - vel_min_[axis];
                    result[i * 3 + axis] = vel_min_[axis] + normalized * range;
                }
            }
        }

    } catch (const H5::Exception& e) {
        std::cerr << "Warning: Could not read velocity data: " << e.getDetailMsg() << "\n";
    }

    return result;
}

// Read state data
std::optional<data::StateData> HDF5Reader::read_state(int timestep) {
    if (!is_open_ || !states_group_) {
        return std::nullopt;
    }

    try {
        std::string group_name = "timestep_" + std::to_string(timestep);
        if (!H5Lexists(states_group_->getId(), group_name.c_str(), H5P_DEFAULT)) {
            return std::nullopt;
        }

        data::StateData state;

        // Get time value
        state.time = get_timestep_time(timestep);

        // Read displacement data
        state.node_displacements = read_displacement_data(timestep);

        // Read velocity data
        state.node_velocities = read_velocity_data(timestep);

        return state;

    } catch (const H5::Exception& e) {
        std::cerr << "Warning: Could not read state " << timestep << ": " << e.getDetailMsg() << "\n";
        return std::nullopt;
    }
}

// Close file
void HDF5Reader::close() {
    if (is_open_) {
        try {
            states_group_.reset();
            mesh_group_.reset();
            file_.reset();
            is_open_ = false;
        } catch (const H5::Exception& e) {
            std::cerr << "Warning: Error closing HDF5 file: " << e.getDetailMsg() << "\n";
        }
    }
}

// ========================================
// Validation functions
// ========================================

// Validate nodes
ValidationResult HDF5Reader::validate_nodes(
    const std::vector<data::Node>& original,
    double tolerance
) {
    ValidationResult result;

    auto loaded = read_nodes();

    if (loaded.size() != original.size()) {
        result.passed = false;
        result.message = "Node count mismatch: original=" +
                        std::to_string(original.size()) +
                        ", loaded=" + std::to_string(loaded.size());
        return result;
    }

    double max_err = 0.0;
    double sum_err = 0.0;
    double sum_sq_err = 0.0;
    double max_rel_err = 0.0;

    for (size_t i = 0; i < original.size(); ++i) {
        double dx = std::abs(original[i].x - loaded[i].x);
        double dy = std::abs(original[i].y - loaded[i].y);
        double dz = std::abs(original[i].z - loaded[i].z);

        double err = std::sqrt(dx*dx + dy*dy + dz*dz);
        max_err = std::max(max_err, err);
        sum_err += err;
        sum_sq_err += err * err;

        // Relative error
        double orig_mag = std::sqrt(
            original[i].x * original[i].x +
            original[i].y * original[i].y +
            original[i].z * original[i].z
        );
        if (orig_mag > 1e-10) {
            double rel_err = err / orig_mag * 100.0;
            max_rel_err = std::max(max_rel_err, rel_err);
        }
    }

    size_t n = original.size();
    result.max_error = max_err;
    result.mean_error = sum_err / n;
    result.rms_error = std::sqrt(sum_sq_err / n);
    result.max_relative_error = max_rel_err;

    if (max_err > tolerance) {
        result.passed = false;
        result.message = "Maximum error (" + std::to_string(max_err) +
                        ") exceeds tolerance (" + std::to_string(tolerance) + ")";
    } else {
        result.passed = true;
        result.message = "All nodes within tolerance";
    }

    return result;
}

// Validate solids
ValidationResult HDF5Reader::validate_solids(const std::vector<data::Element>& original) {
    ValidationResult result;

    auto mesh = read_mesh();
    const auto& loaded = mesh.solids;

    if (loaded.size() != original.size()) {
        result.passed = false;
        result.message = "Solid count mismatch: original=" +
                        std::to_string(original.size()) +
                        ", loaded=" + std::to_string(loaded.size());
        return result;
    }

    for (size_t i = 0; i < original.size(); ++i) {
        // Compare node_ids
        if (original[i].node_ids.size() != loaded[i].node_ids.size()) {
            result.passed = false;
            result.message = "Solid " + std::to_string(i) + " node count mismatch";
            return result;
        }
        for (size_t j = 0; j < original[i].node_ids.size(); ++j) {
            if (original[i].node_ids[j] != loaded[i].node_ids[j]) {
                result.passed = false;
                result.message = "Solid " + std::to_string(i) +
                                " node " + std::to_string(j) + " mismatch";
                return result;
            }
        }
        if (original[i].material_id != loaded[i].material_id) {
            result.passed = false;
            result.message = "Solid " + std::to_string(i) + " material_id mismatch";
            return result;
        }
    }

    result.passed = true;
    result.message = "All solids match exactly";
    return result;
}

// Validate shells
ValidationResult HDF5Reader::validate_shells(const std::vector<data::Element>& original) {
    ValidationResult result;

    auto mesh = read_mesh();
    const auto& loaded = mesh.shells;

    if (loaded.size() != original.size()) {
        result.passed = false;
        result.message = "Shell count mismatch: original=" +
                        std::to_string(original.size()) +
                        ", loaded=" + std::to_string(loaded.size());
        return result;
    }

    for (size_t i = 0; i < original.size(); ++i) {
        if (original[i].node_ids.size() != loaded[i].node_ids.size()) {
            result.passed = false;
            result.message = "Shell " + std::to_string(i) + " node count mismatch";
            return result;
        }
        for (size_t j = 0; j < original[i].node_ids.size(); ++j) {
            if (original[i].node_ids[j] != loaded[i].node_ids[j]) {
                result.passed = false;
                result.message = "Shell " + std::to_string(i) +
                                " node " + std::to_string(j) + " mismatch";
                return result;
            }
        }
        if (original[i].material_id != loaded[i].material_id) {
            result.passed = false;
            result.message = "Shell " + std::to_string(i) + " material_id mismatch";
            return result;
        }
    }

    result.passed = true;
    result.message = "All shells match exactly";
    return result;
}

// Analyze significant digits
ValidationResult HDF5Reader::analyze_significant_digits(
    const std::vector<double>& original,
    const std::vector<double>& loaded,
    int required_digits
) {
    ValidationResult result;

    if (original.size() != loaded.size()) {
        result.passed = false;
        result.message = "Size mismatch";
        return result;
    }

    int min_digits = 15;  // Start with max
    int count_meeting_requirement = 0;

    for (size_t i = 0; i < original.size(); ++i) {
        double orig = original[i];
        double load = loaded[i];

        if (std::abs(orig) < 1e-15) {
            // Skip near-zero values
            if (std::abs(load) < 1e-15) {
                count_meeting_requirement++;
            }
            continue;
        }

        // Calculate relative error
        double rel_err = std::abs(orig - load) / std::abs(orig);

        // Convert to significant digits
        // sig_digits = -log10(rel_err)
        int sig_digits;
        if (rel_err < 1e-15) {
            sig_digits = 15;  // Essentially exact
        } else {
            sig_digits = static_cast<int>(-std::log10(rel_err));
        }

        min_digits = std::min(min_digits, sig_digits);

        if (sig_digits >= required_digits) {
            count_meeting_requirement++;
        }
    }

    result.min_significant_digits = min_digits;
    result.significant_digit_ratio =
        static_cast<double>(count_meeting_requirement) / original.size() * 100.0;

    if (min_digits >= required_digits) {
        result.passed = true;
        result.message = "All values have >= " + std::to_string(required_digits) +
                        " significant digits";
    } else {
        result.passed = false;
        result.message = "Minimum significant digits (" + std::to_string(min_digits) +
                        ") is less than required (" + std::to_string(required_digits) + ")";
    }

    return result;
}

} // namespace hdf5
} // namespace kood3plot
