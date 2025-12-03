#pragma once

// OpenMP support detection
#ifdef _OPENMP
    #define KOOD3PLOT_HAS_OPENMP 1
    #include <omp.h>
#else
    #define KOOD3PLOT_HAS_OPENMP 0
#endif

// SIMD support detection
#if defined(__SSE4_2__) || defined(__AVX2__)
    #define KOOD3PLOT_HAS_SIMD 1
    #ifdef __AVX2__
        #define KOOD3PLOT_HAS_AVX2 1
        #include <immintrin.h>
    #elif defined(__SSE4_2__)
        #define KOOD3PLOT_HAS_SSE42 1
        #include <nmmintrin.h>
    #endif
#else
    #define KOOD3PLOT_HAS_SIMD 0
#endif

// Platform detection
#if defined(_WIN32) || defined(_WIN64)
    #define KOOD3PLOT_PLATFORM_WINDOWS 1
    #define KOOD3PLOT_PLATFORM_UNIX 0
#elif defined(__unix__) || defined(__unix) || defined(__linux__) || defined(__APPLE__)
    #define KOOD3PLOT_PLATFORM_WINDOWS 0
    #define KOOD3PLOT_PLATFORM_UNIX 1
#else
    #define KOOD3PLOT_PLATFORM_WINDOWS 0
    #define KOOD3PLOT_PLATFORM_UNIX 0
#endif

// Compiler detection
#if defined(__GNUC__) || defined(__GNUG__)
    #define KOOD3PLOT_COMPILER_GCC 1
    #define KOOD3PLOT_COMPILER_CLANG 0
    #define KOOD3PLOT_COMPILER_MSVC 0
#elif defined(__clang__)
    #define KOOD3PLOT_COMPILER_GCC 0
    #define KOOD3PLOT_COMPILER_CLANG 1
    #define KOOD3PLOT_COMPILER_MSVC 0
#elif defined(_MSC_VER)
    #define KOOD3PLOT_COMPILER_GCC 0
    #define KOOD3PLOT_COMPILER_CLANG 0
    #define KOOD3PLOT_COMPILER_MSVC 1
#else
    #define KOOD3PLOT_COMPILER_GCC 0
    #define KOOD3PLOT_COMPILER_CLANG 0
    #define KOOD3PLOT_COMPILER_MSVC 0
#endif

// Debug/Release build detection
#if defined(NDEBUG)
    #define KOOD3PLOT_BUILD_DEBUG 0
    #define KOOD3PLOT_BUILD_RELEASE 1
#else
    #define KOOD3PLOT_BUILD_DEBUG 1
    #define KOOD3PLOT_BUILD_RELEASE 0
#endif

// Inline hint
#if KOOD3PLOT_COMPILER_MSVC
    #define KOOD3PLOT_INLINE __forceinline
#else
    #define KOOD3PLOT_INLINE inline __attribute__((always_inline))
#endif

// Alignment
#if KOOD3PLOT_COMPILER_MSVC
    #define KOOD3PLOT_ALIGN(x) __declspec(align(x))
#else
    #define KOOD3PLOT_ALIGN(x) __attribute__((aligned(x)))
#endif

// Likely/unlikely branch prediction hints (C++20 has [[likely]]/[[unlikely]], but we're on C++17)
#if KOOD3PLOT_COMPILER_GCC || KOOD3PLOT_COMPILER_CLANG
    #define KOOD3PLOT_LIKELY(x) __builtin_expect(!!(x), 1)
    #define KOOD3PLOT_UNLIKELY(x) __builtin_expect(!!(x), 0)
#else
    #define KOOD3PLOT_LIKELY(x) (x)
    #define KOOD3PLOT_UNLIKELY(x) (x)
#endif

namespace kood3plot {
namespace config {

/**
 * @brief Default buffer size for file I/O (in bytes)
 */
constexpr size_t DEFAULT_BUFFER_SIZE = 8 * 1024 * 1024; // 8 MB

/**
 * @brief Maximum number of parallel threads for OpenMP
 * Set to 0 to use all available cores
 */
constexpr int MAX_THREADS = 0;

/**
 * @brief Enable validation checks (affects performance)
 */
constexpr bool ENABLE_VALIDATION = KOOD3PLOT_BUILD_DEBUG;

/**
 * @brief Enable verbose logging
 */
constexpr bool ENABLE_LOGGING = KOOD3PLOT_BUILD_DEBUG;

} // namespace config
} // namespace kood3plot
