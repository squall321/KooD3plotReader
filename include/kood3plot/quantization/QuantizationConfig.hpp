#pragma once

#include <string>
#include <cmath>
#include <stdexcept>

namespace kood3plot {
namespace quantization {

/**
 * @brief Physical quantity types for automatic quantization
 *
 * Each type has associated units and precision requirements
 * that determine optimal bit depth.
 */
enum class PhysicalType {
    DISPLACEMENT,        // Linear motion (mm)
    VELOCITY,           // Linear velocity (mm/s)
    ACCELERATION,       // Linear acceleration (mm/s^2)
    STRESS_VON_MISES,   // Von Mises stress (MPa)
    STRESS_COMPONENT,   // Stress tensor component (MPa)
    STRAIN,             // Engineering strain (dimensionless)
    FORCE,              // Force (N)
    ENERGY,             // Energy (J)
    TEMPERATURE,        // Temperature (°C or K)
    PRESSURE,           // Pressure (MPa)
    CUSTOM              // User-defined
};

/**
 * @brief Unit system for physical quantities
 */
enum class Unit {
    // Length
    MILLIMETER,
    METER,
    CENTIMETER,

    // Stress/Pressure
    MEGAPASCAL,
    PASCAL,
    GIGAPASCAL,

    // Force
    NEWTON,
    KILONEWTON,

    // Energy
    JOULE,
    MILLIJOULE,

    // Temperature
    CELSIUS,
    KELVIN,

    // Dimensionless
    DIMENSIONLESS
};

/**
 * @brief Quantization strategy
 */
enum class QuantizationStrategy {
    LINEAR,      // Linear quantization: Q = (value - min) / (max - min) * (2^bits - 1)
    LOGARITHMIC  // Log quantization for wide-range data (e.g., Von Mises 0.001-1000 MPa)
};

/**
 * @brief Quantization configuration for a physical quantity
 *
 * Week 1-2 Goal: Implement automatic bit-depth calculation based on
 * physical type, unit, and required precision.
 */
struct QuantizationConfig {
    PhysicalType physical_type;
    Unit unit;
    QuantizationStrategy strategy;

    // Precision requirement (e.g., 0.01 mm for displacement)
    double required_precision;

    // Data range (will be computed from actual data)
    double min_value;
    double max_value;

    // Computed quantization parameters
    int bits;           // Number of bits (8, 16, 32)
    double scale;       // Scale factor for dequantization
    double offset;      // Offset for dequantization

    /**
     * @brief Default constructor
     */
    QuantizationConfig()
        : physical_type(PhysicalType::CUSTOM)
        , unit(Unit::DIMENSIONLESS)
        , strategy(QuantizationStrategy::LINEAR)
        , required_precision(0.01)
        , min_value(0.0)
        , max_value(1.0)
        , bits(16)
        , scale(1.0)
        , offset(0.0)
    {}

    /**
     * @brief Create default config for displacement (mm)
     *
     * Precision: 0.01 mm
     * Bits: 16 (65536 levels)
     * Strategy: Linear
     */
    static QuantizationConfig create_displacement_config() {
        QuantizationConfig config;
        config.physical_type = PhysicalType::DISPLACEMENT;
        config.unit = Unit::MILLIMETER;
        config.strategy = QuantizationStrategy::LINEAR;
        config.required_precision = 0.01;  // 0.01 mm precision
        config.bits = 16;  // 65536 levels
        return config;
    }

    /**
     * @brief Create default config for Von Mises stress (MPa)
     *
     * Precision: 2% relative error
     * Bits: 16
     * Strategy: Logarithmic (handles 0.001-1000 MPa range)
     */
    static QuantizationConfig create_von_mises_config() {
        QuantizationConfig config;
        config.physical_type = PhysicalType::STRESS_VON_MISES;
        config.unit = Unit::MEGAPASCAL;
        config.strategy = QuantizationStrategy::LOGARITHMIC;
        config.required_precision = 0.02;  // 2% relative error
        config.bits = 16;
        return config;
    }

    /**
     * @brief Create default config for strain
     *
     * Precision: 0.0001 (0.01% strain)
     * Bits: 16
     * Strategy: Linear
     */
    static QuantizationConfig create_strain_config() {
        QuantizationConfig config;
        config.physical_type = PhysicalType::STRAIN;
        config.unit = Unit::DIMENSIONLESS;
        config.strategy = QuantizationStrategy::LINEAR;
        config.required_precision = 0.0001;  // 0.01% strain
        config.bits = 16;
        return config;
    }

    /**
     * @brief Compute required bits based on precision and range
     *
     * Week 1-2 Goal: Automatic bit-depth calculation
     *
     * Formula: bits = ceil(log2((max - min) / precision))
     *
     * @param data_min Minimum value in dataset
     * @param data_max Maximum value in dataset
     * @return Required number of bits (clamped to 8, 16, or 32)
     */
    int compute_required_bits(double data_min, double data_max) {
        min_value = data_min;
        max_value = data_max;

        double range = max_value - min_value;

        if (range < 1e-10) {
            // Constant data, use minimal bits
            bits = 8;
            return bits;
        }

        // Calculate required levels
        double required_levels = range / required_precision;

        // Calculate bits (round up)
        int required_bits = static_cast<int>(std::ceil(std::log2(required_levels)));

        // Clamp to standard sizes: 8, 16, or 32 bits
        if (required_bits <= 8) {
            bits = 8;
        } else if (required_bits <= 16) {
            bits = 16;
        } else {
            bits = 32;
        }

        // Compute scale and offset for linear quantization
        if (strategy == QuantizationStrategy::LINEAR) {
            int max_quantized = (1 << bits) - 1;  // 2^bits - 1
            scale = range / max_quantized;
            offset = min_value;
        }

        return bits;
    }

    /**
     * @brief Get human-readable name for physical type
     */
    std::string get_physical_type_name() const {
        switch (physical_type) {
            case PhysicalType::DISPLACEMENT: return "Displacement";
            case PhysicalType::VELOCITY: return "Velocity";
            case PhysicalType::ACCELERATION: return "Acceleration";
            case PhysicalType::STRESS_VON_MISES: return "Von Mises Stress";
            case PhysicalType::STRESS_COMPONENT: return "Stress Component";
            case PhysicalType::STRAIN: return "Strain";
            case PhysicalType::FORCE: return "Force";
            case PhysicalType::ENERGY: return "Energy";
            case PhysicalType::TEMPERATURE: return "Temperature";
            case PhysicalType::PRESSURE: return "Pressure";
            case PhysicalType::CUSTOM: return "Custom";
            default: return "Unknown";
        }
    }

    /**
     * @brief Get human-readable unit name
     */
    std::string get_unit_name() const {
        switch (unit) {
            case Unit::MILLIMETER: return "mm";
            case Unit::METER: return "m";
            case Unit::CENTIMETER: return "cm";
            case Unit::MEGAPASCAL: return "MPa";
            case Unit::PASCAL: return "Pa";
            case Unit::GIGAPASCAL: return "GPa";
            case Unit::NEWTON: return "N";
            case Unit::KILONEWTON: return "kN";
            case Unit::JOULE: return "J";
            case Unit::MILLIJOULE: return "mJ";
            case Unit::CELSIUS: return "°C";
            case Unit::KELVIN: return "K";
            case Unit::DIMENSIONLESS: return "";
            default: return "?";
        }
    }
};

} // namespace quantization
} // namespace kood3plot
