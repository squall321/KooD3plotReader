/**
 * @file QuantitySelector.cpp
 * @brief Implementation of QuantitySelector class
 * @author KooD3plot V3 Development Team
 * @date 2025-11-21
 * @version 3.0.0
 */

#include "kood3plot/query/QuantitySelector.h"
#include <algorithm>
#include <sstream>

namespace kood3plot {
namespace query {

// ============================================================
// PIMPL Implementation Struct
// ============================================================

/**
 * @brief Implementation details for QuantitySelector
 */
struct QuantitySelector::Impl {
    /// Set of selected quantity types (using set for uniqueness)
    std::set<QuantityType> selected_quantities;

    /**
     * @brief Clear all selections
     */
    void clear() {
        selected_quantities.clear();
    }
};

// ============================================================
// Constructors and Destructor
// ============================================================

QuantitySelector::QuantitySelector()
    : pImpl(std::make_unique<Impl>())
{
}

QuantitySelector::QuantitySelector(const QuantitySelector& other)
    : pImpl(std::make_unique<Impl>(*other.pImpl))
{
}

QuantitySelector::QuantitySelector(QuantitySelector&& other) noexcept
    : pImpl(std::move(other.pImpl))
{
}

QuantitySelector& QuantitySelector::operator=(const QuantitySelector& other) {
    if (this != &other) {
        pImpl = std::make_unique<Impl>(*other.pImpl);
    }
    return *this;
}

QuantitySelector& QuantitySelector::operator=(QuantitySelector&& other) noexcept {
    if (this != &other) {
        pImpl = std::move(other.pImpl);
    }
    return *this;
}

QuantitySelector::~QuantitySelector() = default;

// ============================================================
// Selection by Type Enum
// ============================================================

QuantitySelector& QuantitySelector::add(QuantityType type) {
    pImpl->selected_quantities.insert(type);
    return *this;
}

QuantitySelector& QuantitySelector::add(const std::vector<QuantityType>& types) {
    pImpl->selected_quantities.insert(types.begin(), types.end());
    return *this;
}

// ============================================================
// Selection by Name String
// ============================================================

QuantitySelector& QuantitySelector::add(const std::string& name) {
    auto type_opt = getTypeFromName(name);
    if (type_opt.has_value()) {
        pImpl->selected_quantities.insert(type_opt.value());
    }
    // Silently ignore unknown names (could add warning/logging here)
    return *this;
}

QuantitySelector& QuantitySelector::add(const std::vector<std::string>& names) {
    for (const auto& name : names) {
        add(name);
    }
    return *this;
}

// ============================================================
// Selection by Component ID
// ============================================================

QuantitySelector& QuantitySelector::addByComponentId(int component_id) {
    auto type_opt = getTypeFromComponentId(component_id);
    if (type_opt.has_value()) {
        pImpl->selected_quantities.insert(type_opt.value());
    }
    return *this;
}

QuantitySelector& QuantitySelector::addByComponentId(const std::vector<int>& component_ids) {
    for (int id : component_ids) {
        addByComponentId(id);
    }
    return *this;
}

// ============================================================
// Bulk Selection by Category
// ============================================================

QuantitySelector& QuantitySelector::addStressAll() {
    addStressQuantities();
    return *this;
}

QuantitySelector& QuantitySelector::addStrainAll() {
    addStrainQuantities();
    return *this;
}

QuantitySelector& QuantitySelector::addDisplacementAll() {
    addDisplacementQuantities();
    return *this;
}

QuantitySelector& QuantitySelector::addEnergyAll() {
    addEnergyQuantities();
    return *this;
}

QuantitySelector& QuantitySelector::addAll() {
    addStressQuantities();
    addStrainQuantities();
    addDisplacementQuantities();
    addEnergyQuantities();

    // Add velocity & acceleration
    pImpl->selected_quantities.insert(QuantityType::VELOCITY_MAGNITUDE);
    pImpl->selected_quantities.insert(QuantityType::ACCELERATION_MAGNITUDE);

    // Add other quantities
    pImpl->selected_quantities.insert(QuantityType::SHELL_THICKNESS);
    pImpl->selected_quantities.insert(QuantityType::TRIAXIALITY);
    pImpl->selected_quantities.insert(QuantityType::NORMALIZED_MEAN_STRESS);

    return *this;
}

// ============================================================
// Query Methods
// ============================================================

std::vector<QuantityType> QuantitySelector::getQuantities() const {
    return std::vector<QuantityType>(
        pImpl->selected_quantities.begin(),
        pImpl->selected_quantities.end()
    );
}

std::vector<std::string> QuantitySelector::getQuantityNames() const {
    std::vector<std::string> names;
    names.reserve(pImpl->selected_quantities.size());

    for (auto type : pImpl->selected_quantities) {
        names.push_back(getNameFromType(type));
    }

    return names;
}

std::vector<int> QuantitySelector::getComponentIds() const {
    std::vector<int> ids;
    ids.reserve(pImpl->selected_quantities.size());

    for (auto type : pImpl->selected_quantities) {
        ids.push_back(getComponentId(type));
    }

    return ids;
}

size_t QuantitySelector::count() const {
    return pImpl->selected_quantities.size();
}

bool QuantitySelector::hasSelection() const {
    return !pImpl->selected_quantities.empty();
}

bool QuantitySelector::contains(QuantityType type) const {
    return pImpl->selected_quantities.find(type) != pImpl->selected_quantities.end();
}

bool QuantitySelector::contains(const std::string& name) const {
    auto type_opt = getTypeFromName(name);
    if (type_opt.has_value()) {
        return contains(type_opt.value());
    }
    return false;
}

// ============================================================
// Removal Methods
// ============================================================

QuantitySelector& QuantitySelector::remove(QuantityType type) {
    pImpl->selected_quantities.erase(type);
    return *this;
}

QuantitySelector& QuantitySelector::remove(const std::string& name) {
    auto type_opt = getTypeFromName(name);
    if (type_opt.has_value()) {
        pImpl->selected_quantities.erase(type_opt.value());
    }
    return *this;
}

QuantitySelector& QuantitySelector::clear() {
    pImpl->clear();
    return *this;
}

// ============================================================
// Utility Methods
// ============================================================

std::string QuantitySelector::getDescription() const {
    if (pImpl->selected_quantities.empty()) {
        return "No quantities selected";
    }

    std::ostringstream oss;
    oss << pImpl->selected_quantities.size() << " quantities: [";

    bool first = true;
    for (auto type : pImpl->selected_quantities) {
        if (!first) oss << ", ";
        oss << getNameFromType(type);
        first = false;
    }
    oss << "]";

    return oss.str();
}

bool QuantitySelector::isEmpty() const {
    return pImpl->selected_quantities.empty();
}

std::optional<QuantityType> QuantitySelector::getTypeFromName(const std::string& name) {
    return query::getQuantityType(name);  // Use utility from QueryTypes.h
}

std::string QuantitySelector::getNameFromType(QuantityType type) {
    return query::getQuantityName(type);  // Use utility from QueryTypes.h
}

int QuantitySelector::getComponentId(QuantityType type) {
    return query::getFringeComponentId(type);  // Use utility from QueryTypes.h
}

std::optional<QuantityType> QuantitySelector::getTypeFromComponentId(int component_id) {
    // Reverse lookup in FRINGE_COMPONENT_IDS map
    for (const auto& [type, id] : FRINGE_COMPONENT_IDS) {
        if (id == component_id) {
            return type;
        }
    }
    return std::nullopt;
}

// ============================================================
// Category Query Methods
// ============================================================

bool QuantitySelector::isStress(QuantityType type) {
    return type == QuantityType::STRESS_X ||
           type == QuantityType::STRESS_Y ||
           type == QuantityType::STRESS_Z ||
           type == QuantityType::STRESS_XY ||
           type == QuantityType::STRESS_YZ ||
           type == QuantityType::STRESS_ZX ||
           type == QuantityType::STRESS_VON_MISES ||
           type == QuantityType::STRESS_PRESSURE ||
           type == QuantityType::STRESS_MAX_SHEAR ||
           type == QuantityType::STRESS_PRINCIPAL_1 ||
           type == QuantityType::STRESS_PRINCIPAL_2 ||
           type == QuantityType::STRESS_PRINCIPAL_3 ||
           type == QuantityType::STRESS_SIGNED_VON_MISES;
}

bool QuantitySelector::isStrain(QuantityType type) {
    return type == QuantityType::STRAIN_X ||
           type == QuantityType::STRAIN_Y ||
           type == QuantityType::STRAIN_Z ||
           type == QuantityType::STRAIN_XY ||
           type == QuantityType::STRAIN_YZ ||
           type == QuantityType::STRAIN_ZX ||
           type == QuantityType::STRAIN_EFFECTIVE ||
           type == QuantityType::STRAIN_EFFECTIVE_PLASTIC ||
           type == QuantityType::STRAIN_PRINCIPAL_1 ||
           type == QuantityType::STRAIN_PRINCIPAL_2 ||
           type == QuantityType::STRAIN_PRINCIPAL_3 ||
           type == QuantityType::STRAIN_VOLUMETRIC;
}

bool QuantitySelector::isDisplacement(QuantityType type) {
    return type == QuantityType::DISPLACEMENT_X ||
           type == QuantityType::DISPLACEMENT_Y ||
           type == QuantityType::DISPLACEMENT_Z ||
           type == QuantityType::DISPLACEMENT_MAGNITUDE;
}

bool QuantitySelector::isEnergy(QuantityType type) {
    return type == QuantityType::ENERGY_HOURGLASS_DENSITY ||
           type == QuantityType::ENERGY_STRAIN_DENSITY;
}

std::string QuantitySelector::getCategory(QuantityType type) {
    if (isStress(type)) return "stress";
    if (isStrain(type)) return "strain";
    if (isDisplacement(type)) return "displacement";
    if (isEnergy(type)) return "energy";

    if (type == QuantityType::VELOCITY_MAGNITUDE ||
        type == QuantityType::ACCELERATION_MAGNITUDE) {
        return "motion";
    }

    return "other";
}

// ============================================================
// Predefined Selectors (Static Factory Methods)
// ============================================================

QuantitySelector QuantitySelector::vonMises() {
    QuantitySelector selector;
    selector.add(QuantityType::STRESS_VON_MISES);
    return selector;
}

QuantitySelector QuantitySelector::effectiveStrain() {
    QuantitySelector selector;
    selector.add(QuantityType::STRAIN_EFFECTIVE);
    return selector;
}

QuantitySelector QuantitySelector::displacement() {
    QuantitySelector selector;
    selector.add(QuantityType::DISPLACEMENT_MAGNITUDE);
    return selector;
}

QuantitySelector QuantitySelector::allStress() {
    QuantitySelector selector;
    selector.addStressAll();
    return selector;
}

QuantitySelector QuantitySelector::allStrain() {
    QuantitySelector selector;
    selector.addStrainAll();
    return selector;
}

QuantitySelector QuantitySelector::commonCrash() {
    QuantitySelector selector;
    selector.add(QuantityType::STRESS_VON_MISES)
            .add(QuantityType::STRAIN_EFFECTIVE)
            .add(QuantityType::DISPLACEMENT_MAGNITUDE);
    return selector;
}

// ============================================================
// Private Helper Methods
// ============================================================

void QuantitySelector::addStressQuantities() {
    // Basic stress components
    pImpl->selected_quantities.insert(QuantityType::STRESS_X);
    pImpl->selected_quantities.insert(QuantityType::STRESS_Y);
    pImpl->selected_quantities.insert(QuantityType::STRESS_Z);
    pImpl->selected_quantities.insert(QuantityType::STRESS_XY);
    pImpl->selected_quantities.insert(QuantityType::STRESS_YZ);
    pImpl->selected_quantities.insert(QuantityType::STRESS_ZX);

    // Derived stress quantities
    pImpl->selected_quantities.insert(QuantityType::STRESS_VON_MISES);
    pImpl->selected_quantities.insert(QuantityType::STRESS_PRESSURE);
    pImpl->selected_quantities.insert(QuantityType::STRESS_MAX_SHEAR);

    // Principal stresses
    pImpl->selected_quantities.insert(QuantityType::STRESS_PRINCIPAL_1);
    pImpl->selected_quantities.insert(QuantityType::STRESS_PRINCIPAL_2);
    pImpl->selected_quantities.insert(QuantityType::STRESS_PRINCIPAL_3);

    // Advanced
    pImpl->selected_quantities.insert(QuantityType::STRESS_SIGNED_VON_MISES);
}

void QuantitySelector::addStrainQuantities() {
    // Basic strain components
    pImpl->selected_quantities.insert(QuantityType::STRAIN_X);
    pImpl->selected_quantities.insert(QuantityType::STRAIN_Y);
    pImpl->selected_quantities.insert(QuantityType::STRAIN_Z);
    pImpl->selected_quantities.insert(QuantityType::STRAIN_XY);
    pImpl->selected_quantities.insert(QuantityType::STRAIN_YZ);
    pImpl->selected_quantities.insert(QuantityType::STRAIN_ZX);

    // Effective strains
    pImpl->selected_quantities.insert(QuantityType::STRAIN_EFFECTIVE);
    pImpl->selected_quantities.insert(QuantityType::STRAIN_EFFECTIVE_PLASTIC);

    // Principal strains
    pImpl->selected_quantities.insert(QuantityType::STRAIN_PRINCIPAL_1);
    pImpl->selected_quantities.insert(QuantityType::STRAIN_PRINCIPAL_2);
    pImpl->selected_quantities.insert(QuantityType::STRAIN_PRINCIPAL_3);

    // Special
    pImpl->selected_quantities.insert(QuantityType::STRAIN_VOLUMETRIC);
}

void QuantitySelector::addDisplacementQuantities() {
    pImpl->selected_quantities.insert(QuantityType::DISPLACEMENT_X);
    pImpl->selected_quantities.insert(QuantityType::DISPLACEMENT_Y);
    pImpl->selected_quantities.insert(QuantityType::DISPLACEMENT_Z);
    pImpl->selected_quantities.insert(QuantityType::DISPLACEMENT_MAGNITUDE);
}

void QuantitySelector::addEnergyQuantities() {
    pImpl->selected_quantities.insert(QuantityType::ENERGY_HOURGLASS_DENSITY);
    pImpl->selected_quantities.insert(QuantityType::ENERGY_STRAIN_DENSITY);
}

} // namespace query
} // namespace kood3plot
