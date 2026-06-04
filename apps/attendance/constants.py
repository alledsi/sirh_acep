"""Constantes de référence pour la détection d'anomalies de pointage.

Ces valeurs sont des défauts en attendant l'implémentation du Sprint 4
(module Planning). Elles seront remplacées par une consultation du planning
de l'employé qui pourra varier dans le temps.
"""
from datetime import time, timedelta

# Heure de référence d'arrivée (au-delà + tolérance = retard)
DEFAULT_ARRIVAL_REFERENCE = time(8, 0)
DEFAULT_ARRIVAL_TOLERANCE = timedelta(minutes=5)

# Durée maximale d'une pause (au-delà = anomalie)
DEFAULT_MAX_BREAK_DURATION = timedelta(hours=1, minutes=30)

# Heure de référence de départ (au-delà sans pointage = absence ou oubli)
DEFAULT_DEPARTURE_REFERENCE = time(17, 0)
