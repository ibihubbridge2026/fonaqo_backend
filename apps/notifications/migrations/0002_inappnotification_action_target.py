from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='inappnotification',
            name='action',
            field=models.CharField(
                blank=True,
                default='',
                help_text='Type de navigation: mission, chat, wallet, generic',
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name='inappnotification',
            name='target_id',
            field=models.CharField(
                blank=True,
                default='',
                help_text='ID cible (mission, conversation, etc.)',
                max_length=64,
            ),
        ),
    ]
