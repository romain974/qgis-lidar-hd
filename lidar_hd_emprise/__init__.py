# -*- coding: utf-8 -*-
"""Point d'entrée du plugin pour QGIS."""


def classFactory(iface):  # noqa: N802 (nom imposé par QGIS)
    """QGIS appelle cette fonction pour instancier le plugin."""
    from .plugin import PluginLidarHD

    return PluginLidarHD(iface)
