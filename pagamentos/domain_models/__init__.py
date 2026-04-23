"""Inicialização do pacote de modelos de domínio do fluxo financeiro.

Este módulo expõe os principais modelos de domínio relacionados a processos, documentos, status e catálogos do fluxo financeiro.
"""


from .catalogos import (
    FormasPagamento,
    StatusOpcoesPendencia,
    StatusOpcoesProcesso,
    OpcoesEtiqueta,
    TiposDocumento,
    TiposPagamento,
    TiposPendencia,
)
from .documentos import BoletoBancario, ComprovantePagamento, DocumentoOrcamentarioProcessual, DocumentoProcesso
from .processos import (
    STATUS_PROCESSO_BLOQUEADOS_FORM,
    STATUS_PROCESSO_BLOQUEADOS_TOTAL,
    STATUS_PROCESSO_CONTAS_A_PAGAR,
    STATUS_PROCESSO_PAGOS,
    STATUS_PROCESSO_PAGOS_E_POSTERIORES,
    STATUS_PROCESSO_PRE_AUTORIZACAO,
    STATUS_PROCESSO_SOMENTE_DOCUMENTOS,
    Processo,
    GerenciadorProcesso,
    StatusProcesso,
    ReuniaoConselhoFiscal,
    StatusReuniaoConselho,
)
from .suporte import (
    AssinaturaEletronica,
    CancelamentoProcessual,
    ContingenciaProcessual,
    DevolucaoProcessual,
    PendenciaProcessual,
    RegistroAcessoArquivoProcessual,
    STATUS_CONTINGENCIA,
)

# Aliases legados para transição incremental dos módulos de views/serviços.
ProcessoStatus = StatusProcesso
PROCESSO_STATUS_BLOQUEADOS_FORM = STATUS_PROCESSO_BLOQUEADOS_FORM
PROCESSO_STATUS_BLOQUEADOS_TOTAL = STATUS_PROCESSO_BLOQUEADOS_TOTAL
PROCESSO_STATUS_CONTAS_A_PAGAR = STATUS_PROCESSO_CONTAS_A_PAGAR
PROCESSO_STATUS_PAGOS = STATUS_PROCESSO_PAGOS
PROCESSO_STATUS_PAGOS_E_POSTERIORES = STATUS_PROCESSO_PAGOS_E_POSTERIORES
PROCESSO_STATUS_PRE_AUTORIZACAO = STATUS_PROCESSO_PRE_AUTORIZACAO
PROCESSO_STATUS_SOMENTE_DOCUMENTOS = STATUS_PROCESSO_SOMENTE_DOCUMENTOS
AssinaturaAutentique = AssinaturaEletronica
Contingencia = ContingenciaProcessual
Cancelamento = CancelamentoProcessual
Devolucao = DevolucaoProcessual
Pendencia = PendenciaProcessual
RegistroAcessoArquivo = RegistroAcessoArquivoProcessual
ReuniaoConselho = ReuniaoConselhoFiscal
ReuniaoConselhoStatus = StatusReuniaoConselho
StatusChoicesProcesso = StatusOpcoesProcesso
StatusChoicesPendencias = StatusOpcoesPendencia
TagChoices = OpcoesEtiqueta
FormasDePagamento = FormasPagamento
TiposDePagamento = TiposPagamento
TiposDeDocumento = TiposDocumento
TiposDePendencias = TiposPendencia
Boleto_Bancario = BoletoBancario
DocumentoOrcamentario = DocumentoOrcamentarioProcessual
ComprovanteDePagamento = ComprovantePagamento


__all__ = [
    "AssinaturaEletronica",
    "CancelamentoProcessual",
    "ComprovantePagamento",
    "ContingenciaProcessual",
    "DevolucaoProcessual",
    "BoletoBancario",
    "DocumentoOrcamentarioProcessual",
    "DocumentoProcesso",
    "FormasPagamento",
    "PendenciaProcessual",
    "STATUS_PROCESSO_BLOQUEADOS_FORM",
    "STATUS_PROCESSO_BLOQUEADOS_TOTAL",
    "STATUS_PROCESSO_CONTAS_A_PAGAR",
    "STATUS_PROCESSO_PAGOS",
    "STATUS_PROCESSO_PAGOS_E_POSTERIORES",
    "STATUS_PROCESSO_PRE_AUTORIZACAO",
    "STATUS_PROCESSO_SOMENTE_DOCUMENTOS",
    "ProcessoStatus",
    "PROCESSO_STATUS_BLOQUEADOS_FORM",
    "PROCESSO_STATUS_BLOQUEADOS_TOTAL",
    "PROCESSO_STATUS_CONTAS_A_PAGAR",
    "PROCESSO_STATUS_PAGOS",
    "PROCESSO_STATUS_PAGOS_E_POSTERIORES",
    "PROCESSO_STATUS_PRE_AUTORIZACAO",
    "PROCESSO_STATUS_SOMENTE_DOCUMENTOS",
    "Processo",
    "GerenciadorProcesso",
    "StatusProcesso",
    "RegistroAcessoArquivoProcessual",
    "ReuniaoConselhoFiscal",
    "StatusReuniaoConselho",
    "STATUS_CONTINGENCIA",
    "StatusOpcoesPendencia",
    "StatusOpcoesProcesso",
    "OpcoesEtiqueta",
    "TiposDocumento",
    "TiposPagamento",
    "TiposPendencia",
    "AssinaturaAutentique",
    "Contingencia",
    "Cancelamento",
    "Devolucao",
    "Pendencia",
    "RegistroAcessoArquivo",
    "ReuniaoConselho",
    "ReuniaoConselhoStatus",
    "StatusChoicesProcesso",
    "StatusChoicesPendencias",
    "TagChoices",
    "FormasDePagamento",
    "TiposDePagamento",
    "TiposDeDocumento",
    "TiposDePendencias",
    "Boleto_Bancario",
    "DocumentoOrcamentario",
    "ComprovanteDePagamento",
]
