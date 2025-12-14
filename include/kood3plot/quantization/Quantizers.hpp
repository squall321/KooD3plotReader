#pragma once

#include <kood3plot/quantization/QuantizationConfig.hpp>
#include <kood3plot/analysis/VectorMath.hpp>

#include <vector>
#include <array>
#include <cmath>
#include <algorithm>
#include <limits>
#include <stdexcept>

namespace kood3plot {
namespace quantization {

// Import Vec3 from analysis namespace
using analysis::Vec3;

/**
 * @brief Quantization metadata - stored as HDF5 attributes
 */
struct QuantizationMetadata {
    PhysicalType physical_type = PhysicalType::CUSTOM;
    Unit unit = Unit::DIMENSIONLESS;
    QuantizationStrategy strategy = QuantizationStrategy::LINEAR;

    int bits = 16;
    double scale = 1.0;
    double offset = 0.0;
    double min_value = 0.0;
    double max_value = 1.0;
    double precision = 0.01;

    // For logarithmic quantization
    double log_min = 0.0;
    double log_scale = 0.0;

    // Validation
    double max_quantization_error = 0.0;
    double mean_quantization_error = 0.0;
};

/**
 * @brief 변위 양자화기 (Displacement Quantizer)
 *
 * 특성:
 * - 선형 양자화 (LINEAR)
 * - 기본 16-bit (65536 levels)
 * - 목표 정밀도: 0.01mm
 * - 3축 독립 처리 (x, y, z)
 */
class DisplacementQuantizer {
public:
    DisplacementQuantizer()
        : config_(QuantizationConfig::create_displacement_config())
        , calibrated_(false)
    {}

    /**
     * @brief 데이터로 캘리브레이션
     * @param data 변위 데이터 (Vec3 배열)
     */
    void calibrate(const std::vector<Vec3>& data) {
        if (data.empty()) {
            throw std::invalid_argument("Cannot calibrate with empty data");
        }

        // 각 축의 min/max 찾기
        min_values_ = {std::numeric_limits<double>::max(),
                       std::numeric_limits<double>::max(),
                       std::numeric_limits<double>::max()};
        max_values_ = {std::numeric_limits<double>::lowest(),
                       std::numeric_limits<double>::lowest(),
                       std::numeric_limits<double>::lowest()};

        for (const auto& v : data) {
            min_values_[0] = std::min(min_values_[0], v.x);
            min_values_[1] = std::min(min_values_[1], v.y);
            min_values_[2] = std::min(min_values_[2], v.z);
            max_values_[0] = std::max(max_values_[0], v.x);
            max_values_[1] = std::max(max_values_[1], v.y);
            max_values_[2] = std::max(max_values_[2], v.z);
        }

        // 각 축의 scale 계산
        int max_value = (1 << config_.bits) - 1;  // 2^bits - 1
        for (int i = 0; i < 3; ++i) {
            double range = max_values_[i] - min_values_[i];
            if (range < 1e-10) {
                // 상수 데이터
                scales_[i] = 1.0;
            } else {
                scales_[i] = range / max_value;
            }
        }

        calibrated_ = true;

        // 양자화 오차 계산
        double max_err = 0.0;
        double sum_err = 0.0;

        for (const auto& v : data) {
            auto q = quantize(v);
            auto dq = dequantize(q);

            double err = (dq - v).magnitude();
            max_err = std::max(max_err, err);
            sum_err += err;
        }

        metadata_.max_quantization_error = max_err;
        metadata_.mean_quantization_error = sum_err / data.size();
    }

    /**
     * @brief Single vector quantization
     * @return Quantized values (16-bit unsigned * 3)
     */
    std::array<uint16_t, 3> quantize(const Vec3& value) const {
        if (!calibrated_) {
            throw std::runtime_error("Quantizer not calibrated");
        }

        std::array<uint16_t, 3> result;
        int max_quant = (1 << config_.bits) - 1;

        double vals[3] = {value.x, value.y, value.z};
        for (int i = 0; i < 3; ++i) {
            double range = max_values_[i] - min_values_[i];
            double normalized = (range > 1e-10) ?
                (vals[i] - min_values_[i]) / range : 0.5;
            normalized = std::clamp(normalized, 0.0, 1.0);
            result[i] = static_cast<uint16_t>(std::round(normalized * max_quant));
        }

        return result;
    }

    /**
     * @brief Dequantization
     */
    Vec3 dequantize(const std::array<uint16_t, 3>& q) const {
        if (!calibrated_) {
            throw std::runtime_error("Quantizer not calibrated");
        }

        int max_quant = (1 << config_.bits) - 1;

        return Vec3{
            min_values_[0] + (static_cast<double>(q[0]) / max_quant) * (max_values_[0] - min_values_[0]),
            min_values_[1] + (static_cast<double>(q[1]) / max_quant) * (max_values_[1] - min_values_[1]),
            min_values_[2] + (static_cast<double>(q[2]) / max_quant) * (max_values_[2] - min_values_[2])
        };
    }

    /**
     * @brief 배열 양자화
     */
    std::vector<uint16_t> quantize_array(const std::vector<Vec3>& data) const {
        std::vector<uint16_t> result;
        result.reserve(data.size() * 3);

        for (const auto& v : data) {
            auto q = quantize(v);
            result.push_back(q[0]);
            result.push_back(q[1]);
            result.push_back(q[2]);
        }

        return result;
    }

    /**
     * @brief 배열 역양자화
     */
    std::vector<Vec3> dequantize_array(const std::vector<uint16_t>& data) const {
        if (data.size() % 3 != 0) {
            throw std::invalid_argument("Data size must be multiple of 3");
        }

        std::vector<Vec3> result;
        result.reserve(data.size() / 3);

        for (size_t i = 0; i < data.size(); i += 3) {
            result.push_back(dequantize({data[i], data[i+1], data[i+2]}));
        }

        return result;
    }

    /**
     * @brief 메타데이터 반환 (HDF5 저장용)
     */
    QuantizationMetadata get_metadata() const {
        QuantizationMetadata meta;
        meta.physical_type = PhysicalType::DISPLACEMENT;
        meta.unit = Unit::MILLIMETER;
        meta.strategy = QuantizationStrategy::LINEAR;
        meta.bits = config_.bits;
        meta.precision = config_.required_precision;

        // 3축 중 가장 큰 범위 기준
        double max_range = 0.0;
        for (int i = 0; i < 3; ++i) {
            max_range = std::max(max_range, max_values_[i] - min_values_[i]);
        }
        meta.min_value = *std::min_element(min_values_.begin(), min_values_.end());
        meta.max_value = *std::max_element(max_values_.begin(), max_values_.end());
        meta.scale = max_range / ((1 << config_.bits) - 1);
        meta.offset = meta.min_value;

        meta.max_quantization_error = metadata_.max_quantization_error;
        meta.mean_quantization_error = metadata_.mean_quantization_error;

        return meta;
    }

    bool is_calibrated() const { return calibrated_; }

    // 축별 스케일/오프셋 접근자 (HDF5 저장용)
    std::array<double, 3> get_scales() const { return scales_; }
    std::array<double, 3> get_min_values() const { return min_values_; }
    std::array<double, 3> get_max_values() const { return max_values_; }

    // 설정
    void set_bits(int bits) {
        if (bits != 8 && bits != 16 && bits != 32) {
            throw std::invalid_argument("Bits must be 8, 16, or 32");
        }
        config_.bits = bits;
    }

private:
    QuantizationConfig config_;
    bool calibrated_;

    std::array<double, 3> min_values_;
    std::array<double, 3> max_values_;
    std::array<double, 3> scales_;

    QuantizationMetadata metadata_;
};


/**
 * @brief Von Mises stress quantizer
 *
 * Practical accuracy requirements:
 * - Below threshold (default 0.1 MPa): accuracy not critical (noise level)
 * - Above threshold: ~1% relative error acceptable (100 MPa -> 101 MPa OK)
 *
 * Strategy:
 * - Logarithmic quantization for wide dynamic range
 * - 16-bit default (65536 levels)
 * - Values below threshold are clamped
 */
class VonMisesQuantizer {
public:
    VonMisesQuantizer()
        : config_(QuantizationConfig::create_von_mises_config())
        , calibrated_(false)
        , min_log_(0.0)
        , threshold_(0.1)  // 0.1 MPa - below this, accuracy doesn't matter
    {}

    /**
     * @brief Set threshold below which accuracy doesn't matter
     * @param threshold Threshold value in MPa (default 0.1)
     */
    void set_threshold(double threshold) {
        threshold_ = threshold;
    }

    /**
     * @brief Calibrate with data
     * @param data Von Mises stress values (MPa)
     */
    void calibrate(const std::vector<double>& data) {
        if (data.empty()) {
            throw std::invalid_argument("Cannot calibrate with empty data");
        }

        // Use threshold as minimum value for log scale
        // Values below threshold are clamped anyway
        min_value_ = threshold_;
        max_value_ = threshold_;

        for (double v : data) {
            if (v > threshold_) {
                max_value_ = std::max(max_value_, v);
            }
        }

        // Add 10% margin to max for safety
        max_value_ *= 1.1;

        // Log transform
        min_log_ = std::log(min_value_);
        double max_log = std::log(max_value_);

        // Calculate log range
        log_range_ = max_log - min_log_;
        if (log_range_ < 1e-10) {
            log_range_ = 1.0;  // Constant data
        }

        calibrated_ = true;

        // Calculate quantization error (only for values above threshold)
        double max_rel_err = 0.0;
        double sum_rel_err = 0.0;
        int count_above_threshold = 0;

        for (double v : data) {
            if (v >= threshold_) {
                uint16_t q = quantize(v);
                double dq = dequantize(q);

                double rel_err = std::abs(v - dq) / v * 100.0;
                max_rel_err = std::max(max_rel_err, rel_err);
                sum_rel_err += rel_err;
                count_above_threshold++;
            }
        }

        max_relative_error_ = max_rel_err;
        if (count_above_threshold > 0) {
            mean_relative_error_ = sum_rel_err / count_above_threshold;
        }

        metadata_.max_quantization_error = max_rel_err;
        metadata_.mean_quantization_error = mean_relative_error_;
    }

    /**
     * @brief Single value quantization (log scale)
     * Values below threshold are clamped to 0
     */
    uint16_t quantize(double value) const {
        if (!calibrated_) {
            throw std::runtime_error("Quantizer not calibrated");
        }

        // Clamp values below threshold to minimum
        double safe_value = std::max(value, threshold_);

        double log_value = std::log(safe_value);
        int max_quant = (1 << config_.bits) - 1;

        double normalized = (log_value - min_log_) / log_range_;
        normalized = std::clamp(normalized, 0.0, 1.0);

        return static_cast<uint16_t>(std::round(normalized * max_quant));
    }

    /**
     * @brief Dequantization
     */
    double dequantize(uint16_t q) const {
        if (!calibrated_) {
            throw std::runtime_error("Quantizer not calibrated");
        }

        int max_quant = (1 << config_.bits) - 1;
        double log_value = min_log_ + (static_cast<double>(q) / max_quant) * log_range_;
        return std::exp(log_value);
    }

    /**
     * @brief 배열 양자화
     */
    std::vector<uint16_t> quantize_array(const std::vector<double>& data) const {
        std::vector<uint16_t> result;
        result.reserve(data.size());

        for (double v : data) {
            result.push_back(quantize(v));
        }

        return result;
    }

    /**
     * @brief 배열 역양자화
     */
    std::vector<double> dequantize_array(const std::vector<uint16_t>& data) const {
        std::vector<double> result;
        result.reserve(data.size());

        for (uint16_t q : data) {
            result.push_back(dequantize(q));
        }

        return result;
    }

    /**
     * @brief Get metadata for HDF5 storage
     */
    QuantizationMetadata get_metadata() const {
        QuantizationMetadata meta;
        meta.physical_type = PhysicalType::STRESS_VON_MISES;
        meta.unit = Unit::MEGAPASCAL;
        meta.strategy = QuantizationStrategy::LOGARITHMIC;
        meta.bits = config_.bits;
        meta.min_value = min_value_;
        meta.max_value = max_value_;
        meta.precision = threshold_;  // Use threshold as effective precision
        meta.log_min = min_log_;
        meta.log_scale = log_range_;  // Store log range
        meta.max_quantization_error = max_relative_error_;
        meta.mean_quantization_error = mean_relative_error_;

        return meta;
    }

    bool is_calibrated() const { return calibrated_; }
    double get_max_relative_error() const { return max_relative_error_; }
    double get_mean_relative_error() const { return mean_relative_error_; }
    double get_threshold() const { return threshold_; }

    // Settings
    void set_bits(int bits) {
        if (bits != 8 && bits != 16 && bits != 32) {
            throw std::invalid_argument("Bits must be 8, 16, or 32");
        }
        config_.bits = bits;
    }

private:
    QuantizationConfig config_;
    bool calibrated_;

    double min_value_;
    double max_value_;
    double min_log_;
    double log_range_;
    double threshold_;
    double max_relative_error_ = 0.0;
    double mean_relative_error_ = 0.0;

    QuantizationMetadata metadata_;
};


/**
 * @brief 변형률(Strain) 양자화기
 *
 * 특성:
 * - 선형 양자화 (LINEAR)
 * - 기본 16-bit
 * - 목표 정밀도: 0.01% (0.0001)
 */
class StrainQuantizer {
public:
    StrainQuantizer()
        : calibrated_(false)
        , min_value_(0.0)
        , max_value_(0.0)
        , scale_(0.0)
        , bits_(16)
    {}

    /**
     * @brief 데이터로 캘리브레이션
     */
    void calibrate(const std::vector<double>& data) {
        if (data.empty()) {
            throw std::invalid_argument("Cannot calibrate with empty data");
        }

        min_value_ = *std::min_element(data.begin(), data.end());
        max_value_ = *std::max_element(data.begin(), data.end());

        double range = max_value_ - min_value_;
        int max_quant = (1 << bits_) - 1;

        if (range < 1e-15) {
            scale_ = 1.0;
        } else {
            scale_ = range / max_quant;
        }

        calibrated_ = true;
    }

    uint16_t quantize(double value) const {
        if (!calibrated_) {
            throw std::runtime_error("Quantizer not calibrated");
        }

        int max_quant = (1 << bits_) - 1;
        double range = max_value_ - min_value_;
        double normalized = (range > 1e-15) ?
            (value - min_value_) / range : 0.5;
        normalized = std::clamp(normalized, 0.0, 1.0);
        return static_cast<uint16_t>(std::round(normalized * max_quant));
    }

    double dequantize(uint16_t q) const {
        if (!calibrated_) {
            throw std::runtime_error("Quantizer not calibrated");
        }

        int max_quant = (1 << bits_) - 1;
        double range = max_value_ - min_value_;
        return min_value_ + (static_cast<double>(q) / max_quant) * range;
    }

    std::vector<uint16_t> quantize_array(const std::vector<double>& data) const {
        std::vector<uint16_t> result;
        result.reserve(data.size());
        for (double v : data) {
            result.push_back(quantize(v));
        }
        return result;
    }

    std::vector<double> dequantize_array(const std::vector<uint16_t>& data) const {
        std::vector<double> result;
        result.reserve(data.size());
        for (uint16_t q : data) {
            result.push_back(dequantize(q));
        }
        return result;
    }

    QuantizationMetadata get_metadata() const {
        QuantizationMetadata meta;
        meta.physical_type = PhysicalType::STRAIN;
        meta.unit = Unit::DIMENSIONLESS;
        meta.strategy = QuantizationStrategy::LINEAR;
        meta.bits = bits_;
        meta.min_value = min_value_;
        meta.max_value = max_value_;
        meta.scale = scale_;
        meta.offset = min_value_;
        meta.precision = 0.0001;  // 0.01%
        return meta;
    }

    bool is_calibrated() const { return calibrated_; }

private:
    bool calibrated_;
    double min_value_;
    double max_value_;
    double scale_;
    int bits_;
};

} // namespace quantization
} // namespace kood3plot
