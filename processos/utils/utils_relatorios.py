"""Helpers para exportação tabular de relatórios em CSV."""

import csv
from django.http import HttpResponse


def gerar_csv_relatorio(queryset, tipo_relatorio):
    """Gera um ``HttpResponse`` CSV para o tipo de relatório solicitado."""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="relatorio_{tipo_relatorio}.csv"'
    response.write('\ufeff'.encode('utf8'))  # BOM for Excel UTF-8 compatibility
    writer = csv.writer(response, delimiter=';')

    # Mapeamento: 'tipo': (['Cabeçalhos'], lambda obj: ['Valores'])
    mapa_relatorios = {
        'processos': (
            ['ID', 'Empenho', 'Credor', 'Valor Bruto', 'Valor Líquido', 'Status', 'Data Pagamento'],
            lambda p: [p.id, p.n_nota_empenho, p.credor.nome if p.credor else '', p.valor_bruto, p.valor_liquido, p.status.status_choice if p.status else '', p.data_pagamento]
        ),
        'diarias': (
            ['ID', 'Beneficiário', 'Proponente', 'Período', 'Destino', 'Valor', 'Status'],
            lambda d: [d.id, d.beneficiario.nome if d.beneficiario else '', d.proponente.get_full_name() if d.proponente else '', f"{d.data_saida} a {d.data_retorno}", d.cidade_destino, d.valor_total, d.status.status_choice if d.status else '']
        ),
        'impostos': (
            ['ID', 'NF', 'Processo Pai', 'Código', 'Valor Retido', 'Competência', 'Processo Pagamento'],
            lambda i: [i.id, i.nota_fiscal.numero_nota_fiscal, i.nota_fiscal.processo.id, i.codigo.codigo if i.codigo else '', i.valor, i.competencia, i.processo_pagamento.id if i.processo_pagamento else 'Pendente']
        ),
    }

    cabecalhos, extrator = mapa_relatorios.get(tipo_relatorio, (['Erro'], lambda x: ['Tipo não configurado']))
    writer.writerow(cabecalhos)

    for obj in queryset:
        writer.writerow(extrator(obj))

    return response
