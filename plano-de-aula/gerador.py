"""
Módulo de geração do conteúdo pedagógico via IA.

Suporta:
  - OpenAI (e qualquer API compatível: Groq, OpenRouter, Together, Ollama etc.)
  - Google Gemini

Configuração (variáveis de ambiente ou arquivo config.json ao lado deste arquivo):
  AI_PROVIDER = "openai" | "gemini"
  AI_API_KEY  = chave da API
  AI_MODEL    = ex.: "gpt-4o-mini" (OpenAI) ou "gemini-3.8-flash" (Gemini)
  AI_BASE_URL = (opcional, só OpenAI-compatível) ex.: "https://api.groq.com/openai/v1"
"""
import json
import os
import re
import time
from pathlib import Path

import requests

BASE_DIR = Path(__file__).parent
CONFIG_FILE = BASE_DIR / "config.json"

CAMPOS = ["habilidade", "habilidade_ef", "objetivo", "metodologia", "recursos", "avaliacao", "fontes"]


# --------------------------------------------------------------------------- #
# Configuração
# --------------------------------------------------------------------------- #
def carregar_config(overrides: dict | None = None) -> dict:
    cfg = {
        "provider": "openai",
        "api_key": "",
        "model": "",
        "base_url": "",
    }
    if CONFIG_FILE.exists():
        try:
            cfg.update({k: v for k, v in json.loads(CONFIG_FILE.read_text("utf-8")).items() if v})
        except Exception:
            pass
    env = {
        "provider": os.getenv("AI_PROVIDER"),
        "api_key": os.getenv("AI_API_KEY"),
        "model": os.getenv("AI_MODEL"),
        "base_url": os.getenv("AI_BASE_URL"),
    }
    cfg.update({k: v for k, v in env.items() if v})
    if overrides:
        cfg.update({k: v for k, v in overrides.items() if v})

    cfg["provider"] = (cfg["provider"] or "openai").lower().strip()
    if not cfg["model"]:
        cfg["model"] = "gemini-3.8-flash" if cfg["provider"] == "gemini" else "gpt-4o-mini"
    if not cfg["base_url"]:
        cfg["base_url"] = "https://api.openai.com/v1"
    return cfg


# --------------------------------------------------------------------------- #
# Prompt
# --------------------------------------------------------------------------- #
SYSTEM_PROMPT = """Você é um coordenador pedagógico experiente de uma escola pública de Ensino Médio Integral no estado de Minas Gerais, Brasil.
Sua função é redigir planos de aula semanais completos, alinhados à BNCC (Base Nacional Comum Curricular) do Ensino Médio e ao Currículo Referência de Minas Gerais.
Escreva sempre em português do Brasil, em linguagem técnica-pedagógica clara e objetiva, na norma culta.
Responda EXCLUSIVAMENTE com um objeto JSON válido, sem comentários, sem markdown e sem texto fora do JSON."""

USER_PROMPT = """Elabore o plano de aula semanal com os dados abaixo. Seja objetivo: textos completos, porém enxutos (o plano cabe em 1 a 2 páginas A4).

REFERÊNCIAS QUE DEVEM FUNDAMENTAR O PLANO:
{contexto}

DISCIPLINA: {disciplina}
CONTEÚDO/TEMA: {conteudo}
TURMA: {serie} do Ensino Médio
DATA DE REFERÊNCIA (semana): {data}
QUANTIDADE DE AULAS NA SEMANA: {aulas} aula(s) de 50 minutos
OBSERVAÇÕES DO PROFESSOR: {observacoes}

Retorne um JSON com exatamente estas chaves (todas strings):

"tema": título curto e claro do tema da semana (máx. 12 palavras).

"habilidade": 1 a 3 habilidades da BNCC do Ensino Médio pertinentes ao conteúdo, cada uma em uma linha, no formato "(CÓDIGO) descrição oficial". Use códigos reais da BNCC (ex.: EM13MAT302, EM13LGG103, EM13CNT101, EM13CHS102). Separe as habilidades com quebra de linha. REGRAS ESPECIAIS: (a) componentes de curso técnico (Automação Industrial, Mecatrônica, Desenvolvimento Back-end/Front-end/de Aplicativos/de Softwares, Arquitetura de Sistemas, Segurança de Softwares, Prática Profissional e Empreendedora): NÃO invente códigos BNCC; escreva as competências/habilidades profissionais do Catálogo Nacional de Cursos Técnicos e do plano de curso do eixo tecnológico, e, se couber, 1 habilidade geral da BNCC relacionada (ex.: EM13MAT ou EM13LGG); (b) Nivelamento – Língua Portuguesa / Matemática: use habilidades do Ensino Fundamental anos finais (códigos EF0xLP / EF0xMA) que estão sendo recuperadas, ligadas às do EM; (c) Projeto de Vida, Eletiva, Estudos Orientados, Práticas Experimentais, PICS, Cultura Digital e Fundamentos de IA, Ferramentas para o Mundo do Trabalho e Práticas de Leitura e Escrita: use as Competências Gerais da BNCC (1 a 10) e os princípios da Escola da Escolha, além de habilidades específicas quando houver.

"habilidade_ef": {instrucao_ef}

"objetivo": objetivos de aprendizagem em 3 a 5 itens, cada item iniciado com "• " e com verbo no infinitivo (compreender, analisar, resolver, produzir...). Um item por linha.

"metodologia": desenvolvimento detalhado da(s) aula(s), organizado por momentos, no formato:
"1º MOMENTO – Acolhida e problematização (10 min): ..."
"2º MOMENTO – Desenvolvimento (25 min): ..."
"3º MOMENTO – Sistematização/atividade (15 min): ..."
Se houver mais de uma aula na semana, organize por "AULA 1", "AULA 2" etc., cada uma com seus momentos. Descreva o que o professor faz e o que os alunos fazem, com metodologias ativas quando fizer sentido. Um momento por linha.

"recursos": lista dos recursos didáticos necessários, cada item iniciado com "• ", um por linha (ex.: quadro, projetor, livro didático com capítulo, material impresso, aplicativos, materiais concretos).

"avaliacao": descrição da avaliação processual e formativa: instrumentos (participação, atividade, produção, exercícios), critérios observados e como será feito o retorno ao aluno. 3 a 6 linhas.

"fontes": lista das fontes efetivamente utilizadas para elaborar o plano, uma por linha, iniciadas com "• ", em formato de referência (ABNT simplificada). Inclua obrigatoriamente as referências listadas em REFERÊNCIAS acima que você usou (BNCC, Currículo Referência de MG, Cadernos do ICE, documentos da biblioteca — citando título e página quando houver "p. N" no trecho) e, além delas, o livro didático ou materiais que você sugerir na metodologia/recursos. Não invente documentos que não foram fornecidos; materiais genéricos podem ser indicados de forma genérica (ex.: "Livro didático adotado pela escola – capítulo sobre ...").

Seja específico para o conteúdo informado: cite exemplos, exercícios, textos, experimentos ou situações concretas relacionadas ao tema. Não use marcadores markdown (**, #, -). Use apenas "• " para listas."""


INSTRUCAO_EF_ON = ('1 a 3 habilidades do ENSINO FUNDAMENTAL (anos finais, BNCC) que são PRÉ-REQUISITO ou correlatas do conteúdo desta aula, uma por linha, no formato "(CÓDIGO) descrição oficial resumida". Use códigos reais e no formato exato EF + ano + componente + número (ex.: EF09MA06, EF08MA07, EF89LP33, EF09CI13, EF09HI10, EF07GE04). Escolha as que o estudante precisa dominar para acompanhar esta aula. Se realmente não houver correlação, devolva "". IMPORTANTE: na "metodologia", inclua no 1º momento uma breve RETOMADA/DIAGNÓSTICO dessas habilidades do Fundamental (5 a 10 min), e na "avaliacao" indique como será observado se o estudante tem esse pré-requisito.')
INSTRUCAO_EF_OFF = 'devolva sempre "" (string vazia) neste campo.'


def _quer_ef(dados: dict) -> bool:
    v = dados.get("incluir_ef", True)
    if isinstance(v, str):
        return v.strip().lower() not in ("0", "false", "nao", "não", "off", "")
    return bool(v)


_RE_EF = re.compile(r"EF(0[1-9]|[1-9][0-9]?|67|89)(LP|MA|CI|GE|HI|AR|EF|LI|ER)\d{2}")


def _filtrar_ef(texto: str) -> str:
    """Mantém só as linhas que trazem um código EF válido no formato da BNCC (evita códigos inventados)."""
    linhas = []
    for l in str(texto or "").split("\n"):
        l = l.strip()
        if not l:
            continue
        if _RE_EF.search(l.replace(" ", "")):
            linhas.append(l if l.startswith(("(", "•")) else "• " + l)
    return "\n".join(linhas[:3])


def montar_prompt(dados: dict, contexto: str = "") -> str:
    return USER_PROMPT.format(
        contexto=contexto or "BNCC do Ensino Médio e Currículo Referência de Minas Gerais.",
        instrucao_ef=INSTRUCAO_EF_ON if _quer_ef(dados) else INSTRUCAO_EF_OFF,
        disciplina=dados.get("disciplina", "").strip(),
        conteudo=dados.get("conteudo", "").strip(),
        serie=dados.get("serie", "").strip(),
        data=dados.get("data", "").strip(),
        aulas=dados.get("aulas") or "2",
        observacoes=dados.get("observacoes", "").strip() or "nenhuma",
    )


# --------------------------------------------------------------------------- #
# Chamadas às APIs
# --------------------------------------------------------------------------- #
def _chamar_openai(cfg: dict, prompt: str, system: str | None = None, max_tokens: int = 4096) -> str:
    url = cfg["base_url"].rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"}
    body = {
        "model": cfg["model"],
        "temperature": 0.7,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system or SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "response_format": {"type": "json_object"},
    }
    r = requests.post(url, headers=headers, json=body, timeout=120)
    if r.status_code >= 400:
        # alguns provedores não aceitam response_format; tenta sem
        body.pop("response_format", None)
        r = requests.post(url, headers=headers, json=body, timeout=120)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


# Preferência de modelos Gemini (do mais recomendado ao menos). A lista real
# disponível para a chave é descoberta automaticamente na API (ListModels).
GEMINI_PREFERIDOS = [
    "gemini-3.8-flash", "gemini-3.7-flash", "gemini-3.6-flash", "gemini-3.5-flash",
    "gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-3-flash-preview",
    "gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-flash-latest", "gemini-2.0-flash",
]
MODELOS_GEMINI_DESCONTINUADOS = {"gemini-1.5-flash", "gemini-1.5-pro", "gemini-1.5-flash-8b",
                                 "gemini-1.5-flash-latest", "gemini-1.5-pro-latest", "gemini-pro"}
TENTATIVAS_POR_MODELO = 2              # tentativas por modelo quando o Google responde 500/503
ESPERA_ENTRE_TENTATIVAS = (2, 4, 6)    # segundos
MAX_MODELOS_TENTADOS = 6               # depois disso, desiste e avisa (em vez de esperar minutos)
_cache_modelos: dict = {"chave": None, "lista": [], "quando": 0.0}

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"


def _headers(api_key: str) -> dict:
    # A chave vai no cabeçalho (e NÃO na URL) para nunca aparecer em mensagens de erro/logs.
    return {"x-goog-api-key": api_key, "Content-Type": "application/json"}


def listar_modelos_gemini(api_key: str) -> list[str]:
    """Consulta a API do Google e devolve os modelos de texto disponíveis para esta chave."""
    agora = time.time()
    if _cache_modelos["chave"] == api_key and agora - _cache_modelos["quando"] < 3600:
        return _cache_modelos["lista"]
    nomes, token = [], None
    for _ in range(5):
        url = f"{GEMINI_BASE}/models?pageSize=200" + (f"&pageToken={token}" if token else "")
        r = requests.get(url, headers=_headers(api_key), timeout=30)
        if r.status_code != 200:
            break
        j = r.json()
        for m in j.get("models", []):
            if "generateContent" in m.get("supportedGenerationMethods", []):
                nomes.append(m["name"].split("/", 1)[-1])
        token = j.get("nextPageToken")
        if not token:
            break
    _cache_modelos.update(chave=api_key, lista=nomes, quando=agora)
    return nomes


def _ordenar_candidatos(preferido: str, disponiveis: list[str]) -> list[str]:
    """Monta a ordem de tentativa: modelo configurado, depois os preferidos que existem,
    depois qualquer outro 'flash' de texto disponível (sem tts/image/live/embedding)."""
    def util(n: str) -> bool:
        ruins = ("tts", "image", "live", "audio", "embedding", "transcribe", "translate", "omni", "gemma", "imagen", "veo")
        return "gemini" in n and not any(x in n for x in ruins)

    disp = [d for d in disponiveis if util(d)]
    ordem: list[str] = []
    # o modelo configurado só entra se existir para esta chave (ou se não foi possível listar)
    if preferido and preferido not in MODELOS_GEMINI_DESCONTINUADOS and (not disp or preferido in disp):
        ordem.append(preferido)
    for m in GEMINI_PREFERIDOS:
        if (not disp or m in disp) and m not in ordem:
            ordem.append(m)
    # cota: os "lite" costumam ter limite diário bem maior -> entram logo após o preferido
    for m in sorted(disp, reverse=True):
        if "lite" in m and m not in ordem:
            ordem.append(m)
    # demais flash disponíveis (mais novos primeiro pela ordenação alfabética inversa)
    for m in sorted(disp, reverse=True):
        if "flash" in m and m not in ordem:
            ordem.append(m)
    for m in sorted(disp, reverse=True):
        if m not in ordem:
            ordem.append(m)
    return ordem[:MAX_MODELOS_TENTADOS]


TIMEOUT_GEMINI = int(os.getenv("AI_TIMEOUT", "75"))          # segundos por tentativa
THINKING_BUDGET = int(os.getenv("AI_THINKING_BUDGET", "512"))  # quanto o modelo pode "pensar" (0 = desligado)


def _gemini_request(model: str, api_key: str, body: dict) -> requests.Response:
    return requests.post(f"{GEMINI_BASE}/models/{model}:generateContent",
                         headers=_headers(api_key), json=body, timeout=TIMEOUT_GEMINI)


def _msg_erro_google(r: requests.Response) -> str:
    try:
        return r.json().get("error", {}).get("message", "") or r.reason
    except Exception:
        return r.reason or ""


def _chaves_gemini(cfg: dict) -> list[str]:
    """Chave principal + extras (AI_API_KEYS_EXTRA, separadas por vírgula). Usadas em rodízio quando a cota estoura."""
    extras = [k.strip() for k in os.getenv("AI_API_KEYS_EXTRA", "").split(",") if k.strip()]
    return [cfg["api_key"]] + [k for k in extras if k != cfg["api_key"]]


def _chamar_gemini(cfg: dict, prompt: str, system: str | None = None, max_tokens: int = 4096) -> str:
    chaves = _chaves_gemini(cfg)
    ultimo_erro = None
    for i, chave in enumerate(chaves):
        try:
            return _chamar_gemini_com_chave({**cfg, "api_key": chave}, prompt, system, max_tokens)
        except RuntimeError as e:
            ultimo_erro = e
            if "cota" not in str(e).lower() or i == len(chaves) - 1:
                raise
    raise ultimo_erro  # pragma: no cover


def _chamar_gemini_com_chave(cfg: dict, prompt: str, system: str | None = None, max_tokens: int = 4096) -> str:
    body = {
        "systemInstruction": {"parts": [{"text": system or SYSTEM_PROMPT}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.7,
            "responseMimeType": "application/json",
            "maxOutputTokens": max_tokens,
            # Modelos 2.5+/3.x "pensam" antes de responder; sem limite isso pode levar 30-60 s.
            # Um orçamento pequeno mantém a qualidade do plano e corta a espera.
            "thinkingConfig": {"thinkingBudget": THINKING_BUDGET},
        },
    }
    try:
        disponiveis = listar_modelos_gemini(cfg["api_key"])
    except requests.RequestException:
        disponiveis = []
    candidatos = _ordenar_candidatos(cfg["model"].strip(), disponiveis)

    erros = []
    houve_429 = False
    for m in candidatos:
        for tentativa in range(TENTATIVAS_POR_MODELO):
            try:
                r = _gemini_request(m, cfg["api_key"], body)
            except requests.RequestException as e:
                erros.append(f"{m}: falha de conexão ({type(e).__name__})")
                time.sleep(ESPERA_ENTRE_TENTATIVAS[min(tentativa, 2)])
                continue

            if r.status_code == 200:
                try:
                    return r.json()["candidates"][0]["content"]["parts"][0]["text"]
                except (KeyError, IndexError):
                    erros.append(f"{m}: resposta vazia")
                    break
            if r.status_code == 400 and "thinking" in _msg_erro_google(r).lower():
                # modelo não suporta configuração de pensamento -> reenvia sem ela
                body_sem = json.loads(json.dumps(body))
                body_sem["generationConfig"].pop("thinkingConfig", None)
                try:
                    r = _gemini_request(m, cfg["api_key"], body_sem)
                    if r.status_code == 200:
                        return r.json()["candidates"][0]["content"]["parts"][0]["text"]
                except (requests.RequestException, KeyError, IndexError):
                    pass
            if r.status_code == 404:                  # modelo não existe -> próximo modelo
                erros.append(f"{m}: não encontrado (404)")
                break
            if r.status_code in (401, 403):
                raise RuntimeError("Chave de API do Gemini inválida ou sem permissão. "
                                   "Gere outra em https://aistudio.google.com/app/apikey "
                                   "e atualize a variável AI_API_KEY.")
            if r.status_code == 429:                 # cota esgotada neste modelo -> próximo modelo, sem esperar
                erros.append(f"{m}: cota esgotada (429)")
                houve_429 = True
                break
            if r.status_code in (500, 502, 503, 504):  # sobrecarga -> espera curta e repete
                erros.append(f"{m}: indisponível ({r.status_code})")
                time.sleep(ESPERA_ENTRE_TENTATIVAS[min(tentativa, 2)])
                continue
            erros.append(f"{m}: {r.status_code} {_msg_erro_google(r)[:120]}")
            break

    if houve_429 and all("429" in e or "cota" in e for e in erros):
        raise RuntimeError(
            "A cota gratuita da chave do Gemini foi atingida (limite de requisições por minuto/dia). "
            "Aguarde alguns minutos e tente de novo. Se acontecer com frequência, a supervisão pode cadastrar "
            "chaves adicionais (AI_API_KEYS_EXTRA) ou ativar o faturamento da chave no Google AI Studio. "
            f"Detalhes: {'; '.join(erros[-4:])}"
        )
    lista = ", ".join(disponiveis[:15]) or "não foi possível listar"
    raise RuntimeError(
        "O serviço do Google Gemini está indisponível para todos os modelos testados. "
        "Aguarde 1–2 minutos e tente novamente. "
        f"Detalhes: {'; '.join(erros[-5:])}. Modelos visíveis para a sua chave: {lista}"
    )


class RespostaInvalida(ValueError):
    """A IA devolveu um texto que não é JSON legível (mesmo após tentativas de reparo)."""


def _reparar_json(t: str) -> str:
    """Conserta os defeitos mais comuns nas respostas da IA: aspas sem escape dentro do texto,
    quebras de linha cruas, vírgulas faltando entre campos, vírgulas sobrando e resposta cortada no meio."""
    out, stack = [], []
    in_str = esc = False
    n = len(t)
    i = 0
    while i < n:
        c = t[i]
        if in_str:
            if esc:
                out.append(c); esc = False
            elif c == "\\":
                out.append(c); esc = True
            elif c == '"':
                j = i + 1
                while j < n and t[j] in " \t\r\n":
                    j += 1
                nxt = t[j] if j < n else ""
                fecha = False
                if nxt in ("", ":", "}", "]"):
                    fecha = True
                elif nxt == ",":                      # vírgula: fecha se depois vier outro campo/valor
                    k = j + 1
                    while k < n and t[k] in " \t\r\n":
                        k += 1
                    prox = t[k] if k < n else ""
                    fecha = prox in ('"', "{", "[", "}", "]", "") or prox.isdigit() or prox == "-" or t.startswith(("true", "false", "null"), k)
                elif nxt == '"' and "\n" in t[i + 1:j]:  # "valor"\n"chave" -> faltou vírgula
                    fecha = True
                if fecha:
                    in_str = False; out.append(c)
                else:
                    out.append('\\"')                  # aspas dentro do texto
            elif c == "\n":
                out.append("\\n")
            elif c == "\t":
                out.append("\\t")
            elif c == "\r":
                pass
            else:
                out.append(c)
        else:
            if c == '"':
                in_str = True; out.append(c)
            elif c in "{[":
                stack.append("}" if c == "{" else "]"); out.append(c)
            elif c in "}]":
                if stack:
                    stack.pop()
                out.append(c)
            else:
                out.append(c)
        i += 1
    s = "".join(out)
    if in_str:
        s += '"'
    s = re.sub(r'("|\d|true|false|null|\}|\])[ \t]*\n\s*(")', r"\1,\n\2", s)   # vírgula faltando entre linhas
    s = re.sub(r",\s*([}\]])", r"\1", s)                                          # vírgula sobrando
    s = re.sub(r",\s*$", "", s.rstrip())
    s = re.sub(r':\s*$', ': ""', s)                                                # cortado logo após "chave":
    while stack:                                                                   # fecha o que ficou aberto
        s += stack.pop()
    return s


def _extrair_json(texto: str) -> dict:
    texto = texto.strip()
    texto = re.sub(r"^```(?:json)?\s*|\s*```$", "", texto, flags=re.I | re.M).strip()
    tentativas = [texto]
    m = re.search(r"\{.*\}", texto, re.S)
    if m:
        tentativas.append(m.group(0))
    ini = texto.find("{")
    if ini >= 0:
        tentativas.append(_reparar_json(texto[ini:]))
    erro = None
    for cand in tentativas:
        try:
            obj = json.loads(cand)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError as e:
            erro = e
    raise RespostaInvalida(f"resposta da IA em formato inválido ({erro})")


def _limpar(txt) -> str:
    if isinstance(txt, list):
        txt = "\n".join(str(t) for t in txt)
    txt = str(txt or "")
    txt = re.sub(r"\*\*(.*?)\*\*", r"\1", txt)       # negrito markdown
    txt = re.sub(r"^\s*[-*]\s+", "• ", txt, flags=re.M)  # marcadores markdown -> •
    txt = re.sub(r"^#+\s*", "", txt, flags=re.M)
    return txt.strip()


# --------------------------------------------------------------------------- #
# Modo demonstração (sem chave de API)
# --------------------------------------------------------------------------- #
def _demo(dados: dict) -> dict:
    d = dados.get("disciplina", "").strip()
    c = dados.get("conteudo", "").strip()
    s = dados.get("serie", "").strip()
    return {
        "tema": c,
        "habilidade": (
            f"(Código BNCC) Habilidade do Ensino Médio relacionada a \"{c}\" na disciplina de {d}.\n"
            "ATENÇÃO: modo demonstração — configure uma chave de IA em \"Configurações\" para que a "
            "habilidade oficial da BNCC seja identificada automaticamente."
        ),
        "habilidade_ef": (
            "(EF09XX00) Habilidade do Ensino Fundamental pré-requisito deste conteúdo — identificada "
            "automaticamente quando a IA estiver configurada."
        ) if _quer_ef(dados) else "",
        "objetivo": (
            f"• Compreender os conceitos fundamentais de {c}.\n"
            f"• Analisar situações-problema envolvendo {c} no contexto do {s}.\n"
            f"• Aplicar os conhecimentos sobre {c} em atividades práticas e contextualizadas.\n"
            "• Desenvolver a argumentação e o trabalho colaborativo."
        ),
        "metodologia": (
            "1º MOMENTO – Acolhida e problematização (10 min): levantamento dos conhecimentos prévios dos "
            f"estudantes sobre {c} por meio de perguntas disparadoras e registro no quadro.\n"
            "2º MOMENTO – Desenvolvimento (25 min): exposição dialogada do conteúdo com exemplos "
            "contextualizados, leitura orientada do livro didático e resolução comentada de exemplos.\n"
            "3º MOMENTO – Sistematização (15 min): atividade em duplas com exercícios de aplicação, "
            "correção coletiva e síntese dos principais conceitos."
        ),
        "recursos": (
            "• Quadro branco e pincel\n• Livro didático\n• Projetor multimídia / slides\n"
            "• Material impresso (lista de exercícios)\n• Caderno do estudante"
        ),
        "avaliacao": (
            "Avaliação processual e formativa, considerando: participação nas discussões, realização da "
            "atividade em duplas, registro no caderno e domínio dos conceitos trabalhados. O retorno aos "
            "estudantes será feito na correção coletiva e por meio de orientações individuais."
        ),
        "fontes": "",
        "_demo": True,
    }


# --------------------------------------------------------------------------- #
# Função principal
# --------------------------------------------------------------------------- #
def _pedir_json(cfg: dict, prompt: str, system: str | None = None, max_tokens: int = 4096) -> dict:
    """Chama a IA e lê o JSON. Se a resposta vier mal formatada, pede de novo uma vez antes de desistir."""
    ultimo = None
    for tentativa in range(2):
        if cfg["provider"] == "gemini":
            bruto = _chamar_gemini(cfg, prompt, system, max_tokens)
        else:
            bruto = _chamar_openai(cfg, prompt, system, max_tokens)
        try:
            return _extrair_json(bruto)
        except RespostaInvalida as e:
            ultimo = e
            time.sleep(1)
    raise RuntimeError("A IA devolveu a resposta em um formato ilegível duas vezes seguidas. "
                       "Clique em gerar novamente (costuma resolver). Se persistir, reduza o número de questões. "
                       f"Detalhe técnico: {ultimo}")


def gerar_plano(dados: dict, overrides: dict | None = None, contexto: str = "",
                citacoes: list[str] | None = None) -> dict:
    cfg = carregar_config(overrides)
    if not cfg["api_key"]:
        d = _demo(dados)
        d["fontes"] = "\n".join("• " + c for c in (citacoes or []))
        return d

    prompt = montar_prompt(dados, contexto)
    obj = _pedir_json(cfg, prompt)
    resultado = {k: _limpar(obj.get(k, "")) for k in CAMPOS}
    resultado["tema"] = _limpar(obj.get("tema") or dados.get("conteudo", ""))
    resultado["habilidade_ef"] = _filtrar_ef(resultado.get("habilidade_ef", "")) if _quer_ef(dados) else ""
    # garante que as referências fornecidas constem nas fontes
    fontes = resultado.get("fontes", "")
    for c in (citacoes or []):
        chave = c.split(".")[0][:25].lower()
        if chave and chave not in fontes.lower():
            fontes = (fontes + "\n" if fontes else "") + "• " + c
    resultado["fontes"] = fontes
    resultado["_demo"] = False
    return resultado


# --------------------------------------------------------------------------- #
# Provas e atividades a partir dos planos de aula
# --------------------------------------------------------------------------- #
TIPOS_ATIVIDADE = {
    "prova": "Prova",
    "simulado": "Simulado",
    "atividade": "Atividade",
    "lista": "Lista de exercícios",
    "trabalho": "Trabalho",
    "recuperacao": "Avaliação de recuperação",
}

SYSTEM_PROMPT_ATIVIDADE = """Você é um professor experiente de Ensino Médio de uma escola pública de Minas Gerais e elaborador de itens de avaliação (ENEM, SAEB, SIMAVE).
Elabore questões originais, corretas, claras e adequadas à série, alinhadas à BNCC e ao conteúdo dos planos de aula fornecidos.
Regras para múltipla escolha: exatamente 5 alternativas (A a E), UMA correta, distratores plausíveis (erros comuns dos estudantes), sem "todas as anteriores"/"nenhuma das anteriores", alternativas com tamanho parecido.
Regras para discursivas: comando claro (explique, calcule, justifique, compare...), resposta esperada objetiva e critérios de correção verificáveis.
Contextualize quando fizer sentido (situações do cotidiano, ciência, trabalho, cidadania), sem enrolação. Português do Brasil, norma culta.
Nunca repita a mesma ideia em duas questões. Números e cálculos devem estar corretos: confira antes de responder.
Responda EXCLUSIVAMENTE com um objeto JSON válido, sem markdown e sem texto fora do JSON."""

USER_PROMPT_ATIVIDADE = """Elabore uma {tipo_nome} de {disciplina} para o {serie} do Ensino Médio com base nos planos de aula abaixo.

PLANOS DE AULA (conteúdos trabalhados):
{planos}

ESPECIFICAÇÕES:
- Quantidade: {n_me} questão(ões) de múltipla escolha e {n_disc} questão(ões) discursiva(s). Total: {total} questões, numeradas em sequência.{lote}
- Dificuldade: {dificuldade}.
- Distribua as questões proporcionalmente entre os conteúdos dos planos (cubra todos).
- Ordene das mais fáceis para as mais difíceis.
- Observações do professor: {observacoes}

FORMATO DE RESPOSTA (JSON):
{{
  "titulo": "título curto da avaliação (ex.: 'Prova bimestral – Funções e Matrizes')",
  "instrucoes": "3 a 5 instruções curtas ao estudante, uma por linha",
  "questoes": [
    {{"tipo": "me", "enunciado": "texto da questão (pode ter mais de um parágrafo, separados por \\n)", "alternativas": ["texto A", "texto B", "texto C", "texto D", "texto E"], "correta": 0, "resolucao": "resolução breve e por que a alternativa está certa", "habilidade": "código BNCC (ex.: EM13MAT302)"}},
    {{"tipo": "disc", "enunciado": "texto da questão", "resposta": "resposta esperada completa", "criterios": "critérios de correção, um por linha (ex.: 'Identifica a fórmula correta (40%)')", "linhas": 6, "habilidade": "código BNCC"}}
  ]
}}
"correta" é o índice da alternativa certa (0 = A, 4 = E). "linhas" é o espaço de resposta (4 a 10 linhas). Não inclua o valor das questões: será atribuído pelo professor.
As questões "me" vêm primeiro, depois as "disc". Não use fórmulas em LaTeX; escreva expressões em texto simples (ex.: x² + 2x, √2, 3/4, 10⁵).
Seja breve em "resolucao", "resposta" e "criterios" (no máximo 3 frases cada). Dentro dos textos, use aspas simples ('assim') em vez de aspas duplas, e nunca quebre linha dentro de um valor sem usar \\n."""

DIFICULDADES = {
    "facil": "fácil (reconhecimento e aplicação direta)",
    "media": "média (aplicação e interpretação)",
    "dificil": "difícil (análise, múltiplas etapas, situações novas)",
    "mista": "mista: cerca de 30% fáceis, 50% médias e 20% difíceis",
}


def _resumo_plano(i: int, p: dict) -> str:
    d, pl = p.get("dados", {}), p.get("plano", {})
    partes = [f"PLANO {i} — {d.get('disciplina','')} · {d.get('serie','')} · semana {d.get('data','')}",
              f"Tema: {pl.get('tema') or d.get('conteudo','')}",
              f"Conteúdo: {d.get('conteudo','')}"]
    for k, rot in (("habilidade", "Habilidade"), ("objetivo", "Objetivos"), ("metodologia", "Desenvolvimento")):
        v = (pl.get(k) or "").strip()
        if v:
            partes.append(f"{rot}: {v[:900]}")
    return "\n".join(partes)


def montar_prompt_atividade(params: dict, planos: list[dict], lote: str = "") -> str:
    n_me = int(params.get("n_me") or 0)
    n_disc = int(params.get("n_disc") or 0)
    return USER_PROMPT_ATIVIDADE.format(
        lote=("\n- " + lote) if lote else "",
        tipo_nome=TIPOS_ATIVIDADE.get(params.get("tipo", "prova"), "Prova").lower(),
        disciplina=params.get("disciplina", ""), serie=params.get("serie", ""),
        planos="\n\n".join(_resumo_plano(i + 1, p) for i, p in enumerate(planos)),
        n_me=n_me, n_disc=n_disc, total=n_me + n_disc,
        dificuldade=DIFICULDADES.get(params.get("dificuldade", "mista"), DIFICULDADES["mista"]),
        observacoes=(params.get("observacoes") or "").strip() or "nenhuma",
    )


def distribuir_valores(total: float, n: int) -> list[float]:
    """Divide o valor total em n partes com 1 casa decimal; a diferença vai para a última questão."""
    if n <= 0:
        return []
    base = int(total * 10 // n) / 10
    vals = [base] * n
    vals[-1] = round(total - base * (n - 1), 2)
    return vals


def _normalizar_questoes(obj: dict, n_me: int, n_disc: int) -> list[dict]:
    out = []
    for q in obj.get("questoes") or []:
        if not isinstance(q, dict):
            continue
        tipo = "me" if str(q.get("tipo", "")).lower().startswith("m") or q.get("alternativas") else "disc"
        item = {"tipo": tipo, "enunciado": _limpar(q.get("enunciado", "")),
                "habilidade": _limpar(q.get("habilidade", ""))[:40]}
        if tipo == "me":
            alts = [_limpar(a) for a in (q.get("alternativas") or [])][:5]
            while len(alts) < 5:
                alts.append("")
            try:
                correta = int(q.get("correta", 0))
            except (TypeError, ValueError):
                correta = 0
            item.update(alternativas=alts, correta=max(0, min(4, correta)), resolucao=_limpar(q.get("resolucao", "")))
        else:
            try:
                linhas = int(q.get("linhas") or 6)
            except (TypeError, ValueError):
                linhas = 6
            item.update(resposta=_limpar(q.get("resposta", "")), criterios=_limpar(q.get("criterios", "")),
                        linhas=max(3, min(15, linhas)))
        if item["enunciado"]:
            out.append(item)
    # garante ordem ME -> discursivas e limita à quantidade pedida
    me = [q for q in out if q["tipo"] == "me"][:n_me]
    disc = [q for q in out if q["tipo"] == "disc"][:n_disc]
    return me + disc


def _demo_atividade(params: dict, planos: list[dict]) -> dict:
    temas = [p.get("plano", {}).get("tema") or p.get("dados", {}).get("conteudo", "") for p in planos]
    qs = []
    for i in range(int(params.get("n_me") or 0)):
        t = temas[i % len(temas)] if temas else "o conteúdo"
        qs.append({"tipo": "me", "enunciado": f"(Demonstração) Questão de múltipla escolha sobre {t}.",
                   "alternativas": ["Alternativa A", "Alternativa B", "Alternativa C", "Alternativa D", "Alternativa E"],
                   "correta": 0, "resolucao": "Configure a IA para gerar questões reais.", "habilidade": ""})
    for i in range(int(params.get("n_disc") or 0)):
        t = temas[i % len(temas)] if temas else "o conteúdo"
        qs.append({"tipo": "disc", "enunciado": f"(Demonstração) Explique, com suas palavras, {t}.",
                   "resposta": "Resposta esperada (modo demonstração).", "criterios": "Clareza (50%)\nCorreção conceitual (50%)",
                   "linhas": 6, "habilidade": ""})
    return {"titulo": f"{TIPOS_ATIVIDADE.get(params.get('tipo','prova'),'Prova')} – {', '.join(temas)[:80]}",
            "instrucoes": "Leia com atenção.\nUse caneta azul ou preta.\nNão é permitido o uso de celular.", "questoes": qs, "_demo": True}


LOTE_MAX = int(os.getenv("AI_LOTE_QUESTOES", "4"))     # questões por pedido à IA (pedidos rodam em paralelo)
LOTES_PARALELOS = int(os.getenv("AI_LOTES_PARALELOS", "5"))


def _dividir_lotes(n_me: int, n_disc: int) -> list[tuple[int, int]]:
    """Divide a prova em lotes pequenos (n_me, n_disc). Ex.: 10 ME + 4 disc -> (4,0),(4,0),(2,0),(0,4)."""
    total = n_me + n_disc
    if total <= LOTE_MAX:
        return [(n_me, n_disc)]
    lotes = []
    for n, tipo in ((n_me, "me"), (n_disc, "disc")):
        while n > 0:
            k = min(LOTE_MAX, n)
            lotes.append((k, 0) if tipo == "me" else (0, k))
            n -= k
    return lotes


def _gerar_atividade_em_lotes(cfg: dict, params: dict, planos: list[dict], n_me: int, n_disc: int) -> dict:
    """Pede as questões em vários lotes simultâneos (muito mais rápido que um pedido grande).
       Cada lote recebe a mesma base (planos) e sabe qual parte da prova está produzindo, para não repetir."""
    from concurrent.futures import ThreadPoolExecutor

    lotes = _dividir_lotes(n_me, n_disc)
    total = n_me + n_disc
    temas = [(p.get("plano", {}).get("tema") or p.get("dados", {}).get("conteudo", "")) for p in planos]

    def pedir(idx: int) -> dict:
        lm, ld = lotes[idx]
        inicio = sum(a + b for a, b in lotes[:idx]) + 1
        fim = inicio + lm + ld - 1
        instr = ""
        if len(lotes) > 1:
            # cada lote foca em conteúdos diferentes quando há vários planos
            foco = ""
            if len(temas) > 1:
                sel = [temas[(idx + j) % len(temas)] for j in range(min(len(temas), 2))]
                foco = f" Priorize os conteúdos: {'; '.join(sel)} (sem ignorar os demais)."
            instr = (f"ATENÇÃO: esta é a PARTE {idx + 1} de {len(lotes)} da mesma prova. Produza SOMENTE as questões "
                     f"{inicio} a {fim} ({lm} de múltipla escolha e {ld} discursiva(s)), com dificuldade crescente dentro do lote."
                     f" Não repita abordagens óbvias; varie contextos e operações.{foco}"
                     f" O JSON deve conter apenas essas {lm + ld} questões.")
        p2 = dict(params, n_me=lm if len(lotes) > 1 else n_me, n_disc=ld if len(lotes) > 1 else n_disc)
        prompt = montar_prompt_atividade(p2, planos, instr)
        max_tokens = min(30000, 2500 + 700 * (lm + ld))
        obj = _pedir_json(cfg, prompt, SYSTEM_PROMPT_ATIVIDADE, max_tokens)
        return {"titulo": _limpar(obj.get("titulo", "")), "instrucoes": _limpar(obj.get("instrucoes", "")),
                "questoes": _normalizar_questoes(obj, lm, ld)}

    if len(lotes) == 1:
        partes = [pedir(0)]
    else:
        with ThreadPoolExecutor(max_workers=min(LOTES_PARALELOS, len(lotes))) as ex:
            partes = list(ex.map(pedir, range(len(lotes))))

    me = [q for p in partes for q in p["questoes"] if q["tipo"] == "me"][:n_me]
    disc = [q for p in partes for q in p["questoes"] if q["tipo"] == "disc"][:n_disc]
    questoes = me + disc
    if not questoes:
        raise RuntimeError("A IA não devolveu questões válidas. Tente novamente.")
    if len(questoes) < total * 0.6:
        raise RuntimeError(f"A IA devolveu só {len(questoes)} de {total} questões. Tente novamente.")
    titulo = next((p["titulo"] for p in partes if p["titulo"]), "")
    instrucoes = next((p["instrucoes"] for p in partes if p["instrucoes"]), "")
    return {"titulo": titulo, "instrucoes": instrucoes, "questoes": questoes, "_demo": False}


def gerar_atividade(params: dict, planos: list[dict], overrides: dict | None = None) -> dict:
    """params: tipo, disciplina, serie, n_me, n_disc, dificuldade, observacoes, avaliativa, valor_total.
       planos: lista de itens do histórico (dados + plano). Devolve {titulo, instrucoes, questoes[]}."""
    n_me, n_disc = int(params.get("n_me") or 0), int(params.get("n_disc") or 0)
    if n_me + n_disc <= 0:
        raise ValueError("Informe pelo menos uma questão.")
    if n_me + n_disc > 30:
        raise ValueError("Máximo de 30 questões por prova/atividade.")
    cfg = carregar_config(overrides)
    if not cfg["api_key"]:
        res = _demo_atividade(params, planos)
    else:
        res = _gerar_atividade_em_lotes(cfg, params, planos, n_me, n_disc)
    if not res["titulo"]:
        res["titulo"] = f"{TIPOS_ATIVIDADE.get(params.get('tipo','prova'),'Prova')} de {params.get('disciplina','')}"
    # valores
    if params.get("avaliativa"):
        try:
            total = float(str(params.get("valor_total") or 10).replace(",", "."))
        except ValueError:
            total = 10.0
        for q, v in zip(res["questoes"], distribuir_valores(total, len(res["questoes"]))):
            q["valor"] = v
    return res
