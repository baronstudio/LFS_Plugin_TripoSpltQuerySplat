#!/usr/bin/env bash
# Lie ce depot au dossier de plugins de LichtFeld Studio (mode developpement).
# LichtFeld construit ensuite l'environnement isole au premier chargement.
set -euo pipefail

PLUGIN_ID="photosplat"
SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_DIR="${HOME}/.lichtfeld/plugins/${PLUGIN_ID}"

mkdir -p "$(dirname "${TARGET_DIR}")"

if [ -L "${TARGET_DIR}" ]; then
    echo "Lien existant remplace : ${TARGET_DIR}"
    rm "${TARGET_DIR}"
elif [ -e "${TARGET_DIR}" ]; then
    echo "ERREUR : ${TARGET_DIR} existe et n'est pas un lien symbolique." >&2
    echo "Deplacez-le ou supprimez-le, puis relancez." >&2
    exit 1
fi

ln -s "${SOURCE_DIR}" "${TARGET_DIR}"
echo "Plugin lie : ${TARGET_DIR} -> ${SOURCE_DIR}"
echo
echo "Dans LichtFeld Studio, console Python :"
echo "  import lichtfeld as lf"
echo "  lf.plugins.discover()"
echo "  lf.plugins.load('${PLUGIN_ID}')"
