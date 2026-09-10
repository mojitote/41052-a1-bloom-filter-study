#include "bloom.hpp"
#include <algorithm>
#include <iostream>
#include <random>
#include <unordered_set>
#include <vector>

namespace {
std::size_t checks = 0;
void require(bool ok, const char* message) {
    ++checks;
    if (!ok) throw std::runtime_error(message);
}
template<class F> void rejects(F f) {
    bool threw = false;
    try { f(); } catch (const std::invalid_argument&) { threw = true; }
    require(threw, "invalid configuration was accepted");
}
}
int main() {
    try {
        rejects([] { bloom::BloomFilter f(0, 1); });
        rejects([] { bloom::BloomFilter f(10, 0); });
        rejects([] { bloom::BloomFilter f(10, 65); });
        for (std::size_t m : {1u, 7u, 63u, 64u, 65u, 127u, 1024u}) {
            for (std::size_t k : {1u, 3u, 64u}) {
                bloom::BloomFilter f(m, k, 42);
                require(f.storage_bytes() == 8 * (m / 64 + (m % 64 != 0)), "word rounding");
                require(!f.contains(0), "empty filter");
                std::vector<bool> reference(m, false);
                std::vector<std::uint64_t> inserted;
                std::mt19937_64 rng(m + k);
                for (int t = 0; t < 100; ++t) {
                    const std::uint64_t x = t == 0 ? 0 : (t == 1 ? UINT64_MAX : rng());
                    const auto before = f.set_bits();
                    f.insert(x);
                    inserted.push_back(x);
                    for (std::size_t i = 0; i < k; ++i) reference[f.position(x, i)] = true;
                    require(f.set_bits() >= before, "insertion cleared a bit");
                    require(f.set_bits() == static_cast<std::size_t>(std::count(reference.begin(), reference.end(), true)), "bit packing disagrees with reference");
                    const auto after = f.set_bits();
                    f.insert(x);
                    require(f.set_bits() == after, "duplicate insertion changed bits");
                    for (auto y : inserted) require(f.contains(y), "false negative");
                    for (int q = 0; q < 10; ++q) {
                        auto y = rng(); bool expected = true;
                        for (std::size_t i = 0; i < k; ++i) expected = expected && reference[f.position(y, i)];
                        require(f.contains(y) == expected, "membership differs from bit oracle");
                    }
                }
            }
        }
        bloom::BloomFilter saturated(1, 1);
        saturated.insert(17);
        require(saturated.contains(99), "one-bit saturated filter should admit false positives");
        bloom::BloomFilter a(100003, 7, 91), b(100003, 7, 91);
        std::unordered_set<std::uint64_t> exact;
        for (std::uint64_t i = 0; i < 10000; ++i) { auto x = bloom::mix64(i); a.insert(x); b.insert(x); exact.insert(x); }
        std::size_t fp = 0;
        for (std::uint64_t i = 0; i < 100000; ++i) {
            auto x = bloom::mix64(i);
            require(a.contains(x) == b.contains(x), "seed reproducibility");
            if (exact.count(x)) require(a.contains(x), "large-set false negative");
            else fp += a.contains(x);
        }
        require(fp > 100 && fp < 3000, "gross statistical/hash failure (broad smoke bounds)");
        require(bloom::predicted_fpr(1000, 7, 0) == 0, "empty theoretical FPR");
        std::cout << "PASS " << checks << " checks; large-set false positives=" << fp << "/90000\n";
    } catch (const std::exception& e) { std::cerr << "FAIL: " << e.what() << '\n'; return 1; }
}
