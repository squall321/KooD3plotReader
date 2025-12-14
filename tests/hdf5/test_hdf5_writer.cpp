#include <gtest/gtest.h>
#include <kood3plot/hdf5/HDF5Writer.hpp>
#include <kood3plot/D3plotReader.hpp>
#include <kood3plot/data/Mesh.hpp>

#include <filesystem>
#include <H5Cpp.h>

namespace fs = std::filesystem;

// Test fixture for HDF5Writer tests
class HDF5WriterTest : public ::testing::Test {
protected:
    void SetUp() override {
        // Clean up any existing test files
        if (fs::exists("test_output.h5")) {
            fs::remove("test_output.h5");
        }
        if (fs::exists("test_mesh.h5")) {
            fs::remove("test_mesh.h5");
        }
    }

    void TearDown() override {
        // Clean up test files after tests
        if (fs::exists("test_output.h5")) {
            fs::remove("test_output.h5");
        }
        if (fs::exists("test_mesh.h5")) {
            fs::remove("test_mesh.h5");
        }
    }
};

// Test 1: Create HDF5 file
TEST_F(HDF5WriterTest, CreateFile) {
    // Create HDF5Writer
    kood3plot::hdf5::HDF5Writer writer("test_output.h5");

    // Check file is open
    EXPECT_TRUE(writer.is_open());

    // Close file
    writer.close();
    EXPECT_FALSE(writer.is_open());

    // Verify file exists
    EXPECT_TRUE(fs::exists("test_output.h5"));

    // Verify file is valid HDF5
    try {
        H5::H5File file("test_output.h5", H5F_ACC_RDONLY);

        // Check format attribute
        H5::Attribute attr = file.openAttribute("format");
        H5::StrType str_type = attr.getStrType();
        std::string format_str;
        attr.read(str_type, format_str);

        EXPECT_EQ(format_str.substr(0, 14), "KooD3plot HDF5");

        // Check groups exist
        EXPECT_NO_THROW(file.openGroup("/mesh"));
        EXPECT_NO_THROW(file.openGroup("/states"));

    } catch (const H5::Exception& e) {
        FAIL() << "HDF5 file validation failed: " << e.getDetailMsg();
    }
}

// Test 2: Write simple mesh
TEST_F(HDF5WriterTest, WriteSimpleMesh) {
    // Create simple test mesh
    kood3plot::Mesh mesh;

    // Add 4 nodes (simple tetrahedron)
    mesh.nodes.push_back({0.0, 0.0, 0.0});
    mesh.nodes.push_back({1.0, 0.0, 0.0});
    mesh.nodes.push_back({0.0, 1.0, 0.0});
    mesh.nodes.push_back({0.0, 0.0, 1.0});

    // Add 1 solid element (8-node hex, but we'll use tetrahedron nodes)
    kood3plot::Solid solid;
    solid.nodes[0] = 0;
    solid.nodes[1] = 1;
    solid.nodes[2] = 2;
    solid.nodes[3] = 3;
    solid.nodes[4] = 0;  // Degenerate (repeat nodes for tet in hex format)
    solid.nodes[5] = 1;
    solid.nodes[6] = 2;
    solid.nodes[7] = 3;
    solid.part_id = 1;
    mesh.solids.push_back(solid);

    // Write mesh to HDF5
    kood3plot::hdf5::HDF5Writer writer("test_mesh.h5");
    EXPECT_NO_THROW(writer.write_mesh(mesh));
    writer.close();

    // Verify mesh was written
    EXPECT_TRUE(fs::exists("test_mesh.h5"));

    // Read back and verify
    try {
        H5::H5File file("test_mesh.h5", H5F_ACC_RDONLY);
        H5::Group mesh_group = file.openGroup("/mesh");

        // Check metadata
        H5::Attribute attr_nodes = mesh_group.openAttribute("num_nodes");
        int num_nodes;
        attr_nodes.read(H5::PredType::NATIVE_INT, &num_nodes);
        EXPECT_EQ(num_nodes, 4);

        H5::Attribute attr_solids = mesh_group.openAttribute("num_solids");
        int num_solids;
        attr_solids.read(H5::PredType::NATIVE_INT, &num_solids);
        EXPECT_EQ(num_solids, 1);

        // Check nodes dataset
        H5::DataSet nodes_dataset = mesh_group.openDataSet("nodes");
        H5::DataSpace nodes_space = nodes_dataset.getSpace();

        int ndims = nodes_space.getSimpleExtentNdims();
        EXPECT_EQ(ndims, 2);

        hsize_t dims[2];
        nodes_space.getSimpleExtentDims(dims);
        EXPECT_EQ(dims[0], 4);  // 4 nodes
        EXPECT_EQ(dims[1], 3);  // x, y, z

        // Read nodes data
        std::vector<double> coords(4 * 3);
        nodes_dataset.read(coords.data(), H5::PredType::NATIVE_DOUBLE);

        // Verify first node (0, 0, 0)
        EXPECT_DOUBLE_EQ(coords[0], 0.0);
        EXPECT_DOUBLE_EQ(coords[1], 0.0);
        EXPECT_DOUBLE_EQ(coords[2], 0.0);

        // Verify second node (1, 0, 0)
        EXPECT_DOUBLE_EQ(coords[3], 1.0);
        EXPECT_DOUBLE_EQ(coords[4], 0.0);
        EXPECT_DOUBLE_EQ(coords[5], 0.0);

        // Check solid connectivity dataset
        H5::DataSet solid_conn_dataset = mesh_group.openDataSet("solid_connectivity");
        H5::DataSpace solid_space = solid_conn_dataset.getSpace();

        hsize_t solid_dims[2];
        solid_space.getSimpleExtentDims(solid_dims);
        EXPECT_EQ(solid_dims[0], 1);  // 1 solid
        EXPECT_EQ(solid_dims[1], 8);  // 8 nodes per solid

        // Read connectivity
        std::vector<int> connectivity(8);
        solid_conn_dataset.read(connectivity.data(), H5::PredType::NATIVE_INT);
        EXPECT_EQ(connectivity[0], 0);
        EXPECT_EQ(connectivity[1], 1);
        EXPECT_EQ(connectivity[2], 2);
        EXPECT_EQ(connectivity[3], 3);

    } catch (const H5::Exception& e) {
        FAIL() << "HDF5 mesh verification failed: " << e.getDetailMsg();
    }
}

// Test 3: Write larger mesh (performance test)
TEST_F(HDF5WriterTest, WriteLargeMesh) {
    // Create larger test mesh (10k nodes, 8k elements)
    kood3plot::Mesh mesh;

    // Generate grid of nodes (100 x 100 x 1 = 10k nodes)
    const int nx = 100;
    const int ny = 100;
    for (int j = 0; j < ny; ++j) {
        for (int i = 0; i < nx; ++i) {
            mesh.nodes.push_back({
                static_cast<double>(i),
                static_cast<double>(j),
                0.0
            });
        }
    }

    // Generate hex elements (99 x 99 = 9801 elements)
    for (int j = 0; j < ny - 1; ++j) {
        for (int i = 0; i < nx - 1; ++i) {
            kood3plot::Solid solid;
            int n0 = j * nx + i;
            int n1 = j * nx + (i + 1);
            int n2 = (j + 1) * nx + (i + 1);
            int n3 = (j + 1) * nx + i;

            // Create degenerate hex (actually a quad)
            solid.nodes[0] = n0;
            solid.nodes[1] = n1;
            solid.nodes[2] = n2;
            solid.nodes[3] = n3;
            solid.nodes[4] = n0;
            solid.nodes[5] = n1;
            solid.nodes[6] = n2;
            solid.nodes[7] = n3;
            solid.part_id = 1;

            mesh.solids.push_back(solid);
        }
    }

    std::cout << "Writing large mesh: " << mesh.nodes.size() << " nodes, "
              << mesh.solids.size() << " solids\n";

    // Write mesh
    kood3plot::hdf5::HDF5Writer writer("test_mesh.h5");
    EXPECT_NO_THROW(writer.write_mesh(mesh));
    writer.close();

    // Check file size
    auto file_size = fs::file_size("test_mesh.h5");
    std::cout << "HDF5 file size: " << file_size / 1024 << " KB\n";

    // Verify compression is working (file should be < uncompressed size)
    // Uncompressed: 10k nodes * 3 * 8 bytes + 9.8k solids * 8 * 4 bytes = ~240KB + ~314KB = ~554KB
    // With compression, should be significantly smaller
    size_t uncompressed_estimate =
        mesh.nodes.size() * 3 * sizeof(double) +
        mesh.solids.size() * 8 * sizeof(int);

    std::cout << "Uncompressed estimate: " << uncompressed_estimate / 1024 << " KB\n";
    std::cout << "Compression ratio: "
              << (100.0 * file_size / uncompressed_estimate) << "%\n";

    // File should be smaller than uncompressed (with HDF5 overhead, expect 60-90%)
    EXPECT_LT(file_size, uncompressed_estimate);
}

// Test 4: RAII behavior (file closes automatically)
TEST_F(HDF5WriterTest, RAIIBehavior) {
    {
        kood3plot::hdf5::HDF5Writer writer("test_output.h5");
        EXPECT_TRUE(writer.is_open());
        // Destructor should close file automatically
    }

    // File should exist and be valid
    EXPECT_TRUE(fs::exists("test_output.h5"));

    // Should be able to open file
    EXPECT_NO_THROW({
        H5::H5File file("test_output.h5", H5F_ACC_RDONLY);
    });
}

// Main function
int main(int argc, char** argv) {
    ::testing::InitGoogleTest(&argc, argv);
    return RUN_ALL_TESTS();
}
