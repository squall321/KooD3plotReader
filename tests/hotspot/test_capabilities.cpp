// --capabilities 가 광고하는 기준 목록이 실제 파서 수용 집합과 같은지 검증
//
// 왜 있나 — 배포본의 지원 기능을 알려면 소스를 읽어야 했고, VERSION 파일이 2주간
// 옛 커밋을 가리키는 바람에 이미 있는 기능을 "없다" 고 판단한 일이 있었다
// (docs/postproc_gap_2026-09/plan.md §0). 그래서 실행 파일이 스스로 답하게 했는데,
// 그 답이 실제와 어긋나면 같은 사고가 반복된다. 여기서 그 일치를 못박는다.
#include "kood3plot/analysis/HotspotClusterAnalyzer.hpp"
#include <algorithm>
#include <cstdio>
#include <string>
#include <vector>
using namespace kood3plot;
using namespace kood3plot::analysis;

static int fails = 0;
static void chkb(const char* n, bool ok) {
    if (!ok) ++fails;
    printf("  %s %-58s\n", ok ? "OK " : "NG ", n);
}

int main() {
    printf("== --capabilities 기준 목록 검증 ==\n");

    const auto all = allHotspotCriteria();

    // ① 목록의 모든 이름이 파서로 같은 값으로 되돌아온다 (광고한 것은 실제로 된다)
    bool roundtrip_ok = true;
    for (HotspotCriterion c : all) {
        const char* nm = hotspotCriterionName(c);
        HotspotCriterion back;
        if (!nm || !parseHotspotCriterion(nm, back) || back != c) roundtrip_ok = false;
    }
    chkb("목록의 모든 이름이 파서 왕복을 통과", roundtrip_ok);

    // ② 목록에 중복이 없다
    std::vector<std::string> names;
    for (HotspotCriterion c : all) names.emplace_back(hotspotCriterionName(c));
    std::vector<std::string> sorted = names;
    std::sort(sorted.begin(), sorted.end());
    chkb("목록에 중복 없음",
         std::adjacent_find(sorted.begin(), sorted.end()) == sorted.end());

    // ③ 목록 밖의 enum 값은 정의돼 있지 않다 (목록이 실제 집합보다 작지 않다)
    //    hotspotCriterionName 의 default 가 "von_mises" 라 되파싱하면 VonMises 로
    //    돌아온다 — 자기 자신과 달라지므로 정의되지 않았음이 드러난다.
    bool no_hidden = true;
    for (int i = 0; i < 64; ++i) {
        const auto c = static_cast<HotspotCriterion>(i);
        const bool listed = std::find(all.begin(), all.end(), c) != all.end();
        if (listed) continue;
        HotspotCriterion back;
        const char* nm = hotspotCriterionName(c);
        if (nm && parseHotspotCriterion(nm, back) && back == c) no_hidden = false;
    }
    chkb("목록 밖에 숨은 기준이 없음", no_hidden);

    // ④ 지금 지원해야 하는 것들이 실제로 들어 있다.
    //    이 단언이 깨지면 기능이 사라진 것이다 (2026-09-11 78b9a55 로 들어옴).
    auto has = [&](const char* n) {
        return std::find(names.begin(), names.end(), std::string(n)) != names.end();
    };
    chkb("von_mises 지원", has("von_mises"));
    chkb("max_principal 지원 (인장 — 인터포저/PPG 크랙)", has("max_principal"));
    chkb("min_principal 지원 (압축 — PCB 측면 찍힘)", has("min_principal"));
    chkb("max_shear 지원 (전단 — 볼 전단)", has("max_shear"));

    // ⑤ 별칭도 정규 이름으로 매핑된다 (사용자가 s1/sigma3 로 써도 통한다)
    struct { const char* alias; const char* canon; } aliases[] = {
        {"vm", "von_mises"}, {"VonMises", "von_mises"}, {"von-mises", "von_mises"},
        {"s1", "max_principal"}, {"sigma1", "max_principal"}, {"P1", "max_principal"},
        {"s3", "min_principal"}, {"sigma3", "min_principal"}, {"min-principal", "min_principal"},
    };
    bool alias_ok = true;
    for (const auto& a : aliases) {
        HotspotCriterion c;
        if (!parseHotspotCriterion(a.alias, c) ||
            std::string(hotspotCriterionName(c)) != a.canon) {
            alias_ok = false;
            printf("     별칭 실패: %s → %s 여야 함\n", a.alias, a.canon);
        }
    }
    chkb("별칭이 정규 이름으로 매핑", alias_ok);

    // ⑥ 모르는 이름은 거부한다 (조용히 von_mises 로 떨어지지 않는다)
    bool reject_ok = true;
    for (const char* bad : {"x_tension", "", "vonmisses", "s2", "max_sheer"}) {
        HotspotCriterion c;
        if (parseHotspotCriterion(bad, c)) { reject_ok = false; printf("     거부 실패: %s\n", bad); }
    }
    chkb("모르는 이름은 거부 (미지원을 조용히 대체하지 않음)", reject_ok);

    // ⑦ parseHotspotCriteria 가 unknown 을 모아 돌려준다
    std::vector<std::string> unknown;
    const auto parsed = parseHotspotCriteria({"von_mises", "x_tension", "s3", "nope"}, &unknown);
    chkb("복수 지정에서 아는 것만 통과 (2개)", parsed.size() == 2);
    chkb("모르는 것은 unknown 으로 보고 (2개)", unknown.size() == 2);

    printf(fails ? "\n[FAIL] 실패 %d 건\n" : "\n[PASS] 실패 0 건\n", fails);
    return fails ? 1 : 0;
}
