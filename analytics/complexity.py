from typing import Dict, List, Any
from database.db import get_connection

ROOT_CAUSES_CONFIG = [
    {
        "id": "gov_br_cpf",
        "name": "Falha no Gov.br e Vínculo de CPF",
        "keywords": ["gov.br", "gov", "cpf", "conta gov", "vincular", "vínculo", "não reconhece cpf", "nao reconhece cpf", "dados inválidos", "dados invalidos", "cpf incorreto", "erro de autenticação", "login gov", "gov br"],
        "severity": "Crítica",
        "severity_color": "#dc2626", # red
        "complexity": "Alta",
        "complexity_score": 3,
        "recommendation": "Aprimorar tratamento de erros da integração OAuth Gov.br/Dataprev com mensagens instrutivas e suporte a múltiplos perfis de acesso."
    },
    {
        "id": "senha_recuperacao",
        "name": "Recuperação de Senha e Redefinição",
        "keywords": ["esqueci a senha", "esqueci minha senha", "redefinir", "recuperar senha", "recuperar", "código", "codigo", "trocar senha", "senha invalida", "senha inválida", "não envia email", "nao envia email", "email não chega", "e-mail não chega", "senha", "senhas", "bloqueada", "bloqueou", "não consigo entrar", "nao consigo entrar", "não entra", "nao entra", "não consigo acessar", "nao consigo acessar", "erro ao entrar"],
        "severity": "Alta",
        "severity_color": "#ea580c", # orange
        "complexity": "Média",
        "complexity_score": 2,
        "recommendation": "Implementar recuperação de senha por SMS/WhatsApp e permitir que o próprio estudante ou responsável valide o e-mail cadastrado."
    },
    {
        "id": "boletim_notas",
        "name": "Boletim em Branco e Notas Ausentes",
        "keywords": ["nota", "notas", "boletim", "bimestre", "não carrega nota", "nao carrega nota", "boletim em branco", "nota zerada", "não aparece nota", "nao aparece nota", "nota sumiu", "lançamento de notas", "ver as notas", "sem nota", "notas não aparecem"],
        "severity": "Alta",
        "severity_color": "#ea580c",
        "complexity": "Alta",
        "complexity_score": 3,
        "recommendation": "Desenvolver cache offline no app e exibir um indicador claro com a data/hora da última sincronização do Diário Escolar Digital (DED)."
    },
    {
        "id": "faltas_frequencia",
        "name": "Faltas e Frequência Divergentes",
        "keywords": ["falta", "faltas", "frequência", "frequencia", "presença", "presenca", "falta errada", "computou falta", "sem presença", "marcou falta"],
        "severity": "Média",
        "severity_color": "#eab308", # yellow
        "complexity": "Média",
        "complexity_score": 2,
        "recommendation": "Exibir extrato detalhado de faltas com disciplina, data e motivo de abono homologado pela coordenação."
    },
    {
        "id": "crash_fechamento",
        "name": "Crash e Fechamento Inesperado",
        "keywords": ["fecha sozinho", "fechando sozinho", "fechando", "fecha", "sai do app", "crash", "trava ao abrir", "nem abre", "parou de funcionar", "app parou", "não abre", "nao abre", "fica saindo", "sai da conta"],
        "severity": "Crítica",
        "severity_color": "#dc2626",
        "complexity": "Alta",
        "complexity_score": 3,
        "recommendation": "Monitorar stack traces no Crashlytics e corrigir vazamentos de memória na tela de inicialização em versões antigas do Android/iOS."
    },
    {
        "id": "lentidao_tela_preta",
        "name": "Lentidão Extrema e Tela Preta",
        "keywords": ["tela preta", "tela branca", "lento", "lentidão", "lentidao", "travando", "trava", "carregando infinito", "roda roda", "não passa da tela", "nao passa da tela", "atualização piorou", "atualizacao piorou", "ruim", "péssimo", "pessimo", "odiei", "horrível", "horrivel", "uma porcaria"],
        "severity": "Alta",
        "severity_color": "#ea580c",
        "complexity": "Média",
        "complexity_score": 2,
        "recommendation": "Otimizar assets, implementar carregamento assíncrono (lazy loading) e timeouts amigáveis com botão de 'Tentar Novamente'."
    },
    {
        "id": "acesso_responsaveis",
        "name": "Acesso dos Pais / Múltiplos Alunos",
        "keywords": ["responsável", "responsavel", "pais", "mãe", "mae", "pai", "filho", "filhos", "ver meu filho", "dependente", "outro filho", "dois filhos"],
        "severity": "Média",
        "severity_color": "#eab308",
        "complexity": "Média",
        "complexity_score": 2,
        "recommendation": "Criar seletor dinâmico de dependentes no topo do app para responsáveis com mais de um aluno matriculado na rede estadual."
    },
    {
        "id": "elogios_satisfacao",
        "name": "Elogios e Avaliações Positivas",
        "keywords": ["ótimo", "otimo", "muito bom", "excelente", "parabéns", "parabens", "ajuda muito", "fácil", "facil", "gostei", "adorei", "perfeito", "bom", "top", "maravilha", "prático", "pratico", "nota 10"],
        "severity": "Baixa",
        "severity_color": "#16a34a", # green
        "complexity": "Baixa",
        "complexity_score": 1,
        "recommendation": "Manter respostas automáticas cordiais para fortalecer a pontuação geral do app nas lojas."
    }
]

def classify_text_issue(content: str, title: str = "", rating: int = 3) -> Dict[str, Any]:
    text = f"{title} {content}".lower().strip()
    
    # Se for avaliação sem texto (apenas estrelas)
    if not text:
        if rating >= 4:
            return next(c for c in ROOT_CAUSES_CONFIG if c["id"] == "elogios_satisfacao")
        else:
            return {
                "id": "avaliacao_sem_comentario",
                "name": "Nota Baixa sem Comentário",
                "severity": "Média",
                "severity_color": "#eab308",
                "complexity": "Baixa",
                "complexity_score": 1,
                "recommendation": "Responder convidando o usuário a detalhar a experiência pelo canal oficial de suporte."
            }

    # Se tiver nota alta (4 ou 5) e nenhum termo negativo forte, classifica como elogio
    if rating >= 4 and not any(w in text for w in ["mas", "porém", "porem", "trava", "fecha", "erro", "ruim", "péssimo", "pessimo", "não", "nao"]):
        return next(c for c in ROOT_CAUSES_CONFIG if c["id"] == "elogios_satisfacao")

    # Busca casamento de palavras-chave nas causas de problemas (priorizando ordem)
    for cfg in ROOT_CAUSES_CONFIG:
        if cfg["id"] == "elogios_satisfacao":
            continue
        for kw in cfg["keywords"]:
            if kw in text:
                return cfg

    # Se sobrou nota baixa
    if rating <= 2:
        return {
            "id": "outros_problemas",
            "name": "Problemas Gerais e Dúvidas",
            "severity": "Média",
            "severity_color": "#eab308",
            "complexity": "Baixa",
            "complexity_score": 1,
            "recommendation": "Analisar caso a caso no atendimento da escola e coletar marca/modelo do aparelho."
        }

    return {
        "id": "geral_outros",
        "name": "Geral / Sugestões Diversas",
        "severity": "Baixa",
        "severity_color": "#16a34a",
        "complexity": "Baixa",
        "complexity_score": 1,
        "recommendation": "Triar sugestões de novos recursos com o comitê pedagógico da SEE-MG."
    }

def get_detailed_problem_analytics() -> Dict[str, Any]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, store, user_name, rating, title, content, review_date FROM reviews")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()

    total_reviews = len(rows)
    if total_reviews == 0:
        return {}

    groups = {}
    for r in rows:
        cluster = classify_text_issue(r.get("content", ""), r.get("title", ""), r.get("rating", 3))
        cid = cluster["id"]
        if cid not in groups:
            from ai.auto_reply_templates import PROBLEM_TEMPLATES_CONFIG
            cfg_tmpl = PROBLEM_TEMPLATES_CONFIG.get(cid, {})
            groups[cid] = {
                "id": cid,
                "name": cluster["name"],
                "severity": cluster["severity"],
                "severity_color": cluster.get("severity_color", "#64748b"),
                "complexity": cluster["complexity"],
                "complexity_score": cluster.get("complexity_score", 1),
                "recommendation": cluster["recommendation"],
                "description": cfg_tmpl.get("description", "Reclamações gerais ou relatos de uso do aplicativo."),
                "keywords": cfg_tmpl.get("keywords", cluster.get("keywords", [])),
                "templates": cfg_tmpl.get("templates", {}),
                "count": 0,
                "ratings": [],
                "sample_reviews": []
            }
        
        groups[cid]["count"] += 1
        groups[cid]["ratings"].append(r["rating"])
        
        # Salva até 3 exemplos reais com texto
        if r.get("content") and len(groups[cid]["sample_reviews"]) < 3:
            groups[cid]["sample_reviews"].append({
                "user_name": r.get("user_name", "Usuário"),
                "rating": r.get("rating"),
                "store": r.get("store"),
                "content": r.get("content"),
                "date": r.get("review_date")
            })

    # Ordena por frequência
    sorted_groups = sorted(groups.values(), key=lambda x: x["count"], reverse=True)

    # Métricas agregadas
    total_complaints = sum(g["count"] for g in sorted_groups if g["id"] != "elogios_satisfacao")

    # Adiciona médias e percentuais
    for g in sorted_groups:
        g["percentage"] = round((g["count"] / total_reviews) * 100, 1)
        g["complaint_percentage"] = round((g["count"] / total_complaints * 100), 1) if total_complaints > 0 and g["id"] != "elogios_satisfacao" else 0
        g["avg_rating"] = round(sum(g["ratings"]) / len(g["ratings"]), 2) if g["ratings"] else 0.0
        
        # Prioridade = Volume * (5 - nota média) / complexidade
        urgency = max(1.0, 5.0 - g["avg_rating"])
        g["priority_score"] = round(g["count"] * urgency, 1)

    # Distribuição de Severidade
    severity_dist = {"Crítica": 0, "Alta": 0, "Média": 0, "Baixa": 0}
    for g in sorted_groups:
        if g["severity"] in severity_dist:
            severity_dist[g["severity"]] += g["count"]

    # Distribuição de Complexidade Técnica
    complexity_dist = {"Crítica": 0, "Alta": 0, "Média": 0, "Baixa": 0}
    for g in sorted_groups:
        if g["complexity"] in complexity_dist:
            complexity_dist[g["complexity"]] += g["count"]

    # Top 5 Problemas para Backlog
    problem_backlog = [g for g in sorted_groups if g["id"] not in ("elogios_satisfacao", "avaliacao_sem_comentario")]
    problem_backlog.sort(key=lambda x: x["priority_score"], reverse=True)

    # Dados para Gráficos
    pareto_items = [g for g in sorted_groups if g["id"] != "elogios_satisfacao"][:6]

    return {
        "total_reviews": total_reviews,
        "total_complaints": total_complaints,
        "problems_ranking": sorted_groups,
        "severity_distribution": severity_dist,
        "complexity_distribution": complexity_dist,
        "top_offenders": problem_backlog[:5],
        "charts": {
            "pareto": {
                "labels": [g["name"] for g in pareto_items],
                "counts": [g["count"] for g in pareto_items],
                "percentages": [g["complaint_percentage"] for g in pareto_items]
            },
            "complexity": {
                "labels": ["Baixa", "Média", "Alta", "Crítica"],
                "data": [complexity_dist.get("Baixa", 0), complexity_dist.get("Média", 0), complexity_dist.get("Alta", 0), complexity_dist.get("Crítica", 0)],
                "colors": ["#16a34a", "#eab308", "#ea580c", "#dc2626"]
            },
            "severity": {
                "labels": ["Crítica", "Alta", "Média", "Baixa"],
                "data": [severity_dist.get("Crítica", 0), severity_dist.get("Alta", 0), severity_dist.get("Média", 0), severity_dist.get("Baixa", 0)],
                "colors": ["#dc2626", "#ea580c", "#eab308", "#16a34a"]
            },
            "rating_impact": {
                "labels": [g["name"] for g in pareto_items],
                "ratings": [g["avg_rating"] for g in pareto_items]
            }
        }
    }
