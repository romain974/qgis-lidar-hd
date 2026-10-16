# -*- coding: utf-8 -*-
"""Construit l'archive installable de l'extension.

    python empaqueter.py   →  dist/lidar_hd_emprise-<version>.zip

L'archive contient un unique dossier ``lidar_hd_emprise/`` à sa racine : c'est la
forme attendue par « Installer depuis un ZIP » et par le dépôt officiel d'extensions.
"""

import os
import re
import sys
import zipfile

RACINE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = "lidar_hd_emprise"
EXCLUS = {"__pycache__", ".pytest_cache"}
EXCLUS_FICHIERS = {".DS_Store", "Thumbs.db"}


def version():
    chemin = os.path.join(RACINE, PLUGIN, "metadata.txt")
    with open(chemin, "r", encoding="utf-8") as fichier:
        contenu = fichier.read()
    trouve = re.search(r"^version\s*=\s*(.+)$", contenu, re.MULTILINE)
    if not trouve:
        raise SystemExit("version introuvable dans metadata.txt")
    return trouve.group(1).strip()


def fichiers():
    source = os.path.join(RACINE, PLUGIN)
    for dossier, sous_dossiers, noms in os.walk(source):
        sous_dossiers[:] = [d for d in sous_dossiers if d not in EXCLUS]
        for nom in noms:
            if nom in EXCLUS_FICHIERS or nom.endswith((".pyc", ".pyo")):
                continue
            complet = os.path.join(dossier, nom)
            relatif = os.path.relpath(complet, RACINE).replace("\\", "/")
            yield complet, relatif


def construire():
    numero = version()
    dossier_sortie = os.path.join(RACINE, "dist")
    if not os.path.isdir(dossier_sortie):
        os.makedirs(dossier_sortie)
    archive = os.path.join(dossier_sortie, "%s-%s.zip" % (PLUGIN, numero))

    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zip_:
        for complet, relatif in fichiers():
            zip_.write(complet, relatif)

    print("%s — %.0f Ko" % (archive, os.path.getsize(archive) / 1024.0))
    return archive


if __name__ == "__main__":
    construire()
    sys.exit(0)
