"""Detection du GPU et derivation des garde-fous.

La cible materielle n'etant pas figee, les limites ne sont pas codees en dur :
elles sont derivees de la VRAM reellement disponible au demarrage.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass

#: Paliers de VRAM (Go) -> nombre de vues traitees en une passe.
#: Valeurs prudentes : mieux vaut un run lent qui aboutit qu'un OOM.
_VIEW_BUDGET = (
    (24.0, 64),
    (16.0, 40),
    (12.0, 24),
    (8.0, 12),
    (0.0, 6),
)


@dataclass(frozen=True)
class GpuInfo:
    """Etat materiel constate. `vram_gb == 0` signifie "inconnu"."""

    available: bool
    name: str
    vram_gb: float

    @property
    def known(self) -> bool:
        return self.vram_gb > 0

    def describe(self) -> str:
        if not self.available:
            return "Aucun GPU NVIDIA detecte -- le plugin ne pourra pas generer."
        if not self.known:
            return f"{self.name} (VRAM inconnue)"
        return f"{self.name} -- {self.vram_gb:.0f} Go de VRAM"


def detect() -> GpuInfo:
    """Detecte le GPU via `nvidia-smi`.

    Volontairement sans torch : son import coute des dizaines de secondes sur
    Windows, et `detect()` est appele a la construction du panneau, donc sur le
    fil de l'interface. `nvidia-smi` repond en quelques dizaines de millisecondes.

    Consequence assumee : on constate la presence d'un GPU et d'un pilote, pas
    l'utilisabilite reelle de CUDA par torch. Cette verification-la a lieu au
    lancement de la generation, ou torch est de toute facon charge.
    """
    info = _detect_with_smi()
    if info is not None:
        return info
    return GpuInfo(available=False, name="inconnu", vram_gb=0.0)


def _detect_with_smi() -> GpuInfo | None:
    if shutil.which("nvidia-smi") is None:
        return None
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        ).stdout.strip()
    except (subprocess.SubprocessError, OSError):
        return None
    if not out:
        return None
    name, _, mib = out.splitlines()[0].partition(",")
    try:
        vram_gb = float(mib.strip()) / 1024.0
    except ValueError:
        vram_gb = 0.0
    return GpuInfo(available=True, name=name.strip(), vram_gb=vram_gb)


def max_views_for(vram_gb: float) -> int:
    """Nombre de vues conseille pour une VRAM donnee.

    VRAM inconnue (0) -> on retient le palier le plus prudent.
    """
    if vram_gb <= 0:
        return _VIEW_BUDGET[-1][1]
    for threshold, views in _VIEW_BUDGET:
        if vram_gb >= threshold:
            return views
    return _VIEW_BUDGET[-1][1]
