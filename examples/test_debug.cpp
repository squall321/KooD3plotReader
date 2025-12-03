#include "kood3plot/D3plotReader.hpp"
#include <iostream>
#include <iomanip>

using namespace kood3plot;

int main(int argc, char* argv[]) {
    if (argc < 2) {
        std::cerr << "Usage: " << argv[0] << " <d3plot_path>\n";
        return 1;
    }

    std::string d3plot_path = argv[1];

    D3plotReader reader(d3plot_path);
    auto result = reader.open();

    if (result != ErrorCode::SUCCESS) {
        std::cerr << "Failed to open d3plot file\n";
        return 1;
    }

    auto control = reader.get_control_data();

    std::cout << "=== Control Data ===" << std::endl;
    std::cout << "NGLBV: " << control.NGLBV << std::endl;
    std::cout << "NND:   " << control.NND << std::endl;
    std::cout << "ENN:   " << control.ENN << std::endl;
    std::cout << "NEL8:  " << control.NEL8 << std::endl;
    std::cout << "NUMNP: " << control.NUMNP << std::endl;
    std::cout << "NV3D:  " << control.NV3D << std::endl;
    
    size_t state_size = 1 + control.NGLBV + control.NND + control.ENN;
    std::cout << "\nCalculated state_size: " << state_size << " words" << std::endl;
    std::cout << "State size in bytes:   " << (state_size * 8) << " bytes (double precision)" << std::endl;

    // Try reading states
    std::cout << "\n=== Reading States ===" << std::endl;
    auto states = reader.read_all_states();
    std::cout << "Total states loaded: " << states.size() << std::endl;
    
    if (!states.empty()) {
        std::cout << "First state time: " << states[0].time << std::endl;
        if (states.size() > 1) {
            std::cout << "Second state time: " << states[1].time << std::endl;
        }
    }

    return 0;
}
