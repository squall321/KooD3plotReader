using System;
using System.Numerics;

namespace KooD3plotViewer.Rendering;

/// <summary>
/// Provides color mapping functions for scalar visualization
/// </summary>
public static class ColorMap
{
    public enum ColorMapType
    {
        Jet,
        Viridis,
        Plasma,
        Turbo,
        Rainbow,
        Cool,
        Hot
    }

    /// <summary>
    /// Get color from normalized value (0-1) using specified colormap
    /// </summary>
    public static Vector3 GetColor(float value, ColorMapType colorMap)
    {
        value = Math.Clamp(value, 0f, 1f);

        return colorMap switch
        {
            ColorMapType.Jet => Jet(value),
            ColorMapType.Viridis => Viridis(value),
            ColorMapType.Plasma => Plasma(value),
            ColorMapType.Turbo => Turbo(value),
            ColorMapType.Rainbow => Rainbow(value),
            ColorMapType.Cool => Cool(value),
            ColorMapType.Hot => Hot(value),
            _ => Jet(value)
        };
    }

    // Classic Jet colormap (blue -> cyan -> green -> yellow -> red)
    private static Vector3 Jet(float t)
    {
        float r = Math.Clamp(1.5f - Math.Abs(4.0f * t - 3.0f), 0f, 1f);
        float g = Math.Clamp(1.5f - Math.Abs(4.0f * t - 2.0f), 0f, 1f);
        float b = Math.Clamp(1.5f - Math.Abs(4.0f * t - 1.0f), 0f, 1f);
        return new Vector3(r, g, b);
    }

    // Viridis - perceptually uniform
    private static Vector3 Viridis(float t)
    {
        // Simplified Viridis approximation
        Vector3 c0 = new Vector3(0.267f, 0.005f, 0.329f);
        Vector3 c1 = new Vector3(0.127f, 0.566f, 0.550f);
        Vector3 c2 = new Vector3(0.993f, 0.906f, 0.144f);

        if (t < 0.5f)
        {
            float s = t * 2f;
            return Vector3.Lerp(c0, c1, s);
        }
        else
        {
            float s = (t - 0.5f) * 2f;
            return Vector3.Lerp(c1, c2, s);
        }
    }

    // Plasma - perceptually uniform
    private static Vector3 Plasma(float t)
    {
        Vector3 c0 = new Vector3(0.050f, 0.030f, 0.529f);
        Vector3 c1 = new Vector3(0.785f, 0.225f, 0.497f);
        Vector3 c2 = new Vector3(0.940f, 0.975f, 0.131f);

        if (t < 0.5f)
        {
            float s = t * 2f;
            return Vector3.Lerp(c0, c1, s);
        }
        else
        {
            float s = (t - 0.5f) * 2f;
            return Vector3.Lerp(c1, c2, s);
        }
    }

    // Turbo - improved rainbow
    private static Vector3 Turbo(float t)
    {
        const float r0 = 0.13572138f, r1 = 4.61539260f, r2 = -42.66032258f, r3 = 132.13108234f, r4 = -152.94239396f, r5 = 59.28637943f;
        const float g0 = 0.09140261f, g1 = 2.19418839f, g2 = 4.84296658f, g3 = -14.18503333f, g4 = 4.27729857f, g5 = 2.82956604f;
        const float b0 = 0.10667330f, b1 = 12.64194608f, b2 = -60.58204836f, b3 = 110.36276771f, b4 = -89.90310912f, b5 = 27.34824973f;

        float r = r0 + t * (r1 + t * (r2 + t * (r3 + t * (r4 + t * r5))));
        float g = g0 + t * (g1 + t * (g2 + t * (g3 + t * (g4 + t * g5))));
        float b = b0 + t * (b1 + t * (b2 + t * (b3 + t * (b4 + t * b5))));

        return new Vector3(Math.Clamp(r, 0f, 1f), Math.Clamp(g, 0f, 1f), Math.Clamp(b, 0f, 1f));
    }

    // Rainbow (HSV-based)
    private static Vector3 Rainbow(float t)
    {
        float h = t * 300f; // 0 to 300 degrees (red to magenta)
        float s = 1.0f;
        float v = 1.0f;

        float c = v * s;
        float x = c * (1 - Math.Abs((h / 60f) % 2 - 1));
        float m = v - c;

        Vector3 rgb;
        if (h < 60) rgb = new Vector3(c, x, 0);
        else if (h < 120) rgb = new Vector3(x, c, 0);
        else if (h < 180) rgb = new Vector3(0, c, x);
        else if (h < 240) rgb = new Vector3(0, x, c);
        else rgb = new Vector3(x, 0, c);

        return new Vector3(rgb.X + m, rgb.Y + m, rgb.Z + m);
    }

    // Cool (cyan to magenta)
    private static Vector3 Cool(float t)
    {
        return new Vector3(t, 1f - t, 1f);
    }

    // Hot (black -> red -> yellow -> white)
    private static Vector3 Hot(float t)
    {
        float r = Math.Clamp(t * 3f, 0f, 1f);
        float g = Math.Clamp(t * 3f - 1f, 0f, 1f);
        float b = Math.Clamp(t * 3f - 2f, 0f, 1f);
        return new Vector3(r, g, b);
    }

    /// <summary>
    /// Get colormap name for display
    /// </summary>
    public static string GetName(ColorMapType colorMap)
    {
        return colorMap switch
        {
            ColorMapType.Jet => "Jet (Classic)",
            ColorMapType.Viridis => "Viridis",
            ColorMapType.Plasma => "Plasma",
            ColorMapType.Turbo => "Turbo",
            ColorMapType.Rainbow => "Rainbow",
            ColorMapType.Cool => "Cool",
            ColorMapType.Hot => "Hot",
            _ => "Unknown"
        };
    }
}