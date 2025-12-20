using System;
using Avalonia;
using Avalonia.Controls;
using Avalonia.Media;
using Avalonia.Media.Imaging;
using KooD3plotViewer.Rendering;

namespace KooD3plotViewer.Controls;

public partial class ColorMapLegendControl : UserControl
{
    private ColorMap.ColorMapType _colorMapType = ColorMap.ColorMapType.Jet;
    private float _minValue = 0f;
    private float _maxValue = 1000f;
    private string _title = "Stress (MPa)";

    public ColorMapLegendControl()
    {
        InitializeComponent();
        UpdateLegend();
    }

    public void SetColorMap(ColorMap.ColorMapType colorMapType, float minValue, float maxValue, string title = "Value")
    {
        _colorMapType = colorMapType;
        _minValue = minValue;
        _maxValue = maxValue;
        _title = title;
        UpdateLegend();
    }

    private void UpdateLegend()
    {
        // Update title
        if (this.FindControl<TextBlock>("TitleText") is { } titleText)
        {
            titleText.Text = _title;
        }

        // Generate color bar image
        var colorBarBitmap = ColorMapLegend.RenderLegend(_colorMapType, _minValue, _maxValue, 30, 300);

        if (this.FindControl<Image>("ColorBarImage") is { } colorBarImage)
        {
            colorBarImage.Source = colorBarBitmap;
        }

        // Update labels
        if (this.FindControl<StackPanel>("LabelsPanel") is { } labelsPanel)
        {
            labelsPanel.Children.Clear();

            var tickLabels = ColorMapLegend.GenerateTickLabels(_minValue, _maxValue);

            foreach (var (value, label) in tickLabels)
            {
                var textBlock = new TextBlock
                {
                    Text = label,
                    FontSize = 10,
                    Foreground = new SolidColorBrush(Color.FromRgb(204, 204, 204)),
                    VerticalAlignment = Avalonia.Layout.VerticalAlignment.Center,
                    Margin = new Thickness(0, 0, 5, 0),
                    Height = 300.0 / (tickLabels.Length - 1)
                };
                labelsPanel.Children.Add(textBlock);
            }
        }

        // Draw tick marks
        if (this.FindControl<Canvas>("TickMarksCanvas") is { } tickCanvas)
        {
            tickCanvas.Children.Clear();

            var tickLabels = ColorMapLegend.GenerateTickLabels(_minValue, _maxValue);
            double spacing = 300.0 / (tickLabels.Length - 1);

            for (int i = 0; i < tickLabels.Length; i++)
            {
                var line = new Avalonia.Controls.Shapes.Line
                {
                    StartPoint = new Point(0, i * spacing),
                    EndPoint = new Point(5, i * spacing),
                    Stroke = new SolidColorBrush(Color.FromRgb(102, 102, 102)),
                    StrokeThickness = 1
                };
                tickCanvas.Children.Add(line);
            }
        }
    }
}
