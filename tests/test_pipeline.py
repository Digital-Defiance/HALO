"""Pipeline regressions; no long search, training, or result-file writes.

Run: python3 -m unittest discover -s tests -v
"""
import argparse
import contextlib
import io
import json
import os
from pathlib import Path
import random
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "halo"))
import aner_scorer
import runner
import search
import shape
import scorer


def flood_reference(grid, cells):
    """Independent cell-by-cell exterior flood, including disconnected shapes."""
    occupied = set(cells)
    x0 = min(x for x, _ in cells) - 1
    x1 = max(x for x, _ in cells) + 1
    y0 = min(y for _, y in cells) - 1
    y1 = max(y for _, y in cells) + 1
    exterior = {(x0, y0)}
    todo = [(x0, y0)]
    for x, y in todo:
        for dx, dy in shape.NEIGHBOURS[grid]:
            p = x + dx, y + dy
            if (x0 <= p[0] <= x1 and y0 <= p[1] <= y1
                    and p not in occupied and p not in exterior):
                exterior.add(p)
                todo.append(p)
    return len(exterior) != (x1 - x0 + 1) * (y1 - y0 + 1) - len(occupied)


class GeometryTests(unittest.TestCase):
    def test_batched_features_match_individual_images(self):
        rng = random.Random(317)
        lines = []
        for grid in ("O", "H"):
            for _ in range(80):
                cells = list({(rng.randrange(-12, 13), rng.randrange(-7, 8))
                              for _ in range(rng.randrange(1, 35))})
                lines.append(shape.fmt(grid, cells))
        for window in (4, 16, 22):
            expected, owner = [], []
            for i, line in enumerate(lines):
                images = scorer.images(line, window)
                expected.extend(images)
                owner.extend([i] * len(images))
            got, indices = scorer.images_many(lines, window)
            np.testing.assert_array_equal(indices, owner)
            if expected:
                np.testing.assert_array_equal(got, np.stack(expected))
            else:
                self.assertEqual(got.shape, (0, scorer.input_size(window)))
            self.assertTrue(got.flags.c_contiguous)
        empty, owner = scorer.images_many([], 22)
        self.assertEqual(empty.shape, (0, 512))
        self.assertEqual(len(owner), 0)

    def test_exhaustive_small_bitboards(self):
        points = [(x - 2, y - 1) for y in range(3) for x in range(4)]
        for grid in ("O", "H"):
            for bits in range(1, 1 << len(points)):
                cells = [p for i, p in enumerate(points) if bits & (1 << i)]
                self.assertEqual(shape.has_hole(grid, cells), flood_reference(grid, cells), (grid, cells))

    def test_random_bitboards_and_long_spans(self):
        rng = random.Random(816)
        for grid in ("O", "H"):
            for _ in range(500):
                cells = list({(rng.randrange(-14, 15), rng.randrange(-4, 5))
                              for _ in range(rng.randrange(1, 150))})
                self.assertEqual(shape.has_hole(grid, cells), flood_reference(grid, cells), (grid, cells))

    def test_parsed_constraints_agree(self):
        for grid, cells in (("H", shape.NEIGHBOURS["H"]),
                            ("O", [(0, 0), (1, 0), (0, 1)]),
                            ("O", [(0, 0), (28, 0)])):
            self.assertEqual(shape.check(shape.fmt(grid, cells)), shape.check_cells(grid, cells))
        self.assertFalse(shape.check_cells("H", [])[0])


class RunnerTests(unittest.TestCase):
    def test_lfs_pointer_is_not_treated_as_an_empty_archive(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "out.jsonl"
            pointer = b"version https://git-lfs.github.com/spec/v1\noid sha256:abc\nsize 100\n"
            path.write_bytes(pointer)
            with self.assertRaisesRegex(ValueError, "git lfs pull"):
                runner.ensure_jsonl_boundary(path)
            self.assertEqual(path.read_bytes(), pointer)

    def test_partial_jsonl_is_preserved(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "out.jsonl"
            old = b'{"shape":"O 0 0"}\n{"interrupted":'
            path.write_bytes(old)
            runner.ensure_jsonl_boundary(path)
            with path.open("a") as fh:
                fh.write('{"next":true}\n')
            self.assertTrue(path.read_bytes().startswith(old))
            self.assertEqual(json.loads(path.read_text().splitlines()[-1]), {"next": True})

    def opts(self, **overrides):
        opts = dict(sat="mock-sat", maxlevel=7, timeout=0.1, timeout_long=1,
                    mem_mb=3000, periodic_budget=0, periodic_quick=0.1,
                    periodic_max_t=24, escalate_maxlevel=9)
        opts.update(overrides)
        return argparse.Namespace(**opts)

    def test_escalates_with_periodic_disabled(self):
        with mock.patch.object(runner, "run_one", side_effect=[
                {"status": "inconclusive", "seconds": 1},
                {"status": "nontiler", "hc": 4, "hh": 4, "seconds": 2}]) as sat:
            rec = runner.classify("H 0 0", self.opts(), "/tmp")
        self.assertEqual(rec["hc"], 4)
        self.assertEqual([c.args[2] for c in sat.call_args_list], [7, 9])
        self.assertIn("total_seconds", rec)

    def test_periodic_proof_short_circuits(self):
        with mock.patch.object(runner, "run_one", return_value={"status": "timeout", "seconds": 1}) as sat, \
                mock.patch.object(runner, "run_periodic", return_value={"status": "tiles"}):
            rec = runner.classify("H 0 0", self.opts(periodic_budget=1), "/tmp")
        self.assertEqual(rec["status"], "periodic")
        self.assertEqual(sat.call_count, 1)

    def test_full_worker_cost(self):
        self.assertEqual(runner.evaluation_seconds({"seconds": 2, "total_seconds": 7,
                         "defect_seconds": 4, "retried_from": {"seconds": 1, "total_seconds": 3}}), 14)
        self.assertEqual(runner.evaluation_seconds({"seconds": 2, "defect_seconds": 4,
                         "retried_from": {"seconds": 1}}), 7)

    def test_exit_timeout_and_memory_cap(self):
        with tempfile.TemporaryDirectory() as d:
            binary = Path(d) / "checker"
            binary.write_text("#!" + sys.executable + "\n"
                              "import pathlib, sys, time\n"
                              "if '-maxlevel' in sys.argv and sys.argv[sys.argv.index('-maxlevel')+1]=='9': time.sleep(2)\n"
                              "pathlib.Path(sys.argv[sys.argv.index('-o')+1]).write_text('O 0 0\\n~ 0 0 0\\n')\n")
            binary.chmod(0o755)
            with mock.patch.object(runner, "rss_mb", return_value=0):
                with mock.patch.object(os, "posix_spawn", wraps=os.posix_spawn) as spawn:
                    rec = runner.run_one(str(binary), "O 0 0", 7, 2, 3000, d)
                    if runner.subprocess._USE_POSIX_SPAWN:
                        self.assertTrue(spawn.called)
                self.assertEqual((rec["status"], rec["hc"]), ("nontiler", 0))
                rec = runner.run_one(str(binary), "O 0 0", 9, 0.03, 3000, d)
                self.assertEqual(rec["status"], "timeout")
            with mock.patch.object(runner, "rss_mb", return_value=4000):
                rec = runner.run_one(str(binary), "O 0 0", 9, 2, 3000, d)
                self.assertEqual(rec["status"], "memout")


class SearchTests(unittest.TestCase):
    def run_guard_case(self, mode=None):
        bad = set()

        class RankingScorer:
            backend = "mock"
            def __init__(self, *args):
                self.ids = {}
            def featurize(self, canon):
                index = len(self.ids) + 1
                self.ids[index] = canon
                x = np.zeros(64, np.float32)
                x[0] = index
                return [x]
            def score(self, features):
                scores = features[:, 0]
                for i in np.argsort(scores)[-8:]:
                    bad.add(self.ids[int(scores[i])])
                return np.column_stack([np.zeros(len(features)), scores])

        def classify(canon, *args):
            time.sleep(0.002)
            hc = 0 if canon in bad else 2
            return {"status": "nontiler", "hc": hc, "hh": hc, "seconds": 0.002}

        extra = ["--guard-checks", "4", "--random-frac", "0.5"]
        if mode is not None:
            extra += ["--guard-mode", mode]
        with tempfile.TemporaryDirectory() as d:
            rows = self.run_search(d, n=240, classifier=classify, scorer=RankingScorer, extra=extra)
            events = [json.loads(s) for s in (Path(d) / "out.jsonl.runs.jsonl").read_text().splitlines()]
        return rows, events

    def test_default_guard_warns_and_keeps_scoring(self):
        rows, events = self.run_guard_case()
        warnings = [e for e in events if e["event"] == "generator_guard_warning"]
        self.assertTrue(warnings)
        self.assertFalse(any(e["event"] == "generator_guard_disabled" for e in events))
        self.assertTrue(any(r["generator"] == "search-scored" for r in rows[150:]))
        self.assertEqual(len({r["canon"] for r in rows}), 240)
        for first, second in zip(warnings, warnings[1:]):
            self.assertGreaterEqual(second["guided_completed"] - first["guided_completed"], 4)

    def test_hard_guard_requires_explicit_disable_mode(self):
        rows, events = self.run_guard_case("disable")
        self.assertTrue(any(e["event"] == "generator_guard_disabled" for e in events))
        self.assertFalse(any(r["generator"] == "search-scored" for r in rows[-50:]))

    def test_off_mode_keeps_scoring_without_guard_events(self):
        rows, events = self.run_guard_case("off")
        self.assertFalse(any(e["event"].startswith("generator_guard_") for e in events))
        self.assertTrue(any(r["generator"] == "search-scored" for r in rows[-50:]))

    def run_search(self, directory, *, n=25, classifier=None, scorer=None, extra=()):
        seed = Path(directory) / "seeds.jsonl"
        if not seed.exists():
            line = shape.canonical("O", [(0, 0), (1, 0), (2, 0), (2, 1), (3, 1), (3, 2), (3, 3), (2, 3)])
            seed.write_text(json.dumps({"shape": line, "status": "nontiler", "hc": 1, "hh": 1, "cells": 8}) + "\n")
        log = Path(directory) / "out.jsonl"
        argv = ["search.py", "--seeds", str(seed), "--log", str(log), "--seed-min-hc", "1",
                "--max-evals", str(n), "--jobs", "3", "--retry-jobs", "0", "--defect-min-hc", "0",
                "--sweep-min-hc", "0", "--guard-checks", "0", "--min-cells", "4", "--max-cells", "12"]
        if scorer is not None:
            argv += ["--scorer", "mock", "--candidates", "16", "--pick", "8", "--random-frac", "0"]
        argv.extend(extra)
        if classifier is None:
            def classifier(*args):
                time.sleep(0.002)
                return {"status": "nontiler", "hc": 0, "hh": 0, "seconds": 0.002}
        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch.object(sys, "argv", argv))
            stack.enter_context(mock.patch.object(runner, "classify", side_effect=classifier))
            stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            if scorer is not None:
                stack.enter_context(mock.patch.object(aner_scorer, "Scorer", scorer))
            search.main()
        return [json.loads(ln) for ln in log.read_text().splitlines()]

    def test_exact_evaluation_limit_and_resume(self):
        with tempfile.TemporaryDirectory() as d:
            rows = self.run_search(d)
            self.assertEqual(len(rows), 25)
            rows = self.run_search(d, n=10)
            events = [json.loads(ln) for ln in (Path(d) / "out.jsonl.runs.jsonl").read_text().splitlines()]
        self.assertEqual(len(rows), 35)
        self.assertEqual(len({r["canon"] for r in rows}), 35)
        self.assertTrue(all(shape.check(r["canon"])[0] for r in rows))
        self.assertEqual(len({r["run_id"] for r in rows}), 2)
        self.assertEqual([r["event"] for r in events], ["started", "finished", "started", "finished"])

    def test_slow_scoring_does_not_block_dispatch(self):
        checked = threading.Event()
        score_saw_check = []

        class SlowScorer:
            backend = "mock"
            def __init__(self, *args):
                pass
            def featurize(self, canon):
                return [np.zeros(64, dtype=np.float32)]
            def score(self, features):
                score_saw_check.append(checked.wait(1))
                time.sleep(0.005)
                return np.ones((len(features), 2), dtype=np.float32)

        def classifier(*args):
            checked.set()
            time.sleep(0.005)
            return {"status": "nontiler", "hc": 0, "hh": 0, "seconds": 0.005}

        with tempfile.TemporaryDirectory() as d:
            rows = self.run_search(d, n=50, classifier=classifier, scorer=SlowScorer)
        self.assertTrue(score_saw_check)
        self.assertTrue(all(score_saw_check))
        self.assertEqual(len(rows), 50)
        self.assertTrue(any(r["generator"] == "search-scored" for r in rows))
        self.assertEqual(len({r["canon"] for r in rows}), 50)

    def test_retry_preserves_initial_cost(self):
        attempts = {}
        def classifier(canon, opts, workdir):
            attempts[canon] = attempts.get(canon, 0) + 1
            if attempts[canon] == 1:
                return {"status": "memout", "seconds": 1, "total_seconds": 3, "peak_rss_mb": 3001}
            return {"status": "nontiler", "hc": 0, "hh": 0, "seconds": 2, "total_seconds": 4}
        with tempfile.TemporaryDirectory() as d:
            rows = self.run_search(d, n=10, classifier=classifier, extra=("--retry-jobs", "1"))
        self.assertEqual(len(rows), 10)
        self.assertTrue(all(r["status"] == "nontiler" for r in rows))
        self.assertTrue(all(runner.evaluation_seconds(r) == 7 for r in rows))


if __name__ == "__main__":
    unittest.main()
