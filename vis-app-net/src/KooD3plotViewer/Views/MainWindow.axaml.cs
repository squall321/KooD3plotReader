using Avalonia.Controls;
using KooD3plotViewer.ViewModels;

namespace KooD3plotViewer.Views;

public partial class MainWindow : Window
{
    private MainWindowViewModel? _currentViewModel;

    public MainWindow()
    {
        InitializeComponent();

        DataContextChanged += (s, e) =>
        {
            if (DataContext is MainWindowViewModel vmNew)
            {
                SetupViewModel(vmNew);
            }
        };
    }

    private void OnClipXCheckBoxChanged(object? sender, Avalonia.Interactivity.RoutedEventArgs e)
    {
        if (ClipXCheckBox?.IsChecked == null) return;
        bool enabled = ClipXCheckBox.IsChecked.Value;

        if (ClipXSlider != null) ClipXSlider.IsEnabled = enabled;
        if (ClipXInvertCheckBox != null) ClipXInvertCheckBox.IsEnabled = enabled;
        if (ClipXNumeric != null) ClipXNumeric.IsEnabled = enabled;
        if (ViewportHost != null) ViewportHost.ClipXEnabled = enabled;
    }

    private void OnClipYCheckBoxChanged(object? sender, Avalonia.Interactivity.RoutedEventArgs e)
    {
        if (ClipYCheckBox?.IsChecked == null) return;
        bool enabled = ClipYCheckBox.IsChecked.Value;

        if (ClipYSlider != null) ClipYSlider.IsEnabled = enabled;
        if (ClipYInvertCheckBox != null) ClipYInvertCheckBox.IsEnabled = enabled;
        if (ClipYNumeric != null) ClipYNumeric.IsEnabled = enabled;
        if (ViewportHost != null) ViewportHost.ClipYEnabled = enabled;
    }

    private void OnClipZCheckBoxChanged(object? sender, Avalonia.Interactivity.RoutedEventArgs e)
    {
        if (ClipZCheckBox?.IsChecked == null) return;
        bool enabled = ClipZCheckBox.IsChecked.Value;

        if (ClipZSlider != null) ClipZSlider.IsEnabled = enabled;
        if (ClipZInvertCheckBox != null) ClipZInvertCheckBox.IsEnabled = enabled;
        if (ClipZNumeric != null) ClipZNumeric.IsEnabled = enabled;
        if (ViewportHost != null) ViewportHost.ClipZEnabled = enabled;
    }

    private void SetupViewModel(MainWindowViewModel vm)
    {
        // Prevent duplicate setup
        if (_currentViewModel == vm)
            return;

        _currentViewModel = vm;

        // Connect log callback
        if (ViewportHost != null)
        {
            ViewportHost.LogCallback = vm.AppendLog;
            vm.AppendLog("Renderer initialized");
        }

        vm.MeshDataLoaded += (mesh, state) =>
        {
            Avalonia.Threading.Dispatcher.UIThread.Post(() =>
            {
                ViewportHost?.LoadMeshData(mesh, state);
            });
        };

        vm.StateDataUpdated += (state) =>
        {
            Avalonia.Threading.Dispatcher.UIThread.Post(() =>
            {
                ViewportHost?.UpdateStateData(state);
            });
        };

        // Connect property changes to ViewportHost
        vm.PropertyChanged += (sender, args) =>
        {
            if (ViewportHost == null) return;

            switch (args.PropertyName)
            {
                case nameof(vm.ShowWireframe):
                    ViewportHost.ShowWireframe = vm.ShowWireframe;
                    break;
                case nameof(vm.DisplacementScale):
                    ViewportHost.DisplacementScale = (float)vm.DisplacementScale;
                    break;
                // Note: ClipXEnabled is handled by OnClipXCheckBoxChanged
                case nameof(vm.ClipYEnabled):
                    ViewportHost.ClipYEnabled = vm.ClipYEnabled;
                    break;
                case nameof(vm.ClipZEnabled):
                    ViewportHost.ClipZEnabled = vm.ClipZEnabled;
                    break;
                case nameof(vm.ClipXValue):
                    ViewportHost.ClipXValue = (float)vm.ClipXValue;
                    break;
                case nameof(vm.ClipYValue):
                    ViewportHost.ClipYValue = (float)vm.ClipYValue;
                    break;
                case nameof(vm.ClipZValue):
                    ViewportHost.ClipZValue = (float)vm.ClipZValue;
                    break;
                case nameof(vm.ClipXInvert):
                    ViewportHost.ClipXInvert = vm.ClipXInvert;
                    break;
                case nameof(vm.ClipYInvert):
                    ViewportHost.ClipYInvert = vm.ClipYInvert;
                    break;
                case nameof(vm.ClipZInvert):
                    ViewportHost.ClipZInvert = vm.ClipZInvert;
                    break;
                case nameof(vm.ShowClipCap):
                    ViewportHost.ShowClipCap = vm.ShowClipCap;
                    break;
                case nameof(vm.SelectedColorScale):
                    ViewportHost.SelectedColorMap = vm.SelectedColorScale;
                    break;
            }
        };
    }
}
