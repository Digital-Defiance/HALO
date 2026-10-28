import copy
import json
from pathlib import Path
import shlex
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'halo'))
import joint_marked as joint
import joint_rule_search as search
import marked_polyform as marked
import marked_charge


class DomainTests(unittest.TestCase):
    def test_default_unknown_domains_and_invalid_bounds(self):
        edges,domains=joint.rule_domains([(0,0)])
        self.assertEqual(len(edges),6)
        self.assertEqual(domains,[7]*6)
        for invalid in ([7]*5,[0]*6,[8]*6,[True]*6):
            with self.assertRaises(ValueError):joint.rule_domains([(0,0)],invalid)
        with self.assertRaises(ValueError):joint.synthesize([(0,0)],3,net=0)
        with self.assertRaises(ValueError):joint.synthesize([(0,0)],0)

    def test_rule_orbit_uses_body_symmetries_and_preserves_charge(self):
        for n in (1,2,4):
            cells,marks=marked.mann_pillar(n)
            orbit=search.rule_orbit(cells,marks)
            self.assertGreater(len(orbit),1)
            self.assertEqual(len(set(orbit)),len(orbit))
            self.assertTrue(all(sum(word)==-1 for word in orbit))
            labels=marked.boundary_marks(cells,marks)
            self.assertIn(tuple(labels[e] for e in sorted(labels)),orbit)

    def test_process_error_cannot_become_unsat(self):
        rows=[{'event':'expanded','level':1,'transforms':1,'variables':1},
              {'event':'result','level':1,'status':'unsat'}]
        with tempfile.TemporaryDirectory() as folder:
            binary=Path(folder)/'bad'
            binary.write_text('#!/bin/sh\nprintf \'%s\\n\' '+
                ' '.join(shlex.quote(json.dumps(row)) for row in rows)+'\nexit 2\n')
            binary.chmod(0o755)
            result=joint.synthesize([(0,0)],1,seconds=5,reserve_mb=0,binary=binary)
        self.assertEqual(result['status'],'solver-error')
        self.assertEqual(result['lower_bound'],0)

    def test_memory_stop_remains_unresolved(self):
        with tempfile.TemporaryDirectory() as folder:
            binary=Path(folder)/'sleep'
            binary.write_text('#!/bin/sh\nexec /bin/sleep 10\n');binary.chmod(0o755)
            with mock.patch.object(joint.runner,'rss_mb',return_value=1000):
                result=joint.synthesize([(0,0)],1,seconds=5,mem_mb=1,reserve_mb=0,binary=binary)
        self.assertEqual(result['status'],'memout')
        self.assertEqual(result['lower_bound'],0)
        self.assertNotIn('marks',result)


class SearchTests(unittest.TestCase):
    def test_deferred_rules_do_not_become_a_family_exclusion(self):
        cells,marks=marked.mann_pillar(2)
        first={'status':'verified','marks':marks}
        for conclusive in (False,True):
            extension={'status':'classified-in-marked-grid' if conclusive else 'timeout',
                       'hc':3 if conclusive else None,'lower_bound':3,'levels':[]}
            with mock.patch.object(joint,'synthesize',side_effect=[first,{'status':'unsat'}]), \
                 mock.patch.object(marked,'run',return_value=extension):
                rows=list(search.search(cells,target=5,synthesis_level=1,total_seconds=20))
            self.assertEqual(rows[-1]['status'],'remaining-space-unsat')
            self.assertEqual(rows[-1]['family_target_excluded'],conclusive)
            self.assertEqual(rows[-1]['deferred'],0 if conclusive else 1)

    def test_verified_lower_bound_survives_a_later_resource_cap(self):
        cells,marks=marked.mann_pillar(2)
        with mock.patch.object(joint,'synthesize',return_value={'status':'verified','marks':marks}), \
             mock.patch.object(marked,'run',return_value={'status':'timeout','hc':None,'lower_bound':4,'levels':[]}):
            rows=list(search.search(cells,target=4,synthesis_level=1,total_seconds=20))
        self.assertEqual(rows[-1]['status'],'target-reached-in-marked-model')
        self.assertEqual(rows[-1]['lower_bound'],4)


@unittest.skipUnless(joint.DEFAULT_BINARY.exists(),'build the isolated joint solver first')
class NativeTests(unittest.TestCase):
    def test_three_rings_without_markings_and_four_impossible(self):
        positive=joint.synthesize([(0,0)],3,seconds=5,reserve_mb=0)
        self.assertEqual(positive['status'],'verified',positive)
        self.assertEqual(positive['fixed_edges'],0)
        self.assertEqual(positive['verification']['copies'],37)
        self.assertEqual(sum(m[-1] for m in positive['marks']),-1)
        negative=joint.synthesize([(0,0)],4,seconds=5,reserve_mb=0)
        self.assertEqual(negative['status'],'unsat',negative)
        self.assertEqual(negative['lower_bound'],0)
        flipped=joint.synthesize([(0,0)],3,net=1,seconds=5,reserve_mb=0)
        self.assertEqual(flipped['status'],'verified',flipped)
        self.assertEqual(sum(m[-1] for m in flipped['marks']),1)

    def test_dihex_four_rings_and_separate_fixed_rule_classifier(self):
        cells=[(0,0),(1,0)]
        result=joint.synthesize(cells,4,seconds=10,mem_mb=1000,reserve_mb=0)
        self.assertEqual(result['status'],'verified',result)
        self.assertEqual(result['fixed_edges'],0)
        if marked.DEFAULT_BINARY.exists():
            forward=marked.run(cells,result['marks'],maxlevel=5,seconds=10,mem_mb=1000,reserve_mb=0)
            self.assertEqual(forward['hc'],4,forward)

    def test_domains_and_exclusion_of_exact_and_symmetric_rules(self):
        body=[(0,0)]
        impossible=joint.synthesize(body,1,domains=[2]*6,seconds=5,reserve_mb=0)
        self.assertEqual(impossible['status'],'unsat')
        original=joint.synthesize(body,3,seconds=5,reserve_mb=0)
        self.assertEqual(original['status'],'verified')
        labels=marked.boundary_marks(body,original['marks']);edges=sorted(labels)
        word=[labels[e] for e in edges]
        other=joint.synthesize(body,3,blocked_rules=[word],seconds=5,reserve_mb=0)
        self.assertEqual(other['status'],'verified',other)
        other_labels=marked.boundary_marks(body,other['marks'])
        self.assertNotEqual(word,[other_labels[e] for e in edges])
        blocked=search.rule_orbit(body,original['marks'])
        exhausted=joint.synthesize(body,3,blocked_rules=blocked,seconds=5,reserve_mb=0)
        self.assertEqual(exhausted['status'],'unsat',exhausted)

    def test_verifier_rejects_missing_marks_wrong_domains_and_wrong_net(self):
        body=[(0,0)]
        result=joint.synthesize(body,3,seconds=5,reserve_mb=0)
        self.assertEqual(result['status'],'verified')
        answer={k:result[k] for k in ('marks','placements')}
        incomplete=copy.deepcopy(answer);incomplete['marks'].pop()
        with self.assertRaises(ValueError):joint.check_solution(body,[7]*6,-1,3,incomplete)
        with self.assertRaisesRegex(ValueError,'domain'):
            joint.check_solution(body,[2]*6,-1,3,answer)
        with self.assertRaisesRegex(ValueError,'net-charge'):
            joint.check_solution(body,[7]*6,1,3,answer)

    def test_fit_feedback_preserves_a_genuinely_better_rule(self):
        body=[(0,0)]
        word=(1,1,-1,0,-1,-1)  # sign reversal of an independently checked Hc=1 word
        marks=[[0,0,dx,dy,q] for (dx,dy),q in zip(marked_charge.DIRS,word)]
        labels=marked.boundary_marks(body,marks)
        vector=[labels[e] for e in sorted(labels)]
        result=joint.synthesize(body,3,fit_exclusions=[vector],seconds=5,reserve_mb=0)
        self.assertEqual(result['status'],'verified',result)
        self.assertGreater(result['fit_gain_counts'][0],0)
        self.assertTrue(marked.legal_relative_fits(body,result['marks'])-
                        marked.legal_relative_fits(body,marks))

    @unittest.skipUnless(marked.DEFAULT_BINARY.exists(),'fixed-rule backend required')
    def test_resume_checks_the_proof_and_does_not_recheck_the_same_rule(self):
        cells,marks=marked.mann_pillar(1)
        forward=marked.run(cells,marks,maxlevel=4,seconds=5,reserve_mb=0)
        self.assertEqual(forward['hc'],3)
        prior={'cells':cells,'marks':marks,'extension':forward}
        rows=list(search.search(cells,target=4,synthesis_level=3,total_seconds=10,
                                prior_checked=[prior],reserve_mb=0))
        self.assertEqual(rows[-1]['status'],'remaining-space-unsat',rows[-1])
        self.assertTrue(rows[-1]['family_target_excluded'])
        self.assertEqual(rows[-1]['tested'],0)
        self.assertEqual(rows[-1]['reused_forward_checks'],1)
        bad=copy.deepcopy(prior);bad['extension']['status']='timeout';bad['extension']['hc']=None
        with self.assertRaises(ValueError):list(search.search(cells,target=4,prior_checked=[bad]))
        changed=copy.deepcopy(prior);changed['extension']['input_sha256']='0'*64
        with self.assertRaises(ValueError):list(search.search(cells,target=4,prior_checked=[changed]))


if __name__=='__main__':
    unittest.main()
