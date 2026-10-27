from pathlib import Path
import shutil
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'halo'))
import patch_repair as repair
import pose_synthesis as poses
import shape
import verify

ROOT=Path(__file__).resolve().parents[1]


def unit_witness():
    copies=[(0,*poses.IDENTITY)] + [(1,1,0,x,0,1,y) for x,y in shape.NEIGHBOURS['H']]
    return repair.witness_text('H',[(0,0)],copies,1), copies


def fix(model,copies):
    for i,(_,a,b,x,d,e,y) in enumerate(copies):
        r=model.syms.index((a,b,d,e))
        for symbol,value in ((f'r{i}',r),(f'x{i}',x),(f'y{i}',y)):
            model.add(f'(= {symbol} {poses.smt_int(value)})')


class AlgebraTests(unittest.TestCase):
    def test_grid_group_composition_and_inverse_with_reflections(self):
        for grid in ('O','H'):
            for a,b,d,e in shape.SYMMETRIES[grid]:
                A=(a,b,-3,d,e,7)
                self.assertEqual(poses.compose(A,poses.inverse(A)),poses.IDENTITY)
                self.assertEqual(poses.compose(poses.inverse(A),A),poses.IDENTITY)
                B=(1,0,5,0,1,-11)
                for point in [(0,0),(-2,5),(4,-1)]:
                    self.assertEqual(repair.transform(poses.compose(A,B),point),
                                     repair.transform(A,repair.transform(B,point)))

    def test_graph_discards_all_absolute_transforms(self):
        text=(ROOT/'shapes/reference/hex11_h4.witness.txt').read_text()
        grid,cells,graph=poses.graph_from_witness(text)
        self.assertEqual(set(graph),{'levels','edges','root'})
        self.assertEqual(len(graph['levels']),62)
        self.assertIn((0,0),cells)
        self.assertEqual(max(graph['levels']),4)

    def test_model_parser_rejects_duplicate_and_incomplete_values(self):
        self.assertEqual(poses.parse_values('((r0 2) (x0 (- 3)) (y0 5))'),
                         {'r0':2,'x0':-3,'y0':5})
        for text in ('((x0 1) (x0 2))','((x0 2)','((x0 2)))'):
            with self.assertRaises(ValueError):
                poses.parse_values(text)


@unittest.skipUnless(shutil.which('z3'),'Z3 CLI required')
class SolverTests(unittest.TestCase):
    def test_known_hex_patch_reconstructs_and_impossible_contacts_are_unsat(self):
        text,_=unit_witness()
        grid,cells,graph=poses.graph_from_witness(text)
        for weighted in (True,False):
            model=poses.PoseModel(grid,cells,graph,weighted)
            result=poses.solve(model,seconds=5,reserve_mb=0)
            self.assertEqual(result['status'],'sat',result)
            copies,images=model.decode(result['values'])
            self.assertTrue(verify.verify(repair.witness_text(grid,cells,copies,1))[0])
        graph=dict(graph,edges=[list(e) for e in graph['edges']])
        graph['edges'][0][2]=999
        model=poses.PoseModel(grid,cells,graph)
        self.assertEqual(poses.solve(model,seconds=5,reserve_mb=0)['status'],'unsat')

    def test_real_first_corona_with_all_noncentral_poses_free(self):
        text=(ROOT/'shapes/reference/hex11_h4.witness.txt').read_text()
        grid,cells,graph=poses.graph_from_witness(text,1)
        model=poses.PoseModel(grid,cells,graph)
        result=poses.solve(model,seconds=5,reserve_mb=0)
        self.assertEqual(result['status'],'sat',result)
        copies,_=model.decode(result['values'])
        self.assertTrue(verify.verify(repair.witness_text(grid,cells,copies,1))[0])

    def test_overlap_and_enclosure_cuts_preserve_known_valid_layout(self):
        text,valid=unit_witness()
        grid,cells,graph=poses.graph_from_witness(text)
        for failure in ('overlap','coverage'):
            model=poses.PoseModel(grid,cells,graph)
            bad=list(valid)
            bad[1]=bad[2] if failure=='overlap' else (1,1,0,2,0,1,0)
            images=[{repair.transform(p[1:],q) for q in cells} for p in bad]
            cuts=model.refine(bad,images)
            self.assertGreater(cuts.get(failure,0),0)
            fix(model,valid)
            self.assertEqual(poses.solve(model,seconds=5,reserve_mb=0)['status'],'sat')

    def test_hole_cut_allows_filling_the_hole_and_rejects_unchanged_wall(self):
        text,valid=unit_witness()
        grid,cells,graph=poses.graph_from_witness(text)
        model=poses.PoseModel(grid,cells,graph)
        bad=list(valid)
        bad[0]=(0,1,0,5,0,1,5)  # six copies now surround an empty origin
        images=[{repair.transform(p[1:],q) for q in cells} for p in bad]
        formulas=list(model.hole_formulas(bad,images))
        self.assertEqual(len(formulas),1)
        model.add(formulas[0])
        fix(model,valid)  # the central tile fills the same wall's anchor
        self.assertEqual(poses.solve(model,seconds=5,reserve_mb=0)['status'],'sat')
        # Isolate the hole predicate from root/contact/enclosure constraints.
        isolated=poses.PoseModel(grid,cells,graph)
        isolated.lines=[ln for ln in isolated.lines if not ln.startswith('(assert ')]
        isolated.add(formulas[0])
        fix(isolated,bad)
        self.assertEqual(poses.solve(isolated,seconds=5,reserve_mb=0)['status'],'unsat')


if __name__=='__main__':
    unittest.main()
