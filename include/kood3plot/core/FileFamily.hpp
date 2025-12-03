#pragma once

#include "kood3plot/Types.hpp"
#include <string>
#include <vector>

namespace kood3plot {
namespace core {

/**
 * @brief Manages multi-file d3plot families (d3plot, d3plot01, d3plot02, ...)
 */
class FileFamily {
public:
    /**
     * @brief Constructor
     * @param base_path Path to the base d3plot file
     */
    explicit FileFamily(const std::string& base_path);

    /**
     * @brief Get list of all files in the family
     */
    std::vector<std::string> get_family_files() const;

    /**
     * @brief Get number of files in the family
     */
    size_t get_file_count() const;

    /**
     * @brief Get specific file path by index (0 = base, 1 = d3plot01, etc.)
     */
    std::string get_file_path(size_t index) const;

private:
    std::string base_path_;
    std::vector<std::string> family_files_;

    /**
     * @brief Discover all files in the family
     */
    void discover_files();
};

} // namespace core
} // namespace kood3plot
