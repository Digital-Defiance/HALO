import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("hex_budget", Path(__file__).resolve().parents[1] /
                                               "scripts/check_hex_chain_budget.py")
budget = importlib.util.module_from_spec(spec)
spec.loader.exec_module(budget)


class ConstructionBudgetTests(unittest.TestCase):
    def test_hexagon_area_and_valid_sparse_coordinates(self):
        for side in range(1, 5):
            cells = budget.hexagon(side)
            self.assertEqual(len(cells), 6 * side * side)
            self.assertTrue(all(x % 3 == y % 3 and x % 3 in (0, 1) for x, y in cells))

    def test_small_hexagon_matches_explicit_six_triangles(self):
        self.assertEqual(budget.hexagon(1), {(0, 0), (3, -3), (3, 0), (1, -2), (4, -2), (1, 1)})

    def test_four_hexagon_body_hits_span_before_cell_budget(self):
        small, subdivided, large = [budget.screen(4, s) for s in (1, 2, 3)]
        self.assertEqual((small['cells'], small['best_span_sum_minmax']), (24, 26))
        self.assertEqual((subdivided['cells'], subdivided['best_span_sum_minmax']), (96, 56))
        self.assertTrue(subdivided['body_within_cell_limit'])
        self.assertFalse(subdivided['body_within_span_limit'])
        self.assertEqual((large['cells'], large['best_span_sum_minmax']), (216, 86))
        self.assertFalse(large['body_within_cell_limit'])


if __name__ == '__main__':
    unittest.main()
