from pathlib import Path
import itertools
import shutil
import sys
import types
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'halo'))
import outer_synthesis as outer
import patch_repair as repair
import shape
import template_synthesis
import verify

ROOT = Path(__file__).resolve().parents[1]
PARENT = 'H 0 1 0 2 1 1 1 2 1 3 2 1 2 3 3 0 3 2 4 0 4 2'


class PoolTests(unittest.TestCase):
    def test_collision_filter_keeps_every_small_feasible_joint_edit_pose(self):
        source = {(0, 0), (1, 0)}
        prefix = [[0, 1, 0, 0, 0, 1, 0]]
        poses, info = outer.outer_pool('H', source, prefix, 1, 2, 2,
                                       radius=1, max_poses=10000)
        self.assertFalse(info['pool_capped'])
        poses = set(poses)
        checked = 0
        window = outer.cell_window('H', source, 1)
        for cells in map(set, itertools.combinations(window, 2)):
            if len(cells ^ source) > 2 or not shape.connected('H', sorted(cells)):
                continue
            for a, b, d, e in shape.SYMMETRIES['H']:
                for dx, dy in itertools.product(range(-4, 5), repeat=2):
                    image = {(a*x+b*y+dx, d*x+e*y+dy) for x, y in cells}
                    if cells & image or not any((x+u, y+v) in cells for x, y in image
                                               for u, v in shape.NEIGHBOURS['H']):
                        continue
                    self.assertIn((1, a, b, dx, d, e, dy), poses)
                    checked += 1
        self.assertGreater(checked, 100)

    def test_caps_and_infeasible_prefix_are_explicit(self):
        source = [(0, 0)]
        prefix = [[0, 1, 0, 0, 0, 1, 0]]
        poses, info = outer.outer_pool('H', source, prefix, 1, 0, 1, radius=0, max_poses=1)
        self.assertEqual(len(poses), 1)
        self.assertTrue(info['pool_capped'])
        poses, info = outer.outer_pool('H', source, prefix + [[1, 1, 0, 0, 0, 1, 0]],
                                       2, 0, 1, radius=0)
        self.assertEqual(poses, [])
        self.assertEqual(info['prefix_feasible_deletion_masks'], 0)

    def test_fixed_tile_pool_contains_full_held_out_known_outer_ring(self):
        text = (ROOT / 'shapes/reference/hex11_h4.witness.txt').read_text()
        grid, cells, hc, _, copies = verify.parse_witness(text)
        prefix = [[k, *T] for k, T in copies if k < hc]
        gold = {tuple([k, *T]) for k, T in copies if k == hc}
        poses, info = outer.outer_pool(grid, cells, prefix, hc, 0, len(cells),
                                       radius=0, max_poses=4096)
        self.assertFalse(info['pool_capped'])
        self.assertTrue(gold <= set(poses))


class HoleCutTests(unittest.TestCase):
    def test_cut_allows_filling_anchor_or_breaking_wall_and_rejects_same_hole(self):
        cnf = repair.CNF()
        occupied = cnf.variable()
        cnf.add([occupied])
        wall = [(1, 1, 0, x, 0, 1, y) for x, y in shape.NEIGHBOURS['H']]
        fill = (1, 1, 0, 0, 0, 1, 0)
        placements = [(p, cnf.variable()) for p in wall + [fill]]
        model = types.SimpleNamespace(grid='H', variables={(0, 0): occupied},
                                      cnf=cnf, placements=placements)
        self.assertEqual(outer.add_fixed_tile_hole_cuts(model, [(0, 0)], wall), [1])
        selected = {occupied} | {selector for p, selector in placements if p in wall}
        self.assertFalse(cnf.satisfied_by(selected))
        self.assertTrue(cnf.satisfied_by(selected | {placements[-1][1]}))
        for _, selector in placements[:-1]:
            self.assertTrue(cnf.satisfied_by(selected - {selector}))
        cnf._seen.remove((occupied,))
        with self.assertRaisesRegex(ValueError, 'fixed occupied'):
            outer.add_fixed_tile_hole_cuts(model, [(0, 0)], wall)


@unittest.skipUnless(shutil.which('cryptominisat5'), 'CryptoMiniSat required')
class SynthesisControlTests(unittest.TestCase):
    def test_recovers_hc4_without_supplying_any_outer_poses(self):
        text = (ROOT / 'shapes/reference/hex11_h4.witness.txt').read_text()
        sketch, info = template_synthesis.make_sketch(PARENT, text)
        # The synthesis function receives no reference last-ring placements.
        sketch['placements'] = [p for p in sketch['placements'] if p[0] < sketch['level']]
        negative = list(outer.prefix_synthesis(sketch, info, 2, seconds=5, reserve_mb=0))
        self.assertEqual(negative[-1]['status'], 'prefix-unsat')
        rows = list(outer.prefix_synthesis(sketch, info, 4, seconds=5, reserve_mb=0,
                                           max_shapes=1, max_layouts=16))
        answer = rows[-1]
        self.assertEqual(answer['status'], 'verified', [r['status'] for r in rows])
        self.assertEqual(answer['canon'], info['template_tile'])
        self.assertEqual(answer['verified_lower_bound'], 4)
        self.assertTrue(verify.verify(answer['witness'])[0])
        self.assertTrue(any(row.get('hole_cut_sizes') for row in rows))


if __name__ == '__main__':
    unittest.main()
