import logging
import requests
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

APP_ID = "6749247611"
COUNTRY = "br"

def get_apple_store_metadata() -> Dict[str, Any]:
    """Obtém metadados oficiais reais do app na Apple App Store"""
    try:
        url = f"https://itunes.apple.com/{COUNTRY}/lookup?id={APP_ID}"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            results = data.get("results", [])
            if results:
                item = results[0]
                return {
                    "title": item.get("trackName", "Minha Escola MG"),
                    "seller": item.get("sellerName", "Prodemge"),
                    "score": round(float(item.get("averageUserRating", 0)), 1),
                    "ratings_count": item.get("userRatingCount", 0),
                    "icon": item.get("artworkUrl512", item.get("artworkUrl100", "")),
                    "version": item.get("version", "")
                }
    except Exception as e:
        logger.error(f"Erro ao obter metadados da Apple Store: {e}")
    return {}

def fetch_apple_store_reviews(max_pages: int = 10) -> List[Dict[str, Any]]:
    """
    Coleta todas as avaliações reais escritas da Apple App Store para o app Minha Escola MG
    utilizando a API oficial de RSS da Apple.
    """
    reviews_list = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    for page in range(1, max_pages + 1):
        url = f"https://itunes.apple.com/{COUNTRY}/rss/customerreviews/page={page}/id={APP_ID}/sortBy=mostRecent/json"
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            if resp.status_code != 200:
                break
                
            data = resp.json()
            entries = data.get("feed", {}).get("entry", [])
            
            if not entries:
                break
                
            for entry in entries:
                if "im:rating" not in entry:
                    continue
                    
                review_id = str(entry.get("id", {}).get("label", ""))
                if not review_id:
                    continue
                    
                author = entry.get("author", {}).get("name", {}).get("label", "Usuário Apple")
                rating = int(entry.get("im:rating", {}).get("label", 0))
                title = entry.get("title", {}).get("label", "").strip()
                content = entry.get("content", {}).get("label", "").strip()
                updated = entry.get("updated", {}).get("label", "")
                
                full_content = f"{title} - {content}" if title and title not in content else content
                app_version = entry.get("im:version", {}).get("label", "")
                
                from analytics.device_detector import detect_device_and_os
                dev_info = detect_device_and_os({
                    "store": "apple",
                    "title": title,
                    "content": full_content,
                    "app_version": app_version
                })

                reviews_list.append({
                    "id": f"apple_{review_id}",
                    "store": "apple",
                    "review_id": review_id,
                    "user_name": author,
                    "rating": rating,
                    "title": title,
                    "content": full_content,
                    "review_date": updated,
                    "developer_response": None,
                    "developer_response_date": None,
                    "status": "pendente",
                    "device_brand": dev_info["device_brand"],
                    "device_model": dev_info["device_model"],
                    "os_name": dev_info["os_name"],
                    "os_version": dev_info["os_version"],
                    "app_version": dev_info["app_version"],
                    "device_source": dev_info["device_source"]
                })
                
        except Exception as e:
            logger.error(f"Erro ao buscar página {page} da Apple App Store: {e}")
            break

    logger.info(f"Coletadas {len(reviews_list)} avaliações REAIS da Apple App Store.")
    return reviews_list
