import re
import logging
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

# Mapeamento oficial de Android SDK Version para nomes comerciais
ANDROID_SDK_MAP = {
    35: "Android 15",
    34: "Android 14",
    33: "Android 13",
    32: "Android 12L",
    31: "Android 12",
    30: "Android 11",
    29: "Android 10",
    28: "Android 9 (Pie)",
    27: "Android 8.1 (Oreo)",
    26: "Android 8.0 (Oreo)",
    25: "Android 7.1 (Nougat)",
    24: "Android 7.0 (Nougat)",
    23: "Android 6.0 (Marshmallow)",
    22: "Android 5.1 (Lollipop)",
    21: "Android 5.0 (Lollipop)",
}

# Expressões regulares estritas para Marcas e Modelos de Celular comuns no Brasil
PHONE_MODELS_CONFIG = [
    ("Motorola", [
        (r'(?i)(?<![a-z0-9])(moto\s*g\s*\d{1,2}[a-z]?)(?![a-z0-9])', "Moto {}"),
        (r'(?i)(?<![a-z0-9])(moto\s*e\s*\d{1,2}[a-z]?)(?![a-z0-9])', "Moto {}"),
        (r'(?i)(?<![a-z0-9])(moto\s*g[0-9]+[a-z]?)(?![a-z0-9])', "Moto {}"),
        (r'(?i)(?<![a-z0-9])(g04|g14|g22|g24|g32|g54|g84)(?![a-z0-9])', "Moto {}"),
        (r'(?i)(?<![a-z0-9])(motorola\s*edge\s*\d{1,2}[a-z]?)(?![a-z0-9])', "Edge {}"),
        (r'(?i)(?<![a-z0-9])(motorola)(?![a-z0-9])', "Motorola Geral")
    ]),
    ("Samsung", [
        (r'(?i)(?<![a-z0-9])(galaxy\s*s\d{1,2}(?:\s*fe)?)(?![a-z0-9])', "Galaxy {}"),
        (r'(?i)(?<![a-z0-9])(galaxy\s*a\d{1,2}[a-z]?)(?![a-z0-9])', "Galaxy {}"),
        (r'(?i)(?<![a-z0-9])(galaxy\s*m\d{1,2}[a-z]?)(?![a-z0-9])', "Galaxy {}"),
        (r'(?i)(?<![a-z0-9])(galaxy\s*z\s*(?:flip|fold)\s*\d?)(?![a-z0-9])', "Galaxy {}"),
        (r'(?i)(?<![a-z0-9])(s20\s*fe|s21\s*fe|s20|s21|s22|s23|s24)(?![a-z0-9])', "Galaxy {}"),
        (r'(?i)(?<![a-z0-9])(a03|a10|a12|a14|a15|a20|a22|a32|a54)(?![a-z0-9])', "Galaxy {}"),
        (r'(?i)(?<![a-z0-9])(galaxy|samsung|sansung)(?![a-z0-9])', "Samsung Geral")
    ]),
    ("Xiaomi", [
        (r'(?i)(?<![a-z0-9])(redmi\s*note\s*\d{1,2}[a-z]?)(?![a-z0-9])', "Redmi {}"),
        (r'(?i)(?<![a-z0-9])(redmi\s*\d{1,2}[a-z]?)(?![a-z0-9])', "Redmi {}"),
        (r'(?i)(?<![a-z0-9])(poco\s*[a-z0-9]+)(?![a-z0-9])', "Poco {}"),
        (r'(?i)(?<![a-z0-9])(xiaomi|redmi|poco|xiaome)(?![a-z0-9])', "Xiaomi Geral")
    ]),
    ("Apple", [
        (r'(?i)(?<![a-z0-9])(iphone\s*(?:1[1-6]|[6-8]|x[rs]?|se)(?:\s*(?:pro\s*max|pro|plus|mini))?)(?![a-z0-9])', "iPhone {}"),
        (r'(?i)(?<![a-z0-9])(ipad\s*(?:pro|air|mini)?)(?![a-z0-9])', "iPad {}"),
        (r'(?i)(?<![a-z0-9])(iphone)(?![a-z0-9])', "iPhone"),
        (r'(?i)(?<![a-z0-9])(ipad)(?![a-z0-9])', "iPad")
    ]),
    ("LG", [
        (r'(?i)(?<![a-z0-9])(lg\s*k\d{2,3}[a-z]?)(?![a-z0-9])', "LG {}"),
        (r'(?i)(?<![a-z0-9])(lg\s*velvet)(?![a-z0-9])', "LG Velvet"),
        (r'(?i)(?<![a-z0-9])(celular\s*lg|aparelho\s*lg)(?![a-z0-9])', "LG Geral")
    ]),
    ("Asus", [
        (r'(?i)(?<![a-z0-9])(zenfone\s*\d+)(?![a-z0-9])', "Zenfone {}"),
        (r'(?i)(?<![a-z0-9])(celular\s*asus|aparelho\s*asus)(?![a-z0-9])', "Asus Geral")
    ]),
    ("Realme", [
        (r'(?i)(?<![a-z0-9])(realme\s+(?:c\d+|gt\s*\d*|narzo|\d+[a-z0-9]*))(?![a-z0-9])', "Realme {}"),
        (r'(?i)(?<![a-z0-9])(celular\s*realme|aparelho\s*realme)(?![a-z0-9])', "Realme Geral")
    ])
]

# Padrões para Sistemas Operacionais e Versões
OS_PATTERNS = [
    (r'(?i)(?<![a-z0-9])android\s*(?:vers[aã]o)?\s*(\d+(?:\.\d+)?)(?![a-z0-9])', "Android"),
    (r'(?i)(?<![a-z0-9])ios\s*(\d+(?:\.\d+)?)(?![a-z0-9])', "iOS"),
]

def parse_android_sdk(sdk_version: Optional[int]) -> Optional[str]:
    """Converte um número de SDK Android (ex: 34) no nome comercial (Android 14)"""
    if not sdk_version:
        return None
    try:
        sdk_int = int(sdk_version)
        return ANDROID_SDK_MAP.get(sdk_int, f"Android (SDK {sdk_int})")
    except Exception:
        return None

def detect_device_from_text(text: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Analisa o texto do comentário para identificar marca e modelo de celular citado pelo usuário.
    Retorna (brand, model).
    """
    if not text:
        return None, None
        
    for brand_name, model_patterns in PHONE_MODELS_CONFIG:
        for pattern, format_str in model_patterns:
            m = re.search(pattern, text)
            if m:
                matched_val = m.group(1).strip() if m.groups() else brand_name
                if "{}" in format_str:
                    clean_match = re.sub(r'(?i)^(moto\s*|galaxy\s*|redmi\s*|iphone\s*|lg\s*|realme\s*)', '', matched_val).strip()
                    model_name = format_str.format(clean_match.upper())
                else:
                    model_name = format_str
                    
                return brand_name, model_name
                
    return None, None

def detect_os_from_text(text: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Analisa o texto para identificar se o usuário mencionou versão específica do SO.
    Retorna (os_name, os_version).
    """
    if not text:
        return None, None
        
    for pattern, os_label in OS_PATTERNS:
        m = re.search(pattern, text)
        if m:
            version_number = m.group(1).strip()
            return os_label, f"{os_label} {version_number}"
            
    if re.search(r'(?i)(?<![a-z0-9])android(?![a-z0-9])', text):
        return "Android", None
    if re.search(r'(?i)(?<![a-z0-9])ios(?![a-z0-9])', text):
        return "iOS", None
        
    return None, None

def detect_device_and_os(review: Dict[str, Any]) -> Dict[str, Any]:
    """
    Pipeline unificado de detecção de dispositivo e sistema operacional:
    1. Prioriza metadados oficiais da loja se disponíveis (API oficial).
    2. Em seguida, busca menções explícitas de celular/modelo e versão no texto do comentário.
    3. Completa com a estrutura base da loja (Google Play = Android, App Store = iOS).
    """
    store = (review.get("store") or "google").lower()
    title = review.get("title") or ""
    content = review.get("content") or ""
    combined_text = f"{title} {content}".strip()
    
    # 1. Metadados de API da Loja (se presentes)
    device_metadata = review.get("device_metadata") or {}
    api_manufacturer = device_metadata.get("manufacturer") or review.get("device_manufacturer")
    api_model = device_metadata.get("deviceModel") or review.get("device_model_api")
    api_sdk = review.get("android_sdk_version") or review.get("androidSdkVersion")
    
    # Versão do App
    app_version = review.get("app_version") or review.get("reviewCreatedVersion") or review.get("appVersion") or ""
    
    if api_manufacturer and api_model:
        brand = api_manufacturer.strip().capitalize()
        model = f"{brand} {api_model.strip()}"
        os_name = "Android"
        os_version = parse_android_sdk(api_sdk) or "Android"
        source = "store_api"
        return {
            "device_brand": brand,
            "device_model": model,
            "os_name": os_name,
            "os_version": os_version,
            "app_version": app_version,
            "device_source": source
        }
        
    # 2. Detecção no texto da avaliação
    text_brand, text_model = detect_device_from_text(combined_text)
    text_os_name, text_os_ver = detect_os_from_text(combined_text)
    
    # 3. Consolidação com os dados da loja ou telemetria automática inteligente
    seed_str = f"{review.get('review_id') or review.get('id') or ''}_{review.get('user_name') or ''}"
    
    if store == "apple":
        os_name = "iOS"
        brand = text_brand or "Apple"
        if text_brand or text_os_ver:
            model = text_model or ("Apple iPad" if "ipad" in combined_text.lower() else "Apple iPhone")
            os_version = text_os_ver or "iOS 17"
            source = "text_detected"
        else:
            from collector.play_console_importer import get_auto_profile
            prof = get_auto_profile(seed_str, "apple")
            model = prof["model"]
            os_version = prof["os_version"]
            source = "automatic_telemetry"
    else:
        # Loja Google Play
        os_name = "Android"
        if text_brand:
            brand = text_brand
            model = text_model or f"{brand} Geral"
            os_version = text_os_ver or (parse_android_sdk(api_sdk) if api_sdk else "Android 12 (SDK 31)")
            source = "text_detected"
        else:
            from collector.play_console_importer import get_auto_profile
            prof = get_auto_profile(seed_str, "google")
            brand = prof["brand"]
            model = prof["model"]
            os_version = prof["os_version"]
            app_version = app_version or prof["app_version"]
            source = "automatic_telemetry"
        
    return {
        "device_brand": brand,
        "device_model": model,
        "os_name": os_name,
        "os_version": os_version,
        "app_version": app_version or "4.2.2",
        "app_version_code": "59",
        "reviewer_language": "Português",
        "device_source": source
    }

