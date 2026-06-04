"""Services du module Organisation.

`resolve_bureau_from_ip(ip)` est le service central : à partir d'une adresse IP
source (lue depuis une requête HTTP), il retourne le Bureau correspondant en
parcourant les IPBureauMapping actifs.

Ce service sera utilisé par le module Attendance (Sprint 3) à chaque action de
pointage pour déterminer le bureau de connexion automatiquement.
"""
from ipaddress import ip_address, ip_network

from .models import Bureau, IPBureauMapping


def resolve_bureau_from_ip(ip: str) -> Bureau | None:
    """Retourne le Bureau correspondant à l'IP source, ou None si inconnue.

    Parcourt les IPBureauMapping actifs et teste si l'IP est dans la plage.
    Supporte les CIDR (192.168.1.0/24) et les IPs uniques (192.168.1.42).

    Args:
        ip: Adresse IP source (str), récupérée via apps.core.services.get_client_ip().

    Returns:
        Bureau si une plage matche, None sinon (= anomalie UNKNOWN_IP côté Attendance).
    """
    if not ip:
        return None

    try:
        addr = ip_address(ip)
    except ValueError:
        return None

    mappings = IPBureauMapping.objects.filter(
        is_active=True,
        bureau__is_active=True,
    ).select_related('bureau__agence__mutuelle')

    for mapping in mappings:
        try:
            network = ip_network(mapping.ip_pattern, strict=False)
            if addr in network:
                return mapping.bureau
        except ValueError:
            # Plage mal formée — on log et on continue
            continue

    return None
