"""Tests du module Employees."""
from datetime import date

from django.test import TestCase

from apps.core.models import User
from apps.organization.models import Agence, Bureau, Direction, Mutuelle

from .models import Contract, Employee


class EmployeeModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.mut = Mutuelle.objects.create(code='M', name='Mut')
        cls.ag = Agence.objects.create(mutuelle=cls.mut, code='A', name='Ag')
        cls.bureau = Bureau.objects.create(agence=cls.ag, code='B', name='Bureau')
        cls.dir = Direction.objects.create(code='D', name='Direction')
        cls.user = User.objects.create_user(
            matricule='1042', email='a@acep.sn', password='passw0rdsecure',
            first_name='Aïssatou', last_name='Ndiaye',
        )
        cls.emp = Employee.objects.create(
            user=cls.user, hire_date=date(2020, 1, 1),
            bureau=cls.bureau, direction=cls.dir, position='Chargée clientèle',
        )

    def test_str_includes_matricule(self):
        self.assertIn('1042', str(self.emp))

    def test_matricule_property(self):
        self.assertEqual(self.emp.matricule, '1042')

    def test_initials(self):
        self.assertEqual(self.emp.initials, 'AN')

    def test_agence_and_mutuelle_property(self):
        self.assertEqual(self.emp.agence, self.ag)
        self.assertEqual(self.emp.mutuelle, self.mut)

    def test_contract_creation(self):
        c = Contract.objects.create(
            employee=self.emp, contract_type='CDI',
            start_date=date(2020, 1, 1), weekly_hours=40,
        )
        self.assertEqual(self.emp.contracts.count(), 1)
        self.assertIn('CDI', str(c))


class EmployeeFormTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.mut = Mutuelle.objects.create(code='M', name='Mut')
        cls.ag = Agence.objects.create(mutuelle=cls.mut, code='A', name='Ag')
        cls.bureau = Bureau.objects.create(agence=cls.ag, code='B', name='Bureau')
        cls.dir = Direction.objects.create(code='D', name='Direction')

    def test_create_employee_creates_user_and_employee(self):
        """La création d'un employé crée bien le User et l'Employee liés."""
        from .forms import EmployeeCreateForm

        form = EmployeeCreateForm(data={
            'matricule': '0001', 'first_name': 'Test', 'last_name': 'User',
            'email': 'test@acep.sn', 'password': 'MotDePasse10Caracteres!',
            'must_change_password': True, 'roles': ['AGENT'],
            'bureau': self.bureau.pk, 'direction': self.dir.pk,
            'position': 'Caissier', 'hire_date': '2024-01-15',
        })
        self.assertTrue(form.is_valid(), form.errors)
        emp = form.save()
        self.assertEqual(emp.user.matricule, '0001')
        self.assertEqual(emp.user.roles, ['AGENT'])
        self.assertTrue(emp.user.must_change_password)
        self.assertEqual(emp.position, 'Caissier')

    def test_duplicate_matricule_rejected(self):
        User.objects.create_user(matricule='1042', email='x@x.sn', password='AbcDef1234!')
        from .forms import EmployeeCreateForm
        form = EmployeeCreateForm(data={
            'matricule': '1042', 'first_name': 'A', 'last_name': 'B',
            'email': 'b@b.sn', 'password': 'MotDePasse10Cara!',
            'roles': ['AGENT'], 'bureau': self.bureau.pk,
            'direction': self.dir.pk, 'position': 'P', 'hire_date': '2024-01-01',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('matricule', form.errors)
