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

    // Uniform data
    [StructLayout(LayoutKind.Sequential)]
    private struct UniformData
    {
        public Matrix4x4 WorldViewProjection;
        public Vector4 LightDir1;
        public Vector4 LightDir2;
        public Vector4 LightDir3;
        public Vector4 AmbientColor;
    }

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

            // Try Vulkan first, then D3D11
            try
            {
                _graphicsDevice = GraphicsDevice.CreateVulkan(options);
                Log($"GPU: Vulkan initialized - {_graphicsDevice.DeviceName}");
            }
            catch
            {
                _graphicsDevice = GraphicsDevice.CreateD3D11(options);
                Log($"GPU: D3D11 initialized - {_graphicsDevice.DeviceName}");
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
        if (_graphicsDevice == null) return;

        var factory = _graphicsDevice.ResourceFactory;

        // Vertex shader
        string vertexCode = @"
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
    vec4 AmbientColor;
};

void main()
{
    gl_Position = WorldViewProjection * vec4(Position, 1.0);
    fsin_Normal = Normal;
    fsin_Color = Color;
}
";

        // Fragment shader
        string fragmentCode = @"
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
    vec4 AmbientColor;
};

void main()
{
    vec3 normal = normalize(fsin_Normal);

    // Multi-directional lighting
    float diffuse1 = max(0.0, dot(normal, LightDir1.xyz));
    float diffuse2 = max(0.0, dot(normal, LightDir2.xyz));
    float diffuse3 = abs(dot(normal, LightDir3.xyz));

    float lighting = AmbientColor.w + diffuse1 * 0.5 + diffuse2 * 0.2 + diffuse3 * 0.15;
    lighting = clamp(lighting, 0.1, 1.0);

    vec3 litColor = fsin_Color.rgb * lighting;
    fsout_Color = vec4(litColor, fsin_Color.a);
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
            BufferUsage.VertexBuffer));
        _graphicsDevice.UpdateBuffer(_vertexBuffer, 0, vertices);

        // Create index buffer
        _indexBuffer = factory.CreateBuffer(new BufferDescription(
            (uint)(indices.Length * sizeof(uint)),
            BufferUsage.IndexBuffer));
        _graphicsDevice.UpdateBuffer(_indexBuffer, 0, indices);

        _indexCount = (uint)indices.Length;

        Log($"GPU mesh uploaded: {vertices.Length} verts, {indices.Length / 3} tris");
    }

    public void Render(Matrix4x4 worldViewProjection, uint[] outputPixels)
    {
        if (!_isInitialized || _graphicsDevice == null || _commandList == null ||
            _framebuffer == null || _vertexBuffer == null || _indexBuffer == null ||
            _pipeline == null || _resourceSet == null || _uniformBuffer == null)
            return;

        // Update uniforms
        var uniforms = new UniformData
        {
            WorldViewProjection = worldViewProjection,
            LightDir1 = new Vector4(Vector3.Normalize(new Vector3(0.5f, 1.0f, 0.8f)), 0),
            LightDir2 = new Vector4(Vector3.Normalize(new Vector3(-0.5f, -0.3f, -0.8f)), 0),
            LightDir3 = new Vector4(Vector3.Normalize(new Vector3(0.0f, 0.0f, 1.0f)), 0),
            AmbientColor = new Vector4(0.15f, 0.15f, 0.15f, 0.15f)  // w = ambient intensity
        };

        _graphicsDevice.UpdateBuffer(_uniformBuffer, 0, uniforms);

        // Begin command list
        _commandList.Begin();

        // Set framebuffer and clear
        _commandList.SetFramebuffer(_framebuffer);
        _commandList.ClearColorTarget(0, new RgbaFloat(0.145f, 0.145f, 0.149f, 1.0f)); // Background color
        _commandList.ClearDepthStencil(1.0f);

        // Set pipeline and resources
        _commandList.SetPipeline(_pipeline);
        _commandList.SetVertexBuffer(0, _vertexBuffer);
        _commandList.SetIndexBuffer(_indexBuffer, IndexFormat.UInt32);
        _commandList.SetGraphicsResourceSet(0, _resourceSet);

        // Draw
        _commandList.DrawIndexed(_indexCount, 1, 0, 0, 0);

        // Copy to staging texture for readback
        if (_offscreenColor != null && _stagingTexture != null)
        {
            _commandList.CopyTexture(_offscreenColor, _stagingTexture);
        }

        _commandList.End();
        _graphicsDevice.SubmitCommands(_commandList);
        _graphicsDevice.WaitForIdle();

        // Read back pixels
        ReadBackPixels(outputPixels);
    }

    private void ReadBackPixels(uint[] outputPixels)
    {
        if (_graphicsDevice == null || _stagingTexture == null) return;

        var map = _graphicsDevice.Map(_stagingTexture, MapMode.Read);
        try
        {
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
        }
        finally
        {
            _graphicsDevice.Unmap(_stagingTexture);
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

    public void Dispose()
    {
        _pipeline?.Dispose();
        _resourceSet?.Dispose();
        _resourceLayout?.Dispose();
        _uniformBuffer?.Dispose();
        _vertexBuffer?.Dispose();
        _indexBuffer?.Dispose();
        _framebuffer?.Dispose();
        _offscreenColor?.Dispose();
        _offscreenDepth?.Dispose();
        _stagingTexture?.Dispose();
        _commandList?.Dispose();
        _graphicsDevice?.Dispose();

        _isInitialized = false;
    }
}
