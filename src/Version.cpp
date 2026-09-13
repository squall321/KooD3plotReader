// 빌드 시 주입된 git 커밋·빌드 시각을 돌려주는 구현 (헤더 인라인 금지 — ODR 회피)
//
// 왜 별도 파일인가 — 매크로(KOOD3PLOT_GIT_COMMIT)를 헤더의 인라인 함수에 걸면,
// 매크로를 받은 TU 와 못 받은 TU 가 서로 다른 본문을 갖게 되어 ODR 위반이 된다.
// 이 파일 하나만 매크로를 받고, 나머지는 선언만 본다.
#include "kood3plot/Version.hpp"

#ifndef KOOD3PLOT_GIT_COMMIT
#define KOOD3PLOT_GIT_COMMIT "unknown"
#endif
#ifndef KOOD3PLOT_BUILD_DATE
#define KOOD3PLOT_BUILD_DATE "unknown"
#endif

namespace kood3plot {

std::string Version::build_commit() { return KOOD3PLOT_GIT_COMMIT; }
std::string Version::build_date()   { return KOOD3PLOT_BUILD_DATE; }

} // namespace kood3plot
