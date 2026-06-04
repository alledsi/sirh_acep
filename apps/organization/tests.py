"""Tests du module Organisation.

Focus sur la résolution IP → Bureau, qui est le mécanisme critique du pointage.
"""
from django.core.exceptions import ValidationError
from django.test import TestCase

from .models import Agence, Bureau, Direction, IPBureauMapping, Mutuelle
from .services import resolve_bureau_from_ip


class IPResolutionTests(TestCase):
    """Vérifie que la résolution IP → Bureau fonctionne correctement, y
    compris quand un bureau possède plusieurs plages IP."""

    @classmethod
    def setUpTestData(cls):
        cls.mut = Mutuelle.objects.create(code='MUT-DKR', name='Mutuelle Dakar')
        cls.ag = Agence.objects.create(mutuelle=cls.mut, code='AG-VDN', name='Agence VDN')
        cls.bureau_vdn = Bureau.objects.create(agence=cls.ag, code='BUR-VDN', name='Bureau VDN')
        cls.bureau_yoff = Bureau.objects.create(agence=cls.ag, code='BUR-YOFF', name='Bureau Yoff')
        # Le bureau VDN a DEUX plages IP différentes (cas réel demandé par le client)
        IPBureauMapping.objects.create(bureau=cls.bureau_vdn, ip_pattern='192.168.7.0/24')
        IPBureauMapping.objects.create(bureau=cls.bureau_vdn, ip_pattern='192.168.8.0/24')
        IPBureauMapping.objects.create(bureau=cls.bureau_yoff, ip_pattern='192.168.9.0/24')

    def test_resolve_ip_in_first_range(self):
        self.assertEqual(resolve_bureau_from_ip('192.168.7.42'), self.bureau_vdn)

    def test_resolve_ip_in_second_range_same_bureau(self):
        """Un bureau peut avoir plusieurs plages — la 2e plage doit aussi marcher."""
        self.assertEqual(resolve_bureau_from_ip('192.168.8.10'), self.bureau_vdn)

    def test_resolve_ip_other_bureau(self):
        self.assertEqual(resolve_bureau_from_ip('192.168.9.55'), self.bureau_yoff)

    def test_resolve_unknown_ip(self):
        """Une IP non rattachée doit retourner None (→ anomalie UNKNOWN_IP)."""
        self.assertIsNone(resolve_bureau_from_ip('10.0.0.1'))

    def test_resolve_invalid_ip(self):
        self.assertIsNone(resolve_bureau_from_ip('not-an-ip'))

    def test_resolve_empty_ip(self):
        self.assertIsNone(resolve_bureau_from_ip(''))
        self.assertIsNone(resolve_bureau_from_ip(None))

    def test_inactive_mapping_ignored(self):
        """Une plage IP désactivée ne doit plus matcher."""
        IPBureauMapping.objects.filter(bureau=self.bureau_vdn).update(is_active=False)
        self.assertIsNone(resolve_bureau_from_ip('192.168.7.42'))

    def test_inactive_bureau_ignored(self):
        """Un bureau désactivé ne doit plus matcher."""
        self.bureau_vdn.is_active = False
        self.bureau_vdn.save()
        self.assertIsNone(resolve_bureau_from_ip('192.168.7.42'))

    def test_single_ip_pattern(self):
        """Une IP unique (sans /xx) doit aussi fonctionner."""
        bureau_test = Bureau.objects.create(agence=self.ag, code='BUR-TEST', name='Bureau test')
        IPBureauMapping.objects.create(bureau=bureau_test, ip_pattern='10.5.5.5')
        self.assertEqual(resolve_bureau_from_ip('10.5.5.5'), bureau_test)
        self.assertIsNone(resolve_bureau_from_ip('10.5.5.6'))


class IPBureauMappingValidationTests(TestCase):
    """Le validateur d'IPBureauMapping doit rejeter les plages mal formées."""

    @classmethod
    def setUpTestData(cls):
        cls.mut = Mutuelle.objects.create(code='M', name='M')
        cls.ag = Agence.objects.create(mutuelle=cls.mut, code='A', name='A')
        cls.bureau = Bureau.objects.create(agence=cls.ag, code='B', name='B')

    def test_valid_cidr(self):
        mapping = IPBureauMapping(bureau=self.bureau, ip_pattern='192.168.1.0/24')
        mapping.full_clean()   # ne lève pas

    def test_valid_single_ip(self):
        mapping = IPBureauMapping(bureau=self.bureau, ip_pattern='192.168.1.42')
        mapping.full_clean()

    def test_invalid_pattern_raises(self):
        mapping = IPBureauMapping(bureau=self.bureau, ip_pattern='not-an-ip')
        with self.assertRaises(ValidationError):
            mapping.full_clean()


class ModelStringTests(TestCase):
    """Vérifications basiques des __str__ et propriétés calculées."""

    def test_bureau_mutuelle_property(self):
        mut = Mutuelle.objects.create(code='M1', name='Mutuelle 1')
        ag = Agence.objects.create(mutuelle=mut, code='A1', name='Agence 1')
        bureau = Bureau.objects.create(agence=ag, code='B1', name='Bureau 1')
        self.assertEqual(bureau.mutuelle, mut)

    def test_bureau_ip_patterns(self):
        mut = Mutuelle.objects.create(code='M2', name='M2')
        ag = Agence.objects.create(mutuelle=mut, code='A2', name='A2')
        bureau = Bureau.objects.create(agence=ag, code='B2', name='B2')
        IPBureauMapping.objects.create(bureau=bureau, ip_pattern='10.0.0.0/24')
        IPBureauMapping.objects.create(bureau=bureau, ip_pattern='10.0.1.0/24', is_active=False)
        # Une seule plage active
        self.assertEqual(bureau.ip_patterns, ['10.0.0.0/24'])
