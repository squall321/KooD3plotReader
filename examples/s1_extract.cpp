// d3plot 에서 S1 경량 추출본(겉면 변위·응력·삭제·게이트·자세, HDF5)을 만드는 도구 — DynaForge 계약 C-3
/**
 * 사용:
 *   s1_extract <d3plot> --output <s1.h5> [--floor-part N] [--exclude-parts a,b]
 *              [--units "mm, t, s, MPa"] [--state-step N] [--time-window t0,t1]
 *              [--precision q16|float32]
 *
 * 계약: docs/s1_extractor_2026-10/contract-c3-s1-draft.md (스키마 kood3plot.s1 판 1)
 * 상태를 하나씩 두 번 읽는다 — 1차는 시각·스케일·게이트·자세, 2차는 고른 상태 쓰기.
 * 종료 코드: 0 = 완성(경고는 루트 속성 warnings 와 stderr), 1 = 실패(파일을 남기지 않는다).
 */
#include "kood3plot/D3plotReader.hpp"
#include "kood3plot/analysis/UnifiedConfigParser.hpp"
#include "kood3plot/data/NodeKinematics.hpp"
#include "kood3plot/s1/S1Core.hpp"

#include <hdf5.h>

#include <algorithm>
#include <cctype>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <ctime>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <limits>
#include <map>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

#ifndef KOOD3PLOT_GIT_COMMIT
#define KOOD3PLOT_GIT_COMMIT "unknown"
#endif

using namespace kood3plot;
namespace fs = std::filesystem;

namespace {

constexpr int kSchemaVersion = 1;
// 상태 배열 청크 [64 상태, 256 항목, …] — 시간 쪽으로 길게 잡아야 deflate(창 32 KB)가 이웃 상태의
// 중복을 본다. [16 상태, 전 항목] 이면 한 상태(운영 덱 138 KB)가 창보다 커서 못 본다
// (운영 덱 실측: 변위 581 → 344 MB, von Mises 208 → 198 MB).
constexpr hsize_t kChunkStates = 64;
constexpr hsize_t kChunkItems = 256;

const char* kSurfaceRule =
    "대상은 제외 파트를 뺀 솔리드. 요소 꼴은 고유 절점 8=육면체, 4=사면체(배치 무관), 6=쐐기, 5=피라미드, "
    "그 밖은 육면체 6면 고리에서 이어진 같은 절점을 지운 고리가 닫힌 다면체일 때 쐐기·피라미드로 받고 아니면 실패. "
    "면 순서는 육면체 (0,3,2,1)(4,5,6,7)(0,1,5,4)(1,2,6,5)(2,3,7,6)(3,0,4,7), 사면체 (0,3,2)(0,2,1)(0,1,3)(1,2,3) — "
    "양의 야코비안에서 바깥 방향, 부호 부피가 음수인 요소는 뒤집는다. 고유 절점 3개 미만인 고리는 버린다. "
    "정렬한 고유 절점을 열쇠로 대상 솔리드 전체에서 한 번만 나온 면이 겉면, 셋 이상이면 실패(StepForge core/deck_surface.py 꼴).";

// ── 인자 ────────────────────────────────────────────────────
struct Options {
    std::string d3plot;
    std::string output;
    int floor_part = -1;
    std::set<int32_t> excluded;
    std::string units = "deck_units";
    int state_step = 1;
    double t0 = -std::numeric_limits<double>::infinity();
    double t1 = std::numeric_limits<double>::infinity();
    bool float32 = false;
};

std::vector<std::string> splitComma(const std::string& s) {
    std::vector<std::string> out;
    std::stringstream ss(s);
    for (std::string t; std::getline(ss, t, ',');) {
        if (!t.empty()) out.push_back(t);
    }
    return out;
}

Options parseArgs(int argc, char** argv) {
    Options o;
    for (int i = 1; i < argc; ++i) {
        const std::string a = argv[i];
        auto next = [&]() -> std::string {
            if (i + 1 >= argc) throw std::runtime_error(a + " 뒤에 값이 없다");
            return argv[++i];
        };
        if (a == "--output") o.output = next();
        else if (a == "--floor-part") o.floor_part = std::stoi(next());
        else if (a == "--exclude-parts") {
            for (const auto& t : splitComma(next())) o.excluded.insert(std::stoi(t));
        } else if (a == "--units") o.units = next();
        else if (a == "--state-step") o.state_step = std::max(1, std::stoi(next()));
        else if (a == "--time-window") {
            const auto v = splitComma(next());
            if (v.size() != 2) throw std::runtime_error("--time-window 은 t0,t1 이다");
            o.t0 = std::stod(v[0]);
            o.t1 = std::stod(v[1]);
        } else if (a == "--precision") {
            const std::string p = next();
            if (p == "float32") o.float32 = true;
            else if (p != "q16") throw std::runtime_error("--precision 은 q16 또는 float32");
        } else if (a == "-h" || a == "--help") {
            std::cout << "s1_extract <d3plot> --output <s1.h5> [--floor-part N] [--exclude-parts a,b] "
                         "[--units STR] [--state-step N] [--time-window t0,t1] [--precision q16|float32]\n";
            std::exit(0);
        } else if (!a.empty() && a[0] == '-') {
            throw std::runtime_error("모르는 인자: " + a);
        } else if (o.d3plot.empty()) {
            o.d3plot = a;
        } else {
            throw std::runtime_error("d3plot 경로가 둘이다: " + a);
        }
    }
    if (o.d3plot.empty() || o.output.empty()) throw std::runtime_error("d3plot 과 --output 이 필요하다");
    if (o.floor_part >= 0) o.excluded.insert(o.floor_part);
    // units 는 「길이, 질량, 시간, 응력」 넷을 ", " 로 이은 꼴로 정규화한다 — 같은 단위가 표본마다
    // "mm, t, s, MPa" · "mm,t,s,MPa" 로 갈렸다(post_analyze --s1-opts 는 빈칸을 못 넘긴다)
    if (o.units != "deck_units") {
        std::string norm;
        for (std::string t : splitComma(o.units)) {
            t.erase(std::remove_if(t.begin(), t.end(), [](unsigned char c) { return std::isspace(c); }), t.end());
            if (!t.empty()) norm += (norm.empty() ? "" : ", ") + t;
        }
        o.units = norm;
    }
    return o;
}

// ── 작은 도우미 ─────────────────────────────────────────────
std::string shellQuote(const std::string& s) {
    std::string q = "'";
    for (char c : s) q += (c == '\'') ? std::string("'\\''") : std::string(1, c);
    return q + "'";
}

std::string runCapture(const std::string& cmd) {
    std::string out;
    if (FILE* p = popen(cmd.c_str(), "r")) {
        char buf[256];
        while (std::fgets(buf, sizeof(buf), p)) out += buf;
        pclose(p);
    }
    const auto sp = out.find(' ');
    return sp == std::string::npos ? out : out.substr(0, sp);
}

std::string isoNowUtc() {
    const std::time_t t = std::time(nullptr);
    char buf[32];
    std::strftime(buf, sizeof(buf), "%Y-%m-%dT%H:%M:%SZ", std::gmtime(&t));
    return buf;
}

// ── 곁파일 JSON ─────────────────────────────────────────────
std::string jstr(const std::string& v) {
    std::string o = "\"";
    for (unsigned char c : v) {
        if (c == '"' || c == '\\') { o += '\\'; o += static_cast<char>(c); }
        else if (c == '\n') o += "\\n";
        else if (c < 0x20) { char b[8]; std::snprintf(b, sizeof(b), "\\u%04x", c); o += b; }
        else o += static_cast<char>(c);
    }
    return o + "\"";
}

std::string jnum(double v) {
    if (!std::isfinite(v)) return "null";
    char b[40];
    std::snprintf(b, sizeof(b), "%.17g", v);
    return b;
}

// ── HDF5 쓰기 ───────────────────────────────────────────────
void h5check(herr_t r, const char* what) {
    if (r < 0) throw std::runtime_error(std::string("HDF5 실패: ") + what);
}

hid_t h5check_id(hid_t id, const char* what) {
    if (id < 0) throw std::runtime_error(std::string("HDF5 실패: ") + what);
    return id;
}

void attrStr(hid_t obj, const std::string& name, const std::string& value) {
    hid_t t = H5Tcopy(H5T_C_S1);
    H5Tset_size(t, H5T_VARIABLE);
    H5Tset_cset(t, H5T_CSET_UTF8);
    hid_t sp = H5Screate(H5S_SCALAR);
    hid_t a = h5check_id(H5Acreate2(obj, name.c_str(), t, sp, H5P_DEFAULT, H5P_DEFAULT), name.c_str());
    const char* p = value.c_str();
    h5check(H5Awrite(a, t, &p), name.c_str());
    H5Aclose(a);
    H5Sclose(sp);
    H5Tclose(t);
}

void attrStrArray(hid_t obj, const std::string& name, const std::vector<std::string>& values) {
    hid_t t = H5Tcopy(H5T_C_S1);
    H5Tset_size(t, H5T_VARIABLE);
    H5Tset_cset(t, H5T_CSET_UTF8);
    const hsize_t n = values.size();
    hid_t sp = H5Screate_simple(1, &n, nullptr);
    hid_t a = h5check_id(H5Acreate2(obj, name.c_str(), t, sp, H5P_DEFAULT, H5P_DEFAULT), name.c_str());
    std::vector<const char*> p;
    for (const auto& v : values) p.push_back(v.c_str());
    if (n) h5check(H5Awrite(a, t, p.data()), name.c_str());
    H5Aclose(a);
    H5Sclose(sp);
    H5Tclose(t);
}

template <typename T>
hid_t nativeType();
template <> hid_t nativeType<double>() { return H5T_NATIVE_DOUBLE; }
template <> hid_t nativeType<float>() { return H5T_NATIVE_FLOAT; }
template <> hid_t nativeType<int32_t>() { return H5T_NATIVE_INT32; }
template <> hid_t nativeType<uint32_t>() { return H5T_NATIVE_UINT32; }
template <> hid_t nativeType<uint16_t>() { return H5T_NATIVE_UINT16; }
template <> hid_t nativeType<uint8_t>() { return H5T_NATIVE_UINT8; }

// 1-D 배열 속성 (길이 1 이어도 배열 — 받는 쪽이 꼴을 가정할 수 있게, 길이 0 은 빈 공간)
template <typename T>
void attrNum(hid_t obj, const std::string& name, const std::vector<T>& v) {
    const hsize_t n = v.size();
    hid_t sp = n == 0 ? H5Screate(H5S_NULL) : H5Screate_simple(1, &n, nullptr);
    hid_t a = h5check_id(H5Acreate2(obj, name.c_str(), nativeType<T>(), sp, H5P_DEFAULT, H5P_DEFAULT),
                         name.c_str());
    if (n) h5check(H5Awrite(a, nativeType<T>(), v.data()), name.c_str());
    H5Aclose(a);
    H5Sclose(sp);
}

template <typename T>
void attrScalar(hid_t obj, const std::string& name, T v) {
    hid_t sp = H5Screate(H5S_SCALAR);
    hid_t a = h5check_id(H5Acreate2(obj, name.c_str(), nativeType<T>(), sp, H5P_DEFAULT, H5P_DEFAULT),
                         name.c_str());
    h5check(H5Awrite(a, nativeType<T>(), &v), name.c_str());
    H5Aclose(a);
    H5Sclose(sp);
}

// 작은 배열은 통째로, 큰 배열은 청크+shuffle+deflate
template <typename T>
hid_t writeArray(hid_t parent, const std::string& name, const std::vector<hsize_t>& dims, const T* data) {
    hid_t sp = H5Screate_simple(static_cast<int>(dims.size()), dims.data(), nullptr);
    hid_t dcpl = H5Pcreate(H5P_DATASET_CREATE);
    hsize_t total = 1;
    for (auto d : dims) total *= d;
    if (total > 4096) {
        std::vector<hsize_t> chunk = dims;
        // 첫 축을 잘라 청크 하나가 대략 1 MiB 를 넘지 않게
        const hsize_t row = total / std::max<hsize_t>(1, dims[0]);
        chunk[0] = std::max<hsize_t>(1, std::min<hsize_t>(dims[0], (1u << 20) / std::max<hsize_t>(1, row * sizeof(T))));
        H5Pset_chunk(dcpl, static_cast<int>(chunk.size()), chunk.data());
        H5Pset_shuffle(dcpl);
        H5Pset_deflate(dcpl, 6);
    }
    hid_t ds = h5check_id(H5Dcreate2(parent, name.c_str(), nativeType<T>(), sp, H5P_DEFAULT, dcpl, H5P_DEFAULT),
                          name.c_str());
    if (total) h5check(H5Dwrite(ds, nativeType<T>(), H5S_ALL, H5S_ALL, H5P_DEFAULT, data), name.c_str());
    H5Pclose(dcpl);
    H5Sclose(sp);
    return ds;
}

template <typename T>
void writeArrayClose(hid_t parent, const std::string& name, const std::vector<hsize_t>& dims, const T* data) {
    H5Dclose(writeArray<T>(parent, name, dims, data));
}

void writeStrings(hid_t parent, const std::string& name, const std::vector<std::string>& values) {
    hid_t t = H5Tcopy(H5T_C_S1);
    H5Tset_size(t, H5T_VARIABLE);
    H5Tset_cset(t, H5T_CSET_UTF8);
    const hsize_t n = values.size();
    hid_t sp = H5Screate_simple(1, &n, nullptr);
    hid_t ds = h5check_id(H5Dcreate2(parent, name.c_str(), t, sp, H5P_DEFAULT, H5P_DEFAULT, H5P_DEFAULT),
                          name.c_str());
    std::vector<const char*> p;
    for (const auto& v : values) p.push_back(v.c_str());
    if (n) h5check(H5Dwrite(ds, t, H5S_ALL, H5S_ALL, H5P_DEFAULT, p.data()), name.c_str());
    H5Dclose(ds);
    H5Sclose(sp);
    H5Tclose(t);
}

// 상태 축 [T, ...] 데이터셋 — 청크 [16, ...] 로 만들고 16 상태씩 모아 쓴다
class StateSeries {
public:
    StateSeries(hid_t parent, const std::string& name, hid_t type, size_t elem_size, hsize_t T,
                std::vector<hsize_t> tail)
        : type_(type), elem_size_(elem_size), T_(T), tail_(std::move(tail)) {
        row_ = 1;
        for (auto d : tail_) row_ *= d;
        std::vector<hsize_t> dims{T_};
        dims.insert(dims.end(), tail_.begin(), tail_.end());
        std::vector<hsize_t> chunk{std::min<hsize_t>(kChunkStates, std::max<hsize_t>(1, T_))};
        chunk.insert(chunk.end(), tail_.begin(), tail_.end());
        if (chunk.size() > 1) chunk[1] = std::max<hsize_t>(1, std::min<hsize_t>(kChunkItems, chunk[1]));
        hid_t sp = H5Screate_simple(static_cast<int>(dims.size()), dims.data(), nullptr);
        hid_t dcpl = H5Pcreate(H5P_DATASET_CREATE);
        if (T_ > 0 && row_ > 0) {
            H5Pset_chunk(dcpl, static_cast<int>(chunk.size()), chunk.data());
            H5Pset_shuffle(dcpl);
            H5Pset_deflate(dcpl, 6);
        }
        ds_ = h5check_id(H5Dcreate2(parent, name.c_str(), type_, sp, H5P_DEFAULT, dcpl, H5P_DEFAULT),
                         name.c_str());
        H5Pclose(dcpl);
        H5Sclose(sp);
        buf_.reserve(static_cast<size_t>(kChunkStates * row_) * elem_size_);
    }
    hid_t id() const { return ds_; }
    void append(const void* row) {
        const auto* p = static_cast<const unsigned char*>(row);
        buf_.insert(buf_.end(), p, p + row_ * elem_size_);
        ++buffered_;
        if (buffered_ == kChunkStates) flush();
    }
    void flush() {
        if (!buffered_) return;
        std::vector<hsize_t> start{written_}, count{buffered_};
        for (auto d : tail_) {
            start.push_back(0);
            count.push_back(d);
        }
        hid_t fsp = H5Dget_space(ds_);
        H5Sselect_hyperslab(fsp, H5S_SELECT_SET, start.data(), nullptr, count.data(), nullptr);
        hid_t msp = H5Screate_simple(static_cast<int>(count.size()), count.data(), nullptr);
        h5check(H5Dwrite(ds_, type_, msp, fsp, H5P_DEFAULT, buf_.data()), "state series");
        H5Sclose(msp);
        H5Sclose(fsp);
        written_ += buffered_;
        buffered_ = 0;
        buf_.clear();
    }
    void close() {
        flush();
        if (written_ != T_) {
            throw std::runtime_error("상태 배열을 " + std::to_string(written_) + "/" + std::to_string(T_) +
                                     " 만 썼다");
        }
        H5Dclose(ds_);
        ds_ = -1;
    }

private:
    hid_t ds_ = -1;
    hid_t type_;
    size_t elem_size_;
    hsize_t T_;
    std::vector<hsize_t> tail_;
    hsize_t row_ = 1;
    std::vector<unsigned char> buf_;
    hsize_t buffered_ = 0, written_ = 0;
};

void setEncodingAttrs(hid_t ds, bool float32, const std::string& scale_path, const std::string& offset_path,
                      const std::string& group_rule) {
    if (float32) {
        attrStr(ds, "encoding", "float32");
        attrStr(ds, "decode", "value = stored");
        return;
    }
    attrStr(ds, "encoding", "linear_q16");
    attrStr(ds, "decode", "value = offset[g" + std::string(scale_path.find("displacement") != std::string::npos ? ", c" : "") +
                              "] + scale[g" + std::string(scale_path.find("displacement") != std::string::npos ? ", c" : "") +
                              "] * q  (q = 저장된 uint16, " + group_rule + ")");
    attrStr(ds, "scale_table", scale_path);
    attrStr(ds, "offset_table", offset_path);
}

uint16_t quantize(double v, double offset, double scale) {
    const double q = std::round((v - offset) / scale);
    return static_cast<uint16_t>(std::min(65535.0, std::max(0.0, q)));
}

// ── 본체 ───────────────────────────────────────────────────
struct PartGate {
    double vm_all = -1, vm_surf = -1;
    uint32_t all_elem = 0, surf_elem = 0;
    double all_time = 0, surf_time = 0;
};

int run(const Options& o) {
    std::vector<std::string> warnings;
    auto warn = [&](const std::string& w) {
        warnings.push_back(w);
        std::cerr << "WARNING: " << w << std::endl;
    };
    const auto t_start = std::chrono::steady_clock::now();

    D3plotReader reader(o.d3plot);
    if (reader.open() != ErrorCode::SUCCESS) throw std::runtime_error("d3plot 을 열지 못했다: " + o.d3plot);
    const auto& cd = reader.get_control_data();
    const data::Mesh mesh = reader.read_mesh();

    // ── 겉면 ──
    const s1::Surface surf = s1::extractSurface(mesh, o.excluded);
    if (surf.faces.empty()) throw std::runtime_error("겉면이 비었다 — 제외 파트·요소 꼴을 확인하라");
    if (surf.n_shell_elems_skipped) {
        warn("셸·두꺼운 셸 요소 " + std::to_string(surf.n_shell_elems_skipped) + "개는 판 1 에 넣지 않았다");
    }
    if (surf.n_inter_part_shared_faces) {
        warn("서로 다른 파트가 공유한 면이 " + std::to_string(surf.n_inter_part_shared_faces) +
             "개다 — 파트별로 세는 StepForge 와 겉면 집합이 다르다");
    }
    auto realNode = [&](int32_t idx) -> uint32_t {
        return idx < static_cast<int32_t>(mesh.real_node_ids.size()) ? mesh.real_node_ids[idx] : idx + 1;
    };
    auto realSolid = [&](size_t s) -> uint32_t {
        return s < mesh.real_solid_ids.size() ? mesh.real_solid_ids[s] : static_cast<uint32_t>(s + 1);
    };
    auto partOf = [&](size_t s) -> int32_t { return s < mesh.solid_parts.size() ? mesh.solid_parts[s] : 0; };

    // 겉면 절점(실제 ID 오름차순)·요소(실제 ID 오름차순)
    std::vector<int32_t> snodes;
    {
        std::set<int32_t> u;
        for (const auto& f : surf.faces)
            for (int32_t n : f.nodes)
                if (n >= 0) u.insert(n);
        snodes.assign(u.begin(), u.end());
        std::sort(snodes.begin(), snodes.end(), [&](int32_t a, int32_t b) { return realNode(a) < realNode(b); });
    }
    std::vector<size_t> selems;
    {
        std::set<size_t> u;
        for (const auto& f : surf.faces) u.insert(f.solid_index);
        selems.assign(u.begin(), u.end());
        std::sort(selems.begin(), selems.end(), [&](size_t a, size_t b) { return realSolid(a) < realSolid(b); });
    }
    std::map<int32_t, int32_t> node_pos;
    for (size_t i = 0; i < snodes.size(); ++i) node_pos[snodes[i]] = static_cast<int32_t>(i);
    std::map<size_t, int32_t> elem_pos;
    for (size_t i = 0; i < selems.size(); ++i) elem_pos[selems[i]] = static_cast<int32_t>(i);

    // 장치 파트 표(제외 파트 뺌)
    std::vector<int32_t> parts;
    {
        std::set<int32_t> u;
        for (size_t s = 0; s < mesh.solids.size(); ++s)
            if (!o.excluded.count(partOf(s))) u.insert(partOf(s));
        parts.assign(u.begin(), u.end());
    }
    std::map<int32_t, int32_t> part_pos;
    for (size_t i = 0; i < parts.size(); ++i) part_pos[parts[i]] = static_cast<int32_t>(i);
    const size_t P = parts.size(), Ns = snodes.size(), Ne = selems.size(), Nf = surf.faces.size();

    // 절점 스케일 묶음 = 그 절점을 쓰는 첫 겉면의 파트 순번
    std::vector<uint16_t> node_group(Ns, 0);
    {
        std::vector<bool> seen(Ns, false);
        for (const auto& f : surf.faces) {
            const uint16_t g = static_cast<uint16_t>(part_pos[partOf(f.solid_index)]);
            for (int32_t n : f.nodes) {
                if (n < 0) continue;
                const int32_t i = node_pos[n];
                if (!seen[i]) {
                    seen[i] = true;
                    node_group[i] = g;
                }
            }
        }
    }
    // 솔리드마다 /parts 줄(제외 파트는 -1) — 상태마다 도는 자리에서 map 을 찾지 않게 미리 센다
    std::vector<int32_t> solid_pidx(mesh.solids.size(), -1);
    for (size_t s = 0; s < mesh.solids.size(); ++s) {
        auto it = part_pos.find(partOf(s));
        if (it != part_pos.end()) solid_pidx[s] = it->second;
    }
    std::vector<uint8_t> is_surface_solid(mesh.solids.size(), 0);
    for (size_t s : selems) is_surface_solid[s] = 1;
    std::vector<int32_t> elem_group(Ne);
    for (size_t i = 0; i < Ne; ++i) elem_group[i] = part_pos[partOf(selems[i])];

    std::cerr << "[s1] 겉면 — 면 " << Nf << " · 절점 " << Ns << " · 요소 " << Ne << " · 장치 파트 " << P
              << " (대상 솔리드 " << surf.n_device_elems << ", 뒤집은 요소 " << surf.n_flipped_elems << ")\n";

    const bool deletion = cd.MDLOPT == 2 && cd.DELNN > 0;
    if (!deletion) warn("삭제표가 없는 덱이다(MDLOPT≠2) — alive 는 전부 1");

    // ── 1차 읽기: 시각·스케일·게이트·초기 속도 ──
    std::vector<double> times;
    std::vector<double> dmin(P * 3, 1e300), dmax(P * 3, -1e300);
    std::vector<double> vmin(P, 1e300), vmax(P, -1e300);
    std::vector<PartGate> gate(P);
    s1::V3 vel0;
    std::string vel_source;
    s1::V3 mean_u1;
    double t1_time = 0;
    const std::vector<int32_t> device(surf.device_nodes.begin(), surf.device_nodes.end());

    const size_t n_states = reader.for_each_state([&](size_t si, const data::StateData& st) {
        times.push_back(st.time);
        for (size_t i = 0; i < Ns; ++i) {
            const auto u = data::nodeDisplacement(mesh, st, snodes[i]);
            const double c3[3] = {u.x, u.y, u.z};
            for (int c = 0; c < 3; ++c) {
                double& lo = dmin[node_group[i] * 3 + c];
                double& hi = dmax[node_group[i] * 3 + c];
                lo = std::min(lo, c3[c]);
                hi = std::max(hi, c3[c]);
            }
        }
        // 삭제(침식)된 요소는 게이트에서 뺀다 — 리포트 파트 최대(SinglePassAnalyzer)와 같은 정의.
        // deleted_solids 는 솔리드 배열 안 1-based 순번이다. 스케일 범위에는 넣는다(저장 값이 넘치지 않게).
        std::vector<uint8_t> dead;
        if (deletion && !st.deleted_solids.empty()) {
            dead.assign(mesh.solids.size(), 0);
            for (int32_t ord : st.deleted_solids)
                if (ord >= 1 && static_cast<size_t>(ord) <= dead.size()) dead[ord - 1] = 1;
        }
        for (size_t s = 0; s < mesh.solids.size(); ++s) {
            const int32_t pi = solid_pidx[s];
            if (pi < 0) continue;
            const double vm = s1::solidVonMises(st, s, cd.NV3D);
            if (is_surface_solid[s]) {
                vmin[pi] = std::min(vmin[pi], vm);
                vmax[pi] = std::max(vmax[pi], vm);
            }
            if (!dead.empty() && dead[s]) continue;
            PartGate& g = gate[pi];
            if (vm > g.vm_all) {
                g.vm_all = vm;
                g.all_elem = realSolid(s);
                g.all_time = st.time;
            }
            if (is_surface_solid[s] && vm > g.vm_surf) {
                g.vm_surf = vm;
                g.surf_elem = realSolid(s);
                g.surf_time = st.time;
            }
        }
        if (si == 0 && !st.node_velocities.empty()) {
            for (int32_t n : device) {
                vel0.x += st.node_velocities[n * 3 + 0];
                vel0.y += st.node_velocities[n * 3 + 1];
                vel0.z += st.node_velocities[n * 3 + 2];
            }
            vel0 = {vel0.x / device.size(), vel0.y / device.size(), vel0.z / device.size()};
            vel_source = "d3plot_state0";
        }
        if (si == 1) {
            for (int32_t n : device) {
                const auto u = data::nodeDisplacement(mesh, st, n);
                mean_u1.x += u.x;
                mean_u1.y += u.y;
                mean_u1.z += u.z;
            }
            mean_u1 = {mean_u1.x / device.size(), mean_u1.y / device.size(), mean_u1.z / device.size()};
            t1_time = st.time;
        }
        if ((si + 1) % 500 == 0) std::cerr << "[s1] 1차 " << (si + 1) << " 상태\n";
    });
    if (n_states == 0) throw std::runtime_error("상태가 없다");
    for (const auto& w : reader.last_read_warnings()) {
        warnings.push_back(w);  // 리더가 이미 stderr 에 찍었다
    }
    if (vel_source.empty() && n_states > 1 && t1_time > times[0]) {
        const double dt = t1_time - times[0];
        vel0 = {mean_u1.x / dt, mean_u1.y / dt, mean_u1.z / dt};
        vel_source = "displacement_difference";
        warn("d3plot 에 절점 속도가 없어 초기 속도를 상태 0→1 변위 차분으로 셈했다");
    }

    // ── 고를 상태 ──
    std::vector<size_t> sel;
    {
        std::vector<size_t> win;
        for (size_t i = 0; i < times.size(); ++i)
            if (times[i] >= o.t0 && times[i] <= o.t1) win.push_back(i);
        if (win.empty()) throw std::runtime_error("시간 창 안에 상태가 없다");
        for (size_t k = 0; k < win.size(); k += o.state_step) sel.push_back(win[k]);
        if (sel.back() != win.back()) sel.push_back(win.back());
    }
    std::vector<uint8_t> want(times.size(), 0);
    for (size_t i : sel) want[i] = 1;
    const hsize_t T = sel.size();

    // 스케일 (범위 0 이면 1)
    std::vector<double> dscale(P * 3), vscale(P);
    // 발산 의심 — 묶음 변위 범위가 장치 크기의 10배를 넘으면 q16 정밀도(scale/2)가 그만큼 거칠다
    double device_diag = 0;
    {
        double lo[3] = {1e300, 1e300, 1e300}, hi[3] = {-1e300, -1e300, -1e300};
        for (int32_t n : device) {
            const double p3[3] = {mesh.nodes[n].x, mesh.nodes[n].y, mesh.nodes[n].z};
            for (int c = 0; c < 3; ++c) {
                lo[c] = std::min(lo[c], p3[c]);
                hi[c] = std::max(hi[c], p3[c]);
            }
        }
        for (int c = 0; c < 3; ++c) device_diag += (hi[c] - lo[c]) * (hi[c] - lo[c]);
        device_diag = std::sqrt(device_diag);
    }
    for (size_t g = 0; g < P; ++g) {
        double range = 0;
        for (int c = 0; c < 3; ++c) range = std::max(range, dmax[g * 3 + c] - dmin[g * 3 + c]);
        if (device_diag > 0 && range > 10.0 * device_diag) {
            warn("파트 " + std::to_string(parts[g]) + " 의 변위 범위 " + std::to_string(range) +
                 " 가 장치 크기 " + std::to_string(device_diag) + " 의 10배를 넘는다(해석 발산 의심) — " +
                 (o.float32 ? "float32 라 값은 그대로다" :
                  "q16 오차 한계가 " + std::to_string(range / 65535.0 / 2) + " 로 거칠다. --precision float32 를 권한다"));
        }
    }
    for (size_t k = 0; k < P * 3; ++k) {
        if (dmin[k] > dmax[k]) dmin[k] = dmax[k] = 0;  // 이 묶음에 겉면 절점이 없다
        dscale[k] = dmax[k] > dmin[k] ? (dmax[k] - dmin[k]) / 65535.0 : 1.0;
        // 0 이 범위 안이면 offset 을 scale 의 정수배로 내린다 — 변위 0(상태 0 등)이 정수 q 에 떨어져
        // offset + scale·q 가 정확히 0 이 된다(SceneForge 제안). 한 칸을 비워 둬 최댓값이 넘치지 않게.
        if (dmax[k] > dmin[k] && dmin[k] <= 0.0 && dmax[k] >= 0.0) {
            dscale[k] = (dmax[k] - dmin[k]) / 65534.0;
            dmin[k] = std::floor(dmin[k] / dscale[k]) * dscale[k];
        }
    }
    for (size_t k = 0; k < P; ++k) {
        if (vmin[k] > vmax[k]) vmin[k] = vmax[k] = 0;
        vscale[k] = vmax[k] > vmin[k] ? (vmax[k] - vmin[k]) / 65535.0 : 1.0;
    }

    // ── 파일 ──
    fs::path out = fs::absolute(o.output);
    fs::create_directories(out.parent_path());
    const fs::path tmp = out.string() + ".tmp";
    fs::remove(tmp);
    hid_t fapl = H5Pcreate(H5P_FILE_ACCESS);
    H5Pset_libver_bounds(fapl, H5F_LIBVER_LATEST, H5F_LIBVER_LATEST);
    hid_t file = h5check_id(H5Fcreate(tmp.c_str(), H5F_ACC_TRUNC, H5P_DEFAULT, fapl), "파일 만들기");
    H5Pclose(fapl);

    // /mesh
    {
        hid_t g = H5Gcreate2(file, "mesh", H5P_DEFAULT, H5P_DEFAULT, H5P_DEFAULT);
        std::vector<uint32_t> ids(Ns);
        std::vector<float> xyz(Ns * 3);
        for (size_t i = 0; i < Ns; ++i) {
            ids[i] = realNode(snodes[i]);
            const auto& n = mesh.nodes[snodes[i]];
            xyz[i * 3 + 0] = static_cast<float>(n.x);
            xyz[i * 3 + 1] = static_cast<float>(n.y);
            xyz[i * 3 + 2] = static_cast<float>(n.z);
        }
        writeArrayClose<uint32_t>(g, "node_ids", {Ns}, ids.data());
        writeArrayClose<float>(g, "coords0", {Ns, 3}, xyz.data());
        writeArrayClose<uint16_t>(g, "node_group", {Ns}, node_group.data());
        std::vector<int32_t> faces(Nf * 4), fpart(Nf), fel(Nf);
        for (size_t f = 0; f < Nf; ++f) {
            for (int k = 0; k < 4; ++k) {
                const int32_t n = surf.faces[f].nodes[k];
                faces[f * 4 + k] = n < 0 ? -1 : node_pos[n];
            }
            fpart[f] = partOf(surf.faces[f].solid_index);
            fel[f] = elem_pos[surf.faces[f].solid_index];
        }
        hid_t fd = writeArray<int32_t>(g, "faces", {Nf, 4}, faces.data());
        attrStr(fd, "note", "node_ids 의 순번, 넷째가 -1 이면 삼각형, 바깥 방향");
        H5Dclose(fd);
        writeArrayClose<int32_t>(g, "face_part_id", {Nf}, fpart.data());
        writeArrayClose<int32_t>(g, "face_elem_index", {Nf}, fel.data());
        std::vector<uint32_t> eids(Ne);
        std::vector<int32_t> epart(Ne);
        for (size_t i = 0; i < Ne; ++i) {
            eids[i] = realSolid(selems[i]);
            epart[i] = partOf(selems[i]);
        }
        writeArrayClose<uint32_t>(g, "elem_ids", {Ne}, eids.data());
        writeArrayClose<int32_t>(g, "elem_part_id", {Ne}, epart.data());
        attrScalar<uint32_t>(g, "n_device_nodes", static_cast<uint32_t>(surf.device_nodes.size()));
        attrScalar<uint32_t>(g, "n_device_elems", static_cast<uint32_t>(surf.n_device_elems));
        attrScalar<uint32_t>(g, "n_inter_part_shared_faces", static_cast<uint32_t>(surf.n_inter_part_shared_faces));
        attrScalar<uint32_t>(g, "n_shell_elems_skipped", static_cast<uint32_t>(surf.n_shell_elems_skipped));
        H5Gclose(g);
    }

    // /parts
    std::string keyword_path;
    std::string parts_json;          // 곁파일 s1.json 에 그대로 싣는다
    std::string posture_json = "null";
    {
        const auto names = analysis::UnifiedConfigParser::loadPartNames(o.d3plot, &keyword_path);
        hid_t g = H5Gcreate2(file, "parts", H5P_DEFAULT, H5P_DEFAULT, H5P_DEFAULT);
        std::vector<int32_t> nsurf(P, 0);
        for (size_t i = 0; i < Ne; ++i) ++nsurf[elem_group[i]];
        std::vector<std::string> nm(P);
        std::vector<double> va(P), vs(P), ta(P), ts(P);
        std::vector<uint32_t> ea(P), es(P);
        std::vector<uint8_t> on(P);
        for (size_t k = 0; k < P; ++k) {
            auto it = names.find(parts[k]);
            nm[k] = it == names.end() ? "" : it->second;
            va[k] = gate[k].vm_all;
            vs[k] = gate[k].vm_surf;
            ta[k] = gate[k].all_time;
            ts[k] = gate[k].surf_time;
            ea[k] = gate[k].all_elem;
            es[k] = gate[k].surf_elem;
            // 전 요소 최대를 낸 요소·값이 겉면 최대와 같으면 그 요소는 겉면이다
            on[k] = gate[k].vm_all >= 0 && gate[k].all_elem == gate[k].surf_elem &&
                    gate[k].vm_all == gate[k].vm_surf;
        }
        writeArrayClose<int32_t>(g, "part_id", {P}, parts.data());
        writeStrings(g, "name", nm);
        writeArrayClose<int32_t>(g, "n_surface_elems", {P}, nsurf.data());
        writeArrayClose<double>(g, "vm_max_all", {P}, va.data());
        writeArrayClose<uint32_t>(g, "vm_max_all_elem_id", {P}, ea.data());
        writeArrayClose<double>(g, "vm_max_all_time", {P}, ta.data());
        writeArrayClose<double>(g, "vm_max_surface", {P}, vs.data());
        writeArrayClose<uint32_t>(g, "vm_max_surface_elem_id", {P}, es.data());
        writeArrayClose<double>(g, "vm_max_surface_time", {P}, ts.data());
        writeArrayClose<uint8_t>(g, "max_elem_on_surface", {P}, on.data());
        attrStr(g, "note", "전 상태(솎기 전)·양자화 전 원값, 삭제된 요소 제외. 겉면이 없는 파트의 vm_max_surface 는 -1");
        H5Gclose(g);
        for (size_t k = 0; k < P; ++k) {
            parts_json += std::string(k ? ",\n    " : "\n    ") + "{\"part_id\": " + std::to_string(parts[k]) +
                          ", \"name\": " + jstr(nm[k]) + ", \"n_surface_elems\": " + std::to_string(nsurf[k]) +
                          ", \"vm_max_all\": " + jnum(va[k]) + ", \"vm_max_all_elem_id\": " + std::to_string(ea[k]) +
                          ", \"vm_max_all_time\": " + jnum(ta[k]) + ", \"vm_max_surface\": " + jnum(vs[k]) +
                          ", \"vm_max_surface_elem_id\": " + std::to_string(es[k]) +
                          ", \"vm_max_surface_time\": " + jnum(ts[k]) +
                          ", \"max_elem_on_surface\": " + (on[k] ? "true" : "false") + "}";
        }
    }

    // /posture
    if (o.floor_part >= 0) {
        std::vector<s1::V3> floor_nodes;
        std::set<int32_t> fset;
        for (size_t s = 0; s < mesh.solids.size(); ++s)
            if (partOf(s) == o.floor_part)
                for (int32_t id : mesh.solids[s].node_ids) fset.insert(id - 1);
        for (size_t i = 0; i < mesh.shells.size(); ++i)
            if (i < mesh.shell_parts.size() && mesh.shell_parts[i] == o.floor_part)
                for (int32_t id : mesh.shells[i].node_ids) fset.insert(id - 1);
        for (int32_t n : fset) floor_nodes.push_back({mesh.nodes[n].x, mesh.nodes[n].y, mesh.nodes[n].z});
        if (floor_nodes.size() < 3) {
            warn("바닥 파트 " + std::to_string(o.floor_part) + " 의 절점이 없어 /posture 를 쓰지 않는다");
        } else {
            s1::V3 dc;
            for (int32_t n : device) {
                dc.x += mesh.nodes[n].x;
                dc.y += mesh.nodes[n].y;
                dc.z += mesh.nodes[n].z;
            }
            dc = {dc.x / device.size(), dc.y / device.size(), dc.z / device.size()};
            const s1::FloorPlane fp = s1::fitFloorPlane(floor_nodes, dc);
            double gap = 1e300;
            for (int32_t n : device) {
                const auto& p = mesh.nodes[n];
                gap = std::min(gap, (p.x - fp.point.x) * fp.normal.x + (p.y - fp.point.y) * fp.normal.y +
                                        (p.z - fp.point.z) * fp.normal.z);
            }
            const double speed = std::sqrt(vel0.x * vel0.x + vel0.y * vel0.y + vel0.z * vel0.z);
            const double cosang = speed > 0 ? -(vel0.x * fp.normal.x + vel0.y * fp.normal.y + vel0.z * fp.normal.z) / speed : 0;
            const double angle = std::acos(std::max(-1.0, std::min(1.0, cosang))) * 180.0 / M_PI;
            hid_t g = H5Gcreate2(file, "posture", H5P_DEFAULT, H5P_DEFAULT, H5P_DEFAULT);
            const double v3[3] = {vel0.x, vel0.y, vel0.z};
            hid_t dv = writeArray<double>(g, "initial_velocity", {3}, v3);
            attrStr(dv, "velocity_source", vel_source.empty() ? "none" : vel_source);
            H5Dclose(dv);
            const double pt[3] = {fp.point.x, fp.point.y, fp.point.z};
            const double nn[3] = {fp.normal.x, fp.normal.y, fp.normal.z};
            writeArrayClose<double>(g, "floor_point", {3}, pt);
            writeArrayClose<double>(g, "floor_normal", {3}, nn);
            attrScalar<double>(g, "floor_flatness", fp.flatness);
            attrScalar<uint32_t>(g, "floor_layer_nodes", static_cast<uint32_t>(fp.n_layer_nodes));
            attrScalar<double>(g, "gap", gap);
            attrScalar<double>(g, "first_contact_s", speed > 0 ? gap / speed : -1.0);
            attrStr(g, "first_contact_basis", "gap_over_speed");
            attrScalar<double>(g, "velocity_normal_angle_deg", angle);
            attrScalar<int32_t>(g, "floor_part", o.floor_part);
            H5Gclose(g);
            posture_json = "{\"initial_velocity\": [" + jnum(v3[0]) + ", " + jnum(v3[1]) + ", " + jnum(v3[2]) +
                           "], \"velocity_source\": " + jstr(vel_source.empty() ? "none" : vel_source) +
                           ", \"floor_part\": " + std::to_string(o.floor_part) +
                           ", \"floor_point\": [" + jnum(pt[0]) + ", " + jnum(pt[1]) + ", " + jnum(pt[2]) +
                           "], \"floor_normal\": [" + jnum(nn[0]) + ", " + jnum(nn[1]) + ", " + jnum(nn[2]) +
                           "], \"floor_flatness\": " + jnum(fp.flatness) +
                           ", \"floor_layer_nodes\": " + std::to_string(fp.n_layer_nodes) +
                           ", \"gap\": " + jnum(gap) +
                           ", \"first_contact_s\": " + jnum(speed > 0 ? gap / speed : -1.0) +
                           ", \"first_contact_basis\": \"gap_over_speed\"" +
                           ", \"velocity_normal_angle_deg\": " + jnum(angle) + "}";
            if (speed <= 0) warn("초기 속도가 0 이라 first_contact_s 를 셈할 수 없다(-1)");
            std::cerr << "[s1] 자세 — 틈 " << gap << " · 속도 " << speed << " · 법선각 " << angle
                      << "° · 평평함 " << fp.flatness << "\n";
        }
    } else {
        warn("바닥 파트(--floor-part)를 주지 않아 /posture 를 쓰지 않는다");
    }

    // /states — 2차 읽기
    {
        hid_t g = H5Gcreate2(file, "states", H5P_DEFAULT, H5P_DEFAULT, H5P_DEFAULT);
        std::vector<int32_t> sidx(T);
        std::vector<double> stime(T);
        for (size_t k = 0; k < T; ++k) {
            sidx[k] = static_cast<int32_t>(sel[k]);
            stime[k] = times[sel[k]];
        }
        writeArrayClose<int32_t>(g, "state_index", {T}, sidx.data());
        writeArrayClose<double>(g, "time", {T}, stime.data());
        if (!o.float32) {
            std::vector<double> doff(dmin), voff(vmin);
            writeArrayClose<double>(g, "displacement_offset", {P, 3}, doff.data());
            writeArrayClose<double>(g, "displacement_scale", {P, 3}, dscale.data());
            writeArrayClose<double>(g, "von_mises_offset", {P}, voff.data());
            writeArrayClose<double>(g, "von_mises_scale", {P}, vscale.data());
        }
        attrScalar<uint32_t>(g, "n_states", static_cast<uint32_t>(T));
        attrScalar<uint32_t>(g, "n_states_source", static_cast<uint32_t>(n_states));
        attrScalar<uint8_t>(g, "deletion_available", deletion ? 1 : 0);

        const hid_t vtype = o.float32 ? H5T_NATIVE_FLOAT : H5T_NATIVE_UINT16;
        const size_t vsize = o.float32 ? sizeof(float) : sizeof(uint16_t);
        StateSeries sdisp(g, "displacement", vtype, vsize, T, {Ns, 3});
        StateSeries svm(g, "von_mises", vtype, vsize, T, {Ne});
        StateSeries salive(g, "alive", H5T_NATIVE_UINT8, 1, T, {Ne});
        setEncodingAttrs(sdisp.id(), o.float32, "/states/displacement_scale", "/states/displacement_offset",
                         "g = /mesh/node_group[i], c = 성분");
        setEncodingAttrs(svm.id(), o.float32, "/states/von_mises_scale", "/states/von_mises_offset",
                         "g = 요소 파트의 /parts 줄 = /mesh/elem_part_id 를 /parts/part_id 에서 찾은 순번");

        std::vector<float> fd(Ns * 3), fv(Ne);
        std::vector<uint16_t> qd(Ns * 3), qv(Ne);
        std::vector<uint8_t> alive(Ne);
        size_t written = 0;
        reader.for_each_state(
            [&](size_t, const data::StateData& st) {
                for (size_t i = 0; i < Ns; ++i) {
                    const auto u = data::nodeDisplacement(mesh, st, snodes[i]);
                    const double c3[3] = {u.x, u.y, u.z};
                    for (int c = 0; c < 3; ++c) {
                        const size_t k = node_group[i] * 3 + c;
                        if (o.float32) fd[i * 3 + c] = static_cast<float>(c3[c]);
                        else qd[i * 3 + c] = quantize(c3[c], dmin[k], dscale[k]);
                    }
                }
                std::set<int32_t> dead;
                if (deletion) dead.insert(st.deleted_solids.begin(), st.deleted_solids.end());
                for (size_t i = 0; i < Ne; ++i) {
                    const double vm = s1::solidVonMises(st, selems[i], cd.NV3D);
                    const int32_t gi = elem_group[i];
                    if (o.float32) fv[i] = static_cast<float>(vm);
                    else qv[i] = quantize(vm, vmin[gi], vscale[gi]);
                    // deleted_solids 는 솔리드 배열 안 1-based 순번이다(실제 요소 ID 가 아니다)
                    alive[i] = dead.count(static_cast<int32_t>(selems[i] + 1)) ? 0 : 1;
                }
                if (o.float32) {
                    sdisp.append(fd.data());
                    svm.append(fv.data());
                } else {
                    sdisp.append(qd.data());
                    svm.append(qv.data());
                }
                salive.append(alive.data());
                if (++written % 500 == 0) std::cerr << "[s1] 2차 " << written << "/" << T << " 상태\n";
            },
            [&](size_t i) { return i < want.size() && want[i]; });
        sdisp.close();
        svm.close();
        salive.close();
        H5Gclose(g);
    }

    // 루트 속성 (곁파일 머리도 같은 값으로)
    std::string root_json;
    {
        attrStr(file, "schema", "kood3plot.s1");
        attrScalar<int32_t>(file, "schema_version", kSchemaVersion);
        attrStr(file, "tool", "s1_extract");
        attrStr(file, "tool_version", KOOD3PLOT_GIT_COMMIT);
        const std::string created = isoNowUtc();
        attrStr(file, "created_utc", created);
        const std::string src = fs::absolute(o.d3plot).string();
        attrStr(file, "source_d3plot", src);
        std::string fp = "files=";
        {
            core::FileFamily fam(src);
            fp += std::to_string(fam.get_file_count()) + ";sizes=";
            for (size_t i = 0; i < fam.get_file_count(); ++i) {
                fp += (i ? "," : "") + std::to_string(fs::file_size(fam.get_file_path(i)));
            }
        }
        fp += ";head4k_sha256=" + runCapture("head -c 4096 " + shellQuote(src) + " | sha256sum");
        attrStr(file, "source_fingerprint", fp);
        attrStr(file, "deck_path", keyword_path);
        attrStr(file, "deck_sha256", keyword_path.empty() ? "" : runCapture("sha256sum " + shellQuote(keyword_path)));
        if (keyword_path.empty()) warn("키워드 덱을 찾지 못했다 — deck_sha256·파트 이름이 비었다");
        if (o.units == "deck_units") warn("--units 를 주지 않아 단위가 미상(deck_units)이다");
        attrStr(file, "units", o.units);
        attrStr(file, "surface_rule_id", "deck-surface/stepforge-2026-10");
        attrStr(file, "surface_rule", kSurfaceRule);
        attrNum<int32_t>(file, "excluded_parts", std::vector<int32_t>(o.excluded.begin(), o.excluded.end()));
        attrScalar<int32_t>(file, "selection_step", o.state_step);
        attrNum<double>(file, "selection_window_s", {o.t0, o.t1});
        attrStrArray(file, "warnings", warnings);
        std::string ws, ex;
        for (const auto& w : warnings) ws += (ws.empty() ? "" : ", ") + jstr(w);
        for (int32_t e : o.excluded) ex += (ex.empty() ? "" : ", ") + std::to_string(e);
        root_json = "  \"schema\": \"kood3plot.s1\", \"schema_version\": " + std::to_string(kSchemaVersion) +
                    ",\n  \"tool\": \"s1_extract\", \"tool_version\": " + jstr(KOOD3PLOT_GIT_COMMIT) +
                    ",\n  \"created_utc\": " + jstr(created) +
                    ",\n  \"source_d3plot\": " + jstr(src) + ",\n  \"source_fingerprint\": " + jstr(fp) +
                    ",\n  \"deck_path\": " + jstr(keyword_path) + ", \"deck_sha256\": " +
                    jstr(keyword_path.empty() ? "" : runCapture("sha256sum " + shellQuote(keyword_path))) +
                    ",\n  \"units\": " + jstr(o.units) + ", \"surface_rule_id\": \"deck-surface/stepforge-2026-10\"" +
                    ",\n  \"excluded_parts\": [" + ex + "], \"selection_step\": " + std::to_string(o.state_step) +
                    ", \"selection_window_s\": [" + jnum(o.t0) + ", " + jnum(o.t1) + "]" +
                    ",\n  \"n_states\": " + std::to_string(T) + ", \"n_states_source\": " + std::to_string(n_states) +
                    ", \"encoding\": " + jstr(o.float32 ? "float32" : "linear_q16") +
                    ",\n  \"warnings\": [" + ws + "]";
    }
    h5check(H5Fclose(file), "파일 닫기");
    fs::rename(tmp, out);

    // 곁파일 s1.json — 큰 파일을 받지 않고도 manifest·게이트를 지을 수 있게(DynaForge 요청).
    // sha256 은 파일 안에 넣을 수 없어 여기에만 있다. 바로 쓴 파일이라 페이지 캐시에서 읽는다.
    {
        const std::string sha = runCapture("sha256sum " + shellQuote(out.string()));
        if (sha.size() != 64) throw std::runtime_error("s1.h5 의 sha256 을 구하지 못했다");
        const fs::path jpath = out.parent_path() / (out.stem().string() + ".json");
        const fs::path jtmp = jpath.string() + ".tmp";
        {
            std::ofstream js(jtmp);
            js << "{\n" << root_json << ",\n  \"file\": " << jstr(out.filename().string())
               << ", \"bytes\": " << fs::file_size(out) << ", \"sha256\": " << jstr(sha)
               << ",\n  \"parts\": [" << parts_json << "\n  ],\n  \"posture\": " << posture_json << "\n}\n";
            if (!js) throw std::runtime_error("곁파일을 쓰지 못했다: " + jtmp.string());
        }
        fs::rename(jtmp, jpath);
    }

    const double sec = std::chrono::duration<double>(std::chrono::steady_clock::now() - t_start).count();
    std::cerr << "[s1] 완성 " << out.string() << " — 상태 " << T << "/" << n_states << ", "
              << fs::file_size(out) / 1048576.0 << " MB, " << sec << " s, 경고 " << warnings.size() << "\n";
    return 0;
}

}  // namespace

int main(int argc, char** argv) {
    Options o;
    try {
        o = parseArgs(argc, argv);
        return run(o);
    } catch (const std::exception& e) {
        std::cerr << "ERROR: " << e.what() << std::endl;
        if (!o.output.empty()) {
            std::error_code ec;
            fs::remove(fs::absolute(o.output).string() + ".tmp", ec);
        }
        return 1;
    }
}
