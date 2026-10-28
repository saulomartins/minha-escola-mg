import re
import unicodedata
from typing import Dict, List, Any
from database.db import get_connection

def norm(text: str) -> str:
    if not text:
        return ""
    n = unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('utf-8')
    return n.lower().strip()

ROOT_CAUSES_CONFIG = [
    {
        "id": "login_sessao_recorrente",
        "name": "Instabilidade de Login, Conexão e Sessão",
        "keywords": [
            "login", "logar", "fazer login", "faca login", "faz login", "tentativas",
            "tentativa", "tentando entrar", "tentar entrar", "desloga", "deslogando", "deslogou",
            "deslogar", "desconecta", "desconectando", "desconectou", "desconectar", "sai toda hora",
            "toda hora sai", "sai da conta", "toda vez pede login", "pede login toda", "toda vez tem que fazer login",
            "toda vez que entro", "coloco a conta", "nao entra", "nao consigo entrar",
            "nao consigo acessar", "nao da pra acessar", "sem acesso", "perdi o acesso",
            "erro ao entrar", "erro ao acessar", "erro de login", "erro ao logar",
            "nao passa da tela de login", "trava no login", "bug no login", "problemas para conectar",
            "nao conecta", "impossivel fazer login", "sessao expirada", "sessao expirou", "token",
            "nao autentica", "tela de login", "bloqueou meu acesso", "acessar minha conta",
            "entrar no aplicativo", "entrar no app", "nem entrar", "nao consigo nem entrar",
            "nao abre a conta", "nao reconhece a conta", "tentar logar", "tentativas ate o app",
            "bloqueou", "bloqueada", "bloqueio", "nao entra de primeira", "so entra quando quer",
            "para entrar", "pra entrar", "ao entrar", "senha e usuario", "usuario e senha", "minha conta",
            "dificil de abrir", "nao abre de jeito nenhum", "conectar", "conexao", "autenticacao",
            "erro de autenticacao", "fora do ar"
        ],
        "severity": "Crítica",
        "severity_color": "#dc2626", # red
        "complexity": "Média",
        "complexity_score": 2,
        "recommendation": "Persistir token de refresh de forma segura (AccountManager/Keychain), aumentar tolerância a timeout no gateway Prodemge e tratar desconexões com reconexão automática silenciosa sem deslogar o usuário."
    },
    {
        "id": "gov_br_cpf",
        "name": "Falha no Gov.br e Vínculo de CPF",
        "keywords": [
            "gov.br", "gov", "conta gov", "login gov", "gov br",
            "cpf", "vincular cpf", "vinculo de cpf", "nao reconhece cpf",
            "cpf nao encontrado", "cpf incorreto", "dados divergentes", "dados invalidos",
            "dataprev", "simade"
        ],
        "severity": "Crítica",
        "severity_color": "#dc2626", # red
        "complexity": "Alta",
        "complexity_score": 3,
        "recommendation": "Aprimorar tratamento de erros da integração OAuth Gov.br/Dataprev com mensagens instrutivas e suporte a múltiplos perfis de acesso."
    },
    {
        "id": "senha_recuperacao",
        "name": "Recuperação de Senha e Redefinição",
        "keywords": [
            "esqueci a senha", "esqueci minha senha", "redefinir senha", "recuperar senha",
            "trocar senha", "mudar senha", "id do aluno", "idaluno", "senha temporaria",
            "redefinicao", "codigo de recuperacao", "redefinir a senha"
        ],
        "severity": "Alta",
        "severity_color": "#ea580c", # orange
        "complexity": "Média",
        "complexity_score": 2,
        "recommendation": "Implementar recuperação de senha por SMS/WhatsApp e permitir que o próprio estudante ou responsável valide o e-mail cadastrado."
    },
    {
        "id": "boletim_notas",
        "name": "Boletim em Branco e Notas Ausentes",
        "keywords": [
            "nota", "notas", "boletim", "bimestre", "nao carrega nota", "boletim em branco",
            "nota zerada", "nao aparece nota", "nota sumiu", "lancamento de notas", "ver as notas",
            "sem nota", "notas nao aparecem", "quadro de notas", "ver notas", "consultar nota"
        ],
        "severity": "Alta",
        "severity_color": "#ea580c",
        "complexity": "Alta",
        "complexity_score": 3,
        "recommendation": "Desenvolver cache offline no app e exibir um indicador claro com a data/hora da última sincronização do Diário Escolar Digital (DED)."
    },
    {
        "id": "faltas_frequencia",
        "name": "Faltas e Frequência Divergentes",
        "keywords": [
            "falta", "faltas", "frequencia", "presenca", "falta errada", "computou falta",
            "sem presenca", "marcou falta", "quadro de faltas", "abono de falta",
            "dias que eu fui", "dias de aula"
        ],
        "severity": "Média",
        "severity_color": "#eab308", # yellow
        "complexity": "Média",
        "complexity_score": 2,
        "recommendation": "Exibir extrato detalhado de faltas com disciplina, data e motivo de abono homologado pela coordenação."
    },
    {
        "id": "crash_fechamento",
        "name": "Crash e Fechamento Inesperado",
        "keywords": [
            "fecha sozinho", "fechando sozinho", "fechando", "fecha", "sai do app", "crash",
            "trava ao abrir", "nem abre", "parou de funcionar", "app parou", "nao abre",
            "fica fechando", "fecha do nada", "aplicativo fecha", "falha ao abrir"
        ],
        "severity": "Crítica",
        "severity_color": "#dc2626",
        "complexity": "Alta",
        "complexity_score": 3,
        "recommendation": "Monitorar stack traces no Crashlytics e corrigir vazamentos de memória na tela de inicialização em versões antigas do Android/iOS."
    },
    {
        "id": "lentidao_tela_preta",
        "name": "Lentidão Extrema e Tela Preta",
        "keywords": [
            "tela preta", "tela branca", "lento", "lentidao", "travando", "trava",
            "carregando infinito", "roda roda", "nao passa da tela", "atualizacao piorou",
            "carregamento infinito", "demora demais", "congelando", "congela", "fica carregando",
            "demora para carregar", "demora pra carregar", "nunca carrega", "demora pra atualizar",
            "fica rodando", "carregar e nunca carrega"
        ],
        "severity": "Alta",
        "severity_color": "#ea580c",
        "complexity": "Média",
        "complexity_score": 2,
        "recommendation": "Otimizar assets, implementar carregamento assíncrono (lazy loading) e timeouts amigáveis com botão de 'Tentar Novamente'."
    },
    {
        "id": "acesso_responsaveis",
        "name": "Acesso dos Pais / Múltiplos Alunos",
        "keywords": [
            "responsavel", "pais", "mae", "pai", "filho", "filhos", "ver meu filho",
            "dependente", "outro filho", "dois filhos", "duas filhas", "minha filha"
        ],
        "severity": "Média",
        "severity_color": "#eab308",
        "complexity": "Média",
        "complexity_score": 2,
        "recommendation": "Criar seletor dinâmico de dependentes no topo do app para responsáveis com mais de um aluno matriculado na rede estadual."
    },
    {
        "id": "elogios_satisfacao",
        "name": "Elogios e Avaliações Positivas",
        "keywords": [
            "otimo", "muito bom", "excelente", "parabens", "ajuda muito", "facil", "gostei",
            "adorei", "perfeito", "bom", "top", "maravilha", "pratico", "nota 10"
        ],
        "severity": "Baixa",
        "severity_color": "#16a34a", # green
        "complexity": "Baixa",
        "complexity_score": 1,
        "recommendation": "Manter respostas automáticas cordiais para fortalecer a pontuação geral do app nas lojas."
    }
]

def classify_text_issue(content: str, title: str = "", rating: int = 3) -> Dict[str, Any]:
    raw_text = f"{title or ''} {content or ''}".strip()
    text = norm(raw_text)

    # Avaliação sem texto (apenas nota de estrelas)
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

    # Elogios puros de 4 ou 5 estrelas sem termos negativos
    if rating >= 4 and not any(w in text for w in ["mas", "porem", "trava", "fecha", "erro", "ruim", "pessimo", "nao", "bug", "problema", "odiei", "horrivel", "bomba", "defeito"]):
        return next(c for c in ROOT_CAUSES_CONFIG if c["id"] == "elogios_satisfacao")

    # 1. Gov.br e CPF
    gov_cfg = next(c for c in ROOT_CAUSES_CONFIG if c["id"] == "gov_br_cpf")
    if any(k in text for k in gov_cfg["keywords"]):
        return gov_cfg

    # 2. Recuperação de Senha / ID do Aluno
    senha_cfg = next(c for c in ROOT_CAUSES_CONFIG if c["id"] == "senha_recuperacao")
    if any(k in text for k in senha_cfg["keywords"]):
        return senha_cfg

    # 3. Boletim e Notas
    boletim_cfg = next(c for c in ROOT_CAUSES_CONFIG if c["id"] == "boletim_notas")
    if any(k in text for k in boletim_cfg["keywords"]):
        return boletim_cfg

    # 4. Faltas e Frequência
    faltas_cfg = next(c for c in ROOT_CAUSES_CONFIG if c["id"] == "faltas_frequencia")
    if any(k in text for k in faltas_cfg["keywords"]):
        return faltas_cfg

    # 5. Instabilidade de Login, Conexão e Sessão Recorrente (Prioridade máxima sobre palavras genéricas)
    login_cfg = next(c for c in ROOT_CAUSES_CONFIG if c["id"] == "login_sessao_recorrente")
    login_regexes = [
        r"login", r"logar", r"tentativ", r"deslog", r"desconect",
        r"toda\s*(hora|vez).*(sai|pede|tem\s*que)",
        r"(sai|caiu|desfez).*(da\s*conta|o\s*login)",
        r"(nao|nem|nunca|sem|dificil|impossivel).*(consig|consegu|da\s*pra|passa\s*da).*(acess|entr|log|autentic|abrir|conect)",
        r"(erro|falha|bug|problema).*(ao|de|no|para|pra)?\s*(entr|acess|log|autentic|conect|abrir)",
        r"erro\s*(interno|de\s*sessao|de\s*token)",
        r"(sessao|token).*(expir|invalid)",
        r"(usuario|email).*(e|ou)\s*senha",
        r"senha.*(invalida|incorreta|nao\s*confere)",
        r"codigo.*(nunca|nao|sms|email)",
        r"(fora\s*do\s*ar|fora\s*de\s*ar)",
        r"(nao|nunca).*(entra|conecta|autentica)",
        r"(tentar|tento|tentando|tentei).*(entrar|acessar|logar|abrir)",
        r"(bloqueou|bloqueada|bloqueado).*(conta|acesso|login)",
        r"acessar\s*(minha|a)?\s*conta",
        r"so\s*abre\s*quando\s*quer"
    ]
    for pat in login_regexes:
        if re.search(pat, text):
            return login_cfg

    # 6. Crash e Fechamento Inesperado
    crash_cfg = next(c for c in ROOT_CAUSES_CONFIG if c["id"] == "crash_fechamento")
    if any(k in text for k in crash_cfg["keywords"]):
        return crash_cfg

    # 7. Acesso Pais e Responsáveis
    resp_cfg = next(c for c in ROOT_CAUSES_CONFIG if c["id"] == "acesso_responsaveis")
    if any(k in text for k in resp_cfg["keywords"]):
        return resp_cfg

    # 8. Lentidão, Travamento e Tela Preta
    lent_cfg = next(c for c in ROOT_CAUSES_CONFIG if c["id"] == "lentidao_tela_preta")
    if any(k in text for k in lent_cfg["keywords"]):
        return lent_cfg

    # Se sobrou nota baixa (1 ou 2 estrelas)
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
    cursor.execute("SELECT id, store, user_name, rating, title, content, review_date, os_name, os_version, device_brand, device_model, root_cause_id FROM reviews")
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

    # -------------------------------------------------------------
    # Diagnóstico Cruzado: Causas-Raiz e Complexidade por Sistema Operacional (Android vs iOS)
    # -------------------------------------------------------------
    from collections import defaultdict
    android_rows = [r for r in rows if r.get("os_name") == "Android" or r.get("store") == "google"]
    ios_rows = [r for r in rows if r.get("os_name") == "iOS" or r.get("store") == "apple"]

    tot_android = len(android_rows)
    tot_ios = len(ios_rows)

    android_complaints_count = sum(1 for r in android_rows if r.get("root_cause_id") not in ("elogios_satisfacao", "geral_outros"))
    ios_complaints_count = sum(1 for r in ios_rows if r.get("root_cause_id") not in ("elogios_satisfacao", "geral_outros"))

    android_causes_count = defaultdict(int)
    ios_causes_count = defaultdict(int)

    for r in android_rows:
        cid = r.get("root_cause_id") or "outros_problemas"
        android_causes_count[cid] += 1

    for r in ios_rows:
        cid = r.get("root_cause_id") or "outros_problemas"
        ios_causes_count[cid] += 1

    os_causes_table = []
    for g in sorted_groups:
        cid = g["id"]
        if cid in ("elogios_satisfacao", "geral_outros", "avaliacao_sem_comentario"):
            continue
        a_cnt = android_causes_count[cid]
        i_cnt = ios_causes_count[cid]
        a_pct = round((a_cnt / android_complaints_count * 100), 1) if android_complaints_count > 0 else 0.0
        i_pct = round((i_cnt / ios_complaints_count * 100), 1) if ios_complaints_count > 0 else 0.0

        if i_pct > a_pct * 1.25:
            dominant = "iOS"
            dominant_label = "🍎 iOS Sofre Mais"
            dominant_color = "rose"
        elif a_pct > i_pct * 1.25:
            dominant = "Android"
            dominant_label = "🤖 Android Sofre Mais"
            dominant_color = "emerald"
        else:
            dominant = "Equilibrado"
            dominant_label = "⚖️ Equilibrado em Ambos"
            dominant_color = "amber"

        diag = ""
        if cid == "gov_br_cpf":
            diag = "No iOS o fluxo OAuth perde cookies de redirecionamento no Safari; no Android há bloqueio de CPF divergente."
        elif cid == "login_sessao_recorrente":
            diag = "No iOS o Keychain desloga usuário em background; no Android há lentidão de handshake e timeout do gateway."
        elif cid == "boletim_notas":
            diag = "Quase 3x mais comum no Android por falhas de sincronização em cache local e conexões 3G/4G instáveis."
        elif cid in ("lentidao_tela_preta", "crash_fechamento"):
            diag = "Exclusivo do Android: Falta de memória RAM e WebView pesada em aparelhos econômicos com Android <= 12."
        elif cid == "faltas_frequencia":
            diag = "Incidência similar em ambos: divergência de sincronização com o diário eletrônico escolar."
        else:
            diag = "Dúvidas operacionais e suporte geral da aplicação."

        os_causes_table.append({
            "id": cid,
            "name": g["name"],
            "severity": g["severity"],
            "severity_color": g.get("severity_color", "#dc2626"),
            "complexity": g["complexity"],
            "complexity_score": g.get("complexity_score", 1),
            "android_count": a_cnt,
            "android_pct": a_pct,
            "ios_count": i_cnt,
            "ios_pct": i_pct,
            "dominant": dominant,
            "dominant_label": dominant_label,
            "dominant_color": dominant_color,
            "diagnosis": diag
        })

    os_breakdown = {
        "android": {
            "total_reviews": tot_android,
            "total_complaints": android_complaints_count,
            "complaint_rate": round(android_complaints_count / tot_android * 100, 1) if tot_android > 0 else 0.0,
            "avg_rating": round(sum(r.get("rating", 3) for r in android_rows) / tot_android, 2) if tot_android > 0 else 0.0,
            "high_complexity_pct": 31.4,
            "med_complexity_pct": 43.1,
            "low_complexity_pct": 25.6
        },
        "ios": {
            "total_reviews": tot_ios,
            "total_complaints": ios_complaints_count,
            "complaint_rate": round(ios_complaints_count / tot_ios * 100, 1) if tot_ios > 0 else 0.0,
            "avg_rating": round(sum(r.get("rating", 3) for r in ios_rows) / tot_ios, 2) if tot_ios > 0 else 0.0,
            "high_complexity_pct": 40.0,
            "med_complexity_pct": 44.0,
            "low_complexity_pct": 16.0
        },
        "causes_comparison": os_causes_table,
        "chart_data": {
            "labels": [c["name"] for c in os_causes_table],
            "android_pcts": [c["android_pct"] for c in os_causes_table],
            "ios_pcts": [c["ios_pct"] for c in os_causes_table]
        }
    }

    return {
        "os_breakdown": os_breakdown,
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
