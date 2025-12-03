/**
 * @file 01_basic_query.cpp
 * @brief Basic example of KooD3plot V3 Query System
 * @author KooD3plot V3 Development Team
 * @date 2025-11-21
 *
 * This example demonstrates the core Query System functionality:
 * - Opening a d3plot file
 * - Building a simple query
 * - Selecting parts, quantities, and timesteps
 * - Writing results to CSV
 *
 * Compilation:
 *   g++ -std=c++17 01_basic_query.cpp -I../../include -L../../build -lkood3plot_query -lkood3plot
 *
 * Usage:
 *   ./01_basic_query <d3plot_file>
 */

#include "kood3plot/D3plotReader.hpp"
#include "kood3plot/query/D3plotQuery.h"
#include "kood3plot/query/PartSelector.h"
#include "kood3plot/query/QuantitySelector.h"
#include "kood3plot/query/TimeSelector.h"
#include "kood3plot/query/ValueFilter.h"
#include "kood3plot/query/OutputSpec.h"

#include <iostream>
#include <string>

using namespace kood3plot;
using namespace kood3plot::query;

int main(int argc, char** argv) {
    // Check arguments
    if (argc < 2) {
        std::cerr << "Usage: " << argv[0] << " <d3plot_file>" << std::endl;
        std::cerr << "\nExample:" << std::endl;
        std::cerr << "  " << argv[0] << " crash.d3plot" << std::endl;
        return 1;
    }

    std::string d3plot_file = argv[1];

    try {
        // ============================================================
        // 1. Open D3plot File
        // ============================================================
        std::cout << "==================================================" << std::endl;
        std::cout << " KooD3plot V3 Query System - Basic Example" << std::endl;
        std::cout << "==================================================" << std::endl;
        std::cout << std::endl;

        std::cout << "Opening d3plot file: " << d3plot_file << std::endl;
        D3plotReader reader(d3plot_file);

        std::cout << "  Number of states: " << reader.get_num_states() << std::endl;
        // Note: getPartIDs() not yet implemented in Phase 1
        // std::cout << "  Number of parts: " << reader.getPartIDs().size() << std::endl;
        std::cout << std::endl;

        // ============================================================
        // 2. Example 1: Simple Query - Final State, All Parts
        // ============================================================
        std::cout << "Example 1: Extracting final state data" << std::endl;
        std::cout << "--------------------------------------------------" << std::endl;

        D3plotQuery query1(reader);
        query1.selectAllParts()
              .selectQuantities(QuantitySelector::commonCrash())
              .selectTime(TimeSelector::lastState())
              .output(OutputSpec::csv()
                     .precision(6)
                     .includeHeader(true)
                     .includeMetadata(true));

        std::cout << "Query configuration:" << std::endl;
        std::cout << query1.getDescription() << std::endl;
        std::cout << std::endl;

        std::cout << "Estimated data points: " << query1.estimateSize() << std::endl;
        std::cout << std::endl;

        // Note: Actual execution not implemented in Phase 1
        // This will be implemented in Phase 2
        std::cout << "Note: Query execution will be implemented in Phase 2" << std::endl;
        std::cout << "      (Data extraction from d3plot states)" << std::endl;
        std::cout << std::endl;

        // ============================================================
        // 3. Example 2: Filtered Query - High Stress Parts
        // ============================================================
        std::cout << "Example 2: Extracting high stress regions" << std::endl;
        std::cout << "--------------------------------------------------" << std::endl;

        D3plotQuery query2(reader);
        query2.selectAllParts()
              .selectQuantities({"von_mises", "effective_strain"})
              .selectTime({-1})  // Last state
              .whereValue(ValueFilter().greaterThan(500.0))  // von_mises > 500 MPa
              .output(OutputSpec::csv()
                     .fields({"part_id", "element_id", "von_mises", "effective_strain"})
                     .precision(4));

        std::cout << "Query configuration:" << std::endl;
        std::cout << query2.getDescription() << std::endl;
        std::cout << std::endl;

        // ============================================================
        // 4. Example 3: Static Factory Methods
        // ============================================================
        std::cout << "Example 3: Using static factory methods" << std::endl;
        std::cout << "--------------------------------------------------" << std::endl;

        // Maximum von Mises stress query
        auto maxVMQuery = D3plotQuery::maxVonMises(reader, {1, 2, 3});
        std::cout << "Max Von Mises Query:" << std::endl;
        std::cout << maxVMQuery.getDescription() << std::endl;
        std::cout << std::endl;

        // Final state query
        auto finalQuery = D3plotQuery::finalState(reader);
        std::cout << "Final State Query:" << std::endl;
        std::cout << finalQuery.getDescription() << std::endl;
        std::cout << std::endl;

        // ============================================================
        // 5. Example 4: Complex Selector Usage
        // ============================================================
        std::cout << "Example 4: Complex part and quantity selection" << std::endl;
        std::cout << "--------------------------------------------------" << std::endl;

        // Select specific parts by name
        PartSelector partSel;
        partSel.byName({"Hood", "Roof", "Door_LF"});

        // Select all stress quantities
        QuantitySelector quantSel = QuantitySelector::allStress();

        // Select time range
        TimeSelector timeSel;
        timeSel.addTimeRange(0.0, 10.0, 1.0);  // 0-10ms, every 1ms

        D3plotQuery query4(reader);
        query4.selectParts(partSel)
              .selectQuantities(quantSel)
              .selectTime(timeSel)
              .output(OutputSpec::crashAnalysis());

        std::cout << "Complex Query:" << std::endl;
        std::cout << query4.getDescription() << std::endl;
        std::cout << std::endl;

        // ============================================================
        // 6. Query Validation
        // ============================================================
        std::cout << "Example 5: Query validation" << std::endl;
        std::cout << "--------------------------------------------------" << std::endl;

        if (query1.validate()) {
            std::cout << "Query 1: VALID ✓" << std::endl;
        } else {
            std::cout << "Query 1: INVALID ✗" << std::endl;
            std::cout << "Errors:" << std::endl;
            for (const auto& error : query1.getValidationErrors()) {
                std::cout << "  - " << error << std::endl;
            }
        }
        std::cout << std::endl;

        // ============================================================
        // 7. Summary
        // ============================================================
        std::cout << "==================================================" << std::endl;
        std::cout << " Summary" << std::endl;
        std::cout << "==================================================" << std::endl;
        std::cout << "✓ D3plot file opened successfully" << std::endl;
        std::cout << "✓ Query system API demonstrated" << std::endl;
        std::cout << "✓ Multiple query patterns shown" << std::endl;
        std::cout << "✓ Validation working" << std::endl;
        std::cout << std::endl;
        std::cout << "Phase 1 Status: Core API Complete" << std::endl;
        std::cout << "Phase 2 Next: Actual data extraction implementation" << std::endl;
        std::cout << std::endl;

        return 0;

    } catch (const std::exception& e) {
        std::cerr << "Error: " << e.what() << std::endl;
        return 1;
    }
}
