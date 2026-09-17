import os
import time
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
try:
    import jwt
    ExpiredSignatureError = jwt.ExpiredSignatureError
    InvalidTokenError = getattr(jwt, "InvalidTokenError", Exception)
except ImportError:
    from jose import jwt
    from jose.exceptions import ExpiredSignatureError, JWTError as InvalidTokenError

try:
    from google.oauth2 import id_token
    from google.auth.transport import requests as google_requests
except ImportError:
    id_token = None
    google_requests = None

from database.db import (
    get_user_by_email, get_user_by_id, handle_user_login, 
    get_setting, SUPER_ADMIN_EMAIL
)

logger = logging.getLogger("auth")

# Chave secreta para assinatura dos cookies de sessão
SECRET_KEY = os.environ.get("SECRET_KEY", "prodemge-minha-escola-mg-jwt-secret-2026-auth")
ALGORITHM = "HS256"
SESSION_COOKIE_NAME = "session_token"
SESSION_DURATION_DAYS = 7

def get_google_client_id() -> str:
    """Obtém o Google Client ID das variáveis de ambiente ou das configurações do banco."""
    client_id = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
    if not client_id:
        client_id = get_setting("google_client_id", "").strip()
    return client_id

def create_session_token(user: Dict[str, Any]) -> str:
    """Gera um JWT assinado para a sessão do usuário."""
    exp = datetime.utcnow() + timedelta(days=SESSION_DURATION_DAYS)
    payload = {
        "sub": str(user["id"]),
        "email": user["email"].lower(),
        "name": user.get("name") or user["email"].split("@")[0],
        "role": user.get("role", "viewer"),
        "picture": user.get("picture", ""),
        "status": user.get("status", "approved"),
        "exp": int(exp.timestamp()),
        "iat": int(time.time()) - 10
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return token

def decode_session_token(token: str) -> Optional[Dict[str, Any]]:
    """Decodifica e valida o JWT da sessão."""
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM], leeway=60)
        return payload
    except ExpiredSignatureError:
        logger.warning("Token de sessão expirado")
        return None
    except InvalidTokenError as e:
        logger.warning(f"Token de sessão inválido: {e}")
        return None

def verify_google_credential(credential: str) -> Dict[str, Any]:
    """
    Valida a credencial JWT retornada pelo Google Identity Services (GIS).
    Retorna o dicionário com os dados do usuário autenticado no Google.
    """
    if not id_token or not google_requests:
        raise RuntimeError("google-auth não está instalado no ambiente.")

    client_id = get_google_client_id()
    if not client_id:
        raise ValueError("GOOGLE_CLIENT_ID não está configurado no servidor.")
    
    try:
        id_info = id_token.verify_oauth2_token(
            credential,
            google_requests.Request(),
            client_id,
            clock_skew_in_seconds=10
        )
        
        email = id_info.get("email", "").lower()
        if not email:
            raise ValueError("O token do Google não contém um e-mail válido.")
            
        name = id_info.get("name", "")
        picture = id_info.get("picture", "")
        
        return {
            "email": email,
            "name": name,
            "picture": picture,
            "sub": id_info.get("sub", "")
        }
    except Exception as e:
        logger.error(f"Falha na validação do token Google: {e}")
        raise ValueError(f"Token do Google inválido ou expirado: {str(e)}")

def authenticate_google_user(credential: str) -> Dict[str, Any]:
    """
    Valida token com o Google e processa o usuário no banco de dados:
    - Se for Super Admin (saulomartins.costa@gmail.com): aprovado e admin automático.
    - Se for usuário aprovado: retorna sessão liberada.
    - Se não for cadastrado: registra como pendente para aprovação do Saulo.
    """
    google_data = verify_google_credential(credential)
    user = handle_user_login(
        email=google_data["email"],
        name=google_data["name"],
        picture=google_data["picture"]
    )
    return user

def dev_login_admin() -> Dict[str, Any]:
    """
    Permite login direto do Administrador Saulo para testes locais
    quando o Google Client ID ainda não estiver configurado.
    """
    user = handle_user_login(
        email=SUPER_ADMIN_EMAIL,
        name="Saulo Martins Costa",
        picture=""
    )
    return user
