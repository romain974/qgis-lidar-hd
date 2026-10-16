# -*- coding: utf-8 -*-
"""Tests hors ligne du module lidarhd (aucun accès réseau, aucune dépendance QGIS).

    python tests/test_lidarhd.py
"""

import json
import os
import shutil
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

RACINE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lidar_hd_emprise"
)
sys.path.insert(0, RACINE)

import lidarhd  # noqa: E402

# --- Faux catalogue WFS ------------------------------------------------------

FAUSSES_DALLES = {
    "features": [
        {
            "geometry": {
                "type": "MultiPolygon",
                "coordinates": [[[[6.11, 45.89], [6.12, 45.89], [6.12, 45.90], [6.11, 45.90], [6.11, 45.89]]]],
            },
            "properties": {
                "coordonnees_nw": "0943-6540",
                "nombre_points": 46291482,
                "url_npl": "https://exemple/LHD_FXX_0943_6540_PTS_LAMB93_IGN69.copc.laz",
            },
        },
        {
            "geometry": {
                "type": "MultiPolygon",
                "coordinates": [[[[6.12, 45.89], [6.13, 45.89], [6.13, 45.90], [6.12, 45.90], [6.12, 45.89]]]],
            },
            "properties": {
                "coordonnees_nw": "0944-6540",
                "nombre_points": 41000000,
                "url_npl": "https://exemple/LHD_FXX_0944_6540_PTS_LAMB93_IGN69.copc.laz",
            },
        },
        # Doublon : même URL, doit être écarté.
        {
            "geometry": None,
            "properties": {
                "coordonnees_nw": "0944-6540",
                "nombre_points": 41000000,
                "url_npl": "https://exemple/LHD_FXX_0944_6540_PTS_LAMB93_IGN69.copc.laz",
            },
        },
        # Dalle sans nuage de points (MNT seulement) : doit être écartée.
        {"geometry": None, "properties": {"coordonnees_nw": "0945-6540", "url_npl": None}},
    ]
}


class FauxServeur(threading.Thread):
    """Petit serveur HTTP local : sert ``contenu`` et annonce sa taille."""

    def __init__(self, contenu):
        super().__init__(daemon=True)
        self.contenu = contenu
        self.appels = []

        classe = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                classe.appels.append(("GET", self.path))
                self.send_response(200)
                self.send_header("Content-Length", str(len(classe.contenu)))
                self.end_headers()
                self.wfile.write(classe.contenu)

            def do_HEAD(self):
                self.send_response(200)
                self.send_header("Content-Length", str(len(classe.contenu)))
                self.end_headers()

            def log_message(self, *args):
                pass

        self.serveur = HTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.serveur.server_address[1]

    def run(self):
        self.serveur.serve_forever()

    def url(self, chemin="/fichier.bin"):
        return "http://127.0.0.1:%d%s" % (self.port, chemin)

    def stop(self):
        self.serveur.shutdown()


class TestRequeteWfs(unittest.TestCase):
    def test_ordre_des_axes(self):
        """Le WFS 2.0 attend l'emprise en lat,lon — l'inverser renvoie zéro dalle."""
        url = lidarhd.url_wfs((6.11, 45.89, 6.13, 45.90))
        self.assertIn("BBOX=45.89,6.11,45.9,6.13", url)
        self.assertIn("SRSName=epsg:4326", url)
        self.assertIn(lidarhd.COUCHE_METADONNEE, url)

    def test_limite_reprise_dans_l_url(self):
        self.assertIn("count=7", lidarhd.url_wfs((0, 0, 1, 1), maximum=7))


class TestEmpriseGeometrie(unittest.TestCase):
    def test_multipolygon(self):
        geometrie = FAUSSES_DALLES["features"][0]["geometry"]
        self.assertEqual(lidarhd.emprise_geometrie(geometrie), (6.11, 45.89, 6.12, 45.90))

    def test_polygon_et_geometrie_absente(self):
        self.assertEqual(
            lidarhd.emprise_geometrie({"type": "Polygon", "coordinates": [[[0, 1], [2, 3]]]}),
            (0.0, 1.0, 2.0, 3.0),
        )
        self.assertIsNone(lidarhd.emprise_geometrie(None))
        self.assertIsNone(lidarhd.emprise_geometrie({"type": "Point", "coordinates": [0, 0]}))


class TestDalles(unittest.TestCase):
    def setUp(self):
        self.reponses = []

        def fausse_lecture(url, timeout=30):
            self.reponses.append(url)
            return json.dumps(FAUSSES_DALLES).encode("utf-8")

        self.vraie_lecture = lidarhd._lire
        lidarhd._lire = fausse_lecture

    def tearDown(self):
        lidarhd._lire = self.vraie_lecture

    def test_deduplication_et_noms(self):
        dalles = lidarhd.dalles_pour_emprise((6.11, 45.89, 6.13, 45.90))
        self.assertEqual([d["nom"] for d in dalles], ["LHD_FXX_0943_6540_PTS_LAMB93_IGN69",
                                                      "LHD_FXX_0944_6540_PTS_LAMB93_IGN69"])
        self.assertEqual(dalles[0]["points"], 46291482)
        self.assertTrue(dalles[0]["url"].endswith(".copc.laz"))

    def test_emprise_transmise_dans_le_bon_ordre(self):
        """L'emprise part en lat,lon — le WFS 2.0 renvoie zéro dalle sinon."""
        lidarhd.dalles_pour_emprise((6.11, 45.89, 6.13, 45.90))
        self.assertIn("BBOX=45.89,6.11,45.9,6.13", self.reponses[0])

    def test_catalogue_vide(self):
        lidarhd._lire = lambda url, timeout=30: b'{"features": []}'
        self.assertEqual(lidarhd.dalles_pour_emprise((0, 0, 1, 1)), [])


class TestTelechargement(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contenu = os.urandom(300000)
        cls.serveur = FauxServeur(cls.contenu)
        cls.serveur.start()
        cls.dossier = tempfile.mkdtemp(prefix="lidarhd-test-")

    @classmethod
    def tearDownClass(cls):
        cls.serveur.stop()
        shutil.rmtree(cls.dossier, ignore_errors=True)

    def test_taille_fichier(self):
        self.assertEqual(lidarhd.taille_fichier(self.serveur.url()), len(self.contenu))

    def test_telechargement_complet(self):
        destination = os.path.join(self.dossier, "dalle.copc.laz")
        etapes = []
        resultat = lidarhd.telecharger(
            self.serveur.url(), destination, progres=lambda faits, total: etapes.append((faits, total))
        )
        self.assertEqual(resultat, destination)
        with open(destination, "rb") as fichier:
            self.assertEqual(fichier.read(), self.contenu)
        self.assertFalse(os.path.exists(destination + ".part"))
        self.assertTrue(etapes, "la progression n'a jamais été signalée")
        self.assertEqual(etapes[-1], (len(self.contenu), len(self.contenu)))

    def test_arret_supprime_le_fichier_partiel(self):
        destination = os.path.join(self.dossier, "interrompu.copc.laz")
        appels = {"n": 0}

        def arret():
            appels["n"] += 1
            return appels["n"] > 1

        resultat = lidarhd.telecharger(
            self.serveur.url(), destination, arret=arret, bloc=4096
        )
        self.assertIsNone(resultat)
        self.assertFalse(os.path.exists(destination))
        self.assertFalse(os.path.exists(destination + ".part"))

    def test_dossier_absent_cree(self):
        destination = os.path.join(self.dossier, "sous", "dossier", "dalle.copc.laz")
        self.assertEqual(lidarhd.telecharger(self.serveur.url(), destination), destination)
        self.assertTrue(os.path.isfile(destination))


if __name__ == "__main__":
    unittest.main(verbosity=2)
