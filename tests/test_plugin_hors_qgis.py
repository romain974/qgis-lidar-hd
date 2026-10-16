# -*- coding: utf-8 -*-
"""Import et exercice du plugin hors de QGIS.

QGIS n'est pas installé sur cette machine : on remplace l'arbre ``qgis`` par des
doublures minimales, puis on vérifie que le plugin s'importe, que ``classFactory``
construit bien l'objet, que la fenêtre se monte, et que la tâche d'analyse
produit la liste de dalles attendue.

Ce test attrape les fautes de frappe, les noms d'API inexistants et les erreurs
d'import ; il ne remplace pas un essai dans QGIS.

    python tests/test_plugin_hors_qgis.py
"""

import os
import sys
import types
import unittest
from unittest.mock import MagicMock

RACINE = os.environ.get("PLUGIN_DIR") or os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lidar_hd_emprise"
)

# Étiquettes construites par les doublures : sert à vérifier le crédit affiché.
ETIQUETTES_CREES = []


# --- Doublures de l'API QGIS -------------------------------------------------


def _classe_factice(nom):
    """Classe permissive : accepte tout argument, répond à tout appel."""

    def __init__(self, *args, **kwargs):
        pass

    def __getattr__(self, item):
        return MagicMock()

    return type(nom, (object,), {"__init__": __init__, "__getattr__": __getattr__})


def _installer_doublures():
    noms_core = [
        "Qgis",
        "QgsCoordinateReferenceSystem",
        "QgsCoordinateTransform",
        "QgsMessageLog",
        "QgsPointCloudLayer",
        "QgsProject",
        "QgsRectangle",
        "QgsTask",
        "QgsTaskManager",
        "QgsApplication",
        "QgsSettings",
    ]
    noms_qtcore = ["QStandardPaths", "Qt", "QUrl", "QObject", "pyqtSignal"]
    noms_qtgui = ["QDesktopServices", "QIcon", "QAction"]
    noms_qtwidgets = [
        "QAction",
        "QComboBox",
        "QDialog",
        "QFileDialog",
        "QFormLayout",
        "QHBoxLayout",
        "QLabel",
        "QLineEdit",
        "QMessageBox",
        "QProgressBar",
        "QPushButton",
        "QTextEdit",
        "QVBoxLayout",
    ]

    qgis = types.ModuleType("qgis")
    qgis.__path__ = []

    core = types.ModuleType("qgis.core")
    for nom in noms_core:
        setattr(core, nom, _classe_factice(nom))
    core.Qgis = MagicMock(Warning=1, Info=0, Success=2)
    core.QgsMessageLog = MagicMock()

    class _FauxQgsTask(object):
        """Squelette suffisant pour exercer les tâches du plugin."""

        CanCancel = 1
        Complete = 2
        Terminated = 3

        def __init__(self, description="", *args, **kwargs):
            self.description = description
            self._progres = 0

        def isCanceled(self):
            return False

        def setProgress(self, valeur):
            self._progres = valeur

        def status(self):
            return self.Complete

    core.QgsTask = _FauxQgsTask
    core.QgsProject = _classe_factice("QgsProject")
    core.QgsProject.instance = staticmethod(lambda: MagicMock())
    core.QgsCoordinateReferenceSystem = _classe_factice("QgsCoordinateReferenceSystem")
    qgis.core = core

    pyqt = types.ModuleType("qgis.PyQt")
    pyqt.__path__ = []

    qtcore = types.ModuleType("qgis.PyQt.QtCore")
    for nom in noms_qtcore:
        setattr(qtcore, nom, _classe_factice(nom))
    qtcore.Qt = MagicMock()
    # QStandardPaths est réellement exercé par le plugin (dossier par défaut).
    qtcore.QStandardPaths = _classe_factice("QStandardPaths")
    qtcore.QStandardPaths.DocumentsLocation = 1
    qtcore.QStandardPaths.writableLocation = staticmethod(
        lambda *args: os.path.join(os.path.expanduser("~"), "Documents")
    )
    pyqt.QtCore = qtcore

    qtgui = types.ModuleType("qgis.PyQt.QtGui")
    for nom in noms_qtgui:
        setattr(qtgui, nom, _classe_factice(nom))
    pyqt.QtGui = qtgui

    qtwidgets = types.ModuleType("qgis.PyQt.QtWidgets")
    for nom in noms_qtwidgets:
        setattr(qtwidgets, nom, _classe_factice(nom))

    class _FauxCombo(object):
        """Combo minimal : on veut vérifier ce que le plugin y met réellement."""

        class _Signal(object):
            def connect(self, *args):
                pass

        def __init__(self, *args):
            self.items = []
            # Dans Qt, currentIndexChanged est un signal (attribut), pas une méthode.
            self.currentIndexChanged = self._Signal()

        def addItems(self, valeurs):
            self.items.extend(valeurs)

        def count(self):
            return len(self.items)

        def currentIndex(self):
            return 0

    class _FauxLabel(object):
        """Étiquette qui retient son texte : on veut vérifier le crédit affiché."""

        def __init__(self, texte="", *args):
            self.texte = texte
            ETIQUETTES_CREES.append(self)

        def setWordWrap(self, *args):
            pass

        def setOpenExternalLinks(self, *args):
            pass

        def setStyleSheet(self, *args):
            pass

    qtwidgets.QLabel = _FauxLabel
    qtwidgets.QComboBox = _FauxCombo
    pyqt.QtWidgets = qtwidgets

    sys.modules["qgis"] = qgis
    sys.modules["qgis.core"] = core
    sys.modules["qgis.PyQt"] = pyqt
    sys.modules["qgis.PyQt.QtCore"] = qtcore
    sys.modules["qgis.PyQt.QtGui"] = qtgui
    sys.modules["qgis.PyQt.QtWidgets"] = qtwidgets


_installer_doublures()
sys.path.insert(0, os.path.dirname(RACINE))

import lidar_hd_emprise  # noqa: E402
from lidar_hd_emprise import lidarhd, plugin  # noqa: E402


class FauxIface:
    """Interface QGIS réduite au strict nécessaire."""

    def mainWindow(self):
        return MagicMock()

    def activeLayer(self):
        return None

    def mapCanvas(self):
        return MagicMock()

    def addToolBarIcon(self, *args):
        pass

    def addPluginToMenu(self, *args):
        pass

    def removePluginMenu(self, *args):
        pass

    def removeToolBarIcon(self, *args):
        pass


class TestChargement(unittest.TestCase):
    def test_classFactory(self):
        instance = lidar_hd_emprise.classFactory(FauxIface())
        self.assertIsInstance(instance, plugin.PluginLidarHD)

    def test_initGui_et_unload(self):
        instance = lidar_hd_emprise.classFactory(FauxIface())
        instance.initGui()
        self.assertIsNotNone(instance.action)
        self.assertTrue(instance.action.text())
        instance.unload()
        self.assertIsNone(instance.action)

    def test_icone_presente(self):
        chemin = os.path.join(RACINE, "icon.png")
        self.assertTrue(os.path.isfile(chemin), "icon.png manquant dans le plugin")
        self.assertGreater(os.path.getsize(chemin), 100)

    def test_fenetre_se_construit(self):
        fenetre = plugin.FenetreLidarHD(FauxIface())
        self.assertEqual(
            fenetre.choix_mode.items,
            [
                "Télécharger les dalles puis les afficher",
                "Lire à distance, sans rien télécharger (COPC)",
            ],
        )

    def test_le_credit_pointe_vers_le_site(self):
        """Le crédit est une condition de la licence : sa présence est testée."""
        del ETIQUETTES_CREES[:]
        plugin.FenetreLidarHD(FauxIface())
        textes = [etiquette.texte for etiquette in ETIQUETTES_CREES]
        self.assertTrue(textes, "aucune étiquette construite")
        self.assertTrue(
            any(plugin.SITE_AUTEUR in texte for texte in textes),
            "aucun libellé ne porte le lien vers %s" % plugin.SITE_AUTEUR,
        )


class TestTacheAnalyse(unittest.TestCase):
    def setUp(self):
        self.dalles = [
            {"nom": "LHD_FXX_0943_6540_PTS_LAMB93_IGN69",
             "url": "https://exemple/dalle.copc.laz",
             "points": 46291482,
             "emprise": None},
        ]
        self.vrai_dalles = lidarhd.dalles_pour_emprise
        self.vrai_taille = lidarhd.taille_fichier

    def tearDown(self):
        lidarhd.dalles_pour_emprise = self.vrai_dalles
        lidarhd.taille_fichier = self.vrai_taille

    def test_run_collecte_les_poids(self):
        lidarhd.dalles_pour_emprise = lambda bbox, maximum=50: list(self.dalles)
        lidarhd.taille_fichier = lambda url: 242413076
        tache = plugin.TacheAnalyse((6.11, 45.89, 6.13, 45.90))
        self.assertTrue(tache.run())
        self.assertEqual(tache.dalles[0]["octets"], 242413076)
        self.assertFalse(tache.tronquee)

    def test_run_remonte_l_erreur_sans_lever(self):
        def explose(bbox, maximum=50):
            raise lidarhd.ErreurIGN("Service IGN injoignable")

        lidarhd.dalles_pour_emprise = explose
        tache = plugin.TacheAnalyse((0, 0, 1, 1))
        self.assertFalse(tache.run())
        self.assertIn("injoignable", tache.erreur)

    def test_emprise_tronquee_signalee(self):
        lidarhd.dalles_pour_emprise = lambda bbox, maximum=50: [dict(d) for d in self.dalles * maximum]
        lidarhd.taille_fichier = lambda url: 1
        tache = plugin.TacheAnalyse((0, 0, 1, 1))
        self.assertTrue(tache.run())
        self.assertTrue(tache.tronquee)


class TestAjoutDesCouches(unittest.TestCase):
    """La lecture à distance passe l'URL ; le téléchargement passe un chemin local."""

    def setUp(self):
        self.fenetre = plugin.FenetreLidarHD(FauxIface())
        self.fenetre.dalles = [
            {"nom": "LHD_FXX_0943_6540_PTS_LAMB93_IGN69",
             "url": "https://exemple/dalle.copc.laz",
             "points": 1,
             "emprise": None}
        ]
        self.construits = []

        construits = self.construits

        class FausseCouche(object):
            def __init__(self, uri, nom, fournisseur):
                construits.append((uri, nom, fournisseur))

            def isValid(self):
                return True

            def extent(self):
                return MagicMock()

        self.vraie_couche = plugin.QgsPointCloudLayer
        self.vrai_projet = plugin.QgsProject
        plugin.QgsPointCloudLayer = FausseCouche
        plugin.QgsProject = MagicMock()
        plugin.QgsProject.instance.return_value.addMapLayer.return_value = True

    def tearDown(self):
        plugin.QgsPointCloudLayer = self.vraie_couche
        plugin.QgsProject = self.vrai_projet

    def test_uri_distante(self):
        self.fenetre.ajouter(distance=True)
        self.assertEqual(self.construits[0][0], "https://exemple/dalle.copc.laz")
        self.assertEqual(self.construits[0][2], "pointcloud")

    def test_chemin_local_normalise(self):
        self.fenetre.ajouter(
            chemins=[os.path.join("C:\\", "tmp", "LHD_FXX_0943_6540_PTS_LAMB93_IGN69.copc.laz")],
            distance=False,
        )
        uri = self.construits[0][0]
        self.assertTrue(uri.endswith("LHD_FXX_0943_6540_PTS_LAMB93_IGN69.copc.laz"))
        self.assertNotIn("\\", uri, "QGIS attend des barres obliques dans l'URI")

    def test_fichier_absent_ignore_sans_erreur(self):
        self.fenetre.ajouter(chemins=["/autre/chose.copc.laz"], distance=False)
        self.assertEqual(self.construits, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
