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
    private bool _logTriCountOnce = false;
    private bool _logFillTriOnce = false;

    // Display options
    public bool ShowWireframe { get; set; } = false;
    public bool ShowSolid { get; set; } = true;
    public float DisplacementScale { get; set; } = 1.0f;

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

            // Try GPU rendering first if mesh is uploaded
            if (_useGpuRendering && _gpuRenderer != null && _gpuMeshUploaded && _meshData != null)
            {
                RenderWithGpu(pixels);
            }
            else
            {
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
        _gpuRenderer.Render(wvp, pixels);
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

                        // Reset view
                        _zoom = 1.0f;
                        _panOffset = Vector3.Zero;
                        _rotationX = 0.3f;
                        _rotationY = 0.5f;
                    }

                    _isLoading = false;
                    _loadingStatus = "";

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

        _loadingStatus = "Uploading to GPU...";
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

    public void UpdateStateData(StateData state)
    {
        if (_meshData != null && state.Displacements.Length > 0)
        {
            _meshData.ApplyDisplacement(state.Displacements, DisplacementScale);
            _meshData.ComputeNormals();

            // Update scalar values
            _meshData.ScalarValues = new float[_meshData.VertexCount];
            float minVal = float.MaxValue, maxVal = float.MinValue;

            for (int i = 0; i < _meshData.VertexCount; i++)
            {
                float dx = state.Displacements[i * 3 + 0];
                float dy = state.Displacements[i * 3 + 1];
                float dz = state.Displacements[i * 3 + 2];
                float mag = MathF.Sqrt(dx * dx + dy * dy + dz * dz);
                _meshData.ScalarValues[i] = mag;
                minVal = Math.Min(minVal, mag);
                maxVal = Math.Max(maxVal, mag);
            }

            _meshData.ScalarMin = minVal;
            _meshData.ScalarMax = maxVal;
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
}
