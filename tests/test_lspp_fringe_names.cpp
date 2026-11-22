// 설정 · deep 이 보내는 fringe 이름이 LS-PrePost 명령의 fringe 번호로 바르게 옮겨지는지 보는 시험
//
// deep 은 LS-PrePost 단면 영상에 `displacement_mag` · `max_shear` · `pressure` 를 보낸다(job_builder._FRINGE_MAP).
// 예전에는 C++ 쪽 대응표(렌더 잡 두 곳 · 파트별 단면 한 곳)가 이 이름을 몰라 말없이 von Mises(9)로 그렸다 —
// 영상 안 범례는 「Effective Stress (v-m)」 인데 갤러리는 변위 · 최대 전단이라 적는다(2026-11-22 실측, Test_006).
// 대응표를 render::fringeTypeFromName 하나로 모으고, 모르는 이름은 known = false 로 알린다(부르는 쪽이 경고 줄을 낸다).
//
// 빌드·실행:
//   cd build && make test_lspp_fringe_names && ./tests/test_lspp_fringe_names
#include "kood3plot/render/LSPrePostRenderer.h"

#include <cstdio>
#include <string>

using kood3plot::render::FringeType;
using kood3plot::render::LSPrePostRenderer;
using kood3plot::render::RenderOptions;
using kood3plot::render::fringeTypeFromName;

namespace {

int g_failed = 0;

void chk(const std::string& what, bool ok, const std::string& detail = "") {
    if (!ok) ++g_failed;
    std::printf("  %s %-58s %s\n", ok ? "OK " : "NG ", what.c_str(), detail.c_str());
}

}  // namespace

int main() {
    LSPrePostRenderer r("/nonexistent/lsprepost");

    struct Want {
        const char* name;
        FringeType type;
        int code;   // LS-PrePost fringe 번호
    };
    // 앞 다섯은 deep 의 _FRINGE_MAP 이 보내는 이름 전부, 뒤 셋은 설정 파일에 적던 이름
    const Want wants[] = {
        {"von_mises", FringeType::VON_MISES, 9},
        {"eff_plastic_strain", FringeType::EFFECTIVE_PLASTIC_STRAIN, 7},
        {"displacement_mag", FringeType::DISPLACEMENT, 20},
        {"pressure", FringeType::PRESSURE, 8},
        {"max_shear", FringeType::MAX_SHEAR_STRESS, 13},
        {"displacement", FringeType::DISPLACEMENT, 20},
        {"velocity", FringeType::VELOCITY, 24},
        {"acceleration", FringeType::ACCELERATION, 23},
    };

    std::printf("[1] 이름 → fringe — 아는 이름이고, 명령 파일에 그 번호가 적힌다(타겟 있음 · 없음)\n");
    for (const Want& w : wants) {
        bool known = false;
        const FringeType t = fringeTypeFromName(w.name, &known);
        const std::string code = "fringe " + std::to_string(w.code) + "\npfringe\n";
        RenderOptions o;
        o.fringe_type = t;
        const std::string plain = r.generateScript("/x/d3plot", "/x/out", o);
        o.highlight_parts = {6};
        const std::string target = r.generateScript("/x/d3plot", "/x/out", o);
        chk(std::string(w.name) + " → " + std::to_string(w.code),
            known && t == w.type && plain.find(code) != std::string::npos && target.find(code) != std::string::npos,
            known ? "" : "(모르는 이름으로 읽혔다)");
    }

    std::printf("[2] 모르는 이름 — known 이 거짓이고 von Mises 로 돌아온다(부르는 쪽이 경고 줄을 낸다)\n");
    for (const char* name : {"displacment", "Von_Mises", ""}) {
        bool known = true;
        const FringeType t = fringeTypeFromName(name, &known);
        chk(std::string("'") + name + "'", !known && t == FringeType::VON_MISES);
    }

    std::printf("\n%s\n", g_failed ? (std::to_string(g_failed) + "건 실패").c_str() : "전부 통과");
    return g_failed ? 1 : 0;
}
