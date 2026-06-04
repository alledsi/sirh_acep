"""Tests du module Attendance."""
from datetime import date, datetime, time, timedelta
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import RequestFactory, TestCase
from django.utils import timezone

from apps.core.models import User
from apps.employees.models import Employee
from apps.organization.models import Agence, Bureau, Direction, IPBureauMapping, Mutuelle

from .models import Anomaly, TimeEntry
from .services import (
    ACTION_ARRIVAL, ACTION_BREAK_END, ACTION_BREAK_START, ACTION_DEPARTURE,
    detect_anomalies, record_punch,
)


def _build_request(ip='192.168.7.42'):
    factory = RequestFactory()
    req = factory.post('/pointer/arrivee/')
    req.META['REMOTE_ADDR'] = ip
    return req


class PointageScenarioTests(TestCase):
    """Scénario complet : arrivée → pause → fin pause → départ."""

    @classmethod
    def setUpTestData(cls):
        cls.mut = Mutuelle.objects.create(code='M', name='Mut')
        cls.ag = Agence.objects.create(mutuelle=cls.mut, code='A', name='Ag')
        cls.bureau_vdn = Bureau.objects.create(agence=cls.ag, code='B-VDN', name='Bureau VDN')
        cls.bureau_yoff = Bureau.objects.create(agence=cls.ag, code='B-YOFF', name='Bureau Yoff')
        IPBureauMapping.objects.create(bureau=cls.bureau_vdn, ip_pattern='192.168.7.0/24')
        IPBureauMapping.objects.create(bureau=cls.bureau_yoff, ip_pattern='192.168.9.0/24')
        cls.dir = Direction.objects.create(code='D', name='Direction')
        cls.user = User.objects.create_user(
            matricule='1042', email='a@a.sn', password='passw0rd1234',
            first_name='A', last_name='N',
        )
        cls.emp = Employee.objects.create(
            user=cls.user, hire_date=date(2020, 1, 1),
            bureau=cls.bureau_vdn, direction=cls.dir, position='Test',
        )

    def test_full_punch_flow(self):
        """Un cycle complet de pointage doit fonctionner."""
        record_punch(ACTION_ARRIVAL, self.emp, _build_request('192.168.7.42'))
        entry = TimeEntry.objects.get(employee=self.emp)
        self.assertIsNotNone(entry.arrival_time)
        self.assertEqual(entry.arrival_bureau, self.bureau_vdn)

        record_punch(ACTION_BREAK_START, self.emp, _build_request('192.168.7.42'))
        record_punch(ACTION_BREAK_END, self.emp, _build_request('192.168.7.42'))
        record_punch(ACTION_DEPARTURE, self.emp, _build_request('192.168.7.42'))
        entry.refresh_from_db()
        self.assertIsNotNone(entry.departure_time)

    def test_cannot_arrive_twice(self):
        record_punch(ACTION_ARRIVAL, self.emp, _build_request())
        with self.assertRaises(ValidationError):
            record_punch(ACTION_ARRIVAL, self.emp, _build_request())

    def test_cannot_depart_during_break(self):
        record_punch(ACTION_ARRIVAL, self.emp, _build_request())
        record_punch(ACTION_BREAK_START, self.emp, _build_request())
        with self.assertRaises(ValidationError):
            record_punch(ACTION_DEPARTURE, self.emp, _build_request())

    def test_cannot_depart_before_arrival(self):
        with self.assertRaises(ValidationError):
            record_punch(ACTION_DEPARTURE, self.emp, _build_request())


class AnomalyDetectionTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.mut = Mutuelle.objects.create(code='M', name='Mut')
        cls.ag = Agence.objects.create(mutuelle=cls.mut, code='A', name='Ag')
        cls.bureau_vdn = Bureau.objects.create(agence=cls.ag, code='B-VDN', name='Bureau VDN')
        cls.bureau_yoff = Bureau.objects.create(agence=cls.ag, code='B-YOFF', name='Bureau Yoff')
        IPBureauMapping.objects.create(bureau=cls.bureau_vdn, ip_pattern='192.168.7.0/24')
        IPBureauMapping.objects.create(bureau=cls.bureau_yoff, ip_pattern='192.168.9.0/24')
        cls.dir = Direction.objects.create(code='D', name='Direction')
        cls.user = User.objects.create_user(
            matricule='1042', email='a@a.sn', password='passw0rd1234',
            first_name='A', last_name='N',
        )
        cls.emp = Employee.objects.create(
            user=cls.user, hire_date=date(2020, 1, 1),
            bureau=cls.bureau_vdn, direction=cls.dir, position='Test',
        )

    def test_incoherence_bureau_detected(self):
        """L'employé pointe depuis Yoff alors qu'il est affecté à VDN."""
        record_punch(ACTION_ARRIVAL, self.emp, _build_request('192.168.9.55'))
        ano = Anomaly.objects.filter(anomaly_type=Anomaly.TYPE_INCOHERENCE_BUREAU)
        self.assertEqual(ano.count(), 1)

    def test_unknown_ip_detected(self):
        """Une IP non rattachée doit déclencher UNKNOWN_IP."""
        record_punch(ACTION_ARRIVAL, self.emp, _build_request('10.0.0.99'))
        self.assertEqual(
            Anomaly.objects.filter(anomaly_type=Anomaly.TYPE_UNKNOWN_IP).count(),
            1,
        )

    def test_no_anomaly_for_coherent_arrival_on_time(self):
        """Arrivée tôt + bonne IP = aucune anomalie."""
        # On force une arrivée à 07:30 (avant 08:05)
        now = timezone.now()
        entry = TimeEntry.objects.create(
            employee=self.emp,
            work_date=now.date(),
            arrival_time=now.replace(hour=7, minute=30, second=0, microsecond=0),
            arrival_bureau=self.bureau_vdn,
            arrival_ip='192.168.7.42',
        )
        anos = detect_anomalies(entry)
        types = [a.anomaly_type for a in anos]
        self.assertNotIn(Anomaly.TYPE_LATE, types)
        self.assertNotIn(Anomaly.TYPE_UNKNOWN_IP, types)
        self.assertNotIn(Anomaly.TYPE_INCOHERENCE_BUREAU, types)


class TimeEntryPropertiesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.mut = Mutuelle.objects.create(code='M', name='Mut')
        cls.ag = Agence.objects.create(mutuelle=cls.mut, code='A', name='Ag')
        cls.bureau = Bureau.objects.create(agence=cls.ag, code='B', name='Bureau')
        cls.dir = Direction.objects.create(code='D', name='Direction')
        cls.user = User.objects.create_user(matricule='X', email='x@x.sn', password='passw0rd1234')
        cls.emp = Employee.objects.create(
            user=cls.user, hire_date=date(2020, 1, 1),
            bureau=cls.bureau, direction=cls.dir, position='T',
        )

    def test_worked_duration_with_break(self):
        now = timezone.now().replace(hour=8, minute=0, second=0, microsecond=0)
        entry = TimeEntry.objects.create(
            employee=self.emp, work_date=now.date(),
            arrival_time=now,
            break_start=now.replace(hour=12, minute=30),
            break_end=now.replace(hour=13, minute=30),
            departure_time=now.replace(hour=17, minute=0),
        )
        # 9h moins 1h pause = 8h
        self.assertEqual(entry.worked_duration, timedelta(hours=8))
