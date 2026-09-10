// Follow-up experiment motivated by the main run: absent queries were slower
// despite the early return. Compare early exit against a full scan on the SAME
// reconstructed layout. The diagnostic filter is not the submitted core API.
#include "bloom.hpp"
#include <algorithm>
#include <array>
#include <chrono>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <random>
#include <string>

volatile std::size_t sink = 0;
struct Diagnostic {
    bloom::BloomFilter mapping;
    std::vector<std::uint64_t> words;
    Diagnostic(std::size_t m, std::size_t k, std::uint64_t seed):mapping(m,k,seed),words(m/64+(m%64!=0),0){}
    void insert(std::uint64_t x) {
        mapping.insert(x);
        for (std::size_t i=0;i<mapping.hashes();++i) { auto p=mapping.position(x,i);words[p/64]|=UINT64_C(1)<<(p%64); }
    }
    bool full(std::uint64_t x) const {
        bool result=true;
        for (std::size_t i=0;i<mapping.hashes();++i) {auto p=mapping.position(x,i);result &= (words[p/64] & (UINT64_C(1)<<(p%64))) != 0;}
        return result;
    }
    std::size_t probes(std::uint64_t x) const {
        for(std::size_t i=0;i<mapping.hashes();++i) {auto p=mapping.position(x,i);if(!(words[p/64]&(UINT64_C(1)<<(p%64)))) return i+1;}
        return mapping.hashes();
    }
};
int main(int argc,char** argv){
    if(argc!=2){std::cerr<<"Usage: early_exit NEW_OUTPUT.csv\n";return 2;}
    if(std::ifstream(argv[1]).good()){std::cerr<<"Refusing to overwrite existing result\n";return 2;}
    std::ofstream csv(argv[1]); if(!csv)return 1;
    csv<<"seed,n,k,negative_fraction,repeat,method,ns_per_query,mean_probes,returned_positive\n"<<std::setprecision(12);
    for(int seed=1;seed<=4;++seed)for(std::size_t n:{20000u,200000u}){
        Diagnostic f(n*10,7,seed); const auto offset=static_cast<std::uint64_t>(seed)<<40;
        for(std::size_t i=0;i<n;++i)f.insert(bloom::mix64(offset+i));
        for(int absent:{0,1}){
            std::vector<std::uint64_t> query;std::mt19937_64 rng(seed*997+n+absent);
            for(std::size_t i=0;i<200000;++i)query.push_back(bloom::mix64(offset+(absent?(UINT64_C(1)<<32)+i:rng()%n)));
            std::shuffle(query.begin(),query.end(),rng);
            std::size_t probes=0,expected=0;
            for(auto x:query){if(f.mapping.contains(x)!=f.full(x)){std::cerr<<"layout mismatch\n";return 1;}probes+=f.probes(x);expected+=f.full(x);}
            auto run=[&](int method){std::size_t count=0;if(method==0)for(auto x:query)count+=f.mapping.contains(x);else for(auto x:query)count+=f.full(x);return count;};
            for(int method:{0,1})sink+=run(method);
            for(int rep=0;rep<7;++rep){std::array<int,2> order{0,1};std::shuffle(order.begin(),order.end(),rng);
                for(auto method:order){auto start=std::chrono::steady_clock::now();auto count=run(method);
                    auto ns=std::chrono::duration<double,std::nano>(std::chrono::steady_clock::now()-start).count();sink+=count;
                    if(count!=expected)return 1;
                    csv<<seed<<','<<n<<",7,"<<absent<<','<<rep<<','<<(method==0?"early_exit":"full_scan")<<','<<ns/query.size()<<','<<(method==0?double(probes)/query.size():7.)<<','<<count<<'\n';
                }
            }
        }
    }
    std::cout<<"Ablation complete; checksum="<<sink<<'\n';return csv?0:1;
}
