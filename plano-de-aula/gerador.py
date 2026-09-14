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

CAMPOS = ["habilidade", "objetivo", "metodologia", "recursos", "avaliacao", "fontes"]


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

USER_PROMPT = """Elabore o plano de aula semanal com os dados abaixo.

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


def montar_prompt(dados: dict, contexto: str = "") -> str:
    return USER_PROMPT.format(
        contexto=contexto or "BNCC do Ensino Médio e Currículo Referência de Minas Gerais.",
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
def _chamar_openai(cfg: dict, prompt: str) -> str:
    url = cfg["base_url"].rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"}
    body = {
        "model": cfg["model"],
        "temperature": 0.7,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
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
TENTATIVAS_POR_MODELO = 2              # novas tentativas quando o Google responde 500/503
ESPERA_ENTRE_TENTATIVAS = (3, 6, 10)   # segundos
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
    if preferido and preferido not in MODELOS_GEMINI_DESCONTINUADOS:
        ordem.append(preferido)
    for m in GEMINI_PREFERIDOS:
        if (not disp or m in disp) and m not in ordem:
            ordem.append(m)
    # demais flash disponíveis (mais novos primeiro pela ordenação alfabética inversa)
    for m in sorted(disp, reverse=True):
        if "flash" in m and m not in ordem:
            ordem.append(m)
    for m in sorted(disp, reverse=True):
        if m not in ordem:
            ordem.append(m)
    return ordem[:12]


def _gemini_request(model: str, api_key: str, body: dict) -> requests.Response:
    return requests.post(f"{GEMINI_BASE}/models/{model}:generateContent",
                         headers=_headers(api_key), json=body, timeout=120)


def _msg_erro_google(r: requests.Response) -> str:
    try:
        return r.json().get("error", {}).get("message", "") or r.reason
    except Exception:
        return r.reason or ""


def _chamar_gemini(cfg: dict, prompt: str) -> str:
    body = {
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.7, "responseMimeType": "application/json"},
    }
    try:
        disponiveis = listar_modelos_gemini(cfg["api_key"])
    except requests.RequestException:
        disponiveis = []
    candidatos = _ordenar_candidatos(cfg["model"].strip(), disponiveis)

    erros = []
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
            if r.status_code == 404:                  # modelo não existe -> próximo modelo
                erros.append(f"{m}: não encontrado (404)")
                break
            if r.status_code in (401, 403):
                raise RuntimeError("Chave de API do Gemini inválida ou sem permissão. "
                                   "Gere outra em https://aistudio.google.com/app/apikey "
                                   "e atualize a variável AI_API_KEY.")
            if r.status_code in (429, 500, 502, 503, 504):  # limite/sobrecarga -> espera e repete
                erros.append(f"{m}: indisponível ({r.status_code})")
                time.sleep(ESPERA_ENTRE_TENTATIVAS[min(tentativa, 2)])
                continue
            erros.append(f"{m}: {r.status_code} {_msg_erro_google(r)[:120]}")
            break

    lista = ", ".join(disponiveis[:15]) or "não foi possível listar"
    raise RuntimeError(
        "O serviço do Google Gemini está indisponível para todos os modelos testados. "
        "Aguarde 1–2 minutos e tente novamente. "
        f"Detalhes: {'; '.join(erros[-5:])}. Modelos visíveis para a sua chave: {lista}"
    )


def _extrair_json(texto: str) -> dict:
    texto = texto.strip()
    texto = re.sub(r"^```(?:json)?\s*|\s*```$", "", texto, flags=re.I | re.M).strip()
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", texto, re.S)
        if not m:
            raise
        return json.loads(m.group(0))


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
def gerar_plano(dados: dict, overrides: dict | None = None, contexto: str = "",
                citacoes: list[str] | None = None) -> dict:
    cfg = carregar_config(overrides)
    if not cfg["api_key"]:
        d = _demo(dados)
        d["fontes"] = "\n".join("• " + c for c in (citacoes or []))
        return d

    prompt = montar_prompt(dados, contexto)
    if cfg["provider"] == "gemini":
        bruto = _chamar_gemini(cfg, prompt)
    else:
        bruto = _chamar_openai(cfg, prompt)

    obj = _extrair_json(bruto)
    resultado = {k: _limpar(obj.get(k, "")) for k in CAMPOS}
    resultado["tema"] = _limpar(obj.get("tema") or dados.get("conteudo", ""))
    # garante que as referências fornecidas constem nas fontes
    fontes = resultado.get("fontes", "")
    for c in (citacoes or []):
        chave = c.split(".")[0][:25].lower()
        if chave and chave not in fontes.lower():
            fontes = (fontes + "\n" if fontes else "") + "• " + c
    resultado["fontes"] = fontes
    resultado["_demo"] = False
    return resultado
