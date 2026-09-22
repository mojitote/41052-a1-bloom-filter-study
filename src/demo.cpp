#include "bloom.hpp"
#include <bitset>
#include <iostream>
#include <string>
#include <vector>

namespace {
std::size_t word_count(const bloom::BloomFilter& filter) {
    return filter.storage_bytes() / sizeof(std::uint64_t);
}

void print_word_rows(const bloom::BloomFilter& filter, std::uint64_t key) {
    std::vector<std::string> marks(word_count(filter), std::string(64, ' '));
    for (std::size_t i = 0; i < filter.hashes(); ++i) {
        const auto p = filter.position(key, i);
        marks[p / 64][63 - (p % 64)] = '^';
    }
    for (std::size_t i = 0; i < word_count(filter); ++i) {
        const std::string prefix = "  word[" + std::to_string(i) + "] = ";
        std::cout << prefix << std::bitset<64>(filter.debug_word(i)) << '\n';
        std::cout << std::string(prefix.size(), ' ') << marks[i] << '\n';
    }
}

void print_words(const bloom::BloomFilter& filter, std::uint64_t key) {
    print_word_rows(filter, key);
}

void print_initial_words(const bloom::BloomFilter& filter) {
    std::cout << "\n[initial bit array]\n";
    for (std::size_t i = 0; i < word_count(filter); ++i)
        std::cout << "  word[" << i << "] = "
                  << std::bitset<64>(filter.debug_word(i)) << '\n';
}

void print_checked_word(const bloom::BloomFilter& filter, std::uint64_t key) {
    std::cout << "  checked key " << key << "\n";
    print_word_rows(filter, key);
}

void print_positions(const bloom::BloomFilter& filter, std::uint64_t key) {
    std::cout << "positions:";
    for (std::size_t i = 0; i < filter.hashes(); ++i)
        std::cout << ' ' << filter.position(key, i);
    std::cout << '\n';
}
}

int main() {
    const std::uint64_t seed = 7;
    bloom::BloomFilter f(65, 3, seed);
    std::cout << "constructor -> bits=" << f.bits()
              << ", hashes=" << f.hashes()
              << ", seed=" << seed << '\n';
    print_initial_words(f);
    for (auto x : {10, 20, 3}) {
        std::cout << "\n[insert key " << x << "]\n"
                  << "insert(" << x << ")\n";
        print_positions(f, x);
        f.insert(x);
        std::cout << "occupied=" << f.set_bits() << "/" << f.bits() << '\n';
        print_words(f, x);
    }
    std::uint64_t fp = 31;
    while (!f.contains(fp)) ++fp;
    std::cout << "\n[lookup: inserted key 10]\n";
    std::cout << "contains(10)=" << f.contains(10) << " (inserted)\n";
    print_positions(f, 10);
    print_checked_word(f, 10);
    std::cout << "\n[lookup: false-positive candidate " << fp << "]\n";
    std::cout << "contains(" << fp << ")=" << f.contains(fp)
              << " (NOT inserted: false positive)\n";
    print_positions(f, fp);
    print_checked_word(f, fp);
}
