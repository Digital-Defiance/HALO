// Experimental marked-polyhex driver. No geometry-only tiling classification.
#include <array>
#include <chrono>
#include <iostream>
#include <map>
#include <set>
#include <stdexcept>
#include "heesch.h"

using grid = HexGrid<int16_t>;
using point_t = grid::point_t;
using EdgeKey = std::array<int,4>;
static const int directions[6][2]={{1,0},{0,1},{-1,1},{-1,0},{0,-1},{1,-1}};

int main(int argc,char** argv)
{
    try {
        size_t maxlevel=argc>1 ? std::stoul(argv[1]) : 7;
        uint64_t conflicts=argc>2 ? std::stoull(argv[2]) : 2000000;
        if (maxlevel<1 || maxlevel>=MAX_CORONA || !conflicts) throw std::runtime_error("invalid limits");
        int n;
        if (!(std::cin>>n) || n<1 || n>200) throw std::runtime_error("invalid tile size");
        Shape<grid> shape;
        std::set<std::pair<int,int>> occupied;
        for (int i=0;i<n;++i) {
            int x,y;
            if (!(std::cin>>x>>y) || abs(x)>100 || abs(y)>100 || !occupied.insert({x,y}).second)
                throw std::runtime_error("invalid cell");
            shape.add(x,y);
        }
        shape.complete();
        if (!shape.simplyConnected()) throw std::runtime_error("tile must be a disk");
        std::map<EdgeKey,int> marks;
        for (const auto& [x,y] : occupied) for (const auto& d : directions) {
            if (!occupied.count({x+d[0],y+d[1]})) marks[{x,y,d[0],d[1]}]=0;
        }
        int m;
        if (!(std::cin>>m) || m<0 || m>int(marks.size())) throw std::runtime_error("invalid marks");
        std::set<EdgeKey> seen;
        for (int i=0;i<m;++i) {
            int x,y,dx,dy,q;
            if (!(std::cin>>x>>y>>dx>>dy>>q) || abs(q)>100) throw std::runtime_error("invalid mark");
            EdgeKey edge{x,y,dx,dy};
            if (!marks.count(edge) || !seen.insert(edge).second) throw std::runtime_error("mark is not a unique boundary edge");
            marks[edge]=q;
        }
        std::string extra;
        if (std::cin>>extra) throw std::runtime_error("extra input");
        HeeschSolver<grid> solver {shape,ALL,false};
        solver.setMarkedPairFilter([&](const grid::xform_t& T) {
            for (const auto& [edge,q] : marks) {
                point_t a=T*point_t(edge[0],edge[1]);
                point_t b=T*point_t(edge[0]+edge[2],edge[1]+edge[3]);
                if (occupied.count({b.x_,b.y_})) {
                    auto found=marks.find({b.x_,b.y_,a.x_-b.x_,a.y_-b.y_});
                    if (found==marks.end() || found->second+q!=0) return false;
                }
            }
            return true;
        });
        for (size_t level=1;level<=maxlevel;++level) {
            auto start=std::chrono::steady_clock::now();
            solver.increaseLevel();
            HeeschSolver<grid>::patch_t patch;
            auto result=solver.markedPatch(patch,conflicts);
            const char* status=result==CMSat::l_True ? "sat" : result==CMSat::l_False ? "unsat" : "unknown";
            double seconds=std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count();
            std::cout<<"{\"level\":"<<level<<",\"status\":\""<<status<<"\",\"seconds\":"<<seconds;
            if (result==CMSat::l_True) {
                std::cout<<",\"placements\":[";
                bool first=true;
                for (const auto& [lev,T] : patch) {
                    if (!first) std::cout<<',';
                    first=false;
                    std::cout<<'['<<lev<<','<<T.a_<<','<<T.b_<<','<<T.c_<<','<<T.d_<<','<<T.e_<<','<<T.f_<<']';
                }
                std::cout<<']';
            }
            std::cout<<"}"<<std::endl;
            if (result!=CMSat::l_True) break;
        }
    } catch (const std::exception& error) {
        std::cerr<<error.what()<<std::endl;
        return 2;
    }
}
