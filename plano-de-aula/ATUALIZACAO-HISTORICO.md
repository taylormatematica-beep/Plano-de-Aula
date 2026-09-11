# Atualização: Histórico + Assinaturas

## O que mudou
- **Campo Professor(a)** obrigatório no formulário (o nome fica salvo no navegador).
- **Histórico** (`/historico`): cada professor vê e reabre os próprios planos; a supervisão vê todos,
  filtra por professor/disciplina/série/tema, marca **"visto"** e baixa qualquer PDF.
- **Bloco de assinaturas** no PDF: Professor(a) | Supervisão Pedagógica | Direção, com data.
- **Configurações** da IA agora só podem ser alteradas pela supervisão.
- Planos reabertos do histórico podem ser editados e o PDF gerado novamente.

## Arquivos a enviar ao GitHub
Substituir: `app.py`, `pdf.py`, `requirements.txt`, `render.yaml`, `templates/index.html`
Novos:      `db.py`, `templates/historico.html`

Mais simples: apagar o repositório antigo e subir o conteúdo de `plano-de-aula-para-github.zip`.

## IMPORTANTE — banco de dados no Render
O disco do plano gratuito do Render é **apagado a cada publicação**. Para o histórico não sumir,
é preciso um banco PostgreSQL (gratuito por 30 dias; depois US$ 7/mês — ou veja alternativa abaixo).

### Passo a passo no Render
1. Dashboard → **New +** → **PostgreSQL** → nome `plano-de-aula-db` → plano **Free** → **Create Database**.
2. Na página do banco, copie **Internal Database URL**.
3. Abra o serviço web `plano-de-aula` → **Environment** → adicione:

| Variável            | Valor                                             |
|---------------------|---------------------------------------------------|
| `DATABASE_URL`      | (a Internal Database URL copiada)                 |
| `SUPERVISAO_SENHA`  | senha só da supervisão (ex.: `sup2026`)           |
| `SUPERVISAO_NOME`   | nome do(a) supervisor(a) impresso no PDF          |
| `DIRECAO_NOME`      | nome do(a) diretor(a) impresso no PDF             |

4. **Save Changes** → o Render republica sozinho.

### Alternativa gratuita permanente (banco fora do Render)
Crie um PostgreSQL gratuito em **https://neon.tech** (ou Supabase), copie a "connection string"
e use-a em `DATABASE_URL`. Funciona igual e não expira.

### Sem banco (não recomendado)
Se `DATABASE_URL` não for definida, o sistema usa um arquivo SQLite local — funciona, mas no
Render gratuito o histórico é perdido a cada nova publicação.

## Links para divulgar
- Professores: `https://SEU-APP.onrender.com`  (senha `APP_SENHA`)
- Supervisão: `https://SEU-APP.onrender.com/supervisao/login`  (senha `SUPERVISAO_SENHA`)

## Rotina sugerida com o Google Drive
Professor gera → baixa o PDF → coloca na pasta do Drive da turma/disciplina.
A supervisão usa `/historico` para conferir o que foi gerado, marcar como visto e,
se precisar, baixar novamente qualquer plano (sem depender do professor).
