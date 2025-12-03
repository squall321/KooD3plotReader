#pragma once

/**
 * @file PartSelector.h
 * @brief Part selection interface for the KooD3plot Query System
 * @author KooD3plot V3 Development Team
 * @date 2025-11-21
 * @version 3.0.0
 *
 * PartSelector provides flexible methods to select parts from a d3plot model:
 * - By ID (single or multiple)
 * - By name (exact match)
 * - By pattern (glob or regex)
 * - By material ID
 * - By geometric properties (volume, mass, centroid)
 * - Logical operations (AND, OR, NOT)
 * - Special selectors (all, none)
 *
 * Example usage:
 * @code
 * PartSelector selector;
 * selector.byName("Hood")
 *         .byPattern("Door_*")
 *         .byMaterial({10, 11});
 * auto parts = selector.evaluate(reader);
 * @endcode
 */

#include "QueryTypes.h"
#include "../D3plotReader.hpp"
#include <set>

namespace kood3plot {
namespace query {

/**
 * @class PartSelector
 * @brief Selects parts from d3plot model based on various criteria
 *
 * This class implements the builder pattern, allowing method chaining
 * for intuitive query construction. All selection methods add to the
 * current selection set.
 */
class PartSelector {
public:
    // ============================================================
    // Constructors
    // ============================================================

    /**
     * @brief Default constructor
     */
    PartSelector();

    /**
     * @brief Copy constructor
     */
    PartSelector(const PartSelector& other);

    /**
     * @brief Move constructor
     */
    PartSelector(PartSelector&& other) noexcept;

    /**
     * @brief Assignment operator
     */
    PartSelector& operator=(const PartSelector& other);

    /**
     * @brief Move assignment operator
     */
    PartSelector& operator=(PartSelector&& other) noexcept;

    /**
     * @brief Destructor
     */
    ~PartSelector();

    // ============================================================
    // Selection by ID
    // ============================================================

    /**
     * @brief Select part by single ID
     * @param id Part ID
     * @return Reference to this selector for method chaining
     *
     * Example:
     * @code
     * selector.byId(1);  // Select part with ID 1
     * @endcode
     */
    PartSelector& byId(int32_t id);

    /**
     * @brief Select parts by multiple IDs
     * @param ids Vector of part IDs
     * @return Reference to this selector for method chaining
     *
     * Example:
     * @code
     * selector.byId({1, 2, 3, 100});
     * @endcode
     */
    PartSelector& byId(const std::vector<int32_t>& ids);

    // ============================================================
    // Selection by Name
    // ============================================================

    /**
     * @brief Select part by exact name match
     * @param name Part name (case-sensitive)
     * @return Reference to this selector for method chaining
     *
     * Example:
     * @code
     * selector.byName("Hood");
     * @endcode
     */
    PartSelector& byName(const std::string& name);

    /**
     * @brief Select parts by multiple exact name matches
     * @param names Vector of part names
     * @return Reference to this selector for method chaining
     *
     * Example:
     * @code
     * selector.byName({"Hood", "Door_LF", "Door_RF"});
     * @endcode
     */
    PartSelector& byName(const std::vector<std::string>& names);

    // ============================================================
    // Selection by Pattern
    // ============================================================

    /**
     * @brief Select parts by pattern matching
     * @param pattern Pattern string
     * @param type Pattern type (GLOB or REGEX)
     * @return Reference to this selector for method chaining
     *
     * Glob patterns:
     * - * matches any sequence of characters
     * - ? matches any single character
     * - [abc] matches a, b, or c
     *
     * Example:
     * @code
     * selector.byPattern("Door_*", PatternType::GLOB);     // All doors
     * selector.byPattern("^Pillar_[AB]$", PatternType::REGEX);  // Pillar_A or Pillar_B
     * @endcode
     */
    PartSelector& byPattern(const std::string& pattern,
                           PatternType type = PatternType::GLOB);

    /**
     * @brief Select parts by multiple patterns
     * @param patterns Vector of pattern strings
     * @param type Pattern type (GLOB or REGEX)
     * @return Reference to this selector for method chaining
     */
    PartSelector& byPattern(const std::vector<std::string>& patterns,
                           PatternType type = PatternType::GLOB);

    // ============================================================
    // Selection by Material
    // ============================================================

    /**
     * @brief Select parts by material ID
     * @param material_id Material ID
     * @return Reference to this selector for method chaining
     *
     * Example:
     * @code
     * selector.byMaterial(10);  // Parts with material ID 10
     * @endcode
     */
    PartSelector& byMaterial(int32_t material_id);

    /**
     * @brief Select parts by multiple material IDs
     * @param material_ids Vector of material IDs
     * @return Reference to this selector for method chaining
     *
     * Example:
     * @code
     * selector.byMaterial({10, 11, 12});  // Parts with material 10, 11, or 12
     * @endcode
     */
    PartSelector& byMaterial(const std::vector<int32_t>& material_ids);

    // ============================================================
    // Selection by Property
    // ============================================================

    /**
     * @brief Select parts by geometric/physical properties
     * @param filter Property filter specification
     * @return Reference to this selector for method chaining
     *
     * Example:
     * @code
     * PropertyFilter filter;
     * filter.min_volume = 100.0;
     * filter.max_volume = 1000.0;
     * filter.centroid_near = {500.0, 0.0, 0.0};
     * filter.centroid_tolerance = 50.0;
     * selector.byProperty(filter);
     * @endcode
     */
    PartSelector& byProperty(const PropertyFilter& filter);

    // ============================================================
    // Logical Operations
    // ============================================================

    /**
     * @brief Combine with another selector using AND logic
     * @param other Another part selector
     * @return New selector with intersection of both selections
     *
     * Example:
     * @code
     * auto selector1 = PartSelector().byName("Hood");
     * auto selector2 = PartSelector().byMaterial(10);
     * auto combined = selector1 && selector2;  // Hood AND material 10
     * @endcode
     */
    PartSelector operator&&(const PartSelector& other) const;

    /**
     * @brief Combine with another selector using OR logic
     * @param other Another part selector
     * @return New selector with union of both selections
     *
     * Example:
     * @code
     * auto selector1 = PartSelector().byName("Hood");
     * auto selector2 = PartSelector().byName("Roof");
     * auto combined = selector1 || selector2;  // Hood OR Roof
     * @endcode
     */
    PartSelector operator||(const PartSelector& other) const;

    /**
     * @brief Invert selection (NOT logic)
     * @return New selector with inverted selection
     *
     * Example:
     * @code
     * auto selector = PartSelector().byName("Hood");
     * auto inverted = !selector;  // All parts EXCEPT Hood
     * @endcode
     */
    PartSelector operator!() const;

    // ============================================================
    // Special Selectors
    // ============================================================

    /**
     * @brief Select all parts in the model
     * @return Reference to this selector
     *
     * Example:
     * @code
     * selector.selectAll();
     * @endcode
     */
    PartSelector& selectAll();

    /**
     * @brief Clear selection (select no parts)
     * @return Reference to this selector
     *
     * Example:
     * @code
     * selector.selectNone();
     * @endcode
     */
    PartSelector& selectNone();

    /**
     * @brief Static method to create "all parts" selector
     * @return Selector configured to select all parts
     *
     * Example:
     * @code
     * auto selector = PartSelector::all();
     * @endcode
     */
    static PartSelector all();

    /**
     * @brief Static method to create "no parts" selector
     * @return Selector configured to select no parts
     *
     * Example:
     * @code
     * auto selector = PartSelector::none();
     * @endcode
     */
    static PartSelector none();

    // ============================================================
    // Evaluation
    // ============================================================

    /**
     * @brief Evaluate selector against d3plot reader
     * @param reader D3plot reader instance
     * @return Vector of selected part IDs
     *
     * This method processes all selection criteria and returns
     * the final list of part IDs that match.
     *
     * Example:
     * @code
     * D3plotReader reader("crash.d3plot");
     * PartSelector selector;
     * selector.byPattern("Door_*");
     * auto part_ids = selector.evaluate(reader);
     * // part_ids now contains IDs of all door parts
     * @endcode
     */
    std::vector<int32_t> evaluate(const D3plotReader& reader) const;

    /**
     * @brief Evaluate and get part names instead of IDs
     * @param reader D3plot reader instance
     * @return Vector of selected part names
     */
    std::vector<std::string> evaluateNames(const D3plotReader& reader) const;

    /**
     * @brief Count how many parts match the selection
     * @param reader D3plot reader instance
     * @return Number of matching parts
     *
     * Example:
     * @code
     * int count = selector.count(reader);
     * std::cout << "Selected " << count << " parts\n";
     * @endcode
     */
    size_t count(const D3plotReader& reader) const;

    /**
     * @brief Check if any parts match the selection
     * @param reader D3plot reader instance
     * @return true if at least one part matches
     */
    bool hasMatches(const D3plotReader& reader) const;

    // ============================================================
    // Query State
    // ============================================================

    /**
     * @brief Check if this is an "all parts" selector
     * @return true if selector will select all parts
     */
    bool isAll() const;

    /**
     * @brief Check if this is a "no parts" selector
     * @return true if selector will select no parts
     */
    bool isNone() const;

    /**
     * @brief Check if selector is inverted
     * @return true if selection is inverted
     */
    bool isInverted() const;

    /**
     * @brief Get selection mode description (for debugging)
     * @return String describing the selection criteria
     */
    std::string getDescription() const;

    // ============================================================
    // Advanced Methods
    // ============================================================

    /**
     * @brief Manually set selected part IDs (bypasses criteria)
     * @param ids Part IDs to select
     * @return Reference to this selector
     *
     * This is useful for programmatic selection or when you
     * already have a list of part IDs from another source.
     */
    PartSelector& setExplicitIds(const std::vector<int32_t>& ids);

    /**
     * @brief Clear all selection criteria
     * @return Reference to this selector
     */
    PartSelector& clear();

private:
    // ============================================================
    // Private Implementation
    // ============================================================

    /**
     * @brief Implementation struct (PIMPL pattern)
     *
     * This hides implementation details and reduces compilation dependencies.
     */
    struct Impl;
    std::unique_ptr<Impl> pImpl;

    // ============================================================
    // Private Helper Methods
    // ============================================================

    /**
     * @brief Match pattern against string (glob or regex)
     */
    bool matchPattern(const std::string& text,
                     const std::string& pattern,
                     PatternType type) const;

    /**
     * @brief Check if part matches property filter
     */
    bool matchesPropertyFilter(const D3plotReader& reader,
                               int32_t part_id,
                               const PropertyFilter& filter) const;

    /**
     * @brief Combine two sets of part IDs using AND logic
     */
    static std::set<int32_t> intersect(const std::set<int32_t>& a,
                                       const std::set<int32_t>& b);

    /**
     * @brief Combine two sets of part IDs using OR logic
     */
    static std::set<int32_t> unite(const std::set<int32_t>& a,
                                   const std::set<int32_t>& b);

    /**
     * @brief Get all part IDs from reader
     */
    static std::set<int32_t> getAllPartIds(const D3plotReader& reader);
};

} // namespace query
} // namespace kood3plot
