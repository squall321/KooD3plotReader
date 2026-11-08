// 파트별 LS-PrePost 단면 영상의 폴더 이름이 덱 이름을 살리되 셸 · LS-PrePost 명령을 깨는 글자는 남기지 않는지
//
// 왜 있나 — 예전 폴더는 늘 `part_<id>_Part<id>` 라 deep 키워드(덱 *PART 제목과 맞춘다)를 폴더를 보고 고르면 헛쳤다(2026-11-08
// v50 판정, 셸 덱 PCB_FR4). 덱 이름을 쓰면 이름이 셸 명령 `c="…"` 과 LS-PrePost 의 `"…"` 안에 그대로 들어가므로
// 따옴표 · `$` · 역따옴표 · 공백 같은 글자는 남으면 안 된다.
#include "kood3plot/render/LSPrePostRenderer.h"

#include <cstdio>
#include <string>

using kood3plot::render::LSPrePostRenderer;

namespace {

int g_failed = 0;

void chk(const char* what, bool ok, const std::string& detail = "") {
    if (!ok) ++g_failed;
    std::printf("  %s %-52s %s\n", ok ? "OK " : "NG ", what, detail.c_str());
}

void eq(const char* what, int pid, const std::string& name, const std::string& want) {
    const std::string got = LSPrePostRenderer::partFolderName(pid, name);
    chk(what, got == want, got);
}

bool only_safe(const std::string& s) {
    for (char c : s) {
        const bool ok = (c >= '0' && c <= '9') || (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') ||
                        c == '.' || c == '-' || c == '_';
        if (!ok) return false;
    }
    return true;
}

}  // namespace

int main() {
    std::printf("[A] 덱 이름을 살린다\n");
    eq("셸 덱 PCB_FR4", 1, "PCB_FR4", "part_1_PCB_FR4");
    eq("점 · 하이픈은 그대로", 12, "BGA-1.0", "part_12_BGA-1.0");
    eq("공백은 _ 하나로", 3, "BGA  solder ball", "part_3_BGA_solder_ball");
    eq("앞뒤 공백 · _ 는 뗀다", 4, "  __PKG__ ", "part_4_PKG");

    std::printf("\n[B] 명령을 깨는 글자는 남기지 않는다\n");
    eq("따옴표 · $ · 역따옴표 · 경로 구분자", 5, "a\"b$c`d/e\\f:g", "part_5_a_b_c_d_e_f_g");
    eq("한글이 섞이면 영문 · 숫자만", 6, "BGA 솔더/볼:1", "part_6_BGA_1");
    std::string all;
    for (int c = 1; c < 256; ++c) all += static_cast<char>(c);
    const std::string got = LSPrePostRenderer::partFolderName(7, all);
    chk("1~255 모든 바이트 → 안전한 글자만", only_safe(got), got);

    std::printf("\n[C] 남는 글자가 없거나 너무 길면\n");
    eq("빈 이름은 종전대로 Part<id>", 8, "", "part_8_Part8");
    eq("한글만이면 Part<id>", 9, "기판", "part_9_Part9");
    eq("문장부호만이면 Part<id>", 10, "...--", "part_10_Part10");
    eq("40자에서 자른다", 11, std::string(70, 'X'), "part_11_" + std::string(40, 'X'));
    eq("자른 끝의 _ 도 뗀다", 13, std::string(39, 'Y') + " Z", "part_13_" + std::string(39, 'Y'));

    std::printf("\n%s  실패 %d 건\n", g_failed ? "[FAIL]" : "[PASS]", g_failed);
    return g_failed ? 1 : 0;
}
