"""Migration : ajout des champs de régularisation sur TimeEntry +
modèle AbsenceJustification (pièces jointes).
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0001_initial'),
        ('employees', '0002_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Régularisation sur TimeEntry
        migrations.AddField(
            model_name='timeentry',
            name='is_regularized',
            field=models.BooleanField(
                default=False,
                help_text='Coché si la RH a modifié manuellement ce pointage (incident technique, oubli, etc.)',
                verbose_name='Pointage régularisé manuellement',
            ),
        ),
        migrations.AddField(
            model_name='timeentry',
            name='regularization_reason',
            field=models.TextField(
                blank=True,
                help_text='Motif détaillé : incident technique, oubli de pointage, etc.',
                verbose_name='Motif de la régularisation',
            ),
        ),
        migrations.AddField(
            model_name='timeentry',
            name='regularized_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Régularisé le'),
        ),
        migrations.AddField(
            model_name='timeentry',
            name='regularized_by',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='regularizations',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Régularisé par',
            ),
        ),

        # AbsenceJustification
        migrations.CreateModel(
            name='AbsenceJustification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Modifié le')),
                ('is_deleted', models.BooleanField(default=False, verbose_name='Archivé')),
                ('deleted_at', models.DateTimeField(blank=True, null=True, verbose_name='Archivé le')),
                ('absence_date', models.DateField(db_index=True, verbose_name='Date concernée')),
                ('justification_type', models.CharField(
                    choices=[('ABSENCE', 'Absence'), ('LATE', 'Retard'),
                             ('EARLY_DEPARTURE', 'Départ anticipé'), ('OTHER', 'Autre')],
                    default='ABSENCE', max_length=20, verbose_name='Type',
                )),
                ('reason', models.TextField(help_text='Expliquer la raison.', verbose_name='Motif détaillé')),
                ('attachment', models.FileField(
                    blank=True, null=True,
                    help_text='Certificat médical, courrier, etc. (PDF, image)',
                    upload_to='justifications/%Y/%m/',
                    verbose_name='Pièce jointe',
                )),
                ('status', models.CharField(
                    choices=[('PENDING', 'En attente'), ('APPROVED', 'Approuvée'), ('REJECTED', 'Rejetée')],
                    default='PENDING', max_length=20, verbose_name='Statut',
                )),
                ('reviewed_at', models.DateTimeField(blank=True, null=True, verbose_name='Validée le')),
                ('review_note', models.TextField(blank=True, verbose_name='Note du valideur')),
                ('employee', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='justifications',
                    to='employees.employee',
                    verbose_name='Employé',
                )),
                ('reviewed_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='justifications_reviewed',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Validée par',
                )),
            ],
            options={
                'verbose_name': "Justification d'absence",
                'verbose_name_plural': "Justifications d'absence",
                'ordering': ['-absence_date', '-created_at'],
            },
        ),
    ]
