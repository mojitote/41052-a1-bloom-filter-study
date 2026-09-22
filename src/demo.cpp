#include "bloom.hpp"
#include <bitset>
#include <iostream>

namespace {
void print_words(const bloom::BloomFilter& filter) {
    for (std::size_t i = 0; i < filter.storage_bytes() / sizeof(std::uint64_t); ++i) {
        std::cout << "  word[" << i << "] = "
                  << std::bitset<64>(filter.debug_word(i)) << '\n';
    }
}
}

int main() {
    const std::uint64_t seed = 7;
    bloom::BloomFilter f(64, 3, seed);
    std::cout << "constructor -> bits=" << f.bits()
              << ", hashes=" << f.hashes()
              << ", seed=" << seed << '\n';
    for (auto x : {10, 20, 30}) {
        std::cout << "insert " << x << "; positions:";
        for (std::size_t i = 0; i < f.hashes(); ++i) std::cout << ' ' << f.position(x, i);
        f.insert(x); std::cout << "; occupied=" << f.set_bits() << "/64\n";
        print_words(f);
    }
    std::uint64_t fp = 31;
    while (!f.contains(fp)) ++fp;
    std::cout << "contains(10)=" << f.contains(10) << " (inserted)\n"
              << "  -> checks positions: ";
    for (std::size_t i = 0; i < f.hashes(); ++i) {
        if (i) std::cout << " -> ";
        std::cout << f.position(10, i);
    }
    std::cout << '\n';
    std::cout << "contains(" << fp << ")=" << f.contains(fp)
              << " (NOT inserted: false positive)\n"
              << "  -> checks positions: ";
    for (std::size_t i = 0; i < f.hashes(); ++i) {
        if (i) std::cout << " -> ";
        std::cout << f.position(fp, i);
    }
    std::cout << '\n';
}
