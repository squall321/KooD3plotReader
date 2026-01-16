using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;

namespace KooD3plot.Data;

/// <summary>
/// D3plot file data loader implementing IDataLoader interface.
/// Uses the native kood3plot library via P/Invoke for reading LS-DYNA d3plot files.
/// </summary>
public class D3plotDataLoader : IDataLoader
{
    private readonly string _filePath;
    private IntPtr _handle;
    private bool _isOpen;
    private DataFileInfo? _fileInfo;
    private MeshData? _meshData;
    private KooFileInfo _nativeFileInfo;
    private KooMeshInfo _nativeMeshInfo;
    private readonly Dictionary<int, StateData> _stateCache = new();
    private const int MaxCacheSize = 50;  // Increase cache size for smoother playback

    /// <summary>
    /// Check if the loader is currently open and valid
    /// </summary>
    public bool IsOpen => _isOpen && _handle != IntPtr.Zero;

    /// <summary>
    /// Get the file path being read
    /// </summary>
    public string FilePath => _filePath;

    /// <summary>
    /// Create a new D3plot data loader.
    /// </summary>
    /// <param name="filePath">Path to the d3plot file (base file without number suffix)</param>
    public D3plotDataLoader(string filePath)
    {
        _filePath = filePath;

        // Initialize the native library
        D3plotNativeWrapper.Initialize();

        // Open the file
        Open();
    }

    private void Open()
    {
        _handle = D3plotNativeWrapper.Open(_filePath);
        if (_handle == IntPtr.Zero)
        {
            var error = D3plotNativeWrapper.GetLastError();
            throw new IOException($"Failed to open D3plot file '{_filePath}': {D3plotNativeWrapper.GetErrorMessage(error)}");
        }

        _isOpen = true;

        // Load file info
        LoadFileInfo();
    }

    private void LoadFileInfo()
    {
        var result = D3plotNativeWrapper.GetFileInfo(_handle, out _nativeFileInfo);
        if (result != KooError.Success)
        {
            throw new IOException($"Failed to get file info: {D3plotNativeWrapper.GetErrorMessage(result)}");
        }

        result = D3plotNativeWrapper.GetMeshInfo(_handle, out _nativeMeshInfo);
        if (result != KooError.Success)
        {
            throw new IOException($"Failed to get mesh info: {D3plotNativeWrapper.GetErrorMessage(result)}");
        }

        // Get file size
        long fileSize = 0;
        try
        {
            var fileInfo = new FileInfo(_filePath);
            if (fileInfo.Exists)
            {
                fileSize = fileInfo.Length;

                // Also count d3plot01, d3plot02, etc.
                var dir = fileInfo.DirectoryName ?? ".";
                var baseName = fileInfo.Name;
                for (int i = 1; i <= 999; i++)
                {
                    var suffix = i.ToString("D2");
                    var familyFile = Path.Combine(dir, baseName + suffix);
                    if (File.Exists(familyFile))
                    {
                        fileSize += new FileInfo(familyFile).Length;
                    }
                    else
                    {
                        break;
                    }
                }
            }
        }
        catch
        {
            // Ignore file size calculation errors
        }

        _fileInfo = new DataFileInfo(
            FormatType: "D3plot",
            FormatVersion: D3plotNativeWrapper.GetVersion(),
            NumNodes: _nativeFileInfo.NumNodes,
            NumSolids: _nativeFileInfo.NumSolids,
            NumShells: _nativeFileInfo.NumShells,
            NumBeams: _nativeFileInfo.NumBeams,
            NumThickShells: _nativeFileInfo.NumThickShells,
            NumTimesteps: _nativeFileInfo.NumStates,
            FileSizeBytes: fileSize,
            CompressionRatio: 1.0,  // D3plot is not compressed
            Title: _nativeFileInfo.Title?.Trim() ?? ""
        );
    }

    /// <summary>
    /// Get file metadata information
    /// </summary>
    public DataFileInfo GetFileInfo()
    {
        ThrowIfNotOpen();
        return _fileInfo ?? throw new InvalidOperationException("File info not loaded");
    }

    /// <summary>
    /// Get list of available timestep indices
    /// </summary>
    public List<int> GetTimestepList()
    {
        ThrowIfNotOpen();

        var numStates = D3plotNativeWrapper.GetNumStates(_handle);
        var timesteps = new List<int>(numStates);
        for (int i = 0; i < numStates; i++)
        {
            timesteps.Add(i);
        }
        return timesteps;
    }

    /// <summary>
    /// Get simulation time for a specific timestep
    /// </summary>
    public double GetTimestepTime(int timestep)
    {
        ThrowIfNotOpen();
        return D3plotNativeWrapper.GetStateTime(_handle, timestep);
    }

    /// <summary>
    /// Get mesh geometry data (cached after first call)
    /// </summary>
    public MeshData GetMeshData()
    {
        ThrowIfNotOpen();

        if (_meshData != null) return _meshData;

        _meshData = new MeshData();

        // Read node positions
        if (_nativeMeshInfo.NumNodes > 0)
        {
            _meshData.NodePositions = new float[_nativeMeshInfo.NumNodes * 3];
            var result = D3plotNativeWrapper.ReadNodes(_handle, _meshData.NodePositions);
            if (result != KooError.Success)
            {
                Console.WriteLine($"Warning: Failed to read nodes: {D3plotNativeWrapper.GetErrorMessage(result)}");
                _meshData.NodePositions = Array.Empty<float>();
            }

            // Read node IDs
            _meshData.NodeIds = new int[_nativeMeshInfo.NumNodes];
            result = D3plotNativeWrapper.ReadNodeIds(_handle, _meshData.NodeIds);
            if (result != KooError.Success)
            {
                // Generate sequential IDs as fallback
                for (int i = 0; i < _nativeMeshInfo.NumNodes; i++)
                {
                    _meshData.NodeIds[i] = i + 1;
                }
            }
        }

        // Read solid element connectivity
        if (_nativeMeshInfo.NumSolids > 0)
        {
            _meshData.SolidConnectivity = new int[_nativeMeshInfo.NumSolids * 8];
            var result = D3plotNativeWrapper.ReadSolidConnectivity(_handle, _meshData.SolidConnectivity);
            if (result != KooError.Success)
            {
                Console.WriteLine($"Warning: Failed to read solid connectivity: {D3plotNativeWrapper.GetErrorMessage(result)}");
                _meshData.SolidConnectivity = Array.Empty<int>();
            }
            else
            {
                // Convert from 1-based (LS-DYNA) to 0-based (array index)
                for (int i = 0; i < _meshData.SolidConnectivity.Length; i++)
                {
                    if (_meshData.SolidConnectivity[i] > 0)
                        _meshData.SolidConnectivity[i]--;
                }
            }

            // Read solid part IDs
            _meshData.SolidPartIds = new int[_nativeMeshInfo.NumSolids];
            result = D3plotNativeWrapper.ReadSolidPartIds(_handle, _meshData.SolidPartIds);
            if (result != KooError.Success)
            {
                // Set default part ID
                Array.Fill(_meshData.SolidPartIds, 1);
            }
        }

        // Read shell element connectivity
        if (_nativeMeshInfo.NumShells > 0)
        {
            _meshData.ShellConnectivity = new int[_nativeMeshInfo.NumShells * 4];
            var result = D3plotNativeWrapper.ReadShellConnectivity(_handle, _meshData.ShellConnectivity);
            if (result != KooError.Success)
            {
                Console.WriteLine($"Warning: Failed to read shell connectivity: {D3plotNativeWrapper.GetErrorMessage(result)}");
                _meshData.ShellConnectivity = Array.Empty<int>();
            }
            else
            {
                // Convert from 1-based (LS-DYNA) to 0-based (array index)
                for (int i = 0; i < _meshData.ShellConnectivity.Length; i++)
                {
                    if (_meshData.ShellConnectivity[i] > 0)
                        _meshData.ShellConnectivity[i]--;
                }
            }

            // Read shell part IDs
            _meshData.ShellPartIds = new int[_nativeMeshInfo.NumShells];
            result = D3plotNativeWrapper.ReadShellPartIds(_handle, _meshData.ShellPartIds);
            if (result != KooError.Success)
            {
                Array.Fill(_meshData.ShellPartIds, 1);
            }
        }

        // Read beam element connectivity
        if (_nativeMeshInfo.NumBeams > 0)
        {
            _meshData.BeamConnectivity = new int[_nativeMeshInfo.NumBeams * 2];
            var result = D3plotNativeWrapper.ReadBeamConnectivity(_handle, _meshData.BeamConnectivity);
            if (result != KooError.Success)
            {
                Console.WriteLine($"Warning: Failed to read beam connectivity: {D3plotNativeWrapper.GetErrorMessage(result)}");
                _meshData.BeamConnectivity = Array.Empty<int>();
            }
            else
            {
                // Convert from 1-based (LS-DYNA) to 0-based (array index)
                for (int i = 0; i < _meshData.BeamConnectivity.Length; i++)
                {
                    if (_meshData.BeamConnectivity[i] > 0)
                        _meshData.BeamConnectivity[i]--;
                }
            }
        }

        return _meshData;
    }

    /// <summary>
    /// Get state data for a specific timestep
    /// </summary>
    public StateData GetStateData(int timestep)
    {
        ThrowIfNotOpen();

        // Check cache
        if (_stateCache.TryGetValue(timestep, out var cachedState))
        {
            return cachedState;
        }

        var state = new StateData
        {
            Time = GetTimestepTime(timestep)
        };

        // Read displacement data if available
        if (_nativeFileInfo.HasDisplacement != 0 && _nativeMeshInfo.NumNodes > 0)
        {
            state.Displacements = new float[_nativeMeshInfo.NumNodes * 3];
            var result = D3plotNativeWrapper.ReadDisplacement(_handle, timestep, state.Displacements);
            if (result != KooError.Success)
            {
                Console.WriteLine($"Warning: Failed to read displacement for timestep {timestep}: {D3plotNativeWrapper.GetErrorMessage(result)}");
                state.Displacements = Array.Empty<float>();
            }
        }

        // Read velocity data if available
        if (_nativeFileInfo.HasVelocity != 0 && _nativeMeshInfo.NumNodes > 0)
        {
            state.Velocities = new float[_nativeMeshInfo.NumNodes * 3];
            var result = D3plotNativeWrapper.ReadVelocity(_handle, timestep, state.Velocities);
            if (result != KooError.Success)
            {
                state.Velocities = Array.Empty<float>();
            }
        }

        // Read acceleration data if available
        if (_nativeFileInfo.HasAcceleration != 0 && _nativeMeshInfo.NumNodes > 0)
        {
            state.Accelerations = new float[_nativeMeshInfo.NumNodes * 3];
            var result = D3plotNativeWrapper.ReadAcceleration(_handle, timestep, state.Accelerations);
            if (result != KooError.Success)
            {
                state.Accelerations = Array.Empty<float>();
            }
        }

        // Read stress data - compute Von Mises from displacement if stress not available
        // For now, compute displacement magnitude as a proxy for visualization
        if (state.Displacements.Length > 0)
        {
            int numNodes = state.Displacements.Length / 3;
            state.StressData = new float[numNodes];  // One value per node (displacement magnitude)
            for (int i = 0; i < numNodes; i++)
            {
                float dx = state.Displacements[i * 3 + 0];
                float dy = state.Displacements[i * 3 + 1];
                float dz = state.Displacements[i * 3 + 2];
                state.StressData[i] = MathF.Sqrt(dx * dx + dy * dy + dz * dz);
            }
        }

        // Cache the state (limit cache size with LRU-like behavior)
        if (_stateCache.Count >= MaxCacheSize)
        {
            // Remove oldest quarter of entries
            var keysToRemove = _stateCache.Keys.OrderBy(k => k).Take(MaxCacheSize / 4).ToList();
            foreach (var key in keysToRemove)
            {
                _stateCache.Remove(key);
            }
        }
        _stateCache[timestep] = state;

        return state;
    }

    /// <summary>
    /// Clear the state data cache to free memory
    /// </summary>
    public void ClearStateCache()
    {
        _stateCache.Clear();
    }

    private void ThrowIfNotOpen()
    {
        if (!IsOpen)
        {
            throw new InvalidOperationException("D3plot file is not open");
        }
    }

    /// <summary>
    /// Dispose the loader and release native resources
    /// </summary>
    public void Dispose()
    {
        if (_isOpen && _handle != IntPtr.Zero)
        {
            D3plotNativeWrapper.Close(_handle);
            _handle = IntPtr.Zero;
            _isOpen = false;
        }
        _stateCache.Clear();
        GC.SuppressFinalize(this);
    }

    /// <summary>
    /// Finalizer
    /// </summary>
    ~D3plotDataLoader()
    {
        Dispose();
    }
}

/// <summary>
/// Factory for creating the appropriate data loader based on file type
/// </summary>
public static class DataLoaderFactory
{
    /// <summary>
    /// Create a data loader for the given file path.
    /// Automatically detects file type (HDF5 or D3plot).
    /// </summary>
    /// <param name="filePath">Path to the data file</param>
    /// <returns>An IDataLoader implementation</returns>
    public static IDataLoader Create(string filePath)
    {
        if (string.IsNullOrEmpty(filePath))
        {
            throw new ArgumentException("File path cannot be null or empty", nameof(filePath));
        }

        // Check file extension and magic bytes
        var extension = Path.GetExtension(filePath).ToLowerInvariant();

        if (extension == ".h5" || extension == ".hdf5")
        {
            return new Hdf5DataLoader(filePath);
        }

        // Check if it's an HDF5 file by magic bytes
        if (File.Exists(filePath))
        {
            try
            {
                using var fs = new FileStream(filePath, FileMode.Open, FileAccess.Read, FileShare.Read);
                byte[] magic = new byte[8];
                if (fs.Read(magic, 0, 8) == 8)
                {
                    // HDF5 magic bytes: 0x89 0x48 0x44 0x46 0x0d 0x0a 0x1a 0x0a
                    if (magic[0] == 0x89 && magic[1] == 0x48 && magic[2] == 0x44 && magic[3] == 0x46)
                    {
                        return new Hdf5DataLoader(filePath);
                    }
                }
            }
            catch
            {
                // Fall through to D3plot
            }
        }

        // Default to D3plot
        return new D3plotDataLoader(filePath);
    }

    /// <summary>
    /// Check if D3plot native library is available
    /// </summary>
    public static bool IsD3plotSupported()
    {
        try
        {
            return D3plotNativeWrapper.IsD3plotAvailable();
        }
        catch
        {
            return false;
        }
    }

    /// <summary>
    /// Check if HDF5 library is available
    /// </summary>
    public static bool IsHdf5Supported()
    {
        try
        {
            return Hdf5NativeLoader.IsHdf5Available();
        }
        catch
        {
            return false;
        }
    }
}
