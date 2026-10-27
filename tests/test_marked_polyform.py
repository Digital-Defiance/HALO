import json
from pathlib import Path
import shlex
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'halo'))
import marked_charge
import marked_polyform as marked
import patch_repair as repair
import shape


class MarkTests(unittest.TestCase):
    def test_pillar_mark_counts_and_flat_end(self):
        for n in (2,3,4):
            cells,marks=marked.mann_pillar(n)
            values=[m[-1] for m in marks]
            self.assertEqual(len(cells),n)
            self.assertEqual(values.count(1),2*n)
            self.assertEqual(values.count(-1),2*n+1)
            self.assertEqual(values.count(0),1)
            self.assertEqual(sum(values),-1)

    def test_marks_reject_internal_edges_and_duplicates(self):
        with self.assertRaises(ValueError):
            marked.boundary_marks([(0,0),(1,0)],[[0,0,1,0,1]])
        with self.assertRaises(ValueError):
            marked.boundary_marks([(0,0)],[[0,0,1,0,1]]*2)

    def test_independent_checker_rejects_bad_labels(self):
        copies=[(0,1,0,0,0,1,0)]+[(1,1,0,x,0,1,y) for x,y in shape.NEIGHBOURS['H']]
        valid=marked.verify_patch([(0,0)],[],copies,1)
        self.assertEqual(valid['boundary_charge'],0)
        marks=[[0,0,dx,dy,1] for dx,dy in marked_charge.DIRS]
        with self.assertRaisesRegex(ValueError,'do not match'):
            marked.verify_patch([(0,0)],marks,copies,1)

    def test_resource_stop_keeps_a_verified_lower_bound_and_no_hc(self):
        copies=[(0,1,0,0,0,1,0)]+[(1,1,0,x,0,1,y) for x,y in shape.NEIGHBOURS['H']]
        row={'level':1,'status':'sat','seconds':0,'placements':copies}
        with tempfile.TemporaryDirectory() as folder:
            binary=Path(folder)/'fake'
            binary.write_text('#!/bin/sh\nprintf \'%s\\n\' '+shlex.quote(json.dumps(row))+'\nexec /bin/sleep 10\n')
            binary.chmod(0o755)
            result=marked.run([(0,0)],[],seconds=1,reserve_mb=0,binary=binary)
        self.assertEqual(result['status'],'timeout')
        self.assertIsNone(result['hc'])
        self.assertEqual(result['lower_bound'],1)


@unittest.skipUnless(marked.DEFAULT_BINARY.exists(),'build the isolated marked solver first')
class NativeTests(unittest.TestCase):
    def test_flat_tiler_is_unresolved_at_bound_and_charge_word_agrees(self):
        flat=marked.run([(0,0)],[],maxlevel=2,seconds=5,reserve_mb=0)
        self.assertEqual(flat['status'],'unresolved')
        self.assertIsNone(flat['hc'])
        self.assertEqual(flat['lower_bound'],2)
        word=(-2,1,-1,2,-1,2)
        marks=[[0,0,dx,dy,q] for (dx,dy),q in zip(marked_charge.DIRS,word)]
        record=marked.run([(0,0)],marks,maxlevel=3,seconds=5,reserve_mb=0)
        self.assertEqual(record['hc'],1)

    def test_known_marked_hc4_pillar_and_all_prefix_witnesses(self):
        cells,marks=marked.mann_pillar(2)
        result=marked.run(cells,marks,maxlevel=6,seconds=10,mem_mb=1000,reserve_mb=0)
        self.assertEqual(result['status'],'classified-in-marked-grid',result)
        self.assertEqual(result['hc'],4)
        self.assertEqual(result['levels'][-1]['status'],'unsat')
        self.assertEqual([r['level'] for r in result['levels'] if 'verification' in r],[1,2,3,4])


if __name__=='__main__':
    unittest.main()
