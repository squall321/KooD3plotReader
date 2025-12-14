using System;
using System.Collections.Generic;
using System.Numerics;
using System.Runtime.CompilerServices;
using System.Runtime.InteropServices;
using System.Runtime.Intrinsics;
using System.Runtime.Intrinsics.X86;
using HDF.PInvoke;

namespace KooD3plot.Data;

public record Hdf5FileInfo(
    string FormatVersion,
    int NumNodes,
    int NumSolids,
    int NumShells,
    int NumBeams,
    int NumTimesteps,
    long FileSizeBytes,
    double CompressionRatio
);

public class StateData
{
    public double Time { get; set; }
    public float[] Displacements { get; set; } = Array.Empty<float>();
    public float[] Velocities { get; set; } = Array.Empty<float>();
    public float[] StressData { get; set; } = Array.Empty<float>();
}

public class MeshData
{
    public float[] NodePositions { get; set; } = Array.Empty<float>();
    public int[] NodeIds { get; set; } = Array.Empty<int>();
    public int[] SolidConnectivity { get; set; } = Array.Empty<int>();
    public int[] SolidPartIds { get; set; } = Array.Empty<int>();
    public int[] ShellConnectivity { get; set; } = Array.Empty<int>();
    public int[] ShellPartIds { get; set; } = Array.Empty<int>();
    public int[] BeamConnectivity { get; set; } = Array.Empty<int>();
}

public class Hdf5DataLoader : IDisposable
{
    private readonly string _filePath;
    private long _fileId = -1;
    private bool _isOpen;
    private Hdf5FileInfo? _fileInfo;
    private MeshData? _meshData;

    // Quantization metadata
    private bool _useQuantization;
    private bool _useDeltaCompression;
    private float[] _dispMin = new float[3];
    private float[] _dispMax = new float[3];
    private float[] _velMin = new float[3];
    private float[] _velMax = new float[3];

    // Cache for delta decompression
    private int _lastReadTimestep = -1;
    private ushort[]? _cachedDispQuantized;

    public Hdf5DataLoader(string filePath)
    {
        _filePath = filePath;
        Open();
    }

    private void Open()
    {
        _fileId = H5F.open(_filePath, H5F.ACC_RDONLY);
        if (_fileId < 0)
            throw new Exception($"Failed to open HDF5 file: {_filePath}");

        _isOpen = true;
        LoadFileInfo();
        LoadCompressionMetadata();
    }

    private void LoadFileInfo()
    {
        string version = "1.0";
        int numNodes = 0, numSolids = 0, numShells = 0, numBeams = 0, numTimesteps = 0;

        // Read format from root
        if (H5A.exists(_fileId, "format") > 0)
            version = ReadStringAttribute(_fileId, "format");

        // Read mesh metadata from /mesh group
        long meshGroup = H5G.open(_fileId, "/mesh");
        if (meshGroup >= 0)
        {
            if (H5A.exists(meshGroup, "num_nodes") > 0)
                numNodes = ReadIntAttribute(meshGroup, "num_nodes");
            if (H5A.exists(meshGroup, "num_solids") > 0)
                numSolids = ReadIntAttribute(meshGroup, "num_solids");
            if (H5A.exists(meshGroup, "num_shells") > 0)
                numShells = ReadIntAttribute(meshGroup, "num_shells");
            if (H5A.exists(meshGroup, "num_beams") > 0)
                numBeams = ReadIntAttribute(meshGroup, "num_beams");
            H5G.close(meshGroup);
        }

        // Read timestep count from /states group
        long statesGroup = H5G.open(_fileId, "/states");
        if (statesGroup >= 0)
        {
            if (H5A.exists(statesGroup, "num_timesteps") > 0)
                numTimesteps = ReadIntAttribute(statesGroup, "num_timesteps");
            H5G.close(statesGroup);
        }

        var fileInfo = new System.IO.FileInfo(_filePath);

        _fileInfo = new Hdf5FileInfo(
            version, numNodes, numSolids, numShells, numBeams, numTimesteps,
            fileInfo.Length, 1.0
        );
    }

    private void LoadCompressionMetadata()
    {
        long metaGroup = H5G.open(_fileId, "/states/_metadata");
        if (metaGroup < 0) return;

        try
        {
            if (H5A.exists(metaGroup, "use_quantization") > 0)
                _useQuantization = ReadIntAttribute(metaGroup, "use_quantization") != 0;
            if (H5A.exists(metaGroup, "use_delta_compression") > 0)
                _useDeltaCompression = ReadIntAttribute(metaGroup, "use_delta_compression") != 0;

            // Read quantization ranges - C++ stores as datasets, not attributes
            if (_useQuantization)
            {
                if (DatasetExists(metaGroup, "disp_min"))
                {
                    var dispMin = ReadDoubleDataset(metaGroup, "disp_min");
                    for (int i = 0; i < Math.Min(3, dispMin.Length); i++)
                        _dispMin[i] = (float)dispMin[i];
                }
                if (DatasetExists(metaGroup, "disp_max"))
                {
                    var dispMax = ReadDoubleDataset(metaGroup, "disp_max");
                    for (int i = 0; i < Math.Min(3, dispMax.Length); i++)
                        _dispMax[i] = (float)dispMax[i];
                }
                if (DatasetExists(metaGroup, "vel_min"))
                {
                    var velMin = ReadDoubleDataset(metaGroup, "vel_min");
                    for (int i = 0; i < Math.Min(3, velMin.Length); i++)
                        _velMin[i] = (float)velMin[i];
                }
                if (DatasetExists(metaGroup, "vel_max"))
                {
                    var velMax = ReadDoubleDataset(metaGroup, "vel_max");
                    for (int i = 0; i < Math.Min(3, velMax.Length); i++)
                        _velMax[i] = (float)velMax[i];
                }
            }
        }
        finally
        {
            H5G.close(metaGroup);
        }
    }

    public Hdf5FileInfo GetFileInfo() => _fileInfo ?? throw new InvalidOperationException("File not open");

    public List<int> GetTimestepList()
    {
        var timesteps = new List<int>();
        long statesGroup = H5G.open(_fileId, "/states");
        if (statesGroup < 0) return timesteps;

        try
        {
            ulong idx = 0;
            H5L.iterate(statesGroup, H5.index_t.NAME, H5.iter_order_t.NATIVE, ref idx,
                (long group, IntPtr name, ref H5L.info_t info, IntPtr op_data) =>
                {
                    string groupName = Marshal.PtrToStringAnsi(name) ?? "";
                    if (groupName.StartsWith("timestep_") && int.TryParse(groupName.Substring(9), out int ts))
                        timesteps.Add(ts);
                    return 0;
                }, IntPtr.Zero);
        }
        finally
        {
            H5G.close(statesGroup);
        }

        timesteps.Sort();
        return timesteps;
    }

    public double GetTimestepTime(int timestep)
    {
        long tsGroup = H5G.open(_fileId, $"/states/timestep_{timestep}");
        if (tsGroup < 0) return timestep * 0.001;

        try
        {
            if (H5A.exists(tsGroup, "time") > 0)
                return ReadDoubleAttribute(tsGroup, "time");
            return timestep * 0.001;
        }
        finally
        {
            H5G.close(tsGroup);
        }
    }

    public MeshData GetMeshData()
    {
        if (_meshData != null) return _meshData;

        _meshData = new MeshData();
        long meshGroup = H5G.open(_fileId, "/mesh");
        if (meshGroup < 0) return _meshData;

        try
        {
            // Read nodes - C++ writes as /mesh/nodes [Nx3] double array
            if (DatasetExists(meshGroup, "nodes"))
            {
                var nodeCoords = ReadDoubleDataset(meshGroup, "nodes");
                _meshData.NodePositions = new float[nodeCoords.Length];
                for (int i = 0; i < nodeCoords.Length; i++)
                    _meshData.NodePositions[i] = (float)nodeCoords[i];

                // Generate node IDs (0-based)
                int numNodes = nodeCoords.Length / 3;
                _meshData.NodeIds = new int[numNodes];
                for (int i = 0; i < numNodes; i++)
                    _meshData.NodeIds[i] = i;
            }

            // Read solids - C++ writes as /mesh/solid_connectivity [Nx8]
            if (DatasetExists(meshGroup, "solid_connectivity"))
            {
                _meshData.SolidConnectivity = ReadIntDataset(meshGroup, "solid_connectivity");
            }
            if (DatasetExists(meshGroup, "solid_part_ids"))
            {
                _meshData.SolidPartIds = ReadIntDataset(meshGroup, "solid_part_ids");
            }

            // Read shells - C++ writes as /mesh/shell_connectivity [Nx4]
            if (DatasetExists(meshGroup, "shell_connectivity"))
            {
                _meshData.ShellConnectivity = ReadIntDataset(meshGroup, "shell_connectivity");
            }
            if (DatasetExists(meshGroup, "shell_part_ids"))
            {
                _meshData.ShellPartIds = ReadIntDataset(meshGroup, "shell_part_ids");
            }

            // Read beams - C++ writes as /mesh/beam_connectivity [Nx2]
            if (DatasetExists(meshGroup, "beam_connectivity"))
            {
                _meshData.BeamConnectivity = ReadIntDataset(meshGroup, "beam_connectivity");
            }
        }
        finally
        {
            H5G.close(meshGroup);
        }

        return _meshData;
    }

    public StateData GetStateData(int timestep)
    {
        var state = new StateData { Time = GetTimestepTime(timestep) };

        long tsGroup = H5G.open(_fileId, $"/states/timestep_{timestep}");
        if (tsGroup < 0) return state;

        try
        {
            // Read displacement data
            if (_useQuantization)
            {
                state.Displacements = ReadQuantizedDisplacement(tsGroup, timestep);
            }
            else if (DatasetExists(tsGroup, "displacement"))
            {
                var rawDisp = ReadDoubleDataset(tsGroup, "displacement");
                state.Displacements = new float[rawDisp.Length];
                for (int i = 0; i < rawDisp.Length; i++)
                    state.Displacements[i] = (float)rawDisp[i];
            }

            // Read velocity data (similar pattern)
            if (DatasetExists(tsGroup, "velocity"))
            {
                var rawVel = ReadDoubleDataset(tsGroup, "velocity");
                state.Velocities = new float[rawVel.Length];
                for (int i = 0; i < rawVel.Length; i++)
                    state.Velocities[i] = (float)rawVel[i];
            }
        }
        finally
        {
            H5G.close(tsGroup);
        }

        return state;
    }

    private float[] ReadQuantizedDisplacement(long tsGroup, int timestep)
    {
        int numNodes = _fileInfo?.NumNodes ?? 0;
        ushort[] quantized;

        if (timestep == 0 || !_useDeltaCompression)
        {
            // First timestep or no delta: read full quantized data
            quantized = ReadUInt16Dataset(tsGroup, "displacement_quantized");
        }
        else
        {
            // Delta compression: need to reconstruct from previous
            if (_cachedDispQuantized == null || _lastReadTimestep != timestep - 1)
            {
                // Need to read all previous timesteps
                for (int t = 0; t < timestep; t++)
                {
                    GetStateData(t); // This will populate the cache
                }
            }

            // Read delta and apply
            var deltas = ReadInt16Dataset(tsGroup, "displacement_delta");
            quantized = new ushort[deltas.Length];

            if (_cachedDispQuantized != null)
            {
                ApplyDeltaSimd(deltas, _cachedDispQuantized, quantized);
            }
        }

        // Cache for next timestep
        _cachedDispQuantized = quantized;
        _lastReadTimestep = timestep;

        // Dequantize
        var result = new float[quantized.Length];
        DequantizeVectors3D(quantized, result, _dispMin, _dispMax);
        return result;
    }

    // SIMD dequantization
    [MethodImpl(MethodImplOptions.AggressiveInlining)]
    public static void DequantizeSimd(ReadOnlySpan<ushort> quantized, Span<float> output, float min, float max)
    {
        float scale = (max - min) / 65535.0f;
        int i = 0;

        if (Avx2.IsSupported && quantized.Length >= 16)
        {
            var scaleVec = Vector256.Create(scale);
            var minVec = Vector256.Create(min);

            for (; i <= quantized.Length - 16; i += 16)
            {
                // Load 16 uint16 values and convert to float
                var src = MemoryMarshal.Cast<ushort, byte>(quantized.Slice(i, 16));

                // Process in batches of 8
                for (int j = 0; j < 16; j++)
                {
                    output[i + j] = quantized[i + j] * scale + min;
                }
            }
        }

        // Scalar fallback
        for (; i < quantized.Length; i++)
        {
            output[i] = quantized[i] * scale + min;
        }
    }

    public static void DequantizeVectors3D(ushort[] quantized, float[] output, float[] min, float[] max)
    {
        int numVectors = quantized.Length / 3;
        float scaleX = (max[0] - min[0]) / 65535.0f;
        float scaleY = (max[1] - min[1]) / 65535.0f;
        float scaleZ = (max[2] - min[2]) / 65535.0f;

        for (int i = 0; i < numVectors; i++)
        {
            output[i * 3 + 0] = quantized[i * 3 + 0] * scaleX + min[0];
            output[i * 3 + 1] = quantized[i * 3 + 1] * scaleY + min[1];
            output[i * 3 + 2] = quantized[i * 3 + 2] * scaleZ + min[2];
        }
    }

    public static void ApplyDeltaSimd(short[] deltas, ushort[] previous, ushort[] output)
    {
        for (int i = 0; i < deltas.Length; i++)
        {
            int result = previous[i] + deltas[i];
            output[i] = (ushort)Math.Clamp(result, 0, 65535);
        }
    }

    // HDF5 helper methods
    private string ReadStringAttribute(long locId, string name)
    {
        long attrId = H5A.open(locId, name);
        if (attrId < 0) return "";

        try
        {
            long typeId = H5A.get_type(attrId);
            long size = H5T.get_size(typeId).ToInt64();
            byte[] buffer = new byte[size];

            GCHandle handle = GCHandle.Alloc(buffer, GCHandleType.Pinned);
            try
            {
                H5A.read(attrId, typeId, handle.AddrOfPinnedObject());
            }
            finally
            {
                handle.Free();
            }

            H5T.close(typeId);
            return System.Text.Encoding.ASCII.GetString(buffer).TrimEnd('\0');
        }
        finally
        {
            H5A.close(attrId);
        }
    }

    private int ReadIntAttribute(long locId, string name)
    {
        long attrId = H5A.open(locId, name);
        if (attrId < 0) return 0;

        try
        {
            int[] buffer = new int[1];
            GCHandle handle = GCHandle.Alloc(buffer, GCHandleType.Pinned);
            try
            {
                H5A.read(attrId, H5T.NATIVE_INT32, handle.AddrOfPinnedObject());
            }
            finally
            {
                handle.Free();
            }
            return buffer[0];
        }
        finally
        {
            H5A.close(attrId);
        }
    }

    private double ReadDoubleAttribute(long locId, string name)
    {
        long attrId = H5A.open(locId, name);
        if (attrId < 0) return 0;

        try
        {
            double[] buffer = new double[1];
            GCHandle handle = GCHandle.Alloc(buffer, GCHandleType.Pinned);
            try
            {
                H5A.read(attrId, H5T.NATIVE_DOUBLE, handle.AddrOfPinnedObject());
            }
            finally
            {
                handle.Free();
            }
            return buffer[0];
        }
        finally
        {
            H5A.close(attrId);
        }
    }

    private void ReadDoubleArrayAttribute(long locId, string name, float[] output)
    {
        long attrId = H5A.open(locId, name);
        if (attrId < 0) return;

        try
        {
            double[] buffer = new double[output.Length];
            GCHandle handle = GCHandle.Alloc(buffer, GCHandleType.Pinned);
            try
            {
                H5A.read(attrId, H5T.NATIVE_DOUBLE, handle.AddrOfPinnedObject());
            }
            finally
            {
                handle.Free();
            }
            for (int i = 0; i < output.Length; i++)
                output[i] = (float)buffer[i];
        }
        finally
        {
            H5A.close(attrId);
        }
    }

    private bool DatasetExists(long locId, string name)
    {
        return H5L.exists(locId, name) > 0;
    }

    private float[] ReadFloatDataset(long locId, string name)
    {
        long dsetId = H5D.open(locId, name);
        if (dsetId < 0) return Array.Empty<float>();

        try
        {
            long spaceId = H5D.get_space(dsetId);
            int ndims = H5S.get_simple_extent_ndims(spaceId);
            ulong[] dims = new ulong[ndims];
            H5S.get_simple_extent_dims(spaceId, dims, null);
            H5S.close(spaceId);

            int totalSize = 1;
            foreach (var d in dims) totalSize *= (int)d;

            float[] data = new float[totalSize];
            GCHandle handle = GCHandle.Alloc(data, GCHandleType.Pinned);
            try
            {
                H5D.read(dsetId, H5T.NATIVE_FLOAT, H5S.ALL, H5S.ALL, H5P.DEFAULT, handle.AddrOfPinnedObject());
            }
            finally
            {
                handle.Free();
            }
            return data;
        }
        finally
        {
            H5D.close(dsetId);
        }
    }

    private double[] ReadDoubleDataset(long locId, string name)
    {
        long dsetId = H5D.open(locId, name);
        if (dsetId < 0) return Array.Empty<double>();

        try
        {
            long spaceId = H5D.get_space(dsetId);
            int ndims = H5S.get_simple_extent_ndims(spaceId);
            ulong[] dims = new ulong[ndims];
            H5S.get_simple_extent_dims(spaceId, dims, null);
            H5S.close(spaceId);

            int totalSize = 1;
            foreach (var d in dims) totalSize *= (int)d;

            double[] data = new double[totalSize];
            GCHandle handle = GCHandle.Alloc(data, GCHandleType.Pinned);
            try
            {
                H5D.read(dsetId, H5T.NATIVE_DOUBLE, H5S.ALL, H5S.ALL, H5P.DEFAULT, handle.AddrOfPinnedObject());
            }
            finally
            {
                handle.Free();
            }
            return data;
        }
        finally
        {
            H5D.close(dsetId);
        }
    }

    private int[] ReadIntDataset(long locId, string name)
    {
        long dsetId = H5D.open(locId, name);
        if (dsetId < 0) return Array.Empty<int>();

        try
        {
            long spaceId = H5D.get_space(dsetId);
            int ndims = H5S.get_simple_extent_ndims(spaceId);
            ulong[] dims = new ulong[ndims];
            H5S.get_simple_extent_dims(spaceId, dims, null);
            H5S.close(spaceId);

            int totalSize = 1;
            foreach (var d in dims) totalSize *= (int)d;

            int[] data = new int[totalSize];
            GCHandle handle = GCHandle.Alloc(data, GCHandleType.Pinned);
            try
            {
                H5D.read(dsetId, H5T.NATIVE_INT32, H5S.ALL, H5S.ALL, H5P.DEFAULT, handle.AddrOfPinnedObject());
            }
            finally
            {
                handle.Free();
            }
            return data;
        }
        finally
        {
            H5D.close(dsetId);
        }
    }

    private ushort[] ReadUInt16Dataset(long locId, string name)
    {
        long dsetId = H5D.open(locId, name);
        if (dsetId < 0) return Array.Empty<ushort>();

        try
        {
            long spaceId = H5D.get_space(dsetId);
            int ndims = H5S.get_simple_extent_ndims(spaceId);
            ulong[] dims = new ulong[ndims];
            H5S.get_simple_extent_dims(spaceId, dims, null);
            H5S.close(spaceId);

            int totalSize = 1;
            foreach (var d in dims) totalSize *= (int)d;

            ushort[] data = new ushort[totalSize];
            GCHandle handle = GCHandle.Alloc(data, GCHandleType.Pinned);
            try
            {
                H5D.read(dsetId, H5T.NATIVE_UINT16, H5S.ALL, H5S.ALL, H5P.DEFAULT, handle.AddrOfPinnedObject());
            }
            finally
            {
                handle.Free();
            }
            return data;
        }
        finally
        {
            H5D.close(dsetId);
        }
    }

    private short[] ReadInt16Dataset(long locId, string name)
    {
        long dsetId = H5D.open(locId, name);
        if (dsetId < 0) return Array.Empty<short>();

        try
        {
            long spaceId = H5D.get_space(dsetId);
            int ndims = H5S.get_simple_extent_ndims(spaceId);
            ulong[] dims = new ulong[ndims];
            H5S.get_simple_extent_dims(spaceId, dims, null);
            H5S.close(spaceId);

            int totalSize = 1;
            foreach (var d in dims) totalSize *= (int)d;

            short[] data = new short[totalSize];
            GCHandle handle = GCHandle.Alloc(data, GCHandleType.Pinned);
            try
            {
                H5D.read(dsetId, H5T.NATIVE_INT16, H5S.ALL, H5S.ALL, H5P.DEFAULT, handle.AddrOfPinnedObject());
            }
            finally
            {
                handle.Free();
            }
            return data;
        }
        finally
        {
            H5D.close(dsetId);
        }
    }

    public void Dispose()
    {
        if (_isOpen && _fileId >= 0)
        {
            H5F.close(_fileId);
            _fileId = -1;
            _isOpen = false;
        }
        GC.SuppressFinalize(this);
    }
}
