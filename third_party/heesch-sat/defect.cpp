// HALO addition to heesch-sat: how close does a non-tiler come to its next corona?
//
// For each input shape (heesch-sat text format; classified records are used as
// they are, unclassified shapes are classified first), prints one JSON line:
//   {"status": "nontiler", "hc": k, "hh": h, "level": k+1, "defect": d,
//    "ring": r, "exact": true|false, "seconds": t}
// d = fewest cells next to a k-patch that a (k+1)-corona leaves uncovered (holes
// allowed in corona k+1), r = number of cells next to that k-patch. d = 0 means
// a (k+1)-corona exists with holes only away from the patch. "defect": -1 means
// none was found with at most -maxd uncovered cells (or the shape is not
// surroundable at all). Tilers and inconclusive shapes are reported by status only.
//
// Usage: defect [-maxlevel n] [-maxd n] [-confl n] [-patch] [file]
// -patch includes the best layout and required/uncovered cells in its own
// coordinate frame. It is a diagnostic partial patch, not a complete witness.

#include <iostream>
#include <cstdint>
#include <cstring>
#include <chrono>
#include <fstream>
#include <filesystem>
#include <map>
#include <set>

#include "heesch.h"
#include "grid.h"
#include "tileio.h"

using namespace std;

static size_t max_level = 7;
static size_t max_d = 64;
static uint64_t max_confl = 2000000;
static bool show_patch = false;

template<typename grid>
static void printPatch(const Shape<grid>& shape,
    const typename HeeschSolver<grid>::patch_t& patch, size_t hc)
{
    using point_t = typename grid::point_t;
    using pair_t = pair<int, int>;
    map<pair_t, size_t> occupied;
    set<pair_t> required;
    Shape<grid> halo, border;
    shape.getHaloAndBorder(halo, border);
    for (const auto& [level, T] : patch) {
        for (const auto& p : shape) {
            point_t q = T * p;
            occupied[{q.x_, q.y_}] = level;
        }
    }
    for (const auto& [level, T] : patch) {
        if (level != hc) continue;
        for (const auto& p : halo) {
            point_t q = T * p;
            pair_t key {q.x_, q.y_};
            auto it = occupied.find(key);
            if (it == occupied.end() || it->second > hc) required.insert(key);
        }
    }
    auto printCells = [](const auto& cells) {
        bool first = true;
        cout << '[';
        for (const auto& p : cells) {
            if (!first) cout << ',';
            first = false;
            cout << '[' << p.first << ',' << p.second << ']';
        }
        cout << ']';
    };
    set<pair_t> tile, uncovered;
    for (const auto& p : shape) tile.insert({p.x_, p.y_});
    for (const auto& p : required) {
        if (!occupied.count(p)) uncovered.insert(p);
    }
    cout << ", \"patch\": {\"grid\": \"" << gridTypeAbbreviation(grid::grid_type)
         << "\", \"level\": " << hc + 1 << ", \"cells\": ";
    printCells(tile);
    cout << ", \"placements\": [";
    bool first = true;
    for (const auto& [level, T] : patch) {
        if (!first) cout << ',';
        first = false;
        cout << '[' << level << ',' << int(T.a_) << ',' << int(T.b_) << ',' << int(T.c_)
             << ',' << int(T.d_) << ',' << int(T.e_) << ',' << int(T.f_) << ']';
    }
    cout << "], \"required\": ";
    printCells(required);
    cout << ", \"uncovered\": ";
    printCells(uncovered);
    cout << '}';
}

template<typename grid>
static bool computeDefect(TileInfo<grid>& info)
{
	auto t0 = chrono::steady_clock::now();
	if ((info.getRecordType() == TileInfo<grid>::UNKNOWN)
			|| (info.getRecordType() == TileInfo<grid>::INCONCLUSIVE)) {
		HeeschSolver<grid> solver {info.getShape(), ALL, true};
		solver.setCheckIsohedral(true);
		solver.solve(false, max_level, info);
	}
	const char *status = "unknown";
	switch (info.getRecordType()) {
		case TileInfo<grid>::HOLE: status = "hole"; break;
		case TileInfo<grid>::INCONCLUSIVE: status = "inconclusive"; break;
		case TileInfo<grid>::NONTILER: status = "nontiler"; break;
		case TileInfo<grid>::ISOHEDRAL: status = "isohedral"; break;
		default: break;
	}
	if (info.getRecordType() != TileInfo<grid>::NONTILER) {
		cout << "{\"status\": \"" << status << "\"}" << endl;
		return true;
	}
	size_t hc = info.getHeeschConnected();
	size_t hh = info.getHeeschHoles();

	HeeschSolver<grid> ds {info.getShape(), ALL, true};
	for (size_t i = 0; i <= hc; ++i) {
		ds.increaseLevel();
	}
	size_t d = 0, ring = 0;
	bool exact = false;
    typename HeeschSolver<grid>::patch_t patch;
	bool ok = ds.minDefect(max_d, max_confl, d, ring, exact, show_patch ? &patch : nullptr);
	double secs = chrono::duration<double>(chrono::steady_clock::now() - t0).count();
	cout << "{\"status\": \"nontiler\", \"hc\": " << hc << ", \"hh\": " << hh
		<< ", \"metric_version\": 2"
		<< ", \"level\": " << (hc + 1) << ", \"defect\": " << (ok ? (long)d : -1L)
		<< ", \"ring\": " << ring << ", \"exact\": " << (exact ? "true" : "false")
		<< ", \"seconds\": " << secs;
    if (show_patch && ok) printPatch<grid>(info.getShape(), patch, hc);
    cout << "}" << endl;
	return true;
}

int main(int argc, char **argv)
{
	const char *inname = nullptr;
	for (int idx = 1; idx < argc; ++idx) {
		if (!strcmp(argv[idx], "-patch")) {
            show_patch = true;
        } else if (!strcmp(argv[idx], "-maxlevel")) {
			max_level = atoi(argv[++idx]);
		} else if (!strcmp(argv[idx], "-maxd")) {
			max_d = atoi(argv[++idx]);
		} else if (!strcmp(argv[idx], "-confl")) {
			max_confl = strtoull(argv[++idx], nullptr, 10);
		} else if (filesystem::exists(argv[idx])) {
			inname = argv[idx];
		} else {
			cerr << "Argument \"" << argv[idx] << "\" is neither a file nor a parameter" << endl;
			return 1;
		}
	}
	if (inname) {
		ifstream ifs(inname);
		processInputStream(ifs, computeDefect);
	} else {
		processInputStream(cin, computeDefect);
	}
	return 0;
}
