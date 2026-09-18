// 빌드 시 주입된 git 커밋·빌드 시각을 돌려주는 구현 (헤더 인라인 금지 — ODR 회피)
//
// 왜 별도 파일인가 — 매크로(KOOD3PLOT_GIT_COMMIT)를 헤더의 인라인 함수에 걸면,
// 매크로를 받은 TU 와 못 받은 TU 가 서로 다른 본문을 갖게 되어 ODR 위반이 된다.
// 이 파일 하나만 매크로를 받고, 나머지는 선언만 본다.
#include "kood3plot/Version.hpp"

// 빌드 시점에 갱신되는 각인이 있으면 그것을 쓴다. 설정 시점 매크로만 믿으면
// 커밋을 쌓고 make 만 한 바이너리가 옛 커밋을 자기 버전이라고 답한다
// (cmake/GitVersion.cmake 주석 참조).
#if defined(__has_include)
#  if __has_include(<kood3plot_build_info.h>)
#    include <kood3plot_build_info.h>
#  endif
#endif

#ifndef KOOD3PLOT_GIT_COMMIT
#define KOOD3PLOT_GIT_COMMIT "unknown"
#endif
#ifndef KOOD3PLOT_BUILD_DATE
#define KOOD3PLOT_BUILD_DATE "unknown"
#endif
#ifndef KOOD3PLOT_GIT_COMMIT_RT
#define KOOD3PLOT_GIT_COMMIT_RT KOOD3PLOT_GIT_COMMIT
#endif
#ifndef KOOD3PLOT_BUILD_DATE_RT
#define KOOD3PLOT_BUILD_DATE_RT KOOD3PLOT_BUILD_DATE
#endif

namespace kood3plot {

std::string Version::build_commit() { return KOOD3PLOT_GIT_COMMIT_RT; }
std::string Version::build_date()   { return KOOD3PLOT_BUILD_DATE_RT; }

} // namespace kood3plot
