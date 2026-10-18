// 군집을 안 돌렸으면 hotspot_clusters 키 자체가 없어야 한다는 것을 못박는 시험
//
// 왜 필요한가 (2026-10-18 실측). 전에는 비활성일 때도 `"hotspot_clusters": []` 를
// 냈다. 그러면 읽는 쪽이 **"돌렸는데 아무것도 안 잡혔다" 와 "애초에 안 돌렸다" 를
// 구분할 수 없다.** 이 저장소가 반복해 고쳐 온 '0 위장' 과 같은 종류다.
// koo_sphere_report 의 로더는 "--hotspot-clusters 없이 돌린 런에는 키 자체가 없다"
// 를 전제로 서로 다른 안내문을 내고 있었는데, 그 전제가 틀려 있었다.
//
// 함께 본다: 키를 빼도 JSON 이 유효해야 한다. 이 키는 객체의 **마지막** 항목이라
// 앞 항목의 쉼표를 잘못 다루면 `...,}` 로 깨진다.
//
// 빌드: g++ -std=c++17 -I include tests/hotspot/test_hotspot_key_omitted.cpp -o /tmp/t && /tmp/t
#include "kood3plot/analysis/AnalysisResult.hpp"
#include "kood3plot/analysis/HotspotClusterAnalyzer.hpp"
#include <cstdio>
#include <string>

using namespace kood3plot::analysis;

static int fails = 0;
static void check(bool ok, const char* what) {
    std::printf("  %s  %s\n", ok ? "OK " : "NG ", what);
    if (!ok) ++fails;
}

// 중괄호·대괄호 짝과 쉼표 뒤 닫힘(`,}` / `,]`)만 보는 최소 검사.
// 문자열 안의 괄호는 건너뛴다.
static bool json_wellformed(const std::string& s) {
    int depth = 0;
    bool in_str = false, esc = false;
    char prev_sig = 0;                 // 공백이 아닌 직전 문자
    for (char c : s) {
        if (in_str) {
            if (esc)            esc = false;
            else if (c == '\\') esc = true;
            else if (c == '"')  in_str = false;
            continue;
        }
        if (c == '"') { in_str = true; prev_sig = c; continue; }
        if (c == '{' || c == '[') ++depth;
        if (c == '}' || c == ']') {
            if (prev_sig == ',') return false;   // `,}` 또는 `,]`
            if (--depth < 0) return false;
        }
        if (c != ' ' && c != '\n' && c != '\t' && c != '\r') prev_sig = c;
    }
    return depth == 0 && !in_str;
}

int main() {
    std::printf("핫스팟 키 생략 규칙\n");

    // ── 안 돌린 경우: 키가 없어야 한다
    AnalysisResult off;
    const std::string s_off = off.toJSON(true);
    check(s_off.find("\"hotspot_clusters\"") == std::string::npos,
          "군집이 비면 hotspot_clusters 키가 없다");
    check(json_wellformed(s_off),
          "키를 빼도 JSON 이 유효하다 (마지막 항목의 쉼표 처리)");

    // ── 돌린 경우: 키가 있어야 한다
    AnalysisResult on;
    PartHotspotResult item;
    item.part_id = 7;
    item.criterion = "von_mises";
    on.hotspot_clusters.push_back(item);
    const std::string s_on = on.toJSON(true);
    check(s_on.find("\"hotspot_clusters\"") != std::string::npos,
          "군집이 있으면 hotspot_clusters 키가 있다");
    check(json_wellformed(s_on), "군집이 있을 때도 JSON 이 유효하다");

    // ── 군집 배열이 비어 있는 항목만 있어도 '돌렸다' 는 사실은 남아야 한다.
    //    (파트×기준량마다 항목이 생기므로, 항목이 있다는 것 자체가 실행의 증거다)
    check(s_on.find("\"part_id\"") != std::string::npos,
          "군집 0개인 항목이라도 실행 사실이 남는다");

    // ── 비압축(pretty=false)에서도 같아야 한다
    check(AnalysisResult().toJSON(false).find("\"hotspot_clusters\"") == std::string::npos,
          "pretty=false 에서도 키가 없다");
    check(json_wellformed(AnalysisResult().toJSON(false)),
          "pretty=false JSON 도 유효하다");

    std::printf("\n[%s]  실패 %d 건\n", fails ? "FAIL" : "PASS", fails);
    return fails ? 1 : 0;
}
