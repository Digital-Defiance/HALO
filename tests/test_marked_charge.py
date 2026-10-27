import itertools
from pathlib import Path
import shutil
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'halo'))
import marked_charge as marked
import patch_repair as repair


def brute_first_ring(word):
    # Independent cyclic-word rotations/reflections, followed by exhaustive
    # orientation assignments to the six neighbours of the central hexagon.
    words=set()
    for reflected in (tuple(word),tuple(reversed(word))):
        for k in range(6):
            words.add(reflected[k:]+reflected[:k])
    domains=[[state for state in words if word[d]+state[(d+3)%6]==0]
             for d in range(6)]
    return any(all(states[d][(d+2)%6]+states[(d+1)%6][(d+5)%6]==0
                   for d in range(6)) for states in itertools.product(*domains))


class ChargeTests(unittest.TestCase):
    def test_ball_and_boundary_counts_independently(self):
        for r in range(9):
            cells=set(marked.ball(r))
            boundary=sum((x+dx,y+dy) not in cells for x,y in cells for dx,dy in marked.DIRS)
            self.assertEqual((len(cells),boundary),marked.counts(r))
        self.assertEqual(marked.counts(7),(169,90))
        self.assertEqual(marked.counts(8),(217,102))
        self.assertEqual(marked.charge_upper_bound(1,2),7)
        self.assertEqual(marked.charge_upper_bound(1,1),3)

    def test_every_cap2_pattern_against_exhaustive_first_ring(self):
        words=list(marked.patterns(2,1))
        self.assertEqual(len(words),140)
        satisfiable=0
        for word in words:
            brute=brute_first_ring(word)
            model=marked.MarkedModel(word,1)
            if model.contradiction is not None:
                self.assertFalse(brute)
            satisfiable+=brute
            certificate=marked.label_charge_certificate(word)
            self.assertLessEqual(certificate['upper_bound'],3)
            self.assertEqual(sum(certificate['weights'][q] for q in word),certificate['net'])
            for q in word:
                self.assertEqual(certificate['weights'][q],-certificate['weights'][-q])
        self.assertEqual(satisfiable,1)

    def test_balanced_labels_have_no_additive_obstruction(self):
        self.assertIsNone(marked.label_charge_certificate((-2,2,-1,1,0,0))['upper_bound'])


@unittest.skipUnless(shutil.which('cryptominisat5'),'CryptoMiniSat required')
class SolverTests(unittest.TestCase):
    def test_inverse_charge_target_three_has_a_witness_and_exact_upper_bound(self):
        result=marked.classify((-1,-1,0,1,1,1),maxlevel=3,reserve_mb=0)
        self.assertEqual(result['hc'],3)
        self.assertEqual(result['charge_upper_bound'],3)
        self.assertEqual(result['checks'][-1]['verified']['tiles'],37)

    def test_flat_hex_control_and_independent_assignment_rejection(self):
        model=marked.MarkedModel((0,)*6,3)
        result=repair.solve_cnf(model.cnf,timeout=5,reserve_mb=0)
        self.assertEqual(result['status'],'sat')
        assignment=model.decode(result['positive'])
        report=marked.verify_assignment(model.word,3,assignment)
        self.assertEqual(report['boundary_charge'],0)
        assignment.pop((0,0))
        with self.assertRaisesRegex(ValueError,'exactly'):
            marked.verify_assignment(model.word,3,assignment)

    def test_only_surroundable_cap2_pattern_has_exactly_one_ring(self):
        result=marked.classify((-2,1,-1,2,-1,2),reserve_mb=0)
        self.assertEqual(result['hc'],1)
        self.assertEqual(result['checks'][0]['verified']['boundary_charge'],7)
        self.assertEqual(result['checks'][1]['status'],'unsat')


if __name__=='__main__':
    unittest.main()
