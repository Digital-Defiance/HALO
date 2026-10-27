import copy
import itertools
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "halo"))
import patch_repair as repair
import runner
import add_defects
import search
import shape


def hex_patch(missing=False):
    neighbours = shape.NEIGHBOURS["H"]
    if missing:
        neighbours = neighbours[:-1]
    return {"grid": "H", "level": 1, "cells": [[0, 0]],
            "placements": [[0, 1, 0, 0, 0, 1, 0]]
            + [[1, 1, 0, x, 0, 1, y] for x, y in neighbours]}


def satisfiable(clauses, assigned=None):
    """Tiny independent DPLL oracle for exhaustive cardinality truth tables."""
    clauses = [set(c) for c in clauses]
    while True:
        if not clauses:
            return True
        if any(not c for c in clauses):
            return False
        unit = next((next(iter(c)) for c in clauses if len(c) == 1), None)
        if unit is None:
            literal = next(iter(clauses[0]))
            return any(satisfiable(clauses + [{v}]) for v in (literal, -literal))
        clauses = [c - {-unit} for c in clauses if unit not in c]


class GeometryTests(unittest.TestCase):
    def test_failed_remeasurement_drops_legacy_patch(self):
        with tempfile.TemporaryDirectory() as d:
            source, output = Path(d) / "input.jsonl", Path(d) / "output.jsonl"
            source.write_text(json.dumps({"canon": "H 0 0", "cells": 1, "hc": 3, "hh": 3,
                "status": "nontiler", "defect": 1, "ring": 100, "defect_version": 1,
                "defect_patch": {"stale": True}}) + '\n')
            with mock.patch.object(sys, "argv", ['add_defects', str(source), '--out', str(output)]), \
                    mock.patch.object(runner, "run_defect", return_value={"defect": None, "defect_stop": "timeout"}):
                add_defects.main()
            record = json.loads(output.read_text())
            self.assertNotIn("defect_patch", record)
            self.assertNotIn("defect_version", record)
            self.assertIsNone(record['defect'])
            self.assertEqual(record['hc'], 3)

    def test_complete_and_partial_ring_counts(self):
        report = repair.analyze_patch(hex_patch())
        self.assertEqual((report["defect"], report["ring"], report["inner_verified"]), (0, 6, True))
        report = repair.analyze_patch(hex_patch(True))
        self.assertEqual((report["defect"], report["ring"]), (1, 6))

    def test_reject_tampered_geometry_counts_overlap_and_transform(self):
        for field, value in (("uncovered", [[100, 100]]), ("required", [])):
            patch = hex_patch()
            patch[field] = value
            with self.assertRaises(ValueError):
                repair.analyze_patch(patch)
        patch = hex_patch()
        patch["placements"][1][3] = patch["placements"][1][6] = 0
        with self.assertRaisesRegex(ValueError, "overlap"):
            repair.analyze_patch(patch)
        patch = hex_patch()
        patch["placements"][1][1] = 2
        with self.assertRaisesRegex(ValueError, "symmetry"):
            repair.analyze_patch(patch)

    def test_reject_reported_summary_mismatch(self):
        with self.assertRaisesRegex(ValueError, "reported defect"):
            repair.analyze_patch({"defect_patch": hex_patch(), "defect": 1, "ring": 6})

    def test_legacy_holed_prefix_is_not_a_valid_near_miss(self):
        path = ROOT / "tests/fixtures/legacy_h4_holed_patch.json"
        if not path.exists():
            self.skipTest("native diagnostic fixture not available")
        report = repair.analyze_patch(json.loads(path.read_text()))
        self.assertEqual((report["defect"], report["ring"]), (5, 169))
        self.assertFalse(report["inner_verified"])
        self.assertIn("hole", report["inner_message"])

    def test_search_ignores_unversioned_defect(self):
        old = {"defect": 1, "ring": 100}
        self.assertEqual(search.defect_frac(old), 1)
        self.assertEqual(search.defect_frac(dict(old, defect_version=2)), .01)


class EncodingTests(unittest.TestCase):
    def test_signed_cardinality_against_exhaustive_truth_table(self):
        for n in range(1, 6):
            for k in range(n + 1):
                cnf = repair.CNF()
                vs = [cnf.variable() for _ in range(n)]
                literals = [v if v % 2 else -v for v in vs]
                cnf.at_most(literals, k)
                for bits in itertools.product((False, True), repeat=n):
                    count = sum(bit if lit > 0 else not bit for bit, lit in zip(bits, literals))
                    units = [[v if bit else -v] for v, bit in zip(vs, bits)]
                    self.assertEqual(satisfiable(cnf.clauses + units), count <= k)

    def test_zero_edit_valid_fixture_and_missing_copy_unsat(self):
        for missing in (False, True):
            model = repair.RepairModel(hex_patch(missing), 0, radius=0, require_change=False)
            self.assertEqual(satisfiable(model.cnf.clauses), not missing)
        model = repair.RepairModel(hex_patch(), 0, radius=0, require_change=True)
        self.assertFalse(satisfiable(model.cnf.clauses))


@unittest.skipUnless(shutil.which("cryptominisat5"), "CryptoMiniSat CLI required")
class SolverTests(unittest.TestCase):
    def test_shared_boundary_edit_repairs_all_copies(self):
        patch = {"grid": "O", "level": 1, "cells": [[0, 0]],
                 "placements": [[int(x != 0 or y != 0), 1, 0, x, 0, 1, y]
                                for x in (-2, 0, 2) for y in (-1, 0, 1)]}
        # Nine unit squares have gaps; one shared horizontal cell addition
        # turns every copy into a domino and closes the complete corona.
        self.assertGreater(repair.analyze_patch(patch)["defect"], 0)
        model = repair.RepairModel(patch, 1, radius=1)
        result = repair.solve_cnf(model.cnf, timeout=5, reserve_mb=0)
        self.assertEqual(result["status"], "sat")
        cells, placements = model.decode(result["positive"])
        self.assertEqual(len(cells), 2)
        self.assertTrue(repair.validate_candidate(model, cells, placements)[0])

    def test_inner_and_outer_shifts_repair_a_missing_inner_copy(self):
        patch = hex_patch(True)
        cells = {(0, 0)} | set(shape.NEIGHBOURS["H"])
        ring2 = {(x + dx, y + dy) for x, y in cells for dx, dy in shape.NEIGHBOURS["H"]} - cells
        patch["level"] = 2
        patch["placements"] += [[2, 1, 0, x, 0, 1, y] for x, y in sorted(ring2)]
        fixed = repair.RepairModel(patch, 0, radius=0, require_change=False)
        self.assertEqual(repair.solve_cnf(fixed.cnf, timeout=5, reserve_mb=0)["status"], "unsat")
        shifted = repair.RepairModel(patch, 0, radius=0, require_change=False,
                                     outer_shifts=1, shift_from_level=1)
        result = repair.solve_cnf(shifted.cnf, timeout=5, reserve_mb=0)
        self.assertEqual(result["status"], "sat")
        new, placements = shifted.decode(result["positive"])
        self.assertTrue(repair.validate_candidate(shifted, new, placements)[0])

    def test_real_hc4_witness_is_preserved(self):
        import verify
        grid, cells, hc, _, placements = verify.parse_witness((ROOT / "shapes/hex21_h4.witness").read_text())
        patch = {"grid": grid, "cells": cells, "level": hc,
                 "placements": [[level, *T] for level, T in placements]}
        model = repair.RepairModel(patch, 0, radius=1, require_change=False)
        result = repair.solve_cnf(model.cnf, timeout=5, reserve_mb=0)
        self.assertEqual(result["status"], "sat")
        new, placements = model.decode(result["positive"])
        self.assertTrue(repair.validate_candidate(model, new, placements)[0])

    def test_real_model_decodes_and_verifies(self):
        model = repair.RepairModel(hex_patch(), 0, radius=0, require_change=False)
        result = repair.solve_cnf(model.cnf, timeout=5, reserve_mb=0)
        self.assertEqual(result["status"], "sat")
        cells, placements = model.decode(result["positive"])
        self.assertTrue(repair.validate_candidate(model, cells, placements)[0])
        model.block(result["positive"])
        self.assertEqual(repair.solve_cnf(model.cnf, timeout=5, reserve_mb=0)["status"], "unsat")

    def test_shifted_outer_options_repair_a_missing_copy(self):
        model = repair.RepairModel(hex_patch(True), 0, radius=0, require_change=False, outer_shifts=1)
        result = repair.solve_cnf(model.cnf, timeout=5, reserve_mb=0)
        self.assertEqual(result["status"], "sat")
        cells, placements = model.decode(result["positive"])
        self.assertTrue(repair.validate_candidate(model, cells, placements)[0])
        self.assertEqual(len(placements), 7)

    def test_timeout_and_memory_pressure_never_become_unsat(self):
        with tempfile.TemporaryDirectory() as d:
            binary = Path(d) / "solver"
            binary.write_text('#!' + sys.executable + '\nimport time\ntime.sleep(10)\n')
            binary.chmod(0o755)
            cnf = repair.CNF()
            cnf.add([cnf.variable()])
            with mock.patch.object(runner, "rss_mb", return_value=0):
                result = repair.solve_cnf(cnf, str(binary), timeout=.05, reserve_mb=0)
            self.assertEqual(result["status"], "timeout")
            with mock.patch.object(runner, "rss_mb", return_value=100):
                result = repair.solve_cnf(cnf, str(binary), timeout=1, mem_mb=1, reserve_mb=0)
            self.assertEqual(result["status"], "memout")


class ExportTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get("HALO_SLOW_TESTS") == "1", "opt-in native Hc=4 regression")
    def test_native_hc4_defect_excludes_holed_prefix(self):
        binary = runner.DEFAULT_DEFECT
        if not Path(binary).exists():
            self.skipTest("build the v2 diagnostic exporter first")
        line = (ROOT / "shapes/hex21_h4.witness").read_text().splitlines()[0]
        with runner.use_memory_budget(runner.MemoryBudget(24000, 8000)):
            record = runner.run_defect(line, 4, 4, timeout=120, mem_mb=20000,
                                       binary=binary, include_patch=True)
        self.assertIn("defect_patch", record, record)
        self.assertEqual(record["defect_version"], 2)
        self.assertTrue(repair.analyze_patch(record)["inner_verified"])

    def test_native_export_has_valid_inner_corona_and_exact_counts(self):
        binary = Path(runner.DEFAULT_DEFECT)
        if not binary.exists():
            self.skipTest("build the checked diagnostic exporter first")
        line = (ROOT / "shapes/reference/octomino_h1.txt").read_text().splitlines()[0]
        output = subprocess.run([str(binary), "-patch", "-maxd", "32", "-confl", "5000"],
                                input=line + '\n~ 1 1 0\n', text=True, capture_output=True,
                                check=True, timeout=15)
        record = json.loads(output.stdout.strip().splitlines()[-1])
        self.assertEqual(record["metric_version"], 2)
        report = repair.analyze_patch(record)
        self.assertTrue(report["inner_verified"], report)


if __name__ == "__main__":
    unittest.main()
