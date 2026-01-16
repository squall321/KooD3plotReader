using System;
using System.IO;
using System.Runtime.InteropServices;

namespace KooD3plot.Data;

/// <summary>
/// Error codes returned by the C API
/// </summary>
public enum KooError
{
    Success = 0,
    FileNotFound = 1,
    InvalidFormat = 2,
    ReadFailed = 3,
    InvalidHandle = 4,
    OutOfMemory = 5,
    InvalidIndex = 6,
    Unknown = 99
}

/// <summary>
/// File information structure (matches koo_file_info_t)
/// </summary>
[StructLayout(LayoutKind.Sequential, CharSet = CharSet.Ansi)]
public struct KooFileInfo
{
    [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 81)]
    public string Title;
    public int NumNodes;
    public int NumSolids;
    public int NumShells;
    public int NumBeams;
    public int NumThickShells;
    public int NumStates;
    public int WordSize;
    public int HasDisplacement;
    public int HasVelocity;
    public int HasAcceleration;
    public int HasTemperature;
}

/// <summary>
/// Mesh information structure (matches koo_mesh_info_t)
/// </summary>
[StructLayout(LayoutKind.Sequential)]
public struct KooMeshInfo
{
    public int NumNodes;
    public int NumSolids;
    public int NumShells;
    public int NumBeams;
    public int NumThickShells;
}

/// <summary>
/// P/Invoke wrapper for kood3plot_net native library.
/// Provides D3plot file reading functionality for .NET applications.
/// </summary>
public static class D3plotNativeWrapper
{
    private const string LibraryName = "kood3plot_net";

    private static bool _initialized = false;
    private static readonly object _lock = new();
    private static string? _loadedLibraryPath = null;

    #region P/Invoke Declarations

    [DllImport(LibraryName, CallingConvention = CallingConvention.Cdecl)]
    private static extern IntPtr koo_open([MarshalAs(UnmanagedType.LPUTF8Str)] string filepath);

    [DllImport(LibraryName, CallingConvention = CallingConvention.Cdecl)]
    private static extern void koo_close(IntPtr handle);

    [DllImport(LibraryName, CallingConvention = CallingConvention.Cdecl)]
    private static extern KooError koo_get_last_error();

    [DllImport(LibraryName, CallingConvention = CallingConvention.Cdecl)]
    private static extern IntPtr koo_get_error_message(KooError error);

    [DllImport(LibraryName, CallingConvention = CallingConvention.Cdecl)]
    private static extern KooError koo_get_file_info(IntPtr handle, out KooFileInfo info);

    [DllImport(LibraryName, CallingConvention = CallingConvention.Cdecl)]
    private static extern KooError koo_get_mesh_info(IntPtr handle, out KooMeshInfo info);

    [DllImport(LibraryName, CallingConvention = CallingConvention.Cdecl)]
    private static extern int koo_get_num_states(IntPtr handle);

    [DllImport(LibraryName, CallingConvention = CallingConvention.Cdecl)]
    private static extern double koo_get_state_time(IntPtr handle, int stateIndex);

    [DllImport(LibraryName, CallingConvention = CallingConvention.Cdecl)]
    private static extern KooError koo_read_nodes(IntPtr handle, [Out] float[] buffer, int bufferSize);

    [DllImport(LibraryName, CallingConvention = CallingConvention.Cdecl)]
    private static extern KooError koo_read_nodes_double(IntPtr handle, [Out] double[] buffer, int bufferSize);

    [DllImport(LibraryName, CallingConvention = CallingConvention.Cdecl)]
    private static extern KooError koo_read_node_ids(IntPtr handle, [Out] int[] buffer, int bufferSize);

    [DllImport(LibraryName, CallingConvention = CallingConvention.Cdecl)]
    private static extern KooError koo_read_solid_connectivity(IntPtr handle, [Out] int[] buffer, int bufferSize);

    [DllImport(LibraryName, CallingConvention = CallingConvention.Cdecl)]
    private static extern KooError koo_read_solid_part_ids(IntPtr handle, [Out] int[] buffer, int bufferSize);

    [DllImport(LibraryName, CallingConvention = CallingConvention.Cdecl)]
    private static extern KooError koo_read_shell_connectivity(IntPtr handle, [Out] int[] buffer, int bufferSize);

    [DllImport(LibraryName, CallingConvention = CallingConvention.Cdecl)]
    private static extern KooError koo_read_shell_part_ids(IntPtr handle, [Out] int[] buffer, int bufferSize);

    [DllImport(LibraryName, CallingConvention = CallingConvention.Cdecl)]
    private static extern KooError koo_read_beam_connectivity(IntPtr handle, [Out] int[] buffer, int bufferSize);

    [DllImport(LibraryName, CallingConvention = CallingConvention.Cdecl)]
    private static extern KooError koo_read_displacement(IntPtr handle, int stateIndex, [Out] float[] buffer, int bufferSize);

    [DllImport(LibraryName, CallingConvention = CallingConvention.Cdecl)]
    private static extern KooError koo_read_velocity(IntPtr handle, int stateIndex, [Out] float[] buffer, int bufferSize);

    [DllImport(LibraryName, CallingConvention = CallingConvention.Cdecl)]
    private static extern KooError koo_read_acceleration(IntPtr handle, int stateIndex, [Out] float[] buffer, int bufferSize);

    [DllImport(LibraryName, CallingConvention = CallingConvention.Cdecl)]
    private static extern KooError koo_read_solid_stress(IntPtr handle, int stateIndex, [Out] float[] buffer, int bufferSize);

    [DllImport(LibraryName, CallingConvention = CallingConvention.Cdecl)]
    private static extern KooError koo_read_shell_stress(IntPtr handle, int stateIndex, [Out] float[] buffer, int bufferSize);

    [DllImport(LibraryName, CallingConvention = CallingConvention.Cdecl)]
    private static extern IntPtr koo_get_version();

    [DllImport(LibraryName, CallingConvention = CallingConvention.Cdecl)]
    private static extern float koo_calc_von_mises(float sigmaXx, float sigmaYy, float sigmaZz,
                                                    float tauXy, float tauYz, float tauZx);

    #endregion

    #region Library Loading

    /// <summary>
    /// Initialize the native library loader.
    /// Call this before using any D3plot functions.
    /// </summary>
    public static void Initialize()
    {
        if (_initialized) return;

        lock (_lock)
        {
            if (_initialized) return;

            // Set up native library resolution
            NativeLibrary.SetDllImportResolver(typeof(D3plotNativeWrapper).Assembly, ResolveDllImport);

            _initialized = true;
        }
    }

    private static IntPtr ResolveDllImport(string libraryName, System.Reflection.Assembly assembly, DllImportSearchPath? searchPath)
    {
        if (libraryName != LibraryName)
            return IntPtr.Zero;

        // Try to load from platform-specific paths
        var paths = GetPlatformLibraryPaths();

        foreach (var path in paths)
        {
            if (File.Exists(path))
            {
                try
                {
                    var handle = NativeLibrary.Load(path);
                    if (handle != IntPtr.Zero)
                    {
                        _loadedLibraryPath = path;
                        return handle;
                    }
                }
                catch
                {
                    // Try next path
                }
            }
        }

        // Let the system try default resolution
        return IntPtr.Zero;
    }

    private static string[] GetPlatformLibraryPaths()
    {
        var baseDir = AppContext.BaseDirectory;
        var projectDir = Path.GetFullPath(Path.Combine(baseDir, "..", "..", "..", ".."));

        if (RuntimeInformation.IsOSPlatform(OSPlatform.Windows))
        {
            return new[]
            {
                // Application directory
                Path.Combine(baseDir, "kood3plot_net.dll"),
                // Native subfolder (runtime ID)
                Path.Combine(baseDir, "runtimes", "win-x64", "native", "kood3plot_net.dll"),
                // Project native folder
                Path.Combine(projectDir, "native", "win-x64", "kood3plot_net.dll"),
                // Build output
                Path.Combine(projectDir, "..", "..", "build", "kood3plot_net.dll"),
                Path.Combine(projectDir, "..", "..", "installed", "library", "bin", "kood3plot_net.dll"),
            };
        }
        else if (RuntimeInformation.IsOSPlatform(OSPlatform.Linux))
        {
            return new[]
            {
                Path.Combine(baseDir, "libkood3plot_net.so"),
                Path.Combine(baseDir, "runtimes", "linux-x64", "native", "libkood3plot_net.so"),
                Path.Combine(projectDir, "native", "linux-x64", "libkood3plot_net.so"),
                "/usr/local/lib/libkood3plot_net.so",
                "/usr/lib/libkood3plot_net.so",
            };
        }
        else if (RuntimeInformation.IsOSPlatform(OSPlatform.OSX))
        {
            return new[]
            {
                Path.Combine(baseDir, "libkood3plot_net.dylib"),
                Path.Combine(baseDir, "runtimes", "osx-x64", "native", "libkood3plot_net.dylib"),
                Path.Combine(projectDir, "native", "osx-x64", "libkood3plot_net.dylib"),
                "/usr/local/lib/libkood3plot_net.dylib",
                "/opt/homebrew/lib/libkood3plot_net.dylib",
            };
        }

        return Array.Empty<string>();
    }

    /// <summary>
    /// Check if the D3plot native library is available.
    /// </summary>
    public static bool IsD3plotAvailable()
    {
        Initialize();

        try
        {
            var version = GetVersion();
            return !string.IsNullOrEmpty(version);
        }
        catch
        {
            return false;
        }
    }

    /// <summary>
    /// Get the path to the loaded native library.
    /// </summary>
    public static string? GetLoadedLibraryPath() => _loadedLibraryPath;

    #endregion

    #region Public API

    /// <summary>
    /// Open a D3plot file for reading.
    /// </summary>
    /// <param name="filepath">Path to the d3plot file</param>
    /// <returns>Handle to the opened file, or IntPtr.Zero on failure</returns>
    public static IntPtr Open(string filepath)
    {
        Initialize();
        return koo_open(filepath);
    }

    /// <summary>
    /// Close a D3plot file handle.
    /// </summary>
    public static void Close(IntPtr handle)
    {
        if (handle != IntPtr.Zero)
        {
            koo_close(handle);
        }
    }

    /// <summary>
    /// Get the last error code.
    /// </summary>
    public static KooError GetLastError() => koo_get_last_error();

    /// <summary>
    /// Get an error message for an error code.
    /// </summary>
    public static string GetErrorMessage(KooError error)
    {
        var ptr = koo_get_error_message(error);
        return ptr != IntPtr.Zero ? Marshal.PtrToStringAnsi(ptr) ?? "Unknown error" : "Unknown error";
    }

    /// <summary>
    /// Get file information.
    /// </summary>
    public static KooError GetFileInfo(IntPtr handle, out KooFileInfo info)
        => koo_get_file_info(handle, out info);

    /// <summary>
    /// Get mesh information (for buffer allocation).
    /// </summary>
    public static KooError GetMeshInfo(IntPtr handle, out KooMeshInfo info)
        => koo_get_mesh_info(handle, out info);

    /// <summary>
    /// Get number of time states.
    /// </summary>
    public static int GetNumStates(IntPtr handle) => koo_get_num_states(handle);

    /// <summary>
    /// Get time value for a specific state.
    /// </summary>
    public static double GetStateTime(IntPtr handle, int stateIndex)
        => koo_get_state_time(handle, stateIndex);

    /// <summary>
    /// Read node positions as floats.
    /// Buffer should be [numNodes * 3] floats.
    /// </summary>
    public static KooError ReadNodes(IntPtr handle, float[] buffer)
        => koo_read_nodes(handle, buffer, buffer.Length);

    /// <summary>
    /// Read node positions as doubles.
    /// Buffer should be [numNodes * 3] doubles.
    /// </summary>
    public static KooError ReadNodesDouble(IntPtr handle, double[] buffer)
        => koo_read_nodes_double(handle, buffer, buffer.Length);

    /// <summary>
    /// Read node IDs.
    /// Buffer should be [numNodes] ints.
    /// </summary>
    public static KooError ReadNodeIds(IntPtr handle, int[] buffer)
        => koo_read_node_ids(handle, buffer, buffer.Length);

    /// <summary>
    /// Read solid element connectivity.
    /// Buffer should be [numSolids * 8] ints.
    /// </summary>
    public static KooError ReadSolidConnectivity(IntPtr handle, int[] buffer)
        => koo_read_solid_connectivity(handle, buffer, buffer.Length);

    /// <summary>
    /// Read solid element part IDs.
    /// Buffer should be [numSolids] ints.
    /// </summary>
    public static KooError ReadSolidPartIds(IntPtr handle, int[] buffer)
        => koo_read_solid_part_ids(handle, buffer, buffer.Length);

    /// <summary>
    /// Read shell element connectivity.
    /// Buffer should be [numShells * 4] ints.
    /// </summary>
    public static KooError ReadShellConnectivity(IntPtr handle, int[] buffer)
        => koo_read_shell_connectivity(handle, buffer, buffer.Length);

    /// <summary>
    /// Read shell element part IDs.
    /// Buffer should be [numShells] ints.
    /// </summary>
    public static KooError ReadShellPartIds(IntPtr handle, int[] buffer)
        => koo_read_shell_part_ids(handle, buffer, buffer.Length);

    /// <summary>
    /// Read beam element connectivity.
    /// Buffer should be [numBeams * 2] ints.
    /// </summary>
    public static KooError ReadBeamConnectivity(IntPtr handle, int[] buffer)
        => koo_read_beam_connectivity(handle, buffer, buffer.Length);

    /// <summary>
    /// Read displacement data for a specific state.
    /// Buffer should be [numNodes * 3] floats.
    /// </summary>
    public static KooError ReadDisplacement(IntPtr handle, int stateIndex, float[] buffer)
        => koo_read_displacement(handle, stateIndex, buffer, buffer.Length);

    /// <summary>
    /// Read velocity data for a specific state.
    /// Buffer should be [numNodes * 3] floats.
    /// </summary>
    public static KooError ReadVelocity(IntPtr handle, int stateIndex, float[] buffer)
        => koo_read_velocity(handle, stateIndex, buffer, buffer.Length);

    /// <summary>
    /// Read acceleration data for a specific state.
    /// Buffer should be [numNodes * 3] floats.
    /// </summary>
    public static KooError ReadAcceleration(IntPtr handle, int stateIndex, float[] buffer)
        => koo_read_acceleration(handle, stateIndex, buffer, buffer.Length);

    /// <summary>
    /// Read solid stress data for a specific state.
    /// Buffer size depends on element data.
    /// </summary>
    public static KooError ReadSolidStress(IntPtr handle, int stateIndex, float[] buffer)
        => koo_read_solid_stress(handle, stateIndex, buffer, buffer.Length);

    /// <summary>
    /// Read shell stress data for a specific state.
    /// Buffer size depends on element data.
    /// </summary>
    public static KooError ReadShellStress(IntPtr handle, int stateIndex, float[] buffer)
        => koo_read_shell_stress(handle, stateIndex, buffer, buffer.Length);

    /// <summary>
    /// Get the library version string.
    /// </summary>
    public static string GetVersion()
    {
        var ptr = koo_get_version();
        return ptr != IntPtr.Zero ? Marshal.PtrToStringAnsi(ptr) ?? "unknown" : "unknown";
    }

    /// <summary>
    /// Calculate Von Mises stress from stress tensor components.
    /// </summary>
    public static float CalcVonMises(float sigmaXx, float sigmaYy, float sigmaZz,
                                      float tauXy, float tauYz, float tauZx)
        => koo_calc_von_mises(sigmaXx, sigmaYy, sigmaZz, tauXy, tauYz, tauZx);

    #endregion
}

/// <summary>
/// Safe handle wrapper for D3plot file handles.
/// Automatically closes the handle when disposed.
/// </summary>
public class D3plotHandle : SafeHandle
{
    public D3plotHandle() : base(IntPtr.Zero, true)
    {
    }

    public D3plotHandle(IntPtr handle) : base(handle, true)
    {
    }

    public override bool IsInvalid => handle == IntPtr.Zero;

    protected override bool ReleaseHandle()
    {
        if (!IsInvalid)
        {
            D3plotNativeWrapper.Close(handle);
        }
        return true;
    }

    /// <summary>
    /// Open a D3plot file.
    /// </summary>
    public static D3plotHandle Open(string filepath)
    {
        var ptr = D3plotNativeWrapper.Open(filepath);
        if (ptr == IntPtr.Zero)
        {
            var error = D3plotNativeWrapper.GetLastError();
            throw new IOException($"Failed to open D3plot file: {D3plotNativeWrapper.GetErrorMessage(error)}");
        }
        return new D3plotHandle(ptr);
    }
}
