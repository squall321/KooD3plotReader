/**
 * @file 06_advanced_multisection.cpp
 * @brief 고급 다중 섹션 렌더링 예제
 *
 * 여러 섹션 평면과 Part 필터링을 조합한 고급 렌더링 예제입니다.
 * 설정 파일 없이 프로그램 내에서 직접 설정을 생성합니다.
 */

#include "kood3plot/render/LSPrePostRenderer.h"
#include "kood3plot/render/RenderConfig.h"
#include <iostream>
#include <vector>

using namespace kood3plot::render;

int main(int argc, char** argv) {
    std::cout << "==============================================\n";
    std::cout << "예제 6: 고급 다중 섹션 렌더링\n";
    std::cout << "==============================================\n\n";

    // 입력 파일 경로
    std::string d3plot_file = (argc > 1) ? argv[1] : "results/d3plot";
    std::string output_dir = (argc > 2) ? argv[2] : "./output";

    std::cout << "입력 파일: " << d3plot_file << "\n";
    std::cout << "출력 디렉토리: " << output_dir << "\n\n";

    // LSPrePost 경로 (installed 디렉토리 사용)
    std::string lsprepost_path = "installed/lsprepost/lspp412_mesa";
    LSPrePostRenderer renderer(lsprepost_path);

    // ============================================================
    // 시나리오 1: Z 방향 다중 섹션 렌더링
    // ============================================================
    std::cout << "시나리오 1: Z 방향 3개 섹션 (Z=50, 100, 150)\n";
    std::cout << "────────────────────────────────────────────\n";

    {
        RenderOptions opts;
        opts.create_animation = true;
        opts.fringe_type = FringeType::VON_MISES;
        opts.auto_fringe_range = false;
        opts.fringe_min = 0.0;
        opts.fringe_max = 500.0;
        opts.view = ViewOrientation::LEFT;
        opts.zoom_factor = 1.2;
        opts.use_auto_fit = true;

        // Z 방향 섹션 3개 추가
        opts.section_planes = {
            {{0, 0, 50}, {0, 0, 1}},
            {{0, 0, 100}, {0, 0, 1}},
            {{0, 0, 150}, {0, 0, 1}}
        };

        std::string output = output_dir + "/multi_section_z.mp4";
        std::cout << "렌더링 중: " << output << "\n";

        if (renderer.renderAnimation(d3plot_file, output, opts)) {
            std::cout << "✓ 성공!\n";
        } else {
            std::cerr << "✗ 실패: " << renderer.getLastError() << "\n";
        }
    }

    std::cout << "\n";

    // ============================================================
    // 시나리오 2: Part 필터링 + 섹션
    // ============================================================
    std::cout << "시나리오 2: Part ID 1만 표시 + 섹션\n";
    std::cout << "────────────────────────────────────────────\n";

    {
        RenderOptions opts;
        opts.create_animation = true;
        opts.fringe_type = FringeType::DISPLACEMENT;
        opts.part_id = 1;  // Part 1만 표시
        opts.view = ViewOrientation::ISOMETRIC;
        opts.zoom_factor = 1.5;

        // 중간 섹션 1개
        opts.section_planes = {
            {{0, 0, 100}, {0, 0, 1}}
        };

        std::string output = output_dir + "/part1_section.mp4";
        std::cout << "렌더링 중: " << output << "\n";

        if (renderer.renderAnimation(d3plot_file, output, opts)) {
            std::cout << "✓ 성공!\n";
        } else {
            std::cerr << "✗ 실패: " << renderer.getLastError() << "\n";
        }
    }

    std::cout << "\n";

    // ============================================================
    // 시나리오 3: 3방향 섹션 (X, Y, Z 각 1개씩)
    // ============================================================
    std::cout << "시나리오 3: XYZ 각 방향 섹션\n";
    std::cout << "────────────────────────────────────────────\n";

    {
        RenderOptions opts;
        opts.create_animation = true;
        opts.fringe_type = FringeType::STRESS_XX;
        opts.view = ViewOrientation::ISOMETRIC;
        opts.use_auto_fit = true;

        // X, Y, Z 방향 각 1개씩
        opts.section_planes = {
            {{100, 0, 0}, {1, 0, 0}},  // X 방향
            {{0, 50, 0}, {0, 1, 0}},   // Y 방향
            {{0, 0, 75}, {0, 0, 1}}    // Z 방향
        };

        std::string output = output_dir + "/xyz_sections.mp4";
        std::cout << "렌더링 중: " << output << "\n";

        if (renderer.renderAnimation(d3plot_file, output, opts)) {
            std::cout << "✓ 성공!\n";
        } else {
            std::cerr << "✗ 실패: " << renderer.getLastError() << "\n";
        }
    }

    std::cout << "\n";

    // ============================================================
    // 시나리오 4: 설정을 파일로 저장
    // ============================================================
    std::cout << "시나리오 4: 설정을 JSON/YAML로 저장\n";
    std::cout << "────────────────────────────────────────────\n";

    {
        // RenderConfig 객체 생성 및 데이터 설정
        RenderConfig config;
        RenderConfigData data;

        // Analysis 설정
        data.analysis.data_path = "./results";
        data.analysis.output_path = output_dir;
        data.analysis.run_ids = {"run_001", "run_002"};

        // Fringe 설정
        data.fringe.type = "von_mises";
        data.fringe.min = 0.0;
        data.fringe.max = 500.0;
        data.fringe.auto_range = false;

        // Output 설정
        data.output.movie = true;
        data.output.images = false;
        data.output.width = 1920;
        data.output.height = 1080;
        data.output.fps = 30;
        data.output.format = "MP4";

        // View 설정
        data.view.orientation = "left";
        data.view.zoom_factor = 1.2;
        data.view.auto_fit = true;

        // Section 설정
        SectionConfig section;
        section.part.id = 1;
        section.part.name = "Hood";
        section.planes = {
            {{0, 0, 50}, {0, 0, 1}},
            {{0, 0, 100}, {0, 0, 1}}
        };
        data.sections.push_back(section);

        config.setData(data);

        // 저장
        std::string json_file = output_dir + "/generated_config.json";
        std::string yaml_file = output_dir + "/generated_config.yaml";

        if (config.saveToJSON(json_file)) {
            std::cout << "✓ JSON 저장: " << json_file << "\n";
        }

        if (config.saveToYAML(yaml_file)) {
            std::cout << "✓ YAML 저장: " << yaml_file << "\n";
        }

        // 저장된 설정으로 렌더링 테스트
        RenderOptions opts = config.toRenderOptions();
        std::string output = output_dir + "/from_generated_config.mp4";

        std::cout << "\n생성된 설정으로 렌더링 중: " << output << "\n";

        if (renderer.renderAnimation(d3plot_file, output, opts)) {
            std::cout << "✓ 성공!\n";
        } else {
            std::cerr << "✗ 실패: " << renderer.getLastError() << "\n";
        }
    }

    std::cout << "\n";
    std::cout << "==============================================\n";
    std::cout << "모든 시나리오 완료!\n";
    std::cout << "==============================================\n";

    return 0;
}
