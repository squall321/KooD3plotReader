# OpenRadioss Animation File Converter

OpenRadioss animation file (A00/A01/A02...) to VTK converter implementation.

## Overview

This converter enables reading OpenRadioss animation files and converting them to VTK format for visualization in ParaView or other VTK-compatible tools.

### File Format

Based on reverse engineering of OpenRadioss `genani.F` source code:

#### A00 File (Header + Geometry)
```
- Magic number (int32): 21548 (0x542b)
- Time (float32)
- Text strings (81 bytes each, null-padded):
  * "Time=" or "Frequency="
  * Simulation title
  * "Radioss Run="
- Animation mode (int32)
- Additional flag (int32)
- Element type flags (9 x int32):
  * has_3d, has_1d, hierarchy, th, shell_ref, sph, vers, reserved, reserved
- Counts:
  * NUMNOD (int32): number of nodes
  * NBF (int32): number of 2D elements
  * NBPART (int32): number of parts
  * NN_ANI (int32): nodal scalar variables
  * NCE_ANI (int32): element scalar variables
  * NV_ANI (int32): nodal vector variables (1=vel, 2=disp, 3=acc)
  * NCT_ANI (int32): element tensor variables
  * NSKEW (int32): number of skew systems
- Skew systems data (if NSKEW > 0)
- Node coordinates: NUMNOD * 3 float32 (X, Y, Z)
- Element connectivity (varies by element type)
- Part IDs (one int32 per element)
- Variable names (81-byte text strings)
```

#### A01, A02, ... State Files
```
- Time (float32)
- Nodal vectors (if NV_ANI > 0):
  * Velocity (3 * NUMNOD float32)
  * Displacement (3 * NUMNOD float32)
  * Acceleration (3 * NUMNOD float32)
- Nodal scalars (if NN_ANI > 0)
- Element scalars (if NCE_ANI > 0)
- Element tensors (if NCT_ANI > 0)
  * Stress (6 * num_elements float32, Voigt notation)
```

## Implementation

### Classes

#### `RadiossReader`
Reads OpenRadioss A00 and state files.

```cpp
#include "kood3plot/converter/RadiossReader.h"

RadiossReader reader("path/to/A00");
if (reader.open() != ErrorCode::SUCCESS) {
    std::cerr << "Error: " << reader.getLastError() << "\n";
    return 1;
}

auto header = reader.getHeader();
auto mesh = reader.getMesh();
auto states = reader.readAllStates();  // Read A01, A02, ...
reader.close();
```

#### `RadiossToVtkConverter`
Converts OpenRadioss data to VTK format.

```cpp
#include "kood3plot/converter/RadiossToVtkConverter.h"

RadiossToVtkOptions options;
options.export_displacement = true;
options.export_velocity = true;
options.export_stress = true;

RadiossToVtkConverter converter;
converter.setOptions(options);

// Convert single state
auto result = converter.convert(header, mesh, states[0], "output.vtk");

// Convert time series
auto result = converter.convertSeries(header, mesh, states, "output/state");
// Creates: output/state_0000.vtk, output/state_0001.vtk, ...
```

### Data Structures

```cpp
struct RadiossHeader {
    std::string title;
    int32_t num_nodes;
    int32_t num_solids, num_shells, num_beams;
    bool has_displacement, has_velocity, has_acceleration;
    bool has_stress, has_strain, has_plastic_strain;
    int word_size;  // 4 (float32) or 8 (float64)
};

struct RadiossMesh {
    std::vector<Node> nodes;
    std::vector<Element> solids, shells, beams;
    std::vector<int32_t> solid_parts, shell_parts, beam_parts;
};

struct RadiossState {
    double time;
    std::vector<double> node_displacements;    // 3 * num_nodes
    std::vector<double> node_velocities;       // 3 * num_nodes
    std::vector<double> node_accelerations;    // 3 * num_nodes
    std::vector<double> solid_stress;          // 6 * num_solids (Voigt)
    std::vector<double> shell_stress;          // 6 * num_shells
    std::vector<double> plastic_strain;        // num_elements
};
```

## Examples

### Basic Conversion
```bash
# Convert OpenRadioss animation to VTK time series
./converter_radioss_to_vtk /path/to/A00 output_dir

# Output:
#   output_dir/state_0000.vtk
#   output_dir/state_0001.vtk
#   ...
#   output_dir/simulation.pvd  (for ParaView)

# Visualize in ParaView
paraview output_dir/simulation.pvd
```

### Three-Way Conversion Chain

The full conversion chain is now complete:

```
D3plot ←→ VTK ←→ OpenRadioss A00
```

**Example workflows:**

1. **D3plot → VTK → OpenRadioss**
   ```bash
   ./converter_real_d3plot d3plot vtk_temp
   # Then convert VTK to OpenRadioss (if reverse converter implemented)
   ```

2. **OpenRadioss → VTK → D3plot**
   ```bash
   ./converter_radioss_to_vtk A00 vtk_temp
   # Then use VtkToD3plotConverter
   ```

3. **Full roundtrip: D3plot → VTK → Radioss → VTK → D3plot**
   - Validates data preservation across all formats

## Limitations & Future Work

### Current Implementation
- ✅ A00 header parsing (magic, flags, counts)
- ✅ Node coordinates reading
- ✅ Shell element connectivity (4-node quads)
- ✅ State file parsing (velocity, displacement, acceleration)
- ✅ Stress tensor data (Voigt 6-component)
- ✅ Plastic strain data

### Known Limitations
1. **Element types**: Currently supports shells (4-node quads)
   - TODO: Solids (8-node hexahedra)
   - TODO: Beams (2-node lines)
   - TODO: SPH particles
   - TODO: XFEM elements

2. **Advanced features** not yet implemented:
   - Multi-layer composite shells
   - XFEM crack data
   - Airbag/fluid-structure interaction data
   - Multi-material ALE data

3. **Variable detection**: Currently uses NV_ANI counts
   - TODO: Parse variable name text strings
   - TODO: Handle optional data blocks

### Testing Status
- ⚠️ **Needs validation with real OpenRadioss files**
- Format structure based on source code analysis
- Binary layout confirmed from genani.F
- Actual file testing recommended before production use

## Technical Notes

### Binary Format Details

1. **Endianness**: Little-endian (default)
2. **Word size**: 4 bytes (float32) by default
3. **Text encoding**: ASCII, null-padded to 81 bytes
4. **Integer type**: int32
5. **Float type**: float32 (single precision)

### OpenRadioss Source Reference

Implementation based on:
- `engine/source/output/anim/generate/genani.F` (main animation writer)
- `engine/source/output/anim/generate/ani_txt.F` (text string writer)
- `engine/source/output/anim/generate/xyznod.F` (node coordinate writer)

### Differences from Official Format

OpenRadioss does not have official A00 format documentation. This implementation is based on:
1. Reverse engineering of OpenRadioss source code
2. Binary pattern analysis
3. Community knowledge

**Validation recommended** with actual Radioss simulation outputs.

## Build Instructions

```bash
cd KooD3plotReader
mkdir build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release
cmake --build . --target kood3plot_converter
cmake --build . --target converter_radioss_to_vtk
```

## Usage Example (C++)

```cpp
#include "kood3plot/converter/RadiossReader.h"
#include "kood3plot/converter/RadiossToVtkConverter.h"

int main() {
    // Open A00 file
    RadiossReader reader("simulation/A00");
    if (reader.open() != ErrorCode::SUCCESS) {
        std::cerr << "Error: " << reader.getLastError() << "\n";
        return 1;
    }

    auto header = reader.getHeader();
    auto mesh = reader.getMesh();

    std::cout << "Title: " << header.title << "\n";
    std::cout << "Nodes: " << header.num_nodes << "\n";
    std::cout << "Shells: " << header.num_shells << "\n";

    // Read all state files
    auto states = reader.readAllStates();
    std::cout << "States: " << states.size() << "\n";

    reader.close();

    // Convert to VTK
    RadiossToVtkOptions options;
    options.export_displacement = true;
    options.export_velocity = true;
    options.export_stress = true;

    RadiossToVtkConverter converter;
    converter.setOptions(options);

    auto result = converter.convertSeries(
        header, mesh, states, "output/state");

    if (result.success) {
        std::cout << "Converted " << result.output_files.size()
                  << " states to VTK\n";
    }

    return 0;
}
```

## Contributing

To improve OpenRadioss support:

1. **Test with real files**: Validate against actual OpenRadioss outputs
2. **Add element types**: Implement solid/beam parsing
3. **Handle advanced features**: SPH, XFEM, multi-layer composites
4. **Document format variations**: Different OpenRadioss versions
5. **Create test suite**: Binary format validation tests

## License

Same as parent project (see main README).

## References

- [OpenRadioss GitHub](https://github.com/OpenRadioss/OpenRadioss)
- OpenRadioss source: `engine/source/output/anim/generate/genani.F`
- VTK file format: [VTK Legacy Format](https://vtk.org/wp-content/uploads/2015/04/file-formats.pdf)
