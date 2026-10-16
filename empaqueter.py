# -*- coding: utf-8 -*-
"""Construit l'archive à déposer sur le dépôt officiel d'extensions QGIS.

    python empaqueter.py   →  dist/lidar_hd_emprise-<version>.zip

Contraintes du dépôt officiel (docs QGIS, « Releasing your plugin ») :

- un unique dossier à la racine de l'archive, nommé avec des caractères ASCII
  (lettres, chiffres, ``_`` et ``-``), ne commençant pas par un chiffre ;
- ``metadata.txt``, ``__init__.py`` et ``LICENSE`` obligatoires dans ce dossier ;
- la licence doit s'appeler ``LICENSE``, **sans extension**.

La licence est présente aux deux endroits où elle est attendue — à la racine du dépôt
(GitHub l'affiche) et dans le dossier du plugin (le dépôt officiel l'exige dans l'archive).
``verifier()`` contrôle que les deux copies sont identiques, pour qu'elles ne divergent pas.
"""

import os
import re
import sys
import zipfile

RACINE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = "lidar_hd_emprise"
EXCLUS = {"__pycache__", ".pytest_cache", ".git"}
EXCLUS_FICHIERS = {".DS_Store", "Thumbs.db"}
LICENCE = "LICENSE"

# html : interdit dans les champs de metadata.txt
TAGS_HTML = re.compile(r"<[a-zA-Z/][^>]*>")


def version():
    return valeur(lire_metadata(), "version")


def lire_metadata():
    chemin = os.path.join(RACINE, PLUGIN, "metadata.txt")
    with open(chemin, "r", encoding="utf-8") as fichier:
        contenu = fichier.read()

    champs = {}
    courant = None
    for ligne in contenu.splitlines():
        if not ligne.strip() or ligne.lstrip().startswith((";", "#")):
            continue
        if ligne.lstrip() != ligne:  # ligne de continuation
            if courant:
                champs[courant] += "\n" + ligne.strip()
            continue
        if "=" not in ligne:
            continue
        cle, valeur = ligne.split("=", 1)
        courant = cle.strip()
        champs[courant] = valeur.strip()
    return champs


def valeur(champs, nom):
    """Lecture d'un champ sans tenir compte de la casse de la clé."""
    for cle, contenu in champs.items():
        if cle.lower() == nom.lower():
            return contenu
    return None


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


def verifier():
    """Rejoue les règles du dépôt officiel sur l'archive produite."""
    archive = construire()
    problemes = []

    with zipfile.ZipFile(archive) as zip_:
        noms = zip_.namelist()

        # 1. Un unique dossier à la racine, dont le nom est dans le jeu autorisé.
        racines = {nom.split("/")[0] for nom in noms}
        if racines != {PLUGIN}:
            problemes.append("l'archive doit contenir un seul dossier racine : %s" % sorted(racines))
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_-]*$", PLUGIN):
            problemes.append("nom de dossier invalide pour le dépôt : %s" % PLUGIN)

        # 2. Fichiers obligatoires.
        for obligatoire in ("metadata.txt", "__init__.py", LICENCE):
            if "%s/%s" % (PLUGIN, obligatoire) not in noms:
                problemes.append("fichier obligatoire absent : %s" % obligatoire)
        if any(nom.endswith((".pyc", ".pyo")) or "__pycache__" in nom for nom in noms):
            problemes.append("l'archive contient des fichiers compilés")

        # 3. Métadonnées obligatoires, sans HTML.
        champs = lire_metadata()
        for requis in ("name", "qgisMinimumVersion", "description", "about", "version",
                       "author", "email", "repository"):
            if not valeur(champs, requis):
                problemes.append("champ de metadata.txt manquant : %s" % requis)
        for cle, contenu in champs.items():
            if contenu is None:
                continue
            trouve = TAGS_HTML.search(contenu)
            if trouve:
                problemes.append("balise HTML interdite dans « %s » : %s" % (cle, trouve.group(0)))
        if not re.match(r"^\d+(\.\d+)*$", valeur(champs, "version") or ""):
            problemes.append("version non numérique : %s" % valeur(champs, "version"))
        if not re.match(r"^https?://", valeur(champs, "repository") or ""):
            problemes.append("repository n'est pas une URL : %s" % valeur(champs, "repository"))
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", valeur(champs, "email") or ""):
            problemes.append("email invalide : %s" % valeur(champs, "email"))
        if valeur(champs, "category") not in ("Raster", "Vector", "Database", "Mesh", "Web"):
            problemes.append("catégorie hors liste : %s" % valeur(champs, "category"))
        icone = "%s/%s" % (PLUGIN, valeur(champs, "icon") or "icon.png")
        if icone not in noms:
            problemes.append("icône introuvable dans l'archive : %s" % icone)

        # La licence du dossier du plugin doit être identique à celle de la racine.
        racine_licence = os.path.join(RACINE, LICENCE)
        plugin_licence = os.path.join(RACINE, PLUGIN, LICENCE)
        if not os.path.isfile(plugin_licence):
            problemes.append("licence absente du dossier du plugin")
        elif open(racine_licence, "rb").read() != open(plugin_licence, "rb").read():
            problemes.append(
                "les deux copies de %s ont divergé : recopiez la racine dans %s/" % (LICENCE, PLUGIN)
            )

        # Le dépôt doit porter exactement ce que l'archive contient (hors fichiers compilés).
        for nom in noms:
            if not os.path.isfile(os.path.join(RACINE, nom)):
                problemes.append("fichier de l'archive absent du dépôt : %s" % nom)

        # 4. Le paquet doit rester sous la limite d'envoi du dépôt (20 Mo).
        if os.path.getsize(archive) > 20 * 1024 * 1024:
            problemes.append("archive au-delà de la limite d'envoi de 20 Mo")

        print("Archive : %s" % archive)
        for nom in sorted(noms):
            print("  %-46s %7d o" % (nom, zip_.getinfo(nom).file_size))

    if problemes:
        print("\nÉCHEC — %d problème(s) :" % len(problemes))
        for probleme in problemes:
            print("  - %s" % probleme)
        return 1

    print("\nOK — l'archive respecte les règles du dépôt officiel.")
    return 0


if __name__ == "__main__":
    sys.exit(verifier())
