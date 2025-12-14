using System;
using System.Numerics;
using System.Runtime.CompilerServices;

namespace KooD3plot.Rendering;

/// <summary>
/// Color map types for scalar visualization
/// </summary>
public enum ColorMapType
{
    Jet,
    Rainbow,
    Viridis,
    Plasma,
    Inferno,
    Magma,
    CoolWarm,
    BlueRed,
    Grayscale
}

/// <summary>
/// Color mapping utilities for scalar field visualization
/// </summary>
public static class ColorMap
{
    /// <summary>
    /// Map a normalized scalar value (0-1) to RGB color
    /// </summary>
    [MethodImpl(MethodImplOptions.AggressiveInlining)]
    public static Vector3 Map(float t, ColorMapType type = ColorMapType.Jet)
    {
        t = Math.Clamp(t, 0, 1);

        return type switch
        {
            ColorMapType.Jet => Jet(t),
            ColorMapType.Rainbow => Rainbow(t),
            ColorMapType.Viridis => Viridis(t),
            ColorMapType.CoolWarm => CoolWarm(t),
            ColorMapType.BlueRed => BlueRed(t),
            ColorMapType.Grayscale => new Vector3(t),
            _ => Jet(t)
        };
    }

    /// <summary>
    /// Jet colormap (blue-cyan-green-yellow-red)
    /// </summary>
    [MethodImpl(MethodImplOptions.AggressiveInlining)]
    public static Vector3 Jet(float t)
    {
        float r = Math.Clamp(1.5f - Math.Abs(4.0f * t - 3.0f), 0, 1);
        float g = Math.Clamp(1.5f - Math.Abs(4.0f * t - 2.0f), 0, 1);
        float b = Math.Clamp(1.5f - Math.Abs(4.0f * t - 1.0f), 0, 1);
        return new Vector3(r, g, b);
    }

    /// <summary>
    /// Rainbow colormap (red-orange-yellow-green-cyan-blue-purple)
    /// </summary>
    [MethodImpl(MethodImplOptions.AggressiveInlining)]
    public static Vector3 Rainbow(float t)
    {
        float h = (1 - t) * 300; // Hue from red (0) to blue (240) to purple (300)
        return HsvToRgb(h, 1.0f, 1.0f);
    }

    /// <summary>
    /// Viridis colormap (perceptually uniform, colorblind-friendly)
    /// </summary>
    public static Vector3 Viridis(float t)
    {
        // Approximate viridis using polynomial fit
        float r = 0.267004f + t * (0.004874f + t * (1.556212f + t * (-2.179769f + t * 1.350598f)));
        float g = 0.004874f + t * (1.556212f + t * (-2.179769f + t * (2.699283f - t * 1.078255f)));
        float b = 0.329415f + t * (1.375676f + t * (-2.304024f + t * (2.168437f - t * 0.736963f)));
        return new Vector3(Math.Clamp(r, 0, 1), Math.Clamp(g, 0, 1), Math.Clamp(b, 0, 1));
    }

    /// <summary>
    /// Cool-warm diverging colormap (blue-white-red)
    /// </summary>
    [MethodImpl(MethodImplOptions.AggressiveInlining)]
    public static Vector3 CoolWarm(float t)
    {
        // Blue at 0, white at 0.5, red at 1
        if (t < 0.5f)
        {
            float s = t * 2;
            return new Vector3(s, s, 1);
        }
        else
        {
            float s = (1 - t) * 2;
            return new Vector3(1, s, s);
        }
    }

    /// <summary>
    /// Simple blue to red colormap
    /// </summary>
    [MethodImpl(MethodImplOptions.AggressiveInlining)]
    public static Vector3 BlueRed(float t)
    {
        return new Vector3(t, 0, 1 - t);
    }

    /// <summary>
    /// Convert HSV to RGB
    /// </summary>
    private static Vector3 HsvToRgb(float h, float s, float v)
    {
        h = h % 360;
        if (h < 0) h += 360;

        float c = v * s;
        float x = c * (1 - Math.Abs((h / 60) % 2 - 1));
        float m = v - c;

        float r, g, b;
        if (h < 60) { r = c; g = x; b = 0; }
        else if (h < 120) { r = x; g = c; b = 0; }
        else if (h < 180) { r = 0; g = c; b = x; }
        else if (h < 240) { r = 0; g = x; b = c; }
        else if (h < 300) { r = x; g = 0; b = c; }
        else { r = c; g = 0; b = x; }

        return new Vector3(r + m, g + m, b + m);
    }

    /// <summary>
    /// Generate a texture lookup table for GPU use
    /// </summary>
    public static byte[] GenerateLut(ColorMapType type, int size = 256)
    {
        var data = new byte[size * 4]; // RGBA

        for (int i = 0; i < size; i++)
        {
            float t = i / (float)(size - 1);
            var color = Map(t, type);

            data[i * 4 + 0] = (byte)(color.X * 255);
            data[i * 4 + 1] = (byte)(color.Y * 255);
            data[i * 4 + 2] = (byte)(color.Z * 255);
            data[i * 4 + 3] = 255;
        }

        return data;
    }

    /// <summary>
    /// Map scalar array to RGBA colors (for CPU-side coloring)
    /// </summary>
    public static void MapScalarsToColors(
        ReadOnlySpan<float> scalars,
        Span<byte> rgba,
        float minValue,
        float maxValue,
        ColorMapType type = ColorMapType.Jet)
    {
        float range = maxValue - minValue;
        if (range < float.Epsilon) range = 1.0f;
        float invRange = 1.0f / range;

        for (int i = 0; i < scalars.Length; i++)
        {
            float t = (scalars[i] - minValue) * invRange;
            var color = Map(t, type);

            rgba[i * 4 + 0] = (byte)(color.X * 255);
            rgba[i * 4 + 1] = (byte)(color.Y * 255);
            rgba[i * 4 + 2] = (byte)(color.Z * 255);
            rgba[i * 4 + 3] = 255;
        }
    }
}
