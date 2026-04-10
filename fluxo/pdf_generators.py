import logging
from datetime import date

from commons.shared.pdf_tools import BasePDFDocument, _draw_wrapped_text, _contar_paginas_documentos
from commons.shared.text_tools import format_brl_currency as _formatar_moeda

logger = logging.getLogger(__name__)
_SIGNATURE_BLOCK_HEIGHT = 160
_MAX_AUDIT_TRAIL_ENTRIES = 10
_AUTH_SIG_Y = 120
_AUTH_SIG_HALF_WIDTH = 130
_AUTH_SIG_DATE_OFFSET = 32
_COUNCIL_SIG_Y = 110
_COUNCIL_SIG_WIDTH = 145


class TermoContabilizacaoDocument(BasePDFDocument):
    """Gera o PDF do Termo de Contabilização para um processo."""

    def draw_content(self):
        """Desenha corpo do Termo de Contabilização no canvas."""
        processo = self.obj
        c = self.canvas
        page_width = self.page_width

        c.setFont("Helvetica-Bold", 14)
        c.drawCentredString(page_width / 2, 620, "TERMO DE CONTABILIZAÇÃO")

        c.setFont("Helvetica", 11)
        line_height = 20
        y = 550
        credor_nome = processo.credor.nome if processo.credor else "N/A"
        details = [
            f"Processo Nº: {processo.id}",
            f"Nota de Empenho: {processo.n_nota_empenho or 'N/A'}",
            f"Credor: {credor_nome}",
            f"Valor Consolidado: R$ {processo.valor_liquido}",
        ]
        for line in details:
            c.drawString(72, y, line)
            y -= line_height

        declaration = (
            "Certifico que a despesa referente ao Processo acima identificado foi devidamente "
            "registrada e contabilizada no sistema financeiro nesta data, em estrita conformidade "
            "com as normas contábeis e a legislação vigente."
        )
        c.setFont("Helvetica", 11)
        wrapped_lines = textwrap.wrap(declaration, width=85)
        y = 430
        for line in wrapped_lines:
            c.drawString(72, y, line)
            y -= line_height

        sig_x = page_width / 2
        c.line(sig_x - 120, 220, sig_x + 120, 220)
        c.setFont("Helvetica", 11)
        c.drawCentredString(sig_x, 205, "Assinatura do(a) Contador(a)")
        c.drawCentredString(sig_x, 180, "Data da Contabilização: _____ / _____ / _________")


class TermoAtesteDocument(BasePDFDocument):
    """Gera o PDF do Termo de Liquidação e Ateste para documento fiscal."""

    def draw_content(self):
        """Desenha corpo do Termo de Liquidação e Ateste no canvas."""
        documento_fiscal = self.obj
        c = self.canvas
        page_width = self.page_width

        c.setFont("Helvetica-Bold", 14)
        c.drawCentredString(page_width / 2, 620, "TERMO DE LIQUIDAÇÃO E ATESTE")

        c.setFont("Helvetica", 11)
        line_height = 20
        y = 550

        processo_id = (
            documento_fiscal.processo.id if documento_fiscal.processo else "N/A"
        )
        fornecedor = (
            documento_fiscal.processo.credor.nome
            if documento_fiscal.processo and documento_fiscal.processo.credor
            else "N/A"
        )
        details = [
            f"Processo Nº: {processo_id}",
            f"Documento Fiscal / Nota Nº: {documento_fiscal.numero_nota_fiscal}",
            f"Fornecedor: {fornecedor}",
            f"Valor do Documento: R$ {documento_fiscal.valor_bruto}",
        ]
        for line in details:
            c.drawString(72, y, line)
            y -= line_height

        declaration = (
            "Atesto, para os devidos fins e sob as penas da lei, que os serviços referenciados "
            "no documento fiscal supra foram efetivamente prestados, ou os materiais entregues, "
            "de forma satisfatória e de acordo com as especificações contratuais exigidas."
        )
        c.setFont("Helvetica", 11)
        y = _draw_wrapped_text(declaration, 72, 430, 500, font_name="Helvetica", font_size=11, leading=20)

        sig_x = page_width / 2
        if documento_fiscal.fiscal_contrato:
            fiscal_name = documento_fiscal.fiscal_contrato.get_full_name()
        else:
            fiscal_name = "Fiscal Não Atribuído"
        c.setFont("Helvetica", 11)
        c.drawCentredString(sig_x, 235, fiscal_name)
        c.line(sig_x - 120, 220, sig_x + 120, 220)
        c.drawCentredString(sig_x, 205, "Fiscal do Contrato")
        c.drawCentredString(sig_x, 180, "Local e Data: Florianópolis, _____ / _____ / _________")


class AutorizacaoDocument(BasePDFDocument):
    """Gera o PDF do Termo de Autorização de Pagamento para um processo."""

    def draw_content(self):
        """Desenha corpo do Termo de Autorização de Pagamento no canvas."""
        processo = self.obj
        c = self.canvas
        width = self.page_width
        height = self.page_height

        margin_left = 70
        margin_right = 70
        text_width = width - margin_left - margin_right

        y = height - 160

        c.setFont("Helvetica-Bold", 13)
        c.drawCentredString(width / 2.0, y, "TERMO DE AUTORIZAÇÃO DE PAGAMENTO")
        y -= 18
        c.setFont("Helvetica-Bold", 12)
        c.drawCentredString(width / 2.0, y, f"PROCESSO Nº {processo.id}")
        y -= 30

        c.setLineWidth(0.5)
        c.line(margin_left, y, width - margin_right, y)
        y -= 20

        c.setFont("Helvetica-Bold", 11)
        c.drawString(margin_left, y, "DADOS DO CREDOR:")
        y -= 16
        c.setFont("Helvetica", 11)

        nome_credor = str(processo.credor.nome) if processo.credor and processo.credor.nome else "Não informado"
        cpf_cnpj = str(processo.credor.cpf_cnpj) if processo.credor and processo.credor.cpf_cnpj else "Não informado"

        c.drawString(margin_left, y, f"Nome / Razão Social:  {nome_credor}")
        y -= 16
        c.drawString(margin_left, y, f"CPF / CNPJ:           {cpf_cnpj}")
        y -= 24

        c.setFont("Helvetica-Bold", 11)
        c.drawString(margin_left, y, "COMPOSIÇÃO DO VALOR:")
        y -= 16
        c.setFont("Helvetica", 11)

        valor_bruto = processo.valor_bruto or 0
        valor_liquido = processo.valor_liquido or 0
        total_retencoes = valor_bruto - valor_liquido

        c.drawString(margin_left, y, f"Valor Bruto:                    {_formatar_moeda(valor_bruto)}")
        y -= 16
        c.drawString(margin_left, y, f"Total de Retenções (Impostos):  {_formatar_moeda(total_retencoes)}")
        y -= 16
        c.setFont("Helvetica-Bold", 11)
        c.drawString(margin_left, y, f"Valor Líquido a Pagar:          {_formatar_moeda(valor_liquido)}")
        y -= 24

        conta_credor = processo.credor.conta if processo.credor else None
        if conta_credor:
            c.setFont("Helvetica-Bold", 11)
            c.drawString(margin_left, y, "DADOS BANCÁRIOS DO CREDOR:")
            y -= 16
            c.setFont("Helvetica", 11)
            c.drawString(margin_left, y, f"Banco:    {conta_credor.banco or 'Não informado'}")
            y -= 16
            c.drawString(margin_left, y, f"Agência:  {conta_credor.agencia or 'Não informado'}")
            y -= 16
            c.drawString(margin_left, y, f"Conta:    {conta_credor.conta or 'Não informado'}")
            y -= 24

        c.setFont("Helvetica-Bold", 11)
        c.drawString(margin_left, y, "DETALHAMENTO / JUSTIFICATIVA:")
        y -= 16
        detalhamento = processo.detalhamento or "Não informado."
        y = _draw_wrapped_text(c, detalhamento, margin_left, y, text_width, font_name="Helvetica", font_size=11)
        y -= 20

        c.setLineWidth(0.5)
        c.line(margin_left, y, width - margin_right, y)
        y -= 16

        boilerplate = (
            "Autorizo, nos termos da legislação vigente, o pagamento da despesa acima especificada, "
            "face à regular liquidação do processo."
        )
        _draw_wrapped_text(c, boilerplate, margin_left, y, text_width, font_name="Helvetica-Oblique", font_size=10)

        sig_x = width / 2.0
        c.setFont("Helvetica", 10)
        c.drawCentredString(sig_x, _AUTH_SIG_Y + _AUTH_SIG_DATE_OFFSET, "Local e Data: _____________________________, _____ / _____ / _________")
        c.line(sig_x - _AUTH_SIG_HALF_WIDTH, _AUTH_SIG_Y, sig_x + _AUTH_SIG_HALF_WIDTH, _AUTH_SIG_Y)
        c.drawCentredString(sig_x, _AUTH_SIG_Y - 14, "Ordenador(a) de Despesa")








class ConselhoFiscalDocument(BasePDFDocument):
    """Gera o PDF do parecer do Conselho Fiscal para um processo.

    Aceita ``numero_reuniao`` em ``kwargs`` para exibir a reunião no cabeçalho.
    """

    def draw_content(self):
        """Desenha corpo do parecer do Conselho Fiscal no canvas."""
        processo = self.obj
        c = self.canvas
        width = self.page_width
        height = self.page_height

        margin_left = 70
        margin_right = 70
        text_width = width - margin_left - margin_right
        y_min = _SIGNATURE_BLOCK_HEIGHT

        y = height - 160

        c.setFont("Helvetica-Bold", 13)
        c.drawCentredString(width / 2.0, y, "PARECER DE AUDITORIA - CONSELHO FISCAL")
        y -= 18
        c.setFont("Helvetica-Bold", 11)
        c.drawCentredString(width / 2.0, y, f"PROCESSO Nº {processo.id}")
        y -= 28

        numero_reuniao = self.kwargs.get('numero_reuniao')
        if numero_reuniao:
            c.setFont("Helvetica", 10)
            c.drawCentredString(
                width / 2.0, y,
                f"Processo aprovado na {numero_reuniao}ª Reunião do Conselho Fiscal"
            )
            y -= 18

        c.setLineWidth(0.5)
        c.line(margin_left, y, width - margin_right, y)
        y -= 18

        total_docs, total_pages = _contar_paginas_documentos(processo)

        c.setFont("Helvetica-Bold", 11)
        c.drawString(margin_left, y, "INTEGRIDADE DOCUMENTAL:")
        y -= 16

        integridade_texto = (
            f"O processo é composto por {total_docs} documento(s) anexo(s) "
            f"totalizando {total_pages} página(s)."
        )
        y = _draw_wrapped_text(c, integridade_texto, margin_left, y, text_width, font_name="Helvetica", font_size=11)
        y -= 20

        c.setFont("Helvetica-Bold", 11)
        c.drawString(margin_left, y, "TRILHA DE AUDITORIA (TRANSIÇÕES DE STATUS):")
        y -= 16

        history_records = list(processo.history.all().order_by('history_date'))
        log_lines = []
        for i, record in enumerate(history_records):
            prev_status_id = history_records[i - 1].status_id if i > 0 else None
            if record.history_type == '+' or (record.history_type == '~' and record.status_id != prev_status_id):
                try:
                    if record.history_user:
                        user_str = record.history_user.get_full_name() or record.history_user.username
                    else:
                        user_str = "Sistema"
                    date_str = record.history_date.strftime('%d/%m/%Y às %H:%M')
                    if record.history_type == '+':
                        log_lines.append(f"• Processo criado em {date_str} por {user_str}")
                    else:
                        status_str = str(record.status) if record.status else "Status atualizado"
                        log_lines.append(f"• {status_str} em {date_str} por {user_str}")
                except AttributeError as exc:
                    logger.warning(
                        "Falha ao montar trilha de auditoria do processo %s: %s",
                        processo.id,
                        exc,
                    )

        if log_lines:
            for line in log_lines[:_MAX_AUDIT_TRAIL_ENTRIES]:
                if y > y_min:
                    y = _draw_wrapped_text(
                        c, line, margin_left, y, text_width,
                        font_name="Helvetica", font_size=10, leading=14,
                    )
        else:
            c.setFont("Helvetica-Oblique", 10)
            c.drawString(margin_left, y, "Nenhuma transição de status registrada.")
            y -= 14

        y -= 16

        if y > y_min:
            c.setFont("Helvetica-Bold", 11)
            c.drawString(margin_left, y, "CONTINGÊNCIAS E RETIFICAÇÕES EXCEPCIONAIS:")
            y -= 16

            contingencias = processo.contingencias.all().select_related(
                'solicitante', 'aprovado_por_supervisor', 'aprovado_por_ordenador', 'aprovado_por_conselho'
            )

            if contingencias.exists():
                for cont in contingencias:
                    if y <= y_min:
                        break
                    solicitante_str = cont.solicitante.get_full_name() or cont.solicitante.username
                    data_str = cont.data_solicitacao.strftime('%d/%m/%Y')
                    status_display = cont.get_status_display()

                    cont_header = (
                        f"• Contingência #{cont.pk} [{status_display}] — "
                        f"Solicitada em {data_str} por {solicitante_str}"
                    )
                    y = _draw_wrapped_text(
                        c, cont_header, margin_left, y, text_width,
                        font_name="Helvetica-Bold", font_size=10, leading=14,
                    )

                    if cont.justificativa and y > y_min:
                        y = _draw_wrapped_text(
                            c, f"  Justificativa: {cont.justificativa}",
                            margin_left, y, text_width,
                            font_name="Helvetica", font_size=10, leading=13,
                        )

                    if cont.aprovado_por_supervisor and y > y_min:
                        aprov = cont.aprovado_por_supervisor
                        y = _draw_wrapped_text(
                            c, f"  Supervisor: Aprovado por {aprov.get_full_name() or aprov.username}",
                            margin_left, y, text_width,
                            font_name="Helvetica", font_size=10, leading=13,
                        )

                    if cont.aprovado_por_ordenador and y > y_min:
                        aprov = cont.aprovado_por_ordenador
                        y = _draw_wrapped_text(
                            c, f"  Ordenador: Aprovado por {aprov.get_full_name() or aprov.username}",
                            margin_left, y, text_width,
                            font_name="Helvetica", font_size=10, leading=13,
                        )

                    if cont.aprovado_por_conselho and y > y_min:
                        aprov = cont.aprovado_por_conselho
                        y = _draw_wrapped_text(
                            c, f"  Conselho: Aprovado por {aprov.get_full_name() or aprov.username}",
                            margin_left, y, text_width,
                            font_name="Helvetica", font_size=10, leading=13,
                        )

                    y -= 8
            else:
                c.setFont("Helvetica-Bold", 10)
                c.drawString(
                    margin_left, y,
                    "Nenhuma contingência ou retificação excepcional registrada para este processo.",
                )
                y -= 16

        y -= 10

        if y > y_min:
            c.setLineWidth(0.5)
            c.line(margin_left, y, width - margin_right, y)
            y -= 14
            boilerplate = (
                "O Conselho Fiscal manifesta-se pela REGULARIDADE das despesas, "
                "conforme histórico auditado acima."
            )
            _draw_wrapped_text(c, boilerplate, margin_left, y, text_width, font_name="Helvetica-Oblique", font_size=10)

        positions = [
            (margin_left + _COUNCIL_SIG_WIDTH / 2, "Conselheiro(a) Fiscal 1"),
            (width / 2.0, "Conselheiro(a) Fiscal 2"),
            (width - margin_right - _COUNCIL_SIG_WIDTH / 2, "Conselheiro(a) Fiscal 3"),
        ]
        c.setFont("Helvetica", 9)
        for sig_x, label in positions:
            c.line(sig_x - _COUNCIL_SIG_WIDTH / 2, _COUNCIL_SIG_Y, sig_x + _COUNCIL_SIG_WIDTH / 2, _COUNCIL_SIG_Y)
            c.drawCentredString(sig_x, _COUNCIL_SIG_Y - 12, label)


class TermoAuditoriaDocument(BasePDFDocument):
    """Gera o PDF do Termo de Auditoria para um processo."""

    def draw_content(self):
        """Desenha corpo do Termo de Auditoria no canvas."""
        processo = self.obj
        c = self.canvas
        width = self.page_width
        height = self.page_height

        margin_left = 70
        margin_right = 70
        text_width = width - margin_left - margin_right

        y = height - 160

        c.setFont("Helvetica-Bold", 13)
        c.drawCentredString(width / 2.0, y, "TERMO DE AUDITORIA")
        y -= 18
        c.setFont("Helvetica-Bold", 11)
        c.drawCentredString(width / 2.0, y, f"PROCESSO Nº {processo.id}")
        y -= 28

        c.setLineWidth(0.5)
        c.line(margin_left, y, width - margin_right, y)
        y -= 20

        c.setFont("Helvetica", 11)
        c.drawString(margin_left, y, f"Credor: {processo.credor.nome if processo.credor else 'Não informado'}")
        y -= 16
        c.drawString(margin_left, y, f"Valor Líquido: {_formatar_moeda(processo.valor_liquido)}")
        y -= 16
        c.drawString(
            margin_left,
            y,
            f"Data de Auditoria: {date.today().strftime('%d/%m/%Y')}",
        )
        y -= 24

        texto = (
            "Certifico, para os devidos fins, que o processo foi auditado e que os "
            "documentos apresentados atendem aos requisitos formais e materiais "
            "para continuidade do fluxo institucional."
        )
        y = _draw_wrapped_text(c, texto, margin_left, y, text_width, font_name="Helvetica", font_size=11)
        y -= 30

        sig_x = width / 2.0
        c.setFont("Helvetica", 10)
        c.drawCentredString(sig_x, _AUTH_SIG_Y + _AUTH_SIG_DATE_OFFSET, "Local e Data: _____________________________, _____ / _____ / _________")
        c.line(sig_x - _AUTH_SIG_HALF_WIDTH, _AUTH_SIG_Y, sig_x + _AUTH_SIG_HALF_WIDTH, _AUTH_SIG_Y)
        c.drawCentredString(sig_x, _AUTH_SIG_Y - 14, "Responsável pela Auditoria")





# Registry de documentos específicos de fluxo (pagamentos)
FLUXO_DOCUMENT_REGISTRY = {
    'contabilizacao': TermoContabilizacaoDocument,
    'auditoria': TermoAuditoriaDocument,
    'ateste': TermoAtesteDocument,
    'autorizacao': AutorizacaoDocument,
    'conselho_fiscal': ConselhoFiscalDocument,
}


__all__ = [
    "TermoContabilizacaoDocument",
    "TermoAtesteDocument",
    "AutorizacaoDocument",
    "ConselhoFiscalDocument",
    "TermoAuditoriaDocument",
    "FLUXO_DOCUMENT_REGISTRY",
]
