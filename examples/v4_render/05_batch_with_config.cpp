/**
 * @file 05_batch_with_config.cpp
 * @brief 설정 파일을 사용한 배치 처리 예제
 *
 * 여러 d3plot 파일을 자동으로 처리하는 배치 렌더링 예제입니다.
 * 진행 상황을 실시간으로 보여주고 결과 리포트를 생성합니다.
 */

#include "kood3plot/render/BatchRenderer.h"
#include "kood3plot/render/ProgressMonitor.h"
#include "kood3plot/render/RenderConfig.h"
#include <iostream>
#include <iomanip>

using namespace kood3plot::render;

int main(int argc, char** argv) {
    std::cout << "==============================================\n";
    std::cout << "예제 5: 설정 파일 기반 배치 처리\n";
    std::cout << "==============================================\n\n";

    // 설정 파일 로드
    std::string config_file = (argc > 1) ? argv[1] : "render_config_example.json";

    RenderConfig config;
    if (!config.loadFromJSON(config_file)) {
        std::cerr << "오류: 설정 파일 로드 실패: " << config.getLastError() << "\n";
        return 1;
    }

    std::cout << "✓ 설정 파일 로드 완료: " << config_file << "\n\n";

    // LSPrePost 경로 (installed 디렉토리 사용)
    std::string lsprepost_path = "installed/lsprepost/lspp412_mesa";

    // BatchRenderer 생성
    BatchRenderer batch(lsprepost_path);

    // 배치 작업 생성
    const auto& data = config.getData();
    std::cout << "배치 작업 생성 중...\n";

    // Von Mises 응력 렌더링
    RenderOptions vm_opts = config.toRenderOptions();
    vm_opts.fringe_type = FringeType::VON_MISES;
    batch.addJob({
        "vm_stress",
        data.analysis.data_path + "/d3plot",
        data.analysis.output_path + "/von_mises.mp4",
        vm_opts
    });

    // 변위 렌더링
    RenderOptions disp_opts = config.toRenderOptions();
    disp_opts.fringe_type = FringeType::DISPLACEMENT;
    batch.addJob({
        "displacement",
        data.analysis.data_path + "/d3plot",
        data.analysis.output_path + "/displacement.mp4",
        disp_opts
    });

    // Effective Strain 렌더링
    RenderOptions strain_opts = config.toRenderOptions();
    strain_opts.fringe_type = FringeType::EFFECTIVE_STRAIN;
    batch.addJob({
        "eff_strain",
        data.analysis.data_path + "/d3plot",
        data.analysis.output_path + "/effective_strain.mp4",
        strain_opts
    });

    std::cout << "✓ 총 " << batch.getJobCount() << "개 작업 등록\n\n";

    // ProgressMonitor 생성
    ProgressMonitor progress(batch.getJobCount());
    progress.start();

    std::cout << "배치 처리 시작...\n";
    std::cout << "────────────────────────────────────────────\n\n";

    // 진행 상황 콜백 함수
    auto progress_callback = [&](size_t completed, size_t total,
                                  const std::string& job_id, double pct) {
        // Progress bar 표시
        int bar_width = 40;
        int pos = bar_width * pct / 100.0;

        std::cout << "\r[";
        for (int i = 0; i < bar_width; ++i) {
            if (i < pos) std::cout << "=";
            else if (i == pos) std::cout << ">";
            else std::cout << " ";
        }
        std::cout << "] " << std::fixed << std::setprecision(1) << pct << "% ";
        std::cout << "(" << completed << "/" << total << ") ";
        std::cout << "현재: " << job_id << "          ";
        std::cout << std::flush;
    };

    // 배치 처리 실행
    size_t successful = batch.processAll(progress_callback);

    std::cout << "\n\n";
    std::cout << "────────────────────────────────────────────\n";
    std::cout << "배치 처리 완료!\n\n";

    // 결과 요약
    std::cout << "처리 결과:\n";
    std::cout << "  성공: " << successful << " / " << batch.getJobCount() << "\n";
    std::cout << "  실패: " << batch.getFailedCount() << "\n";

    if (batch.hasFailures()) {
        std::cout << "\n실패한 작업:\n";
        auto errors = batch.getErrors();
        for (const auto& [job_id, error] : errors) {
            std::cout << "  - " << job_id << ": " << error << "\n";
        }
    }

    // 리포트 저장
    std::string report_path = data.analysis.output_path + "/batch_report.txt";
    std::string csv_path = data.analysis.output_path + "/batch_results.csv";

    if (batch.saveReport(report_path)) {
        std::cout << "\n✓ 텍스트 리포트 저장: " << report_path << "\n";
    }

    if (batch.exportToCSV(csv_path)) {
        std::cout << "✓ CSV 결과 저장: " << csv_path << "\n";
    }

    // 상세 리포트 출력
    std::cout << "\n" << std::string(50, '=') << "\n";
    std::cout << batch.generateReport();
    std::cout << std::string(50, '=') << "\n";

    return (successful == batch.getJobCount()) ? 0 : 1;
}
