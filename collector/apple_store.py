import logging
import requests
import re
import json
from typing import List, Dict, Any, Optional
from config import get_apple_store_id, get_apple_store_country, get_app_name, get_organization_name

logger = logging.getLogger(__name__)

def get_current_app_id() -> str:
    return get_apple_store_id()

def get_current_country() -> str:
    return get_apple_store_country()

APP_ID = get_current_app_id()
COUNTRY = get_current_country()

def get_apple_store_metadata(app_id: Optional[str] = None, country: Optional[str] = None) -> Dict[str, Any]:
    """Obtém metadados oficiais reais do app na Apple App Store"""
    a_id = app_id or get_current_app_id()
    c = country or get_current_country()
    try:
        url = f"https://itunes.apple.com/{c}/lookup?id={a_id}"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            results = data.get("results", [])
            if results:
                item = results[0]
                return {
                    "title": item.get("trackName", get_app_name()),
                    "seller": item.get("sellerName", get_organization_name()),
                    "score": round(float(item.get("averageUserRating", 0)), 1),
                    "ratings_count": item.get("userRatingCount", 0),
                    "icon": item.get("artworkUrl512", item.get("artworkUrl100", "")),
                    "version": item.get("version", "")
                }
    except Exception as e:
        logger.error(f"Erro ao obter metadados da Apple Store: {e}")
    return {}

def fetch_apple_web_responses(app_id: Optional[str] = None, country: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
    """
    Coleta as respostas oficiais do desenvolvedor publicadas na Apple App Store.
    A API RSS pública da Apple não inclui respostas, portanto esta função varre as páginas
    oficiais da loja extraindo os dados serializados do app.
    """
    a_id = app_id or get_current_app_id()
    c = country or get_current_country()
    responses_map: Dict[str, Dict[str, Any]] = {}
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    sorts = ["mostRecent", "mostHelpful", "highestRatings", "lowestRatings"]
    urls = [
        f"https://apps.apple.com/{c}/app/app/id{a_id}?see-all=reviews",
        f"https://apps.apple.com/{c}/app/app/id{a_id}"
    ] + [f"https://apps.apple.com/{c}/app/app/id{a_id}?see-all=reviews&sort={s}" for s in sorts]

    def extract_from_json(obj):
        if isinstance(obj, dict):
            rev_id = (
                obj.get("moreAction", {}).get("pageData", {}).get("targetReviewId")
                or obj.get("targetReviewId")
                or obj.get("id")
            )
            resp = obj.get("response")
            if rev_id and resp and isinstance(resp, dict) and "contents" in resp:
                clean_id = str(rev_id).strip()
                responses_map[clean_id] = {
                    "response": resp.get("contents", "").strip(),
                    "date": resp.get("date", ""),
                    "author": obj.get("reviewerName", ""),
                    "rating": obj.get("rating", 0),
                    "title": obj.get("title", ""),
                    "content": obj.get("userReview", "") or obj.get("content", "")
                }
            for v in obj.values():
                extract_from_json(v)
        elif isinstance(obj, list):
            for it in obj:
                extract_from_json(it)

    for url in urls:
        try:
            r = requests.get(url, headers=headers, timeout=12)
            if r.status_code != 200:
                continue
            m = re.search(r'<script[^>]*id=["\']serialized-server-data["\'][^>]*>(.*?)</script>', r.text, re.DOTALL)
            if m:
                data = json.loads(m.group(1).strip())
                extract_from_json(data)
        except Exception as e:
            logger.warning(f"Aviso ao buscar respostas na página {url}: {e}")

    logger.info(f"Coletadas {len(responses_map)} respostas oficiais de desenvolvedor da Apple Store.")
    return responses_map

def fetch_apple_store_reviews(max_pages: int = 10, app_id: Optional[str] = None, country: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Coleta todas as avaliações reais escritas da Apple App Store para o app configurado
    utilizando a API oficial de RSS da Apple e enriquece com as respostas oficiais do desenvolvedor.
    """
    a_id = app_id or get_current_app_id()
    c = country or get_current_country()

    # 1. Coleta mapa de respostas oficiais da Apple
    web_responses = fetch_apple_web_responses(app_id=a_id, country=c)

    reviews_list = []
    seen_ids = set()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    from analytics.device_detector import detect_device_and_os

    for page in range(1, max_pages + 1):
        url = f"https://itunes.apple.com/{c}/rss/customerreviews/page={page}/id={a_id}/sortBy=mostRecent/json"
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
                if not review_id or review_id in seen_ids:
                    continue
                seen_ids.add(review_id)
                    
                author = entry.get("author", {}).get("name", {}).get("label", "Usuário Apple")
                rating = int(entry.get("im:rating", {}).get("label", 0))
                title = entry.get("title", {}).get("label", "").strip()
                content = entry.get("content", {}).get("label", "").strip()
                updated = entry.get("updated", {}).get("label", "")
                
                full_content = f"{title} - {content}" if title and title not in content else content
                app_version = entry.get("im:version", {}).get("label", "")
                
                dev_info = detect_device_and_os({
                    "store": "apple",
                    "title": title,
                    "content": full_content,
                    "app_version": app_version
                })

                # Verifica se há resposta do desenvolvedor capturada
                resp_info = web_responses.get(review_id)
                dev_response = resp_info["response"] if resp_info else None
                dev_response_date = resp_info["date"] if resp_info else None
                status = "respondida" if dev_response else "pendente"
                published = 1 if dev_response else 0

                reviews_list.append({
                    "id": f"apple_{review_id}",
                    "store": "apple",
                    "review_id": review_id,
                    "user_name": author,
                    "rating": rating,
                    "title": title,
                    "content": full_content,
                    "review_date": updated,
                    "developer_response": dev_response,
                    "developer_response_date": dev_response_date,
                    "status": status,
                    "published_to_store": published,
                    "device_brand": dev_info["device_brand"],
                    "device_model": dev_info["device_model"],
                    "os_name": dev_info["os_name"],
                    "os_version": dev_info["os_version"],
                    "app_version": dev_info["app_version"],
                    "device_source": dev_info["device_source"],
                    "app_id": (lambda: (__import__('config').get_app_id()))()
                })
                
        except Exception as e:
            logger.error(f"Erro ao buscar página {page} da Apple App Store: {e}")
            break

    logger.info(f"Coletadas {len(reviews_list)} avaliações REAIS da Apple App Store ({sum(1 for r in reviews_list if r['developer_response'])} com resposta).")
    return reviews_list
