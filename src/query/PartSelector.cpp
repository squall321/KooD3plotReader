/**
 * @file PartSelector.cpp
 * @brief Implementation of PartSelector class
 * @author KooD3plot V3 Development Team
 * @date 2025-11-21
 * @version 3.0.0
 */

#include "kood3plot/query/PartSelector.h"
#include <regex>
#include <algorithm>
#include <sstream>
#include <cmath>
#include <set>
#include <map>

namespace kood3plot {
namespace query {

// ============================================================
// Data Extraction Implementations
// ============================================================

namespace {

/**
 * @brief Get part map from reader
 *
 * Creates a mapping from part ID to part name. Since d3plot files typically
 * don't store part names directly, we generate default names "Part_N".
 * Part names would come from the keyword file (*PART) if available.
 *
 * @param reader D3plot reader
 * @return Map of part ID to part name
 */
std::map<int32_t, std::string> getPartMap(const kood3plot::D3plotReader& reader) {
    // Note: We use const_cast because read_mesh() is logically const
    // (it may cache the mesh internally but doesn't change the file)
    auto& mutable_reader = const_cast<kood3plot::D3plotReader&>(reader);
    std::map<int32_t, std::string> part_map;

    // Read mesh to get part information
    auto mesh = mutable_reader.read_mesh();

    // Collect unique part IDs from all element types
    std::set<int32_t> unique_parts;

    for (int32_t pid : mesh.solid_parts) {
        unique_parts.insert(pid);
    }
    for (int32_t pid : mesh.shell_parts) {
        unique_parts.insert(pid);
    }
    for (int32_t pid : mesh.beam_parts) {
        unique_parts.insert(pid);
    }
    for (int32_t pid : mesh.thick_shell_parts) {
        unique_parts.insert(pid);
    }

    // Generate part names (d3plot doesn't contain part names, so we use IDs)
    for (int32_t pid : unique_parts) {
        part_map[pid] = "Part_" + std::to_string(pid);
    }

    return part_map;
}

/**
 * @brief Get all part IDs from reader
 *
 * Extracts all unique part IDs from the mesh data by collecting
 * part IDs from all element types (solids, shells, beams, thick shells).
 *
 * @param reader D3plot reader
 * @return Set of all part IDs
 */
std::set<int32_t> getAllPartIdsFromReader(const kood3plot::D3plotReader& reader) {
    auto& mutable_reader = const_cast<kood3plot::D3plotReader&>(reader);
    std::set<int32_t> all_ids;

    // Read mesh to get part information
    auto mesh = mutable_reader.read_mesh();

    // Collect from all element types
    for (int32_t pid : mesh.solid_parts) {
        all_ids.insert(pid);
    }
    for (int32_t pid : mesh.shell_parts) {
        all_ids.insert(pid);
    }
    for (int32_t pid : mesh.beam_parts) {
        all_ids.insert(pid);
    }
    for (int32_t pid : mesh.thick_shell_parts) {
        all_ids.insert(pid);
    }

    return all_ids;
}

/**
 * @brief Get element IDs belonging to a specific part
 *
 * @param reader D3plot reader
 * @param part_id Target part ID
 * @return Vector of element IDs (real IDs from NARBS)
 */
std::vector<int32_t> getElementsForPart(const kood3plot::D3plotReader& reader, int32_t part_id) {
    auto& mutable_reader = const_cast<kood3plot::D3plotReader&>(reader);
    std::vector<int32_t> element_ids;

    auto mesh = mutable_reader.read_mesh();

    // Collect solid elements for this part
    for (size_t i = 0; i < mesh.solid_parts.size(); ++i) {
        if (mesh.solid_parts[i] == part_id) {
            if (i < mesh.real_solid_ids.size()) {
                element_ids.push_back(mesh.real_solid_ids[i]);
            } else if (i < mesh.solids.size()) {
                element_ids.push_back(mesh.solids[i].id);
            }
        }
    }

    // Collect shell elements for this part
    for (size_t i = 0; i < mesh.shell_parts.size(); ++i) {
        if (mesh.shell_parts[i] == part_id) {
            if (i < mesh.real_shell_ids.size()) {
                element_ids.push_back(mesh.real_shell_ids[i]);
            } else if (i < mesh.shells.size()) {
                element_ids.push_back(mesh.shells[i].id);
            }
        }
    }

    // Collect beam elements for this part
    for (size_t i = 0; i < mesh.beam_parts.size(); ++i) {
        if (mesh.beam_parts[i] == part_id) {
            if (i < mesh.real_beam_ids.size()) {
                element_ids.push_back(mesh.real_beam_ids[i]);
            } else if (i < mesh.beams.size()) {
                element_ids.push_back(mesh.beams[i].id);
            }
        }
    }

    // Collect thick shell elements for this part
    for (size_t i = 0; i < mesh.thick_shell_parts.size(); ++i) {
        if (mesh.thick_shell_parts[i] == part_id) {
            if (i < mesh.real_thick_shell_ids.size()) {
                element_ids.push_back(mesh.real_thick_shell_ids[i]);
            } else if (i < mesh.thick_shells.size()) {
                element_ids.push_back(mesh.thick_shells[i].id);
            }
        }
    }

    return element_ids;
}

} // anonymous namespace

// ============================================================
// PIMPL Implementation Struct
// ============================================================

/**
 * @brief Implementation details for PartSelector
 *
 * This struct contains all the internal state and selection criteria.
 * Using PIMPL pattern provides:
 * - Reduced compilation dependencies
 * - Binary compatibility
 * - Cleaner header interface
 */
struct PartSelector::Impl {
    // Selection criteria
    std::set<int32_t> selected_ids;                  ///< Explicitly selected part IDs
    std::vector<std::string> selected_names;         ///< Selected part names
    std::vector<std::string> glob_patterns;          ///< Glob patterns
    std::vector<std::string> regex_patterns;         ///< Regex patterns
    std::set<int32_t> selected_materials;            ///< Selected material IDs
    std::vector<PropertyFilter> property_filters;    ///< Property filters

    // State flags
    bool select_all_parts = false;       ///< Select all parts flag
    bool select_no_parts = false;        ///< Select no parts flag
    bool inverted = false;                ///< Invert selection flag
    bool has_explicit_ids = false;        ///< Has explicit IDs set

    /**
     * @brief Clear all selection criteria
     */
    void clear() {
        selected_ids.clear();
        selected_names.clear();
        glob_patterns.clear();
        regex_patterns.clear();
        selected_materials.clear();
        property_filters.clear();
        select_all_parts = false;
        select_no_parts = false;
        inverted = false;
        has_explicit_ids = false;
    }
};

// ============================================================
// Constructors and Destructor
// ============================================================

PartSelector::PartSelector()
    : pImpl(std::make_unique<Impl>())
{
}

PartSelector::PartSelector(const PartSelector& other)
    : pImpl(std::make_unique<Impl>(*other.pImpl))
{
}

PartSelector::PartSelector(PartSelector&& other) noexcept
    : pImpl(std::move(other.pImpl))
{
}

PartSelector& PartSelector::operator=(const PartSelector& other) {
    if (this != &other) {
        pImpl = std::make_unique<Impl>(*other.pImpl);
    }
    return *this;
}

PartSelector& PartSelector::operator=(PartSelector&& other) noexcept {
    if (this != &other) {
        pImpl = std::move(other.pImpl);
    }
    return *this;
}

PartSelector::~PartSelector() = default;

// ============================================================
// Selection by ID
// ============================================================

PartSelector& PartSelector::byId(int32_t id) {
    pImpl->selected_ids.insert(id);
    pImpl->select_no_parts = false;
    return *this;
}

PartSelector& PartSelector::byId(const std::vector<int32_t>& ids) {
    pImpl->selected_ids.insert(ids.begin(), ids.end());
    pImpl->select_no_parts = false;
    return *this;
}

// ============================================================
// Selection by Name
// ============================================================

PartSelector& PartSelector::byName(const std::string& name) {
    pImpl->selected_names.push_back(name);
    pImpl->select_no_parts = false;
    return *this;
}

PartSelector& PartSelector::byName(const std::vector<std::string>& names) {
    pImpl->selected_names.insert(pImpl->selected_names.end(),
                                  names.begin(), names.end());
    pImpl->select_no_parts = false;
    return *this;
}

// ============================================================
// Selection by Pattern
// ============================================================

PartSelector& PartSelector::byPattern(const std::string& pattern, PatternType type) {
    if (type == PatternType::GLOB) {
        pImpl->glob_patterns.push_back(pattern);
    } else {
        pImpl->regex_patterns.push_back(pattern);
    }
    pImpl->select_no_parts = false;
    return *this;
}

PartSelector& PartSelector::byPattern(const std::vector<std::string>& patterns,
                                     PatternType type) {
    if (type == PatternType::GLOB) {
        pImpl->glob_patterns.insert(pImpl->glob_patterns.end(),
                                    patterns.begin(), patterns.end());
    } else {
        pImpl->regex_patterns.insert(pImpl->regex_patterns.end(),
                                     patterns.begin(), patterns.end());
    }
    pImpl->select_no_parts = false;
    return *this;
}

// ============================================================
// Selection by Material
// ============================================================

PartSelector& PartSelector::byMaterial(int32_t material_id) {
    pImpl->selected_materials.insert(material_id);
    pImpl->select_no_parts = false;
    return *this;
}

PartSelector& PartSelector::byMaterial(const std::vector<int32_t>& material_ids) {
    pImpl->selected_materials.insert(material_ids.begin(), material_ids.end());
    pImpl->select_no_parts = false;
    return *this;
}

// ============================================================
// Selection by Property
// ============================================================

PartSelector& PartSelector::byProperty(const PropertyFilter& filter) {
    pImpl->property_filters.push_back(filter);
    pImpl->select_no_parts = false;
    return *this;
}

// ============================================================
// Logical Operations
// ============================================================

PartSelector PartSelector::operator&&(const PartSelector& other) const {
    // For now, we'll create a new selector that will evaluate both
    // and return the intersection. This is a simplified implementation.
    PartSelector result;

    // Combine explicit IDs (intersection)
    result.pImpl->selected_ids = intersect(pImpl->selected_ids,
                                           other.pImpl->selected_ids);

    // If both have explicit IDs, use their intersection
    if (!pImpl->selected_ids.empty() && !other.pImpl->selected_ids.empty()) {
        result.pImpl->has_explicit_ids = true;
    }

    return result;
}

PartSelector PartSelector::operator||(const PartSelector& other) const {
    PartSelector result;

    // Combine explicit IDs (union)
    result.pImpl->selected_ids = unite(pImpl->selected_ids,
                                       other.pImpl->selected_ids);

    // Combine names
    result.pImpl->selected_names = pImpl->selected_names;
    result.pImpl->selected_names.insert(result.pImpl->selected_names.end(),
                                       other.pImpl->selected_names.begin(),
                                       other.pImpl->selected_names.end());

    // Combine patterns
    result.pImpl->glob_patterns = pImpl->glob_patterns;
    result.pImpl->glob_patterns.insert(result.pImpl->glob_patterns.end(),
                                      other.pImpl->glob_patterns.begin(),
                                      other.pImpl->glob_patterns.end());

    result.pImpl->regex_patterns = pImpl->regex_patterns;
    result.pImpl->regex_patterns.insert(result.pImpl->regex_patterns.end(),
                                       other.pImpl->regex_patterns.begin(),
                                       other.pImpl->regex_patterns.end());

    // Combine materials
    result.pImpl->selected_materials = unite(pImpl->selected_materials,
                                            other.pImpl->selected_materials);

    return result;
}

PartSelector PartSelector::operator!() const {
    PartSelector result(*this);
    result.pImpl->inverted = !result.pImpl->inverted;
    return result;
}

// ============================================================
// Special Selectors
// ============================================================

PartSelector& PartSelector::selectAll() {
    pImpl->clear();
    pImpl->select_all_parts = true;
    return *this;
}

PartSelector& PartSelector::selectNone() {
    pImpl->clear();
    pImpl->select_no_parts = true;
    return *this;
}

PartSelector PartSelector::all() {
    PartSelector selector;
    selector.selectAll();
    return selector;
}

PartSelector PartSelector::none() {
    PartSelector selector;
    selector.selectNone();
    return selector;
}

// ============================================================
// Evaluation
// ============================================================

std::vector<int32_t> PartSelector::evaluate(const D3plotReader& reader) const {
    // Handle special cases first
    if (pImpl->select_no_parts) {
        return {};
    }

    std::set<int32_t> result_set;

    if (pImpl->select_all_parts) {
        result_set = getAllPartIds(reader);
    } else if (pImpl->has_explicit_ids && pImpl->selected_ids.size() > 0) {
        // Use explicit IDs if set
        result_set = pImpl->selected_ids;
    } else {
        // Accumulate from all selection criteria

        // Add by ID
        if (!pImpl->selected_ids.empty()) {
            result_set.insert(pImpl->selected_ids.begin(),
                            pImpl->selected_ids.end());
        }

        // Add by name
        if (!pImpl->selected_names.empty()) {
            auto part_map = getPartMap(reader);  // Phase 1 stub
            for (const auto& name : pImpl->selected_names) {
                for (const auto& [id, part_name] : part_map) {
                    if (part_name == name) {
                        result_set.insert(id);
                    }
                }
            }
        }

        // Add by glob patterns
        if (!pImpl->glob_patterns.empty()) {
            auto part_map = getPartMap(reader);  // Phase 1 stub
            for (const auto& pattern : pImpl->glob_patterns) {
                for (const auto& [id, part_name] : part_map) {
                    if (matchPattern(part_name, pattern, PatternType::GLOB)) {
                        result_set.insert(id);
                    }
                }
            }
        }

        // Add by regex patterns
        if (!pImpl->regex_patterns.empty()) {
            auto part_map = getPartMap(reader);  // Phase 1 stub
            for (const auto& pattern : pImpl->regex_patterns) {
                for (const auto& [id, part_name] : part_map) {
                    if (matchPattern(part_name, pattern, PatternType::REGEX)) {
                        result_set.insert(id);
                    }
                }
            }
        }

        // Add by material
        if (!pImpl->selected_materials.empty()) {
            auto part_map = getPartMap(reader);  // Phase 1 stub
            for (const auto& [id, part_name] : part_map) {
                // TODO Phase 2: Get material ID for part from reader
                // For now, we'll skip this as it requires material info
                // which might not be readily available in current GeometryData
            }
        }

        // Filter by properties
        if (!pImpl->property_filters.empty()) {
            std::set<int32_t> filtered_ids;
            auto all_ids = result_set.empty() ? getAllPartIds(reader) : result_set;

            for (int32_t id : all_ids) {
                bool matches_all_filters = true;
                for (const auto& filter : pImpl->property_filters) {
                    if (!matchesPropertyFilter(reader, id, filter)) {
                        matches_all_filters = false;
                        break;
                    }
                }
                if (matches_all_filters) {
                    filtered_ids.insert(id);
                }
            }
            result_set = filtered_ids;
        }

        // If no criteria were specified, default to no selection
        if (result_set.empty() &&
            pImpl->selected_ids.empty() &&
            pImpl->selected_names.empty() &&
            pImpl->glob_patterns.empty() &&
            pImpl->regex_patterns.empty() &&
            pImpl->selected_materials.empty() &&
            pImpl->property_filters.empty()) {
            return {};
        }
    }

    // Apply inversion if needed
    if (pImpl->inverted) {
        auto all_ids = getAllPartIds(reader);
        std::set<int32_t> inverted_set;
        std::set_difference(all_ids.begin(), all_ids.end(),
                          result_set.begin(), result_set.end(),
                          std::inserter(inverted_set, inverted_set.begin()));
        result_set = inverted_set;
    }

    // Convert to vector
    return std::vector<int32_t>(result_set.begin(), result_set.end());
}

std::vector<std::string> PartSelector::evaluateNames(const D3plotReader& reader) const {
    auto ids = evaluate(reader);
    auto part_map = getPartMap(reader);  // Phase 1 stub

    std::vector<std::string> names;
    names.reserve(ids.size());

    for (int32_t id : ids) {
        auto it = part_map.find(id);
        if (it != part_map.end()) {
            names.push_back(it->second);
        }
    }

    return names;
}

size_t PartSelector::count(const D3plotReader& reader) const {
    return evaluate(reader).size();
}

bool PartSelector::hasMatches(const D3plotReader& reader) const {
    return count(reader) > 0;
}

// ============================================================
// Query State
// ============================================================

bool PartSelector::isAll() const {
    return pImpl->select_all_parts && !pImpl->inverted;
}

bool PartSelector::isNone() const {
    return pImpl->select_no_parts ||
           (pImpl->select_all_parts && pImpl->inverted);
}

bool PartSelector::isInverted() const {
    return pImpl->inverted;
}

std::string PartSelector::getDescription() const {
    std::ostringstream oss;

    if (pImpl->select_all_parts) {
        oss << "All parts";
    } else if (pImpl->select_no_parts) {
        oss << "No parts";
    } else {
        std::vector<std::string> criteria;

        if (!pImpl->selected_ids.empty()) {
            oss << "IDs: [";
            bool first = true;
            for (int32_t id : pImpl->selected_ids) {
                if (!first) oss << ", ";
                oss << id;
                first = false;
            }
            oss << "]";
            criteria.push_back(oss.str());
            oss.str("");
        }

        if (!pImpl->selected_names.empty()) {
            oss << "Names: [";
            for (size_t i = 0; i < pImpl->selected_names.size(); ++i) {
                if (i > 0) oss << ", ";
                oss << pImpl->selected_names[i];
            }
            oss << "]";
            criteria.push_back(oss.str());
            oss.str("");
        }

        if (!pImpl->glob_patterns.empty()) {
            oss << "Glob: [";
            for (size_t i = 0; i < pImpl->glob_patterns.size(); ++i) {
                if (i > 0) oss << ", ";
                oss << pImpl->glob_patterns[i];
            }
            oss << "]";
            criteria.push_back(oss.str());
            oss.str("");
        }

        if (!pImpl->regex_patterns.empty()) {
            oss << "Regex: [";
            for (size_t i = 0; i < pImpl->regex_patterns.size(); ++i) {
                if (i > 0) oss << ", ";
                oss << pImpl->regex_patterns[i];
            }
            oss << "]";
            criteria.push_back(oss.str());
            oss.str("");
        }

        if (!pImpl->selected_materials.empty()) {
            oss << "Materials: [";
            bool first = true;
            for (int32_t id : pImpl->selected_materials) {
                if (!first) oss << ", ";
                oss << id;
                first = false;
            }
            oss << "]";
            criteria.push_back(oss.str());
            oss.str("");
        }

        // Join criteria
        for (size_t i = 0; i < criteria.size(); ++i) {
            if (i > 0) oss << " | ";
            oss << criteria[i];
        }
    }

    if (pImpl->inverted) {
        return "NOT (" + oss.str() + ")";
    }

    return oss.str();
}

// ============================================================
// Advanced Methods
// ============================================================

PartSelector& PartSelector::setExplicitIds(const std::vector<int32_t>& ids) {
    pImpl->clear();
    pImpl->selected_ids.insert(ids.begin(), ids.end());
    pImpl->has_explicit_ids = true;
    return *this;
}

PartSelector& PartSelector::clear() {
    pImpl->clear();
    return *this;
}

// ============================================================
// Private Helper Methods
// ============================================================

bool PartSelector::matchPattern(const std::string& text,
                               const std::string& pattern,
                               PatternType type) const {
    if (type == PatternType::GLOB) {
        // Convert glob pattern to regex
        std::string regex_pattern = pattern;

        // Escape special regex characters except * and ?
        std::string escaped;
        for (char c : regex_pattern) {
            switch (c) {
                case '.':
                case '^':
                case '$':
                case '+':
                case '(':
                case ')':
                case '[':
                case ']':
                case '{':
                case '}':
                case '|':
                case '\\':
                    escaped += '\\';
                    escaped += c;
                    break;
                case '*':
                    escaped += ".*";
                    break;
                case '?':
                    escaped += '.';
                    break;
                default:
                    escaped += c;
            }
        }

        std::regex re(escaped);
        return std::regex_match(text, re);
    } else {
        // Use regex directly
        try {
            std::regex re(pattern);
            return std::regex_match(text, re);
        } catch (const std::regex_error&) {
            // Invalid regex pattern
            return false;
        }
    }
}

bool PartSelector::matchesPropertyFilter(const D3plotReader& reader,
                                        int32_t part_id,
                                        const PropertyFilter& filter) const {
    // TODO: Implement property filtering
    // This requires:
    // 1. Getting part geometry (elements, nodes)
    // 2. Calculating volume
    // 3. Calculating mass (if material density available)
    // 4. Calculating centroid

    // For now, return true (no filtering)
    // This will be implemented in Phase 2
    return true;
}

std::set<int32_t> PartSelector::intersect(const std::set<int32_t>& a,
                                          const std::set<int32_t>& b) {
    std::set<int32_t> result;
    std::set_intersection(a.begin(), a.end(),
                         b.begin(), b.end(),
                         std::inserter(result, result.begin()));
    return result;
}

std::set<int32_t> PartSelector::unite(const std::set<int32_t>& a,
                                      const std::set<int32_t>& b) {
    std::set<int32_t> result;
    std::set_union(a.begin(), a.end(),
                  b.begin(), b.end(),
                  std::inserter(result, result.begin()));
    return result;
}

std::set<int32_t> PartSelector::getAllPartIds(const D3plotReader& reader) {
    // Phase 1 stub - returns from helper function
    return getAllPartIdsFromReader(reader);
}

} // namespace query
} // namespace kood3plot
