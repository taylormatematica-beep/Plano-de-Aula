"""
Cartão-resposta de papel com leitura óptica (OMR) a partir de uma foto de celular.

  gerar_cartao_pdf(...)  -> PDF A4 com 4 marcas de canto, campo de nome, bolhas do nº da chamada e bolhas A–E.
  ler_cartao(bytes)      -> {"numero": "12", "respostas": {pos: k}, "duvidas": [...], "recorte_nome": png_b64, ...}

O layout é calculado em milímetros pelas mesmas funções nos dois lados (impressão e leitura),
então qualquer mudança aqui vale para ambos.
"""
import base64
from io import BytesIO

import numpy as np

# ------------------------------------------------------------------ layout (mm, origem no canto superior esquerdo)
PAG_W, PAG_H = 210.0, 297.0
FID = 8.0                                   # lado da marca de canto
FIDS = [(15.0, 15.0), (195.0, 15.0), (15.0, 282.0), (195.0, 282.0)]   # centros TL, TR, BL, BR
ORI = (27.0, 13.0, 12.0, 4.0)               # marcador de orientação (x, y, w, h) — só existe perto do canto superior esquerdo
NOME_BOX = (15.0, 34.0, 125.0, 12.0)        # x, y, w, h
NUM_BOX = (145.0, 34.0, 50.0, 12.0)
NUM_COLS_X = (165.0, 180.0)                 # dezena, unidade
NUM_Y0, NUM_PITCH, NUM_R = 60.0, 6.0, 2.0   # bolhas de 0 a 9
Q_BLOCOS_X = (35.0, 110.0)                  # x da coluna A de cada bloco
Q_Y0, Q_PITCH, Q_R = 60.0, 7.0, 2.25        # linhas das questões
Q_COL_PITCH = 9.0                           # distância entre A, B, C, D, E
Q_POR_BLOCO = 25
SCALE = 4                                   # px por mm na imagem normalizada
LETRAS = "ABCDE"


def _pos_questao(pos: int) -> tuple[float, float]:
    """Centro (mm) da bolha A da questão `pos` (0-based)."""
    bloco, linha = divmod(pos, Q_POR_BLOCO)
    return Q_BLOCOS_X[min(bloco, 1)], Q_Y0 + linha * Q_PITCH


def posicoes_bolhas(n_me: int) -> list[list[tuple[float, float]]]:
    out = []
    for pos in range(n_me):
        x0, y = _pos_questao(pos)
        out.append([(x0 + k * Q_COL_PITCH, y) for k in range(5)])
    return out


def posicoes_numero() -> list[list[tuple[float, float]]]:
    return [[(x, NUM_Y0 + d * NUM_PITCH) for d in range(10)] for x in NUM_COLS_X]


# ------------------------------------------------------------------ PDF
def gerar_cartao_pdf(titulo: str, subtitulo: str, codigo: str, n_me: int, copias: int = 1,
                     nomes: list[str] | None = None, logo_path=None) -> bytes:
    """Um cartão por página. Se `nomes` for informado, gera um cartão pré-preenchido por nome (ignora `copias`)."""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas as rl_canvas

    n_me = max(1, min(n_me, Q_POR_BLOCO * 2))
    buf = BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=A4)
    c.setTitle(f"Cartão-resposta {codigo}")
    mm = 72 / 25.4

    def X(x):
        return x * mm

    def Y(y):
        return (PAG_H - y) * mm

    paginas = nomes if nomes else [None] * max(1, min(copias, 60))
    for pag, nome_pre in enumerate(paginas):
        # marcas de canto
        c.setFillGray(0)
        for fx, fy in FIDS:
            c.rect(X(fx - FID / 2), Y(fy + FID / 2), FID * mm, FID * mm, stroke=0, fill=1)
        ox, oy, ow, oh = ORI
        c.rect(X(ox), Y(oy + oh), ow * mm, oh * mm, stroke=0, fill=1)
        # cabeçalho
        if logo_path and str(logo_path) and __import__("os").path.exists(str(logo_path)):
            try:
                c.drawImage(str(logo_path), X(150), Y(29), width=40 * mm, height=11 * mm, preserveAspectRatio=True, mask="auto", anchor="ne")
            except Exception:  # noqa: BLE001
                pass
        c.setFont("Helvetica-Bold", 11)
        c.drawString(X(45), Y(21), (f"CARTÃO-RESPOSTA — {titulo}")[:60])
        c.setFont("Helvetica", 8.5)
        c.drawString(X(45), Y(26), (f"{subtitulo} · código {codigo} · Q1–Q{n_me}")[:100])
        # campos nome / número
        for (bx, by, bw, bh), rot in ((NOME_BOX, "NOME:"), (NUM_BOX, "Nº DA CHAMADA:")):
            c.setLineWidth(0.6)
            c.rect(X(bx), Y(by + bh), bw * mm, bh * mm, stroke=1, fill=0)
            c.setFont("Helvetica-Bold", 7)
            c.drawString(X(bx + 1.5), Y(by + 3), rot)
        if nome_pre:
            c.setFont("Helvetica", 11)
            c.drawString(X(NOME_BOX[0] + 3), Y(NOME_BOX[1] + 9.5), str(nome_pre)[:48])
        # bolhas do número
        c.setFont("Helvetica-Bold", 7)
        c.drawString(X(NUM_COLS_X[0] - 12), Y(NUM_Y0 - 5), "Nº (preencha):")
        c.setFont("Helvetica", 6)
        c.drawCentredString(X(NUM_COLS_X[0]), Y(NUM_Y0 - 5), "dezena")
        c.drawCentredString(X(NUM_COLS_X[1]), Y(NUM_Y0 - 5), "unidade")
        c.setLineWidth(0.5)
        for col in posicoes_numero():
            for d, (x, y) in enumerate(col):
                c.circle(X(x), Y(y), NUM_R * mm, stroke=1, fill=0)
                c.setFont("Helvetica", 5.5)
                c.drawCentredString(X(x), Y(y) - 2, str(d))
        # bolhas das questões
        c.setFont("Helvetica-Bold", 8)
        for bloco in range(2 if n_me > Q_POR_BLOCO else 1):
            x0 = Q_BLOCOS_X[bloco]
            for k, L in enumerate(LETRAS):
                c.drawCentredString(X(x0 + k * Q_COL_PITCH), Y(Q_Y0 - 5.5), L)
        for pos, linha in enumerate(posicoes_bolhas(n_me)):
            x0, y = linha[0]
            c.setFont("Helvetica-Bold", 8)
            c.drawRightString(X(x0 - 6.5), Y(y) - 2.5, f"{pos + 1:02d}")
            if pos % 5 == 4 and pos < n_me - 1:            # leve separação a cada 5
                pass
            for (x, yy) in linha:
                c.circle(X(x), Y(yy), Q_R * mm, stroke=1, fill=0)
        # instruções
        yi = 240.0
        c.setFont("Helvetica-Bold", 8)
        c.drawString(X(15), Y(yi), "INSTRUÇÕES")
        c.setFont("Helvetica", 7.5)
        for i, t in enumerate([
            "Use caneta preta ou azul. Preencha a bolha por completo, sem ultrapassar a borda:",
            "Marque só UMA alternativa por questão. Não rasure: questão com duas marcas será anulada.",
            "Preencha também as bolhas do seu número da chamada (dezena e unidade) e escreva seu nome.",
            "Não dobre, não amasse e não escreva sobre os quadrados pretos dos cantos.",
        ]):
            c.drawString(X(15), Y(yi + 5 + i * 4.2), t)
        # exemplo de bolhas
        ex_y = yi + 5 - 0.7
        c.circle(X(118), Y(ex_y), 2.1 * mm, stroke=1, fill=1)
        c.setFont("Helvetica", 6.5)
        c.drawString(X(121), Y(ex_y) - 2, "certo")
        c.circle(X(134), Y(ex_y), 2.1 * mm, stroke=1, fill=0)
        c.line(X(132.6), Y(ex_y - 1.4), X(135.4), Y(ex_y + 1.4))
        c.drawString(X(137), Y(ex_y) - 2, "errado")
        c.circle(X(151), Y(ex_y), 2.1 * mm, stroke=1, fill=0)
        c.circle(X(151), Y(ex_y), 0.8 * mm, stroke=0, fill=1)
        c.drawString(X(154), Y(ex_y) - 2, "errado")
        c.setFont("Helvetica", 6)
        c.setFillGray(0.4)
        c.drawString(X(15), Y(270), f"Assistente de Plano de Aula · cartão {codigo} · as questões correspondem às de múltipla escolha, na ordem da prova.")
        c.setFillGray(0)
        c.showPage()
    c.save()
    return buf.getvalue()


# ------------------------------------------------------------------ leitura
class LeituraFalhou(Exception):
    pass


def _carregar(img_bytes: bytes):
    import cv2
    arr = np.frombuffer(img_bytes, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise LeituraFalhou("Não consegui abrir a imagem. Envie uma foto JPG ou PNG.")
    h, w = img.shape[:2]
    m = max(h, w)
    if m > 2000:
        f = 2000 / m
        img = cv2.resize(img, (int(w * f), int(h * f)), interpolation=cv2.INTER_AREA)
    return img


def _achar_fiduciais(gray):
    """Devolve os centros das 4 marcas de canto (quadrados pretos cheios) ou None."""
    import cv2
    h, w = gray.shape
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    thr = cv2.adaptiveThreshold(blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 51, 15)
    thr = cv2.morphologyEx(thr, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    contornos, _ = cv2.findContours(thr, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    area_img = h * w
    cands = []
    for ct in contornos:
        a = cv2.contourArea(ct)
        if a < area_img * 0.00015 or a > area_img * 0.01:
            continue
        x, y, bw, bh = cv2.boundingRect(ct)
        if bw == 0 or bh == 0:
            continue
        aspecto = bw / bh
        if not 0.6 < aspecto < 1.6:
            continue
        preench = a / (bw * bh)
        if preench < 0.7:
            continue
        # tem que ser realmente escuro por dentro
        roi = gray[y:y + bh, x:x + bw]
        if roi.mean() > 110:
            continue
        cands.append((x + bw / 2, y + bh / 2, a))
    if len(cands) < 4:
        return None
    # escolhe, para cada canto da imagem, o candidato mais próximo (entre os maiores)
    cands.sort(key=lambda c: -c[2])
    cands = cands[:40]
    cantos = [(0, 0), (w, 0), (0, h), (w, h)]
    esc = []
    usados = set()
    for cx, cy in cantos:
        melhor = None
        for i, (x, y, a) in enumerate(cands):
            if i in usados:
                continue
            d = (x - cx) ** 2 + (y - cy) ** 2
            if melhor is None or d < melhor[0]:
                melhor = (d, i)
        if melhor is None:
            return None
        usados.add(melhor[1])
        esc.append(cands[melhor[1]][:2])
    # sanidade: quadrilátero grande
    xs = [p[0] for p in esc]; ys = [p[1] for p in esc]
    if (max(xs) - min(xs)) < w * 0.4 or (max(ys) - min(ys)) < h * 0.4:
        return None
    return np.array(esc, dtype=np.float32)   # TL, TR, BL, BR


def _normalizar(gray, pts):
    """Corrige perspectiva: devolve imagem onde 1 mm = SCALE px e a origem é o canto (0,0) mm da folha."""
    import cv2
    W, H = int(PAG_W * SCALE), int(PAG_H * SCALE)
    dst = np.array([[x * SCALE, y * SCALE] for x, y in FIDS], dtype=np.float32)
    M = cv2.getPerspectiveTransform(pts, dst)
    return cv2.warpPerspective(gray, M, (W, H), flags=cv2.INTER_AREA, borderValue=255)


def _escuridao(binimg, x_mm, y_mm, r_mm):
    """Fração de pixels 'marcados' dentro do círculo (usa raio interno para ignorar a borda impressa)."""
    r = max(2, int(r_mm * SCALE * 0.72))
    cx, cy = int(x_mm * SCALE), int(y_mm * SCALE)
    y0, y1, x0, x1 = cy - r, cy + r + 1, cx - r, cx + r + 1
    if y0 < 0 or x0 < 0 or y1 > binimg.shape[0] or x1 > binimg.shape[1]:
        return 0.0
    roi = binimg[y0:y1, x0:x1]
    yy, xx = np.ogrid[-r:r + 1, -r:r + 1]
    mask = xx * xx + yy * yy <= r * r
    return float((roi[mask] > 0).mean())


def _orientacao_ok(binimg) -> bool:
    ox, oy, ow, oh = ORI
    roi = binimg[int((oy + 0.8) * SCALE):int((oy + oh - 0.8) * SCALE), int((ox + 1) * SCALE):int((ox + ow - 1) * SCALE)]
    return roi.size > 0 and (roi > 0).mean() > 0.6


def _binarizar(norm):
    import cv2
    blur = cv2.GaussianBlur(norm, (3, 3), 0)
    return cv2.adaptiveThreshold(blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 41, 12)


def _decidir(vals: list[float]) -> tuple[int | None, str]:
    """vals = escuridão de cada opção. Devolve (índice ou None, motivo: ''|'branco'|'dupla'|'fraca')."""
    ordem = sorted(range(len(vals)), key=lambda i: -vals[i])
    a, b = vals[ordem[0]], vals[ordem[1]] if len(vals) > 1 else 0.0
    if a < 0.22:
        return None, "branco"
    if b >= 0.35 and b >= 0.55 * a:
        return None, "dupla"
    if a < 0.40:
        return ordem[0], "fraca"
    return ordem[0], ""


def ler_cartao(img_bytes: bytes, n_me: int) -> dict:
    import cv2
    img = _carregar(img_bytes)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    pts = _achar_fiduciais(gray)
    if pts is None:
        raise LeituraFalhou("Não encontrei os 4 quadrados pretos dos cantos. Fotografe o cartão inteiro, de frente, "
                            "com boa luz e sem cortar as bordas.")
    # tenta as 4 orientações (foto de cabeça para baixo / deitada)
    ordens = [(0, 1, 2, 3), (3, 2, 1, 0), (1, 3, 0, 2), (2, 0, 3, 1)]
    norm = binimg = None
    for o in ordens:
        cand = _normalizar(gray, pts[list(o)])
        b = _binarizar(cand)
        if _orientacao_ok(b):
            norm, binimg = cand, b
            break
    if norm is None:
        raise LeituraFalhou("Encontrei os cantos, mas não consegui confirmar a orientação do cartão. "
                            "Tente uma foto mais nítida e de frente.")
    # número da chamada
    numero = ""
    num_duvida = False
    for col in posicoes_numero():
        vals = [_escuridao(binimg, x, y, NUM_R) for (x, y) in col]
        d, motivo = _decidir(vals)
        if d is None:
            numero += "" if motivo == "branco" else "?"
            num_duvida = num_duvida or motivo != "branco"
        else:
            numero += str(d)
    numero = numero.lstrip("0") if numero and "?" not in numero else numero
    # respostas
    respostas, duvidas, detalhes = {}, [], []
    for pos, linha in enumerate(posicoes_bolhas(n_me)):
        vals = [_escuridao(binimg, x, y, Q_R) for (x, y) in linha]
        k, motivo = _decidir(vals)
        if k is not None:
            respostas[pos] = k
        if motivo in ("dupla", "fraca"):
            duvidas.append({"pos": pos, "motivo": motivo, "vals": [round(v, 2) for v in vals]})
        detalhes.append(k)
    # recorte do campo de nome (para o professor conferir/digitar)
    bx, by, bw, bh = NOME_BOX
    rec = norm[int(by * SCALE):int((by + bh) * SCALE), int(bx * SCALE):int((bx + bw) * SCALE)]
    ok, png = cv2.imencode(".png", rec)
    recorte = base64.b64encode(png.tobytes()).decode() if ok else ""
    # miniatura com as leituras desenhadas (conferência visual)
    vis = cv2.cvtColor(norm, cv2.COLOR_GRAY2BGR)
    for pos, linha in enumerate(posicoes_bolhas(n_me)):
        k = detalhes[pos]
        for j, (x, y) in enumerate(linha):
            if k == j:
                cv2.circle(vis, (int(x * SCALE), int(y * SCALE)), int(Q_R * SCALE) + 3, (0, 170, 0), 2)
        if any(d["pos"] == pos for d in duvidas):
            x0, y = linha[0]
            cv2.rectangle(vis, (int((x0 - 5) * SCALE), int((y - 3.2) * SCALE)), (int((linha[-1][0] + 4) * SCALE), int((y + 3.2) * SCALE)), (0, 0, 255), 2)
    vis = cv2.resize(vis, (int(PAG_W * 2), int(PAG_H * 2)), interpolation=cv2.INTER_AREA)
    ok, jpg = cv2.imencode(".jpg", vis, [cv2.IMWRITE_JPEG_QUALITY, 70])
    miniatura = base64.b64encode(jpg.tobytes()).decode() if ok else ""
    return {"numero": numero, "numero_duvida": num_duvida, "respostas": respostas, "duvidas": duvidas,
            "letras": "".join(LETRAS[respostas[p]] if p in respostas else "-" for p in range(n_me)),
            "recorte_nome": recorte, "miniatura": miniatura}
