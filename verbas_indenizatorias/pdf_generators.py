
"""Geradores de PDF para documentos de verbas indenizatórias.

Este módulo implementa classes para geração de PDFs de propostas, solicitações e recibos de diárias, reembolsos, jetons, auxílios e suprimentos.
"""
Geradores de PDF específicos de Verbas Indenizatórias (Diárias, Reembolsos, Auxílios, Jetons, Suprimentos).
"""
from commons.shared.pdf_tools import BasePDFDocument, _draw_wrapped_text


_PCD_SIG_Y = 120
_PCD_SIG_HALF_WIDTH = 130
_SCD_SIG_Y = 200
_SCD_SIG_LABEL_Y = 186


class PCDDocument(BasePDFDocument):
	"""Gera o PDF da Proposta de Concessão de Diárias (PCD)."""

	def draw_content(self):
		"""Desenha corpo da PCD no canvas."""
		diaria = self.obj
		c = self.canvas
		width = self.page_width
		height = self.page_height

		margin_left = 70
		margin_right = 70
		text_width = width - margin_left - margin_right

		y = height - 160

		c.setFont("Helvetica-Bold", 13)
		c.drawCentredString(width / 2.0, y, "PROPOSTA DE CONCESSÃO DE DIÁRIAS (PCD)")
		y -= 18
		c.setFont("Helvetica-Bold", 11)
		c.drawCentredString(width / 2.0, y, f"Nº {diaria.numero_siscac}")
		y -= 16
		c.setFont("Helvetica", 10)
		c.drawCentredString(width / 2.0, y, f"Tipo: {diaria.get_tipo_solicitacao_display()}")
		y -= 28

		c.setLineWidth(0.5)
		c.line(margin_left, y, width - margin_right, y)
		y -= 20

		nome = str(diaria.beneficiario.nome) if diaria.beneficiario and diaria.beneficiario.nome else "Não informado"
		cpf = str(diaria.beneficiario.cpf_cnpj) if diaria.beneficiario and diaria.beneficiario.cpf_cnpj else "Não informado"
		cargo = str(diaria.beneficiario.cargo_funcao) if diaria.beneficiario and diaria.beneficiario.cargo_funcao else "Não informado"

		c.setFont("Helvetica-Bold", 11)
		c.drawString(margin_left, y, "DADOS DO BENEFICIÁRIO:")
		y -= 16
		c.setFont("Helvetica", 11)
		c.drawString(margin_left, y, f"Nome:              {nome}")
		y -= 16
		c.drawString(margin_left, y, f"CPF:               {cpf}")
		y -= 16
		c.drawString(margin_left, y, f"Cargo / Função:    {cargo}")
		y -= 24

		if diaria.proponente:
			c.setFont("Helvetica-Bold", 11)
			c.drawString(margin_left, y, "PROPONENTE:")
			y -= 16
			c.setFont("Helvetica", 11)
			nome_p = diaria.proponente.get_full_name() or diaria.proponente.username
			email_p = diaria.proponente.email or "Não informado"
			cargo_p = "Não informado"
			c.drawString(margin_left, y, f"Nome:              {nome_p}")
			y -= 16
			c.drawString(margin_left, y, f"E-mail:            {email_p}")
			y -= 16
			c.drawString(margin_left, y, f"Cargo / Função:    {cargo_p}")
			y -= 24

		c.setFont("Helvetica-Bold", 11)
		c.drawString(margin_left, y, "DADOS DA VIAGEM:")
		y -= 16
		c.setFont("Helvetica", 11)

		data_saida = diaria.data_saida.strftime('%d/%m/%Y') if diaria.data_saida else "Não informado"
		data_retorno = diaria.data_retorno.strftime('%d/%m/%Y') if diaria.data_retorno else "Não informado"

		c.drawString(margin_left, y, f"Data de Saída:           {data_saida}")
		y -= 16
		c.drawString(margin_left, y, f"Data de Retorno:         {data_retorno}")
		y -= 16
		c.drawString(margin_left, y, f"Cidade de Origem:        {diaria.cidade_origem or 'Não informado'}")
		y -= 16
		c.drawString(margin_left, y, f"Cidade(s) de Destino:    {diaria.cidade_destino or 'Não informado'}")
		y -= 16
		if diaria.meio_de_transporte:
			c.drawString(margin_left, y, f"Meio de Transporte:      {diaria.meio_de_transporte}")
			y -= 16
		y -= 8

		c.setFont("Helvetica-Bold", 11)
		c.drawString(margin_left, y, "OBJETIVO DA VIAGEM:")
		y -= 16
		y = _draw_wrapped_text(c, diaria.objetivo or "Não informado.", margin_left, y, text_width,
							   font_name="Helvetica", font_size=11)
		y -= 20

		c.setFont("Helvetica-Bold", 11)
		c.drawString(margin_left, y, "VALORES:")
		y -= 16
		c.setFont("Helvetica", 11)
		c.drawString(margin_left, y, f"Quantidade de Diárias:   {diaria.quantidade_diarias}")
		y -= 16
		c.setFont("Helvetica-Bold", 11)
		c.drawString(margin_left, y, f"Valor Total:             {self._formatar_moeda(diaria.valor_total)}")
		y -= 28

		c.setLineWidth(0.5)
		c.line(margin_left, y, width - margin_right, y)
		y -= 14
		boilerplate = (
			"Proposta de concessão de diárias elaborada nos termos da legislação e regulamento interno vigentes, "
			"para fins de autorização pelo Ordenador de Despesas."
		)
		_draw_wrapped_text(c, boilerplate, margin_left, y, text_width, font_name="Helvetica-Oblique", font_size=10)

		sig_left_x = margin_left + _PCD_SIG_HALF_WIDTH
		sig_right_x = width - margin_right - _PCD_SIG_HALF_WIDTH

		c.setFont("Helvetica", 9)

		c.drawCentredString(sig_left_x, _PCD_SIG_Y + 38, nome)
		c.drawCentredString(sig_left_x, _PCD_SIG_Y + 26, f"CPF: {cpf}")
		c.drawCentredString(sig_left_x, _PCD_SIG_Y + 14, cargo)
		c.line(sig_left_x - _PCD_SIG_HALF_WIDTH, _PCD_SIG_Y,
			   sig_left_x + _PCD_SIG_HALF_WIDTH, _PCD_SIG_Y)
		c.drawCentredString(sig_left_x, _PCD_SIG_Y - 12, "Assinatura do(a) Beneficiário(a)")

		c.drawCentredString(sig_right_x, _PCD_SIG_Y + 14,
							"Local e Data: _____ / _____ / _________")
		c.line(sig_right_x - _PCD_SIG_HALF_WIDTH, _PCD_SIG_Y,
			   sig_right_x + _PCD_SIG_HALF_WIDTH, _PCD_SIG_Y)
		c.drawCentredString(sig_right_x, _PCD_SIG_Y - 12, "Ordenador(a) de Despesa")

	def _formatar_moeda(self, valor):
		"""Formata valor em moeda brasileira (R$)."""
		from commons.shared.text_tools import format_brl_currency
		return format_brl_currency(valor)


class SCDDocument(BasePDFDocument):
	"""Gera o PDF da Solicitação de Concessão de Diárias (SCD)."""

	def draw_content(self):
		"""Desenha corpo da SCD no canvas."""
		diaria = self.obj
		c = self.canvas
		width = self.page_width

		margin_left = 70
		margin_right = 70
		text_width = width - margin_left - margin_right

		c.setFont("Helvetica-Bold", 14)
		c.drawCentredString(width / 2.0, 620, "SOLICITAÇÃO DE CONCESSÃO DE DIÁRIAS - SCD")

		c.setFont("Helvetica", 11)
		y = 550

		siscac = diaria.numero_siscac or 'N/A'
		nome_benef = diaria.beneficiario.nome if diaria.beneficiario else 'N/A'
		cpf_benef = diaria.beneficiario.cpf_cnpj if diaria.beneficiario else 'N/A'
		proponente = diaria.proponente.get_full_name() if diaria.proponente else 'N/A'
		data_saida = diaria.data_saida.strftime('%d/%m/%Y') if diaria.data_saida else 'N/A'
		data_retorno = diaria.data_retorno.strftime('%d/%m/%Y') if diaria.data_retorno else 'N/A'
		transporte = diaria.meio_de_transporte.meio_de_transporte if diaria.meio_de_transporte else 'N/A'

		fields = [
			f"Nº SISCAC: {siscac}",
			f"Beneficiário: {nome_benef} - CPF: {cpf_benef}",
			f"Proponente: {proponente}",
			f"Período: {data_saida} a {data_retorno}",
			f"Trajeto: {diaria.cidade_origem} para {diaria.cidade_destino}",
			f"Transporte: {transporte}",
		]
		for field in fields:
			c.drawString(margin_left, y, field)
			y -= 20

		c.setFont("Helvetica-Bold", 11)
		c.drawString(margin_left, 430, "Objetivo:")
		_draw_wrapped_text(c, diaria.objetivo or 'N/A', margin_left, 410, text_width,
						   font_name="Helvetica", font_size=11)

		c.setFont("Helvetica", 11)
		c.drawString(
			margin_left, 380,
			f"Cálculo: {diaria.quantidade_diarias} diárias - Total Estimado: {self._formatar_moeda(diaria.valor_total)}",
		)

		sig_left_x = margin_left + _PCD_SIG_HALF_WIDTH
		sig_right_x = width - margin_right - _PCD_SIG_HALF_WIDTH

		c.setFont("Helvetica", 10)
		c.line(sig_left_x - _PCD_SIG_HALF_WIDTH, _SCD_SIG_Y,
			   sig_left_x + _PCD_SIG_HALF_WIDTH, _SCD_SIG_Y)
		c.drawCentredString(sig_left_x, _SCD_SIG_LABEL_Y, "Assinatura do Beneficiário")

		c.line(sig_right_x - _PCD_SIG_HALF_WIDTH, _SCD_SIG_Y,
			   sig_right_x + _PCD_SIG_HALF_WIDTH, _SCD_SIG_Y)
		c.drawCentredString(sig_right_x, _SCD_SIG_LABEL_Y, "Assinatura do Proponente")

	def _formatar_moeda(self, valor):
		"""Formata valor em moeda brasileira (R$)."""
		from commons.shared.text_tools import format_brl_currency
		return format_brl_currency(valor)


class ReciboDocument(BasePDFDocument):
	"""Gera PDF de recibo para reembolso, auxílio, jeton e suprimento."""

	def draw_content(self):
		"""Desenha corpo do recibo com dispatch por tipo de objeto."""
		obj = self.obj
		c = self.canvas
		page_width = self.page_width

		_RECIBO_DISPATCH = {
			'ReembolsoCombustivel': (
				"Reembolso de Combustível",
				lambda o: o.beneficiario,
				lambda o: o.valor_total,
			),
			'AuxilioRepresentacao': (
				"Auxílio Representação",
				lambda o: o.beneficiario,
				lambda o: o.valor_total,
			),
			'Jeton': (
				"Jeton",
				lambda o: o.beneficiario,
				lambda o: o.valor_total,
			),
			'SuprimentoDeFundos': (
				"Suprimento de Fundos",
				lambda o: o.suprido,
				lambda o: o.valor_liquido,
			),
		}

		class_name = obj.__class__.__name__
		dispatch = _RECIBO_DISPATCH.get(class_name)
		if dispatch is None:
			raise ValueError(
				f"ReciboDocument não suporta o tipo '{class_name}'. "
				f"Tipos aceitos: {', '.join(_RECIBO_DISPATCH)}."
			)
		tipo_verba, get_beneficiario, get_valor = dispatch
		beneficiario = get_beneficiario(obj)
		valor = get_valor(obj)

		valor_formatado = self._formatar_moeda(valor)
		beneficiario_nome = beneficiario.nome if beneficiario else "N/A"
		beneficiario_cpf = beneficiario.cpf_cnpj if beneficiario else "N/A"

		c.setFont("Helvetica-Bold", 14)
		c.drawCentredString(page_width / 2, 620, "RECIBO DE PAGAMENTO")

		c.setFont("Helvetica-Bold", 12)
		c.drawCentredString(page_width / 2, 590, tipo_verba.upper())

		declaration = (
			f"Recebi do Conselho Regional de Corretores de Imóveis de Santa Catarina - "
			f"11ª Região (CRECI-SC), a importância líquida de {valor_formatado}, "
			f"referente ao pagamento de {tipo_verba}."
		)
		margin_left = 72
		text_width = page_width - 2 * margin_left
		_draw_wrapped_text(
			c, declaration, margin_left, 540, text_width,
			font_name="Helvetica", font_size=12,
		)

		c.setFont("Helvetica", 11)
		c.drawString(margin_left, 450, f"Beneficiário / Recebedor: {beneficiario_nome}")
		c.drawString(margin_left, 434, f"CPF / CNPJ: {beneficiario_cpf}")

		sig_x = page_width / 2
		c.line(sig_x - 130, 250, sig_x + 130, 250)
		c.setFont("Helvetica", 11)
		c.drawCentredString(sig_x, 265, beneficiario_nome)
		c.drawCentredString(sig_x, 236, "Assinatura do Recebedor")
		c.drawCentredString(sig_x, 220, "Local e Data: Florianópolis, _____ / _____ / _________")

	def _formatar_moeda(self, valor):
		"""Formata valor em moeda brasileira (R$)."""
		from commons.shared.text_tools import format_brl_currency
		return format_brl_currency(valor)


# Registry de documentos específicos de Verbas Indenizatórias
VERBAS_DOCUMENT_REGISTRY = {
	'scd': SCDDocument,
	'pcd': PCDDocument,
	'recibo_reembolso': ReciboDocument,
	'recibo_auxilio': ReciboDocument,
	'recibo_jeton': ReciboDocument,
	'recibo_suprimento': ReciboDocument,
}


__all__ = [
	"PCDDocument",
	"SCDDocument",
	"ReciboDocument",
	"VERBAS_DOCUMENT_REGISTRY",
]
