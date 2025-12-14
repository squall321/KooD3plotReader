using System;
using System.Numerics;

namespace KooD3plot.Rendering;

/// <summary>
/// Arcball camera for 3D viewport navigation
/// </summary>
public class Camera
{
    private Vector3 _position;
    private Vector3 _target;
    private Vector3 _up;
    private float _fov;
    private float _nearPlane;
    private float _farPlane;
    private float _aspectRatio;

    // Arcball parameters
    private float _distance;
    private float _rotationX; // Pitch (around X axis)
    private float _rotationY; // Yaw (around Y axis)
    private float _rotationZ; // Roll (around Z axis)

    // Interaction state
    private Vector2 _lastMousePos;
    private bool _isRotating;
    private bool _isPanning;
    private bool _isZooming;

    // Sensitivity settings
    public float RotationSensitivity { get; set; } = 0.005f;
    public float PanSensitivity { get; set; } = 0.5f;
    public float ZoomSensitivity { get; set; } = 0.1f;
    public float MinDistance { get; set; } = 1.0f;
    public float MaxDistance { get; set; } = 100000.0f;

    public Camera()
    {
        _target = Vector3.Zero;
        _up = Vector3.UnitY;
        _fov = 45.0f;
        _nearPlane = 0.1f;
        _farPlane = 100000.0f;
        _aspectRatio = 16.0f / 9.0f;
        _distance = 500.0f;
        _rotationX = 0;
        _rotationY = 0;
        _rotationZ = 0;

        UpdatePosition();
    }

    public Vector3 Position => _position;
    public Vector3 Target
    {
        get => _target;
        set { _target = value; UpdatePosition(); }
    }

    public float FieldOfView
    {
        get => _fov;
        set => _fov = Math.Clamp(value, 10.0f, 120.0f);
    }

    public float AspectRatio
    {
        get => _aspectRatio;
        set => _aspectRatio = value;
    }

    public float Distance
    {
        get => _distance;
        set
        {
            _distance = Math.Clamp(value, MinDistance, MaxDistance);
            UpdatePosition();
        }
    }

    /// <summary>
    /// Get the view matrix
    /// </summary>
    public Matrix4x4 ViewMatrix => Matrix4x4.CreateLookAt(_position, _target, _up);

    /// <summary>
    /// Get the projection matrix
    /// </summary>
    public Matrix4x4 ProjectionMatrix => Matrix4x4.CreatePerspectiveFieldOfView(
        _fov * MathF.PI / 180.0f,
        _aspectRatio,
        _nearPlane,
        _farPlane
    );

    /// <summary>
    /// Get the combined view-projection matrix
    /// </summary>
    public Matrix4x4 ViewProjectionMatrix => ViewMatrix * ProjectionMatrix;

    /// <summary>
    /// Get the forward direction (towards target)
    /// </summary>
    public Vector3 Forward => Vector3.Normalize(_target - _position);

    /// <summary>
    /// Get the right direction
    /// </summary>
    public Vector3 Right => Vector3.Normalize(Vector3.Cross(Forward, _up));

    /// <summary>
    /// Get the up direction (camera local)
    /// </summary>
    public Vector3 Up => Vector3.Cross(Right, Forward);

    /// <summary>
    /// Begin rotation interaction
    /// </summary>
    public void BeginRotate(float x, float y)
    {
        _lastMousePos = new Vector2(x, y);
        _isRotating = true;
    }

    /// <summary>
    /// Begin pan interaction
    /// </summary>
    public void BeginPan(float x, float y)
    {
        _lastMousePos = new Vector2(x, y);
        _isPanning = true;
    }

    /// <summary>
    /// End all interactions
    /// </summary>
    public void EndInteraction()
    {
        _isRotating = false;
        _isPanning = false;
        _isZooming = false;
    }

    /// <summary>
    /// Update camera based on mouse movement
    /// </summary>
    public void OnMouseMove(float x, float y)
    {
        var delta = new Vector2(x, y) - _lastMousePos;
        _lastMousePos = new Vector2(x, y);

        if (_isRotating)
        {
            Rotate(delta.X, delta.Y);
        }
        else if (_isPanning)
        {
            Pan(delta.X, delta.Y);
        }
    }

    /// <summary>
    /// Rotate the camera around the target
    /// </summary>
    public void Rotate(float deltaX, float deltaY)
    {
        _rotationY -= deltaX * RotationSensitivity;
        _rotationX -= deltaY * RotationSensitivity;

        // Clamp pitch to prevent gimbal lock
        _rotationX = Math.Clamp(_rotationX, -MathF.PI / 2 + 0.01f, MathF.PI / 2 - 0.01f);

        UpdatePosition();
    }

    /// <summary>
    /// Pan the camera (move target)
    /// </summary>
    public void Pan(float deltaX, float deltaY)
    {
        var panScale = _distance * PanSensitivity * 0.001f;
        _target -= Right * deltaX * panScale;
        _target += Up * deltaY * panScale;
        UpdatePosition();
    }

    /// <summary>
    /// Zoom the camera (change distance)
    /// </summary>
    public void Zoom(float delta)
    {
        _distance *= 1.0f - delta * ZoomSensitivity;
        _distance = Math.Clamp(_distance, MinDistance, MaxDistance);
        UpdatePosition();
    }

    /// <summary>
    /// Reset camera to default view
    /// </summary>
    public void Reset()
    {
        _target = Vector3.Zero;
        _distance = 500.0f;
        _rotationX = 0;
        _rotationY = 0;
        _rotationZ = 0;
        UpdatePosition();
    }

    /// <summary>
    /// Fit the camera to view the given bounding box
    /// </summary>
    public void FitToBounds(Vector3 boundsMin, Vector3 boundsMax)
    {
        var center = (boundsMin + boundsMax) * 0.5f;
        var size = (boundsMax - boundsMin).Length();

        _target = center;
        _distance = size / (2.0f * MathF.Tan(_fov * MathF.PI / 360.0f));
        _rotationX = -0.4f; // Slight downward angle
        _rotationY = 0.3f;  // Slight rotation

        UpdatePosition();
    }

    /// <summary>
    /// Set view to standard engineering view
    /// </summary>
    public void SetStandardView(StandardView view)
    {
        switch (view)
        {
            case StandardView.Front:
                _rotationX = 0;
                _rotationY = 0;
                break;
            case StandardView.Back:
                _rotationX = 0;
                _rotationY = MathF.PI;
                break;
            case StandardView.Left:
                _rotationX = 0;
                _rotationY = MathF.PI / 2;
                break;
            case StandardView.Right:
                _rotationX = 0;
                _rotationY = -MathF.PI / 2;
                break;
            case StandardView.Top:
                _rotationX = -MathF.PI / 2 + 0.001f;
                _rotationY = 0;
                break;
            case StandardView.Bottom:
                _rotationX = MathF.PI / 2 - 0.001f;
                _rotationY = 0;
                break;
            case StandardView.Isometric:
                _rotationX = -MathF.Atan(1.0f / MathF.Sqrt(2.0f)); // ~35.26°
                _rotationY = MathF.PI / 4; // 45°
                break;
        }
        UpdatePosition();
    }

    private void UpdatePosition()
    {
        // Compute position from spherical coordinates
        var rotationMatrix = Matrix4x4.CreateRotationY(_rotationY) * Matrix4x4.CreateRotationX(_rotationX);
        var offset = Vector3.Transform(new Vector3(0, 0, _distance), rotationMatrix);
        _position = _target + offset;

        // Update up vector based on rotation
        _up = Vector3.Transform(Vector3.UnitY, rotationMatrix);
    }
}

/// <summary>
/// Standard engineering views
/// </summary>
public enum StandardView
{
    Front,
    Back,
    Left,
    Right,
    Top,
    Bottom,
    Isometric
}
