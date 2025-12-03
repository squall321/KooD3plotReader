#ifndef KOOD3PLOT_D3PLOT_CACHE_H
#define KOOD3PLOT_D3PLOT_CACHE_H

#include <string>
#include <memory>
#include <chrono>
#include <map>
#include <list>
#include <mutex>
#include <functional>
#include "kood3plot/data/Mesh.hpp"
#include "kood3plot/data/ControlData.hpp"

namespace kood3plot {
namespace render {

// Forward declarations
struct BoundingBox;

/**
 * @brief Cache key for identifying cached data
 */
struct CacheKey {
    std::string file_path;
    std::string data_type;  // "mesh", "bbox", "control"
    int part_id;            // For part-specific data, -1 for all
    size_t state_index;     // For state-specific data, -1 for N/A

    CacheKey(const std::string& path, const std::string& type,
             int pid = -1, size_t state = static_cast<size_t>(-1))
        : file_path(path), data_type(type), part_id(pid), state_index(state) {}

    bool operator<(const CacheKey& other) const {
        if (file_path != other.file_path) return file_path < other.file_path;
        if (data_type != other.data_type) return data_type < other.data_type;
        if (part_id != other.part_id) return part_id < other.part_id;
        return state_index < other.state_index;
    }

    bool operator==(const CacheKey& other) const {
        return file_path == other.file_path &&
               data_type == other.data_type &&
               part_id == other.part_id &&
               state_index == other.state_index;
    }
};

/**
 * @brief Generic cache entry
 */
template<typename T>
struct CacheEntry {
    T data;
    std::chrono::steady_clock::time_point timestamp;
    size_t access_count;
    size_t size_bytes;  // Approximate memory usage

    CacheEntry(const T& d, size_t size = 0)
        : data(d)
        , timestamp(std::chrono::steady_clock::now())
        , access_count(0)
        , size_bytes(size)
    {}
};

/**
 * @brief Cache statistics
 */
struct CacheStats {
    size_t total_requests = 0;
    size_t cache_hits = 0;
    size_t cache_misses = 0;
    size_t total_entries = 0;
    size_t total_memory_bytes = 0;

    double getHitRate() const {
        return total_requests > 0
            ? static_cast<double>(cache_hits) / total_requests
            : 0.0;
    }

    void recordHit() {
        ++total_requests;
        ++cache_hits;
    }

    void recordMiss() {
        ++total_requests;
        ++cache_misses;
    }
};

/**
 * @brief LRU cache for D3plot data
 *
 * Thread-safe cache implementation with LRU eviction policy.
 * Supports caching of:
 * - Mesh geometry
 * - Bounding boxes (per part)
 * - Control data
 */
class D3plotCache {
public:
    /**
     * @brief Constructor
     * @param max_memory_mb Maximum memory usage in MB (0 = unlimited)
     * @param max_age_seconds Maximum age of cache entries in seconds (0 = unlimited)
     */
    explicit D3plotCache(size_t max_memory_mb = 1024,
                        size_t max_age_seconds = 3600);

    ~D3plotCache();

    // Mesh caching
    bool hasMesh(const std::string& d3plot_path);
    std::shared_ptr<data::Mesh> getMesh(const std::string& d3plot_path);
    void putMesh(const std::string& d3plot_path, std::shared_ptr<data::Mesh> mesh);

    // Bounding box caching
    bool hasBoundingBox(const std::string& d3plot_path, int part_id, size_t state_index);
    BoundingBox getBoundingBox(const std::string& d3plot_path, int part_id, size_t state_index);
    void putBoundingBox(const std::string& d3plot_path, int part_id, size_t state_index,
                       const BoundingBox& bbox);

    // Control data caching
    bool hasControlData(const std::string& d3plot_path);
    std::shared_ptr<data::ControlData> getControlData(const std::string& d3plot_path);
    void putControlData(const std::string& d3plot_path, std::shared_ptr<data::ControlData> control);

    // Cache management
    void clear();
    void clearOldEntries();
    void evictLRU();

    // Statistics
    CacheStats getStats() const;
    void resetStats();
    void printStats() const;

    // Configuration
    void setMaxMemory(size_t max_memory_mb);
    void setMaxAge(size_t max_age_seconds);

private:
    struct Impl;
    std::unique_ptr<Impl> pImpl;

    // Helper methods
    template<typename T>
    bool hasEntry(const CacheKey& key);

    template<typename T>
    std::shared_ptr<T> getEntry(const CacheKey& key);

    template<typename T>
    void putEntry(const CacheKey& key, std::shared_ptr<T> data, size_t size_bytes);

    void touchEntry(const CacheKey& key);
    size_t estimateMeshSize(const data::Mesh& mesh) const;
    size_t getCurrentMemoryUsage() const;
    void enforceMemoryLimit();
};

/**
 * @brief Global cache instance accessor
 *
 * Returns a singleton cache instance that can be shared across
 * the application. This is useful for MultiRunProcessor where
 * multiple runs may access the same d3plot file.
 */
D3plotCache& getGlobalCache();

/**
 * @brief RAII cache scope guard
 *
 * Automatically clears cache when going out of scope.
 * Useful for ensuring cache is cleaned up after processing.
 */
class CacheScopeGuard {
public:
    explicit CacheScopeGuard(D3plotCache& cache, bool clear_on_exit = true)
        : cache_(cache), clear_on_exit_(clear_on_exit) {}

    ~CacheScopeGuard() {
        if (clear_on_exit_) {
            cache_.clear();
        }
    }

    // Non-copyable
    CacheScopeGuard(const CacheScopeGuard&) = delete;
    CacheScopeGuard& operator=(const CacheScopeGuard&) = delete;

private:
    D3plotCache& cache_;
    bool clear_on_exit_;
};

} // namespace render
} // namespace kood3plot

#endif // KOOD3PLOT_D3PLOT_CACHE_H
