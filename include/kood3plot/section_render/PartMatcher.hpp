#pragma once
/**
 * @file PartMatcher.hpp
 * @brief Identifies which parts are "target" vs "background" for section rendering
 *
 * Parts can be selected by:
 *   - Numeric ID
 *   - Glob pattern on part name  (e.g. "*battery*", "cell_??")
 *   - Keyword substring match    (case-insensitive)
 *
 * The same API is used for both target-part and background-part selection.
 * A part not matched as target is treated as background by default.
 */

#include <cstdint>
#include <string>
#include <unordered_set>
#include <vector>

namespace kood3plot {
namespace section_render {

class PartMatcher {
public:
    PartMatcher() = default;

    // ----------------------------------------------------------------
    // Population
    // ----------------------------------------------------------------

    /** Accept a part by its numeric ID */
    void addById(int32_t part_id);

    /**
     * @brief Accept parts whose name matches a glob pattern
     *
     * Supports '*' (any sequence) and '?' (single character).
     * Pattern matching is case-insensitive.
     * Example: addByPattern("*battery*"), addByPattern("cell_??")
     */
    void addByPattern(const std::string& pattern);

    /**
     * @brief Accept parts whose name contains keyword as a substring
     *
     * Equivalent to addByPattern("*keyword*") but simpler to use.
     * Matching is case-insensitive.
     */
    void addByKeyword(const std::string& keyword);

    /** Remove all previously registered criteria */
    void clear();

    /** True if no criteria have been registered (matches nothing) */
    bool empty() const;

    /** True if at least one numeric ID was registered (not just patterns/keywords) */
    bool hasSpecificIds() const { return !ids_.empty(); }

    // ----------------------------------------------------------------
    // Query
    // ----------------------------------------------------------------

    /**
     * @brief Test whether a part is accepted by ID only (ignores patterns/keywords)
     */
    bool matches(int32_t part_id) const { return ids_.count(part_id) > 0; }

    /**
     * @brief Test whether a part is accepted
     * @param part_id   Numeric part ID
     * @param part_name Part name string (may be empty if no keyword file found)
     */
    bool matches(int32_t part_id, const std::string& part_name) const;

private:
    std::unordered_set<int32_t> ids_;
    std::vector<std::string>    patterns_;   ///< Glob patterns (lower-cased)
    std::vector<std::string>    keywords_;   ///< Plain substrings (lower-cased)

    static bool globMatch(const std::string& pattern, const std::string& text);
    static std::string toLower(const std::string& s);
};

} // namespace section_render
} // namespace kood3plot
