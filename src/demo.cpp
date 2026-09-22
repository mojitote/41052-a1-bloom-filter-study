#include "bloom.hpp"
#include <iostream>
#include <string>

int main(int argc, char** argv) {
    if (argc > 1 && std::string(argv[1]) == "--help") {
        std::cout << "Usage: bloom_demo [--what-breaks]\nShows an insertion invariant and a deterministic false positive.\n";
        return 0;
    }
    if (argc > 1 && std::string(argv[1]) != "--what-breaks") {
        std::cerr << "Unknown option; use --help\n"; return 2;
    }
    bloom::BloomFilter f(64, 3, 7);
    for (auto x : {10, 20, 30}) {
        std::cout << "insert " << x << "; positions:";
        for (std::size_t i = 0; i < f.hashes(); ++i) std::cout << ' ' << f.position(x, i);
        f.insert(x); std::cout << "; occupied=" << f.set_bits() << "/64\n";
    }
    std::uint64_t fp = 31;
    while (!f.contains(fp)) ++fp;
    std::cout << "contains(10)=" << f.contains(10) << " (inserted)\n";
    std::cout << "false-positive candidate " << fp << "; positions:";
    for (std::size_t i = 0; i < f.hashes(); ++i) std::cout << ' ' << f.position(fp, i);
    std::cout << "\ncontains(" << fp << ")=" << f.contains(fp)
              << " (NOT inserted: false positive)\n";
}
