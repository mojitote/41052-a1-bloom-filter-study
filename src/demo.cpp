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
    std::cout << "contains(10)=" << f.contains(10) << " (inserted)\n"
              << "contains(" << fp << ")=" << f.contains(fp) << " (NOT inserted: false positive)\n";
    if (argc > 1) {
        // Deliberate, isolated mutation demonstration, not the real implementation.
        std::uint64_t correct = 0, broken = 0;
        for (auto x : {10, 20}) for (std::size_t i = 0; i < f.hashes(); ++i) {
            auto mask = UINT64_C(1) << f.position(x, i);
            correct |= mask;
            broken = mask; // What breaks if |= becomes = ? Earlier bits disappear.
        }
        bool good = true, bad = true;
        for (std::size_t i = 0; i < f.hashes(); ++i) {
            auto mask = UINT64_C(1) << f.position(10, i);
            good = good && (correct & mask); bad = bad && (broken & mask);
        }
        std::cout << "Mutation |= to =: inserted key 10, correct=" << good << ", broken=" << bad << '\n';
        return good && !bad ? 0 : 1;
    }
}
