// Included inside HeeschSolver's public section in an isolated build only.
// Pair incompatibility is an extra non-coexistence relation. All geometric
// adjacency reduction and geometry-only tiling shortcuts must be disabled.
void setMarkedPairFilter(const std::function<bool(const xform_t&)>& allowed)
{
    if (level_ != 0 || reduce_ || check_isohedral_ || check_periodic_) {
        throw std::runtime_error("marked filter requires a fresh unreduced solver without tiling shortcuts");
    }
    auto filter = [&](auto& transforms) {
        std::vector<xform_t> rejected;
        for (const auto& T : transforms) if (!allowed(T)) rejected.push_back(T);
        for (const auto& T : rejected) {
            transforms.erase(T);
            cloud_.overlapping_.insert(T);
        }
    };
    filter(cloud_.adjacent_);
    filter(cloud_.adjacent_culled_);
    filter(cloud_.adjacent_hole_);
    std::set<std::pair<int,int>> covered;
    for (const auto& T : cloud_.adjacent_) for (const auto& p : shape_) {
        const auto q = T*p;
        covered.insert({q.x_,q.y_});
    }
    for (const auto& p : cloud_.halo_) {
        if (!covered.count({p.x_,p.y_})) cloud_.surroundable_ = false;
    }
}

CMSat::lbool markedPatch(patch_t& patch, uint64_t max_conflicts)
{
    patch.clear();
    if (!cloud_.surroundable_) return CMSat::l_False;
    CMSat::SATSolver solver;
    solver.set_num_threads(1);
    solver.new_vars(next_var_);
    solver.set_max_confl(max_conflicts);
    // Pairwise-hole pruning is avoided here. Check every complete prefix and
    // block its exact selected/unselected assignment so filling a hole remains
    // available. This is deliberately conservative and may cost more clauses.
    getClauses(solver,true);
    while (true) {
        auto status = solver.solve();
        if (status != CMSat::l_True) return status;
        const auto& model = solver.get_model();
        bool rejected = false;
        for (size_t level=1; level<=level_; ++level) {
            HoleFinder<grid> finder {shape_};
            for (const auto& tile : tiles_) {
                for (auto v : tile.levelRange(0,level+1)) {
                    if (model[v.second] == CMSat::l_True) {
                        finder.addCopy(tile.index_,tile.T_);
                        break;
                    }
                }
            }
            std::vector<std::vector<tile_index>> holes;
            if (finder.getHoles(holes)) {
                std::vector<CMSat::Lit> block;
                for (const auto& tile : tiles_) {
                    for (auto v : tile.levelRange(0,level+1)) {
                        block.push_back(model[v.second] == CMSat::l_True ? neg(v.second) : pos(v.second));
                    }
                }
                solver.add_clause(block);
                rejected = true;
                break;
            }
        }
        if (!rejected) {
            getSolution(solver,patch,level_);
            return CMSat::l_True;
        }
    }
}
