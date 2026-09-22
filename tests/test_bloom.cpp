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
        // Fixed known-answer vectors do not call the implementation to compute expected positions.
        require(bloom::mix64(0) == 0, "mixer zero vector");
        require(bloom::mix64(1) == UINT64_C(0x5692161d100b05e5), "mixer known-answer vector");
        bloom::BloomFilter trace(64, 3, 7);
        const std::size_t expected10[] = {30, 14, 16};
        const std::size_t expected20[] = {11, 31, 46};
        for (std::size_t i = 0; i < 3; ++i) {
            require(trace.position(10, i) == expected10[i], "known index for 10");
            require(trace.position(20, i) == expected20[i], "known index for 20");
        }
        for (std::size_t m : {1u, 7u, 63u, 64u, 65u, 127u, 1024u}) {
            for (std::size_t k : {1u, 3u, 64u}) {
                bloom::BloomFilter f(m, k, 42);
                require(f.storage_bytes() == 8 * (m / 64 + (m % 64 != 0)), "word rounding");
                require(!f.contains(0), "empty filter");
                require(!f.contains_full_scan(0), "empty full scan");
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
                    const auto expected_set_bits = static_cast<std::size_t>(std::count(reference.begin(), reference.end(), true));
                    const auto actual_set_bits = f.set_bits();
                    if (actual_set_bits != expected_set_bits) {
                        std::cerr << "bit packing mismatch: m=" << m
                                  << ", k=" << k
                                  << ", insertion=" << t
                                  << ", key=" << x
                                  << ", actual set bits=" << actual_set_bits
                                  << ", reference set bits=" << expected_set_bits
                                  << "\n  A previous bit was cleared; check the |= in BloomFilter::insert().\n";
                        throw std::runtime_error("bit packing disagrees with reference");
                    }
                    const auto after = f.set_bits();
                    f.insert(x);
                    require(f.set_bits() == after, "duplicate insertion changed bits");
                    for (auto y : inserted) require(f.contains(y), "false negative");
                    for (int q = 0; q < 10; ++q) {
                        auto y = rng(); bool expected = true;
                        for (std::size_t i = 0; i < k; ++i) expected = expected && reference[f.position(y, i)];
                        require(f.contains(y) == expected, "membership differs from bit oracle");
                        require(f.contains_full_scan(y) == expected, "full scan differs from bit oracle");
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
            require(a.contains_full_scan(x) == a.contains(x), "full scan equivalence");
            if (exact.count(x)) require(a.contains(x), "large-set false negative");
            else fp += a.contains(x);
            require((a.contains(x) && exact.count(x) != 0) == (exact.count(x) != 0),
                    "filtered exact lookup must match oracle on each key, not only total count");
        }
        require(fp > 100 && fp < 3000, "gross statistical/hash failure (broad smoke bounds)");
        require(bloom::predicted_fpr(1000, 7, 0) == 0, "empty theoretical FPR");
        std::cout << "PASS " << checks << " checks; large-set false positives=" << fp << "/90000\n";
    } catch (const std::exception& e) { std::cerr << "FAIL: " << e.what() << '\n'; return 1; }
}
