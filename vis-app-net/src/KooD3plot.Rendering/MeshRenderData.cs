using System;
using System.Numerics;

namespace KooD3plot.Rendering;

/// <summary>
/// Vertex data for GPU rendering
/// </summary>
public struct Vertex
{
    public Vector3 Position;
    public Vector3 Normal;
    public Vector4 Color;
    public float ScalarValue; // For color mapping

    public const uint SizeInBytes = 48; // 12 + 12 + 16 + 4 + padding
}

/// <summary>
/// Mesh data prepared for GPU rendering
/// </summary>
public class MeshRenderData
{
    /// <summary>
    /// Original node positions (reference configuration)
    /// </summary>
    public float[] BasePositions { get; set; } = Array.Empty<float>();

    /// <summary>
    /// Current displaced positions
    /// </summary>
    public float[] CurrentPositions { get; set; } = Array.Empty<float>();

    /// <summary>
    /// Per-vertex normals
    /// </summary>
    public float[] Normals { get; set; } = Array.Empty<float>();

    /// <summary>
    /// Scalar values for color mapping (e.g., von Mises stress)
    /// </summary>
    public float[] ScalarValues { get; set; } = Array.Empty<float>();

    /// <summary>
    /// Triangle indices for shell/solid surface rendering
    /// </summary>
    public uint[] Indices { get; set; } = Array.Empty<uint>();

    /// <summary>
    /// Line indices for beam rendering
    /// </summary>
    public uint[] BeamIndices { get; set; } = Array.Empty<uint>();

    /// <summary>
    /// Wireframe indices
    /// </summary>
    public uint[] WireframeIndices { get; set; } = Array.Empty<uint>();

    /// <summary>
    /// Number of vertices
    /// </summary>
    public int VertexCount { get; set; }

    /// <summary>
    /// Number of triangles
    /// </summary>
    public int TriangleCount { get; set; }

    /// <summary>
    /// Bounding box minimum
    /// </summary>
    public Vector3 BoundsMin { get; set; }

    /// <summary>
    /// Bounding box maximum
    /// </summary>
    public Vector3 BoundsMax { get; set; }

    /// <summary>
    /// Scalar range for color mapping
    /// </summary>
    public float ScalarMin { get; set; }
    public float ScalarMax { get; set; }

    /// <summary>
    /// Apply displacement with scale factor
    /// </summary>
    public void ApplyDisplacement(ReadOnlySpan<float> displacements, float scale)
    {
        if (displacements.Length != BasePositions.Length)
            throw new ArgumentException("Displacement array size mismatch");

        for (int i = 0; i < BasePositions.Length; i++)
        {
            CurrentPositions[i] = BasePositions[i] + displacements[i] * scale;
        }
    }

    /// <summary>
    /// Compute normals from triangle indices
    /// </summary>
    public void ComputeNormals()
    {
        if (Normals.Length != CurrentPositions.Length)
            Normals = new float[CurrentPositions.Length];

        // Clear normals
        Array.Clear(Normals);

        // Accumulate face normals
        for (int i = 0; i < Indices.Length; i += 3)
        {
            int i0 = (int)Indices[i] * 3;
            int i1 = (int)Indices[i + 1] * 3;
            int i2 = (int)Indices[i + 2] * 3;

            var v0 = new Vector3(CurrentPositions[i0], CurrentPositions[i0 + 1], CurrentPositions[i0 + 2]);
            var v1 = new Vector3(CurrentPositions[i1], CurrentPositions[i1 + 1], CurrentPositions[i1 + 2]);
            var v2 = new Vector3(CurrentPositions[i2], CurrentPositions[i2 + 1], CurrentPositions[i2 + 2]);

            var edge1 = v1 - v0;
            var edge2 = v2 - v0;
            var normal = Vector3.Cross(edge1, edge2);

            // Add to all three vertices
            AddNormal(i0, normal);
            AddNormal(i1, normal);
            AddNormal(i2, normal);
        }

        // Normalize
        for (int i = 0; i < Normals.Length; i += 3)
        {
            var n = new Vector3(Normals[i], Normals[i + 1], Normals[i + 2]);
            var len = n.Length();
            if (len > 0.0001f)
            {
                n /= len;
                Normals[i] = n.X;
                Normals[i + 1] = n.Y;
                Normals[i + 2] = n.Z;
            }
        }
    }

    private void AddNormal(int idx, Vector3 normal)
    {
        Normals[idx] += normal.X;
        Normals[idx + 1] += normal.Y;
        Normals[idx + 2] += normal.Z;
    }

    /// <summary>
    /// Compute bounding box from current positions
    /// </summary>
    public void ComputeBounds()
    {
        if (CurrentPositions.Length == 0) return;

        var min = new Vector3(float.MaxValue);
        var max = new Vector3(float.MinValue);

        for (int i = 0; i < CurrentPositions.Length; i += 3)
        {
            min.X = Math.Min(min.X, CurrentPositions[i]);
            min.Y = Math.Min(min.Y, CurrentPositions[i + 1]);
            min.Z = Math.Min(min.Z, CurrentPositions[i + 2]);

            max.X = Math.Max(max.X, CurrentPositions[i]);
            max.Y = Math.Max(max.Y, CurrentPositions[i + 1]);
            max.Z = Math.Max(max.Z, CurrentPositions[i + 2]);
        }

        BoundsMin = min;
        BoundsMax = max;
    }
}
