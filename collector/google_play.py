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
            "version": data.get("version", "")
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
