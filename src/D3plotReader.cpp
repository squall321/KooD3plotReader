#include "kood3plot/D3plotReader.hpp"
#include "kood3plot/parsers/ControlDataParser.hpp"
#include "kood3plot/parsers/GeometryParser.hpp"
#include "kood3plot/parsers/StateDataParser.hpp"
#include <stdexcept>
#include <iostream>
#include <thread>
#include <atomic>
#include <mutex>
#include <algorithm>
#include <iterator>
#include <system_error>

namespace kood3plot {

namespace {

std::string file_name_of(const std::string& path) {
    return path.substr(path.find_last_of("/\\") + 1);
}

// LS-DYNA 는 가족 파일을 512 워드 단위로 채운다 — 이보다 짧은 꼬리는 패딩이다.
constexpr size_t kPaddingWords = 512;

// 가족 파일 하나를 다 읽은 뒤 끝 모양을 판정한다. 중간 파일이 상태 도중 끝났으면
// 예외(뒤 파일의 상태와 시간이 어긋난다), 마지막 파일이면 경고 문구를 돌려준다
// (해석이 쓰는 도중 끝났고 앞 상태는 온전하다). 문제가 없으면 빈 문자열.
// 실덱 근거: 운영 덱(249 파일)은 모든 파일이 EOF 표지로 끝나고, 해석이 쓰다 끝난
// 덱은 마지막 파일만 덜 써진 상태를 단다. D3plotWriter 는 표지 없이 상태 경계에서
// 끊는다(꼬리 0). 기본 파일(d3plot)은 상태 시작 위치가 덱마다 달라 판정하지 않는다.
std::string check_family_tail(const parsers::StateDataParser& parser, size_t file_idx,
                              size_t file_count, const std::string& path, size_t n_states) {
    using StopReason = parsers::StateDataParser::StopReason;
    if (file_idx == 0) return "";
    if (parser.stop_reason() == StopReason::EOF_MARKER ||
        parser.trailing_words() < kPaddingWords) return "";
    const std::string msg = file_name_of(path) + ": 상태 " + std::to_string(n_states) +
        "개 뒤에 " + std::to_string(parser.trailing_words()) +
        " 워드가 남았는데 EOF 표지(-999999)가 아니다 — 상태 하나를 다 쓰지 못하고 끝났다";
    if (file_idx + 1 < file_count) {
        throw std::runtime_error(msg + ". 중간 가족 파일이라 잘렸거나 손상됐다 — "
                                 "뒤 파일의 상태와 시간이 어긋나므로 읽기를 멈춘다");
    }
    return msg + ". 마지막 파일이라 해석이 쓰는 도중 끝난 것으로 보고 덜 써진 상태 하나를 버린다";
}

void check_family_gap(const core::FileFamily& family) {
    if (!family.gap_description().empty()) {
        throw std::runtime_error("d3plot 가족 파일 번호에 구멍이 있다 — " +
                                 family.gap_description() +
                                 ". 그 뒤 상태가 통째로 빠지므로 읽기를 멈춘다");
    }
}

std::string read_error_message(const std::string& path, const std::exception& e) {
    if (dynamic_cast<const std::bad_alloc*>(&e)) {
        return file_name_of(path) + ": 메모리 부족(std::bad_alloc) — 상태 전부를 메모리에 "
               "올리는 경로라 덱의 상태 데이터만큼 메모리가 필요하다";
    }
    const std::string prefix = file_name_of(path) + ":";
    const std::string what = e.what();
    // 잘림 판정 문구는 이미 파일 이름으로 시작한다
    return what.compare(0, prefix.size(), prefix) == 0 ? what : prefix + " " + what;
}

}  // namespace

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

    check_family_gap(*file_family_);

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
                // 여기서 멈추고 읽은 만큼 돌려주면 뒤 상태가 빠진 채 '성공' 한다
                throw std::runtime_error(file_name_of(file_path) +
                                         " 을 열지 못했다 — 그 뒤 상태가 빠지므로 읽기를 멈춘다");
            }
        }

        // Parse states from this file
        // Family files (file_idx > 0) contain only state data starting at offset 0
        bool is_family_file = (file_idx > 0);
        parsers::StateDataParser state_parser(family_reader, control_data_, is_family_file);

        std::vector<data::StateData> file_states;
        try {
            file_states = state_parser.parse_all();
        } catch (const std::exception& e) {
            std::cerr << " parsing failed" << std::endl;
            throw std::runtime_error(read_error_message(file_path, e));
        }
        const std::string tail_warning = check_family_tail(
            state_parser, file_idx, file_count, file_path, file_states.size());

        // Append states from this file to the collection
        all_states.insert(all_states.end(), file_states.begin(), file_states.end());

        size_t states_in_file = file_states.size();
        std::cerr << " " << states_in_file << " states (total: " << all_states.size() << ")" << std::endl;
        if (!tail_warning.empty()) std::cerr << "WARNING: " << tail_warning << std::endl;

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

    check_family_gap(*file_family_);

    // Determine number of threads to use
    if (num_threads == 0) {
        num_threads = std::thread::hardware_concurrency();
        if (num_threads == 0) num_threads = 4; // Default fallback
    }
    const size_t n_workers = std::min(num_threads, file_count - 1);

    std::cerr << "Reading d3plot states from " << file_count << " file(s) in PARALLEL using "
              << n_workers << " threads..." << std::endl;

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
    auto read_file = [this, &output_mutex, file_count](size_t file_idx) -> FileResult {
        FileResult result;
        result.file_idx = file_idx;
        result.success = false;

        std::string file_path = file_family_->get_file_path(file_idx);
        try {
            // Thread-safe progress output
            {
                std::lock_guard<std::mutex> lock(output_mutex);
                std::cerr << "[" << (file_idx + 1) << "/" << file_count
                          << "] Reading: " << file_name_of(file_path)
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
                result.error_msg = file_name_of(file_path) +
                                   " 을 열지 못했다 — 그 뒤 상태가 빠지므로 읽기를 멈춘다";
                std::lock_guard<std::mutex> lock(output_mutex);
                std::cerr << " failed to open" << std::endl;
                return result;
            }

            // Parse states from this file
            // This lambda is only called for family files (file_idx >= 1)
            // Family files contain only state data starting at offset 0
            parsers::StateDataParser state_parser(family_reader, control_data_, true);  // is_family_file = true
            result.states = state_parser.parse_all();
            const std::string tail_warning = check_family_tail(
                state_parser, file_idx, file_count, file_path, result.states.size());
            result.success = true;

            // Thread-safe success output
            {
                std::lock_guard<std::mutex> lock(output_mutex);
                std::cerr << " " << result.states.size() << " states" << std::endl;
                if (!tail_warning.empty()) std::cerr << "WARNING: " << tail_warning << std::endl;
            }

            // Close the reader (we created a new one for each file in parallel mode)
            family_reader->close();

        } catch (const std::exception& e) {
            result.states.clear();
            result.error_msg = read_error_message(file_path, e);
            result.success = false;
            std::lock_guard<std::mutex> lock(output_mutex);
            std::cerr << " ERROR: " << result.error_msg << std::endl;
        } catch (...) {
            result.states.clear();
            result.error_msg = file_name_of(file_path) + ": 알 수 없는 예외";
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
                  << file_name_of(file_path) << "..." << std::flush;

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
            std::cerr << " parsing failed" << std::endl;
            throw std::runtime_error(read_error_message(file_path, e));
        }
    }

    // Step 2: Read family files (file_idx >= 1) — 작업자 n_workers 개가 나눠 읽는다.
    // 🔴 파일마다 스레드를 띄우면 안 된다 — 249 파일 덱에서 주소 공간 상한(12 GiB)
    //    아래 std::system_error 가 잡히지 않아 SIGABRT(rc -6) 로 죽었다
    //    (2026-10-28 DynaForge 보고 K-3). 호출 스레드도 작업자 하나로 쓰고, 스레드를
    //    더 못 띄우면 띄운 만큼으로 계속한다.
    std::vector<FileResult> results(file_count - 1);
    std::atomic<size_t> next_idx{1};
    // 한 파일이 실패하면 어차피 전체가 실패다 — 남은 파일을 더 집지 않는다
    // (메모리 부족이면 남은 작업자가 파일마다 같은 오류를 내며 시간만 쓴다).
    std::atomic<bool> any_failed{false};
    auto worker = [&]() {
        for (size_t i = next_idx++; i < file_count && !any_failed; i = next_idx++) {
            results[i - 1] = read_file(i);
            if (!results[i - 1].success) any_failed = true;
        }
    };
    std::vector<std::thread> pool;
    for (size_t t = 1; t < n_workers; ++t) {
        try {
            pool.emplace_back(worker);
        } catch (const std::system_error& e) {
            std::cerr << "WARNING: 읽기 스레드를 " << (pool.size() + 1)
                      << "개만 띄웠다 (" << e.what() << ")" << std::endl;
            break;
        }
    }
    worker();
    for (auto& t : pool) t.join();

    // 한 파일이라도 실패하면 읽은 만큼 돌려주지 않는다 — 시간 축에 구멍이 난 채
    // '성공' 하면 피크·시계열이 조용히 틀린다. 빨리 멈춰 읽지 않은 파일은
    // 사유가 비어 있으니 사유가 있는 첫 실패를 낸다.
    if (any_failed) {
        for (const auto& result : results) {
            if (!result.success && !result.error_msg.empty()) {
                throw std::runtime_error(result.error_msg);
            }
        }
    }

    size_t total_states = all_states.size(); // Start with base file states
    for (const auto& result : results) {
        total_states += result.states.size();
    }
    all_states.reserve(total_states);

    // Merge family file states (base file states already in all_states).
    // 🔴 복사하면 안 된다 — 상태 배열은 덱 하나가 수십 GB 다. 복사하면 합치는
    //    동안 같은 데이터가 두 벌 존재해 피크 메모리가 정확히 2배가 된다
    //    (실측: 400상태 2.6 GB 짜리 덱에서 피크 5.5 GB). 이동으로 버퍼를
    //    넘기고, 넘긴 사본은 바로 비워 메모리를 돌려준다.
    for (auto& result : results) {
        all_states.insert(all_states.end(),
                          std::make_move_iterator(result.states.begin()),
                          std::make_move_iterator(result.states.end()));
        std::vector<data::StateData>().swap(result.states);   // 즉시 해제
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
    // Ensure state cache is initialized
    if (!states_cached_) {
        init_state_cache();
    }

    if (state_index >= cached_num_states_) {
        throw std::out_of_range("State index out of range");
    }

    // Load full cache on first access
    if (!full_cache_loaded_) {
        load_full_cache();
    }

    return cached_states_[state_index];
}

void D3plotReader::load_full_cache() const {
    if (full_cache_loaded_) {
        return;
    }

    auto& self = const_cast<D3plotReader&>(*this);
    cached_states_ = self.read_all_states();
    full_cache_loaded_ = true;
}

size_t D3plotReader::get_num_states() const {
    if (!states_cached_) {
        init_state_cache();
    }
    return cached_num_states_;
}

std::vector<double> D3plotReader::get_time_values() {
    if (!states_cached_) {
        init_state_cache();
    }
    return cached_time_values_;
}

void D3plotReader::init_control_data() {
    parsers::ControlDataParser parser(reader_);
    control_data_ = parser.parse();
}

void D3plotReader::init_state_cache() const {
    if (states_cached_) {
        return;
    }

    // Cast away const for file reading operations
    auto& self = const_cast<D3plotReader&>(*this);

    cached_time_values_.clear();
    cached_num_states_ = 0;

    // Scan all files to count states and get time values (lightweight scan)
    check_family_gap(*file_family_);
    size_t file_count = file_family_->get_file_count();

    for (size_t file_idx = 0; file_idx < file_count; ++file_idx) {
        std::string file_path = file_family_->get_file_path(file_idx);

        // Create reader for this file
        std::shared_ptr<core::BinaryReader> family_reader;
        if (file_idx == 0) {
            family_reader = self.reader_;
        } else {
            family_reader = std::make_shared<core::BinaryReader>(file_path);
            // Family files need open_family_file with precision/endian from base file
            if (family_reader->open_family_file(self.reader_->get_precision(),
                                                 self.reader_->get_endian()) != ErrorCode::SUCCESS) {
                // 건너뛰면 상태 수가 전체 읽기(read_all_states)와 갈린다
                throw std::runtime_error(file_name_of(file_path) +
                                         " 을 열지 못했다 — 그 뒤 상태가 빠지므로 읽기를 멈춘다");
            }
        }

        // Use StateDataParser to scan states (time values only)
        // For family files (d3plot01, etc.), set is_family_file=true so parser starts at offset 0
        bool is_family = (file_idx > 0);
        parsers::StateDataParser parser(family_reader, self.control_data_, is_family);
        auto file_states = parser.parse_time_values_only();
        // 경고는 전체 읽기가 낸다 — 여기서는 잘림 오류만 같은 규칙으로 판정한다
        check_family_tail(parser, file_idx, file_count, file_path, file_states.size());

        cached_time_values_.insert(cached_time_values_.end(),
                                   file_states.begin(), file_states.end());

        if (file_idx != 0) {
            family_reader->close();
        }
    }

    cached_num_states_ = cached_time_values_.size();
    states_cached_ = true;
}

} // namespace kood3plot
