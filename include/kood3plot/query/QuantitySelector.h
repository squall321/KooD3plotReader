#pragma once

/**
 * @file QuantitySelector.h
 * @brief Physical quantity selection interface for the KooD3plot Query System
 * @author KooD3plot V3 Development Team
 * @date 2025-11-21
 * @version 3.0.0
 *
 * QuantitySelector provides flexible methods to select physical quantities
 * from d3plot results:
 * - By type (von_mises, effective_strain, displacement, etc.)
 * - By category (all stress, all strain, all displacement)
 * - By component ID (LS-PrePost fringe component IDs)
 * - Multiple quantities simultaneously
 *
 * Example usage:
 * @code
 * QuantitySelector selector;
 * selector.add("von_mises")
 *         .add("effective_strain")
 *         .addStressAll();
 * auto quantities = selector.getQuantities();
 * @endcode
 */

#include "QueryTypes.h"
#include <vector>
#include <set>
#include <string>

namespace kood3plot {
namespace query {

/**
 * @class QuantitySelector
 * @brief Selects physical quantities to extract from d3plot results
 *
 * This class manages selection of physical quantities (stress, strain,
 * displacement, energy, etc.) that should be extracted from the d3plot
 * database. It supports:
 * - Individual quantity selection by name or type
 * - Bulk selection by category (all stress, all strain)
 * - Component ID-based selection for LS-PrePost compatibility
 * - Query of selected quantities and their properties
 */
class QuantitySelector {
public:
    // ============================================================
    // Constructors
    // ============================================================

    /**
     * @brief Default constructor
     */
    QuantitySelector();

    /**
     * @brief Copy constructor
     */
    QuantitySelector(const QuantitySelector& other);

    /**
     * @brief Move constructor
     */
    QuantitySelector(QuantitySelector&& other) noexcept;

    /**
     * @brief Assignment operator
     */
    QuantitySelector& operator=(const QuantitySelector& other);

    /**
     * @brief Move assignment operator
     */
    QuantitySelector& operator=(QuantitySelector&& other) noexcept;

    /**
     * @brief Destructor
     */
    ~QuantitySelector();

    // ============================================================
    // Selection by Type Enum
    // ============================================================

    /**
     * @brief Add quantity by QuantityType enum
     * @param type Quantity type enum value
     * @return Reference to this selector for method chaining
     *
     * Example:
     * @code
     * selector.add(QuantityType::STRESS_VON_MISES);
     * @endcode
     */
    QuantitySelector& add(QuantityType type);

    /**
     * @brief Add multiple quantities by type enum
     * @param types Vector of quantity type enums
     * @return Reference to this selector for method chaining
     *
     * Example:
     * @code
     * selector.add({
     *     QuantityType::STRESS_VON_MISES,
     *     QuantityType::STRAIN_EFFECTIVE,
     *     QuantityType::DISPLACEMENT_MAGNITUDE
     * });
     * @endcode
     */
    QuantitySelector& add(const std::vector<QuantityType>& types);

    // ============================================================
    // Selection by Name String
    // ============================================================

    /**
     * @brief Add quantity by name string
     * @param name Quantity name (e.g., "von_mises", "effective_strain")
     * @return Reference to this selector for method chaining
     *
     * Supported names:
     * - Stress: "von_mises", "pressure", "x_stress", "principal_stress_1", etc.
     * - Strain: "effective_strain", "plastic_strain", "x_strain", etc.
     * - Displacement: "displacement", "x_displacement", "y_displacement", etc.
     * - Energy: "energy_density", "hourglass_energy_density"
     * - Other: "triaxiality", "thickness"
     *
     * Example:
     * @code
     * selector.add("von_mises")
     *         .add("effective_strain");
     * @endcode
     */
    QuantitySelector& add(const std::string& name);

    /**
     * @brief Add multiple quantities by name strings
     * @param names Vector of quantity names
     * @return Reference to this selector for method chaining
     *
     * Example:
     * @code
     * selector.add({"von_mises", "effective_strain", "displacement"});
     * @endcode
     */
    QuantitySelector& add(const std::vector<std::string>& names);

    // ============================================================
    // Selection by Component ID
    // ============================================================

    /**
     * @brief Add quantity by LS-PrePost fringe component ID
     * @param component_id Fringe component ID (e.g., 9 for von mises)
     * @return Reference to this selector for method chaining
     *
     * Common component IDs:
     * - 1-6: Stress components (x, y, z, xy, yz, zx)
     * - 7: Effective plastic strain
     * - 8: Pressure
     * - 9: Von Mises stress
     * - 14-16: Principal stresses
     * - 17-20: Displacements
     * - 80: Effective strain
     *
     * Example:
     * @code
     * selector.addByComponentId(9);  // Von Mises stress
     * @endcode
     */
    QuantitySelector& addByComponentId(int component_id);

    /**
     * @brief Add multiple quantities by component IDs
     * @param component_ids Vector of component IDs
     * @return Reference to this selector for method chaining
     */
    QuantitySelector& addByComponentId(const std::vector<int>& component_ids);

    // ============================================================
    // Bulk Selection by Category
    // ============================================================

    /**
     * @brief Add all stress-related quantities
     * @return Reference to this selector
     *
     * Adds:
     * - x, y, z stress components
     * - xy, yz, zx shear stresses
     * - von mises stress
     * - pressure
     * - principal stresses (1, 2, 3)
     * - max shear stress
     *
     * Example:
     * @code
     * selector.addStressAll();
     * @endcode
     */
    QuantitySelector& addStressAll();

    /**
     * @brief Add all strain-related quantities
     * @return Reference to this selector
     *
     * Adds:
     * - x, y, z strain components
     * - xy, yz, zx shear strains
     * - effective strain
     * - effective plastic strain
     * - principal strains (1, 2, 3)
     * - volumetric strain
     */
    QuantitySelector& addStrainAll();

    /**
     * @brief Add all displacement quantities
     * @return Reference to this selector
     *
     * Adds:
     * - x, y, z displacements
     * - resultant displacement magnitude
     */
    QuantitySelector& addDisplacementAll();

    /**
     * @brief Add all energy quantities
     * @return Reference to this selector
     *
     * Adds:
     * - Hourglass energy density
     * - Strain energy density
     */
    QuantitySelector& addEnergyAll();

    /**
     * @brief Add all available quantities
     * @return Reference to this selector
     *
     * Adds ALL supported quantity types (40+ quantities).
     * Use with caution as this may result in large output.
     */
    QuantitySelector& addAll();

    // ============================================================
    // Query Methods
    // ============================================================

    /**
     * @brief Get selected quantities as type enums
     * @return Vector of selected quantity types
     *
     * Example:
     * @code
     * auto types = selector.getQuantities();
     * for (auto type : types) {
     *     std::cout << getQuantityName(type) << std::endl;
     * }
     * @endcode
     */
    std::vector<QuantityType> getQuantities() const;

    /**
     * @brief Get selected quantities as name strings
     * @return Vector of quantity names
     *
     * Example:
     * @code
     * auto names = selector.getQuantityNames();
     * // ["von_mises", "effective_strain"]
     * @endcode
     */
    std::vector<std::string> getQuantityNames() const;

    /**
     * @brief Get fringe component IDs for selected quantities
     * @return Vector of component IDs
     *
     * Useful for LS-PrePost CFile generation.
     *
     * Example:
     * @code
     * auto ids = selector.getComponentIds();
     * // [9, 80] for von_mises and effective_strain
     * @endcode
     */
    std::vector<int> getComponentIds() const;

    /**
     * @brief Count how many quantities are selected
     * @return Number of selected quantities
     */
    size_t count() const;

    /**
     * @brief Check if any quantities are selected
     * @return true if at least one quantity is selected
     */
    bool hasSelection() const;

    /**
     * @brief Check if a specific quantity is selected
     * @param type Quantity type to check
     * @return true if the quantity is selected
     */
    bool contains(QuantityType type) const;

    /**
     * @brief Check if a specific quantity is selected (by name)
     * @param name Quantity name to check
     * @return true if the quantity is selected
     */
    bool contains(const std::string& name) const;

    // ============================================================
    // Removal Methods
    // ============================================================

    /**
     * @brief Remove a quantity from selection
     * @param type Quantity type to remove
     * @return Reference to this selector
     */
    QuantitySelector& remove(QuantityType type);

    /**
     * @brief Remove a quantity from selection (by name)
     * @param name Quantity name to remove
     * @return Reference to this selector
     */
    QuantitySelector& remove(const std::string& name);

    /**
     * @brief Clear all selected quantities
     * @return Reference to this selector
     */
    QuantitySelector& clear();

    // ============================================================
    // Utility Methods
    // ============================================================

    /**
     * @brief Get description of selected quantities (for debugging)
     * @return String describing selected quantities
     *
     * Example output: "3 quantities: [von_mises, effective_strain, displacement]"
     */
    std::string getDescription() const;

    /**
     * @brief Check if selector is empty (no quantities selected)
     * @return true if no quantities are selected
     */
    bool isEmpty() const;

    /**
     * @brief Get quantity type from name string
     * @param name Quantity name
     * @return Optional quantity type (empty if name not recognized)
     *
     * This is a static utility method.
     */
    static std::optional<QuantityType> getTypeFromName(const std::string& name);

    /**
     * @brief Get quantity name from type enum
     * @param type Quantity type
     * @return Quantity name string
     *
     * This is a static utility method.
     */
    static std::string getNameFromType(QuantityType type);

    /**
     * @brief Get fringe component ID from quantity type
     * @param type Quantity type
     * @return Component ID (-1 if not found)
     *
     * This is a static utility method.
     */
    static int getComponentId(QuantityType type);

    /**
     * @brief Get quantity type from component ID
     * @param component_id Component ID
     * @return Optional quantity type (empty if ID not recognized)
     *
     * This is a static utility method.
     */
    static std::optional<QuantityType> getTypeFromComponentId(int component_id);

    // ============================================================
    // Category Query Methods
    // ============================================================

    /**
     * @brief Check if quantity is a stress type
     * @param type Quantity type to check
     * @return true if it's a stress quantity
     */
    static bool isStress(QuantityType type);

    /**
     * @brief Check if quantity is a strain type
     * @param type Quantity type to check
     * @return true if it's a strain quantity
     */
    static bool isStrain(QuantityType type);

    /**
     * @brief Check if quantity is a displacement type
     * @param type Quantity type to check
     * @return true if it's a displacement quantity
     */
    static bool isDisplacement(QuantityType type);

    /**
     * @brief Check if quantity is an energy type
     * @param type Quantity type to check
     * @return true if it's an energy quantity
     */
    static bool isEnergy(QuantityType type);

    /**
     * @brief Get category name for a quantity
     * @param type Quantity type
     * @return Category name ("stress", "strain", "displacement", "energy", "other")
     */
    static std::string getCategory(QuantityType type);

    // ============================================================
    // Predefined Selectors (Static Factory Methods)
    // ============================================================

    /**
     * @brief Create selector with von mises stress only
     * @return QuantitySelector with von_mises selected
     */
    static QuantitySelector vonMises();

    /**
     * @brief Create selector with effective strain only
     * @return QuantitySelector with effective_strain selected
     */
    static QuantitySelector effectiveStrain();

    /**
     * @brief Create selector with displacement magnitude only
     * @return QuantitySelector with displacement selected
     */
    static QuantitySelector displacement();

    /**
     * @brief Create selector with all stress quantities
     * @return QuantitySelector with all stress types selected
     */
    static QuantitySelector allStress();

    /**
     * @brief Create selector with all strain quantities
     * @return QuantitySelector with all strain types selected
     */
    static QuantitySelector allStrain();

    /**
     * @brief Create selector with common crash analysis quantities
     * @return QuantitySelector with: von_mises, effective_strain, displacement
     */
    static QuantitySelector commonCrash();

private:
    // ============================================================
    // Private Implementation
    // ============================================================

    /**
     * @brief Implementation struct (PIMPL pattern)
     */
    struct Impl;
    std::unique_ptr<Impl> pImpl;

    /**
     * @brief Add stress quantities to internal set
     */
    void addStressQuantities();

    /**
     * @brief Add strain quantities to internal set
     */
    void addStrainQuantities();

    /**
     * @brief Add displacement quantities to internal set
     */
    void addDisplacementQuantities();

    /**
     * @brief Add energy quantities to internal set
     */
    void addEnergyQuantities();
};

} // namespace query
} // namespace kood3plot
