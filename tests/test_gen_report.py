import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'halo'))
import gen_report


class GeneratorReportTests(unittest.TestCase):
    def test_parent_unique_hits_run_filter_and_full_cost(self):
        rows = [
            {'generator': 'search-sweep2', 'parent': 'H 0 0', 'canon': 'H 0 0 1 0',
             'run_id': 'new', 'cells': 18, 'status': 'nontiler', 'hc': 3, 'seconds': 2,
             'total_seconds': 7, 'defect_seconds': 4, 'retried_from': {'seconds': 3}},
            {'generator': 'search-sweep2', 'parent': 'H 0 0', 'canon': 'H 0 0 1 0',
             'run_id': 'new', 'cells': 18, 'status': 'nontiler', 'hc': 4, 'seconds': 1},
            {'generator': 'search-sweep2', 'parent': 'H 0 0', 'canon': 'H 0 0 2 0',
             'run_id': 'new', 'cells': 18, 'status': 'memout', 'seconds': 5},
            {'generator': 'search', 'parent': 'H 0 0', 'run_id': 'new', 'cells': 18, 'status': 'isohedral'},
            {'generator': 'search-sweep2', 'parent': 'H 0 0', 'run_id': 'old', 'cells': 18,
             'status': 'nontiler', 'hc': 7},
        ]
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'log.jsonl'
            p.write_text(''.join(json.dumps(r) + '\n' for r in rows))
            stats, snapshot = gen_report.collect_stats(p, run_id='new', min_cells=18,
                generator='search-sweep2', by_parent=True)
        row, = gen_report.parent_rows(stats)
        self.assertEqual((row['checks'], row['unique_hc3plus'], row['unique_hc4plus'], row['unique_hc5plus']),
                         (3, 1, 1, 0))
        self.assertEqual((row['unsettled'], row['worker_seconds']), (1, 20))
        self.assertEqual(snapshot['partial_rows'], 0)

    def test_byte_snapshot_and_partial_tail_are_read_only(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'log.jsonl'
            good = json.dumps({'generator': 'search', 'status': 'nontiler', 'hc': 2}) + '\n'
            p.write_text(good)
            old_size = p.stat().st_size
            with p.open('a') as f:
                f.write(good + '{"partial":')
            before = p.read_bytes()
            stats, _ = gen_report.collect_stats(p, snapshot_bytes=old_size)
            self.assertEqual(stats['search']['n'], 1)
            stats, metadata = gen_report.collect_stats(p)
            self.assertEqual(stats['search']['n'], 2)
            self.assertEqual(metadata['partial_rows'], 1)
            self.assertEqual(p.read_bytes(), before)

    def test_manifest_selects_last_started_run(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'log.jsonl'
            Path(str(p) + '.runs.jsonl').write_text('\n'.join([
                json.dumps({'event': 'started', 'run_id': 'first'}),
                json.dumps({'event': 'started', 'run_id': 'second'}),
                json.dumps({'event': 'generator_guard_warning', 'run_id': 'first'}), 'broken']) + '\n')
            self.assertEqual(gen_report.latest_run(p), 'second')

    def test_default_generator_histogram_still_counts_completed_records(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'log.jsonl'
            p.write_text('{"generator":"search","status":"nontiler","hc":3}\n' * 2 + 'broken\n')
            stats, meta = gen_report.collect_stats(p)
            self.assertEqual(stats['search']['hc'], {3: 2})
            self.assertEqual(meta['malformed_rows'], 1)


if __name__ == '__main__':
    unittest.main()
