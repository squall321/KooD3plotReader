/**
 * @file kood3plot_capi.cpp
 * @brief C API implementation for kood3plot library
 */

#include "kood3plot_capi.h"
#include "kood3plot/D3plotReader.hpp"
#include "kood3plot/Version.hpp"

#include <cstring>
#include <cmath>
#include <memory>
#include <mutex>
#include <unordered_map>

// Thread-local error storage
static thread_local koo_error_t g_last_error = KOO_SUCCESS;

// Handle management
struct HandleData {
    std::unique_ptr<kood3plot::D3plotReader> reader;
    kood3plot::data::Mesh mesh;
    std::vector<kood3plot::data::StateData> states;
    bool mesh_loaded = false;
    bool states_loaded = false;  // All states loaded at once
};

static std::mutex g_handles_mutex;
static std::unordered_map<koo_handle_t, std::unique_ptr<HandleData>> g_handles;
static uint64_t g_next_handle_id = 1;

// Helper: set error and return
static inline koo_error_t set_error(koo_error_t err) {
    g_last_error = err;
    return err;
}

// Helper: convert kood3plot ErrorCode to koo_error_t
static koo_error_t convert_error(kood3plot::ErrorCode ec) {
    switch (ec) {
        case kood3plot::ErrorCode::SUCCESS: return KOO_SUCCESS;
        case kood3plot::ErrorCode::FILE_NOT_FOUND: return KOO_ERROR_FILE_NOT_FOUND;
        case kood3plot::ErrorCode::INVALID_FORMAT: return KOO_ERROR_INVALID_FORMAT;
        case kood3plot::ErrorCode::IO_ERROR: return KOO_ERROR_READ_FAILED;
        case kood3plot::ErrorCode::CORRUPTED_DATA: return KOO_ERROR_READ_FAILED;
        default: return KOO_ERROR_UNKNOWN;
    }
}

// Helper: get handle data
static HandleData* get_handle(koo_handle_t handle) {
    std::lock_guard<std::mutex> lock(g_handles_mutex);
    auto it = g_handles.find(handle);
    if (it == g_handles.end()) {
        return nullptr;
    }
    return it->second.get();
}

/*============================================================================
 * File Operations
 *============================================================================*/

KOO_API koo_handle_t koo_open(const char* filepath) {
    if (!filepath) {
        set_error(KOO_ERROR_FILE_NOT_FOUND);
        return nullptr;
    }

    try {
        auto data = std::make_unique<HandleData>();
        data->reader = std::make_unique<kood3plot::D3plotReader>(filepath);

        auto err = data->reader->open();
        if (err != kood3plot::ErrorCode::SUCCESS) {
            set_error(convert_error(err));
            return nullptr;
        }

        // Generate handle ID
        koo_handle_t handle = reinterpret_cast<koo_handle_t>(g_next_handle_id++);

        // Store in map
        {
            std::lock_guard<std::mutex> lock(g_handles_mutex);
            g_handles[handle] = std::move(data);
        }

        set_error(KOO_SUCCESS);
        return handle;
    }
    catch (const std::exception&) {
        set_error(KOO_ERROR_UNKNOWN);
        return nullptr;
    }
}

KOO_API void koo_close(koo_handle_t handle) {
    if (!handle) return;

    std::lock_guard<std::mutex> lock(g_handles_mutex);
    auto it = g_handles.find(handle);
    if (it != g_handles.end()) {
        g_handles.erase(it);
    }
}

KOO_API koo_error_t koo_get_last_error(void) {
    return g_last_error;
}

KOO_API const char* koo_get_error_message(koo_error_t error) {
    switch (error) {
        case KOO_SUCCESS: return "Success";
        case KOO_ERROR_FILE_NOT_FOUND: return "File not found";
        case KOO_ERROR_INVALID_FORMAT: return "Invalid file format";
        case KOO_ERROR_READ_FAILED: return "Read failed";
        case KOO_ERROR_INVALID_HANDLE: return "Invalid handle";
        case KOO_ERROR_OUT_OF_MEMORY: return "Out of memory";
        case KOO_ERROR_INVALID_INDEX: return "Invalid index";
        default: return "Unknown error";
    }
}

// Forward declarations
static bool ensure_states_loaded(HandleData* data);

/*============================================================================
 * File Information
 *============================================================================*/

KOO_API koo_error_t koo_get_file_info(koo_handle_t handle, koo_file_info_t* info) {
    if (!info) return set_error(KOO_ERROR_INVALID_HANDLE);

    auto* data = get_handle(handle);
    if (!data || !data->reader) return set_error(KOO_ERROR_INVALID_HANDLE);

    try {
        const auto& ctrl = data->reader->get_control_data();

        std::memset(info, 0, sizeof(koo_file_info_t));
        std::strncpy(info->title, ctrl.TITLE.c_str(), 80);
        info->num_nodes = ctrl.NUMNP;
        info->num_solids = ctrl.NEL8;
        info->num_shells = ctrl.NEL4;
        info->num_beams = ctrl.NEL2;
        info->num_thick_shells = ctrl.NELT;

        // Load and cache states to get count
        if (ensure_states_loaded(data)) {
            info->num_states = static_cast<int32_t>(data->states.size());
        } else {
            info->num_states = 0;
        }

        info->word_size = ctrl.NDIM > 5 ? 8 : 4;  // Approximate
        info->has_displacement = ctrl.IU != 0 ? 1 : 0;
        info->has_velocity = ctrl.IV != 0 ? 1 : 0;
        info->has_acceleration = ctrl.IA != 0 ? 1 : 0;
        info->has_temperature = ctrl.IT != 0 ? 1 : 0;

        return set_error(KOO_SUCCESS);
    }
    catch (const std::exception&) {
        return set_error(KOO_ERROR_READ_FAILED);
    }
}

KOO_API koo_error_t koo_get_mesh_info(koo_handle_t handle, koo_mesh_info_t* info) {
    if (!info) return set_error(KOO_ERROR_INVALID_HANDLE);

    auto* data = get_handle(handle);
    if (!data || !data->reader) return set_error(KOO_ERROR_INVALID_HANDLE);

    try {
        const auto& ctrl = data->reader->get_control_data();

        info->num_nodes = ctrl.NUMNP;
        info->num_solids = ctrl.NEL8;
        info->num_shells = ctrl.NEL4;
        info->num_beams = ctrl.NEL2;
        info->num_thick_shells = ctrl.NELT;

        return set_error(KOO_SUCCESS);
    }
    catch (const std::exception&) {
        return set_error(KOO_ERROR_READ_FAILED);
    }
}

KOO_API int32_t koo_get_num_states(koo_handle_t handle) {
    auto* data = get_handle(handle);
    if (!data || !data->reader) {
        set_error(KOO_ERROR_INVALID_HANDLE);
        return -1;
    }

    // Use cached states
    if (!ensure_states_loaded(data)) {
        set_error(KOO_ERROR_READ_FAILED);
        return -1;
    }

    return static_cast<int32_t>(data->states.size());
}

KOO_API double koo_get_state_time(koo_handle_t handle, int32_t state_index) {
    auto* data = get_handle(handle);
    if (!data || !data->reader) {
        set_error(KOO_ERROR_INVALID_HANDLE);
        return -1.0;
    }

    // Use cached states
    if (!ensure_states_loaded(data)) {
        set_error(KOO_ERROR_READ_FAILED);
        return -1.0;
    }

    if (state_index < 0 || state_index >= static_cast<int32_t>(data->states.size())) {
        set_error(KOO_ERROR_INVALID_INDEX);
        return -1.0;
    }

    return data->states[state_index].time;
}

/*============================================================================
 * Mesh Data Reading - Helper to ensure mesh is loaded
 *============================================================================*/

static bool ensure_mesh_loaded(HandleData* data) {
    if (data->mesh_loaded) return true;

    try {
        data->mesh = data->reader->read_mesh();
        data->mesh_loaded = true;
        return true;
    }
    catch (const std::exception&) {
        return false;
    }
}

/*============================================================================
 * State Data Reading - Helper to ensure states are loaded (cached)
 *============================================================================*/

static bool ensure_states_loaded(HandleData* data) {
    if (data->states_loaded) return true;

    try {
        data->states = data->reader->read_all_states();
        data->states_loaded = true;
        return true;
    }
    catch (const std::exception&) {
        return false;
    }
}

KOO_API koo_error_t koo_read_nodes(koo_handle_t handle, float* buffer, int32_t buffer_size) {
    if (!buffer) return set_error(KOO_ERROR_INVALID_HANDLE);

    auto* data = get_handle(handle);
    if (!data || !data->reader) return set_error(KOO_ERROR_INVALID_HANDLE);

    if (!ensure_mesh_loaded(data)) return set_error(KOO_ERROR_READ_FAILED);

    try {
        const auto& nodes = data->mesh.nodes;
        int32_t required = static_cast<int32_t>(nodes.size() * 3);
        if (buffer_size < required) return set_error(KOO_ERROR_OUT_OF_MEMORY);

        for (size_t i = 0; i < nodes.size(); i++) {
            buffer[i * 3 + 0] = static_cast<float>(nodes[i].x);
            buffer[i * 3 + 1] = static_cast<float>(nodes[i].y);
            buffer[i * 3 + 2] = static_cast<float>(nodes[i].z);
        }

        return set_error(KOO_SUCCESS);
    }
    catch (const std::exception&) {
        return set_error(KOO_ERROR_READ_FAILED);
    }
}

KOO_API koo_error_t koo_read_nodes_double(koo_handle_t handle, double* buffer, int32_t buffer_size) {
    if (!buffer) return set_error(KOO_ERROR_INVALID_HANDLE);

    auto* data = get_handle(handle);
    if (!data || !data->reader) return set_error(KOO_ERROR_INVALID_HANDLE);

    if (!ensure_mesh_loaded(data)) return set_error(KOO_ERROR_READ_FAILED);

    try {
        const auto& nodes = data->mesh.nodes;
        int32_t required = static_cast<int32_t>(nodes.size() * 3);
        if (buffer_size < required) return set_error(KOO_ERROR_OUT_OF_MEMORY);

        for (size_t i = 0; i < nodes.size(); i++) {
            buffer[i * 3 + 0] = nodes[i].x;
            buffer[i * 3 + 1] = nodes[i].y;
            buffer[i * 3 + 2] = nodes[i].z;
        }

        return set_error(KOO_SUCCESS);
    }
    catch (const std::exception&) {
        return set_error(KOO_ERROR_READ_FAILED);
    }
}

KOO_API koo_error_t koo_read_node_ids(koo_handle_t handle, int32_t* buffer, int32_t buffer_size) {
    if (!buffer) return set_error(KOO_ERROR_INVALID_HANDLE);

    auto* data = get_handle(handle);
    if (!data || !data->reader) return set_error(KOO_ERROR_INVALID_HANDLE);

    if (!ensure_mesh_loaded(data)) return set_error(KOO_ERROR_READ_FAILED);

    try {
        const auto& ids = data->mesh.real_node_ids;
        int32_t required = static_cast<int32_t>(ids.size());
        if (buffer_size < required) return set_error(KOO_ERROR_OUT_OF_MEMORY);

        std::memcpy(buffer, ids.data(), ids.size() * sizeof(int32_t));

        return set_error(KOO_SUCCESS);
    }
    catch (const std::exception&) {
        return set_error(KOO_ERROR_READ_FAILED);
    }
}

KOO_API koo_error_t koo_read_solid_connectivity(koo_handle_t handle, int32_t* buffer, int32_t buffer_size) {
    if (!buffer) return set_error(KOO_ERROR_INVALID_HANDLE);

    auto* data = get_handle(handle);
    if (!data || !data->reader) return set_error(KOO_ERROR_INVALID_HANDLE);

    if (!ensure_mesh_loaded(data)) return set_error(KOO_ERROR_READ_FAILED);

    try {
        const auto& solids = data->mesh.solids;
        int32_t required = static_cast<int32_t>(solids.size() * 8);
        if (buffer_size < required) return set_error(KOO_ERROR_OUT_OF_MEMORY);

        for (size_t i = 0; i < solids.size(); i++) {
            for (size_t j = 0; j < 8 && j < solids[i].node_ids.size(); j++) {
                buffer[i * 8 + j] = solids[i].node_ids[j];
            }
            // Pad with -1 if less than 8 nodes
            for (size_t j = solids[i].node_ids.size(); j < 8; j++) {
                buffer[i * 8 + j] = -1;
            }
        }

        return set_error(KOO_SUCCESS);
    }
    catch (const std::exception&) {
        return set_error(KOO_ERROR_READ_FAILED);
    }
}

KOO_API koo_error_t koo_read_solid_part_ids(koo_handle_t handle, int32_t* buffer, int32_t buffer_size) {
    if (!buffer) return set_error(KOO_ERROR_INVALID_HANDLE);

    auto* data = get_handle(handle);
    if (!data || !data->reader) return set_error(KOO_ERROR_INVALID_HANDLE);

    if (!ensure_mesh_loaded(data)) return set_error(KOO_ERROR_READ_FAILED);

    try {
        const auto& parts = data->mesh.solid_parts;
        int32_t required = static_cast<int32_t>(parts.size());
        if (buffer_size < required) return set_error(KOO_ERROR_OUT_OF_MEMORY);

        std::memcpy(buffer, parts.data(), parts.size() * sizeof(int32_t));

        return set_error(KOO_SUCCESS);
    }
    catch (const std::exception&) {
        return set_error(KOO_ERROR_READ_FAILED);
    }
}

KOO_API koo_error_t koo_read_shell_connectivity(koo_handle_t handle, int32_t* buffer, int32_t buffer_size) {
    if (!buffer) return set_error(KOO_ERROR_INVALID_HANDLE);

    auto* data = get_handle(handle);
    if (!data || !data->reader) return set_error(KOO_ERROR_INVALID_HANDLE);

    if (!ensure_mesh_loaded(data)) return set_error(KOO_ERROR_READ_FAILED);

    try {
        const auto& shells = data->mesh.shells;
        int32_t required = static_cast<int32_t>(shells.size() * 4);
        if (buffer_size < required) return set_error(KOO_ERROR_OUT_OF_MEMORY);

        for (size_t i = 0; i < shells.size(); i++) {
            for (size_t j = 0; j < 4 && j < shells[i].node_ids.size(); j++) {
                buffer[i * 4 + j] = shells[i].node_ids[j];
            }
            for (size_t j = shells[i].node_ids.size(); j < 4; j++) {
                buffer[i * 4 + j] = -1;
            }
        }

        return set_error(KOO_SUCCESS);
    }
    catch (const std::exception&) {
        return set_error(KOO_ERROR_READ_FAILED);
    }
}

KOO_API koo_error_t koo_read_shell_part_ids(koo_handle_t handle, int32_t* buffer, int32_t buffer_size) {
    if (!buffer) return set_error(KOO_ERROR_INVALID_HANDLE);

    auto* data = get_handle(handle);
    if (!data || !data->reader) return set_error(KOO_ERROR_INVALID_HANDLE);

    if (!ensure_mesh_loaded(data)) return set_error(KOO_ERROR_READ_FAILED);

    try {
        const auto& parts = data->mesh.shell_parts;
        int32_t required = static_cast<int32_t>(parts.size());
        if (buffer_size < required) return set_error(KOO_ERROR_OUT_OF_MEMORY);

        std::memcpy(buffer, parts.data(), parts.size() * sizeof(int32_t));

        return set_error(KOO_SUCCESS);
    }
    catch (const std::exception&) {
        return set_error(KOO_ERROR_READ_FAILED);
    }
}

KOO_API koo_error_t koo_read_beam_connectivity(koo_handle_t handle, int32_t* buffer, int32_t buffer_size) {
    if (!buffer) return set_error(KOO_ERROR_INVALID_HANDLE);

    auto* data = get_handle(handle);
    if (!data || !data->reader) return set_error(KOO_ERROR_INVALID_HANDLE);

    if (!ensure_mesh_loaded(data)) return set_error(KOO_ERROR_READ_FAILED);

    try {
        const auto& beams = data->mesh.beams;
        int32_t required = static_cast<int32_t>(beams.size() * 2);
        if (buffer_size < required) return set_error(KOO_ERROR_OUT_OF_MEMORY);

        for (size_t i = 0; i < beams.size(); i++) {
            for (size_t j = 0; j < 2 && j < beams[i].node_ids.size(); j++) {
                buffer[i * 2 + j] = beams[i].node_ids[j];
            }
            for (size_t j = beams[i].node_ids.size(); j < 2; j++) {
                buffer[i * 2 + j] = -1;
            }
        }

        return set_error(KOO_SUCCESS);
    }
    catch (const std::exception&) {
        return set_error(KOO_ERROR_READ_FAILED);
    }
}

/*============================================================================
 * State Data Reading - Helper to ensure state is loaded (uses cached states)
 *============================================================================*/

static bool ensure_state_loaded(HandleData* data, int32_t state_index) {
    if (state_index < 0) return false;

    // Ensure all states are loaded first
    if (!ensure_states_loaded(data)) return false;

    // Check index bounds
    size_t idx = static_cast<size_t>(state_index);
    if (idx >= data->states.size()) return false;

    return true;
}

KOO_API koo_error_t koo_read_displacement(koo_handle_t handle, int32_t state_index,
                                          float* buffer, int32_t buffer_size) {
    if (!buffer) return set_error(KOO_ERROR_INVALID_HANDLE);

    auto* data = get_handle(handle);
    if (!data || !data->reader) return set_error(KOO_ERROR_INVALID_HANDLE);

    if (!ensure_state_loaded(data, state_index)) return set_error(KOO_ERROR_READ_FAILED);

    try {
        const auto& disp = data->states[state_index].node_displacements;
        int32_t required = static_cast<int32_t>(disp.size());
        if (buffer_size < required) return set_error(KOO_ERROR_OUT_OF_MEMORY);

        for (size_t i = 0; i < disp.size(); i++) {
            buffer[i] = static_cast<float>(disp[i]);
        }

        return set_error(KOO_SUCCESS);
    }
    catch (const std::exception&) {
        return set_error(KOO_ERROR_READ_FAILED);
    }
}

KOO_API koo_error_t koo_read_velocity(koo_handle_t handle, int32_t state_index,
                                      float* buffer, int32_t buffer_size) {
    if (!buffer) return set_error(KOO_ERROR_INVALID_HANDLE);

    auto* data = get_handle(handle);
    if (!data || !data->reader) return set_error(KOO_ERROR_INVALID_HANDLE);

    if (!ensure_state_loaded(data, state_index)) return set_error(KOO_ERROR_READ_FAILED);

    try {
        const auto& vel = data->states[state_index].node_velocities;
        int32_t required = static_cast<int32_t>(vel.size());
        if (buffer_size < required) return set_error(KOO_ERROR_OUT_OF_MEMORY);

        for (size_t i = 0; i < vel.size(); i++) {
            buffer[i] = static_cast<float>(vel[i]);
        }

        return set_error(KOO_SUCCESS);
    }
    catch (const std::exception&) {
        return set_error(KOO_ERROR_READ_FAILED);
    }
}

KOO_API koo_error_t koo_read_acceleration(koo_handle_t handle, int32_t state_index,
                                          float* buffer, int32_t buffer_size) {
    if (!buffer) return set_error(KOO_ERROR_INVALID_HANDLE);

    auto* data = get_handle(handle);
    if (!data || !data->reader) return set_error(KOO_ERROR_INVALID_HANDLE);

    if (!ensure_state_loaded(data, state_index)) return set_error(KOO_ERROR_READ_FAILED);

    try {
        const auto& acc = data->states[state_index].node_accelerations;
        int32_t required = static_cast<int32_t>(acc.size());
        if (buffer_size < required) return set_error(KOO_ERROR_OUT_OF_MEMORY);

        for (size_t i = 0; i < acc.size(); i++) {
            buffer[i] = static_cast<float>(acc[i]);
        }

        return set_error(KOO_SUCCESS);
    }
    catch (const std::exception&) {
        return set_error(KOO_ERROR_READ_FAILED);
    }
}

KOO_API koo_error_t koo_read_solid_stress(koo_handle_t handle, int32_t state_index,
                                          float* buffer, int32_t buffer_size) {
    if (!buffer) return set_error(KOO_ERROR_INVALID_HANDLE);

    auto* data = get_handle(handle);
    if (!data || !data->reader) return set_error(KOO_ERROR_INVALID_HANDLE);

    if (!ensure_state_loaded(data, state_index)) return set_error(KOO_ERROR_READ_FAILED);

    try {
        const auto& stress = data->states[state_index].solid_data;
        int32_t required = static_cast<int32_t>(stress.size());
        if (buffer_size < required) return set_error(KOO_ERROR_OUT_OF_MEMORY);

        for (size_t i = 0; i < stress.size(); i++) {
            buffer[i] = static_cast<float>(stress[i]);
        }

        return set_error(KOO_SUCCESS);
    }
    catch (const std::exception&) {
        return set_error(KOO_ERROR_READ_FAILED);
    }
}

KOO_API koo_error_t koo_read_shell_stress(koo_handle_t handle, int32_t state_index,
                                          float* buffer, int32_t buffer_size) {
    if (!buffer) return set_error(KOO_ERROR_INVALID_HANDLE);

    auto* data = get_handle(handle);
    if (!data || !data->reader) return set_error(KOO_ERROR_INVALID_HANDLE);

    if (!ensure_state_loaded(data, state_index)) return set_error(KOO_ERROR_READ_FAILED);

    try {
        const auto& stress = data->states[state_index].shell_data;
        int32_t required = static_cast<int32_t>(stress.size());
        if (buffer_size < required) return set_error(KOO_ERROR_OUT_OF_MEMORY);

        for (size_t i = 0; i < stress.size(); i++) {
            buffer[i] = static_cast<float>(stress[i]);
        }

        return set_error(KOO_SUCCESS);
    }
    catch (const std::exception&) {
        return set_error(KOO_ERROR_READ_FAILED);
    }
}

/*============================================================================
 * Utility Functions
 *============================================================================*/

KOO_API const char* koo_get_version(void) {
    static std::string version = kood3plot::Version::get_version_string();
    return version.c_str();
}

KOO_API float koo_calc_von_mises(float sigma_xx, float sigma_yy, float sigma_zz,
                                  float tau_xy, float tau_yz, float tau_zx) {
    float a = (sigma_xx - sigma_yy) * (sigma_xx - sigma_yy);
    float b = (sigma_yy - sigma_zz) * (sigma_yy - sigma_zz);
    float c = (sigma_zz - sigma_xx) * (sigma_zz - sigma_xx);
    float d = 6.0f * (tau_xy * tau_xy + tau_yz * tau_yz + tau_zx * tau_zx);

    return std::sqrt(0.5f * (a + b + c + d));
}
