using System;
using System.IO;
using System.Runtime.InteropServices;

namespace KooD3plot.Data;

/// <summary>
/// Cross-platform HDF5 native library loader.
/// On Windows: Uses bundled HDF5 DLLs from HDF.PInvoke.NETStandard package
/// On Linux: Uses system-installed libhdf5 (apt install libhdf5-dev)
/// On macOS: Uses Homebrew-installed HDF5 (brew install hdf5)
/// </summary>
public static class Hdf5NativeLoader
{
    private static bool _initialized = false;
    private static readonly object _lock = new();

    /// <summary>
    /// Initialize HDF5 native library loading.
    /// Call this before using any HDF5 functions.
    /// </summary>
    public static void Initialize()
    {
        if (_initialized) return;

        lock (_lock)
        {
            if (_initialized) return;

            if (RuntimeInformation.IsOSPlatform(OSPlatform.Linux))
            {
                InitializeLinux();
            }
            else if (RuntimeInformation.IsOSPlatform(OSPlatform.OSX))
            {
                InitializeMacOS();
            }
            // Windows uses bundled DLLs from NuGet package - no special handling needed

            _initialized = true;
        }
    }

    private static void InitializeLinux()
    {
        // On Linux, HDF.PInvoke looks for 'libhdf5.so' or 'hdf5.dll'
        // System HDF5 typically installs as 'libhdf5_serial.so' or 'libhdf5.so.X'
        // We need to ensure the library can be found

        var possiblePaths = new[]
        {
            // Ubuntu/Debian with libhdf5-dev
            "/usr/lib/x86_64-linux-gnu/hdf5/serial/libhdf5.so",
            "/usr/lib/x86_64-linux-gnu/libhdf5_serial.so",
            "/usr/lib/x86_64-linux-gnu/libhdf5.so",
            // CentOS/RHEL
            "/usr/lib64/libhdf5.so",
            // Generic paths
            "/usr/local/lib/libhdf5.so",
            "/usr/lib/libhdf5.so",
        };

        foreach (var path in possiblePaths)
        {
            if (File.Exists(path))
            {
                // Set environment variable for native library resolution
                var ldLibraryPath = Environment.GetEnvironmentVariable("LD_LIBRARY_PATH") ?? "";
                var dir = Path.GetDirectoryName(path);
                if (!string.IsNullOrEmpty(dir) && !ldLibraryPath.Contains(dir))
                {
                    Environment.SetEnvironmentVariable("LD_LIBRARY_PATH",
                        string.IsNullOrEmpty(ldLibraryPath) ? dir : $"{dir}:{ldLibraryPath}");
                }

                // Try to preload the library
                try
                {
                    NativeLibrary.Load(path);
                }
                catch
                {
                    // Ignore - HDF.PInvoke will try to load it
                }
                break;
            }
        }
    }

    private static void InitializeMacOS()
    {
        // On macOS, HDF5 is typically installed via Homebrew
        var possiblePaths = new[]
        {
            // Homebrew on Apple Silicon
            "/opt/homebrew/lib/libhdf5.dylib",
            "/opt/homebrew/opt/hdf5/lib/libhdf5.dylib",
            // Homebrew on Intel
            "/usr/local/lib/libhdf5.dylib",
            "/usr/local/opt/hdf5/lib/libhdf5.dylib",
        };

        foreach (var path in possiblePaths)
        {
            if (File.Exists(path))
            {
                var dir = Path.GetDirectoryName(path);
                if (!string.IsNullOrEmpty(dir))
                {
                    var dylibPath = Environment.GetEnvironmentVariable("DYLD_LIBRARY_PATH") ?? "";
                    if (!dylibPath.Contains(dir))
                    {
                        Environment.SetEnvironmentVariable("DYLD_LIBRARY_PATH",
                            string.IsNullOrEmpty(dylibPath) ? dir : $"{dir}:{dylibPath}");
                    }
                }

                try
                {
                    NativeLibrary.Load(path);
                }
                catch
                {
                    // Ignore
                }
                break;
            }
        }
    }

    /// <summary>
    /// Check if HDF5 native library is available on this platform.
    /// </summary>
    public static bool IsHdf5Available()
    {
        Initialize();

        try
        {
            // Try to call a simple HDF5 function
            uint major = 0, minor = 0, release = 0;
            var version = HDF.PInvoke.H5.get_libversion(ref major, ref minor, ref release);
            return version >= 0;
        }
        catch
        {
            return false;
        }
    }

    /// <summary>
    /// Get HDF5 library version string.
    /// </summary>
    public static string GetHdf5Version()
    {
        try
        {
            uint major = 0, minor = 0, release = 0;
            HDF.PInvoke.H5.get_libversion(ref major, ref minor, ref release);
            return $"{major}.{minor}.{release}";
        }
        catch
        {
            return "unknown";
        }
    }
}
