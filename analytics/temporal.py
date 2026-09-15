"""
Módulo de Diagnóstico Temporal e Tendências Mensais - Minha Escola MG
Analisa a linha do tempo histórica das causas-raiz de problemas, tempo decorrido (recency/aging),
distribuição mês a mês e identificação de tendências (aumentando, diminuindo ou estável).
"""

import sqlite3
import os
from datetime import datetime
from collections import defaultdict
from typing import Dict, Any, List

ROOT_CAUSE_NAMES = {
    "gov_br_cpf": "Falha no Gov.br e Vínculo de CPF",
    "senha_recuperacao": "Recuperação de Senha e Redefinição",
    "boletim_notas": "Boletim em Branco e Notas Ausentes",
    "faltas_frequencia": "Faltas e Frequência Divergentes",
    "crash_fechamento": "Crash e Fechamento Inesperado",
    "lentidao_tela_preta": "Lentidão Extrema e Tela Preta",
    "acesso_responsaveis": "Acesso dos Pais / Múltiplos Alunos",
    "elogios_satisfacao": "Elogios e Avaliações Positivas",
    "outros_problemas": "Problemas Gerais e Dúvidas",
    "geral_outros": "Geral / Sugestões Diversas"
}

ROOT_CAUSE_ICONS = {
    "gov_br_cpf": "fa-building-columns text-red-600",
    "senha_recuperacao": "fa-key text-amber-600",
    "boletim_notas": "fa-chart-simple text-blue-600",
    "faltas_frequencia": "fa-calendar-days text-indigo-600",
    "crash_fechamento": "fa-burst text-rose-600",
    "lentidao_tela_preta": "fa-hourglass-half text-orange-600",
    "acesso_responsaveis": "fa-users text-teal-600",
    "elogios_satisfacao": "fa-star text-amber-400",
    "outros_problemas": "fa-circle-question text-slate-600",
    "geral_outros": "fa-lightbulb text-purple-600"
}

ROOT_CAUSE_COLORS = {
    "gov_br_cpf": "#dc2626",
    "senha_recuperacao": "#d97706",
    "boletim_notas": "#2563eb",
    "faltas_frequencia": "#4f46e5",
    "crash_fechamento": "#e11d48",
    "lentidao_tela_preta": "#ea580c",
    "acesso_responsaveis": "#0d9488",
    "elogios_satisfacao": "#10b981",
    "outros_problemas": "#64748b",
    "geral_outros": "#9333ea"
}

MONTH_NAMES_PT = {
    "01": "Janeiro", "02": "Fevereiro", "03": "Março", "04": "Abril",
    "05": "Maio", "06": "Junho", "07": "Julho", "08": "Agosto",
    "09": "Setembro", "10": "Outubro", "11": "Novembro", "12": "Dezembro"
}

MONTH_SHORT_PT = {
    "01": "Jan", "02": "Fev", "03": "Mar", "04": "Abr",
    "05": "Mai", "06": "Jun", "07": "Jul", "08": "Ago",
    "09": "Set", "10": "Out", "11": "Nov", "12": "Dez"
}

def format_relative_time(days: int) -> str:
    if days == 0:
        return "Hoje"
    elif days == 1:
        return "Ontem"
    elif days < 7:
        return f"Há {days} dias"
    elif days < 30:
        weeks = max(1, days // 7)
        return f"Há {weeks} {'semana' if weeks == 1 else 'semanas'}"
    elif days < 365:
        months = max(1, round(days / 30.4))
        return f"Há {months} {'mês' if months == 1 else 'meses'}"
    else:
        years = round(days / 365.25, 1)
        return f"Há {years} anos"

def get_temporal_diagnostics() -> Dict[str, Any]:
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "reviews.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, store, user_name, rating, content, review_date, root_cause_id, sentiment, device_brand, device_model
        FROM reviews
        ORDER BY review_date ASC
    """)
    reviews = [dict(r) for r in cursor.fetchall()]
    conn.close()

    now = datetime(2026, 9, 14, 15, 30, 0)

    monthly_map = defaultdict(lambda: {
        "total": 0,
        "negative": 0,
        "positive": 0,
        "neutral": 0,
        "ratings_sum": 0,
        "root_causes": defaultdict(int),
        "reviews_sample": []
    })

    cause_dates = defaultdict(list)

    aging_buckets = {
        "recent_30d": {"label": "Últimos 30 Dias (Recentes)", "count": 0, "color": "rose"},
        "month_1_3": {"label": "1 a 3 Meses Atrás", "count": 0, "color": "amber"},
        "month_3_6": {"label": "3 a 6 Meses Atrás", "count": 0, "color": "indigo"},
        "older_6m": {"label": "Mais de 6 Meses (+180 dias)", "count": 0, "color": "slate"}
    }

    for r in reviews:
        raw_d = r.get("review_date") or "2026-09-01"
        try:
            dt = datetime.fromisoformat(raw_d.replace("Z", "+00:00")).replace(tzinfo=None)
        except Exception:
            dt = datetime(2026, 9, 1)

        ym = dt.strftime("%Y-%m")
        rating = int(r.get("rating") or 3)
        rc = r.get("root_cause_id") or "outros_problemas"
        
        days_ago = max(0, (now - dt).days)

        if days_ago <= 30:
            aging_buckets["recent_30d"]["count"] += 1
        elif days_ago <= 90:
            aging_buckets["month_1_3"]["count"] += 1
        elif days_ago <= 180:
            aging_buckets["month_3_6"]["count"] += 1
        else:
            aging_buckets["older_6m"]["count"] += 1

        m = monthly_map[ym]
        m["total"] += 1
        m["ratings_sum"] += rating
        if rating <= 2:
            m["negative"] += 1
        elif rating >= 4:
            m["positive"] += 1
        else:
            m["neutral"] += 1

        m["root_causes"][rc] += 1
        if len(m["reviews_sample"]) < 3:
            m["reviews_sample"].append({
                "id": r["id"],
                "user_name": r.get("user_name") or "Usuário",
                "rating": rating,
                "content": r.get("content") or "",
                "date": dt.strftime("%d/%m/%Y"),
                "days_ago": days_ago,
                "days_ago_text": format_relative_time(days_ago)
            })

        cause_dates[rc].append({
            "id": r["id"],
            "date": dt,
            "days_ago": days_ago,
            "rating": rating,
            "content": r.get("content") or "",
            "user_name": r.get("user_name") or "Usuário",
            "model": r.get("device_model") or "Desconhecido"
        })

    months_sorted = sorted(monthly_map.keys())
    monthly_series = []
    prev_total = None

    for ym in months_sorted:
        data = monthly_map[ym]
        tot = data["total"]
        avg_r = round(data["ratings_sum"] / tot, 2) if tot > 0 else 0.0
        neg_pct = round((data["negative"] / tot) * 100, 1) if tot > 0 else 0.0

        year_str, month_str = ym.split("-")
        label_short = f"{MONTH_SHORT_PT.get(month_str, month_str)}/{year_str[2:]}"
        label_full = f"{MONTH_NAMES_PT.get(month_str, month_str)} de {year_str}"

        top_problem = None
        problem_causes = [(k, v) for k, v in data["root_causes"].items() if k != "elogios_satisfacao"]
        if problem_causes:
            top_tup = max(problem_causes, key=lambda x: x[1])
            top_problem = {
                "id": top_tup[0],
                "name": ROOT_CAUSE_NAMES.get(top_tup[0], top_tup[0]),
                "count": top_tup[1],
                "pct": round((top_tup[1] / tot) * 100, 1)
            }
        elif data["root_causes"]:
            top_tup = max(data["root_causes"].items(), key=lambda x: x[1])
            top_problem = {
                "id": top_tup[0],
                "name": ROOT_CAUSE_NAMES.get(top_tup[0], top_tup[0]),
                "count": top_tup[1],
                "pct": round((top_tup[1] / tot) * 100, 1)
            }

        mom_change = None
        if prev_total is not None and prev_total > 0:
            mom_change = round(((tot - prev_total) / prev_total) * 100, 1)
        prev_total = tot

        monthly_series.append({
            "ym": ym,
            "label": label_short,
            "label_full": label_full,
            "total": tot,
            "negative": data["negative"],
            "positive": data["positive"],
            "neutral": data["neutral"],
            "avg_rating": avg_r,
            "negative_pct": neg_pct,
            "mom_change": mom_change,
            "top_problem": top_problem,
            "root_causes": dict(data["root_causes"]),
            "sample_reviews": data["reviews_sample"]
        })

    cause_trends = []
    rising_causes = []
    falling_causes = []

    for rc, name in ROOT_CAUSE_NAMES.items():
        records = cause_dates.get(rc, [])
        if not records:
            continue

        records.sort(key=lambda x: x["date"])
        first_record = records[0]
        last_record = records[-1]

        first_seen_str = first_record["date"].strftime("%d/%m/%Y")
        last_seen_str = last_record["date"].strftime("%d/%m/%Y")
        first_days = first_record["days_ago"]
        last_days = last_record["days_ago"]

        recent_cnt = sum(1 for x in records if x["days_ago"] <= 30)
        prev_cnt = sum(1 for x in records if 31 <= x["days_ago"] <= 60)

        if prev_cnt == 0:
            if recent_cnt > 0:
                trend_dir = "increasing"
                trend_pct = 100.0
            else:
                trend_dir = "stable"
                trend_pct = 0.0
        else:
            trend_pct = round(((recent_cnt - prev_cnt) / prev_cnt) * 100, 1)
            if trend_pct >= 20.0:
                trend_dir = "increasing"
            elif trend_pct <= -20.0:
                trend_dir = "decreasing"
            else:
                trend_dir = "stable"

        monthly_counts = []
        for ym in months_sorted:
            monthly_counts.append(monthly_map[ym]["root_causes"].get(rc, 0))

        if rc in ("gov_br_cpf", "senha_recuperacao"):
            pattern = "Pico Sazonal: Início de Ano Letivo & Cadastros (Fevereiro e Agosto)"
            recommendation = "Revisar fluxo de autenticação e timeout de tokens Gov.br nos períodos de matrícula."
        elif rc in ("boletim_notas", "faltas_frequencia"):
            pattern = "Pico Bimestral: Fechamento de Bimestre e Lançamento de Notas (Maio e Setembro)"
            recommendation = "Garantir sincronização do diário de classe e pré-carregamento em cache para evitar telas em branco."
        elif rc in ("lentidao_tela_preta", "crash_fechamento"):
            pattern = "Gargalo de Hardware: Aumentou após Versões Recentes em Aparelhos Econômicos"
            recommendation = "Otimizar consumo de RAM em WebViews e telas nativas para aparelhos no Android <= 12."
        elif rc == "elogios_satisfacao":
            pattern = "Avaliações Positivas: Alunos e responsáveis elogiando rapidez nas notas"
            recommendation = "Manter boa usabilidade de consulta de notas e facilidade de login."
        else:
            pattern = "Recorrente: Dúvidas operacionais e suporte contínuo"
            recommendation = "Manter links de ajuda claros e FAQ dentro do aplicativo."

        trend_entry = {
            "id": rc,
            "name": name,
            "icon": ROOT_CAUSE_ICONS.get(rc, "fa-circle-exclamation"),
            "color": ROOT_CAUSE_COLORS.get(rc, "#6366f1"),
            "total": len(records),
            "pct_of_all": round((len(records) / len(reviews)) * 100, 1),
            "first_seen_date": first_seen_str,
            "first_seen_days_ago": first_days,
            "first_seen_text": format_relative_time(first_days),
            "last_seen_date": last_seen_str,
            "last_seen_days_ago": last_days,
            "last_seen_text": format_relative_time(last_days),
            "recent_count_30d": recent_cnt,
            "prev_count_30_60d": prev_cnt,
            "trend_direction": trend_dir,
            "trend_pct": trend_pct,
            "pattern": pattern,
            "recommendation": recommendation,
            "monthly_history": monthly_counts,
            "sample_recent": [
                {
                    "id": x["id"],
                    "user_name": x["user_name"],
                    "content": x["content"][:140] + ("..." if len(x["content"]) > 140 else ""),
                    "days_ago_text": format_relative_time(x["days_ago"]),
                    "model": x["model"],
                    "rating": x["rating"]
                }
                for x in sorted(records, key=lambda it: it["days_ago"])[:3]
            ]
        }

        cause_trends.append(trend_entry)
        if rc != "elogios_satisfacao":
            if trend_dir == "increasing" and recent_cnt >= 5:
                rising_causes.append(trend_entry)
            elif trend_dir == "decreasing":
                falling_causes.append(trend_entry)

    cause_trends.sort(key=lambda x: x["recent_count_30d"], reverse=True)
    peak_month = max(monthly_series, key=lambda x: x["total"]) if monthly_series else None

    first_month = monthly_series[0]["label"] if monthly_series else "-"
    last_month = monthly_series[-1]["label"] if monthly_series else "-"

    return {
        "summary": {
            "total_reviews": len(reviews),
            "total_months": len(monthly_series),
            "date_range_label": f"{first_month} a {last_month}",
            "peak_month": {
                "label": peak_month["label_full"] if peak_month else "-",
                "total": peak_month["total"] if peak_month else 0,
                "negative": peak_month["negative"] if peak_month else 0,
                "top_cause": peak_month["top_problem"]["name"] if peak_month and peak_month["top_problem"] else "-"
            },
            "recent_30d_total": aging_buckets["recent_30d"]["count"],
            "rising_causes_count": len(rising_causes),
            "falling_causes_count": len(falling_causes),
            "top_rising_cause": rising_causes[0]["name"] if rising_causes else "Nenhuma em alta crítica",
            "top_falling_cause": falling_causes[0]["name"] if falling_causes else "Estável"
        },
        "aging_buckets": aging_buckets,
        "months_labels": [m["label"] for m in monthly_series],
        "monthly_series": monthly_series,
        "cause_trends": cause_trends,
        "top_problem_causes_chart": [
            {
                "id": c["id"],
                "name": c["name"],
                "color": c["color"],
                "data": c["monthly_history"]
            }
            for c in cause_trends if c["id"] != "elogios_satisfacao"
        ][:6]
    }
