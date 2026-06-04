"""Tests du module Planning."""
from datetime import date, time

from django.test import TestCase

from apps.core.models import User
from apps.employees.models import Employee
from apps.organization.models import Agence, Bureau, Direction, Mutuelle

from .models import DailySchedule, Planning
from .services import can_punch_on, get_active_planning


class PlanningSingletonTests(TestCase):
    def test_get_active_planning_creates_default(self):
        """Au premier appel, un Planning par défaut est créé avec 7 DailySchedules."""
        self.assertEqual(Planning.objects.count(), 0)
        planning = get_active_planning()
        self.assertEqual(Planning.objects.count(), 1)
        self.assertEqual(planning.schedules.count(), 7)

    def test_default_monday_is_mandatory(self):
        get_active_planning()
        mon = DailySchedule.objects.get(day_of_week=0)
        self.assertEqual(mon.mode, DailySchedule.MODE_MANDATORY)
        self.assertEqual(mon.start_time, time(8, 0))

    def test_default_saturday_is_optional(self):
        get_active_planning()
        sat = DailySchedule.objects.get(day_of_week=5)
        self.assertEqual(sat.mode, DailySchedule.MODE_OPTIONAL)

    def test_default_sunday_not_worked(self):
        get_active_planning()
        sun = DailySchedule.objects.get(day_of_week=6)
        self.assertEqual(sun.mode, DailySchedule.MODE_NOT_WORKED)


class CanPunchOnTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        mut = Mutuelle.objects.create(code='M', name='Mut')
        ag = Agence.objects.create(mutuelle=mut, code='A', name='Ag')
        bureau = Bureau.objects.create(agence=ag, code='B', name='B')
        cls.dir = Direction.objects.create(code='D', name='D')
        u = User.objects.create_user(matricule='1', email='a@a.sn', password='passw0rd')
        cls.emp = Employee.objects.create(
            user=u, hire_date=date(2020, 1, 1),
            bureau=bureau, direction=cls.dir, position='X',
        )
        get_active_planning()

    def test_can_punch_on_monday(self):
        d = date(2026, 4, 27)  # un lundi
        ok, _msg = can_punch_on(self.emp, d)
        self.assertTrue(ok)

    def test_cannot_punch_on_sunday(self):
        d = date(2026, 4, 26)  # un dimanche
        ok, _msg = can_punch_on(self.emp, d)
        self.assertFalse(ok)

    def test_can_punch_on_saturday(self):
        """Samedi optionnel = pointage libre, toujours autorisé."""
        d = date(2026, 5, 2)  # un samedi
        ok, _msg = can_punch_on(self.emp, d)
        self.assertTrue(ok)
