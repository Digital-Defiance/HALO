from pathlib import Path
import shutil
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'halo'))
import patch_repair as repair
import template_synthesis as synthesis
import shape

ROOT = Path(__file__).resolve().parents[1]
PARENT = 'H 0 1 0 2 1 1 1 2 1 3 2 1 2 3 3 0 3 2 4 0 4 2'


class TemplateTests(unittest.TestCase):
    def test_alignment_handles_rotation_translation_and_cell_edits(self):
        _, source = shape.parse(PARENT)
        moved = [(-y + 17, x + y - 9) for x, y in source]
        aligned, distance, _ = synthesis.align_cells('H', moved, source)
        self.assertEqual(distance, 0)
        self.assertEqual(set(aligned), set(source))

    @unittest.skipUnless(shutil.which('cryptominisat5'), 'CryptoMiniSat required')
    def test_recovers_known_hc4_from_hc3_using_target_template(self):
        text = (ROOT / 'shapes/reference/hex11_h4.witness.txt').read_text()
        sketch, metadata = synthesis.make_sketch(PARENT, text)
        self.assertEqual(metadata['aligned_distance'], 4)
        for edits, expected in [(2, 'unsat'), (4, 'sat')]:
            model = repair.RepairModel(sketch, edits, radius=2, min_cells=11, max_cells=11,
                                       freeze_interior=False)
            answer = repair.solve_cnf(model.cnf, timeout=5, reserve_mb=0)
            self.assertEqual(answer['status'], expected)
            if expected == 'sat':
                cells, placements = model.decode(answer['positive'])
                self.assertTrue(repair.validate_candidate(model, cells, placements)[0])
                self.assertEqual(shape.canonical('H', cells), metadata['template_tile'])


if __name__ == '__main__':
    unittest.main()
