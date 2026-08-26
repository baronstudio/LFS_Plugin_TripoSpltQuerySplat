"""Execution d'une generation en tache de fond.

Le panneau est redessine plusieurs fois par seconde : la generation doit donc
tourner dans un thread, et l'interface se contente de lire un etat protege par
un verrou.
"""

from __future__ import annotations

import threading
import traceback
from dataclasses import dataclass, field
from pathlib import Path

from .backends.base import Backend, Cancelled, RunResult

STATE_IDLE = "idle"
STATE_RUNNING = "running"
STATE_DONE = "done"
STATE_ERROR = "error"
STATE_CANCELLED = "cancelled"


@dataclass
class JobState:
    """Instantane de l'etat courant, copie a chaque lecture."""

    state: str = STATE_IDLE
    progress: float = 0.0
    message: str = ""
    log: list[str] = field(default_factory=list)
    result: RunResult | None = None
    error: str = ""

    @property
    def running(self) -> bool:
        return self.state == STATE_RUNNING


class Job:
    """Une generation a la fois. Relancer remplace l'etat precedent."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._state = JobState()
        self._cancel = threading.Event()
        self._thread: threading.Thread | None = None

    def snapshot(self) -> JobState:
        """Copie de l'etat, sure a lire depuis le thread d'interface."""
        with self._lock:
            return JobState(
                state=self._state.state,
                progress=self._state.progress,
                message=self._state.message,
                log=list(self._state.log),
                result=self._state.result,
                error=self._state.error,
            )

    def start(
        self,
        backend: Backend,
        images: list[Path],
        work_dir: Path,
        params: dict,
    ) -> bool:
        """Demarre une generation. Retourne False si une autre tourne deja."""
        with self._lock:
            if self._state.state == STATE_RUNNING:
                return False
            self._state = JobState(state=STATE_RUNNING, message="Demarrage")
            self._cancel = threading.Event()

        self._thread = threading.Thread(
            target=self._run,
            args=(backend, images, work_dir, params),
            name="photosplat-job",
            daemon=True,
        )
        self._thread.start()
        return True

    def cancel(self) -> None:
        """Demande l'arret. Prise en compte au prochain point de controle."""
        self._cancel.set()
        self._append("Annulation demandee, arret au prochain point de controle...")

    def _run(self, backend: Backend, images: list[Path], work_dir: Path, params: dict) -> None:
        try:
            result = backend.run(images, work_dir, params, self._report, self._cancel)
            with self._lock:
                self._state.state = STATE_DONE
                self._state.progress = 1.0
                self._state.message = "Generation terminee"
                self._state.result = result
                self._state.log.extend(result.log)
        except Cancelled as exc:
            with self._lock:
                self._state.state = STATE_CANCELLED
                self._state.message = str(exc)
        except Exception as exc:  # noqa: BLE001 - toute erreur doit remonter a l'UI
            with self._lock:
                self._state.state = STATE_ERROR
                self._state.message = "Echec de la generation"
                self._state.error = f"{type(exc).__name__}: {exc}"
                self._state.log.append(traceback.format_exc(limit=8))

    def _report(self, progress: float, message: str) -> None:
        with self._lock:
            self._state.progress = max(0.0, min(1.0, progress))
            self._state.message = message
            self._state.log.append(message)

    def _append(self, message: str) -> None:
        with self._lock:
            self._state.log.append(message)
