"""Cycle de vie d'une generation en tache de fond."""

import threading
import time
import unittest
from pathlib import Path

from core import pipeline
from core.backends.base import Cancelled, RunResult


def _wait(job, timeout=3.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        snapshot = job.snapshot()
        if not snapshot.running:
            return snapshot
        time.sleep(0.01)
    raise AssertionError("La tache ne s'est pas terminee dans le delai imparti.")


class _Backend:
    """Moteur factice pilotable, pour tester le runner sans GPU."""

    def __init__(self, behaviour="ok"):
        self.behaviour = behaviour
        self.started = threading.Event()

    def check(self):
        return []

    def run(self, images, work_dir, params, report, cancel):
        self.started.set()
        report(0.5, "moitie")
        if self.behaviour == "boom":
            raise ValueError("panne simulee")
        if self.behaviour == "cancel":
            while not cancel.is_set():
                time.sleep(0.01)
            raise Cancelled("interrompu")
        result = RunResult(dataset_dir=work_dir)
        result.add("dataset ecrit")
        return result


class TestJob(unittest.TestCase):
    def test_success_exposes_result_and_log(self):
        job = pipeline.Job()
        self.assertTrue(job.start(_Backend(), [], Path("/tmp/x"), {}))
        snapshot = _wait(job)
        self.assertEqual(snapshot.state, pipeline.STATE_DONE)
        self.assertEqual(snapshot.progress, 1.0)
        self.assertEqual(snapshot.result.dataset_dir, Path("/tmp/x"))
        self.assertIn("dataset ecrit", snapshot.log)

    def test_failure_is_reported_not_raised(self):
        job = pipeline.Job()
        job.start(_Backend("boom"), [], Path("/tmp/x"), {})
        snapshot = _wait(job)
        self.assertEqual(snapshot.state, pipeline.STATE_ERROR)
        self.assertIn("panne simulee", snapshot.error)

    def test_cancel_stops_the_run(self):
        job = pipeline.Job()
        backend = _Backend("cancel")
        job.start(backend, [], Path("/tmp/x"), {})
        self.assertTrue(backend.started.wait(2.0))
        job.cancel()
        snapshot = _wait(job)
        self.assertEqual(snapshot.state, pipeline.STATE_CANCELLED)

    def test_only_one_run_at_a_time(self):
        job = pipeline.Job()
        backend = _Backend("cancel")
        job.start(backend, [], Path("/tmp/x"), {})
        self.assertTrue(backend.started.wait(2.0))
        self.assertFalse(job.start(_Backend(), [], Path("/tmp/y"), {}))
        job.cancel()
        _wait(job)

    def test_snapshot_is_a_copy(self):
        job = pipeline.Job()
        snapshot = job.snapshot()
        snapshot.log.append("pollution")
        self.assertEqual(job.snapshot().log, [])


if __name__ == "__main__":
    unittest.main()
