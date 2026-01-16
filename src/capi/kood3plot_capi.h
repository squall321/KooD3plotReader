/**
 * @file kood3plot_capi.h
 * @brief C API wrapper for kood3plot library
 *
 * This header provides a C-compatible interface for the kood3plot library,
 * suitable for use with P/Invoke in .NET applications.
 *
 * Usage:
 * @code
 * koo_handle_t handle = koo_open("path/to/d3plot");
 * if (handle != NULL) {
 *     koo_mesh_info_t mesh_info;
 *     koo_get_mesh_info(handle, &mesh_info);
 *     // ... use data
 *     koo_close(handle);
 * }
 * @endcode
 */

#ifndef KOOD3PLOT_CAPI_H
#define KOOD3PLOT_CAPI_H

#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Platform-specific export macro */
#if defined(_WIN32) || defined(_WIN64)
    #ifdef KOOD3PLOT_EXPORTS
        #define KOO_API __declspec(dllexport)
    #else
        #define KOO_API __declspec(dllimport)
    #endif
#else
    #define KOO_API __attribute__((visibility("default")))
#endif

/* Opaque handle type */
typedef void* koo_handle_t;

/* Error codes */
typedef enum {
    KOO_SUCCESS = 0,
    KOO_ERROR_FILE_NOT_FOUND = 1,
    KOO_ERROR_INVALID_FORMAT = 2,
    KOO_ERROR_READ_FAILED = 3,
    KOO_ERROR_INVALID_HANDLE = 4,
    KOO_ERROR_OUT_OF_MEMORY = 5,
    KOO_ERROR_INVALID_INDEX = 6,
    KOO_ERROR_UNKNOWN = 99
} koo_error_t;

/* File info structure */
typedef struct {
    char title[81];           /* Simulation title */
    int32_t num_nodes;        /* Number of nodes */
    int32_t num_solids;       /* Number of solid elements */
    int32_t num_shells;       /* Number of shell elements */
    int32_t num_beams;        /* Number of beam elements */
    int32_t num_thick_shells; /* Number of thick shell elements */
    int32_t num_states;       /* Number of time states */
    int32_t word_size;        /* Word size (4 or 8 bytes) */
    int32_t has_displacement; /* Flag: displacement data available */
    int32_t has_velocity;     /* Flag: velocity data available */
    int32_t has_acceleration; /* Flag: acceleration data available */
    int32_t has_temperature;  /* Flag: temperature data available */
} koo_file_info_t;

/* Mesh info structure (sizes only, for buffer allocation) */
typedef struct {
    int32_t num_nodes;
    int32_t num_solids;
    int32_t num_shells;
    int32_t num_beams;
    int32_t num_thick_shells;
} koo_mesh_info_t;

/* State info structure */
typedef struct {
    double time;
    int32_t has_displacement;
    int32_t has_velocity;
    int32_t has_acceleration;
    int32_t has_stress;
} koo_state_info_t;

/*============================================================================
 * File Operations
 *============================================================================*/

/**
 * @brief Open a D3plot file
 * @param filepath Path to d3plot file (base file)
 * @return Handle to opened file, or NULL on failure
 *
 * The function automatically detects and handles multi-file families
 * (d3plot, d3plot01, d3plot02, ...).
 */
KOO_API koo_handle_t koo_open(const char* filepath);

/**
 * @brief Close a D3plot file handle
 * @param handle Handle to close
 */
KOO_API void koo_close(koo_handle_t handle);

/**
 * @brief Get last error code
 * @return Last error code
 */
KOO_API koo_error_t koo_get_last_error(void);

/**
 * @brief Get error message for an error code
 * @param error Error code
 * @return Error message string (static, do not free)
 */
KOO_API const char* koo_get_error_message(koo_error_t error);

/*============================================================================
 * File Information
 *============================================================================*/

/**
 * @brief Get file information
 * @param handle File handle
 * @param info Output file info structure
 * @return Error code
 */
KOO_API koo_error_t koo_get_file_info(koo_handle_t handle, koo_file_info_t* info);

/**
 * @brief Get mesh information (for buffer allocation)
 * @param handle File handle
 * @param info Output mesh info structure
 * @return Error code
 */
KOO_API koo_error_t koo_get_mesh_info(koo_handle_t handle, koo_mesh_info_t* info);

/**
 * @brief Get number of time states
 * @param handle File handle
 * @return Number of states, or -1 on error
 */
KOO_API int32_t koo_get_num_states(koo_handle_t handle);

/**
 * @brief Get time value for a specific state
 * @param handle File handle
 * @param state_index State index (0-based)
 * @return Time value, or -1.0 on error
 */
KOO_API double koo_get_state_time(koo_handle_t handle, int32_t state_index);

/*============================================================================
 * Mesh Data Reading
 *============================================================================*/

/**
 * @brief Read node positions
 * @param handle File handle
 * @param buffer Output buffer for node positions [num_nodes * 3] (x,y,z per node)
 * @param buffer_size Size of buffer in floats
 * @return Error code
 */
KOO_API koo_error_t koo_read_nodes(koo_handle_t handle, float* buffer, int32_t buffer_size);

/**
 * @brief Read node positions as doubles
 * @param handle File handle
 * @param buffer Output buffer for node positions [num_nodes * 3]
 * @param buffer_size Size of buffer in doubles
 * @return Error code
 */
KOO_API koo_error_t koo_read_nodes_double(koo_handle_t handle, double* buffer, int32_t buffer_size);

/**
 * @brief Read node IDs (real user IDs, not internal indices)
 * @param handle File handle
 * @param buffer Output buffer for node IDs [num_nodes]
 * @param buffer_size Size of buffer in int32s
 * @return Error code
 */
KOO_API koo_error_t koo_read_node_ids(koo_handle_t handle, int32_t* buffer, int32_t buffer_size);

/**
 * @brief Read solid element connectivity
 * @param handle File handle
 * @param buffer Output buffer [num_solids * 8] (8 nodes per solid)
 * @param buffer_size Size of buffer in int32s
 * @return Error code
 */
KOO_API koo_error_t koo_read_solid_connectivity(koo_handle_t handle, int32_t* buffer, int32_t buffer_size);

/**
 * @brief Read solid element part IDs
 * @param handle File handle
 * @param buffer Output buffer [num_solids]
 * @param buffer_size Size of buffer in int32s
 * @return Error code
 */
KOO_API koo_error_t koo_read_solid_part_ids(koo_handle_t handle, int32_t* buffer, int32_t buffer_size);

/**
 * @brief Read shell element connectivity
 * @param handle File handle
 * @param buffer Output buffer [num_shells * 4] (4 nodes per shell)
 * @param buffer_size Size of buffer in int32s
 * @return Error code
 */
KOO_API koo_error_t koo_read_shell_connectivity(koo_handle_t handle, int32_t* buffer, int32_t buffer_size);

/**
 * @brief Read shell element part IDs
 * @param handle File handle
 * @param buffer Output buffer [num_shells]
 * @param buffer_size Size of buffer in int32s
 * @return Error code
 */
KOO_API koo_error_t koo_read_shell_part_ids(koo_handle_t handle, int32_t* buffer, int32_t buffer_size);

/**
 * @brief Read beam element connectivity
 * @param handle File handle
 * @param buffer Output buffer [num_beams * 2] (2 nodes per beam)
 * @param buffer_size Size of buffer in int32s
 * @return Error code
 */
KOO_API koo_error_t koo_read_beam_connectivity(koo_handle_t handle, int32_t* buffer, int32_t buffer_size);

/*============================================================================
 * State Data Reading
 *============================================================================*/

/**
 * @brief Read displacement data for a specific state
 * @param handle File handle
 * @param state_index State index (0-based)
 * @param buffer Output buffer [num_nodes * 3] (dx, dy, dz per node)
 * @param buffer_size Size of buffer in floats
 * @return Error code
 */
KOO_API koo_error_t koo_read_displacement(koo_handle_t handle, int32_t state_index,
                                          float* buffer, int32_t buffer_size);

/**
 * @brief Read velocity data for a specific state
 * @param handle File handle
 * @param state_index State index (0-based)
 * @param buffer Output buffer [num_nodes * 3] (vx, vy, vz per node)
 * @param buffer_size Size of buffer in floats
 * @return Error code
 */
KOO_API koo_error_t koo_read_velocity(koo_handle_t handle, int32_t state_index,
                                      float* buffer, int32_t buffer_size);

/**
 * @brief Read acceleration data for a specific state
 * @param handle File handle
 * @param state_index State index (0-based)
 * @param buffer Output buffer [num_nodes * 3] (ax, ay, az per node)
 * @param buffer_size Size of buffer in floats
 * @return Error code
 */
KOO_API koo_error_t koo_read_acceleration(koo_handle_t handle, int32_t state_index,
                                          float* buffer, int32_t buffer_size);

/**
 * @brief Read solid stress data for a specific state
 * @param handle File handle
 * @param state_index State index (0-based)
 * @param buffer Output buffer [num_solids * 6] (sigma_xx, sigma_yy, sigma_zz, tau_xy, tau_yz, tau_zx)
 * @param buffer_size Size of buffer in floats
 * @return Error code
 */
KOO_API koo_error_t koo_read_solid_stress(koo_handle_t handle, int32_t state_index,
                                          float* buffer, int32_t buffer_size);

/**
 * @brief Read shell stress data for a specific state
 * @param handle File handle
 * @param state_index State index (0-based)
 * @param buffer Output buffer (varies by element)
 * @param buffer_size Size of buffer in floats
 * @return Error code
 */
KOO_API koo_error_t koo_read_shell_stress(koo_handle_t handle, int32_t state_index,
                                          float* buffer, int32_t buffer_size);

/*============================================================================
 * Utility Functions
 *============================================================================*/

/**
 * @brief Get library version string
 * @return Version string (e.g., "1.0.0")
 */
KOO_API const char* koo_get_version(void);

/**
 * @brief Calculate Von Mises stress from stress tensor
 * @param sigma_xx Normal stress XX
 * @param sigma_yy Normal stress YY
 * @param sigma_zz Normal stress ZZ
 * @param tau_xy Shear stress XY
 * @param tau_yz Shear stress YZ
 * @param tau_zx Shear stress ZX
 * @return Von Mises equivalent stress
 */
KOO_API float koo_calc_von_mises(float sigma_xx, float sigma_yy, float sigma_zz,
                                  float tau_xy, float tau_yz, float tau_zx);

#ifdef __cplusplus
}
#endif

#endif /* KOOD3PLOT_CAPI_H */
