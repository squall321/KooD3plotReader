/**
 * @file TemplateManager.cpp
 * @brief Implementation of TemplateManager class
 * @author KooD3plot V3 Development Team
 * @date 2025-11-22
 * @version 3.0.0
 */

#include "kood3plot/query/TemplateManager.h"
#include <fstream>
#include <sstream>
#include <algorithm>
#include <iostream>
#include <filesystem>

namespace kood3plot {
namespace query {

namespace fs = std::filesystem;

// ============================================================
// PIMPL Implementation
// ============================================================

struct TemplateManager::Impl {
    std::map<std::string, QueryTemplate> templates;
    std::map<std::string, std::string> aliases;
    bool builtin_loaded = false;

    void ensureBuiltinLoaded() {
        if (!builtin_loaded) {
            loadBuiltin();
            builtin_loaded = true;
        }
    }

    void loadBuiltin() {
        // Register all built-in templates
        auto max_stress = QueryTemplate::maxStressHistory();
        templates[max_stress.getName()] = max_stress;

        auto max_strain = QueryTemplate::maxStrainHistory();
        templates[max_strain.getName()] = max_strain;

        auto final_state = QueryTemplate::finalStateAnalysis();
        templates[final_state.getName()] = final_state;

        auto critical = QueryTemplate::criticalZones();
        templates[critical.getName()] = critical;

        auto elem_history = QueryTemplate::elementHistory();
        templates[elem_history.getName()] = elem_history;

        auto part_comp = QueryTemplate::partComparison();
        templates[part_comp.getName()] = part_comp;

        auto disp_env = QueryTemplate::displacementEnvelope();
        templates[disp_env.getName()] = disp_env;

        auto energy = QueryTemplate::energyBalance();
        templates[energy.getName()] = energy;

        auto contact = QueryTemplate::contactForceHistory();
        templates[contact.getName()] = contact;

        auto failure = QueryTemplate::failureAnalysis();
        templates[failure.getName()] = failure;

        // Add common aliases
        aliases["stress"] = "max_stress_history";
        aliases["strain"] = "max_strain_history";
        aliases["final"] = "final_state";
        aliases["critical"] = "critical_zones";
        aliases["history"] = "element_history";
        aliases["compare"] = "part_comparison";
        aliases["displacement"] = "displacement_envelope";
        aliases["energy"] = "energy_balance";
        aliases["contact"] = "contact_force_history";
        aliases["failure"] = "failure_analysis";
    }
};

// ============================================================
// Singleton Implementation
// ============================================================

TemplateManager& TemplateManager::instance() {
    static TemplateManager instance;
    return instance;
}

TemplateManager::TemplateManager()
    : pImpl(std::make_unique<Impl>())
{
}

TemplateManager::~TemplateManager() = default;

// ============================================================
// Template Registration
// ============================================================

void TemplateManager::registerTemplate(const QueryTemplate& tmpl) {
    pImpl->ensureBuiltinLoaded();
    pImpl->templates[tmpl.getName()] = tmpl;
}

void TemplateManager::registerTemplate(const std::string& name, const QueryTemplate& tmpl) {
    pImpl->ensureBuiltinLoaded();
    QueryTemplate copy = tmpl;
    copy.setName(name);
    pImpl->templates[name] = copy;
}

bool TemplateManager::unregisterTemplate(const std::string& name) {
    pImpl->ensureBuiltinLoaded();
    auto it = pImpl->templates.find(name);
    if (it != pImpl->templates.end()) {
        pImpl->templates.erase(it);
        return true;
    }
    return false;
}

bool TemplateManager::hasTemplate(const std::string& name) const {
    pImpl->ensureBuiltinLoaded();
    return pImpl->templates.find(name) != pImpl->templates.end();
}

// ============================================================
// Template Access
// ============================================================

QueryTemplate TemplateManager::get(const std::string& name) const {
    pImpl->ensureBuiltinLoaded();

    auto it = pImpl->templates.find(name);
    if (it != pImpl->templates.end()) {
        return it->second;
    }

    throw std::runtime_error("Template not found: " + name);
}

QueryTemplate TemplateManager::getByAlias(const std::string& name_or_alias) const {
    pImpl->ensureBuiltinLoaded();

    // First try direct name
    auto it = pImpl->templates.find(name_or_alias);
    if (it != pImpl->templates.end()) {
        return it->second;
    }

    // Try alias
    auto alias_it = pImpl->aliases.find(name_or_alias);
    if (alias_it != pImpl->aliases.end()) {
        return get(alias_it->second);
    }

    throw std::runtime_error("Template or alias not found: " + name_or_alias);
}

std::vector<std::string> TemplateManager::listTemplates() const {
    pImpl->ensureBuiltinLoaded();

    std::vector<std::string> names;
    names.reserve(pImpl->templates.size());

    for (const auto& [name, tmpl] : pImpl->templates) {
        names.push_back(name);
    }

    std::sort(names.begin(), names.end());
    return names;
}

std::vector<std::string> TemplateManager::listTemplates(const std::string& category) const {
    pImpl->ensureBuiltinLoaded();

    std::vector<std::string> names;

    for (const auto& [name, tmpl] : pImpl->templates) {
        if (tmpl.getCategory() == category) {
            names.push_back(name);
        }
    }

    std::sort(names.begin(), names.end());
    return names;
}

std::vector<TemplateCategory> TemplateManager::getCategories() const {
    pImpl->ensureBuiltinLoaded();

    std::map<std::string, TemplateCategory> cat_map;

    for (const auto& [name, tmpl] : pImpl->templates) {
        std::string cat = tmpl.getCategory();
        if (cat.empty()) cat = "general";

        if (cat_map.find(cat) == cat_map.end()) {
            cat_map[cat] = TemplateCategory{cat, "", {}};
        }
        cat_map[cat].templates.push_back(name);
    }

    std::vector<TemplateCategory> result;
    for (auto& [name, cat] : cat_map) {
        std::sort(cat.templates.begin(), cat.templates.end());
        result.push_back(std::move(cat));
    }

    return result;
}

std::vector<std::string> TemplateManager::searchTemplates(const std::string& keyword) const {
    pImpl->ensureBuiltinLoaded();

    std::vector<std::string> matches;
    std::string lower_keyword = keyword;
    std::transform(lower_keyword.begin(), lower_keyword.end(), lower_keyword.begin(), ::tolower);

    for (const auto& [name, tmpl] : pImpl->templates) {
        std::string lower_name = name;
        std::transform(lower_name.begin(), lower_name.end(), lower_name.begin(), ::tolower);

        std::string lower_desc = tmpl.getDescription();
        std::transform(lower_desc.begin(), lower_desc.end(), lower_desc.begin(), ::tolower);

        if (lower_name.find(lower_keyword) != std::string::npos ||
            lower_desc.find(lower_keyword) != std::string::npos) {
            matches.push_back(name);
        }
    }

    std::sort(matches.begin(), matches.end());
    return matches;
}

// ============================================================
// Template Information
// ============================================================

std::string TemplateManager::getTemplateSummary(const std::string& name) const {
    return get(name).getSummary();
}

std::map<std::string, std::string> TemplateManager::getAllSummaries() const {
    pImpl->ensureBuiltinLoaded();

    std::map<std::string, std::string> summaries;
    for (const auto& [name, tmpl] : pImpl->templates) {
        summaries[name] = tmpl.getSummary();
    }
    return summaries;
}

void TemplateManager::printTemplateList(std::ostream& os, bool detailed) const {
    pImpl->ensureBuiltinLoaded();

    os << "Available Templates (" << pImpl->templates.size() << "):\n";
    os << "========================================\n\n";

    auto categories = getCategories();

    for (const auto& cat : categories) {
        os << "[" << cat.name << "]\n";

        for (const auto& tmpl_name : cat.templates) {
            const auto& tmpl = pImpl->templates.at(tmpl_name);
            os << "  " << tmpl_name << "\n";
            os << "    " << tmpl.getDescription() << "\n";

            if (detailed) {
                auto params = tmpl.getParameters();
                if (!params.empty()) {
                    os << "    Parameters:\n";
                    for (const auto& param : params) {
                        os << "      - " << param.name << " (" << param.type << ")";
                        if (param.required) os << " [required]";
                        os << "\n";
                    }
                }
            }
            os << "\n";
        }
    }

    // Print aliases
    if (!pImpl->aliases.empty()) {
        os << "Aliases:\n";
        for (const auto& [alias, target] : pImpl->aliases) {
            os << "  " << alias << " -> " << target << "\n";
        }
    }
}

// ============================================================
// Template Aliases
// ============================================================

void TemplateManager::addAlias(const std::string& alias, const std::string& template_name) {
    pImpl->ensureBuiltinLoaded();
    if (!hasTemplate(template_name)) {
        throw std::runtime_error("Cannot add alias for non-existent template: " + template_name);
    }
    pImpl->aliases[alias] = template_name;
}

void TemplateManager::removeAlias(const std::string& alias) {
    pImpl->aliases.erase(alias);
}

std::map<std::string, std::string> TemplateManager::getAliases() const {
    return pImpl->aliases;
}

// ============================================================
// File Operations
// ============================================================

size_t TemplateManager::loadFromDirectory(const std::string& directory,
                                          const std::string& extension) {
    size_t count = 0;

    try {
        for (const auto& entry : fs::directory_iterator(directory)) {
            if (entry.is_regular_file()) {
                std::string path = entry.path().string();
                if (path.size() >= extension.size() &&
                    path.substr(path.size() - extension.size()) == extension) {
                    try {
                        loadFromFile(path);
                        ++count;
                    } catch (const std::exception& e) {
                        // Log error but continue
                        std::cerr << "Warning: Failed to load template from "
                                  << path << ": " << e.what() << "\n";
                    }
                }
            }
        }
    } catch (const std::exception& e) {
        throw std::runtime_error("Failed to read directory: " + directory);
    }

    return count;
}

std::string TemplateManager::loadFromFile(const std::string& filename) {
    QueryTemplate tmpl;

    if (filename.find(".yaml") != std::string::npos ||
        filename.find(".yml") != std::string::npos) {
        tmpl = QueryTemplate::loadFromYAML(filename);
    } else if (filename.find(".json") != std::string::npos) {
        tmpl = QueryTemplate::loadFromJSON(filename);
    } else {
        throw std::runtime_error("Unsupported file format: " + filename);
    }

    std::string name = tmpl.getName();
    registerTemplate(tmpl);
    return name;
}

void TemplateManager::saveToFile(const std::string& name, const std::string& filename) const {
    auto tmpl = get(name);

    if (filename.find(".yaml") != std::string::npos ||
        filename.find(".yml") != std::string::npos) {
        tmpl.saveToYAML(filename);
    } else if (filename.find(".json") != std::string::npos) {
        tmpl.saveToJSON(filename);
    } else {
        throw std::runtime_error("Unsupported file format: " + filename);
    }
}

void TemplateManager::exportAll(const std::string& directory, const std::string& format) const {
    pImpl->ensureBuiltinLoaded();

    // Create directory if it doesn't exist
    fs::create_directories(directory);

    std::string ext = (format == "json") ? ".json" : ".yaml";

    for (const auto& [name, tmpl] : pImpl->templates) {
        std::string filename = directory + "/" + name + ext;
        if (format == "json") {
            tmpl.saveToJSON(filename);
        } else {
            tmpl.saveToYAML(filename);
        }
    }
}

// ============================================================
// Built-in Templates
// ============================================================

void TemplateManager::loadBuiltinTemplates() {
    pImpl->loadBuiltin();
    pImpl->builtin_loaded = true;
}

void TemplateManager::resetToBuiltin() {
    pImpl->templates.clear();
    pImpl->aliases.clear();
    pImpl->builtin_loaded = false;
    pImpl->ensureBuiltinLoaded();
}

size_t TemplateManager::size() const {
    pImpl->ensureBuiltinLoaded();
    return pImpl->templates.size();
}

} // namespace query
} // namespace kood3plot
