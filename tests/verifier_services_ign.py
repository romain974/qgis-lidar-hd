# -*- coding: utf-8 -*-
"""Vérification en direct des services de l'IGN utilisés par le plugin.

Contrôle que le catalogue LiDAR HD répond, que la dalle annoncée se laisse lire
en HTTP Range (c'est la condition de la lecture à distance dans QGIS), et que
l'en-tête du fichier est bien un LAS/COPC exploitable.

    python tests/verifier_services_ign.py
"""

import os
import struct
import sys

RACINE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lidar_hd_emprise"
)
sys.path.insert(0, RACINE)

import lidarhd  # noqa: E402

EMPRISE = (6.1200, 45.8950, 6.1350, 45.9050)  # Annecy


def verifier_catalogue():
    dalles = lidarhd.dalles_pour_emprise(EMPRISE, maximum=10)
    assert dalles, "le catalogue n'a renvoyé aucune dalle pour l'emprise test"
    dalle = dalles[0]
    assert dalle["url"].startswith("https://data.geopf.fr/"), dalle["url"]
    assert dalle["url"].endswith(".copc.laz"), dalle["url"]
    assert dalle["points"] > 0
    print("  catalogue WFS      : %d dalle(s) — %s (%s points)"
          % (len(dalles), dalle["nom"], format(dalle["points"], ",")))
    return dalle


def verifier_tete_de_fichier(url):
    """Lit le début du fichier en Range et contrôle l'en-tête LAS/COPC.

    Signature « LASF », version 1.4, en-tête de 375 octets, et première VLR
    signée « copc » (record 1) : c'est exactement ce que QGIS lit avant
    d'ouvrir la couche de nuage de points, et c'est ce qui autorise la lecture
    à distance par blocs.
    """
    import urllib.request

    requete = urllib.request.Request(url, headers={"User-Agent": "QGIS-LiDAR-HD-Emprise",
                                                   "Range": "bytes=0-459"})
    with urllib.request.urlopen(requete, timeout=30) as reponse:
        code = reponse.status
        bloc = reponse.read()
    assert code == 206, "le serveur ne gère pas les requêtes Range (HTTP %s)" % code
    assert bloc[:4] == b"LASF", "signature LAS absente : %r" % bloc[:4]

    version = "%d.%d" % (bloc[24], bloc[25])
    format_points = bloc[104] & 0x3F  # le bit 7 signale la compression LAZ
    compresse = bool(bloc[104] & 0x80)
    taille_en_tete = struct.unpack("<H", bloc[94:96])[0]
    # En LAS 1.4 le compte historique (offset 107) vaut 0 : le vrai compte est
    # le champ étendu sur 8 octets à l'offset 247.
    nombre_points = struct.unpack("<Q", bloc[247:255])[0]
    assert version == "1.4", "version LAS inattendue : %s" % version
    assert taille_en_tete == 375, "taille d'en-tête LAS inattendue : %d" % taille_en_tete
    assert compresse, "le fichier n'est pas compressé (LAZ attendu)"

    # Première VLR, juste après l'en-tête : user_id sur 16 octets à +2.
    user_id = bloc[taille_en_tete + 2: taille_en_tete + 18].split(b"\x00")[0]
    record_id = struct.unpack("<H", bloc[taille_en_tete + 18: taille_en_tete + 20])[0]
    assert user_id == b"copc" and record_id == 1, (
        "première VLR inattendue : %r (record %d) — fichier non COPC" % (user_id, record_id)
    )
    print("  en-tête du fichier : LAS %s, format de point %d compressé, "
          "%s points, 1re VLR « %s » (COPC)"
          % (version, format_points, format(nombre_points, ","), user_id.decode()))
    return nombre_points


def verifier_poids(url):
    octets = lidarhd.taille_fichier(url)
    assert octets > 1024 * 1024, "poids annoncé suspect : %s" % octets
    print("  poids de la dalle  : %.0f Mo" % (octets / 1024.0 / 1024.0))
    return octets


if __name__ == "__main__":
    print("Vérification des services LiDAR HD de l'IGN — emprise d'Annecy")
    dalle = verifier_catalogue()
    points = verifier_tete_de_fichier(dalle["url"])
    octets = verifier_poids(dalle["url"])

    ecart = abs(points - dalle["points"]) / float(dalle["points"])
    assert ecart < 0.02, (
        "le catalogue annonce %d points, l'en-tête en contient %d (écart %.1f %%)"
        % (dalle["points"], points, ecart * 100)
    )
    print("  cohérence         : catalogue et en-tête concordent à %.2f %%" % (ecart * 100))
    print("  OK — la dalle est lisible en flux, sans téléchargement complet "
          "(%.0f Mo annoncés, un COPC n'en récupère que les blocs utiles)."
          % (octets / 1024.0 / 1024.0))
