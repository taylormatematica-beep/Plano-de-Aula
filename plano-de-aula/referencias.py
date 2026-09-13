"""
Fontes de referência para a geração do plano de aula.

1) Base interna (sempre disponível): estrutura e conceitos-chave dos Cadernos de Formação
   do ICE (Modelo Escola da Escolha), BNCC e Currículo Referência de Minas Gerais.
2) Biblioteca (documentos enviados pela supervisão em PDF/TXT): o texto é extraído,
   dividido em trechos e os mais relevantes para o tema são incluídos no prompt.
"""
import re
import unicodedata

import db

# --------------------------------------------------------------------------- #
# Fontes fixas
# --------------------------------------------------------------------------- #
FONTES = {
    "bncc": {
        "nome": "BNCC – Base Nacional Comum Curricular (Ensino Médio)",
        "citacao": "BRASIL. Ministério da Educação. Base Nacional Comum Curricular: Ensino Médio. Brasília: MEC, 2018.",
        "padrao": True,
        "resumo": (
            "Competências gerais (10) e competências/habilidades específicas por área: Linguagens e suas Tecnologias "
            "(EM13LGG), Matemática e suas Tecnologias (EM13MAT), Ciências da Natureza e suas Tecnologias (EM13CNT), "
            "Ciências Humanas e Sociais Aplicadas (EM13CHS). Códigos no formato EM13XXX000."
        ),
    },
    "crmg": {
        "nome": "Currículo Referência de Minas Gerais – Ensino Médio",
        "citacao": "MINAS GERAIS. Secretaria de Estado de Educação. Currículo Referência de Minas Gerais: Ensino Médio. Belo Horizonte: SEE/MG, 2021.",
        "padrao": True,
        "resumo": (
            "Detalha as habilidades da BNCC por ano/série e componente curricular, com objetos de conhecimento e "
            "orientações pedagógicas para a rede estadual mineira. Organiza a Formação Geral Básica e os Itinerários "
            "Formativos, incluindo os componentes da parte diversificada do Ensino Médio em Tempo Integral (EMTI)."
        ),
    },
    "ice": {
        "nome": "Cadernos de Formação do ICE – Modelo Escola da Escolha",
        "citacao": "ICE – Instituto de Corresponsabilidade pela Educação. Cadernos de Formação: Modelo Pedagógico e Modelo de Gestão da Escola da Escolha. Recife: ICE, 2019.",
        "padrao": True,
        "resumo": "Modelo pedagógico e de gestão adotado no Ensino Médio em Tempo Integral de Minas Gerais.",
    },
}

# Conhecimento estruturado dos cadernos do ICE (usado no prompt quando a fonte "ice" está marcada)
ICE_CADERNOS = """
CADERNOS DE FORMAÇÃO DO ICE – MODELO ESCOLA DA ESCOLHA (síntese para orientar o plano de aula)

Caderno 1 – Memória e Concepção do Modelo / Concepção do Modelo da Escola da Escolha:
 • Centralidade do estudante e do seu PROJETO DE VIDA; escola como espaço de formação integral.
 • Três Eixos Formativos: Formação Acadêmica de Excelência, Formação para a Vida e Formação de Competências para o Século XXI.

Caderno 2 – Modelo Pedagógico: Princípios Educativos:
 • PROTAGONISMO: o estudante como ator principal e solução dos problemas reais (autonomia, autoria, participação).
 • QUATRO PILARES DA EDUCAÇÃO (Delors): aprender a conhecer, a fazer, a conviver e a ser.
 • PEDAGOGIA DA PRESENÇA: o educador presente, que acolhe, faz-se disponível e é referência (presença afetiva, ética e construtiva).
 • EDUCAÇÃO INTERDIMENSIONAL: dimensões cognitiva (logos), afetiva (pathos), corporal (eros) e espiritual (mythos).

Caderno 3 – Modelo Pedagógico: Conceitos:
 • Excelência acadêmica com formação para a vida; educação para valores; corresponsabilidade; replicabilidade.
 • Competências socioemocionais integradas ao currículo; avaliação formativa e devolutiva ao estudante.

Caderno 4 – Modelo Pedagógico: Metodologias de Êxito (parte diversificada / componentes curriculares):
 • PROJETO DE VIDA (componente central), ELETIVAS (temas de interesse, culminância), ESTUDO ORIENTADO (aprender a estudar:
   técnicas, planejamento, autonomia), PRÁTICAS EXPERIMENTAIS (vivência prática de Matemática, Física, Química e Biologia),
   PREPARAÇÃO PÓS-MÉDIO / PREPARAÇÃO ACADÊMICA, NIVELAMENTO (recuperação de habilidades básicas de Língua Portuguesa e Matemática).

Caderno 5 – Modelo Pedagógico: Metodologias de Êxito – Práticas Educativas:
 • ACOLHIMENTO (dos estudantes, das famílias, dos educadores), TUTORIA (acompanhamento personalizado do estudante),
   CLUBES DE PROTAGONISMO, LÍDERES DE TURMA, CONSELHO DE LÍDERES, avaliação semanal do Projeto de Vida.

Caderno 6 – Modelo Pedagógico: Ambientes de Aprendizagem (sala de aula, laboratórios, biblioteca, espaços de convivência)
 e Caderno 7 – Instrumentos e Rotinas Pedagógicas:
 • GUIA DE APRENDIZAGEM (contrato didático por bimestre: objetivos, fontes, atividades didáticas, atividades autodidáticas,
   atividades complementares e valores), PLANO DE AULA articulado ao Guia, ALINHAMENTO SEMANAL por área,
   NIVELAMENTO, ACOMPANHAMENTO PEDAGÓGICO, registro e uso de resultados para intervenção.
 • Aula estruturada: acolhida/problematização, desenvolvimento com metodologias ativas, sistematização, avaliação
   formativa e devolutiva; diversificação de estratégias (aula dialogada, trabalho em pares e grupos, resolução de problemas,
   experimentação, sala de aula invertida, seminários, produção autoral).

Caderno 8 – Modelo de Gestão: Tecnologia de Gestão Educacional (TGE):
 • Ciclo PDCA (Planejar, Executar, Checar, Agir), Plano de Ação da escola, Programa de Ação do educador,
   Educação pelo Trabalho, Ciclo Virtuoso, Excelência em Gestão, Corresponsabilidade.

Como isso deve aparecer no plano de aula:
 • Metodologia com protagonismo do estudante (ele faz, discute, produz) e pedagogia da presença (professor acolhe, circula, dá devolutiva).
 • Conexão explícita do conteúdo com o Projeto de Vida do estudante e com situações reais (sentido e significado).
 • Trabalho com os Quatro Pilares (conhecer/fazer/conviver/ser) e competências socioemocionais quando pertinente.
 • Articulação com Metodologias de Êxito quando fizer sentido: Estudo Orientado (tarefa autodidática), Práticas Experimentais,
   Nivelamento (estudantes com defasagem), Tutoria (encaminhamentos).
 • Avaliação formativa, processual, com devolutiva ao estudante e registro para o acompanhamento pedagógico.
""".strip()


# --------------------------------------------------------------------------- #
# Biblioteca (documentos enviados)
# --------------------------------------------------------------------------- #
STOP = set("""a o e de da do das dos em no na nos nas um uma uns umas para por com sem sobre entre ao aos à às que se
como mais menos muito pouco ser estar ter haver seu sua seus suas este esta isto esse essa isso aquele aquela aquilo
os as ou mas também já não sim qual quais quando onde porque porquê pois então assim ainda até após ante desde
ano anos aula aulas plano planos conteúdo conteúdos tema temas ensino médio série turma""".split())


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9 ]+", " ", t)


def _termos(t: str) -> set[str]:
    return {w for w in _norm(t).split() if len(w) > 2 and w not in STOP}


def dividir_em_trechos(texto: str, tamanho: int = 900, sobreposicao: int = 150) -> list[str]:
    texto = re.sub(r"[ \t]+", " ", texto or "")
    texto = re.sub(r"\n{3,}", "\n\n", texto).strip()
    if not texto:
        return []
    paras = [p.strip() for p in re.split(r"\n\s*\n", texto) if p.strip()]
    trechos, atual = [], ""
    for p in paras:
        if len(atual) + len(p) + 1 <= tamanho:
            atual = (atual + "\n" + p).strip()
        else:
            if atual:
                trechos.append(atual)
            while len(p) > tamanho:            # parágrafo gigante
                trechos.append(p[:tamanho])
                p = p[tamanho - sobreposicao:]
            atual = p
    if atual:
        trechos.append(atual)
    return trechos


def extrair_texto(nome_arquivo: str, conteudo: bytes) -> str:
    nome = nome_arquivo.lower()
    if nome.endswith(".pdf"):
        from io import BytesIO
        from pypdf import PdfReader
        r = PdfReader(BytesIO(conteudo))
        paginas = []
        for i, p in enumerate(r.pages):
            try:
                t = p.extract_text() or ""
            except Exception:
                t = ""
            if t.strip():
                paginas.append(f"[p. {i + 1}]\n{t}")
        return "\n\n".join(paginas)
    if nome.endswith(".docx"):
        from io import BytesIO
        import zipfile
        with zipfile.ZipFile(BytesIO(conteudo)) as z:
            xml = z.read("word/document.xml").decode("utf-8", "ignore")
        xml = re.sub(r"</w:p>", "\n", xml)
        return re.sub(r"<[^>]+>", "", xml)
    return conteudo.decode("utf-8", "ignore")


def buscar_trechos(consulta: str, doc_ids: list[int] | None, limite: int = 6) -> list[dict]:
    """Ranqueia trechos por sobreposição de termos com a consulta (tema + disciplina)."""
    termos = _termos(consulta)
    if not termos:
        return []
    candidatos = db.trechos_listar(doc_ids)
    pontuados = []
    for t in candidatos:
        tt = _termos(t["texto"])
        inter = termos & tt
        if not inter:
            continue
        score = len(inter) / (len(termos) ** 0.5) + 0.02 * sum(_norm(t["texto"]).count(w) for w in inter)
        pontuados.append((score, t))
    pontuados.sort(key=lambda x: -x[0])
    saida, por_doc = [], {}
    for score, t in pontuados:
        if por_doc.get(t["documento_id"], 0) >= 3:   # no máx. 3 trechos por documento
            continue
        por_doc[t["documento_id"]] = por_doc.get(t["documento_id"], 0) + 1
        saida.append(t)
        if len(saida) >= limite:
            break
    return saida


def montar_contexto(fontes: list[str], doc_ids: list[int], consulta: str) -> tuple[str, list[str]]:
    """Devolve (texto para o prompt, lista de citações das fontes usadas)."""
    partes, citacoes = [], []
    for k in ("bncc", "crmg", "ice"):
        if k in fontes:
            f = FONTES[k]
            citacoes.append(f["citacao"])
            if k == "ice":
                partes.append(ICE_CADERNOS)
            else:
                partes.append(f"{f['nome'].upper()}: {f['resumo']}")
    if doc_ids:
        trechos = buscar_trechos(consulta, doc_ids)
        docs_usados = {}
        for t in trechos:
            docs_usados.setdefault(t["documento_id"], t["titulo"])
        if trechos:
            bloco = ["TRECHOS DOS DOCUMENTOS DA BIBLIOTECA DA ESCOLA (use e cite quando pertinente):"]
            for t in trechos:
                pg = re.match(r"\[p\. (\d+)\]", t["texto"])
                ref = f"{t['titulo']}" + (f", p. {pg.group(1)}" if pg else "")
                bloco.append(f"--- Fonte: {ref} ---\n{t['texto'][:900]}")
            partes.append("\n".join(bloco))
        for did, titulo in docs_usados.items():
            d = db.documento_obter(did)
            citacoes.append(d.get("citacao") or titulo)
    return "\n\n".join(partes), citacoes
