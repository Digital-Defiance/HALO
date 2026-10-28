// Joint ternary boundary rules and corona placements on a fixed polyhex body.
#include <array>
#include <chrono>
#include <iostream>
#include <map>
#include <set>
#include <stdexcept>
#include "heesch.h"

using grid=HexGrid<int16_t>;
using EdgeKey=std::array<int,4>;
using TransformKey=std::array<int,6>;
static const int dirs[6][2]={{1,0},{0,1},{-1,1},{-1,0},{0,-1},{1,-1}};

int main(int argc,char** argv)
{
    try {
        size_t target=argc>1 ? std::stoul(argv[1]) : 3;
        uint64_t conflicts=argc>2 ? std::stoull(argv[2]) : 2000000;
        size_t rounds=argc>3 ? std::stoul(argv[3]) : 256;
        if (target<1 || target>12 || !conflicts || !rounds) throw std::runtime_error("invalid limits");
        int n;
        if (!(std::cin>>n) || n<1 || n>200) throw std::runtime_error("invalid tile size");
        Shape<grid> shape;
        std::set<std::pair<int,int>> occupied;
        for (int i=0;i<n;++i) {
            int x,y;
            if (!(std::cin>>x>>y) || x < -100 || x>100 || y < -100 || y>100 || !occupied.insert({x,y}).second)
                throw std::runtime_error("invalid cell");
            shape.add(x,y);
        }
        shape.complete();
        if (!shape.simplyConnected()) throw std::runtime_error("body must be a disk");
        std::map<EdgeKey,size_t> indices;
        std::vector<EdgeKey> edges;
        for (auto [x,y]:occupied) for (const auto& d:dirs) {
            if (!occupied.count({x+d[0],y+d[1]})) edges.push_back({x,y,d[0],d[1]});
        }
        std::sort(edges.begin(),edges.end());
        for (size_t i=0;i<edges.size();++i) indices[edges[i]]=i;
        int m,net;
        if (!(std::cin>>m>>net) || m!=int(edges.size())) throw std::runtime_error("invalid boundary domains");
        std::vector<unsigned> domains(m);
        for (auto& d:domains) if (!(std::cin>>d) || !d || d>7) throw std::runtime_error("invalid charge domain");
        HeeschSolver<grid> solver {shape,ALL,false};
        int blocked=0;
        if (std::cin>>blocked) {
            if (blocked<0 || blocked>100000) throw std::runtime_error("invalid exclusion count");
            for (int i=0;i<blocked;++i) {
                std::vector<int> word(m);
                for (auto& q:word) if (!(std::cin>>q) || q < -1 || q>1) throw std::runtime_error("invalid excluded rule");
                solver.joint_blocked_.push_back(word);
            }
            int fit_exclusions=0;
            if (std::cin>>fit_exclusions) {
                if (fit_exclusions<0 || fit_exclusions>100000) throw std::runtime_error("invalid fit exclusions");
                for (int i=0;i<fit_exclusions;++i) {
                    std::vector<int> word(m);
                    for (auto& q:word) if (!(std::cin>>q) || q < -1 || q>1) throw std::runtime_error("invalid fit-excluded rule");
                    solver.joint_fit_exclusions_.push_back(word);
                }
                std::string extra;
                if (std::cin>>extra) throw std::runtime_error("extra input");
            } else if (!std::cin.eof()) throw std::runtime_error("invalid fit exclusion trailer");
        } else if (!std::cin.eof()) throw std::runtime_error("invalid input trailer");
        if (argc>4 && std::string(argv[4])=="lazy") solver.joint_eager_=false;
        std::map<TransformKey,std::vector<HeeschSolver<grid>::JointContact>> cache;
        solver.setJointMarkedRules(domains,net,[&](const grid::xform_t& T) {
            TransformKey key {T.a_,T.b_,T.c_,T.d_,T.e_,T.f_};
            auto found=cache.find(key);
            if (found!=cache.end()) return found->second;
            std::vector<HeeschSolver<grid>::JointContact> pairs;
            for (size_t f=0;f<edges.size();++f) {
                auto e=edges[f];
                auto a=T*grid::point_t(e[0],e[1]);
                auto b=T*grid::point_t(e[0]+e[2],e[1]+e[3]);
                if (occupied.count({b.x_,b.y_})) {
                    auto it=indices.find({b.x_,b.y_,a.x_-b.x_,a.y_-b.y_});
                    if (it==indices.end()) throw std::runtime_error("invalid contact edge");
                    pairs.push_back({it->second,f});
                }
            }
            cache[key]=pairs;
            return pairs;
        },rounds);
        for (size_t level=1;level<=target;++level) {
            solver.increaseLevel();
            auto stats=solver.jointMarkedStats();
            std::cout<<"{\"event\":\"expanded\",\"level\":"<<level<<",\"transforms\":"<<stats[0]
                     <<",\"variables\":"<<stats[1]<<"}"<<std::endl;
        }
        HeeschSolver<grid>::patch_t patch;
        auto start=std::chrono::steady_clock::now();
        auto result=solver.markedPatch(patch,conflicts);
        auto stats=solver.jointMarkedStats();
        std::cout<<"{\"event\":\"result\",\"encoding\":\"factored-global-fits-v2\",\"level\":"<<target<<",\"status\":\""
                 <<(result==CMSat::l_True?"sat":result==CMSat::l_False?"unsat":"unknown")
                 <<"\",\"rounds\":"<<stats[2]<<",\"match_cuts\":"<<stats[3]
                 <<",\"solve_seconds\":"<<std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count();
        if (result==CMSat::l_True) {
            std::cout<<",\"marks\":[";
            for (size_t i=0;i<edges.size();++i) {
                if (i) std::cout<<',';
                auto e=edges[i];
                std::cout<<'['<<e[0]<<','<<e[1]<<','<<e[2]<<','<<e[3]<<','<<solver.joint_solution_[i]<<']';
            }
            std::cout<<"],\"placements\":[";
            bool first=true;
            for (const auto& [level,T]:patch) {
                if (!first) std::cout<<',';first=false;
                std::cout<<'['<<level<<','<<T.a_<<','<<T.b_<<','<<T.c_<<','<<T.d_<<','<<T.e_<<','<<T.f_<<']';
            }
            std::cout<<']';
        }
        std::cout<<"}"<<std::endl;
    } catch (const std::exception& error) {
        std::cerr<<error.what()<<std::endl;return 2;
    }
}
