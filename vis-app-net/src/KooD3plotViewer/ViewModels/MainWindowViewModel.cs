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
using System.IO;

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
    private StreamWriter? _logFile;

    // Clip plane settings
    private bool _clipXEnabled;
    private bool _clipYEnabled;
    private bool _clipZEnabled;
    private double _clipXValue = 0.5;
    private double _clipYValue = 0.5;
    private double _clipZValue = 0.5;
    private bool _clipXInvert;
    private bool _clipYInvert;
    private bool _clipZInvert;
    private bool _showClipCap = true;

    private Hdf5DataLoader? _dataLoader;

    public MainWindowViewModel()
    {
        // Initialize log file
        try
        {
            var logPath = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Desktop), "KooD3plotViewer.log");
            _logFile = new StreamWriter(logPath, false) { AutoFlush = true };
            _logFile.WriteLine($"=== KooD3plotViewer Log Started at {DateTime.Now} ===");
        }
        catch { /* Ignore log file errors */ }

        // Initialize commands
        OpenFileCommand = ReactiveCommand.CreateFromTask(OpenFileAsync);
        ExitCommand = ReactiveCommand.Create(Exit);
        ResetCameraCommand = ReactiveCommand.Create(ResetCamera);
        FitToWindowCommand = ReactiveCommand.Create(FitToWindow);
        AboutCommand = ReactiveCommand.Create(ShowAbout);
        LoadTestMeshCommand = ReactiveCommand.CreateFromTask(LoadTestMeshAsync);
        LoadSmallTestMeshCommand = ReactiveCommand.CreateFromTask(LoadSmallTestMeshAsync);

        PlayPauseCommand = ReactiveCommand.Create(TogglePlayPause);
        FirstFrameCommand = ReactiveCommand.Create(() => { CurrentTimestep = 0; });
        LastFrameCommand = ReactiveCommand.Create(() => { CurrentTimestep = MaxTimestep; });
        PrevFrameCommand = ReactiveCommand.Create(() => { CurrentTimestep = Math.Max(0, CurrentTimestep - 1); });
        NextFrameCommand = ReactiveCommand.Create(() => { CurrentTimestep = Math.Min(MaxTimestep, CurrentTimestep + 1); });

        // Initialize collections
        ModelTreeItems = new ObservableCollection<TreeItemViewModel>();
        ColorScaleOptions = new ObservableCollection<string>
        {
            "None (Solid Color)",
            "Jet (Classic)",
            "Viridis",
            "Plasma",
            "Turbo",
            "Rainbow",
            "Cool",
            "Hot"
        };
        SelectedColorScale = ColorScaleOptions[1]; // Default to Jet
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

    // Clip plane properties
    public bool ClipXEnabled
    {
        get => _clipXEnabled;
        set => this.RaiseAndSetIfChanged(ref _clipXEnabled, value);
    }

    public bool ClipYEnabled
    {
        get => _clipYEnabled;
        set => this.RaiseAndSetIfChanged(ref _clipYEnabled, value);
    }

    public bool ClipZEnabled
    {
        get => _clipZEnabled;
        set => this.RaiseAndSetIfChanged(ref _clipZEnabled, value);
    }

    public double ClipXValue
    {
        get => _clipXValue;
        set => this.RaiseAndSetIfChanged(ref _clipXValue, value);
    }

    public double ClipYValue
    {
        get => _clipYValue;
        set => this.RaiseAndSetIfChanged(ref _clipYValue, value);
    }

    public double ClipZValue
    {
        get => _clipZValue;
        set => this.RaiseAndSetIfChanged(ref _clipZValue, value);
    }

    public bool ClipXInvert
    {
        get => _clipXInvert;
        set => this.RaiseAndSetIfChanged(ref _clipXInvert, value);
    }

    public bool ClipYInvert
    {
        get => _clipYInvert;
        set => this.RaiseAndSetIfChanged(ref _clipYInvert, value);
    }

    public bool ClipZInvert
    {
        get => _clipZInvert;
        set => this.RaiseAndSetIfChanged(ref _clipZInvert, value);
    }

    public bool ShowClipCap
    {
        get => _showClipCap;
        set => this.RaiseAndSetIfChanged(ref _showClipCap, value);
    }

    public string PlayPauseIcon => _isPlaying ? "⏸" : "▶";

    public void AppendLog(string message)
    {
        Avalonia.Threading.Dispatcher.UIThread.Post(() =>
        {
            var timestamp = DateTime.Now.ToString("HH:mm:ss.fff");
            var newLine = $"[{timestamp}] {message}";

            // Write to file
            try
            {
                _logFile?.WriteLine(newLine);
            }
            catch { /* Ignore file write errors */ }

            // Keep last 100 lines in UI
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

    // Event for fast state updates (animation) without full mesh reload
    public event Action<StateData>? StateDataUpdated;

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

    private async Task LoadTestMeshAsync()
    {
        // Create a cube mesh with ~10M elements (215^3 = 9,938,375)
        const int nx = 215, ny = 215, nz = 215;
        const float spacing = 1.0f;

        StatusText = $"Generating test mesh ({nx}x{ny}x{nz})...";

        var mesh = await Task.Run(() => CreateTestMesh(nx, ny, nz, spacing));
        int numNodes = (nx + 1) * (ny + 1) * (nz + 1);
        int numElements = nx * ny * nz;

        // Update model tree
        ModelTreeItems.Clear();
        ModelTreeItems.Add(new TreeItemViewModel("Nodes", numNodes));
        ModelTreeItems.Add(new TreeItemViewModel("Solids", numElements));
        ModelTreeItems.Add(new TreeItemViewModel("Shells", 0));

        StatusText = $"Loaded test mesh: {numNodes:N0} nodes, {numElements:N0} elements";

        // Store mesh for animation and clear HDF5 loader
        _currentTestMesh = mesh;
        _dataLoader?.Dispose();
        _dataLoader = null;
        _meshLoaded = false;

        // Create animated displacement for testing timeline
        MaxTimestep = 50;
        CurrentTimestep = 0;

        // Generate test displacement for initial frame (large mesh uses center at 215/2)
        var state = GenerateTestDisplacementLarge(mesh, 0, 215);
        MeshDataLoaded?.Invoke(mesh, state);
        _meshLoaded = true;
    }

    private MeshData CreateTestMesh(int nx, int ny, int nz, float spacing)
    {
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

        return mesh;
    }

    private StateData GenerateTestDisplacementLarge(MeshData mesh, int timestep, int gridSize)
    {
        int numNodes = mesh.NodePositions.Length / 3;
        var state = new StateData
        {
            Time = timestep * 0.01,
            Displacements = new float[numNodes * 3]
        };

        float t = timestep / 50.0f; // 0 to 1 over 50 frames
        float phase = t * MathF.PI * 2; // One full cycle
        float center = gridSize / 2.0f;

        for (int i = 0; i < numNodes; i++)
        {
            float x = mesh.NodePositions[i * 3 + 0];
            float y = mesh.NodePositions[i * 3 + 1];
            float z = mesh.NodePositions[i * 3 + 2];

            float dx = x - center;
            float dy = y - center;
            float dz = z - center;
            float dist = MathF.Sqrt(dx * dx + dy * dy + dz * dz);

            // Wave pattern
            float amplitude = 10.0f * MathF.Sin(phase - dist * 0.1f);

            // Radial displacement
            float scale = dist > 0.01f ? amplitude / dist : 0;
            state.Displacements[i * 3 + 0] = dx * scale;
            state.Displacements[i * 3 + 1] = dy * scale;
            state.Displacements[i * 3 + 2] = dz * scale;
        }

        return state;
    }

    private async Task LoadSmallTestMeshAsync()
    {
        // Create a small cube mesh with 125,000 elements (50^3)
        const int nx = 50, ny = 50, nz = 50;
        const float spacing = 1.0f;

        StatusText = $"Generating small test mesh ({nx}x{ny}x{nz})...";

        var mesh = await Task.Run(() => CreateTestMesh(nx, ny, nz, spacing));
        int numNodes = (nx + 1) * (ny + 1) * (nz + 1);
        int numElements = nx * ny * nz;

        // Update model tree
        ModelTreeItems.Clear();
        ModelTreeItems.Add(new TreeItemViewModel("Nodes", numNodes));
        ModelTreeItems.Add(new TreeItemViewModel("Solids", numElements));
        ModelTreeItems.Add(new TreeItemViewModel("Shells", 0));

        StatusText = $"Loaded test mesh: {numNodes:N0} nodes, {numElements:N0} elements";

        // Store mesh for animation and clear HDF5 loader
        _currentTestMesh = mesh;
        _dataLoader?.Dispose();
        _dataLoader = null;
        _meshLoaded = false;

        // Create animated displacement for testing timeline
        MaxTimestep = 50;
        CurrentTimestep = 0;

        // Generate test displacement for initial frame
        var state = GenerateTestDisplacement(mesh, 0);
        MeshDataLoaded?.Invoke(mesh, state);
        _meshLoaded = true;
    }

    private StateData GenerateTestDisplacement(MeshData mesh, int timestep)
    {
        int numNodes = mesh.NodePositions.Length / 3;
        var state = new StateData
        {
            Time = timestep * 0.01,
            Displacements = new float[numNodes * 3]
        };

        float t = timestep / 50.0f; // 0 to 1 over 50 frames
        float phase = t * MathF.PI * 2; // One full cycle

        for (int i = 0; i < numNodes; i++)
        {
            float x = mesh.NodePositions[i * 3 + 0];
            float y = mesh.NodePositions[i * 3 + 1];
            float z = mesh.NodePositions[i * 3 + 2];

            // Center point
            float cx = 25f, cy = 25f, cz = 25f; // Center of 50x50x50 mesh
            float dx = x - cx;
            float dy = y - cy;
            float dz = z - cz;
            float dist = MathF.Sqrt(dx * dx + dy * dy + dz * dz);

            // Wave pattern: amplitude varies with time and distance from center
            float amplitude = 5.0f * MathF.Sin(phase - dist * 0.2f);

            // Radial displacement
            float scale = dist > 0.01f ? amplitude / dist : 0;
            state.Displacements[i * 3 + 0] = dx * scale;
            state.Displacements[i * 3 + 1] = dy * scale;
            state.Displacements[i * 3 + 2] = dz * scale;
        }

        return state;
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

    private MeshData? _currentTestMesh; // Store test mesh for animation
    private bool _meshLoaded = false; // Track if mesh has been loaded already

    private void OnTimestepChanged()
    {
        if (_dataLoader != null)
        {
            CurrentTime = _dataLoader.GetTimestepTime(CurrentTimestep);

            // Load and update state data for the current timestep
            try
            {
                var stateData = _dataLoader.GetStateData(CurrentTimestep);

                // Use fast update path if mesh already loaded
                if (_meshLoaded)
                {
                    StateDataUpdated?.Invoke(stateData);
                }
                else
                {
                    // First load: full mesh rebuild
                    var meshData = _dataLoader.GetMeshData();
                    MeshDataLoaded?.Invoke(meshData, stateData);
                    _meshLoaded = true;
                }
            }
            catch (Exception ex)
            {
                AppendLog($"Error loading timestep {CurrentTimestep}: {ex.Message}");
            }
        }
        else if (_currentTestMesh != null)
        {
            // Test mesh animation
            CurrentTime = CurrentTimestep * 0.01;
            var state = GenerateTestDisplacement(_currentTestMesh, CurrentTimestep);

            // Use fast update path if mesh already loaded
            if (_meshLoaded)
            {
                StateDataUpdated?.Invoke(state);
            }
            else
            {
                // First load: full mesh rebuild
                MeshDataLoaded?.Invoke(_currentTestMesh, state);
                _meshLoaded = true;
            }
        }
    }

    public void LoadFile(string filePath)
    {
        try
        {
            StatusText = $"Loading {System.IO.Path.GetFileName(filePath)}...";

            _dataLoader = new Hdf5DataLoader(filePath);
            var info = _dataLoader.GetFileInfo();

            _currentTestMesh = null; // Clear test mesh
            _meshLoaded = false; // Reset flag for new file

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
