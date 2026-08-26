"""Panneau principal du plugin PhotoSplat.

Regle de conception : ce fichier ne contient que de l'affichage et de la
liaison d'etat. Toute la logique metier vit dans `core/` et reste testable
sans lancer LichtFeld Studio.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import lichtfeld as lf

# Imports relatifs : le plugin est charge comme un paquet. En absolu, les noms
# `core` et `panels` sont si generiques qu'ils entreraient en collision avec
# ceux des autres plugins charges dans le meme interpreteur.
from ..core import gpu, lfs, pipeline
from ..core import images as images_mod
from ..core import settings as settings_mod
from ..core.backends import KIND_DATASET, registry
from ..core.version import PLUGIN_ID, PLUGIN_NAME, __version__

_OK = (0.45, 0.85, 0.45, 1.0)
_WARN = (0.95, 0.75, 0.30, 1.0)
_ERR = (0.95, 0.45, 0.45, 1.0)

#: Nombre de lignes de journal conservees a l'ecran.
_LOG_LINES = 12


class MainPanel(lf.ui.Panel):
    """Photos -> dataset ou splat -> scene LichtFeld.

    `MAIN_PANEL_TAB` place le panneau dans la zone a onglets principale, aux
    cotes de « Rendering » et « Training ».

    `template` designe la coquille RML du panneau. Elle n'est pas optionnelle en
    pratique : le gabarit genere par `lf.plugins.create()` comme les plugins
    existants en fournissent tous une. Sans elle, le panneau est enregistre mais
    n'apparait nulle part, sans erreur. Le contenu, lui, reste dessine en mode
    immediat par `draw()`, qui se monte dans le `<div id="im-root">`.
    """

    id = f"{PLUGIN_ID}.main_panel"
    label = PLUGIN_NAME
    space = lf.ui.PanelSpace.MAIN_PANEL_TAB
    order = 230
    template = str(Path(__file__).resolve().with_name("main_panel.rml"))
    update_policy = "interval"
    update_interval_ms = 120

    def __init__(self) -> None:
        # Pas de `super().__init__()` : la classe de base est exposee depuis le
        # C++ et son constructeur n'accepte pas d'appel explicite. L'invoquer
        # fait echouer la construction du panneau -- le plugin reste « active »
        # mais aucun panneau n'apparait, sans erreur visible.
        self.settings = settings_mod.Settings.load()
        self.job = pipeline.Job()
        self.gpu = gpu.detect()
        self.images = images_mod.ImageSet(paths=(), ignored=())
        self._backend_problems: list[str] = []
        self._image_problems: list[str] = []
        self._scanned_for: str = ""
        self._notice: str = ""
        self._draw_failure: str = ""
        if self.settings.images_dir:
            self._scan()
        self._refresh_backend_check()

    # ------------------------------------------------------------------ etat

    def _scan(self) -> None:
        self.images = images_mod.scan_folder(self.settings.images_dir, self.settings.recursive)
        self._scanned_for = self.settings.images_dir
        self._notice = ""
        self._revalidate()

    def _refresh_backend_check(self) -> None:
        try:
            self._backend_problems = registry.get(self.settings.backend).check()
        except KeyError:
            self.settings.backend = registry.default_name()
            self._backend_problems = registry.get(self.settings.backend).check()
        self._revalidate()

    def _revalidate(self) -> None:
        """Recalcule les problemes lies aux images.

        Appele uniquement quand le lot ou le moteur change : `validate` lit la
        taille des fichiers sur disque, ce qui n'a pas sa place dans `draw()`,
        rejoue plusieurs fois par seconde.
        """
        backend = registry.get(self.settings.backend)
        self._image_problems = images_mod.validate(
            self.images, backend.info.min_images, backend.info.max_images
        )

    def _effective_max_views(self) -> int:
        """Plafond applique : reglage explicite, sinon deduit de la VRAM."""
        if self.settings.max_views > 0:
            return self.settings.max_views
        return gpu.max_views_for(self.gpu.vram_gb)

    def _selected_images(self) -> list[Path]:
        return list(self.images.paths[: self._effective_max_views()])

    def _blocking_problems(self) -> list[str]:
        """Problemes empechant le lancement, tous deja calcules hors du rendu."""
        return self._backend_problems + self._image_problems

    # ------------------------------------------------------------------ dessin

    def draw(self, ui) -> None:
        """Point d'entree du rendu, protege.

        Une exception ici -- typiquement un ecart d'API de l'hote -- fait
        disparaitre le panneau entier : LichtFeld journalise « Panel draw
        error » et n'affiche plus rien. On prefere afficher la panne dans le
        panneau, et ne la journaliser qu'une fois plutot qu'a chaque frame.
        """
        try:
            self._draw(ui)
        except Exception as exc:  # noqa: BLE001 - le panneau doit survivre
            self._render_failure(ui, exc)

    def _render_failure(self, ui, exc: Exception) -> None:
        message = f"{type(exc).__name__}: {exc}"
        if message != self._draw_failure:
            self._draw_failure = message
            lfs.log(f"PhotoSplat : erreur de rendu du panneau -- {message}")
        ui.heading(PLUGIN_NAME)
        ui.text_colored("Le panneau a rencontre une erreur.", _ERR)
        ui.text_wrapped(message)
        ui.text_disabled("Details complets dans l'onglet Logging.")

    def _draw(self, ui) -> None:
        state = self.job.snapshot()
        backend = registry.get(self.settings.backend)

        ui.heading(PLUGIN_NAME)
        ui.text_disabled(f"v{__version__}  -  {self.gpu.describe()}")
        if not self.gpu.available:
            ui.text_colored("GPU NVIDIA requis pour generer.", _ERR)
        ui.separator()

        self._draw_images_section(ui)
        ui.separator()
        self._draw_engine_section(ui, backend)
        ui.separator()
        self._draw_settings_section(ui)
        ui.separator()
        self._draw_run_section(ui, backend, state)
        self._draw_result_section(ui, backend, state)
        self._draw_log_section(ui, state)

    def _draw_images_section(self, ui) -> None:
        ui.label("1. Photos")
        changed, value = ui.path_input(
            "Dossier",
            self.settings.images_dir,
            folder_mode=True,
            dialog_title="Dossier des photos",
        )
        if changed:
            self.settings.images_dir = value
            self.settings.save()
            self._scan()

        changed, value = ui.checkbox("Inclure les sous-dossiers", self.settings.recursive)
        if changed:
            self.settings.recursive = value
            self.settings.save()
            self._scan()

        if ui.button("Analyser"):
            self._scan()
        ui.same_line()
        ui.text_disabled(images_mod.summarize(self.images))

        if self.settings.images_dir and self._scanned_for != self.settings.images_dir:
            ui.text_colored("Dossier modifie : relancez l'analyse.", _WARN)

        selected = len(self._selected_images())
        if selected and selected < self.images.count:
            ui.text_colored(
                f"Seules les {selected} premieres vues seront traitees "
                f"(plafond VRAM). Voir Reglages.",
                _WARN,
            )

    def _draw_engine_section(self, ui, backend) -> None:
        ui.label("2. Moteur")
        names = registry.names()
        current = names.index(self.settings.backend) if self.settings.backend in names else 0
        changed, index = ui.combo("Moteur", current, registry.labels())
        if changed:
            self.settings.backend = names[index]
            self.settings.save()
            self._refresh_backend_check()

        ui.text_wrapped(backend.info.summary)
        color = _OK if backend.info.commercial_ok else _ERR
        ui.text_colored(backend.info.license_line(), color)
        ui.text_disabled(f"Modele : {backend.info.model_id}")

        for problem in self._backend_problems:
            ui.text_colored(problem, _ERR)

    def _draw_settings_section(self, ui) -> None:
        if not ui.collapsing_header("3. Reglages", default_open=False):
            return
        changed, value = ui.input_int("Graine", self.settings.seed, 1, 10)
        if changed:
            self.settings.seed = max(0, value)
            self.settings.save()
        ui.set_tooltip("Meme graine + memes photos = meme resultat.")

        changed, value = ui.input_float(
            "Finesse du nuage", self.settings.voxel_fraction, 0.001, 0.01, "%.3f"
        )
        if changed:
            self.settings.voxel_fraction = min(max(value, 0.001), 0.2)
            self.settings.save()
        ui.set_tooltip(
            "Taille du voxel de sous-echantillonnage, en fraction de l'etendue "
            "de la scene. Plus petit = nuage d'initialisation plus dense."
        )

        changed, value = ui.input_int("Vues max (0 = auto)", self.settings.max_views, 1, 10)
        if changed:
            self.settings.max_views = max(0, value)
            self.settings.save()
        ui.text_disabled(f"Plafond applique : {self._effective_max_views()} vues")

        changed, value = ui.checkbox(
            "Entrainer automatiquement apres generation", self.settings.auto_train
        )
        if changed:
            self.settings.auto_train = value
            self.settings.save()

    def _draw_run_section(self, ui, backend, state) -> None:
        ui.label("4. Generation")
        problems = self._blocking_problems()

        if state.running:
            ui.progress_bar(state.progress, overlay=state.message)
            if ui.button_styled("Annuler", "warning", (0, 0)):
                self.job.cancel()
            return

        ui.begin_disabled(bool(problems) or not self.gpu.available)
        if ui.button_styled("Generer", "primary", (0, 0)):
            self._launch(backend)
        ui.end_disabled()

        for problem in problems:
            ui.text_colored(problem, _WARN)
        if self._notice:
            ui.text_colored(self._notice, _WARN)
        if state.state == pipeline.STATE_ERROR:
            ui.text_colored(state.error, _ERR)
        elif state.state == pipeline.STATE_CANCELLED:
            ui.text_disabled(state.message)

    def _draw_result_section(self, ui, backend, state) -> None:
        if state.state != pipeline.STATE_DONE or state.result is None:
            return
        result = state.result
        ui.separator()
        ui.label("5. Resultat")

        if backend.info.kind == KIND_DATASET and result.dataset_dir:
            ui.text_disabled(str(result.dataset_dir))
            if ui.button("Charger le dataset"):
                self._load_dataset(result)
            ui.same_line()
            if ui.button_styled("Charger et entrainer", "success", (0, 0)):
                if self._load_dataset(result):
                    lfs.start_training()
        elif result.splat_ply:
            ui.text_disabled(str(result.splat_ply))
            if ui.button("Inserer dans la scene"):
                if not lfs.load_splat(result.splat_ply):
                    self._notice = "API LichtFeld indisponible."

    def _draw_log_section(self, ui, state) -> None:
        if not state.log:
            return
        ui.separator()
        if not ui.collapsing_header("Journal", default_open=False):
            return
        for line in state.log[-_LOG_LINES:]:
            ui.text_disabled(line)

    # ------------------------------------------------------------------ actions

    def _launch(self, backend) -> None:
        if lfs.is_training_active():
            self._notice = "Un entrainement est en cours : arretez-le pour liberer la VRAM."
            return
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        work_dir = settings_mod.runs_dir() / f"{stamp}-{backend.info.name}"
        params = {
            "seed": self.settings.seed,
            "voxel_fraction": self.settings.voxel_fraction,
        }
        started = self.job.start(backend, self._selected_images(), work_dir, params)
        self._notice = "" if started else "Une generation est deja en cours."

    def _load_dataset(self, result) -> bool:
        if result.dataset_dir is None:
            return False
        output_dir = result.dataset_dir / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        if not lfs.load_dataset(result.dataset_dir, result.init_ply, output_dir):
            self._notice = "API LichtFeld indisponible."
            return False
        return True
