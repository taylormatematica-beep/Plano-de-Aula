"""
Integração com o Google Drive (OAuth 2.0 — conta Google da escola).

Fluxo:
  1. A coordenação cria um "OAuth Client ID" (tipo Web) no Google Cloud e informa
     GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET (variáveis de ambiente).
  2. Na tela de Configurações, a supervisão clica em "Conectar Google Drive" e autoriza.
  3. O refresh_token fica salvo no banco (tabela config); a partir daí os PDFs são
     enviados automaticamente para  <Pasta raiz>/<Ano letivo>/<Série>/<Disciplina>/.

Somente a API REST é usada (requests) — sem bibliotecas pesadas do Google.
"""
import json
import os
import re
import secrets
import time
import unicodedata
from datetime import datetime

import requests

import db
import fuso

CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "").strip()
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
SCOPE = "https://www.googleapis.com/auth/drive"  # acesso ao Drive (necessário para usar as pastas já existentes dos professores)
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
API = "https://www.googleapis.com/drive/v3"
UPLOAD = "https://www.googleapis.com/upload/drive/v3/files"

_token_cache = {"access": None, "exp": 0.0}
_pasta_cache: dict[str, str] = {}


# --------------------------------------------------------------------------- #
# Estado / configuração
# --------------------------------------------------------------------------- #
def credenciais_ok() -> bool:
    return bool(CLIENT_ID and CLIENT_SECRET)


def conectado() -> bool:
    return credenciais_ok() and bool(db.config_get("drive_refresh_token"))


def status() -> dict:
    return {
        "credenciais": credenciais_ok(),
        "conectado": conectado(),
        "conta": db.config_get("drive_conta"),
        "pasta_raiz_nome": db.config_get("drive_pasta_nome", "Planos de Aula"),
        "pasta_raiz_link": db.config_get("drive_pasta_link"),
        "auto": db.config_get("drive_auto", "1") == "1",
        "estrutura": db.config_get("drive_estrutura", "professor"),
        "acesso_total": "auth/drive " in (db.config_get("drive_escopo", "") + " "),
        "visto_atualiza": db.config_get("drive_visto_atualiza", "1") == "1",
    }


def desconectar():
    db.config_del("drive_refresh_token", "drive_conta", "drive_pasta_id", "drive_pasta_link")
    _token_cache.update(access=None, exp=0.0)
    _pasta_cache.clear()


# --------------------------------------------------------------------------- #
# OAuth
# --------------------------------------------------------------------------- #
def url_autorizacao(redirect_uri: str, state: str) -> str:
    from urllib.parse import urlencode
    q = {
        "client_id": CLIENT_ID, "redirect_uri": redirect_uri, "response_type": "code",
        "scope": SCOPE + " openid email", "access_type": "offline", "prompt": "consent",
        "include_granted_scopes": "true", "state": state,
    }
    return AUTH_URL + "?" + urlencode(q)


def trocar_codigo(code: str, redirect_uri: str) -> dict:
    r = requests.post(TOKEN_URL, data={
        "code": code, "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
        "redirect_uri": redirect_uri, "grant_type": "authorization_code",
    }, timeout=30)
    r.raise_for_status()
    tok = r.json()
    if "refresh_token" not in tok:
        raise RuntimeError("O Google não devolveu o refresh_token. Desconecte o app em "
                           "https://myaccount.google.com/permissions e tente novamente.")
    db.config_set("drive_refresh_token", tok["refresh_token"])
    db.config_set("drive_escopo", tok.get("scope", ""))
    _token_cache.update(access=tok["access_token"], exp=time.time() + tok.get("expires_in", 3600) - 60)
    # e-mail da conta conectada
    try:
        u = requests.get("https://www.googleapis.com/oauth2/v3/userinfo",
                         headers=_auth(), timeout=15).json()
        db.config_set("drive_conta", u.get("email", ""))
    except Exception:
        pass
    _pasta_cache.clear()
    db.config_del("drive_pasta_id", "drive_pasta_link")
    return tok


def _access_token() -> str:
    if _token_cache["access"] and time.time() < _token_cache["exp"]:
        return _token_cache["access"]
    rt = db.config_get("drive_refresh_token")
    if not rt:
        raise RuntimeError("Google Drive não conectado.")
    r = requests.post(TOKEN_URL, data={
        "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
        "refresh_token": rt, "grant_type": "refresh_token",
    }, timeout=30)
    if r.status_code != 200:
        raise RuntimeError("Autorização do Google Drive expirou ou foi revogada. "
                           "Reconecte em Configurações → Google Drive.")
    tok = r.json()
    _token_cache.update(access=tok["access_token"], exp=time.time() + tok.get("expires_in", 3600) - 60)
    return tok["access_token"]


def _auth() -> dict:
    return {"Authorization": f"Bearer {_access_token()}"}


# --------------------------------------------------------------------------- #
# Pastas
# --------------------------------------------------------------------------- #
def _limpo(nome: str) -> str:
    nome = re.sub(r"[\\/:*?\"<>|]+", "-", nome or "").strip()
    return nome or "Sem nome"


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def _listar_subpastas(pai: str | None) -> list[dict]:
    q = "mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    q += f" and '{pai}' in parents" if pai else " and 'root' in parents"
    pastas, token = [], None
    while True:
        params = {"q": q, "fields": "nextPageToken,files(id,name)", "pageSize": 200,
                  "supportsAllDrives": "true", "includeItemsFromAllDrives": "true"}
        if token:
            params["pageToken"] = token
        r = requests.get(f"{API}/files", headers=_auth(), params=params, timeout=30)
        r.raise_for_status()
        j = r.json()
        pastas += j.get("files", [])
        token = j.get("nextPageToken")
        if not token:
            return pastas


def _buscar_pasta(nome: str, pai: str | None) -> str | None:
    """Procura a pasta pelo nome. Ignora acentos, maiúsculas e espaços extras
    (ex.: 'ana lima' encontra 'Ana Lima'; 'Profª Ana Lima' também é aceita se contiver o nome)."""
    alvo = _norm(nome)
    pastas = _listar_subpastas(pai)
    for f in pastas:                      # 1) igual
        if _norm(f["name"]) == alvo:
            return f["id"]
    for f in pastas:                      # 2) pasta cujo nome contém o nome do professor (ou vice-versa)
        n = _norm(f["name"])
        if alvo and (alvo in n or (n and n in alvo)):
            return f["id"]
    return None


def pasta_do_professor(nome: str, pasta_id_fixa: str | None = None) -> str:
    """Pasta do professor dentro da raiz: usa o ID fixo (definido pela supervisão) ou localiza/cria pelo nome."""
    if pasta_id_fixa:
        return pasta_id_fixa
    raiz, _ = pasta_raiz()
    return _pasta(nome or "Sem nome", raiz)


def _criar_pasta(nome: str, pai: str | None) -> str:
    meta = {"name": nome, "mimeType": "application/vnd.google-apps.folder"}
    if pai:
        meta["parents"] = [pai]
    r = requests.post(f"{API}/files", headers={**_auth(), "Content-Type": "application/json"},
                      params={"fields": "id", "supportsAllDrives": "true"}, json=meta, timeout=30)
    r.raise_for_status()
    return r.json()["id"]


def _pasta(nome: str, pai: str | None) -> str:
    nome = _limpo(nome)
    chave = f"{pai or 'root'}/{nome}"
    if chave in _pasta_cache:
        return _pasta_cache[chave]
    fid = _buscar_pasta(nome, pai) or _criar_pasta(nome, pai)
    _pasta_cache[chave] = fid
    return fid


def pasta_raiz() -> tuple[str, str]:
    """Garante a pasta raiz (ex.: 'Planos de Aula') e devolve (id, link)."""
    fid = db.config_get("drive_pasta_id")
    if fid:
        return fid, db.config_get("drive_pasta_link")
    nome = db.config_get("drive_pasta_nome", "Planos de Aula")
    fid = _pasta(nome, None)
    link = f"https://drive.google.com/drive/folders/{fid}"
    db.config_set("drive_pasta_id", fid)
    db.config_set("drive_pasta_link", link)
    return fid, link


def definir_pasta_raiz(nome_ou_link: str):
    """Aceita um nome de pasta OU o link/ID de uma pasta já existente no Drive."""
    nome_ou_link = (nome_ou_link or "").strip()
    m = re.search(r"folders/([A-Za-z0-9_-]{10,})", nome_ou_link) or re.fullmatch(r"([A-Za-z0-9_-]{25,})", nome_ou_link)
    _pasta_cache.clear()
    if m:
        fid = m.group(1)
        # confirma acesso e pega o nome
        r = requests.get(f"{API}/files/{fid}", headers=_auth(),
                         params={"fields": "id,name", "supportsAllDrives": "true"}, timeout=30)
        if r.status_code != 200:
            escopo = db.config_get("drive_escopo", "")
            if "auth/drive " not in escopo + " ":
                raise RuntimeError("A permissão concedida ao Google é limitada (só arquivos criados pelo app). "
                                   "Clique em Desconectar, depois em Conectar Google Drive novamente e, na tela do Google, "
                                   "aceite 'Ver, editar, criar e excluir todos os seus arquivos do Google Drive'.")
            raise RuntimeError("Não foi possível acessar essa pasta com a conta conectada. "
                               "Verifique se a pasta é da mesma conta ou foi compartilhada com ela como Editor.")
        db.config_set("drive_pasta_nome", r.json().get("name") or "Pasta")
        db.config_set("drive_pasta_id", fid)
        db.config_set("drive_pasta_link", f"https://drive.google.com/drive/folders/{fid}")
    else:
        db.config_set("drive_pasta_nome", nome_ou_link or "Planos de Aula")
        db.config_del("drive_pasta_id", "drive_pasta_link")
        pasta_raiz()


# --------------------------------------------------------------------------- #
# Upload
# --------------------------------------------------------------------------- #
def _slug(t: str) -> str:
    t = unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9]+", "-", t).strip("-")


def _ano_letivo(data_ref: str) -> str:
    m = re.search(r"(\d{4})", data_ref or "")
    return m.group(1) if m else str(fuso.hoje().year)


def nome_arquivo(dados: dict) -> str:
    if dados.get("_nome_arquivo"):
        return dados["_nome_arquivo"].replace("  ", " ")
    return (f"Plano de Aula - {dados.get('disciplina','')} - {dados.get('serie','')} - "
            f"{_slug(dados.get('data',''))} - {dados.get('professor','')}.pdf").replace("  ", " ")


def enviar_pdf(pdf: bytes, dados: dict, file_id_existente: str | None = None) -> dict:
    """Envia (ou atualiza) o PDF. Estrutura conforme configuração:
       - 'professor' (padrão): Raiz/<Pasta do professor>/arquivo.pdf
       - 'serie':              Raiz/Ano/Série/Disciplina/arquivo.pdf
       Devolve {id, link, pasta_link}."""
    if db.config_get("drive_estrutura", "professor") == "professor":
        p_disc = pasta_do_professor(dados.get("professor", ""), dados.get("_pasta_id"))
    else:
        raiz, _ = pasta_raiz()
        p_ano = _pasta(_ano_letivo(dados.get("data", "")), raiz)
        p_serie = _pasta(dados.get("serie", "Sem série"), p_ano)
        p_disc = _pasta(dados.get("disciplina", "Sem disciplina"), p_serie)

    nome = _limpo(nome_arquivo(dados))
    meta = {"name": nome, "description": f"Tema: {dados.get('_tema','')} | Gerado pelo Docea (assistente pedagógico)"}
    boundary = "planoaula" + secrets.token_hex(8)
    corpo = (
        f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n{json.dumps(meta, ensure_ascii=False)}\r\n"
        f"--{boundary}\r\nContent-Type: application/pdf\r\n\r\n"
    ).encode("utf-8") + pdf + f"\r\n--{boundary}--".encode()
    headers = {**_auth(), "Content-Type": f"multipart/related; boundary={boundary}"}
    params = {"uploadType": "multipart", "fields": "id,webViewLink", "supportsAllDrives": "true"}

    if file_id_existente:
        r = requests.patch(f"{UPLOAD}/{file_id_existente}", headers=headers, params=params, data=corpo, timeout=120)
        if r.status_code == 404:
            file_id_existente = None
    if not file_id_existente:
        meta["parents"] = [p_disc]
        corpo = (
            f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n{json.dumps(meta, ensure_ascii=False)}\r\n"
            f"--{boundary}\r\nContent-Type: application/pdf\r\n\r\n"
        ).encode("utf-8") + pdf + f"\r\n--{boundary}--".encode()
        r = requests.post(UPLOAD, headers=headers, params=params, data=corpo, timeout=120)
    r.raise_for_status()
    j = r.json()
    return {"id": j["id"], "link": j.get("webViewLink", f"https://drive.google.com/file/d/{j['id']}/view"),
            "pasta_link": f"https://drive.google.com/drive/folders/{p_disc}"}
