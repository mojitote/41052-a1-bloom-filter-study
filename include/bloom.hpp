#pragma once
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <stdexcept>
#include <vector>

namespace bloom {
// SplitMix64 finalizer: a fast non-cryptographic permutation of 64-bit words.
// Unsigned arithmetic wraps modulo 2^64, as required by this mixer.
inline std::uint64_t mix64(std::uint64_t x) noexcept {
    x = (x ^ (x >> 30)) * UINT64_C(0xbf58476d1ce4e5b9);
    x = (x ^ (x >> 27)) * UINT64_C(0x94d049bb133111eb);
    return x ^ (x >> 31);
}

class BloomFilter {
public:
    BloomFilter(std::size_t bits, std::size_t hashes, std::uint64_t seed = 1)
        : bits_(bits), hashes_(hashes), seed_(seed) {
        if (bits == 0 || hashes == 0 || hashes > 64)
            throw std::invalid_argument("bits must be positive; hashes must be in [1,64]");
        // Division before addition avoids overflow for large bit counts.
        words_.assign(bits / 64 + (bits % 64 != 0), 0);
    }

    void insert(std::uint64_t key) noexcept {
        for (std::size_t i = 0; i < hashes_; ++i) {
            const auto p = position(key, i);
        // Example: p = 70
        // p / 64 = 1, so the target is words_[1].
        // p % 64 = 6, so the target bit is bit 6 in that word.
        //
        // UINT64_C(1) << 6 creates a 64-bit mask:
        //
        //   bit index:  ... 6 5 4 3 2 1 0
        //   mask:      ... 1 0 0 0 0 0 0
        //
        // Bitwise OR assignment then sets bit 6:
        //
        //   old word:  ... x x x x x x x
        //   mask:      ... 0 1 0 0 0 0 0
        //   result:    ... x 1 x x x x x
        //
        // Existing 1 bits stay 1, and existing 0 bits stay 0,
        // except for the target bit, which becomes 1.
            words_[p / 64] |= UINT64_C(1) << (p % 64);
        }
    }

    //main invariant ： once a bit required by an inserted key is set, it is never cleared.
    bool contains(std::uint64_t key) const noexcept {
        for (std::size_t i = 0; i < hashes_; ++i) {
            const auto p = position(key, i);
            if ((words_[p / 64] & (UINT64_C(1) << (p % 64))) == 0)
                return false; // One absent bit is a certificate of non-membership.
        }
        return true; // Possibly present; this is not an exact membership proof.
    }

    // Experimental alternative: same storage and mapping, no source-level early return.
    bool contains_full_scan(std::uint64_t key) const noexcept {
        bool present = true;
        for (std::size_t i = 0; i < hashes_; ++i) {
            const auto p = position(key, i);
            present &= (words_[p / 64] & (UINT64_C(1) << (p % 64))) != 0;
        }
        return present;
    }

    std::size_t bits() const noexcept { return bits_; }
    std::size_t hashes() const noexcept { return hashes_; }
    std::size_t storage_bytes() const noexcept { return words_.size() * sizeof(std::uint64_t); }
    std::size_t set_bits() const noexcept {
        std::size_t count = 0;
        for (auto word : words_) { while (word) { word &= word - 1; ++count; } }
        return count;
    }
    // Exposed for the educational trace and independent indexing tests.
    std::size_t position(std::uint64_t key, std::size_t i) const noexcept {
        const auto salt = mix64(seed_ + UINT64_C(0x9e3779b97f4a7c15) * (i + 1));
        return static_cast<std::size_t>(mix64(key ^ salt) % bits_);
    }
private:
    std::size_t bits_, hashes_;
    std::uint64_t seed_;
    std::vector<std::uint64_t> words_;
};

inline double predicted_fpr(std::size_t bits, std::size_t hashes, std::size_t distinct) {
    if (!bits || !hashes) throw std::invalid_argument("positive bits and hashes required");
    return std::pow(-std::expm1(-static_cast<double>(hashes) * distinct / bits),
                    static_cast<double>(hashes));
}
} // namespace bloom
