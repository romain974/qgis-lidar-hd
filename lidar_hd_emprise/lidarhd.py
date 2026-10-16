# -*- coding: utf-8 -*-
"""
Résolution et téléchargement des dalles LiDAR HD (IGN / Géoplateforme).

Ce module ne dépend PAS de QGIS : il ne fait que du réseau et de la géométrie.
Il est donc testable seul (voir tests/test_lidarhd.py).

Source des données : programme LiDAR HD de l'IGN, diffusé en open data
(licence Etalab 2.0) sur la Géoplateforme <https://geopf.fr>.
"""

import json
import os
import urllib.error
import urllib.parse
import urllib.request

# --- Services de l'IGN -------------------------------------------------------

WFS = "https://data.geopf.fr/wfs/ows"
COUCHE_METADONNEE = "IGNF_LIDAR-HD_METADONNEE:metadata"

# Hôtes des dalles : les URLs de nuages de points viennent du WFS, on ne les
# ouvre que si elles pointent bien chez le diffuseur.
HOTES_DONNEES = ("data.geopf.fr",)

AGENT = "QGIS-LiDAR-HD-Emprise"

# Le WFS n'accepte l'emprise qu'en WGS84, et dans l'ordre lat,lon (WFS 2.0).
CRS_REQUETE = "epsg:4326"

# Seuls ces schémas sont ouverts. Sans ce garde-fou, une URL `file:///` ou
# `ftp://` injectée dans une réponse du WFS serait suivie telle quelle.
SCHEMAS_AUTORISES = ("http", "https")


class ErreurIGN(Exception):
    """Erreur remontée par le service de l'IGN."""


# --- Utilitaires -------------------------------------------------------------


def verifier_url(url, hotes=None):
    """Refuse tout ce qui n'est pas une URL http(s) attendue.

    Lève ``ErreurIGN`` si le schéma n'est pas http ou https, ou si ``hotes`` est
    fourni et que le domaine n'en fait pas partie. Renvoie l'URL inchangée.
    """
    if not isinstance(url, str):
        raise ErreurIGN("URL invalide : %r" % (url,))
    parties = urllib.parse.urlsplit(url)
    if parties.scheme.lower() not in SCHEMAS_AUTORISES:
        raise ErreurIGN(
            "schéma d'URL refusé (%s) : seules les adresses http et https sont ouvertes."
            % (parties.scheme or "aucun")
        )
    if not parties.netloc:
        raise ErreurIGN("URL sans domaine : %s" % url)
    if hotes is not None and (parties.hostname or "").lower() not in tuple(
        h.lower() for h in hotes
    ):
        raise ErreurIGN(
            "domaine d'URL refusé (%s) : attendu %s."
            % (parties.hostname, " ou ".join(hotes))
        )
    return url


def _ouvrir(url, timeout=30, methode=None, hotes=None):
    """Ouvre une URL après contrôle du schéma (et du domaine si demandé).

    ``urlopen`` accepte ``file://``, ``ftp://`` et tout schéma enregistré par une
    bibliothèque tierce : c'est la porte d'entrée classique. Le contrôle du
    schéma est fait ici, avant l'ouverture, et c'est la seule fonction du module
    qui appelle ``urlopen``.
    """
    verifier_url(url, hotes=hotes)
    requete = urllib.request.Request(url, method=methode, headers={"User-Agent": AGENT})
    # Le schéma et le domaine viennent d'être contrôlés : pas d'ouverture
    # possible de file://, ftp:// ou d'un schéma enregistré par une dépendance.
    return urllib.request.urlopen(requete, timeout=timeout)  # nosec B310


def _lire(url, timeout=30):
    """GET simple, avec un User-Agent explicite."""
    with _ouvrir(url, timeout=timeout) as reponse:
        return reponse.read()


def url_wfs(bbox_wgs84, maximum=50):
    """URL de la requête WFS listant les dalles qui intersectent l'emprise.

    ``bbox_wgs84`` = (minLon, minLat, maxLon, maxLat).
    """
    min_lon, min_lat, max_lon, max_lat = bbox_wgs84
    return (
        "%s?SERVICE=WFS&VERSION=2.0.0&REQUEST=GetFeature"
        "&TYPENAME=%s&outputFormat=application/json&SRSName=%s"
        "&count=%d&BBOX=%s,%s,%s,%s"
        % (
            WFS,
            COUCHE_METADONNEE,
            CRS_REQUETE,
            maximum,
            min_lat,
            min_lon,
            max_lat,
            max_lon,
        )
    )


def emprise_geometrie(geometrie):
    """Emprise (minLon, minLat, maxLon, maxLat) d'une géométrie GeoJSON."""
    if not geometrie:
        return None
    if geometrie.get("type") == "Polygon":
        polygones = [geometrie.get("coordinates") or []]
    elif geometrie.get("type") == "MultiPolygon":
        polygones = geometrie.get("coordinates") or []
    else:
        return None

    x_min = y_min = float("inf")
    x_max = y_max = float("-inf")
    for polygone in polygones:
        for anneau in polygone[:1]:
            for point in anneau:
                x_min = min(x_min, point[0])
                y_min = min(y_min, point[1])
                x_max = max(x_max, point[0])
                y_max = max(y_max, point[1])
    if x_min == float("inf"):
        return None
    return (x_min, y_min, x_max, y_max)


# --- Résolution des dalles ---------------------------------------------------


def dalles_pour_emprise(bbox_wgs84, maximum=50):
    """Liste des dalles LiDAR HD qui recouvrent l'emprise.

    Renvoie une liste de dictionnaires ::

        {"nom": "LHD_FXX_0943_6540_PTS_LAMB93_IGN69",
         "url": "https://data.geopf.fr/telechargement/...copc.laz",
         "points": 46291482,
         "emprise": (minLon, minLat, maxLon, maxLat)}
    """
    try:
        brut = _lire(url_wfs(bbox_wgs84, maximum))
    except urllib.error.HTTPError as erreur:
        raise ErreurIGN("Le service WFS de l'IGN a répondu HTTP %s." % erreur.code)
    except urllib.error.URLError as erreur:
        raise ErreurIGN("Service IGN injoignable : %s" % erreur.reason)

    try:
        donnees = json.loads(brut.decode("utf-8"))
    except ValueError:
        raise ErreurIGN("Réponse illisible du service WFS de l'IGN.")

    dalles = []
    vues = set()
    for entite in donnees.get("features") or []:
        proprietes = entite.get("properties") or {}
        url = proprietes.get("url_npl")
        if not url or url in vues:
            continue
        vues.add(url)
        nom = os.path.basename(url.split("?")[0])
        if nom.endswith(".copc.laz"):
            nom = nom[: -len(".copc.laz")]
        elif nom.endswith(".laz"):
            nom = nom[: -len(".laz")]
        dalles.append(
            {
                "nom": nom or proprietes.get("coordonnees_nw") or "dalle",
                "url": url,
                "points": proprietes.get("nombre_points") or 0,
                "emprise": emprise_geometrie(entite.get("geometry")),
            }
        )

    # Les plus grosses dalles d'abord : l'ordre d'ajout à la carte est plus lisible.
    dalles.sort(key=lambda d: d["nom"])
    return dalles


def taille_fichier(url, timeout=30):
    """Poids du fichier en octets (0 si le serveur ne l'annonce pas)."""
    try:
        with _ouvrir(url, timeout=timeout, methode="HEAD", hotes=HOTES_DONNEES) as reponse:
            return int(reponse.headers.get("Content-Length") or 0)
    except Exception:
        return 0


def telecharger(url, destination, progres=None, arret=None, bloc=1024 * 512):
    """Télécharge ``url`` vers ``destination``.

    ``progres(faits, total)`` est appelé régulièrement (total peut valoir 0).
    ``arret()`` est interrogé entre deux blocs ; s'il renvoie vrai, on s'arrête
    et le fichier partiel est supprimé. Le fichier n'apparaît à sa place
    définitive qu'une fois complet (écriture dans ``.part`` puis renommage).

    L'URL est contrôlée avant ouverture : schéma http(s) obligatoire, et domaine
    du diffuseur imposé — les URLs viennent d'une réponse du WFS.
    """
    verifier_url(url, hotes=HOTES_DONNEES)

    dossier = os.path.dirname(destination)
    if dossier and not os.path.isdir(dossier):
        os.makedirs(dossier)

    partiel = destination + ".part"
    with _ouvrir(url, timeout=60, hotes=HOTES_DONNEES) as reponse:
        total = int(reponse.headers.get("Content-Length") or 0)
        faits = 0
        with open(partiel, "wb") as fichier:
            while True:
                if arret is not None and arret():
                    fichier.close()
                    os.remove(partiel)
                    return None
                morceau = reponse.read(bloc)
                if not morceau:
                    break
                fichier.write(morceau)
                faits += len(morceau)
                if progres is not None:
                    progres(faits, total)

    os.replace(partiel, destination)
    return destination
