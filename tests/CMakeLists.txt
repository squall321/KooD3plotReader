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
