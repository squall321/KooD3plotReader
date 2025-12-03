/**
 * @file ConfigParser.cpp
 * @brief Implementation of ConfigParser class
 * @author KooD3plot V3 Development Team
 * @date 2025-11-22
 * @version 3.0.0
 */

#include "kood3plot/query/ConfigParser.h"
#include "kood3plot/query/PartSelector.h"
#include "kood3plot/query/QuantitySelector.h"
#include "kood3plot/query/TimeSelector.h"
#include "kood3plot/query/ValueFilter.h"
#include "kood3plot/query/OutputSpec.h"
#include "kood3plot/query/SpatialSelector.h"

#include <fstream>
#include <sstream>
#include <algorithm>
#include <cctype>
#include <stdexcept>
#include <cstdlib>

namespace kood3plot {
namespace query {

// ============================================================
// ConfigNode Implementation
// ============================================================

struct ConfigNode::Impl {
    enum class Type { Null, Scalar, Array, Map };
    Type type = Type::Null;

    ConfigValue scalar_value;
    std::vector<ConfigNode> array_values;
    std::map<std::string, ConfigNode> map_values;
};

ConfigNode::ConfigNode() : pImpl(std::make_unique<Impl>()) {}
ConfigNode::~ConfigNode() = default;
ConfigNode::ConfigNode(const ConfigNode& other) : pImpl(std::make_unique<Impl>(*other.pImpl)) {}
ConfigNode::ConfigNode(ConfigNode&& other) noexcept = default;
ConfigNode& ConfigNode::operator=(const ConfigNode& other) {
    if (this != &other) {
        pImpl = std::make_unique<Impl>(*other.pImpl);
    }
    return *this;
}
ConfigNode& ConfigNode::operator=(ConfigNode&& other) noexcept = default;

bool ConfigNode::isNull() const { return pImpl->type == Impl::Type::Null; }
bool ConfigNode::isScalar() const { return pImpl->type == Impl::Type::Scalar; }
bool ConfigNode::isArray() const { return pImpl->type == Impl::Type::Array; }
bool ConfigNode::isMap() const { return pImpl->type == Impl::Type::Map; }

bool ConfigNode::asBool(bool default_val) const {
    if (!isScalar()) return default_val;
    if (std::holds_alternative<bool>(pImpl->scalar_value)) {
        return std::get<bool>(pImpl->scalar_value);
    }
    if (std::holds_alternative<std::string>(pImpl->scalar_value)) {
        std::string s = std::get<std::string>(pImpl->scalar_value);
        std::transform(s.begin(), s.end(), s.begin(), ::tolower);
        return s == "true" || s == "yes" || s == "1";
    }
    return default_val;
}

int64_t ConfigNode::asInt(int64_t default_val) const {
    if (!isScalar()) return default_val;
    if (std::holds_alternative<int64_t>(pImpl->scalar_value)) {
        return std::get<int64_t>(pImpl->scalar_value);
    }
    if (std::holds_alternative<double>(pImpl->scalar_value)) {
        return static_cast<int64_t>(std::get<double>(pImpl->scalar_value));
    }
    if (std::holds_alternative<std::string>(pImpl->scalar_value)) {
        try {
            return std::stoll(std::get<std::string>(pImpl->scalar_value));
        } catch (...) {
            return default_val;
        }
    }
    return default_val;
}

double ConfigNode::asDouble(double default_val) const {
    if (!isScalar()) return default_val;
    if (std::holds_alternative<double>(pImpl->scalar_value)) {
        return std::get<double>(pImpl->scalar_value);
    }
    if (std::holds_alternative<int64_t>(pImpl->scalar_value)) {
        return static_cast<double>(std::get<int64_t>(pImpl->scalar_value));
    }
    if (std::holds_alternative<std::string>(pImpl->scalar_value)) {
        try {
            return std::stod(std::get<std::string>(pImpl->scalar_value));
        } catch (...) {
            return default_val;
        }
    }
    return default_val;
}

std::string ConfigNode::asString(const std::string& default_val) const {
    if (!isScalar()) return default_val;
    if (std::holds_alternative<std::string>(pImpl->scalar_value)) {
        return std::get<std::string>(pImpl->scalar_value);
    }
    if (std::holds_alternative<int64_t>(pImpl->scalar_value)) {
        return std::to_string(std::get<int64_t>(pImpl->scalar_value));
    }
    if (std::holds_alternative<double>(pImpl->scalar_value)) {
        return std::to_string(std::get<double>(pImpl->scalar_value));
    }
    if (std::holds_alternative<bool>(pImpl->scalar_value)) {
        return std::get<bool>(pImpl->scalar_value) ? "true" : "false";
    }
    return default_val;
}

std::vector<std::string> ConfigNode::asStringArray() const {
    std::vector<std::string> result;
    if (isArray()) {
        for (const auto& child : pImpl->array_values) {
            result.push_back(child.asString());
        }
    } else if (isScalar()) {
        result.push_back(asString());
    }
    return result;
}

std::vector<double> ConfigNode::asDoubleArray() const {
    std::vector<double> result;
    if (isArray()) {
        for (const auto& child : pImpl->array_values) {
            result.push_back(child.asDouble());
        }
    } else if (isScalar()) {
        result.push_back(asDouble());
    }
    return result;
}

std::vector<int64_t> ConfigNode::asIntArray() const {
    std::vector<int64_t> result;
    if (isArray()) {
        for (const auto& child : pImpl->array_values) {
            result.push_back(child.asInt());
        }
    } else if (isScalar()) {
        result.push_back(asInt());
    }
    return result;
}

bool ConfigNode::hasKey(const std::string& key) const {
    if (!isMap()) return false;
    return pImpl->map_values.find(key) != pImpl->map_values.end();
}

ConfigNode ConfigNode::operator[](const std::string& key) const {
    if (!isMap()) return ConfigNode();
    auto it = pImpl->map_values.find(key);
    if (it != pImpl->map_values.end()) {
        return it->second;
    }
    return ConfigNode();
}

ConfigNode ConfigNode::operator[](size_t index) const {
    if (!isArray() || index >= pImpl->array_values.size()) {
        return ConfigNode();
    }
    return pImpl->array_values[index];
}

std::vector<std::string> ConfigNode::keys() const {
    std::vector<std::string> result;
    if (isMap()) {
        for (const auto& [k, v] : pImpl->map_values) {
            result.push_back(k);
        }
    }
    return result;
}

size_t ConfigNode::size() const {
    if (isArray()) return pImpl->array_values.size();
    if (isMap()) return pImpl->map_values.size();
    return 0;
}

void ConfigNode::setValue(const ConfigValue& val) {
    pImpl->type = Impl::Type::Scalar;
    pImpl->scalar_value = val;
}

void ConfigNode::setChild(const std::string& key, const ConfigNode& child) {
    pImpl->type = Impl::Type::Map;
    pImpl->map_values[key] = child;
}

void ConfigNode::appendChild(const ConfigNode& child) {
    pImpl->type = Impl::Type::Array;
    pImpl->array_values.push_back(child);
}

// ============================================================
// ConfigParser Implementation
// ============================================================

struct ConfigParser::Impl {
    std::string last_error;
    bool valid = true;
    std::vector<std::string> warnings;

    // Simple YAML parser (handles basic cases)
    ConfigNode parseYAMLContent(const std::string& content);

    // Simple JSON parser (handles basic cases)
    ConfigNode parseJSONContent(const std::string& content);

    // Helper functions
    std::string trim(const std::string& s);
    std::string unquote(const std::string& s);
    int getIndent(const std::string& line);
};

std::string ConfigParser::Impl::trim(const std::string& s) {
    size_t start = s.find_first_not_of(" \t\r\n");
    if (start == std::string::npos) return "";
    size_t end = s.find_last_not_of(" \t\r\n");
    return s.substr(start, end - start + 1);
}

std::string ConfigParser::Impl::unquote(const std::string& s) {
    if (s.size() >= 2 && ((s.front() == '"' && s.back() == '"') ||
                          (s.front() == '\'' && s.back() == '\''))) {
        return s.substr(1, s.size() - 2);
    }
    return s;
}

int ConfigParser::Impl::getIndent(const std::string& line) {
    int indent = 0;
    for (char c : line) {
        if (c == ' ') indent++;
        else if (c == '\t') indent += 2;
        else break;
    }
    return indent;
}

ConfigNode ConfigParser::Impl::parseYAMLContent(const std::string& content) {
    ConfigNode root;
    std::istringstream iss(content);
    std::string line;
    std::vector<std::pair<int, ConfigNode*>> stack;
    stack.push_back({-1, &root});

    while (std::getline(iss, line)) {
        // Skip empty lines and comments
        std::string trimmed = trim(line);
        if (trimmed.empty() || trimmed[0] == '#') continue;

        int indent = getIndent(line);

        // Pop stack to correct level
        while (stack.size() > 1 && indent <= stack.back().first) {
            stack.pop_back();
        }

        // Check for array item
        if (trimmed[0] == '-') {
            std::string value = trim(trimmed.substr(1));
            ConfigNode item;
            item.setValue(unquote(value));
            stack.back().second->appendChild(item);
        }
        // Check for key: value
        else {
            size_t colonPos = trimmed.find(':');
            if (colonPos != std::string::npos) {
                std::string key = trim(trimmed.substr(0, colonPos));
                std::string value = trim(trimmed.substr(colonPos + 1));

                ConfigNode child;
                if (!value.empty()) {
                    // Scalar value
                    child.setValue(unquote(value));
                }
                // else it's a map or array (will be filled by children)

                stack.back().second->setChild(key, child);

                // If no value, this might be a parent node
                if (value.empty()) {
                    // We need to reference the child we just added
                    // This is a bit tricky with our current structure
                }
            }
        }
    }

    return root;
}

ConfigNode ConfigParser::Impl::parseJSONContent(const std::string& content) {
    ConfigNode root;
    size_t pos = 0;

    // Skip whitespace
    auto skipWS = [&]() {
        while (pos < content.size() && std::isspace(content[pos])) pos++;
    };

    // Forward declarations for recursive parsing
    std::function<ConfigNode()> parseValue;
    std::function<ConfigNode()> parseObject;
    std::function<ConfigNode()> parseArray;
    std::function<std::string()> parseString;

    parseString = [&]() -> std::string {
        if (content[pos] != '"') return "";
        pos++;  // skip opening quote
        std::string result;
        while (pos < content.size() && content[pos] != '"') {
            if (content[pos] == '\\' && pos + 1 < content.size()) {
                pos++;
                switch (content[pos]) {
                    case 'n': result += '\n'; break;
                    case 't': result += '\t'; break;
                    case 'r': result += '\r'; break;
                    default: result += content[pos]; break;
                }
            } else {
                result += content[pos];
            }
            pos++;
        }
        if (pos < content.size()) pos++;  // skip closing quote
        return result;
    };

    parseObject = [&]() -> ConfigNode {
        ConfigNode node;
        if (content[pos] != '{') return node;
        pos++;  // skip '{'

        skipWS();
        while (pos < content.size() && content[pos] != '}') {
            skipWS();
            std::string key = parseString();
            skipWS();
            if (pos < content.size() && content[pos] == ':') pos++;
            skipWS();
            ConfigNode value = parseValue();
            node.setChild(key, value);
            skipWS();
            if (pos < content.size() && content[pos] == ',') pos++;
            skipWS();
        }
        if (pos < content.size()) pos++;  // skip '}'
        return node;
    };

    parseArray = [&]() -> ConfigNode {
        ConfigNode node;
        if (content[pos] != '[') return node;
        pos++;  // skip '['

        skipWS();
        while (pos < content.size() && content[pos] != ']') {
            skipWS();
            ConfigNode value = parseValue();
            node.appendChild(value);
            skipWS();
            if (pos < content.size() && content[pos] == ',') pos++;
            skipWS();
        }
        if (pos < content.size()) pos++;  // skip ']'
        return node;
    };

    parseValue = [&]() -> ConfigNode {
        skipWS();
        ConfigNode node;

        if (pos >= content.size()) return node;

        if (content[pos] == '{') {
            return parseObject();
        } else if (content[pos] == '[') {
            return parseArray();
        } else if (content[pos] == '"') {
            std::string s = parseString();
            node.setValue(s);
        } else if (content[pos] == 't' || content[pos] == 'f') {
            // boolean
            if (content.substr(pos, 4) == "true") {
                node.setValue(true);
                pos += 4;
            } else if (content.substr(pos, 5) == "false") {
                node.setValue(false);
                pos += 5;
            }
        } else if (content[pos] == 'n') {
            // null
            if (content.substr(pos, 4) == "null") {
                pos += 4;
            }
        } else if (std::isdigit(content[pos]) || content[pos] == '-') {
            // number
            size_t start = pos;
            bool isDouble = false;
            if (content[pos] == '-') pos++;
            while (pos < content.size() && (std::isdigit(content[pos]) || content[pos] == '.' || content[pos] == 'e' || content[pos] == 'E')) {
                if (content[pos] == '.' || content[pos] == 'e' || content[pos] == 'E') isDouble = true;
                pos++;
            }
            std::string numStr = content.substr(start, pos - start);
            if (isDouble) {
                node.setValue(std::stod(numStr));
            } else {
                node.setValue(static_cast<int64_t>(std::stoll(numStr)));
            }
        }

        return node;
    };

    skipWS();
    root = parseValue();
    return root;
}

ConfigParser::ConfigParser() : pImpl(std::make_unique<Impl>()) {}
ConfigParser::~ConfigParser() = default;

QueryConfig ConfigParser::parseYAML(const std::string& filepath) {
    std::ifstream file(filepath);
    if (!file.is_open()) {
        pImpl->last_error = "Cannot open file: " + filepath;
        pImpl->valid = false;
        return QueryConfig{};
    }

    std::stringstream buffer;
    buffer << file.rdbuf();
    return parseYAMLString(buffer.str());
}

QueryConfig ConfigParser::parseJSON(const std::string& filepath) {
    std::ifstream file(filepath);
    if (!file.is_open()) {
        pImpl->last_error = "Cannot open file: " + filepath;
        pImpl->valid = false;
        return QueryConfig{};
    }

    std::stringstream buffer;
    buffer << file.rdbuf();
    return parseJSONString(buffer.str());
}

QueryConfig ConfigParser::parseYAMLString(const std::string& yaml_content) {
    pImpl->valid = true;
    pImpl->warnings.clear();

    ConfigNode root = pImpl->parseYAMLContent(yaml_content);
    return parseNode(root);
}

QueryConfig ConfigParser::parseJSONString(const std::string& json_content) {
    pImpl->valid = true;
    pImpl->warnings.clear();

    ConfigNode root = pImpl->parseJSONContent(json_content);
    return parseNode(root);
}

QueryConfig ConfigParser::parse(const std::string& filepath) {
    // Auto-detect format from extension
    size_t dotPos = filepath.rfind('.');
    if (dotPos != std::string::npos) {
        std::string ext = filepath.substr(dotPos + 1);
        std::transform(ext.begin(), ext.end(), ext.begin(), ::tolower);
        if (ext == "json") {
            return parseJSON(filepath);
        } else if (ext == "yaml" || ext == "yml") {
            return parseYAML(filepath);
        }
    }

    // Default to YAML
    return parseYAML(filepath);
}

QueryConfig ConfigParser::parseNode(const ConfigNode& root) {
    QueryConfig config;

    // Parse d3plot path
    if (root.hasKey("d3plot")) {
        config.d3plot_path = root["d3plot"].asString();
    } else if (root.hasKey("file")) {
        config.d3plot_path = root["file"].asString();
    }

    // Parse parts
    if (root.hasKey("parts")) {
        config.parts = root["parts"].asStringArray();
    }

    // Parse quantities
    if (root.hasKey("quantities")) {
        config.quantities = root["quantities"].asStringArray();
    }

    // Parse time selection
    if (root.hasKey("time")) {
        auto timeNode = root["time"];
        if (timeNode.hasKey("start")) {
            config.time_start = timeNode["start"].asDouble();
        }
        if (timeNode.hasKey("end")) {
            config.time_end = timeNode["end"].asDouble();
        }
        if (timeNode.hasKey("step")) {
            config.time_step = static_cast<int>(timeNode["step"].asInt(1));
        }
        if (timeNode.hasKey("states")) {
            auto states = timeNode["states"].asIntArray();
            for (int64_t s : states) {
                config.state_indices.push_back(static_cast<int>(s));
            }
        }
    }

    // Parse spatial selection
    if (root.hasKey("spatial")) {
        auto spatialNode = root["spatial"];
        config.has_spatial = true;
        config.spatial_type = spatialNode["type"].asString();
        if (spatialNode.hasKey("params")) {
            config.spatial_params = spatialNode["params"].asDoubleArray();
        }
    }

    // Parse filter
    if (root.hasKey("filter")) {
        auto filterNode = root["filter"];
        if (filterNode.hasKey("min")) {
            config.min_value = filterNode["min"].asDouble();
        }
        if (filterNode.hasKey("max")) {
            config.max_value = filterNode["max"].asDouble();
        }
    }

    // Parse output
    if (root.hasKey("output")) {
        auto outputNode = root["output"];
        if (outputNode.hasKey("path")) {
            config.output_path = outputNode["path"].asString();
        }
        if (outputNode.hasKey("format")) {
            config.output_format = outputNode["format"].asString();
        }
        if (outputNode.hasKey("metadata")) {
            config.include_metadata = outputNode["metadata"].asBool(true);
        }
        if (outputNode.hasKey("statistics")) {
            config.include_statistics = outputNode["statistics"].asBool(true);
        }
    }

    // Parse template
    if (root.hasKey("template")) {
        auto tmplNode = root["template"];
        if (tmplNode.isScalar()) {
            config.template_name = tmplNode.asString();
        } else if (tmplNode.hasKey("name")) {
            config.template_name = tmplNode["name"].asString();
            if (tmplNode.hasKey("params")) {
                auto paramsNode = tmplNode["params"];
                for (const auto& key : paramsNode.keys()) {
                    config.template_params[key] = paramsNode[key].asString();
                }
            }
        }
    }

    // Parse options
    if (root.hasKey("verbose")) {
        config.verbose = root["verbose"].asBool();
    }

    validateConfig(config);
    return config;
}

void ConfigParser::validateConfig(QueryConfig& config) {
    // Validate required fields
    if (config.d3plot_path.empty() && config.d3plot_files.empty()) {
        pImpl->warnings.push_back("No d3plot file specified");
    }

    // Validate output format
    std::string fmt = config.output_format;
    std::transform(fmt.begin(), fmt.end(), fmt.begin(), ::tolower);
    if (fmt != "csv" && fmt != "json" && fmt != "hdf5") {
        pImpl->warnings.push_back("Unknown output format: " + config.output_format + ", using csv");
        config.output_format = "csv";
    }
}

PartSelector ConfigParser::createPartSelector(const QueryConfig& config) {
    PartSelector selector;
    for (const auto& part : config.parts) {
        selector.byName(part);
    }
    return selector;
}

QuantitySelector ConfigParser::createQuantitySelector(const QueryConfig& config) {
    QuantitySelector selector;
    for (const auto& qty : config.quantities) {
        std::string q = qty;
        std::transform(q.begin(), q.end(), q.begin(), ::tolower);

        if (q == "von_mises" || q == "vonmises") {
            selector.vonMises();
        } else if (q == "displacement" || q == "disp") {
            selector.displacement();
        } else if (q == "stress" || q == "all_stress") {
            selector.allStress();
        } else if (q == "strain" || q == "all_strain") {
            selector.allStrain();
        } else if (q == "plastic_strain" || q == "effective_strain") {
            selector.effectiveStrain();
        }
    }
    return selector;
}

TimeSelector ConfigParser::createTimeSelector(const QueryConfig& config) {
    TimeSelector selector;

    if (!config.state_indices.empty()) {
        for (int idx : config.state_indices) {
            selector.addStep(idx);
        }
        return selector;
    }

    if (config.time_end > config.time_start) {
        selector.addTimeRange(config.time_start, config.time_end);
        return selector;
    }

    if (config.time_step > 1) {
        selector.everyNth(config.time_step);
        return selector;
    }

    selector.all();
    return selector;
}

ValueFilter ConfigParser::createValueFilter(const QueryConfig& config) {
    ValueFilter filter;

    if (config.min_value > std::numeric_limits<double>::lowest()) {
        filter.greaterThan(config.min_value);
    }
    if (config.max_value < std::numeric_limits<double>::max()) {
        filter.lessThan(config.max_value);
    }

    return filter;
}

OutputSpec ConfigParser::createOutputSpec(const QueryConfig& config) {
    OutputSpec spec;

    std::string fmt = config.output_format;
    std::transform(fmt.begin(), fmt.end(), fmt.begin(), ::tolower);

    if (fmt == "csv") {
        spec.format(OutputFormat::CSV);
    } else if (fmt == "json") {
        spec.format(OutputFormat::JSON);
    } else if (fmt == "hdf5") {
        spec.format(OutputFormat::HDF5);
    }

    spec.includeMetadata(config.include_metadata);
    spec.includeStatisticsSection(config.include_statistics);

    return spec;
}

SpatialSelector ConfigParser::createSpatialSelector(const QueryConfig& config) {
    if (!config.has_spatial) {
        return SpatialSelector::all();
    }

    std::string type = config.spatial_type;
    std::transform(type.begin(), type.end(), type.begin(), ::tolower);
    const auto& p = config.spatial_params;

    if (type == "box" && p.size() >= 6) {
        return SpatialSelector::boundingBox({p[0], p[1], p[2]}, {p[3], p[4], p[5]});
    } else if (type == "sphere" && p.size() >= 4) {
        return SpatialSelector::sphereRegion({p[0], p[1], p[2]}, p[3]);
    } else if (type == "plane" && p.size() >= 6) {
        double tol = (p.size() >= 7) ? p[6] : 1.0;
        return SpatialSelector::sectionPlane({p[0], p[1], p[2]}, {p[3], p[4], p[5]}, tol);
    }

    return SpatialSelector::all();
}

std::string ConfigParser::getLastError() const {
    return pImpl->last_error;
}

bool ConfigParser::isValid() const {
    return pImpl->valid;
}

std::vector<std::string> ConfigParser::getWarnings() const {
    return pImpl->warnings;
}

// ============================================================
// ConfigFactory Implementation
// ============================================================

namespace ConfigFactory {

QueryConfig fromArgs(int argc, char* argv[]) {
    QueryConfig config;

    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];

        if ((arg == "-f" || arg == "--file") && i + 1 < argc) {
            config.d3plot_path = argv[++i];
        } else if ((arg == "-o" || arg == "--output") && i + 1 < argc) {
            config.output_path = argv[++i];
        } else if ((arg == "-p" || arg == "--part") && i + 1 < argc) {
            config.parts.push_back(argv[++i]);
        } else if ((arg == "-q" || arg == "--quantity") && i + 1 < argc) {
            config.quantities.push_back(argv[++i]);
        } else if (arg == "--format" && i + 1 < argc) {
            config.output_format = argv[++i];
        } else if (arg == "-v" || arg == "--verbose") {
            config.verbose = true;
        } else if (arg[0] != '-' && config.d3plot_path.empty()) {
            config.d3plot_path = arg;
        }
    }

    return config;
}

QueryConfig fromEnv() {
    QueryConfig config;

    const char* d3plot = std::getenv("KOOD3PLOT_FILE");
    if (d3plot) config.d3plot_path = d3plot;

    const char* output = std::getenv("KOOD3PLOT_OUTPUT");
    if (output) config.output_path = output;

    const char* format = std::getenv("KOOD3PLOT_FORMAT");
    if (format) config.output_format = format;

    return config;
}

QueryConfig merge(const QueryConfig& base, const QueryConfig& override_cfg) {
    QueryConfig result = base;

    if (!override_cfg.d3plot_path.empty()) {
        result.d3plot_path = override_cfg.d3plot_path;
    }
    if (!override_cfg.parts.empty()) {
        result.parts = override_cfg.parts;
    }
    if (!override_cfg.quantities.empty()) {
        result.quantities = override_cfg.quantities;
    }
    if (!override_cfg.output_path.empty()) {
        result.output_path = override_cfg.output_path;
    }
    if (override_cfg.output_format != "csv") {
        result.output_format = override_cfg.output_format;
    }
    if (override_cfg.verbose) {
        result.verbose = true;
    }

    return result;
}

} // namespace ConfigFactory

} // namespace query
} // namespace kood3plot
