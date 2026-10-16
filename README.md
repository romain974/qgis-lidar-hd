# LiDAR HD — dalles par emprise

**Un plugin QGIS qui part de l'étendue de la carte et affiche les dalles LiDAR HD de l'IGN.**

Vous tracez une emprise, ou vous utilisez la vue courante. Le plugin interroge le catalogue
national LiDAR HD, liste les dalles de nuage de points qui la recouvrent, puis les affiche —
soit en les téléchargeant, soit en les lisant à distance par requêtes HTTP Range, sans
télécharger le moindre gigaoctet.

Données : **LiDAR HD © IGN**, open data (licence Etalab 2.0). Aucune clé d'API, aucun compte,
aucun serveur intermédiaire.

---

## Ce que fait le plugin

1. Il lit l'**emprise** : l'étendue affichée dans QGIS, ou l'emprise de la sélection de la
   couche active si vous en avez une.
2. Il interroge le **WFS de la Géoplateforme** (`IGNF_LIDAR-HD_METADONNEE:metadata`) pour
   connaître les dalles de 1 km × 1 km qui intersectent cette emprise.
3. Il vous annonce ce qu'il a trouvé : nombre de dalles, nombre de points, poids total.
4. Il **affiche** ces dalles comme couches de nuage de points, en téléchargement ou en
   lecture à distance.

| | |
| --- | --- |
| Format des dalles | `.copc.laz` (COPC), LAS 1.4 compressé, ~10 points/m² |
| Poids d'une dalle | 150 à 250 Mo pour 1 km² |
| Classification | ASPRS — sol 2, végétation 3/4/5, bâtiment 6, eau 9 |
| Couverture | France métropolitaine et DROM, au fil des campagnes d'acquisition |

## Pourquoi deux modes

Le format COPC est un octree feuilleté : chaque nœud est un petit bloc compressé, et un
serveur qui gère les requêtes `Range` peut vous livrer uniquement les blocs utiles. Le mode
**lecture à distance** s'appuie dessus : vous affichez une maison en récupérant quelques
centaines de kilooctets, au lieu des 200 Mo de la dalle entière.

Le mode **téléchargement** fait ce que son nom indique : il écrit les `.copc.laz` dans un
dossier, une fois pour toutes. À préférer si vous travaillez hors connexion ou si vous
enchaînez les ouvertures. Le plugin saute les fichiers déjà présents et complets.

## Installation

### Depuis ce dépôt

```bash
git clone https://github.com/romain974/qgis-lidar-hd.git
```

Copiez le dossier `lidar_hd_emprise` dans le répertoire des extensions de votre profil QGIS :

| Système | Chemin |
| --- | --- |
| Windows | `%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\` |
| Linux | `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/` |
| macOS | `~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/` |

Puis **Extensions → Installer/gérer les extensions → Installées**, et cochez
« LiDAR HD - dalles par emprise ».

### Depuis l'archive

```bash
python empaqueter.py     # → dist/lidar_hd_emprise-<version>.zip (et contrôle les règles du dépôt officiel)
```

Le zip s'installe directement via **Installer depuis un ZIP**.

**QGIS 3.32 ou plus récent est requis** : c'est la version où le fournisseur de nuages de
points sait ouvrir un COPC distant en HTTP Range.

## Dépôt officiel d'extensions

L'archive est prête pour <https://plugins.qgis.org/plugins/add/>. Le script d'empaquetage
rejoue les règles de validation documentées par QGIS :

- un unique dossier racine, au nom composé de lettres ASCII, chiffres, `_` et `-` ;
- `metadata.txt`, `__init__.py` et `LICENSE` présents — la licence sous le nom exact
  `LICENSE`, sans extension, et sans HTML dans les champs de `metadata.txt` ;
- `version`, `repository`, `email`, `category` conformes, icône présente, archive sous 20 Mo.

```bash
python empaqueter.py     # affiche le contenu de l'archive et sort en erreur si une règle casse
```

Une fois en ligne, la fiche du dépôt référence la page d'accueil du projet — c'est le lien
que ce dépôt publie.

## Utilisation

1. Affichez la zone qui vous intéresse, ou sélectionnez une entité d'une couche vecteur.
2. **Extensions → LiDAR HD → Dalles LiDAR HD par emprise** (ou l'icône de la barre d'outils).
3. Le plugin annonce les dalles trouvées et leur poids.
4. Choisissez le mode, puis **Charger les dalles**.

Les couches arrivent dans le projet sous le nom `LiDAR HD LHD_FXX_0943_6540_...`, et la vue
se recadre dessus.

Pour changer l'aspect des points : clic droit sur la couche → **Propriétés → Symbologie**.
QGIS rend les nuages de points en 2D comme en 3D, sans réglage particulier.

## Ce que le plugin ne fait pas

- Il ne colore pas les points par classification et ne produit pas de modèle numérique de
  surface : il affiche le nuage tel que l'IGN le livre.
- Il ne mesure rien. Pour obtenir la **surface, la pente, l'orientation et l'azimut** d'un
  versant à partir de ces mêmes dalles, c'est le métier du
  [simulateur de toiture](https://www.simulateur-toiture.fr), un outil en ligne gratuit qui
  reconstruit le modèle 3D du bâtiment au clic.
- Il ne couvre pas les zones que le programme LiDAR HD n'a pas encore acquises : dans ce cas
  il le dit explicitement au lieu de renvoyer une carte vide.

## Crédits et licence

Le plugin est distribué sous **GPL-2.0-or-later** (voir `LICENSE`), comme l'exige l'écosystème
des extensions QGIS.

Il a été écrit par l'auteur du **[simulateur de toiture](https://www.simulateur-toiture.fr)**,
qui exploite les mêmes dalles LiDAR HD de l'IGN — mêmes fichiers, même format COPC, même
lecture par blocs — pour mesurer la surface et la pente d'une toiture depuis une simple
adresse. C'est le même auteur, la même donnée, et deux usages différents : ici on regarde le
nuage, là-bas on en tire des mètres carrés.

Les données restent la propriété de leurs producteurs :

- **LiDAR HD © IGN** — diffusé en open data sur la [Géoplateforme](https://geoservices.ign.fr/lidarhd)
  sous licence Etalab 2.0. Si vous publiez une carte ou une étude à partir de ces données,
  citez l'IGN.
- Le plugin n'est qu'un client de ces services : il ne produit, ne modifie et ne redistribue
  aucune donnée.

## Ce que le plugin appelle

| Service | Usage |
| --- | --- |
| `data.geopf.fr/wfs/ows` | catalogue des dalles (nom, emprise, nombre de points, URL du nuage) |
| `data.geopf.fr/telechargement/download/LiDARHD-NUALID/...` | le fichier `.copc.laz` lui-même |

Les URLs des nuages de points arrivent donc **depuis une réponse du WFS**, pas de votre saisie.
Avant toute ouverture, chacune est contrôlée : le schéma doit être `http` ou `https`, et le
domaine doit être celui de l'IGN (`data.geopf.fr`). Un `file://`, un `ftp://` ou un domaine
tiers est refusé, rien n'est écrit, et l'erreur est affichée telle quelle. C'est le
signalement Bandit `B310` qui a fait remonter ce point — la vérification est en place depuis
la version 1.0.1.

## Développement

```bash
python tests/test_lidarhd.py            # 11 tests hors ligne (réseau simulé, serveur local)
python tests/test_plugin_hors_qgis.py   # import du plugin et logique, sans QGIS installé
python tests/verifier_services_ign.py    # vérification en direct des services de l'IGN
```

`verifier_services_ign.py` interroge réellement la Géoplateforme pour une emprise d'Annecy :
il contrôle que le catalogue répond, que la dalle annoncée accepte les requêtes `Range`
(HTTP 206), que son en-tête est un LAS 1.4 compressé dont la première VLR est bien `copc`, et
que le nombre de points annoncé par le catalogue correspond à celui de l'en-tête.

```
lidar_hd_emprise/
├── __init__.py        # classFactory : point d'entrée QGIS
├── plugin.py          # interface, tâches QgsTask, ajout des couches
├── lidarhd.py         # requêtes IGN et téléchargement (aucune dépendance QGIS)
├── metadata.txt       # fiche de l'extension
└── icon.png
```

`tests/test_plugin_hors_qgis.py` accepte `PLUGIN_DIR` : pointez-le sur le dossier extrait
de l'archive pour tester l'artefact publié plutôt que les sources.

```bash
PLUGIN_DIR=.../lidar_hd_emprise python tests/test_plugin_hors_qgis.py
```

## English summary

A QGIS plugin that turns the current map extent (or the selection of the active layer) into
IGN LiDAR HD point-cloud tiles: it queries the national LiDAR HD catalogue on the
Géoplateforme, lists the 1 km × 1 km `.copc.laz` tiles covering the extent, and adds them as
point-cloud layers. Two modes: download the tiles, or stream only the COPC blocks needed for
the current zoom through HTTP Range requests. Requires QGIS 3.32 or newer. Data: LiDAR HD
© IGN, open data (Etalab 2.0). Written by the author of the
[simulateur de toiture](https://www.simulateur-toiture.fr), an online tool that derives roof
area, pitch and orientation from the same LiDAR HD tiles.

