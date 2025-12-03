cmake_minimum_required(VERSION 3.15)

project(KooD3plotReader
    VERSION 1.0.0
    DESCRIPTION "High-performance LS-DYNA d3plot file reader"
    LANGUAGES CXX
)

# C++17 standard required
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Build options
option(KOOD3PLOT_BUILD_TESTS "Build unit tests" ON)
option(KOOD3PLOT_BUILD_EXAMPLES "Build example programs" ON)
option(KOOD3PLOT_BUILD_V3_QUERY "Build V3 Query System" ON)
option(KOOD3PLOT_ENABLE_OPENMP "Enable OpenMP parallelization" ON)
option(KOOD3PLOT_ENABLE_SIMD "Enable SIMD optimizations" ON)

# Find OpenMP
if(KOOD3PLOT_ENABLE_OPENMP)
    find_package(OpenMP REQUIRED)
    if(OpenMP_CXX_FOUND)
        message(STATUS "OpenMP found: ${OpenMP_CXX_VERSION}")
    endif()
endif()

# Compiler flags
if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    add_compile_options(
        -Wall
        -Wextra
        -Wpedantic
        -Wno-unused-parameter
    )
    if(CMAKE_BUILD_TYPE MATCHES "Release")
        add_compile_options(-O3 -march=native)
        if(KOOD3PLOT_ENABLE_SIMD)
            add_compile_options(-msse4.2)
        endif()
    endif()
elseif(MSVC)
    add_compile_options(/W4)
    if(CMAKE_BUILD_TYPE MATCHES "Release")
        add_compile_options(/O2)
        if(KOOD3PLOT_ENABLE_SIMD)
            add_compile_options(/arch:AVX2)
        endif()
    endif()
endif()

# Library source files
set(KOOD3PLOT_SOURCES
    # Core
    src/core/BinaryReader.cpp
    src/core/FileFamily.cpp

    # Parsers
    src/parsers/ControlDataParser.cpp
    src/parsers/GeometryParser.cpp
    src/parsers/StateDataParser.cpp
    src/parsers/TitlesParser.cpp
    src/parsers/NARBSParser.cpp

    # Data structures
    src/data/ControlData.cpp
    src/data/Mesh.cpp
    src/data/StateData.cpp

    # Public API
    src/D3plotReader.cpp

    # Export utilities
    src/export/KeywordExporter.cpp

    # Analysis
    src/analysis/PartAnalyzer.cpp
    src/analysis/BoundingBox.cpp
)

# Library headers
set(KOOD3PLOT_HEADERS
    # Public headers
    include/kood3plot/Types.hpp
    include/kood3plot/Version.hpp
    include/kood3plot/Config.hpp
    include/kood3plot/D3plotReader.hpp

    # Core headers
    include/kood3plot/core/BinaryReader.hpp
    include/kood3plot/core/FileFamily.hpp
    include/kood3plot/core/Endian.hpp

    # Parser headers
    include/kood3plot/parsers/ControlDataParser.hpp
    include/kood3plot/parsers/GeometryParser.hpp
    include/kood3plot/parsers/StateDataParser.hpp
    include/kood3plot/parsers/TitlesParser.hpp
    include/kood3plot/parsers/NARBSParser.hpp

    # Data structure headers
    include/kood3plot/data/ControlData.hpp
    include/kood3plot/data/Mesh.hpp
    include/kood3plot/data/StateData.hpp

    # Export headers
    include/kood3plot/export/KeywordExporter.h

    # Analysis headers
    include/kood3plot/analysis/PartAnalyzer.hpp
    include/kood3plot/analysis/BoundingBox.hpp
)

# Create library target
add_library(kood3plot ${KOOD3PLOT_SOURCES} ${KOOD3PLOT_HEADERS})

# Set include directories
target_include_directories(kood3plot
    PUBLIC
        $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
        $<INSTALL_INTERFACE:include>
    PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/src
)

# Link OpenMP if enabled
if(KOOD3PLOT_ENABLE_OPENMP AND OpenMP_CXX_FOUND)
    target_link_libraries(kood3plot PUBLIC OpenMP::OpenMP_CXX)
endif()

# ============================================================
# V3 Query System Library (Optional)
# ============================================================
if(KOOD3PLOT_BUILD_V3_QUERY)
    message(STATUS "Building V3 Query System")

    # V3 Query System source files
    set(KOOD3PLOT_QUERY_SOURCES
        # Query system
        src/query/PartSelector.cpp
        src/query/QuantitySelector.cpp
        src/query/TimeSelector.cpp
        src/query/ValueFilter.cpp
        src/query/OutputSpec.cpp
        src/query/D3plotQuery.cpp
        src/query/QueryResult.cpp
        src/query/SpatialSelector.cpp
        src/query/ConfigParser.cpp

        # Streaming query (memory-efficient large file processing)
        src/query/StreamingQuery.cpp

        # Template system (Phase 5)
        src/query/QueryTemplate.cpp
        src/query/TemplateManager.cpp

        # Writers
        src/query/writers/CSVWriter.cpp
        src/query/writers/JSONWriter.cpp
        src/query/writers/HDF5Writer.cpp
    )

    # V3 Query System header files
    set(KOOD3PLOT_QUERY_HEADERS
        # Public query headers
        include/kood3plot/query/QueryTypes.h
        include/kood3plot/query/PartSelector.h
        include/kood3plot/query/QuantitySelector.h
        include/kood3plot/query/TimeSelector.h
        include/kood3plot/query/ValueFilter.h
        include/kood3plot/query/OutputSpec.h
        include/kood3plot/query/D3plotQuery.h
        include/kood3plot/query/QueryResult.h
        include/kood3plot/query/SpatialSelector.h
        include/kood3plot/query/ConfigParser.h

        # Streaming query (memory-efficient large file processing)
        include/kood3plot/query/StreamingQuery.hpp

        # Template system (Phase 5)
        include/kood3plot/query/QueryTemplate.h
        include/kood3plot/query/TemplateManager.h

        # Writers
        src/query/writers/CSVWriter.h
        src/query/writers/JSONWriter.h
        src/query/writers/HDF5Writer.h
    )

    # Create V3 Query System library
    add_library(kood3plot_query ${KOOD3PLOT_QUERY_SOURCES} ${KOOD3PLOT_QUERY_HEADERS})

    # Set include directories for V3
    target_include_directories(kood3plot_query
        PUBLIC
            $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
            $<INSTALL_INTERFACE:include>
        PRIVATE
            ${CMAKE_CURRENT_SOURCE_DIR}/src
            ${CMAKE_CURRENT_SOURCE_DIR}/src/query
    )

    # Link with main kood3plot library
    target_link_libraries(kood3plot_query PUBLIC kood3plot)

    # Install V3 Query System library
    install(TARGETS kood3plot_query
        EXPORT KooD3plotTargets
        ARCHIVE DESTINATION lib
        LIBRARY DESTINATION lib
        RUNTIME DESTINATION bin
    )

    # Install V3 Query System headers
    install(DIRECTORY include/kood3plot/query
        DESTINATION include/kood3plot
        FILES_MATCHING PATTERN "*.h"
    )

    message(STATUS "V3 Query System library configured")
endif()

# ============================================================
# V4 Render System Library (Optional)
# ============================================================
option(KOOD3PLOT_BUILD_V4_RENDER "Build V4 LSPrePost Renderer" ON)

if(KOOD3PLOT_BUILD_V4_RENDER)
    message(STATUS "Building V4 Render System")

    # V4 Render System source files
    set(KOOD3PLOT_RENDER_SOURCES
        src/render/LSPrePostRenderer.cpp
        src/render/BatchRenderer.cpp
        src/render/ProgressMonitor.cpp
        src/render/RenderConfig.cpp
        src/render/GeometryAnalyzer.cpp
        src/render/MultiRunProcessor.cpp
        src/render/D3plotCache.cpp
    )

    # V4 Render System header files
    set(KOOD3PLOT_RENDER_HEADERS
        include/kood3plot/render/LSPrePostRenderer.h
        include/kood3plot/render/BatchRenderer.h
        include/kood3plot/render/ProgressMonitor.h
        include/kood3plot/render/RenderConfig.h
        include/kood3plot/render/GeometryAnalyzer.h
        include/kood3plot/render/MultiRunProcessor.h
        include/kood3plot/render/D3plotCache.h
    )

    # Create V4 Render System library
    add_library(kood3plot_render ${KOOD3PLOT_RENDER_SOURCES} ${KOOD3PLOT_RENDER_HEADERS})

    # Set include directories for V4
    target_include_directories(kood3plot_render
        PUBLIC
            $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
            $<INSTALL_INTERFACE:include>
        PRIVATE
            ${CMAKE_CURRENT_SOURCE_DIR}/src
    )

    # Link with main kood3plot library
    target_link_libraries(kood3plot_render PUBLIC kood3plot)

    # Install V4 Render System library
    install(TARGETS kood3plot_render
        EXPORT KooD3plotTargets
        ARCHIVE DESTINATION lib
        LIBRARY DESTINATION lib
        RUNTIME DESTINATION bin
    )

    # Install V4 Render System headers
    install(DIRECTORY include/kood3plot/render
        DESTINATION include/kood3plot
        FILES_MATCHING PATTERN "*.h"
    )

    message(STATUS "V4 Render System library configured")
endif()

# ============================================================
# CLI Tool (requires V3 Query System)
# ============================================================
if(KOOD3PLOT_BUILD_V3_QUERY)
    add_executable(kood3plot_cli src/cli/kood3plot_cli.cpp)
    target_link_libraries(kood3plot_cli PRIVATE kood3plot_query kood3plot)
    target_include_directories(kood3plot_cli PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/src/query
    )

    # Link with V4 render library if enabled
    if(KOOD3PLOT_BUILD_V4_RENDER)
        target_link_libraries(kood3plot_cli PRIVATE kood3plot_render)
    endif()

    install(TARGETS kood3plot_cli
        RUNTIME DESTINATION bin
    )

    message(STATUS "CLI tool configured")
endif()

# Configure version header
configure_file(
    ${CMAKE_CURRENT_SOURCE_DIR}/include/kood3plot/Version.hpp.in
    ${CMAKE_CURRENT_SOURCE_DIR}/include/kood3plot/Version.hpp
    @ONLY
)

# Testing
if(KOOD3PLOT_BUILD_TESTS)
    enable_testing()

    # Find Google Test
    find_package(GTest QUIET)
    if(NOT GTest_FOUND)
        # Download and build Google Test
        include(FetchContent)
        FetchContent_Declare(
            googletest
            GIT_REPOSITORY https://github.com/google/googletest.git
            GIT_TAG release-1.12.1
        )
        # For Windows: Prevent overriding the parent project's compiler/linker settings
        set(gtest_force_shared_crt ON CACHE BOOL "" FORCE)
        FetchContent_MakeAvailable(googletest)
    endif()

    add_subdirectory(tests)
endif()

# Examples
if(KOOD3PLOT_BUILD_EXAMPLES)
    add_subdirectory(examples)
endif()

# Installation
install(TARGETS kood3plot
    EXPORT KooD3plotTargets
    ARCHIVE DESTINATION lib
    LIBRARY DESTINATION lib
    RUNTIME DESTINATION bin
)

install(DIRECTORY include/kood3plot
    DESTINATION include
    FILES_MATCHING PATTERN "*.hpp"
)

# Export targets
install(EXPORT KooD3plotTargets
    FILE KooD3plotTargets.cmake
    NAMESPACE KooD3plot::
    DESTINATION lib/cmake/KooD3plot
)

# Create config file
include(CMakePackageConfigHelpers)
write_basic_package_version_file(
    KooD3plotConfigVersion.cmake
    VERSION ${PROJECT_VERSION}
    COMPATIBILITY SameMajorVersion
)

install(FILES
    ${CMAKE_CURRENT_BINARY_DIR}/KooD3plotConfigVersion.cmake
    DESTINATION lib/cmake/KooD3plot
)
