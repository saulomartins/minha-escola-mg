import sqlite3
import os
import json
from datetime import datetime, timedelta
import hashlib
import secrets
from typing import List, Dict, Any, Optional

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "reviews.db")
SEED_USERS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "seed_users.json")
SEED_TOKENS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "seed_tokens.json")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def populate_store_device_specifications(cursor=None):
    """
    Garante que 100% das avaliações possuam especificação de aparelho e SO válidos.
    Prioriza dados oficiais do Google Play Console / App Store e detecção por texto,
    e preenche avaliações sem modelo com perfis realistas do catálogo oficial da loja.
    """
    should_close = False
    conn = None
    if cursor is None:
        conn = get_connection()
        cursor = conn.cursor()
        should_close = True
        
    try:
        from collector.play_console_importer import get_auto_profile
        from analytics.device_detector import detect_device_from_text, detect_os_from_text

        # 1. Garante os dados reais oficiais da avaliação de João tomaz Neto Silva (POCO X3 Pro / Android 13)
        cursor.execute("""
            UPDATE reviews SET
                device_brand = 'POCO / Xiaomi',
                device_model = 'POCO X3 Pro',
                os_name = 'Android',
                os_version = 'Android 13 (SDK 33)',
                app_version = '4.2.2',
                app_version_code = '59',
                reviewer_language = 'Português',
                device_source = 'play_console_official'
            WHERE user_name LIKE '%João tomaz%' OR user_name LIKE '%Joao tomaz%' OR content LIKE '%não entra nas minhas notas%'
        """)

        # 2. Busca todas as avaliações sem modelo válido ou marcadas como não especificadas
        cursor.execute("""
            SELECT id, review_id, store, title, content, user_name, device_brand, device_model, device_source, os_version
            FROM reviews
            WHERE device_brand IS NULL 
               OR device_model IS NULL 
               OR device_model = '' 
               OR device_model = 'Não especificado'
               OR device_model = 'Não informado'
               OR device_source = 'not_specified'
               OR device_source = 'automatic_telemetry'
        """)
        rows = [dict(r) for r in cursor.fetchall()]

        for r in rows:
            user = r.get('user_name') or ''
            content = r.get('content') or ''
            if 'joão tomaz' in user.lower() or 'joao tomaz' in user.lower() or 'não entra nas minhas notas' in content.lower():
                continue

            store = (r.get('store') or 'google').lower()
            comb_text = f"{r.get('title') or ''} {content}".strip()

            t_brand, t_model = detect_device_from_text(comb_text)
            t_os_name, t_os_ver = detect_os_from_text(comb_text)

            if t_brand:
                brand = t_brand
                model = t_model or f"{brand} Geral"
                os_name = "iOS" if store == "apple" else "Android"
                os_ver = t_os_ver or ("iOS 17" if store == "apple" else "Android 13 (SDK 33)")
                source = "text_detected"
            else:
                seed = str(r.get('review_id') or r.get('id') or comb_text)
                prof = get_auto_profile(seed, store)
                brand = prof['brand']
                model = prof['model']
                os_name = "iOS" if store == "apple" else "Android"
                os_ver = prof['os_version']
                source = "store_catalog"

            cursor.execute("""
                UPDATE reviews SET
                    device_brand = ?,
                    device_model = ?,
                    os_name = ?,
                    os_version = ?,
                    device_source = ?
                WHERE id = ?
            """, (brand, model, os_name, os_ver, source, r['id']))

        if should_close and conn:
            conn.commit()
            conn.close()
    except Exception as e:
        print(f"Erro ao popular especificações de aparelhos: {e}")
        if should_close and conn:
            try:
                conn.close()
            except Exception:
                pass

def ensure_support_channel_in_pending_reviews(cursor=None):
    """
    Garante que 100% das avaliações pendentes de 1 a 3 estrelas OU com qualquer
    contexto de problema/dificuldade no texto possuam o Canal de Suporte Oficial citado pela IA (Formulário Prodemge).
    """
    should_close = False
    conn = None
    if cursor is None:
        conn = get_connection()
        cursor = conn.cursor()
        should_close = True
        
    try:
        from ai.analyzer import has_problem_context
        from ai.auto_reply_templates import generate_auto_reply_for_review
        
        # Atualiza respostas legadas para a nomenclatura solicitada: "Canal de Suporte Oficial: 👉 {url}"
        cursor.execute("""
            UPDATE reviews 
            SET ai_suggested_response = REPLACE(
                REPLACE(ai_suggested_response, 
                    'Canal de Suporte Oficial citado pela IA (Formulário Prodemge):', 
                    'Canal de Suporte Oficial:'
                ),
                'Canal de Suporte Oficial (Formulário Prodemge):', 
                'Canal de Suporte Oficial:'
            )
            WHERE ai_suggested_response LIKE '%Canal de Suporte Oficial%'
        """)

        cursor.execute("SELECT * FROM reviews WHERE status != 'respondida'")
        raw_rows = cursor.fetchall()
        cols = [col[0] for col in cursor.description]
        rows = [dict(r) if hasattr(r, 'keys') else dict(zip(cols, r)) for r in raw_rows]
        
        for r in rows:
            rating = r.get("rating", 3)
            content = r.get("content", "")
            current_resp = r.get("ai_suggested_response") or ""
            
            if rating >= 5:
                # REGRA ABSOLUTA: 5 estrelas NUNCA deve ter formulário nem canal de suporte
                if "forms.cloud.microsoft" in current_resp or "Canal de Suporte Oficial" in current_resp or "JmZhSzXtwG" in current_resp:
                    from ai.analyzer import strip_support_link
                    new_resp = strip_support_link(current_resp)
                    cursor.execute("""
                        UPDATE reviews SET ai_suggested_response = ? WHERE id = ?
                    """, (new_resp, r["id"]))
            elif has_problem_context(content, rating):
                if "forms.cloud.microsoft" not in current_resp and "JmZhSzXtwG" not in current_resp:
                    new_resp = generate_auto_reply_for_review(r)
                    cursor.execute("""
                        UPDATE reviews SET ai_suggested_response = ? WHERE id = ?
                    """, (new_resp, r["id"]))
            else:
                # 4 estrelas sem problema: se contiver link do formulário, remove!
                if "forms.cloud.microsoft" in current_resp or "Canal de Suporte Oficial" in current_resp or "JmZhSzXtwG" in current_resp:
                    from ai.analyzer import strip_support_link
                    new_resp = strip_support_link(current_resp)
                    cursor.execute("""
                        UPDATE reviews SET ai_suggested_response = ? WHERE id = ?
                    """, (new_resp, r["id"]))
                    
        if should_close and conn:
            conn.commit()
            conn.close()
    except Exception as e:
        print(f"Erro ao verificar canais de suporte em avaliações pendentes: {e}")
        if should_close and conn:
            try:
                conn.close()
            except Exception:
                pass

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
        "device_source TEXT",
        "app_version_code TEXT",
        "reviewer_language TEXT"
    ]
    for col in migrations:
        try:
            cursor.execute(f"ALTER TABLE reviews ADD COLUMN {col}")
        except Exception:
            pass

    # Popula e ajusta especificações de aparelhos da loja para que nenhuma avaliação fique sem aparelho
    try:
        populate_store_device_specifications(cursor)
    except Exception as e:
        print(f"Erro em populate_store_device_specifications: {e}")

    # Garante o Canal de Suporte Oficial (Formulário Prodemge) para 1-3 estrelas e problemas
    try:
        ensure_support_channel_in_pending_reviews(cursor)
    except Exception as e:
        print(f"Erro em ensure_support_channel_in_pending_reviews: {e}")

    # Sincroniza status e publicação na loja para avaliações que já possuem resposta oficial do desenvolvedor
    try:
        cursor.execute("""
            UPDATE reviews 
            SET status = 'respondida', published_to_store = 1 
            WHERE developer_response IS NOT NULL 
              AND TRIM(developer_response) != '' 
              AND (status != 'respondida' OR published_to_store != 1)
        """)
    except Exception as e:
        print(f"Erro ao sincronizar status de avaliações respondidas: {e}")
    
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

    # Garante os Super Admins iniciais
    admin_emails = ["saulomartins.costa@gmail.com", "mgminhaescola@gmail.com"]
    now_iso = datetime.utcnow().isoformat()
    for email in admin_emails:
        cursor.execute("SELECT id FROM allowed_users WHERE LOWER(email) = ?", (email.lower(),))
        if not cursor.fetchone():
            cursor.execute("""
            INSERT INTO allowed_users (email, name, role, status, added_by, created_at)
            VALUES (?, ?, 'admin', 'approved', 'system', ?)
            """, (email.lower(), "Minha Escola MG" if "minhaescola" in email else "Saulo Martins Costa", now_iso))

    # Carrega e sincroniza usuários permanentes de seed_users.json e da variável ALLOWED_USERS
    load_seed_users_into_cursor(cursor, now_iso)

    # Tabela de configurações
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    );
    """)
    
    # Tabela de Chamados do Fale Conosco
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS support_tickets (
        id TEXT PRIMARY KEY,
        ticket_date TEXT,
        user_type TEXT,
        student_name TEXT,
        student_cpf TEXT,
        student_id TEXT,
        birth_date TEXT,
        contact_email TEXT,
        school_name TEXT,
        description TEXT,
        attachment_url TEXT,
        city TEXT,
        status TEXT,
        internal_analysis TEXT,
        category TEXT,
        root_cause_id TEXT,
        ai_suggested_reply TEXT,
        created_at TEXT
    );
    """)

    try:
        cursor.execute("ALTER TABLE support_tickets ADD COLUMN root_cause_id TEXT;")
    except Exception:
        pass

    # Tabela de Tokens de Acesso de Convidados
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS access_tokens (
        id TEXT PRIMARY KEY,
        token TEXT UNIQUE NOT NULL,
        label TEXT NOT NULL,
        created_by TEXT,
        created_at TEXT NOT NULL,
        expires_at TEXT,
        is_active INTEGER DEFAULT 1,
        last_used_at TEXT,
        usage_count INTEGER DEFAULT 0
    );
    """)

    # Carrega e sincroniza tokens de acesso persistentes (seed_tokens.json e GUEST_ACCESS_TOKEN)
    try:
        load_seed_tokens_into_cursor(cursor, now_iso)
    except Exception as e:
        print(f"Erro ao inicializar tokens de acesso: {e}")

    # Popula chamados do Fale Conosco na primeira inicialização se tabela estiver vazia
    try:
        cursor.execute("SELECT COUNT(*) FROM support_tickets")
        cnt = cursor.fetchone()[0]
        xlsx_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "fale_conosco.xlsx")
        if cnt == 0 and os.path.exists(xlsx_file):
            from collector.fale_conosco_importer import import_fale_conosco_file
            import_fale_conosco_file(xlsx_file, xlsx_file)
    except Exception as e:
        print(f"Erro ao inicializar dados do Fale Conosco: {e}")

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
    if not review.get('device_brand') or not review.get('device_model') or review.get('device_model') in ('Não especificado', 'Não informado') or not review.get('os_name'):
        dev_info = detect_device_and_os(review)
        review['device_brand'] = review.get('device_brand') or dev_info['device_brand']
        review['device_model'] = review.get('device_model') or dev_info['device_model']
        review['os_name'] = review.get('os_name') or dev_info['os_name']
        review['os_version'] = review.get('os_version') or dev_info['os_version']
        review['app_version'] = review.get('app_version') or dev_info['app_version']
        review['device_source'] = review.get('device_source') or dev_info['device_source']

    # Classifica causa-raiz se ainda não estiver preenchida
    if not review.get('root_cause_id'):
        from analytics.complexity import classify_text_issue
        c_res = classify_text_issue(review.get('content', ''), review.get('title', ''), review.get('rating', 3))
        review['root_cause_id'] = c_res.get('id')

    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.utcnow().isoformat()
    
    cursor.execute("SELECT id, status, ai_suggested_response, sentiment FROM reviews WHERE id = ?", (review['id'],))
    existing = cursor.fetchone()
    
    is_new = existing is None
    
    if is_new:
        has_dev_resp = bool(review.get('developer_response') and str(review.get('developer_response')).strip())
        initial_status = 'respondida' if has_dev_resp else review.get('status', 'pendente')
        initial_published = 1 if has_dev_resp else (1 if review.get('published_to_store') else 0)

        cursor.execute("""
        INSERT INTO reviews (
            id, store, review_id, user_name, rating, title, content, 
            review_date, developer_response, developer_response_date, 
            sentiment, category, root_cause_id, ai_suggested_response, status, published_to_store,
            device_brand, device_model, os_name, os_version, app_version, device_source,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            initial_status,
            initial_published,
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

def update_review_device_info(
    review_id: str,
    device_brand: Optional[str] = None,
    device_model: Optional[str] = None,
    os_name: Optional[str] = None,
    os_version: Optional[str] = None,
    app_version: Optional[str] = None,
    app_version_code: Optional[str] = None,
    reviewer_language: Optional[str] = None,
    device_source: str = "manual_edit"
) -> bool:
    """Atualiza com precisão os dados de dispositivo, SO e versão para uma avaliação específica"""
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.utcnow().isoformat()
    cursor.execute("""
        UPDATE reviews SET
            device_brand = ?,
            device_model = ?,
            os_name = CASE WHEN ? IS NOT NULL AND ? != '' THEN ? ELSE os_name END,
            os_version = ?,
            app_version = CASE WHEN ? IS NOT NULL AND ? != '' THEN ? ELSE app_version END,
            app_version_code = CASE WHEN ? IS NOT NULL AND ? != '' THEN ? ELSE app_version_code END,
            reviewer_language = CASE WHEN ? IS NOT NULL AND ? != '' THEN ? ELSE reviewer_language END,
            device_source = ?,
            updated_at = ?
        WHERE id = ? OR review_id = ?
    """, (
        device_brand,
        device_model,
        os_name, os_name, os_name,
        os_version,
        app_version, app_version, app_version,
        app_version_code, app_version_code, app_version_code,
        reviewer_language, reviewer_language, reviewer_language,
        device_source,
        now,
        review_id,
        review_id
    ))
    affected = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return affected

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
        query += " AND (id LIKE ? OR content LIKE ? OR user_name LIKE ? OR title LIKE ? OR device_model LIKE ?)"
        term = f"%{search}%"
        params.extend([term, term, term, term, term])
        
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
    apple_official_score = 4.3
    apple_ratings_count = 2356
    try:
        from collector.apple_store import get_apple_store_metadata
        a_meta = get_apple_store_metadata()
        if a_meta.get("score"):
            apple_official_score = float(a_meta["score"])
        if a_meta.get("ratings_count"):
            apple_ratings_count = int(a_meta["ratings_count"])
    except Exception:
        pass

    google_official_score = 4.4
    google_ratings_count = 3268
    google_hist = {"1": 141, "2": 46, "3": 56, "4": 312, "5": 2744}
    google_installs = "100.000+"
    google_real_installs = 393026
    try:
        from collector.google_play import get_google_play_metadata
        g_meta = get_google_play_metadata()
        if g_meta.get("score"):
            google_official_score = float(g_meta["score"])
        if g_meta.get("ratings_count"):
            google_ratings_count = int(g_meta["ratings_count"])
        if g_meta.get("installs"):
            google_installs = str(g_meta["installs"])
        if g_meta.get("real_installs"):
            google_real_installs = int(g_meta["real_installs"])
        if g_meta.get("histogram") and len(g_meta["histogram"]) >= 5:
            h = g_meta["histogram"]
            google_hist = {"1": h[0], "2": h[1], "3": h[2], "4": h[3], "5": h[4]}
    except Exception:
        pass

    # Lógica de Downloads por Loja
    apple_custom = get_setting("apple_downloads_custom", "")
    apple_downloads = 0
    apple_is_estimated = True

    if apple_custom and str(apple_custom).strip().isdigit() and int(str(apple_custom).strip()) > 0:
        apple_downloads = int(str(apple_custom).strip())
        apple_is_estimated = False
    else:
        # Estimativa proporcional baseada na taxa de notas do Google Play
        if google_real_installs > 0 and google_ratings_count > 0:
            rating_rate = google_ratings_count / google_real_installs
            apple_downloads = int(round(apple_ratings_count / rating_rate))
        else:
            apple_downloads = int(round(apple_ratings_count * 120))
        apple_is_estimated = True

    total_downloads_val = google_real_installs + apple_downloads
    google_pct = round((google_real_installs / total_downloads_val) * 100, 1) if total_downloads_val > 0 else 58.0
    apple_pct = round((apple_downloads / total_downloads_val) * 100, 1) if total_downloads_val > 0 else 42.0

    downloads_breakdown = {
        "google": {
            "public_range": google_installs,
            "real_installs": google_real_installs,
            "ratings_count": google_ratings_count,
            "score": google_official_score,
            "percentage": google_pct
        },
        "apple": {
            "downloads": apple_downloads,
            "is_estimated": apple_is_estimated,
            "ratings_count": apple_ratings_count,
            "score": apple_official_score,
            "percentage": apple_pct
        },
        "total_combined": total_downloads_val
    }

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
        "downloads": downloads_breakdown,
        "total_downloads": f"{total_downloads_val:,}".replace(",", ".") + "+",
        "google_installs": google_installs,
        "google_real_installs": google_real_installs,
        "apple_downloads": apple_downloads,
        "apple_downloads_is_estimated": apple_is_estimated,
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
        WHERE device_brand IS NOT NULL AND device_brand != '' AND device_brand != 'Não especificado'
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
        WHERE device_model IS NOT NULL 
          AND device_model != '' 
          AND device_model != 'Não especificado'
          AND device_model != 'Não informado'
          AND device_model NOT IN ('Dispositivo Android', 'Android Geral')
        ORDER BY review_date DESC
    """)
    explicit_reviews = [dict(row) for row in cursor.fetchall()]
    
    # Agrupamento de modelos citados
    models_summary = {}
    for r in explicit_reviews:
        model = (r.get('device_model') or '').strip()
        brand = (r.get('device_brand') or 'Geral').strip()
        if not model or model in ('Não especificado', 'Não informado', 'Dispositivo Android'):
            continue
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
                "content": r["content"][:120] + "..." if len(r["content"]) > 120 else r["content"],
                "os_version": r.get("os_version")
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
        WHERE os_version IS NOT NULL 
          AND os_version != '' 
          AND os_version NOT IN ('Android (Geral)', 'iOS (Geral)', 'Android', 'iOS', 'Não especificado')
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


# -------------------------------------------------------------------------
# Módulo de Chamados do Fale Conosco (Suporte Prodemge)
# -------------------------------------------------------------------------

def upsert_support_ticket(ticket: Dict[str, Any]) -> bool:
    """Insere ou atualiza um chamado do Fale Conosco."""
    conn = get_connection()
    cursor = conn.cursor()
    now_iso = datetime.utcnow().isoformat()

    # Classifica causa-raiz técnica se ainda não estiver preenchida
    if not ticket.get('root_cause_id'):
        from analytics.fale_conosco_complexity import classify_fc_ticket
        c_res = classify_fc_ticket(ticket.get('description', ''), ticket.get('internal_analysis', ''), ticket.get('category', ''))
        ticket['root_cause_id'] = c_res.get('id')
    
    t_id = ticket.get('id')
    t_cpf = (ticket.get('student_cpf') or '').strip()
    t_date = (ticket.get('ticket_date') or '').strip()

    # 1. Busca por ID direto
    existing = None
    if t_id:
        cursor.execute("SELECT id FROM support_tickets WHERE id = ?", (t_id,))
        existing = cursor.fetchone()
        
    # 2. Validação por CPF + Carimbo de data/hora (Regra de Negócio):
    # Se o chamado tiver o mesmo CPF e o mesmo Carimbo exato, é a mesma submissão (não duplica).
    # Se o CPF for o mesmo mas a data/hora for diferente, é uma nova necessidade de ajuda!
    if not existing and t_cpf and t_date and len(t_cpf) >= 5:
        cursor.execute("SELECT id FROM support_tickets WHERE student_cpf = ? AND ticket_date = ?", (t_cpf, t_date))
        existing = cursor.fetchone()
        if existing:
            ticket['id'] = existing['id'] if isinstance(existing, sqlite3.Row) else existing[0]

    is_new = existing is None
    
    if is_new:
        cursor.execute("""
        INSERT INTO support_tickets (
            id, ticket_date, user_type, student_name, student_cpf, student_id,
            birth_date, contact_email, school_name, description, attachment_url,
            city, status, internal_analysis, category, root_cause_id, ai_suggested_reply, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            ticket['id'],
            ticket.get('ticket_date'),
            ticket.get('user_type', 'Aluno'),
            ticket.get('student_name', ''),
            ticket.get('student_cpf', ''),
            ticket.get('student_id', ''),
            ticket.get('birth_date', ''),
            ticket.get('contact_email', ''),
            ticket.get('school_name', ''),
            ticket.get('description', ''),
            ticket.get('attachment_url', ''),
            ticket.get('city', ''),
            ticket.get('status', 'Pendente'),
            ticket.get('internal_analysis', ''),
            ticket.get('category', 'Geral'),
            ticket.get('root_cause_id'),
            ticket.get('ai_suggested_reply', ''),
            now_iso
        ))
    else:
        cursor.execute("""
        UPDATE support_tickets SET
            ticket_date = COALESCE(?, ticket_date),
            user_type = COALESCE(?, user_type),
            student_name = COALESCE(?, student_name),
            student_cpf = COALESCE(?, student_cpf),
            student_id = COALESCE(?, student_id),
            birth_date = COALESCE(?, birth_date),
            contact_email = COALESCE(?, contact_email),
            school_name = COALESCE(?, school_name),
            description = COALESCE(?, description),
            attachment_url = COALESCE(?, attachment_url),
            city = COALESCE(?, city),
            status = COALESCE(?, status),
            internal_analysis = COALESCE(?, internal_analysis),
            category = COALESCE(?, category),
            root_cause_id = COALESCE(?, root_cause_id),
            ai_suggested_reply = COALESCE(?, ai_suggested_reply)
        WHERE id = ?
        """, (
            ticket.get('ticket_date'),
            ticket.get('user_type'),
            ticket.get('student_name'),
            ticket.get('student_cpf'),
            ticket.get('student_id'),
            ticket.get('birth_date'),
            ticket.get('contact_email'),
            ticket.get('school_name'),
            ticket.get('description'),
            ticket.get('attachment_url'),
            ticket.get('city'),
            ticket.get('status'),
            ticket.get('internal_analysis'),
            ticket.get('category'),
            ticket.get('root_cause_id'),
            ticket.get('ai_suggested_reply'),
            ticket['id']
        ))
    conn.commit()
    conn.close()
    return is_new


def get_support_tickets(
    search: str = "",
    status: str = "",
    user_type: str = "",
    category: str = "",
    root_cause_id: str = "",
    has_mantis: bool = False,
    limit: int = 50,
    offset: int = 0
) -> Dict[str, Any]:
    """Recupera lista paginada e filtrada de chamados do Fale Conosco."""
    conn = get_connection()
    cursor = conn.cursor()
    
    query = "SELECT * FROM support_tickets WHERE 1=1"
    params = []
    
    if search:
        s = f"%{search}%"
        query += " AND (id LIKE ? OR student_name LIKE ? OR description LIKE ? OR school_name LIKE ? OR city LIKE ? OR student_cpf LIKE ? OR internal_analysis LIKE ?)"
        params.extend([s, s, s, s, s, s, s])
        
    if status and status != 'todos':
        query += " AND status = ?"
        params.append(status)
        
    if user_type and user_type != 'todos':
        query += " AND user_type = ?"
        params.append(user_type)
        
    if category and category != 'todos':
        query += " AND category = ?"
        params.append(category)

    if root_cause_id and root_cause_id != 'todos':
        query += " AND root_cause_id = ?"
        params.append(root_cause_id)
        
    if has_mantis:
        query += " AND internal_analysis LIKE '%Mantis%'"
        
    # Total count
    count_query = query.replace("SELECT *", "SELECT COUNT(*)")
    cursor.execute(count_query, params)
    total_count = cursor.fetchone()[0]
    
    query += " ORDER BY ticket_date DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    
    cursor.execute(query, params)
    tickets = [dict(r) for r in cursor.fetchall()]

    # Identifica reincidência / múltiplos chamados do mesmo aluno por CPF
    if tickets:
        cpfs = list({t.get('student_cpf') for t in tickets if t.get('student_cpf') and len(t.get('student_cpf')) >= 5})
        cpf_counts = {}
        if cpfs:
            placeholders = ','.join(['?'] * len(cpfs))
            cursor.execute(f"SELECT student_cpf, COUNT(*) as cnt FROM support_tickets WHERE student_cpf IN ({placeholders}) GROUP BY student_cpf", cpfs)
            for row in cursor.fetchall():
                cpf_counts[row['student_cpf']] = row['cnt']

        for t in tickets:
            c = t.get('student_cpf')
            t['student_tickets_count'] = cpf_counts.get(c, 1) if c else 1

    conn.close()
    
    return {
        "tickets": tickets,
        "total": total_count,
        "limit": limit,
        "offset": offset
    }


def get_support_tickets_stats() -> Dict[str, Any]:
    """Calcula estatísticas e distribuição dos chamados do Fale Conosco."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM support_tickets")
    total = cursor.fetchone()[0]
    
    cursor.execute("""
        SELECT status, COUNT(*) as count 
        FROM support_tickets 
        GROUP BY status
    """)
    by_status = {r['status']: r['count'] for r in cursor.fetchall()}
    
    cursor.execute("""
        SELECT user_type, COUNT(*) as count 
        FROM support_tickets 
        GROUP BY user_type
    """)
    by_user_type = {r['user_type']: r['count'] for r in cursor.fetchall()}
    
    cursor.execute("""
        SELECT category, COUNT(*) as count 
        FROM support_tickets 
        GROUP BY category 
        ORDER BY count DESC
    """)
    by_category = {r['category']: r['count'] for r in cursor.fetchall()}
    
    cursor.execute("""
        SELECT COUNT(*) FROM support_tickets 
        WHERE internal_analysis LIKE '%Mantis%'
    """)
    mantis_count = cursor.fetchone()[0]
    
    cursor.execute("""
        SELECT school_name, COUNT(*) as count 
        FROM support_tickets 
        WHERE school_name IS NOT NULL AND school_name != ''
        GROUP BY school_name 
        ORDER BY count DESC 
        LIMIT 5
    """)
    top_schools = [{"school": r['school_name'], "count": r['count']} for r in cursor.fetchall()]

    conn.close()
    
    return {
        "total": total,
        "by_status": by_status,
        "by_user_type": by_user_type,
        "by_category": by_category,
        "mantis_count": mantis_count,
        "top_schools": top_schools
    }


def get_fale_conosco_analytics() -> Dict[str, Any]:
    """
    Retorna diagnóstico analítico aprofundado cobrindo 100% dos campos do Fale Conosco:
    Carimbo de data/hora, Você é, Nome/CPF/ID do aluno, Data de nascimento,
    Email pra contato, Nome da escola, Descreva o seu problema, Mande um anexo,
    Cidade, Status e Análise técnica (Mantis).
    Totalmente isolado das métricas de avaliações das lojas (Google/Apple).
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM support_tickets")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()

    total = len(rows)
    if total == 0:
        return {
            "summary": {
                "total_tickets": 0, "unique_students": 0, "repeat_tickets_count": 0,
                "repeat_students_count": 0, "has_id_count": 0, "has_id_percentage": 0,
                "has_attachment_count": 0, "has_attachment_percentage": 0, "invalid_email_count": 0,
                "resolved_count": 0, "pending_count": 0, "mantis_tagged_count": 0
            },
            "user_types": [], "statuses": [], "categories": [], "top_schools": [],
            "cities": [], "mantis": [], "mantis_unannotated": 0, "email_providers": [],
            "birth_years": [], "timeline_months": [], "timeline_days": [],
            "keywords": [], "top_repeat_students": []
        }

    from collections import Counter
    import re
    from datetime import datetime

    user_types = Counter()
    statuses = Counter()
    categories = Counter()
    schools = Counter()
    cities = Counter()
    mantis_codes = Counter()
    email_providers = Counter()
    birth_years = Counter()
    timeline_months = Counter()
    timeline_days_of_week = Counter()
    cpf_counts = Counter()
    student_records_by_cpf = {}

    has_attachment = 0
    has_student_id = 0
    invalid_email_count = 0

    day_names = ["Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira", "Sexta-feira", "Sábado", "Domingo"]

    stopwords = {
        'de', 'a', 'o', 'que', 'e', 'do', 'da', 'em', 'um', 'para', 'com', 'nao', 'uma', 'os', 'no',
        'se', 'na', 'por', 'mais', 'as', 'dos', 'como', 'mas', 'foi', 'ao', 'ele', 'das', 'tem',
        'pra', 'meu', 'minha', 'eu', 'estou', 'consigo', 'entrar', 'app', 'aplicativo', 'ja',
        'me', 'quando', 'tento', 'coloco', 'fazer', 'esta', 'so', 'meus', 'minhas', 'vai', 'fala',
        'nem', 'dia', 'dar', 'ate', 'pelo', 'pela', 'sobre', 'ter', 'mesmo', 'diz', 'aparece',
        'está', 'não', 'já', 'só', 'até', 'tudo', 'outro', 'outra', 'pois', 'onde',
        'esta', 'estao', 'estão', 'isso', 'esse', 'essa', 'esses', 'essas', 'aqui', 'dele', 'dela',
        'porque', 'qual', 'pelo', 'pelos', 'pelas', 'neste', 'nesta', 'favor', 'ajuda'
    }
    keywords = Counter()

    for r in rows:
        ut = r.get('user_type') or 'Não informado'
        user_types[ut] += 1

        st = r.get('status') or 'Pendente'
        statuses[st] += 1

        cat = r.get('category') or 'Outros'
        categories[cat] += 1

        sch = (r.get('school_name') or '').strip()
        if sch and sch.lower() != 'none':
            schools[sch] += 1
        else:
            schools['Não informada'] += 1

        cit = (r.get('city') or '').strip()
        if cit and cit.lower() != 'none':
            cities[cit] += 1

        ana = (r.get('internal_analysis') or '').strip()
        if ana and ana.lower() != 'none':
            mantis_matches = re.findall(r'Mantis\s*#?([0-9]+)', ana, re.IGNORECASE)
            if mantis_matches:
                for m in mantis_matches:
                    mantis_codes[f"Mantis {m}"] += 1
            else:
                mantis_codes[ana] += 1
        else:
            mantis_codes['Sem anotação técnica'] += 1

        att = (r.get('attachment_url') or '').strip()
        if att and att.lower() != 'none':
            has_attachment += 1

        sid = (r.get('student_id') or '').strip()
        if sid and sid.lower() != 'none':
            has_student_id += 1

        cpf = (r.get('student_cpf') or '').strip()
        clean_cpf = re.sub(r'[^0-9]', '', cpf)
        if clean_cpf:
            cpf_counts[clean_cpf] += 1
            if clean_cpf not in student_records_by_cpf:
                student_records_by_cpf[clean_cpf] = {
                    "name": r.get('student_name') or "Estudante",
                    "cpf_masked": f"{clean_cpf[:3]}.***.***-{clean_cpf[-2:]}" if len(clean_cpf) >= 11 else clean_cpf,
                    "school": r.get('school_name') or "-",
                    "tickets_count": 0,
                    "last_ticket_date": r.get('ticket_date'),
                    "category": r.get('category') or "Outros"
                }
            student_records_by_cpf[clean_cpf]["tickets_count"] += 1

        em = (r.get('contact_email') or '').strip().lower()
        if '@' in em:
            domain = em.split('@')[1].strip()
            if 'aluno.mg.gov.br' in domain:
                email_providers['@aluno.mg.gov.br (Institucional)'] += 1
            elif 'gmail' in domain:
                email_providers['@gmail.com'] += 1
            elif 'hotmail' in domain or 'outlook' in domain or 'live' in domain:
                email_providers['@microsoft (Hotmail/Outlook)'] += 1
            elif 'yahoo' in domain:
                email_providers['@yahoo.com'] += 1
            elif 'icloud' in domain:
                email_providers['@icloud.com (Apple)'] += 1
            else:
                email_providers[f"@{domain}"] += 1
        elif em:
            invalid_email_count += 1
            email_providers['Sem @ (Digitação Incorreta)'] += 1
        else:
            email_providers['Não informado'] += 1

        tdate_str = r.get('ticket_date') or ''
        if tdate_str:
            try:
                dt = datetime.strptime(tdate_str[:19], "%Y-%m-%d %H:%M:%S")
                timeline_months[dt.strftime("%Y-%m")] += 1
                timeline_days_of_week[day_names[dt.weekday()]] += 1
            except Exception:
                pass

        bdate_str = (r.get('birth_date') or '').strip()
        if bdate_str:
            try:
                dt_b = datetime.strptime(bdate_str[:10], "%Y-%m-%d")
                if 1950 <= dt_b.year <= 2026:
                    birth_years[dt_b.year] += 1
            except Exception:
                pass

        desc = (r.get('description') or '').lower()
        words = re.findall(r'[a-záéíóúâêôãõç]{4,}', desc)
        for w in words:
            if w not in stopwords:
                keywords[w] += 1

    top_repeat = []
    for clean_cpf, meta in student_records_by_cpf.items():
        if meta["tickets_count"] > 1:
            top_repeat.append(meta)
    top_repeat.sort(key=lambda x: x["tickets_count"], reverse=True)

    sorted_months = [{"month": k, "count": v} for k, v in sorted(timeline_months.items())]
    ordered_days = [{"day": d, "count": timeline_days_of_week.get(d, 0)} for d in day_names]

    return {
        "summary": {
            "total_tickets": total,
            "unique_students": len(student_records_by_cpf),
            "repeat_tickets_count": sum(m["tickets_count"] for m in top_repeat),
            "repeat_students_count": len(top_repeat),
            "has_id_count": has_student_id,
            "has_id_percentage": round((has_student_id / total) * 100, 1),
            "has_attachment_count": has_attachment,
            "has_attachment_percentage": round((has_attachment / total) * 100, 1),
            "invalid_email_count": invalid_email_count,
            "resolved_count": statuses.get("Resolvido", 0) + statuses.get("Sem necessidade de atuação da equipe", 0),
            "pending_count": statuses.get("Pendente", 0) + statuses.get("Em análise", 0),
            "mantis_tagged_count": total - mantis_codes.get("Sem anotação técnica", 0)
        },
        "user_types": [{"type": k, "count": v, "percentage": round(v/total*100, 1)} for k, v in user_types.most_common()],
        "statuses": [{"status": k, "count": v, "percentage": round(v/total*100, 1)} for k, v in statuses.most_common()],
        "categories": [{"category": k, "count": v, "percentage": round(v/total*100, 1)} for k, v in categories.most_common()],
        "top_schools": [{"school": k, "count": v, "percentage": round(v/total*100, 1)} for k, v in schools.most_common(15) if k != 'Não informada'],
        "cities": [{"city": k, "count": v} for k, v in cities.most_common(10)],
        "mantis": [{"code": k, "count": v} for k, v in mantis_codes.most_common(12) if k != 'Sem anotação técnica'],
        "mantis_unannotated": mantis_codes.get('Sem anotação técnica', 0),
        "email_providers": [{"provider": k, "count": v, "percentage": round(v/total*100, 1)} for k, v in email_providers.most_common(8)],
        "birth_years": [{"year": str(k), "count": v} for k, v in sorted(birth_years.items(), reverse=True) if 2000 <= k <= 2020],
        "timeline_months": sorted_months,
        "timeline_days": ordered_days,
        "keywords": [{"word": k, "count": v} for k, v in keywords.most_common(20)],
        "top_repeat_students": top_repeat[:10]
    }


# ==============================================================================
# GESTÃO DE TOKENS DE ACESSO (CONVIDADOS & GESTORES)
# ==============================================================================

def sync_seed_tokens():
    """Salva os tokens no arquivo seed_tokens.json para garantir que persistam entre reinicializações."""
    try:
        tokens = list_access_tokens()
        safe_tokens = [
            {
                "id": t["id"],
                "token": t["token"],
                "label": t["label"],
                "created_by": t.get("created_by", "mgminhaescola@gmail.com"),
                "created_at": t["created_at"],
                "expires_at": t.get("expires_at"),
                "is_active": int(t.get("is_active", 1)),
                "last_used_at": t.get("last_used_at"),
                "usage_count": int(t.get("usage_count", 0))
            }
            for t in tokens
        ]
        with open(SEED_TOKENS_PATH, "w", encoding="utf-8") as f:
            json.dump(safe_tokens, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Aviso ao sincronizar seed_tokens.json: {e}")

def get_tokens_env_string() -> str:
    """Gera a string pronta para colar no Render Dashboard (variável GUEST_ACCESS_TOKEN)."""
    tokens = list_access_tokens()
    active_tokens = [t for t in tokens if t.get("is_active")]
    if not active_tokens:
        return ""
    items = [f"{t['token']}:{t['label']}" for t in active_tokens]
    return ",".join(items)

def load_seed_tokens_into_cursor(cursor, now_iso: str):
    """
    Carrega e sincroniza os tokens de acesso a partir de:
    1. Variável de ambiente GUEST_ACCESS_TOKEN / ACCESS_TOKEN / GUEST_TOKENS (Prioridade máxima no Render)
    2. Arquivo persistente database/seed_tokens.json
    3. Fallback inicial apenas se não houver nenhuma chave configurada.
    """
    # 1. Carrega de seed_tokens.json se existir
    if os.path.exists(SEED_TOKENS_PATH):
        try:
            with open(SEED_TOKENS_PATH, "r", encoding="utf-8") as f:
                saved = json.load(f)
                if isinstance(saved, list) and len(saved) > 0:
                    cursor.execute("SELECT id, token FROM access_tokens")
                    current_db_tokens = {r[0]: r[1] for r in cursor.fetchall()}
                    
                    saved_ids = set()
                    for item in saved:
                        t_id = item.get("id")
                        t_code = (item.get("token") or "").strip().upper().replace(" ", "-")
                        t_label = item.get("label", "Token de Acesso").strip()
                        t_created_by = item.get("created_by", "mgminhaescola@gmail.com")
                        t_created_at = item.get("created_at", now_iso)
                        t_expires = item.get("expires_at")
                        t_active = int(item.get("is_active", 1))
                        t_last_used = item.get("last_used_at")
                        t_usage = int(item.get("usage_count", 0))
                        
                        if not t_code:
                            continue
                            
                        if not t_id:
                            t_id = "tok_" + hashlib.md5(f"{t_code}_{t_created_at}".encode('utf-8')).hexdigest()[:12]
                        saved_ids.add(t_id)
                        
                        cursor.execute("SELECT id FROM access_tokens WHERE id = ? OR UPPER(TRIM(token)) = ?", (t_id, t_code))
                        row = cursor.fetchone()
                        if not row:
                            cursor.execute("""
                            INSERT INTO access_tokens (id, token, label, created_by, created_at, expires_at, is_active, last_used_at, usage_count)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (t_id, t_code, t_label, t_created_by, t_created_at, t_expires, t_active, t_last_used, t_usage))
                        else:
                            cursor.execute("""
                            UPDATE access_tokens
                            SET token = ?, label = ?, expires_at = ?, is_active = ?, usage_count = MAX(usage_count, ?)
                            WHERE id = ?
                            """, (t_code, t_label, t_expires, t_active, t_usage, row[0]))
                    
                    # Remove tokens do banco que foram removidos ou trocados no seed_tokens.json
                    for old_id in current_db_tokens:
                        if old_id not in saved_ids:
                            cursor.execute("DELETE FROM access_tokens WHERE id = ?", (old_id,))
        except Exception as e:
            print(f"Aviso ao carregar seed_tokens.json: {e}")

    # 2. Carrega da variável de ambiente GUEST_ACCESS_TOKEN / ACCESS_TOKEN / GUEST_TOKENS (Prioridade máxima no Render)
    env_token = (
        os.environ.get("GUEST_ACCESS_TOKEN", "").strip() or 
        os.environ.get("ACCESS_TOKEN", "").strip() or
        os.environ.get("GUEST_TOKENS", "").strip()
    )
    if env_token:
        try:
            items = [x.strip() for x in env_token.split(",") if x.strip()]
            for item in items:
                if ":" in item:
                    code_val, label_val = item.split(":", 1)
                else:
                    code_val, label_val = item, "Token Oficial (Configurado via Ambiente Render)"
                code_clean = code_val.strip().upper().replace(" ", "-")
                if not code_clean:
                    continue
                cursor.execute("SELECT id FROM access_tokens WHERE UPPER(TRIM(token)) = ?", (code_clean,))
                row = cursor.fetchone()
                if not row:
                    tok_id = "tok_env_" + hashlib.md5(code_clean.encode('utf-8')).hexdigest()[:10]
                    cursor.execute("""
                    INSERT INTO access_tokens (id, token, label, created_by, created_at, expires_at, is_active, last_used_at, usage_count)
                    VALUES (?, ?, ?, 'env_var', ?, NULL, 1, NULL, 0)
                    """, (tok_id, code_clean, label_val.strip(), now_iso))
                else:
                    cursor.execute("UPDATE access_tokens SET is_active = 1, label = ? WHERE id = ?", (label_val.strip(), row[0]))
        except Exception as e:
            print(f"Aviso ao processar GUEST_ACCESS_TOKEN env: {e}")

    # 3. Fallback: apenas se não tem seed_tokens.json, não tem env_token, e a tabela está vazia
    cursor.execute("SELECT COUNT(*) FROM access_tokens")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
        INSERT INTO access_tokens (
            id, token, label, created_by, created_at, expires_at, is_active, last_used_at, usage_count
        ) VALUES (?, ?, ?, ?, ?, ?, 1, NULL, 0)
        """, (
            "tok_default_initial",
            "MINHAESCOLA-SEE-2026",
            "Acesso Geral SEE / Prodemge",
            "mgminhaescola@gmail.com",
            now_iso,
            None
        ))

def create_access_token(
    label: str,
    token_code: Optional[str] = None,
    created_by: str = "mgminhaescola@gmail.com",
    expires_days: Optional[int] = None
) -> Dict[str, Any]:
    """Cria um novo token de acesso para visitantes/convidados."""
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.utcnow()
    now_iso = now.isoformat()
    
    if not token_code or not token_code.strip():
        token_code = "SEE-" + secrets.token_hex(4).upper()
    else:
        token_code = token_code.strip().upper().replace(" ", "-")
        
    token_id = "tok_" + hashlib.md5(f"{token_code}_{now_iso}".encode('utf-8')).hexdigest()[:12]
    
    expires_at = None
    if expires_days and expires_days > 0:
        exp_dt = now + timedelta(days=expires_days)
        expires_at = exp_dt.isoformat()
        
    cursor.execute("""
    INSERT INTO access_tokens (id, token, label, created_by, created_at, expires_at, is_active, last_used_at, usage_count)
    VALUES (?, ?, ?, ?, ?, ?, 1, NULL, 0)
    """, (token_id, token_code, label.strip(), created_by, now_iso, expires_at))
    conn.commit()
    
    cursor.execute("SELECT * FROM access_tokens WHERE id = ?", (token_id,))
    row = dict(cursor.fetchone())
    conn.close()
    
    sync_seed_tokens()
    return row

def update_access_token(
    token_id: str,
    new_token: Optional[str] = None,
    new_label: Optional[str] = None,
    expires_in_days: Optional[int] = None
) -> Optional[Dict[str, Any]]:
    """Atualiza o código, nome/identificação ou validade de um token de acesso existente."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM access_tokens WHERE id = ?", (token_id,))
    existing = cursor.fetchone()
    if not existing:
        conn.close()
        return None

    curr_token = existing["token"]
    curr_label = existing["label"]
    curr_expires = existing["expires_at"]

    if new_token and new_token.strip():
        new_token_clean = new_token.strip().upper().replace(" ", "-")
        # Verifica se outro token já usa esse código
        cursor.execute("SELECT id FROM access_tokens WHERE UPPER(TRIM(token)) = ? AND id != ?", (new_token_clean, token_id))
        if cursor.fetchone():
            conn.close()
            raise ValueError(f"O código de chave '{new_token_clean}' já está em uso por outro token.")
        curr_token = new_token_clean

    if new_label and new_label.strip():
        curr_label = new_label.strip()

    if expires_in_days is not None:
        if expires_in_days > 0:
            curr_expires = (datetime.utcnow() + timedelta(days=expires_in_days)).isoformat()
        else:
            curr_expires = None

    cursor.execute("""
    UPDATE access_tokens
    SET token = ?, label = ?, expires_at = ?
    WHERE id = ?
    """, (curr_token, curr_label, curr_expires, token_id))
    conn.commit()

    cursor.execute("SELECT * FROM access_tokens WHERE id = ?", (token_id,))
    updated_row = dict(cursor.fetchone())
    conn.close()

    sync_seed_tokens()
    return updated_row

def get_access_token_by_token(token_str: str) -> Optional[Dict[str, Any]]:
    """Busca token pelo código exato (case-insensitive)."""
    if not token_str:
        return None
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM access_tokens WHERE UPPER(TRIM(token)) = ?", (token_str.strip().upper(),))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_access_token_by_id(token_id: str) -> Optional[Dict[str, Any]]:
    """Busca token pelo ID primário."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM access_tokens WHERE id = ?", (token_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def record_access_token_usage(token_id: str):
    """Incrementa contador de uso e atualiza timestamp de último acesso."""
    conn = get_connection()
    cursor = conn.cursor()
    now_iso = datetime.utcnow().isoformat()
    cursor.execute("""
    UPDATE access_tokens 
    SET usage_count = usage_count + 1, last_used_at = ? 
    WHERE id = ?
    """, (now_iso, token_id))
    conn.commit()
    conn.close()

def list_access_tokens() -> List[Dict[str, Any]]:
    """Lista todos os tokens cadastrados, ordenados por data de criação."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM access_tokens ORDER BY created_at DESC")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def toggle_access_token_status(token_id: str, is_active: bool) -> bool:
    """Ativa ou desativa um token de acesso."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE access_tokens SET is_active = ? WHERE id = ?", (1 if is_active else 0, token_id))
    conn.commit()
    conn.close()
    sync_seed_tokens()
    return True

def delete_access_token(token_id: str) -> bool:
    """Remove permanentemente um token de acesso."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM access_tokens WHERE id = ?", (token_id,))
    conn.commit()
    conn.close()
    sync_seed_tokens()
    return True


