// 🔴 이 파일은 CMake 가 Version.hpp.in 에서 **생성**한다 (CMakeLists.txt
//    configure_file). include/kood3plot/Version.hpp 를 직접 고치면 다음
//    `cmake` 실행 때 조용히 덮어써진다 — 고칠 곳은 Version.hpp.in 이다.
#pragma once

#include <string>

namespace kood3plot {

/**
 * @brief Library version information
 */
struct Version {
    static constexpr int MAJOR = 1;
    static constexpr int MINOR = 0;
    static constexpr int PATCH = 0;

    static std::string get_version_string() {
        return "1.0.0";
    }

    static std::string get_full_version_string() {
        return "KooD3plotReader v1.0.0";
    }

    /// 빌드된 git 커밋 (`git describe --tags --always --dirty`). 없으면 "unknown".
    ///
    /// MAJOR/MINOR/PATCH 는 2026년 내내 1.0.0 이라 어느 판인지 구분하지 못한다.
    /// 산출물만 보고 "어느 빌드로 돌렸는지" 알 수 있어야 해서 따로 둔다
    /// (docs/postproc_gap_2026-09/plan.md §P0-3).
    /// 구현은 src/Version.cpp — 헤더 인라인으로 두면 매크로를 받은 TU 와 못 받은
    /// TU 의 본문이 달라져 ODR 위반이 된다.
    static std::string build_commit();

    /// 빌드 시각 (ISO 8601 UTC). 없으면 "unknown".
    static std::string build_date();
};

} // namespace kood3plot
