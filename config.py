import os
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app_config.json")
PRESETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "presets")

DEFAULT_CONFIG: Dict[str, Any] = {
    "app_id": "minha_escola_mg",
    "app_name": "Minha Escola MG",
    "app_short_name": "minhaescola",
    "domain": "education",
    "organization_name": "Governo de Minas Gerais / Prodemge",
    "developer_name": "Prodemge - Secretaria de Estado de Educação de MG",
    "app_tagline": "Central de Inteligência e Diagnóstico de Avaliações",
    "app_description": "Sistema de inteligência artificial para monitoramento de avaliações, diagnóstico técnico e geração de respostas automáticas.",
    "support_url": "https://forms.cloud.microsoft/r/JmZhSzXtwG",
    "support_email": "suporte@exemplo.mg.gov.br",
    "google_play": {
        "package_name": "com.prodemge.minhaescolamg",
        "country": "br",
        "language": "pt"
    },
    "apple_store": {
        "app_id": "6749247611",
        "country": "br"
    },
    "branding": {
        "primary_color": "#1e3a8a",
        "header_subtext": "SEE/MG & Prodemge",
        "badge_text": "OFICIAL"
    },
    "guest_token": "MEMG-2026",
    "features": {
        "enable_fale_conosco": True,
        "enable_hardware_matrix": True,
        "enable_ai_suggestions": True
    }
}

def load_json_file(path: str) -> Optional[Dict[str, Any]]:
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Erro ao carregar arquivo de configuração {path}: {e}")
    return None

def get_app_config() -> Dict[str, Any]:
    """
    Retorna a configuração ativa com cascata de prioridades:
    1. Defaults (Minha Escola MG)
    2. Arquivo app_config.json (se existir)
    3. Banco de dados SQLite (tabela settings, permitindo edição no painel)
    4. Variáveis de ambiente (.env / Render) - maior prioridade
    """
    config = dict(DEFAULT_CONFIG)

    # 1. Carrega do app_config.json
    file_cfg = load_json_file(CONFIG_PATH)
    if file_cfg:
        config.update(file_cfg)

    # 2. Sobrescreve com valores salvos no banco de dados SQLite (se houver)
    try:
        from database.db import get_all_settings
        db_settings = get_all_settings()
        if db_settings.get("app_id"):
            config["app_id"] = db_settings["app_id"]
        if db_settings.get("domain"):
            config["domain"] = db_settings["domain"]
        if db_settings.get("app_name"):
            config["app_name"] = db_settings["app_name"]
        if db_settings.get("organization_name"):
            config["organization_name"] = db_settings["organization_name"]
        if db_settings.get("developer_name"):
            config["developer_name"] = db_settings["developer_name"]
        if db_settings.get("support_contact_url") or db_settings.get("support_url"):
            config["support_url"] = db_settings.get("support_contact_url") or db_settings.get("support_url")
        if db_settings.get("support_email"):
            config["support_email"] = db_settings["support_email"]
        if db_settings.get("google_play_package"):
            if "google_play" not in config:
                config["google_play"] = {}
            config["google_play"]["package_name"] = db_settings["google_play_package"]
        if db_settings.get("apple_store_id"):
            if "apple_store" not in config:
                config["apple_store"] = {}
            config["apple_store"]["app_id"] = db_settings["apple_store_id"]
    except Exception:
        pass

    # 3. Variáveis de ambiente têm prioridade máxima (ideal para Docker / Render)
    env_app_id = os.getenv("APP_ID")
    if env_app_id:
        config["app_id"] = env_app_id.strip()

    env_domain = os.getenv("APP_DOMAIN")
    if env_domain:
        config["domain"] = env_domain.strip()

    env_app_name = os.getenv("APP_NAME")
    if env_app_name:
        config["app_name"] = env_app_name.strip()

    env_org = os.getenv("ORGANIZATION_NAME")
    if env_org:
        config["organization_name"] = env_org.strip()

    env_dev = os.getenv("DEVELOPER_NAME")
    if env_dev:
        config["developer_name"] = env_dev.strip()

    env_pkg = os.getenv("GOOGLE_PLAY_PACKAGE")
    if env_pkg:
        if "google_play" not in config:
            config["google_play"] = {}
        config["google_play"]["package_name"] = env_pkg.strip()

    env_apple_id = os.getenv("APPLE_STORE_ID")
    if env_apple_id:
        if "apple_store" not in config:
            config["apple_store"] = {}
        config["apple_store"]["app_id"] = env_apple_id.strip()

    env_apple_country = os.getenv("APPLE_STORE_COUNTRY")
    if env_apple_country:
        if "apple_store" not in config:
            config["apple_store"] = {}
        config["apple_store"]["country"] = env_apple_country.strip()

    env_support_url = os.getenv("SUPPORT_CHANNEL_URL") or os.getenv("SUPPORT_URL")
    if env_support_url:
        config["support_url"] = env_support_url.strip()

    env_support_email = os.getenv("SUPPORT_EMAIL")
    if env_support_email:
        config["support_email"] = env_support_email.strip()

    
    # Garantia de Coerência entre app_id, app_name e domain
    curr_id = config.get("app_id", "minha_escola_mg")
    if curr_id == "minha_escola_mg":
        if "escola" not in config.get("app_name", "").lower():
            config["app_name"] = "Minha Escola MG"
        config["domain"] = "education"
    elif curr_id == "mg_app_cidadao":
        if "cidad" not in config.get("app_name", "").lower():
            config["app_name"] = "MG App Cidadão"
        config["domain"] = "public_services"
        gp_pkg = config.get("google_play", {}).get("package_name")
        if not gp_pkg or gp_pkg == "br.gov.prodemge.cidadao":
            config.setdefault("google_play", {})["package_name"] = "br.gov.prodemge.projetosocialminas"
        apple_id = config.get("apple_store", {}).get("app_id")
        if not apple_id or apple_id == "1158925514":
            config.setdefault("apple_store", {})["app_id"] = "1057649491"
    elif curr_id == "fintech_banco":
        if "banco" not in config.get("app_name", "").lower() and "fintech" not in config.get("app_name", "").lower():
            config["app_name"] = "Banco Digital & Cartões"
        config["domain"] = "fintech"
    elif curr_id == "app_generico":
        config["domain"] = "general"

    return config

def save_app_config(new_config: Dict[str, Any]) -> bool:
    """Salva a nova configuração no arquivo app_config.json e no banco."""
    try:
        current = get_app_config()
        current.update(new_config)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(current, f, indent=2, ensure_ascii=False)

        # Atualiza também no banco para persistência imediata
        from database.db import set_setting
        if "app_id" in new_config:
            set_setting("app_id", str(new_config["app_id"]))
        if "domain" in new_config:
            set_setting("domain", str(new_config["domain"]))
        if "app_name" in new_config:
            set_setting("app_name", str(new_config["app_name"]))
        if "organization_name" in new_config:
            set_setting("organization_name", str(new_config["organization_name"]))
        if "support_url" in new_config:
            set_setting("support_contact_url", str(new_config["support_url"]))
        if "google_play" in new_config and "package_name" in new_config["google_play"]:
            set_setting("google_play_package", str(new_config["google_play"]["package_name"]))
        if "apple_store" in new_config and "app_id" in new_config["apple_store"]:
            set_setting("apple_store_id", str(new_config["apple_store"]["app_id"]))

        return True
    except Exception as e:
        logger.error(f"Erro ao salvar app_config: {e}")
        return False

# Helpers utilitários rápidos
def get_app_id() -> str:
    cfg = get_app_config()
    return cfg.get("app_id") or cfg.get("app_short_name", "minha_escola_mg")

def get_app_domain() -> str:
    cfg = get_app_config()
    return cfg.get("domain", "education" if get_app_id() == "minha_escola_mg" else "general")

def get_app_name() -> str:
    return get_app_config().get("app_name", "Minha Escola MG")

def get_organization_name() -> str:
    return get_app_config().get("organization_name", "Governo de Minas Gerais / Prodemge")

def get_developer_name() -> str:
    return get_app_config().get("developer_name", "Prodemge")

def get_support_url() -> str:
    return get_app_config().get("support_url", "https://forms.cloud.microsoft/r/JmZhSzXtwG")

def get_google_play_package() -> str:
    gp = get_app_config().get("google_play", {})
    return gp.get("package_name", "com.prodemge.minhaescolamg")

def get_apple_store_id() -> str:
    ap = get_app_config().get("apple_store", {})
    return ap.get("app_id", "6749247611")

def get_apple_store_country() -> str:
    ap = get_app_config().get("apple_store", {})
    return ap.get("country", "br")


def get_guest_token() -> str:
    return get_app_config().get("guest_token") or "CONVIDADO-2026"
