/**
 * @file 01_basic_config_usage.cpp
 * @brief JSON/YAML 설정 파일을 사용한 기본 렌더링 예제
 *
 * 이 예제는 설정 파일(JSON 또는 YAML)을 읽어서 렌더링하는 방법을 보여줍니다.
 */

#include "kood3plot/render/LSPrePostRenderer.h"
#include "kood3plot/render/RenderConfig.h"
#include <iostream>
#include <string>

using namespace kood3plot::render;

int main(int argc, char** argv) {
    std::cout << "==============================================\n";
    std::cout << "예제 1: JSON/YAML 설정 파일 사용\n";
    std::cout << "==============================================\n\n";

    // 설정 파일 경로 (기본값: config.json)
    std::string config_file = (argc > 1) ? argv[1] : "render_config_example.json";

    std::cout << "설정 파일 로드: " << config_file << "\n";

    // 1. RenderConfig 객체 생성
    RenderConfig config;

    // 2. 설정 파일 형식 자동 감지 및 로드
    bool loaded = false;
    if (config_file.find(".yaml") != std::string::npos ||
        config_file.find(".yml") != std::string::npos) {
        std::cout << "YAML 형식으로 로드 중...\n";
        loaded = config.loadFromYAML(config_file);
    } else {
        std::cout << "JSON 형식으로 로드 중...\n";
        loaded = config.loadFromJSON(config_file);
    }

    if (!loaded) {
        std::cerr << "오류: 설정 파일 로드 실패: " << config.getLastError() << "\n";
        return 1;
    }

    std::cout << "✓ 설정 파일 로드 성공\n\n";

    // 3. 설정 정보 출력
    const auto& data = config.getData();
    std::cout << "설정 내용:\n";
    std::cout << "  데이터 경로: " << data.analysis.data_path << "\n";
    std::cout << "  출력 경로: " << data.analysis.output_path << "\n";
    std::cout << "  Fringe 타입: " << data.fringe.type << "\n";
    std::cout << "  Fringe 범위: " << data.fringe.min << " ~ " << data.fringe.max << "\n";
    std::cout << "  영상 크기: " << data.output.width << "x" << data.output.height << "\n";
    std::cout << "  FPS: " << data.output.fps << "\n";
    std::cout << "  뷰 방향: " << data.view.orientation << "\n";
    std::cout << "  줌 팩터: " << data.view.zoom_factor << "\n\n";

    // 4. RenderOptions로 변환
    RenderOptions options = config.toRenderOptions();

    // 5. LSPrePostRenderer 생성
    // LSPrePost 실행 파일 경로 (시스템에 따라 조정 필요)
    std::string lsprepost_path = "references/external/lsprepost4.12_common/lsprepost";
    LSPrePostRenderer renderer(lsprepost_path);

    // 6. D3plot 파일 경로 (설정 파일 또는 명령줄에서 지정)
    std::string d3plot_file = (argc > 2) ? argv[2] : "results/d3plot";
    std::string output_file = data.analysis.output_path + "/output.mp4";

    std::cout << "렌더링 시작...\n";
    std::cout << "  입력: " << d3plot_file << "\n";
    std::cout << "  출력: " << output_file << "\n\n";

    // 7. 렌더링 실행
    bool success = renderer.renderAnimation(d3plot_file, output_file, options);

    if (success) {
        std::cout << "\n✓ 렌더링 성공!\n";
        std::cout << "출력 파일: " << output_file << "\n";
    } else {
        std::cerr << "\n✗ 렌더링 실패: " << renderer.getLastError() << "\n";
        return 1;
    }

    // 8. (선택사항) 설정을 다른 형식으로 저장
    std::cout << "\n설정 파일 저장...\n";
    config.saveToJSON("saved_config.json");
    config.saveToYAML("saved_config.yaml");
    std::cout << "✓ saved_config.json 저장됨\n";
    std::cout << "✓ saved_config.yaml 저장됨\n";

    return 0;
}
