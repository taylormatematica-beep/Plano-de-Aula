"""
Correção de provas/atividades.
  - Múltipla escolha: comparação direta com o gabarito (instantânea, 100% determinística).
  - Discursivas: a IA compara a resposta do aluno com a resposta esperada e os critérios,
    sugere nota e comentário; o professor confirma ou ajusta.
"""
import json
from concurrent.futures import ThreadPoolExecutor

import gerador

LETRAS = "ABCDE"

SYSTEM_CORRECAO = """Você é um professor experiente de Ensino Médio corrigindo questões discursivas com justiça e consistência.
Compare a resposta do estudante com a resposta esperada e os critérios de correção. Aceite formulações diferentes que estejam corretas.
Seja rigoroso com erros conceituais e generoso com a forma de escrever. Resposta em branco ou sem relação com a pergunta = nota 0.
Escreva o comentário em português do Brasil, diretamente para o estudante, em até 2 frases, apontando o que acertou e o que faltou.
Responda EXCLUSIVAMENTE com um objeto JSON válido, sem markdown."""

PROMPT_CORRECAO = """QUESTÃO: {enunciado}

RESPOSTA ESPERADA: {resposta}

CRITÉRIOS DE CORREÇÃO: {criterios}

VALOR DA QUESTÃO: {valor} pontos

RESPOSTA DO ESTUDANTE: {aluno}

Avalie e devolva:
{{"nota": número entre 0 e {valor} (use até 1 casa decimal), "percentual": 0 a 100, "comentario": "feedback curto ao estudante", "confianca": "alta" | "media" | "baixa"}}
"confianca" = quão seguro você está da nota (baixa quando a resposta é ambígua, ilegível ou parcialmente fora do tema)."""


def _valor(q: dict, avaliativa: bool) -> float:
    if not avaliativa:
        return 1.0
    try:
        return float(q.get("valor") or 0)
    except (TypeError, ValueError):
        return 0.0


def corrigir_me(questoes: list[dict], respostas: dict, avaliativa: bool) -> tuple[list[dict], float, float]:
    """Devolve (itens, nota_obtida, nota_possivel) só das questões de múltipla escolha."""
    itens, obtida, possivel = [], 0.0, 0.0
    for i, q in enumerate(questoes):
        if q.get("tipo") != "me":
            continue
        v = _valor(q, avaliativa)
        marcada = respostas.get(str(i))
        try:
            marcada = int(marcada) if marcada is not None and str(marcada) != "" else None
        except (TypeError, ValueError):
            marcada = LETRAS.find(str(marcada).strip().upper()[:1]) if marcada else None
            marcada = None if marcada is not None and marcada < 0 else marcada
        correta = int(q.get("correta", 0))
        acertou = marcada == correta
        itens.append({"i": i, "tipo": "me", "marcada": marcada, "correta": correta, "acertou": acertou,
                      "valor": v, "nota": v if acertou else 0.0, "origem": "auto"})
        possivel += v
        obtida += v if acertou else 0.0
    return itens, round(obtida, 2), round(possivel, 2)


def _corrigir_disc_ia(cfg: dict, q: dict, texto: str, valor: float) -> dict:
    if not (texto or "").strip():
        return {"nota": 0.0, "percentual": 0, "comentario": "Questão não respondida.", "confianca": "alta"}
    if not cfg.get("api_key"):
        return {"nota": None, "percentual": None, "comentario": "IA não configurada — corrija manualmente.", "confianca": "baixa"}
    prompt = PROMPT_CORRECAO.format(
        enunciado=(q.get("enunciado") or "")[:1500], resposta=(q.get("resposta") or "não informada")[:1200],
        criterios=(q.get("criterios") or "avalie correção conceitual, completude e clareza")[:800],
        valor=valor, aluno=texto.strip()[:2500])
    try:
        obj = gerador._pedir_json(cfg, prompt, SYSTEM_CORRECAO, 600)
        nota = float(str(obj.get("nota", 0)).replace(",", "."))
        nota = max(0.0, min(valor, round(nota, 1)))
        return {"nota": nota, "percentual": int(obj.get("percentual") or round(100 * nota / valor if valor else 0)),
                "comentario": str(obj.get("comentario") or "")[:400], "confianca": str(obj.get("confianca") or "media")}
    except Exception as e:  # noqa: BLE001
        return {"nota": None, "percentual": None, "comentario": f"Não foi possível corrigir com IA ({str(e)[:80]}). Corrija manualmente.",
                "confianca": "baixa"}


def corrigir_disc(questoes: list[dict], respostas: dict, avaliativa: bool, usar_ia: bool = True,
                  anteriores: dict | None = None) -> list[dict]:
    """Discursivas. `anteriores` = {i: item} já corrigidos/confirmados pelo professor (mantidos)."""
    anteriores = anteriores or {}
    cfg = gerador.carregar_config() if usar_ia else {"api_key": ""}
    pend = []
    itens = []
    for i, q in enumerate(questoes):
        if q.get("tipo") != "disc":
            continue
        v = _valor(q, avaliativa)
        texto = str(respostas.get(str(i)) or "")
        ant = anteriores.get(i) or anteriores.get(str(i))
        if ant and ant.get("origem") == "professor":
            item = dict(ant, i=i, valor=v, texto=texto)
            itens.append(item)
            continue
        item = {"i": i, "tipo": "disc", "texto": texto, "valor": v, "nota": None, "comentario": "", "confianca": "", "origem": "ia"}
        itens.append(item)
        pend.append((item, q, texto, v))
    if pend:
        with ThreadPoolExecutor(max_workers=min(5, len(pend))) as ex:
            resultados = list(ex.map(lambda t: _corrigir_disc_ia(cfg, t[1], t[2], t[3]), pend))
        for (item, *_), r in zip(pend, resultados):
            item.update(nota=r["nota"], comentario=r["comentario"], confianca=r["confianca"], percentual=r.get("percentual"))
    return itens


def consolidar(questoes: list[dict], itens_me: list[dict], itens_disc: list[dict], avaliativa: bool) -> dict:
    """Monta o objeto de correção final + notas."""
    possivel_me = sum(x["valor"] for x in itens_me)
    possivel_disc = sum(x["valor"] for x in itens_disc)
    nota_me = sum(x["nota"] for x in itens_me)
    disc_ok = all(x["nota"] is not None for x in itens_disc)
    nota_disc = sum(x["nota"] or 0 for x in itens_disc)
    total_possivel = possivel_me + possivel_disc
    nota = nota_me + nota_disc
    if not avaliativa and total_possivel:           # não avaliativa: nota = % de acerto (0-10)
        nota = 10 * nota / total_possivel
        nota_me = 10 * nota_me / total_possivel if possivel_me else 0
        nota_disc = 10 * nota_disc / total_possivel if possivel_disc else 0
    status = "corrigido" if disc_ok else "revisar"
    if itens_disc and any(x.get("origem") == "ia" and x.get("confianca") == "baixa" for x in itens_disc):
        status = "revisar"
    acertos = sum(1 for x in itens_me if x["acertou"])
    return {
        "itens": sorted(itens_me + itens_disc, key=lambda x: x["i"]),
        "acertos_me": acertos, "total_me": len(itens_me), "total_disc": len(itens_disc),
        "possivel": round(total_possivel, 2), "nota": round(nota, 2), "nota_me": round(nota_me, 2),
        "nota_disc": round(nota_disc, 2), "status": status,
    }


def corrigir(atividade: dict, respostas: dict, usar_ia: bool = True, anteriores: dict | None = None) -> dict:
    questoes = atividade["conteudo"].get("questoes") or []
    avaliativa = bool(atividade["params"].get("avaliativa"))
    me, _, _ = corrigir_me(questoes, respostas, avaliativa)
    disc = corrigir_disc(questoes, respostas, avaliativa, usar_ia, anteriores)
    return consolidar(questoes, me, disc, avaliativa)


def aplicar_ajuste_professor(correcao: dict, i: int, nota: float, comentario: str | None, questoes: list[dict], avaliativa: bool) -> dict:
    """Professor altera a nota de uma questão (discursiva ou até ME, em caso de anulação)."""
    itens = correcao.get("itens") or []
    for it in itens:
        if it["i"] == i:
            it["nota"] = max(0.0, min(float(it["valor"]), float(nota)))
            if comentario is not None:
                it["comentario"] = comentario[:400]
            it["origem"] = "professor"
            it["confianca"] = "alta"
    me = [x for x in itens if x["tipo"] == "me"]
    disc = [x for x in itens if x["tipo"] == "disc"]
    novo = consolidar(questoes, me, disc, avaliativa)
    if all(x.get("origem") in ("professor", "auto") or x.get("confianca") != "baixa" for x in disc) and all(x["nota"] is not None for x in disc):
        novo["status"] = "corrigido"
    return novo


def estatisticas(atividade: dict, respostas: list[dict]) -> dict:
    """Média, distribuição, % de acerto por questão e por habilidade, questões mais erradas."""
    questoes = atividade["conteudo"].get("questoes") or []
    corrigidas = [r for r in respostas if r.get("correcao")]
    n = len(corrigidas)
    por_q = []
    for i, q in enumerate(questoes):
        acertos = 0.0
        cont = 0
        dist = [0] * 5
        for r in corrigidas:
            it = next((x for x in r["correcao"]["itens"] if x["i"] == i), None)
            if not it:
                continue
            cont += 1
            if it["tipo"] == "me":
                if it.get("marcada") is not None and 0 <= it["marcada"] < 5:
                    dist[it["marcada"]] += 1
                acertos += 1 if it["acertou"] else 0
            elif it.get("nota") is not None and it["valor"]:
                acertos += it["nota"] / it["valor"]
        por_q.append({"i": i, "tipo": q.get("tipo"), "habilidade": q.get("habilidade", ""),
                      "pct": round(100 * acertos / cont) if cont else None, "n": cont,
                      "distribuicao": dist if q.get("tipo") == "me" else None, "correta": q.get("correta"),
                      "enunciado": (q.get("enunciado") or "")[:120]})
    por_hab: dict = {}
    for x in por_q:
        h = (x["habilidade"] or "").strip()
        if h and x["pct"] is not None:
            d = por_hab.setdefault(h, {"soma": 0, "n": 0, "questoes": []})
            d["soma"] += x["pct"]; d["n"] += 1; d["questoes"].append(x["i"] + 1)
    habilidades = sorted([{"habilidade": h, "pct": round(d["soma"] / d["n"]), "questoes": d["questoes"]} for h, d in por_hab.items()],
                         key=lambda x: x["pct"])
    notas = [r["nota"] for r in corrigidas if r.get("nota") is not None]
    possivel = corrigidas[0]["correcao"]["possivel"] if corrigidas else 0
    avaliativa = bool(atividade["params"].get("avaliativa"))
    teto = possivel if avaliativa else 10
    faixas = [0, 0, 0, 0]  # <50%, 50-70, 70-90, >=90
    for nt in notas:
        p = 100 * nt / teto if teto else 0
        faixas[0 if p < 50 else 1 if p < 70 else 2 if p < 90 else 3] += 1
    media = round(sum(notas) / len(notas), 2) if notas else None
    return {
        "n_respostas": len(respostas), "n_corrigidas": n, "n_revisar": sum(1 for r in respostas if r.get("status") == "revisar"),
        "media": media, "maior": max(notas) if notas else None, "menor": min(notas) if notas else None, "teto": teto,
        "abaixo_media": sum(1 for nt in notas if teto and nt < 0.6 * teto),
        "faixas": faixas, "por_questao": por_q, "habilidades": habilidades,
        "mais_erradas": sorted([x for x in por_q if x["pct"] is not None], key=lambda x: x["pct"])[:5],
    }
