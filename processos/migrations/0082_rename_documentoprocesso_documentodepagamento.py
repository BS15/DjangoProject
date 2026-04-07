from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("processos", "0081_documento_orcamentario"),
    ]

    operations = [
        migrations.RenameModel(
            old_name="DocumentoProcesso",
            new_name="DocumentoDePagamento",
        ),
        migrations.RenameModel(
            old_name="HistoricalDocumentoProcesso",
            new_name="HistoricalDocumentoDePagamento",
        ),
    ]
