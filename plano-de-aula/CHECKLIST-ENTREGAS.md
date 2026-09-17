# ✅ Checklist de entregas — Docea
**Escola Estadual Presidente Bernardes – Ensino Médio Integral (Pouso Alegre/MG)**
Atualizado em 14/09/2026

---

## 1. Núcleo: geração automática do plano de aula
- [x] Professor preenche só **4 campos**: matéria, conteúdo, data e série — o resto é automático
- [x] Geração por **inteligência artificial** (Gemini ou OpenAI; descoberta automática do modelo disponível)
- [x] PDF **idêntico ao modelo da escola**: logo, título, cabeçalho (Disciplina / Data / Turma / Supervisão), quadros Tema, Habilidade, Objetivo, Metodologia, Recursos, Avaliação
- [x] **Habilidades BNCC do Ensino Médio** com códigos reais (EM13…)
- [x] **Habilidades correlatas do Ensino Fundamental** (pré-requisitos) no quadro Habilidade, com filtro contra códigos inventados + momento de retomada/diagnóstico na metodologia (opcional, ligado por padrão)
- [x] Regras especiais para **cursos técnicos** (competências profissionais, sem inventar código BNCC), **Nivelamento** (habilidades EF) e **componentes da Escola da Escolha** (Competências Gerais + princípios do ICE)
- [x] Metodologia organizada por momentos; recursos; avaliação processual
- [x] **Pré-visualização editável** na tela antes de baixar (clicar no texto para ajustar)
- [x] Botão "Gerar novamente"
- [x] Campos opcionais: supervisão, direção, observações para a IA, data final da semana, nº de aulas
- [x] Modo demonstração quando a IA não está configurada
- [x] PDF com **quebra automática de página** para planos longos (corrigido erro "too large on page")

## 2. Matérias e séries
- [x] Séries: 1º, 2º e 3º ano do Ensino Médio
- [x] **34 componentes conforme as matrizes 2026** da escola, agrupados no menu:
  - Formação Geral Básica (12)
  - Parte Diversificada / Escola da Escolha (10): Projeto de Vida, Eletiva, Estudos Orientados, Práticas Experimentais, Nivelamento LP e MAT, Cultura Digital e Fundamentos de IA, Ferramentas para o Mundo do Trabalho, PICS, Práticas de Leitura e Escrita
  - Técnico – Automação Industrial III e IV (2º ano)
  - Técnico – Mecatrônica III e IV (2º ano)
  - Técnico – Desenvolvimento de Sistemas (3º ano): 7 componentes
- [x] Opção "Outra…" para imprevistos

## 3. Fontes de pesquisa e referências
- [x] Fontes fixas: **BNCC-EM**, **Currículo Referência de Minas Gerais**, **Cadernos do ICE / Escola da Escolha** (síntese interna: Protagonismo, 4 Pilares, Pedagogia da Presença, Educação Interdimensional, Metodologias de Êxito, TGE)
- [x] Quadro **FONTES / REFERÊNCIAS** (ABNT) ao final de todo plano, na tela e no PDF
- [x] Página **📚 Referências (/biblioteca)**: supervisão envia PDFs/DOCX/TXT (ex.: Cadernos do ICE originais); texto indexado; trechos ligados ao tema são entregues à IA e citados
- [x] "Testar busca" para ver quais trechos seriam usados
- [x] Seleção de fontes na tela (recolhida, tudo marcado por padrão)

## 4. Contas, login e permissões
- [x] Login individual com **e-mail institucional @educacao.mg.gov.br**
- [x] **Autocadastro** ("É seu primeiro acesso?") → link de criação de senha por e-mail (válido 48 h, uso único)
- [x] Recuperação de senha pelo mesmo fluxo
- [x] Perfis **professor** e **supervisão** (definido por SUPERVISAO_EMAILS)
- [x] Nome do professor vem da conta (não precisa digitar)
- [x] Página **Minha conta** (/conta) para alterar nome/senha
- [x] Página **Usuários** (/usuarios) para a supervisão: listar, ativar/desativar, excluir, reenviar link
- [x] Login de emergência da supervisão por senha (/supervisao/login)
- [x] Senhas com hash seguro; tokens sha256

## 5. E-mail
- [x] Envio via **Brevo API** (funciona no plano gratuito do Render, que bloqueia SMTP)
- [x] Alternativas: Resend API ou SMTP (hospedagem paga)
- [x] Remetente validado (Gmail) — resolvido bloqueio DMARC do domínio da SEE
- [x] Botão **"Testar e-mail"** na página Usuários
- [x] E-mails com layout da escola (criação de senha, plano visado)

## 6. Histórico
- [x] Todo plano gerado fica salvo no banco (SQLite local / PostgreSQL no Render)
- [x] Professor vê **seus** planos; supervisão vê **todos**
- [x] Filtros por professor, disciplina, série e busca por tema
- [x] Reabrir plano, baixar PDF novamente, excluir
- [x] Estatísticas: total, visados, pendentes, professores

## 7. Visto eletrônico da supervisão
- [x] Botão **✍ Dar visto** no histórico (só supervisão)
- [x] Carimbo no PDF na coluna Supervisão: **VISTO ELETRÔNICO + nome + data/hora + código de verificação** (ex.: 1B4D-CBB1, gerado com chave secreta — não falsificável)
- [x] Linha "Data" da supervisão preenchida automaticamente
- [x] Plano visado fica **travado para edição** (tela em modo leitura; servidor ignora alterações)
- [x] **E-mail ao professor** avisando do visto, com link para o PDF assinado
- [x] **↩ Desfazer visto** (libera edição)
- [x] **Visto em bloco**: caixas de seleção no histórico + "Dar visto nos selecionados" (pula os já visados)
- [x] Professor vê status "Pendente" / "✔ visto por … em …"
- [x] Vistos antigos migrados para o novo formato

## 8. Assinaturas
- [x] Bloco com duas linhas: **Professor(a) | Supervisão Pedagógica** (Direção removida a pedido)

## 9. Horário
- [x] Todo o sistema em **horário de Brasília** (America/Sao_Paulo): histórico, tokens, visto, diagnóstico

## 10. Infraestrutura e operação
- [x] Publicado no **Render** (gunicorn com threads) + banco **PostgreSQL no Neon (São Paulo)** com pool de conexões e cache de configurações, código no GitHub `taylormatematica-beep/Plano-de-Aula` (pasta `plano-de-aula/`)
- [x] Página **/diagnostico** (supervisão): IA, banco, e-mail, horário, variáveis de ambiente
- [x] **/healthz** público para monitoramento
- [x] Configurações da IA pela tela (⚙ Configurações) ou por variáveis de ambiente
- [x] Chaves de API nunca aparecem em mensagens de erro
- [x] Migrações automáticas do banco (novas colunas/tabelas criadas sozinhas)
- [x] **Google Drive ATIVO**: PDF salvo automaticamente na pasta de cada professor (localizada pelo nome, ou por link em Usuários); mesmo arquivo atualizado ao editar e ao receber o visto; opção alternativa Ano → Série → Disciplina; botão **Enviar todos ao Drive** para planos antigos

## 11. Documentação (na pasta do projeto)
- [x] `LEIA-ME.md` — instalação, variáveis, uso, fontes/ICE
- [x] `USUARIOS-E-EMAIL.md` — guia passo a passo de contas e Brevo, com tabela de erros
- [x] `render.yaml` — modelo de configuração do Render
- [x] `GOOGLE-DRIVE.md` — guia do Google Cloud/Drive
- [x] `MIGRAR-BANCO-NEON.md` + `migrar_banco.py` — referência para mover o banco, se um dia for preciso
- [x] `CHECKLIST-ENTREGAS.md` — este arquivo

---

## 🔒 Pendência de segurança (sua ação)
- [ ] **Revogar e recriar as duas chaves da API Gemini** que apareceram no chat no início do projeto (Google AI Studio → API keys → excluir → criar nova → atualizar AI_API_KEY no Render)

## 💡 Ideias na fila (não iniciadas)
- [ ] Painel da supervisão: entregas da semana por matéria/turma, pendentes em destaque
- [ ] Sequência didática / plano bimestral a partir dos planos semanais
- [ ] Visto eletrônico da Direção
- [ ] Exportar em .docx
- [ ] "Keep-alive" para evitar o Render dormir (plano gratuito)
- [ ] Se a lentidão voltar a incomodar: mover o site para hospedagem com região São Paulo (Fly.io/Koyeb), perto do banco

## Provas e atividades (a partir dos planos)
- [x] Página `/atividades`: professor seleciona 1+ planos → escolhe tipo (prova, simulado, atividade, lista, trabalho, recuperação), formato (mista / só múltipla escolha / só discursiva), quantidade de cada, dificuldade, avaliativa ou não, valor total.
- [x] IA gera questões (5 alternativas, resolução, resposta esperada, critérios, habilidade BNCC). Máx. 30 questões.
- [x] Valor dividido igualmente; editável questão por questão; soma conferida na barra; "Dividir igualmente".
- [x] Editor: enunciado, alternativas, alternativa correta, resolução, resposta, critérios, linhas, remover questão, título, instruções.
- [x] PDF da prova (cabeçalho do estudante, instruções, valor por questão, linhas, cartão-resposta) + PDF do gabarito (quadro de respostas + resoluções + critérios).
- [x] Guardadas na tabela `atividades`; professor vê as suas, supervisão vê todas; envio ao Drive (pasta do professor).
- [x] Histórico de planos: checkbox para todos + botão "Gerar prova/atividade com os selecionados".
- [x] Alerta de plano duplicado (disciplina+série + mesma semana ou conteúdo parecido) com "Abrir e editar" / "Inserir novo".
- [x] Salvar edição de plano; salvar plano visado remove o visto automaticamente.
- [x] Exportar lista de usuários (Excel com resumo / CSV).
- [x] Cota Gemini (429): só modelos da chave, lite como reserva, AI_API_KEYS_EXTRA em rodízio.

## Correção automática de provas
- [x] Aplicação com código de 6 letras + QR + link público `/prova/<código>`; folha PDF para projetar.
- [x] Prova online no celular: identificação (nome + nº), alternativas embaralhadas por aluno, rascunho salvo no aparelho, tempo opcional, envio único (bloqueia duplicado), opção de mostrar acertos.
- [x] Múltipla escolha corrigida na hora; discursivas com nota sugerida pela IA + comentário + nível de confiança → professor confirma/ajusta (individual ou "aceitar todas").
- [x] Prova em papel: lançamento em lote "nº; nome; letras; notas disc." → corrige igual.
- [x] Página `/correcao/<id>`: lista de alunos com mapa de acertos, situação (corrigida/revisar), revisão por aluno, anular questão/crédito parcial, recorrigir, encerrar/reabrir.
- [x] Estatísticas: média, faixas, % acerto por questão (distribuição A–E), por habilidade BNCC, questões mais erradas.
- [x] Exportar Excel (Notas / Por questão / Resumo) e Relatório PDF.
- [x] Permissões: professor só vê as suas; supervisão vê todas; rotas do aluno são públicas (só código).
- [x] Cartão-resposta com leitura óptica (OMR): PDF com marcas de canto, bolhas nº da chamada + A–E (até 50 ME), cartões com nomes; upload de fotos → leitura com correção de perspectiva/rotação → conferência (recorte do nome, miniatura anotada, dúvidas em vermelho editáveis) → lançar e corrigir.
- [x] Scanner no celular (`/scanner/<id>`): câmera ao vivo, pré-detecção local, leitura estabilizada (2 iguais), vibração, painel de confirmação com autocomplete de nomes, nota na hora, histórico dos últimos lidos; QR na página de correção para abrir no celular.
