# Envio automático para o Google Drive

Depois de configurado, **todo PDF baixado é salvo automaticamente** no Drive da escola, **na pasta de cada professor**:

```
Planos de Aula 2026/            ← pasta raiz (a que já existe na conta da escola)
├── Ana Lima/                   ← pasta do professor (já existente ou criada pelo sistema)
│   ├── Plano de Aula - Matemática - 3º ano - 14-09-2026 - Ana Lima.pdf
│   └── Plano de Aula - Matemática - 2º ano - 14-09-2026 - Ana Lima.pdf
└── Bruno Reis/
    └── Plano de Aula - História - 1º ano - 21-09-2026 - Bruno Reis.pdf
```

**Como o sistema acha a pasta do professor:** pelo nome cadastrado na conta dele, dentro da pasta raiz,
ignorando acentos, maiúsculas e prefixos (ex.: "Profª Ana Lima" serve). Se não encontrar, cria.
Se o nome da pasta for muito diferente, a supervisão cola o link da pasta na coluna **Pasta no Drive** em **Usuários**.

Alternativa (⚙ Configurações → Organização das pastas): `Ano → Série → Disciplina`.

- Se o professor editar e baixar de novo, o **mesmo arquivo é atualizado** (não duplica).
- No histórico há um botão **▲ Abrir** (link direto no Drive) ou **▲ Enviar** (para planos antigos).
- Como as pastas dos professores já existem, o app pede permissão de acesso ao Drive da conta conectada (escopo `drive`).
  Use uma conta da escola dedicada aos planos; a permissão pode ser revogada a qualquer momento em myaccount.google.com → Segurança.
- **Compartilhamento:** os PDFs herdam as permissões da pasta. Se a pasta "Ana Lima" já está compartilhada com a Ana, ela vê os planos automaticamente.

A configuração é feita **uma única vez** pela coordenação (~15 min) e usa a **conta Google da escola**.

---

## Parte 1 — Criar as credenciais no Google Cloud (10 min)

1. Entre com a conta Google da escola em **https://console.cloud.google.com**.
2. No topo, clique no seletor de projeto → **Novo projeto** → nome `Plano de Aula` → **Criar** (e selecione-o).
3. Menu ☰ → **APIs e serviços** → **Biblioteca** → busque **Google Drive API** → **Ativar**.
4. Menu ☰ → **APIs e serviços** → **Tela de permissão OAuth** (ou "Branding"):
   - Tipo de usuário: **Externo** → **Criar**
   - Nome do app: `Assistente de Plano de Aula` · e-mail de suporte: o da escola · e-mail do desenvolvedor: o da escola → **Salvar e continuar** até o fim.
   - Em **Público-alvo / Usuários de teste**, clique em **Adicionar usuários** e inclua o e-mail da conta da escola. *(Enquanto o app estiver em "Teste", só esses e-mails podem conectar — é suficiente.)*
5. Menu ☰ → **APIs e serviços** → **Credenciais** → **+ Criar credenciais** → **ID do cliente OAuth**:
   - Tipo de aplicativo: **Aplicativo da Web**
   - Nome: `Plano de Aula Web`
   - **URIs de redirecionamento autorizados** → **+ Adicionar URI** e cole **exatamente**:
     ```
     https://SEU-APP.onrender.com/drive/callback
     ```
     *(troque `SEU-APP.onrender.com` pelo endereço real do seu sistema; a URI exata também aparece em Configurações → Google Drive dentro do app)*
   - **Criar**. Copie o **ID do cliente** e a **Chave secreta do cliente**.

## Parte 2 — Informar as credenciais ao sistema (2 min)

No **Render** → serviço `plano-de-aula` → **Environment** → adicione:

| Variável | Valor |
|---|---|
| `GOOGLE_CLIENT_ID` | o ID do cliente (termina com `.apps.googleusercontent.com`) |
| `GOOGLE_CLIENT_SECRET` | a chave secreta (começa com `GOCSPX-`) |
| `PUBLIC_URL` | `https://SEU-APP.onrender.com` (opcional, mas recomendado) |

**Save Changes** e aguarde o redeploy.

## Parte 3 — Conectar (1 min)

1. Entre no sistema como **supervisão** → **⚙ Configurações** → seção **▲ Google Drive** → **Conectar Google Drive**.
2. Escolha a conta Google da escola e clique em **Permitir**.
   - Se aparecer "O Google não verificou este app": clique em **Avançado** → **Acessar Assistente de Plano de Aula (não seguro)**. É normal para apps internos em modo teste.
3. Você volta ao sistema com a mensagem **"Google Drive conectado com sucesso"**. A pasta **Planos de Aula** é criada na raiz do Drive.

### Opcional: usar uma pasta que já existe
Em Configurações → Google Drive → **Trocar pasta raiz**, cole o link da pasta (ex.: `https://drive.google.com/drive/folders/1AbC...`). A pasta deve pertencer à conta conectada ou estar compartilhada com ela como **Editor**. Funciona também com **Drives compartilhados**.

---

## Problemas comuns

| Sintoma | Causa / solução |
|---|---|
| `redirect_uri_mismatch` | A URI cadastrada no Google Cloud não é idêntica à do app. Confira em Configurações → Google Drive (sem barra final, `https`). |
| `access_denied` / "app não verificado" bloqueando | Adicione o e-mail da escola em **Usuários de teste** na tela de permissão OAuth. |
| "O Google não devolveu o refresh_token" | Acesse https://myaccount.google.com/permissions, remova o app e conecte de novo. |
| "Autorização expirou" após ~7 dias | Apps em modo **Teste** expiram a cada 7 dias. Solução: na tela de permissão OAuth clique em **Publicar app** (não exige verificação para o escopo `drive.file`). Depois reconecte. |
| PDF baixou mas não foi ao Drive | A mensagem de erro aparece na tela; o download nunca é bloqueado. Reenvie pelo histórico (▲ Enviar). |

## Segurança
- O sistema usa o escopo mínimo (`drive.file`): só vê e edita arquivos que ele mesmo criou.
- O token fica no banco de dados do servidor; professores não têm acesso à conta Google.
- **Desconectar** em Configurações revoga o uso; ou remova o app em https://myaccount.google.com/permissions.
