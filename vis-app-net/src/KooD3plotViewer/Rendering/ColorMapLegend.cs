using System;
using System.Numerics;
using Avalonia;
using Avalonia.Media;
using Avalonia.Media.Imaging;
using Avalonia.Platform;
using Vector3 = System.Numerics.Vector3;

namespace KooD3plotViewer.Rendering;

/// <summary>
/// Renders a colormap legend/color bar with labels
/// </summary>
public class ColorMapLegend
{
    private const int LegendWidth = 30;
    private const int LegendHeight = 300;
    private const int LegendMargin = 20;
    private const int TickCount = 5;

    /// <summary>
    /// Render the colormap legend to a bitmap
    /// </summary>
    public static WriteableBitmap RenderLegend(
        ColorMap.ColorMapType colorMapType,
        float minValue,
        float maxValue,
        int width = LegendWidth,
        int height = LegendHeight)
    {
        var bitmap = new WriteableBitmap(
            new PixelSize(width, height),
            new Avalonia.Vector(96, 96),
            PixelFormat.Bgra8888,
            AlphaFormat.Premul);

        using (var buffer = bitmap.Lock())
        {
            unsafe
            {
                var ptr = (uint*)buffer.Address.ToPointer();
                var stride = buffer.RowBytes / 4;

                // Draw color gradient (top to bottom = max to min)
                for (int y = 0; y < height; y++)
                {
                    // Normalize y to 0-1 (inverted: top = 1, bottom = 0)
                    float t = 1.0f - (float)y / height;

                    // Get color from colormap
                    var color = ColorMap.GetColor(t, colorMapType);

                    // Convert to BGRA
                    byte r = (byte)(Math.Clamp(color.X, 0f, 1f) * 255);
                    byte g = (byte)(Math.Clamp(color.Y, 0f, 1f) * 255);
                    byte b = (byte)(Math.Clamp(color.Z, 0f, 1f) * 255);
                    uint bgra = 0xFF000000 | ((uint)r << 16) | ((uint)g << 8) | b;

                    // Fill the row
                    for (int x = 0; x < width; x++)
                    {
                        ptr[y * stride + x] = bgra;
                    }
                }
            }
        }

        return bitmap;
    }

    /// <summary>
    /// Generate tick labels for the legend
    /// </summary>
    public static (float value, string label)[] GenerateTickLabels(float minValue, float maxValue, int tickCount = TickCount)
    {
        var labels = new (float, string)[tickCount];

        for (int i = 0; i < tickCount; i++)
        {
            // Calculate position (top to bottom = max to min)
            float t = 1.0f - (float)i / (tickCount - 1);
            float value = minValue + t * (maxValue - minValue);

            // Format label based on magnitude
            string label = FormatValue(value);
            labels[i] = (value, label);
        }

        return labels;
    }

    private static string FormatValue(float value)
    {
        float absValue = Math.Abs(value);

        if (absValue >= 1e6f)
            return $"{value / 1e6f:F2}M";
        else if (absValue >= 1e3f)
            return $"{value / 1e3f:F2}k";
        else if (absValue >= 1f)
            return $"{value:F2}";
        else if (absValue >= 0.01f)
            return $"{value:F3}";
        else if (absValue > 0f)
            return $"{value:E2}";
        else
            return "0";
    }
}
