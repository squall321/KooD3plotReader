using System;
using System.Numerics;
using System.Runtime.CompilerServices;
using Veldrid;
using Veldrid.SPIRV;

namespace KooD3plot.Rendering;

/// <summary>
/// Veldrid-based renderer supporting Vulkan, D3D12, and Metal
/// </summary>
public class VeldridRenderer : IDisposable
{
    private GraphicsDevice? _graphicsDevice;
    private CommandList? _commandList;
    private Pipeline? _pipeline;
    private Pipeline? _wireframePipeline;
    private DeviceBuffer? _vertexBuffer;
    private DeviceBuffer? _indexBuffer;
    private DeviceBuffer? _uniformBuffer;
    private ResourceSet? _resourceSet;
    private ResourceLayout? _resourceLayout;

    private Swapchain? _swapchain;
    private bool _isInitialized;
    private bool _disposed;

    // Camera state
    private Vector3 _cameraPosition = new(0, 0, 500);
    private Vector3 _cameraTarget = Vector3.Zero;
    private Vector3 _cameraUp = Vector3.UnitY;
    private float _fov = 45.0f;
    private float _nearPlane = 0.1f;
    private float _farPlane = 10000.0f;

    // Mouse interaction state
    private bool _isRotating;
    private bool _isPanning;
    private Vector2 _lastMousePos;
    private float _rotationX;
    private float _rotationY;
    private float _zoom = 1.0f;

    // Mesh data
    private MeshRenderData? _meshData;
    private bool _meshDirty = true;
    private int _indexCount;

    // Rendering state
    private bool _showWireframe;
    private float _displacementScale = 1.0f;

    // Uniform buffer data
    private struct UniformData
    {
        public Matrix4x4 WorldViewProjection;
        public Matrix4x4 World;
        public Vector4 LightDirection;
        public Vector4 CameraPosition;
        public float ScalarMin;
        public float ScalarMax;
        public float DisplacementScale;
        public float Padding;
    }

    public VeldridRenderer(IntPtr windowHandle)
    {
        Initialize(windowHandle);
    }

    private void Initialize(IntPtr windowHandle)
    {
        try
        {
            // Create graphics device with best available backend
            var options = new GraphicsDeviceOptions
            {
                PreferStandardClipSpaceYDirection = true,
                PreferDepthRangeZeroToOne = true,
                SyncToVerticalBlank = true,
                ResourceBindingModel = ResourceBindingModel.Improved
            };

            // Try backends in order of preference: Vulkan > D3D11 > Metal > OpenGL
            GraphicsBackend backend = GetPreferredBackend();

            // Create swapchain source based on platform
            SwapchainSource swapchainSource;
            if (OperatingSystem.IsWindows())
            {
                swapchainSource = SwapchainSource.CreateWin32(windowHandle, IntPtr.Zero);
            }
            else if (OperatingSystem.IsLinux())
            {
                // For Linux/X11 - would need display handle
                swapchainSource = SwapchainSource.CreateXlib(IntPtr.Zero, windowHandle);
            }
            else
            {
                throw new PlatformNotSupportedException("Unsupported platform for Veldrid");
            }

            var swapchainDesc = new SwapchainDescription(
                swapchainSource,
                1600, 900,
                PixelFormat.D32_Float_S8_UInt,
                true
            );

            // Create device based on backend preference
            _graphicsDevice = backend switch
            {
                GraphicsBackend.Vulkan => GraphicsDevice.CreateVulkan(options),
                GraphicsBackend.Direct3D11 => GraphicsDevice.CreateD3D11(options),
                GraphicsBackend.Metal => GraphicsDevice.CreateMetal(options),
                _ => throw new PlatformNotSupportedException("OpenGL fallback not implemented")
            };

            _swapchain = _graphicsDevice.ResourceFactory.CreateSwapchain(swapchainDesc);

            CreateResources();
            _isInitialized = true;
        }
        catch (Exception ex)
        {
            Console.WriteLine($"Veldrid initialization failed: {ex.Message}");
            // Fallback to software rendering or dummy mode
        }
    }

    private static GraphicsBackend GetPreferredBackend()
    {
        if (GraphicsDevice.IsBackendSupported(GraphicsBackend.Vulkan))
            return GraphicsBackend.Vulkan;
        if (GraphicsDevice.IsBackendSupported(GraphicsBackend.Direct3D11))
            return GraphicsBackend.Direct3D11;
        if (GraphicsDevice.IsBackendSupported(GraphicsBackend.Metal))
            return GraphicsBackend.Metal;

        return GraphicsBackend.OpenGL;
    }

    private void CreateResources()
    {
        if (_graphicsDevice == null) return;

        var factory = _graphicsDevice.ResourceFactory;

        // Create command list
        _commandList = factory.CreateCommandList();

        // Create uniform buffer
        _uniformBuffer = factory.CreateBuffer(new BufferDescription(
            (uint)Unsafe.SizeOf<UniformData>(),
            BufferUsage.UniformBuffer | BufferUsage.Dynamic
        ));

        // Create resource layout
        _resourceLayout = factory.CreateResourceLayout(new ResourceLayoutDescription(
            new ResourceLayoutElementDescription("Uniforms", ResourceKind.UniformBuffer, ShaderStages.Vertex | ShaderStages.Fragment)
        ));

        // Create resource set
        _resourceSet = factory.CreateResourceSet(new ResourceSetDescription(
            _resourceLayout,
            _uniformBuffer
        ));

        // Create shaders and pipeline
        CreatePipeline();
    }

    private void CreatePipeline()
    {
        if (_graphicsDevice == null) return;

        var factory = _graphicsDevice.ResourceFactory;

        // Vertex shader (GLSL 450 for SPIRV compilation)
        string vertexShaderCode = @"
#version 450

layout(location = 0) in vec3 Position;
layout(location = 1) in vec3 Normal;
layout(location = 2) in float ScalarValue;

layout(location = 0) out vec3 frag_Normal;
layout(location = 1) out float frag_Scalar;
layout(location = 2) out vec3 frag_WorldPos;

layout(set = 0, binding = 0) uniform Uniforms {
    mat4 WorldViewProjection;
    mat4 World;
    vec4 LightDirection;
    vec4 CameraPosition;
    float ScalarMin;
    float ScalarMax;
    float DisplacementScale;
    float Padding;
};

void main() {
    vec4 worldPos = World * vec4(Position, 1.0);
    gl_Position = WorldViewProjection * vec4(Position, 1.0);
    frag_Normal = mat3(World) * Normal;
    frag_Scalar = ScalarValue;
    frag_WorldPos = worldPos.xyz;
}
";

        // Fragment shader with jet colormap
        string fragmentShaderCode = @"
#version 450

layout(location = 0) in vec3 frag_Normal;
layout(location = 1) in float frag_Scalar;
layout(location = 2) in vec3 frag_WorldPos;

layout(location = 0) out vec4 out_Color;

layout(set = 0, binding = 0) uniform Uniforms {
    mat4 WorldViewProjection;
    mat4 World;
    vec4 LightDirection;
    vec4 CameraPosition;
    float ScalarMin;
    float ScalarMax;
    float DisplacementScale;
    float Padding;
};

// Jet colormap function
vec3 jetColormap(float t) {
    t = clamp(t, 0.0, 1.0);

    float r = clamp(1.5 - abs(4.0 * t - 3.0), 0.0, 1.0);
    float g = clamp(1.5 - abs(4.0 * t - 2.0), 0.0, 1.0);
    float b = clamp(1.5 - abs(4.0 * t - 1.0), 0.0, 1.0);

    return vec3(r, g, b);
}

void main() {
    // Normalize scalar to 0-1 range
    float normalizedScalar = (frag_Scalar - ScalarMin) / max(ScalarMax - ScalarMin, 0.001);
    vec3 baseColor = jetColormap(normalizedScalar);

    // Simple lighting
    vec3 normal = normalize(frag_Normal);
    vec3 lightDir = normalize(LightDirection.xyz);
    float diffuse = max(dot(normal, lightDir), 0.0);
    float ambient = 0.3;

    // Specular
    vec3 viewDir = normalize(CameraPosition.xyz - frag_WorldPos);
    vec3 halfDir = normalize(lightDir + viewDir);
    float specular = pow(max(dot(normal, halfDir), 0.0), 32.0) * 0.3;

    vec3 finalColor = baseColor * (ambient + diffuse * 0.7) + vec3(specular);
    out_Color = vec4(finalColor, 1.0);
}
";

        var vertexShaderDesc = new ShaderDescription(ShaderStages.Vertex, System.Text.Encoding.UTF8.GetBytes(vertexShaderCode), "main");
        var fragmentShaderDesc = new ShaderDescription(ShaderStages.Fragment, System.Text.Encoding.UTF8.GetBytes(fragmentShaderCode), "main");

        var shaders = factory.CreateFromSpirv(vertexShaderDesc, fragmentShaderDesc);

        // Vertex layout
        var vertexLayout = new VertexLayoutDescription(
            new VertexElementDescription("Position", VertexElementSemantic.TextureCoordinate, VertexElementFormat.Float3),
            new VertexElementDescription("Normal", VertexElementSemantic.TextureCoordinate, VertexElementFormat.Float3),
            new VertexElementDescription("ScalarValue", VertexElementSemantic.TextureCoordinate, VertexElementFormat.Float1)
        );

        // Pipeline description
        var pipelineDesc = new GraphicsPipelineDescription
        {
            BlendState = BlendStateDescription.SingleOverrideBlend,
            DepthStencilState = new DepthStencilStateDescription(
                depthTestEnabled: true,
                depthWriteEnabled: true,
                comparisonKind: ComparisonKind.LessEqual
            ),
            RasterizerState = new RasterizerStateDescription(
                cullMode: FaceCullMode.Back,
                fillMode: PolygonFillMode.Solid,
                frontFace: FrontFace.CounterClockwise,
                depthClipEnabled: true,
                scissorTestEnabled: false
            ),
            PrimitiveTopology = PrimitiveTopology.TriangleList,
            ResourceLayouts = new[] { _resourceLayout! },
            ShaderSet = new ShaderSetDescription(
                vertexLayouts: new[] { vertexLayout },
                shaders: shaders
            ),
            Outputs = _swapchain!.Framebuffer.OutputDescription
        };

        _pipeline = factory.CreateGraphicsPipeline(pipelineDesc);

        // Wireframe pipeline
        pipelineDesc.RasterizerState = new RasterizerStateDescription(
            cullMode: FaceCullMode.None,
            fillMode: PolygonFillMode.Wireframe,
            frontFace: FrontFace.CounterClockwise,
            depthClipEnabled: true,
            scissorTestEnabled: false
        );
        _wireframePipeline = factory.CreateGraphicsPipeline(pipelineDesc);

        foreach (var shader in shaders)
            shader.Dispose();
    }

    public void SetMeshData(MeshRenderData data)
    {
        _meshData = data;
        _meshDirty = true;
    }

    public void UpdateTimestep(int timestep)
    {
        // Mesh data should be updated externally, just mark dirty
        _meshDirty = true;
    }

    private void UpdateBuffers()
    {
        if (_graphicsDevice == null || _meshData == null || !_meshDirty) return;

        var factory = _graphicsDevice.ResourceFactory;

        // Create vertex buffer
        int numVertices = _meshData.CurrentPositions.Length / 3;
        uint vertexSize = 7 * sizeof(float); // pos(3) + normal(3) + scalar(1)
        uint vertexBufferSize = (uint)(numVertices * vertexSize);

        _vertexBuffer?.Dispose();
        _vertexBuffer = factory.CreateBuffer(new BufferDescription(vertexBufferSize, BufferUsage.VertexBuffer));

        // Build vertex data
        var vertexData = new float[numVertices * 7];
        for (int i = 0; i < numVertices; i++)
        {
            vertexData[i * 7 + 0] = _meshData.CurrentPositions[i * 3 + 0];
            vertexData[i * 7 + 1] = _meshData.CurrentPositions[i * 3 + 1];
            vertexData[i * 7 + 2] = _meshData.CurrentPositions[i * 3 + 2];
            vertexData[i * 7 + 3] = _meshData.Normals.Length > 0 ? _meshData.Normals[i * 3 + 0] : 0;
            vertexData[i * 7 + 4] = _meshData.Normals.Length > 0 ? _meshData.Normals[i * 3 + 1] : 1;
            vertexData[i * 7 + 5] = _meshData.Normals.Length > 0 ? _meshData.Normals[i * 3 + 2] : 0;
            vertexData[i * 7 + 6] = _meshData.ScalarValues.Length > 0 ? _meshData.ScalarValues[i] : 0;
        }

        _graphicsDevice.UpdateBuffer(_vertexBuffer, 0, vertexData);

        // Create index buffer
        if (_meshData.Indices.Length > 0)
        {
            _indexBuffer?.Dispose();
            _indexBuffer = factory.CreateBuffer(new BufferDescription(
                (uint)(_meshData.Indices.Length * sizeof(uint)),
                BufferUsage.IndexBuffer
            ));
            _graphicsDevice.UpdateBuffer(_indexBuffer, 0, _meshData.Indices);
            _indexCount = _meshData.Indices.Length;
        }

        _meshDirty = false;
    }

    public void Render()
    {
        if (!_isInitialized || _graphicsDevice == null || _commandList == null || _swapchain == null)
            return;

        UpdateBuffers();

        // Update uniforms
        var view = Matrix4x4.CreateLookAt(_cameraPosition, _cameraTarget, _cameraUp);
        var projection = Matrix4x4.CreatePerspectiveFieldOfView(
            _fov * MathF.PI / 180f,
            (float)_swapchain.Framebuffer.Width / _swapchain.Framebuffer.Height,
            _nearPlane,
            _farPlane
        );

        // Apply rotation
        var rotationMatrix = Matrix4x4.CreateRotationY(_rotationY) * Matrix4x4.CreateRotationX(_rotationX);
        var world = rotationMatrix;

        var uniforms = new UniformData
        {
            WorldViewProjection = world * view * projection,
            World = world,
            LightDirection = new Vector4(Vector3.Normalize(new Vector3(1, 1, 1)), 0),
            CameraPosition = new Vector4(_cameraPosition, 1),
            ScalarMin = _meshData?.ScalarMin ?? 0,
            ScalarMax = _meshData?.ScalarMax ?? 1,
            DisplacementScale = _displacementScale,
            Padding = 0
        };

        _graphicsDevice.UpdateBuffer(_uniformBuffer!, 0, uniforms);

        // Begin render
        _commandList.Begin();
        _commandList.SetFramebuffer(_swapchain.Framebuffer);
        _commandList.ClearColorTarget(0, new RgbaFloat(0.15f, 0.15f, 0.15f, 1.0f));
        _commandList.ClearDepthStencil(1.0f);

        if (_vertexBuffer != null && _indexBuffer != null && _indexCount > 0)
        {
            _commandList.SetPipeline(_showWireframe ? _wireframePipeline! : _pipeline!);
            _commandList.SetVertexBuffer(0, _vertexBuffer);
            _commandList.SetIndexBuffer(_indexBuffer, IndexFormat.UInt32);
            _commandList.SetGraphicsResourceSet(0, _resourceSet!);
            _commandList.DrawIndexed((uint)_indexCount);
        }

        _commandList.End();
        _graphicsDevice.SubmitCommands(_commandList);
        _graphicsDevice.SwapBuffers(_swapchain);
    }

    public void OnMouseDown(float x, float y, bool isLeft)
    {
        _lastMousePos = new Vector2(x, y);
        if (isLeft)
            _isRotating = true;
        else
            _isPanning = true;
    }

    public void OnMouseUp()
    {
        _isRotating = false;
        _isPanning = false;
    }

    public void OnMouseMove(float x, float y)
    {
        var delta = new Vector2(x, y) - _lastMousePos;
        _lastMousePos = new Vector2(x, y);

        if (_isRotating)
        {
            _rotationY += delta.X * 0.01f;
            _rotationX += delta.Y * 0.01f;
        }
        else if (_isPanning)
        {
            _cameraTarget += new Vector3(-delta.X * 0.5f, delta.Y * 0.5f, 0);
        }
    }

    public void OnMouseWheel(float delta)
    {
        _zoom *= (delta > 0) ? 0.9f : 1.1f;
        _zoom = Math.Clamp(_zoom, 0.1f, 10.0f);
        _cameraPosition = _cameraTarget + Vector3.Normalize(_cameraPosition - _cameraTarget) * (500 * _zoom);
    }

    public void Resize(uint width, uint height)
    {
        _swapchain?.Resize(width, height);
    }

    public void SetWireframeMode(bool enabled)
    {
        _showWireframe = enabled;
    }

    public void SetDisplacementScale(float scale)
    {
        _displacementScale = scale;
    }

    public void ResetCamera()
    {
        _cameraPosition = new Vector3(0, 0, 500);
        _cameraTarget = Vector3.Zero;
        _rotationX = 0;
        _rotationY = 0;
        _zoom = 1.0f;
    }

    public void FitToView()
    {
        if (_meshData == null) return;

        var center = (_meshData.BoundsMin + _meshData.BoundsMax) * 0.5f;
        var size = (_meshData.BoundsMax - _meshData.BoundsMin).Length();

        _cameraTarget = center;
        _cameraPosition = center + new Vector3(0, 0, size * 2);
    }

    public void Dispose()
    {
        if (_disposed) return;
        _disposed = true;

        _pipeline?.Dispose();
        _wireframePipeline?.Dispose();
        _vertexBuffer?.Dispose();
        _indexBuffer?.Dispose();
        _uniformBuffer?.Dispose();
        _resourceSet?.Dispose();
        _resourceLayout?.Dispose();
        _commandList?.Dispose();
        _swapchain?.Dispose();
        _graphicsDevice?.Dispose();
    }
}
