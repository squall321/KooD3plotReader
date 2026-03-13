/**
 * @file PartMatcher.cpp
 * @brief Implementation of PartMatcher
 */

#include "kood3plot/section_render/PartMatcher.hpp"
#include <algorithm>
#include <cctype>

namespace kood3plot {
namespace section_render {

// ============================================================
// Static helpers
// ============================================================

std::string PartMatcher::toLower(const std::string& s)
{
    std::string out(s.size(), '\0');
    std::transform(s.begin(), s.end(), out.begin(),
                   [](unsigned char c){ return static_cast<char>(std::tolower(c)); });
    return out;
}

/**
 * Recursive glob matcher.
 * '*' matches any sequence (including empty).
 * '?' matches exactly one character.
 * Both pattern and text are assumed to be already lower-cased.
 */
bool PartMatcher::globMatch(const std::string& pattern, const std::string& text)
{
    const char* p = pattern.c_str();
    const char* t = text.c_str();

    // Cache of (p_pos, t_pos) for backtracking when '*' is encountered
    const char* star_p = nullptr;
    const char* star_t = nullptr;

    while (*t) {
        if (*p == '*') {
            star_p = p;
            star_t = t;
            ++p;               // advance past '*' — try matching zero chars first
        } else if (*p == '?' || *p == *t) {
            ++p;
            ++t;
        } else if (star_p) {
            // Mismatch — backtrack: '*' consumes one more character
            p = star_p + 1;
            t = ++star_t;
        } else {
            return false;
        }
    }

    // Consume any trailing '*'s
    while (*p == '*') ++p;

    return *p == '\0';
}

// ============================================================
// Population
// ============================================================

void PartMatcher::addById(int32_t part_id)
{
    ids_.insert(part_id);
}

void PartMatcher::addByPattern(const std::string& pattern)
{
    patterns_.push_back(toLower(pattern));
}

void PartMatcher::addByKeyword(const std::string& keyword)
{
    keywords_.push_back(toLower(keyword));
}

void PartMatcher::clear()
{
    ids_.clear();
    patterns_.clear();
    keywords_.clear();
}

bool PartMatcher::empty() const
{
    return ids_.empty() && patterns_.empty() && keywords_.empty();
}

// ============================================================
// Query
// ============================================================

bool PartMatcher::matches(int32_t part_id, const std::string& part_name) const
{
    // 1. Exact ID match (O(1))
    if (ids_.count(part_id)) return true;

    // 2. Name-based matching (only when name is non-empty)
    if (!part_name.empty()) {
        std::string lower_name = toLower(part_name);

        // Keyword substring
        for (const auto& kw : keywords_) {
            if (lower_name.find(kw) != std::string::npos) return true;
        }

        // Glob patterns
        for (const auto& pat : patterns_) {
            if (globMatch(pat, lower_name)) return true;
        }
    }

    return false;
}

} // namespace section_render
} // namespace kood3plot
