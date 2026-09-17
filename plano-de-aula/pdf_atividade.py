"""
PDF de provas/atividades geradas a partir dos planos de aula, e PDF do gabarito.
Mesmo padrão visual do plano (logo da escola, Helvetica, grade preta).
"""
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate,
                                Spacer, Table, TableStyle)
from reportlab.platypus.flowables import HRFlowable

from pdf import FONT, FONT_B, LOGO, _esc

st_titulo = ParagraphStyle("t", fontName=FONT_B, fontSize=13, leading=16, alignment=TA_CENTER)
st_sub = ParagraphStyle("s", fontName=FONT, fontSize=10, leading=13, alignment=TA_CENTER, textColor=colors.HexColor("#444"))
st_cab = ParagraphStyle("c", fontName=FONT, fontSize=10, leading=13)
st_inst = ParagraphStyle("i", fontName=FONT, fontSize=9.5, leading=12.5, leftIndent=8, firstLineIndent=-8)
st_q = ParagraphStyle("q", fontName=FONT, fontSize=10.5, leading=14, alignment=TA_JUSTIFY)
st_qnum = ParagraphStyle("qn", fontName=FONT_B, fontSize=10.5, leading=14)
st_alt = ParagraphStyle("a", fontName=FONT, fontSize=10.5, leading=14, leftIndent=18, firstLineIndent=-18)
st_val = ParagraphStyle("v", fontName=FONT, fontSize=9, leading=11, alignment=2, textColor=colors.HexColor("#333"))
st_gab = ParagraphStyle("g", fontName=FONT, fontSize=10, leading=13.5)
st_gab_b = ParagraphStyle("gb", fontName=FONT_B, fontSize=10, leading=13.5)
st_rod = ParagraphStyle("r", fontName=FONT, fontSize=8, textColor=colors.grey, alignment=TA_CENTER)

LETRAS = "ABCDE"


def _fmt_valor(v) -> str:
    try:
        v = float(v)
    except (TypeError, ValueError):
        return ""
    return (f"{v:.1f}".rstrip("0").rstrip(".") if v != int(v) else str(int(v))).replace(".", ",")


def _paragrafos(texto: str, estilo) -> list:
    out = []
    for l in str(texto or "").split("\n"):
        if l.strip():
            out.append(Paragraph(_esc(l.strip()), estilo))
        else:
            out.append(Spacer(1, 3))
    return out or [Paragraph("", estilo)]


def _cabecalho(story, ativ: dict, largura: float, subtitulo: str = ""):
    if LOGO.exists():
        img = Image(str(LOGO))
        ratio = img.imageHeight / img.imageWidth
        img.drawWidth = 52 * mm
        img.drawHeight = 52 * mm * ratio
        img.hAlign = "CENTER"
        story += [img, Spacer(1, 3 * mm)]
    story.append(Paragraph(_esc((ativ.get("titulo") or "Atividade").upper()), st_titulo))
    if subtitulo:
        story.append(Paragraph(_esc(subtitulo), st_sub))
    story.append(Spacer(1, 3 * mm))


def gerar_pdf_atividade(ativ: dict, meta: dict) -> bytes:
    """ativ = {titulo, instrucoes, questoes[]}; meta = {disciplina, serie, professor, tipo_nome, avaliativa, valor_total, data}."""
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm,
                            topMargin=12 * mm, bottomMargin=15 * mm,
                            title=ativ.get("titulo") or "Atividade", author="Escola Presidente Bernardes")
    largura = A4[0] - doc.leftMargin - doc.rightMargin
    grade = TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.75, colors.black), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ])
    story: list = []
    sub = f"{meta.get('tipo_nome','')} · {meta.get('disciplina','')} · {meta.get('serie','')}"
    if meta.get("avaliativa"):
        sub += f" · Valor: {_fmt_valor(meta.get('valor_total'))} pontos"
    _cabecalho(story, ativ, largura, sub)

    # Identificação do estudante
    avaliativa = bool(meta.get("avaliativa"))
    l1 = [Paragraph("<b>Estudante:</b> ", st_cab), Paragraph("<b>Nº:</b>", st_cab), Paragraph(f"<b>Turma:</b> {_esc(meta.get('serie',''))}", st_cab)]
    l2 = [Paragraph(f"<b>Professor(a):</b> {_esc(meta.get('professor',''))}", st_cab),
          Paragraph("<b>Data:</b> ____/____/______", st_cab),
          Paragraph("<b>Nota:</b>" if avaliativa else "&nbsp;", st_cab)]
    cab = Table([l1, l2], colWidths=[largura * 0.5, largura * 0.22, largura * 0.28], rowHeights=[11 * mm, 11 * mm])
    cab.setStyle(grade)
    story += [cab, Spacer(1, 3 * mm)]

    # Instruções
    inst = (ativ.get("instrucoes") or "").strip()
    if inst:
        flow = [Paragraph("<b>INSTRUÇÕES</b>", st_cab)]
        for l in inst.split("\n"):
            if l.strip():
                l = l.strip()
                flow.append(Paragraph(_esc(l if l.startswith("•") else "• " + l), st_inst))
        t = Table([[flow]], colWidths=[largura])
        t.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.75, colors.black), ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f4f4f5")),
                               ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                               ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
        story += [t, Spacer(1, 4 * mm)]

    # Questões
    for n, q in enumerate(ativ.get("questoes") or [], 1):
        bloco = []
        cab_q = f"QUESTÃO {n:02d}"
        if avaliativa and q.get("valor") is not None:
            cab_q += f" ({_fmt_valor(q['valor'])} {'ponto' if float(q['valor']) == 1 else 'pontos'})"
        hab = (q.get("habilidade") or "").strip()
        linha = Table([[Paragraph(cab_q, st_qnum), Paragraph(_esc(hab), st_val) if hab else ""]],
                      colWidths=[largura * 0.7, largura * 0.3])
        linha.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                                   ("BOTTOMPADDING", (0, 0), (-1, -1), 1), ("TOPPADDING", (0, 0), (-1, -1), 0),
                                   ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.HexColor("#999"))]))
        bloco.append(linha)
        bloco.append(Spacer(1, 2))
        bloco += _paragrafos(q.get("enunciado", ""), st_q)
        bloco.append(Spacer(1, 2))
        if q.get("tipo") == "me":
            for i, alt in enumerate((q.get("alternativas") or [])[:5]):
                bloco.append(Paragraph(f"<b>{LETRAS[i]})</b> {_esc(alt)}", st_alt))
        else:
            n_lin = int(q.get("linhas") or 6)
            for _ in range(n_lin):
                bloco.append(Spacer(1, 5.2 * mm))
                bloco.append(HRFlowable(width="100%", thickness=0.4, color=colors.HexColor("#777")))
        bloco.append(Spacer(1, 5 * mm))
        # questões curtas ficam inteiras na página; longas podem quebrar
        story.append(KeepTogether(bloco) if len(bloco) < 22 else bloco[0])
        if len(bloco) >= 22:
            story += bloco[1:]

    # Cartão-resposta para múltipla escolha (se houver ≥ 5)
    me = [i for i, q in enumerate(ativ.get("questoes") or [], 1) if q.get("tipo") == "me"]
    if len(me) >= 5:
        story.append(Spacer(1, 3 * mm))
        linhas = [[Paragraph("<b>Nº</b>", st_cab)] + [Paragraph(f"<b>{L}</b>", ParagraphStyle("x", parent=st_cab, alignment=TA_CENTER)) for L in LETRAS]]
        for i in me:
            linhas.append([Paragraph(f"{i:02d}", st_cab)] + [Paragraph(f"({L})", ParagraphStyle("y", parent=st_cab, alignment=TA_CENTER)) for L in LETRAS])
        # duas colunas de cartão se muitas questões
        cw = [12 * mm] + [11 * mm] * 5
        cart = Table(linhas, colWidths=cw)
        cart.setStyle(grade)
        story.append(KeepTogether([Paragraph("<b>CARTÃO-RESPOSTA (múltipla escolha)</b>", st_cab), Spacer(1, 2), cart]))

    def rodape(canvas, d):
        canvas.saveState()
        canvas.setFont(FONT, 8)
        canvas.setFillColor(colors.grey)
        canvas.drawString(d.leftMargin, 8 * mm, f"{meta.get('disciplina','')} · {meta.get('serie','')} · {ativ.get('titulo','')}"[:110])
        canvas.drawRightString(A4[0] - d.rightMargin, 8 * mm, f"Página {d.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=rodape, onLaterPages=rodape)
    return buf.getvalue()


def gerar_pdf_gabarito(ativ: dict, meta: dict) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm,
                            topMargin=12 * mm, bottomMargin=15 * mm,
                            title=f"Gabarito - {ativ.get('titulo') or 'Atividade'}", author="Escola Presidente Bernardes")
    largura = A4[0] - doc.leftMargin - doc.rightMargin
    story: list = []
    _cabecalho(story, {"titulo": f"GABARITO – {ativ.get('titulo','')}"}, largura,
               f"{meta.get('tipo_nome','')} · {meta.get('disciplina','')} · {meta.get('serie','')} · Prof. {meta.get('professor','')} · uso exclusivo do professor")

    qs = ativ.get("questoes") or []
    avaliativa = bool(meta.get("avaliativa"))
    # Quadro-resumo
    me = [(i, q) for i, q in enumerate(qs, 1) if q.get("tipo") == "me"]
    if me:
        cab = [Paragraph("<b>Questão</b>", st_gab), Paragraph("<b>Resposta</b>", st_gab)] + ([Paragraph("<b>Valor</b>", st_gab)] if avaliativa else [])
        linhas = [cab]
        for i, q in me:
            linhas.append([Paragraph(f"{i:02d}", st_gab), Paragraph(f"<b>{LETRAS[int(q.get('correta', 0))]}</b>", st_gab)]
                          + ([Paragraph(_fmt_valor(q.get("valor")), st_gab)] if avaliativa else []))
        # divide em até 3 colunas de tabela para caber
        n_col = 3 if len(linhas) > 12 else (2 if len(linhas) > 6 else 1)
        por_col = -(-(len(linhas) - 1) // n_col)
        blocos = []
        for c in range(n_col):
            parte = [cab] + linhas[1 + c * por_col: 1 + (c + 1) * por_col]
            if len(parte) > 1:
                t = Table(parte, colWidths=[22 * mm, 22 * mm] + ([18 * mm] if avaliativa else []))
                t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.black), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e6e6e6")),
                                       ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
                blocos.append(t)
        wrap = Table([blocos], colWidths=[largura / len(blocos)] * len(blocos))
        wrap.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
        story += [Paragraph("<b>QUADRO DE RESPOSTAS – MÚLTIPLA ESCOLHA</b>", st_gab), Spacer(1, 2), wrap, Spacer(1, 5 * mm)]

    # Detalhamento
    story.append(Paragraph("<b>RESOLUÇÕES E CRITÉRIOS DE CORREÇÃO</b>", st_gab))
    story.append(Spacer(1, 2))
    for i, q in enumerate(qs, 1):
        bloco = []
        t = f"QUESTÃO {i:02d}"
        if avaliativa and q.get("valor") is not None:
            t += f" — {_fmt_valor(q['valor'])} pt"
        if q.get("habilidade"):
            t += f" — {q['habilidade']}"
        bloco.append(Paragraph(_esc(t), st_gab_b))
        enun = (q.get("enunciado") or "").strip().replace("\n", " ")
        bloco.append(Paragraph(_esc(enun[:220] + ("…" if len(enun) > 220 else "")), ParagraphStyle("e", parent=st_gab, textColor=colors.HexColor("#555"), fontSize=9, leading=12)))
        if q.get("tipo") == "me":
            c = int(q.get("correta", 0))
            alts = q.get("alternativas") or []
            bloco.append(Paragraph(f"<b>Resposta: {LETRAS[c]}</b> — {_esc(alts[c] if c < len(alts) else '')}", st_gab))
            if q.get("resolucao"):
                bloco += _paragrafos("Resolução: " + q["resolucao"], st_gab)
        else:
            if q.get("resposta"):
                bloco += _paragrafos("Resposta esperada: " + q["resposta"], st_gab)
            if q.get("criterios"):
                bloco.append(Paragraph("<b>Critérios de correção:</b>", st_gab))
                for l in str(q["criterios"]).split("\n"):
                    if l.strip():
                        l = l.strip()
                        bloco.append(Paragraph(_esc(l if l.startswith("•") else "• " + l), st_inst))
        bloco.append(Spacer(1, 4 * mm))
        story.append(KeepTogether(bloco) if len(bloco) < 15 else bloco[0])
        if len(bloco) >= 15:
            story += bloco[1:]

    if avaliativa:
        total = sum(float(q.get("valor") or 0) for q in qs)
        story.append(Paragraph(f"<b>Total: {_fmt_valor(total)} pontos</b>", st_gab))

    def rodape(canvas, d):
        canvas.saveState()
        canvas.setFont(FONT, 8)
        canvas.setFillColor(colors.grey)
        canvas.drawString(d.leftMargin, 8 * mm, "GABARITO — uso exclusivo do professor")
        canvas.drawRightString(A4[0] - d.rightMargin, 8 * mm, f"Página {d.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=rodape, onLaterPages=rodape)
    return buf.getvalue()


# --------------------------------------------------------------------------- #
# Folha de acesso (código + QR) e relatório de resultado
# --------------------------------------------------------------------------- #
def gerar_pdf_folha_acesso(titulo: str, meta: dict, codigo: str, link: str, turma: str = "") -> bytes:
    import segno
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=18 * mm, bottomMargin=15 * mm,
                            title=f"Acesso à prova {codigo}")
    largura = A4[0] - doc.leftMargin - doc.rightMargin
    story: list = []
    _cabecalho(story, {"titulo": titulo}, largura, f"{meta.get('tipo_nome','')} · {meta.get('disciplina','')} · {turma or meta.get('serie','')} · Prof. {meta.get('professor','')}")
    story.append(Spacer(1, 8 * mm))
    st_big = ParagraphStyle("big", fontName=FONT_B, fontSize=54, leading=62, alignment=TA_CENTER, textColor=colors.HexColor("#e10600"))
    st_med = ParagraphStyle("med", fontName=FONT, fontSize=14, leading=18, alignment=TA_CENTER)
    st_link = ParagraphStyle("lnk", fontName=FONT_B, fontSize=16, leading=20, alignment=TA_CENTER, textColor=colors.HexColor("#1F4E79"))
    story.append(Paragraph("CÓDIGO DA PROVA", st_med))
    story.append(Paragraph(_esc(codigo), st_big))
    story.append(Spacer(1, 6 * mm))
    qr = BytesIO()
    segno.make(link, error="m").save(qr, kind="png", scale=10, border=1)
    qr.seek(0)
    img = Image(qr, width=70 * mm, height=70 * mm)
    img.hAlign = "CENTER"
    story += [img, Spacer(1, 5 * mm)]
    story.append(Paragraph("Aponte a câmera do celular para o QR code ou acesse:", st_med))
    story.append(Paragraph(_esc(link), st_link))
    story.append(Spacer(1, 10 * mm))
    passos = ["Abra o link (ou leia o QR code).", "Digite seu nome completo e seu número da chamada.",
              "Responda com calma. Você pode voltar às questões antes de enviar.", "Clique em ENVIAR ao terminar. Só é possível enviar uma vez."]
    for i, ptxt in enumerate(passos, 1):
        story.append(Paragraph(f"<b>{i}.</b> {_esc(ptxt)}", ParagraphStyle("p", parent=st_med, alignment=0, leftIndent=40)))
    doc.build(story)
    return buf.getvalue()


def gerar_pdf_relatorio(item: dict, ap: dict, respostas: list[dict], est: dict) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm, topMargin=12 * mm, bottomMargin=15 * mm,
                            title="Resultado da prova")
    largura = A4[0] - doc.leftMargin - doc.rightMargin
    meta = {"tipo_nome": "Resultado", "disciplina": item["params"].get("disciplina", ""), "serie": ap.get("turma") or item["params"].get("serie", ""),
            "professor": item["params"].get("professor", "")}
    story: list = []
    _cabecalho(story, {"titulo": f"RESULTADO – {item['conteudo'].get('titulo','')}"}, largura,
               f"{meta['disciplina']} · {meta['serie']} · Prof. {meta['professor']} · código {ap['codigo']}")
    grade = TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.black), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e6e6e6")),
                        ("FONTNAME", (0, 0), (-1, 0), FONT_B), ("FONTSIZE", (0, 0), (-1, -1), 9),
                        ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")])
    fmt = lambda v: "" if v is None else _fmt_valor(v)  # noqa: E731
    # resumo
    res = Table([["Respostas", "Corrigidas", "Média", "Maior", "Menor", "Abaixo de 60%"],
                 [est["n_respostas"], est["n_corrigidas"], fmt(est["media"]), fmt(est["maior"]), fmt(est["menor"]), est["abaixo_media"]]],
                colWidths=[largura / 6] * 6)
    res.setStyle(grade)
    story += [res, Spacer(1, 4 * mm)]
    f = est["faixas"]
    story.append(Paragraph(f"<b>Distribuição:</b> abaixo de 50%: {f[0]} · 50–70%: {f[1]} · 70–90%: {f[2]} · 90% ou mais: {f[3]}", st_gab))
    story.append(Spacer(1, 4 * mm))
    # notas por aluno
    story.append(Paragraph("<b>NOTAS POR ESTUDANTE</b>", st_gab))
    linhas = [["Nº", "Estudante", "Acertos ME", "Nota ME", "Nota disc.", "NOTA", "Situação"]]
    sit = {"corrigido": "Corrigida", "revisar": "Revisar", "pendente": "Pendente"}
    for r in respostas:
        c = r.get("correcao") or {}
        linhas.append([r.get("aluno_numero") or "", Paragraph(_esc(r.get("aluno_nome", "")), st_gab),
                       f"{c.get('acertos_me','')}/{c.get('total_me','')}" if c else "", fmt(r.get("nota_me")), fmt(r.get("nota_disc")),
                       fmt(r.get("nota")), sit.get(r.get("status"), "")])
    t = Table(linhas, colWidths=[12 * mm, largura - 12 * mm - 5 * 22 * mm, 22 * mm, 22 * mm, 22 * mm, 22 * mm, 22 * mm], repeatRows=1)
    t.setStyle(grade)
    story += [t, Spacer(1, 5 * mm)]
    # por questão
    story.append(Paragraph("<b>DESEMPENHO POR QUESTÃO</b>", st_gab))
    linhas = [["Q", "Tipo", "Habilidade", "% acerto", "Gab.", "A", "B", "C", "D", "E"]]
    for x in est["por_questao"]:
        d = x.get("distribuicao") or ["", "", "", "", ""]
        linhas.append([x["i"] + 1, "ME" if x["tipo"] == "me" else "Disc.", x["habilidade"], f"{x['pct']}%" if x["pct"] is not None else "",
                       "ABCDE"[x["correta"]] if x["tipo"] == "me" and x.get("correta") is not None else "", *d])
    t = Table(linhas, colWidths=[10 * mm, 14 * mm, 32 * mm, 20 * mm, 14 * mm] + [12 * mm] * 5, repeatRows=1)
    t.setStyle(grade)
    story += [t, Spacer(1, 4 * mm)]
    if est["mais_erradas"]:
        story.append(Paragraph("<b>QUESTÕES COM MENOR ACERTO (retomar em sala):</b>", st_gab))
        for x in est["mais_erradas"]:
            story.append(Paragraph(_esc(f"• Q{x['i']+1} ({x['pct']}%) — {x['enunciado']}"), st_inst))
    if est["habilidades"]:
        story.append(Spacer(1, 3 * mm))
        story.append(Paragraph("<b>POR HABILIDADE (BNCC):</b>", st_gab))
        for h in est["habilidades"]:
            story.append(Paragraph(_esc(f"• {h['habilidade']}: {h['pct']}% de acerto (questões {', '.join(map(str, h['questoes']))})"), st_inst))

    def rodape(canvas, d):
        canvas.saveState(); canvas.setFont(FONT, 8); canvas.setFillColor(colors.grey)
        canvas.drawRightString(A4[0] - d.rightMargin, 8 * mm, f"Página {d.page}"); canvas.restoreState()
    doc.build(story, onFirstPage=rodape, onLaterPages=rodape)
    return buf.getvalue()
