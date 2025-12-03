/**
 * @file QueryResult.cpp
 * @brief Implementation of QueryResult class
 * @author KooD3plot V3 Development Team
 * @date 2025-11-21
 * @version 3.0.0
 */

#include "kood3plot/query/QueryResult.h"
#include <algorithm>
#include <numeric>
#include <cmath>
#include <sstream>
#include <iomanip>
#include <set>
#include <stdexcept>

namespace kood3plot {
namespace query {

// ============================================================
// PIMPL Implementation Struct
// ============================================================

struct QueryResult::Impl {
    /// Data points
    std::vector<ResultDataPoint> data_points;

    /// Metadata
    std::string query_description;
    std::string source_file;
    std::map<std::string, std::string> metadata;

    Impl() = default;
};

// ============================================================
// Constructors and Destructor
// ============================================================

QueryResult::QueryResult()
    : pImpl(std::make_unique<Impl>())
{
}

QueryResult::QueryResult(const QueryResult& other)
    : pImpl(std::make_unique<Impl>(*other.pImpl))
{
}

QueryResult::QueryResult(QueryResult&& other) noexcept
    : pImpl(std::move(other.pImpl))
{
}

QueryResult& QueryResult::operator=(const QueryResult& other) {
    if (this != &other) {
        pImpl = std::make_unique<Impl>(*other.pImpl);
    }
    return *this;
}

QueryResult& QueryResult::operator=(QueryResult&& other) noexcept {
    if (this != &other) {
        pImpl = std::move(other.pImpl);
    }
    return *this;
}

QueryResult::~QueryResult() = default;

// ============================================================
// Data Point Access
// ============================================================

size_t QueryResult::size() const {
    return pImpl->data_points.size();
}

bool QueryResult::empty() const {
    return pImpl->data_points.empty();
}

const std::vector<ResultDataPoint>& QueryResult::getDataPoints() const {
    return pImpl->data_points;
}

const ResultDataPoint& QueryResult::at(size_t index) const {
    if (index >= pImpl->data_points.size()) {
        throw std::out_of_range("QueryResult index out of range");
    }
    return pImpl->data_points[index];
}

const ResultDataPoint& QueryResult::operator[](size_t index) const {
    return pImpl->data_points[index];
}

// ============================================================
// Iteration Support
// ============================================================

QueryResult::iterator QueryResult::begin() {
    return pImpl->data_points.begin();
}

QueryResult::iterator QueryResult::end() {
    return pImpl->data_points.end();
}

QueryResult::const_iterator QueryResult::begin() const {
    return pImpl->data_points.begin();
}

QueryResult::const_iterator QueryResult::end() const {
    return pImpl->data_points.end();
}

QueryResult::const_iterator QueryResult::cbegin() const {
    return pImpl->data_points.cbegin();
}

QueryResult::const_iterator QueryResult::cend() const {
    return pImpl->data_points.cend();
}

// ============================================================
// Filtering
// ============================================================

QueryResult QueryResult::filterByPart(int32_t part_id) const {
    return filter([part_id](const ResultDataPoint& p) {
        return p.part_id == part_id;
    });
}

QueryResult QueryResult::filterByParts(const std::vector<int32_t>& part_ids) const {
    std::set<int32_t> part_set(part_ids.begin(), part_ids.end());
    return filter([&part_set](const ResultDataPoint& p) {
        return part_set.count(p.part_id) > 0;
    });
}

QueryResult QueryResult::filterByElement(int32_t element_id) const {
    return filter([element_id](const ResultDataPoint& p) {
        return p.element_id == element_id;
    });
}

QueryResult QueryResult::filterByState(int32_t state_index) const {
    return filter([state_index](const ResultDataPoint& p) {
        return p.state_index == state_index;
    });
}

QueryResult QueryResult::filterByTimeRange(double min_time, double max_time) const {
    return filter([min_time, max_time](const ResultDataPoint& p) {
        return p.time >= min_time && p.time <= max_time;
    });
}

QueryResult QueryResult::filter(std::function<bool(const ResultDataPoint&)> predicate) const {
    QueryResult result;
    result.pImpl->query_description = pImpl->query_description + " (filtered)";
    result.pImpl->source_file = pImpl->source_file;
    result.pImpl->metadata = pImpl->metadata;

    for (const auto& point : pImpl->data_points) {
        if (predicate(point)) {
            result.pImpl->data_points.push_back(point);
        }
    }

    return result;
}

// ============================================================
// Statistics
// ============================================================

QuantityStatistics QueryResult::getStatistics(const std::string& quantity_name) const {
    QuantityStatistics stats;
    stats.quantity_name = quantity_name;
    stats.min_value = std::numeric_limits<double>::max();
    stats.max_value = std::numeric_limits<double>::lowest();
    stats.mean_value = 0.0;
    stats.std_dev = 0.0;
    stats.sum = 0.0;
    stats.range = 0.0;
    stats.median = 0.0;
    stats.count = 0;
    stats.min_element_id = -1;
    stats.max_element_id = -1;
    stats.min_state_index = -1;
    stats.max_state_index = -1;
    stats.min_time = 0.0;
    stats.max_time = 0.0;

    // Collect values
    std::vector<double> values;
    for (const auto& point : pImpl->data_points) {
        auto it = point.values.find(quantity_name);
        if (it != point.values.end()) {
            double val = it->second;
            values.push_back(val);

            if (val < stats.min_value) {
                stats.min_value = val;
                stats.min_element_id = point.element_id;
                stats.min_state_index = point.state_index;
                stats.min_time = point.time;
            }

            if (val > stats.max_value) {
                stats.max_value = val;
                stats.max_element_id = point.element_id;
                stats.max_state_index = point.state_index;
                stats.max_time = point.time;
            }
        }
    }

    stats.count = values.size();

    if (stats.count > 0) {
        // Calculate sum
        stats.sum = std::accumulate(values.begin(), values.end(), 0.0);

        // Calculate mean
        stats.mean_value = stats.sum / static_cast<double>(stats.count);

        // Calculate range
        stats.range = stats.max_value - stats.min_value;

        // Calculate median
        std::vector<double> sorted_values = values;
        std::sort(sorted_values.begin(), sorted_values.end());
        size_t n = sorted_values.size();
        if (n % 2 == 0) {
            stats.median = (sorted_values[n/2 - 1] + sorted_values[n/2]) / 2.0;
        } else {
            stats.median = sorted_values[n/2];
        }

        // Calculate standard deviation
        if (stats.count > 1) {
            double sq_sum = 0.0;
            for (double val : values) {
                double diff = val - stats.mean_value;
                sq_sum += diff * diff;
            }
            stats.std_dev = std::sqrt(sq_sum / static_cast<double>(stats.count - 1));
        }
    } else {
        stats.min_value = 0.0;
        stats.max_value = 0.0;
    }

    return stats;
}

std::map<std::string, QuantityStatistics> QueryResult::getAllStatistics() const {
    std::map<std::string, QuantityStatistics> result;

    auto quantity_names = getQuantityNames();
    for (const auto& name : quantity_names) {
        result[name] = getStatistics(name);
    }

    return result;
}

std::vector<std::string> QueryResult::getQuantityNames() const {
    std::set<std::string> names;
    for (const auto& point : pImpl->data_points) {
        for (const auto& kv : point.values) {
            names.insert(kv.first);
        }
    }
    return std::vector<std::string>(names.begin(), names.end());
}

std::vector<int32_t> QueryResult::getPartIds() const {
    std::set<int32_t> ids;
    for (const auto& point : pImpl->data_points) {
        ids.insert(point.part_id);
    }
    return std::vector<int32_t>(ids.begin(), ids.end());
}

std::vector<int32_t> QueryResult::getElementIds() const {
    std::set<int32_t> ids;
    for (const auto& point : pImpl->data_points) {
        ids.insert(point.element_id);
    }
    return std::vector<int32_t>(ids.begin(), ids.end());
}

std::vector<int32_t> QueryResult::getStateIndices() const {
    std::set<int32_t> indices;
    for (const auto& point : pImpl->data_points) {
        indices.insert(point.state_index);
    }
    return std::vector<int32_t>(indices.begin(), indices.end());
}

std::vector<double> QueryResult::getTimeValues() const {
    std::set<double> times;
    for (const auto& point : pImpl->data_points) {
        times.insert(point.time);
    }
    return std::vector<double>(times.begin(), times.end());
}

// ============================================================
// Aggregation
// ============================================================

std::map<int32_t, ElementAggregation> QueryResult::aggregateByElement(AggregationType agg_type) const {
    std::map<int32_t, ElementAggregation> result;

    // Group by element
    std::map<int32_t, std::vector<const ResultDataPoint*>> element_groups;
    for (const auto& point : pImpl->data_points) {
        element_groups[point.element_id].push_back(&point);
    }

    auto quantity_names = getQuantityNames();

    for (const auto& [elem_id, points] : element_groups) {
        ElementAggregation agg;
        agg.element_id = elem_id;
        agg.part_id = points.front()->part_id;

        for (const auto& qty_name : quantity_names) {
            std::vector<double> values;
            double max_val = std::numeric_limits<double>::lowest();
            double min_val = std::numeric_limits<double>::max();
            double time_of_max = 0.0;
            double time_of_min = 0.0;

            for (const auto* pt : points) {
                auto it = pt->values.find(qty_name);
                if (it != pt->values.end()) {
                    double val = it->second;
                    values.push_back(val);

                    if (val > max_val) {
                        max_val = val;
                        time_of_max = pt->time;
                    }
                    if (val < min_val) {
                        min_val = val;
                        time_of_min = pt->time;
                    }
                }
            }

            if (!values.empty()) {
                double agg_value = 0.0;

                switch (agg_type) {
                    case AggregationType::MAX:
                        agg_value = max_val;
                        break;
                    case AggregationType::MIN:
                        agg_value = min_val;
                        break;
                    case AggregationType::MEAN: {
                        double sum = std::accumulate(values.begin(), values.end(), 0.0);
                        agg_value = sum / static_cast<double>(values.size());
                        break;
                    }
                    case AggregationType::STDDEV: {
                        if (values.size() > 1) {
                            double sum = std::accumulate(values.begin(), values.end(), 0.0);
                            double mean = sum / static_cast<double>(values.size());
                            double sq_sum = 0.0;
                            for (double v : values) {
                                double diff = v - mean;
                                sq_sum += diff * diff;
                            }
                            agg_value = std::sqrt(sq_sum / static_cast<double>(values.size() - 1));
                        }
                        break;
                    }
                    case AggregationType::SUM: {
                        agg_value = std::accumulate(values.begin(), values.end(), 0.0);
                        break;
                    }
                    case AggregationType::COUNT: {
                        agg_value = static_cast<double>(values.size());
                        break;
                    }
                    case AggregationType::RANGE: {
                        agg_value = max_val - min_val;
                        break;
                    }
                    case AggregationType::MEDIAN: {
                        std::vector<double> sorted_values = values;
                        std::sort(sorted_values.begin(), sorted_values.end());
                        size_t n = sorted_values.size();
                        if (n % 2 == 0) {
                            agg_value = (sorted_values[n/2 - 1] + sorted_values[n/2]) / 2.0;
                        } else {
                            agg_value = sorted_values[n/2];
                        }
                        break;
                    }
                    case AggregationType::NONE:
                    default:
                        // For NONE, use the last value
                        agg_value = values.back();
                        break;
                }

                agg.aggregated_values[qty_name][agg_type] = agg_value;
                agg.time_of_max[qty_name] = time_of_max;
                agg.time_of_min[qty_name] = time_of_min;
            }
        }

        result[elem_id] = std::move(agg);
    }

    return result;
}

ElementTimeHistory QueryResult::getElementHistory(int32_t element_id) const {
    ElementTimeHistory history;
    history.element_id = element_id;
    history.part_id = -1;

    // Collect points for this element, sorted by time
    std::vector<const ResultDataPoint*> element_points;
    for (const auto& point : pImpl->data_points) {
        if (point.element_id == element_id) {
            element_points.push_back(&point);
            history.part_id = point.part_id;
        }
    }

    // Sort by time
    std::sort(element_points.begin(), element_points.end(),
              [](const ResultDataPoint* a, const ResultDataPoint* b) {
                  return a->time < b->time;
              });

    // Build history
    for (const auto* pt : element_points) {
        history.times.push_back(pt->time);
        history.state_indices.push_back(pt->state_index);

        for (const auto& kv : pt->values) {
            history.quantity_histories[kv.first].push_back(kv.second);
        }
    }

    return history;
}

double QueryResult::aggregate(const std::string& quantity_name, AggregationType agg_type) const {
    auto values = getValues(quantity_name);
    if (values.empty()) {
        return 0.0;
    }

    switch (agg_type) {
        case AggregationType::SUM:
            return std::accumulate(values.begin(), values.end(), 0.0);

        case AggregationType::COUNT:
            return static_cast<double>(values.size());

        case AggregationType::MEAN: {
            double sum_val = std::accumulate(values.begin(), values.end(), 0.0);
            return sum_val / static_cast<double>(values.size());
        }

        case AggregationType::MAX:
            return *std::max_element(values.begin(), values.end());

        case AggregationType::MIN:
            return *std::min_element(values.begin(), values.end());

        case AggregationType::RANGE: {
            auto minmax = std::minmax_element(values.begin(), values.end());
            return *minmax.second - *minmax.first;
        }

        case AggregationType::MEDIAN: {
            std::vector<double> sorted_values = values;
            std::sort(sorted_values.begin(), sorted_values.end());
            size_t n = sorted_values.size();
            if (n % 2 == 0) {
                return (sorted_values[n/2 - 1] + sorted_values[n/2]) / 2.0;
            }
            return sorted_values[n/2];
        }

        case AggregationType::STDDEV: {
            if (values.size() < 2) return 0.0;
            double sum_val = std::accumulate(values.begin(), values.end(), 0.0);
            double mean = sum_val / static_cast<double>(values.size());
            double sq_sum = 0.0;
            for (double v : values) {
                double diff = v - mean;
                sq_sum += diff * diff;
            }
            return std::sqrt(sq_sum / static_cast<double>(values.size() - 1));
        }

        default:
            return values.back();
    }
}

double QueryResult::sum(const std::string& quantity_name) const {
    return aggregate(quantity_name, AggregationType::SUM);
}

size_t QueryResult::count(const std::string& quantity_name) const {
    return static_cast<size_t>(aggregate(quantity_name, AggregationType::COUNT));
}

double QueryResult::range(const std::string& quantity_name) const {
    return aggregate(quantity_name, AggregationType::RANGE);
}

std::vector<double> QueryResult::getValues(const std::string& quantity_name) const {
    std::vector<double> values;
    values.reserve(pImpl->data_points.size());

    for (const auto& point : pImpl->data_points) {
        auto it = point.values.find(quantity_name);
        if (it != point.values.end()) {
            values.push_back(it->second);
        }
    }

    return values;
}

std::optional<ResultDataPoint> QueryResult::findMax(const std::string& quantity_name) const {
    const ResultDataPoint* max_point = nullptr;
    double max_val = std::numeric_limits<double>::lowest();

    for (const auto& point : pImpl->data_points) {
        auto it = point.values.find(quantity_name);
        if (it != point.values.end() && it->second > max_val) {
            max_val = it->second;
            max_point = &point;
        }
    }

    if (max_point) {
        return *max_point;
    }
    return std::nullopt;
}

std::optional<ResultDataPoint> QueryResult::findMin(const std::string& quantity_name) const {
    const ResultDataPoint* min_point = nullptr;
    double min_val = std::numeric_limits<double>::max();

    for (const auto& point : pImpl->data_points) {
        auto it = point.values.find(quantity_name);
        if (it != point.values.end() && it->second < min_val) {
            min_val = it->second;
            min_point = &point;
        }
    }

    if (min_point) {
        return *min_point;
    }
    return std::nullopt;
}

// ============================================================
// Metadata
// ============================================================

std::string QueryResult::getQueryDescription() const {
    return pImpl->query_description;
}

void QueryResult::setQueryDescription(const std::string& description) {
    pImpl->query_description = description;
}

std::string QueryResult::getSourceFile() const {
    return pImpl->source_file;
}

void QueryResult::setSourceFile(const std::string& filename) {
    pImpl->source_file = filename;
}

std::optional<std::string> QueryResult::getMetadata(const std::string& key) const {
    auto it = pImpl->metadata.find(key);
    if (it != pImpl->metadata.end()) {
        return it->second;
    }
    return std::nullopt;
}

void QueryResult::setMetadata(const std::string& key, const std::string& value) {
    pImpl->metadata[key] = value;
}

std::map<std::string, std::string> QueryResult::getAllMetadata() const {
    return pImpl->metadata;
}

// ============================================================
// Modification
// ============================================================

void QueryResult::addDataPoint(const ResultDataPoint& point) {
    pImpl->data_points.push_back(point);
}

void QueryResult::addDataPoint(ResultDataPoint&& point) {
    pImpl->data_points.push_back(std::move(point));
}

void QueryResult::reserve(size_t capacity) {
    pImpl->data_points.reserve(capacity);
}

void QueryResult::clear() {
    pImpl->data_points.clear();
}

void QueryResult::sort(std::function<bool(const ResultDataPoint&, const ResultDataPoint&)> comparator) {
    std::sort(pImpl->data_points.begin(), pImpl->data_points.end(), comparator);
}

void QueryResult::sortByElement() {
    sort([](const ResultDataPoint& a, const ResultDataPoint& b) {
        if (a.element_id != b.element_id) return a.element_id < b.element_id;
        return a.state_index < b.state_index;
    });
}

void QueryResult::sortByTime() {
    sort([](const ResultDataPoint& a, const ResultDataPoint& b) {
        if (a.state_index != b.state_index) return a.state_index < b.state_index;
        return a.element_id < b.element_id;
    });
}

void QueryResult::sortByPart() {
    sort([](const ResultDataPoint& a, const ResultDataPoint& b) {
        if (a.part_id != b.part_id) return a.part_id < b.part_id;
        if (a.element_id != b.element_id) return a.element_id < b.element_id;
        return a.state_index < b.state_index;
    });
}

// ============================================================
// Summary and Output
// ============================================================

std::string QueryResult::getSummary() const {
    std::ostringstream oss;

    oss << "QueryResult Summary\n";
    oss << "==================\n";
    oss << "Source file: " << (pImpl->source_file.empty() ? "(unknown)" : pImpl->source_file) << "\n";
    oss << "Data points: " << size() << "\n";

    auto part_ids = getPartIds();
    oss << "Parts: " << part_ids.size() << "\n";

    auto elem_ids = getElementIds();
    oss << "Elements: " << elem_ids.size() << "\n";

    auto state_indices = getStateIndices();
    oss << "Timesteps: " << state_indices.size() << "\n";

    auto times = getTimeValues();
    if (!times.empty()) {
        oss << "Time range: " << times.front() << " - " << times.back() << "\n";
    }

    oss << "\nQuantities:\n";
    auto all_stats = getAllStatistics();
    for (const auto& [name, stats] : all_stats) {
        oss << "  " << name << ":\n";
        oss << "    Min: " << stats.min_value << " (element " << stats.min_element_id << " at t=" << stats.min_time << ")\n";
        oss << "    Max: " << stats.max_value << " (element " << stats.max_element_id << " at t=" << stats.max_time << ")\n";
        oss << "    Mean: " << stats.mean_value << "\n";
        oss << "    StdDev: " << stats.std_dev << "\n";
    }

    return oss.str();
}

std::string QueryResult::toTable(size_t max_rows) const {
    std::ostringstream oss;

    if (empty()) {
        return "(empty result)\n";
    }

    // Get column names
    std::vector<std::string> columns = {"element_id", "part_id", "state", "time"};
    auto qty_names = getQuantityNames();
    columns.insert(columns.end(), qty_names.begin(), qty_names.end());

    // Calculate column widths
    std::vector<size_t> widths(columns.size(), 0);
    for (size_t i = 0; i < columns.size(); ++i) {
        widths[i] = columns[i].length();
    }

    // Check sample values for width
    size_t rows_to_check = std::min(size(), max_rows > 0 ? max_rows : size());
    for (size_t r = 0; r < rows_to_check; ++r) {
        const auto& pt = pImpl->data_points[r];
        widths[0] = std::max(widths[0], std::to_string(pt.element_id).length());
        widths[1] = std::max(widths[1], std::to_string(pt.part_id).length());
        widths[2] = std::max(widths[2], std::to_string(pt.state_index).length());

        std::ostringstream time_ss;
        time_ss << std::fixed << std::setprecision(6) << pt.time;
        widths[3] = std::max(widths[3], time_ss.str().length());

        for (size_t i = 0; i < qty_names.size(); ++i) {
            auto it = pt.values.find(qty_names[i]);
            if (it != pt.values.end()) {
                std::ostringstream val_ss;
                val_ss << std::fixed << std::setprecision(6) << it->second;
                widths[4 + i] = std::max(widths[4 + i], val_ss.str().length());
            }
        }
    }

    // Minimum width
    for (auto& w : widths) {
        w = std::max(w, size_t(8));
    }

    // Print header
    for (size_t i = 0; i < columns.size(); ++i) {
        oss << std::setw(static_cast<int>(widths[i])) << columns[i];
        if (i < columns.size() - 1) oss << " | ";
    }
    oss << "\n";

    // Print separator
    for (size_t i = 0; i < columns.size(); ++i) {
        oss << std::string(widths[i], '-');
        if (i < columns.size() - 1) oss << "-+-";
    }
    oss << "\n";

    // Print data rows
    size_t rows_to_print = max_rows > 0 ? std::min(size(), max_rows) : size();
    for (size_t r = 0; r < rows_to_print; ++r) {
        const auto& pt = pImpl->data_points[r];

        oss << std::setw(static_cast<int>(widths[0])) << pt.element_id << " | ";
        oss << std::setw(static_cast<int>(widths[1])) << pt.part_id << " | ";
        oss << std::setw(static_cast<int>(widths[2])) << pt.state_index << " | ";
        oss << std::setw(static_cast<int>(widths[3])) << std::fixed << std::setprecision(6) << pt.time;

        for (size_t i = 0; i < qty_names.size(); ++i) {
            oss << " | ";
            auto it = pt.values.find(qty_names[i]);
            if (it != pt.values.end()) {
                oss << std::setw(static_cast<int>(widths[4 + i])) << std::fixed << std::setprecision(6) << it->second;
            } else {
                oss << std::setw(static_cast<int>(widths[4 + i])) << "N/A";
            }
        }
        oss << "\n";
    }

    if (max_rows > 0 && size() > max_rows) {
        oss << "... (" << (size() - max_rows) << " more rows)\n";
    }

    return oss.str();
}

} // namespace query
} // namespace kood3plot
