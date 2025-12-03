#pragma once

/**
 * @file TemplateManager.h
 * @brief Template management and registry for query templates
 * @author KooD3plot V3 Development Team
 * @date 2025-11-22
 * @version 3.0.0
 *
 * TemplateManager provides a centralized registry for query templates,
 * including built-in templates and user-defined custom templates.
 *
 * Example usage:
 * @code
 * auto& manager = TemplateManager::instance();
 *
 * // List available templates
 * for (const auto& name : manager.listTemplates()) {
 *     std::cout << name << std::endl;
 * }
 *
 * // Get a template
 * auto tmpl = manager.get("max_stress_history");
 * tmpl.setParameter("parts", {"Hood", "Fender"});
 *
 * // Execute
 * auto query = tmpl.createQuery(reader);
 * query.writeCSV("output.csv");
 * @endcode
 */

#include "QueryTemplate.h"
#include <string>
#include <vector>
#include <map>
#include <memory>
#include <functional>

namespace kood3plot {
namespace query {

/**
 * @brief Template category information
 */
struct TemplateCategory {
    std::string name;           ///< Category name
    std::string description;    ///< Category description
    std::vector<std::string> templates;  ///< Templates in this category
};

/**
 * @class TemplateManager
 * @brief Singleton manager for query templates
 *
 * Manages registration, discovery, and access to query templates.
 * Includes built-in templates and supports user-defined templates.
 */
class TemplateManager {
public:
    // ============================================================
    // Singleton Access
    // ============================================================

    /**
     * @brief Get singleton instance
     * @return Reference to the manager
     */
    static TemplateManager& instance();

    // Delete copy/move for singleton
    TemplateManager(const TemplateManager&) = delete;
    TemplateManager& operator=(const TemplateManager&) = delete;
    TemplateManager(TemplateManager&&) = delete;
    TemplateManager& operator=(TemplateManager&&) = delete;

    // ============================================================
    // Template Registration
    // ============================================================

    /**
     * @brief Register a template
     * @param tmpl Template to register
     *
     * The template name must be unique.
     */
    void registerTemplate(const QueryTemplate& tmpl);

    /**
     * @brief Register a template with a custom name
     * @param name Template name
     * @param tmpl Template to register
     */
    void registerTemplate(const std::string& name, const QueryTemplate& tmpl);

    /**
     * @brief Unregister a template
     * @param name Template name
     * @return true if template was removed
     */
    bool unregisterTemplate(const std::string& name);

    /**
     * @brief Check if template exists
     * @param name Template name
     * @return true if template is registered
     */
    bool hasTemplate(const std::string& name) const;

    // ============================================================
    // Template Access
    // ============================================================

    /**
     * @brief Get a template by name
     * @param name Template name
     * @return Copy of the template
     * @throws std::runtime_error if template not found
     */
    QueryTemplate get(const std::string& name) const;

    /**
     * @brief Get a template by name (with alias support)
     * @param name Template name or alias
     * @return Copy of the template
     */
    QueryTemplate getByAlias(const std::string& name_or_alias) const;

    /**
     * @brief List all template names
     * @return Vector of template names
     */
    std::vector<std::string> listTemplates() const;

    /**
     * @brief List templates in a category
     * @param category Category name
     * @return Vector of template names in the category
     */
    std::vector<std::string> listTemplates(const std::string& category) const;

    /**
     * @brief Get all categories
     * @return Vector of category information
     */
    std::vector<TemplateCategory> getCategories() const;

    /**
     * @brief Search templates by keyword
     * @param keyword Search keyword
     * @return Vector of matching template names
     */
    std::vector<std::string> searchTemplates(const std::string& keyword) const;

    // ============================================================
    // Template Information
    // ============================================================

    /**
     * @brief Get template summary
     * @param name Template name
     * @return Summary string
     */
    std::string getTemplateSummary(const std::string& name) const;

    /**
     * @brief Get all template summaries
     * @return Map of name to summary
     */
    std::map<std::string, std::string> getAllSummaries() const;

    /**
     * @brief Print template list to stream
     * @param os Output stream
     * @param detailed Include parameter details
     */
    void printTemplateList(std::ostream& os, bool detailed = false) const;

    // ============================================================
    // Template Aliases
    // ============================================================

    /**
     * @brief Add alias for a template
     * @param alias Alias name
     * @param template_name Target template name
     */
    void addAlias(const std::string& alias, const std::string& template_name);

    /**
     * @brief Remove alias
     * @param alias Alias name
     */
    void removeAlias(const std::string& alias);

    /**
     * @brief Get all aliases
     * @return Map of alias to template name
     */
    std::map<std::string, std::string> getAliases() const;

    // ============================================================
    // File Operations
    // ============================================================

    /**
     * @brief Load templates from a directory
     * @param directory Directory path
     * @param extension File extension filter (e.g., ".yaml")
     * @return Number of templates loaded
     */
    size_t loadFromDirectory(const std::string& directory,
                            const std::string& extension = ".yaml");

    /**
     * @brief Load a single template from file
     * @param filename Template file path
     * @return Loaded template name
     */
    std::string loadFromFile(const std::string& filename);

    /**
     * @brief Save a template to file
     * @param name Template name
     * @param filename Output file path
     */
    void saveToFile(const std::string& name, const std::string& filename) const;

    /**
     * @brief Export all templates to directory
     * @param directory Output directory
     * @param format Export format ("yaml" or "json")
     */
    void exportAll(const std::string& directory, const std::string& format = "yaml") const;

    // ============================================================
    // Built-in Templates
    // ============================================================

    /**
     * @brief Load all built-in templates
     *
     * Called automatically on first access.
     */
    void loadBuiltinTemplates();

    /**
     * @brief Reset to built-in templates only
     *
     * Removes all user-registered templates.
     */
    void resetToBuiltin();

    /**
     * @brief Get number of registered templates
     */
    size_t size() const;

private:
    TemplateManager();
    ~TemplateManager();

    struct Impl;
    std::unique_ptr<Impl> pImpl;
};

} // namespace query
} // namespace kood3plot
