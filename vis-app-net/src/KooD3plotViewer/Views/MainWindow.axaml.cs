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

                // Connect ShowWireframe property
                vm.PropertyChanged += (sender, args) =>
                {
                    if (args.PropertyName == nameof(vm.ShowWireframe) && ViewportHost != null)
                    {
                        ViewportHost.ShowWireframe = vm.ShowWireframe;
                    }
                    else if (args.PropertyName == nameof(vm.DisplacementScale) && ViewportHost != null)
                    {
                        ViewportHost.DisplacementScale = (float)vm.DisplacementScale;
                    }
                };
            }
        };
    }
}
