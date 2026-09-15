import os
import json
import time
import logging
from typing import Dict, Any, Tuple, Optional
import requests
import jwt
from google.oauth2 import service_account
from google.auth.transport.requests import Request as GoogleAuthRequest

logger = logging.getLogger(__name__)

PACKAGE_NAME = "com.prodemge.minhaescolamg"

def reply_to_google_play(review_id: str, reply_text: str, service_account_info_or_path: Any) -> Tuple[bool, str]:
    """
    Publica a resposta na Google Play Store usando a API Google Play Developer (v3).
    """
    if not service_account_info_or_path:
        return False, "Credenciais do Google Play Console (Service Account) não configuradas."

    try:
        # Se for string com caminho de arquivo ou string com conteúdo JSON
        if isinstance(service_account_info_or_path, str):
            if os.path.exists(service_account_info_or_path):
                creds = service_account.Credentials.from_service_account_file(
                    service_account_info_or_path,
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
            return False, "Formato de credencial do Google Play inválido."

        # Atualiza token de acesso
        creds.refresh(GoogleAuthRequest())
        token = creds.token

        url = f"https://androidpublisher.googleapis.com/androidpublisher/v3/applications/{PACKAGE_NAME}/reviews/{review_id}:reply"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        body = {
            "replyText": reply_text
        }

        resp = requests.post(url, headers=headers, json=body, timeout=20)
        
        if resp.status_code == 200:
            return True, "Resposta enviada e publicada com sucesso na Google Play Store!"
        else:
            error_detail = resp.text
            try:
                err_json = resp.json()
                error_detail = err_json.get("error", {}).get("message", resp.text)
            except Exception:
                pass
            return False, f"Erro Google Play ({resp.status_code}): {error_detail}"

    except Exception as e:
        logger.error(f"Exceção ao responder na Google Play: {e}")
        return False, f"Falha na conexão com Google Play: {str(e)}"

def generate_apple_jwt(key_id: str, issuer_id: str, private_key_content_or_path: str) -> str:
    """
    Gera o token JWT assinado com algoritmo ES256 exigido pela App Store Connect API.
    """
    if os.path.exists(private_key_content_or_path):
        with open(private_key_content_or_path, "r", encoding="utf-8") as f:
            private_key = f.read()
    else:
        private_key = private_key_content_or_path

    now = int(time.time())
    headers = {
        "alg": "ES256",
        "kid": key_id,
        "typ": "JWT"
    }
    payload = {
        "iss": issuer_id,
        "iat": now,
        "exp": now + 1200,  # 20 minutos de validade
        "aud": "appstoreconnect-v1"
    }

    token = jwt.encode(payload, private_key, algorithm="ES256", headers=headers)
    return token

def reply_to_apple_store(review_id: str, reply_text: str, key_id: str, issuer_id: str, private_key_p8: str) -> Tuple[bool, str]:
    """
    Publica a resposta na Apple App Store usando a App Store Connect API (v1/customerReviewResponses).
    """
    if not (key_id and issuer_id and private_key_p8):
        return False, "Credenciais do App Store Connect (Key ID / Issuer ID / .p8) incompletas."

    try:
        jwt_token = generate_apple_jwt(key_id.strip(), issuer_id.strip(), private_key_p8.strip())

        url = "https://api.appstoreconnect.apple.com/v1/customerReviewResponses"
        headers = {
            "Authorization": f"Bearer {jwt_token}",
            "Content-Type": "application/json"
        }
        body = {
            "data": {
                "type": "customerReviewResponses",
                "attributes": {
                    "responseBody": reply_text
                },
                "relationships": {
                    "review": {
                        "data": {
                            "type": "customerReviews",
                            "id": str(review_id)
                        }
                    }
                }
            }
        }

        resp = requests.post(url, headers=headers, json=body, timeout=20)

        if resp.status_code in (200, 201):
            return True, "Resposta enviada e publicada com sucesso na Apple App Store!"
        else:
            error_detail = resp.text
            try:
                err_json = resp.json()
                errors = err_json.get("errors", [])
                if errors:
                    error_detail = errors[0].get("detail", resp.text)
            except Exception:
                pass
            return False, f"Erro App Store Connect ({resp.status_code}): {error_detail}"

    except Exception as e:
        logger.error(f"Exceção ao responder na App Store: {e}")
        return False, f"Falha na conexão com Apple App Store: {str(e)}"

def test_google_play_credentials(service_account_info_or_path: Any) -> Tuple[bool, str]:
    """
    Testa se as credenciais do Google Play são válidas gerando um token de acesso OAuth2.
    """
    if not service_account_info_or_path:
        return False, "Nenhuma credencial informada."
    try:
        if isinstance(service_account_info_or_path, str):
            if os.path.exists(service_account_info_or_path):
                creds = service_account.Credentials.from_service_account_file(
                    service_account_info_or_path,
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
            return False, "Formato inválido."

        creds.refresh(GoogleAuthRequest())
        if creds.token:
            return True, f"Google Play Console conectado com sucesso! (Conta: {creds.service_account_email})"
        return False, "Não foi possível obter o token de acesso."
    except Exception as e:
        return False, f"Erro ao validar Google Play: {str(e)}"

def test_apple_credentials(key_id: str, issuer_id: str, private_key_p8: str) -> Tuple[bool, str]:
    """
    Testa se as credenciais do App Store Connect geram um JWT válido.
    """
    if not (key_id and issuer_id and private_key_p8):
        return False, "Key ID, Issuer ID e chave .p8 são obrigatórios."
    try:
        token = generate_apple_jwt(key_id.strip(), issuer_id.strip(), private_key_p8.strip())
        if token:
            return True, f"Token JWT da Apple App Store Connect gerado com sucesso para Key ID {key_id}!"
        return False, "Falha na geração do token JWT."
    except Exception as e:
        return False, f"Erro ao validar credenciais Apple: {str(e)}"
