# Unit tests for KooD3plotReader

# VectorMath tests
add_executable(test_vector_math test_vector_math.cpp)
target_link_libraries(test_vector_math PRIVATE kood3plot)
target_include_directories(test_vector_math PRIVATE ${CMAKE_SOURCE_DIR}/include)

# AnalysisResult tests
add_executable(test_analysis_result test_analysis_result.cpp)
target_link_libraries(test_analysis_result PRIVATE kood3plot)
target_include_directories(test_analysis_result PRIVATE ${CMAKE_SOURCE_DIR}/include)

# SurfaceExtractor tests
add_executable(test_surface_extractor test_surface_extractor.cpp)
target_link_libraries(test_surface_extractor PRIVATE kood3plot)
target_include_directories(test_surface_extractor PRIVATE ${CMAKE_SOURCE_DIR}/include)

# SurfaceStressAnalyzer tests
add_executable(test_surface_stress test_surface_stress.cpp)
target_link_libraries(test_surface_stress PRIVATE kood3plot)
target_include_directories(test_surface_stress PRIVATE ${CMAKE_SOURCE_DIR}/include)

# TimeHistoryAnalyzer tests
add_executable(test_time_history test_time_history.cpp)
target_link_libraries(test_time_history PRIVATE kood3plot)
target_include_directories(test_time_history PRIVATE ${CMAKE_SOURCE_DIR}/include)

# ============================================================
# Phase 1: HDF5 Quantization System Tests
# ============================================================
if(KOOD3PLOT_BUILD_HDF5 AND HDF5_FOUND)
    message(STATUS "Adding Phase 1 HDF5 tests")

    # HDF5Writer tests
    add_executable(test_hdf5_writer hdf5/test_hdf5_writer.cpp)
    target_link_libraries(test_hdf5_writer
        PRIVATE
            kood3plot_hdf5
            kood3plot
            GTest::gtest
            GTest::gtest_main
            ${HDF5_CXX_LIBRARIES}
    )
    target_include_directories(test_hdf5_writer
        PRIVATE
            ${CMAKE_SOURCE_DIR}/include
            ${HDF5_INCLUDE_DIRS}
    )

    # Add test to CTest
    add_test(NAME HDF5Writer COMMAND test_hdf5_writer)

    # Week 2: Quantization tests
    add_executable(test_quantization hdf5/test_quantization.cpp)
    target_link_libraries(test_quantization
        PRIVATE
            kood3plot_hdf5
            kood3plot
            GTest::gtest
            GTest::gtest_main
            ${HDF5_CXX_LIBRARIES}
    )
    target_include_directories(test_quantization
        PRIVATE
            ${CMAKE_SOURCE_DIR}/include
            ${HDF5_INCLUDE_DIRS}
    )
    add_test(NAME Quantization COMMAND test_quantization)

    message(STATUS "Phase 1 HDF5 tests configured")
endif()
