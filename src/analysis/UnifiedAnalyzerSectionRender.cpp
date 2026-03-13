/**
 * @file UnifiedAnalyzerSectionRender.cpp
 * @brief processSectionViews() — real implementation compiled only when
 *        KOOD3PLOT_HAS_SECTION_RENDER is defined (KOOD3PLOT_BUILD_SECTION_RENDER=ON).
 *
 * This file is listed in the target_sources() of kood3plot_section_render so
 * it is compiled into that target (and therefore into unified_analyzer when the
 * option is ON). The stub in UnifiedAnalyzer.cpp is compiled only when this
 * define is absent.
 */

#ifdef KOOD3PLOT_HAS_SECTION_RENDER

#include "kood3plot/analysis/UnifiedAnalyzer.hpp"
#include "kood3plot/section_render/SectionViewConfig.hpp"
#include "kood3plot/section_render/SectionViewRenderer.hpp"

namespace kood3plot {
namespace analysis {

bool UnifiedAnalyzer::processSectionViews(
    D3plotReader& reader,
    const UnifiedConfig& config,
    UnifiedProgressCallback callback)
{
    if (config.section_views.empty()) return true;

    bool all_ok = true;

    for (const auto& spec : config.section_views) {
        if (!spec.enabled) {
            if (callback) callback("  [section_view] Skipping (disabled): " + spec.name);
            continue;
        }

        if (callback) callback("  [section_view] Starting: " + spec.name);

        // Parse the YAML block into a SectionViewConfig
        section_render::SectionViewConfig sv_config;
        if (!sv_config.loadFromString(spec.yaml_block)) {
            if (callback) callback("  [section_view] YAML parse error: " + spec.name);
            all_ok = false;
            continue;
        }

        // Run the renderer
        section_render::SectionViewRenderer renderer;
        std::string err = renderer.render(reader, sv_config);

        if (err.empty()) {
            if (callback) callback("  [section_view] Done: " + spec.name
                                   + " → " + sv_config.output_dir);
        } else {
            if (callback) callback("  [section_view] Error (" + spec.name + "): " + err);
            all_ok = false;
        }
    }

    return all_ok;
}

} // namespace analysis
} // namespace kood3plot

#endif // KOOD3PLOT_HAS_SECTION_RENDER
