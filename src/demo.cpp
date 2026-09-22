#include "bloom.hpp"
#include <bitset>
#include <iostream>

namespace {
void print_words(const bloom::BloomFilter& filter, std::uint64_t key) {
    const std::string prefix = "  word[0] = ";
    for (std::size_t i = 0; i < filter.storage_bytes() / sizeof(std::uint64_t); ++i) {
        std::cout << "  word[" << i << "] = " << std::bitset<64>(filter.debug_word(i)) << '\n';
    }
    std::string marks(64, ' ');
    for (std::size_t i = 0; i < filter.hashes(); ++i) {
        const auto p = filter.position(key, i);
        marks[63 - p] = '^';
    }
    std::cout << std::string(prefix.size(), ' ') << marks << '\n';
    std::cout << "  bits set by key " << key << ":";
    for (std::size_t i = 0; i < filter.hashes(); ++i)
        std::cout << ' ' << filter.position(key, i);
    std::cout << '\n';
}

void print_checked_word(const bloom::BloomFilter& filter, std::uint64_t key) {
    const std::string prefix = "  word[0] = ";
    const std::string bits = std::bitset<64>(filter.debug_word(0)).to_string();
    std::string marks(64, ' ');
    std::cout << "  checked key " << key << "\n";
    std::cout << prefix << bits << '\n';
    for (std::size_t i = 0; i < filter.hashes(); ++i) {
        const auto p = filter.position(key, i);
        marks[63 - p] = '^'; // bitset prints bit 63 on the left and bit 0 on the right
    }
    std::cout << std::string(prefix.size(), ' ') << marks << '\n';
    std::cout << "  positions:";
    for (std::size_t i = 0; i < filter.hashes(); ++i)
        std::cout << ' ' << filter.position(key, i);
    std::cout << '\n';
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
        print_words(f, x);
    }
    std::uint64_t fp = 31;
    while (!f.contains(fp)) ++fp;
    std::cout << "contains(10)=" << f.contains(10) << " (inserted)\n";
    print_checked_word(f, 10);
    std::cout << "contains(" << fp << ")=" << f.contains(fp)
              << " (NOT inserted: false positive)\n";
    print_checked_word(f, fp);
}
