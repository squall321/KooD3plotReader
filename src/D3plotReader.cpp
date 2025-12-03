#include "kood3plot/D3plotReader.hpp"
#include "kood3plot/parsers/ControlDataParser.hpp"
#include "kood3plot/parsers/GeometryParser.hpp"
#include "kood3plot/parsers/StateDataParser.hpp"
#include <stdexcept>
#include <iostream>
#include <thread>
#include <future>
#include <mutex>
#include <algorithm>

namespace kood3plot {

D3plotReader::D3plotReader(const std::string& filepath)
    : filepath_(filepath)
    , is_open_(false) {
}

D3plotReader::~D3plotReader() {
    close();
}

ErrorCode D3plotReader::open() {
    // Initialize file family to discover all related files
    file_family_ = std::make_unique<core::FileFamily>(filepath_);

    // Open the base file
    reader_ = std::make_shared<core::BinaryReader>(filepath_);

    auto err = reader_->open();
    if (err != ErrorCode::SUCCESS) {
        return err;
    }

    // Initialize control data and file format
    init_control_data();

    file_format_.precision = reader_->get_precision();
    file_format_.endian = reader_->get_endian();
    file_format_.word_size = reader_->get_word_size();
    file_format_.version = reader_->get_version();

    is_open_ = true;
    return ErrorCode::SUCCESS;
}

void D3plotReader::close() {
    if (reader_) {
        reader_->close();
    }
    is_open_ = false;
}

bool D3plotReader::is_open() const {
    return is_open_;
}

FileFormat D3plotReader::get_file_format() const {
    return file_format_;
}

const data::ControlData& D3plotReader::get_control_data() const {
    return control_data_;
}

data::Mesh D3plotReader::read_mesh() {
    if (!is_open_) {
        throw std::runtime_error("File not open");
    }

    parsers::GeometryParser parser(reader_, control_data_);
    return parser.parse();
}

std::vector<data::StateData> D3plotReader::read_all_states() {
    if (!is_open_) {
        throw std::runtime_error("File not open");
    }

    std::vector<data::StateData> all_states;

    // Read states from all files in the family
    size_t file_count = file_family_->get_file_count();

    std::cerr << "Reading d3plot states from " << file_count << " file(s)..." << std::endl;

    for (size_t file_idx = 0; file_idx < file_count; ++file_idx) {
        std::string file_path = file_family_->get_file_path(file_idx);

        // Show which file is being read
        std::cerr << "[" << (file_idx + 1) << "/" << file_count << "] Reading: "
                  << file_path.substr(file_path.find_last_of("/\\") + 1) << "..." << std::flush;

        // Create a new reader for each family file
        auto family_reader = std::make_shared<core::BinaryReader>(file_path);

        ErrorCode err;
        if (file_idx == 0) {
            // Base file - already open, use existing reader
            family_reader = reader_;
        } else {
            // Family file (d3plot01, d3plot02, etc.)
            // These files contain only state data, no control/geometry
            err = family_reader->open_family_file(reader_->get_precision(), reader_->get_endian());
            if (err != ErrorCode::SUCCESS) {
                std::cerr << " failed to open" << std::endl;
                // Stop if we can't open a family file
                break;
            }
        }

        // Parse states from this file
        // Family files (file_idx > 0) contain only state data starting at offset 0
        bool is_family_file = (file_idx > 0);
        parsers::StateDataParser state_parser(family_reader, control_data_, is_family_file);

        try {
            size_t before_count = all_states.size();
            std::vector<data::StateData> file_states = state_parser.parse_all();

            // Append states from this file to the collection
            all_states.insert(all_states.end(), file_states.begin(), file_states.end());

            size_t states_in_file = file_states.size();
            std::cerr << " " << states_in_file << " states (total: " << all_states.size() << ")" << std::endl;
        } catch (const std::exception&) {
            std::cerr << " parsing failed" << std::endl;
            // If parsing fails, stop reading more files
            break;
        }

        // Close family reader if it's not the base reader
        if (file_idx != 0) {
            family_reader->close();
        }
    }

    std::cerr << "✓ Completed: " << all_states.size() << " total states loaded" << std::endl;

    return all_states;
}

std::vector<data::StateData> D3plotReader::read_all_states_parallel(size_t num_threads) {
    if (!is_open_) {
        throw std::runtime_error("File not open");
    }

    if (!file_family_) {
        // No file family, just read from base file sequentially
        return read_all_states();
    }

    size_t file_count = file_family_->get_file_count();

    if (file_count <= 1) {
        // Only base file exists, no family files to parallelize
        return read_all_states();
    }

    // Determine number of threads to use
    if (num_threads == 0) {
        num_threads = std::thread::hardware_concurrency();
        if (num_threads == 0) num_threads = 4; // Default fallback
    }

    std::cerr << "Reading d3plot states from " << file_count << " file(s) in PARALLEL using "
              << num_threads << " threads..." << std::endl;

    // Structure to hold results from each file
    struct FileResult {
        size_t file_idx;
        std::vector<data::StateData> states;
        bool success;
        std::string error_msg;
    };

    // Mutex for thread-safe output
    std::mutex output_mutex;

    // Lambda function to read a single family file
    auto read_file = [this, &output_mutex](size_t file_idx) -> FileResult {
        FileResult result;
        result.file_idx = file_idx;
        result.success = false;

        try {
            std::string file_path = file_family_->get_file_path(file_idx);

            // Thread-safe progress output
            {
                std::lock_guard<std::mutex> lock(output_mutex);
                std::cerr << "[" << (file_idx + 1) << "/" << file_family_->get_file_count()
                          << "] Reading: " << file_path.substr(file_path.find_last_of("/\\") + 1)
                          << "..." << std::flush;
            }

            // Create a NEW independent reader for this family file
            auto family_reader = std::make_shared<core::BinaryReader>(file_path);

            // Open as family file (contains only state data, no control/geometry)
            ErrorCode err = family_reader->open_family_file(
                reader_->get_precision(),
                reader_->get_endian()
            );

            if (err != ErrorCode::SUCCESS) {
                result.error_msg = "Failed to open file";
                std::lock_guard<std::mutex> lock(output_mutex);
                std::cerr << " failed to open" << std::endl;
                return result;
            }

            // Parse states from this file
            // This lambda is only called for family files (file_idx >= 1)
            // Family files contain only state data starting at offset 0
            parsers::StateDataParser state_parser(family_reader, control_data_, true);  // is_family_file = true
            result.states = state_parser.parse_all();
            result.success = true;

            // Thread-safe success output
            {
                std::lock_guard<std::mutex> lock(output_mutex);
                std::cerr << " " << result.states.size() << " states" << std::endl;
            }

            // Close the reader (we created a new one for each file in parallel mode)
            family_reader->close();

        } catch (const std::exception& e) {
            result.error_msg = e.what();
            result.success = false;
            std::lock_guard<std::mutex> lock(output_mutex);
            std::cerr << " ERROR: " << e.what() << std::endl;
        } catch (...) {
            result.error_msg = "Unknown error";
            result.success = false;
            std::lock_guard<std::mutex> lock(output_mutex);
            std::cerr << " ERROR: Unknown exception" << std::endl;
        }

        return result;
    };

    // Step 1: Read base file (file_idx 0) sequentially
    std::vector<data::StateData> all_states;

    // Read ONLY the base file using sequential logic
    {
        std::string file_path = file_family_->get_file_path(0);
        std::cerr << "[1/" << file_count << "] Reading: "
                  << file_path.substr(file_path.find_last_of("/\\") + 1) << "..." << std::flush;

        // For base file, reuse existing reader
        auto family_reader = reader_;

        // Create parser
        // Base file (file_idx = 0) may contain states after geometry,
        // but in this dataset the base file is too small for states
        parsers::StateDataParser state_parser(family_reader, control_data_, false);  // is_family_file = false

        try {
            std::vector<data::StateData> file_states = state_parser.parse_all();
            all_states.insert(all_states.end(), file_states.begin(), file_states.end());
            std::cerr << " " << file_states.size() << " states (total: " << all_states.size() << ")" << std::endl;
        } catch (const std::exception& e) {
            std::cerr << " parsing failed: " << e.what() << std::endl;
            throw;
        }
    }

    // Step 2: Read family files (file_idx >= 1) in parallel
    if (file_count > 1) {
        std::vector<std::future<FileResult>> futures;
        futures.reserve(file_count - 1);

        // Launch async tasks for family files only
        for (size_t file_idx = 1; file_idx < file_count; ++file_idx) {
            futures.push_back(std::async(std::launch::async, read_file, file_idx));
        }

        // Collect results
        std::vector<FileResult> results;
        results.reserve(file_count - 1);

        for (auto& future : futures) {
            results.push_back(future.get());
        }

        // Sort results by file index to maintain correct order
        std::sort(results.begin(), results.end(),
                  [](const FileResult& a, const FileResult& b) {
                      return a.file_idx < b.file_idx;
                  });

        // Calculate total size for efficient allocation
        size_t total_states = all_states.size(); // Start with base file states
        for (const auto& result : results) {
            if (result.success) {
                total_states += result.states.size();
            }
        }
        all_states.reserve(total_states);

        // Merge family file states (base file states already in all_states)
        for (const auto& result : results) {
            if (result.success) {
                all_states.insert(all_states.end(), result.states.begin(), result.states.end());
            } else {
                // Stop if any file failed (to match sequential behavior)
                std::cerr << "WARNING: Stopping at file_idx " << result.file_idx
                          << " due to error: " << result.error_msg << std::endl;
                break;
            }
        }
    }

    std::cerr << "✓ Completed: " << all_states.size() << " total states loaded (parallel)" << std::endl;

    return all_states;
}

/* DISABLED PARALLEL IMPLEMENTATION - KEEPFOR FUTURE REFERENCE
std::vector<data::StateData> D3plotReader::read_all_states_parallel_DISABLED(size_t num_threads) {
    // Structure to hold results from each file
    struct FileResult {
        size_t file_idx;
        std::vector<data::StateData> states;
        bool success;
        std::string error_msg;
    };

    // Mutex for thread-safe output
    std::mutex output_mutex;

    // Lambda function to read a single family file (file_idx >= 1)
    auto read_file = [this, &output_mutex](size_t file_idx) -> FileResult {
        FileResult result;
        result.file_idx = file_idx;
        result.success = false;

        try {
            std::string file_path = file_family_->get_file_path(file_idx);

            // Thread-safe progress output
            {
                std::lock_guard<std::mutex> lock(output_mutex);
                std::cerr << "[" << (file_idx + 1) << "/" << file_family_->get_file_count()
                          << "] Reading: " << file_path.substr(file_path.find_last_of("/\\") + 1)
                          << "..." << std::flush;
            }

            // Create a new reader for this family file
            auto family_reader = std::make_shared<core::BinaryReader>(file_path);

            // Open as family file (contains only state data, no control/geometry)
            ErrorCode err = family_reader->open_family_file(
                reader_->get_precision(),
                reader_->get_endian()
            );

            if (err != ErrorCode::SUCCESS) {
                result.error_msg = "Failed to open file";
                std::lock_guard<std::mutex> lock(output_mutex);
                std::cerr << " failed to open" << std::endl;
                return result;
            }

            // Parse states from this file
            // This lambda is only called for family files (file_idx >= 1)
            // Family files contain only state data starting at offset 0
            parsers::StateDataParser state_parser(family_reader, control_data_, true);  // is_family_file = true
            result.states = state_parser.parse_all();
            result.success = true;

            // Thread-safe success output
            {
                std::lock_guard<std::mutex> lock(output_mutex);
                std::cerr << " " << result.states.size() << " states" << std::endl;
            }

            // Close the reader (we created a new one for each file in parallel mode)
            family_reader->close();

        } catch (const std::exception& e) {
            result.error_msg = e.what();
            result.success = false;
            std::lock_guard<std::mutex> lock(output_mutex);
            std::cerr << " ERROR: " << e.what() << std::endl;
        } catch (...) {
            result.error_msg = "Unknown error";
            result.success = false;
            std::lock_guard<std::mutex> lock(output_mutex);
            std::cerr << " ERROR: Unknown exception" << std::endl;
        }

        return result;
    };

    // Launch async tasks for family files (file_idx >= 1)
    std::vector<std::future<FileResult>> futures;
    futures.reserve(family_file_count);

    // Launch tasks for family files only
    for (size_t file_idx = 1; file_idx < file_count; ++file_idx) {
        futures.push_back(std::async(std::launch::async, read_file, file_idx));
    }

    // Collect results maintaining order
    std::vector<FileResult> results;
    results.reserve(family_file_count);

    for (auto& future : futures) {
        results.push_back(future.get());
    }

    // Sort results by file index to maintain correct order
    std::sort(results.begin(), results.end(),
              [](const FileResult& a, const FileResult& b) {
                  return a.file_idx < b.file_idx;
              });

    // Calculate total size for efficient allocation
    size_t total_states = all_states.size(); // Start with base file states
    for (const auto& result : results) {
        if (result.success) {
            total_states += result.states.size();
        }
    }
    all_states.reserve(total_states);

    // Merge family file states (base file states already in all_states)
    for (const auto& result : results) {
        if (result.success) {
            all_states.insert(all_states.end(), result.states.begin(), result.states.end());
        } else {
            // Stop if any file failed (to match sequential behavior)
            std::cerr << "WARNING: Stopping at file_idx " << result.file_idx
                      << " due to error: " << result.error_msg << std::endl;
            break;
        }
    }

    std::cerr << "✓ Completed: " << all_states.size() << " total states loaded (parallel)" << std::endl;

    return all_states;
}
*/  // End of DISABLED PARALLEL IMPLEMENTATION comment block

data::StateData D3plotReader::read_state(size_t state_index) {
    // For now, read all states and return the requested one
    // TODO: Optimize to read only the specific state
    auto states = read_all_states();

    if (state_index >= states.size()) {
        throw std::out_of_range("State index out of range");
    }

    return states[state_index];
}

size_t D3plotReader::get_num_states() const {
    // This would require reading all states
    // For Phase 6, we'll implement a simpler version
    return 0;  // TODO: Implement state counting without full read
}

std::vector<double> D3plotReader::get_time_values() {
    auto states = read_all_states();
    std::vector<double> times;
    times.reserve(states.size());

    for (const auto& state : states) {
        times.push_back(state.time);
    }

    return times;
}

void D3plotReader::init_control_data() {
    parsers::ControlDataParser parser(reader_);
    control_data_ = parser.parse();
}

} // namespace kood3plot
