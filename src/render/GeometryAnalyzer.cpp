/**
 * @file GeometryAnalyzer.cpp
 * @brief Implementation of geometry analysis and section calculation
 */

#include "kood3plot/render/GeometryAnalyzer.h"
#include "kood3plot/render/D3plotCache.h"
#include "kood3plot/D3plotReader.hpp"
#include <algorithm>
#include <sstream>
#include <iomanip>

namespace kood3plot {
namespace render {

// ============================================================
// Bounding Box Calculation
// ============================================================

BoundingBox GeometryAnalyzer::calculateModelBounds(
    D3plotReader& reader,
    size_t state_index)
{
    // Try to get from cache first
    auto& cache = getGlobalCache();
    const std::string& filepath = reader.getFilePath();

    if (cache.hasBoundingBox(filepath, -1, state_index)) {
        return cache.getBoundingBox(filepath, -1, state_index);
    }

    // Cache miss - calculate bounds
    // Read mesh to get node coordinates
    auto mesh = reader.read_mesh();

    if (mesh.nodes.empty()) {
        throw std::runtime_error("No nodes found in mesh");
    }

    std::vector<Point3D> coords;
    coords.reserve(mesh.nodes.size());

    // Extract coordinates from nodes
    for (const auto& node : mesh.nodes) {
        Point3D pt;
        pt[0] = node.x;
        pt[1] = node.y;
        pt[2] = node.z;
        coords.push_back(pt);
    }

    BoundingBox bbox = calculateBoundsFromCoords(coords);

    // Store in cache
    cache.putBoundingBox(filepath, -1, state_index, bbox);

    return bbox;
}

BoundingBox GeometryAnalyzer::calculatePartBounds(
    D3plotReader& reader,
    int part_id,
    size_t state_index)
{
    // If part_id is -1, calculate bounds for entire model
    if (part_id == -1) {
        return calculateModelBounds(reader, state_index);
    }

    // Try to get from cache first
    auto& cache = getGlobalCache();
    const std::string& filepath = reader.getFilePath();

    if (cache.hasBoundingBox(filepath, part_id, state_index)) {
        return cache.getBoundingBox(filepath, part_id, state_index);
    }

    // Cache miss - calculate bounds
    // Read mesh to get geometry data
    auto mesh = reader.read_mesh();

    std::vector<Point3D> coords;

    // Find all solid elements for this part
    for (size_t i = 0; i < mesh.solids.size(); ++i) {
        if (mesh.solid_parts[i] == part_id) {
            // Add coordinates for all nodes of the solid
            for (int32_t node_id : mesh.solids[i].node_ids) {
                // node_id is 1-based, but vector is 0-based
                if (node_id > 0 && static_cast<size_t>(node_id) <= mesh.nodes.size()) {
                    const auto& node = mesh.nodes[node_id - 1];
                    Point3D pt;
                    pt[0] = node.x;
                    pt[1] = node.y;
                    pt[2] = node.z;
                    coords.push_back(pt);
                }
            }
        }
    }

    // Also check shell elements
    for (size_t i = 0; i < mesh.shells.size(); ++i) {
        if (mesh.shell_parts[i] == part_id) {
            // Add coordinates for all nodes of the shell
            for (int32_t node_id : mesh.shells[i].node_ids) {
                if (node_id > 0 && static_cast<size_t>(node_id) <= mesh.nodes.size()) {
                    const auto& node = mesh.nodes[node_id - 1];
                    Point3D pt;
                    pt[0] = node.x;
                    pt[1] = node.y;
                    pt[2] = node.z;
                    coords.push_back(pt);
                }
            }
        }
    }

    if (coords.empty()) {
        throw std::runtime_error("No elements found for part ID: " + std::to_string(part_id));
    }

    BoundingBox bbox = calculateBoundsFromCoords(coords);

    // Store in cache
    cache.putBoundingBox(filepath, part_id, state_index, bbox);

    return bbox;
}

BoundingBox GeometryAnalyzer::calculateBoundsFromCoords(
    const std::vector<Point3D>& coords)
{
    if (coords.empty()) {
        throw std::runtime_error("Cannot calculate bounds from empty coordinate list");
    }

    BoundingBox bbox;

    // Initialize with first point
    bbox.min = coords[0];
    bbox.max = coords[0];

    // Find min/max for each axis
    for (const auto& coord : coords) {
        for (int i = 0; i < 3; ++i) {
            bbox.min[i] = std::min(bbox.min[i], coord[i]);
            bbox.max[i] = std::max(bbox.max[i], coord[i]);
        }
    }

    // Calculate center
    for (int i = 0; i < 3; ++i) {
        bbox.center[i] = (bbox.min[i] + bbox.max[i]) / 2.0;
    }

    return bbox;
}

// ============================================================
// Section Plane Generation
// ============================================================

SectionPlane GeometryAnalyzer::createSectionPlane(
    const BoundingBox& bbox,
    const std::string& orientation,
    SectionPosition position,
    double custom_ratio)
{
    if (!bbox.isValid()) {
        throw std::runtime_error("Invalid bounding box");
    }

    SectionPlane section;

    // Get normal vector
    section.normal = getNormalVector(orientation);

    // Get axis index
    int axis_idx = getAxisIndex(orientation);

    // Calculate ratio
    double ratio = (position == SectionPosition::CUSTOM) ?
                   custom_ratio : getPositionRatio(position);

    // Clamp ratio to [0, 1]
    ratio = std::max(0.0, std::min(1.0, ratio));

    // Calculate base point
    section.point = bbox.center;
    section.point[axis_idx] = bbox.min[axis_idx] +
                               (bbox.max[axis_idx] - bbox.min[axis_idx]) * ratio;

    section.visible = true;

    return section;
}

std::vector<SectionPlane> GeometryAnalyzer::createEvenSections(
    const BoundingBox& bbox,
    const std::string& orientation,
    int num_sections)
{
    if (num_sections < 1) {
        throw std::invalid_argument("Number of sections must be at least 1");
    }

    if (!bbox.isValid()) {
        throw std::runtime_error("Invalid bounding box");
    }

    std::vector<SectionPlane> sections;
    sections.reserve(num_sections);

    Point3D normal = getNormalVector(orientation);
    int axis_idx = getAxisIndex(orientation);

    for (int i = 0; i < num_sections; ++i) {
        SectionPlane section;
        section.normal = normal;
        section.visible = true;

        // Calculate ratio for this section
        double ratio = (num_sections == 1) ? 0.5 :
                       static_cast<double>(i) / (num_sections - 1);

        // Calculate base point
        section.point = bbox.center;
        section.point[axis_idx] = bbox.min[axis_idx] +
                                   (bbox.max[axis_idx] - bbox.min[axis_idx]) * ratio;

        sections.push_back(section);
    }

    return sections;
}

std::vector<SectionPlane> GeometryAnalyzer::createUniformSections(
    const BoundingBox& bbox,
    const std::string& orientation,
    double spacing)
{
    if (spacing <= 0.0) {
        throw std::invalid_argument("Spacing must be positive");
    }

    if (!bbox.isValid()) {
        throw std::runtime_error("Invalid bounding box");
    }

    std::vector<SectionPlane> sections;

    Point3D normal = getNormalVector(orientation);
    int axis_idx = getAxisIndex(orientation);

    double axis_size = bbox.max[axis_idx] - bbox.min[axis_idx];
    int num_sections = static_cast<int>(std::ceil(axis_size / spacing)) + 1;

    for (int i = 0; i < num_sections; ++i) {
        SectionPlane section;
        section.normal = normal;
        section.visible = true;

        // Calculate position
        section.point = bbox.center;
        section.point[axis_idx] = bbox.min[axis_idx] + i * spacing;

        // Stop if we exceed the bounding box
        if (section.point[axis_idx] > bbox.max[axis_idx]) {
            break;
        }

        sections.push_back(section);
    }

    return sections;
}

std::vector<SectionPlane> GeometryAnalyzer::createStandard3Sections(
    const BoundingBox& bbox,
    const std::string& orientation)
{
    std::vector<SectionPlane> sections;
    sections.reserve(3);

    // Quarter 1 (25%)
    sections.push_back(createSectionPlane(bbox, orientation, SectionPosition::QUARTER_1));

    // Center (50%)
    sections.push_back(createSectionPlane(bbox, orientation, SectionPosition::CENTER));

    // Quarter 3 (75%)
    sections.push_back(createSectionPlane(bbox, orientation, SectionPosition::QUARTER_3));

    return sections;
}

std::vector<SectionPlane> GeometryAnalyzer::createOffsetSections(
    const BoundingBox& bbox,
    const std::string& orientation,
    double offset_percent)
{
    if (offset_percent < 0.0 || offset_percent >= 50.0) {
        throw std::invalid_argument("Offset percent must be between 0 and 50");
    }

    std::vector<SectionPlane> sections;
    sections.reserve(2);

    // Convert percentage to ratio
    double ratio_offset = offset_percent / 100.0;

    // Near edge (offset from min)
    sections.push_back(createSectionPlane(bbox, orientation,
                                          SectionPosition::CUSTOM, ratio_offset));

    // Far edge (offset from max)
    sections.push_back(createSectionPlane(bbox, orientation,
                                          SectionPosition::CUSTOM, 1.0 - ratio_offset));

    return sections;
}

// ============================================================
// Utility Functions
// ============================================================

double GeometryAnalyzer::getPositionRatio(SectionPosition position)
{
    switch (position) {
        case SectionPosition::CENTER:
            return 0.5;
        case SectionPosition::QUARTER_1:
            return 0.25;
        case SectionPosition::QUARTER_3:
            return 0.75;
        case SectionPosition::EDGE_MIN:
            return 0.0;
        case SectionPosition::EDGE_MAX:
            return 1.0;
        case SectionPosition::CUSTOM:
            return 0.5;  // Default
        default:
            return 0.5;
    }
}

int GeometryAnalyzer::getAxisIndex(const std::string& orientation)
{
    if (orientation == "X" || orientation == "x") return 0;
    if (orientation == "Y" || orientation == "y") return 1;
    if (orientation == "Z" || orientation == "z") return 2;

    throw std::invalid_argument("Invalid orientation: " + orientation +
                                " (must be X, Y, or Z)");
}

Point3D GeometryAnalyzer::getNormalVector(const std::string& orientation)
{
    Point3D normal;
    if (orientation == "X" || orientation == "x") {
        normal[0] = 1.0; normal[1] = 0.0; normal[2] = 0.0;
    }
    else if (orientation == "Y" || orientation == "y") {
        normal[0] = 0.0; normal[1] = 1.0; normal[2] = 0.0;
    }
    else if (orientation == "Z" || orientation == "z") {
        normal[0] = 0.0; normal[1] = 0.0; normal[2] = 1.0;
    }
    else {
        throw std::invalid_argument("Invalid orientation: " + orientation);
    }
    return normal;
}

std::string GeometryAnalyzer::positionToString(SectionPosition position)
{
    switch (position) {
        case SectionPosition::CENTER:     return "center";
        case SectionPosition::QUARTER_1:  return "quarter_1";
        case SectionPosition::QUARTER_3:  return "quarter_3";
        case SectionPosition::EDGE_MIN:   return "edge_min";
        case SectionPosition::EDGE_MAX:   return "edge_max";
        case SectionPosition::CUSTOM:     return "custom";
        default:                           return "unknown";
    }
}

SectionPosition GeometryAnalyzer::stringToPosition(const std::string& str)
{
    if (str == "center")     return SectionPosition::CENTER;
    if (str == "quarter_1")  return SectionPosition::QUARTER_1;
    if (str == "quarter_3")  return SectionPosition::QUARTER_3;
    if (str == "edge_min")   return SectionPosition::EDGE_MIN;
    if (str == "edge_max")   return SectionPosition::EDGE_MAX;
    if (str == "custom")     return SectionPosition::CUSTOM;

    // Default to center
    return SectionPosition::CENTER;
}

} // namespace render
} // namespace kood3plot
