/**
 * @file UnifiedConfigParser.cpp
 * @brief Unified YAML configuration parser implementation
 */

#include "kood3plot/analysis/UnifiedConfigParser.hpp"
#include "kood3plot/D3plotReader.hpp"
#include <fstream>
#include <sstream>
#include <algorithm>
#include <cctype>
#include <cstdlib>
#include <iostream>
#include <map>
#include <filesystem>
#include <unordered_map>
#include <set>

namespace {

/**
 * @brief 한 줄에서 LS-DYNA 키워드 토큰만 뽑는다 (대문자, 주석·주석뒤 내용 제외)
 */
std::string keywordToken(const std::string& line) {
    std::string tok;
    for (char c : line) {
        if (std::isspace(static_cast<unsigned char>(c)) || c == '$') break;
        tok += static_cast<char>(std::toupper(static_cast<unsigned char>(c)));
    }
    return tok;
}

/**
 * @brief 카드의 첫 필드(쉼표 구분이면 첫 항목, 아니면 1-10열)를 잘라낸다
 */
std::string firstField(const std::string& line) {
    std::string field = (line.find(',') != std::string::npos)
                            ? line.substr(0, line.find(','))
                            : line.substr(0, std::min<size_t>(line.size(), 10));
    const size_t s = field.find_first_not_of(" \t\r\n");
    if (s == std::string::npos) return "";
    const size_t e = field.find_last_not_of(" \t\r\n");
    return field.substr(s, e - s + 1);
}

/**
 * @brief 첫 필드가 통째로 숫자인가 (= 제목 카드가 아니라 데이터 카드)
 */
bool firstFieldIsNumeric(const std::string& line) {
    const std::string f = firstField(line);
    if (f.empty()) return false;
    char* end = nullptr;
    std::strtod(f.c_str(), &end);
    return end != nullptr && *end == '\0';
}

std::string trimCopy(const std::string& s) {
    const size_t b = s.find_first_not_of(" \t\r\n");
    if (b == std::string::npos) return "";
    const size_t e = s.find_last_not_of(" \t\r\n");
    return s.substr(b, e - b + 1);
}

/**
 * @brief 키워드 파일에서 *PART 이름을 모은다. *INCLUDE 는 따라 들어간다.
 *
 * 🔴 예전에는 (1) *INCLUDE 를 안 따라가고 (2) "*PART_" 가 든 줄을 통째로 건너뛰고
 *    (3) 한 *PART 블록의 첫 파트만 읽었다. 메시가 *INCLUDE 안에 있는 덱
 *    (실측 /data/battery_study/case_01_phase1_stacked_tier-1 — *PART 34개가
 *    02_mesh_stacked_tier-1.k 에 있다) 에서는 이름을 하나도 못 찾았고,
 *    이름 패턴이 전부 0개로 떨어졌다.
 *
 * @param keyword_path  읽을 파일
 * @param part_names    [출력] PID → 이름
 * @param visited       순환 *INCLUDE 방지
 * @param root_dir      상대 경로 *INCLUDE 의 2차 기준 (최초 덱이 있는 폴더)
 * @param depth         재귀 깊이 (16 에서 멈춘다)
 * @param missing_includes [출력] 못 연 *INCLUDE 개수
 */
void parsePartNamesInto(const std::string& keyword_path,
                        std::unordered_map<int32_t, std::string>& part_names,
                        std::set<std::string>& visited,
                        const std::filesystem::path& root_dir,
                        int depth,
                        size_t& missing_includes) {
    namespace fs = std::filesystem;

    if (depth > 16) return;

    std::error_code ec;
    std::string key = fs::weakly_canonical(fs::path(keyword_path), ec).string();
    if (ec || key.empty()) key = keyword_path;
    if (!visited.insert(key).second) return;   // 이미 읽은 파일 (순환 포함)

    std::ifstream ifs(keyword_path);
    if (!ifs.is_open()) {
        ++missing_includes;
        return;
    }

    const fs::path self_dir = fs::path(keyword_path).parent_path();

    enum class Mode { None, PartMulti, PartSingle, IncludeMulti, IncludeSingle };
    Mode mode = Mode::None;
    int line_in_part = 0;
    std::string current_title;

    std::string line;
    while (std::getline(ifs, line)) {
        if (!line.empty() && line.back() == '\r') line.pop_back();
        if (!line.empty() && line[0] == '$') continue;   // 주석

        if (!line.empty() && line[0] == '*') {
            const std::string tok = keywordToken(line);
            if (tok == "*PART") {
                // 한 블록에 (제목 + PID 카드) 쌍이 여러 개 올 수 있다
                mode = Mode::PartMulti;
            } else if (tok.rfind("*PART_", 0) == 0) {
                // *PART_COMPOSITE / *PART_INERTIA / *PART_CONTACT ...
                // 뒤에 층·관성 카드가 붙으므로 첫 쌍만 읽는다.
                mode = Mode::PartSingle;
            } else if (tok == "*INCLUDE") {
                mode = Mode::IncludeMulti;
            } else if (tok.rfind("*INCLUDE_", 0) == 0) {
                // *INCLUDE_TRANSFORM 등은 첫 줄만 파일 이름이다
                mode = Mode::IncludeSingle;
            } else {
                mode = Mode::None;
            }
            line_in_part = 0;
            current_title.clear();
            continue;
        }

        if (mode == Mode::IncludeMulti || mode == Mode::IncludeSingle) {
            const std::string name = trimCopy(line);
            if (name.empty()) continue;
            fs::path inc(name);
            std::string resolved;
            if (inc.is_absolute() && fs::exists(inc)) {
                resolved = inc.string();
            } else if (fs::exists(self_dir / inc)) {
                resolved = (self_dir / inc).string();
            } else if (fs::exists(root_dir / inc)) {
                resolved = (root_dir / inc).string();
            }
            if (resolved.empty()) {
                ++missing_includes;
            } else {
                parsePartNamesInto(resolved, part_names, visited, root_dir,
                                   depth + 1, missing_includes);
            }
            if (mode == Mode::IncludeSingle) mode = Mode::None;
            continue;
        }

        if (mode != Mode::PartMulti && mode != Mode::PartSingle) continue;

        // 🔴 *PART 블록 안에서는 빈 줄도 카드다 — 건너뛰면 제목/PID 가 한 칸 밀린다.
        ++line_in_part;
        if (line_in_part == 1) {
            if (firstFieldIsNumeric(line)) {
                // 제목 카드가 없는 변형(*PART_ADAPTIVE_FAILURE 등) — 추측하지 않는다
                mode = Mode::None;
                continue;
            }
            current_title = trimCopy(line);
        } else if (line_in_part == 2) {
            const std::string pid_str = firstField(line);
            try {
                const int32_t pid = std::stoi(pid_str);
                if (!current_title.empty()) part_names[pid] = current_title;
            } catch (...) {
                // 숫자가 아니면 이 블록은 우리가 아는 형식이 아니다 — 버린다
                mode = Mode::None;
                continue;
            }
            if (mode == Mode::PartMulti) {
                line_in_part = 0;      // 다음 (제목 + PID) 쌍
                current_title.clear();
            } else {
                mode = Mode::None;     // 변형 키워드는 첫 쌍만
            }
        }
    }
}

/**
 * @brief d3plot 옆의 키워드 파일 후보를 우선순위 순으로 모은다
 *
 * 🔴 예전에는 `fs::directory_iterator` 가 처음 돌려주는 .k 하나만 썼다. 그건
 *    readdir 순서라 주 덱이라는 보장이 없다 (실측 battery case_01 에서는
 *    *PART 가 하나도 없는 07_control_phase1.k 가 먼저 나왔다).
 *    이제 후보를 순서대로 모아두고, 호출부가 이름이 나올 때까지 훑는다.
 */
std::vector<std::string> collectKeywordCandidates(const std::string& d3plot_path) {
    namespace fs = std::filesystem;

    fs::path d3plot(d3plot_path);
    fs::path dir = d3plot.parent_path();

    std::vector<std::string> candidates;
    std::set<std::string> seen;
    auto add = [&](const fs::path& p) {
        if (!fs::exists(p)) return;
        const std::string s = p.string();
        if (seen.insert(s).second) candidates.push_back(s);
    };

    // Common keyword file extensions
    std::vector<std::string> extensions = {".k", ".key", ".dyn", ".K", ".KEY", ".DYN"};

    // Try same name with keyword extension
    std::string stem = d3plot.stem().string();
    // Remove d3plot suffix if present
    if (stem.find("d3plot") != std::string::npos) {
        size_t pos = stem.find("d3plot");
        stem = stem.substr(0, pos);
        if (!stem.empty() && (stem.back() == '_' || stem.back() == '-' || stem.back() == '.')) {
            stem.pop_back();
        }
    }

    for (const auto& ext : extensions) {
        if (!stem.empty()) add(dir / (stem + ext));
        for (const std::string& name : {"main", "input", "model", "keyword"}) {
            add(dir / (name + ext));
        }
    }

    // 나머지 .k/.key/.dyn — readdir 순서에 기대지 않도록 이름순으로 정렬한다
    std::vector<std::string> rest;
    try {
        for (const auto& entry : fs::directory_iterator(dir)) {
            if (!entry.is_regular_file()) continue;
            std::string ext = entry.path().extension().string();
            std::transform(ext.begin(), ext.end(), ext.begin(), ::tolower);
            if (ext == ".k" || ext == ".key" || ext == ".dyn") {
                rest.push_back(entry.path().string());
            }
        }
    } catch (...) {
        // Directory iteration failed
    }
    std::sort(rest.begin(), rest.end());
    for (const auto& p : rest) add(p);

    return candidates;
}

// Global cache for part names (loaded once per d3plot path)
std::unordered_map<std::string, std::unordered_map<int32_t, std::string>> g_part_name_cache;

} // anonymous namespace

namespace kood3plot {
namespace analysis {

std::string UnifiedConfigParser::last_error_;

std::string UnifiedConfigParser::trim(const std::string& str) {
    size_t start = 0;
    while (start < str.size() && std::isspace(str[start])) ++start;
    size_t end = str.size();
    while (end > start && std::isspace(str[end - 1])) --end;
    return str.substr(start, end - start);
}

std::vector<double> UnifiedConfigParser::parseDoubleArray(const std::string& str) {
    std::vector<double> result;
    std::string s = str;

    // Remove brackets
    size_t start = s.find('[');
    size_t end = s.find(']');
    if (start != std::string::npos && end != std::string::npos) {
        s = s.substr(start + 1, end - start - 1);
    }

    std::istringstream iss(s);
    std::string token;
    while (std::getline(iss, token, ',')) {
        try {
            result.push_back(std::stod(trim(token)));
        } catch (...) {}
    }

    return result;
}

std::vector<int32_t> UnifiedConfigParser::parseIntArray(const std::string& str) {
    std::vector<int32_t> result;
    std::string s = str;

    // Remove brackets
    size_t start = s.find('[');
    size_t end = s.find(']');
    if (start != std::string::npos && end != std::string::npos) {
        s = s.substr(start + 1, end - start - 1);
    }

    std::istringstream iss(s);
    std::string token;
    while (std::getline(iss, token, ',')) {
        std::string trimmed = trim(token);
        if (trimmed.empty()) continue;
        try {
            result.push_back(std::stoi(trimmed));
        } catch (...) {}
    }

    return result;
}

std::vector<std::string> UnifiedConfigParser::parseStringArray(const std::string& str) {
    std::vector<std::string> result;
    std::string s = str;

    // Remove brackets
    size_t start = s.find('[');
    size_t end = s.find(']');
    if (start != std::string::npos && end != std::string::npos) {
        s = s.substr(start + 1, end - start - 1);
    }

    std::istringstream iss(s);
    std::string token;
    while (std::getline(iss, token, ',')) {
        std::string trimmed = trim(token);
        // Remove quotes
        if (!trimmed.empty() && (trimmed[0] == '"' || trimmed[0] == '\'')) {
            trimmed = trimmed.substr(1);
        }
        if (!trimmed.empty() && (trimmed.back() == '"' || trimmed.back() == '\'')) {
            trimmed.pop_back();
        }
        if (!trimmed.empty()) {
            result.push_back(trimmed);
        }
    }

    return result;
}

bool UnifiedConfigParser::parseBool(const std::string& str) {
    std::string lower = str;
    std::transform(lower.begin(), lower.end(), lower.begin(), ::tolower);
    return (lower == "true" || lower == "1" || lower == "yes" || lower == "on");
}

bool UnifiedConfigParser::loadFromYAML(const std::string& file_path, UnifiedConfig& config) {
    std::ifstream ifs(file_path);
    if (!ifs.is_open()) {
        last_error_ = "Cannot open file: " + file_path;
        return false;
    }

    std::ostringstream oss;
    oss << ifs.rdbuf();
    return loadFromYAMLString(oss.str(), config);
}

bool UnifiedConfigParser::loadFromYAMLString(const std::string& yaml_content, UnifiedConfig& config) {
    std::istringstream iss(yaml_content);
    std::string line;

    // Reset config
    config = UnifiedConfig();

    // Parse into lines
    std::vector<std::string> lines;
    while (std::getline(iss, line)) {
        // Remove comments
        size_t comment_pos = line.find('#');
        if (comment_pos != std::string::npos) {
            line = line.substr(0, comment_pos);
        }
        lines.push_back(line);
    }

    std::string current_section;
    bool in_analysis_jobs = false;
    bool in_render_jobs = false;
    bool in_section_views = false;
    bool in_part_section_renders = false;
    AnalysisJob current_analysis_job;
    RenderJob current_render_job;
    SectionViewJobSpec current_sv;
    PartSectionRenderJob current_psr;
    SetReportSpec current_sr;
    bool has_current_sr = false;
    bool in_set_reports = false;
    bool has_current_analysis_job = false;
    /// 이 잡 안에서 못 읽는 문법을 만났다 — 기본값으로 돌리지 말고 통째로 뺀다.
    bool current_analysis_job_invalid = false;
    bool has_current_render_job = false;
    bool has_current_sv = false;
    bool has_current_psr = false;
    std::string psr_sub_section;  // "output"

    // Sub-section tracking
    std::string sub_section;  // "surface", "output", "section", "fringe_range"

    auto flush_analysis_job = [&]() {
        if (has_current_analysis_job && !current_analysis_job.name.empty() &&
            !current_analysis_job_invalid) {
            config.analysis_jobs.push_back(current_analysis_job);
        }
        current_analysis_job = AnalysisJob();
        has_current_analysis_job = false;
        current_analysis_job_invalid = false;
        sub_section.clear();
    };

    auto flush_render_job = [&]() {
        if (has_current_render_job && !current_render_job.name.empty()) {
            config.render_jobs.push_back(current_render_job);
        }
        current_render_job = RenderJob();
        has_current_render_job = false;
        sub_section.clear();
    };

    auto flush_sv = [&]() {
        if (has_current_sv) {
            config.section_views.push_back(current_sv);
        }
        current_sv = SectionViewJobSpec();
        has_current_sv = false;
    };

    auto flush_sr = [&]() {
        if (has_current_sr) {
            if (!current_sr.name.empty()) {
                config.set_reports.push_back(current_sr);
            } else {
                // 무음 탈락 금지 — 요청이 조용히 사라지면 부분 산출물이 정상 행세한다
                std::cerr << "[config] 경고: name 없는 set_reports 항목을 건너뜀 "
                          << "(name 은 필수)" << std::endl;
            }
        }
        current_sr = SetReportSpec();
        has_current_sr = false;
    };

    auto flush_psr = [&]() {
        if (has_current_psr) {
            config.part_section_renders.push_back(current_psr);
        }
        current_psr = PartSectionRenderJob();
        has_current_psr = false;
        psr_sub_section.clear();
    };

    for (size_t i = 0; i < lines.size(); ++i) {
        const std::string& raw_line = lines[i];
        std::string trimmed = trim(raw_line);
        if (trimmed.empty()) continue;

        // Count indent
        size_t indent = 0;
        while (indent < raw_line.size() && (raw_line[indent] == ' ' || raw_line[indent] == '\t')) {
            indent++;
        }

        // Check for list item
        bool is_list_item = (trimmed[0] == '-');
        if (is_list_item) {
            trimmed = trim(trimmed.substr(1));
        }

        // Parse key:value
        size_t colon_pos = trimmed.find(':');
        if (colon_pos == std::string::npos) {
            // 값만 있는 리스트 항목('- xxx')은 블록 리스트 문법 — 이 수제 파서가
            // 지원하지 않는다. 무음 폐기하면 'fields 1개 요청'이 '전 필드 기본값'
            // 으로 둔갑하므로 경고. (위에서 '-' 를 이미 벗겼으므로 플래그로 판별)
            if (is_list_item) {
                std::cerr << "[config] 경고: 블록 리스트 문법 미지원 — '- " << trimmed
                          << "' 무시됨. 인라인 [a, b] 형식을 쓰세요" << std::endl;
            }
            continue;
        }

        std::string key = trim(trimmed.substr(0, colon_pos));
        std::string value = trim(trimmed.substr(colon_pos + 1));

        // 인라인 매핑(`surface: { direction: [0,0,1], angle: 45 }`)은 이 수제 파서가
        // 읽지 못한다. 그 줄만 버리면 잡이 **기본값으로** 돌아간다 — 실제로
        // +Z/-Z 두 잡이 모두 기본 -Z 로 돌아 같은 결과를 냈다 (2026-09-17).
        // 경고만으로는 부족하다: 래핑 실행에서는 stderr 가 삼켜지고 산출물에는
        // 표식이 없어, 사용자가 붙인 이름표를 단 기본값이 그대로 보고서에 실린다.
        // 그래서 그 잡을 통째로 빼고 사유를 설정에 남긴다(→ metadata.config_issues).
        if (!value.empty() && value[0] == '{') {
            std::ostringstream issue;
            issue << "설정 " << (i + 1) << "행 '" << key
                  << ":' 의 인라인 매핑 { ... } 은 지원하지 않습니다";
            if (in_analysis_jobs && has_current_analysis_job) {
                current_analysis_job_invalid = true;
                issue << " — 분석 잡 '"
                      << (current_analysis_job.name.empty() ? std::string("(이름 없음)")
                                                            : current_analysis_job.name)
                      << "' 을 건너뜁니다";
            } else {
                issue << " — 이 줄은 무시됩니다";
            }
            issue << ". 블록 형식으로 쓰세요 (다음 줄에 들여쓰기해서 key: value).";
            config.config_issues.push_back(issue.str());
            std::cerr << "[config] 경고: " << issue.str() << std::endl;
            continue;
        }

        // Remove quotes from value
        if (!value.empty() && (value[0] == '"' || value[0] == '\'')) {
            char quote = value[0];
            value = value.substr(1);
            size_t end_quote = value.find(quote);
            if (end_quote != std::string::npos) {
                value = value.substr(0, end_quote);
            }
        }

        // Root level sections (indent == 0)
        if (indent == 0) {
            if (in_analysis_jobs) flush_analysis_job();
            if (in_render_jobs) flush_render_job();
            if (in_section_views) flush_sv();
            if (in_part_section_renders) flush_psr();
            if (in_set_reports) flush_sr();

            in_analysis_jobs = false;
            in_render_jobs = false;
            in_section_views = false;
            in_part_section_renders = false;
            in_set_reports = false;
            current_section = key;

            if (key == "analysis_jobs") {
                in_analysis_jobs = true;
            } else if (key == "render_jobs") {
                in_render_jobs = true;
            } else if (key == "section_views") {
                in_section_views = true;
            } else if (key == "part_section_renders") {
                in_part_section_renders = true;
            } else if (key == "set_reports") {
                in_set_reports = true;
            } else if (key == "version") {
                config.version = value;
            }
            continue;
        }

        // Handle section_views list items
        if (in_section_views && is_list_item && indent <= 2) {
            flush_sv();
            has_current_sv = true;
            if (key == "name") current_sv.name = value;
            continue;
        }

        // Accumulate section_view job content into yaml_block
        if (in_section_views && has_current_sv) {
            if (key == "name") {
                current_sv.name = value;
            } else if (key == "enabled") {
                current_sv.enabled = parseBool(value);
            }
            // Append the raw line with indent normalised to 0
            // (list items sit at indent 2, so sub-keys start at indent 4)
            const size_t sv_base = 4;
            std::string norm = (raw_line.size() > sv_base)
                               ? raw_line.substr(sv_base)
                               : trimmed;
            current_sv.yaml_block += norm + "\n";
            continue;
        }

        // Handle analysis_jobs list items
        if (in_analysis_jobs && is_list_item && indent <= 2) {
            flush_analysis_job();
            has_current_analysis_job = true;
            if (key == "name") {
                current_analysis_job.name = value;
            }
            continue;
        }

        // Handle render_jobs list items
        if (in_render_jobs && is_list_item && indent <= 2) {
            flush_render_job();
            has_current_render_job = true;
            if (key == "name") {
                current_render_job.name = value;
            }
            continue;
        }

        // Handle set_reports list items (Custom Report)
        if (in_set_reports && is_list_item && indent <= 2) {
            flush_sr();
            has_current_sr = true;
            if (key == "name") current_sr.name = value;
            continue;
        }

        // Parse set_reports fields — 인라인 리스트만 지원 ("planes: [xy, yz]").
        // 블록 스타일 '- xy' 는 이 수제 파서가 콜론 없는 줄을 버리므로 쓰지 말 것.
        if (in_set_reports && has_current_sr) {
            if (indent == 4) {
                if (key == "name") {
                    current_sr.name = value;
                } else if (key == "set_type" || key == "type") {
                    current_sr.set_type = value;
                } else if (key == "set_id" || key == "id") {
                    try { current_sr.set_id = std::stoi(value); } catch (...) {
                        std::cerr << "[config] 경고: set_id 파싱 실패 '" << value
                                  << "' — 0 으로 둠 (parts/part_patterns 필요)" << std::endl;
                    }
                } else if (key == "fields") {
                    current_sr.fields = parseStringArray(value);
                } else if (key == "planes") {
                    auto strs = parseStringArray(value);
                    current_sr.planes.clear();
                    for (auto& v2 : strs) {
                        std::string low;
                        for (char c : v2) low.push_back(static_cast<char>(std::tolower(c)));
                        if (low == "xy" || low == "yz" || low == "zx") {
                            current_sr.planes.push_back(low);
                        }
                    }
                } else if (key == "video") {
                    current_sr.video = parseBool(value);
                } else if (key == "peak_snapshot") {
                    current_sr.peak_snapshot = parseBool(value);
                } else if (key == "width") {
                    try { current_sr.width = std::stoi(value); } catch (...) {}
                } else if (key == "height") {
                    try { current_sr.height = std::stoi(value); } catch (...) {}
                } else if (key == "max_frames") {
                    try { current_sr.max_frames = std::stoi(value); } catch (...) {}
                } else if (key == "parts" || key == "part_ids") {
                    auto v2 = parseIntArray(value);
                    current_sr.part_ids.assign(v2.begin(), v2.end());
                } else if (key == "part_patterns" || key == "part_names") {
                    current_sr.part_patterns = parseStringArray(value);
                } else if (key == "highlight_segments" || key == "segments") {
                    auto v2 = parseIntArray(value);
                    current_sr.highlight_segment_sets.assign(v2.begin(), v2.end());
                }
                // 알 수 없는 키는 조용히 넘기되 스키마 확장 여지로 남긴다
            }
            continue;
        }

        // Handle part_section_renders list items
        if (in_part_section_renders && is_list_item && indent <= 2) {
            flush_psr();
            has_current_psr = true;
            if (key == "name") current_psr.name = value;
            continue;
        }

        // Parse part_section_renders fields
        if (in_part_section_renders && has_current_psr) {
            // Sub-section header (indent 4, value empty)
            if (indent == 4 && value.empty()) {
                if (key == "output") { psr_sub_section = "output"; continue; }
                psr_sub_section.clear();
            }

            // Sub-section: output
            if (psr_sub_section == "output" && indent >= 6) {
                if (key == "directory") {
                    current_psr.output_directory = value;
                } else if (key == "resolution") {
                    auto vec = parseIntArray(value);
                    if (vec.size() >= 2) {
                        current_psr.resolution.assign(vec.begin(), vec.begin() + 2);
                    }
                } else if (key == "fps") {
                    try { current_psr.fps = std::stoi(value); } catch (...) {}
                }
                continue;
            }

            // Top-level fields (indent 4)
            if (indent == 4) {
                psr_sub_section.clear();  // exit any sub-section
                if (key == "name") {
                    current_psr.name = value;
                } else if (key == "enabled") {
                    current_psr.enabled = parseBool(value);
                } else if (key == "fringe_type" || key == "fringe") {
                    current_psr.fringe_type = value;
                } else if (key == "axes") {
                    auto strs = parseStringArray(value);
                    current_psr.axes.clear();
                    for (const auto& s : strs) {
                        if (s.empty()) continue;
                        // Normalize to "x" or "+x"/"-x" form (lowercase axis letter)
                        std::string out;
                        size_t p = 0;
                        if (s[0] == '+' || s[0] == '-') {
                            out.push_back(s[0]);
                            p = 1;
                        }
                        if (p < s.size()) out.push_back(std::tolower(s[p]));
                        if (!out.empty()) current_psr.axes.push_back(out);
                    }
                } else if (key == "part_ids" || key == "parts") {
                    auto vec = parseIntArray(value);
                    current_psr.part_ids.assign(vec.begin(), vec.end());
                } else if (key == "section_view") {
                    current_psr.section_view = parseBool(value);
                } else if (key == "iso_clip_view") {
                    current_psr.iso_clip_view = parseBool(value);
                } else if (key == "section_position") {
                    try { current_psr.section_position = std::stod(value); } catch (...) {}
                } else if (key == "section_margin") {
                    try { current_psr.section_margin = std::stod(value); } catch (...) {}
                } else if (key == "iso_clip_margin") {
                    try { current_psr.iso_clip_margin = std::stod(value); } catch (...) {}
                } else if (key == "edge_width") {
                    try { current_psr.edge_width = std::stoi(value); } catch (...) {}
                } else if (key == "crf") {
                    try { current_psr.crf = std::stoi(value); } catch (...) {}
                } else if (key == "reverse_cut") {
                    current_psr.reverse_cut = parseBool(value);
                } else if (key == "sliding_view") {
                    current_psr.sliding_view = parseBool(value);
                } else if (key == "sliding_section_style") {
                    current_psr.sliding_section_style = parseBool(value);
                } else if (key == "sliding_iso_style") {
                    current_psr.sliding_iso_style = parseBool(value);
                } else if (key == "sliding_steps") {
                    try { current_psr.sliding_steps = std::stoi(value); } catch (...) {}
                } else if (key == "sliding_near_to_far") {
                    current_psr.sliding_near_to_far = parseBool(value);
                } else if (key == "sliding_pad") {
                    try { current_psr.sliding_pad = std::stod(value); } catch (...) {}
                } else if (key == "sliding_freeze_time") {
                    current_psr.sliding_freeze_time = parseBool(value);
                } else if (key == "sliding_peak_time") {
                    try { current_psr.sliding_peak_time = std::stod(value); } catch (...) {}
                }
                continue;
            }
        }

        // Parse analysis job properties
        if (in_analysis_jobs && has_current_analysis_job) {
            // Check for sub-sections
            if (value.empty()) {
                sub_section = key;
                continue;
            }

            if (sub_section == "surface") {
                if (key == "direction") {
                    auto vec = parseDoubleArray(value);
                    if (vec.size() >= 3) {
                        current_analysis_job.surface.direction = Vec3(vec[0], vec[1], vec[2]);
                    }
                } else if (key == "angle") {
                    try { current_analysis_job.surface.angle = std::stod(value); } catch (...) {}
                }
            } else {
                // Top-level job properties
                if (key == "name") {
                    current_analysis_job.name = value;
                } else if (key == "type") {
                    current_analysis_job.type = parseJobType(value);
                } else if (key == "parts") {
                    current_analysis_job.part_ids = parseIntArray(value);
                } else if (key == "part_pattern") {
                    current_analysis_job.part_pattern = value;
                } else if (key == "output_prefix") {
                    current_analysis_job.output_prefix = value;
                } else if (key == "quantities") {
                    current_analysis_job.quantities = parseStringArray(value);
                }
            }
            continue;
        }

        // Parse render job properties
        if (in_render_jobs && has_current_render_job) {
            // Reset sub_section when back at job-property indent (≤4, non-list, non-empty value).
            // Sub-section content is at indent 6; job-level properties are at indent 4.
            // Without this, "states:" after "section:" block is silently ignored.
            if (!is_list_item && indent <= 4 && !value.empty() && !sub_section.empty()) {
                sub_section.clear();
            }

            // Check for sub-sections
            if (value.empty()) {
                sub_section = key;
                // Initialize section spec for single section sub-section
                if (key == "section") {
                    current_render_job.sections.clear();
                    current_render_job.sections.push_back(RenderSectionSpec());
                }
                // "sections" (plural) is an array - don't initialize here
                continue;
            }

            // Handle sections array (each item starts with "- axis:")
            if (sub_section == "sections" && is_list_item) {
                // New section item in the array
                current_render_job.sections.push_back(RenderSectionSpec());
                RenderSectionSpec& sec = current_render_job.sections.back();
                if (key == "axis" && !value.empty()) {
                    sec.axis = std::tolower(value[0]);
                }
                continue;
            }

            // Continue parsing current section in sections array
            if (sub_section == "sections" && !current_render_job.sections.empty()) {
                RenderSectionSpec& sec = current_render_job.sections.back();
                if (key == "axis" && !value.empty()) {
                    sec.axis = std::tolower(value[0]);
                } else if (key == "position") {
                    sec = RenderSectionSpec::fromPositionString(sec.axis, value);
                }
                continue;
            }

            if (sub_section == "section") {
                if (current_render_job.sections.empty()) {
                    current_render_job.sections.push_back(RenderSectionSpec());
                }
                RenderSectionSpec& sec = current_render_job.sections.back();
                if (key == "axis") {
                    if (!value.empty()) sec.axis = std::tolower(value[0]);
                } else if (key == "position") {
                    // Use the new fromPositionString helper
                    sec = RenderSectionSpec::fromPositionString(sec.axis, value);
                }
            } else if (sub_section == "fringe_range") {
                if (key == "min") {
                    try { current_render_job.fringe_range.min = std::stod(value); } catch (...) {}
                } else if (key == "max") {
                    try { current_render_job.fringe_range.max = std::stod(value); } catch (...) {}
                }
            } else if (sub_section == "output") {
                if (key == "format") {
                    std::string lower = value;
                    std::transform(lower.begin(), lower.end(), lower.begin(), ::tolower);
                    if (lower == "mp4") current_render_job.output.format = RenderOutputFormat::MP4;
                    else if (lower == "png") current_render_job.output.format = RenderOutputFormat::PNG;
                    else if (lower == "jpg" || lower == "jpeg") current_render_job.output.format = RenderOutputFormat::JPG;
                    else if (lower == "gif") current_render_job.output.format = RenderOutputFormat::GIF;
                } else if (key == "filename") {
                    current_render_job.output.filename = value;
                } else if (key == "directory") {
                    current_render_job.output.directory = value;
                } else if (key == "filename_pattern") {
                    current_render_job.output.filename_pattern = value;
                } else if (key == "fps") {
                    try { current_render_job.output.fps = std::stoi(value); } catch (...) {}
                } else if (key == "resolution") {
                    auto res = parseIntArray(value);
                    if (res.size() >= 2) {
                        current_render_job.output.resolution = {res[0], res[1]};
                    }
                }
            } else {
                // Top-level render job properties
                if (key == "name") {
                    current_render_job.name = value;
                } else if (key == "type") {
                    std::string lower = value;
                    std::transform(lower.begin(), lower.end(), lower.begin(), ::tolower);
                    if (lower == "section_view") current_render_job.type = RenderJobType::SECTION_VIEW;
                    else if (lower == "multi_section") current_render_job.type = RenderJobType::MULTI_SECTION;
                    else if (lower == "part_view") current_render_job.type = RenderJobType::PART_VIEW;
                    else if (lower == "full_model") current_render_job.type = RenderJobType::FULL_MODEL;
                } else if (key == "fringe") {
                    current_render_job.fringe_type = value;
                } else if (key == "parts") {
                    current_render_job.parts = parseIntArray(value);
                } else if (key == "part_pattern") {
                    current_render_job.part_pattern = value;
                } else if (key == "states") {
                    if (value == "all") {
                        current_render_job.states.clear();  // empty = all
                    } else {
                        current_render_job.states = parseIntArray(value);
                    }
                } else if (key == "view") {
                    current_render_job.view_str = value;
                }
            }
            continue;
        }

        // Parse input section
        if (current_section == "sets") {
            if (key == "file") {
                config.sets_file = value;
            }
            continue;
        }

        if (current_section == "input") {
            if (key == "d3plot") {
                config.d3plot_path = value;
            }
        }
        // Parse output section
        else if (current_section == "output") {
            if (key == "directory") {
                config.output_directory = value;
            } else if (key == "json") {
                config.output_json = parseBool(value);
            } else if (key == "csv") {
                config.output_csv = parseBool(value);
            }
        }
        // 핫스팟 군집 섹션.
        // 🔴 키를 접두사 없이 top_percent 등으로 두면 다른 섹션 키와 겹쳐
        //    읽기 어렵고, 문서 전체를 훑는 정규식 소비자와도 충돌한다.
        //    값이 실제로 도달했음을 verbose 로 남겨 '설정이 조용히 무시됨' 을 막는다.
        else if (current_section == "hotspot_clusters") {
            if (key == "enabled") {
                config.hotspot_enabled = parseBool(value);
            } else if (key == "top_percent") {
                try { config.hotspot_top_percent = std::stod(value); } catch (...) {}
            } else if (key == "distance_factor") {
                try { config.hotspot_distance_factor = std::stod(value); } catch (...) {}
            } else if (key == "min_elements") {
                try { config.hotspot_min_elements = std::stoi(value); } catch (...) {}
            } else if (key == "max_clusters") {
                try { config.hotspot_max_clusters = std::stoi(value); } catch (...) {}
            } else if (key == "criterion" || key == "criteria") {
                // 쉼표 목록. "von_mises, max_principal" / "[von_mises, min_principal]" 둘 다 허용.
                // 이름 검증은 분석기(resolveHotspotCriteria)가 한다 — 여기서는 나누기만.
                std::vector<std::string> names;
                std::string cur;
                for (char ch : value) {
                    if (ch == '[' || ch == ']' || ch == '"' || ch == '\'') continue;
                    if (ch == ',') { names.push_back(cur); cur.clear(); continue; }
                    cur.push_back(ch);
                }
                names.push_back(cur);
                std::vector<std::string> cleaned;
                for (std::string& n : names) {
                    const size_t a = n.find_first_not_of(" \t");
                    const size_t b = n.find_last_not_of(" \t");
                    if (a == std::string::npos) continue;
                    cleaned.push_back(n.substr(a, b - a + 1));
                }
                if (!cleaned.empty()) config.hotspot_criteria = cleaned;
            } else if (key == "time_aggregate") {
                // 모르는 값은 조용히 기본으로 떨어뜨리지 않는다 — 사용자가 지정한
                // 방식이 무시되면 과대평가 쪽 값을 보고 맞다고 여기게 된다.
                if (value == "elemmax_then_mean" || value == "mean_then_timemax" ||
                    value == "both") {
                    config.hotspot_time_aggregate = value;
                } else {
                    std::cerr << "[UnifiedConfig] hotspot_clusters.time_aggregate: "
                              << "알 수 없는 값 '" << value << "' — "
                              << "elemmax_then_mean | mean_then_timemax | both 중 하나여야 합니다. "
                              << "기본값(elemmax_then_mean)을 씁니다." << std::endl;
                }
            } else {
                std::cerr << "[UnifiedConfig] hotspot_clusters: 알 수 없는 키 무시 — "
                          << key << std::endl;
            }
        }
        // Parse performance section
        else if (current_section == "performance") {
            if (key == "threads") {
                try { config.num_threads = std::stoi(value); } catch (...) {}
            } else if (key == "render_threads") {
                try { config.render_threads = std::stoi(value); } catch (...) {}
            } else if (key == "sv_threads") {
                try { config.sv_threads = std::stoi(value); } catch (...) {}
            } else if (key == "verbose") {
                config.verbose = parseBool(value);
            } else if (key == "cache_geometry") {
                config.cache_geometry = parseBool(value);
            } else if (key == "surface_defaults") {
                config.surface_defaults = parseBool(value);
            } else if (key == "surface_default_angle") {
                try { config.surface_default_angle = std::stod(value); } catch (...) {}
            } else if (key == "lsprepost_path" || key == "lsprepost") {
                config.lsprepost_path = value;
            }
        }
    }

    // Flush remaining jobs
    if (in_analysis_jobs) flush_analysis_job();
    if (in_render_jobs) flush_render_job();
if (in_set_reports) flush_sr();
        if (in_section_views) flush_sv();
    if (in_part_section_renders) flush_psr();

    return true;
}

bool UnifiedConfigParser::saveToYAML(const std::string& file_path, const UnifiedConfig& config) {
    std::ofstream ofs(file_path);
    if (!ofs.is_open()) {
        last_error_ = "Cannot open file for writing: " + file_path;
        return false;
    }

    ofs << "# KooD3plot Unified Configuration\n";
    ofs << "# Generated automatically\n\n";
    ofs << "version: \"" << config.version << "\"\n\n";

    // Input section
    ofs << "input:\n";
    ofs << "  d3plot: \"" << config.d3plot_path << "\"\n\n";

    // Output section
    ofs << "output:\n";
    ofs << "  directory: \"" << config.output_directory << "\"\n";
    ofs << "  json: " << (config.output_json ? "true" : "false") << "\n";
    ofs << "  csv: " << (config.output_csv ? "true" : "false") << "\n\n";

    // Performance section
    ofs << "performance:\n";
    ofs << "  threads: " << config.num_threads << "\n";
    ofs << "  render_threads: " << config.render_threads << "\n";
    ofs << "  sv_threads: " << config.sv_threads << "\n";
    ofs << "  verbose: " << (config.verbose ? "true" : "false") << "\n";
    ofs << "  cache_geometry: " << (config.cache_geometry ? "true" : "false") << "\n";
    ofs << "  surface_defaults: " << (config.surface_defaults ? "true" : "false") << "\n";
    ofs << "  surface_default_angle: " << config.surface_default_angle << "\n";
    if (!config.lsprepost_path.empty()) {
        ofs << "  lsprepost_path: \"" << config.lsprepost_path << "\"\n";
    }
    ofs << "\n";

    // Analysis jobs
    if (!config.analysis_jobs.empty()) {
        ofs << "analysis_jobs:\n";
        for (const auto& job : config.analysis_jobs) {
            ofs << "  - name: \"" << job.name << "\"\n";
            ofs << "    type: " << jobTypeToString(job.type) << "\n";
            ofs << "    parts: [";
            for (size_t i = 0; i < job.part_ids.size(); ++i) {
                if (i > 0) ofs << ", ";
                ofs << job.part_ids[i];
            }
            ofs << "]\n";

            if (job.type == AnalysisJobType::SURFACE_STRESS || job.type == AnalysisJobType::SURFACE_STRAIN) {
                ofs << "    surface:\n";
                ofs << "      direction: [" << job.surface.direction.x << ", "
                    << job.surface.direction.y << ", " << job.surface.direction.z << "]\n";
                ofs << "      angle: " << job.surface.angle << "\n";
            }

            if (!job.quantities.empty()) {
                ofs << "    quantities:\n";
                for (const auto& q : job.quantities) {
                    ofs << "      - " << q << "\n";
                }
            }

            ofs << "    output_prefix: \"" << job.output_prefix << "\"\n\n";
        }
    }

    // Render jobs
    if (!config.render_jobs.empty()) {
        ofs << "render_jobs:\n";
        for (const auto& job : config.render_jobs) {
            ofs << "  - name: \"" << job.name << "\"\n";

            std::string type_str;
            switch (job.type) {
                case RenderJobType::SECTION_VIEW: type_str = "section_view"; break;
                case RenderJobType::MULTI_SECTION: type_str = "multi_section"; break;
                case RenderJobType::PART_VIEW: type_str = "part_view"; break;
                case RenderJobType::FULL_MODEL: type_str = "full_model"; break;
                default: type_str = "section_view";
            }
            ofs << "    type: " << type_str << "\n";
            ofs << "    fringe: " << job.fringe_type << "\n";

            if (!job.sections.empty()) {
                ofs << "    section:\n";
                const auto& sec = job.sections[0];
                ofs << "      axis: " << sec.axis << "\n";
                if (!sec.position_auto.empty()) {
                    ofs << "      position: " << sec.position_auto << "\n";
                } else {
                    ofs << "      position: " << sec.position << "\n";
                }
            }

            if (job.states.empty()) {
                ofs << "    states: all\n";
            } else {
                ofs << "    states: [";
                for (size_t i = 0; i < job.states.size(); ++i) {
                    if (i > 0) ofs << ", ";
                    ofs << job.states[i];
                }
                ofs << "]\n";
            }

            ofs << "    output:\n";
            std::string format_str;
            switch (job.output.format) {
                case RenderOutputFormat::MP4: format_str = "mp4"; break;
                case RenderOutputFormat::PNG: format_str = "png"; break;
                case RenderOutputFormat::JPG: format_str = "jpg"; break;
                case RenderOutputFormat::GIF: format_str = "gif"; break;
            }
            ofs << "      format: " << format_str << "\n";
            ofs << "      filename: \"" << job.output.filename << "\"\n";
            ofs << "      fps: " << job.output.fps << "\n";
            ofs << "      resolution: [" << job.output.resolution[0] << ", " << job.output.resolution[1] << "]\n\n";
        }
    }

    // Section view jobs
    if (!config.section_views.empty()) {
        ofs << "section_views:\n";
        for (const auto& sv : config.section_views) {
            ofs << "  - name: \"" << sv.name << "\"\n";
            if (!sv.enabled) ofs << "    enabled: false\n";
            // Write the yaml_block lines indented by 4 spaces
            std::istringstream iss(sv.yaml_block);
            std::string ln;
            while (std::getline(iss, ln)) {
                if (!ln.empty()) ofs << "    " << ln << "\n";
            }
            ofs << "\n";
        }
    }

    return true;
}

std::string UnifiedConfigParser::generateExampleYAML() {
    std::ostringstream oss;

    oss << "# ============================================================\n";
    oss << "# KooD3plot Unified Configuration (v2.0)\n";
    oss << "# ============================================================\n";
    oss << "# This file configures both analysis and rendering jobs.\n";
    oss << "# Run with: ./unified_analyzer --config config.yaml\n";
    oss << "# ============================================================\n\n";

    oss << "version: \"2.0\"\n\n";

    oss << "# Input file settings\n";
    oss << "input:\n";
    oss << "  d3plot: \"results/d3plot\"\n\n";

    oss << "# Output settings\n";
    oss << "output:\n";
    oss << "  directory: \"./analysis_output\"\n";
    oss << "  json: true\n";
    oss << "  csv: true\n\n";

    oss << "# Performance settings\n";
    oss << "performance:\n";
    oss << "  threads: 0           # 0 = auto (use all cores for analysis/read)\n";
    oss << "  render_threads: 1    # Parallel LSPrePost instances (default 1)\n";
    oss << "  sv_threads: 2        # Parallel section view renderers (default 2)\n";
    oss << "  verbose: true\n";
    oss << "  cache_geometry: true\n";
    oss << "  # surface_stress/surface_strain 잡을 하나도 안 적으면 +Z/-Z 두 방향을\n";
    oss << "  # 자동으로 분석한다 (낙하 바닥면/상면). 필요 없으면 false.\n";
    oss << "  surface_defaults: true\n";
    oss << "  surface_default_angle: 45.0   # 기준 벡터로부터 허용 각도(deg)\n";
    oss << "  # lsprepost_path: \"/path/to/lsprepost\"  # Optional: custom LSPrePost path\n";
    oss << "  # Linux default: {exe_dir}/../lsprepost/lsprepost\n";
    oss << "  # Windows default: {exe_dir}/../lsprepost/lspp412_win64.exe\n\n";

    oss << "# ============================================================\n";
    oss << "# Analysis Jobs (C++ SinglePassAnalyzer)\n";
    oss << "# ============================================================\n";
    oss << "analysis_jobs:\n";
    oss << "  # Von Mises stress analysis\n";
    oss << "  - name: \"All Parts Stress\"\n";
    oss << "    type: von_mises\n";
    oss << "    parts: []  # empty = all parts\n";
    oss << "    output_prefix: \"stress\"\n\n";

    oss << "  # Effective plastic strain\n";
    oss << "  - name: \"Critical Parts Strain\"\n";
    oss << "    type: eff_plastic_strain\n";
    oss << "    parts: [1, 2, 3]\n";
    oss << "    output_prefix: \"strain\"\n\n";

    oss << "  # Motion analysis (velocity/acceleration)\n";
    oss << "  - name: \"Part Motion\"\n";
    oss << "    type: part_motion\n";
    oss << "    parts: [100, 101]\n";
    oss << "    quantities:\n";
    oss << "      - avg_displacement\n";
    oss << "      - avg_velocity\n";
    oss << "      - avg_acceleration\n";
    oss << "    output_prefix: \"motion\"\n\n";

    oss << "  # Beam resultants (axial force / shear / moment / torsion)\n";
    oss << "  # 볼트·리벳 대체 빔의 축력 판정용. NV1D >= 6 인 덱에서만 나온다.\n";
    oss << "  - name: \"Beam Forces\"\n";
    oss << "    type: beam_force\n";
    oss << "    parts: []\n";
    oss << "    output_prefix: \"beam\"\n\n";

    oss << "  # ---- Custom Report: 세트 후처리 ----\n";
    oss << "  # LS-DYNA *SET_PART/NODE/SEGMENT 정의를 참조해 그 세트만의\n";
    oss << "  # 피크 지표(응력/변형률)와 세트-격리 뷰를 만든다.\n";
    oss << "  # 최상위 sets: 블록으로 세트 파일을 지정한다 (생략 시 자동 탐색).\n";
    oss << "  # sets:\n";
    oss << "  #   file: \"sets.k\"\n";
    oss << "  # set_reports:\n";
    oss << "  #   - name: \"PKG 모듈\"\n";
    oss << "  #     set_type: part          # part | node | segment\n";
    oss << "  #     set_id: 5\n";
    oss << "  #     fields: [von_mises, eff_plastic_strain]\n";
    oss << "  #     planes: [xy, yz, zx]    # 반드시 인라인 리스트\n";
    oss << "  #     video: true\n";
    oss << "  #     peak_snapshot: true\n\n";

    oss << "  # Surface stress analysis\n";
    oss << "  - name: \"Bottom Surface Stress\"\n";
    oss << "    type: surface_stress\n";
    oss << "    parts: []\n";
    oss << "    surface:\n";
    oss << "      direction: [0, 0, -1]\n";
    oss << "      angle: 45.0\n";
    oss << "    output_prefix: \"bottom_surface\"\n\n";

    oss << "  # Surface strain analysis\n";
    oss << "  - name: \"Top Surface Strain\"\n";
    oss << "    type: surface_strain\n";
    oss << "    parts: []\n";
    oss << "    surface:\n";
    oss << "      direction: [0, 0, 1]\n";
    oss << "      angle: 45.0\n";
    oss << "    output_prefix: \"top_strain\"\n\n";

    oss << "  # Element quality analysis (track mesh degradation over time)\n";
    oss << "  - name: \"Element Quality\"\n";
    oss << "    type: element_quality\n";
    oss << "    parts: []  # empty = all parts\n";
    oss << "    output_prefix: \"quality\"\n\n";

    oss << "  # Comprehensive analysis (multiple quantities)\n";
    oss << "  - name: \"Full Part Analysis\"\n";
    oss << "    type: comprehensive\n";
    oss << "    parts: [10]\n";
    oss << "    quantities:\n";
    oss << "      - von_mises\n";
    oss << "      - eff_plastic_strain\n";
    oss << "      - avg_velocity\n";
    oss << "    output_prefix: \"part10_full\"\n\n";

    oss << "# ============================================================\n";
    oss << "# Render Jobs (LSPrePost Backend)\n";
    oss << "# ============================================================\n";
    oss << "render_jobs:\n";
    oss << "  # Section view animation\n";
    oss << "  - name: \"Z-Section Animation\"\n";
    oss << "    type: section_view\n";
    oss << "    fringe: von_mises\n";
    oss << "    section:\n";
    oss << "      axis: z\n";
    oss << "      position: center\n";
    oss << "    states: all\n";
    oss << "    output:\n";
    oss << "      format: mp4\n";
    oss << "      filename: \"section_vonmises.mp4\"\n";
    oss << "      fps: 30\n";
    oss << "      resolution: [1920, 1080]\n\n";

    oss << "  # Final state snapshot\n";
    oss << "  - name: \"Final State\"\n";
    oss << "    type: section_view\n";
    oss << "    fringe: eff_plastic_strain\n";
    oss << "    section:\n";
    oss << "      axis: z\n";
    oss << "      position: center\n";
    oss << "    states: [-1]  # -1 = last state\n";
    oss << "    output:\n";
    oss << "      format: png\n";
    oss << "      filename: \"final_strain.png\"\n";

    oss << "\n";
    oss << "# ============================================================\n";
    oss << "# Section View Jobs (Software-Rasterized, VTK-free)\n";
    oss << "# ============================================================\n";
    oss << "section_views:\n";
    oss << "  - name: \"Z-Section Contour\"\n";
    oss << "    view_mode: section           # section (2D) | section_3d (3D half-model)\n";
    oss << "    plane:\n";
    oss << "      axis: z\n";
    oss << "      point: [0.0, 0.0, 0.0]\n";
    oss << "    target_parts:\n";
    oss << "      ids: [1, 2, 3]\n";
    oss << "    background_parts:\n";
    oss << "      patterns: [\"*\"]\n";
    oss << "    field: von_mises\n";
    oss << "    colormap: rainbow\n";
    oss << "    global_range: false\n";
    oss << "    scale_factor: 1.2\n";
    oss << "    supersampling: 2\n";
    oss << "    output:\n";
    oss << "      width: 1920\n";
    oss << "      height: 1080\n";
    oss << "      png_frames: true\n";
    oss << "      mp4: true\n";
    oss << "      fps: 24\n";
    oss << "      output_dir: \"section_views\"\n";

    return oss.str();
}

std::string UnifiedConfigParser::generateMinimalYAML(const std::string& d3plot_path) {
    std::ostringstream oss;

    oss << "# KooD3plot Minimal Configuration\n";
    oss << "version: \"2.0\"\n\n";

    oss << "input:\n";
    oss << "  d3plot: \"" << d3plot_path << "\"\n\n";

    oss << "output:\n";
    oss << "  directory: \"./analysis_output\"\n";
    oss << "  json: true\n";
    oss << "  csv: true\n\n";

    oss << "analysis_jobs:\n";
    oss << "  - name: \"All Parts Stress\"\n";
    oss << "    type: von_mises\n";
    oss << "    parts: []\n";
    oss << "    output_prefix: \"stress\"\n";

    return oss.str();
}

const std::string& UnifiedConfigParser::getLastError() {
    return last_error_;
}

bool UnifiedConfigParser::validate(const UnifiedConfig& config) {
    if (config.d3plot_path.empty()) {
        last_error_ = "d3plot path is required";
        return false;
    }

    if (config.analysis_jobs.empty() && config.render_jobs.empty() && config.section_views.empty() && config.set_reports.empty()) {
        last_error_ = "At least one analysis_job, render_job, section_view, or set_report is required";
        return false;
    }

    // set_reports 이름이 sanitize 후 같은 폴더로 합쳐지면 키메라 산출물 —
    // 무음 덮어쓰기 대신 명확히 거부한다
    {
        std::map<std::string, std::string> seen_safe;
        for (const auto& sr : config.set_reports) {
            const std::string safe = sanitizeSetName(sr.name);
            auto it = seen_safe.find(safe);
            if (it != seen_safe.end()) {
                last_error_ = "set_reports 이름 충돌: '" + it->second + "' 와 '" + sr.name +
                              "' 이 같은 산출 폴더(" + safe + ")로 정리됨 — 이름을 바꾸세요";
                return false;
            }
            seen_safe[safe] = sr.name;
        }
    }

    // Validate analysis jobs
    for (const auto& job : config.analysis_jobs) {
        if (job.name.empty()) {
            last_error_ = "Analysis job name is required";
            return false;
        }
    }

    // Validate render jobs
    for (const auto& job : config.render_jobs) {
        if (job.name.empty()) {
            last_error_ = "Render job name is required";
            return false;
        }
    }

    return true;
}

// ============================================================
// Pattern Matching Utility Functions
// ============================================================

bool UnifiedConfigParser::matchPattern(const std::string& name, const std::string& pattern) {
    if (pattern.empty()) return true;  // Empty pattern matches all

    // Simple wildcard matching: * matches any sequence, ? matches single char
    size_t n = name.size();
    size_t p = pattern.size();

    std::vector<std::vector<bool>> dp(n + 1, std::vector<bool>(p + 1, false));
    dp[0][0] = true;

    // Handle patterns starting with *
    for (size_t j = 1; j <= p; ++j) {
        if (pattern[j - 1] == '*') {
            dp[0][j] = dp[0][j - 1];
        }
    }

    for (size_t i = 1; i <= n; ++i) {
        for (size_t j = 1; j <= p; ++j) {
            if (pattern[j - 1] == '*') {
                dp[i][j] = dp[i][j - 1] || dp[i - 1][j];
            } else if (pattern[j - 1] == '?' ||
                       std::toupper(pattern[j - 1]) == std::toupper(name[i - 1])) {
                dp[i][j] = dp[i - 1][j - 1];
            }
        }
    }

    return dp[n][p];
}

std::vector<int32_t> UnifiedConfigParser::filterPartsByPattern(
    const D3plotReader& reader,
    const std::string& pattern) {

    std::vector<int32_t> matching_parts;

    if (pattern.empty()) {
        return matching_parts;  // Empty = no filter (caller should use all parts)
    }

    // Check if pattern looks like a part ID (numeric: "1,2,3" or "10-20")
    bool is_numeric = true;
    for (char c : pattern) {
        if (!std::isdigit(c) && c != '-' && c != ',' && c != ' ') {
            is_numeric = false;
            break;
        }
    }

    if (is_numeric) {
        // Parse as part ID range (e.g., "1,2,3" or "10-20")
        matching_parts = parseIntArray("[" + pattern + "]");
        return matching_parts;
    }

    // Pattern contains wildcards - try to load part names from keyword file
    std::string d3plot_path = reader.getFilePath();

    // Check cache first
    if (g_part_name_cache.find(d3plot_path) == g_part_name_cache.end()) {
        // 후보 덱을 우선순위대로 훑어 **이름이 나오는 첫 덱**을 쓴다.
        // (*INCLUDE 는 parsePartNamesInto 가 따라 들어간다)
        const auto candidates = collectKeywordCandidates(d3plot_path);
        const std::filesystem::path root_dir =
            std::filesystem::path(d3plot_path).parent_path();

        std::unordered_map<int32_t, std::string> names;
        std::string used;
        size_t missing_includes = 0;
        for (const auto& cand : candidates) {
            std::set<std::string> visited;
            size_t missing = 0;
            std::unordered_map<int32_t, std::string> found;
            parsePartNamesInto(cand, found, visited, root_dir, 0, missing);
            if (!found.empty()) {
                names = std::move(found);
                used = cand;
                missing_includes = missing;
                break;
            }
        }

        g_part_name_cache[d3plot_path] = names;
        if (!used.empty()) {
            std::cerr << "[UnifiedConfigParser] Loaded part names from: " << used
                      << " (파트 " << names.size() << "개";
            if (missing_includes > 0) {
                std::cerr << ", 못 연 *INCLUDE " << missing_includes << "건";
            }
            std::cerr << ")" << std::endl;
        } else {
            std::cerr << "[UnifiedConfigParser] 파트 이름을 가진 키워드 파일을 찾지 못함 ("
                      << candidates.size() << "개 후보 확인). "
                      << "Using fallback Part_N names." << std::endl;
        }
    }

    const auto& part_names = g_part_name_cache[d3plot_path];

    // Get all part IDs from mesh
    D3plotReader& mutable_reader = const_cast<D3plotReader&>(reader);
    auto mesh = mutable_reader.read_mesh();

    // Collect unique part IDs
    std::set<int32_t> all_part_ids;
    for (int32_t pid : mesh.solid_parts) all_part_ids.insert(pid);
    for (int32_t pid : mesh.shell_parts) all_part_ids.insert(pid);
    for (int32_t pid : mesh.beam_parts) all_part_ids.insert(pid);
    for (int32_t pid : mesh.thick_shell_parts) all_part_ids.insert(pid);

    // Match each part against pattern
    for (int32_t pid : all_part_ids) {
        std::string name;

        // Try to get name from keyword file
        auto it = part_names.find(pid);
        if (it != part_names.end()) {
            name = it->second;
        } else {
            // Fallback: use Part_N format
            name = "Part_" + std::to_string(pid);
        }

        if (matchPattern(name, pattern)) {
            matching_parts.push_back(pid);
        }
    }

    return matching_parts;
}

} // namespace analysis
} // namespace kood3plot
