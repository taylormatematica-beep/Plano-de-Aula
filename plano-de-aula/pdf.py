"""
Geração do PDF no layout idêntico ao modelo da escola (Presidente Bernardes).
"""
from io import BytesIO
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (Image, KeepTogether, Paragraph, SimpleDocTemplate,
                                Spacer, Table, TableStyle)
from reportlab.platypus.flowables import HRFlowable

BASE_DIR = Path(__file__).parent
LOGO = BASE_DIR / "static" / "logo.png"

FONT = "Helvetica"
FONT_B = "Helvetica-Bold"

st_titulo = ParagraphStyle("titulo", fontName=FONT_B, fontSize=14, leading=17, alignment=TA_CENTER)
st_label = ParagraphStyle("label", fontName=FONT_B, fontSize=11, leading=14)
st_texto = ParagraphStyle("texto", fontName=FONT, fontSize=11, leading=14)
st_texto_ind = ParagraphStyle("texto_ind", parent=st_texto, leftIndent=10, firstLineIndent=-10)


def _esc(t: str) -> str:
    return (str(t or "")).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _bloco(label: str, texto: str, min_altura_mm: float = 0):
    """Célula com rótulo em negrito e texto (multilinha) abaixo."""
    flow = [Paragraph(_esc(label), st_label)]
    linhas = [l.rstrip() for l in str(texto or "").split("\n")]
    for l in linhas:
        if not l.strip():
            flow.append(Spacer(1, 4))
            continue
        estilo = st_texto_ind if l.lstrip().startswith("•") else st_texto
        flow.append(Paragraph(_esc(l), estilo))
    if min_altura_mm:
        flow.append(Spacer(1, min_altura_mm * mm))
    return flow


def _inline(label: str, valor: str):
    return Paragraph(f"<b>{_esc(label)}</b> {_esc(valor)}", st_texto)


def gerar_pdf(dados: dict, plano: dict) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=16.7 * mm, rightMargin=15.5 * mm,
        topMargin=12 * mm, bottomMargin=15 * mm,
        title=f"Plano de Aula - {dados.get('disciplina','')} - {dados.get('serie','')}",
        author="Escola Presidente Bernardes",
    )
    largura = A4[0] - doc.leftMargin - doc.rightMargin
    grade = TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.75, colors.black),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ])

    story = []

    # Logo + título
    if LOGO.exists():
        img = Image(str(LOGO))
        ratio = img.imageHeight / img.imageWidth
        img.drawWidth = 62 * mm
        img.drawHeight = 62 * mm * ratio
        img.hAlign = "CENTER"
        story += [img, Spacer(1, 6 * mm)]
    story += [Paragraph("PLANO DE AULA", st_titulo), Spacer(1, 6 * mm)]

    # Cabeçalho 2x2
    col = largura / 2
    cab = Table([
        [_inline("DISCIPLINA:", dados.get("disciplina", "")),
         _inline("DATA DE REFERÊNCIA:", dados.get("data", ""))],
        [_inline("TURMA:", dados.get("serie", "")),
         _inline("SUPERVISÃO:", dados.get("supervisao", ""))],
    ], colWidths=[col, col], rowHeights=[12 * mm, 12 * mm])
    cab.setStyle(grade)
    story += [cab, Spacer(1, 5 * mm)]

    # Corpo principal
    corpo = Table([
        [_bloco("TEMA:", "")],
        [_bloco("HABILIDADE DO PLANO DE CURSO:", plano.get("habilidade", ""), 2)],
        [_bloco("OBJETIVO DA APRENDIZAGEM:", plano.get("objetivo", ""), 2)],
        [_bloco("METODOLOGIA (DESENVOLVIMENTO DA AULA):", plano.get("metodologia", ""), 2)],
    ], colWidths=[largura], repeatRows=0, splitInRow=1)  # splitInRow: bloco longo continua na página seguinte
    # TEMA na mesma linha do rótulo
    corpo._cellvalues[0][0] = [_inline("TEMA:", plano.get("tema", ""))]
    corpo.setStyle(grade)
    story += [corpo, Spacer(1, 5 * mm)]

    rec = Table([[_bloco("RECURSOS DIDÁTICOS:", plano.get("recursos", ""), 2)]], colWidths=[largura], splitInRow=1)
    rec.setStyle(grade)
    story += [rec, Spacer(1, 5 * mm)]

    ava = Table([[_bloco("AVALIAÇÃO:", plano.get("avaliacao", ""), 2)]], colWidths=[largura], splitInRow=1)
    ava.setStyle(grade)
    story += [ava, Spacer(1, 5 * mm)]

    if (plano.get("fontes") or "").strip():
        st_fonte = ParagraphStyle("fonte", parent=st_texto_ind, fontSize=9.5, leading=12)
        flow = [Paragraph("FONTES / REFERÊNCIAS:", st_label)]
        for l in plano["fontes"].split("\n"):
            if l.strip():
                flow.append(Paragraph(_esc(l.strip() if l.strip().startswith("•") else "• " + l.strip()), st_fonte))
        flow.append(Spacer(1, 1 * mm))
        fon = Table([[flow]], colWidths=[largura], splitInRow=1)
        fon.setStyle(grade)
        story += [fon, Spacer(1, 4 * mm)]

    # Bloco de assinaturas: Professor(a) | Supervisão | Direção
    st_ass = ParagraphStyle("ass", fontName=FONT, fontSize=9, leading=11, alignment=TA_CENTER)
    st_ass_b = ParagraphStyle("assb", fontName=FONT_B, fontSize=9, leading=11, alignment=TA_CENTER)

    def col_ass(titulo: str, nome: str):
        return [
            Spacer(1, 12 * mm),                       # espaço para assinar
            HRFlowable(width="88%", thickness=0.7, color=colors.black, spaceAfter=2),
            Paragraph(_esc(titulo), st_ass_b),
            Paragraph(_esc(nome) if nome else "&nbsp;", st_ass),
            Paragraph("Data: ____/____/______", st_ass),
        ]

    ass = Table([[
        col_ass("Professor(a)", dados.get("professor", "")),
        col_ass("Supervisão Pedagógica", dados.get("supervisao", "")),
        col_ass("Direção", dados.get("direcao", "")),
    ]], colWidths=[largura / 3] * 3)
    ass.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    story += [KeepTogether(ass)]

    def rodape(canvas, d):
        canvas.saveState()
        canvas.setFont(FONT, 8)
        canvas.setFillColor(colors.grey)
        canvas.drawRightString(A4[0] - d.rightMargin, 8 * mm, f"Página {d.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=rodape, onLaterPages=rodape)
    return buf.getvalue()
