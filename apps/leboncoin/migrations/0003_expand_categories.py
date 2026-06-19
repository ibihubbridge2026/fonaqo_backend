# Generated manually for FONACO roadmap

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('leboncoin', '0002_rename_leboncoin_l_categor_idx_leboncoin_l_categor_53ef1c_idx_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='locallisting',
            name='category',
            field=models.CharField(
                choices=[
                    ('artisan', 'Artisan expert'),
                    ('restaurant', 'Restaurant'),
                    ('shop', 'Commerce'),
                    ('service', 'Service local'),
                    ('leisure', 'Loisir / sortie'),
                    ('gym', 'Salle de sport'),
                    ('museum', 'Musée / culture'),
                    ('other', 'Autre'),
                ],
                default='other',
                max_length=20,
            ),
        ),
    ]
