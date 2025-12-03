# Example programs

# Test BinaryReader
add_executable(test_binary_reader test_binary_reader.cpp)
target_link_libraries(test_binary_reader PRIVATE kood3plot)

# Test ControlDataParser
add_executable(test_control_data test_control_data.cpp)
target_link_libraries(test_control_data PRIVATE kood3plot)

# Test GeometryParser
add_executable(test_geometry test_geometry.cpp)
target_link_libraries(test_geometry PRIVATE kood3plot)

# Test StateDataParser
add_executable(test_state_data test_state_data.cpp)
target_link_libraries(test_state_data PRIVATE kood3plot)

# Simple read example (Phase 6/7)
add_executable(simple_read simple_read.cpp)
target_link_libraries(simple_read PRIVATE kood3plot)

# Check results - verify displacement and stress data
add_executable(check_results check_results.cpp)
target_link_libraries(check_results PRIVATE kood3plot)

# Extract stress data
add_executable(extract_stress extract_stress.cpp)
target_link_libraries(extract_stress PRIVATE kood3plot)

# Extract displacement data
add_executable(extract_displacement extract_displacement.cpp)
target_link_libraries(extract_displacement PRIVATE kood3plot)

# Extract all data
add_executable(extract_all_data extract_all_data.cpp)
target_link_libraries(extract_all_data PRIVATE kood3plot)

# Show stress and strain data
add_executable(show_stress_strain show_stress_strain.cpp)
target_link_libraries(show_stress_strain PRIVATE kood3plot)

# Show NARBS data
add_executable(show_narbs show_narbs.cpp)
target_link_libraries(show_narbs PRIVATE kood3plot)

# ============================================================
# V3 Query System Examples
# ============================================================
if(KOOD3PLOT_BUILD_V3_QUERY)
    message(STATUS "Building V3 Query System examples")

    # Basic query example
    add_executable(v3_basic_query v3_query/01_basic_query.cpp)
    target_link_libraries(v3_basic_query PRIVATE kood3plot_query kood3plot)

    # Integration test (Phase 2)
    add_executable(v3_integration_test v3_query/02_integration_test.cpp)
    target_link_libraries(v3_integration_test PRIVATE kood3plot_query kood3plot)

    # Phase 3 feature test
    add_executable(v3_phase3_test v3_query/03_phase3_test.cpp)
    target_link_libraries(v3_phase3_test PRIVATE kood3plot_query kood3plot)

    # Phase 5 template test
    add_executable(v3_template_test v3_query/04_template_test.cpp)
    target_link_libraries(v3_template_test PRIVATE kood3plot_query kood3plot)

    # Phase 6 comprehensive example
    add_executable(v3_comprehensive v3_query/05_comprehensive_example.cpp)
    target_link_libraries(v3_comprehensive PRIVATE kood3plot_query kood3plot)

    # Streaming query example (memory-efficient large file processing)
    add_executable(streaming_example streaming_example.cpp)
    target_link_libraries(streaming_example PRIVATE kood3plot_query kood3plot)

    # Future V3 examples (Phase 3+)
    # add_executable(v3_part_selection v3_query/02_part_selection.cpp)
    # target_link_libraries(v3_part_selection PRIVATE kood3plot_query kood3plot)
    #
    # add_executable(v3_time_selection v3_query/03_time_selection.cpp)
    # target_link_libraries(v3_time_selection PRIVATE kood3plot_query kood3plot)
    #
    # add_executable(v3_filtering v3_query/04_filtering.cpp)
    # target_link_libraries(v3_filtering PRIVATE kood3plot_query kood3plot)
    #
    # add_executable(v3_output_formats v3_query/05_output_formats.cpp)
    # target_link_libraries(v3_output_formats PRIVATE kood3plot_query kood3plot)
endif()

# ============================================================
# Fringe Types Validation Test
# ============================================================
if(KOOD3PLOT_BUILD_V4_RENDER)
    add_executable(test_fringe_types test_fringe_types.cpp)
    target_link_libraries(test_fringe_types PRIVATE kood3plot_render kood3plot)

    # Cache performance test
    add_executable(test_cache test_cache.cpp)
    target_link_libraries(test_cache PRIVATE kood3plot_render kood3plot)
endif()

# ============================================================
# Strain Extraction Performance Test
# ============================================================
if(KOOD3PLOT_BUILD_V3_QUERY)
    add_executable(test_strain_extraction test_strain_extraction.cpp)
    target_link_libraries(test_strain_extraction PRIVATE kood3plot_query kood3plot)
endif()

# Simple strain test (no V3 Query dependency)
add_executable(test_strain_simple test_strain_simple.cpp)
target_link_libraries(test_strain_simple PRIVATE kood3plot)

# Parallel strain test
add_executable(test_strain_parallel test_strain_parallel.cpp)
target_link_libraries(test_strain_parallel PRIVATE kood3plot)

# Debug state data test
add_executable(test_debug_states test_debug_states.cpp)
target_link_libraries(test_debug_states PRIVATE kood3plot)

# Base file only test
add_executable(test_base_file_only test_base_file_only.cpp)
target_link_libraries(test_base_file_only PRIVATE kood3plot)

# Family file test
add_executable(test_family_file test_family_file.cpp)
target_link_libraries(test_family_file PRIVATE kood3plot)

# Raw dump test
add_executable(test_raw_dump test_raw_dump.cpp)
target_link_libraries(test_raw_dump PRIVATE kood3plot)

# Find states test
add_executable(find_states find_states.cpp)
target_link_libraries(find_states PRIVATE kood3plot)

# ============================================================
# Comprehensive Example (requires V3 Query and V4 Render)
# ============================================================
if(KOOD3PLOT_BUILD_V3_QUERY AND KOOD3PLOT_BUILD_V4_RENDER)
    add_executable(comprehensive_example comprehensive_example.cpp)
    target_link_libraries(comprehensive_example PRIVATE kood3plot kood3plot_query kood3plot_render)

    # Install comprehensive example
    install(TARGETS comprehensive_example
        RUNTIME DESTINATION bin/examples
    )
endif()

# ============================================================
# V4 Render System Examples
# ============================================================
if(KOOD3PLOT_BUILD_V4_RENDER)
    add_subdirectory(v4_render)
endif()
