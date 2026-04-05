#pragma once
#include <string>
#include <filesystem>
#include <fstream>
#include <iostream>

// Tiny session persistence:
// Reads/writes ~/.config/kooviewer/session.json
// Format: {"mode":"deep","path":"/abs/path/to/dir"}

struct SessionState {
    std::string mode;   // "deep", "sphere", "3d"
    std::string path;
    bool valid = false;
};

inline std::filesystem::path sessionFilePath() {
    std::filesystem::path base;
    const char* home = std::getenv("HOME");
    if (home) base = std::filesystem::path(home) / ".config" / "kooviewer";
    else       base = std::filesystem::temp_directory_path() / "kooviewer";
    return base / "session.json";
}

inline SessionState loadSession() {
    SessionState s;
    auto p = sessionFilePath();
    if (!std::filesystem::exists(p)) return s;
    std::ifstream f(p);
    if (!f.is_open()) return s;

    // Minimal JSON parse — just look for "mode" and "path" string values
    std::string content((std::istreambuf_iterator<char>(f)),
                         std::istreambuf_iterator<char>());
    auto extractStr = [&](const std::string& key) -> std::string {
        std::string needle = "\"" + key + "\"";
        auto pos = content.find(needle);
        if (pos == std::string::npos) return "";
        pos = content.find('"', pos + needle.size() + 1);
        if (pos == std::string::npos) return "";
        auto end = content.find('"', pos + 1);
        if (end == std::string::npos) return "";
        return content.substr(pos + 1, end - pos - 1);
    };

    s.mode  = extractStr("mode");
    s.path  = extractStr("path");
    s.valid = !s.mode.empty() && !s.path.empty() &&
              std::filesystem::exists(s.path);
    return s;
}

inline void saveSession(const std::string& mode, const std::string& path) {
    auto p = sessionFilePath();
    std::error_code ec;
    std::filesystem::create_directories(p.parent_path(), ec);
    if (ec) { std::cerr << "[Session] Cannot create dir: " << ec.message() << "\n"; return; }

    // Escape backslashes for Windows paths
    std::string escaped;
    for (char c : path) escaped += (c == '\\') ? '/' : c;

    std::ofstream f(p);
    if (!f.is_open()) return;
    f << "{\n"
      << "  \"mode\": \"" << mode << "\",\n"
      << "  \"path\": \"" << escaped << "\"\n"
      << "}\n";
    std::cout << "[Session] Saved: " << p << "\n";
}
