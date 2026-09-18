# 빌드할 때마다 git 버전을 다시 읽어 각인 헤더를 갱신하는 스크립트 (cmake -P 로 실행)
#
# 왜 빌드 시점인가. CMake **설정** 시점에 한 번만 읽으면, 그 뒤 커밋을 쌓고 `make`
# 만 한 바이너리가 옛 커밋을 자기 버전이라고 답한다. 산출물의 tool_commit 과
# --skip-existing 의 '분석기가 바뀌었나' 판정이 그 값을 믿으므로, 틀린 각인은
# "고쳤는데도 옛 결과를 재사용" 으로 이어진다 (실측 2026-09-17).
#
# 왜 '바뀔 때만' 쓰는가. 매번 새로 쓰면 빌드 시각이 매번 달라져 전체가 다시
# 링크된다. 커밋 문자열이 같으면 파일을 건드리지 않아 헛 재빌드가 없다.
#
# 인자: -DSRC_DIR=<저장소 루트> -DOUT_FILE=<생성할 헤더 경로>

if(NOT DEFINED SRC_DIR OR NOT DEFINED OUT_FILE)
    message(FATAL_ERROR "GitVersion.cmake: SRC_DIR 과 OUT_FILE 이 필요합니다")
endif()

set(_commit "unknown")
find_package(Git QUIET)
if(GIT_FOUND AND EXISTS "${SRC_DIR}/.git")
    execute_process(
        COMMAND ${GIT_EXECUTABLE} describe --tags --always --dirty
        WORKING_DIRECTORY "${SRC_DIR}"
        OUTPUT_VARIABLE _commit
        OUTPUT_STRIP_TRAILING_WHITESPACE
        ERROR_QUIET
    )
    if(_commit STREQUAL "")
        set(_commit "unknown")   # 조용히 빈 문자열로 두지 않는다
    endif()
endif()

# 이미 같은 커밋이 적혀 있으면 그대로 둔다 (빌드 시각도 그때 값을 유지).
set(_existing "")
if(EXISTS "${OUT_FILE}")
    file(READ "${OUT_FILE}" _existing)
endif()
if(_existing MATCHES "#define KOOD3PLOT_GIT_COMMIT_RT \"([^\"]*)\"")
    if(CMAKE_MATCH_1 STREQUAL _commit)
        return()
    endif()
endif()

string(TIMESTAMP _date "%Y-%m-%dT%H:%M:%SZ" UTC)
file(WRITE "${OUT_FILE}"
"// 빌드할 때 생성되는 파일 — 고치지 마세요 (cmake/GitVersion.cmake 가 씁니다)\n"
"#pragma once\n"
"#define KOOD3PLOT_GIT_COMMIT_RT \"${_commit}\"\n"
"#define KOOD3PLOT_BUILD_DATE_RT \"${_date}\"\n")
message(STATUS "버전 각인 갱신: ${_commit} (${_date})")
