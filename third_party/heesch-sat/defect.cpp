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
// Usage: defect [-maxlevel n] [-maxd n] [-confl n] [file]

#include <iostream>
#include <cstdint>
#include <cstring>
#include <chrono>
#include <fstream>
#include <filesystem>

#include "heesch.h"
#include "grid.h"
#include "tileio.h"

using namespace std;

static size_t max_level = 7;
static size_t max_d = 64;
static uint64_t max_confl = 2000000;

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
	bool ok = ds.minDefect(max_d, max_confl, d, ring, exact);
	double secs = chrono::duration<double>(chrono::steady_clock::now() - t0).count();
	cout << "{\"status\": \"nontiler\", \"hc\": " << hc << ", \"hh\": " << hh
		<< ", \"level\": " << (hc + 1) << ", \"defect\": " << (ok ? (long)d : -1L)
		<< ", \"ring\": " << ring << ", \"exact\": " << (exact ? "true" : "false")
		<< ", \"seconds\": " << secs << "}" << endl;
	return true;
}

int main(int argc, char **argv)
{
	const char *inname = nullptr;
	for (int idx = 1; idx < argc; ++idx) {
		if (!strcmp(argv[idx], "-maxlevel")) {
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
