import re
import unicodedata
from datetime import datetime
from typing import Dict, List, Any, Optional
from database.db import get_connection
from analytics.complexity import classify_text_issue, ROOT_CAUSES_CONFIG

def strip_accents(text: str) -> str:
    """Remove acentos e converte para minúsculas para buscas fonéticas/insensíveis a acentos."""
    if not text:
        return ""
    return "".join(
        c for c in unicodedata.normalize("NFD", text) 
        if unicodedata.category(c) != "Mn"
    ).lower()

def highlight_term_in_text(original_text: str, query: str) -> str:
    """
    Destaca todas as ocorrências de `query` dentro de `original_text`, 
    preservando a caixa original do texto e ignorando acentos.
    """
    if not original_text or not query:
        return original_text or ""
    
    clean_query = query.strip()
    if not clean_query:
        return original_text
    
    # Busca insensível a acentos mapeando posições
    norm_text = strip_accents(original_text)
    norm_query = strip_accents(clean_query)
    
    # Se regex simples funcionar diretamente
    escaped_query = re.escape(norm_query)
    matches = list(re.finditer(escaped_query, norm_text))
    if not matches:
        return original_text
    
    # Reconstrói o texto substituindo os trechos correspondentes por <mark>
    result = []
    last_idx = 0
    for m in matches:
        start, end = m.start(), m.end()
        result.append(original_text[last_idx:start])
        matched_str = original_text[start:end]
        result.append(f'<mark class="bg-amber-300 text-slate-900 px-1 py-0.5 rounded font-extrabold shadow-xs">{matched_str}</mark>')
        last_idx = end
    result.append(original_text[last_idx:])
    return "".join(result)

def format_relative_time(days_ago: int) -> str:
    if days_ago == 0:
        return "Hoje"
    elif days_ago == 1:
        return "Ontem (há 1 dia)"
    elif days_ago < 7:
        return f"Há {days_ago} dias"
    elif days_ago < 30:
        weeks = days_ago // 7
        return f"Há {days_ago} dias ({weeks} sem)"
    elif days_ago < 365:
        months = days_ago // 30
        return f"Há {days_ago} dias ({months} {'mês' if months == 1 else 'meses'})"
    else:
        years = days_ago // 365
        return f"Há {days_ago} dias ({years} ano)"

ROOT_CAUSE_MAP = {rc["id"]: rc["name"] for rc in ROOT_CAUSES_CONFIG}
ROOT_CAUSE_COLORS = {rc["id"]: rc.get("severity_color", "#6366f1") for rc in ROOT_CAUSES_CONFIG}

SUGGESTED_TERMS_CONFIG = [
    {"term": "pdf", "label": "PDF dos Livros / Notas", "icon": "fa-file-pdf", "color": "#ef4444"},
    {"term": "boletim", "label": "Boletim Escolar", "icon": "fa-file-lines", "color": "#f97316"},
    {"term": "baixar", "label": "Baixar / Download", "icon": "fa-download", "color": "#06b6d4"},
    {"term": "nota", "label": "Notas / Trimestre", "icon": "fa-graduation-cap", "color": "#3b82f6"},
    {"term": "livro", "label": "Livro / Material", "icon": "fa-book", "color": "#8b5cf6"},
    {"term": "senha", "label": "Senha / Redefinir", "icon": "fa-key", "color": "#eab308"},
    {"term": "gov", "label": "Gov.br / CPF", "icon": "fa-landmark", "color": "#dc2626"},
    {"term": "trava", "label": "Trava / Congela", "icon": "fa-triangle-exclamation", "color": "#f59e0b"},
    {"term": "tela preta", "label": "Tela Preta", "icon": "fa-mobile-screen", "color": "#64748b"},
    {"term": "atualiz", "label": "Atualização", "icon": "fa-arrows-rotate", "color": "#10b981"},
]

def scan_keywords(query: str = "") -> Dict[str, Any]:
    """
    Executa uma varredura completa e em tempo real em todas as avaliações do banco de dados,
    buscando qualquer palavra ou expressão, quantificando ocorrências, impacto nas notas
    e destacando os trechos exatos onde surgiu.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, user_name, content, title, rating, review_date, store, 
               device_brand, device_model, app_version, status, developer_response,
               developer_response_date, root_cause_id
        FROM reviews
        ORDER BY review_date DESC
    """)
    rows = [dict(r) for r in cursor.fetchall()]
    total_db = len(rows)
    now = datetime.now()

    # Calcula contagens dos termos sugeridos populares
    suggested_terms = []
    for s in SUGGESTED_TERMS_CONFIG:
        sterm_norm = strip_accents(s["term"])
        sterm_escaped = re.escape(sterm_norm)
        match_reviews_cnt = 0
        total_term_occ = 0
        for r in rows:
            combined = f"{r.get('content') or ''} {r.get('title') or ''}"
            cnorm = strip_accents(combined)
            occ = len(re.findall(sterm_escaped, cnorm))
            if occ > 0:
                match_reviews_cnt += 1
                total_term_occ += occ
        suggested_terms.append({
            "term": s["term"],
            "label": s["label"],
            "icon": s["icon"],
            "color": s["color"],
            "reviews_count": match_reviews_cnt,
            "total_occurrences": total_term_occ
        })

    clean_query = query.strip()
    if not clean_query:
        return {
            "query": "",
            "has_searched": False,
            "total_reviews_in_db": total_db,
            "suggested_terms": suggested_terms,
            "total_occurrences": 0,
            "total_reviews_matched": 0,
            "pct_of_all_reviews": 0.0,
            "avg_rating": 0.0,
            "rating_distribution": {1: 0, 2: 0, 3: 0, 4: 0, 5: 0},
            "sentiment": {"negative": 0, "neutral": 0, "positive": 0},
            "stores": {"google": 0, "apple": 0},
            "top_models": [],
            "top_root_causes": [],
            "recent_count_30d": 0,
            "reviews": []
        }

    norm_query = strip_accents(clean_query)
    escaped_query = re.escape(norm_query)

    matching_reviews = []
    total_occurrences = 0
    rating_counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    store_counts = {"google": 0, "apple": 0}
    model_counts: Dict[str, int] = {}
    cause_counts: Dict[str, int] = {}
    recent_30d_count = 0
    ratings_sum = 0

    for r in rows:
        content_raw = r.get("content") or ""
        title_raw = r.get("title") or ""
        combined_text = f"{content_raw} {title_raw}"
        norm_combined = strip_accents(combined_text)

        # Encontra ocorrências
        occurrences = len(re.findall(escaped_query, norm_combined))
        if occurrences == 0:
            continue

        total_occurrences += occurrences
        rating = int(r.get("rating") or 1)
        rating_counts[rating] = rating_counts.get(rating, 0) + 1
        ratings_sum += rating

        st = r.get("store") or "google"
        store_counts[st] = store_counts.get(st, 0) + 1

        model = r.get("device_model") or "Não Informado"
        if model and model != "Desconhecido":
            model_counts[model] = model_counts.get(model, 0) + 1

        # Causa-raiz
        rc_val = r.get("root_cause_id")
        if isinstance(rc_val, str) and rc_val and rc_val != "outros_problemas":
            rc_id = rc_val
            cause_name = ROOT_CAUSE_MAP.get(rc_id, "Outros Problemas")
        else:
            classified = classify_text_issue(content_raw, title_raw, rating)
            if isinstance(classified, dict):
                rc_id = classified.get("id", "outros_problemas")
                cause_name = classified.get("name", "Outros Problemas")
            else:
                rc_id = str(classified)
                cause_name = ROOT_CAUSE_MAP.get(rc_id, "Outros Problemas")
        cause_counts[cause_name] = cause_counts.get(cause_name, 0) + 1

        # Data e dias decorridos
        r_date_str = r.get("review_date") or ""
        dt = None
        days_ago = 999
        formatted_date = "-"
        if r_date_str:
            clean_date = r_date_str.split(".")[0].replace("Z", "")
            for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
                try:
                    dt = datetime.strptime(clean_date, fmt)
                    break
                except ValueError:
                    pass
        if dt:
            days_ago = max(0, (now - dt).days)
            formatted_date = dt.strftime("%d/%m/%Y às %H:%M") if dt.hour != 0 else dt.strftime("%d/%m/%Y")
            if days_ago <= 30:
                recent_30d_count += 1

        # Destaque visual
        content_highlighted = highlight_term_in_text(content_raw, clean_query)
        title_highlighted = highlight_term_in_text(title_raw, clean_query) if title_raw else ""

        matching_reviews.append({
            "id": r["id"],
            "user_name": r.get("user_name") or "Usuário",
            "rating": rating,
            "store": st,
            "store_label": "Google Play" if st == "google" else "Apple App Store",
            "store_icon": "fa-brands fa-google-play text-emerald-600" if st == "google" else "fa-brands fa-apple text-slate-800",
            "model": model,
            "brand": r.get("device_brand") or "",
            "date": formatted_date,
            "date_iso": r_date_str,
            "days_ago": days_ago,
            "days_ago_text": format_relative_time(days_ago),
            "root_cause_id": rc_id,
            "root_cause_name": cause_name,
            "root_cause_color": ROOT_CAUSE_COLORS.get(rc_id, "#6366f1"),
            "content": content_raw,
            "title": title_raw,
            "content_highlighted": content_highlighted,
            "title_highlighted": title_highlighted,
            "occurrences_in_review": occurrences,
            "status": r.get("status") or "pendente",
            "has_response": bool(r.get("developer_response")),
            "developer_response": r.get("developer_response")
        })

    # Ordena por mais recente
    matching_reviews.sort(key=lambda x: x["days_ago"])

    total_matches = len(matching_reviews)
    avg_r = round(ratings_sum / total_matches, 2) if total_matches > 0 else 0.0
    pct_db = round((total_matches / total_db) * 100, 1) if total_db > 0 else 0.0

    sentiment = {
        "negative": rating_counts[1] + rating_counts[2],
        "neutral": rating_counts[3],
        "positive": rating_counts[4] + rating_counts[5]
    }

    # Top modelos
    sorted_models = sorted(model_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    top_models = [{"model": m, "count": c} for m, c in sorted_models]

    # Top causas
    sorted_causes = sorted(cause_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    top_causes = [{"name": n, "count": c} for n, c in sorted_causes]

    return {
        "query": clean_query,
        "has_searched": True,
        "total_reviews_in_db": total_db,
        "suggested_terms": suggested_terms,
        "total_occurrences": total_occurrences,
        "total_reviews_matched": total_matches,
        "pct_of_all_reviews": pct_db,
        "avg_rating": avg_r,
        "rating_distribution": rating_counts,
        "sentiment": sentiment,
        "stores": store_counts,
        "top_models": top_models,
        "top_root_causes": top_causes,
        "recent_count_30d": recent_30d_count,
        "reviews": matching_reviews
    }
