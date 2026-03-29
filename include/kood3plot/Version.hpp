#pragma once

#include <string>

namespace kood3plot {

/**
 * @brief Library version information
 */
struct Version {
    static constexpr int MAJOR = 1;
    static constexpr int MINOR = 3;
    static constexpr int PATCH = 0;

    static std::string get_version_string() {
        return "1.3.0";
    }

    static std::string get_full_version_string() {
        return "KooD3plotReader v1.3.0";
    }
};

} // namespace kood3plot
