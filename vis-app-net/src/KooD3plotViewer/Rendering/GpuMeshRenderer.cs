using System;
using System.Numerics;
using System.Runtime.InteropServices;
using Veldrid;
using Veldrid.SPIRV;

namespace KooD3plotViewer.Rendering;

/// <summary>
/// GPU-accelerated mesh renderer using Veldrid
/// </summary>
public class GpuMeshRenderer : IDisposable
{
    private GraphicsDevice? _graphicsDevice;
    private CommandList? _commandList;
    private DeviceBuffer? _vertexBuffer;
    private DeviceBuffer? _indexBuffer;
    private DeviceBuffer? _uniformBuffer;
    private Pipeline? _pipeline;
    private ResourceSet? _resourceSet;
    private ResourceLayout? _resourceLayout;
    private Framebuffer? _framebuffer;
    private Texture? _offscreenColor;
    private Texture? _offscreenDepth;
    private Texture? _stagingTexture;

    private int _width = 800;
    private int _height = 600;
    private uint _indexCount;
    private bool _isInitialized;

    private Action<string>? _logCallback;
    private bool _deviceLost = false;
    private int _deviceRecreateAttempts = 0;
    private const int MaxRecreateAttempts = 3;

    // Uniform data
    [StructLayout(LayoutKind.Sequential)]
    private struct UniformData
    {
        public Matrix4x4 WorldViewProjection;
        public Vector4 LightDir1;
        public Vector4 LightDir2;
        public Vector4 LightDir3;
        public Vector4 LightDir4;
        public Vector4 LightDir5;
        public Vector4 LightDir6;
        public Vector4 AmbientColor;
        // Clip planes: xyz = plane normal direction, w = clip position (0-1 normalized)
        public Vector4 ClipPlaneX;  // (enabled, invert, min, max) encoded as (sign, value, 0, 0)
        public Vector4 ClipPlaneY;
        public Vector4 ClipPlaneZ;
        public Vector4 ModelBoundsMin;  // For denormalizing clip values
        public Vector4 ModelBoundsMax;
        // Color mapping: x=useColorMap, y=colorMapType(0-6), z=scaleMin, w=scaleMax
        public Vector4 ColorMapSettings;
    }

    // Clip plane settings (set from outside)
    public bool ClipXEnabled { get; set; }
    public bool ClipYEnabled { get; set; }
    public bool ClipZEnabled { get; set; }
    public float ClipXValue { get; set; } = 0.5f;
    public float ClipYValue { get; set; } = 0.5f;
    public float ClipZValue { get; set; } = 0.5f;
    public bool ClipXInvert { get; set; }
    public bool ClipYInvert { get; set; }
    public bool ClipZInvert { get; set; }
    public bool ShowClipCap { get; set; } = true;
    public Vector3 ModelBoundsMin { get; set; }
    public Vector3 ModelBoundsMax { get; set; }

    // Color mapping settings
    public bool UseColorMap { get; set; } = false;
    public ColorMap.ColorMapType ColorMapType { get; set; } = ColorMap.ColorMapType.Jet;
    public float ColorScaleMin { get; set; } = 0f;
    public float ColorScaleMax { get; set; } = 1000f;

    // Section cap rendering
    private DeviceBuffer? _capVertexBuffer;
    private DeviceBuffer? _capIndexBuffer;
    private uint _capIndexCount;
    private Pipeline? _capPipeline;

    // Debug logging flags
    private bool _loggedClipPlanes = false;

    // Vertex structure
    [StructLayout(LayoutKind.Sequential)]
    public struct VertexPositionNormalColor
    {
        public Vector3 Position;
        public Vector3 Normal;
        public Vector4 Color;

        public const uint SizeInBytes = 40;
    }

    public void SetLogCallback(Action<string> callback) => _logCallback = callback;
    private void Log(string message) => _logCallback?.Invoke(message);

    /// <summary>
    /// Check if GPU device is available and not in lost state
    /// </summary>
    public bool IsDeviceAvailable => _isInitialized && !_deviceLost && _graphicsDevice != null;

    /// <summary>
    /// Returns true if device was lost and cannot be recovered
    /// </summary>
    public bool IsDeviceLost => _deviceLost;

    /// <summary>
    /// Returns true if device was recreated and mesh needs to be re-uploaded
    /// </summary>
    public bool NeedsMeshReupload { get; private set; }

    public bool Initialize(int width, int height)
    {
        try
        {
            _width = width;
            _height = height;

            // Create graphics device (prefer Vulkan, fallback to D3D11)
            var options = new GraphicsDeviceOptions
            {
                PreferStandardClipSpaceYDirection = true,
                PreferDepthRangeZeroToOne = true,
                SyncToVerticalBlank = false,
                Debug = false
            };

            // Try D3D11 first (more stable on Windows), then Vulkan
            try
            {
                _graphicsDevice = GraphicsDevice.CreateD3D11(options);
                Log($"GPU: D3D11 initialized - {_graphicsDevice.DeviceName}");
            }
            catch
            {
                try
                {
                    _graphicsDevice = GraphicsDevice.CreateVulkan(options);
                    Log($"GPU: Vulkan initialized - {_graphicsDevice.DeviceName}");
                }
                catch (Exception ex)
                {
                    Log($"GPU: Both D3D11 and Vulkan failed - {ex.Message}");
                    throw;
                }
            }

            _commandList = _graphicsDevice.ResourceFactory.CreateCommandList();

            CreateOffscreenFramebuffer();
            CreatePipeline();
            CreateUniformBuffer();

            _isInitialized = true;
            Log($"GPU renderer ready: {_width}x{_height}");
            return true;
        }
        catch (Exception ex)
        {
            Log($"GPU init failed: {ex.Message}");
            return false;
        }
    }

    private void CreateOffscreenFramebuffer()
    {
        if (_graphicsDevice == null) return;

        var factory = _graphicsDevice.ResourceFactory;

        // Dispose old resources
        _offscreenColor?.Dispose();
        _offscreenDepth?.Dispose();
        _framebuffer?.Dispose();
        _stagingTexture?.Dispose();

        // Create color texture
        _offscreenColor = factory.CreateTexture(TextureDescription.Texture2D(
            (uint)_width, (uint)_height, 1, 1,
            PixelFormat.B8_G8_R8_A8_UNorm,
            TextureUsage.RenderTarget | TextureUsage.Sampled));

        // Create depth texture
        _offscreenDepth = factory.CreateTexture(TextureDescription.Texture2D(
            (uint)_width, (uint)_height, 1, 1,
            PixelFormat.D32_Float_S8_UInt,
            TextureUsage.DepthStencil));

        // Create framebuffer
        _framebuffer = factory.CreateFramebuffer(new FramebufferDescription(_offscreenDepth, _offscreenColor));

        // Create staging texture for readback
        _stagingTexture = factory.CreateTexture(TextureDescription.Texture2D(
            (uint)_width, (uint)_height, 1, 1,
            PixelFormat.B8_G8_R8_A8_UNorm,
            TextureUsage.Staging));
    }

    private void CreatePipeline()
    {
        if (_graphicsDevice == null)
        {
            Log("[GPU] CreatePipeline: graphicsDevice is null");
            return;
        }

        Log("[GPU] Creating main pipeline...");

        try
        {
            var factory = _graphicsDevice.ResourceFactory;

        // Vertex shader
        string vertexCode = @"
#version 450

layout(location = 0) in vec3 Position;
layout(location = 1) in vec3 Normal;
layout(location = 2) in vec4 Color;

layout(location = 0) out vec3 fsin_Normal;
layout(location = 1) out vec4 fsin_Color;
layout(location = 2) out vec3 fsin_WorldPos;

layout(set = 0, binding = 0) uniform UniformBlock
{
    mat4 WorldViewProjection;
    vec4 LightDir1;
    vec4 LightDir2;
    vec4 LightDir3;
    vec4 LightDir4;
    vec4 LightDir5;
    vec4 LightDir6;
    vec4 AmbientColor;
    vec4 ClipPlaneX;
    vec4 ClipPlaneY;
    vec4 ClipPlaneZ;
    vec4 ModelBoundsMin;
    vec4 ModelBoundsMax;
    vec4 ColorMapSettings;
};

void main()
{
    gl_Position = WorldViewProjection * vec4(Position, 1.0);
    fsin_Normal = Normal;
    fsin_Color = Color;
    fsin_WorldPos = Position;
}
";

        // Fragment shader
        string fragmentCode = @"
#version 450

layout(location = 0) in vec3 fsin_Normal;
layout(location = 1) in vec4 fsin_Color;
layout(location = 2) in vec3 fsin_WorldPos;

layout(location = 0) out vec4 fsout_Color;

layout(set = 0, binding = 0) uniform UniformBlock
{
    mat4 WorldViewProjection;
    vec4 LightDir1;
    vec4 LightDir2;
    vec4 LightDir3;
    vec4 LightDir4;
    vec4 LightDir5;
    vec4 LightDir6;
    vec4 AmbientColor;
    vec4 ClipPlaneX;  // x=enabled, y=invert, z=value, w=unused
    vec4 ClipPlaneY;
    vec4 ClipPlaneZ;
    vec4 ModelBoundsMin;
    vec4 ModelBoundsMax;
    vec4 ColorMapSettings;  // x=useColorMap, y=colorMapType, z=scaleMin, w=scaleMax
};

// Colormap functions
vec3 jet(float t) {
    float r = clamp(1.5 - abs(4.0 * t - 3.0), 0.0, 1.0);
    float g = clamp(1.5 - abs(4.0 * t - 2.0), 0.0, 1.0);
    float b = clamp(1.5 - abs(4.0 * t - 1.0), 0.0, 1.0);
    return vec3(r, g, b);
}

vec3 viridis(float t) {
    vec3 c0 = vec3(0.267, 0.005, 0.329);
    vec3 c1 = vec3(0.127, 0.566, 0.550);
    vec3 c2 = vec3(0.993, 0.906, 0.144);
    return (t < 0.5) ? mix(c0, c1, t * 2.0) : mix(c1, c2, (t - 0.5) * 2.0);
}

vec3 plasma(float t) {
    vec3 c0 = vec3(0.050, 0.030, 0.529);
    vec3 c1 = vec3(0.785, 0.225, 0.497);
    vec3 c2 = vec3(0.940, 0.975, 0.131);
    return (t < 0.5) ? mix(c0, c1, t * 2.0) : mix(c1, c2, (t - 0.5) * 2.0);
}

vec3 turbo(float t) {
    const float r0 = 0.13572138, r1 = 4.61539260, r2 = -42.66032258;
    const float g0 = 0.09140261, g1 = 2.19418839, g2 = 4.84296658;
    const float b0 = 0.10667330, b1 = 12.64194608, b2 = -60.58204836;
    float r = r0 + t * (r1 + t * r2);
    float g = g0 + t * (g1 + t * g2);
    float b = b0 + t * (b1 + t * b2);
    return clamp(vec3(r, g, b), 0.0, 1.0);
}

vec3 rainbow(float t) {
    float h = t * 300.0; // 0 to 300 degrees
    float s = 1.0, v = 1.0;
    float c = v * s;
    float x = c * (1.0 - abs(mod(h / 60.0, 2.0) - 1.0));
    vec3 rgb = (h < 60.0) ? vec3(c, x, 0.0) :
               (h < 120.0) ? vec3(x, c, 0.0) :
               (h < 180.0) ? vec3(0.0, c, x) :
               (h < 240.0) ? vec3(0.0, x, c) : vec3(x, 0.0, c);
    return rgb + (v - c);
}

vec3 cool(float t) {
    return vec3(t, 1.0 - t, 1.0);
}

vec3 hot(float t) {
    return vec3(clamp(t * 3.0, 0.0, 1.0),
                clamp(t * 3.0 - 1.0, 0.0, 1.0),
                clamp(t * 3.0 - 2.0, 0.0, 1.0));
}

vec3 applyColorMap(float value, int colorMapType) {
    if (colorMapType == 0) return jet(value);
    if (colorMapType == 1) return viridis(value);
    if (colorMapType == 2) return plasma(value);
    if (colorMapType == 3) return turbo(value);
    if (colorMapType == 4) return rainbow(value);
    if (colorMapType == 5) return cool(value);
    if (colorMapType == 6) return hot(value);
    return jet(value);
}

void main()
{
    // Clip plane tests
    vec3 boundsSize = ModelBoundsMax.xyz - ModelBoundsMin.xyz;

    // X clip plane
    if (ClipPlaneX.x > 0.5) {
        float clipPosX = ModelBoundsMin.x + ClipPlaneX.z * boundsSize.x;
        bool shouldClip = (ClipPlaneX.y > 0.5) ? (fsin_WorldPos.x > clipPosX) : (fsin_WorldPos.x < clipPosX);
        if (shouldClip) discard;
    }

    // Y clip plane
    if (ClipPlaneY.x > 0.5) {
        float clipPosY = ModelBoundsMin.y + ClipPlaneY.z * boundsSize.y;
        bool shouldClip = (ClipPlaneY.y > 0.5) ? (fsin_WorldPos.y > clipPosY) : (fsin_WorldPos.y < clipPosY);
        if (shouldClip) discard;
    }

    // Z clip plane
    if (ClipPlaneZ.x > 0.5) {
        float clipPosZ = ModelBoundsMin.z + ClipPlaneZ.z * boundsSize.z;
        bool shouldClip = (ClipPlaneZ.y > 0.5) ? (fsin_WorldPos.z > clipPosZ) : (fsin_WorldPos.z < clipPosZ);
        if (shouldClip) discard;
    }

    // Determine final color
    vec3 baseColor;
    if (ColorMapSettings.x > 0.5) {
        // Use colormap: vertex color's alpha channel stores the scalar value (0-1 normalized)
        float scalarValue = fsin_Color.a;
        int colorMapType = int(ColorMapSettings.y);
        baseColor = applyColorMap(scalarValue, colorMapType);
    } else {
        // Use vertex color
        baseColor = fsin_Color.rgb;
    }

    // Apply lighting - 6-directional cube lighting for even illumination
    vec3 normal = normalize(fsin_Normal);
    float diffuse1 = max(0.0, dot(normal, LightDir1.xyz));  // +X
    float diffuse2 = max(0.0, dot(normal, LightDir2.xyz));  // -X
    float diffuse3 = max(0.0, dot(normal, LightDir3.xyz));  // +Y
    float diffuse4 = max(0.0, dot(normal, LightDir4.xyz));  // -Y
    float diffuse5 = max(0.0, dot(normal, LightDir5.xyz));  // +Z
    float diffuse6 = max(0.0, dot(normal, LightDir6.xyz));  // -Z

    // Equal contribution from all 6 directions
    float lighting = AmbientColor.w + (diffuse1 + diffuse2 + diffuse3 + diffuse4 + diffuse5 + diffuse6) * 0.15;
    lighting = clamp(lighting, 0.4, 1.0);

    vec3 litColor = baseColor * lighting;
    fsout_Color = vec4(litColor, 1.0);
}
";

        // Compile shaders
        var vertexShaderDesc = new ShaderDescription(ShaderStages.Vertex,
            System.Text.Encoding.UTF8.GetBytes(vertexCode), "main");
        var fragmentShaderDesc = new ShaderDescription(ShaderStages.Fragment,
            System.Text.Encoding.UTF8.GetBytes(fragmentCode), "main");

        var shaders = factory.CreateFromSpirv(vertexShaderDesc, fragmentShaderDesc);

        // Resource layout
        _resourceLayout = factory.CreateResourceLayout(new ResourceLayoutDescription(
            new ResourceLayoutElementDescription("UniformBlock", ResourceKind.UniformBuffer, ShaderStages.Vertex | ShaderStages.Fragment)));

        // Vertex layout
        var vertexLayout = new VertexLayoutDescription(
            new VertexElementDescription("Position", VertexElementSemantic.TextureCoordinate, VertexElementFormat.Float3),
            new VertexElementDescription("Normal", VertexElementSemantic.TextureCoordinate, VertexElementFormat.Float3),
            new VertexElementDescription("Color", VertexElementSemantic.TextureCoordinate, VertexElementFormat.Float4));

        // Pipeline
        var pipelineDesc = new GraphicsPipelineDescription
        {
            BlendState = BlendStateDescription.SingleOverrideBlend,
            DepthStencilState = new DepthStencilStateDescription(
                depthTestEnabled: true,
                depthWriteEnabled: true,
                comparisonKind: ComparisonKind.LessEqual),
            RasterizerState = new RasterizerStateDescription(
                cullMode: FaceCullMode.None,  // Draw both sides
                fillMode: PolygonFillMode.Solid,
                frontFace: FrontFace.CounterClockwise,
                depthClipEnabled: true,
                scissorTestEnabled: false),
            PrimitiveTopology = PrimitiveTopology.TriangleList,
            ResourceLayouts = new[] { _resourceLayout },
            ShaderSet = new ShaderSetDescription(
                vertexLayouts: new[] { vertexLayout },
                shaders: shaders),
            Outputs = _framebuffer!.OutputDescription
        };

            _pipeline = factory.CreateGraphicsPipeline(pipelineDesc);

            foreach (var shader in shaders)
                shader.Dispose();

            Log("[GPU] Main pipeline created successfully");
        }
        catch (Exception ex)
        {
            Log($"[GPU] Failed to create main pipeline: {ex.Message}");
            Log($"[GPU] Stack trace: {ex.StackTrace}");
            _pipeline = null;
        }
    }

    private void CreateUniformBuffer()
    {
        if (_graphicsDevice == null || _resourceLayout == null) return;

        var factory = _graphicsDevice.ResourceFactory;

        _uniformBuffer = factory.CreateBuffer(new BufferDescription(
            (uint)Marshal.SizeOf<UniformData>(),
            BufferUsage.UniformBuffer | BufferUsage.Dynamic));

        _resourceSet = factory.CreateResourceSet(new ResourceSetDescription(
            _resourceLayout, _uniformBuffer));
    }

    public void UploadMesh(VertexPositionNormalColor[] vertices, uint[] indices)
    {
        if (_graphicsDevice == null) return;

        var factory = _graphicsDevice.ResourceFactory;

        // Dispose old buffers
        _vertexBuffer?.Dispose();
        _indexBuffer?.Dispose();

        // Create vertex buffer
        _vertexBuffer = factory.CreateBuffer(new BufferDescription(
            (uint)(vertices.Length * VertexPositionNormalColor.SizeInBytes),
            BufferUsage.VertexBuffer | BufferUsage.Dynamic));
        _graphicsDevice.UpdateBuffer(_vertexBuffer, 0, vertices);

        // Create index buffer
        _indexBuffer = factory.CreateBuffer(new BufferDescription(
            (uint)(indices.Length * sizeof(uint)),
            BufferUsage.IndexBuffer));
        _graphicsDevice.UpdateBuffer(_indexBuffer, 0, indices);

        _indexCount = (uint)indices.Length;
        NeedsMeshReupload = false;  // Mesh has been uploaded

        Log($"GPU mesh uploaded: {vertices.Length} verts, {indices.Length / 3} tris");
    }

    /// <summary>
    /// Fast update of existing vertex buffer without recreating it (for animation)
    /// </summary>
    public void UpdateVertexData(VertexPositionNormalColor[] vertices)
    {
        if (_graphicsDevice == null || _vertexBuffer == null) return;

        // Only update if vertex count matches existing buffer
        if (vertices.Length * VertexPositionNormalColor.SizeInBytes != _vertexBuffer.SizeInBytes)
        {
            Log($"WARNING: UpdateVertexData size mismatch - falling back to full upload");
            return;
        }

        _graphicsDevice.UpdateBuffer(_vertexBuffer, 0, vertices);
    }

    /// <summary>
    /// Upload section cap mesh for clip plane visualization
    /// </summary>
    public void UploadSectionCap(VertexPositionNormalColor[] vertices, uint[] indices)
    {
        if (_graphicsDevice == null || !ShowClipCap) return;

        var factory = _graphicsDevice.ResourceFactory;

        // Dispose old cap buffers
        _capVertexBuffer?.Dispose();
        _capIndexBuffer?.Dispose();

        if (vertices.Length == 0 || indices.Length == 0)
        {
            _capIndexCount = 0;
            return;
        }

        // Create cap vertex buffer
        _capVertexBuffer = factory.CreateBuffer(new BufferDescription(
            (uint)(vertices.Length * VertexPositionNormalColor.SizeInBytes),
            BufferUsage.VertexBuffer));
        _graphicsDevice.UpdateBuffer(_capVertexBuffer, 0, vertices);

        // Create cap index buffer
        _capIndexBuffer = factory.CreateBuffer(new BufferDescription(
            (uint)(indices.Length * sizeof(uint)),
            BufferUsage.IndexBuffer));
        _graphicsDevice.UpdateBuffer(_capIndexBuffer, 0, indices);

        _capIndexCount = (uint)indices.Length;

        Log($"Section cap uploaded: {vertices.Length} verts, {indices.Length / 3} tris");
    }

    public void Render(Matrix4x4 worldViewProjection, uint[] outputPixels)
    {
        if (_deviceLost)
        {
            Log("[GPU] Device lost - cannot render");
            return;
        }

        if (!_isInitialized || _graphicsDevice == null || _commandList == null ||
            _framebuffer == null || _vertexBuffer == null || _indexBuffer == null ||
            _pipeline == null || _resourceSet == null || _uniformBuffer == null)
            return;

        try
        {
            RenderInternal(worldViewProjection, outputPixels);
        }
        catch (SharpGen.Runtime.SharpGenException ex) when (ex.HResult == unchecked((int)0x887A0005) || // DXGI_ERROR_DEVICE_REMOVED
                                                            ex.HResult == unchecked((int)0x887A0007))   // DXGI_ERROR_DEVICE_RESET
        {
            HandleDeviceLost(ex);
        }
        catch (Exception ex)
        {
            Log($"[GPU] Render error: {ex.Message}");
            if (ex.Message.Contains("DEVICE_REMOVED") || ex.Message.Contains("DEVICE_RESET"))
            {
                HandleDeviceLost(ex);
            }
        }
    }

    private void HandleDeviceLost(Exception ex)
    {
        Log($"[GPU] Device lost detected: {ex.Message}");
        _deviceRecreateAttempts++;

        if (_deviceRecreateAttempts > MaxRecreateAttempts)
        {
            Log($"[GPU] Max recreate attempts ({MaxRecreateAttempts}) exceeded - falling back to software rendering");
            _deviceLost = true;
            return;
        }

        Log($"[GPU] Attempting device recreation (attempt {_deviceRecreateAttempts}/{MaxRecreateAttempts})...");

        try
        {
            // Cleanup old resources
            CleanupGpuResources();

            // Try to reinitialize
            if (Initialize(_width, _height))
            {
                Log("[GPU] Device recreated successfully");
                NeedsMeshReupload = true;  // Signal that mesh needs to be re-uploaded
            }
            else
            {
                Log("[GPU] Device recreation failed");
                _deviceLost = true;
            }
        }
        catch (Exception recreateEx)
        {
            Log($"[GPU] Device recreation exception: {recreateEx.Message}");
            _deviceLost = true;
        }
    }

    private void CleanupGpuResources()
    {
        try
        {
            _pipeline?.Dispose();
            _capPipeline?.Dispose();
            _resourceSet?.Dispose();
            _resourceLayout?.Dispose();
            _uniformBuffer?.Dispose();
            _vertexBuffer?.Dispose();
            _indexBuffer?.Dispose();
            _capVertexBuffer?.Dispose();
            _capIndexBuffer?.Dispose();
            _framebuffer?.Dispose();
            _offscreenColor?.Dispose();
            _offscreenDepth?.Dispose();
            _stagingTexture?.Dispose();
            _commandList?.Dispose();
            _graphicsDevice?.Dispose();
        }
        catch { }

        _pipeline = null;
        _capPipeline = null;
        _resourceSet = null;
        _resourceLayout = null;
        _uniformBuffer = null;
        _vertexBuffer = null;
        _indexBuffer = null;
        _capVertexBuffer = null;
        _capIndexBuffer = null;
        _framebuffer = null;
        _offscreenColor = null;
        _offscreenDepth = null;
        _stagingTexture = null;
        _commandList = null;
        _graphicsDevice = null;
        _isInitialized = false;
    }

    private void RenderInternal(Matrix4x4 worldViewProjection, uint[] outputPixels)
    {
        // Update uniforms
        var uniforms = new UniformData
        {
            WorldViewProjection = worldViewProjection,
            // 6-directional cube lighting (each face of the cube)
            LightDir1 = new Vector4(1.0f, 0.0f, 0.0f, 0),   // +X (right)
            LightDir2 = new Vector4(-1.0f, 0.0f, 0.0f, 0),  // -X (left)
            LightDir3 = new Vector4(0.0f, 1.0f, 0.0f, 0),   // +Y (top)
            LightDir4 = new Vector4(0.0f, -1.0f, 0.0f, 0),  // -Y (bottom)
            LightDir5 = new Vector4(0.0f, 0.0f, 1.0f, 0),   // +Z (front)
            LightDir6 = new Vector4(0.0f, 0.0f, -1.0f, 0),  // -Z (back)
            AmbientColor = new Vector4(0.3f, 0.3f, 0.3f, 0.3f),  // w = ambient intensity (reduced since we have 6 lights)
            // Clip planes: x=enabled, y=invert, z=value (0-1), w=unused
            ClipPlaneX = new Vector4(ClipXEnabled ? 1f : 0f, ClipXInvert ? 1f : 0f, ClipXValue, 0),
            ClipPlaneY = new Vector4(ClipYEnabled ? 1f : 0f, ClipYInvert ? 1f : 0f, ClipYValue, 0),
            ClipPlaneZ = new Vector4(ClipZEnabled ? 1f : 0f, ClipZInvert ? 1f : 0f, ClipZValue, 0),
            ModelBoundsMin = new Vector4(ModelBoundsMin, 0),
            ModelBoundsMax = new Vector4(ModelBoundsMax, 0),
            // Color mapping: x=useColorMap, y=colorMapType(0-6), z=scaleMin, w=scaleMax
            ColorMapSettings = new Vector4(UseColorMap ? 1f : 0f, (float)ColorMapType, ColorScaleMin, ColorScaleMax)
        };

        // Debug log clip planes (only once)
        if (!_loggedClipPlanes && (ClipXEnabled || ClipYEnabled || ClipZEnabled))
        {
            Log($"[CLIP] X: enabled={ClipXEnabled}, val={ClipXValue:F2}, inv={ClipXInvert}");
            Log($"[CLIP] Y: enabled={ClipYEnabled}, val={ClipYValue:F2}, inv={ClipYInvert}");
            Log($"[CLIP] Z: enabled={ClipZEnabled}, val={ClipZValue:F2}, inv={ClipZInvert}");
            Log($"[CLIP] Bounds: min={ModelBoundsMin}, max={ModelBoundsMax}");
            _loggedClipPlanes = true;
        }

        _graphicsDevice!.UpdateBuffer(_uniformBuffer, 0, uniforms);

        // Begin command list
        _commandList!.Begin();

        // Set framebuffer and clear
        _commandList.SetFramebuffer(_framebuffer);
        _commandList.ClearColorTarget(0, new RgbaFloat(0.145f, 0.145f, 0.149f, 1.0f));
        _commandList.ClearDepthStencil(1.0f);

        // Set pipeline and resources
        _commandList.SetPipeline(_pipeline);
        _commandList.SetVertexBuffer(0, _vertexBuffer);
        _commandList.SetIndexBuffer(_indexBuffer, IndexFormat.UInt32);
        _commandList.SetGraphicsResourceSet(0, _resourceSet);

        // Draw main mesh
        _commandList.DrawIndexed(_indexCount, 1, 0, 0, 0);

        // Draw clip plane caps (if enabled and caps are available)
        if (ShowClipCap && _capPipeline != null && _capVertexBuffer != null && _capIndexBuffer != null && _capIndexCount > 0)
        {
            _commandList.SetPipeline(_capPipeline);
            _commandList.SetVertexBuffer(0, _capVertexBuffer);
            _commandList.SetIndexBuffer(_capIndexBuffer, IndexFormat.UInt32);
            _commandList.SetGraphicsResourceSet(0, _resourceSet);
            _commandList.DrawIndexed(_capIndexCount, 1, 0, 0, 0);
        }

        _commandList.End();
        _graphicsDevice.SubmitCommands(_commandList);
        _graphicsDevice.WaitForIdle();
    }

    private void ReadBackPixels(uint[] outputPixels)
    {
        if (_graphicsDevice == null || _stagingTexture == null) return;

        try
        {
            var map = _graphicsDevice.Map(_stagingTexture, MapMode.Read);

            if (map.Data == IntPtr.Zero)
            {
                Log("[GPU] Map.Data is null!");
                _graphicsDevice.Unmap(_stagingTexture);
                return;
            }

            int pixelCount = Math.Min(outputPixels.Length, _width * _height);
            uint rowPitch = (uint)map.RowPitch;
            int rowPitchInPixels = (int)(rowPitch / 4);

            unsafe
            {
                uint* srcPtr = (uint*)map.Data;
                for (int y = 0; y < _height; y++)
                {
                    for (int x = 0; x < _width; x++)
                    {
                        int srcIdx = y * rowPitchInPixels + x;
                        int dstIdx = y * _width + x;
                        if (dstIdx < pixelCount)
                            outputPixels[dstIdx] = srcPtr[srcIdx];
                    }
                }
            }

            _graphicsDevice.Unmap(_stagingTexture);
        }
        catch (Exception ex)
        {
            Log($"[GPU] ReadBackPixels error: {ex.Message}");
            try { _graphicsDevice.Unmap(_stagingTexture); } catch { }
        }
    }

    public void Resize(int width, int height)
    {
        if (width <= 0 || height <= 0) return;
        if (_width == width && _height == height) return;

        _width = width;
        _height = height;

        if (_isInitialized)
        {
            CreateOffscreenFramebuffer();

            // Recreate pipeline with new framebuffer
            _pipeline?.Dispose();
            _resourceSet?.Dispose();

            CreatePipeline();
            CreateUniformBuffer();

            Log($"GPU resized: {_width}x{_height}");
        }
    }

    /// <summary>
    /// Update clip cap geometry based on current clip plane settings.
    /// Creates quad planes at the clip positions to show the cross-section.
    /// </summary>
    public void UpdateClipCaps()
    {
        if (_graphicsDevice == null || !_isInitialized) return;

        var vertices = new System.Collections.Generic.List<VertexPositionNormalColor>();
        var indices = new System.Collections.Generic.List<uint>();

        var boundsSize = ModelBoundsMax - ModelBoundsMin;
        var capColor = new Vector4(0.8f, 0.5f, 0.3f, 1.0f); // Orange-ish color for caps

        // X clip plane cap
        if (ClipXEnabled && boundsSize.X > 0.001f)
        {
            float x = ModelBoundsMin.X + ClipXValue * boundsSize.X;
            var normal = ClipXInvert ? new Vector3(1, 0, 0) : new Vector3(-1, 0, 0);
            uint baseIndex = (uint)vertices.Count;

            // Quad vertices (slightly expanded to avoid z-fighting)
            float expand = 0.001f;
            vertices.Add(new VertexPositionNormalColor { Position = new Vector3(x, ModelBoundsMin.Y - expand, ModelBoundsMin.Z - expand), Normal = normal, Color = capColor });
            vertices.Add(new VertexPositionNormalColor { Position = new Vector3(x, ModelBoundsMax.Y + expand, ModelBoundsMin.Z - expand), Normal = normal, Color = capColor });
            vertices.Add(new VertexPositionNormalColor { Position = new Vector3(x, ModelBoundsMax.Y + expand, ModelBoundsMax.Z + expand), Normal = normal, Color = capColor });
            vertices.Add(new VertexPositionNormalColor { Position = new Vector3(x, ModelBoundsMin.Y - expand, ModelBoundsMax.Z + expand), Normal = normal, Color = capColor });

            // Two triangles for quad
            indices.Add(baseIndex + 0); indices.Add(baseIndex + 1); indices.Add(baseIndex + 2);
            indices.Add(baseIndex + 0); indices.Add(baseIndex + 2); indices.Add(baseIndex + 3);
        }

        // Y clip plane cap
        if (ClipYEnabled && boundsSize.Y > 0.001f)
        {
            float y = ModelBoundsMin.Y + ClipYValue * boundsSize.Y;
            var normal = ClipYInvert ? new Vector3(0, 1, 0) : new Vector3(0, -1, 0);
            uint baseIndex = (uint)vertices.Count;

            float expand = 0.001f;
            vertices.Add(new VertexPositionNormalColor { Position = new Vector3(ModelBoundsMin.X - expand, y, ModelBoundsMin.Z - expand), Normal = normal, Color = capColor });
            vertices.Add(new VertexPositionNormalColor { Position = new Vector3(ModelBoundsMax.X + expand, y, ModelBoundsMin.Z - expand), Normal = normal, Color = capColor });
            vertices.Add(new VertexPositionNormalColor { Position = new Vector3(ModelBoundsMax.X + expand, y, ModelBoundsMax.Z + expand), Normal = normal, Color = capColor });
            vertices.Add(new VertexPositionNormalColor { Position = new Vector3(ModelBoundsMin.X - expand, y, ModelBoundsMax.Z + expand), Normal = normal, Color = capColor });

            indices.Add(baseIndex + 0); indices.Add(baseIndex + 1); indices.Add(baseIndex + 2);
            indices.Add(baseIndex + 0); indices.Add(baseIndex + 2); indices.Add(baseIndex + 3);
        }

        // Z clip plane cap
        if (ClipZEnabled && boundsSize.Z > 0.001f)
        {
            float z = ModelBoundsMin.Z + ClipZValue * boundsSize.Z;
            var normal = ClipZInvert ? new Vector3(0, 0, 1) : new Vector3(0, 0, -1);
            uint baseIndex = (uint)vertices.Count;

            float expand = 0.001f;
            vertices.Add(new VertexPositionNormalColor { Position = new Vector3(ModelBoundsMin.X - expand, ModelBoundsMin.Y - expand, z), Normal = normal, Color = capColor });
            vertices.Add(new VertexPositionNormalColor { Position = new Vector3(ModelBoundsMax.X + expand, ModelBoundsMin.Y - expand, z), Normal = normal, Color = capColor });
            vertices.Add(new VertexPositionNormalColor { Position = new Vector3(ModelBoundsMax.X + expand, ModelBoundsMax.Y + expand, z), Normal = normal, Color = capColor });
            vertices.Add(new VertexPositionNormalColor { Position = new Vector3(ModelBoundsMin.X - expand, ModelBoundsMax.Y + expand, z), Normal = normal, Color = capColor });

            indices.Add(baseIndex + 0); indices.Add(baseIndex + 1); indices.Add(baseIndex + 2);
            indices.Add(baseIndex + 0); indices.Add(baseIndex + 2); indices.Add(baseIndex + 3);
        }

        if (vertices.Count == 0)
        {
            _capIndexCount = 0;
            return;
        }

        var factory = _graphicsDevice.ResourceFactory;

        // Dispose old buffers
        _capVertexBuffer?.Dispose();
        _capIndexBuffer?.Dispose();

        // Create new buffers
        _capVertexBuffer = factory.CreateBuffer(new BufferDescription(
            (uint)(vertices.Count * VertexPositionNormalColor.SizeInBytes),
            BufferUsage.VertexBuffer));
        _graphicsDevice.UpdateBuffer(_capVertexBuffer, 0, vertices.ToArray());

        _capIndexBuffer = factory.CreateBuffer(new BufferDescription(
            (uint)(indices.Count * sizeof(uint)),
            BufferUsage.IndexBuffer));
        _graphicsDevice.UpdateBuffer(_capIndexBuffer, 0, indices.ToArray());

        _capIndexCount = (uint)indices.Count;

        // Create cap pipeline if not exists (uses same shaders but with different culling)
        if (_capPipeline == null && _resourceLayout != null)
        {
            CreateCapPipeline();
        }
    }

    private void CreateCapPipeline()
    {
        if (_graphicsDevice == null || _resourceLayout == null || _framebuffer == null)
        {
            Log("[GPU] CreateCapPipeline: missing dependencies");
            return;
        }

        Log("[GPU] Creating cap pipeline...");

        try
        {
            var factory = _graphicsDevice.ResourceFactory;

        // Cap shader - simple flat color with lighting, no clipping (shows the cap itself)
        string capVertexCode = @"
#version 450

layout(location = 0) in vec3 Position;
layout(location = 1) in vec3 Normal;
layout(location = 2) in vec4 Color;

layout(location = 0) out vec3 fsin_Normal;
layout(location = 1) out vec4 fsin_Color;

layout(set = 0, binding = 0) uniform UniformBlock
{
    mat4 WorldViewProjection;
    vec4 LightDir1;
    vec4 LightDir2;
    vec4 LightDir3;
    vec4 LightDir4;
    vec4 LightDir5;
    vec4 LightDir6;
    vec4 AmbientColor;
    vec4 ClipPlaneX;
    vec4 ClipPlaneY;
    vec4 ClipPlaneZ;
    vec4 ModelBoundsMin;
    vec4 ModelBoundsMax;
    vec4 ColorMapSettings;
};

void main()
{
    gl_Position = WorldViewProjection * vec4(Position, 1.0);
    fsin_Normal = Normal;
    fsin_Color = Color;
}
";

        string capFragmentCode = @"
#version 450

layout(location = 0) in vec3 fsin_Normal;
layout(location = 1) in vec4 fsin_Color;

layout(location = 0) out vec4 fsout_Color;

layout(set = 0, binding = 0) uniform UniformBlock
{
    mat4 WorldViewProjection;
    vec4 LightDir1;
    vec4 LightDir2;
    vec4 LightDir3;
    vec4 LightDir4;
    vec4 LightDir5;
    vec4 LightDir6;
    vec4 AmbientColor;
    vec4 ClipPlaneX;
    vec4 ClipPlaneY;
    vec4 ClipPlaneZ;
    vec4 ModelBoundsMin;
    vec4 ModelBoundsMax;
    vec4 ColorMapSettings;
};

void main()
{
    vec3 normal = normalize(fsin_Normal);
    // 6-directional lighting for section caps
    float diffuse1 = max(0.0, dot(normal, LightDir1.xyz));
    float diffuse2 = max(0.0, dot(normal, LightDir2.xyz));
    float diffuse3 = max(0.0, dot(normal, LightDir3.xyz));
    float diffuse4 = max(0.0, dot(normal, LightDir4.xyz));
    float diffuse5 = max(0.0, dot(normal, LightDir5.xyz));
    float diffuse6 = max(0.0, dot(normal, LightDir6.xyz));

    float lighting = AmbientColor.w + (diffuse1 + diffuse2 + diffuse3 + diffuse4 + diffuse5 + diffuse6) * 0.15;
    lighting = clamp(lighting, 0.5, 1.0);

    vec3 litColor = fsin_Color.rgb * lighting;
    fsout_Color = vec4(litColor, fsin_Color.a);
}
";

        var vertexShaderDesc = new ShaderDescription(ShaderStages.Vertex,
            System.Text.Encoding.UTF8.GetBytes(capVertexCode), "main");
        var fragmentShaderDesc = new ShaderDescription(ShaderStages.Fragment,
            System.Text.Encoding.UTF8.GetBytes(capFragmentCode), "main");

        var shaders = factory.CreateFromSpirv(vertexShaderDesc, fragmentShaderDesc);

        var pipelineDesc = new GraphicsPipelineDescription
        {
            BlendState = BlendStateDescription.SingleOverrideBlend,
            DepthStencilState = new DepthStencilStateDescription(
                depthTestEnabled: true,
                depthWriteEnabled: true,
                comparisonKind: ComparisonKind.LessEqual),
            RasterizerState = new RasterizerStateDescription(
                cullMode: FaceCullMode.None,  // Show both sides of cap
                fillMode: PolygonFillMode.Solid,
                frontFace: FrontFace.CounterClockwise,
                depthClipEnabled: true,
                scissorTestEnabled: false),
            PrimitiveTopology = PrimitiveTopology.TriangleList,
            ResourceLayouts = new[] { _resourceLayout },
            ShaderSet = new ShaderSetDescription(
                vertexLayouts: new[] { new VertexLayoutDescription(
                    new VertexElementDescription("Position", VertexElementSemantic.TextureCoordinate, VertexElementFormat.Float3),
                    new VertexElementDescription("Normal", VertexElementSemantic.TextureCoordinate, VertexElementFormat.Float3),
                    new VertexElementDescription("Color", VertexElementSemantic.TextureCoordinate, VertexElementFormat.Float4))
                },
                shaders: shaders),
            Outputs = _framebuffer.OutputDescription
        };

            _capPipeline = factory.CreateGraphicsPipeline(pipelineDesc);
            Log("[GPU] Cap pipeline created successfully");
        }
        catch (Exception ex)
        {
            Log($"[GPU] Failed to create cap pipeline: {ex.Message}");
            Log($"[GPU] Stack trace: {ex.StackTrace}");
            _capPipeline = null;
        }
    }

    public void Dispose()
    {
        _pipeline?.Dispose();
        _capPipeline?.Dispose();
        _resourceSet?.Dispose();
        _resourceLayout?.Dispose();
        _uniformBuffer?.Dispose();
        _vertexBuffer?.Dispose();
        _indexBuffer?.Dispose();
        _capVertexBuffer?.Dispose();
        _capIndexBuffer?.Dispose();
        _framebuffer?.Dispose();
        _offscreenColor?.Dispose();
        _offscreenDepth?.Dispose();
        _stagingTexture?.Dispose();
        _commandList?.Dispose();
        _graphicsDevice?.Dispose();

        _isInitialized = false;
    }
}
