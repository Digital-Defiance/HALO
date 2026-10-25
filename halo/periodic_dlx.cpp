// HALO periodic tiling detector, C++ / Dancing Links version of halo/periodic.py.
//
// A shape tiles the plane periodically iff copies of it (in grid orientations) exactly
// partition some torus Z^2/L. We try sublattices L of index t*area, t = 1..max_t, one per
// orbit under the grid's point symmetries, each as an exact-cover problem solved with
// Knuth's Algorithm X on dancing links. Any solution is re-verified before reporting.
//
// Build:  c++ -O2 -std=c++17 -o periodic_dlx halo/periodic_dlx.cpp
// Usage:  periodic_dlx "O 0 0 1 0 ..." [max_t=24] [budget_seconds=30]
// Output: one JSON object, e.g.
//   {"status":"tiles","t":4,"lattice":[[32,0],[3,1]],"tried":45,"seconds":0.01}
// status: tiles | not_found | budget | unsupported
#include <algorithm>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <set>
#include <sstream>
#include <string>
#include <utility>
#include <vector>

using namespace std;
using Clock = chrono::steady_clock;

struct Mat { long a, b, d, e; };  // x' = a x + b y, y' = d x + e y

static vector<Mat> symmetries(char grid) {
    if (grid == 'O')
        return {{1, 0, 0, 1}, {0, -1, 1, 0}, {-1, 0, 0, -1}, {0, 1, -1, 0},
                {-1, 0, 0, 1}, {1, 0, 0, -1}, {0, 1, 1, 0}, {0, -1, -1, 0}};
    if (grid == 'H') {  // same generation order as halo/shape.py
        auto mul = [](Mat m, Mat n) {
            return Mat{m.a * n.a + m.b * n.d, m.a * n.b + m.b * n.e, m.d * n.a + m.e * n.d, m.d * n.b + m.e * n.e};
        };
        Mat rot{0, -1, 1, 1}, ref{0, 1, 1, 0}, m{1, 0, 0, 1};
        vector<Mat> out;
        for (int i = 0; i < 6; i++) {
            out.push_back(m);
            out.push_back(mul(m, ref));
            m = mul(rot, m);
        }
        return out;
    }
    return {};
}

static long fdiv(long p, long q) { long r = p / q; if ((p % q != 0) && ((p < 0) != (q < 0))) r--; return r; }
static long fmod_(long p, long q) { long r = p % q; if (r < 0) r += (q < 0 ? -q : q); return r; }

static void egcd(long p, long q, long &g, long &s, long &t) {
    long r0 = p, r1 = q, s0 = 1, s1 = 0, t0 = 0, t1 = 1;
    while (r1 != 0) {
        long k = r0 / r1;
        long r2 = r0 - k * r1; r0 = r1; r1 = r2;
        long s2 = s0 - k * s1; s0 = s1; s1 = s2;
        long t2 = t0 - k * t1; t0 = t1; t1 = t2;
    }
    if (r0 < 0) { r0 = -r0; s0 = -s0; t0 = -t0; }
    g = r0; s = s0; t = t0;
}

struct Lat { long a, b, d; bool operator<(const Lat &o) const { return tie(a, b, d) < tie(o.a, o.b, o.d); } };

static Lat hnf(long x1, long y1, long x2, long y2) {
    long det = x1 * y2 - x2 * y1; if (det < 0) det = -det;
    long g, s, t; egcd(y1, y2, g, s, t);
    long a = det / g;
    long wx = s * x1 + t * x2;
    return {a, fmod_(wx, a), g};
}

// ---------------- dancing links ----------------
struct DLX {
    vector<int> L, R, U, D, C, row, S;
    int ncols;
    long nodes = 0, node_limit;
    Clock::time_point deadline;
    bool out_of_budget = false;
    vector<int> sol;

    DLX(int nc, long limit, Clock::time_point dl) : ncols(nc), node_limit(limit), deadline(dl) {
        int n = nc + 1;
        L.resize(n); R.resize(n); U.resize(n); D.resize(n); C.resize(n); row.assign(n, -1); S.assign(nc + 1, 0);
        for (int i = 0; i <= nc; i++) { L[i] = i - 1; R[i] = i + 1; U[i] = D[i] = i; C[i] = i; }
        L[0] = nc; R[nc] = 0;
    }
    void add_row(int r, const vector<int> &cols) {  // cols are 0-based column ids
        int first = -1;
        for (int c0 : cols) {
            int c = c0 + 1;
            int x = (int)L.size();
            L.push_back(x); R.push_back(x); U.push_back(U[c]); D.push_back(c); C.push_back(c); row.push_back(r);
            D[U[c]] = x; U[c] = x; S[c]++;
            if (first < 0) first = x;
            else { R[x] = first; L[x] = L[first]; R[L[first]] = x; L[first] = x; }
        }
    }
    void cover(int c) {
        R[L[c]] = R[c]; L[R[c]] = L[c];
        for (int i = D[c]; i != c; i = D[i])
            for (int j = R[i]; j != i; j = R[j]) { D[U[j]] = D[j]; U[D[j]] = U[j]; S[C[j]]--; }
    }
    void uncover(int c) {
        for (int i = U[c]; i != c; i = U[i])
            for (int j = L[i]; j != i; j = L[j]) { S[C[j]]++; D[U[j]] = j; U[D[j]] = j; }
        R[L[c]] = c; L[R[c]] = c;
    }
    bool search() {
        if (R[0] == 0) return true;
        if ((++nodes & 4095) == 0 && (Clock::now() > deadline || nodes > node_limit)) { out_of_budget = true; return false; }
        int c = R[0];
        for (int j = R[0]; j != 0; j = R[j]) if (S[j] < S[c]) c = j;
        if (S[c] == 0) return false;
        cover(c);
        for (int r = D[c]; r != c; r = D[r]) {
            sol.push_back(row[r]);
            for (int j = R[r]; j != r; j = R[j]) cover(C[j]);
            if (search()) return true;
            for (int j = L[r]; j != r; j = L[j]) uncover(C[j]);
            sol.pop_back();
            if (out_of_budget) break;
        }
        uncover(c);
        return false;
    }
};

int main(int argc, char **argv) {
    if (argc < 2) { fprintf(stderr, "usage: periodic_dlx \"GRID x y ...\" [max_t] [budget]\n"); return 2; }
    int max_t = argc > 2 ? atoi(argv[2]) : 24;
    double budget = argc > 3 ? atof(argv[3]) : 30.0;
    auto t0 = Clock::now();
    auto deadline = t0 + chrono::microseconds((long)(budget * 1e6));
    auto secs = [&]() { return chrono::duration<double>(Clock::now() - t0).count(); };

    istringstream in(argv[1]);
    string head; in >> head;
    char grid = head[0];
    vector<pair<long, long>> cells; long x, y;
    while (in >> x >> y) cells.push_back({x, y});
    vector<Mat> syms = symmetries(grid);
    if (syms.empty() || cells.empty()) { printf("{\"status\":\"unsupported\"}\n"); return 0; }
    long area = (long)cells.size();

    // distinct orientations, normalized to min corner
    set<vector<pair<long, long>>> seen;
    vector<vector<pair<long, long>>> orients;
    for (auto &m : syms) {
        vector<pair<long, long>> p;
        for (auto &c : cells) p.push_back({m.a * c.first + m.b * c.second, m.d * c.first + m.e * c.second});
        long mx = p[0].first, my = p[0].second;
        for (auto &q : p) { mx = min(mx, q.first); my = min(my, q.second); }
        for (auto &q : p) { q.first -= mx; q.second -= my; }
        sort(p.begin(), p.end());
        if (seen.insert(p).second) orients.push_back(p);
    }

    int tried = 0, t = 0;
    for (t = 1; t <= max_t; t++) {
        long n = t * area;
        for (long a = 1; a <= n; a++) {
            if (n % a) continue;
            long d = n / a;
            for (long b = 0; b < a; b++) {
                if (Clock::now() > deadline) {
                    printf("{\"status\":\"budget\",\"tried\":%d,\"t_reached\":%d,\"seconds\":%.3f}\n", tried, t, secs());
                    return 0;
                }
                // one lattice per symmetry orbit
                Lat me{a, b, d}; bool canon = true;
                for (auto &m : syms) {
                    Lat c = hnf(m.a * a, m.d * a, m.a * b + m.b * d, m.d * b + m.e * d);
                    if (c < me) { canon = false; break; }
                }
                if (!canon) continue;
                // placements on the torus
                set<vector<int>> rowset;
                vector<vector<int>> rows;
                for (auto &o : orients)
                    for (long ty = 0; ty < d; ty++)
                        for (long tx = 0; tx < a; tx++) {
                            vector<int> idx;
                            idx.reserve(o.size());
                            for (auto &q : o) {
                                long xx = q.first + tx, yy = q.second + ty;
                                long k = fdiv(yy, d);
                                yy -= k * d; xx -= k * b;
                                xx = fmod_(xx, a);
                                idx.push_back((int)(yy * a + xx));
                            }
                            sort(idx.begin(), idx.end());
                            if (adjacent_find(idx.begin(), idx.end()) != idx.end()) continue;
                            if (rowset.insert(idx).second) rows.push_back(idx);
                        }
                if ((long)rows.size() < t) continue;
                tried++;
                DLX dlx((int)n, 50000000L, deadline);
                for (int r = 0; r < (int)rows.size(); r++) dlx.add_row(r, rows[r]);
                bool ok = dlx.search();
                if (ok) {
                    vector<int> cover(n, 0);
                    for (int r : dlx.sol) for (int c : rows[r]) cover[c]++;
                    bool good = (long)dlx.sol.size() * area == n;
                    for (int v : cover) good = good && v == 1;
                    if (!good) { printf("{\"status\":\"error\",\"error\":\"invalid cover\"}\n"); return 1; }
                    printf("{\"status\":\"tiles\",\"t\":%d,\"lattice\":[[%ld,0],[%ld,%ld]],\"tried\":%d,\"seconds\":%.3f}\n",
                           t, a, b, d, tried, secs());
                    return 0;
                }
                if (dlx.out_of_budget) {
                    printf("{\"status\":\"budget\",\"tried\":%d,\"t_reached\":%d,\"seconds\":%.3f}\n", tried, t, secs());
                    return 0;
                }
            }
        }
    }
    printf("{\"status\":\"not_found\",\"tried\":%d,\"max_t\":%d,\"seconds\":%.3f}\n", tried, max_t, secs());
    return 0;
}
