#include <gtest/gtest.h>
#include <kood3plot/quantization/Quantizers.hpp>
#include <kood3plot/quantization/QuantizationConfig.hpp>
#include <kood3plot/analysis/VectorMath.hpp>

#include <vector>
#include <cmath>
#include <random>
#include <iostream>
#include <iomanip>

using namespace kood3plot;
using namespace kood3plot::quantization;

// ============================================================
// DisplacementQuantizer Tests
// ============================================================

class DisplacementQuantizerTest : public ::testing::Test {
protected:
    void SetUp() override {
        // Generate test displacement data
        std::mt19937 gen(42);  // Fixed seed for reproducibility
        std::uniform_real_distribution<> dis(-100.0, 100.0);

        test_data_.reserve(10000);
        for (int i = 0; i < 10000; ++i) {
            test_data_.push_back(Vec3{dis(gen), dis(gen), dis(gen)});
        }
    }

    std::vector<Vec3> test_data_;
};

TEST_F(DisplacementQuantizerTest, BasicQuantizeDequantize) {
    DisplacementQuantizer quantizer;
    quantizer.calibrate(test_data_);

    EXPECT_TRUE(quantizer.is_calibrated());

    // Test single value
    Vec3 original{10.5, -20.3, 45.7};
    auto quantized = quantizer.quantize(original);
    Vec3 dequantized = quantizer.dequantize(quantized);

    // Check precision (should be < 0.01mm for 16-bit)
    double error = (original - dequantized).magnitude();
    EXPECT_LT(error, 0.01);  // Week 2 target: 0.01mm precision
}

TEST_F(DisplacementQuantizerTest, ArrayQuantization) {
    DisplacementQuantizer quantizer;
    quantizer.calibrate(test_data_);

    auto quantized = quantizer.quantize_array(test_data_);
    auto dequantized = quantizer.dequantize_array(quantized);

    EXPECT_EQ(dequantized.size(), test_data_.size());

    // Check precision for all values
    double max_error = 0.0;
    double sum_error = 0.0;

    for (size_t i = 0; i < test_data_.size(); ++i) {
        double error = (test_data_[i] - dequantized[i]).magnitude();
        max_error = std::max(max_error, error);
        sum_error += error;
    }

    double mean_error = sum_error / test_data_.size();

    std::cout << "[DisplacementQuantizer] 10k vectors:\n";
    std::cout << "  Max error:  " << std::fixed << std::setprecision(6)
              << max_error << " mm\n";
    std::cout << "  Mean error: " << mean_error << " mm\n";

    // Week 2 target: max error < 0.01mm for typical displacement data
    // With range of -100 to 100mm and 16-bit, step size is ~0.003mm
    EXPECT_LT(max_error, 0.01);
}

TEST_F(DisplacementQuantizerTest, CompressionRatio) {
    DisplacementQuantizer quantizer;
    quantizer.calibrate(test_data_);

    auto quantized = quantizer.quantize_array(test_data_);

    // Original: 10000 * 3 * 8 bytes (double) = 240,000 bytes
    // Quantized: 10000 * 3 * 2 bytes (uint16) = 60,000 bytes
    // Expected ratio: 25% (4x compression)

    size_t original_size = test_data_.size() * 3 * sizeof(double);
    size_t quantized_size = quantized.size() * sizeof(uint16_t);

    double ratio = 100.0 * quantized_size / original_size;

    std::cout << "  Original size:  " << original_size << " bytes\n";
    std::cout << "  Quantized size: " << quantized_size << " bytes\n";
    std::cout << "  Compression:    " << std::fixed << std::setprecision(1)
              << (100.0 - ratio) << "% saved\n";

    EXPECT_LT(ratio, 30.0);  // Should be ~25%
}

TEST_F(DisplacementQuantizerTest, MetadataGeneration) {
    DisplacementQuantizer quantizer;
    quantizer.calibrate(test_data_);

    auto metadata = quantizer.get_metadata();

    EXPECT_EQ(metadata.physical_type, PhysicalType::DISPLACEMENT);
    EXPECT_EQ(metadata.unit, Unit::MILLIMETER);
    EXPECT_EQ(metadata.strategy, QuantizationStrategy::LINEAR);
    EXPECT_EQ(metadata.bits, 16);
    EXPECT_GT(metadata.max_value, metadata.min_value);
}

TEST_F(DisplacementQuantizerTest, ExtremeValues) {
    // Test with very large and very small values
    std::vector<Vec3> extreme_data = {
        {0.001, 0.001, 0.001},      // Very small
        {1000.0, 1000.0, 1000.0},   // Very large
        {-1000.0, 500.0, -500.0},   // Mixed
        {0.0, 0.0, 0.0}             // Zero
    };

    DisplacementQuantizer quantizer;
    quantizer.calibrate(extreme_data);

    for (const auto& v : extreme_data) {
        auto q = quantizer.quantize(v);
        auto dq = quantizer.dequantize(q);

        // For extreme range, precision is lower
        double error = (v - dq).magnitude();
        double max_expected_error = 2000.0 / 65536 * std::sqrt(3.0);  // ~0.053mm

        EXPECT_LT(error, max_expected_error * 1.1);  // 10% margin
    }
}

// ============================================================
// VonMisesQuantizer Tests
// ============================================================

class VonMisesQuantizerTest : public ::testing::Test {
protected:
    void SetUp() override {
        // Generate test Von Mises stress data (log-uniform distribution)
        std::mt19937 gen(42);
        std::uniform_real_distribution<> log_dis(-3, 4);  // 0.001 to 10000 MPa

        test_data_.reserve(10000);
        for (int i = 0; i < 10000; ++i) {
            test_data_.push_back(std::pow(10.0, log_dis(gen)));
        }
    }

    std::vector<double> test_data_;
};

TEST_F(VonMisesQuantizerTest, BasicQuantizeDequantize) {
    VonMisesQuantizer quantizer;
    quantizer.calibrate(test_data_);

    EXPECT_TRUE(quantizer.is_calibrated());

    // Test single value
    double original = 250.5;  // MPa
    uint16_t quantized = quantizer.quantize(original);
    double dequantized = quantizer.dequantize(quantized);

    // Check relative error (should be < 2% for log quantization)
    double rel_error = std::abs(original - dequantized) / original * 100.0;

    std::cout << "[VonMisesQuantizer] Single value test:\n";
    std::cout << "  Original:    " << original << " MPa\n";
    std::cout << "  Dequantized: " << dequantized << " MPa\n";
    std::cout << "  Rel. error:  " << std::fixed << std::setprecision(4)
              << rel_error << "%\n";

    EXPECT_LT(rel_error, 2.0);  // Week 2 target: < 2% relative error
}

TEST_F(VonMisesQuantizerTest, ArrayQuantization) {
    VonMisesQuantizer quantizer;
    quantizer.calibrate(test_data_);

    auto quantized = quantizer.quantize_array(test_data_);
    auto dequantized = quantizer.dequantize_array(quantized);

    EXPECT_EQ(dequantized.size(), test_data_.size());

    // Check relative error for all values
    double max_rel_error = 0.0;
    double sum_rel_error = 0.0;

    for (size_t i = 0; i < test_data_.size(); ++i) {
        if (test_data_[i] > 1e-6) {
            double rel_error = std::abs(test_data_[i] - dequantized[i]) / test_data_[i] * 100.0;
            max_rel_error = std::max(max_rel_error, rel_error);
            sum_rel_error += rel_error;
        }
    }

    double mean_rel_error = sum_rel_error / test_data_.size();

    std::cout << "[VonMisesQuantizer] 10k values (0.001-10000 MPa):\n";
    std::cout << "  Max rel. error:  " << std::fixed << std::setprecision(4)
              << max_rel_error << "%\n";
    std::cout << "  Mean rel. error: " << mean_rel_error << "%\n";

    // Week 2 target: max relative error < 2%
    // With 16-bit log quantization over 7 decades, ~0.1% step
    EXPECT_LT(max_rel_error, 2.0);
}

TEST_F(VonMisesQuantizerTest, LogarithmicBehavior) {
    // Test that log quantization handles wide range well
    std::vector<double> wide_range = {
        0.001,    // Very small stress
        0.1,
        1.0,
        10.0,
        100.0,
        1000.0,
        10000.0   // Very high stress
    };

    VonMisesQuantizer quantizer;
    quantizer.calibrate(wide_range);

    for (double v : wide_range) {
        uint16_t q = quantizer.quantize(v);
        double dq = quantizer.dequantize(q);

        double rel_error = std::abs(v - dq) / v * 100.0;

        std::cout << "  " << std::setw(8) << v << " MPa -> "
                  << std::setw(5) << q << " -> "
                  << std::setw(10) << std::fixed << std::setprecision(4) << dq
                  << " MPa (error: " << rel_error << "%)\n";

        EXPECT_LT(rel_error, 2.0);
    }
}

TEST_F(VonMisesQuantizerTest, CompressionRatio) {
    VonMisesQuantizer quantizer;
    quantizer.calibrate(test_data_);

    auto quantized = quantizer.quantize_array(test_data_);

    // Original: 10000 * 8 bytes (double) = 80,000 bytes
    // Quantized: 10000 * 2 bytes (uint16) = 20,000 bytes
    // Expected ratio: 25% (4x compression)

    size_t original_size = test_data_.size() * sizeof(double);
    size_t quantized_size = quantized.size() * sizeof(uint16_t);

    double ratio = 100.0 * quantized_size / original_size;

    std::cout << "  Original size:  " << original_size << " bytes\n";
    std::cout << "  Quantized size: " << quantized_size << " bytes\n";
    std::cout << "  Compression:    " << std::fixed << std::setprecision(1)
              << (100.0 - ratio) << "% saved\n";

    EXPECT_LT(ratio, 30.0);  // Should be ~25%
}

// ============================================================
// StrainQuantizer Tests
// ============================================================

TEST(StrainQuantizerTest, BasicQuantization) {
    std::vector<double> strain_data;
    std::mt19937 gen(42);
    std::uniform_real_distribution<> dis(-0.1, 0.5);  // -10% to 50% strain

    for (int i = 0; i < 1000; ++i) {
        strain_data.push_back(dis(gen));
    }

    StrainQuantizer quantizer;
    quantizer.calibrate(strain_data);

    EXPECT_TRUE(quantizer.is_calibrated());

    auto quantized = quantizer.quantize_array(strain_data);
    auto dequantized = quantizer.dequantize_array(quantized);

    double max_error = 0.0;
    for (size_t i = 0; i < strain_data.size(); ++i) {
        double error = std::abs(strain_data[i] - dequantized[i]);
        max_error = std::max(max_error, error);
    }

    std::cout << "[StrainQuantizer] 1k values (-0.1 to 0.5):\n";
    std::cout << "  Max error: " << std::scientific << std::setprecision(4)
              << max_error << "\n";

    // Target: 0.01% strain precision = 0.0001
    // With range 0.6 and 16-bit: step = 0.6/65536 ≈ 0.000009
    EXPECT_LT(max_error, 0.0001);
}

// ============================================================
// QuantizationConfig Tests
// ============================================================

TEST(QuantizationConfigTest, AutoBitCalculation) {
    QuantizationConfig config;
    config.required_precision = 0.01;

    // Range 100, precision 0.01 -> need 10000 levels -> 14 bits -> rounds to 16
    int bits = config.compute_required_bits(0.0, 100.0);
    EXPECT_EQ(bits, 16);

    // Range 1, precision 0.01 -> need 100 levels -> 7 bits -> rounds to 8
    config.required_precision = 0.01;
    bits = config.compute_required_bits(0.0, 1.0);
    EXPECT_EQ(bits, 8);

    // Range 1000000, precision 0.001 -> need 1e9 levels -> 30 bits -> rounds to 32
    config.required_precision = 0.001;
    bits = config.compute_required_bits(0.0, 1000000.0);
    EXPECT_EQ(bits, 32);
}

TEST(QuantizationConfigTest, DefaultConfigs) {
    auto disp_config = QuantizationConfig::create_displacement_config();
    EXPECT_EQ(disp_config.physical_type, PhysicalType::DISPLACEMENT);
    EXPECT_EQ(disp_config.unit, Unit::MILLIMETER);
    EXPECT_EQ(disp_config.strategy, QuantizationStrategy::LINEAR);
    EXPECT_DOUBLE_EQ(disp_config.required_precision, 0.01);

    auto vm_config = QuantizationConfig::create_von_mises_config();
    EXPECT_EQ(vm_config.physical_type, PhysicalType::STRESS_VON_MISES);
    EXPECT_EQ(vm_config.unit, Unit::MEGAPASCAL);
    EXPECT_EQ(vm_config.strategy, QuantizationStrategy::LOGARITHMIC);
    EXPECT_DOUBLE_EQ(vm_config.required_precision, 0.02);  // 2%

    auto strain_config = QuantizationConfig::create_strain_config();
    EXPECT_EQ(strain_config.physical_type, PhysicalType::STRAIN);
    EXPECT_EQ(strain_config.unit, Unit::DIMENSIONLESS);
    EXPECT_DOUBLE_EQ(strain_config.required_precision, 0.0001);
}

// ============================================================
// Benchmark Tests
// ============================================================

TEST(QuantizationBenchmark, LargeDataset) {
    const size_t NUM_VECTORS = 100000;

    // Generate large dataset
    std::vector<Vec3> displacement_data;
    std::vector<double> stress_data;

    std::mt19937 gen(42);
    std::uniform_real_distribution<> disp_dis(-500.0, 500.0);
    std::uniform_real_distribution<> stress_log_dis(-2, 3);

    displacement_data.reserve(NUM_VECTORS);
    stress_data.reserve(NUM_VECTORS);

    for (size_t i = 0; i < NUM_VECTORS; ++i) {
        displacement_data.push_back(Vec3{disp_dis(gen), disp_dis(gen), disp_dis(gen)});
        stress_data.push_back(std::pow(10.0, stress_log_dis(gen)));
    }

    std::cout << "\n[Benchmark] 100k elements:\n";

    // Displacement quantization
    {
        DisplacementQuantizer quantizer;
        auto start = std::chrono::high_resolution_clock::now();

        quantizer.calibrate(displacement_data);
        auto quantized = quantizer.quantize_array(displacement_data);
        auto dequantized = quantizer.dequantize_array(quantized);

        auto end = std::chrono::high_resolution_clock::now();
        auto duration = std::chrono::duration<double, std::milli>(end - start).count();

        std::cout << "  Displacement: " << std::fixed << std::setprecision(2)
                  << duration << " ms\n";
        std::cout << "    Throughput: "
                  << (NUM_VECTORS * 3 * sizeof(double) / 1024.0 / 1024.0) / (duration / 1000.0)
                  << " MB/s\n";
    }

    // Von Mises quantization
    {
        VonMisesQuantizer quantizer;
        auto start = std::chrono::high_resolution_clock::now();

        quantizer.calibrate(stress_data);
        auto quantized = quantizer.quantize_array(stress_data);
        auto dequantized = quantizer.dequantize_array(quantized);

        auto end = std::chrono::high_resolution_clock::now();
        auto duration = std::chrono::duration<double, std::milli>(end - start).count();

        std::cout << "  Von Mises:    " << std::fixed << std::setprecision(2)
                  << duration << " ms\n";
        std::cout << "    Throughput: "
                  << (NUM_VECTORS * sizeof(double) / 1024.0 / 1024.0) / (duration / 1000.0)
                  << " MB/s\n";
    }
}

// Main
int main(int argc, char** argv) {
    ::testing::InitGoogleTest(&argc, argv);
    return RUN_ALL_TESTS();
}
