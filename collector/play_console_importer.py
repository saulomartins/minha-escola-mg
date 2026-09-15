import os
import csv
import io
import re
import logging
from typing import Dict, Any, List, Tuple
from datetime import datetime

from database.db import get_connection, upsert_review
from analytics.device_detector import detect_device_and_os
from analytics.device_lifecycle import evaluate_stuck_android_12

logger = logging.getLogger("importer")

def detect_encoding_and_delimiter(file_bytes: bytes) -> Tuple[str, str]:
    """Detecta automaticamente codificacao e delimitador"""
    encodings = ['utf-16', 'utf-16-le', 'utf-8-sig', 'utf-8', 'latin-1', 'cp1252']
    delimiters = [',', ';', '\t']
    
    for enc in encodings:
        try:
            sample_text = file_bytes[:4096].decode(enc)
            for delim in delimiters:
                if delim in sample_text:
                    lines = sample_text.split('\n')
                    if len(lines) > 1 and len(lines[0].split(delim)) >= 3:
                        return enc, delim
        except Exception:
            continue
            
    return 'utf-8', ','

def normalize_device_model(device_raw: str) -> Tuple[str, str]:
    """Normaliza codigo ou nome de dispositivo do Google Play para Marca e Modelo amigavel"""
    if not device_raw or device_raw.strip() == "":
        return "Android", "Dispositivo Android"
        
    device_raw = device_raw.strip()
    lower = device_raw.lower()
    
    if "redmi" in lower or "xiaomi" in lower or "poco" in lower:
        brand = "Xiaomi"
        model = device_raw
    elif "moto" in lower or "motorola" in lower:
        brand = "Motorola"
        model = device_raw
    elif "samsung" in lower or "galaxy" in lower or lower.startswith("sm-"):
        brand = "Samsung"
        model = device_raw
    elif "lg" in lower:
        brand = "LG"
        model = device_raw
    elif "apple" in lower or "iphone" in lower:
        brand = "Apple"
        model = device_raw
    elif "realme" in lower:
        brand = "Realme"
        model = device_raw
    elif "infinix" in lower:
        brand = "Infinix"
        model = device_raw
    elif "asus" in lower or "zenfone" in lower:
        brand = "Asus"
        model = device_raw
    else:
        parts = device_raw.split()
        if len(parts) > 1:
            brand = parts[0].capitalize()
            model = " ".join(parts[1:])
        else:
            brand = "Android"
            model = device_raw
            
    return brand, model

def import_play_console_csv(file_content_or_bytes) -> Dict[str, Any]:
    """
    Processa e importa o relatorio oficial de avaliacoes exportado do Google Play Console.
    Atualiza 100% dos comentarios correspondentes com os dados de telemetria oficial.
    """
    if isinstance(file_content_or_bytes, str):
        file_bytes = file_content_or_bytes.encode('utf-8')
    else:
        file_bytes = file_content_or_bytes

    encoding, delimiter = detect_encoding_and_delimiter(file_bytes)
    text = file_bytes.decode(encoding, errors='replace')
    
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    headers = None
    col_map = {}
    
    updated_count = 0
    new_count = 0
    total_processed = 0
    
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, review_id, content, user_name FROM reviews WHERE store = 'google'")
    existing_db = cursor.fetchall()
    
    by_review_id = {}
    by_content_prefix = {}
    
    for row in existing_db:
        r_id = row['review_id']
        by_review_id[r_id] = row['id']
        content_clean = re.sub(r'\s+', ' ', (row['content'] or '')).strip().lower()[:40]
        if content_clean:
            by_content_prefix[content_clean] = row['id']

    for row_idx, row in enumerate(reader):
        if not row:
            continue
            
        if headers is None:
            headers = [h.strip().lower() for h in row]
            for idx, h in enumerate(headers):
                if 'review id' in h or 'id da avalia' in h or h == 'id' or 'review_id' in h:
                    col_map['review_id'] = idx
                elif 'device' in h or 'dispositivo' in h or 'aparelho' in h:
                    col_map['device'] = idx
                elif 'android os version' in h or 'vers' in h and 'so' in h or 'vers' in h and 'android' in h or 'os version' in h:
                    col_map['os_version'] = idx
                elif 'app version code' in h or 'c' in h and 'digo' in h and 'vers' in h:
                    col_map['app_version_code'] = idx
                elif 'app version name' in h or 'nome da vers' in h or 'app version' in h:
                    col_map['app_version'] = idx
                elif 'reviewer language' in h or 'idioma' in h:
                    col_map['language'] = idx
                elif 'star rating' in h or 'classifica' in h or 'nota' in h or 'stars' in h:
                    col_map['rating'] = idx
                elif 'review text' in h or 'texto da avalia' in h or 'coment' in h or 'content' in h:
                    col_map['content'] = idx
                elif 'review submit date' in h or 'data e hora do envio' in h or 'data' in h:
                    col_map['review_date'] = idx
                elif 'user name' in h or 'nome do usu' in h or 'usu' in h:
                    col_map['user_name'] = idx
            continue
            
        total_processed += 1
        
        def get_val(key):
            idx = col_map.get(key)
            if idx is not None and idx < len(row):
                return row[idx].strip()
            return ""
            
        raw_review_id = get_val('review_id')
        raw_device = get_val('device')
        raw_os_version = get_val('os_version')
        raw_app_code = get_val('app_version_code')
        raw_app_version = get_val('app_version')
        raw_lang = get_val('language')
        raw_content = get_val('content')
        raw_rating = get_val('rating')
        raw_user = get_val('user_name') or "Usuario"
        raw_date = get_val('review_date')
        
        brand, model = normalize_device_model(raw_device)
        
        os_name = "Android"
        if raw_os_version and not raw_os_version.lower().startswith("android"):
            os_version = f"Android {raw_os_version}"
        else:
            os_version = raw_os_version or "Android"

        target_db_id = None
        if raw_review_id and raw_review_id in by_review_id:
            target_db_id = by_review_id[raw_review_id]
        elif f"google_{raw_review_id}" in by_review_id:
            target_db_id = by_review_id[f"google_{raw_review_id}"]
        else:
            content_clean = re.sub(r'\s+', ' ', raw_content).strip().lower()[:40]
            if content_clean and content_clean in by_content_prefix:
                target_db_id = by_content_prefix[content_clean]

        now_iso = datetime.utcnow().isoformat()
        
        if target_db_id:
            cursor.execute("""
                UPDATE reviews SET
                    device_brand = ?,
                    device_model = ?,
                    os_name = ?,
                    os_version = ?,
                    app_version = CASE WHEN ? != '' THEN ? ELSE app_version END,
                    app_version_code = CASE WHEN ? != '' THEN ? ELSE app_version_code END,
                    reviewer_language = CASE WHEN ? != '' THEN ? ELSE reviewer_language END,
                    device_source = 'play_console_official',
                    updated_at = ?
                WHERE id = ?
            """, (
                brand, model, os_name, os_version,
                raw_app_version, raw_app_version,
                raw_app_code, raw_app_code,
                raw_lang, raw_lang,
                now_iso, target_db_id
            ))
            updated_count += 1
        else:
            if raw_content:
                try:
                    rating_int = int(re.search(r'\d+', raw_rating).group(0)) if raw_rating else 3
                except Exception:
                    rating_int = 3
                    
                new_id = f"google_{raw_review_id}" if raw_review_id else f"google_import_{row_idx}"
                
                cursor.execute("""
                    INSERT OR REPLACE INTO reviews (
                        id, store, review_id, user_name, rating, content, review_date,
                        device_brand, device_model, os_name, os_version,
                        app_version, app_version_code, reviewer_language, device_source,
                        status, created_at, updated_at
                    ) VALUES (?, 'google', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'play_console_official', 'pendente', ?, ?)
                """, (
                    new_id, raw_review_id or new_id, raw_user, rating_int, raw_content,
                    raw_date or now_iso, brand, model, os_name, os_version,
                    raw_app_version, raw_app_code, raw_lang,
                    now_iso, now_iso
                ))
                new_count += 1
                if raw_review_id:
                    by_review_id[raw_review_id] = new_id

    conn.commit()
    conn.close()
    
    return {
        "success": True,
        "total_in_file": total_processed,
        "updated_reviews": updated_count,
        "new_reviews": new_count,
        "message": f"Sucesso! {updated_count} comentarios foram atualizados com a telemetria oficial (Aparelhos, SO e Versao). {new_count} novos inseridos."
    }
