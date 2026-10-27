from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'halo'))
import marked_screen as screen
import shape


class ScreenTests(unittest.TestCase):
    def test_small_body_counts_and_one_unit_imbalance(self):
        self.assertEqual(len(screen.bodies(4)),7)
        self.assertEqual(len(screen.bodies(5)),22)
        candidates=list(screen.candidates(4))
        self.assertEqual(len(candidates),117)
        self.assertEqual(len({screen.canonical_marked(*c) for c in candidates}),117)
        for cells,marks in candidates:
            self.assertEqual(sum(m[-1] for m in marks),-1)
            self.assertTrue(shape.check_cells('H',cells)[0])

    def test_canonicalization_transforms_marks_and_reflections_together(self):
        cells,marks=next(screen.candidates(4))
        expected=screen.canonical_marked(cells,marks)
        for a,b,d,e in shape.SYMMETRIES['H']:
            body=[(a*x+b*y+13,d*x+e*y-7) for x,y in cells]
            labels=[[a*x+b*y+13,d*x+e*y-7,a*dx+b*dy,d*dx+e*dy,q]
                    for x,y,dx,dy,q in marks]
            self.assertEqual(screen.canonical_marked(body,labels),expected)

    def test_pillar_swaps_preserve_charge_and_exclude_the_unchanged_control(self):
        import marked_polyform
        cells,marks=marked_polyform.mann_pillar(4)
        baseline=screen.canonical_marked(cells,marks)
        variants=list(screen.marking_swaps(4))
        self.assertGreater(len(variants),20)
        for body,labels in variants:
            self.assertEqual(sum(m[-1] for m in labels),-1)
            self.assertNotEqual(screen.canonical_marked(body,labels),baseline)


if __name__=='__main__':
    unittest.main()
