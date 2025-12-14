using ReactiveUI;
using System;
using System.Collections.ObjectModel;
using System.Linq;
using System.Reactive;
using System.Threading.Tasks;
using System.Windows.Input;
using Avalonia.Controls;
using Avalonia.Platform.Storage;
using KooD3plot.Data;

namespace KooD3plotViewer.ViewModels;

public class MainWindowViewModel : ReactiveObject
{
    private string _statusText = "Ready";
    private string _fpsText = "0 FPS";
    private int _currentTimestep;
    private int _maxTimestep = 100;
    private double _currentTime;
    private bool _isPlaying;
    private bool _showWireframe;
    private bool _showNodes;
    private double _displacementScale = 1.0;
    private string _selectedColorScale = "Von Mises Stress";
    private double _colorScaleMin;
    private double _colorScaleMax = 1000;
    private bool _autoColorRange = true;
    private string _selectedNodeInfo = "No selection";
    private string _logText = "";

    private Hdf5DataLoader? _dataLoader;

    public MainWindowViewModel()
    {
        // Initialize commands
        OpenFileCommand = ReactiveCommand.CreateFromTask(OpenFileAsync);
        ExitCommand = ReactiveCommand.Create(Exit);
        ResetCameraCommand = ReactiveCommand.Create(ResetCamera);
        FitToWindowCommand = ReactiveCommand.Create(FitToWindow);
        AboutCommand = ReactiveCommand.Create(ShowAbout);
        LoadTestMeshCommand = ReactiveCommand.Create(LoadTestMesh);
        LoadSmallTestMeshCommand = ReactiveCommand.Create(LoadSmallTestMesh);

        PlayPauseCommand = ReactiveCommand.Create(TogglePlayPause);
        FirstFrameCommand = ReactiveCommand.Create(() => { CurrentTimestep = 0; });
        LastFrameCommand = ReactiveCommand.Create(() => { CurrentTimestep = MaxTimestep; });
        PrevFrameCommand = ReactiveCommand.Create(() => { CurrentTimestep = Math.Max(0, CurrentTimestep - 1); });
        NextFrameCommand = ReactiveCommand.Create(() => { CurrentTimestep = Math.Min(MaxTimestep, CurrentTimestep + 1); });

        // Initialize collections
        ModelTreeItems = new ObservableCollection<TreeItemViewModel>();
        ColorScaleOptions = new ObservableCollection<string>
        {
            "Von Mises Stress",
            "Displacement Magnitude",
            "X Displacement",
            "Y Displacement",
            "Z Displacement",
            "Velocity Magnitude",
            "Plastic Strain"
        };
    }

    // Commands
    public ReactiveCommand<Unit, Unit> OpenFileCommand { get; }
    public ReactiveCommand<Unit, Unit> ExitCommand { get; }
    public ReactiveCommand<Unit, Unit> ResetCameraCommand { get; }
    public ReactiveCommand<Unit, Unit> FitToWindowCommand { get; }
    public ReactiveCommand<Unit, Unit> AboutCommand { get; }
    public ReactiveCommand<Unit, Unit> LoadTestMeshCommand { get; }
    public ReactiveCommand<Unit, Unit> LoadSmallTestMeshCommand { get; }
    public ReactiveCommand<Unit, Unit> PlayPauseCommand { get; }
    public ReactiveCommand<Unit, Unit> FirstFrameCommand { get; }
    public ReactiveCommand<Unit, Unit> LastFrameCommand { get; }
    public ReactiveCommand<Unit, Unit> PrevFrameCommand { get; }
    public ReactiveCommand<Unit, Unit> NextFrameCommand { get; }

    // Collections
    public ObservableCollection<TreeItemViewModel> ModelTreeItems { get; }
    public ObservableCollection<string> ColorScaleOptions { get; }

    // Properties
    public string StatusText
    {
        get => _statusText;
        set => this.RaiseAndSetIfChanged(ref _statusText, value);
    }

    public string FpsText
    {
        get => _fpsText;
        set => this.RaiseAndSetIfChanged(ref _fpsText, value);
    }

    public int CurrentTimestep
    {
        get => _currentTimestep;
        set
        {
            this.RaiseAndSetIfChanged(ref _currentTimestep, value);
            OnTimestepChanged();
        }
    }

    public int MaxTimestep
    {
        get => _maxTimestep;
        set => this.RaiseAndSetIfChanged(ref _maxTimestep, value);
    }

    public double CurrentTime
    {
        get => _currentTime;
        set => this.RaiseAndSetIfChanged(ref _currentTime, value);
    }

    public bool ShowWireframe
    {
        get => _showWireframe;
        set => this.RaiseAndSetIfChanged(ref _showWireframe, value);
    }

    public bool ShowNodes
    {
        get => _showNodes;
        set => this.RaiseAndSetIfChanged(ref _showNodes, value);
    }

    public double DisplacementScale
    {
        get => _displacementScale;
        set => this.RaiseAndSetIfChanged(ref _displacementScale, value);
    }

    public string SelectedColorScale
    {
        get => _selectedColorScale;
        set => this.RaiseAndSetIfChanged(ref _selectedColorScale, value);
    }

    public double ColorScaleMin
    {
        get => _colorScaleMin;
        set => this.RaiseAndSetIfChanged(ref _colorScaleMin, value);
    }

    public double ColorScaleMax
    {
        get => _colorScaleMax;
        set => this.RaiseAndSetIfChanged(ref _colorScaleMax, value);
    }

    public bool AutoColorRange
    {
        get => _autoColorRange;
        set => this.RaiseAndSetIfChanged(ref _autoColorRange, value);
    }

    public string SelectedNodeInfo
    {
        get => _selectedNodeInfo;
        set => this.RaiseAndSetIfChanged(ref _selectedNodeInfo, value);
    }

    public string LogText
    {
        get => _logText;
        set => this.RaiseAndSetIfChanged(ref _logText, value);
    }

    public string PlayPauseIcon => _isPlaying ? "⏸" : "▶";

    public void AppendLog(string message)
    {
        Avalonia.Threading.Dispatcher.UIThread.Post(() =>
        {
            var timestamp = DateTime.Now.ToString("HH:mm:ss.fff");
            var newLine = $"[{timestamp}] {message}";

            // Keep last 100 lines
            var lines = LogText.Split('\n', StringSplitOptions.RemoveEmptyEntries);
            if (lines.Length > 100)
            {
                LogText = string.Join("\n", lines.Skip(lines.Length - 100)) + "\n" + newLine;
            }
            else
            {
                LogText = string.IsNullOrEmpty(LogText) ? newLine : LogText + "\n" + newLine;
            }
        });
    }

    // Event for notifying views about mesh updates
    public event Action<MeshData, StateData?>? MeshDataLoaded;

    // Command implementations
    private async Task OpenFileAsync()
    {
        try
        {
            var topLevel = Avalonia.Application.Current?.ApplicationLifetime is
                Avalonia.Controls.ApplicationLifetimes.IClassicDesktopStyleApplicationLifetime desktop
                ? desktop.MainWindow : null;

            if (topLevel == null) return;

            var files = await topLevel.StorageProvider.OpenFilePickerAsync(new Avalonia.Platform.Storage.FilePickerOpenOptions
            {
                Title = "Open HDF5 File",
                AllowMultiple = false,
                FileTypeFilter = new[]
                {
                    new Avalonia.Platform.Storage.FilePickerFileType("HDF5 Files") { Patterns = new[] { "*.h5", "*.hdf5" } },
                    new Avalonia.Platform.Storage.FilePickerFileType("All Files") { Patterns = new[] { "*.*" } }
                }
            });

            if (files.Count > 0)
            {
                var filePath = files[0].Path.LocalPath;
                await Task.Run(() => LoadHdf5File(filePath));
            }
        }
        catch (Exception ex)
        {
            StatusText = $"Error: {ex.Message}";
        }
    }

    private void LoadHdf5File(string filePath)
    {
        try
        {
            StatusText = $"Loading {System.IO.Path.GetFileName(filePath)}...";

            _dataLoader?.Dispose();
            _dataLoader = new Hdf5DataLoader(filePath);

            var info = _dataLoader.GetFileInfo();
            var timesteps = _dataLoader.GetTimestepList();

            // Update UI on main thread
            Avalonia.Threading.Dispatcher.UIThread.Post(() =>
            {
                MaxTimestep = timesteps.Count > 0 ? timesteps.Count - 1 : 0;
                CurrentTimestep = 0;

                // Build model tree
                ModelTreeItems.Clear();
                ModelTreeItems.Add(new TreeItemViewModel("Nodes", info.NumNodes));
                ModelTreeItems.Add(new TreeItemViewModel("Solids", info.NumSolids));
                ModelTreeItems.Add(new TreeItemViewModel("Shells", info.NumShells));
                ModelTreeItems.Add(new TreeItemViewModel("Beams", info.NumBeams));

                StatusText = $"Loaded: {info.NumNodes:N0} nodes, {info.NumTimesteps} timesteps";

                // Load mesh and first state
                var meshData = _dataLoader.GetMeshData();
                var stateData = timesteps.Count > 0 ? _dataLoader.GetStateData(0) : null;

                MeshDataLoaded?.Invoke(meshData, stateData);
            });
        }
        catch (Exception ex)
        {
            Avalonia.Threading.Dispatcher.UIThread.Post(() =>
            {
                StatusText = $"Error loading file: {ex.Message}";
            });
        }
    }

    private void Exit()
    {
        Environment.Exit(0);
    }

    private void ResetCamera()
    {
        // TODO: Reset camera to default position
        StatusText = "Camera reset";
    }

    private void FitToWindow()
    {
        // TODO: Fit model to viewport
        StatusText = "Fit to window";
    }

    private void ShowAbout()
    {
        // TODO: Show about dialog
    }

    private void LoadTestMesh()
    {
        // Create a cube mesh with ~10M elements (215^3 = 9,938,375)
        const int nx = 215, ny = 215, nz = 215;
        const float spacing = 1.0f;

        StatusText = $"Generating test mesh ({nx}x{ny}x{nz})...";

        var mesh = new MeshData();
        int numNodes = (nx + 1) * (ny + 1) * (nz + 1);  // ~10M nodes
        int numElements = nx * ny * nz;  // ~10M elements

        Console.WriteLine($"[TestMesh] Creating {numNodes:N0} nodes, {numElements:N0} elements...");

        // Create nodes
        mesh.NodePositions = new float[numNodes * 3];
        mesh.NodeIds = new int[numNodes];

        int nodeIndex = 0;
        for (int k = 0; k <= nz; k++)
        {
            for (int j = 0; j <= ny; j++)
            {
                for (int i = 0; i <= nx; i++)
                {
                    mesh.NodePositions[nodeIndex * 3 + 0] = i * spacing;
                    mesh.NodePositions[nodeIndex * 3 + 1] = j * spacing;
                    mesh.NodePositions[nodeIndex * 3 + 2] = k * spacing;
                    mesh.NodeIds[nodeIndex] = nodeIndex;
                    nodeIndex++;
                }
            }
        }

        // Create hex elements
        mesh.SolidConnectivity = new int[numElements * 8];

        int elemIndex = 0;
        for (int k = 0; k < nz; k++)
        {
            for (int j = 0; j < ny; j++)
            {
                for (int i = 0; i < nx; i++)
                {
                    int n0 = k * (ny + 1) * (nx + 1) + j * (nx + 1) + i;
                    int n1 = n0 + 1;
                    int n2 = n0 + (nx + 1) + 1;
                    int n3 = n0 + (nx + 1);
                    int n4 = n0 + (ny + 1) * (nx + 1);
                    int n5 = n4 + 1;
                    int n6 = n4 + (nx + 1) + 1;
                    int n7 = n4 + (nx + 1);

                    mesh.SolidConnectivity[elemIndex * 8 + 0] = n0;
                    mesh.SolidConnectivity[elemIndex * 8 + 1] = n1;
                    mesh.SolidConnectivity[elemIndex * 8 + 2] = n2;
                    mesh.SolidConnectivity[elemIndex * 8 + 3] = n3;
                    mesh.SolidConnectivity[elemIndex * 8 + 4] = n4;
                    mesh.SolidConnectivity[elemIndex * 8 + 5] = n5;
                    mesh.SolidConnectivity[elemIndex * 8 + 6] = n6;
                    mesh.SolidConnectivity[elemIndex * 8 + 7] = n7;

                    elemIndex++;
                }
            }
        }

        mesh.ShellConnectivity = Array.Empty<int>();
        mesh.BeamConnectivity = Array.Empty<int>();
        mesh.SolidPartIds = Array.Empty<int>();
        mesh.ShellPartIds = Array.Empty<int>();

        // Update model tree
        ModelTreeItems.Clear();
        ModelTreeItems.Add(new TreeItemViewModel("Nodes", numNodes));
        ModelTreeItems.Add(new TreeItemViewModel("Solids", numElements));
        ModelTreeItems.Add(new TreeItemViewModel("Shells", 0));

        StatusText = $"Loaded test mesh: {numNodes:N0} nodes, {numElements:N0} elements";

        MeshDataLoaded?.Invoke(mesh, null);
    }

    private void LoadSmallTestMesh()
    {
        // Create a small cube mesh with 125,000 elements (50^3)
        const int nx = 50, ny = 50, nz = 50;
        const float spacing = 1.0f;

        StatusText = $"Generating small test mesh ({nx}x{ny}x{nz})...";

        var mesh = new MeshData();
        int numNodes = (nx + 1) * (ny + 1) * (nz + 1);
        int numElements = nx * ny * nz;

        Console.WriteLine($"[TestMesh] Creating {numNodes:N0} nodes, {numElements:N0} elements...");

        // Create nodes
        mesh.NodePositions = new float[numNodes * 3];
        mesh.NodeIds = new int[numNodes];

        int nodeIndex = 0;
        for (int k = 0; k <= nz; k++)
        {
            for (int j = 0; j <= ny; j++)
            {
                for (int i = 0; i <= nx; i++)
                {
                    mesh.NodePositions[nodeIndex * 3 + 0] = i * spacing;
                    mesh.NodePositions[nodeIndex * 3 + 1] = j * spacing;
                    mesh.NodePositions[nodeIndex * 3 + 2] = k * spacing;
                    mesh.NodeIds[nodeIndex] = nodeIndex;
                    nodeIndex++;
                }
            }
        }

        // Create hex elements
        mesh.SolidConnectivity = new int[numElements * 8];

        int elemIndex = 0;
        for (int k = 0; k < nz; k++)
        {
            for (int j = 0; j < ny; j++)
            {
                for (int i = 0; i < nx; i++)
                {
                    int n0 = k * (ny + 1) * (nx + 1) + j * (nx + 1) + i;
                    int n1 = n0 + 1;
                    int n2 = n0 + (nx + 1) + 1;
                    int n3 = n0 + (nx + 1);
                    int n4 = n0 + (ny + 1) * (nx + 1);
                    int n5 = n4 + 1;
                    int n6 = n4 + (nx + 1) + 1;
                    int n7 = n4 + (nx + 1);

                    mesh.SolidConnectivity[elemIndex * 8 + 0] = n0;
                    mesh.SolidConnectivity[elemIndex * 8 + 1] = n1;
                    mesh.SolidConnectivity[elemIndex * 8 + 2] = n2;
                    mesh.SolidConnectivity[elemIndex * 8 + 3] = n3;
                    mesh.SolidConnectivity[elemIndex * 8 + 4] = n4;
                    mesh.SolidConnectivity[elemIndex * 8 + 5] = n5;
                    mesh.SolidConnectivity[elemIndex * 8 + 6] = n6;
                    mesh.SolidConnectivity[elemIndex * 8 + 7] = n7;

                    elemIndex++;
                }
            }
        }

        mesh.ShellConnectivity = Array.Empty<int>();
        mesh.BeamConnectivity = Array.Empty<int>();
        mesh.SolidPartIds = Array.Empty<int>();
        mesh.ShellPartIds = Array.Empty<int>();

        // Update model tree
        ModelTreeItems.Clear();
        ModelTreeItems.Add(new TreeItemViewModel("Nodes", numNodes));
        ModelTreeItems.Add(new TreeItemViewModel("Solids", numElements));
        ModelTreeItems.Add(new TreeItemViewModel("Shells", 0));

        StatusText = $"Loaded test mesh: {numNodes:N0} nodes, {numElements:N0} elements";

        MeshDataLoaded?.Invoke(mesh, null);
    }

    private void TogglePlayPause()
    {
        _isPlaying = !_isPlaying;
        this.RaisePropertyChanged(nameof(PlayPauseIcon));

        if (_isPlaying)
        {
            StartPlayback();
        }
    }

    private async void StartPlayback()
    {
        while (_isPlaying && CurrentTimestep < MaxTimestep)
        {
            await Task.Delay(33); // ~30 FPS playback
            CurrentTimestep++;
        }
        _isPlaying = false;
        this.RaisePropertyChanged(nameof(PlayPauseIcon));
    }

    private void OnTimestepChanged()
    {
        if (_dataLoader != null)
        {
            CurrentTime = _dataLoader.GetTimestepTime(CurrentTimestep);
        }
    }

    public void LoadFile(string filePath)
    {
        try
        {
            StatusText = $"Loading {System.IO.Path.GetFileName(filePath)}...";

            _dataLoader = new Hdf5DataLoader(filePath);
            var info = _dataLoader.GetFileInfo();

            MaxTimestep = info.NumTimesteps - 1;
            CurrentTimestep = 0;

            // Build model tree
            ModelTreeItems.Clear();
            ModelTreeItems.Add(new TreeItemViewModel("Nodes", info.NumNodes));
            ModelTreeItems.Add(new TreeItemViewModel("Solids", info.NumSolids));
            ModelTreeItems.Add(new TreeItemViewModel("Shells", info.NumShells));
            ModelTreeItems.Add(new TreeItemViewModel("Beams", info.NumBeams));

            StatusText = $"Loaded: {info.NumNodes:N0} nodes, {info.NumTimesteps} timesteps";
        }
        catch (Exception ex)
        {
            StatusText = $"Error: {ex.Message}";
        }
    }
}

public class TreeItemViewModel
{
    public string Name { get; }
    public int Count { get; }
    public ObservableCollection<TreeItemViewModel> Children { get; } = new();

    public TreeItemViewModel(string name, int count = 0)
    {
        Name = name;
        Count = count;
    }
}
