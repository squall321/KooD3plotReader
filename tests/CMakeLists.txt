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

# 빔 파트 응력 이력 tests (합성 d3plot 왕복) — 워드 배치(BEMENG · NEIPB) · 침식 · 값 없는 파트
if(TARGET kood3plot_writer)
    add_executable(test_beam_part_history test_beam_part_history.cpp)
    target_link_libraries(test_beam_part_history PRIVATE kood3plot kood3plot_writer)
    target_include_directories(test_beam_part_history PRIVATE ${CMAKE_SOURCE_DIR}/include)
    add_test(NAME BeamPartHistory COMMAND test_beam_part_history)
endif()

# 솔리드 적분점 여덟 개 덱 tests (합성 d3plot 왕복) — 적분점 극값 · 빈 자리 · 변형률 자리 · 핫스팟 · 피크 텐서
if(TARGET kood3plot_writer)
    add_executable(test_solid_ip_history test_solid_ip_history.cpp)
    target_link_libraries(test_solid_ip_history PRIVATE kood3plot kood3plot_writer)
    target_include_directories(test_solid_ip_history PRIVATE ${CMAKE_SOURCE_DIR}/include)
    add_test(NAME SolidIpHistory COMMAND test_solid_ip_history)
endif()

# 겉면 응력 · 변형률의 솔리드 적분점 처리 tests (합성 d3plot 왕복) — 쓰인 적분점의 평균 텐서 · 빈 자리 · 변형률 자리
if(TARGET kood3plot_writer)
    add_executable(test_surface_ip_mean test_surface_ip_mean.cpp)
    target_link_libraries(test_surface_ip_mean PRIVATE kood3plot kood3plot_writer)
    target_include_directories(test_surface_ip_mean PRIVATE ${CMAKE_SOURCE_DIR}/include)
    add_test(NAME SurfaceIpMean COMMAND test_surface_ip_mean)
endif()

# set 리포트 segments 지표의 솔리드 적분점 처리 tests (합성 d3plot 왕복) — 부모 요소의 적분점 극값 · 빈 자리 · 파트 이력과의 일치
if(TARGET kood3plot_writer)
    add_executable(test_set_segment_ip test_set_segment_ip.cpp)
    target_link_libraries(test_set_segment_ip PRIVATE kood3plot kood3plot_writer)
    target_include_directories(test_set_segment_ip PRIVATE ${CMAKE_SOURCE_DIR}/include)
    add_test(NAME SetSegmentIp COMMAND test_set_segment_ip)
endif()

# MotionAnalyzer tests (합성 d3plot 왕복) — 절점 ID 규약·없는 파트·IV 속도
if(TARGET kood3plot_writer)
    add_executable(test_motion_analyzer test_motion_analyzer.cpp)
    target_link_libraries(test_motion_analyzer PRIVATE kood3plot kood3plot_writer)
    target_include_directories(test_motion_analyzer PRIVATE ${CMAKE_SOURCE_DIR}/include)
    add_test(NAME MotionAnalyzer COMMAND test_motion_analyzer)
endif()

# S1 기하 핵심 (StepForge 겉면 규칙 이식·바깥 방향·von Mises·바닥 평면) — 덱 불필요
add_executable(test_s1_core test_s1_core.cpp)
target_link_libraries(test_s1_core PRIVATE kood3plot)
target_include_directories(test_s1_core PRIVATE ${CMAKE_SOURCE_DIR}/include)
add_test(NAME S1Core COMMAND test_s1_core)

# d3plot 가족 파일 읽기 무결성 (합성 d3plot) — 잘림·누락·열기 실패·스레드 생성 실패.
# fork·setrlimit 을 써서 POSIX 만.
if(TARGET kood3plot_writer AND UNIX)
    add_executable(test_family_read_integrity test_family_read_integrity.cpp)
    target_link_libraries(test_family_read_integrity PRIVATE kood3plot kood3plot_writer)
    target_include_directories(test_family_read_integrity PRIVATE ${CMAKE_SOURCE_DIR}/include)
    add_test(NAME FamilyReadIntegrity COMMAND test_family_read_integrity)
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

# 단면 자를 자리(center_mode) 파싱 — 오타가 조용히 기본값으로 떨어지지 않는지
# 단면 렌더러를 끈 빌드(KOOD3PLOT_BUILD_SECTION_RENDER=OFF)에는 그 라이브러리가 없다 — 조건 없이 링크하면 전체 빌드가 멈췄다
if(TARGET kood3plot_section_render)
    add_executable(test_section_center_mode test_section_center_mode.cpp)
    target_link_libraries(test_section_center_mode PRIVATE kood3plot_section_render)
    target_include_directories(test_section_center_mode PRIVATE ${CMAKE_SOURCE_DIR}/include)
endif()

# 단면 렌더의 절점 평균(NodalAverager) tests (덱 없이 메모리의 메시 · 상태) — 요소 값을 읽는 규칙 · 절점에 나누는 규칙
if(TARGET kood3plot_section_render)
    add_executable(test_nodal_averager test_nodal_averager.cpp)
    target_link_libraries(test_nodal_averager PRIVATE kood3plot_section_render)
    target_include_directories(test_nodal_averager PRIVATE ${CMAKE_SOURCE_DIR}/include)
    add_test(NAME NodalAverager COMMAND test_nodal_averager)
endif()

# 단면 렌더의 지운 요소 tests (덱 없이 메모리의 메시 · 상태) — 절점 평균 · 단면 자르기가 지운 요소를 순번으로 가려 빼는지
if(TARGET kood3plot_section_render)
    add_executable(test_section_deleted test_section_deleted.cpp)
    target_link_libraries(test_section_deleted PRIVATE kood3plot_section_render)
    target_include_directories(test_section_deleted PRIVATE ${CMAKE_SOURCE_DIR}/include)
    add_test(NAME SectionDeletedElements COMMAND test_section_deleted)
endif()

# LS-PrePost 용 Xvfb — 빈 화면 번호 · 준비된 뒤 넘김 · 동시에 둘(가짜 LS-PrePost, Xvfb 가 있어야 돈다)
if(TARGET kood3plot_render)
    add_executable(test_lspp_xvfb test_lspp_xvfb.cpp)
    target_link_libraries(test_lspp_xvfb PRIVATE kood3plot_render)
    target_include_directories(test_lspp_xvfb PRIVATE ${CMAKE_SOURCE_DIR}/include)
endif()

# 파트별 단면 영상 폴더 이름 — 덱 이름을 살리되 셸 · LS-PrePost 명령을 깨는 글자는 남기지 않는다
if(TARGET kood3plot_render)
    add_executable(test_lspp_part_folder test_lspp_part_folder.cpp)
    target_link_libraries(test_lspp_part_folder PRIVATE kood3plot_render)
    target_include_directories(test_lspp_part_folder PRIVATE ${CMAKE_SOURCE_DIR}/include)
    add_test(NAME LsppPartFolder COMMAND test_lspp_part_folder)
endif()

# LS-PrePost 명령 스크립트에서 숨길 파트가 fringe 뒤 · 첫 ac 앞에 꺼지는지(리포트 그림 3단계)
if(TARGET kood3plot_render)
    add_executable(test_lspp_hide_parts test_lspp_hide_parts.cpp)
    target_link_libraries(test_lspp_hide_parts PRIVATE kood3plot_render)
    target_include_directories(test_lspp_hide_parts PRIVATE ${CMAKE_SOURCE_DIR}/include)
endif()

# LS-PrePost 명령 스크립트의 카메라 타겟 맞춤 — 켰을 때의 줄 순서(실측한 그대로)와 껐을 때 글자가 그대로인지
if(TARGET kood3plot_render)
    add_executable(test_lspp_view_fit test_lspp_view_fit.cpp)
    target_link_libraries(test_lspp_view_fit PRIVATE kood3plot_render)
    target_include_directories(test_lspp_view_fit PRIVATE ${CMAKE_SOURCE_DIR}/include)
    add_test(NAME LsppViewFit COMMAND test_lspp_view_fit)
endif()

# 설정 · deep 의 fringe 이름이 LS-PrePost fringe 번호로 옮겨지는지(모르는 이름이 말없이 von Mises 로 그려지던 것)
if(TARGET kood3plot_render)
    add_executable(test_lspp_fringe_names test_lspp_fringe_names.cpp)
    target_link_libraries(test_lspp_fringe_names PRIVATE kood3plot_render)
    target_include_directories(test_lspp_fringe_names PRIVATE ${CMAKE_SOURCE_DIR}/include)
    add_test(NAME LsppFringeNames COMMAND test_lspp_fringe_names)
endif()

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
