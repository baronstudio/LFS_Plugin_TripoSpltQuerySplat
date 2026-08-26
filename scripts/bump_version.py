#!/usr/bin/env python3
"""Montee de version du plugin, en une commande.

    python3 scripts/bump_version.py patch      # 0.1.0 -> 0.1.1
    python3 scripts/bump_version.py minor      # 0.1.1 -> 0.2.0
    python3 scripts/bump_version.py major      # 0.2.0 -> 1.0.0
    python3 scripts/bump_version.py --check    # verifie la coherence, ne modifie rien

Le script met a jour les trois endroits ou la version apparait :
`core/version.py` (source de verite), `pyproject.toml` et `CHANGELOG.md`.
Il n'effectue aucune operation git : les commandes a lancer sont affichees.
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = ROOT / "core" / "version.py"
PYPROJECT = ROOT / "pyproject.toml"
CHANGELOG = ROOT / "CHANGELOG.md"
REPO = "baronstudio/LFS_Plugin_TripoSpltQuerySplat"

_VERSION_RE = re.compile(r'^__version__ = "(\d+)\.(\d+)\.(\d+)"$', re.MULTILINE)


def read_version() -> tuple[int, int, int]:
    match = _VERSION_RE.search(VERSION_FILE.read_text(encoding="utf-8"))
    if match is None:
        sys.exit(f"__version__ introuvable dans {VERSION_FILE}")
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def read_pyproject_version() -> str:
    with PYPROJECT.open("rb") as handle:
        return tomllib.load(handle)["project"]["version"]


def check() -> int:
    """Verifie que toutes les sources de version concordent."""
    current = ".".join(str(part) for part in read_version())
    problems = []
    if read_pyproject_version() != current:
        problems.append(
            f"pyproject.toml annonce {read_pyproject_version()}, core/version.py annonce {current}"
        )
    if f"[{current}]" not in CHANGELOG.read_text(encoding="utf-8"):
        problems.append(f"CHANGELOG.md n'a pas d'entree pour la version {current}")
    for problem in problems:
        print(f"NOK  {problem}")
    if problems:
        return 1
    print(f"OK   version {current} coherente (version.py, pyproject.toml, CHANGELOG.md)")
    return 0


def bump(part: str, date: str) -> None:
    major, minor, patch = read_version()
    if part == "major":
        major, minor, patch = major + 1, 0, 0
    elif part == "minor":
        minor, patch = minor + 1, 0
    else:
        patch += 1
    new = f"{major}.{minor}.{patch}"
    previous = ".".join(str(p) for p in read_version())

    _sub_file(VERSION_FILE, _VERSION_RE, f'__version__ = "{new}"')
    _sub_file(PYPROJECT, re.compile(r'^version = "[^"]+"$', re.MULTILINE), f'version = "{new}"')
    _update_changelog(new, previous, date)

    print(f"Version {previous} -> {new}")
    print("\nRedigez la section de changelog, puis :")
    print(f"  git commit -am 'release: v{new}'")
    print(f"  git tag -a v{new} -m 'v{new}'")
    print(f"  git push && git push origin v{new}")


def _sub_file(path: Path, pattern: re.Pattern[str], replacement: str) -> None:
    text = path.read_text(encoding="utf-8")
    text, count = pattern.subn(replacement, text, count=1)
    if count != 1:
        sys.exit(f"Motif de version introuvable dans {path}")
    path.write_text(text, encoding="utf-8")


def _update_changelog(new: str, previous: str, date: str) -> None:
    text = CHANGELOG.read_text(encoding="utf-8")
    if "## [Non publie]" not in text:
        sys.exit("CHANGELOG.md : section '## [Non publie]' introuvable.")
    text = text.replace(
        "## [Non publie]",
        f"## [Non publie]\n\n## [{new}] - {date}\n\n### Ajoute\n- TODO\n",
        1,
    )
    text = text.replace(
        f"[Non publie]: https://github.com/{REPO}/compare/v{previous}...HEAD",
        f"[Non publie]: https://github.com/{REPO}/compare/v{new}...HEAD\n"
        f"[{new}]: https://github.com/{REPO}/releases/tag/v{new}",
        1,
    )
    CHANGELOG.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("part", nargs="?", choices=("major", "minor", "patch"))
    parser.add_argument(
        "--check", action="store_true", help="verifie la coherence sans rien modifier"
    )
    parser.add_argument(
        "--date", default=dt.date.today().isoformat(), help="date de publication (AAAA-MM-JJ)"
    )
    args = parser.parse_args()

    if args.check:
        return check()
    if args.part is None:
        parser.error("indiquez major, minor ou patch (ou --check)")
    bump(args.part, args.date)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
