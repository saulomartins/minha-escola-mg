import sqlite3
import os
import json
from datetime import datetime
from typing import List, Dict, Any, Optional

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "reviews.db")
SEED_USERS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "seed_users.json")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    # Tabela de avaliações
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS reviews (
        id TEXT PRIMARY KEY,
        store TEXT NOT NULL,
        review_id TEXT NOT NULL,
        user_name TEXT,
        rating INTEGER NOT NULL,
        title TEXT,
        content TEXT NOT NULL,
        review_date TEXT,
        developer_response TEXT,
        developer_response_date TEXT,
        sentiment TEXT,
        category TEXT,
        root_cause_id TEXT,
        ai_suggested_response TEXT,
        status TEXT DEFAULT 'pendente',
        published_to_store INTEGER DEFAULT 0,
        local_response TEXT,
        device_brand TEXT,
        device_model TEXT,
        os_name TEXT,
        os_version TEXT,
        app_version TEXT,
        device_source TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    """)
    
    # Migrações seguras para colunas incrementais
    migrations = [
        "root_cause_id TEXT",
        "published_to_store INTEGER DEFAULT 0",
        "local_response TEXT",
        "device_brand TEXT",
        "device_model TEXT",
        "os_name TEXT",
        "os_version TEXT",
        "app_version TEXT",
        "device_source TEXT"
    ]
    for col in migrations:
        try:
            cursor.execute(f"ALTER TABLE reviews ADD COLUMN {col}")
        except Exception:
            pass
    
    # Tabela de usuários e permissões de acesso
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS allowed_users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        name TEXT,
        picture TEXT,
        role TEXT NOT NULL DEFAULT 'viewer',
        status TEXT NOT NULL DEFAULT 'approved',
        added_by TEXT,
        created_at TEXT NOT NULL,
        last_login_at TEXT
    );
    """)

    # Garante o Super Admin inicial
    admin_email = "saulomartins.costa@gmail.com"
    now_iso = datetime.utcnow().isoformat()
    cursor.execute("SELECT id FROM allowed_users WHERE LOWER(email) = ?", (admin_email.lower(),))
    if not cursor.fetchone():
        cursor.execute("""
        INSERT INTO allowed_users (email, name, role, status, added_by, created_at)
        VALUES (?, ?, 'admin', 'approved', 'system', ?)
        """, (admin_email.lower(), "Saulo Martins Costa", now_iso))

    # Carrega e sincroniza usuários permanentes de seed_users.json e da variável ALLOWED_USERS
    load_seed_users_into_cursor(cursor, now_iso)

    # Tabela de configurações
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    );
    """)
    
    # Configurações padrão
    defaults = {
        "gemini_api_key": os.environ.get("GEMINI_API_KEY", ""),
        "auto_reply_enabled": "false",
        "auto_reply_5_stars_only": "false",
        "support_contact_url": "https://forms.cloud.microsoft/r/JmZhSzXtwG",
        "support_email": "https://forms.cloud.microsoft/r/JmZhSzXtwG",
        "app_name": "Minha Escola MG",
        "google_client_id": os.environ.get("GOOGLE_CLIENT_ID", "")
    }
    
    for k, v in defaults.items():
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))
        
    conn.commit()
    conn.close()

def upsert_review(review: Dict[str, Any]) -> bool:
    """
    Insere ou atualiza uma avaliação com detecção de dispositivo e SO.
    Retorna True se for uma nova avaliação, False se já existia.
    """
    from analytics.device_detector import detect_device_and_os
    
    # Detecta metadados de celular e SO se ainda não estiverem preenchidos
    if not review.get('device_brand') or not review.get('os_name'):
        dev_info = detect_device_and_os(review)
        review['device_brand'] = review.get('device_brand') or dev_info['device_brand']
        review['device_model'] = review.get('device_model') or dev_info['device_model']
        review['os_name'] = review.get('os_name') or dev_info['os_name']
        review['os_version'] = review.get('os_version') or dev_info['os_version']
        review['app_version'] = review.get('app_version') or dev_info['app_version']
        review['device_source'] = review.get('device_source') or dev_info['device_source']

    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.utcnow().isoformat()
    
    cursor.execute("SELECT id, status, ai_suggested_response, sentiment FROM reviews WHERE id = ?", (review['id'],))
    existing = cursor.fetchone()
    
    is_new = existing is None
    
    if is_new:
        cursor.execute("""
        INSERT INTO reviews (
            id, store, review_id, user_name, rating, title, content, 
            review_date, developer_response, developer_response_date, 
            sentiment, category, root_cause_id, ai_suggested_response, status,
            device_brand, device_model, os_name, os_version, app_version, device_source,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            review['id'],
            review['store'],
            review['review_id'],
            review.get('user_name', 'Usuário'),
            review['rating'],
            review.get('title', ''),
            review.get('content', ''),
            review.get('review_date', now),
            review.get('developer_response', None),
            review.get('developer_response_date', None),
            review.get('sentiment', None),
            review.get('category', None),
            review.get('root_cause_id', None),
            review.get('ai_suggested_response', None),
            review.get('status', 'pendente'),
            review.get('device_brand', None),
            review.get('device_model', None),
            review.get('os_name', None),
            review.get('os_version', None),
            review.get('app_version', None),
            review.get('device_source', None),
            now,
            now
        ))
    else:
        dev_resp = review.get('developer_response')
        cursor.execute("""
        UPDATE reviews SET
            user_name = COALESCE(?, user_name),
            rating = ?,
            content = ?,
            developer_response = COALESCE(?, developer_response),
            developer_response_date = COALESCE(?, developer_response_date),
            status = CASE WHEN (? IS NOT NULL AND ? != '') THEN 'respondida' ELSE status END,
            published_to_store = CASE WHEN (? IS NOT NULL AND ? != '') THEN 1 ELSE published_to_store END,
            device_brand = COALESCE(?, device_brand),
            device_model = COALESCE(?, device_model),
            os_name = COALESCE(?, os_name),
            os_version = COALESCE(?, os_version),
            app_version = COALESCE(?, app_version),
            device_source = COALESCE(?, device_source),
            updated_at = ?
        WHERE id = ?
        """, (
            review.get('user_name'),
            review['rating'],
            review.get('content', ''),
            dev_resp,
            review.get('developer_response_date'),
            dev_resp, dev_resp,
            dev_resp, dev_resp,
            review.get('device_brand'),
            review.get('device_model'),
            review.get('os_name'),
            review.get('os_version'),
            review.get('app_version'),
            review.get('device_source'),
            now,
            review['id']
        ))
        
    conn.commit()
    conn.close()
    return is_new

def get_reviews(
    store: Optional[str] = None,
    rating: Optional[int] = None,
    status: Optional[str] = None,
    sentiment: Optional[str] = None,
    root_cause_id: Optional[str] = None,
    os_name: Optional[str] = None,
    device_brand: Optional[str] = None,
    search: Optional[str] = None,
    stuck_android_12: Optional[bool] = None,
    limit: int = 100,
    offset: int = 0
) -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    
    query = "SELECT * FROM reviews WHERE 1=1"
    params = []
    
    if store and store != 'todas':
        query += " AND store = ?"
        params.append(store)
    if rating and rating > 0:
        query += " AND rating = ?"
        params.append(rating)
    if status and status != 'todos':
        query += " AND status = ?"
        params.append(status)
    if sentiment and sentiment != 'todos':
        query += " AND sentiment = ?"
        params.append(sentiment)
    if root_cause_id and root_cause_id != 'todos':
        query += " AND root_cause_id = ?"
        params.append(root_cause_id)
    if os_name and os_name != 'todos':
        query += " AND os_name = ?"
        params.append(os_name)
    if device_brand and device_brand != 'todas':
        query += " AND device_brand = ?"
        params.append(device_brand)
    if search:
        query += " AND (content LIKE ? OR user_name LIKE ? OR title LIKE ? OR device_model LIKE ?)"
        term = f"%{search}%"
        params.extend([term, term, term, term])
        
    query += " ORDER BY review_date DESC"
    
    # Se não houver filtro de stuck_android_12, podemos paginar diretamente no SQL
    if stuck_android_12 is None:
        query += " LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        cursor.execute(query, params)
        raw_rows = [dict(row) for row in cursor.fetchall()]
    else:
        cursor.execute(query, params)
        raw_rows = [dict(row) for row in cursor.fetchall()]
        
    conn.close()
    
    from analytics.device_lifecycle import evaluate_stuck_android_12
    
    enriched_rows = []
    for r in raw_rows:
        stuck_eval = evaluate_stuck_android_12(
            brand=r.get('device_brand'),
            model=r.get('device_model'),
            os_name=r.get('os_name'),
            os_version=r.get('os_version'),
            content=r.get('content')
        )
        r['is_stuck_android_12'] = stuck_eval['is_stuck']
        r['stuck_info'] = stuck_eval
        
        if stuck_android_12 is True and not stuck_eval['is_stuck']:
            continue
        if stuck_android_12 is False and stuck_eval['is_stuck']:
            continue
            
        enriched_rows.append(r)
        
    if stuck_android_12 is not None:
        return enriched_rows[offset:offset + limit]
        
    return enriched_rows


def get_stats() -> Dict[str, Any]:
    conn = get_connection()
    cursor = conn.cursor()
    
    # Total geral e por loja
    cursor.execute("SELECT COUNT(*) as total FROM reviews")
    total = cursor.fetchone()['total']
    
    cursor.execute("SELECT COUNT(*) as total FROM reviews WHERE store = 'google'")
    google_total = cursor.fetchone()['total']
    
    cursor.execute("SELECT COUNT(*) as total FROM reviews WHERE store = 'apple'")
    apple_total = cursor.fetchone()['total']
    
    # Média de notas
    cursor.execute("SELECT AVG(rating) as avg_rating FROM reviews")
    avg_total = cursor.fetchone()['avg_rating'] or 0.0
    
    cursor.execute("SELECT AVG(rating) as avg_rating FROM reviews WHERE store = 'google'")
    avg_google = cursor.fetchone()['avg_rating'] or 0.0
    
    cursor.execute("SELECT AVG(rating) as avg_rating FROM reviews WHERE store = 'apple'")
    avg_apple = cursor.fetchone()['avg_rating'] or 0.0
    
    # Sentimentos
    cursor.execute("SELECT sentiment, COUNT(*) as count FROM reviews WHERE sentiment IS NOT NULL GROUP BY sentiment")
    sentiments = {row['sentiment']: row['count'] for row in cursor.fetchall()}
    
    # Categorias
    cursor.execute("SELECT category, COUNT(*) as count FROM reviews WHERE category IS NOT NULL GROUP BY category")
    categories = {row['category']: row['count'] for row in cursor.fetchall()}
    
    # Status
    cursor.execute("SELECT status, COUNT(*) as count FROM reviews GROUP BY status")
    statuses = {row['status']: row['count'] for row in cursor.fetchall()}
    
    # Distribuição de estrelas
    cursor.execute("SELECT rating, COUNT(*) as count FROM reviews GROUP BY rating ORDER BY rating ASC")
    ratings_dist = {row['rating']: row['count'] for row in cursor.fetchall()}

    # Publicação nas lojas
    cursor.execute("SELECT COUNT(*) as count FROM reviews WHERE status = 'respondida' AND published_to_store = 1")
    published_store_count = cursor.fetchone()['count']

    cursor.execute("SELECT COUNT(*) as count FROM reviews WHERE status = 'respondida' AND (published_to_store = 0 OR published_to_store IS NULL)")
    pending_store_count = cursor.fetchone()['count']
    
    # Distribuição básica de SO e Marcas
    cursor.execute("SELECT os_name, COUNT(*) as count FROM reviews WHERE os_name IS NOT NULL GROUP BY os_name")
    os_dist = {row['os_name']: row['count'] for row in cursor.fetchall()}
    
    cursor.execute("SELECT device_brand, COUNT(*) as count FROM reviews WHERE device_brand IS NOT NULL AND device_brand != 'Android Geral' GROUP BY device_brand ORDER BY count DESC")
    brand_dist = {row['device_brand']: row['count'] for row in cursor.fetchall()}

    # Metadados oficiais das lojas em tempo real
    apple_official_score = 4.2
    apple_ratings_count = 1581
    try:
        from collector.apple_store import get_apple_store_metadata
        a_meta = get_apple_store_metadata()
        if a_meta.get("score"):
            apple_official_score = float(a_meta["score"])
        if a_meta.get("ratings_count"):
            apple_ratings_count = int(a_meta["ratings_count"])
    except Exception:
        pass

    google_official_score = 4.7
    google_ratings_count = 3305
    google_hist = {"1": 141, "2": 46, "3": 56, "4": 312, "5": 2744}
    try:
        from collector.google_play import get_google_play_metadata
        g_meta = get_google_play_metadata()
        if g_meta.get("score"):
            google_official_score = float(g_meta["score"])
        if g_meta.get("ratings_count"):
            google_ratings_count = int(g_meta["ratings_count"])
        if g_meta.get("histogram") and len(g_meta["histogram"]) >= 5:
            h = g_meta["histogram"]
            google_hist = {"1": h[0], "2": h[1], "3": h[2], "4": h[3], "5": h[4]}
    except Exception:
        pass

    conn.close()
    return {
        "total": total,
        "google_total": google_total,
        "apple_total": apple_total,
        "avg_total": round(avg_total, 2),
        "avg_google": round(avg_google, 2),
        "avg_apple": round(avg_apple, 2),
        "google_official_score": google_official_score,
        "google_ratings_count": google_ratings_count,
        "google_official_histogram": google_hist,
        "apple_official_score": apple_official_score,
        "apple_ratings_count": apple_ratings_count,


        "total_downloads": "1.000.000+",
        "developer": "Prodemge - Secretaria de Educação de MG",
        "sentiments": sentiments,
        "categories": categories,
        "statuses": statuses,
        "ratings_distribution": ratings_dist,
        "published_store_count": published_store_count,
        "pending_store_count": pending_store_count,
        "os_distribution": os_dist,
        "brand_distribution": brand_dist
    }

def get_device_diagnostic() -> Dict[str, Any]:
    """
    Retorna diagnóstico analítico completo e aprofundado sobre:
    - Modelos de celulares e fabricantes identificados
    - Sistemas Operacionais (Android vs iOS) e suas distribuições
    - Versões de Sistema Operacional com índices de insatisfação / falhas técnicas
    - Alertas de incompatibilidade por aparelho
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) as total FROM reviews")
    total_reviews = cursor.fetchone()['total'] or 1
    
    # 1. Distribuição de Sistemas Operacionais
    cursor.execute("""
        SELECT 
            COALESCE(os_name, 'Android') as os,
            COUNT(*) as count,
            AVG(rating) as avg_rating,
            SUM(CASE WHEN rating <= 2 THEN 1 ELSE 0 END) as negative_count
        FROM reviews
        GROUP BY os
    """)
    os_rows = cursor.fetchall()
    os_breakdown = []
    for r in os_rows:
        count = r['count']
        pct = round((count / total_reviews) * 100, 1)
        os_breakdown.append({
            "os_name": r['os'],
            "count": count,
            "percentage": pct,
            "avg_rating": round(r['avg_rating'] or 0.0, 2),
            "negative_count": r['negative_count']
        })
        
    # 2. Fabricantes identificados
    cursor.execute("""
        SELECT 
            device_brand,
            COUNT(*) as count,
            AVG(rating) as avg_rating,
            SUM(CASE WHEN rating <= 2 THEN 1 ELSE 0 END) as negative_count
        FROM reviews
        WHERE device_brand IS NOT NULL
        GROUP BY device_brand
        ORDER BY count DESC
    """)
    brand_rows = cursor.fetchall()
    brands = []
    for r in brand_rows:
        brands.append({
            "brand": r['device_brand'],
            "count": r['count'],
            "percentage": round((r['count'] / total_reviews) * 100, 1),
            "avg_rating": round(r['avg_rating'] or 0.0, 2),
            "negative_count": r['negative_count']
        })
        
    # 3. Modelos de celular específicos citados/detectados
    cursor.execute("""
        SELECT 
            id, store, device_brand, device_model, os_name, os_version, rating, content, root_cause_id
        FROM reviews
        WHERE device_source = 'text_detected' OR device_source = 'store_api'
           OR (device_brand NOT IN ('Android Geral', 'Apple') AND device_brand IS NOT NULL)
        ORDER BY review_date DESC
    """)
    explicit_reviews = [dict(row) for row in cursor.fetchall()]
    
    # Agrupamento de modelos citados
    models_summary = {}
    for r in explicit_reviews:
        model = r.get('device_model') or 'Não especificado'
        brand = r.get('device_brand') or 'Geral'
        if model not in models_summary:
            models_summary[model] = {
                "model": model,
                "brand": brand,
                "count": 0,
                "total_rating": 0,
                "ratings": [],
                "issues": []
            }
        models_summary[model]["count"] += 1
        models_summary[model]["total_rating"] += r.get("rating", 0)
        models_summary[model]["ratings"].append(r.get("rating", 0))
        if r.get("content"):
            models_summary[model]["issues"].append({
                "id": r["id"],
                "rating": r["rating"],
                "content": r["content"][:120] + "..." if len(r["content"]) > 120 else r["content"]
            })
            
    from analytics.device_lifecycle import get_device_lifecycle, get_os_lifecycle

    top_models = []
    for k, v in models_summary.items():
        avg = round(v["total_rating"] / v["count"], 2) if v["count"] > 0 else 0.0
        life = get_device_lifecycle(v["brand"], v["model"])
        top_models.append({
            "model": v["model"],
            "brand": v["brand"],
            "count": v["count"],
            "avg_rating": avg,
            "launch_os": life.get("launch_os", "Não catalogado"),
            "max_os": life.get("max_os", "Verificar com fabricante"),
            "last_official_os": life.get("last_official_os") or life.get("max_os", "Verificar com fabricante"),
            "is_stuck_android_12": life.get("is_stuck_android_12", False),
            "support_status": life.get("support_status", "Em análise"),

            "status_badge": life.get("status_badge", "slate"),
            "google_oem_notes": life.get("google_oem_notes", ""),
            "dev_recommendation": life.get("dev_recommendation", ""),
            "issues": v["issues"][:3]
        })
    top_models.sort(key=lambda x: x["count"], reverse=True)
    
    # 4. Versões de SO citadas/detectadas
    cursor.execute("""
        SELECT 
            os_version,
            COUNT(*) as count,
            AVG(rating) as avg_rating,
            SUM(CASE WHEN rating <= 2 THEN 1 ELSE 0 END) as negative_count
        FROM reviews
        WHERE os_version IS NOT NULL AND os_version NOT IN ('Android (Geral)', 'iOS (Geral)', 'Android', 'iOS')
        GROUP BY os_version
        ORDER BY count DESC
    """)
    os_versions = []
    for r in cursor.fetchall():
        os_life = get_os_lifecycle(r['os_version'])
        os_versions.append({
            "version": r['os_version'],
            "count": r['count'],
            "avg_rating": round(r['avg_rating'] or 0.0, 2),
            "negative_count": r['negative_count'],
            "google_status": os_life.get("google_status", "Ativo"),
            "badge": os_life.get("badge", "slate"),
            "details": os_life.get("details", "")
        })
        
    # 5. Versões do App instaladas
    cursor.execute("""
        SELECT 
            app_version,
            COUNT(*) as count,
            AVG(rating) as avg_rating
        FROM reviews
        WHERE app_version IS NOT NULL AND app_version != ''
        GROUP BY app_version
        ORDER BY count DESC
        LIMIT 5
    """)
    app_versions = [
        {"version": r['app_version'], "count": r['count'], "avg_rating": round(r['avg_rating'] or 0.0, 2)}
        for r in cursor.fetchall()
    ]
    
    # 6. Diagnóstico e Recomendações Automáticas
    alerts = []
    # Verifica menções de Android 12
    a12 = next((v for v in os_versions if "12" in v["version"]), None)
    if a12:
        alerts.append({
            "type": "error",
            "title": "Atenção Crítica: O Gargalo do Android 12 e Fim de Suporte do Google/Fabricantes",
            "description": f"Usuários no Android 12 (nota média {a12['avg_rating']} ⭐) relatam travamentos, mas a Google não disponibiliza suporte ativo e fabricantes como Motorola (ex: Moto G22, Moto G32) não liberaram Android 14. O usuário NÃO tem como atualizar o celular; a correção de memória e renderização deve ser feita obrigatoriamente dentro do aplicativo Minha Escola MG pela Prodemge."
        })
        
    # Verifica modelos Motorola Moto G
    moto_issues = [m for m in top_models if "Moto" in m["model"] or "G04" in m["model"] or "G32" in m["model"]]
    if moto_issues:
        names = ", ".join([m["model"] for m in moto_issues[:3]])
        alerts.append({
            "type": "warning",
            "title": f"Gargalo de Compatibilidade em Aparelhos Motorola ({names})",
            "description": "Reclamações apontam encerramento inesperado ou indisponibilidade na Play Store para a linha Moto G."
        })
        
    alerts.append({
        "type": "warning",
        "title": "Atenção: A política da Apple",
        "description": "A Apple tem uma política rigorosa de privacidade. Ela considera que revelar qual iPhone a pessoa tem (ex: iPhone 13, iPhone 15 Pro) ou qual iOS ela usa (ex: iOS 17.4) em um comentário público fere a privacidade do usuário."
    })
    
    # 7. Diagnóstico Especial: Aparelhos e Comentários sem Atualização para Android 13+ (Presos no Android <= 12)
    from analytics.device_lifecycle import evaluate_stuck_android_12
    
    cursor.execute("""
        SELECT id, store, user_name, rating, content, review_date, device_brand, device_model, os_name, os_version
        FROM reviews
        ORDER BY review_date DESC
    """)
    all_revs = [dict(row) for row in cursor.fetchall()]
    
    stuck_reviews = []
    stuck_models_map = {}
    
    for r in all_revs:
        eval_res = evaluate_stuck_android_12(
            brand=r.get('device_brand'),
            model=r.get('device_model'),
            os_name=r.get('os_name'),
            os_version=r.get('os_version'),
            content=r.get('content')
        )
        if eval_res['is_stuck']:
            m_name = r.get('device_model') or 'Não especificado'
            b_name = r.get('device_brand') or 'Geral'
            r_entry = {
                "id": r["id"],
                "user_name": r.get("user_name") or "Usuário",
                "rating": r.get("rating", 1),
                "content": r.get("content") or "",
                "device_brand": b_name,
                "device_model": m_name,
                "os_version": r.get("os_version") or "Android 12 ou anterior",
                "max_os": eval_res["max_os"],
                "reason": eval_res["reason"],
                "support_status": eval_res["support_status"],
                "review_date": r.get("review_date")
            }
            stuck_reviews.append(r_entry)
            
            if m_name not in stuck_models_map:
                stuck_models_map[m_name] = {
                    "model": m_name,
                    "brand": b_name,
                    "max_os": eval_res["max_os"],
                    "support_status": eval_res["support_status"],
                    "google_oem_notes": eval_res["google_oem_notes"],
                    "dev_recommendation": eval_res["recommendation"],
                    "count": 0,
                    "total_rating": 0,
                    "comments": []
                }
            stuck_models_map[m_name]["count"] += 1
            stuck_models_map[m_name]["total_rating"] += r.get("rating", 1)
            stuck_models_map[m_name]["comments"].append(r_entry)

    stuck_models_list = []
    for k, v in stuck_models_map.items():
        avg = round(v["total_rating"] / v["count"], 2) if v["count"] > 0 else 0.0
        stuck_models_list.append({
            "model": v["model"],
            "brand": v["brand"],
            "max_os": v["max_os"],
            "support_status": v["support_status"],
            "google_oem_notes": v["google_oem_notes"],
            "dev_recommendation": v["dev_recommendation"],
            "count": v["count"],
            "avg_rating": avg,
            "sample_comments": v["comments"][:3]
        })
    stuck_models_list.sort(key=lambda x: x["count"], reverse=True)
    
    stuck_android_12_diagnostic = {
        "total_stuck_reviews": len(stuck_reviews),
        "total_stuck_models": len(stuck_models_list),
        "models": stuck_models_list,
        "reviews": stuck_reviews,
        "critical_notice": "Atenção: Os aparelhos listados nesta seção foram congelados pelas fabricantes (Motorola, Samsung, Xiaomi, LG) no Android 12 ou versões anteriores e nunca receberam atualização para o Android 13+. Como o Google também encerrou o suporte ativo a essas versões, os cidadãos NÃO POSSUEM alternativa de upgrade do celular. Portanto, a equipe de engenharia da Prodemge deve obrigatoriamente manter compatibilidade retroativa no Minha Escola MG."
    }

    conn.close()
    return {
        "total_reviews": total_reviews,
        "explicit_devices_count": len(explicit_reviews),
        "os_breakdown": os_breakdown,
        "brands": brands,
        "top_models": top_models,
        "os_versions": os_versions,
        "app_versions": app_versions,
        "explicit_reviews": explicit_reviews,
        "alerts": alerts,
        "stuck_android_12_diagnostic": stuck_android_12_diagnostic
    }


def update_review_analysis(review_id: str, sentiment: str, category: str, suggested_response: str):
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.utcnow().isoformat()
    cursor.execute("""
    UPDATE reviews SET
        sentiment = ?,
        category = ?,
        ai_suggested_response = ?,
        updated_at = ?
    WHERE id = ?
    """, (sentiment, category, suggested_response, now, review_id))
    conn.commit()
    conn.close()

def update_review_status(review_id: str, status: str, response_text: Optional[str] = None, published_to_store: bool = False):
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.utcnow().isoformat()
    if response_text is not None:
        if published_to_store:
            cursor.execute("""
            UPDATE reviews SET
                status = ?,
                local_response = ?,
                developer_response = ?,
                developer_response_date = ?,
                published_to_store = 1,
                updated_at = ?
            WHERE id = ?
            """, (status, response_text, response_text, now, now, review_id))
        else:
            cursor.execute("""
            UPDATE reviews SET
                status = ?,
                local_response = ?,
                published_to_store = 0,
                updated_at = ?
            WHERE id = ?
            """, (status, response_text, now, review_id))
    else:
        cursor.execute("""
        UPDATE reviews SET
            status = ?,
            updated_at = ?
        WHERE id = ?
        """, (status, now, review_id))
    conn.commit()
    conn.close()

def get_setting(key: str, default: str = "") -> str:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    return row['value'] if row else default

def set_setting(key: str, value: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()

def get_all_settings() -> Dict[str, str]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM settings")
    settings = {row['key']: row['value'] for row in cursor.fetchall()}
    conn.close()
    return settings

# ==============================================================================
# GESTÃO DE USUÁRIOS E PERMISSÕES (RBAC)
# ==============================================================================

SUPER_ADMIN_EMAIL = os.environ.get("SUPER_ADMIN_EMAIL", "saulomartins.costa@gmail.com").strip().lower()

def load_seed_users_into_cursor(cursor, now_iso: str):
    """Carrega usuários persistentes do seed_users.json e da variável ALLOWED_USERS."""
    # 1. Carrega do seed_users.json
    if os.path.exists(SEED_USERS_PATH):
        try:
            with open(SEED_USERS_PATH, "r", encoding="utf-8") as f:
                saved = json.load(f)
                for u in saved:
                    email_c = u.get("email", "").strip().lower()
                    if not email_c or "@" not in email_c:
                        continue
                    role_c = u.get("role", "viewer")
                    status_c = u.get("status", "approved")
                    name_c = u.get("name", "")
                    cursor.execute("SELECT id, status, role FROM allowed_users WHERE LOWER(email) = ?", (email_c,))
                    row = cursor.fetchone()
                    if not row:
                        cursor.execute("""
                        INSERT INTO allowed_users (email, name, role, status, added_by, created_at)
                        VALUES (?, ?, ?, ?, 'seed_file', ?)
                        """, (email_c, name_c, role_c, status_c, now_iso))
                    elif row["status"] != status_c or row["role"] != role_c:
                        cursor.execute("UPDATE allowed_users SET status = ?, role = ? WHERE id = ?", (status_c, role_c, row["id"]))
        except Exception as e:
            print(f"Aviso ao carregar seed_users.json: {e}")

    # 2. Carrega da variável de ambiente ALLOWED_USERS (ex: email1@gmail.com:admin,email2@gmail.com:viewer ou JSON)
    env_users_str = os.environ.get("ALLOWED_USERS", "").strip()
    if env_users_str:
        try:
            if env_users_str.startswith("["):
                env_users = json.loads(env_users_str)
                for u in env_users:
                    email_c = u.get("email", "").strip().lower()
                    if "@" in email_c:
                        role_c = u.get("role", "viewer")
                        cursor.execute("SELECT id FROM allowed_users WHERE LOWER(email) = ?", (email_c,))
                        row = cursor.fetchone()
                        if not row:
                            cursor.execute("""
                            INSERT INTO allowed_users (email, name, role, status, added_by, created_at)
                            VALUES (?, ?, ?, 'approved', 'env_var', ?)
                            """, (email_c, u.get("name", ""), role_c, now_iso))
                        else:
                            cursor.execute("UPDATE allowed_users SET status = 'approved', role = ? WHERE id = ?", (role_c, row["id"]))
            else:
                for item in env_users_str.split(","):
                    item = item.strip()
                    if not item:
                        continue
                    parts = item.split(":")
                    email_c = parts[0].strip().lower()
                    role_c = parts[1].strip() if len(parts) > 1 and parts[1].strip() in ["admin", "viewer"] else "viewer"
                    if "@" in email_c:
                        cursor.execute("SELECT id FROM allowed_users WHERE LOWER(email) = ?", (email_c,))
                        row = cursor.fetchone()
                        if not row:
                            cursor.execute("""
                            INSERT INTO allowed_users (email, name, role, status, added_by, created_at)
                            VALUES (?, ?, ?, 'approved', 'env_var', ?)
                            """, (email_c, "", role_c, now_iso))
                        else:
                            cursor.execute("UPDATE allowed_users SET status = 'approved', role = ? WHERE id = ?", (role_c, row["id"]))
        except Exception as e:
            print(f"Aviso ao processar ALLOWED_USERS env: {e}")

def sync_seed_users():
    """Salva os usuários no arquivo seed_users.json para garantir que nunca se percam."""
    try:
        users = list_users()
        safe_users = [
            {
                "email": u["email"],
                "name": u.get("name", ""),
                "role": u.get("role", "viewer"),
                "status": u.get("status", "approved"),
                "added_by": u.get("added_by", "admin")
            }
            for u in users
        ]
        with open(SEED_USERS_PATH, "w", encoding="utf-8") as f:
            json.dump(safe_users, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Aviso ao sincronizar seed_users.json: {e}")

def get_users_env_string() -> str:
    """Gera a string pronta para colar no Render Dashboard (variável ALLOWED_USERS)."""
    users = list_users()
    approved = [u for u in users if u.get("status") == "approved"]
    items = [f"{u['email']}:{u['role']}" for u in approved]
    return ",".join(items)

def bulk_import_users(users_list: List[Dict[str, Any]]) -> int:
    """Importa uma lista de usuários e sincroniza o seed."""
    count = 0
    for u in users_list:
        email = u.get("email", "").strip().lower()
        if not email or "@" not in email:
            continue
        upsert_user(
            email=email,
            name=u.get("name", ""),
            role=u.get("role", "viewer"),
            status=u.get("status", "approved"),
            added_by=u.get("added_by", "import")
        )
        count += 1
    sync_seed_users()
    return count

def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    """Busca usuário pelo e-mail (case-insensitive)."""
    if not email:
        return None
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM allowed_users WHERE LOWER(email) = ?", (email.strip().lower(),))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    """Busca usuário pelo ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM allowed_users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def list_users() -> List[Dict[str, Any]]:
    """Lista todos os usuários ordenados por data de criação decrescente."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM allowed_users ORDER BY CASE WHEN role = 'admin' THEN 0 ELSE 1 END, created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def upsert_user(email: str, name: str = "", role: str = "viewer", status: str = "approved", added_by: str = "admin") -> Dict[str, Any]:
    """Cria ou atualiza um usuário autorizado."""
    email_clean = email.strip().lower()
    now_iso = datetime.utcnow().isoformat()
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM allowed_users WHERE LOWER(email) = ?", (email_clean,))
    existing = cursor.fetchone()
    
    # Se for o super admin, sempre mantém admin e approved
    if email_clean == SUPER_ADMIN_EMAIL.lower():
        role = "admin"
        status = "approved"

    if existing:
        cursor.execute("""
        UPDATE allowed_users SET
            name = CASE WHEN ? != '' THEN ? ELSE name END,
            role = ?,
            status = ?,
            added_by = ?
        WHERE LOWER(email) = ?
        """, (name, name, role, status, added_by, email_clean))
    else:
        cursor.execute("""
        INSERT INTO allowed_users (email, name, role, status, added_by, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (email_clean, name, role, status, added_by, now_iso))
        
    conn.commit()
    cursor.execute("SELECT * FROM allowed_users WHERE LOWER(email) = ?", (email_clean,))
    user = dict(cursor.fetchone())
    conn.close()
    sync_seed_users()
    return user

def handle_user_login(email: str, name: str = "", picture: str = "") -> Dict[str, Any]:
    """
    Processa login com Google:
    - Se já existe: atualiza last_login_at, name e picture se novos.
    - Se não existe: cadastra com status='pending' para aprovação do admin Saulo.
    """
    email_clean = email.strip().lower()
    now_iso = datetime.utcnow().isoformat()
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM allowed_users WHERE LOWER(email) = ?", (email_clean,))
    existing = cursor.fetchone()
    
    if existing:
        user_id = existing['id']
        cursor.execute("""
        UPDATE allowed_users SET
            name = CASE WHEN ? != '' THEN ? ELSE name END,
            picture = CASE WHEN ? != '' THEN ? ELSE picture END,
            last_login_at = ?
        WHERE id = ?
        """, (name, name, picture, picture, now_iso, user_id))
        conn.commit()
        cursor.execute("SELECT * FROM allowed_users WHERE id = ?", (user_id,))
        user = dict(cursor.fetchone())
        conn.close()
        return user
    else:
        # Novo usuário solicitando acesso: status 'pending'
        # A menos que seja o super admin
        is_super_admin = (email_clean == SUPER_ADMIN_EMAIL.lower())
        role = "admin" if is_super_admin else "viewer"
        status = "approved" if is_super_admin else "pending"
        
        cursor.execute("""
        INSERT INTO allowed_users (email, name, picture, role, status, added_by, created_at, last_login_at)
        VALUES (?, ?, ?, ?, ?, 'google_oauth', ?, ?)
        """, (email_clean, name, picture, role, status, now_iso, now_iso))
        conn.commit()
        user_id = cursor.lastrowid
        cursor.execute("SELECT * FROM allowed_users WHERE id = ?", (user_id,))
        user = dict(cursor.fetchone())
        conn.close()
        return user

def update_user_status(user_id: int, status: str) -> bool:
    """Atualiza o status de aprovação de um usuário (approved, pending, blocked)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT email FROM allowed_users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return False
    if row['email'].lower() == SUPER_ADMIN_EMAIL.lower() and status != 'approved':
        conn.close()
        return False  # O super admin não pode ser bloqueado
    cursor.execute("UPDATE allowed_users SET status = ? WHERE id = ?", (status, user_id))
    conn.commit()
    conn.close()
    sync_seed_users()
    return True

def update_user_role(user_id: int, role: str) -> bool:
    """Atualiza o papel de um usuário (admin ou viewer)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT email FROM allowed_users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return False
    if row['email'].lower() == SUPER_ADMIN_EMAIL.lower() and role != 'admin':
        conn.close()
        return False  # O super admin não pode perder privilégios de admin
    cursor.execute("UPDATE allowed_users SET role = ? WHERE id = ?", (role, user_id))
    conn.commit()
    conn.close()
    sync_seed_users()
    return True

def delete_user(user_id: int) -> bool:
    """Remove um usuário (não permite remover o super admin)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT email FROM allowed_users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return False
    if row['email'].lower() == SUPER_ADMIN_EMAIL.lower():
        conn.close()
        return False  # O super admin nunca pode ser removido
    cursor.execute("DELETE FROM allowed_users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    sync_seed_users()
    return True
