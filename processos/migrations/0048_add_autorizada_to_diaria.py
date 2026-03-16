from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('processos', '0047_add_proponente_to_diaria'),
    ]

    operations = [
        migrations.AddField(
            model_name='diaria',
            name='autorizada',
            field=models.BooleanField(default=False, verbose_name='Autorizada'),
        ),
    ]
