from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('processos', '0078_contafixa_data_inicio'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='processo',
            options={
                'permissions': [
                    ('acesso_backoffice', 'Pode acessar as telas gerais do sistema financeiro'),
                    ('pode_operar_contas_pagar', 'Pode empenhar, triar notas e fazer conferência'),
                    ('pode_atestar_liquidacao', 'Pode atestar notas fiscais (Fiscal do Contrato)'),
                    ('pode_autorizar_pagamento', 'Pode autorizar pagamentos (Ordenador)'),
                    ('pode_contabilizar', 'Pode registrar a contabilização (Contador)'),
                    ('pode_auditar_conselho', 'Pode aprovar no Conselho Fiscal'),
                    ('pode_arquivar', 'Pode realizar o arquivamento definitivo de processos'),
                    ('pode_visualizar_verbas', 'Pode visualizar painéis e listas de verbas indenizatórias'),
                    ('pode_criar_diarias', 'Pode cadastrar solicitações de diárias'),
                    ('pode_importar_diarias', 'Pode importar diárias em lote'),
                    ('pode_gerenciar_diarias', 'Pode editar diárias e seus documentos'),
                    ('pode_autorizar_diarias', 'Pode autorizar e aprovar diárias'),
                    ('pode_gerenciar_reembolsos', 'Pode cadastrar e editar reembolsos de combustível'),
                    ('pode_gerenciar_jetons', 'Pode cadastrar e editar jetons'),
                    ('pode_gerenciar_auxilios', 'Pode cadastrar e editar auxílios representação'),
                    ('pode_agrupar_verbas', 'Pode agrupar verbas em processos de pagamento'),
                    ('pode_gerenciar_processos_verbas', 'Pode editar processos originados de verbas indenizatórias'),
                    ('pode_sincronizar_diarias_siscac', 'Pode sincronizar/importar diárias via SISCAC'),
                ],
            },
        ),
    ]