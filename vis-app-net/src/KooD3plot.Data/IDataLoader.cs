using System;
using System.Collections.Generic;

namespace KooD3plot.Data;

/// <summary>
/// Common file information for both HDF5 and D3plot formats
/// </summary>
public record DataFileInfo(
    string FormatType,       // "HDF5" or "D3plot"
    string FormatVersion,    // Format version string
    int NumNodes,
    int NumSolids,
    int NumShells,
    int NumBeams,
    int NumThickShells,
    int NumTimesteps,
    long FileSizeBytes,
    double CompressionRatio,
    string Title             // Simulation title (from D3plot)
);

/// <summary>
/// Common interface for data loaders (HDF5, D3plot, etc.)
/// </summary>
public interface IDataLoader : IDisposable
{
    /// <summary>
    /// Get file metadata information
    /// </summary>
    DataFileInfo GetFileInfo();

    /// <summary>
    /// Get list of available timestep indices
    /// </summary>
    List<int> GetTimestepList();

    /// <summary>
    /// Get simulation time for a specific timestep
    /// </summary>
    double GetTimestepTime(int timestep);

    /// <summary>
    /// Get mesh geometry data (cached after first call)
    /// </summary>
    MeshData GetMeshData();

    /// <summary>
    /// Get state data for a specific timestep
    /// </summary>
    StateData GetStateData(int timestep);

    /// <summary>
    /// Check if the loader is currently open and valid
    /// </summary>
    bool IsOpen { get; }

    /// <summary>
    /// Get the file path(s) being read
    /// </summary>
    string FilePath { get; }
}
