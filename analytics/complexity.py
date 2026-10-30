import re
import unicodedata
from collections import defaultdict
from typing import Dict, List, Any, Optional
from database.db import get_connection
from analytics.taxonomy import get_root_causes_config, get_root_causes_map

def norm(text: str) -> str:
    if not text:
        return ""
    n = unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('utf-8')
    return n.lower().strip()

# Compatibilidade retroativa direta
ROOT_CAUSES_CONFIG = get_root_causes_config()

def classify_text_issue(content: str, title: str = "", rating: int = 3, domain: Optional[str] = None) -> Dict[str, Any]:
    """
    Classifica uma avaliação em uma Causa-Raiz utilizando a taxonomia configurada para o domínio do app ativo.
    """
    raw_text = f"{title or ''} {content or ''}".strip()
    text = norm(raw_text)

    causes = get_root_causes_config(domain=domain)
    elogio_cfg = next((c for c in causes if c["id"] == "elogios_satisfacao"), causes[-1])

    # Avaliação sem texto (apenas nota de estrelas)
    if not text:
        if rating >= 4:
            return elogio_cfg
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
    negative_signals = [
        "mas", "porem", "trava", "fecha", "erro", "ruim", "pessimo", "nao", "bug", 
        "problema", "odiei", "horrivel", "bomba", "defeito", "falha", "lento"
    ]
    if rating >= 4 and not any(w in text for w in negative_signals):
        return elogio_cfg

    # Prioridade para Instabilidade de Login / Sessão se houver termos característicos
    login_cfg = next((c for c in causes if c["id"] == "login_sessao_recorrente"), None)
    if login_cfg:
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

    # Percorre as causas do domínio e universais testando as palavras-chave
    for cfg in causes:
        if cfg["id"] in ("elogios_satisfacao", "outros_problemas"):
            continue
        keywords = cfg.get("keywords", [])
        if any(k in text for k in keywords):
            return cfg

    # Fallback
    if rating >= 4:
        return elogio_cfg

    outros_cfg = next((c for c in causes if c["id"] == "outros_problemas"), causes[-1])
    return outros_cfg

def get_detailed_problem_analytics(app_id: Optional[str] = None, domain: Optional[str] = None) -> Dict[str, Any]:
    """
    Retorna a matriz de complexidade técnica, causas-raiz ofensoras e diagnóstico
    cruzado por Sistema Operacional especificamente para o aplicativo ativo (app_id).
    """
    target_app_id = app_id or (lambda: (__import__('config').get_app_id()))()
    target_domain = domain or (lambda: (__import__('config').get_domain()))()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, store, user_name, rating, title, content, review_date, 
               os_name, os_version, device_brand, device_model, root_cause_id 
        FROM reviews 
        WHERE app_id = ?
    """, (target_app_id,))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()

    total_reviews = len(rows)
    if total_reviews == 0:
        return {
            "total_reviews": 0,
            "total_complaints": 0,
            "groups": [],
            "severity_distribution": {"Crítica": 0, "Alta": 0, "Média": 0, "Baixa": 0},
            "complexity_distribution": {"Crítica": 0, "Alta": 0, "Média": 0, "Baixa": 0},
            "backlog": [],
            "pareto": [],
            "os_breakdown": {
                "total_android": 0,
                "total_ios": 0,
                "android_complaints": 0,
                "ios_complaints": 0,
                "causes_table": []
            }
        }

    causes = get_root_causes_config(domain=target_domain)
    causes_map = {c["id"]: c for c in causes}

    groups: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        cluster = classify_text_issue(r.get("content", ""), r.get("title", ""), r.get("rating", 3), domain=target_domain)
        cid = cluster["id"]
        if cid not in groups:
            cfg_info = causes_map.get(cid, cluster)
            groups[cid] = {
                "id": cid,
                "name": cluster["name"],
                "severity": cluster["severity"],
                "severity_color": cluster.get("severity_color", "#64748b"),
                "complexity": cluster["complexity"],
                "complexity_score": cluster.get("complexity_score", 1),
                "recommendation": cluster["recommendation"],
                "description": cfg_info.get("description", "Reclamações relatadas no uso do aplicativo."),
                "keywords": cfg_info.get("keywords", cluster.get("keywords", [])),
                "templates": cfg_info.get("templates", {}),
                "count": 0,
                "ratings": [],
                "sample_reviews": []
            }

        groups[cid]["count"] += 1
        groups[cid]["ratings"].append(r["rating"])

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
    total_complaints = sum(g["count"] for g in sorted_groups if g["id"] != "elogios_satisfacao")

    # Adiciona médias e percentuais
    for g in sorted_groups:
        g["percentage"] = round((g["count"] / total_reviews) * 100, 1)
        g["complaint_percentage"] = round((g["count"] / total_complaints * 100), 1) if total_complaints > 0 and g["id"] != "elogios_satisfacao" else 0
        g["avg_rating"] = round(sum(g["ratings"]) / len(g["ratings"]), 2) if g["ratings"] else 0.0
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

    # Top Problemas para Backlog
    problem_backlog = [g for g in sorted_groups if g["id"] not in ("elogios_satisfacao", "avaliacao_sem_comentario")]
    problem_backlog.sort(key=lambda x: x["priority_score"], reverse=True)

    pareto_items = [g for g in sorted_groups if g["id"] != "elogios_satisfacao"][:6]

    # -------------------------------------------------------------
    # Diagnóstico Cruzado: Causas-Raiz por Sistema Operacional (Android vs iOS)
    # -------------------------------------------------------------
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
            diag = f"Incidência proporcionalmente maior no iOS ({i_pct}% vs {a_pct}% no Android). Recomenda-se auditar compatibilidade no WebKit/Safari e ciclo de vida no iOS."
        elif a_pct > i_pct * 1.25:
            dominant = "Android"
            dominant_label = "🤖 Android Sofre Mais"
            dominant_color = "emerald"
            diag = f"Incidência concentrada no Android ({a_pct}% vs {i_pct}% no iOS). Aponta para diversidade de fabricantes, restrições de memória RAM e versões legadas de SO."
        else:
            dominant = "Equilibrado"
            dominant_label = "⚖️ Equilibrado em Ambos"
            dominant_color = "amber"
            diag = f"Distribuição equilibrada ({a_pct}% Android vs {i_pct}% iOS), indicando que a causa decorre de serviços de backend ou regras de negócio centrais da aplicação."

        os_causes_table.append({
            "id": cid,
            "name": g["name"],
            "severity": g["severity"],
            "severity_color": g["severity_color"],
            "complexity": g["complexity"],
            "android_count": a_cnt,
            "android_pct": a_pct,
            "ios_count": i_cnt,
            "ios_pct": i_pct,
            "dominant": dominant,
            "dominant_label": dominant_label,
            "dominant_color": dominant_color,
            "recommendation": g["recommendation"],
            "diagnostic": diag
        })

    pareto_labels = [g["name"] for g in pareto_items]
    pareto_counts = [g["count"] for g in pareto_items]
    pareto_pcts = [g["percentage"] for g in pareto_items]

    charts = {
        "pareto": {
            "labels": pareto_labels,
            "counts": pareto_counts,
            "percentages": pareto_pcts
        }
    }

    return {
        "total_reviews": total_reviews,
        "total_complaints": total_complaints,
        "groups": sorted_groups,
        "problems_ranking": sorted_groups,
        "charts": charts,
        "severity_distribution": severity_dist,
        "complexity_distribution": complexity_dist,
        "backlog": problem_backlog,
        "pareto": pareto_items,
        "os_breakdown": {
            "total_android": tot_android,
            "total_ios": tot_ios,
            "android_complaints": android_complaints_count,
            "ios_complaints": ios_complaints_count,
            "causes_table": os_causes_table
        }
    }
