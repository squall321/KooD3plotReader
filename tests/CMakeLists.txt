# Unit tests for KooD3plotReader
#
# 등록 규약 — 두 갈래다.
#   (가) 덱이 필요 없는 시험: add_executable + add_test. `ctest` 가 실제로 돌린다.
#   (나) 실덱이 있어야 도는 시험: add_executable 만 한다. 덱이 없는 머신(CI·새 클론)
#        에서는 검사가 건너뛰어지므로 ctest 에 올리면 초록불만 늘고 보증은 늘지
#        않는다. 대신 빌드 대상으로는 올려 두어 헤더·API 변경으로 깨지면 CI 가
#        컴파일 단계에서 잡는다. 실행은 각 파일 머리말의 g++ 명령으로 한다.

# VectorMath tests
add_executable(test_vector_math test_vector_math.cpp)
target_link_libraries(test_vector_math PRIVATE kood3plot)
target_include_directories(test_vector_math PRIVATE ${CMAKE_SOURCE_DIR}/include)
add_test(NAME VectorMath COMMAND test_vector_math)

# AnalysisResult tests
add_executable(test_analysis_result test_analysis_result.cpp)
target_link_libraries(test_analysis_result PRIVATE kood3plot)
target_include_directories(test_analysis_result PRIVATE ${CMAKE_SOURCE_DIR}/include)
add_test(NAME AnalysisResult COMMAND test_analysis_result)

# SurfaceExtractor tests — (나) results/d3plot 필요
add_executable(test_surface_extractor test_surface_extractor.cpp)
target_link_libraries(test_surface_extractor PRIVATE kood3plot)
target_include_directories(test_surface_extractor PRIVATE ${CMAKE_SOURCE_DIR}/include)

# SurfaceStressAnalyzer tests — (나) results/d3plot 필요
add_executable(test_surface_stress test_surface_stress.cpp)
target_link_libraries(test_surface_stress PRIVATE kood3plot)
target_include_directories(test_surface_stress PRIVATE ${CMAKE_SOURCE_DIR}/include)

# SurfaceStrainAnalyzer 텐서 수식 tests
add_executable(test_surface_strain_math test_surface_strain_math.cpp)
target_link_libraries(test_surface_strain_math PRIVATE kood3plot)
target_include_directories(test_surface_strain_math PRIVATE ${CMAKE_SOURCE_DIR}/include)
add_test(NAME SurfaceStrainMath COMMAND test_surface_strain_math)

# BeamAnalyzer tests (합성 d3plot 왕복) — Writer 로 테스트 데이터를 만든다
if(TARGET kood3plot_writer)
    add_executable(test_beam_analyzer test_beam_analyzer.cpp)
    target_link_libraries(test_beam_analyzer PRIVATE kood3plot kood3plot_writer)
    target_include_directories(test_beam_analyzer PRIVATE ${CMAKE_SOURCE_DIR}/include)
    add_test(NAME BeamAnalyzer COMMAND test_beam_analyzer)
endif()

# MotionAnalyzer tests (합성 d3plot 왕복) — 절점 ID 규약·없는 파트·IV 속도
if(TARGET kood3plot_writer)
    add_executable(test_motion_analyzer test_motion_analyzer.cpp)
    target_link_libraries(test_motion_analyzer PRIVATE kood3plot kood3plot_writer)
    target_include_directories(test_motion_analyzer PRIVATE ${CMAKE_SOURCE_DIR}/include)
    add_test(NAME MotionAnalyzer COMMAND test_motion_analyzer)
endif()

# TET10(NEL8<0) 덱의 표면 응력 침식 제외 tests — Writer 로 합성 덱을 만든다
if(TARGET kood3plot_writer)
    add_executable(test_surface_stress_tet10 test_surface_stress_tet10.cpp)
    target_link_libraries(test_surface_stress_tet10 PRIVATE kood3plot kood3plot_writer)
    target_include_directories(test_surface_stress_tet10 PRIVATE ${CMAKE_SOURCE_DIR}/include)
endif()

# 인라인 매핑 YAML 이 잡을 기본값으로 돌리지 않는지 보는 tests
add_executable(test_config_inline_mapping test_config_inline_mapping.cpp)
target_link_libraries(test_config_inline_mapping PRIVATE kood3plot)
target_include_directories(test_config_inline_mapping PRIVATE ${CMAKE_SOURCE_DIR}/include)

# 요소 품질 시계열 다운샘플이 극값을 보존하는지 보는 tests
add_executable(test_element_quality_downsample test_element_quality_downsample.cpp)
target_link_libraries(test_element_quality_downsample PRIVATE kood3plot)
target_include_directories(test_element_quality_downsample PRIVATE ${CMAKE_SOURCE_DIR}/include)

# 헤더 안 CSV 작성기의 수치 표기 tests
add_executable(test_csv_notation test_csv_notation.cpp)
target_link_libraries(test_csv_notation PRIVATE kood3plot)
target_include_directories(test_csv_notation PRIVATE ${CMAKE_SOURCE_DIR}/include)

# NARBS 구역 경계 tests — Writer 로 합성 덱을 만든다
if(TARGET kood3plot_writer)
    add_executable(test_narbs_section_bounds test_narbs_section_bounds.cpp)
    target_link_libraries(test_narbs_section_bounds PRIVATE kood3plot kood3plot_writer)
    target_include_directories(test_narbs_section_bounds PRIVATE ${CMAKE_SOURCE_DIR}/include)
endif()

# KeywordSetParser tests
add_executable(test_keyword_set_parser test_keyword_set_parser.cpp)
target_link_libraries(test_keyword_set_parser PRIVATE kood3plot)
target_include_directories(test_keyword_set_parser PRIVATE ${CMAKE_SOURCE_DIR}/include)
add_test(NAME KeywordSetParser COMMAND test_keyword_set_parser)

# *SET_SEGMENT 부모 solid 조회 tests (합성 메시)
add_executable(test_segment_parent_lookup test_segment_parent_lookup.cpp)
target_link_libraries(test_segment_parent_lookup PRIVATE kood3plot)
target_include_directories(test_segment_parent_lookup PRIVATE ${CMAKE_SOURCE_DIR}/include)
add_test(NAME SegmentParentLookup COMMAND test_segment_parent_lookup)

# TimeHistoryAnalyzer tests — (나) results/d3plot 필요
add_executable(test_time_history test_time_history.cpp)
target_link_libraries(test_time_history PRIVATE kood3plot)
target_include_directories(test_time_history PRIVATE ${CMAKE_SOURCE_DIR}/include)

# toExtendedJSON 수치 표기·비유한값·미산출 표기 tests
# (tests/test_unified_analyzer_output.cpp 은 실행 파일 소스를 통째로 가져오므로
#  CMake 대신 g++ 로 돌린다 — 그 파일 머리말의 명령 참고)
add_executable(test_extended_json test_extended_json.cpp)
target_link_libraries(test_extended_json PRIVATE kood3plot)
target_include_directories(test_extended_json PRIVATE ${CMAKE_SOURCE_DIR}/include)
add_test(NAME ExtendedJSON COMMAND test_extended_json)

# ------------------------------------------------------------
# (나) 실덱이 있어야 도는 시험 — 빌드 대상으로만 올린다(ctest 미등록).
#   test_element_quality_states : /data/koopark/Test_DTMIN_erode/dtmin_0p1
#   test_erosion_stats          : /data/koopark/Test_DTMIN_erode/dtmin_0p1
#   test_part_name_lookup       : /data/battery_study/case_01_phase1_stacked_tier-1
#   test_series_element_ids     : /data/battery_study/case_01_phase1_stacked_tier-1
#   test_stress_unit_label      : /data/battery_study/case_01_phase1_stacked_tier-1
# ------------------------------------------------------------
foreach(_deck_test
        test_element_quality_states
        test_erosion_stats
        test_part_name_lookup
        test_series_element_ids
        test_stress_unit_label)
    add_executable(${_deck_test} ${_deck_test}.cpp)
    target_link_libraries(${_deck_test} PRIVATE kood3plot)
    target_include_directories(${_deck_test} PRIVATE ${CMAKE_SOURCE_DIR}/include)
endforeach()

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
