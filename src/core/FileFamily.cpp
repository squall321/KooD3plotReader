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
            // 뒤 번호가 남아 있으면 구멍이다 — 그대로 멈추면 뒤 파일의 상태가
            // 조용히 빠진 채 '성공' 한다. 판정은 읽는 쪽(D3plotReader)이 한다.
            std::error_code ec;
            for (const auto& entry : fs::directory_iterator(directory, ec)) {
                const std::string name = entry.path().filename().string();
                if (name.size() <= base_name.size() || name.compare(0, base_name.size(), base_name) != 0)
                    continue;
                const std::string digits = name.substr(base_name.size());
                if (digits.size() < 2 || digits.size() > 3 ||
                    digits.find_first_not_of("0123456789") != std::string::npos)
                    continue;
                if (std::stoi(digits) > i) {
                    gap_description_ = oss.str() + " 이 없는데 " + name + " 이 있다";
                    break;
                }
            }
            break;
        }
    }
}

} // namespace core
} // namespace kood3plot
