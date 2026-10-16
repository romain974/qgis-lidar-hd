# Journal des versions

Toutes les dates sont au format AAAA-MM-JJ. Le format suit
[Keep a Changelog](https://keepachangelog.com/fr/1.1.0/) et le projet respecte
le [versionnage sémantique](https://semver.org/lang/fr/).

## [1.0.1] — 2026-10-16

### Corrigé

- **Sécurité — contrôle des URLs avant ouverture** (signalement Bandit `B310`).
  Les adresses des dalles arrivent dans les réponses du WFS, elles n'étaient pas
  vérifiées. Chacune est désormais contrôlée : schéma `http` ou `https`
  uniquement, et domaine limité à l'hôte des données de l'IGN. Un `file://`, un
  `ftp://` ou un domaine tiers est refusé, rien n'est écrit sur le disque, et
  l'erreur est affichée telle quelle.
- Un seul appel à `urlopen` subsiste dans le module, derrière ce contrôle.

## [1.0.0] — 2026-10-16

### Ajouté

- Recherche des dalles LiDAR HD qui recouvrent l'étendue de la carte, ou la
  sélection de la couche active.
- Deux modes d'affichage : téléchargement des fichiers `.copc.laz` dans un
  dossier, ou lecture à distance par requêtes HTTP Range — seuls les blocs utiles
  au zoom courant sont alors récupérés.
- Tâches `QgsTask` : l'interface ne se bloque pas, le téléchargement est
  interruptible, et les fichiers déjà présents et complets sont sautés.
- Garde-fous : emprise plafonnée à 40 dalles, avertissement au-delà de 3 Go à
  télécharger, message explicite sur les zones non encore couvertes par le
  programme LiDAR HD.
- 30 tests hors ligne et un script de vérification en direct des services de
  l'IGN.

[1.0.1]: https://github.com/romain974/qgis-lidar-hd/releases/tag/v1.0.1
[1.0.0]: https://github.com/romain974/qgis-lidar-hd/releases/tag/v1.0.0
