"""Eventos e signals globais (cross-domain) para desacoplamento de negócios."""

import django.dispatch

# Sinal emitido por módulos satélites (Verbas, Suprimentos, etc)
# quando suas entidades sofrem cancelamento e o Processo base precisa ser estornado.
# Argumentos esperados:
# - sender: Classe do modelo remetente (ex: Diaria)
# - instance: A instância cancelada em si
# - processo: Instância do ProcessoFinanceiro vinculado
# - justificativa: str
# - usuario: Instância de User que disparou a ação
# - dados_devolucao: dict com os dados de devolução financeira (se aplicável)
# - tipo_cancelamento_relacional: str opcional para mapeamento no DB
# - kwargs_relacional: dict com kargs para acoplar no CancelamentoProcessual
solicitacao_cancelamento_processo = django.dispatch.Signal()
