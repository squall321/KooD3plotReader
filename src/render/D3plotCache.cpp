#include "kood3plot/render/D3plotCache.h"
#include "kood3plot/render/GeometryAnalyzer.h"
#include <iostream>
#include <iomanip>
#include <algorithm>

namespace kood3plot {
namespace render {

// ============================================================
// Implementation details (Pimpl idiom)
// ============================================================

struct D3plotCache::Impl {
    // Cache storage
    std::map<CacheKey, CacheEntry<std::shared_ptr<data::Mesh>>> mesh_cache;
    std::map<CacheKey, CacheEntry<BoundingBox>> bbox_cache;
    std::map<CacheKey, CacheEntry<std::shared_ptr<data::ControlData>>> control_cache;

    // LRU tracking
    std::list<CacheKey> lru_list;
    std::map<CacheKey, std::list<CacheKey>::iterator> lru_map;

    // Configuration
    size_t max_memory_bytes;
    size_t max_age_seconds;

    // Statistics
    mutable CacheStats stats;

    // Thread safety
    mutable std::mutex mutex;

    Impl(size_t max_memory_mb, size_t max_age_sec)
        : max_memory_bytes(max_memory_mb * 1024 * 1024)
        , max_age_seconds(max_age_sec)
    {}

    void touchKey(const CacheKey& key) {
        auto it = lru_map.find(key);
        if (it != lru_map.end()) {
            lru_list.erase(it->second);
        }
        lru_list.push_front(key);
        lru_map[key] = lru_list.begin();
    }

    void removeKey(const CacheKey& key) {
        auto it = lru_map.find(key);
        if (it != lru_map.end()) {
            lru_list.erase(it->second);
            lru_map.erase(it);
        }
    }

    size_t getTotalMemoryUsage() const {
        size_t total = 0;

        for (const auto& pair : mesh_cache) {
            total += pair.second.size_bytes;
        }

        for (const auto& pair : bbox_cache) {
            total += pair.second.size_bytes;
        }

        for (const auto& pair : control_cache) {
            total += pair.second.size_bytes;
        }

        return total;
    }

    bool isExpired(const std::chrono::steady_clock::time_point& timestamp) const {
        if (max_age_seconds == 0) return false;

        auto now = std::chrono::steady_clock::now();
        auto age = std::chrono::duration_cast<std::chrono::seconds>(now - timestamp);
        return age.count() >= static_cast<long>(max_age_seconds);
    }

    void clearExpiredEntries() {
        // Clear expired mesh entries
        for (auto it = mesh_cache.begin(); it != mesh_cache.end();) {
            if (isExpired(it->second.timestamp)) {
                removeKey(it->first);
                it = mesh_cache.erase(it);
            } else {
                ++it;
            }
        }

        // Clear expired bbox entries
        for (auto it = bbox_cache.begin(); it != bbox_cache.end();) {
            if (isExpired(it->second.timestamp)) {
                removeKey(it->first);
                it = bbox_cache.erase(it);
            } else {
                ++it;
            }
        }

        // Clear expired control entries
        for (auto it = control_cache.begin(); it != control_cache.end();) {
            if (isExpired(it->second.timestamp)) {
                removeKey(it->first);
                it = control_cache.erase(it);
            } else {
                ++it;
            }
        }
    }

    void evictLRUEntry() {
        if (lru_list.empty()) return;

        // Get least recently used key
        CacheKey lru_key = lru_list.back();

        // Remove from all possible caches
        mesh_cache.erase(lru_key);
        bbox_cache.erase(lru_key);
        control_cache.erase(lru_key);

        // Remove from LRU tracking
        removeKey(lru_key);
    }
};

// ============================================================
// D3plotCache implementation
// ============================================================

D3plotCache::D3plotCache(size_t max_memory_mb, size_t max_age_seconds)
    : pImpl(std::make_unique<Impl>(max_memory_mb, max_age_seconds))
{}

D3plotCache::~D3plotCache() = default;

// Mesh caching
bool D3plotCache::hasMesh(const std::string& d3plot_path) {
    std::lock_guard<std::mutex> lock(pImpl->mutex);
    CacheKey key(d3plot_path, "mesh");
    return pImpl->mesh_cache.find(key) != pImpl->mesh_cache.end();
}

std::shared_ptr<data::Mesh> D3plotCache::getMesh(const std::string& d3plot_path) {
    std::lock_guard<std::mutex> lock(pImpl->mutex);
    CacheKey key(d3plot_path, "mesh");

    auto it = pImpl->mesh_cache.find(key);
    if (it != pImpl->mesh_cache.end()) {
        // Check if expired
        if (pImpl->isExpired(it->second.timestamp)) {
            pImpl->mesh_cache.erase(it);
            pImpl->removeKey(key);
            pImpl->stats.recordMiss();
            return nullptr;
        }

        // Update access statistics
        it->second.access_count++;
        pImpl->touchKey(key);
        pImpl->stats.recordHit();
        return it->second.data;
    }

    pImpl->stats.recordMiss();
    return nullptr;
}

void D3plotCache::putMesh(const std::string& d3plot_path, std::shared_ptr<data::Mesh> mesh) {
    std::lock_guard<std::mutex> lock(pImpl->mutex);

    if (!mesh) return;

    CacheKey key(d3plot_path, "mesh");
    size_t size = estimateMeshSize(*mesh);

    // Create cache entry
    CacheEntry<std::shared_ptr<data::Mesh>> entry(mesh, size);
    pImpl->mesh_cache.insert_or_assign(key, entry);
    pImpl->touchKey(key);

    // Enforce memory limits
    enforceMemoryLimit();
}

// Bounding box caching
bool D3plotCache::hasBoundingBox(const std::string& d3plot_path, int part_id, size_t state_index) {
    std::lock_guard<std::mutex> lock(pImpl->mutex);
    CacheKey key(d3plot_path, "bbox", part_id, state_index);
    return pImpl->bbox_cache.find(key) != pImpl->bbox_cache.end();
}

BoundingBox D3plotCache::getBoundingBox(const std::string& d3plot_path, int part_id, size_t state_index) {
    std::lock_guard<std::mutex> lock(pImpl->mutex);
    CacheKey key(d3plot_path, "bbox", part_id, state_index);

    auto it = pImpl->bbox_cache.find(key);
    if (it != pImpl->bbox_cache.end()) {
        // Check if expired
        if (pImpl->isExpired(it->second.timestamp)) {
            pImpl->bbox_cache.erase(it);
            pImpl->removeKey(key);
            pImpl->stats.recordMiss();
            return BoundingBox();
        }

        // Update access statistics
        it->second.access_count++;
        pImpl->touchKey(key);
        pImpl->stats.recordHit();
        return it->second.data;
    }

    pImpl->stats.recordMiss();
    return BoundingBox();
}

void D3plotCache::putBoundingBox(const std::string& d3plot_path, int part_id,
                                 size_t state_index, const BoundingBox& bbox) {
    std::lock_guard<std::mutex> lock(pImpl->mutex);

    CacheKey key(d3plot_path, "bbox", part_id, state_index);
    size_t size = sizeof(BoundingBox);

    // Create cache entry
    CacheEntry<BoundingBox> entry(bbox, size);
    pImpl->bbox_cache.insert_or_assign(key, entry);
    pImpl->touchKey(key);

    // Enforce memory limits
    enforceMemoryLimit();
}

// Control data caching
bool D3plotCache::hasControlData(const std::string& d3plot_path) {
    std::lock_guard<std::mutex> lock(pImpl->mutex);
    CacheKey key(d3plot_path, "control");
    return pImpl->control_cache.find(key) != pImpl->control_cache.end();
}

std::shared_ptr<data::ControlData> D3plotCache::getControlData(const std::string& d3plot_path) {
    std::lock_guard<std::mutex> lock(pImpl->mutex);
    CacheKey key(d3plot_path, "control");

    auto it = pImpl->control_cache.find(key);
    if (it != pImpl->control_cache.end()) {
        // Check if expired
        if (pImpl->isExpired(it->second.timestamp)) {
            pImpl->control_cache.erase(it);
            pImpl->removeKey(key);
            pImpl->stats.recordMiss();
            return nullptr;
        }

        // Update access statistics
        it->second.access_count++;
        pImpl->touchKey(key);
        pImpl->stats.recordHit();
        return it->second.data;
    }

    pImpl->stats.recordMiss();
    return nullptr;
}

void D3plotCache::putControlData(const std::string& d3plot_path,
                                 std::shared_ptr<data::ControlData> control) {
    std::lock_guard<std::mutex> lock(pImpl->mutex);

    if (!control) return;

    CacheKey key(d3plot_path, "control");
    size_t size = sizeof(data::ControlData); // Approximate

    // Create cache entry
    CacheEntry<std::shared_ptr<data::ControlData>> entry(control, size);
    pImpl->control_cache.insert_or_assign(key, entry);
    pImpl->touchKey(key);

    // Enforce memory limits
    enforceMemoryLimit();
}

// Cache management
void D3plotCache::clear() {
    std::lock_guard<std::mutex> lock(pImpl->mutex);
    pImpl->mesh_cache.clear();
    pImpl->bbox_cache.clear();
    pImpl->control_cache.clear();
    pImpl->lru_list.clear();
    pImpl->lru_map.clear();
}

void D3plotCache::clearOldEntries() {
    std::lock_guard<std::mutex> lock(pImpl->mutex);
    pImpl->clearExpiredEntries();
}

void D3plotCache::evictLRU() {
    std::lock_guard<std::mutex> lock(pImpl->mutex);
    pImpl->evictLRUEntry();
}

// Statistics
CacheStats D3plotCache::getStats() const {
    std::lock_guard<std::mutex> lock(pImpl->mutex);
    pImpl->stats.total_entries = pImpl->mesh_cache.size() +
                                 pImpl->bbox_cache.size() +
                                 pImpl->control_cache.size();
    pImpl->stats.total_memory_bytes = pImpl->getTotalMemoryUsage();
    return pImpl->stats;
}

void D3plotCache::resetStats() {
    std::lock_guard<std::mutex> lock(pImpl->mutex);
    pImpl->stats = CacheStats();
}

void D3plotCache::printStats() const {
    auto stats = getStats();

    std::cout << "\n=== D3plot Cache Statistics ===\n";
    std::cout << "Total Requests: " << stats.total_requests << "\n";
    std::cout << "Cache Hits: " << stats.cache_hits << "\n";
    std::cout << "Cache Misses: " << stats.cache_misses << "\n";
    std::cout << "Hit Rate: " << std::fixed << std::setprecision(2)
              << (stats.getHitRate() * 100.0) << "%\n";
    std::cout << "Total Entries: " << stats.total_entries << "\n";
    std::cout << "Memory Usage: "
              << (stats.total_memory_bytes / (1024.0 * 1024.0))
              << " MB\n";
    std::cout << "==============================\n\n";
}

// Configuration
void D3plotCache::setMaxMemory(size_t max_memory_mb) {
    std::lock_guard<std::mutex> lock(pImpl->mutex);
    pImpl->max_memory_bytes = max_memory_mb * 1024 * 1024;
    enforceMemoryLimit();
}

void D3plotCache::setMaxAge(size_t max_age_seconds) {
    std::lock_guard<std::mutex> lock(pImpl->mutex);
    pImpl->max_age_seconds = max_age_seconds;
}

// Private helpers
size_t D3plotCache::estimateMeshSize(const data::Mesh& mesh) const {
    size_t size = 0;

    // Nodes
    size += mesh.nodes.size() * sizeof(Node);

    // Elements
    size += mesh.solids.size() * sizeof(Element);
    size += mesh.thick_shells.size() * sizeof(Element);
    size += mesh.beams.size() * sizeof(Element);
    size += mesh.shells.size() * sizeof(Element);

    // Part IDs
    size += mesh.solid_parts.size() * sizeof(int32_t);
    size += mesh.thick_shell_parts.size() * sizeof(int32_t);
    size += mesh.beam_parts.size() * sizeof(int32_t);
    size += mesh.shell_parts.size() * sizeof(int32_t);

    // Real IDs (if present)
    size += mesh.real_node_ids.size() * sizeof(int32_t);
    size += mesh.real_solid_ids.size() * sizeof(int32_t);
    size += mesh.real_beam_ids.size() * sizeof(int32_t);
    size += mesh.real_shell_ids.size() * sizeof(int32_t);
    size += mesh.real_thick_shell_ids.size() * sizeof(int32_t);

    return size;
}

size_t D3plotCache::getCurrentMemoryUsage() const {
    // Note: mutex should already be locked by caller
    return pImpl->getTotalMemoryUsage();
}

void D3plotCache::enforceMemoryLimit() {
    // Note: mutex should already be locked by caller
    if (pImpl->max_memory_bytes == 0) return;

    // First clear expired entries
    pImpl->clearExpiredEntries();

    // Then evict LRU entries if still over limit
    while (getCurrentMemoryUsage() > pImpl->max_memory_bytes && !pImpl->lru_list.empty()) {
        pImpl->evictLRUEntry();
    }
}

// Global cache instance
D3plotCache& getGlobalCache() {
    static D3plotCache global_cache(1024, 3600); // 1GB, 1 hour
    return global_cache;
}

} // namespace render
} // namespace kood3plot
