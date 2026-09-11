# Como publicar e gerar o link para os professores

O sistema precisa ficar hospedado em um servidor na internet para ter um link permanente.
Abaixo estão três caminhos — o primeiro é o mais simples e **gratuito**.

> Antes de começar, tenha em mãos:
> - **Chave de IA**: gratuita em https://aistudio.google.com/app/apikey (Google Gemini)
> - **Senha de acesso** que será compartilhada com os professores (ex.: `bernardes2026`)

---

## Opção 1 — Render.com (gratuito, ~10 minutos) ✅ recomendado

1. Crie uma conta em https://github.com e outra em https://render.com (pode entrar com a conta do GitHub).
2. No GitHub, clique em **New repository** → nome `plano-de-aula` → **Create**.
   Depois em **uploading an existing file** e arraste **todos os arquivos desta pasta** (`plano-de-aula/`). Clique em **Commit changes**.
3. No Render, clique em **New +** → **Web Service** → conecte ao repositório `plano-de-aula`.
4. O Render lê o arquivo `render.yaml` automaticamente. Confirme:
   - Runtime: **Python**
   - Start command: `gunicorn -w 2 -t 180 -b 0.0.0.0:$PORT app:app`
   - Plano: **Free**
5. Em **Environment** adicione as variáveis:
   | Nome | Valor |
   |---|---|
   | `AI_PROVIDER` | `gemini` |
   | `AI_MODEL` | `gemini-1.5-flash` |
   | `AI_API_KEY` | *(sua chave do Gemini)* |
   | `APP_SENHA` | *(senha para os professores)* |
   | `SECRET_KEY` | *(qualquer texto longo aleatório)* |
6. Clique em **Create Web Service**. Em ~3 minutos o Render mostra o link, no formato:
   **`https://plano-de-aula.onrender.com`** ← este é o link para os professores.

> Observação do plano gratuito: após 15 min sem uso o serviço "dorme"; o primeiro acesso
> seguinte demora ~30–50 s para acordar. Se isso incomodar, o plano pago custa US$ 7/mês.

---

## Opção 2 — Hugging Face Spaces (gratuito, sem "dormir" tanto)

1. Conta em https://huggingface.co → **New Space** → SDK: **Docker** → visibilidade **Public**.
2. Envie todos os arquivos desta pasta (há um `Dockerfile` pronto).
3. Em **Settings → Variables and secrets**, crie os *secrets* `AI_PROVIDER`, `AI_MODEL`, `AI_API_KEY`, `APP_SENHA`, `SECRET_KEY`.
4. Link: `https://SEU-USUARIO-plano-de-aula.hf.space`

---

## Opção 3 — Computador/servidor da própria escola (rede interna)

```bash
pip install -r requirements.txt
set APP_SENHA=bernardes2026          (Windows)   |  export APP_SENHA=bernardes2026  (Linux/Mac)
set AI_PROVIDER=gemini
set AI_API_KEY=SUA_CHAVE
python app.py
```
Os professores acessam pelo IP do computador na rede da escola: `http://192.168.x.x:5000`.
Para um link externo sem servidor, use um túnel como **Cloudflare Tunnel** ou **ngrok** (`ngrok http 5000`).

---

## Depois de publicado

- Envie aos professores: **o link + a senha**. Nada mais é necessário.
- A chave da IA fica só no servidor; ninguém precisa configurá-la.
- Para trocar a senha, altere a variável `APP_SENHA` e reinicie o serviço.
- Para sair da sessão no navegador: `link/sair`.
