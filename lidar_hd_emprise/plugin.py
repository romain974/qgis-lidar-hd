# -*- coding: utf-8 -*-
"""Plugin QGIS « LiDAR HD - dalles par emprise ».

Interroge le catalogue LiDAR HD de la Géoplateforme depuis l'étendue de la
carte, puis télécharge (ou lit à distance) les dalles de nuage de points
correspondantes et les ajoute au projet.

Développé par l'auteur du simulateur de toiture <https://www.simulateur-toiture.fr>,
qui exploite ces mêmes dalles LiDAR HD de l'IGN.
"""

import os
import traceback

from qgis.core import (
    Qgis,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsMessageLog,
    QgsPointCloudLayer,
    QgsProject,
    QgsRectangle,
    QgsTask,
)
from qgis.PyQt.QtCore import QStandardPaths
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import (
    QAction,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from . import lidarhd

NOM_MENU = "&LiDAR HD"
SITE_AUTEUR = "https://www.simulateur-toiture.fr"
MAX_DALLES = 40  # au-delà, on refuse : l'emprise est trop large pour être utile


def _dossier_par_defaut():
    racine = QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation)
    if not racine:
        racine = os.path.expanduser("~")
    return os.path.join(racine, "LiDAR HD")


def _octets_en_texte(n):
    if not n:
        return "taille inconnue"
    unites = ("o", "Ko", "Mo", "Go", "To")
    valeur = float(n)
    rang = 0
    while valeur >= 1024 and rang < len(unites) - 1:
        valeur /= 1024.0
        rang += 1
    return "%.0f %s" % (valeur, unites[rang]) if rang == 0 else "%.1f %s" % (valeur, unites[rang])


# --- Tâches (exécutées hors du fil de l'interface) ---------------------------


class TacheAnalyse(QgsTask):
    """Liste les dalles qui recouvrent l'emprise, et leur poids."""

    def __init__(self, bbox):
        super().__init__("LiDAR HD : recherche des dalles", QgsTask.CanCancel)
        self.bbox = bbox
        self.dalles = []
        self.tronquee = False
        self.erreur = None

    def run(self):
        try:
            self.dalles = lidarhd.dalles_pour_emprise(self.bbox, maximum=MAX_DALLES)
            self.tronquee = len(self.dalles) >= MAX_DALLES
            for dalle in self.dalles:
                if self.isCanceled():
                    return False
                dalle["octets"] = lidarhd.taille_fichier(dalle["url"])
        except Exception as erreur:  # remonté tel quel dans le journal
            self.erreur = str(erreur)
            QgsMessageLog.logMessage(traceback.format_exc(), "LiDAR HD", Qgis.Warning)
            return False
        return True


class TacheTelechargement(QgsTask):
    """Télécharge les dalles une par une dans un dossier."""

    def __init__(self, dalles, dossier):
        super().__init__(
            "LiDAR HD : téléchargement de %d dalle(s)" % len(dalles), QgsTask.CanCancel
        )
        self.dalles = dalles
        self.dossier = dossier
        self.chemins = []
        self.erreur = None

    def run(self):
        total = sum(dalle.get("octets") or 0 for dalle in self.dalles) or 1
        deja_fait = 0
        try:
            for dalle in self.dalles:
                if self.isCanceled():
                    return False
                destination = os.path.join(self.dossier, dalle["nom"] + ".copc.laz")

                # Fichier déjà présent et complet : on ne retélécharge rien.
                attendu = dalle.get("octets") or 0
                if attendu and os.path.exists(destination):
                    if os.path.getsize(destination) == attendu:
                        self.chemins.append(destination)
                        deja_fait += attendu
                        continue

                def progres(faits, _total, base=deja_fait):
                    self.setProgress(min(100.0, 100.0 * (base + faits) / total))

                resultat = lidarhd.telecharger(
                    dalle["url"],
                    destination,
                    progres=progres,
                    arret=self.isCanceled,
                )
                if resultat is None:
                    return False
                self.chemins.append(destination)
                deja_fait += attendu
        except Exception as erreur:
            self.erreur = str(erreur)
            QgsMessageLog.logMessage(traceback.format_exc(), "LiDAR HD", Qgis.Warning)
            return False
        return True


# --- Fenêtre -----------------------------------------------------------------


class FenetreLidarHD(QDialog):
    def __init__(self, iface):
        super().__init__(iface.mainWindow())
        self.iface = iface
        self.dalles = []
        self.taches = []

        self.setWindowTitle("LiDAR HD — dalles par emprise")
        self.setMinimumWidth(560)

        disposition = QVBoxLayout(self)

        intro = QLabel(
            "Le plugin interroge le catalogue <b>LiDAR HD</b> de l'IGN pour l'étendue "
            "affichée dans QGIS, puis affiche les dalles de nuage de points correspondantes."
        )
        intro.setWordWrap(True)
        disposition.addWidget(intro)

        self.etiquette_emprise = QLabel()
        self.etiquette_emprise.setWordWrap(True)
        self.etiquette_emprise.setStyleSheet("color: palette(mid);")
        disposition.addWidget(self.etiquette_emprise)

        formulaire = QFormLayout()
        self.choix_mode = QComboBox()
        self.choix_mode.addItems(
            [
                "Télécharger les dalles puis les afficher",
                "Lire à distance, sans rien télécharger (COPC)",
            ]
        )
        formulaire.addRow("Mode :", self.choix_mode)

        self.champ_dossier = QLineEdit(_dossier_par_defaut())
        bouton_dossier = QPushButton("Parcourir…")
        bouton_dossier.clicked.connect(self.choisir_dossier)
        ligne_dossier = QHBoxLayout()
        ligne_dossier.addWidget(self.champ_dossier)
        ligne_dossier.addWidget(bouton_dossier)
        self.ligne_dossier = ligne_dossier
        formulaire.addRow("Dossier :", ligne_dossier)

        disposition.addLayout(formulaire)

        self.journal = QTextEdit()
        self.journal.setReadOnly(True)
        self.journal.setMinimumHeight(150)
        disposition.addWidget(self.journal)

        self.jauge = QProgressBar()
        self.jauge.setRange(0, 100)
        self.jauge.setValue(0)
        disposition.addWidget(self.jauge)

        ligne_boutons = QHBoxLayout()
        self.bouton_analyser = QPushButton("Analyser une autre emprise")
        self.bouton_analyser.clicked.connect(self.analyser)
        self.bouton_charger = QPushButton("Charger les dalles")
        self.bouton_charger.setEnabled(False)
        self.bouton_charger.clicked.connect(self.charger)
        ligne_boutons.addWidget(self.bouton_analyser)
        ligne_boutons.addStretch(1)
        ligne_boutons.addWidget(self.bouton_charger)
        disposition.addLayout(ligne_boutons)

        # Crédit discret : même technologie, même auteur. Le lien porte le sens.
        credit = QLabel(
            'Mêmes dalles LiDAR HD que le '
            '<a href="%s">simulateur de toiture</a>, qui mesure surface, '
            "pente et orientation d'un toit à partir de ces nuages de points."
            % SITE_AUTEUR
        )
        credit.setWordWrap(True)
        credit.setOpenExternalLinks(True)
        credit.setStyleSheet("color: palette(mid); font-size: 11px;")
        disposition.addWidget(credit)

        self.choix_mode.currentIndexChanged.connect(self._maj_mode)

    # -- état de l'interface ------------------------------------------------

    def _maj_mode(self):
        telechargement = self.choix_mode.currentIndex() == 0
        self.ligne_dossier.setEnabled(telechargement)

    def choisir_dossier(self):
        choisi = QFileDialog.getExistingDirectory(
            self, "Dossier de téléchargement des dalles", self.champ_dossier.text()
        )
        if choisi:
            self.champ_dossier.setText(choisi)

    def ecrire(self, texte):
        self.journal.append(texte)

    # -- emprise ------------------------------------------------------------

    def emprise_en_wgs84(self):
        """Emprise de référence : la sélection de la couche active, sinon la carte."""
        projet = QgsProject.instance()
        canvas = self.iface.mapCanvas()

        rectangle = None
        source = "étendue de la carte"
        couche = self.iface.activeLayer()
        if couche is not None and hasattr(couche, "selectedFeatures"):
            entites = couche.selectedFeatures()
            if entites:
                rectangle = QgsRectangle()
                rectangle.setMinimal()
                for entite in entites:
                    geometrie = entite.geometry()
                    if geometrie is not None and not geometrie.isEmpty():
                        rectangle.combineExtentWith(geometrie.boundingBox())
                if rectangle.isEmpty():
                    rectangle = None
                else:
                    source = "sélection dans « %s »" % couche.name()

        if rectangle is None:
            rectangle = QgsRectangle(canvas.extent())

        cible = QgsCoordinateReferenceSystem("EPSG:4326")
        if projet.crs() != cible:
            transformation = QgsCoordinateTransform(projet.crs(), cible, projet)
            rectangle = transformation.transformBoundingBox(rectangle)

        return (
            rectangle.xMinimum(),
            rectangle.yMinimum(),
            rectangle.xMaximum(),
            rectangle.yMaximum(),
            source,
        )

    # -- analyse ------------------------------------------------------------

    def analyser(self):
        self.dalles = []
        self.bouton_charger.setEnabled(False)
        self.journal.clear()
        self.jauge.setValue(0)

        bbox = self.emprise_en_wgs84()
        self.bbox = bbox[:4]
        self.etiquette_emprise.setText(
            "Emprise analysée : %s — %.0f m × %.0f m environ."
            % (
                bbox[4],
                abs(bbox[2] - bbox[0]) * 111320 * 0.7,
                abs(bbox[3] - bbox[1]) * 110540,
            )
        )

        tache = TacheAnalyse(self.bbox)
        tache.taskCompleted.connect(lambda: self.analyse_terminee(tache))
        tache.taskTerminated.connect(lambda: self.analyse_terminee(tache))
        self.taches.append(tache)
        QgsProject.instance().taskManager().addTask(tache)

        self.bouton_analyser.setEnabled(False)
        self.ecrire("Interrogation du catalogue LiDAR HD de l'IGN…")

    def analyse_terminee(self, tache):
        self.bouton_analyser.setEnabled(True)

        if tache.erreur:
            self.ecrire("<b>Échec :</b> %s" % tache.erreur)
            return
        if not tache.dalles:
            self.ecrire(
                "Aucune dalle LiDAR HD sur cette emprise. "
                "Le programme national ne couvre pas encore toute la France, "
                "et certaines zones restent à acquérir."
            )
            return

        self.dalles = tache.dalles
        total = sum(dalle.get("octets") or 0 for dalle in self.dalles)
        self.ecrire("<b>%d dalle(s) LiDAR HD</b> — %s au total :" % (len(self.dalles), _octets_en_texte(total)))
        for dalle in self.dalles:
            self.ecrire(
                "  • %s — %s points — %s"
                % (dalle["nom"], format(dalle["points"], ",d").replace(",", " "), _octets_en_texte(dalle["octets"]))
            )
        if tache.tronquee:
            self.ecrire(
                "<b>Attention :</b> l'emprise dépasse %d dalles ; seules les %d premières "
                "sont proposées. Réduisez l'étendue pour un jeu complet." % (MAX_DALLES, MAX_DALLES)
            )
        if total > 3 * 1024 ** 3:
            self.ecrire(
                "<b>Attention :</b> %s à télécharger. Préférez la lecture à distance."
                % _octets_en_texte(total)
            )
        self.ecrire("Prêt.")
        self.bouton_charger.setEnabled(True)

    # -- chargement ---------------------------------------------------------

    def charger(self):
        if not self.dalles:
            return

        distance = self.choix_mode.currentIndex() == 1
        if distance:
            self.ajouter(distance=True)
            return

        dossier = self.champ_dossier.text().strip() or _dossier_par_defaut()
        self.champ_dossier.setText(dossier)
        self.bouton_charger.setEnabled(False)
        self.bouton_analyser.setEnabled(False)

        tache = TacheTelechargement(self.dalles, dossier)
        tache.progressChanged.connect(self.jauge.setValue)
        tache.taskCompleted.connect(lambda: self.telechargement_termine(tache))
        tache.taskTerminated.connect(lambda: self.telechargement_termine(tache))
        self.taches.append(tache)
        QgsProject.instance().taskManager().addTask(tache)
        self.ecrire("Téléchargement dans %s…" % dossier)

    def telechargement_termine(self, tache):
        self.bouton_analyser.setEnabled(True)
        self.bouton_charger.setEnabled(True)

        if tache.erreur:
            self.ecrire("<b>Échec du téléchargement :</b> %s" % tache.erreur)
            return
        if not tache.chemins:
            self.ecrire("Téléchargement interrompu.")
            return

        self.jauge.setValue(100)
        self.ajouter(chemins=tache.chemins)

    def ajouter(self, chemins=None, distance=False):
        """Ajoute les couches de nuage de points au projet."""
        ajoutees = 0
        echecs = []
        emprise = QgsRectangle()
        emprise.setMinimal()
        for dalle in self.dalles:
            if distance:
                uri = dalle["url"]
            else:
                if chemins is None:
                    continue
                uri = None
                for chemin in chemins:
                    if os.path.basename(chemin) == dalle["nom"] + ".copc.laz":
                        uri = chemin.replace("\\", "/")
                        break
                if uri is None:
                    continue

            couche = QgsPointCloudLayer(uri, "LiDAR HD %s" % dalle["nom"], "pointcloud")
            if couche.isValid() and QgsProject.instance().addMapLayer(couche):
                ajoutees += 1
                emprise.combineExtentWith(couche.extent())
            else:
                echecs.append(dalle["nom"])

        canvas = self.iface.mapCanvas()
        if ajoutees and canvas is not None and not emprise.isEmpty():
            canvas.setExtent(emprise)
            canvas.refresh()

        self.ecrire("<b>%d couche(s) ajoutée(s)</b> au projet." % ajoutees)
        if echecs:
            self.ecrire(
                "Non ajoutées : %s. Un nuage de points demande QGIS 3.32 ou plus récent."
                % ", ".join(echecs)
            )


# --- Cycle de vie du plugin --------------------------------------------------


class PluginLidarHD:
    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.fenetre = None

    def initGui(self):  # noqa: N802 (nom imposé par QGIS)
        icone = os.path.join(os.path.dirname(__file__), "icon.png")
        self.action = QAction(QIcon(icone), "Dalles LiDAR HD par emprise", self.iface.mainWindow())
        self.action.setToolTip(
            "Télécharger et afficher les dalles LiDAR HD de l'IGN recouvrant l'étendue de la carte"
        )
        self.action.triggered.connect(self.executer)
        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToMenu(NOM_MENU, self.action)

    def unload(self):
        if self.fenetre is not None:
            self.fenetre.close()
            self.fenetre = None
        if self.action is not None:
            self.iface.removePluginMenu(NOM_MENU, self.action)
            self.iface.removeToolBarIcon(self.action)
            self.action = None

    def executer(self):
        if self.fenetre is None:
            self.fenetre = FenetreLidarHD(self.iface)
        self.fenetre.show()
        self.fenetre.raise_()
        self.fenetre.activateWindow()
        self.fenetre.analyser()
