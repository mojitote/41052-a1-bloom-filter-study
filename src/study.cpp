#include "bloom.hpp"
#include <algorithm>
#include <array>
#include <chrono>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <memory>
#include <numeric>
#include <random>
#include <string>
#include <unordered_set>

using Clock = std::chrono::steady_clock;
using Key = std::uint64_t;
volatile std::uint64_t observable = 0;
struct Ledger { std::size_t live = 0, peak = 0; };
template<class T> struct CountingAllocator {
    using value_type = T;
    Ledger* ledger;
    explicit CountingAllocator(Ledger* p) : ledger(p) {}
    template<class U> CountingAllocator(const CountingAllocator<U>& a) : ledger(a.ledger) {}
    T* allocate(std::size_t n) {
        T* p = std::allocator<T>{}.allocate(n);
        ledger->live += n * sizeof(T); ledger->peak = std::max(ledger->peak, ledger->live);
        return p;
    }
    void deallocate(T* p, std::size_t n) noexcept {
        ledger->live -= n * sizeof(T); std::allocator<T>{}.deallocate(p, n);
    }
    template<class U> bool operator==(const CountingAllocator<U>& b) const { return ledger == b.ledger; }
    template<class U> bool operator!=(const CountingAllocator<U>& b) const { return !(*this == b); }
};
struct ExactHash { std::size_t operator()(Key x) const noexcept { return bloom::mix64(x); } };
using Exact = std::unordered_set<Key, ExactHash, std::equal_to<Key>, CountingAllocator<Key>>;

double elapsed_ns(Clock::time_point begin) {
    return std::chrono::duration<double, std::nano>(Clock::now() - begin).count();
}
std::vector<Key> keys(std::size_t n, Key offset) {
    std::vector<Key> v; v.reserve(n);
    for (std::size_t i = 0; i < n; ++i) v.push_back(bloom::mix64(offset + i));
    return v; // mix64 is bijective: non-overlapping counter ranges cannot collide.
}
void accuracy(const std::filesystem::path& out, bool quick) {
    std::ofstream csv(out / "accuracy.csv");
    csv << "experiment,seed,n,m,k,queries,false_positives,false_negatives,set_bits,predicted_fpr,storage_bytes\n" << std::setprecision(12);
    const std::size_t base = quick ? 2000 : 20000, q = quick ? 20000 : 200000;
    const int trials = quick ? 2 : 8;
    auto one = [&](const char* experiment, int seed, std::size_t n, std::size_t m, std::size_t k) {
        const Key offset = static_cast<Key>(seed) << 40;
        auto inserted = keys(n, offset), negative = keys(q, offset + (UINT64_C(1) << 32));
        bloom::BloomFilter filter(m, k, seed);
        for (auto x : inserted) filter.insert(x);
        std::size_t fp = 0, fn = 0;
        for (auto x : inserted) fn += !filter.contains(x);
        for (auto x : negative) fp += filter.contains(x);
        if (fn) throw std::runtime_error("false negative in accuracy study");
        csv << experiment << ',' << seed << ',' << n << ',' << m << ',' << k << ',' << q << ',' << fp << ',' << fn << ','
            << filter.set_bits() << ',' << bloom::predicted_fpr(m, k, n) << ',' << filter.storage_bytes() << '\n';
    };
    for (int seed = 1; seed <= trials; ++seed) {
        for (std::size_t b : {4u, 8u, 10u, 16u})
            for (std::size_t k = 1; k <= 16; ++k) one("hash_sweep", seed, base, base * b, k);
        for (double load : {0.25, 0.5, 1.0, 1.5, 2.0, 3.0})
            one("capacity", seed, static_cast<std::size_t>(base * load), base * 10, 7);
        std::cerr << "accuracy seed " << seed << '/' << trials << " complete\n";
    }
    if (!csv) throw std::runtime_error("accuracy CSV write failed");
}
void performance(const std::filesystem::path& out, bool quick) {
    std::ofstream csv(out / "timing.csv"), memory(out / "memory.csv");
    csv << "seed,n,m,k,negative_fraction,queries,repeat,order,method,ns_per_query,returned_positive,expected_exact_positive,backend_lookups\n" << std::setprecision(12);
    memory << "seed,n,m,k,bloom_bytes,set_live_bytes,set_peak_bytes,combined_live_bytes,bloom_build_ns,set_build_ns\n" << std::setprecision(12);
    const std::size_t q = quick ? 20000 : 200000;
    const int trials = quick ? 2 : 4, repeats = quick ? 3 : 7;
    const std::vector<std::size_t> sizes = quick ? std::vector<std::size_t>{2000, 20000} : std::vector<std::size_t>{20000, 200000};
    for (int seed = 1; seed <= trials; ++seed) for (auto n : sizes) {
        auto inserted = keys(n, static_cast<Key>(seed) << 40);
        Ledger ledger;
        Exact exact(0, ExactHash{}, std::equal_to<Key>{}, CountingAllocator<Key>(&ledger));
        const auto set_start = Clock::now();
        exact.max_load_factor(1.0f); exact.reserve(n);
        for (auto x : inserted) exact.insert(x);
        const auto set_ns = elapsed_ns(set_start);
        for (std::size_t k : {1u, 3u, 7u, 11u}) {
            const auto bf_start = Clock::now();
            bloom::BloomFilter filter(n * 10, k, seed);
            for (auto x : inserted) filter.insert(x);
            const auto bf_ns = elapsed_ns(bf_start);
            memory << seed << ',' << n << ',' << n * 10 << ',' << k << ',' << filter.storage_bytes() << ',' << ledger.live << ',' << ledger.peak << ','
                   << ledger.live + filter.storage_bytes() << ',' << bf_ns << ',' << set_ns << '\n';
            for (double miss : {0.0, 0.5, 0.9, 1.0}) {
                const auto negatives = static_cast<std::size_t>(std::llround(q * miss));
                std::vector<Key> queries; queries.reserve(q);
                std::mt19937_64 rng(seed * 1009 + n + negatives);
                for (std::size_t i = 0; i < q - negatives; ++i) queries.push_back(inserted[rng() % n]);
                auto absent = keys(negatives, (static_cast<Key>(seed) << 40) + (UINT64_C(1) << 32));
                queries.insert(queries.end(), absent.begin(), absent.end());
                std::shuffle(queries.begin(), queries.end(), rng);
                std::size_t bloom_count = 0;
                for (auto x : queries) bloom_count += filter.contains(x);
                auto run = [&](int method) {
                    std::size_t hits = 0;
                    // Dispatch outside the hot loop. Output/allocation/generation are not timed.
                    if (method == 0) for (auto x : queries) hits += exact.find(x) != exact.end();
                    if (method == 1) for (auto x : queries) hits += filter.contains(x);
                    if (method == 2) for (auto x : queries) hits += filter.contains(x) && exact.find(x) != exact.end();
                    return hits;
                };
                for (int method = 0; method < 3; ++method) observable += run(method); // warm-up
                for (int rep = 0; rep < repeats; ++rep) {
                    std::array<int, 3> order{0, 1, 2}; std::shuffle(order.begin(), order.end(), rng);
                    int position = 0;
                    for (auto method : order) {
                        auto start = Clock::now(); const auto hits = run(method); const auto ns = elapsed_ns(start);
                        observable += hits;
                        if (hits != (method == 1 ? bloom_count : q - negatives))
                            throw std::runtime_error("benchmark returned wrong membership count");
                        const char* name = method == 0 ? "set" : (method == 1 ? "bloom" : "filtered_set");
                        csv << seed << ',' << n << ',' << n * 10 << ',' << k << ',' << miss << ',' << q << ',' << rep << ',' << position++ << ',' << name << ','
                            << ns / q << ',' << hits << ',' << q - negatives << ',' << (method == 0 ? q : (method == 2 ? bloom_count : 0)) << '\n';
                    }
                }
            }
        }
        std::cerr << "timing seed=" << seed << " n=" << n << " complete\n";
    }
    if (!csv || !memory) throw std::runtime_error("timing/memory CSV write failed");
}
int main(int argc, char** argv) {
    try {
        bool quick = false; std::filesystem::path out;
        for (int i = 1; i < argc; ++i) {
            std::string a = argv[i];
            if (a == "--quick") quick = true;
            else if (a == "--out" && i + 1 < argc) out = argv[++i];
            else if (a == "--help") {
                std::cout << "Usage: study --out NEW_DIRECTORY [--quick]\nDefault: full study. Existing results are never overwritten.\n"; return 0;
            } else throw std::invalid_argument("unknown or incomplete option: " + a);
        }
        if (out.empty()) throw std::invalid_argument("--out NEW_DIRECTORY is required");
        if (std::filesystem::exists(out)) throw std::invalid_argument("output path already exists; choose a new run directory");
        std::filesystem::create_directories(out);
        accuracy(out, quick); performance(out, quick);
        std::cout << "Study complete; observable checksum=" << observable << '\n';
    } catch (const std::exception& e) { std::cerr << "Error: " << e.what() << '\n'; return 1; }
}
