# Generated migration to add the pode_arquivar permission to the Processo model.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('processos', '0060_add_registroacessoarquivo'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='processo',
            options={'permissions': [
                ('acesso_backoffice', 'Pode acessar as telas gerais do sistema financeiro'),
                ('pode_operar_contas_pagar', 'Pode empenhar, triar notas e fazer conferência'),
                ('pode_atestar_liquidacao', 'Pode atestar notas fiscais (Fiscal do Contrato)'),
                ('pode_autorizar_pagamento', 'Pode autorizar pagamentos (Ordenador)'),
                ('pode_contabilizar', 'Pode registrar a contabilização (Contador)'),
                ('pode_auditar_conselho', 'Pode aprovar no Conselho Fiscal'),
                ('pode_arquivar', 'Pode realizar o arquivamento definitivo de processos'),
            ]},
        ),
    ]
