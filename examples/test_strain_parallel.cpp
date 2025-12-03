#include "kood3plot/D3plotReader.hpp"
#include <iostream>
#include <iomanip>
#include <chrono>
#include <cmath>

using namespace kood3plot;

// Von Mises stress calculation
double calculate_von_mises(double sx, double sy, double sz,
                          double txy, double tyz, double tzx) {
    return std::sqrt(0.5 * (
        (sx - sy) * (sx - sy) +
        (sy - sz) * (sy - sz) +
        (sz - sx) * (sz - sx)
    ) + 3.0 * (txy*txy + tyz*tyz + tzx*tzx));
}

int main(int argc, char* argv[]) {
    size_t num_threads = 0; // 0 = auto-detect

    if (argc < 2) {
        std::cerr << "Usage: " << argv[0] << " <d3plot_path> [num_threads]\n";
        std::cerr << "  num_threads: Number of threads to use (0 = auto-detect)\n";
        return 1;
    }

    std::string d3plot_path = argv[1];

    if (argc >= 3) {
        num_threads = std::stoul(argv[2]);
    }

    std::cout << "==============================================\n";
    std::cout << "  Parallel Stress Extraction Test\n";
    std::cout << "==============================================\n\n";

    try {
        // Open D3plot file
        std::cout << "Opening: " << d3plot_path << "\n";
        D3plotReader reader(d3plot_path);
        auto open_result = reader.open();

        if (open_result != ErrorCode::SUCCESS) {
            std::cerr << "Failed to open d3plot file\n";
            return 1;
        }

        auto control = reader.get_control_data();

        std::cout << "File info:\n";
        std::cout << "  Solid elements: " << std::abs(control.NEL8) << "\n";
        std::cout << "  Nodal points: " << control.NUMNP << "\n";
        std::cout << "  Values per element (NV3D): " << control.NV3D << "\n";
        if (num_threads == 0) {
            std::cout << "  Threads: auto-detect\n\n";
        } else {
            std::cout << "  Threads: " << num_threads << "\n\n";
        }

        // Read all states using PARALLEL version
        std::cout << "Reading all state data (PARALLEL)...\n";
        auto start_read = std::chrono::high_resolution_clock::now();
        auto states = reader.read_all_states_parallel(num_threads);
        auto end_read = std::chrono::high_resolution_clock::now();
        auto read_duration = std::chrono::duration_cast<std::chrono::milliseconds>(end_read - start_read).count();

        if (states.empty()) {
            std::cerr << "No state data found!\n";
            return 1;
        }

        size_t num_states = states.size();
        int num_elements = std::abs(control.NEL8);
        int nv3d = control.NV3D;

        std::cout << "  Total states: " << num_states << "\n";
        std::cout << "  Read time: " << read_duration << " ms (" << (read_duration/1000.0) << " sec)\n\n";

        // Extract max von Mises stress across all elements and timesteps
        std::cout << "Extracting max von Mises stress...\n";

        auto start = std::chrono::high_resolution_clock::now();

        double max_stress = 0.0;
        size_t max_stress_state = 0;
        int max_stress_element = 0;

        // Process each state
        for (size_t state_idx = 0; state_idx < num_states; ++state_idx) {
            const auto& state_data = states[state_idx];

            // Process solid elements
            for (int elem_idx = 0; elem_idx < num_elements; ++elem_idx) {
                int offset = elem_idx * nv3d;

                if (offset + 6 > state_data.solid_data.size()) {
                    continue;
                }

                double sx = state_data.solid_data[offset + 0];
                double sy = state_data.solid_data[offset + 1];
                double sz = state_data.solid_data[offset + 2];
                double txy = state_data.solid_data[offset + 3];
                double tyz = state_data.solid_data[offset + 4];
                double tzx = state_data.solid_data[offset + 5];

                double von_mises = calculate_von_mises(sx, sy, sz, txy, tyz, tzx);

                if (von_mises > max_stress) {
                    max_stress = von_mises;
                    max_stress_state = state_idx;
                    max_stress_element = elem_idx + 1; // 1-indexed
                }
            }

            // Progress indicator
            if ((state_idx + 1) % 10 == 0 || state_idx == 0 || state_idx == num_states - 1) {
                std::cout << "  Processed state " << (state_idx + 1) << "/" << num_states
                          << " (" << std::fixed << std::setprecision(1)
                          << (100.0 * (state_idx + 1) / num_states) << "%)\n";
            }
        }

        auto end = std::chrono::high_resolution_clock::now();
        auto duration_ms = std::chrono::duration_cast<std::chrono::milliseconds>(end - start).count();

        std::cout << "\n==============================================\n";
        std::cout << "  Results\n";
        std::cout << "==============================================\n";
        std::cout << "Data read time (PARALLEL): " << read_duration << " ms (" << (read_duration/1000.0) << " sec)\n";
        std::cout << "Extraction time: " << duration_ms << " ms (" << (duration_ms/1000.0) << " sec)\n";
        std::cout << "Total time: " << (read_duration + duration_ms) << " ms ("
                  << ((read_duration + duration_ms)/1000.0) << " sec)\n";
        std::cout << "Time per state: " << (duration_ms / (double)num_states) << " ms\n\n";

        std::cout << "Max Von Mises Stress:\n";
        std::cout << "----------------------------------------------\n";
        std::cout << "  Max Stress: " << std::fixed << std::setprecision(2) << max_stress << "\n";
        std::cout << "  State Index: " << max_stress_state << " (time: "
                  << std::setprecision(6) << states[max_stress_state].time << " sec)\n";
        std::cout << "  Element ID: " << max_stress_element << "\n\n";

        std::cout << "==============================================\n";
        std::cout << "  Performance Summary\n";
        std::cout << "==============================================\n";
        size_t total_points = (size_t)num_elements * num_states;
        std::cout << "Total data points processed: " << total_points << "\n";
        std::cout << "Throughput: " << std::fixed << std::setprecision(0)
                  << (total_points / (duration_ms / 1000.0))
                  << " data points/sec\n";

    } catch (const std::exception& e) {
        std::cerr << "Error: " << e.what() << "\n";
        return 1;
    }

    return 0;
}
