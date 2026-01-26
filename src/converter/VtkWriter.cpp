/**
 * @file VtkWriter.cpp
 * @brief Implementation of VtkWriter class
 */

#include "kood3plot/converter/VtkWriter.h"
#include <iostream>
#include <iomanip>
#include <sstream>

namespace kood3plot {
namespace converter {

VtkWriter::VtkWriter(const std::string& filepath)
    : filepath_(filepath)
{
}

VtkWriter::~VtkWriter() {
    if (file_.is_open()) {
        file_.close();
    }
}

void VtkWriter::setOptions(const VtkWriterOptions& options) {
    options_ = options;
}

ErrorCode VtkWriter::write(const VtkMesh& mesh) {
    bytes_written_ = 0;
    last_error_.clear();

    // Only support Legacy ASCII for now
    if (options_.format != VtkFormat::LEGACY_ASCII) {
        last_error_ = "Only Legacy ASCII format is supported";
        return ErrorCode::INVALID_FORMAT;
    }

    return writeLegacyAscii(mesh);
}

std::string VtkWriter::getLastError() const {
    return last_error_;
}

size_t VtkWriter::getBytesWritten() const {
    return bytes_written_;
}

ErrorCode VtkWriter::writeLegacyAscii(const VtkMesh& mesh) {
    file_.open(filepath_);
    if (!file_.is_open()) {
        last_error_ = "Cannot open file for writing: " + filepath_;
        return ErrorCode::IO_ERROR;
    }

    if (options_.verbose) {
        std::cout << "[VtkWriter] Writing VTK file: " << filepath_ << "\n";
    }

    // Header
    writeLine("# vtk DataFile Version 3.0");
    writeLine(mesh.title.empty() ? "VTK Data" : mesh.title);
    writeLine("ASCII");
    writeLine("DATASET UNSTRUCTURED_GRID");
    writeLine("");

    // Points
    size_t num_points = mesh.points.size() / 3;
    writeLine("POINTS " + std::to_string(num_points) + " float");

    for (size_t i = 0; i < num_points; ++i) {
        std::ostringstream oss;
        oss << std::fixed << std::setprecision(6)
            << mesh.points[i * 3 + 0] << " "
            << mesh.points[i * 3 + 1] << " "
            << mesh.points[i * 3 + 2];
        writeLine(oss.str());
    }
    writeLine("");

    // Cells
    size_t num_cells = mesh.cell_types.size();
    if (num_cells > 0) {
        // Calculate total connectivity size (num_cells + sum of nodes per cell)
        size_t total_size = 0;
        size_t offset = 0;
        for (size_t i = 0; i < num_cells; ++i) {
            size_t num_nodes = (i < num_cells - 1) ?
                (mesh.offsets[i + 1] - mesh.offsets[i]) :
                (mesh.connectivity.size() - mesh.offsets[i]);
            total_size += (1 + num_nodes);  // 1 for count, num_nodes for indices
            offset += num_nodes;
        }

        writeLine("CELLS " + std::to_string(num_cells) + " " + std::to_string(total_size));

        for (size_t i = 0; i < num_cells; ++i) {
            size_t start = mesh.offsets[i];
            size_t end = (i < num_cells - 1) ? mesh.offsets[i + 1] : mesh.connectivity.size();
            size_t num_nodes = end - start;

            std::ostringstream oss;
            oss << num_nodes;
            for (size_t j = start; j < end; ++j) {
                oss << " " << mesh.connectivity[j];
            }
            writeLine(oss.str());
        }
        writeLine("");

        // Cell types
        writeLine("CELL_TYPES " + std::to_string(num_cells));
        for (size_t i = 0; i < num_cells; ++i) {
            writeLine(std::to_string(static_cast<int>(mesh.cell_types[i])));
        }
        writeLine("");
    }

    // Point data
    if (!mesh.point_data.empty()) {
        writeLine("POINT_DATA " + std::to_string(num_points));

        for (const auto& array : mesh.point_data) {
            if (array.num_components == 1) {
                // Scalar
                writeLine("SCALARS " + array.name + " float 1");
                writeLine("LOOKUP_TABLE default");
                for (size_t i = 0; i < array.data.size(); ++i) {
                    writeLine(std::to_string(array.data[i]));
                }
            } else if (array.num_components == 3) {
                // Vector
                writeLine("VECTORS " + array.name + " float");
                for (size_t i = 0; i < array.data.size(); i += 3) {
                    std::ostringstream oss;
                    oss << std::fixed << std::setprecision(6)
                        << array.data[i] << " "
                        << array.data[i + 1] << " "
                        << array.data[i + 2];
                    writeLine(oss.str());
                }
            } else if (array.num_components == 6 || array.num_components == 9) {
                // Tensor
                writeLine("TENSORS " + array.name + " float");
                for (size_t i = 0; i < array.data.size(); i += array.num_components) {
                    if (array.num_components == 6) {
                        // Voigt notation → full 3x3 tensor
                        // [Sxx, Syy, Szz, Sxy, Syz, Szx]
                        double sxx = array.data[i];
                        double syy = array.data[i + 1];
                        double szz = array.data[i + 2];
                        double sxy = array.data[i + 3];
                        double syz = array.data[i + 4];
                        double szx = array.data[i + 5];

                        std::ostringstream oss;
                        oss << std::fixed << std::setprecision(6)
                            << sxx << " " << sxy << " " << szx << "\n"
                            << sxy << " " << syy << " " << syz << "\n"
                            << szx << " " << syz << " " << szz;
                        writeLine(oss.str());
                    } else {
                        // Full 3x3 tensor
                        std::ostringstream oss;
                        oss << std::fixed << std::setprecision(6);
                        for (size_t j = 0; j < 3; ++j) {
                            oss << array.data[i + j * 3] << " "
                                << array.data[i + j * 3 + 1] << " "
                                << array.data[i + j * 3 + 2];
                            if (j < 2) oss << "\n";
                        }
                        writeLine(oss.str());
                    }
                }
            }
            writeLine("");
        }
    }

    // Cell data
    if (!mesh.cell_data.empty()) {
        writeLine("CELL_DATA " + std::to_string(num_cells));

        for (const auto& array : mesh.cell_data) {
            if (array.num_components == 1) {
                // Scalar
                writeLine("SCALARS " + array.name + " float 1");
                writeLine("LOOKUP_TABLE default");
                for (size_t i = 0; i < array.data.size(); ++i) {
                    writeLine(std::to_string(array.data[i]));
                }
            } else if (array.num_components == 3) {
                // Vector
                writeLine("VECTORS " + array.name + " float");
                for (size_t i = 0; i < array.data.size(); i += 3) {
                    std::ostringstream oss;
                    oss << std::fixed << std::setprecision(6)
                        << array.data[i] << " "
                        << array.data[i + 1] << " "
                        << array.data[i + 2];
                    writeLine(oss.str());
                }
            } else if (array.num_components == 6 || array.num_components == 9) {
                // Tensor
                writeLine("TENSORS " + array.name + " float");
                for (size_t i = 0; i < array.data.size(); i += array.num_components) {
                    if (array.num_components == 6) {
                        // Voigt notation → full 3x3 tensor
                        double sxx = array.data[i];
                        double syy = array.data[i + 1];
                        double szz = array.data[i + 2];
                        double sxy = array.data[i + 3];
                        double syz = array.data[i + 4];
                        double szx = array.data[i + 5];

                        std::ostringstream oss;
                        oss << std::fixed << std::setprecision(6)
                            << sxx << " " << sxy << " " << szx << "\n"
                            << sxy << " " << syy << " " << syz << "\n"
                            << szx << " " << syz << " " << szz;
                        writeLine(oss.str());
                    } else {
                        // Full 3x3 tensor
                        std::ostringstream oss;
                        oss << std::fixed << std::setprecision(6);
                        for (size_t j = 0; j < 3; ++j) {
                            oss << array.data[i + j * 3] << " "
                                << array.data[i + j * 3 + 1] << " "
                                << array.data[i + j * 3 + 2];
                            if (j < 2) oss << "\n";
                        }
                        writeLine(oss.str());
                    }
                }
            }
            writeLine("");
        }
    }

    file_.close();

    if (options_.verbose) {
        std::cout << "[VtkWriter] Written " << bytes_written_ << " bytes\n";
    }

    return ErrorCode::SUCCESS;
}

void VtkWriter::writeLine(const std::string& line) {
    file_ << line << "\n";
    bytes_written_ += line.size() + 1;
}

std::string VtkWriter::vtkCellTypeToString(VtkCellType type) {
    switch (type) {
        case VtkCellType::VERTEX: return "VERTEX";
        case VtkCellType::LINE: return "LINE";
        case VtkCellType::TRIANGLE: return "TRIANGLE";
        case VtkCellType::QUAD: return "QUAD";
        case VtkCellType::TETRA: return "TETRA";
        case VtkCellType::HEXAHEDRON: return "HEXAHEDRON";
        case VtkCellType::WEDGE: return "WEDGE";
        case VtkCellType::PYRAMID: return "PYRAMID";
        case VtkCellType::QUADRATIC_TETRA: return "QUADRATIC_TETRA";
        case VtkCellType::QUADRATIC_HEXAHEDRON: return "QUADRATIC_HEXAHEDRON";
        default: return "UNKNOWN";
    }
}

} // namespace converter
} // namespace kood3plot
