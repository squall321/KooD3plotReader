using Avalonia.Controls;
using KooD3plotViewer.ViewModels;

namespace KooD3plotViewer.Views;

public partial class MainWindow : Window
{
    public MainWindow()
    {
        InitializeComponent();

        // Subscribe to ViewModel events after DataContext is set
        DataContextChanged += (s, e) =>
        {
            if (DataContext is MainWindowViewModel vm)
            {
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

                // Connect ShowWireframe and ClipPlane properties
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
                        // Clip plane properties
                        case nameof(vm.ClipXEnabled):
                            ViewportHost.ClipXEnabled = vm.ClipXEnabled;
                            break;
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
        };
    }
}
