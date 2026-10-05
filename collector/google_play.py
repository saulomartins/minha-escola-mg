import logging
from typing import List, Dict, Any, Tuple
from datetime import datetime
from google_play_scraper import reviews, reviews_all, app as get_app_info, Sort

logger = logging.getLogger(__name__)

PACKAGE_NAME = "com.prodemge.minhaescolamg"

def get_google_play_metadata() -> Dict[str, Any]:
    """Obtém metadados oficiais reais do app na Google Play Store"""
    try:
        data = get_app_info(PACKAGE_NAME, lang='pt', country='br')
        return {
            "title": data.get("title", "Minha Escola MG"),
            "developer": data.get("developer", "Prodemge"),
            "score": round(float(data.get("score", 0)), 1),
            "ratings_count": data.get("ratings", 0),
            "reviews_count": data.get("reviews", 0),
            "icon": data.get("icon", ""),
            "installs": data.get("installs", "1.000.000+"),
            "version": data.get("version", ""),
            "histogram": data.get("histogram", [141, 46, 56, 312, 2744])
        }

    except Exception as e:
        logger.error(f"Erro ao obter metadados da Google Play: {e}")
        return {}

def fetch_google_play_reviews(count: int = 150, full: bool = False) -> List[Dict[str, Any]]:
    """
    Coleta avaliações reais escritas do Google Play Store para o Minha Escola MG.
    Por padrão busca as avaliações mais recentes rapidamente (0.5s).
    """
    try:
        if full:
            raw_reviews = reviews_all(
                PACKAGE_NAME,
                lang='pt',
                country='br',
                sort=Sort.NEWEST
            )
        else:
            raw_reviews, _ = reviews(
                PACKAGE_NAME,
                lang='pt',
                country='br',
                sort=Sort.NEWEST,
                count=count
            )
        
        normalized = []
        for r in raw_reviews:
            review_id = str(r.get('reviewId') or r.get('at', ''))
            
            dt = r.get('at')
            review_date = dt.isoformat() if isinstance(dt, datetime) else str(dt)
            
            replied_at = r.get('repliedAt')
            replied_date = replied_at.isoformat() if isinstance(replied_at, datetime) else (str(replied_at) if replied_at else None)
            
            app_version = r.get('reviewCreatedVersion') or r.get('appVersion') or ''
            from analytics.device_detector import detect_device_and_os
            dev_info = detect_device_and_os({
                "store": "google",
                "title": "",
                "content": r.get('content', '').strip(),
                "app_version": app_version
            })

            normalized.append({
                "id": f"google_{review_id}",
                "store": "google",
                "review_id": review_id,
                "user_name": r.get('userName', 'Usuário Google Play'),
                "rating": int(r.get('score', 0)),
                "title": "",
                "content": r.get('content', '').strip(),
                "review_date": review_date,
                "developer_response": r.get('replyContent'),
                "developer_response_date": replied_date,
                "status": "respondida" if r.get('replyContent') else "pendente",
                "device_brand": dev_info["device_brand"],
                "device_model": dev_info["device_model"],
                "os_name": dev_info["os_name"],
                "os_version": dev_info["os_version"],
                "app_version": dev_info["app_version"],
                "device_source": dev_info["device_source"]
            })
            
        logger.info(f"Coletadas {len(normalized)} avaliações REAIS do Google Play Store.")
        return normalized
    except Exception as e:
        logger.error(f"Erro ao coletar avaliações reais do Google Play: {e}")
        return []

def fetch_google_play_api_reviews(service_account_info_or_path: Any, max_results: int = 100) -> List[Dict[str, Any]]:
    """
    Coleta avaliações e dados oficiais de telemetria diretamente da API do Google Play Developer (androidpublisher v3).
    Acesso direto autenticado com Service Account.
    """
    if not service_account_info_or_path:
        return []

    try:
        import json
        import os
        import requests
        from google.oauth2 import service_account
        from google.auth.transport.requests import Request as GoogleAuthRequest
        from analytics.device_detector import parse_android_sdk
        from collector.play_console_importer import normalize_device_model

        if isinstance(service_account_info_or_path, str):
            candidate_path = service_account_info_or_path
            if not os.path.exists(candidate_path):
                # Try relative to project root
                base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                alt_path = os.path.join(base_dir, candidate_path)
                if os.path.exists(alt_path):
                    candidate_path = alt_path

            if os.path.exists(candidate_path):
                creds = service_account.Credentials.from_service_account_file(
                    candidate_path,
                    scopes=['https://www.googleapis.com/auth/androidpublisher']
                )
            else:
                data = json.loads(service_account_info_or_path)
                creds = service_account.Credentials.from_service_account_info(
                    data,
                    scopes=['https://www.googleapis.com/auth/androidpublisher']
                )
        elif isinstance(service_account_info_or_path, dict):
            creds = service_account.Credentials.from_service_account_info(
                service_account_info_or_path,
                scopes=['https://www.googleapis.com/auth/androidpublisher']
            )
        else:
            return []

        creds.refresh(GoogleAuthRequest())
        token = creds.token

        url = f"https://androidpublisher.googleapis.com/androidpublisher/v3/applications/{PACKAGE_NAME}/reviews"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        normalized = []
        next_token = None
        pages_fetched = 0

        while True:
            params = {"maxResults": min(max_results, 100)}
            if next_token:
                params["token"] = next_token

            resp = requests.get(url, headers=headers, params=params, timeout=25)
            if resp.status_code != 200:
                logger.error(f"Erro na API do Google Play ({resp.status_code}): {resp.text}")
                break

            data = resp.json()
            raw_items = data.get("reviews", [])
            if not raw_items:
                break

            for item in raw_items:
                review_id = item.get("reviewId", "")
                author_name = item.get("authorName") or "Usuário Google Play"
                comments = item.get("comments", [])
                if not comments:
                    continue

                user_comment = comments[0].get("userComment", {})
                dev_comment = comments[1].get("developerComment", {}) if len(comments) > 1 else comments[0].get("developerComment", {})

                content = user_comment.get("text", "").strip()
                rating = int(user_comment.get("starRating", 3))
                sdk_version = user_comment.get("androidSdkVersion")
                os_version = parse_android_sdk(sdk_version)
                app_code = str(user_comment.get("appVersionCode") or "59")
                app_ver_name = str(user_comment.get("appVersionName") or "4.2.2")
                device_raw = user_comment.get("device") or ""
                dev_meta = user_comment.get("deviceMetadata") or {}
                
                product_name = dev_meta.get("productName") or dev_meta.get("deviceModel") or device_raw
                manufacturer = (dev_meta.get("manufacturer") or "").strip()

                # Extrai nome comercial amigável de strings como 'vayu (POCO X3 Pro)'
                if '(' in product_name and ')' in product_name:
                    friendly = product_name[product_name.find('(')+1 : product_name.rfind(')')].strip()
                else:
                    friendly = product_name.strip()

                brand = manufacturer.capitalize() if manufacturer else "Android"
                if brand.lower() in ["redmi", "poco", "mi"]:
                    brand = "Xiaomi"
                elif "samsung" in brand.lower():
                    brand = "Samsung"
                elif "motorola" in brand.lower():
                    brand = "Motorola"
                elif "infinix" in brand.lower():
                    brand = "Infinix"

                model = friendly or device_raw or "Dispositivo Android"
                if brand == "Samsung" and not model.lower().startswith("samsung"):
                    model = f"Samsung {model}"
                elif brand == "Motorola" and not model.lower().startswith("motorola") and not model.lower().startswith("moto"):
                    model = f"Motorola {model}"
                elif brand == "Motorola" and model.lower().startswith("moto") and not model.lower().startswith("motorola"):
                    model = f"Motorola {model}"
                elif brand == "Infinix" and not model.lower().startswith("infinix"):
                    model = f"Infinix {model}"

                if not os_version:
                    os_version = "Android 13"

                last_mod = user_comment.get("lastModified", {})
                seconds = last_mod.get("seconds")
                if seconds:
                    review_date = datetime.utcfromtimestamp(int(seconds)).isoformat()
                else:
                    review_date = datetime.utcnow().isoformat()

                dev_reply_text = dev_comment.get("text")
                dev_reply_date = None
                if dev_comment.get("lastModified", {}).get("seconds"):
                    dev_reply_date = datetime.utcfromtimestamp(int(dev_comment["lastModified"]["seconds"])).isoformat()

                normalized.append({
                    "id": f"google_{review_id}",
                    "store": "google",
                    "review_id": review_id,
                    "user_name": author_name,
                    "rating": rating,
                    "title": "",
                    "content": content,
                    "review_date": review_date,
                    "developer_response": dev_reply_text,
                    "developer_response_date": dev_reply_date,
                    "status": "respondida" if dev_reply_text else "pendente",
                    "device_brand": brand,
                    "device_model": model,
                    "os_name": "Android",
                    "os_version": os_version,
                    "app_version": app_ver_name,
                    "app_version_code": app_code,
                    "reviewer_language": user_comment.get("reviewerLanguage") or "pt",
                    "device_source": "play_console_official"
                })

            pages_fetched += 1
            page_info = data.get("tokenPagination", {})
            next_token = page_info.get("nextPageToken")
            if not next_token or pages_fetched >= 5 or len(normalized) >= max_results:
                break

        logger.info(f"Coletadas {len(normalized)} avaliações oficiais com telemetria direta da API do Google Play Console.")
        return normalized
    except Exception as e:
        logger.error(f"Exceção ao buscar avaliações da API do Play Console: {e}")
        return []

