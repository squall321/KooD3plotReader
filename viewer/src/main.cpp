#include "app/App.hpp"
#include "app/DeepReportApp.hpp"
#include "app/SphereReportApp.hpp"
#include <iostream>
#include <string>
#include <filesystem>

int main(int argc, char* argv[]) {
    if (argc < 2) {
        std::cerr << "Usage: koo_viewer <mode> <path>\n";
        std::cerr << "  Modes:\n";
        std::cerr << "    deep   <output_dir>   — Single analysis report viewer\n";
        std::cerr << "    sphere <test_dir>      — All-angle sphere report viewer\n";
        std::cerr << "    3d     <d3plot_path>   — 3D model viewer\n";
        std::cerr << "    <d3plot_or_dir>        — Auto-detect mode\n";
        return 1;
    }

    std::string mode = "auto";
    std::string path;

    if (argc >= 3 && (std::string(argv[1]) == "deep" || std::string(argv[1]) == "sphere" || std::string(argv[1]) == "3d")) {
        mode = argv[1];
        path = argv[2];
    } else {
        path = argv[1];
        // Auto-detect mode from path contents
        namespace fs = std::filesystem;
        if (fs::exists(fs::path(path) / "report.json") || fs::path(path).extension() == ".json") {
            // Check if it's a sphere report JSON
            mode = "sphere";
        } else if (fs::exists(fs::path(path) / "analysis_result.json") || fs::exists(fs::path(path) / "result.json")) {
            mode = "deep";
        } else if (fs::exists(path) && fs::path(path).filename().string().find("d3plot") != std::string::npos) {
            mode = "3d";
        } else {
            mode = "deep";
        }
    }

    std::cout << "[KooViewer] Mode: " << mode << "\n";
    std::cout << "[KooViewer] Path: " << path << "\n";

    if (mode == "deep") {
        DeepReportApp app;
        if (!app.init(1600, 900)) return 1;
        app.run(path);
        app.shutdown();
    } else if (mode == "3d") {
        App app;
        if (!app.init(1600, 900, "KooViewer — 3D")) return 1;
        app.run(path);
        app.shutdown();
    } else if (mode == "sphere") {
        // Find report.json — either path is the JSON or a directory containing it
        std::string jsonPath = path;
        namespace fs = std::filesystem;
        if (fs::is_directory(path)) {
            if (fs::exists(fs::path(path) / "report.json"))
                jsonPath = (fs::path(path) / "report.json").string();
            else if (fs::exists(fs::path(path) / "sphere_report.json"))
                jsonPath = (fs::path(path) / "sphere_report.json").string();
            else {
                std::cerr << "No report.json found in: " << path << "\n";
                std::cerr << "Run: koo_sphere_report --format json --json report.json ...\n";
                return 1;
            }
        }
        SphereReportApp app;
        if (!app.init(1600, 900)) return 1;
        app.run(jsonPath);
        app.shutdown();
    }

    return 0;
}
