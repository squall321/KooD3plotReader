# V4 Render System Examples

# Check if V4 Render is enabled
if(NOT KOOD3PLOT_BUILD_V4_RENDER)
    message(STATUS "V4 Render examples skipped (KOOD3PLOT_BUILD_V4_RENDER is OFF)")
    return()
endif()

message(STATUS "Configuring V4 Render examples")

# Example 1: Basic render
add_executable(v4_01_basic_render 01_basic_render.cpp)
target_link_libraries(v4_01_basic_render PRIVATE kood3plot_render kood3plot)
target_include_directories(v4_01_basic_render PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/../../include
)

# Example 2: Section view
add_executable(v4_02_section_view 02_section_view.cpp)
target_link_libraries(v4_02_section_view PRIVATE kood3plot_render kood3plot)
target_include_directories(v4_02_section_view PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/../../include
)

# Example 3: Animation
add_executable(v4_03_animation 03_animation.cpp)
target_link_libraries(v4_03_animation PRIVATE kood3plot_render kood3plot)
target_include_directories(v4_03_animation PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/../../include
)

# Example 4: Custom views
add_executable(v4_04_custom_views 04_custom_views.cpp)
target_link_libraries(v4_04_custom_views PRIVATE kood3plot_render kood3plot)
target_include_directories(v4_04_custom_views PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/../../include
)

# Example 5: Batch with config
add_executable(v4_05_batch_with_config 05_batch_with_config.cpp)
target_link_libraries(v4_05_batch_with_config PRIVATE kood3plot_render kood3plot)
target_include_directories(v4_05_batch_with_config PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/../../include
)

# Example 6: Advanced multisection
add_executable(v4_06_advanced_multisection 06_advanced_multisection.cpp)
target_link_libraries(v4_06_advanced_multisection PRIVATE kood3plot_render kood3plot)
target_include_directories(v4_06_advanced_multisection PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/../../include
)

# Example 7: Auto-sections with geometry analyzer
add_executable(v4_07_auto_sections 07_auto_sections.cpp)
target_link_libraries(v4_07_auto_sections PRIVATE kood3plot_render kood3plot)
target_include_directories(v4_07_auto_sections PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/../../include
)

# Example 8: Multi-run comparison with parallel processing
add_executable(v4_08_multirun_comparison 08_multirun_comparison.cpp)
target_link_libraries(v4_08_multirun_comparison PRIVATE kood3plot_render kood3plot)
target_include_directories(v4_08_multirun_comparison PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/../../include
)

# Installation
install(TARGETS
    v4_01_basic_render
    v4_02_section_view
    v4_03_animation
    v4_04_custom_views
    v4_05_batch_with_config
    v4_06_advanced_multisection
    v4_07_auto_sections
    v4_08_multirun_comparison
    RUNTIME DESTINATION bin/examples/v4_render
)

message(STATUS "V4 Render examples configured: 8 programs")
