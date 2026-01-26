/**
 * @file VtkReader.cpp
 * @brief Implementation of VTK file reader
 */

#include "kood3plot/converter/VtkReader.h"
#include <fstream>
#include <sstream>
#include <iostream>
#include <algorithm>
#include <cctype>
#include <cstring>

namespace kood3plot {
namespace converter {

// ============================================================
// Implementation Class
// ============================================================

class VtkReader::Impl {
public:
    std::string filepath;
    VtkReaderOptions options;
    VtkMesh mesh;
    VtkFormat format = VtkFormat::UNKNOWN;
    std::string last_error;

    // Parsing state
    std::ifstream file;
    std::string current_line;
    int line_number = 0;

    // ========================================
    // Format Detection
    // ========================================

    VtkFormat detectFormat() {
        std::ifstream f(filepath, std::ios::binary);
        if (!f.is_open()) {
            last_error = "Cannot open file: " + filepath;
            return VtkFormat::UNKNOWN;
        }

        // Read first 256 bytes to detect format
        char buffer[256];
        f.read(buffer, sizeof(buffer));
        std::string header(buffer, f.gcount());

        // Check for XML VTU format
        if (header.find("<?xml") != std::string::npos ||
            header.find("<VTKFile") != std::string::npos) {
            if (header.find("UnstructuredGrid") != std::string::npos) {
                return VtkFormat::XML_VTU;
            }
        }

        // Check for Legacy VTK format
        if (header.find("# vtk DataFile") != std::string::npos) {
            // Check ASCII vs BINARY
            if (header.find("ASCII") != std::string::npos) {
                return VtkFormat::LEGACY_ASCII;
            } else if (header.find("BINARY") != std::string::npos) {
                return VtkFormat::LEGACY_BINARY;
            }
        }

        // Check for PVD series file
        if (header.find("<VTKFile") != std::string::npos &&
            header.find("Collection") != std::string::npos) {
            return VtkFormat::XML_VTU_SERIES;
        }

        return VtkFormat::UNKNOWN;
    }

    // ========================================
    // Legacy VTK ASCII Parser
    // ========================================

    ErrorCode readLegacyAscii() {
        file.open(filepath);
        if (!file.is_open()) {
            last_error = "Cannot open file: " + filepath;
            return ErrorCode::FILE_NOT_FOUND;
        }

        line_number = 0;

        // Line 1: Version identifier (special case: don't skip # lines)
        if (!std::getline(file, current_line)) return parseError("Unexpected end of file");
        line_number++;
        if (current_line.find("# vtk DataFile") == std::string::npos) {
            return parseError("Invalid VTK header");
        }

        // Line 2: Title
        if (!getNextLine()) return parseError("Missing title");
        mesh.title = current_line;

        // Line 3: Data type (ASCII or BINARY)
        if (!getNextLine()) return parseError("Missing data type");
        if (current_line.find("ASCII") == std::string::npos) {
            return parseError("Expected ASCII format");
        }

        // Line 4: Dataset type
        if (!getNextLine()) return parseError("Missing dataset type");
        std::string dataset_type = toUpper(current_line);

        if (dataset_type.find("UNSTRUCTURED_GRID") != std::string::npos) {
            return readUnstructuredGrid();
        } else if (dataset_type.find("POLYDATA") != std::string::npos) {
            return readPolyData();
        } else if (dataset_type.find("STRUCTURED_POINTS") != std::string::npos) {
            return parseError("STRUCTURED_POINTS not supported, use UNSTRUCTURED_GRID");
        } else {
            return parseError("Unsupported dataset type: " + current_line);
        }
    }

    ErrorCode readUnstructuredGrid() {
        while (getNextLine()) {
            std::string keyword = toUpper(getFirstWord(current_line));

            if (keyword == "POINTS") {
                auto err = readPoints();
                if (err != ErrorCode::SUCCESS) return err;
            }
            else if (keyword == "CELLS") {
                auto err = readCells();
                if (err != ErrorCode::SUCCESS) return err;
            }
            else if (keyword == "CELL_TYPES") {
                auto err = readCellTypes();
                if (err != ErrorCode::SUCCESS) return err;
            }
            else if (keyword == "POINT_DATA") {
                auto err = readPointData();
                if (err != ErrorCode::SUCCESS) return err;
            }
            else if (keyword == "CELL_DATA") {
                auto err = readCellData();
                if (err != ErrorCode::SUCCESS) return err;
            }
            else if (keyword == "FIELD") {
                auto err = readFieldData();
                if (err != ErrorCode::SUCCESS) return err;
            }
        }

        return ErrorCode::SUCCESS;
    }

    ErrorCode readPolyData() {
        // Similar to unstructured grid but with POLYGONS/LINES instead of CELLS
        while (getNextLine()) {
            std::string keyword = toUpper(getFirstWord(current_line));

            if (keyword == "POINTS") {
                auto err = readPoints();
                if (err != ErrorCode::SUCCESS) return err;
            }
            else if (keyword == "POLYGONS" || keyword == "TRIANGLE_STRIPS") {
                auto err = readPolygons();
                if (err != ErrorCode::SUCCESS) return err;
            }
            else if (keyword == "LINES") {
                auto err = readLines();
                if (err != ErrorCode::SUCCESS) return err;
            }
            else if (keyword == "POINT_DATA") {
                auto err = readPointData();
                if (err != ErrorCode::SUCCESS) return err;
            }
            else if (keyword == "CELL_DATA") {
                auto err = readCellData();
                if (err != ErrorCode::SUCCESS) return err;
            }
        }

        return ErrorCode::SUCCESS;
    }

    ErrorCode readPoints() {
        // Format: POINTS n dataType
        std::istringstream iss(current_line);
        std::string keyword;
        size_t num_points;
        std::string data_type;

        iss >> keyword >> num_points >> data_type;

        if (options.verbose) {
            std::cout << "[VtkReader] Reading " << num_points << " points\n";
        }

        mesh.num_points = num_points;
        mesh.points.reserve(num_points * 3);

        size_t values_read = 0;
        while (values_read < num_points * 3 && getNextLine()) {
            std::istringstream line_stream(current_line);
            double value;
            while (line_stream >> value) {
                mesh.points.push_back(value);
                values_read++;
            }
        }

        if (mesh.points.size() != num_points * 3) {
            return parseError("Expected " + std::to_string(num_points * 3) +
                            " point coordinates, got " + std::to_string(mesh.points.size()));
        }

        return ErrorCode::SUCCESS;
    }

    ErrorCode readCells() {
        // Format: CELLS n size
        std::istringstream iss(current_line);
        std::string keyword;
        size_t num_cells, total_size;

        iss >> keyword >> num_cells >> total_size;

        if (options.verbose) {
            std::cout << "[VtkReader] Reading " << num_cells << " cells\n";
        }

        mesh.num_cells = num_cells;
        mesh.connectivity.reserve(total_size);
        mesh.offsets.reserve(num_cells);

        size_t current_offset = 0;
        for (size_t i = 0; i < num_cells; ++i) {
            if (!getNextLine()) {
                return parseError("Unexpected end of file in CELLS section");
            }

            std::istringstream line_stream(current_line);
            int num_pts;
            line_stream >> num_pts;

            mesh.offsets.push_back(static_cast<int32_t>(current_offset + num_pts));

            for (int j = 0; j < num_pts; ++j) {
                int pt_id;
                line_stream >> pt_id;
                mesh.connectivity.push_back(pt_id);
            }
            current_offset += num_pts;
        }

        return ErrorCode::SUCCESS;
    }

    ErrorCode readCellTypes() {
        // Format: CELL_TYPES n
        std::istringstream iss(current_line);
        std::string keyword;
        size_t num_cells;

        iss >> keyword >> num_cells;

        mesh.cell_types.reserve(num_cells);

        size_t types_read = 0;
        while (types_read < num_cells && getNextLine()) {
            std::istringstream line_stream(current_line);
            int cell_type;
            while (line_stream >> cell_type) {
                mesh.cell_types.push_back(cell_type);
                types_read++;
            }
        }

        return ErrorCode::SUCCESS;
    }

    ErrorCode readPolygons() {
        // Format: POLYGONS n size
        std::istringstream iss(current_line);
        std::string keyword;
        size_t num_cells, total_size;

        iss >> keyword >> num_cells >> total_size;

        mesh.num_cells = num_cells;
        mesh.connectivity.reserve(total_size);
        mesh.offsets.reserve(num_cells);
        mesh.cell_types.reserve(num_cells);

        size_t current_offset = 0;
        for (size_t i = 0; i < num_cells; ++i) {
            if (!getNextLine()) {
                return parseError("Unexpected end of file in POLYGONS section");
            }

            std::istringstream line_stream(current_line);
            int num_pts;
            line_stream >> num_pts;

            mesh.offsets.push_back(static_cast<int32_t>(current_offset + num_pts));

            // Determine cell type based on number of vertices
            if (num_pts == 3) {
                mesh.cell_types.push_back(static_cast<int32_t>(VtkCellType::TRIANGLE));
            } else if (num_pts == 4) {
                mesh.cell_types.push_back(static_cast<int32_t>(VtkCellType::QUAD));
            } else {
                mesh.cell_types.push_back(7);  // VTK_POLYGON
            }

            for (int j = 0; j < num_pts; ++j) {
                int pt_id;
                line_stream >> pt_id;
                mesh.connectivity.push_back(pt_id);
            }
            current_offset += num_pts;
        }

        return ErrorCode::SUCCESS;
    }

    ErrorCode readLines() {
        // Format: LINES n size
        std::istringstream iss(current_line);
        std::string keyword;
        size_t num_lines, total_size;

        iss >> keyword >> num_lines >> total_size;

        mesh.num_cells += num_lines;
        mesh.connectivity.reserve(mesh.connectivity.size() + total_size);

        for (size_t i = 0; i < num_lines; ++i) {
            if (!getNextLine()) {
                return parseError("Unexpected end of file in LINES section");
            }

            std::istringstream line_stream(current_line);
            int num_pts;
            line_stream >> num_pts;

            // Line element
            mesh.cell_types.push_back(static_cast<int32_t>(VtkCellType::LINE));

            for (int j = 0; j < num_pts; ++j) {
                int pt_id;
                line_stream >> pt_id;
                mesh.connectivity.push_back(pt_id);
            }
        }

        return ErrorCode::SUCCESS;
    }

    ErrorCode readPointData() {
        if (!options.read_point_data) {
            return skipDataSection();
        }

        // Format: POINT_DATA n
        std::istringstream iss(current_line);
        std::string keyword;
        size_t num_points;
        iss >> keyword >> num_points;

        if (options.verbose) {
            std::cout << "[VtkReader] Reading point data for " << num_points << " points\n";
        }

        return readDataArrays(true, num_points);
    }

    ErrorCode readCellData() {
        if (!options.read_cell_data) {
            return skipDataSection();
        }

        // Format: CELL_DATA n
        std::istringstream iss(current_line);
        std::string keyword;
        size_t num_cells;
        iss >> keyword >> num_cells;

        if (options.verbose) {
            std::cout << "[VtkReader] Reading cell data for " << num_cells << " cells\n";
        }

        return readDataArrays(false, num_cells);
    }

    ErrorCode readDataArrays(bool is_point_data, size_t num_tuples) {
        while (peekNextLine()) {
            std::string keyword = toUpper(getFirstWord(current_line));

            if (keyword == "POINT_DATA" || keyword == "CELL_DATA" ||
                keyword == "POINTS" || keyword == "CELLS") {
                // Start of another section, don't consume line
                break;
            }

            getNextLine();

            if (keyword == "SCALARS") {
                auto err = readScalars(is_point_data, num_tuples);
                if (err != ErrorCode::SUCCESS) return err;
            }
            else if (keyword == "VECTORS") {
                auto err = readVectors(is_point_data, num_tuples);
                if (err != ErrorCode::SUCCESS) return err;
            }
            else if (keyword == "TENSORS") {
                auto err = readTensors(is_point_data, num_tuples);
                if (err != ErrorCode::SUCCESS) return err;
            }
            else if (keyword == "FIELD") {
                auto err = readFieldData();
                if (err != ErrorCode::SUCCESS) return err;
            }
            else if (keyword == "LOOKUP_TABLE") {
                // Skip lookup table
                continue;
            }
        }

        return ErrorCode::SUCCESS;
    }

    ErrorCode readScalars(bool is_point_data, size_t num_tuples) {
        // Format: SCALARS name dataType [numComp]
        std::istringstream iss(current_line);
        std::string keyword, name, data_type;
        int num_comp = 1;

        iss >> keyword >> name >> data_type;
        if (iss >> num_comp) {
            // numComp was provided
        }

        // Skip LOOKUP_TABLE line if present
        if (peekNextLine() && toUpper(getFirstWord(current_line)).find("LOOKUP_TABLE") != std::string::npos) {
            getNextLine();
        }

        if (!shouldReadArray(name)) {
            return skipDataValues(num_tuples * num_comp);
        }

        if (options.verbose) {
            std::cout << "[VtkReader]   SCALARS: " << name << " (" << num_comp << " components)\n";
        }

        VtkDataArray arr;
        arr.name = name;
        arr.num_components = num_comp;
        arr.is_point_data = is_point_data;
        arr.data.reserve(num_tuples * num_comp);

        size_t values_read = 0;
        while (values_read < num_tuples * num_comp && getNextLine()) {
            std::istringstream line_stream(current_line);
            double value;
            while (line_stream >> value) {
                arr.data.push_back(value);
                values_read++;
            }
        }

        if (is_point_data) {
            mesh.point_data.push_back(std::move(arr));
        } else {
            mesh.cell_data.push_back(std::move(arr));
        }

        return ErrorCode::SUCCESS;
    }

    ErrorCode readVectors(bool is_point_data, size_t num_tuples) {
        // Format: VECTORS name dataType
        std::istringstream iss(current_line);
        std::string keyword, name, data_type;
        iss >> keyword >> name >> data_type;

        if (!shouldReadArray(name)) {
            return skipDataValues(num_tuples * 3);
        }

        if (options.verbose) {
            std::cout << "[VtkReader]   VECTORS: " << name << "\n";
        }

        VtkDataArray arr;
        arr.name = name;
        arr.num_components = 3;
        arr.is_point_data = is_point_data;
        arr.data.reserve(num_tuples * 3);

        size_t values_read = 0;
        while (values_read < num_tuples * 3 && getNextLine()) {
            std::istringstream line_stream(current_line);
            double value;
            while (line_stream >> value) {
                arr.data.push_back(value);
                values_read++;
            }
        }

        if (is_point_data) {
            mesh.point_data.push_back(std::move(arr));
        } else {
            mesh.cell_data.push_back(std::move(arr));
        }

        return ErrorCode::SUCCESS;
    }

    ErrorCode readTensors(bool is_point_data, size_t num_tuples) {
        // Format: TENSORS name dataType
        std::istringstream iss(current_line);
        std::string keyword, name, data_type;
        iss >> keyword >> name >> data_type;

        if (!shouldReadArray(name)) {
            return skipDataValues(num_tuples * 9);
        }

        if (options.verbose) {
            std::cout << "[VtkReader]   TENSORS: " << name << "\n";
        }

        VtkDataArray arr;
        arr.name = name;
        arr.num_components = 9;  // 3x3 tensor
        arr.is_point_data = is_point_data;
        arr.data.reserve(num_tuples * 9);

        size_t values_read = 0;
        while (values_read < num_tuples * 9 && getNextLine()) {
            std::istringstream line_stream(current_line);
            double value;
            while (line_stream >> value) {
                arr.data.push_back(value);
                values_read++;
            }
        }

        if (is_point_data) {
            mesh.point_data.push_back(std::move(arr));
        } else {
            mesh.cell_data.push_back(std::move(arr));
        }

        return ErrorCode::SUCCESS;
    }

    ErrorCode readFieldData() {
        // Format: FIELD name numArrays
        std::istringstream iss(current_line);
        std::string keyword, name;
        int num_arrays;
        iss >> keyword >> name >> num_arrays;

        for (int i = 0; i < num_arrays; ++i) {
            if (!getNextLine()) break;

            // Format: arrayName numComponents numTuples dataType
            std::istringstream arr_iss(current_line);
            std::string arr_name, data_type;
            int num_comp, num_tuples;
            arr_iss >> arr_name >> num_comp >> num_tuples >> data_type;

            // Check for time field
            if (toUpper(arr_name) == "TIME" || toUpper(arr_name) == "TIMESTEP") {
                if (getNextLine()) {
                    std::istringstream time_iss(current_line);
                    time_iss >> mesh.time;
                }
                continue;
            }

            // Skip array data
            skipDataValues(num_comp * num_tuples);
        }

        return ErrorCode::SUCCESS;
    }

    // ========================================
    // XML VTU Parser (simplified)
    // ========================================

    ErrorCode readXmlVtu() {
        // Simple XML parser for VTU format
        file.open(filepath);
        if (!file.is_open()) {
            last_error = "Cannot open file: " + filepath;
            return ErrorCode::FILE_NOT_FOUND;
        }

        std::stringstream buffer;
        buffer << file.rdbuf();
        std::string content = buffer.str();

        // Extract number of points and cells from header
        size_t piece_pos = content.find("<Piece");
        if (piece_pos == std::string::npos) {
            return parseError("Cannot find <Piece> element");
        }

        // Parse NumberOfPoints and NumberOfCells
        mesh.num_points = extractAttribute<size_t>(content, piece_pos, "NumberOfPoints");
        mesh.num_cells = extractAttribute<size_t>(content, piece_pos, "NumberOfCells");

        if (options.verbose) {
            std::cout << "[VtkReader] VTU file: " << mesh.num_points << " points, "
                      << mesh.num_cells << " cells\n";
        }

        // Read Points
        auto err = readXmlDataArray(content, "<Points>", "</Points>", mesh.points, mesh.num_points * 3);
        if (err != ErrorCode::SUCCESS) return err;

        // Read Cells connectivity
        err = readXmlCells(content);
        if (err != ErrorCode::SUCCESS) return err;

        // Read PointData
        if (options.read_point_data) {
            readXmlPointData(content);
        }

        // Read CellData
        if (options.read_cell_data) {
            readXmlCellData(content);
        }

        return ErrorCode::SUCCESS;
    }

    ErrorCode readXmlCells(const std::string& content) {
        size_t cells_start = content.find("<Cells>");
        size_t cells_end = content.find("</Cells>");
        if (cells_start == std::string::npos || cells_end == std::string::npos) {
            return parseError("Cannot find <Cells> section");
        }

        std::string cells_section = content.substr(cells_start, cells_end - cells_start);

        // Find connectivity DataArray
        std::vector<int32_t> connectivity_raw;
        readXmlIntDataArray(cells_section, "connectivity", connectivity_raw);
        mesh.connectivity = std::move(connectivity_raw);

        // Find offsets DataArray
        readXmlIntDataArray(cells_section, "offsets", mesh.offsets);

        // Find types DataArray
        readXmlIntDataArray(cells_section, "types", mesh.cell_types);

        return ErrorCode::SUCCESS;
    }

    void readXmlPointData(const std::string& content) {
        size_t pd_start = content.find("<PointData");
        size_t pd_end = content.find("</PointData>");
        if (pd_start == std::string::npos || pd_end == std::string::npos) return;

        std::string pd_section = content.substr(pd_start, pd_end - pd_start);
        readXmlDataArrays(pd_section, true);
    }

    void readXmlCellData(const std::string& content) {
        size_t cd_start = content.find("<CellData");
        size_t cd_end = content.find("</CellData>");
        if (cd_start == std::string::npos || cd_end == std::string::npos) return;

        std::string cd_section = content.substr(cd_start, cd_end - cd_start);
        readXmlDataArrays(cd_section, false);
    }

    void readXmlDataArrays(const std::string& section, bool is_point_data) {
        size_t pos = 0;
        while ((pos = section.find("<DataArray", pos)) != std::string::npos) {
            size_t end_tag = section.find(">", pos);
            size_t close_tag = section.find("</DataArray>", end_tag);
            if (close_tag == std::string::npos) break;

            std::string header = section.substr(pos, end_tag - pos);
            std::string data_content = section.substr(end_tag + 1, close_tag - end_tag - 1);

            // Extract Name attribute
            std::string name = extractStringAttribute(header, "Name");
            if (name.empty()) {
                pos = close_tag;
                continue;
            }

            if (!shouldReadArray(name)) {
                pos = close_tag;
                continue;
            }

            // Extract NumberOfComponents
            int num_comp = extractAttribute<int>(header, 0, "NumberOfComponents");
            if (num_comp == 0) num_comp = 1;

            if (options.verbose) {
                std::cout << "[VtkReader]   DataArray: " << name << " (" << num_comp << " components)\n";
            }

            VtkDataArray arr;
            arr.name = name;
            arr.num_components = num_comp;
            arr.is_point_data = is_point_data;

            // Parse data values
            std::istringstream iss(data_content);
            double value;
            while (iss >> value) {
                arr.data.push_back(value);
            }

            if (is_point_data) {
                mesh.point_data.push_back(std::move(arr));
            } else {
                mesh.cell_data.push_back(std::move(arr));
            }

            pos = close_tag;
        }
    }

    // ========================================
    // Helper Functions
    // ========================================

    bool getNextLine() {
        while (std::getline(file, current_line)) {
            line_number++;
            // Trim whitespace
            size_t start = current_line.find_first_not_of(" \t\r\n");
            if (start == std::string::npos) continue;  // Skip empty lines
            size_t end = current_line.find_last_not_of(" \t\r\n");
            current_line = current_line.substr(start, end - start + 1);
            if (current_line.empty() || current_line[0] == '#') continue;  // Skip comments
            return true;
        }
        return false;
    }

    bool peekNextLine() {
        auto pos = file.tellg();
        bool result = getNextLine();
        file.seekg(pos);
        return result;
    }

    ErrorCode skipDataSection() {
        while (getNextLine()) {
            std::string keyword = toUpper(getFirstWord(current_line));
            if (keyword == "POINT_DATA" || keyword == "CELL_DATA" ||
                keyword == "POINTS" || keyword == "CELLS") {
                break;
            }
        }
        return ErrorCode::SUCCESS;
    }

    ErrorCode skipDataValues(size_t count) {
        size_t values_skipped = 0;
        while (values_skipped < count && getNextLine()) {
            std::istringstream iss(current_line);
            double value;
            while (iss >> value) {
                values_skipped++;
            }
        }
        return ErrorCode::SUCCESS;
    }

    bool shouldReadArray(const std::string& name) {
        if (options.array_filter.empty()) return true;
        for (const auto& filter : options.array_filter) {
            if (toUpper(name).find(toUpper(filter)) != std::string::npos) {
                return true;
            }
        }
        return false;
    }

    ErrorCode parseError(const std::string& msg) {
        last_error = "Parse error at line " + std::to_string(line_number) + ": " + msg;
        return ErrorCode::INVALID_FORMAT;
    }

    static std::string toUpper(const std::string& s) {
        std::string result = s;
        std::transform(result.begin(), result.end(), result.begin(), ::toupper);
        return result;
    }

    static std::string getFirstWord(const std::string& line) {
        size_t end = line.find_first_of(" \t");
        return line.substr(0, end);
    }

    template<typename T>
    static T extractAttribute(const std::string& content, size_t start, const std::string& attr) {
        std::string search = attr + "=\"";
        size_t pos = content.find(search, start);
        if (pos == std::string::npos) return T();

        pos += search.length();
        size_t end = content.find("\"", pos);
        if (end == std::string::npos) return T();

        std::string value = content.substr(pos, end - pos);
        std::istringstream iss(value);
        T result;
        iss >> result;
        return result;
    }

    static std::string extractStringAttribute(const std::string& content, const std::string& attr) {
        std::string search = attr + "=\"";
        size_t pos = content.find(search);
        if (pos == std::string::npos) return "";

        pos += search.length();
        size_t end = content.find("\"", pos);
        if (end == std::string::npos) return "";

        return content.substr(pos, end - pos);
    }

    ErrorCode readXmlDataArray(const std::string& content,
                               const std::string& start_tag,
                               const std::string& end_tag,
                               std::vector<double>& data,
                               size_t expected_count) {
        size_t start = content.find(start_tag);
        size_t end = content.find(end_tag);
        if (start == std::string::npos || end == std::string::npos) {
            return parseError("Cannot find " + start_tag + " section");
        }

        std::string section = content.substr(start, end - start);

        // Find DataArray within section
        size_t da_start = section.find("<DataArray");
        if (da_start == std::string::npos) {
            return parseError("Cannot find DataArray in " + start_tag);
        }

        size_t da_content_start = section.find(">", da_start) + 1;
        size_t da_end = section.find("</DataArray>");

        std::string data_content = section.substr(da_content_start, da_end - da_content_start);

        data.reserve(expected_count);
        std::istringstream iss(data_content);
        double value;
        while (iss >> value) {
            data.push_back(value);
        }

        return ErrorCode::SUCCESS;
    }

    void readXmlIntDataArray(const std::string& section,
                             const std::string& name,
                             std::vector<int32_t>& data) {
        std::string search = "Name=\"" + name + "\"";
        size_t pos = section.find(search);
        if (pos == std::string::npos) return;

        size_t da_content_start = section.find(">", pos) + 1;
        size_t da_end = section.find("</DataArray>", da_content_start);

        std::string data_content = section.substr(da_content_start, da_end - da_content_start);

        std::istringstream iss(data_content);
        int32_t value;
        while (iss >> value) {
            data.push_back(value);
        }
    }
};

// ============================================================
// VtkReader Public Methods
// ============================================================

VtkReader::VtkReader(const std::string& filepath)
    : pImpl(std::make_unique<Impl>())
{
    pImpl->filepath = filepath;
}

VtkReader::~VtkReader() = default;

VtkReader::VtkReader(VtkReader&&) noexcept = default;
VtkReader& VtkReader::operator=(VtkReader&&) noexcept = default;

void VtkReader::setOptions(const VtkReaderOptions& options) {
    pImpl->options = options;
}

VtkFormat VtkReader::detectFormat() {
    pImpl->format = pImpl->detectFormat();
    return pImpl->format;
}

ErrorCode VtkReader::read() {
    if (pImpl->format == VtkFormat::UNKNOWN) {
        detectFormat();
    }

    switch (pImpl->format) {
        case VtkFormat::LEGACY_ASCII:
            return pImpl->readLegacyAscii();

        case VtkFormat::XML_VTU:
            return pImpl->readXmlVtu();

        case VtkFormat::LEGACY_BINARY:
            pImpl->last_error = "Legacy binary VTK format not yet supported";
            return ErrorCode::INVALID_FORMAT;

        case VtkFormat::XML_VTU_SERIES:
            pImpl->last_error = "Use readPvdSeries() for VTU series files";
            return ErrorCode::INVALID_FORMAT;

        default:
            pImpl->last_error = "Unknown VTK format";
            return ErrorCode::INVALID_FORMAT;
    }
}

const VtkMesh& VtkReader::getMesh() const {
    return pImpl->mesh;
}

std::string VtkReader::getLastError() const {
    return pImpl->last_error;
}

std::vector<std::string> VtkReader::getPointDataArrayNames() const {
    std::vector<std::string> names;
    for (const auto& arr : pImpl->mesh.point_data) {
        names.push_back(arr.name);
    }
    return names;
}

std::vector<std::string> VtkReader::getCellDataArrayNames() const {
    std::vector<std::string> names;
    for (const auto& arr : pImpl->mesh.cell_data) {
        names.push_back(arr.name);
    }
    return names;
}

std::vector<VtkMesh> VtkReader::readSeries(
    const std::vector<std::string>& filepaths,
    const VtkReaderOptions& options)
{
    std::vector<VtkMesh> meshes;
    meshes.reserve(filepaths.size());

    for (size_t i = 0; i < filepaths.size(); ++i) {
        VtkReader reader(filepaths[i]);
        reader.setOptions(options);

        if (reader.read() == ErrorCode::SUCCESS) {
            VtkMesh mesh = reader.getMesh();
            if (mesh.time == 0.0) {
                mesh.time = static_cast<double>(i);  // Use index as time if not set
            }
            meshes.push_back(std::move(mesh));
        }
    }

    return meshes;
}

std::vector<VtkMesh> VtkReader::readPvdSeries(
    const std::string& pvd_path,
    const VtkReaderOptions& options)
{
    // Parse PVD file to get list of VTU files and times
    std::ifstream file(pvd_path);
    if (!file.is_open()) {
        return {};
    }

    std::vector<std::pair<double, std::string>> files_with_times;

    std::string line;
    while (std::getline(file, line)) {
        // Look for DataSet elements
        if (line.find("<DataSet") != std::string::npos) {
            // Extract timestep
            double time = 0.0;
            size_t time_pos = line.find("timestep=\"");
            if (time_pos != std::string::npos) {
                time_pos += 10;
                size_t time_end = line.find("\"", time_pos);
                std::string time_str = line.substr(time_pos, time_end - time_pos);
                time = std::stod(time_str);
            }

            // Extract file path
            size_t file_pos = line.find("file=\"");
            if (file_pos != std::string::npos) {
                file_pos += 6;
                size_t file_end = line.find("\"", file_pos);
                std::string filepath = line.substr(file_pos, file_end - file_pos);

                // Make path relative to PVD file location
                size_t last_slash = pvd_path.find_last_of("/\\");
                if (last_slash != std::string::npos) {
                    filepath = pvd_path.substr(0, last_slash + 1) + filepath;
                }

                files_with_times.emplace_back(time, filepath);
            }
        }
    }

    // Sort by time
    std::sort(files_with_times.begin(), files_with_times.end());

    // Read each file
    std::vector<VtkMesh> meshes;
    for (const auto& [time, filepath] : files_with_times) {
        VtkReader reader(filepath);
        reader.setOptions(options);

        if (reader.read() == ErrorCode::SUCCESS) {
            VtkMesh mesh = reader.getMesh();
            mesh.time = time;
            meshes.push_back(std::move(mesh));
        }
    }

    return meshes;
}

} // namespace converter
} // namespace kood3plot
