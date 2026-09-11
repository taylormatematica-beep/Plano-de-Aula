
Módulo de geração do conteúdo pedagógico via IA.

Suporta:
  - OpenAI (e qualquer API compatível: Groq, OpenRouter, Together, Ollama etc.)
  - Google Gemini

Configuração (variáveis de ambiente ou arquivo config.json ao lado deste arquivo):
  AI_PROVIDER = "openai" | "gemini"
  AI_API_KEY  = chave da API
  AI_MODEL    = ex.: "gpt-4o-mini" (OpenAI) ou "gemini-2.5-flash" (Gemini)
  AI_BASE_URL = (opcional, só OpenAI-compatível) ex.: "https://api.groq.com/openai/v1"
"""
import json
import os
import re
from pathlib import Path

import requests

BASE_DIR = Path(__file__).parent
CONFIG_FILE = BASE_DIR / "config.json"

CAMPOS = ["habilidade", "objetivo", "metodologia", "recursos", "avaliacao"]


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
        cfg["model"] = "gemini-2.5-flash" if cfg["provider"] == "gemini" else "gpt-4o-mini"
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

DISCIPLINA: {disciplina}
CONTEÚDO/TEMA: {conteudo}
TURMA: {serie} do Ensino Médio
DATA DE REFERÊNCIA (semana): {data}
QUANTIDADE DE AULAS NA SEMANA: {aulas} aula(s) de 50 minutos
OBSERVAÇÕES DO PROFESSOR: {observacoes}

Retorne um JSON com exatamente estas chaves (todas strings):

"tema": título curto e claro do tema da semana (máx. 12 palavras).

"habilidade": 1 a 3 habilidades da BNCC do Ensino Médio pertinentes ao conteúdo, cada uma em uma linha, no formato "(CÓDIGO) descrição oficial". Use códigos reais da BNCC (ex.: EM13MAT302, EM13LGG103, EM13CNT101, EM13CHS102). Separe as habilidades com quebra de linha.

"objetivo": objetivos de aprendizagem em 3 a 5 itens, cada item iniciado com "• " e com verbo no infinitivo (compreender, analisar, resolver, produzir...). Um item por linha.

"metodologia": desenvolvimento detalhado da(s) aula(s), organizado por momentos, no formato:
"1º MOMENTO – Acolhida e problematização (10 min): ..."
"2º MOMENTO – Desenvolvimento (25 min): ..."
"3º MOMENTO – Sistematização/atividade (15 min): ..."
Se houver mais de uma aula na semana, organize por "AULA 1", "AULA 2" etc., cada uma com seus momentos. Descreva o que o professor faz e o que os alunos fazem, com metodologias ativas quando fizer sentido. Um momento por linha.

"recursos": lista dos recursos didáticos necessários, cada item iniciado com "• ", um por linha (ex.: quadro, projetor, livro didático com capítulo, material impresso, aplicativos, materiais concretos).

"avaliacao": descrição da avaliação processual e formativa: instrumentos (participação, atividade, produção, exercícios), critérios observados e como será feito o retorno ao aluno. 3 a 6 linhas.

Seja específico para o conteúdo informado: cite exemplos, exercícios, textos, experimentos ou situações concretas relacionadas ao tema. Não use marcadores markdown (**, #, -). Use apenas "• " para listas."""


def montar_prompt(dados: dict) -> str:
    return USER_PROMPT.format(
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


GEMINI_FALLBACKS = ["gemini-2.5-flash", "gemini-flash-latest", "gemini-2.0-flash", "gemini-2.5-flash-lite"]
MODELOS_GEMINI_DESCONTINUADOS = {"gemini-1.5-flash", "gemini-1.5-pro", "gemini-1.5-flash-8b",
                                 "gemini-1.5-flash-latest", "gemini-1.5-pro-latest", "gemini-pro"}


def _gemini_request(model: str, api_key: str, body: dict) -> requests.Response:
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{model}:generateContent?key={api_key}")
    return requests.post(url, json=body, timeout=120)


def _chamar_gemini(cfg: dict, prompt: str) -> str:
    body = {
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.7, "responseMimeType": "application/json"},
    }
    modelo = cfg["model"].strip()
    if modelo in MODELOS_GEMINI_DESCONTINUADOS:
        modelo = GEMINI_FALLBACKS[0]  # 1.5 foi desligado pelo Google em set/2025
    candidatos = [modelo] + [m for m in GEMINI_FALLBACKS if m != modelo]

    ultimo_erro = None
    for m in candidatos:
        r = _gemini_request(m, cfg["api_key"], body)
        if r.status_code == 404:          # modelo não existe mais -> tenta o próximo
            ultimo_erro = f"modelo '{m}' não encontrado (404)"
            continue
        if r.status_code in (401, 403):
            raise RuntimeError("Chave de API do Gemini inválida ou sem permissão. "
                               "Gere outra em https://aistudio.google.com/app/apikey")
        if r.status_code == 429:
            raise RuntimeError("Limite de uso da API do 
