"""Migration : ajout du modèle Holiday (jours fériés)."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('planning', '0002_remove_saturday_schedule'),
    ]

    operations = [
        migrations.CreateModel(
            name='Holiday',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Modifié le')),
                ('is_deleted', models.BooleanField(default=False, verbose_name='Archivé')),
                ('deleted_at', models.DateTimeField(blank=True, null=True, verbose_name='Archivé le')),
                ('name', models.CharField(help_text="Ex : Fête de l'Indépendance", max_length=200, verbose_name='Nom')),
                ('date', models.DateField(db_index=True, unique=True, verbose_name='Date')),
                ('description', models.TextField(blank=True, verbose_name='Description')),
                ('is_paid', models.BooleanField(default=True, help_text='Si coché, pas de retenue.', verbose_name='Férié payé')),
                ('is_active', models.BooleanField(default=True, verbose_name='Actif')),
            ],
            options={
                'verbose_name': 'Jour férié',
                'verbose_name_plural': 'Jours fériés',
                'ordering': ['-date'],
            },
        ),
    ]
