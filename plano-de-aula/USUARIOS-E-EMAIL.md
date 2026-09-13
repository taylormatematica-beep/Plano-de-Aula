# Login individual dos professores (autocadastro)

## Como funciona para o professor
1. Acessa o sistema → **"É seu primeiro acesso?"**
2. Digita o e-mail institucional `nome@educacao.mg.gov.br` (outros domínios são recusados).
3. Recebe um e-mail com o botão **Criar minha senha** (válido por 48 h, uso único).
4. Informa nome completo + senha (mín. 8 caracteres, letras e números) e já entra.
5. Próximos acessos: e-mail + senha. "Esqueci minha senha" repete o fluxo.

Ninguém precisa ser cadastrado previamente. O nome do professor vai automaticamente para o plano e o PDF
(editável em **Minha conta**). O histórico fica vinculado ao e-mail.

---

## O que a supervisão precisa configurar (uma vez)

### 1. E-mail de saída — Gmail da escola (5 min)
1. Entre no Google da escola e ative a verificação em duas etapas:
   https://myaccount.google.com/signinoptions/two-step-verification
2. Crie uma **senha de app**: https://myaccount.google.com/apppasswords → nome `Plano de Aula` → **Criar** → copie os 16 caracteres.
3. **Render → Environment**:

| Variável | Valor |
|---|---|
| `SMTP_HOST` | `smtp.gmail.com` |
| `SMTP_PORT` | `587` |
| `SMTP_USER` | e-mail da escola (ex.: `escola@gmail.com`) |
| `SMTP_PASS` | a senha de app de 16 caracteres |
| `SMTP_FROM` | `Assistente de Plano de Aula <escola@gmail.com>` |

*(Alternativas: Brevo — `smtp-relay.brevo.com`; Outlook — `smtp.office365.com`; mesma porta 587.)*

### 2. Quem é supervisão + endereço público

| Variável | Valor |
|---|---|
| `SUPERVISAO_EMAILS` | e-mails da supervisão separados por vírgula |
| `PUBLIC_URL` | `https://SEU-APP.onrender.com` |
| `SUPERVISAO_SENHA` | *(opcional)* acesso de emergência em `/supervisao/login` |

`APP_SENHA` não é mais usada — pode remover.

### 3. Primeiro uso
1. Acesse `/primeiro-acesso` com seu e-mail (listado em `SUPERVISAO_EMAILS`) e crie sua senha — você entra como supervisão.
2. Envie aos professores:

> **Assistente de Plano de Aula** — acesse `https://SEU-APP.onrender.com`, clique em **"É seu primeiro acesso?"**,
> digite seu e-mail @educacao.mg.gov.br e siga o link que chegar (confira o spam). Crie sua senha e pronto.

---

## Tela 👥 Usuários (supervisão)
Mostra quem já criou senha e quem não; permite reenviar link, redefinir senha, promover a supervisão,
desativar ou excluir. Também aceita cadastrar e-mails em lote, se um dia for útil.

## Variáveis opcionais
| Variável | Padrão | Para quê |
|---|---|---|
| `DOMINIO_EMAIL` | `educacao.mg.gov.br` | domínio aceito |
| `DOMINIOS_EXTRAS` | — | outros domínios, separados por vírgula (ex.: para testes) |
| `LINK_VALIDADE_HORAS` | `48` | validade do link |

## Problemas comuns
| Sintoma | Solução |
|---|---|
| "O servidor de e-mail recusou o login" | No Gmail é obrigatório usar **senha de app**, não a senha normal. |
| E-mail não chega | Verifique spam; confira `/diagnostico` (linha E-mail SMTP); ou reenvie pela tela Usuários. |
| Link "expirado" ou "já utilizado" | Professor usa "Esqueci minha senha" para receber outro. |
| Sem SMTP configurado | O sistema segue funcionando: o link aparece na tela da supervisão para repassar manualmente. |
