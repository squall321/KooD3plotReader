using Avalonia;
using Avalonia.Controls;
using Avalonia.Input;
using Avalonia.Media;
using Avalonia.Media.Imaging;
using Avalonia.Platform;
using Avalonia.Threading;
using KooD3plot.Data;
using KooD3plot.Rendering;
using KooD3plotViewer.Rendering;
using System;
using System.Numerics;
using System.Runtime.InteropServices;
using System.Threading;
using System.Threading.Tasks;
using Vector3 = System.Numerics.Vector3;

namespace KooD3plotViewer.Views;

public partial class VeldridView : UserControl
{
    private WriteableBitmap? _renderBitmap;
    private Image? _imageControl;
    private bool _isInitialized;
    private int _width = 800;
    private int _height = 600;

    // Camera/view state
    private float _rotationX;
    private float _rotationY;
    private float _zoom = 1.0f;
    private bool _isRotating;
    private bool _isPanning;
    private Point _lastMousePos;
    private Vector3 _panOffset = Vector3.Zero;

    // Render data
    private MeshRenderData? _meshData;
    private MeshData? _originalMesh; // Store for section cap generation
    private float[] _zBuffer = Array.Empty<float>();
    private Vector3 _modelCenter = Vector3.Zero;
    private float _modelScale = 1.0f;

    // GPU Renderer
    private GpuMeshRenderer? _gpuRenderer;
    private bool _useGpuRendering = true;  // Try GPU first
    private bool _gpuMeshUploaded = false;

    // Async loading state
    private bool _isLoading = false;
    private string _loadingStatus = "";
    private CancellationTokenSource? _loadingCts;

    // Log flags (to avoid spamming)
    private bool _logFirstTriOnce = false;
    private bool _logClipDebug = false;
    private bool _logTriCountOnce = false;
    private bool _logFillTriOnce = false;

    // Display options
    public bool ShowWireframe { get; set; } = false;
    public bool ShowSolid { get; set; } = true;
    public float DisplacementScale { get; set; } = 1.0f;

    // Color mapping settings
    private string _selectedColorMap = "Jet (Classic)";
    public string SelectedColorMap
    {
        get => _selectedColorMap;
        set
        {
            _selectedColorMap = value;
            UpdateColorMap();
        }
    }

    private void UpdateColorMap()
    {
        if (_gpuRenderer == null) return;

        // Map colormap name to enum
        var colorMapType = _selectedColorMap switch
        {
            "None (Solid Color)" => KooD3plotViewer.Rendering.ColorMap.ColorMapType.Jet,
            "Jet (Classic)" => KooD3plotViewer.Rendering.ColorMap.ColorMapType.Jet,
            "Viridis" => KooD3plotViewer.Rendering.ColorMap.ColorMapType.Viridis,
            "Plasma" => KooD3plotViewer.Rendering.ColorMap.ColorMapType.Plasma,
            "Turbo" => KooD3plotViewer.Rendering.ColorMap.ColorMapType.Turbo,
            "Rainbow" => KooD3plotViewer.Rendering.ColorMap.ColorMapType.Rainbow,
            "Cool" => KooD3plotViewer.Rendering.ColorMap.ColorMapType.Cool,
            "Hot" => KooD3plotViewer.Rendering.ColorMap.ColorMapType.Hot,
            _ => KooD3plotViewer.Rendering.ColorMap.ColorMapType.Jet
        };

        _gpuRenderer.UseColorMap = _selectedColorMap != "None (Solid Color)";
        _gpuRenderer.ColorMapType = colorMapType;

        // Update legend
        UpdateLegend();
    }

    private void UpdateLegend()
    {
        var legend = this.FindControl<Controls.ColorMapLegendControl>("ColorMapLegend");
        if (legend == null) return;

        bool showLegend = _selectedColorMap != "None (Solid Color)";
        legend.IsVisible = showLegend;

        if (showLegend && _gpuRenderer != null)
        {
            var colorMapType = _selectedColorMap switch
            {
                "Jet (Classic)" => KooD3plotViewer.Rendering.ColorMap.ColorMapType.Jet,
                "Viridis" => KooD3plotViewer.Rendering.ColorMap.ColorMapType.Viridis,
                "Plasma" => KooD3plotViewer.Rendering.ColorMap.ColorMapType.Plasma,
                "Turbo" => KooD3plotViewer.Rendering.ColorMap.ColorMapType.Turbo,
                "Rainbow" => KooD3plotViewer.Rendering.ColorMap.ColorMapType.Rainbow,
                "Cool" => KooD3plotViewer.Rendering.ColorMap.ColorMapType.Cool,
                "Hot" => KooD3plotViewer.Rendering.ColorMap.ColorMapType.Hot,
                _ => KooD3plotViewer.Rendering.ColorMap.ColorMapType.Jet
            };

            legend.SetColorMap(
                colorMapType,
                _gpuRenderer.ColorScaleMin,
                _gpuRenderer.ColorScaleMax,
                "Stress (MPa)"
            );
        }
    }

    // Clip plane settings
    private bool _clipXEnabled;
    private bool _clipYEnabled;
    private bool _clipZEnabled;
    private float _clipXValue = 0.5f;
    private float _clipYValue = 0.5f;
    private float _clipZValue = 0.5f;
    private bool _clipXInvert;
    private bool _clipYInvert;
    private bool _clipZInvert;

    public bool ClipXEnabled
    {
        get => _clipXEnabled;
        set { _clipXEnabled = value; UpdateClipPlanes(); }
    }

    public bool ClipYEnabled
    {
        get => _clipYEnabled;
        set { _clipYEnabled = value; UpdateClipPlanes(); }
    }

    public bool ClipZEnabled
    {
        get => _clipZEnabled;
        set { _clipZEnabled = value; UpdateClipPlanes(); }
    }

    public float ClipXValue
    {
        get => _clipXValue;
        set { _clipXValue = value; UpdateClipPlanes(); }
    }

    public float ClipYValue
    {
        get => _clipYValue;
        set { _clipYValue = value; UpdateClipPlanes(); }
    }

    public float ClipZValue
    {
        get => _clipZValue;
        set { _clipZValue = value; UpdateClipPlanes(); }
    }

    public bool ClipXInvert
    {
        get => _clipXInvert;
        set { _clipXInvert = value; UpdateClipPlanes(); }
    }

    public bool ClipYInvert
    {
        get => _clipYInvert;
        set { _clipYInvert = value; UpdateClipPlanes(); }
    }

    public bool ClipZInvert
    {
        get => _clipZInvert;
        set { _clipZInvert = value; UpdateClipPlanes(); }
    }

    private bool _showClipCap = true;
    public bool ShowClipCap
    {
        get => _showClipCap;
        set { _showClipCap = value; UpdateClipPlanes(); }
    }

    private void UpdateClipPlanes()
    {
        // Only use GPU renderer if it exists AND GPU is still working
        if (_gpuRenderer != null && _useGpuRendering)
        {
            try
            {
                _gpuRenderer.ClipXEnabled = _clipXEnabled;
                _gpuRenderer.ClipYEnabled = _clipYEnabled;
                _gpuRenderer.ClipZEnabled = _clipZEnabled;
                _gpuRenderer.ClipXValue = _clipXValue;
                _gpuRenderer.ClipYValue = _clipYValue;
                _gpuRenderer.ClipZValue = _clipZValue;
                _gpuRenderer.ClipXInvert = _clipXInvert;
                _gpuRenderer.ClipYInvert = _clipYInvert;
                _gpuRenderer.ClipZInvert = _clipZInvert;
                _gpuRenderer.ShowClipCap = _showClipCap;

                // Only update clip cap geometry when at least one clip plane is enabled
                bool anyClipEnabled = _clipXEnabled || _clipYEnabled || _clipZEnabled;
                if (anyClipEnabled)
                {
                    _gpuRenderer.UpdateClipCaps();

                    // Also update VeldridView section caps if mesh is loaded
                    if (_meshData != null && _originalMesh != null)
                    {
                        UploadSectionCaps();
                    }
                }
            }
            catch (Exception ex)
            {
                Log($"[CLIP-UPDATE] GPU error, falling back to software: {ex.Message}");
                _useGpuRendering = false;
            }
        }

        // Always trigger re-render (for both GPU and software rendering)
        InvalidateVisual();
    }

    // Log callback
    public Action<string>? LogCallback { get; set; }

    private void Log(string message)
    {
        LogCallback?.Invoke(message);
        Console.WriteLine(message);
    }

    public VeldridView()
    {
        InitializeComponent();
    }

    protected override void OnAttachedToVisualTree(VisualTreeAttachmentEventArgs e)
    {
        base.OnAttachedToVisualTree(e);
        InitializeRenderer();
    }

    private void InitializeRenderer()
    {
        if (_isInitialized) return;

        try
        {
            _renderBitmap = new WriteableBitmap(
                new PixelSize(_width, _height),
                new Avalonia.Vector(96, 96),
                Avalonia.Platform.PixelFormat.Bgra8888,
                AlphaFormat.Premul);

            _imageControl = new Image
            {
                Source = _renderBitmap,
                Stretch = Stretch.Fill,
                IsHitTestVisible = false  // Let mouse events pass through to VeldridView
            };

            var border = this.FindControl<Border>("RenderTarget");
            if (border != null)
            {
                border.Child = _imageControl;
            }

            _zBuffer = new float[_width * _height];

            // Try to initialize GPU renderer
            if (_useGpuRendering)
            {
                try
                {
                    _gpuRenderer = new GpuMeshRenderer();
                    _gpuRenderer.SetLogCallback(Log);
                    if (!_gpuRenderer.Initialize(_width, _height))
                    {
                        _gpuRenderer.Dispose();
                        _gpuRenderer = null;
                        _useGpuRendering = false;
                        Log("Falling back to software rendering");
                    }
                }
                catch (Exception gpuEx)
                {
                    Log($"GPU init error: {gpuEx.Message}");
                    _gpuRenderer?.Dispose();
                    _gpuRenderer = null;
                    _useGpuRendering = false;
                }
            }

            _isInitialized = true;

            StartRenderLoop();
        }
        catch (Exception ex)
        {
            Console.WriteLine($"Failed to initialize renderer: {ex.Message}");
        }
    }

    private void StartRenderLoop()
    {
        var timer = new DispatcherTimer
        {
            Interval = TimeSpan.FromMilliseconds(33)
        };
        timer.Tick += (s, e) =>
        {
            if (_isInitialized)
            {
                Render();
            }
        };
        timer.Start();
    }

    private void Render()
    {
        if (_renderBitmap == null) return;

        using (var fb = _renderBitmap.Lock())
        {
            var pixels = new uint[_width * _height];

            // Try GPU rendering first, fall back to software if it fails
            // Also check if GPU device was lost - if so, permanently fall back to software
            if (_gpuRenderer != null && _gpuRenderer.IsDeviceLost)
            {
                Log("[RENDER] GPU device permanently lost - using software rendering");
                _useGpuRendering = false;
            }

            // Check if GPU device was recreated and needs mesh re-upload
            if (_gpuRenderer != null && _gpuRenderer.NeedsMeshReupload && _meshData != null && _originalMesh != null)
            {
                Log("[RENDER] GPU device recreated - re-uploading mesh...");
                _gpuMeshUploaded = false;
                ReuploadMeshToGpu();
            }

            bool usingGpu = _useGpuRendering && _gpuRenderer != null && _gpuRenderer.IsDeviceAvailable && _gpuMeshUploaded && _meshData != null;

            if (usingGpu)
            {
                if (_logFirstTriOnce)
                {
                    Log("Using GPU rendering");
                    _logFirstTriOnce = false;
                }
                RenderWithGpu(pixels);
            }
            else
            {
                if (_logFirstTriOnce && _gpuMeshUploaded)
                {
                    Log($"Using SOFTWARE rendering (useGpu={_useGpuRendering}, renderer={_gpuRenderer != null}, uploaded={_gpuMeshUploaded})");
                    _logFirstTriOnce = false;
                }
                // Software rendering fallback
                // Clear buffers
                uint clearColor = 0xFF252526;
                for (int i = 0; i < pixels.Length; i++)
                {
                    pixels[i] = clearColor;
                    _zBuffer[i] = float.MaxValue;
                }

                // Draw grid
                DrawGrid(pixels);

                // Draw mesh or demo cube (only if not loading)
                if (!_isLoading && _meshData != null && _meshData.CurrentPositions.Length > 0)
                {
                    DrawMesh(pixels);
                }
                else if (!_isLoading)
                {
                    DrawWireframeCube(pixels);
                }

                // Draw axes
                DrawAxes(pixels);
            }

            // Draw loading indicator if loading
            if (_isLoading || !string.IsNullOrEmpty(_loadingStatus))
            {
                DrawLoadingIndicator(pixels);
            }

            Marshal.Copy(MemoryMarshal.Cast<uint, byte>(pixels.AsSpan()).ToArray(), 0, fb.Address, pixels.Length * 4);
        }

        _imageControl?.InvalidateVisual();
    }

    private void RenderWithGpu(uint[] pixels)
    {
        if (_gpuRenderer == null || _meshData == null) return;

        // Build transformation matrix
        float cosX = MathF.Cos(_rotationX);
        float sinX = MathF.Sin(_rotationX);
        float cosY = MathF.Cos(_rotationY);
        float sinY = MathF.Sin(_rotationY);

        // Build rotation matrices
        var rotY = new Matrix4x4(
            cosY, 0, -sinY, 0,
            0, 1, 0, 0,
            sinY, 0, cosY, 0,
            0, 0, 0, 1);

        var rotX = new Matrix4x4(
            1, 0, 0, 0,
            0, cosX, sinX, 0,
            0, -sinX, cosX, 0,
            0, 0, 0, 1);

        // Translation to center the model
        var translation = Matrix4x4.CreateTranslation(-_modelCenter.X, -_modelCenter.Y, -_modelCenter.Z);

        // Scale to normalized size
        var scale = Matrix4x4.CreateScale(_modelScale);

        // Apply pan
        var panTranslation = Matrix4x4.CreateTranslation(_panOffset.X / (_width * 0.4f * _zoom),
                                                          -_panOffset.Y / (_height * 0.4f * _zoom), 0);

        // Build world matrix: translate to origin -> scale -> rotate
        var world = translation * scale * rotY * rotX * panTranslation;

        // Orthographic projection
        float aspect = (float)_width / _height;
        float orthoScale = 2.0f / _zoom;  // Larger orthoScale = smaller view
        var projection = Matrix4x4.CreateOrthographic(orthoScale * aspect, orthoScale, -10f, 10f);

        // Final world-view-projection matrix
        var wvp = world * projection;

        // Render
        try
        {
            _gpuRenderer.Render(wvp, pixels);
        }
        catch (Exception ex)
        {
            Log($"GPU render error: {ex.GetType().Name}: {ex.Message}");
            Log($"Stack trace: {ex.StackTrace}");
            if (ex.InnerException != null)
            {
                Log($"Inner exception: {ex.InnerException.Message}");
            }
            _useGpuRendering = false; // Fallback to software
        }
    }

    public void LoadMeshData(MeshData mesh, StateData? state)
    {
        // Cancel any previous loading operation
        _loadingCts?.Cancel();
        _loadingCts = new CancellationTokenSource();
        var ct = _loadingCts.Token;

        // Reset log flags for new mesh
        _logFirstTriOnce = true;
        _logTriCountOnce = true;
        _logFillTriOnce = true;
        _fillDebugCounter = 0;

        _isLoading = true;
        _loadingStatus = "Processing mesh...";
        _gpuMeshUploaded = false;

        int nodeCount = mesh.NodePositions.Length / 3;
        int solidCount = mesh.SolidConnectivity.Length / 8;
        Log($"LoadMeshData: nodes={nodeCount}, solids={solidCount}");

        // Process mesh data on background thread
        Task.Run(() =>
        {
            try
            {
                if (ct.IsCancellationRequested) return;

                // Heavy computation on background thread
                var sw = System.Diagnostics.Stopwatch.StartNew();
                var renderData = CreateRenderData(mesh, state);
                sw.Stop();

                if (ct.IsCancellationRequested) return;

                // Update UI thread with results
                Dispatcher.UIThread.Post(() =>
                {
                    if (ct.IsCancellationRequested) return;

                    _meshData = renderData;
                    _originalMesh = mesh; // Store for section cap generation
                    Log($"RenderData: verts={_meshData.VertexCount}, tris={_meshData.TriangleCount} ({sw.ElapsedMilliseconds}ms)");

                    // Compute model center and scale for proper viewing
                    if (_meshData.CurrentPositions.Length > 0)
                    {
                        _meshData.ComputeBounds();
                        _modelCenter = (_meshData.BoundsMin + _meshData.BoundsMax) * 0.5f;
                        var size = _meshData.BoundsMax - _meshData.BoundsMin;
                        float maxDim = Math.Max(Math.Max(size.X, size.Y), size.Z);

                        if (maxDim > 0.0001f)
                            _modelScale = 2.0f / maxDim;
                        else
                            _modelScale = 1.0f;

                        Log($"Bounds: min={_meshData.BoundsMin}, max={_meshData.BoundsMax}");
                        Log($"Center={_modelCenter}, Scale={_modelScale:F4}, MaxDim={maxDim:F1}");

                        // Update GPU renderer with model bounds for clip planes
                        if (_gpuRenderer != null)
                        {
                            _gpuRenderer.ModelBoundsMin = _meshData.BoundsMin;
                            _gpuRenderer.ModelBoundsMax = _meshData.BoundsMax;
                            Log($"[CLIP-SETUP] ModelBounds set: min={_meshData.BoundsMin}, max={_meshData.BoundsMax}");
                        }

                        // Reset view
                        _zoom = 1.0f;
                        _panOffset = Vector3.Zero;
                        _rotationX = 0.3f;
                        _rotationY = 0.5f;
                    }

                    _isLoading = false;
                    _loadingStatus = "";

                    Log("Mesh processed, uploading to GPU...");

                    // Start GPU upload asynchronously
                    UploadMeshToGpuAsync(ct);
                });
            }
            catch (Exception ex)
            {
                Dispatcher.UIThread.Post(() =>
                {
                    Log($"Mesh processing error: {ex.Message}");
                    _isLoading = false;
                    _loadingStatus = "";
                });
            }
        }, ct);
    }

    private void UploadMeshToGpuAsync(CancellationToken ct)
    {
        if (_gpuRenderer == null || _meshData == null || _meshData.Indices.Length == 0)
        {
            _gpuMeshUploaded = false;
            return;
        }

        var meshData = _meshData; // Capture for closure

        Task.Run(() =>
        {
            try
            {
                if (ct.IsCancellationRequested) return;

                var sw = System.Diagnostics.Stopwatch.StartNew();

                // Build GPU vertex buffer on background thread
                int numIndices = meshData.Indices.Length;
                var vertices = new GpuMeshRenderer.VertexPositionNormalColor[numIndices];

                // Parallel processing for large meshes
                int chunkSize = Math.Max(3000, numIndices / Environment.ProcessorCount);
                Parallel.For(0, (numIndices + chunkSize - 1) / chunkSize, chunkIdx =>
                {
                    if (ct.IsCancellationRequested) return;

                    int start = chunkIdx * chunkSize;
                    int end = Math.Min(start + chunkSize, numIndices);
                    // Ensure we start at triangle boundary
                    start = (start / 3) * 3;
                    end = Math.Min(((end + 2) / 3) * 3, numIndices);

                    for (int i = start; i < end; i += 3)
                    {
                        uint i0 = meshData.Indices[i + 0];
                        uint i1 = meshData.Indices[i + 1];
                        uint i2 = meshData.Indices[i + 2];

                        Vector3 p0 = new Vector3(
                            meshData.CurrentPositions[i0 * 3 + 0],
                            meshData.CurrentPositions[i0 * 3 + 1],
                            meshData.CurrentPositions[i0 * 3 + 2]);
                        Vector3 p1 = new Vector3(
                            meshData.CurrentPositions[i1 * 3 + 0],
                            meshData.CurrentPositions[i1 * 3 + 1],
                            meshData.CurrentPositions[i1 * 3 + 2]);
                        Vector3 p2 = new Vector3(
                            meshData.CurrentPositions[i2 * 3 + 0],
                            meshData.CurrentPositions[i2 * 3 + 1],
                            meshData.CurrentPositions[i2 * 3 + 2]);

                        Vector3 edge1 = p1 - p0;
                        Vector3 edge2 = p2 - p0;
                        Vector3 normal = Vector3.Normalize(Vector3.Cross(edge1, edge2));
                        if (float.IsNaN(normal.X)) normal = Vector3.UnitZ;

                        Vector4 c0 = GetJetColorVecFromData(meshData, (int)i0);
                        Vector4 c1 = GetJetColorVecFromData(meshData, (int)i1);
                        Vector4 c2 = GetJetColorVecFromData(meshData, (int)i2);

                        vertices[i + 0] = new GpuMeshRenderer.VertexPositionNormalColor { Position = p0, Normal = normal, Color = c0 };
                        vertices[i + 1] = new GpuMeshRenderer.VertexPositionNormalColor { Position = p1, Normal = normal, Color = c1 };
                        vertices[i + 2] = new GpuMeshRenderer.VertexPositionNormalColor { Position = p2, Normal = normal, Color = c2 };
                    }
                });

                if (ct.IsCancellationRequested) return;

                // Build sequential indices
                var indices = new uint[numIndices];
                for (uint i = 0; i < numIndices; i++)
                    indices[i] = i;

                sw.Stop();
                long prepTime = sw.ElapsedMilliseconds;

                // GPU upload must happen on UI thread (for some graphics APIs)
                Dispatcher.UIThread.Post(() =>
                {
                    if (ct.IsCancellationRequested) return;

                    try
                    {
                        var uploadSw = System.Diagnostics.Stopwatch.StartNew();
                        _gpuRenderer!.UploadMesh(vertices, indices);
                        uploadSw.Stop();

                        _gpuMeshUploaded = true;
                        _loadingStatus = "";
                        Log($"GPU upload: {numIndices / 3} tris (prep:{prepTime}ms, upload:{uploadSw.ElapsedMilliseconds}ms)");
                        Log("Mesh ready for rendering!");

                        // Trigger initial render
                        InvalidateVisual();
                    }
                    catch (Exception ex)
                    {
                        Log($"GPU upload failed: {ex.Message}");
                        _gpuMeshUploaded = false;
                        _loadingStatus = "";
                    }
                });
            }
            catch (Exception ex)
            {
                Dispatcher.UIThread.Post(() =>
                {
                    Log($"GPU prep error: {ex.Message}");
                    _gpuMeshUploaded = false;
                    _loadingStatus = "";
                });
            }
        }, ct);
    }

    /// <summary>
    /// Re-upload mesh to GPU after device recreation (synchronous, called from render loop)
    /// </summary>
    private void ReuploadMeshToGpu()
    {
        if (_gpuRenderer == null || _meshData == null || _meshData.Indices.Length == 0)
        {
            _gpuMeshUploaded = false;
            return;
        }

        try
        {
            var sw = System.Diagnostics.Stopwatch.StartNew();

            // Build GPU vertex buffer
            int numIndices = _meshData.Indices.Length;
            var vertices = new GpuMeshRenderer.VertexPositionNormalColor[numIndices];

            for (int i = 0; i < numIndices; i += 3)
            {
                uint i0 = _meshData.Indices[i + 0];
                uint i1 = _meshData.Indices[i + 1];
                uint i2 = _meshData.Indices[i + 2];

                Vector3 p0 = new Vector3(
                    _meshData.CurrentPositions[i0 * 3 + 0],
                    _meshData.CurrentPositions[i0 * 3 + 1],
                    _meshData.CurrentPositions[i0 * 3 + 2]);
                Vector3 p1 = new Vector3(
                    _meshData.CurrentPositions[i1 * 3 + 0],
                    _meshData.CurrentPositions[i1 * 3 + 1],
                    _meshData.CurrentPositions[i1 * 3 + 2]);
                Vector3 p2 = new Vector3(
                    _meshData.CurrentPositions[i2 * 3 + 0],
                    _meshData.CurrentPositions[i2 * 3 + 1],
                    _meshData.CurrentPositions[i2 * 3 + 2]);

                Vector3 edge1 = p1 - p0;
                Vector3 edge2 = p2 - p0;
                Vector3 normal = Vector3.Normalize(Vector3.Cross(edge1, edge2));
                if (float.IsNaN(normal.X)) normal = Vector3.UnitZ;

                Vector4 c0 = GetJetColorVecFromData(_meshData, (int)i0);
                Vector4 c1 = GetJetColorVecFromData(_meshData, (int)i1);
                Vector4 c2 = GetJetColorVecFromData(_meshData, (int)i2);

                vertices[i + 0] = new GpuMeshRenderer.VertexPositionNormalColor { Position = p0, Normal = normal, Color = c0 };
                vertices[i + 1] = new GpuMeshRenderer.VertexPositionNormalColor { Position = p1, Normal = normal, Color = c1 };
                vertices[i + 2] = new GpuMeshRenderer.VertexPositionNormalColor { Position = p2, Normal = normal, Color = c2 };
            }

            // Build sequential indices
            var indices = new uint[numIndices];
            for (uint i = 0; i < numIndices; i++)
                indices[i] = i;

            sw.Stop();
            long prepTime = sw.ElapsedMilliseconds;

            var uploadSw = System.Diagnostics.Stopwatch.StartNew();
            _gpuRenderer.UploadMesh(vertices, indices);
            uploadSw.Stop();

            _gpuMeshUploaded = true;
            Log($"GPU re-upload: {numIndices / 3} tris (prep:{prepTime}ms, upload:{uploadSw.ElapsedMilliseconds}ms)");
        }
        catch (Exception ex)
        {
            Log($"GPU re-upload failed: {ex.Message}");
            _gpuMeshUploaded = false;
            _useGpuRendering = false;  // Fall back to software rendering
        }
    }

    /// <summary>
    /// Fast update of state data (displacement/scalars) without rebuilding mesh topology
    /// </summary>
    public void UpdateStateData(StateData state)
    {
        if (_meshData == null || _gpuRenderer == null || !_gpuMeshUploaded)
        {
            Log("UpdateStateData: Mesh not loaded, skipping fast update");
            return;
        }

        // Don't show loading indicator for fast state updates during animation
        // Process on background thread
        Task.Run(() =>
        {
            try
            {
                var sw = System.Diagnostics.Stopwatch.StartNew();

                // Update positions with displacement
                int nodeCount = _meshData.BasePositions.Length / 3;
                var newPositions = new float[_meshData.BasePositions.Length];

                if (state.Displacements != null && state.Displacements.Length == _meshData.BasePositions.Length)
                {
                    for (int i = 0; i < _meshData.BasePositions.Length; i++)
                    {
                        newPositions[i] = _meshData.BasePositions[i] + state.Displacements[i] * DisplacementScale;
                    }
                }
                else
                {
                    Array.Copy(_meshData.BasePositions, newPositions, _meshData.BasePositions.Length);
                }

                // Update scalar values (displacement magnitude for colormap)
                var newScalarValues = new float[nodeCount];
                if (state.Displacements != null)
                {
                    for (int i = 0; i < nodeCount; i++)
                    {
                        float dx = state.Displacements[i * 3 + 0];
                        float dy = state.Displacements[i * 3 + 1];
                        float dz = state.Displacements[i * 3 + 2];
                        newScalarValues[i] = MathF.Sqrt(dx * dx + dy * dy + dz * dz);
                    }
                }

                // Compute min/max for color mapping
                float scalarMin = float.MaxValue;
                float scalarMax = float.MinValue;
                foreach (var val in newScalarValues)
                {
                    if (val < scalarMin) scalarMin = val;
                    if (val > scalarMax) scalarMax = val;
                }

                // Update mesh data
                _meshData.CurrentPositions = newPositions;
                _meshData.ScalarValues = newScalarValues;
                _meshData.ScalarMin = scalarMin;
                _meshData.ScalarMax = scalarMax;

                // Rebuild vertex buffer with new positions/colors
                int numIndices = _meshData.Indices.Length;
                var vertices = new GpuMeshRenderer.VertexPositionNormalColor[numIndices];

                // Parallel processing
                int chunkSize = Math.Max(3000, numIndices / Environment.ProcessorCount);
                System.Threading.Tasks.Parallel.For(0, (numIndices + chunkSize - 1) / chunkSize, chunkIdx =>
                {
                    int start = chunkIdx * chunkSize;
                    int end = Math.Min(start + chunkSize, numIndices);
                    start = (start / 3) * 3;
                    end = Math.Min(((end + 2) / 3) * 3, numIndices);

                    for (int i = start; i < end; i += 3)
                    {
                        uint i0 = _meshData.Indices[i + 0];
                        uint i1 = _meshData.Indices[i + 1];
                        uint i2 = _meshData.Indices[i + 2];

                        Vector3 p0 = new Vector3(
                            newPositions[i0 * 3 + 0],
                            newPositions[i0 * 3 + 1],
                            newPositions[i0 * 3 + 2]);
                        Vector3 p1 = new Vector3(
                            newPositions[i1 * 3 + 0],
                            newPositions[i1 * 3 + 1],
                            newPositions[i1 * 3 + 2]);
                        Vector3 p2 = new Vector3(
                            newPositions[i2 * 3 + 0],
                            newPositions[i2 * 3 + 1],
                            newPositions[i2 * 3 + 2]);

                        Vector3 edge1 = p1 - p0;
                        Vector3 edge2 = p2 - p0;
                        Vector3 normal = Vector3.Normalize(Vector3.Cross(edge1, edge2));
                        if (float.IsNaN(normal.X)) normal = Vector3.UnitZ;

                        Vector4 c0 = GetJetColorVecFromData(_meshData, (int)i0);
                        Vector4 c1 = GetJetColorVecFromData(_meshData, (int)i1);
                        Vector4 c2 = GetJetColorVecFromData(_meshData, (int)i2);

                        vertices[i + 0] = new GpuMeshRenderer.VertexPositionNormalColor { Position = p0, Normal = normal, Color = c0 };
                        vertices[i + 1] = new GpuMeshRenderer.VertexPositionNormalColor { Position = p1, Normal = normal, Color = c1 };
                        vertices[i + 2] = new GpuMeshRenderer.VertexPositionNormalColor { Position = p2, Normal = normal, Color = c2 };
                    }
                });

                sw.Stop();

                // Update GPU on UI thread
                Dispatcher.UIThread.Post(() =>
                {
                    try
                    {
                        _gpuRenderer!.UpdateVertexData(vertices);
                        _gpuRenderer.ColorScaleMin = scalarMin;
                        _gpuRenderer.ColorScaleMax = scalarMax;

                        UpdateLegend();

                        _loadingStatus = "";
                        Log($"Fast state update: {sw.ElapsedMilliseconds}ms");
                    }
                    catch (Exception ex)
                    {
                        Log($"GPU update error: {ex.Message}");
                        _loadingStatus = "";
                    }
                });
            }
            catch (Exception ex)
            {
                Dispatcher.UIThread.Post(() =>
                {
                    Log($"State update error: {ex.Message}");
                    _loadingStatus = "";
                });
            }
        });
    }

    private static Vector4 GetJetColorVecFromData(MeshRenderData meshData, int vertexIndex)
    {
        if (meshData.ScalarValues.Length == 0)
            return new Vector4(0.5f, 0.56f, 0.63f, 1.0f);

        float scalar = meshData.ScalarValues[vertexIndex];
        float range = meshData.ScalarMax - meshData.ScalarMin;
        float t = range > 0 ? (scalar - meshData.ScalarMin) / range : 0.5f;
        t = Math.Clamp(t, 0f, 1f);

        float r, g, b;
        if (t < 0.25f) { float s = t / 0.25f; r = 0; g = s; b = 1; }
        else if (t < 0.5f) { float s = (t - 0.25f) / 0.25f; r = 0; g = 1; b = 1 - s; }
        else if (t < 0.75f) { float s = (t - 0.5f) / 0.25f; r = s; g = 1; b = 0; }
        else { float s = (t - 0.75f) / 0.25f; r = 1; g = 1 - s; b = 0; }

        return new Vector4(r, g, b, 1.0f);
    }


    private MeshRenderData CreateRenderData(MeshData mesh, StateData? state)
    {
        var renderData = new MeshRenderData
        {
            BasePositions = mesh.NodePositions,
            CurrentPositions = new float[mesh.NodePositions.Length],
            VertexCount = mesh.NodePositions.Length / 3
        };

        // Copy base positions to current
        Array.Copy(mesh.NodePositions, renderData.CurrentPositions, mesh.NodePositions.Length);

        // Apply displacement if available
        if (state != null && state.Displacements.Length == mesh.NodePositions.Length)
        {
            renderData.ApplyDisplacement(state.Displacements, DisplacementScale);
        }

        // Build triangle indices from shell and solid connectivity
        var indices = new System.Collections.Generic.List<uint>();

        // Shell connectivity format: node0, node1, node2, node3 (quads) per element
        if (mesh.ShellConnectivity.Length > 0)
        {
            int numElements = mesh.ShellConnectivity.Length / 4;

            for (int e = 0; e < numElements; e++)
            {
                int n0 = mesh.ShellConnectivity[e * 4 + 0];
                int n1 = mesh.ShellConnectivity[e * 4 + 1];
                int n2 = mesh.ShellConnectivity[e * 4 + 2];
                int n3 = mesh.ShellConnectivity[e * 4 + 3];

                // First triangle (0-1-2)
                if (n0 >= 0 && n1 >= 0 && n2 >= 0 && n0 < renderData.VertexCount && n1 < renderData.VertexCount && n2 < renderData.VertexCount)
                {
                    indices.Add((uint)n0);
                    indices.Add((uint)n1);
                    indices.Add((uint)n2);
                }

                // Second triangle (0-2-3) for quads
                if (n3 >= 0 && n0 >= 0 && n2 >= 0 && n3 != n2 && n3 < renderData.VertexCount)
                {
                    indices.Add((uint)n0);
                    indices.Add((uint)n2);
                    indices.Add((uint)n3);
                }
            }
        }

        // Solid connectivity format: 8 nodes per hex element - render ONLY exterior faces
        if (mesh.SolidConnectivity.Length > 0)
        {
            int numElements = mesh.SolidConnectivity.Length / 8;

            // Build a set of shared faces to identify exterior faces
            // A face is exterior if it's not shared by two elements
            var faceCount = new Dictionary<(int, int, int, int), int>();

            // Hex faces (6 faces, each with 4 nodes)
            int[,] hexFaces = new int[6, 4]
            {
                { 0, 3, 2, 1 }, // bottom (Z-)
                { 4, 5, 6, 7 }, // top (Z+)
                { 0, 1, 5, 4 }, // front (Y-)
                { 2, 3, 7, 6 }, // back (Y+)
                { 1, 2, 6, 5 }, // right (X+)
                { 0, 4, 7, 3 }  // left (X-)
            };

            // First pass: count face occurrences
            for (int e = 0; e < numElements; e++)
            {
                int[] nodes = new int[8];
                for (int i = 0; i < 8; i++)
                    nodes[i] = mesh.SolidConnectivity[e * 8 + i];

                for (int f = 0; f < 6; f++)
                {
                    int[] faceNodes = new int[4];
                    for (int i = 0; i < 4; i++)
                        faceNodes[i] = nodes[hexFaces[f, i]];

                    // Sort to create canonical face key
                    Array.Sort(faceNodes);
                    var key = (faceNodes[0], faceNodes[1], faceNodes[2], faceNodes[3]);

                    if (faceCount.ContainsKey(key))
                        faceCount[key]++;
                    else
                        faceCount[key] = 1;
                }
            }

            // Second pass: only add exterior faces (count == 1)
            for (int e = 0; e < numElements; e++)
            {
                int[] nodes = new int[8];
                for (int i = 0; i < 8; i++)
                    nodes[i] = mesh.SolidConnectivity[e * 8 + i];

                for (int f = 0; f < 6; f++)
                {
                    int n0 = nodes[hexFaces[f, 0]];
                    int n1 = nodes[hexFaces[f, 1]];
                    int n2 = nodes[hexFaces[f, 2]];
                    int n3 = nodes[hexFaces[f, 3]];

                    // Check if exterior
                    int[] faceNodes = new int[] { n0, n1, n2, n3 };
                    Array.Sort(faceNodes);
                    var key = (faceNodes[0], faceNodes[1], faceNodes[2], faceNodes[3]);

                    if (faceCount[key] == 1) // Exterior face
                    {
                        if (n0 >= 0 && n1 >= 0 && n2 >= 0 && n3 >= 0 &&
                            n0 < renderData.VertexCount && n1 < renderData.VertexCount &&
                            n2 < renderData.VertexCount && n3 < renderData.VertexCount)
                        {
                            // Two triangles per quad face
                            indices.Add((uint)n0);
                            indices.Add((uint)n1);
                            indices.Add((uint)n2);

                            indices.Add((uint)n0);
                            indices.Add((uint)n2);
                            indices.Add((uint)n3);
                        }
                    }
                }
            }

            Log($"Exterior faces: {indices.Count / 3} triangles (from {numElements * 12} total)");
        }

        renderData.Indices = indices.ToArray();
        renderData.TriangleCount = indices.Count / 3;

        // Build wireframe indices
        var wireIndices = new System.Collections.Generic.List<uint>();

        if (mesh.ShellConnectivity.Length > 0)
        {
            int numElements = mesh.ShellConnectivity.Length / 4;

            for (int e = 0; e < numElements; e++)
            {
                int n0 = mesh.ShellConnectivity[e * 4 + 0];
                int n1 = mesh.ShellConnectivity[e * 4 + 1];
                int n2 = mesh.ShellConnectivity[e * 4 + 2];
                int n3 = mesh.ShellConnectivity[e * 4 + 3];

                if (n0 >= 0 && n1 >= 0) { wireIndices.Add((uint)n0); wireIndices.Add((uint)n1); }
                if (n1 >= 0 && n2 >= 0) { wireIndices.Add((uint)n1); wireIndices.Add((uint)n2); }
                if (n2 >= 0 && n3 >= 0 && n3 != n2) { wireIndices.Add((uint)n2); wireIndices.Add((uint)n3); }
                if (n3 >= 0 && n0 >= 0 && n3 != n2) { wireIndices.Add((uint)n3); wireIndices.Add((uint)n0); }
                else if (n2 >= 0 && n0 >= 0) { wireIndices.Add((uint)n2); wireIndices.Add((uint)n0); }
            }
        }

        // Solid wireframe - 12 edges per hex
        if (mesh.SolidConnectivity.Length > 0)
        {
            int numElements = mesh.SolidConnectivity.Length / 8;
            int[,] hexEdges = new int[12, 2]
            {
                {0,1}, {1,2}, {2,3}, {3,0},  // bottom
                {4,5}, {5,6}, {6,7}, {7,4},  // top
                {0,4}, {1,5}, {2,6}, {3,7}   // verticals
            };

            for (int e = 0; e < numElements; e++)
            {
                int[] nodes = new int[8];
                for (int i = 0; i < 8; i++)
                    nodes[i] = mesh.SolidConnectivity[e * 8 + i];

                for (int edge = 0; edge < 12; edge++)
                {
                    int n0 = nodes[hexEdges[edge, 0]];
                    int n1 = nodes[hexEdges[edge, 1]];
                    if (n0 >= 0 && n1 >= 0 && n0 < renderData.VertexCount && n1 < renderData.VertexCount)
                    {
                        wireIndices.Add((uint)n0);
                        wireIndices.Add((uint)n1);
                    }
                }
            }
        }

        renderData.WireframeIndices = wireIndices.ToArray();

        // Compute scalar values for coloring (displacement magnitude)
        if (state != null && state.Displacements.Length > 0)
        {
            renderData.ScalarValues = new float[renderData.VertexCount];
            float minVal = float.MaxValue, maxVal = float.MinValue;

            for (int i = 0; i < renderData.VertexCount; i++)
            {
                float dx = state.Displacements[i * 3 + 0];
                float dy = state.Displacements[i * 3 + 1];
                float dz = state.Displacements[i * 3 + 2];
                float mag = MathF.Sqrt(dx * dx + dy * dy + dz * dz);
                renderData.ScalarValues[i] = mag;
                minVal = Math.Min(minVal, mag);
                maxVal = Math.Max(maxVal, mag);
            }

            renderData.ScalarMin = minVal;
            renderData.ScalarMax = maxVal;
        }

        // Compute normals
        renderData.ComputeNormals();
        renderData.ComputeBounds();

        return renderData;
    }

    /// <summary>
    /// Create section cap mesh at clip plane intersections
    /// </summary>
    private (List<Vector3> capVertices, List<float> capScalars, List<uint> capIndices) CreateSectionCapMesh(
        MeshData mesh, MeshRenderData renderData, char axis, float clipValue, bool invert)
    {
        var capVertices = new List<Vector3>();
        var capScalars = new List<float>();
        var capIndices = new List<uint>();

        if (mesh.SolidConnectivity.Length == 0)
            return (capVertices, capScalars, capIndices);

        int numElements = mesh.SolidConnectivity.Length / 8;
        Vector3 boundsMin = renderData.BoundsMin;
        Vector3 boundsMax = renderData.BoundsMax;

        // Calculate absolute clip position
        float clipPos = axis switch
        {
            'X' => boundsMin.X + clipValue * (boundsMax.X - boundsMin.X),
            'Y' => boundsMin.Y + clipValue * (boundsMax.Y - boundsMin.Y),
            'Z' => boundsMin.Z + clipValue * (boundsMax.Z - boundsMin.Z),
            _ => 0f
        };

        // Hex edge definitions (12 edges connecting 8 nodes)
        int[,] hexEdges = new int[12, 2]
        {
            {0,1}, {1,2}, {2,3}, {3,0}, // bottom
            {4,5}, {5,6}, {6,7}, {7,4}, // top
            {0,4}, {1,5}, {2,6}, {3,7}  // verticals
        };

        // Process each hex element
        for (int e = 0; e < numElements; e++)
        {
            // Get element nodes
            int[] nodeIndices = new int[8];
            Vector3[] nodePositions = new Vector3[8];
            float[] nodeScalars = new float[8];

            for (int i = 0; i < 8; i++)
            {
                int nodeIdx = mesh.SolidConnectivity[e * 8 + i];
                if (nodeIdx < 0 || nodeIdx >= renderData.VertexCount) continue;

                nodeIndices[i] = nodeIdx;
                nodePositions[i] = new Vector3(
                    renderData.CurrentPositions[nodeIdx * 3 + 0],
                    renderData.CurrentPositions[nodeIdx * 3 + 1],
                    renderData.CurrentPositions[nodeIdx * 3 + 2]
                );
                nodeScalars[i] = renderData.ScalarValues.Length > nodeIdx ?
                    renderData.ScalarValues[nodeIdx] : 0f;
            }

            // Find intersection points on edges
            var intersectionPoints = new List<(Vector3 pos, float scalar)>();

            for (int edge = 0; edge < 12; edge++)
            {
                Vector3 p0 = nodePositions[hexEdges[edge, 0]];
                Vector3 p1 = nodePositions[hexEdges[edge, 1]];
                float s0 = nodeScalars[hexEdges[edge, 0]];
                float s1 = nodeScalars[hexEdges[edge, 1]];

                // Get coordinate along clip axis
                float v0 = axis switch { 'X' => p0.X, 'Y' => p0.Y, 'Z' => p0.Z, _ => 0f };
                float v1 = axis switch { 'X' => p1.X, 'Y' => p1.Y, 'Z' => p1.Z, _ => 0f };

                // Check if edge crosses clip plane
                if ((v0 <= clipPos && v1 >= clipPos) || (v0 >= clipPos && v1 <= clipPos))
                {
                    // Linear interpolation parameter
                    float t = Math.Abs(v1 - v0) > 1e-6f ? (clipPos - v0) / (v1 - v0) : 0.5f;
                    t = Math.Clamp(t, 0f, 1f);

                    // Interpolate position and scalar
                    Vector3 intersectPos = p0 + t * (p1 - p0);
                    float intersectScalar = s0 + t * (s1 - s0);

                    intersectionPoints.Add((intersectPos, intersectScalar));
                }
            }

            // Need at least 3 points to form a polygon
            if (intersectionPoints.Count >= 3)
            {
                // Compute polygon center for triangulation
                Vector3 center = Vector3.Zero;
                float centerScalar = 0f;
                foreach (var (pos, scalar) in intersectionPoints)
                {
                    center += pos;
                    centerScalar += scalar;
                }
                center /= intersectionPoints.Count;
                centerScalar /= intersectionPoints.Count;

                // Sort points by angle around center (for proper triangulation)
                // Project to 2D plane perpendicular to clip axis
                var sortedPoints = SortPolygonPoints(intersectionPoints, center, axis);

                // Add center vertex
                uint centerIdx = (uint)capVertices.Count;
                capVertices.Add(center);
                capScalars.Add(centerScalar);

                // Create triangles from center to each edge
                for (int i = 0; i < sortedPoints.Count; i++)
                {
                    uint idx0 = (uint)capVertices.Count;
                    uint idx1 = (uint)(capVertices.Count + 1);

                    capVertices.Add(sortedPoints[i].pos);
                    capScalars.Add(sortedPoints[i].scalar);

                    int nextI = (i + 1) % sortedPoints.Count;
                    capVertices.Add(sortedPoints[nextI].pos);
                    capScalars.Add(sortedPoints[nextI].scalar);

                    // Add triangle (winding order depends on invert)
                    if (!invert)
                    {
                        capIndices.Add(centerIdx);
                        capIndices.Add(idx0);
                        capIndices.Add(idx1);
                    }
                    else
                    {
                        capIndices.Add(centerIdx);
                        capIndices.Add(idx1);
                        capIndices.Add(idx0);
                    }
                }
            }
        }

        return (capVertices, capScalars, capIndices);
    }

    /// <summary>
    /// Sort polygon points by angle around center (for triangulation)
    /// </summary>
    private List<(Vector3 pos, float scalar)> SortPolygonPoints(
        List<(Vector3 pos, float scalar)> points, Vector3 center, char axis)
    {
        // Choose two axes perpendicular to the clip axis
        int axis1, axis2;
        switch (axis)
        {
            case 'X': axis1 = 1; axis2 = 2; break; // Y-Z plane
            case 'Y': axis1 = 0; axis2 = 2; break; // X-Z plane
            case 'Z': default: axis1 = 0; axis2 = 1; break; // X-Y plane
        }

        // Compute angles and sort
        var pointsWithAngle = points.Select(p =>
        {
            Vector3 dir = p.pos - center;
            float[] dirArray = { dir.X, dir.Y, dir.Z };
            float angle = MathF.Atan2(dirArray[axis2], dirArray[axis1]);
            return (p.pos, p.scalar, angle);
        }).OrderBy(p => p.angle).ToList();

        return pointsWithAngle.Select(p => (p.pos, p.scalar)).ToList();
    }

    private void DrawMesh(uint[] pixels)
    {
        if (_meshData == null) return;

        float cx = _width / 2f;
        float cy = _height / 2f;

        // Build rotation matrix
        float cosX = MathF.Cos(_rotationX);
        float sinX = MathF.Sin(_rotationX);
        float cosY = MathF.Cos(_rotationY);
        float sinY = MathF.Sin(_rotationY);

        // Transform all vertices
        int numVerts = _meshData.VertexCount;
        var projectedX = new float[numVerts];
        var projectedY = new float[numVerts];
        var projectedZ = new float[numVerts];

        // Use orthographic projection
        // Model is normalized to [-1,1] range (diameter 2), so after rotation worst case is sqrt(3)*2 ≈ 3.46
        // To fit in screen, we need: viewScale * 3.46 < min(width,height) / 2
        // So viewScale < min(width,height) / 6.92 ≈ 0.144, but we want the model to fill more of the screen
        // Using 0.4 gives a good visible size while staying in bounds
        float viewScale = Math.Min(_width, _height) * 0.4f * _zoom;

        for (int i = 0; i < numVerts; i++)
        {
            // Center the model at origin
            float x = _meshData.CurrentPositions[i * 3 + 0] - _modelCenter.X;
            float y = _meshData.CurrentPositions[i * 3 + 1] - _modelCenter.Y;
            float z = _meshData.CurrentPositions[i * 3 + 2] - _modelCenter.Z;

            // Normalize to unit size
            x *= _modelScale;
            y *= _modelScale;
            z *= _modelScale;

            // Apply rotation (Y axis first, then X axis)
            float rx = x * cosY - z * sinY;
            float rz = x * sinY + z * cosY;
            x = rx; z = rz;

            float ry = y * cosX - z * sinX;
            rz = y * sinX + z * cosX;
            y = ry; z = rz;

            // Scale to screen
            x *= viewScale;
            y *= viewScale;
            z *= viewScale;

            // Apply pan
            x += _panOffset.X;
            y += _panOffset.Y;

            // Orthographic projection (much simpler and more reliable)
            projectedX[i] = cx + x;
            projectedY[i] = cy - y; // Flip Y for screen coordinates
            projectedZ[i] = z; // Use z for depth buffer (negative = closer)
        }

        // Draw solid triangles with Z-buffer and lighting
        if (ShowSolid && _meshData.Indices.Length > 0)
        {
            DrawSolidTriangles(pixels, projectedX, projectedY, projectedZ);
        }

        // Draw section caps (cut surfaces)
        if (_showClipCap && (_clipXEnabled || _clipYEnabled || _clipZEnabled))
        {
            DrawSectionCaps(pixels, projectedX, projectedY, projectedZ);
        }

        // Draw wireframe
        if (ShowWireframe && _meshData.WireframeIndices.Length > 0)
        {
            uint wireColor = 0xFF00FF00; // Green
            for (int i = 0; i < _meshData.WireframeIndices.Length; i += 2)
            {
                int i0 = (int)_meshData.WireframeIndices[i];
                int i1 = (int)_meshData.WireframeIndices[i + 1];
                if (i0 < numVerts && i1 < numVerts)
                {
                    DrawLine(pixels, (int)projectedX[i0], (int)projectedY[i0],
                             (int)projectedX[i1], (int)projectedY[i1], wireColor);
                }
            }
        }
    }

    private void DrawSolidTriangles(uint[] pixels, float[] px, float[] py, float[] pz)
    {
        if (_meshData == null) return;

        // Multiple light directions for better visibility
        var lightDir1 = Vector3.Normalize(new Vector3(0.5f, 1.0f, 0.8f));   // Main light (top-right-front)
        var lightDir2 = Vector3.Normalize(new Vector3(-0.5f, -0.3f, -0.8f)); // Fill light (opposite side)
        var lightDir3 = Vector3.Normalize(new Vector3(0.0f, 0.0f, 1.0f));    // Front light (camera direction)

        int drawnCount = 0;
        // Draw all triangles - Z-buffer handles occlusion
        int maxTris = _meshData.Indices.Length;
        for (int t = 0; t < maxTris; t += 3)
        {
            int i0 = (int)_meshData.Indices[t + 0];
            int i1 = (int)_meshData.Indices[t + 1];
            int i2 = (int)_meshData.Indices[t + 2];

            if (i0 >= px.Length || i1 >= px.Length || i2 >= px.Length)
                continue;

            // Clipping test - check if all vertices are clipped
            bool v0Clipped = IsVertexClipped(i0);
            bool v1Clipped = IsVertexClipped(i1);
            bool v2Clipped = IsVertexClipped(i2);

            // If all vertices are clipped, skip this triangle
            if (v0Clipped && v1Clipped && v2Clipped)
                continue;

            // Screen coordinates
            float x0 = px[i0], y0 = py[i0], z0 = pz[i0];
            float x1 = px[i1], y1 = py[i1], z1 = pz[i1];
            float x2 = px[i2], y2 = py[i2], z2 = pz[i2];

            // Backface culling
            float cross = (x1 - x0) * (y2 - y0) - (y1 - y0) * (x2 - x0);
            // Disable backface culling for now - faces may have wrong winding
            // if (cross < 0) continue; // Cull backfaces

            // Compute face normal for lighting
            Vector3 edge1 = new Vector3(
                _meshData.CurrentPositions[i1 * 3 + 0] - _meshData.CurrentPositions[i0 * 3 + 0],
                _meshData.CurrentPositions[i1 * 3 + 1] - _meshData.CurrentPositions[i0 * 3 + 1],
                _meshData.CurrentPositions[i1 * 3 + 2] - _meshData.CurrentPositions[i0 * 3 + 2]);
            Vector3 edge2 = new Vector3(
                _meshData.CurrentPositions[i2 * 3 + 0] - _meshData.CurrentPositions[i0 * 3 + 0],
                _meshData.CurrentPositions[i2 * 3 + 1] - _meshData.CurrentPositions[i0 * 3 + 1],
                _meshData.CurrentPositions[i2 * 3 + 2] - _meshData.CurrentPositions[i0 * 3 + 2]);
            var normal = Vector3.Normalize(Vector3.Cross(edge1, edge2));

            // Multi-directional lighting for better face distinction
            float diffuse1 = Math.Max(0, Vector3.Dot(normal, lightDir1));  // Main light
            float diffuse2 = Math.Max(0, Vector3.Dot(normal, lightDir2));  // Fill light (weaker)
            float diffuse3 = Math.Abs(Vector3.Dot(normal, lightDir3));     // Front light (both sides)

            float ambient = 0.15f;
            float lighting = ambient + diffuse1 * 0.5f + diffuse2 * 0.2f + diffuse3 * 0.15f;
            lighting = Math.Clamp(lighting, 0.1f, 1.0f);

            // Get color from scalar values (jet colormap)
            uint baseColor = GetJetColor(i0);

            // Apply lighting to color
            uint color = ApplyLighting(baseColor, lighting);

            // Rasterize triangle
            FillTriangle(pixels, x0, y0, z0, x1, y1, z1, x2, y2, z2, color);
            drawnCount++;

            // Debug first triangle (log once when mesh first loads)
            if (t == 0 && _logFirstTriOnce)
            {
                Log($"First tri: ({x0:F0},{y0:F0}) ({x1:F0},{y1:F0}) ({x2:F0},{y2:F0})");
                Log($"BBox: x[{Math.Min(x0, Math.Min(x1, x2)):F0}-{Math.Max(x0, Math.Max(x1, x2)):F0}] y[{Math.Min(y0, Math.Min(y1, y2)):F0}-{Math.Max(y0, Math.Max(y1, y2)):F0}]");
                _logFirstTriOnce = false;
            }
        }

        // Log triangle count once
        if (drawnCount > 0 && _logTriCountOnce)
        {
            Log($"Drawing {drawnCount} triangles per frame");
            _logTriCountOnce = false;
        }
    }

    private uint GetJetColor(int vertexIndex)
    {
        if (_meshData == null || _meshData.ScalarValues.Length == 0)
            return 0xFF8090A0; // Default gray-blue for solid appearance

        float scalar = _meshData.ScalarValues[vertexIndex];
        float range = _meshData.ScalarMax - _meshData.ScalarMin;
        float t = range > 0 ? (scalar - _meshData.ScalarMin) / range : 0.5f;
        t = Math.Clamp(t, 0f, 1f);

        // Jet colormap: blue -> cyan -> green -> yellow -> red
        float r, g, b;
        if (t < 0.25f)
        {
            float s = t / 0.25f;
            r = 0; g = s; b = 1;
        }
        else if (t < 0.5f)
        {
            float s = (t - 0.25f) / 0.25f;
            r = 0; g = 1; b = 1 - s;
        }
        else if (t < 0.75f)
        {
            float s = (t - 0.5f) / 0.25f;
            r = s; g = 1; b = 0;
        }
        else
        {
            float s = (t - 0.75f) / 0.25f;
            r = 1; g = 1 - s; b = 0;
        }

        return 0xFF000000 | ((uint)(b * 255) << 16) | ((uint)(g * 255) << 8) | (uint)(r * 255);
    }

    private uint ApplyLighting(uint color, float lighting)
    {
        byte r = (byte)(color & 0xFF);
        byte g = (byte)((color >> 8) & 0xFF);
        byte b = (byte)((color >> 16) & 0xFF);

        r = (byte)Math.Clamp((int)(r * lighting), 0, 255);
        g = (byte)Math.Clamp((int)(g * lighting), 0, 255);
        b = (byte)Math.Clamp((int)(b * lighting), 0, 255);

        return 0xFF000000 | ((uint)b << 16) | ((uint)g << 8) | r;
    }

    private int _spinnerFrame = 0;
    private void DrawLoadingIndicator(uint[] pixels)
    {
        int cx = _width / 2;
        int cy = _height / 2;

        // Draw semi-transparent background box
        int boxW = 200;
        int boxH = 60;
        int boxX = cx - boxW / 2;
        int boxY = cy - boxH / 2;

        for (int y = Math.Max(0, boxY); y < Math.Min(_height, boxY + boxH); y++)
        {
            for (int x = Math.Max(0, boxX); x < Math.Min(_width, boxX + boxW); x++)
            {
                int idx = y * _width + x;
                // Darken existing pixel
                uint existing = pixels[idx];
                byte er = (byte)((existing >> 0) & 0xFF);
                byte eg = (byte)((existing >> 8) & 0xFF);
                byte eb = (byte)((existing >> 16) & 0xFF);
                er = (byte)(er / 2);
                eg = (byte)(eg / 2);
                eb = (byte)(eb / 2);
                pixels[idx] = 0xFF000000 | ((uint)eb << 16) | ((uint)eg << 8) | er;
            }
        }

        // Draw animated spinner (rotating dots)
        _spinnerFrame++;
        int numDots = 8;
        int radius = 15;
        float phase = _spinnerFrame * 0.15f;

        for (int i = 0; i < numDots; i++)
        {
            float angle = phase + (i * MathF.PI * 2 / numDots);
            int dotX = cx + (int)(MathF.Cos(angle) * radius);
            int dotY = cy + (int)(MathF.Sin(angle) * radius);

            // Fade based on position
            byte brightness = (byte)(255 - (i * 255 / numDots));
            uint dotColor = 0xFF000000 | ((uint)brightness << 16) | ((uint)brightness << 8) | brightness;

            // Draw dot (3x3)
            for (int dy = -1; dy <= 1; dy++)
            {
                for (int dx = -1; dx <= 1; dx++)
                {
                    int px = dotX + dx;
                    int py = dotY + dy;
                    if (px >= 0 && px < _width && py >= 0 && py < _height)
                    {
                        pixels[py * _width + px] = dotColor;
                    }
                }
            }
        }

        // Draw status text as simple indicator below spinner
        string status = _isLoading ? "Loading..." : _loadingStatus;
        if (!string.IsNullOrEmpty(status))
        {
            // Simple text indicator - just draw a line of dots for now
            int textY = cy + 25;
            uint textColor = 0xFFAAFFAA;
            for (int i = 0; i < Math.Min(status.Length, 20); i++)
            {
                int px = cx - 50 + i * 5;
                if (px >= 0 && px < _width && textY >= 0 && textY < _height)
                {
                    pixels[textY * _width + px] = textColor;
                }
            }
        }
    }

    private static int _fillDebugCounter = 0;
    private void FillTriangle(uint[] pixels, float x0, float y0, float z0,
                              float x1, float y1, float z1,
                              float x2, float y2, float z2, uint color)
    {
        // Bounding box (use ceiling for max to ensure we cover all pixels)
        int minX = Math.Max(0, (int)MathF.Floor(Math.Min(x0, Math.Min(x1, x2))));
        int maxX = Math.Min(_width - 1, (int)MathF.Ceiling(Math.Max(x0, Math.Max(x1, x2))));
        int minY = Math.Max(0, (int)MathF.Floor(Math.Min(y0, Math.Min(y1, y2))));
        int maxY = Math.Min(_height - 1, (int)MathF.Ceiling(Math.Max(y0, Math.Max(y1, y2))));

        // Skip if triangle is completely off-screen
        if (minX > maxX || minY > maxY) return;

        // Compute twice the signed area of the triangle
        float area2 = (x1 - x0) * (y2 - y0) - (y1 - y0) * (x2 - x0);
        if (MathF.Abs(area2) < 0.001f) return; // Degenerate triangle

        float invArea2 = 1.0f / area2;

        int pixelsDrawn = 0;
        for (int py = minY; py <= maxY; py++)
        {
            for (int px = minX; px <= maxX; px++)
            {
                float cx = px + 0.5f;
                float cy = py + 0.5f;

                // Barycentric coordinates using cross products
                // w0 = area of triangle (p, v1, v2) / area of triangle (v0, v1, v2)
                float w0 = ((x1 - cx) * (y2 - cy) - (y1 - cy) * (x2 - cx)) * invArea2;
                float w1 = ((x2 - cx) * (y0 - cy) - (y2 - cy) * (x0 - cx)) * invArea2;
                float w2 = 1.0f - w0 - w1;

                // Point is inside if all barycentric coords are >= 0 (with small epsilon for edge cases)
                const float eps = -0.001f;
                if (w0 >= eps && w1 >= eps && w2 >= eps)
                {
                    // Interpolate Z
                    float z = w0 * z0 + w1 * z1 + w2 * z2;

                    int idx = py * _width + px;
                    if (z < _zBuffer[idx])
                    {
                        _zBuffer[idx] = z;
                        pixels[idx] = color;
                        pixelsDrawn++;
                    }
                }
            }
        }

        // Debug: log first few triangles
        if (_fillDebugCounter < 3 && pixelsDrawn > 0)
        {
            Log($"FillTri: {pixelsDrawn} px, bbox=[{minX}-{maxX}]x[{minY}-{maxY}], area={area2:F1}");
            _fillDebugCounter++;
        }
        // Log if no pixels drawn for first triangle
        if (_logFillTriOnce && pixelsDrawn == 0)
        {
            Log($"FillTri: 0 px! bbox=[{minX}-{maxX}]x[{minY}-{maxY}], area={area2:F1}");
            _logFillTriOnce = false;
        }
    }

    private void DrawWireframeCube(uint[] pixels)
    {
        float size = 100 * _zoom;
        float cx = _width / 2f;
        float cy = _height / 2f;

        float[,] vertices = new float[8, 3]
        {
            { -1, -1, -1 }, { 1, -1, -1 }, { 1, 1, -1 }, { -1, 1, -1 },
            { -1, -1, 1 }, { 1, -1, 1 }, { 1, 1, 1 }, { -1, 1, 1 }
        };

        int[,] edges = new int[12, 2]
        {
            { 0, 1 }, { 1, 2 }, { 2, 3 }, { 3, 0 },
            { 4, 5 }, { 5, 6 }, { 6, 7 }, { 7, 4 },
            { 0, 4 }, { 1, 5 }, { 2, 6 }, { 3, 7 }
        };

        float[] projX = new float[8];
        float[] projY = new float[8];

        float cosX = MathF.Cos(_rotationX);
        float sinX = MathF.Sin(_rotationX);
        float cosY = MathF.Cos(_rotationY);
        float sinY = MathF.Sin(_rotationY);

        for (int i = 0; i < 8; i++)
        {
            float x = vertices[i, 0] * size;
            float y = vertices[i, 1] * size;
            float z = vertices[i, 2] * size;

            float rx = x * cosY - z * sinY;
            float rz = x * sinY + z * cosY;
            x = rx; z = rz;

            float ry = y * cosX - z * sinX;
            rz = y * sinX + z * cosX;
            y = ry; z = rz;

            float perspective = 500f / (500f + z);
            projX[i] = cx + x * perspective;
            projY[i] = cy + y * perspective;
        }

        uint lineColor = 0xFF00FF00;
        for (int i = 0; i < 12; i++)
        {
            int v0 = edges[i, 0];
            int v1 = edges[i, 1];
            DrawLine(pixels, (int)projX[v0], (int)projY[v0], (int)projX[v1], (int)projY[v1], lineColor);
        }
    }

    private void DrawGrid(uint[] pixels)
    {
        uint gridColor = 0xFF3F3F3F;
        int cx = _width / 2;
        int cy = _height / 2;
        int gridSize = 200;
        int step = 20;

        for (int y = cy - gridSize; y <= cy + gridSize; y += step)
        {
            if (y >= 0 && y < _height)
            {
                for (int x = Math.Max(0, cx - gridSize); x < Math.Min(_width, cx + gridSize); x++)
                {
                    pixels[y * _width + x] = gridColor;
                }
            }
        }

        for (int x = cx - gridSize; x <= cx + gridSize; x += step)
        {
            if (x >= 0 && x < _width)
            {
                for (int y = Math.Max(0, cy - gridSize); y < Math.Min(_height, cy + gridSize); y++)
                {
                    pixels[y * _width + x] = gridColor;
                }
            }
        }
    }

    private void DrawAxes(uint[] pixels)
    {
        int cx = _width / 2;
        int cy = _height / 2;
        DrawLine(pixels, cx, cy, cx + 50, cy, 0xFFFF0000); // X - Red
        DrawLine(pixels, cx, cy, cx, cy - 50, 0xFF00FF00); // Y - Green
    }

    private void DrawLine(uint[] pixels, int x0, int y0, int x1, int y1, uint color)
    {
        int dx = Math.Abs(x1 - x0);
        int dy = Math.Abs(y1 - y0);
        int sx = x0 < x1 ? 1 : -1;
        int sy = y0 < y1 ? 1 : -1;
        int err = dx - dy;

        while (true)
        {
            if (x0 >= 0 && x0 < _width && y0 >= 0 && y0 < _height)
            {
                pixels[y0 * _width + x0] = color;
            }

            if (x0 == x1 && y0 == y1) break;

            int e2 = 2 * err;
            if (e2 > -dy) { err -= dy; x0 += sx; }
            if (e2 < dx) { err += dx; y0 += sy; }
        }
    }

    protected override void OnPointerPressed(PointerPressedEventArgs e)
    {
        base.OnPointerPressed(e);
        _lastMousePos = e.GetPosition(this);
        var props = e.GetCurrentPoint(this).Properties;
        _isRotating = props.IsLeftButtonPressed;
        _isPanning = props.IsMiddleButtonPressed || props.IsRightButtonPressed;
        Console.WriteLine($"[Mouse] Pressed: rotating={_isRotating}, panning={_isPanning}");
        e.Handled = true;
        Focus();
    }

    protected override void OnPointerReleased(PointerReleasedEventArgs e)
    {
        base.OnPointerReleased(e);
        _isRotating = false;
        _isPanning = false;
    }

    protected override void OnPointerMoved(PointerEventArgs e)
    {
        base.OnPointerMoved(e);

        var pos = e.GetPosition(this);
        var delta = pos - _lastMousePos;
        _lastMousePos = pos;

        if (_isRotating)
        {
            _rotationY += (float)delta.X * 0.01f;
            _rotationX += (float)delta.Y * 0.01f;
            if (Math.Abs(delta.X) > 1 || Math.Abs(delta.Y) > 1)
                Console.WriteLine($"[Mouse] Rotating: rotX={_rotationX:F2}, rotY={_rotationY:F2}");
        }
        else if (_isPanning)
        {
            _panOffset.X += (float)delta.X;
            _panOffset.Y -= (float)delta.Y;
        }
    }

    protected override void OnPointerWheelChanged(PointerWheelEventArgs e)
    {
        base.OnPointerWheelChanged(e);
        _zoom *= e.Delta.Y > 0 ? 1.1f : 0.9f;
        _zoom = Math.Clamp(_zoom, 0.1f, 10f);
    }

    protected override void OnSizeChanged(SizeChangedEventArgs e)
    {
        base.OnSizeChanged(e);

        if (e.NewSize.Width > 0 && e.NewSize.Height > 0)
        {
            _width = (int)e.NewSize.Width;
            _height = (int)e.NewSize.Height;

            _renderBitmap = new WriteableBitmap(
                new PixelSize(_width, _height),
                new Avalonia.Vector(96, 96),
                Avalonia.Platform.PixelFormat.Bgra8888,
                AlphaFormat.Premul);

            _zBuffer = new float[_width * _height];

            if (_imageControl != null)
            {
                _imageControl.Source = _renderBitmap;
            }

            // Resize GPU framebuffer
            _gpuRenderer?.Resize(_width, _height);
        }
    }

    public void SetMeshData(MeshRenderData data)
    {
        _meshData = data;
        if (_meshData.CurrentPositions.Length > 0)
        {
            _meshData.ComputeBounds();
            _modelCenter = (_meshData.BoundsMin + _meshData.BoundsMax) * 0.5f;
            var size = _meshData.BoundsMax - _meshData.BoundsMin;
            _modelScale = 200.0f / Math.Max(Math.Max(size.X, size.Y), size.Z);
        }
    }

    public void UpdateTimestep(int timestep)
    {
        // This will be called from ViewModel when timestep changes
    }

    public void ResetView()
    {
        _rotationX = 0;
        _rotationY = 0;
        _zoom = 1.0f;
        _panOffset = Vector3.Zero;
    }

    /// <summary>
    /// Generate and upload section cap meshes for active clip planes
    /// </summary>
    private void UploadSectionCaps()
    {
        if (_gpuRenderer == null || _meshData == null || _originalMesh == null) return;

        // Call the actual section cap builder
        BuildAndUploadSectionCaps(_originalMesh, _meshData);
    }

    /// <summary>
    /// Helper to build and upload section cap for all enabled clip planes
    /// </summary>
    private void BuildAndUploadSectionCaps(MeshData mesh, MeshRenderData renderData)
    {
        if (_gpuRenderer == null) return;

        var allCapVertices = new List<GpuMeshRenderer.VertexPositionNormalColor>();
        var allCapIndices = new List<uint>();
        uint indexOffset = 0;

        // Generate caps for each enabled clip plane
        if (_gpuRenderer.ClipXEnabled)
        {
            var (verts, scalars, indices) = CreateSectionCapMesh(
                mesh, renderData, 'X', _gpuRenderer.ClipXValue, _gpuRenderer.ClipXInvert);

            AddCapMeshToBuffers(verts, scalars, indices, allCapVertices, allCapIndices, ref indexOffset);
        }

        if (_gpuRenderer.ClipYEnabled)
        {
            var (verts, scalars, indices) = CreateSectionCapMesh(
                mesh, renderData, 'Y', _gpuRenderer.ClipYValue, _gpuRenderer.ClipYInvert);

            AddCapMeshToBuffers(verts, scalars, indices, allCapVertices, allCapIndices, ref indexOffset);
        }

        if (_gpuRenderer.ClipZEnabled)
        {
            var (verts, scalars, indices) = CreateSectionCapMesh(
                mesh, renderData, 'Z', _gpuRenderer.ClipZValue, _gpuRenderer.ClipZInvert);

            AddCapMeshToBuffers(verts, scalars, indices, allCapVertices, allCapIndices, ref indexOffset);
        }

        // Upload to GPU
        if (allCapVertices.Count > 0)
        {
            _gpuRenderer.UploadSectionCap(allCapVertices.ToArray(), allCapIndices.ToArray());
            Log($"Section caps: {allCapVertices.Count} verts, {allCapIndices.Count / 3} tris");
        }
    }

    /// <summary>
    /// Convert cap mesh data to GPU vertex format and add to buffers
    /// </summary>
    private void AddCapMeshToBuffers(
        List<Vector3> vertices, List<float> scalars, List<uint> indices,
        List<GpuMeshRenderer.VertexPositionNormalColor> allVertices,
        List<uint> allIndices, ref uint indexOffset)
    {
        for (int i = 0; i < indices.Count; i += 3)
        {
            uint i0 = indices[i + 0];
            uint i1 = indices[i + 1];
            uint i2 = indices[i + 2];

            Vector3 p0 = vertices[(int)i0];
            Vector3 p1 = vertices[(int)i1];
            Vector3 p2 = vertices[(int)i2];

            // Compute face normal
            Vector3 edge1 = p1 - p0;
            Vector3 edge2 = p2 - p0;
            Vector3 normal = Vector3.Normalize(Vector3.Cross(edge1, edge2));
            if (float.IsNaN(normal.X)) normal = Vector3.UnitZ;

            // Get colors from scalars
            float s0 = scalars[(int)i0];
            float s1 = scalars[(int)i1];
            float s2 = scalars[(int)i2];

            // Normalize scalar values to 0-1 for colormap
            float range = _meshData!.ScalarMax - _meshData.ScalarMin;
            float t0 = range > 0 ? (s0 - _meshData.ScalarMin) / range : 0.5f;
            float t1 = range > 0 ? (s1 - _meshData.ScalarMin) / range : 0.5f;
            float t2 = range > 0 ? (s2 - _meshData.ScalarMin) / range : 0.5f;

            Vector4 c0 = GetJetColorVecFromNormalizedScalar(t0);
            Vector4 c1 = GetJetColorVecFromNormalizedScalar(t1);
            Vector4 c2 = GetJetColorVecFromNormalizedScalar(t2);

            allVertices.Add(new GpuMeshRenderer.VertexPositionNormalColor
            {
                Position = p0,
                Normal = normal,
                Color = c0
            });
            allVertices.Add(new GpuMeshRenderer.VertexPositionNormalColor
            {
                Position = p1,
                Normal = normal,
                Color = c1
            });
            allVertices.Add(new GpuMeshRenderer.VertexPositionNormalColor
            {
                Position = p2,
                Normal = normal,
                Color = c2
            });

            allIndices.Add(indexOffset++);
            allIndices.Add(indexOffset++);
            allIndices.Add(indexOffset++);
        }
    }

    /// <summary>
    /// Get Jet colormap color from normalized scalar (0-1)
    /// </summary>
    private static Vector4 GetJetColorVecFromNormalizedScalar(float t)
    {
        t = Math.Clamp(t, 0f, 1f);

        float r, g, b;
        if (t < 0.25f) { float s = t / 0.25f; r = 0; g = s; b = 1; }
        else if (t < 0.5f) { float s = (t - 0.25f) / 0.25f; r = 0; g = 1; b = 1 - s; }
        else if (t < 0.75f) { float s = (t - 0.5f) / 0.25f; r = s; g = 1; b = 0; }
        else { float s = (t - 0.75f) / 0.25f; r = 1; g = 1 - s; b = 0; }

        return new Vector4(r, g, b, 1.0f);
    }

    private void DrawSectionCaps(uint[] pixels, float[] px, float[] py, float[] pz)
    {
        if (_meshData == null) return;

        // Collect all intersection segments with scalar values
        List<(Vector3 pos1, float scalar1, Vector3 pos2, float scalar2)> segments = new List<(Vector3, float, Vector3, float)>();

        // Process all triangles to find intersection segments
        for (int t = 0; t < _meshData.Indices.Length; t += 3)
        {
            int i0 = (int)_meshData.Indices[t + 0];
            int i1 = (int)_meshData.Indices[t + 1];
            int i2 = (int)_meshData.Indices[t + 2];

            if (i0 >= _meshData.CurrentPositions.Length / 3 ||
                i1 >= _meshData.CurrentPositions.Length / 3 ||
                i2 >= _meshData.CurrentPositions.Length / 3)
                continue;

            // Get world positions
            Vector3 p0 = new Vector3(
                _meshData.CurrentPositions[i0 * 3 + 0],
                _meshData.CurrentPositions[i0 * 3 + 1],
                _meshData.CurrentPositions[i0 * 3 + 2]);
            Vector3 p1 = new Vector3(
                _meshData.CurrentPositions[i1 * 3 + 0],
                _meshData.CurrentPositions[i1 * 3 + 1],
                _meshData.CurrentPositions[i1 * 3 + 2]);
            Vector3 p2 = new Vector3(
                _meshData.CurrentPositions[i2 * 3 + 0],
                _meshData.CurrentPositions[i2 * 3 + 1],
                _meshData.CurrentPositions[i2 * 3 + 2]);

            // Get scalar values for color mapping
            float s0 = _meshData.ScalarValues[i0];
            float s1 = _meshData.ScalarValues[i1];
            float s2 = _meshData.ScalarValues[i2];

            // Check which vertices are clipped
            bool v0Clipped = IsVertexClipped(i0);
            bool v1Clipped = IsVertexClipped(i1);
            bool v2Clipped = IsVertexClipped(i2);

            // Count clipped vertices
            int clippedCount = (v0Clipped ? 1 : 0) + (v1Clipped ? 1 : 0) + (v2Clipped ? 1 : 0);

            // We only care about partially clipped triangles (1 or 2 vertices clipped)
            if (clippedCount == 0 || clippedCount == 3)
                continue;

            // Find the two intersection points on the clip plane with interpolated scalars
            List<(Vector3 pos, float scalar)> intersections = new List<(Vector3, float)>();

            // Check edge p0-p1
            var int01 = GetClipPlaneIntersectionWithScalar(p0, s0, p1, s1);
            if (int01.HasValue) intersections.Add(int01.Value);

            // Check edge p1-p2
            var int12 = GetClipPlaneIntersectionWithScalar(p1, s1, p2, s2);
            if (int12.HasValue) intersections.Add(int12.Value);

            // Check edge p2-p0
            var int20 = GetClipPlaneIntersectionWithScalar(p2, s2, p0, s0);
            if (int20.HasValue) intersections.Add(int20.Value);

            // If we found exactly 2 intersections, add this segment
            if (intersections.Count == 2)
            {
                segments.Add((intersections[0].pos, intersections[0].scalar,
                             intersections[1].pos, intersections[1].scalar));
            }
        }

        // Now draw all the collected segments as filled polygons with color mapping
        if (segments.Count > 0)
        {
            // Try to fill the interior by creating triangles from segment center
            if (segments.Count >= 3)
            {
                // Calculate center point and average scalar value
                Vector3 centerPos = Vector3.Zero;
                float centerScalar = 0;
                int pointCount = 0;
                foreach (var seg in segments)
                {
                    centerPos += seg.pos1;
                    centerPos += seg.pos2;
                    centerScalar += seg.scalar1;
                    centerScalar += seg.scalar2;
                    pointCount += 2;
                }
                centerPos /= pointCount;
                centerScalar /= pointCount;

                // Draw triangles from center to each segment with interpolated colors
                foreach (var seg in segments)
                {
                    var s1 = ProjectPoint(seg.pos1, px, py, pz);
                    var s2 = ProjectPoint(seg.pos2, px, py, pz);
                    var sc = ProjectPoint(centerPos, px, py, pz);

                    // Get colors from scalar values
                    uint c1 = GetJetColorFromScalar(seg.scalar1);
                    uint c2 = GetJetColorFromScalar(seg.scalar2);
                    uint cc = GetJetColorFromScalar(centerScalar);

                    // Fill triangle with per-vertex colors
                    FillTriangleWithColors(pixels, s1.X, s1.Y, s1.Z, c1,
                                                    s2.X, s2.Y, s2.Z, c2,
                                                    sc.X, sc.Y, sc.Z, cc);
                }
            }
        }
    }

    private Vector3? GetClipPlaneIntersection(Vector3 p0, Vector3 p1)
    {
        if (_meshData == null) return null;

        var boundsMin = _gpuRenderer?.ModelBoundsMin ?? Vector3.Zero;
        var boundsMax = _gpuRenderer?.ModelBoundsMax ?? new Vector3(1, 1, 1);
        var boundsSize = boundsMax - boundsMin;

        // Check X clip plane
        if (_clipXEnabled)
        {
            float clipPosX = boundsMin.X + _clipXValue * boundsSize.X;

            // Check if edge crosses the clip plane
            bool p0Side = _clipXInvert ? (p0.X > clipPosX) : (p0.X < clipPosX);
            bool p1Side = _clipXInvert ? (p1.X > clipPosX) : (p1.X < clipPosX);

            // If points are on opposite sides, find intersection
            if (p0Side != p1Side)
            {
                float denom = p1.X - p0.X;
                if (MathF.Abs(denom) > 0.0001f)
                {
                    float t = (clipPosX - p0.X) / denom;
                    if (t >= 0 && t <= 1)
                    {
                        return p0 + t * (p1 - p0);
                    }
                }
            }
        }

        // Check Y clip plane
        if (_clipYEnabled)
        {
            float clipPosY = boundsMin.Y + _clipYValue * boundsSize.Y;

            bool p0Side = _clipYInvert ? (p0.Y > clipPosY) : (p0.Y < clipPosY);
            bool p1Side = _clipYInvert ? (p1.Y > clipPosY) : (p1.Y < clipPosY);

            if (p0Side != p1Side)
            {
                float denom = p1.Y - p0.Y;
                if (MathF.Abs(denom) > 0.0001f)
                {
                    float t = (clipPosY - p0.Y) / denom;
                    if (t >= 0 && t <= 1)
                    {
                        return p0 + t * (p1 - p0);
                    }
                }
            }
        }

        // Check Z clip plane
        if (_clipZEnabled)
        {
            float clipPosZ = boundsMin.Z + _clipZValue * boundsSize.Z;

            bool p0Side = _clipZInvert ? (p0.Z > clipPosZ) : (p0.Z < clipPosZ);
            bool p1Side = _clipZInvert ? (p1.Z > clipPosZ) : (p1.Z < clipPosZ);

            if (p0Side != p1Side)
            {
                float denom = p1.Z - p0.Z;
                if (MathF.Abs(denom) > 0.0001f)
                {
                    float t = (clipPosZ - p0.Z) / denom;
                    if (t >= 0 && t <= 1)
                    {
                        return p0 + t * (p1 - p0);
                    }
                }
            }
        }

        return null;
    }

    private (Vector3 pos, float scalar)? GetClipPlaneIntersectionWithScalar(Vector3 p0, float s0, Vector3 p1, float s1)
    {
        if (_meshData == null) return null;

        var boundsMin = _gpuRenderer?.ModelBoundsMin ?? Vector3.Zero;
        var boundsMax = _gpuRenderer?.ModelBoundsMax ?? new Vector3(1, 1, 1);
        var boundsSize = boundsMax - boundsMin;

        // Check X clip plane
        if (_clipXEnabled)
        {
            float clipPosX = boundsMin.X + _clipXValue * boundsSize.X;

            // Check if edge crosses the clip plane
            bool p0Side = _clipXInvert ? (p0.X > clipPosX) : (p0.X < clipPosX);
            bool p1Side = _clipXInvert ? (p1.X > clipPosX) : (p1.X < clipPosX);

            // If points are on opposite sides, find intersection
            if (p0Side != p1Side)
            {
                float denom = p1.X - p0.X;
                if (MathF.Abs(denom) > 0.0001f)
                {
                    float t = (clipPosX - p0.X) / denom;
                    if (t >= 0 && t <= 1)
                    {
                        Vector3 pos = p0 + t * (p1 - p0);
                        float scalar = s0 + t * (s1 - s0); // Interpolate scalar
                        return (pos, scalar);
                    }
                }
            }
        }

        // Check Y clip plane
        if (_clipYEnabled)
        {
            float clipPosY = boundsMin.Y + _clipYValue * boundsSize.Y;

            bool p0Side = _clipYInvert ? (p0.Y > clipPosY) : (p0.Y < clipPosY);
            bool p1Side = _clipYInvert ? (p1.Y > clipPosY) : (p1.Y < clipPosY);

            if (p0Side != p1Side)
            {
                float denom = p1.Y - p0.Y;
                if (MathF.Abs(denom) > 0.0001f)
                {
                    float t = (clipPosY - p0.Y) / denom;
                    if (t >= 0 && t <= 1)
                    {
                        Vector3 pos = p0 + t * (p1 - p0);
                        float scalar = s0 + t * (s1 - s0);
                        return (pos, scalar);
                    }
                }
            }
        }

        // Check Z clip plane
        if (_clipZEnabled)
        {
            float clipPosZ = boundsMin.Z + _clipZValue * boundsSize.Z;

            bool p0Side = _clipZInvert ? (p0.Z > clipPosZ) : (p0.Z < clipPosZ);
            bool p1Side = _clipZInvert ? (p1.Z > clipPosZ) : (p1.Z < clipPosZ);

            if (p0Side != p1Side)
            {
                float denom = p1.Z - p0.Z;
                if (MathF.Abs(denom) > 0.0001f)
                {
                    float t = (clipPosZ - p0.Z) / denom;
                    if (t >= 0 && t <= 1)
                    {
                        Vector3 pos = p0 + t * (p1 - p0);
                        float scalar = s0 + t * (s1 - s0);
                        return (pos, scalar);
                    }
                }
            }
        }

        return null;
    }

    private uint GetJetColorFromScalar(float scalarValue)
    {
        if (_meshData == null || _meshData.ScalarValues.Length == 0)
            return 0xFF8090A0; // Default gray-blue

        // Normalize scalar to 0-1 range
        float range = _meshData.ScalarMax - _meshData.ScalarMin;
        if (range < 0.0001f) return 0xFF0000FF; // Blue if no range

        float t = (scalarValue - _meshData.ScalarMin) / range;
        t = Math.Clamp(t, 0, 1);

        // Jet colormap
        float r, g, b;
        if (t < 0.25f)
        {
            r = 0;
            g = 4 * t;
            b = 1;
        }
        else if (t < 0.5f)
        {
            r = 0;
            g = 1;
            b = 1 - 4 * (t - 0.25f);
        }
        else if (t < 0.75f)
        {
            r = 4 * (t - 0.5f);
            g = 1;
            b = 0;
        }
        else
        {
            r = 1;
            g = 1 - 4 * (t - 0.75f);
            b = 0;
        }

        // Note: Color format is BGRA (same as GetJetColor)
        return (uint)(0xFF000000 | ((uint)(b * 255) << 16) | ((uint)(g * 255) << 8) | (uint)(r * 255));
    }

    private void FillTriangleWithColors(uint[] pixels,
                                         float x0, float y0, float z0, uint c0,
                                         float x1, float y1, float z1, uint c1,
                                         float x2, float y2, float z2, uint c2)
    {
        // Bounding box
        int minX = Math.Max(0, (int)MathF.Floor(Math.Min(x0, Math.Min(x1, x2))));
        int maxX = Math.Min(_width - 1, (int)MathF.Ceiling(Math.Max(x0, Math.Max(x1, x2))));
        int minY = Math.Max(0, (int)MathF.Floor(Math.Min(y0, Math.Min(y1, y2))));
        int maxY = Math.Min(_height - 1, (int)MathF.Ceiling(Math.Max(y0, Math.Max(y1, y2))));

        if (minX > maxX || minY > maxY) return;

        // Compute twice the signed area
        float area2 = (x1 - x0) * (y2 - y0) - (y1 - y0) * (x2 - x0);
        if (MathF.Abs(area2) < 0.001f) return;

        float invArea2 = 1.0f / area2;

        // Extract color components (BGRA format)
        float b0 = ((c0 >> 16) & 0xFF) / 255f;
        float g0 = ((c0 >> 8) & 0xFF) / 255f;
        float r0 = (c0 & 0xFF) / 255f;

        float b1 = ((c1 >> 16) & 0xFF) / 255f;
        float g1 = ((c1 >> 8) & 0xFF) / 255f;
        float r1 = (c1 & 0xFF) / 255f;

        float b2 = ((c2 >> 16) & 0xFF) / 255f;
        float g2 = ((c2 >> 8) & 0xFF) / 255f;
        float r2 = (c2 & 0xFF) / 255f;

        for (int py = minY; py <= maxY; py++)
        {
            for (int px = minX; px <= maxX; px++)
            {
                float cx = px + 0.5f;
                float cy = py + 0.5f;

                // Barycentric coordinates
                float w0 = ((x1 - cx) * (y2 - cy) - (y1 - cy) * (x2 - cx)) * invArea2;
                float w1 = ((x2 - cx) * (y0 - cy) - (y2 - cy) * (x0 - cx)) * invArea2;
                float w2 = 1.0f - w0 - w1;

                const float eps = -0.001f;
                if (w0 >= eps && w1 >= eps && w2 >= eps)
                {
                    // Interpolate Z
                    float z = w0 * z0 + w1 * z1 + w2 * z2;

                    int idx = py * _width + px;
                    if (z < _zBuffer[idx])
                    {
                        _zBuffer[idx] = z;

                        // Interpolate color
                        float r = w0 * r0 + w1 * r1 + w2 * r2;
                        float g = w0 * g0 + w1 * g1 + w2 * g2;
                        float b = w0 * b0 + w1 * b1 + w2 * b2;

                        byte rb = (byte)(Math.Clamp(r, 0, 1) * 255);
                        byte gb = (byte)(Math.Clamp(g, 0, 1) * 255);
                        byte bb = (byte)(Math.Clamp(b, 0, 1) * 255);

                        // Output in BGRA format
                        pixels[idx] = (uint)(0xFF000000 | (bb << 16) | (gb << 8) | rb);
                    }
                }
            }
        }
    }

    private Vector3 ProjectPoint(Vector3 worldPos, float[] px, float[] py, float[] pz)
    {
        float cx = _width / 2f;
        float cy = _height / 2f;

        // Apply same transformations as in DrawMesh
        float x = worldPos.X - _modelCenter.X;
        float y = worldPos.Y - _modelCenter.Y;
        float z = worldPos.Z - _modelCenter.Z;

        x *= _modelScale;
        y *= _modelScale;
        z *= _modelScale;

        // Apply rotation
        float cosX = MathF.Cos(_rotationX);
        float sinX = MathF.Sin(_rotationX);
        float cosY = MathF.Cos(_rotationY);
        float sinY = MathF.Sin(_rotationY);

        float rx = x * cosY - z * sinY;
        float rz = x * sinY + z * cosY;
        x = rx; z = rz;

        float ry = y * cosX - z * sinX;
        rz = y * sinX + z * cosX;
        y = ry; z = rz;

        // Scale to screen
        float viewScale = Math.Min(_width, _height) * 0.4f * _zoom;
        x *= viewScale;
        y *= viewScale;
        z *= viewScale;

        // Apply pan
        x += _panOffset.X;
        y += _panOffset.Y;

        return new Vector3(cx + x, cy - y, z);
    }

    private void DrawThickLine(uint[] pixels, int x0, int y0, int x1, int y1, uint color, int thickness)
    {
        // Draw multiple parallel lines for thickness
        for (int dy = -thickness; dy <= thickness; dy++)
        {
            for (int dx = -thickness; dx <= thickness; dx++)
            {
                if (dx * dx + dy * dy <= thickness * thickness)
                {
                    DrawLine(pixels, x0 + dx, y0 + dy, x1 + dx, y1 + dy, color);
                }
            }
        }
    }

    private bool IsVertexClipped(int vertexIndex)
    {
        if (_meshData == null) return false;

        float x = _meshData.CurrentPositions[vertexIndex * 3 + 0];
        float y = _meshData.CurrentPositions[vertexIndex * 3 + 1];
        float z = _meshData.CurrentPositions[vertexIndex * 3 + 2];

        // Get model bounds from GPU renderer
        var boundsMin = _gpuRenderer?.ModelBoundsMin ?? Vector3.Zero;
        var boundsMax = _gpuRenderer?.ModelBoundsMax ?? new Vector3(1, 1, 1);
        var boundsSize = boundsMax - boundsMin;

        // Debug log first call (for testing)
        if (vertexIndex == 0 && _clipXEnabled && !_logClipDebug)
        {
            float clipPosX = boundsMin.X + _clipXValue * boundsSize.X;
            Log($"[CLIP-DEBUG] ClipX: value={_clipXValue:F2}, pos={clipPosX:F2}, invert={_clipXInvert}, bounds=[{boundsMin.X:F2}, {boundsMax.X:F2}]");
            _logClipDebug = true;
        }

        // X clip plane
        if (_clipXEnabled)
        {
            float clipPosX = boundsMin.X + _clipXValue * boundsSize.X;
            bool shouldClip = _clipXInvert ? (x > clipPosX) : (x < clipPosX);
            if (shouldClip) return true;
        }

        // Y clip plane
        if (_clipYEnabled)
        {
            float clipPosY = boundsMin.Y + _clipYValue * boundsSize.Y;
            bool shouldClip = _clipYInvert ? (y > clipPosY) : (y < clipPosY);
            if (shouldClip) return true;
        }

        // Z clip plane
        if (_clipZEnabled)
        {
            float clipPosZ = boundsMin.Z + _clipZValue * boundsSize.Z;
            bool shouldClip = _clipZInvert ? (z > clipPosZ) : (z < clipPosZ);
            if (shouldClip) return true;
        }

        return false;
    }
}
