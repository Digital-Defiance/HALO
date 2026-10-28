// Appended inside the isolated solver's public section. Shared ternary edge
// rules and copy placements are solved together. No marking template required.
using JointContact = std::pair<size_t,size_t>;
std::vector<unsigned> joint_domains_;
std::vector<std::array<var_id,2>> joint_flags_; // positive, negative; neither = flat
std::vector<std::pair<xform_t,std::vector<JointContact>>> joint_relations_;
std::vector<var_id> joint_present_;
std::set<std::array<size_t,4>> joint_added_;
std::vector<int> joint_solution_;
std::vector<std::vector<int>> joint_blocked_;
std::vector<std::vector<int>> joint_fit_exclusions_;
int joint_net_ = -1;
size_t joint_rounds_ = 0;
size_t joint_limit_ = 256;
bool joint_eager_ = true;
size_t joint_gates_ = 0;

bool jointPairPossible(const std::vector<JointContact>& contacts) const
{
    size_t n=joint_domains_.size();
    std::vector<std::vector<size_t>> graph(n);
    for (auto [a,b] : contacts) {
        if (a>=n || b>=n) throw std::runtime_error("invalid rule-edge index");
        graph[a].push_back(b); graph[b].push_back(a);
    }
    std::vector<int> signs(n,0);
    std::set<int> reachable {0};
    for (size_t start=0; start<n; ++start) {
        if (signs[start]) continue;
        std::vector<size_t> nodes {start}; signs[start]=1;
        bool odd=false;
        for (size_t i=0; i<nodes.size(); ++i) {
            size_t a=nodes[i];
            for (size_t b : graph[a]) {
                if (!signs[b]) { signs[b]=-signs[a]; nodes.push_back(b); }
                else if (signs[b]!=-signs[a]) odd=true;
            }
        }
        std::set<int> contributions;
        for (int value=-1; value<=1; ++value) {
            if (odd && value) continue;
            bool allowed=true; int sum=0;
            for (size_t a : nodes) {
                int q=signs[a]*value;
                allowed &= bool(joint_domains_[a] & (1u<<(q+1)));
                sum+=q;
            }
            if (allowed) contributions.insert(sum);
        }
        std::set<int> next;
        for (int a : reachable) for (int b : contributions) next.insert(a+b);
        reachable.swap(next);
    }
    return reachable.count(joint_net_);
}

void setJointMarkedRules(const std::vector<unsigned>& domains, int net,
    const std::function<std::vector<JointContact>(const xform_t&)>& contacts,
    size_t round_limit=256)
{
    if (domains.empty() || !net || net < -int(domains.size()) || net>int(domains.size()) || !round_limit)
        throw std::runtime_error("invalid joint rule bounds");
    for (unsigned d : domains) if (!d || d>7) throw std::runtime_error("invalid rule domain");
    joint_domains_=domains; joint_net_=net; joint_limit_=round_limit;
    setMarkedPairFilter([&](const xform_t& T) { return jointPairPossible(contacts(T)); });
    for (const auto* transforms : {&cloud_.adjacent_, &cloud_.adjacent_culled_, &cloud_.adjacent_hole_}) {
        for (const auto& T : *transforms) joint_relations_.push_back({T,contacts(T)});
    }
    for (size_t i=0;i<domains.size();++i) joint_flags_.push_back({declareVariable(),declareVariable()});
}

static void jointAtMost(CMSat::SATSolver& solver, std::vector<CMSat::Lit> literals, int limit)
{
    if (limit<0) { solver.add_clause({}); return; }
    if (limit>=int(literals.size())) return;
    if (!limit) { for (auto p:literals) solver.add_clause({~p}); return; }
    std::vector<std::vector<CMSat::Lit>> layer;
    for (auto p:literals) layer.push_back({p});
    while (layer.size()>1) {
        std::vector<std::vector<CMSat::Lit>> next;
        for (size_t i=0;i+1<layer.size();i+=2) {
            const auto& a=layer[i]; const auto& b=layer[i+1];
            std::vector<CMSat::Lit> out;
            size_t count=std::min(size_t(limit+1),a.size()+b.size());
            for (size_t j=0;j<count;++j) { out.push_back(pos(solver.nVars())); solver.new_var(); }
            for (size_t ia=0;ia<=a.size();++ia) for (size_t ib=0;ib<=b.size();++ib) {
                if (!ia && !ib) continue;
                std::vector<CMSat::Lit> clause;
                if (ia) clause.push_back(~a[ia-1]);
                if (ib) clause.push_back(~b[ib-1]);
                clause.push_back(out[std::min(ia+ib,count)-1]);
                solver.add_clause(clause);
            }
            next.push_back(std::move(out));
        }
        if (layer.size()%2) next.push_back(layer.back());
        layer.swap(next);
    }
    solver.add_clause({~layer[0][limit]});
}

void addJointMarkedClauses(CMSat::SATSolver& solver)
{
    if (joint_flags_.empty()) return;
    joint_rounds_=0; joint_gates_=0; joint_added_.clear(); joint_solution_.clear(); joint_present_.clear();
    std::vector<CMSat::Lit> sum;
    for (size_t i=0;i<joint_flags_.size();++i) {
        auto [b,n]=joint_flags_[i]; unsigned domain=joint_domains_[i];
        solver.add_clause({neg(b),neg(n)});
        if (!(domain&1)) solver.add_clause({neg(n)});
        if (!(domain&2)) solver.add_clause({pos(b),pos(n)});
        if (!(domain&4)) solver.add_clause({neg(b)});
        sum.push_back(pos(b)); sum.push_back(neg(n));
    }
    int target=int(joint_flags_.size())+joint_net_;
    jointAtMost(solver,sum,target);
    for (auto& p:sum) p=~p;
    jointAtMost(solver,sum,int(sum.size())-target);
    for (const auto& word:joint_blocked_) {
        if (word.size()!=joint_flags_.size()) throw std::runtime_error("invalid blocked rule length");
        std::vector<CMSat::Lit> block;
        for (size_t i=0;i<word.size();++i) {
            auto [b,n]=joint_flags_[i];
            if (word[i]==-1) block.push_back(neg(n));
            else if (word[i]==1) block.push_back(neg(b));
            else if (!word[i]) { block.push_back(pos(b)); block.push_back(pos(n)); }
            else throw std::runtime_error("invalid blocked charge");
        }
        solver.add_clause(block);
    }
    for (const auto& tile:tiles_) {
        var_id present=solver.nVars(); solver.new_var(); joint_present_.push_back(present);
        std::vector<CMSat::Lit> back {neg(present)};
        for (auto v:tile) { solver.add_clause({neg(v.second),pos(present)}); back.push_back(pos(v.second)); }
        solver.add_clause(back);
    }
    if (!joint_eager_) {
        if (!joint_fit_exclusions_.empty()) throw std::runtime_error("fit exclusions require factored eager matching");
        return;
    }
    // One shared literal per rule-edge compatibility, then one per relative
    // fit. Every world occurrence reuses it. This avoids repeating four label
    // clauses for each contact of each pair of placed copies.
    std::map<JointContact,var_id> matches;
    std::map<std::vector<JointContact>,var_id> conjunctions;
    std::vector<std::pair<xform_t,var_id>> fits;
    for (const auto& [relative,contacts]:joint_relations_) {
        std::vector<JointContact> normalized;
        for (auto [e,f]:contacts) normalized.push_back(std::minmax(e,f));
        std::sort(normalized.begin(),normalized.end());
        normalized.erase(std::unique(normalized.begin(),normalized.end()),normalized.end());
        auto existing=conjunctions.find(normalized);
        if (existing!=conjunctions.end()) { fits.push_back({relative,existing->second}); continue; }
        std::vector<var_id> atoms;
        for (auto [e,f]:normalized) {
            auto found=matches.find({e,f});
            if (found!=matches.end()) { atoms.push_back(found->second); continue; }
            var_id m=solver.nVars(); solver.new_var(); matches[{e,f}]=m; atoms.push_back(m);
            auto [be,ne]=joint_flags_[e]; auto [bf,nf]=joint_flags_[f];
            solver.add_clause({neg(m),neg(be),pos(nf)});
            solver.add_clause({neg(m),pos(be),neg(nf)});
            solver.add_clause({neg(m),neg(ne),pos(bf)});
            solver.add_clause({neg(m),pos(ne),neg(bf)});
            solver.add_clause({neg(be),neg(nf),pos(m)});
            solver.add_clause({neg(ne),neg(bf),pos(m)});
            solver.add_clause({pos(be),pos(ne),pos(bf),pos(nf),pos(m)});
        }
        var_id fit;
        if (atoms.size()==1) fit=atoms[0];
        else {
            fit=solver.nVars(); solver.new_var();
            std::vector<CMSat::Lit> back {pos(fit)};
            for (auto m:atoms) { solver.add_clause({neg(fit),pos(m)}); back.push_back(neg(m)); }
            solver.add_clause(back);
        }
        conjunctions[normalized]=fit; fits.push_back({relative,fit});
    }
    // If a proved-below-target rule allowed A, any better rule must enable a
    // relative fit outside A. A rule whose fits are a subset of A cannot have
    // a corona absent for A. The caller records the forward UNSAT evidence.
    for (const auto& word:joint_fit_exclusions_) {
        if (word.size()!=joint_flags_.size()) throw std::runtime_error("invalid fit exclusion");
        std::set<var_id> gains;
        for (size_t i=0;i<joint_relations_.size();++i) {
            bool allowed=true;
            for (auto [e,f]:joint_relations_[i].second) allowed &= word[e]+word[f]==0;
            if (!allowed) gains.insert(fits[i].second);
        }
        std::vector<CMSat::Lit> clause;
        for (auto v:gains) clause.push_back(pos(v));
        solver.add_clause(clause);
    }
    for (const auto& tile:tiles_) for (const auto& [relative,fit]:fits) {
        auto j=getTile(tile.T_*relative);
        if (j==-1 || size_t(j)<=tile.index_) continue;
        solver.add_clause({neg(joint_present_[tile.index_]),neg(joint_present_[j]),pos(fit)});
        ++joint_gates_;
    }
}

bool refineJointMarkedClauses(CMSat::SATSolver& solver)
{
    if (joint_flags_.empty()) return false;
    ++joint_rounds_;
    const auto model=solver.get_model();
    auto value=[&](size_t edge) {
        auto [b,n]=joint_flags_[edge];
        return int(model[b]==CMSat::l_True)-int(model[n]==CMSat::l_True);
    };
    bool changed=false;
    for (const auto& tile:tiles_) {
        size_t i=tile.index_;
        if (model[joint_present_[i]]!=CMSat::l_True) continue;
        for (const auto& [relative,contacts]:joint_relations_) {
            auto index=getTile(tile.T_*relative);
            if (index==-1 || size_t(index)<=i || model[joint_present_[index]]!=CMSat::l_True) continue;
            for (auto [e,f]:contacts) {
                if (value(e)+value(f)==0) continue;
                if (joint_eager_) throw std::runtime_error("factored joint match constraint violated");
                if (!joint_added_.insert({i,size_t(index),e,f}).second)
                    throw std::runtime_error("joint solver violated an existing match constraint");
                auto [be,ne]=joint_flags_[e]; auto [bf,nf]=joint_flags_[f];
                auto x=neg(joint_present_[i]), y=neg(joint_present_[index]);
                solver.add_clause({x,y,neg(be),pos(nf)});
                solver.add_clause({x,y,pos(be),neg(nf)});
                solver.add_clause({x,y,neg(ne),pos(bf)});
                solver.add_clause({x,y,pos(ne),neg(bf)});
                changed=true;
            }
        }
    }
    return changed;
}

void captureJointMarkedSolution(const CMSat::SATSolver& solver)
{
    joint_solution_.clear();
    const auto& model=solver.get_model();
    for (auto [b,n]:joint_flags_)
        joint_solution_.push_back(int(model[b]==CMSat::l_True)-int(model[n]==CMSat::l_True));
}

std::array<size_t,4> jointMarkedStats() const
{
    return {tiles_.size(),next_var_,joint_rounds_,joint_gates_+joint_added_.size()};
}
