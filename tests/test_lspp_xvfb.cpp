// LS-PrePost 를 띄우는 Xvfb 명령이 빈 화면 번호를 스스로 고르고 준비된 뒤에 넘기는지 — 가짜 LS-PrePost 둘을 동시에 돌려 본다
//
// 왜 있나 — 예전 명령은 화면 번호를 `:10 + 작업자 번호`(프로세스마다 0 부터)로 고정하고 `sleep 0.5` 만 기다렸다.
// 같은 노드에서 분석기 둘이 겹치면 둘째 Xvfb 는 잠금에 막혀 못 뜨고 둘째 LS-PrePost 가 첫째의 화면에 붙어, 첫째가
// 끝나며 화면을 닫으면 도중에 화면을 잃었다. 부하가 높으면 소켓이 1~3 s 늦게 생겨 화면을 못 열었다(2026-11-08).
// Xvfb 가 없는 머신에서는 건너뛴다.
#include "kood3plot/render/LSPrePostRenderer.h"

#include <cstdio>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <string>
#include <sys/wait.h>
#include <unistd.h>

using kood3plot::render::LSPrePostRenderer;
namespace fs = std::filesystem;

namespace {

int g_failed = 0;

void chk(const char* what, bool ok, const std::string& detail = "") {
    if (!ok) ++g_failed;
    std::printf("  %s %-52s %s\n", ok ? "OK " : "NG ", what, detail.c_str());
}

pid_t spawn(const std::string& cmd, const std::string& path_env = "") {
    const pid_t p = fork();
    if (p == 0) {
        if (!path_env.empty()) setenv("PATH", path_env.c_str(), 1);
        execl("/bin/sh", "sh", "-c", cmd.c_str(), nullptr);
        _exit(1);
    }
    return p;
}

int wait_rc(pid_t p) {
    int st = 0;
    waitpid(p, &st, 0);
    return WIFEXITED(st) ? WEXITSTATUS(st) : 128 + WTERMSIG(st);
}

std::string first_line(const fs::path& p) {
    std::ifstream f(p);
    std::string s;
    std::getline(f, s);
    return s;
}

std::string which(const char* name) {
    std::string out;
    if (FILE* f = popen((std::string("command -v ") + name).c_str(), "r")) {
        char buf[512];
        if (fgets(buf, sizeof buf, f)) out = buf;
        pclose(f);
    }
    while (!out.empty() && (out.back() == '\n' || out.back() == '\r')) out.pop_back();
    return out;
}

}  // namespace

int main() {
    if (which("Xvfb").empty()) {
        std::printf("Xvfb 없음 — 건너뜀\n");
        return 0;
    }
    const fs::path dir = fs::temp_directory_path() / ("lspp_xvfb_test_" + std::to_string(getpid()));
    fs::create_directories(dir);

    // 가짜 LS-PrePost — 화면 소켓이 이미 있는지 보고(없으면 rc 41), 번호를 적고, 잠깐 붙어 있다가 받은 rc 로 끝난다
    const fs::path fake = dir / "fake_lspp.sh";
    {
        std::ofstream f(fake);
        f << "#!/bin/sh\n"
             "n=${DISPLAY#:}; n=${n%.0}\n"
             "[ -S /tmp/.X11-unix/X$n ] || exit 41\n"
             "out=${1#c=}\n"
             "echo $n > \"$out\"\n"
             "sleep 1\n"
             "exit ${FAKE_RC:-0}\n";
    }
    fs::permissions(fake, fs::perms::owner_all);

    std::printf("[동시에 둘]\n");
    const pid_t a = spawn(LSPrePostRenderer::xvfbRunCommand("", fake.string(), (dir / "a.txt").string()));
    const pid_t b = spawn(LSPrePostRenderer::xvfbRunCommand("", fake.string(), (dir / "b.txt").string()));
    const int ra = wait_rc(a), rb = wait_rc(b);
    const std::string na = first_line(dir / "a.txt"), nb = first_line(dir / "b.txt");
    chk("둘 다 성공(rc 0)", ra == 0 && rb == 0, std::to_string(ra) + " / " + std::to_string(rb));
    chk("넘겨받을 때 이미 화면 소켓이 있었다(rc 41 아님)", ra != 41 && rb != 41);
    chk("서로 다른 화면 번호를 받았다", !na.empty() && !nb.empty() && na != nb, ":" + na + " / :" + nb);
    chk("끝나면 그 Xvfb 소켓이 사라진다",
        !na.empty() && !nb.empty() && !fs::exists("/tmp/.X11-unix/X" + na) && !fs::exists("/tmp/.X11-unix/X" + nb));

    std::printf("[LS-PrePost 의 종료 코드를 그대로]\n");
    const int rc7 = wait_rc(spawn("FAKE_RC=7; export FAKE_RC; " +
                                  LSPrePostRenderer::xvfbRunCommand("", fake.string(), (dir / "c.txt").string())));
    chk("LS-PrePost 가 7 이면 7", rc7 == 7, std::to_string(rc7));

    std::printf("[Xvfb 를 못 띄우면 rc 97]\n");
    {
        // Xvfb · setpriv 가 없는 PATH — 명령이 쓰는 나머지(mktemp · sleep · cat · rm)만 둔다
        const fs::path bin = dir / "bin";
        fs::create_directories(bin);
        for (const char* t : {"mktemp", "sleep", "cat", "rm"}) {
            const std::string w = which(t);
            if (!w.empty()) fs::create_symlink(w, bin / t);
        }
        const int r97 = wait_rc(spawn(LSPrePostRenderer::xvfbRunCommand("", fake.string(), (dir / "d.txt").string()),
                                      bin.string()));
        chk("rc 97 · 가짜 LS-PrePost 는 돌지 않았다", r97 == 97 && !fs::exists(dir / "d.txt"), std::to_string(r97));
    }

    std::error_code ec;
    fs::remove_all(dir, ec);
    std::printf(g_failed ? "\n[FAIL] 실패 %d 건\n" : "\n[PASS] 실패 0 건\n", g_failed);
    return g_failed ? 1 : 0;
}
