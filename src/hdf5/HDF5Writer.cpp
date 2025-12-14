#include <kood3plot/hdf5/HDF5Writer.hpp>

// HDF5 C++ API
#include <H5Cpp.h>

#include <iostream>
#include <stdexcept>
#include <vector>
#include <cmath>
#include <algorithm>
#include <limits>

namespace kood3plot {
namespace hdf5 {

// Constructor
HDF5Writer::HDF5Writer(const std::string& filename, const CompressionOptions& options)
    : file_(nullptr)
    , mesh_group_(nullptr)
    , states_group_(nullptr)
    , is_open_(false)
    , filename_(filename)
    , options_(options)
{
    try {
        // Turn off auto-printing when failure occurs
        H5::Exception::dontPrint();

        // Create HDF5 file (overwrite if exists)
        file_ = std::make_unique<H5::H5File>(
            filename,
            H5F_ACC_TRUNC  // Truncate (overwrite) if exists
        );

        is_open_ = true;

        // Create main groups
        create_groups();

        // Write file attributes
        H5::Attribute attr = file_->createAttribute(
            "format",
            H5::StrType(H5::PredType::C_S1, 32),
            H5::DataSpace(H5S_SCALAR)
        );
        const char* format_str = "KooD3plot HDF5 v1.0";
        attr.write(H5::StrType(H5::PredType::C_S1, 32), format_str);

    } catch (const H5::FileIException& e) {
        throw std::runtime_error("Failed to create HDF5 file: " + filename + " - " + e.getDetailMsg());
    } catch (const H5::Exception& e) {
        throw std::runtime_error("HDF5 error: " + e.getDetailMsg());
    }
}

// Destructor
HDF5Writer::~HDF5Writer() {
    close();
}

// Create main groups
void HDF5Writer::create_groups() {
    try {
        // Create /mesh group
        mesh_group_ = std::make_unique<H5::Group>(
            file_->createGroup("/mesh")
        );

        // Create /states group
        states_group_ = std::make_unique<H5::Group>(
            file_->createGroup("/states")
        );

    } catch (const H5::Exception& e) {
        throw std::runtime_error("Failed to create HDF5 groups: " + e.getDetailMsg());
    }
}

// Write mesh data
void HDF5Writer::write_mesh(const data::Mesh& mesh) {
    if (!is_open_) {
        throw std::runtime_error("HDF5 file is not open");
    }

    try {
        // Write mesh metadata
        write_mesh_metadata(mesh);

        // Write nodes
        write_nodes(mesh);

        // Write elements
        if (!mesh.solids.empty()) {
            write_solids(mesh);
        }

        if (!mesh.shells.empty()) {
            write_shells(mesh);
        }

        if (!mesh.beams.empty()) {
            write_beams(mesh);
        }

        std::cout << "Mesh written to HDF5: "
                  << mesh.nodes.size() << " nodes, "
                  << mesh.solids.size() << " solids, "
                  << mesh.shells.size() << " shells, "
                  << mesh.beams.size() << " beams\n";

    } catch (const H5::Exception& e) {
        throw std::runtime_error("Failed to write mesh: " + e.getDetailMsg());
    }
}

// Write mesh metadata
void HDF5Writer::write_mesh_metadata(const data::Mesh& mesh) {
    try {
        // Write number of nodes
        H5::Attribute attr_nodes = mesh_group_->createAttribute(
            "num_nodes",
            H5::PredType::NATIVE_INT,
            H5::DataSpace(H5S_SCALAR)
        );
        int num_nodes = static_cast<int>(mesh.nodes.size());
        attr_nodes.write(H5::PredType::NATIVE_INT, &num_nodes);

        // Write number of elements
        H5::Attribute attr_solids = mesh_group_->createAttribute(
            "num_solids",
            H5::PredType::NATIVE_INT,
            H5::DataSpace(H5S_SCALAR)
        );
        int num_solids = static_cast<int>(mesh.solids.size());
        attr_solids.write(H5::PredType::NATIVE_INT, &num_solids);

        H5::Attribute attr_shells = mesh_group_->createAttribute(
            "num_shells",
            H5::PredType::NATIVE_INT,
            H5::DataSpace(H5S_SCALAR)
        );
        int num_shells = static_cast<int>(mesh.shells.size());
        attr_shells.write(H5::PredType::NATIVE_INT, &num_shells);

        H5::Attribute attr_beams = mesh_group_->createAttribute(
            "num_beams",
            H5::PredType::NATIVE_INT,
            H5::DataSpace(H5S_SCALAR)
        );
        int num_beams = static_cast<int>(mesh.beams.size());
        attr_beams.write(H5::PredType::NATIVE_INT, &num_beams);

    } catch (const H5::Exception& e) {
        throw std::runtime_error("Failed to write mesh metadata: " + e.getDetailMsg());
    }
}

// Write nodes
void HDF5Writer::write_nodes(const data::Mesh& mesh) {
    if (mesh.nodes.empty()) {
        return;
    }

    try {
        // Prepare node data: [N x 3] array (x, y, z)
        size_t num_nodes = mesh.nodes.size();
        std::vector<double> coords(num_nodes * 3);

        for (size_t i = 0; i < num_nodes; ++i) {
            coords[i * 3 + 0] = mesh.nodes[i].x;
            coords[i * 3 + 1] = mesh.nodes[i].y;
            coords[i * 3 + 2] = mesh.nodes[i].z;
        }

        // Create dataspace: [num_nodes x 3]
        hsize_t dims[2] = {num_nodes, 3};
        H5::DataSpace dataspace(2, dims);

        // Create dataset with chunking and compression
        H5::DSetCreatPropList plist;

        // Enable chunking (required for compression)
        hsize_t chunk_dims[2] = {
            std::min(num_nodes, static_cast<size_t>(10000)),  // Max 10k nodes per chunk
            3
        };
        plist.setChunk(2, chunk_dims);

        // Enable gzip compression (level 6 = balanced speed/compression)
        plist.setDeflate(6);

        // Create dataset
        H5::DataSet dataset = mesh_group_->createDataSet(
            "nodes",
            H5::PredType::NATIVE_DOUBLE,
            dataspace,
            plist
        );

        // Write data
        dataset.write(coords.data(), H5::PredType::NATIVE_DOUBLE);

        // Write dataset attributes
        H5::Attribute attr_desc = dataset.createAttribute(
            "description",
            H5::StrType(H5::PredType::C_S1, 64),
            H5::DataSpace(H5S_SCALAR)
        );
        const char* desc_str = "Node coordinates [x, y, z] in mm";
        attr_desc.write(H5::StrType(H5::PredType::C_S1, 64), desc_str);

        H5::Attribute attr_unit = dataset.createAttribute(
            "unit",
            H5::StrType(H5::PredType::C_S1, 16),
            H5::DataSpace(H5S_SCALAR)
        );
        const char* unit_str = "mm";
        attr_unit.write(H5::StrType(H5::PredType::C_S1, 16), unit_str);

    } catch (const H5::Exception& e) {
        throw std::runtime_error("Failed to write nodes: " + e.getDetailMsg());
    }
}

// Write solid elements
void HDF5Writer::write_solids(const data::Mesh& mesh) {
    if (mesh.solids.empty()) {
        return;
    }

    try {
        size_t num_solids = mesh.solids.size();

        // Prepare connectivity data: [N x 8] array
        std::vector<int> connectivity(num_solids * 8);
        std::vector<int> part_ids(num_solids);

        for (size_t i = 0; i < num_solids; ++i) {
            const auto& solid = mesh.solids[i];
            for (size_t j = 0; j < std::min(size_t(8), solid.node_ids.size()); ++j) {
                connectivity[i * 8 + j] = solid.node_ids[j];
            }
            part_ids[i] = solid.material_id;
        }

        // Create connectivity dataset
        hsize_t dims_conn[2] = {num_solids, 8};
        H5::DataSpace dataspace_conn(2, dims_conn);

        H5::DSetCreatPropList plist_conn;
        hsize_t chunk_dims[2] = {
            std::min(num_solids, static_cast<size_t>(10000)),
            8
        };
        plist_conn.setChunk(2, chunk_dims);
        plist_conn.setDeflate(6);

        H5::DataSet dataset_conn = mesh_group_->createDataSet(
            "solid_connectivity",
            H5::PredType::NATIVE_INT,
            dataspace_conn,
            plist_conn
        );
        dataset_conn.write(connectivity.data(), H5::PredType::NATIVE_INT);

        // Create part IDs dataset
        hsize_t dims_parts[1] = {num_solids};
        H5::DataSpace dataspace_parts(1, dims_parts);

        H5::DSetCreatPropList plist_parts;
        hsize_t chunk_parts[1] = {std::min(num_solids, static_cast<size_t>(10000))};
        plist_parts.setChunk(1, chunk_parts);
        plist_parts.setDeflate(6);

        H5::DataSet dataset_parts = mesh_group_->createDataSet(
            "solid_part_ids",
            H5::PredType::NATIVE_INT,
            dataspace_parts,
            plist_parts
        );
        dataset_parts.write(part_ids.data(), H5::PredType::NATIVE_INT);

    } catch (const H5::Exception& e) {
        throw std::runtime_error("Failed to write solids: " + e.getDetailMsg());
    }
}

// Write shell elements
void HDF5Writer::write_shells(const data::Mesh& mesh) {
    if (mesh.shells.empty()) {
        return;
    }

    try {
        size_t num_shells = mesh.shells.size();

        // Prepare connectivity data: [N x 4] array
        std::vector<int> connectivity(num_shells * 4);
        std::vector<int> part_ids(num_shells);

        for (size_t i = 0; i < num_shells; ++i) {
            const auto& shell = mesh.shells[i];
            for (size_t j = 0; j < std::min(size_t(4), shell.node_ids.size()); ++j) {
                connectivity[i * 4 + j] = shell.node_ids[j];
            }
            part_ids[i] = shell.material_id;
        }

        // Create connectivity dataset
        hsize_t dims_conn[2] = {num_shells, 4};
        H5::DataSpace dataspace_conn(2, dims_conn);

        H5::DSetCreatPropList plist_conn;
        hsize_t chunk_dims[2] = {
            std::min(num_shells, static_cast<size_t>(10000)),
            4
        };
        plist_conn.setChunk(2, chunk_dims);
        plist_conn.setDeflate(6);

        H5::DataSet dataset_conn = mesh_group_->createDataSet(
            "shell_connectivity",
            H5::PredType::NATIVE_INT,
            dataspace_conn,
            plist_conn
        );
        dataset_conn.write(connectivity.data(), H5::PredType::NATIVE_INT);

        // Create part IDs dataset
        hsize_t dims_parts[1] = {num_shells};
        H5::DataSpace dataspace_parts(1, dims_parts);

        H5::DSetCreatPropList plist_parts;
        hsize_t chunk_parts[1] = {std::min(num_shells, static_cast<size_t>(10000))};
        plist_parts.setChunk(1, chunk_parts);
        plist_parts.setDeflate(6);

        H5::DataSet dataset_parts = mesh_group_->createDataSet(
            "shell_part_ids",
            H5::PredType::NATIVE_INT,
            dataspace_parts,
            plist_parts
        );
        dataset_parts.write(part_ids.data(), H5::PredType::NATIVE_INT);

    } catch (const H5::Exception& e) {
        throw std::runtime_error("Failed to write shells: " + e.getDetailMsg());
    }
}

// Write beam elements
void HDF5Writer::write_beams(const data::Mesh& mesh) {
    if (mesh.beams.empty()) {
        return;
    }

    try {
        size_t num_beams = mesh.beams.size();

        // Prepare connectivity data: [N x 2] array
        std::vector<int> connectivity(num_beams * 2);
        std::vector<int> part_ids(num_beams);

        for (size_t i = 0; i < num_beams; ++i) {
            const auto& beam = mesh.beams[i];
            if (beam.node_ids.size() >= 2) {
                connectivity[i * 2 + 0] = beam.node_ids[0];
                connectivity[i * 2 + 1] = beam.node_ids[1];
            }
            part_ids[i] = beam.material_id;
        }

        // Create connectivity dataset
        hsize_t dims_conn[2] = {num_beams, 2};
        H5::DataSpace dataspace_conn(2, dims_conn);

        H5::DSetCreatPropList plist_conn;
        hsize_t chunk_dims[2] = {
            std::min(num_beams, static_cast<size_t>(10000)),
            2
        };
        plist_conn.setChunk(2, chunk_dims);
        plist_conn.setDeflate(6);

        H5::DataSet dataset_conn = mesh_group_->createDataSet(
            "beam_connectivity",
            H5::PredType::NATIVE_INT,
            dataspace_conn,
            plist_conn
        );
        dataset_conn.write(connectivity.data(), H5::PredType::NATIVE_INT);

        // Create part IDs dataset
        hsize_t dims_parts[1] = {num_beams};
        H5::DataSpace dataspace_parts(1, dims_parts);

        H5::DSetCreatPropList plist_parts;
        hsize_t chunk_parts[1] = {std::min(num_beams, static_cast<size_t>(10000))};
        plist_parts.setChunk(1, chunk_parts);
        plist_parts.setDeflate(6);

        H5::DataSet dataset_parts = mesh_group_->createDataSet(
            "beam_part_ids",
            H5::PredType::NATIVE_INT,
            dataspace_parts,
            plist_parts
        );
        dataset_parts.write(part_ids.data(), H5::PredType::NATIVE_INT);

    } catch (const H5::Exception& e) {
        throw std::runtime_error("Failed to write beams: " + e.getDetailMsg());
    }
}

// Calibrate quantizers from first timestep data
void HDF5Writer::calibrate_quantizers(const data::StateData& state) {
    if (calibrated_) return;

    // Find min/max for displacements (Ux, Uy, Uz interleaved)
    if (!state.node_displacements.empty()) {
        size_t num_nodes = state.node_displacements.size() / 3;
        for (int axis = 0; axis < 3; ++axis) {
            disp_min_[axis] = std::numeric_limits<double>::max();
            disp_max_[axis] = std::numeric_limits<double>::lowest();
        }
        for (size_t i = 0; i < num_nodes; ++i) {
            for (int axis = 0; axis < 3; ++axis) {
                double v = state.node_displacements[i * 3 + axis];
                disp_min_[axis] = std::min(disp_min_[axis], v);
                disp_max_[axis] = std::max(disp_max_[axis], v);
            }
        }
        // Add 10% margin
        for (int axis = 0; axis < 3; ++axis) {
            double range = disp_max_[axis] - disp_min_[axis];
            if (range < 1e-10) range = 1.0;  // Avoid zero range
            disp_min_[axis] -= range * 0.1;
            disp_max_[axis] += range * 0.1;
        }
    }

    // Find min/max for velocities
    if (!state.node_velocities.empty()) {
        size_t num_nodes = state.node_velocities.size() / 3;
        for (int axis = 0; axis < 3; ++axis) {
            vel_min_[axis] = std::numeric_limits<double>::max();
            vel_max_[axis] = std::numeric_limits<double>::lowest();
        }
        for (size_t i = 0; i < num_nodes; ++i) {
            for (int axis = 0; axis < 3; ++axis) {
                double v = state.node_velocities[i * 3 + axis];
                vel_min_[axis] = std::min(vel_min_[axis], v);
                vel_max_[axis] = std::max(vel_max_[axis], v);
            }
        }
        for (int axis = 0; axis < 3; ++axis) {
            double range = vel_max_[axis] - vel_min_[axis];
            if (range < 1e-10) range = 1.0;
            vel_min_[axis] -= range * 0.1;
            vel_max_[axis] += range * 0.1;
        }
    }

    calibrated_ = true;
}

// Write timestep metadata
void HDF5Writer::write_timestep_metadata(int timestep, double time) {
    try {
        std::string group_name = "/states/timestep_" + std::to_string(timestep);
        H5::Group ts_group = file_->createGroup(group_name);

        // Write time attribute
        H5::Attribute attr_time = ts_group.createAttribute(
            "time",
            H5::PredType::NATIVE_DOUBLE,
            H5::DataSpace(H5S_SCALAR)
        );
        attr_time.write(H5::PredType::NATIVE_DOUBLE, &time);

        // Write timestep index
        H5::Attribute attr_idx = ts_group.createAttribute(
            "timestep_index",
            H5::PredType::NATIVE_INT,
            H5::DataSpace(H5S_SCALAR)
        );
        attr_idx.write(H5::PredType::NATIVE_INT, &timestep);

        // Write compression mode
        int is_delta = (timestep > 0 && options_.use_delta_compression) ? 1 : 0;
        H5::Attribute attr_delta = ts_group.createAttribute(
            "is_delta_compressed",
            H5::PredType::NATIVE_INT,
            H5::DataSpace(H5S_SCALAR)
        );
        attr_delta.write(H5::PredType::NATIVE_INT, &is_delta);

    } catch (const H5::Exception& e) {
        throw std::runtime_error("Failed to write timestep metadata: " + e.getDetailMsg());
    }
}

// Write displacement data with optional quantization and delta compression
void HDF5Writer::write_displacement_data(int timestep, const std::vector<double>& displacements) {
    if (displacements.empty()) return;

    try {
        std::string group_name = "/states/timestep_" + std::to_string(timestep);
        H5::Group ts_group = file_->openGroup(group_name);

        size_t num_nodes = displacements.size() / 3;
        bool use_delta = (timestep > 0) && options_.use_delta_compression &&
                         !prev_displacement_quantized_.empty();

        if (options_.use_quantization) {
            // Quantize to 16-bit
            std::vector<uint16_t> quantized(displacements.size());
            const int max_quant = 65535;

            for (size_t i = 0; i < num_nodes; ++i) {
                for (int axis = 0; axis < 3; ++axis) {
                    double v = displacements[i * 3 + axis];
                    double range = disp_max_[axis] - disp_min_[axis];
                    double normalized = (v - disp_min_[axis]) / range;
                    normalized = std::clamp(normalized, 0.0, 1.0);
                    quantized[i * 3 + axis] = static_cast<uint16_t>(std::round(normalized * max_quant));
                }
            }

            if (use_delta) {
                // Store deltas as int16
                std::vector<int16_t> deltas(quantized.size());
                for (size_t i = 0; i < quantized.size(); ++i) {
                    int32_t delta = static_cast<int32_t>(quantized[i]) -
                                   static_cast<int32_t>(prev_displacement_quantized_[i]);
                    deltas[i] = static_cast<int16_t>(std::clamp(delta, -32768, 32767));
                }

                // Write delta data
                hsize_t dims[2] = {num_nodes, 3};
                H5::DataSpace dataspace(2, dims);

                H5::DSetCreatPropList plist;
                hsize_t chunk_dims[2] = {std::min(num_nodes, size_t(10000)), 3};
                plist.setChunk(2, chunk_dims);
                if (options_.gzip_level > 0) {
                    plist.setDeflate(options_.gzip_level);
                }

                H5::DataSet dataset = ts_group.createDataSet(
                    "displacement_delta",
                    H5::PredType::NATIVE_INT16,
                    dataspace,
                    plist
                );
                dataset.write(deltas.data(), H5::PredType::NATIVE_INT16);

            } else {
                // Store full quantized data (first timestep)
                hsize_t dims[2] = {num_nodes, 3};
                H5::DataSpace dataspace(2, dims);

                H5::DSetCreatPropList plist;
                hsize_t chunk_dims[2] = {std::min(num_nodes, size_t(10000)), 3};
                plist.setChunk(2, chunk_dims);
                if (options_.gzip_level > 0) {
                    plist.setDeflate(options_.gzip_level);
                }

                H5::DataSet dataset = ts_group.createDataSet(
                    "displacement_quantized",
                    H5::PredType::NATIVE_UINT16,
                    dataspace,
                    plist
                );
                dataset.write(quantized.data(), H5::PredType::NATIVE_UINT16);
            }

            // Store for next delta
            prev_displacement_quantized_ = std::move(quantized);

        } else {
            // Store raw double data (lossless mode)
            hsize_t dims[2] = {num_nodes, 3};
            H5::DataSpace dataspace(2, dims);

            H5::DSetCreatPropList plist;
            hsize_t chunk_dims[2] = {std::min(num_nodes, size_t(10000)), 3};
            plist.setChunk(2, chunk_dims);
            if (options_.gzip_level > 0) {
                plist.setDeflate(options_.gzip_level);
            }

            H5::DataSet dataset = ts_group.createDataSet(
                "displacement",
                H5::PredType::NATIVE_DOUBLE,
                dataspace,
                plist
            );
            dataset.write(displacements.data(), H5::PredType::NATIVE_DOUBLE);
        }

    } catch (const H5::Exception& e) {
        throw std::runtime_error("Failed to write displacement data: " + e.getDetailMsg());
    }
}

// Write velocity data
void HDF5Writer::write_velocity_data(int timestep, const std::vector<double>& velocities) {
    if (velocities.empty()) return;

    try {
        std::string group_name = "/states/timestep_" + std::to_string(timestep);
        H5::Group ts_group = file_->openGroup(group_name);

        size_t num_nodes = velocities.size() / 3;
        bool use_delta = (timestep > 0) && options_.use_delta_compression &&
                         !prev_velocity_quantized_.empty();

        if (options_.use_quantization) {
            std::vector<uint16_t> quantized(velocities.size());
            const int max_quant = 65535;

            for (size_t i = 0; i < num_nodes; ++i) {
                for (int axis = 0; axis < 3; ++axis) {
                    double v = velocities[i * 3 + axis];
                    double range = vel_max_[axis] - vel_min_[axis];
                    double normalized = (v - vel_min_[axis]) / range;
                    normalized = std::clamp(normalized, 0.0, 1.0);
                    quantized[i * 3 + axis] = static_cast<uint16_t>(std::round(normalized * max_quant));
                }
            }

            if (use_delta) {
                std::vector<int16_t> deltas(quantized.size());
                for (size_t i = 0; i < quantized.size(); ++i) {
                    int32_t delta = static_cast<int32_t>(quantized[i]) -
                                   static_cast<int32_t>(prev_velocity_quantized_[i]);
                    deltas[i] = static_cast<int16_t>(std::clamp(delta, -32768, 32767));
                }

                hsize_t dims[2] = {num_nodes, 3};
                H5::DataSpace dataspace(2, dims);

                H5::DSetCreatPropList plist;
                hsize_t chunk_dims[2] = {std::min(num_nodes, size_t(10000)), 3};
                plist.setChunk(2, chunk_dims);
                if (options_.gzip_level > 0) {
                    plist.setDeflate(options_.gzip_level);
                }

                H5::DataSet dataset = ts_group.createDataSet(
                    "velocity_delta",
                    H5::PredType::NATIVE_INT16,
                    dataspace,
                    plist
                );
                dataset.write(deltas.data(), H5::PredType::NATIVE_INT16);

            } else {
                hsize_t dims[2] = {num_nodes, 3};
                H5::DataSpace dataspace(2, dims);

                H5::DSetCreatPropList plist;
                hsize_t chunk_dims[2] = {std::min(num_nodes, size_t(10000)), 3};
                plist.setChunk(2, chunk_dims);
                if (options_.gzip_level > 0) {
                    plist.setDeflate(options_.gzip_level);
                }

                H5::DataSet dataset = ts_group.createDataSet(
                    "velocity_quantized",
                    H5::PredType::NATIVE_UINT16,
                    dataspace,
                    plist
                );
                dataset.write(quantized.data(), H5::PredType::NATIVE_UINT16);
            }

            prev_velocity_quantized_ = std::move(quantized);

        } else {
            hsize_t dims[2] = {num_nodes, 3};
            H5::DataSpace dataspace(2, dims);

            H5::DSetCreatPropList plist;
            hsize_t chunk_dims[2] = {std::min(num_nodes, size_t(10000)), 3};
            plist.setChunk(2, chunk_dims);
            if (options_.gzip_level > 0) {
                plist.setDeflate(options_.gzip_level);
            }

            H5::DataSet dataset = ts_group.createDataSet(
                "velocity",
                H5::PredType::NATIVE_DOUBLE,
                dataspace,
                plist
            );
            dataset.write(velocities.data(), H5::PredType::NATIVE_DOUBLE);
        }

    } catch (const H5::Exception& e) {
        throw std::runtime_error("Failed to write velocity data: " + e.getDetailMsg());
    }
}

// Write compression metadata to file
void HDF5Writer::write_compression_metadata() {
    try {
        H5::Group meta_group = states_group_->createGroup("_metadata");

        // Write quantization ranges for dequantization
        if (options_.use_quantization) {
            // Displacement ranges
            {
                hsize_t dims[1] = {3};
                H5::DataSpace dataspace(1, dims);
                H5::DataSet ds_min = meta_group.createDataSet("disp_min", H5::PredType::NATIVE_DOUBLE, dataspace);
                H5::DataSet ds_max = meta_group.createDataSet("disp_max", H5::PredType::NATIVE_DOUBLE, dataspace);
                ds_min.write(disp_min_, H5::PredType::NATIVE_DOUBLE);
                ds_max.write(disp_max_, H5::PredType::NATIVE_DOUBLE);
            }

            // Velocity ranges
            {
                hsize_t dims[1] = {3};
                H5::DataSpace dataspace(1, dims);
                H5::DataSet ds_min = meta_group.createDataSet("vel_min", H5::PredType::NATIVE_DOUBLE, dataspace);
                H5::DataSet ds_max = meta_group.createDataSet("vel_max", H5::PredType::NATIVE_DOUBLE, dataspace);
                ds_min.write(vel_min_, H5::PredType::NATIVE_DOUBLE);
                ds_max.write(vel_max_, H5::PredType::NATIVE_DOUBLE);
            }
        }

        // Write compression options
        int use_quant = options_.use_quantization ? 1 : 0;
        int use_delta = options_.use_delta_compression ? 1 : 0;

        H5::Attribute attr_quant = meta_group.createAttribute("use_quantization", H5::PredType::NATIVE_INT, H5::DataSpace(H5S_SCALAR));
        attr_quant.write(H5::PredType::NATIVE_INT, &use_quant);

        H5::Attribute attr_delta = meta_group.createAttribute("use_delta_compression", H5::PredType::NATIVE_INT, H5::DataSpace(H5S_SCALAR));
        attr_delta.write(H5::PredType::NATIVE_INT, &use_delta);

        H5::Attribute attr_gzip = meta_group.createAttribute("gzip_level", H5::PredType::NATIVE_INT, H5::DataSpace(H5S_SCALAR));
        attr_gzip.write(H5::PredType::NATIVE_INT, &options_.gzip_level);

    } catch (const H5::Exception& e) {
        throw std::runtime_error("Failed to write compression metadata: " + e.getDetailMsg());
    }
}

// Write timestep
void HDF5Writer::write_timestep(int timestep, const data::StateData& state) {
    if (!is_open_) {
        throw std::runtime_error("HDF5 file is not open");
    }

    try {
        // Calibrate quantizers on first timestep
        if (!calibrated_ && options_.use_quantization) {
            calibrate_quantizers(state);
        }

        // Write timestep metadata (creates group)
        write_timestep_metadata(timestep, state.time);

        // Write displacement data
        if (!state.node_displacements.empty()) {
            write_displacement_data(timestep, state.node_displacements);
        }

        // Write velocity data
        if (!state.node_velocities.empty()) {
            write_velocity_data(timestep, state.node_velocities);
        }

        // Write compression metadata after first timestep
        if (timestep == 0 && options_.use_quantization) {
            write_compression_metadata();
        }

        // Update num_timesteps attribute
        int num_ts = timestep + 1;
        try {
            states_group_->removeAttr("num_timesteps");
        } catch (...) {}

        H5::Attribute attr = states_group_->createAttribute(
            "num_timesteps",
            H5::PredType::NATIVE_INT,
            H5::DataSpace(H5S_SCALAR)
        );
        attr.write(H5::PredType::NATIVE_INT, &num_ts);

        last_timestep_ = timestep;

    } catch (const H5::Exception& e) {
        throw std::runtime_error("Failed to write timestep " + std::to_string(timestep) + ": " + e.getDetailMsg());
    }
}

// Close file
void HDF5Writer::close() {
    if (is_open_) {
        try {
            // Close groups first
            mesh_group_.reset();
            states_group_.reset();

            // Close file
            file_.reset();

            is_open_ = false;

        } catch (const H5::Exception& e) {
            std::cerr << "Warning: Error closing HDF5 file: " << e.getDetailMsg() << "\n";
        }
    }
}

} // namespace hdf5
} // namespace kood3plot
