"""Tests du module Reporting."""
from datetime import date, time, timedelta

from django.test import TestCase
from django.utils import timezone

from apps.attendance.models import Anomaly, TimeEntry
from apps.core.models import User
from apps.employees.models import Employee
from apps.organization.models import Agence, Bureau, Direction, Mutuelle

from .services import (
    get_anomalies_for_user, get_directeur_directions, get_directeur_employees,
    get_global_overview,
)


class DirecteurScopeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.mut = Mutuelle.objects.create(code='M', name='Mut')
        cls.ag = Agence.objects.create(mutuelle=cls.mut, code='A', name='Ag')
        cls.bureau = Bureau.objects.create(agence=cls.ag, code='B', name='Bureau')
        cls.dir_com = Direction.objects.create(code='DIR-COM', name='Commerciale')
        cls.dir_cre = Direction.objects.create(code='DIR-CRE', name='Crédit')

        # Le directeur commercial
        u_dir = User.objects.create_user(
            matricule='D1', email='d@a.sn', password='passw0rd',
            first_name='Dir', last_name='Com',
        )
        u_dir.roles = ['AGENT', 'DIRECTEUR']
        u_dir.save()
        cls.emp_dir = Employee.objects.create(
            user=u_dir, hire_date=date(2020, 1, 1),
            bureau=cls.bureau, direction=cls.dir_com, position='Directeur',
        )
        cls.dir_com.directeur = cls.emp_dir
        cls.dir_com.save()

        # 2 employés dans la direction commerciale
        for i in range(2):
            u = User.objects.create_user(
                matricule=f'C{i}', email=f'c{i}@a.sn', password='passw0rd',
            )
            u.roles = ['AGENT']
            u.save()
            Employee.objects.create(
                user=u, hire_date=date(2020, 1, 1),
                bureau=cls.bureau, direction=cls.dir_com, position='Caissier',
            )

        # 1 employé dans Crédit (pas dans le scope du directeur com)
        u_cre = User.objects.create_user(
            matricule='CR1', email='cr@a.sn', password='passw0rd',
        )
        u_cre.roles = ['AGENT']
        u_cre.save()
        Employee.objects.create(
            user=u_cre, hire_date=date(2020, 1, 1),
            bureau=cls.bureau, direction=cls.dir_cre, position='Chargé crédit',
        )

    def test_directeur_sees_only_his_direction(self):
        directions = get_directeur_directions(self.emp_dir.user)
        self.assertEqual(directions.count(), 1)
        self.assertEqual(directions.first(), self.dir_com)

    def test_directeur_employees_count(self):
        """3 employés dans Commerciale (le directeur lui-même + 2 caissiers)."""
        employees = get_directeur_employees(self.emp_dir.user)
        self.assertEqual(employees.count(), 3)

    def test_role_directeur_without_nomination_fallbacks_to_own_direction(self):
        """Un utilisateur avec le rôle DIRECTEUR mais non nommé directement
        sur une direction voit quand même sa propre direction d'affectation."""
        u = User.objects.create_user(
            matricule='DSOLO', email='dsolo@a.sn', password='passw0rd',
        )
        u.roles = ['AGENT', 'DIRECTEUR']
        u.save()
        Employee.objects.create(
            user=u, hire_date=date(2020, 1, 1),
            bureau=self.bureau, direction=self.dir_cre, position='Manager',
        )
        directions = get_directeur_directions(u)
        self.assertEqual(directions.count(), 1)
        self.assertEqual(directions.first(), self.dir_cre)


class RHGlobalStatsTests(TestCase):
    def test_global_overview_returns_structure(self):
        # Création minimale pour ne pas crasher
        mut = Mutuelle.objects.create(code='M', name='M')
        ag = Agence.objects.create(mutuelle=mut, code='A', name='A')
        bureau = Bureau.objects.create(agence=ag, code='B', name='B')
        dir_ = Direction.objects.create(code='D', name='D')
        u = User.objects.create_user(matricule='X', email='x@x.sn', password='passw0rd')
        Employee.objects.create(
            user=u, hire_date=date(2020, 1, 1),
            bureau=bureau, direction=dir_, position='T',
        )
        ov = get_global_overview()
        self.assertEqual(ov['total_employees'], 1)
        self.assertIn('attendance_rate_today', ov)


class AnomalyScopeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.mut = Mutuelle.objects.create(code='M', name='M')
        cls.ag = Agence.objects.create(mutuelle=cls.mut, code='A', name='A')
        cls.bureau = Bureau.objects.create(agence=cls.ag, code='B', name='B')
        cls.dir_com = Direction.objects.create(code='DC', name='Com')
        cls.dir_cre = Direction.objects.create(code='DR', name='Cre')

        # Directeur de Com
        u_dir = User.objects.create_user(matricule='D', email='d@a.sn', password='passw0rd')
        u_dir.roles = ['AGENT', 'DIRECTEUR']; u_dir.save()
        cls.emp_dir = Employee.objects.create(
            user=u_dir, hire_date=date(2020, 1, 1),
            bureau=cls.bureau, direction=cls.dir_com, position='D',
        )
        cls.dir_com.directeur = cls.emp_dir; cls.dir_com.save()

        # Employé dans Cre
        u2 = User.objects.create_user(matricule='X', email='x@a.sn', password='passw0rd')
        u2.roles = ['AGENT']; u2.save()
        emp2 = Employee.objects.create(
            user=u2, hire_date=date(2020, 1, 1),
            bureau=cls.bureau, direction=cls.dir_cre, position='X',
        )
        # Une anomalie sur ce TimeEntry (hors scope du directeur Com)
        entry = TimeEntry.objects.create(employee=emp2, work_date=timezone.localdate())
        Anomaly.objects.create(
            time_entry=entry,
            anomaly_type=Anomaly.TYPE_LATE,
            severity=Anomaly.SEVERITY_WARNING,
            description='Retard test',
        )

    def test_directeur_does_not_see_other_directions_anomalies(self):
        anos = get_anomalies_for_user(self.emp_dir.user, only_pending=False)
        self.assertEqual(anos.count(), 0)

    def test_rh_sees_all_anomalies(self):
        rh = User.objects.create_user(matricule='RH', email='rh@a.sn', password='passw0rd')
        rh.roles = ['RH']; rh.save()
        anos = get_anomalies_for_user(rh, only_pending=False)
        self.assertEqual(anos.count(), 1)
