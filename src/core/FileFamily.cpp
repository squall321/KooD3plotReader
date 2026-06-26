#include "kood3plot/core/FileFamily.hpp"
#include <filesystem>
#include <sstream>
#include <iomanip>

namespace kood3plot {
namespace core {

FileFamily::FileFamily(const std::string& base_path)
    : base_path_(base_path) {
    discover_files();
}

std::vector<std::string> FileFamily::get_family_files() const {
    return family_files_;
}

size_t FileFamily::get_file_count() const {
    return family_files_.size();
}

std::string FileFamily::get_file_path(size_t index) const {
    if (index >= family_files_.size()) {
        return "";
    }
    return family_files_[index];
}

void FileFamily::discover_files() {
    // Add base file first
    family_files_.push_back(base_path_);

    // Check if base file exists
    namespace fs = std::filesystem;
    if (!fs::exists(base_path_)) {
        return;  // Base file doesn't exist, no family to discover
    }

    // Extract directory and base filename
    fs::path base_file_path(base_path_);
    fs::path directory = base_file_path.parent_path();
    std::string base_name = base_file_path.filename().string();

    // If directory is empty, use current directory
    if (directory.empty()) {
        directory = ".";
    }

    // Discover family files: d3plot01..d3plot99, then d3plot100..d3plot999.
    // LS-DYNA spec (ls-dyna_database.txt): successive members append a two- OR
    // three-digit number, 01,02,...,99,100,...,999. setw(2) is a MINIMUM width,
    // so i>=100 renders as 3 digits naturally. Capping at 99 silently dropped
    // every family file past d3plot99 → truncated state history → wrong peaks.
    // (Mesh-adaptivity letter appendage d3plotaa.. is a separate, unhandled case.)
    for (int i = 1; i <= 999; ++i) {
        std::ostringstream oss;
        oss << base_name << std::setfill('0') << std::setw(2) << i;

        fs::path family_file_path = directory / oss.str();

        if (fs::exists(family_file_path)) {
            family_files_.push_back(family_file_path.string());
        } else {
            // Stop at first missing file (assume sequential numbering)
            break;
        }
    }
}

} // namespace core
} // namespace kood3plot
