// Paired exact-pipeline comparison. Both query variants use the SAME Bloom object.
#include "bloom.hpp"
#include <algorithm>
#include <array>
#include <chrono>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <random>
#include <unordered_set>
volatile std::size_t pipeline_sink = 0;
struct Hash { std::size_t operator()(std::uint64_t x) const noexcept { return bloom::mix64(x); } };
int main(int argc, char** argv) {
    if (argc != 2) { std::cerr << "Usage: pipeline_exit NEW_OUTPUT.csv\n"; return 2; }
    if (std::ifstream(argv[1]).good()) { std::cerr << "Refusing overwrite\n"; return 2; }
    std::ofstream out(argv[1]); if (!out) return 1;
    out << "seed,n,k,negative_fraction,repeat,method,ns_per_query,returned_positive,expected_positive,backend_calls\n" << std::setprecision(12);
    for (unsigned seed=1; seed<=4; ++seed) for (std::size_t n: {20000u,200000u}) for (std::size_t k: {1u,7u}) {
        bloom::BloomFilter f(n*10,k,seed);
        std::unordered_set<std::uint64_t,Hash> exact; exact.max_load_factor(1.0); exact.reserve(n);
        const auto offset=static_cast<std::uint64_t>(seed)<<40;
        for (std::size_t j=0;j<n;++j) { auto x=bloom::mix64(offset+j); exact.insert(x); f.insert(x); }
        for (unsigned percent: {0u,50u,90u,100u}) {
            const std::size_t total=200000, negatives=total*percent/100;
            std::mt19937_64 rng(seed*997+n+percent); // identical workload across k
            std::vector<std::uint64_t> query; query.reserve(total);
            for (std::size_t j=0;j<total;++j) query.push_back(bloom::mix64(offset+(j<negatives?(UINT64_C(1)<<32)+j:rng()%n)));
            std::shuffle(query.begin(),query.end(),rng);
            std::size_t backend=0;
            for(auto x:query) {
                const bool a=f.contains(x), b=f.contains_full_scan(x), truth=exact.count(x)!=0;
                if(a!=b || (a && truth)!=truth || (b && truth)!=truth) return 1;
                backend+=a;
            }
            auto run=[&](int method) {
                std::size_t count=0;
                if(method==0) for(auto x:query) count+=exact.find(x)!=exact.end();
                else if(method==1) for(auto x:query) count+=f.contains(x) && exact.find(x)!=exact.end();
                else for(auto x:query) count+=f.contains_full_scan(x) && exact.find(x)!=exact.end();
                return count;
            };
            for(int method:{0,1,2}) pipeline_sink+=run(method);
            for(int rep=0;rep<7;++rep) {
                std::array<int,3> order{0,1,2}; std::shuffle(order.begin(),order.end(),rng);
                for(int method:order) {
                    auto start=std::chrono::steady_clock::now(); auto count=run(method);
                    double ns=std::chrono::duration<double,std::nano>(std::chrono::steady_clock::now()-start).count(); pipeline_sink+=count;
                    if(count!=total-negatives) return 1;
                    out<<seed<<','<<n<<','<<k<<','<<percent/100.0<<','<<rep<<','
                       <<(method==0?"set":method==1?"early_exit":"full_scan")<<','<<ns/total<<','<<count<<','<<total-negatives<<','<<(method==0?total:backend)<<'\n';
                }
            }
        }
    }
    std::cout<<"PASS per-key equivalence and all timed counts; checksum="<<pipeline_sink<<'\n'; return out?0:1;
}
