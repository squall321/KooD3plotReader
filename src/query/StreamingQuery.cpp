/**
 * @file StreamingQuery.cpp
 * @brief Implementation of StreamingQuery for large-scale d3plot processing
 * @author KooD3plot V3 Development Team
 * @date 2025-12-02
 * @version 3.1.0
 */

// Standard library includes first (before any project headers)
#include <algorithm>
#include <chrono>
#include <cmath>
#include <fstream>
#include <iomanip>
#include <limits>
#include <queue>
#include <ratio>
#include <set>
#include <sstream>
#include <string>

// Project headers
#include "kood3plot/query/StreamingQuery.hpp"
#include "kood3plot/data/ControlData.hpp"
#include "kood3plot/data/Mesh.hpp"
#include "kood3plot/data/StateData.hpp"

namespace kood3plot {
namespace query {

// ============================================================
// Helper Functions
// ============================================================

namespace {

/**
 * @brief Calculate Von Mises stress from 6 stress components
 */
double calculateVonMises(double sx, double sy, double sz,
                        double txy, double tyz, double tzx) {
    double d1 = sx - sy;
    double d2 = sy - sz;
    double d3 = sz - sx;
    return std::sqrt(0.5 * (d1*d1 + d2*d2 + d3*d3) + 3.0 * (txy*txy + tyz*tyz + tzx*tzx));
}

/**
 * @brief Calculate hydrostatic pressure
 */
double calculatePressure(double sx, double sy, double sz) {
    return -(sx + sy + sz) / 3.0;
}

/**
 * @brief Calculate magnitude
 */
double calculateMagnitude(double x, double y, double z) {
    return std::sqrt(x*x + y*y + z*z);
}

/**
 * @brief Online statistics calculator (Welford's algorithm)
 */
class OnlineStats {
public:
    void update(double value) {
        count_++;
        double delta = value - mean_;
        mean_ += delta / count_;
        double delta2 = value - mean_;
        m2_ += delta * delta2;

        if (value < min_) min_ = value;
        if (value > max_) max_ = value;
        sum_ += value;
    }

    size_t count() const { return count_; }
    double mean() const { return mean_; }
    double variance() const { return count_ > 1 ? m2_ / (count_ - 1) : 0.0; }
    double stddev() const { return std::sqrt(variance()); }
    double min() const { return min_; }
    double max() const { return max_; }
    double sum() const { return sum_; }

private:
    size_t count_ = 0;
    double mean_ = 0.0;
    double m2_ = 0.0;
    double min_ = std::numeric_limits<double>::max();
    double max_ = std::numeric_limits<double>::lowest();
    double sum_ = 0.0;
};

} // anonymous namespace

// ============================================================
// StreamingQueryIterator Implementation
// ============================================================

struct StreamingQueryIterator::Impl {
    StreamingQuery* query = nullptr;
    std::vector<ResultDataPoint> current_buffer;
    size_t buffer_index = 0;
    size_t global_index = 0;
    int current_state_index = 0;
    std::vector<int> state_indices;
    size_t state_position = 0;
    bool at_end = true;

    Impl() = default;
};

StreamingQueryIterator::StreamingQueryIterator()
    : pImpl(std::make_shared<Impl>())
{
}

StreamingQueryIterator::StreamingQueryIterator(StreamingQuery* query)
    : pImpl(std::make_shared<Impl>())
{
    pImpl->query = query;
    pImpl->at_end = false;

    // Initialize state indices from query
    // This will be done in advance()
    advance();
}

StreamingQueryIterator::StreamingQueryIterator(const StreamingQueryIterator& other)
    : pImpl(other.pImpl)
{
}

StreamingQueryIterator::StreamingQueryIterator(StreamingQueryIterator&& other) noexcept
    : pImpl(std::move(other.pImpl))
{
}

StreamingQueryIterator::~StreamingQueryIterator() = default;

StreamingQueryIterator::reference StreamingQueryIterator::operator*() const {
    return pImpl->current_buffer[pImpl->buffer_index];
}

StreamingQueryIterator::pointer StreamingQueryIterator::operator->() const {
    return &pImpl->current_buffer[pImpl->buffer_index];
}

StreamingQueryIterator& StreamingQueryIterator::operator++() {
    advance();
    return *this;
}

StreamingQueryIterator StreamingQueryIterator::operator++(int) {
    StreamingQueryIterator tmp(*this);
    advance();
    return tmp;
}

bool StreamingQueryIterator::operator==(const StreamingQueryIterator& other) const {
    // Both at end
    if (pImpl->at_end && other.pImpl->at_end) return true;
    // Only one at end
    if (pImpl->at_end != other.pImpl->at_end) return false;
    // Compare position
    return pImpl->global_index == other.pImpl->global_index;
}

bool StreamingQueryIterator::operator!=(const StreamingQueryIterator& other) const {
    return !(*this == other);
}

bool StreamingQueryIterator::valid() const {
    return !pImpl->at_end;
}

size_t StreamingQueryIterator::index() const {
    return pImpl->global_index;
}

void StreamingQueryIterator::advance() {
    if (pImpl->at_end || !pImpl->query) return;

    pImpl->buffer_index++;
    pImpl->global_index++;

    // Need to load more data?
    if (pImpl->buffer_index >= pImpl->current_buffer.size()) {
        loadNextState();
    }
}

void StreamingQueryIterator::loadNextState() {
    pImpl->current_buffer.clear();
    pImpl->buffer_index = 0;

    if (pImpl->state_indices.empty()) {
        // First call - initialize state indices
        // This is a simplification - actual implementation would get from query
        pImpl->at_end = true;
        return;
    }

    while (pImpl->state_position < pImpl->state_indices.size() &&
           pImpl->current_buffer.empty()) {

        int state_idx = pImpl->state_indices[pImpl->state_position++];

        // Process this state and fill buffer
        pImpl->query->processState(state_idx, [this](ResultDataPoint&& point) {
            pImpl->current_buffer.push_back(std::move(point));
        });
    }

    if (pImpl->current_buffer.empty()) {
        pImpl->at_end = true;
    }
}

// ============================================================
// StreamingQuery Implementation
// ============================================================

struct StreamingQuery::Impl {
    D3plotReader& reader;

    // Configuration
    StreamingConfig config;
    StreamingProgressCallback progress_callback;

    // Selectors
    PartSelector part_selector;
    QuantitySelector quantity_selector;
    TimeSelector time_selector;
    ValueFilter value_filter;

    // State
    std::atomic<bool> cancelled{false};
    StreamingStats last_stats;

    // Cached data
    std::optional<data::Mesh> cached_mesh;
    std::optional<data::ControlData> cached_control;
    std::set<int32_t> selected_part_set;
    std::vector<int> selected_states;
    std::vector<QuantityType> selected_quantities;

    explicit Impl(D3plotReader& r) : reader(r) {
        // Default selectors
        part_selector = PartSelector::all();
        quantity_selector = QuantitySelector::vonMises();
        time_selector = TimeSelector::allStates();
    }

    void ensureCached() {
        if (!cached_mesh) {
            cached_mesh = reader.read_mesh();
        }
        if (!cached_control) {
            cached_control = reader.get_control_data();
        }
    }

    void updateSelections() {
        ensureCached();

        auto part_ids = part_selector.evaluate(reader);
        selected_part_set = std::set<int32_t>(part_ids.begin(), part_ids.end());

        selected_states = time_selector.evaluate(reader);
        selected_quantities = quantity_selector.getQuantities();
    }
};

StreamingQuery::StreamingQuery(D3plotReader& reader)
    : pImpl(std::make_unique<Impl>(reader))
{
}

StreamingQuery::StreamingQuery(StreamingQuery&& other) noexcept
    : pImpl(std::move(other.pImpl))
{
}

StreamingQuery& StreamingQuery::operator=(StreamingQuery&& other) noexcept {
    if (this != &other) {
        pImpl = std::move(other.pImpl);
    }
    return *this;
}

StreamingQuery::~StreamingQuery() = default;

// Configuration methods
StreamingQuery& StreamingQuery::config(const StreamingConfig& cfg) {
    pImpl->config = cfg;
    return *this;
}

StreamingQuery& StreamingQuery::chunkSize(size_t size) {
    pImpl->config.chunk_size = size;
    return *this;
}

StreamingQuery& StreamingQuery::reportProgress(bool enable) {
    pImpl->config.report_progress = enable;
    return *this;
}

StreamingQuery& StreamingQuery::onProgress(StreamingProgressCallback callback) {
    pImpl->progress_callback = std::move(callback);
    return *this;
}

// Selection methods
StreamingQuery& StreamingQuery::selectParts(const PartSelector& selector) {
    pImpl->part_selector = selector;
    return *this;
}

StreamingQuery& StreamingQuery::selectParts(const std::vector<int32_t>& part_ids) {
    pImpl->part_selector = PartSelector().byId(part_ids);
    return *this;
}

StreamingQuery& StreamingQuery::selectAllParts() {
    pImpl->part_selector = PartSelector::all();
    return *this;
}

StreamingQuery& StreamingQuery::selectQuantities(const QuantitySelector& selector) {
    pImpl->quantity_selector = selector;
    return *this;
}

StreamingQuery& StreamingQuery::selectQuantities(const std::vector<std::string>& names) {
    pImpl->quantity_selector = QuantitySelector().add(names);
    return *this;
}

StreamingQuery& StreamingQuery::selectTime(const TimeSelector& selector) {
    pImpl->time_selector = selector;
    return *this;
}

StreamingQuery& StreamingQuery::selectTime(const std::vector<int>& state_indices) {
    pImpl->time_selector = TimeSelector().addSteps(state_indices);
    return *this;
}

StreamingQuery& StreamingQuery::whereValue(const ValueFilter& filter) {
    pImpl->value_filter = filter;
    return *this;
}

// Iteration
StreamingQueryIterator StreamingQuery::begin() {
    return StreamingQueryIterator(this);
}

StreamingQueryIterator StreamingQuery::end() {
    return StreamingQueryIterator();
}

// Core processing method
void StreamingQuery::processState(int state_index,
                                  const std::function<void(ResultDataPoint&&)>& emitter) {
    pImpl->updateSelections();

    auto& mesh = *pImpl->cached_mesh;
    auto& control = *pImpl->cached_control;

    // Read state data
    auto state_data = pImpl->reader.read_state(static_cast<size_t>(state_index));
    double current_time = state_data.time;

    // Process solid elements
    size_t nv3d = static_cast<size_t>(control.NV3D);
    if (nv3d > 0 && !state_data.solid_data.empty()) {
        size_t num_solids = state_data.solid_data.size() / nv3d;

        for (size_t i = 0; i < num_solids && !pImpl->cancelled; ++i) {
            // Get part ID
            int32_t part_id = -1;
            if (i < mesh.solid_parts.size()) {
                part_id = mesh.solid_parts[i];
            } else if (i < mesh.solid_materials.size()) {
                part_id = mesh.solid_materials[i];
            }

            // Skip if part not selected
            if (!pImpl->selected_part_set.empty() &&
                pImpl->selected_part_set.find(part_id) == pImpl->selected_part_set.end()) {
                continue;
            }

            // Get element ID
            int32_t elem_id = (i < mesh.real_solid_ids.size()) ?
                             mesh.real_solid_ids[i] :
                             static_cast<int32_t>(i + 1);

            size_t base = i * nv3d;

            ResultDataPoint point;
            point.element_id = elem_id;
            point.part_id = part_id;
            point.state_index = state_index;
            point.time = current_time;

            // Extract data if we have enough values
            if (base + 6 < state_data.solid_data.size()) {
                double sx = state_data.solid_data[base + 0];
                double sy = state_data.solid_data[base + 1];
                double sz = state_data.solid_data[base + 2];
                double txy = state_data.solid_data[base + 3];
                double tyz = state_data.solid_data[base + 4];
                double tzx = state_data.solid_data[base + 5];
                double eps = state_data.solid_data[base + 6];

                for (auto qty : pImpl->selected_quantities) {
                    switch (qty) {
                        case QuantityType::STRESS_X:
                            point.values["x_stress"] = sx;
                            break;
                        case QuantityType::STRESS_Y:
                            point.values["y_stress"] = sy;
                            break;
                        case QuantityType::STRESS_Z:
                            point.values["z_stress"] = sz;
                            break;
                        case QuantityType::STRESS_XY:
                            point.values["xy_stress"] = txy;
                            break;
                        case QuantityType::STRESS_YZ:
                            point.values["yz_stress"] = tyz;
                            break;
                        case QuantityType::STRESS_ZX:
                            point.values["zx_stress"] = tzx;
                            break;
                        case QuantityType::STRESS_VON_MISES:
                            point.values["von_mises"] = calculateVonMises(sx, sy, sz, txy, tyz, tzx);
                            break;
                        case QuantityType::STRESS_PRESSURE:
                            point.values["pressure"] = calculatePressure(sx, sy, sz);
                            break;
                        case QuantityType::STRAIN_EFFECTIVE_PLASTIC:
                            point.values["plastic_strain"] = eps;
                            break;
                        default:
                            break;
                    }
                }
            }

            // Apply value filter
            if (!point.values.empty()) {
                if (pImpl->value_filter.isEmpty() || pImpl->value_filter.evaluate(point.values)) {
                    emitter(std::move(point));
                }
            }
        }
    }

    // Similar processing for shells (simplified)
    // ...
}

// Chunk processing
StreamingStats StreamingQuery::forEachChunk(size_t chunk_size, ChunkCallback callback) {
    StreamingStats stats;
    auto start_time = std::chrono::high_resolution_clock::now();

    pImpl->updateSelections();
    pImpl->cancelled = false;

    std::vector<ResultDataPoint> chunk;
    chunk.reserve(chunk_size);
    size_t chunk_index = 0;
    size_t total_estimated = estimateSize();

    for (int state_idx : pImpl->selected_states) {
        if (pImpl->cancelled) break;

        processState(state_idx, [&](ResultDataPoint&& point) {
            chunk.push_back(std::move(point));

            if (chunk.size() >= chunk_size) {
                if (!callback(chunk, chunk_index++)) {
                    pImpl->cancelled = true;
                }
                stats.points_processed += chunk.size();
                chunk.clear();

                // Progress report
                if (pImpl->config.report_progress && pImpl->progress_callback) {
                    pImpl->progress_callback(stats.points_processed, total_estimated,
                        "Processing chunk " + std::to_string(chunk_index));
                }
            }
        });

        stats.states_processed++;
    }

    // Emit remaining chunk
    if (!chunk.empty() && !pImpl->cancelled) {
        callback(chunk, chunk_index);
        stats.points_processed += chunk.size();
    }

    auto end_time = std::chrono::high_resolution_clock::now();
    stats.processing_time_ms = std::chrono::duration_cast<std::chrono::milliseconds>(
        end_time - start_time).count();
    stats.cancelled = pImpl->cancelled;

    pImpl->last_stats = stats;
    return stats;
}

StreamingStats StreamingQuery::forEachChunk(ChunkCallback callback) {
    return forEachChunk(pImpl->config.chunk_size, std::move(callback));
}

StreamingStats StreamingQuery::forEach(PointCallback callback) {
    StreamingStats stats;
    auto start_time = std::chrono::high_resolution_clock::now();

    pImpl->updateSelections();
    pImpl->cancelled = false;

    size_t index = 0;
    size_t total_estimated = estimateSize();

    for (int state_idx : pImpl->selected_states) {
        if (pImpl->cancelled) break;

        processState(state_idx, [&](ResultDataPoint&& point) {
            if (!callback(point, index++)) {
                pImpl->cancelled = true;
            }
            stats.points_processed++;

            // Progress report
            if (pImpl->config.report_progress &&
                pImpl->progress_callback &&
                stats.points_processed % pImpl->config.progress_interval == 0) {
                pImpl->progress_callback(stats.points_processed, total_estimated,
                    "Processing point " + std::to_string(stats.points_processed));
            }
        });

        stats.states_processed++;
    }

    auto end_time = std::chrono::high_resolution_clock::now();
    stats.processing_time_ms = std::chrono::duration_cast<std::chrono::milliseconds>(
        end_time - start_time).count();
    stats.cancelled = pImpl->cancelled;

    pImpl->last_stats = stats;
    return stats;
}

// Direct file output
StreamingStats StreamingQuery::streamToCSV(const std::string& filename, const OutputSpec& spec) {
    StreamingStats stats;
    auto start_time = std::chrono::high_resolution_clock::now();

    std::ofstream file(filename);
    if (!file.is_open()) {
        stats.error_message = "Failed to open file: " + filename;
        return stats;
    }

    // Set buffer size
    std::vector<char> buffer(pImpl->config.io_buffer_size);
    file.rdbuf()->pubsetbuf(buffer.data(), buffer.size());

    pImpl->updateSelections();
    pImpl->cancelled = false;

    bool header_written = false;
    std::vector<std::string> field_names;
    size_t total_estimated = estimateSize();

    for (int state_idx : pImpl->selected_states) {
        if (pImpl->cancelled) break;

        processState(state_idx, [&](ResultDataPoint&& point) {
            // Write header on first point
            if (!header_written) {
                field_names = {"element_id", "part_id", "state", "time"};
                for (const auto& kv : point.values) {
                    field_names.push_back(kv.first);
                }

                // CSV header
                for (size_t i = 0; i < field_names.size(); ++i) {
                    if (i > 0) file << ",";
                    file << field_names[i];
                }
                file << "\n";
                header_written = true;
            }

            // Write data row
            file << point.element_id << ","
                 << point.part_id << ","
                 << point.state_index << ","
                 << std::fixed << std::setprecision(spec.getPrecision())
                 << point.time;

            for (size_t i = 4; i < field_names.size(); ++i) {
                file << ",";
                auto it = point.values.find(field_names[i]);
                if (it != point.values.end()) {
                    file << it->second;
                }
            }
            file << "\n";

            stats.points_processed++;

            // Progress report
            if (pImpl->config.report_progress &&
                pImpl->progress_callback &&
                stats.points_processed % pImpl->config.progress_interval == 0) {
                pImpl->progress_callback(stats.points_processed, total_estimated,
                    "Writing row " + std::to_string(stats.points_processed));
            }
        });

        stats.states_processed++;
    }

    file.flush();
    stats.bytes_written = static_cast<size_t>(file.tellp());
    file.close();

    auto end_time = std::chrono::high_resolution_clock::now();
    stats.processing_time_ms = std::chrono::duration_cast<std::chrono::milliseconds>(
        end_time - start_time).count();
    stats.cancelled = pImpl->cancelled;

    pImpl->last_stats = stats;
    return stats;
}

StreamingStats StreamingQuery::streamToJSON(const std::string& filename, const OutputSpec& spec) {
    StreamingStats stats;
    auto start_time = std::chrono::high_resolution_clock::now();

    std::ofstream file(filename);
    if (!file.is_open()) {
        stats.error_message = "Failed to open file: " + filename;
        return stats;
    }

    pImpl->updateSelections();
    pImpl->cancelled = false;

    file << "{\n  \"data\": [\n";
    bool first_point = true;
    size_t total_estimated = estimateSize();

    for (int state_idx : pImpl->selected_states) {
        if (pImpl->cancelled) break;

        processState(state_idx, [&](ResultDataPoint&& point) {
            if (!first_point) {
                file << ",\n";
            }
            first_point = false;

            file << "    {";
            file << "\"element_id\":" << point.element_id << ",";
            file << "\"part_id\":" << point.part_id << ",";
            file << "\"state\":" << point.state_index << ",";
            file << "\"time\":" << std::fixed << std::setprecision(spec.getPrecision()) << point.time;

            for (const auto& kv : point.values) {
                file << ",\"" << kv.first << "\":" << kv.second;
            }
            file << "}";

            stats.points_processed++;
        });

        stats.states_processed++;
    }

    file << "\n  ]\n}\n";

    stats.bytes_written = static_cast<size_t>(file.tellp());
    file.close();

    auto end_time = std::chrono::high_resolution_clock::now();
    stats.processing_time_ms = std::chrono::duration_cast<std::chrono::milliseconds>(
        end_time - start_time).count();

    pImpl->last_stats = stats;
    return stats;
}

// Aggregation methods
std::optional<ResultDataPoint> StreamingQuery::findMax(const std::string& quantity_name) {
    std::optional<ResultDataPoint> max_point;
    double max_val = std::numeric_limits<double>::lowest();

    forEach([&](const ResultDataPoint& point, size_t) {
        auto it = point.values.find(quantity_name);
        if (it != point.values.end() && it->second > max_val) {
            max_val = it->second;
            max_point = point;
        }
        return !pImpl->cancelled;
    });

    return max_point;
}

std::optional<ResultDataPoint> StreamingQuery::findMin(const std::string& quantity_name) {
    std::optional<ResultDataPoint> min_point;
    double min_val = std::numeric_limits<double>::max();

    forEach([&](const ResultDataPoint& point, size_t) {
        auto it = point.values.find(quantity_name);
        if (it != point.values.end() && it->second < min_val) {
            min_val = it->second;
            min_point = point;
        }
        return !pImpl->cancelled;
    });

    return min_point;
}

QuantityStatistics StreamingQuery::calculateStats(const std::string& quantity_name) {
    OnlineStats online;
    int32_t min_elem_id = -1, max_elem_id = -1;
    int32_t min_state = -1, max_state = -1;
    double min_time = 0.0, max_time = 0.0;

    forEach([&](const ResultDataPoint& point, size_t) {
        auto it = point.values.find(quantity_name);
        if (it != point.values.end()) {
            double val = it->second;

            if (online.count() == 0 || val < online.min()) {
                min_elem_id = point.element_id;
                min_state = point.state_index;
                min_time = point.time;
            }
            if (online.count() == 0 || val > online.max()) {
                max_elem_id = point.element_id;
                max_state = point.state_index;
                max_time = point.time;
            }

            online.update(val);
        }
        return !pImpl->cancelled;
    });

    QuantityStatistics stats;
    stats.quantity_name = quantity_name;
    stats.count = online.count();
    stats.min_value = online.min();
    stats.max_value = online.max();
    stats.mean_value = online.mean();
    stats.std_dev = online.stddev();
    stats.sum = online.sum();
    stats.range = online.max() - online.min();
    stats.min_element_id = min_elem_id;
    stats.max_element_id = max_elem_id;
    stats.min_state_index = min_state;
    stats.max_state_index = max_state;
    stats.min_time = min_time;
    stats.max_time = max_time;

    return stats;
}

std::vector<ResultDataPoint> StreamingQuery::topN(const std::string& quantity_name, size_t n) {
    // Simple approach: keep sorted vector of top N
    std::vector<std::pair<double, ResultDataPoint>> top_values;
    top_values.reserve(n + 1);

    forEach([&](const ResultDataPoint& point, size_t) {
        auto it = point.values.find(quantity_name);
        if (it != point.values.end()) {
            double val = it->second;

            if (top_values.size() < n) {
                top_values.emplace_back(val, point);
                std::sort(top_values.begin(), top_values.end(),
                         [](const auto& a, const auto& b) { return a.first > b.first; });
            } else if (val > top_values.back().first) {
                top_values.back() = std::make_pair(val, point);
                std::sort(top_values.begin(), top_values.end(),
                         [](const auto& a, const auto& b) { return a.first > b.first; });
            }
        }
        return !pImpl->cancelled;
    });

    // Extract results (already sorted descending)
    std::vector<ResultDataPoint> result;
    result.reserve(top_values.size());
    for (const auto& pair : top_values) {
        result.push_back(pair.second);
    }

    return result;
}

std::vector<ResultDataPoint> StreamingQuery::bottomN(const std::string& quantity_name, size_t n) {
    // Simple approach: keep sorted vector of bottom N
    std::vector<std::pair<double, ResultDataPoint>> bottom_values;
    bottom_values.reserve(n + 1);

    forEach([&](const ResultDataPoint& point, size_t) {
        auto it = point.values.find(quantity_name);
        if (it != point.values.end()) {
            double val = it->second;

            if (bottom_values.size() < n) {
                bottom_values.emplace_back(val, point);
                std::sort(bottom_values.begin(), bottom_values.end(),
                         [](const auto& a, const auto& b) { return a.first < b.first; });
            } else if (val < bottom_values.back().first) {
                bottom_values.back() = std::make_pair(val, point);
                std::sort(bottom_values.begin(), bottom_values.end(),
                         [](const auto& a, const auto& b) { return a.first < b.first; });
            }
        }
        return !pImpl->cancelled;
    });

    // Extract results (already sorted ascending)
    std::vector<ResultDataPoint> result;
    result.reserve(bottom_values.size());
    for (const auto& pair : bottom_values) {
        result.push_back(pair.second);
    }

    return result;
}

// Control
void StreamingQuery::cancel() {
    pImpl->cancelled = true;
}

bool StreamingQuery::isCancelled() const {
    return pImpl->cancelled;
}

void StreamingQuery::resetCancel() {
    pImpl->cancelled = false;
}

// Information
size_t StreamingQuery::estimateSize() const {
    pImpl->ensureCached();

    auto& mesh = *pImpl->cached_mesh;
    size_t num_elements = mesh.num_solids + mesh.num_shells;

    auto states = pImpl->time_selector.evaluate(pImpl->reader);
    size_t num_states = states.size();

    return num_elements * num_states;
}

size_t StreamingQuery::estimateMemoryBytes() const {
    // Rough estimate: each data point ~200 bytes
    return estimateSize() * 200;
}

std::string StreamingQuery::getDescription() const {
    std::ostringstream oss;
    oss << "Streaming Query:\n";
    oss << "  Parts: " << pImpl->part_selector.getDescription() << "\n";
    oss << "  Quantities: " << pImpl->quantity_selector.getDescription() << "\n";
    oss << "  Time: " << pImpl->time_selector.getDescription() << "\n";
    oss << "  Estimated size: " << estimateSize() << " points\n";
    oss << "  Estimated memory: " << (estimateMemoryBytes() / 1024 / 1024) << " MB\n";
    return oss.str();
}

StreamingStats StreamingQuery::getLastStats() const {
    return pImpl->last_stats;
}

// ============================================================
// StreamingFileWriter Implementation
// ============================================================

struct StreamingFileWriter::Impl {
    std::ofstream file;
    OutputFormat format;
    std::vector<std::string> fields;
    size_t bytes_written = 0;
    bool header_written = false;
    bool first_row = true;

    Impl(const std::string& filename, OutputFormat fmt)
        : format(fmt)
    {
        file.open(filename);
    }
};

StreamingFileWriter::StreamingFileWriter(const std::string& filename, OutputFormat format)
    : pImpl(std::make_unique<Impl>(filename, format))
{
}

StreamingFileWriter::~StreamingFileWriter() {
    close();
}

void StreamingFileWriter::writeHeader(const std::vector<std::string>& fields) {
    if (pImpl->header_written) return;

    pImpl->fields = fields;

    switch (pImpl->format) {
        case OutputFormat::CSV:
            for (size_t i = 0; i < fields.size(); ++i) {
                if (i > 0) pImpl->file << ",";
                pImpl->file << fields[i];
            }
            pImpl->file << "\n";
            break;

        case OutputFormat::JSON:
            pImpl->file << "{\n  \"data\": [\n";
            break;

        default:
            break;
    }

    pImpl->header_written = true;
}

void StreamingFileWriter::writeRow(const ResultDataPoint& point) {
    switch (pImpl->format) {
        case OutputFormat::CSV:
            pImpl->file << point.element_id << ","
                       << point.part_id << ","
                       << point.state_index << ","
                       << std::fixed << std::setprecision(6) << point.time;

            for (size_t i = 4; i < pImpl->fields.size(); ++i) {
                pImpl->file << ",";
                auto it = point.values.find(pImpl->fields[i]);
                if (it != point.values.end()) {
                    pImpl->file << it->second;
                }
            }
            pImpl->file << "\n";
            break;

        case OutputFormat::JSON:
            if (!pImpl->first_row) {
                pImpl->file << ",\n";
            }
            pImpl->first_row = false;

            pImpl->file << "    {";
            pImpl->file << "\"element_id\":" << point.element_id << ",";
            pImpl->file << "\"part_id\":" << point.part_id << ",";
            pImpl->file << "\"state\":" << point.state_index << ",";
            pImpl->file << "\"time\":" << std::fixed << std::setprecision(6) << point.time;

            for (const auto& kv : point.values) {
                pImpl->file << ",\"" << kv.first << "\":" << kv.second;
            }
            pImpl->file << "}";
            break;

        default:
            break;
    }
}

void StreamingFileWriter::writeFooter(const StreamingStats& stats) {
    switch (pImpl->format) {
        case OutputFormat::JSON:
            pImpl->file << "\n  ],\n";
            pImpl->file << "  \"stats\": {\n";
            pImpl->file << "    \"points_processed\": " << stats.points_processed << ",\n";
            pImpl->file << "    \"processing_time_ms\": " << stats.processing_time_ms << "\n";
            pImpl->file << "  }\n";
            pImpl->file << "}\n";
            break;

        default:
            break;
    }
}

void StreamingFileWriter::flush() {
    pImpl->file.flush();
}

void StreamingFileWriter::close() {
    if (pImpl->file.is_open()) {
        pImpl->bytes_written = static_cast<size_t>(pImpl->file.tellp());
        pImpl->file.close();
    }
}

size_t StreamingFileWriter::bytesWritten() const {
    return pImpl->bytes_written;
}

} // namespace query
} // namespace kood3plot
