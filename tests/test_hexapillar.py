"""Regression tests for the hexapillar construction experiment (no checker binary needed).

Run: python3 -m unittest discover -s tests -v
"""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "halo"))
import hexapillar as hp  # noqa: E402
import shape  # noqa: E402


class HexapillarTests(unittest.TestCase):
    def test_macro_hexagons_tile(self):
        for k in (2, 3, 4):
            ok, msg = hp.check_tiling(k)
            self.assertTrue(ok, msg)
            self.assertEqual(len(hp.macro_hex((0, 0), k)), 3 * k * k - 3 * k + 1)

    def test_marking_counts_and_limits(self):
        for k, n, cells in ((2, 4, 27), (3, 4, 75)):
            got, bumps, nicks = hp.hexapillar(n, k)
            self.assertEqual((len(got), bumps, nicks), (cells, 2 * n, 2 * n + 1))
            ok, problems, _ = shape.check(shape.canonical("H", got))
            self.assertTrue(ok, problems)

    def test_bump_fits_neighbour_nick(self):
        k = 3
        u = hp.lattice(k)
        for j in range(6):
            a, b = hp.edge_cells((0, 0), u[j], k)
            a2, b2 = hp.edge_cells(u[j], u[(j + 3) % 6], k)
            self.assertEqual((a, b), (b2, a2))

    def test_iamond_realization(self):
        cells, bumps, nicks = hp.iamond_hexapillar(4)
        self.assertEqual((len(cells), bumps, nicks), (23, 8, 9))
        self.assertTrue(hp.tri_connected(cells))
        self.assertEqual(sum(hp.tri_best_spans(cells)), 26)


if __name__ == "__main__":
    unittest.main()
