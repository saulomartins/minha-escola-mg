"""
analytics/hardware_root_cause.py
Motor analítico de correlação entre Hardware (Fabricantes e Modelos de Celular)
e Causas-Raiz de problemas relatados nas avaliações do aplicativo Minha Escola MG.
"""

from collections import defaultdict
from typing import Dict, List, Any, Optional
from database.db import get_connection
from analytics.complexity import ROOT_CAUSES_CONFIG, classify_text_issue
from analytics.device_lifecycle import get_device_lifecycle

# Dicionário rápido de metadados de Causas-Raiz
CAUSES_META: Dict[str, Dict[str, Any]] = {
    cfg["id"]: {
        "name": cfg["name"],
        "severity": cfg["severity"],
        "severity_color": cfg.get("severity_color", "#64748b"),
        "complexity": cfg.get("complexity", "Média")
    }
    for cfg in ROOT_CAUSES_CONFIG
}

# Causas adicionais com fallback
CAUSES_META["outros_problemas"] = {
    "name": "Problemas Gerais e Dúvidas",
    "severity": "Média",
    "severity_color": "#eab308",
    "complexity": "Baixa"
}
CAUSES_META["geral_outros"] = {
    "name": "Geral / Sugestões Diversas",
    "severity": "Baixa",
    "severity_color": "#64748b",
    "complexity": "Baixa"
}
CAUSES_META["avaliacao_sem_comentario"] = {
    "name": "Nota Baixa sem Comentário",
    "severity": "Média",
    "severity_color": "#94a3b8",
    "complexity": "Baixa"
}


def get_hardware_root_cause_analytics(
    filter_brand: Optional[str] = None,
    filter_root_cause_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Retorna métricas cruzadas entre Fabricantes, Modelos de Celular e Causas-Raiz.
    Suporta filtros opcionais de marca e causa-raiz.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # Busca todas as avaliações com dados de hardware e causas
    cursor.execute("""
        SELECT 
            id, store, user_name, rating, title, content, 
            device_brand, device_model, os_name, os_version, 
            root_cause_id, review_date
        FROM reviews
        ORDER BY review_date DESC
    """)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()

    total_reviews = len(rows)
    if total_reviews == 0:
        return {
            "kpis": {},
            "by_root_cause": [],
            "by_brand": [],
            "by_model": [],
            "charts": {},
            "filter_options": {"available_brands": [], "available_causes": []}
        }

    # Normalização e classificação garantida
    processed_reviews = []
    for r in rows:
        brand = (r.get("device_brand") or "Não especificado").strip()
        model = (r.get("device_model") or "Não especificado").strip()
        
        # Formata nome do modelo composto com a marca para clareza
        if brand and brand != "Não especificado" and not model.lower().startswith(brand.lower()):
            model_full = f"{brand} {model}"
        else:
            model_full = model

        rc_id = r.get("root_cause_id")
        if not rc_id:
            classified = classify_text_issue(r.get("content", ""), r.get("title", ""), r.get("rating", 3))
            rc_id = classified["id"]

        r["normalized_brand"] = brand
        r["normalized_model"] = model
        r["model_full"] = model_full
        r["normalized_root_cause_id"] = rc_id
        processed_reviews.append(r)

    # Coleta de opções para filtros
    all_brands = sorted(list(set(r["normalized_brand"] for r in processed_reviews if r["normalized_brand"] not in ("Não especificado", ""))))
    all_causes_ids = sorted(list(set(r["normalized_root_cause_id"] for r in processed_reviews)))
    available_causes = []
    for cid in all_causes_ids:
        meta = CAUSES_META.get(cid, {"name": cid, "severity": "Média", "severity_color": "#64748b"})
        available_causes.append({
            "id": cid,
            "name": meta["name"],
            "severity": meta["severity"],
            "severity_color": meta["severity_color"]
        })

    # Aplicação de filtros se requisitado
    filtered_reviews = processed_reviews
    if filter_brand and filter_brand.lower() != "todos":
        filtered_reviews = [r for r in filtered_reviews if r["normalized_brand"].lower() == filter_brand.lower()]
    if filter_root_cause_id and filter_root_cause_id.lower() != "todos":
        filtered_reviews = [r for r in filtered_reviews if r["normalized_root_cause_id"] == filter_root_cause_id]

    # Estruturas de agregação
    # 1. Por Causa-Raiz -> Fabricantes & Modelos
    rc_aggregate = defaultdict(lambda: {
        "count": 0,
        "brands": defaultdict(int),
        "models": defaultdict(lambda: {"count": 0, "brand": "", "raw_model": "", "ratings": []}),
        "ratings": []
    })

    # 2. Por Fabricante -> Modelos & Causas-Raiz
    brand_aggregate = defaultdict(lambda: {
        "count": 0,
        "models": defaultdict(int),
        "causes": defaultdict(int),
        "ratings": []
    })

    # 3. Por Modelo Específico -> Causas-Raiz & Detalhes
    model_aggregate = defaultdict(lambda: {
        "count": 0,
        "brand": "",
        "raw_model": "",
        "causes": defaultdict(int),
        "ratings": [],
        "samples": []
    })

    for r in filtered_reviews:
        cid = r["normalized_root_cause_id"]
        brand = r["normalized_brand"]
        m_full = r["model_full"]
        m_raw = r["normalized_model"]
        rating = r.get("rating", 3)
        content = r.get("content", "")

        # Agregação por causa
        rc_aggregate[cid]["count"] += 1
        rc_aggregate[cid]["ratings"].append(rating)
        rc_aggregate[cid]["brands"][brand] += 1
        rc_aggregate[cid]["models"][m_full]["count"] += 1
        rc_aggregate[cid]["models"][m_full]["brand"] = brand
        rc_aggregate[cid]["models"][m_full]["raw_model"] = m_raw
        rc_aggregate[cid]["models"][m_full]["ratings"].append(rating)

        # Agregação por marca
        brand_aggregate[brand]["count"] += 1
        brand_aggregate[brand]["models"][m_full] += 1
        brand_aggregate[brand]["causes"][cid] += 1
        brand_aggregate[brand]["ratings"].append(rating)

        # Agregação por modelo
        model_aggregate[m_full]["count"] += 1
        model_aggregate[m_full]["brand"] = brand
        model_aggregate[m_full]["raw_model"] = m_raw
        model_aggregate[m_full]["causes"][cid] += 1
        model_aggregate[m_full]["ratings"].append(rating)
        if content and len(model_aggregate[m_full]["samples"]) < 2:
            model_aggregate[m_full]["samples"].append({
                "id": r["id"],
                "content": content[:120] + ("..." if len(content) > 120 else ""),
                "rating": rating,
                "date": r.get("review_date", "")
            })

    # Formatação do resultado `by_root_cause`
    by_root_cause = []
    for cid, data in rc_aggregate.items():
        meta = CAUSES_META.get(cid, {
            "name": cid,
            "severity": "Média",
            "severity_color": "#64748b",
            "complexity": "Média"
        })
        total_c = data["count"]
        avg_r = round(sum(data["ratings"]) / len(data["ratings"]), 2) if data["ratings"] else 0.0

        # Top marcas dentro desta causa
        sorted_brands = []
        for b_name, b_count in sorted(data["brands"].items(), key=lambda x: x[1], reverse=True):
            sorted_brands.append({
                "brand": b_name,
                "count": b_count,
                "percentage": round((b_count / total_c) * 100, 1)
            })

        # Top modelos dentro desta causa
        sorted_models = []
        for m_name, m_info in sorted(data["models"].items(), key=lambda x: x[1]["count"], reverse=True):
            life = get_device_lifecycle(m_info["brand"], m_info["raw_model"])
            sorted_models.append({
                "model_name": m_name,
                "brand": m_info["brand"],
                "raw_model": m_info["raw_model"],
                "count": m_info["count"],
                "percentage": round((m_info["count"] / total_c) * 100, 1),
                "last_official_os": life.get("last_official_os") or life.get("max_os", "Não catalogado"),
                "is_stuck_android_12": life.get("is_stuck_android_12", False),
                "status_badge": life.get("status_badge", "slate")
            })

        by_root_cause.append({
            "id": cid,
            "name": meta["name"],
            "severity": meta["severity"],
            "severity_color": meta["severity_color"],
            "complexity": meta["complexity"],
            "total_occurrences": total_c,
            "percentage_of_all": round((total_c / len(filtered_reviews)) * 100, 1) if filtered_reviews else 0.0,
            "avg_rating": avg_r,
            "unique_models_count": len(data["models"]),
            "top_brands": sorted_brands,
            "top_models": sorted_models[:8]
        })

    by_root_cause.sort(key=lambda x: x["total_occurrences"], reverse=True)

    # Formatação do resultado `by_brand`
    by_brand = []
    for b_name, b_data in brand_aggregate.items():
        if not b_name or b_name == "Não especificado":
            continue
        total_b = b_data["count"]
        avg_r = round(sum(b_data["ratings"]) / len(b_data["ratings"]), 2) if b_data["ratings"] else 0.0

        # Top causas dessa marca
        b_causes = []
        for cid, c_count in sorted(b_data["causes"].items(), key=lambda x: x[1], reverse=True):
            meta = CAUSES_META.get(cid, {"name": cid, "severity": "Média", "severity_color": "#64748b"})
            b_causes.append({
                "id": cid,
                "name": meta["name"],
                "severity": meta["severity"],
                "severity_color": meta["severity_color"],
                "count": c_count,
                "percentage": round((c_count / total_b) * 100, 1)
            })

        # Top modelos dessa marca
        b_models = []
        for m_name, m_count in sorted(b_data["models"].items(), key=lambda x: x[1], reverse=True):
            b_models.append({
                "model_name": m_name,
                "count": m_count,
                "percentage": round((m_count / total_b) * 100, 1)
            })

        by_brand.append({
            "brand": b_name,
            "total_reviews": total_b,
            "percentage": round((total_b / len(filtered_reviews)) * 100, 1) if filtered_reviews else 0.0,
            "avg_rating": avg_r,
            "unique_models_count": len(b_data["models"]),
            "top_causes": b_causes,
            "top_models": b_models[:6]
        })

    by_brand.sort(key=lambda x: x["total_reviews"], reverse=True)

    # Formatação do resultado `by_model`
    by_model = []
    for m_name, m_data in model_aggregate.items():
        total_m = m_data["count"]
        brand = m_data["brand"]
        raw_m = m_data["raw_model"]
        avg_r = round(sum(m_data["ratings"]) / len(m_data["ratings"]), 2) if m_data["ratings"] else 0.0
        life = get_device_lifecycle(brand, raw_m)

        # Causas discriminadas do modelo
        m_causes = []
        for cid, c_count in sorted(m_data["causes"].items(), key=lambda x: x[1], reverse=True):
            meta = CAUSES_META.get(cid, {"name": cid, "severity": "Média", "severity_color": "#64748b"})
            m_causes.append({
                "id": cid,
                "name": meta["name"],
                "severity": meta["severity"],
                "severity_color": meta["severity_color"],
                "count": c_count,
                "percentage": round((c_count / total_m) * 100, 1)
            })

        primary_cause = m_causes[0] if m_causes else None

        by_model.append({
            "model_name": m_name,
            "brand": brand,
            "raw_model": raw_m,
            "total_reviews": total_m,
            "avg_rating": avg_r,
            "launch_os": life.get("launch_os", "Não catalogado"),
            "last_official_os": life.get("last_official_os") or life.get("max_os", "Verificar com fabricante"),
            "is_stuck_android_12": life.get("is_stuck_android_12", False),
            "support_status": life.get("support_status", "Ativo"),
            "status_badge": life.get("status_badge", "slate"),
            "root_causes": m_causes,
            "primary_cause": primary_cause,
            "samples": m_data["samples"]
        })

    by_model.sort(key=lambda x: x["total_reviews"], reverse=True)

    # 4. KPIs Executivos
    top_brand_item = by_brand[0] if by_brand else None
    top_model_item = by_model[0] if by_model else None
    
    # Causa com mais modelos afetados (excluindo elogios)
    critical_causes = [c for c in by_root_cause if c["id"] != "elogios_satisfacao"]
    top_dispersion_cause = max(critical_causes, key=lambda x: x["unique_models_count"]) if critical_causes else None

    kpis = {
        "total_reviews_analyzed": len(filtered_reviews),
        "total_unique_models": len(by_model),
        "total_unique_brands": len(by_brand),
        "top_brand": {
            "brand": top_brand_item["brand"] if top_brand_item else "-",
            "count": top_brand_item["total_reviews"] if top_brand_item else 0,
            "percentage": top_brand_item["percentage"] if top_brand_item else 0
        },
        "top_model": {
            "model_name": top_model_item["model_name"] if top_model_item else "-",
            "count": top_model_item["total_reviews"] if top_model_item else 0,
            "brand": top_model_item["brand"] if top_model_item else "-",
            "last_official_os": top_model_item["last_official_os"] if top_model_item else "-"
        },
        "top_cause": {
            "name": top_dispersion_cause["name"] if top_dispersion_cause else "-",
            "models_count": top_dispersion_cause["unique_models_count"] if top_dispersion_cause else 0,
            "occurrences": top_dispersion_cause["total_occurrences"] if top_dispersion_cause else 0,
            "severity": top_dispersion_cause["severity"] if top_dispersion_cause else "-"
        }
    }

    # 5. Dados para Gráficos Chart.js
    # Gráfico 1: Top 8 Modelos x Causas mais frequentes (Stacked Bar)
    top_8_models = by_model[:8]
    top_common_causes = [c for c in by_root_cause if c["id"] != "elogios_satisfacao"][:5]
    
    chart_datasets = []
    palette = ["#dc2626", "#ea580c", "#eab308", "#6366f1", "#8b5cf6"]
    for idx, c_info in enumerate(top_common_causes):
        c_id = c_info["id"]
        data_points = []
        for m in top_8_models:
            found = next((rc["count"] for rc in m["root_causes"] if rc["id"] == c_id), 0)
            data_points.append(found)
        chart_datasets.append({
            "label": c_info["name"],
            "data": data_points,
            "backgroundColor": palette[idx % len(palette)]
        })

    charts = {
        "stacked_models": {
            "labels": [m["model_name"] for m in top_8_models],
            "datasets": chart_datasets
        },
        "brand_shares": {
            "labels": [b["brand"] for b in by_brand[:5]],
            "data": [b["total_reviews"] for b in by_brand[:5]],
            "colors": ["#f97316", "#0284c7", "#3b82f6", "#64748b", "#a855f7"]
        }
    }

    return {
        "kpis": kpis,
        "by_root_cause": by_root_cause,
        "by_brand": by_brand,
        "by_model": by_model,
        "charts": charts,
        "filter_options": {
            "available_brands": all_brands,
            "available_causes": available_causes
        }
    }
