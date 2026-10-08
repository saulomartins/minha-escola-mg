import os
import sys
import json
import asyncio
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, BackgroundTasks, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse, Response, RedirectResponse
import io
import csv
import re
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

# Garante acesso aos módulos no caminho
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db import (
    init_db, upsert_review, get_reviews, get_stats, get_device_diagnostic,
    update_review_analysis, update_review_status, update_review_device_info,
    get_setting, set_setting, get_all_settings, get_connection,
    list_users, get_user_by_id, get_user_by_email, upsert_user,
    update_user_status, update_user_role, delete_user, SUPER_ADMIN_EMAIL,
    bulk_import_users, get_users_env_string,
    create_access_token, get_access_token_by_token, get_access_token_by_id,
    record_access_token_usage, list_access_tokens, toggle_access_token_status,
    delete_access_token, update_access_token, get_tokens_env_string
)
from auth.google_auth import (
    get_google_client_id, create_session_token, decode_session_token,
    authenticate_google_user, dev_login_admin, SESSION_COOKIE_NAME,
    create_guest_session_token, SESSION_DURATION_DAYS
)
from analytics.device_detector import detect_device_and_os
from collector.play_console_importer import import_play_console_csv
from collector.google_play import fetch_google_play_reviews
from collector.apple_store import fetch_apple_store_reviews
from ai.analyzer import analyze_review, test_gemini_key
from publisher.store_publisher import (
    reply_to_google_play, reply_to_apple_store,
    test_google_play_credentials, test_apple_credentials
)
from analytics.complexity import get_detailed_problem_analytics, classify_text_issue
from analytics.temporal import get_temporal_diagnostics
from ai.auto_reply_templates import PROBLEM_TEMPLATES_CONFIG, generate_auto_reply_for_review

logger = logging.getLogger("app_reviews")

# Inicializa o banco de dados
init_db()

# Tarefa periódica de sincronização
async def periodic_sync_worker():
    """Verifica e sincroniza as lojas periodicamente em segundo plano"""
    while True:
        try:
            interval_str = get_setting("auto_sync_interval", "0")
            interval_min = int(interval_str) if interval_str.isdigit() else 0
            
            if interval_min > 0:
                logger.info(f"Executando sincronização periódica agendada (intervalo: {interval_min} min)...")
                run_sync_and_auto_analyze()
                await asyncio.sleep(interval_min * 60)
            else:
                # Se desativado, verifica a cada 60s se a configuração mudou
                await asyncio.sleep(60)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Erro no agendador periódico: {e}")
            await asyncio.sleep(60)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Inicialização
    worker_task = asyncio.create_task(periodic_sync_worker())
    yield
    # Encerramento
    worker_task.cancel()
    try:
        await worker_task
    except asyncio.CancelledError:
        pass

app = FastAPI(title="Minha Escola MG - Analisador de Avaliações", lifespan=lifespan)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Modelos Pydantic
class ReplyRequest(BaseModel):
    review_id: str
    response_text: str
    send_to_store: bool = False

class SettingsRequest(BaseModel):
    gemini_api_key: Optional[str] = None
    google_play_service_account: Optional[str] = None
    apple_key_id: Optional[str] = None
    apple_issuer_id: Optional[str] = None
    apple_private_key_p8: Optional[str] = None
    auto_publish_direct: Optional[str] = None
    auto_reply_5_stars_only: Optional[str] = None
    auto_sync_interval: Optional[str] = None
    support_email: Optional[str] = None
    apple_downloads_custom: Optional[str] = None

class TestKeyRequest(BaseModel):
    key: Optional[str] = None

class TestGoogleRequest(BaseModel):
    service_account: Optional[str] = None

class TestAppleRequest(BaseModel):
    key_id: Optional[str] = None
    issuer_id: Optional[str] = None
    private_key_p8: Optional[str] = None

# Modelos de Autenticação e Usuários
class GoogleAuthRequest(BaseModel):
    credential: str

class AddUserRequest(BaseModel):
    email: str
    name: Optional[str] = ""
    role: str = "viewer"

class UserStatusRequest(BaseModel):
    status: str
    role: Optional[str] = None

class UserRoleRequest(BaseModel):
    role: str

class TokenLoginRequest(BaseModel):
    token: str

class CreateTokenRequest(BaseModel):
    label: str
    token: Optional[str] = None
    expires_in_days: Optional[int] = None

class UpdateTokenRequest(BaseModel):
    label: Optional[str] = None
    token: Optional[str] = None
    expires_in_days: Optional[int] = None

class ToggleTokenStatusRequest(BaseModel):
    is_active: bool

class UpdateReviewDeviceRequest(BaseModel):
    device_brand: Optional[str] = None
    device_model: Optional[str] = None
    os_name: Optional[str] = "Android"
    os_version: Optional[str] = None
    app_version: Optional[str] = None
    app_version_code: Optional[str] = None
    reviewer_language: Optional[str] = None

# Helpers de Sessão e Permissão
def get_current_user_from_request(request: Request) -> Optional[Dict[str, Any]]:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        return None
    payload = decode_session_token(token)
    if not payload:
        return None

    # 1. Usuário Convidado via Token de Acesso
    if payload.get("is_token_guest"):
        token_str = payload.get("token_str")
        if not token_str:
            return None
        token_db = get_access_token_by_token(token_str)
        if not token_db or not token_db.get("is_active"):
            return None
        if token_db.get("expires_at"):
            try:
                exp_dt = datetime.fromisoformat(token_db["expires_at"])
                if datetime.utcnow() > exp_dt:
                    return None
            except Exception:
                pass
        return {
            "id": f"token_{token_db['id']}",
            "email": f"convidado_{token_db['token'].lower()}@token.local",
            "name": token_db.get("label") or "Convidado por Token",
            "role": "viewer",
            "picture": "",
            "is_token_guest": True,
            "token_id": token_db["id"],
            "token_str": token_db["token"],
            "status": "approved"
        }

    # 2. Usuário Autenticado via Conta Google
    user_id = payload.get("sub")
    user_db = None
    if user_id:
        try:
            user_db = get_user_by_id(int(user_id))
        except (ValueError, TypeError):
            pass
    if not user_db and payload.get("email"):
        user_db = get_user_by_email(payload["email"])

    user_email = (payload.get("email") or "").lower()
    # Se for o super admin ou mgminhaescola@gmail.com, sempre garante acesso admin ativo
    if user_email in [SUPER_ADMIN_EMAIL.lower(), "mgminhaescola@gmail.com"]:
        if not user_db:
            user_db = upsert_user(user_email, name="Administrador", role="admin", status="approved", added_by="system")
        else:
            user_db["role"] = "admin"
            user_db["status"] = "approved"

    if not user_db or user_db.get("status") != "approved":
        return None
    return user_db

def require_admin(request: Request) -> Dict[str, Any]:
    user = get_current_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="Sessão não autenticada. Faça login com sua conta Google.")
    if user.get("role") != "admin" or user.get("is_token_guest"):
        raise HTTPException(status_code=403, detail="Acesso restrito ao Administrador do Sistema.")
    return user

def require_auth(request: Request) -> Dict[str, Any]:
    user = get_current_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="Acesso restrito. Faça login ou informe um token de acesso válido.")
    return user

@app.middleware("http")
async def auth_gate_middleware(request: Request, call_next):
    """Barreira de acesso: protege o dashboard e APIs contra acessos públicos anônimos."""
    path = request.url.path

    # Rotas públicas que não exigem login prévio
    if (
        path in [
            "/login",
            "/api/auth/google",
            "/api/auth/token-login",
            "/api/auth/dev-login",
            "/logout",
            "/favicon.ico"
        ]
        or path.startswith("/static")
    ):
        return await call_next(request)

    # 1. Validação de token direto na URL (ex: /?access_token=SEE-2026 ou /?token=...)
    token_param = request.query_params.get("access_token") or request.query_params.get("token")
    if token_param:
        token_obj = get_access_token_by_token(token_param.strip())
        if token_obj and token_obj.get("is_active"):
            is_expired = False
            if token_obj.get("expires_at"):
                try:
                    exp_dt = datetime.fromisoformat(token_obj["expires_at"])
                    if datetime.utcnow() > exp_dt:
                        is_expired = True
                except Exception:
                    pass
            if not is_expired:
                record_access_token_usage(token_obj["id"])
                session_tok = create_guest_session_token(token_obj)
                res = RedirectResponse(url="/", status_code=302)
                res.set_cookie(
                    key=SESSION_COOKIE_NAME,
                    value=session_tok,
                    httponly=True,
                    max_age=SESSION_DURATION_DAYS * 86400,
                    samesite="lax",
                    secure=False
                )
                return res

    # 2. Validação da sessão do usuário
    user = get_current_user_from_request(request)
    request.state.user = user

    if not user:
        if path.startswith("/api/"):
            return JSONResponse(
                status_code=401,
                content={"error": "Acesso restrito. Informe um token de acesso válido ou faça login."}
            )
        # Redireciona visitantes não autenticados para a tela de login
        return RedirectResponse(url="/login", status_code=302)

    return await call_next(request)

# ==============================================================================
# ROTAS DE AUTENTICAÇÃO (GOOGLE SIGN-IN)
# ==============================================================================

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Página de Login com Google Identity Services"""
    user = get_current_user_from_request(request)
    if user and user.get("status") == "approved":
        return RedirectResponse(url="/", status_code=302)
    client_id = get_google_client_id()
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"google_client_id": client_id}
    )

@app.post("/api/auth/google")
async def api_auth_google(req: GoogleAuthRequest):
    """Valida token Google e processa login / solicitação de acesso"""
    try:
        user = authenticate_google_user(req.credential)
        if user.get("status") == "approved":
            token = create_session_token(user)
            res = JSONResponse({"status": "ok", "user": user})
            res.set_cookie(
                key=SESSION_COOKIE_NAME,
                value=token,
                httponly=True,
                samesite="lax",
                max_age=7 * 86400
            )
            return res
        elif user.get("status") == "pending":
            return JSONResponse(
                {"status": "pending", "email": user["email"], "name": user.get("name")},
                status_code=403
            )
        elif user.get("status") == "blocked":
            return JSONResponse(
                {"status": "blocked", "email": user["email"]},
                status_code=403
            )
        else:
            return JSONResponse({"status": "unauthorized"}, status_code=403)
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=400)

@app.get("/dev-login")
async def quick_dev_login(request: Request):
    """Permite acesso local direto como Super Admin no localhost"""
    user = dev_login_admin()
    token = create_session_token(user)
    res = RedirectResponse(url="/", status_code=302)
    res.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=7 * 86400
    )
    return res

@app.post("/api/auth/dev-login")
async def api_auth_dev_login():
    """Login direto desativado quando o Google Client ID estiver configurado"""
    if get_google_client_id():
        raise HTTPException(
            status_code=403, 
            detail="Modo de teste desativado. O sistema agora exige login real via Google Sign-In."
        )
    user = dev_login_admin()
    token = create_session_token(user)
    res = JSONResponse({"status": "ok", "user": user})
    res.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=7 * 86400
    )
    return res

@app.post("/api/auth/token-login")
async def api_auth_token_login(req: TokenLoginRequest):
    """Autentica um visitante utilizando um token de acesso compartilhado."""
    token_str = (req.token or "").strip()
    if not token_str:
        raise HTTPException(status_code=400, detail="Informe o token de acesso.")
    
    token_obj = get_access_token_by_token(token_str)
    if not token_obj:
        raise HTTPException(status_code=401, detail="Token de acesso incorreto ou não encontrado.")
    
    if not token_obj.get("is_active"):
        raise HTTPException(status_code=403, detail="Este token de acesso foi desativado pelo administrador.")
        
    if token_obj.get("expires_at"):
        try:
            exp_dt = datetime.fromisoformat(token_obj["expires_at"])
            if datetime.utcnow() > exp_dt:
                raise HTTPException(status_code=403, detail="Este token de acesso expirou.")
        except Exception:
            pass

    record_access_token_usage(token_obj["id"])
    session_tok = create_guest_session_token(token_obj)
    
    res = JSONResponse({
        "status": "ok",
        "label": token_obj.get("label"),
        "role": "viewer"
    })
    res.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_tok,
        httponly=True,
        max_age=SESSION_DURATION_DAYS * 86400,
        samesite="lax",
        secure=False
    )
    return res

@app.get("/logout")
async def logout():
    """Encerra a sessão e redireciona para a tela de login"""
    res = RedirectResponse(url="/login", status_code=302)
    res.delete_cookie(SESSION_COOKIE_NAME)
    return res

@app.get("/api/auth/me")
async def api_auth_me(request: Request):
    """Retorna os dados do usuário autenticado atual"""
    user = get_current_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="Não autenticado.")
    return user

# ==============================================================================
# GESTÃO DE USUÁRIOS E PERMISSÕES (ADMIN EXCLUSIVE)
# ==============================================================================

@app.get("/api/admin/users")
async def api_admin_list_users(request: Request):
    """Lista todos os usuários com métricas de acesso"""
    require_admin(request)
    all_users = list_users()
    stats = {
        "total": len(all_users),
        "approved": sum(1 for u in all_users if u["status"] == "approved"),
        "pending": sum(1 for u in all_users if u["status"] == "pending"),
        "blocked": sum(1 for u in all_users if u["status"] == "blocked"),
        "admins": sum(1 for u in all_users if u["role"] == "admin" and u["status"] == "approved")
    }
    return {"stats": stats, "users": all_users, "super_admin": SUPER_ADMIN_EMAIL}

@app.get("/api/admin/users/env-string")
async def api_admin_users_env_string(request: Request):
    """Retorna a string formatada para configurar ALLOWED_USERS no Render."""
    require_admin(request)
    all_users = list_users()
    return {
        "env_key": "ALLOWED_USERS",
        "env_variable": "ALLOWED_USERS",
        "env_value": get_users_env_string(),
        "count": len(all_users)
    }

@app.get("/api/admin/users/export")
async def api_admin_users_export(request: Request):
    """Exporta a lista completa de usuários cadastrados para backup JSON."""
    require_admin(request)
    users = list_users()
    return {"users": users, "exported_at": datetime.utcnow().isoformat(), "count": len(users)}

@app.post("/api/admin/users/import")
async def api_admin_users_import(request: Request):
    """Importa usuários a partir de um backup JSON (suporta lista ou objeto com 'users')."""
    require_admin(request)
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="JSON inválido.")
        
    if isinstance(body, dict) and "users" in body:
        users = body["users"]
    elif isinstance(body, list):
        users = body
    else:
        raise HTTPException(status_code=400, detail="Formato inválido. O arquivo deve conter uma lista de usuários.")
        
    imported = bulk_import_users(users)
    return {"status": "ok", "imported_count": imported}

@app.post("/api/admin/users")
async def api_admin_add_user(req: AddUserRequest, request: Request):
    """Adiciona ou pré-autoriza um novo e-mail Gmail"""
    admin = require_admin(request)
    email = req.email.strip().lower()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Por favor, informe um endereço de e-mail válido.")
    user = upsert_user(
        email=email,
        name=req.name or "",
        role=req.role if req.role in ["admin", "viewer"] else "viewer",
        status="approved",
        added_by=admin["email"]
    )
    return {"status": "ok", "user": user}

@app.post("/api/admin/users/{user_id}/status")
async def api_admin_set_status(user_id: int, req: UserStatusRequest, request: Request):
    """Aprova, coloca em espera ou bloqueia um usuário"""
    require_admin(request)
    if req.status not in ["approved", "pending", "blocked"]:
        raise HTTPException(status_code=400, detail="Status inválido.")
    if req.role and req.role in ["admin", "viewer"]:
        update_user_role(user_id, req.role)
    success = update_user_status(user_id, req.status)
    if not success:
        raise HTTPException(status_code=400, detail="Não é possível alterar o status deste usuário (Super Admin protegido).")
    return {"status": "ok"}

@app.post("/api/admin/users/{user_id}/role")
async def api_admin_set_role(user_id: int, req: UserRoleRequest, request: Request):
    """Altera o papel do usuário (admin ou viewer)"""
    require_admin(request)
    if req.role not in ["admin", "viewer"]:
        raise HTTPException(status_code=400, detail="Papel inválido.")
    success = update_user_role(user_id, req.role)
    if not success:
        raise HTTPException(status_code=400, detail="Não é possível alterar o papel deste usuário.")
    return {"status": "ok"}

@app.delete("/api/admin/users/{user_id}")
async def api_admin_delete_user(user_id: int, request: Request):
    """Remove um usuário do cadastro (Super Admin protegido)"""
    require_admin(request)
    success = delete_user(user_id)
    if not success:
        raise HTTPException(status_code=400, detail="Não é permitido excluir o Administrador Geral.")
    return {"status": "ok"}

# ==============================================================================
# GESTÃO DE TOKENS DE ACESSO (ADMIN EXCLUSIVE)
# ==============================================================================

@app.get("/api/admin/tokens")
def api_admin_list_tokens(request: Request):
    """Lista todos os tokens de acesso de convidados."""
    require_admin(request)
    return list_access_tokens()

@app.post("/api/admin/tokens")
def api_admin_create_token(req: CreateTokenRequest, request: Request):
    """Cria uma nova chave ou token de acesso de convidado."""
    admin = require_admin(request)
    if not req.label or not req.label.strip():
        raise HTTPException(status_code=400, detail="O nome/identificação do token é obrigatório.")
    new_token = create_access_token(
        label=req.label,
        token_code=req.token,
        created_by=admin.get("email") or "admin",
        expires_days=req.expires_in_days
    )
    return new_token

@app.post("/api/admin/tokens/{token_id}/status")
def api_admin_toggle_token_status(token_id: str, req: ToggleTokenStatusRequest, request: Request):
    """Ativa ou desativa um token de acesso de convidado."""
    require_admin(request)
    toggle_access_token_status(token_id, req.is_active)
    return {"status": "ok", "token_id": token_id, "is_active": req.is_active}

@app.put("/api/admin/tokens/{token_id}")
@app.post("/api/admin/tokens/{token_id}")
def api_admin_update_token(token_id: str, req: UpdateTokenRequest, request: Request):
    """Atualiza o código da chave, nome/descrição ou prazo de expiração de um token."""
    require_admin(request)
    try:
        updated = update_access_token(
            token_id=token_id,
            new_token=req.token,
            new_label=req.label,
            expires_in_days=req.expires_in_days
        )
        if not updated:
            raise HTTPException(status_code=404, detail="Token não encontrado.")
        return updated
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/api/admin/tokens/{token_id}")
def api_admin_delete_token(token_id: str, request: Request):
    """Exclui permanentemente um token de acesso."""
    require_admin(request)
    delete_access_token(token_id)
    return {"status": "ok", "deleted": token_id}

@app.get("/api/admin/tokens/env-string")
def api_admin_tokens_env_string(request: Request):
    """Retorna a string formatada para configurar a variável de ambiente GUEST_ACCESS_TOKEN no Render."""
    require_admin(request)
    return {"env_var_name": "GUEST_ACCESS_TOKEN", "env_value": get_tokens_env_string()}

# ==============================================================================
# PÁGINA PRINCIPAL DO SISTEMA
# ==============================================================================

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    user = get_current_user_from_request(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"current_user": user}
    )

@app.get("/api/stats")
def api_stats():
    return get_stats()

@app.get("/api/analytics/problems")
def api_analytics_problems():
    return get_detailed_problem_analytics()

@app.get("/api/analytics/templates")
def api_analytics_templates():
    """Retorna o mapeamento completo de causas-raiz, palavras-chave e templates de resposta para todas as estrelas"""
    return PROBLEM_TEMPLATES_CONFIG

@app.get("/api/analytics/devices")
def api_analytics_devices():
    """Retorna diagnóstico completo sobre modelos de celulares, sistemas operacionais e versões"""
    return get_device_diagnostic()

@app.get("/api/analytics/temporal")
def api_analytics_temporal():
    """Retorna diagnóstico temporal completo: linha do tempo, faixas de envelhecimento, evolução mês a mês e tendências por causa-raiz"""
    return get_temporal_diagnostics()

@app.get("/api/analytics/hardware-root-cause")
def api_analytics_hardware_root_cause(
    brand: Optional[str] = None,
    root_cause_id: Optional[str] = None
):
    """Retorna análise cruzada de hardware (fabricantes e modelos) com causas-raiz de problemas."""
    from analytics.hardware_root_cause import get_hardware_root_cause_analytics
    return get_hardware_root_cause_analytics(filter_brand=brand, filter_root_cause_id=root_cause_id)

@app.get("/api/analytics/keyword-scan")
def api_analytics_keyword_scan(q: str = ""):
    """Realiza varredura dinâmica e profunda em tempo real por termos ou palavras-chave em todos os comentários."""
    from analytics.keyword_scanner import scan_keywords
    return scan_keywords(q)


@app.post("/api/reviews/backfill-devices")
def api_backfill_devices():
    """Atualiza e normaliza a detecção de aparelhos e sistemas operacionais em todas as avaliações salvas (sem sobrescrever dados manuais ou oficiais do Play Console)"""
    from database.db import populate_store_device_specifications
    populate_store_device_specifications()
    return {"success": True, "message": "Especificação de aparelhos e sistemas operacionais atualizada com sucesso no banco de dados!"}

@app.post("/api/reviews/{review_id}/device")
def api_update_review_device(review_id: str, payload: UpdateReviewDeviceRequest):
    """Atualiza manualmente dados de hardware e versão obtidos do Google Play Console para uma avaliação"""
    success = update_review_device_info(
        review_id=review_id,
        device_brand=payload.device_brand,
        device_model=payload.device_model,
        os_name=payload.os_name,
        os_version=payload.os_version,
        app_version=payload.app_version,
        app_version_code=payload.app_version_code,
        reviewer_language=payload.reviewer_language,
        device_source="play_console_official" if payload.device_brand or payload.device_model else "manual_edit"
    )
    if not success:
        raise HTTPException(status_code=404, detail="Avaliação não encontrada")

    # Retorna o registro atualizado
    revs = get_reviews(search=review_id, limit=1)
    if not revs:
        # Tenta buscar pelo id ou review_id
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT id FROM reviews WHERE id = ? OR review_id = ?", (review_id, review_id))
        row = c.fetchone()
        conn.close()
        if row:
            revs = get_reviews(search=row['id'], limit=1)

    return {
        "success": True,
        "message": "Dados do dispositivo atualizados com sucesso!",
        "review": revs[0] if revs else None
    }

@app.get("/api/reviews")
def api_reviews(
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
):
    reviews = get_reviews(
        store=store,
        rating=rating,
        status=status,
        sentiment=sentiment,
        root_cause_id=root_cause_id,
        os_name=os_name,
        device_brand=device_brand,
        search=search,
        stuck_android_12=stuck_android_12,
        limit=limit,
        offset=offset
    )
    return {"reviews": reviews, "count": len(reviews)}

@app.get("/api/reviews/export")
def api_export_reviews(
    format: str = "excel",
    scope: str = "all",
    all: Optional[bool] = False,
    store: Optional[str] = None,
    rating: Optional[int] = None,
    status: Optional[str] = None,
    sentiment: Optional[str] = None,
    root_cause_id: Optional[str] = None,
    os_name: Optional[str] = None,
    device_brand: Optional[str] = None,
    search: Optional[str] = None,
    stuck_android_12: Optional[bool] = None
):
    """
    Exporta todas as avaliações com colunas estruturadas: Loja, Data, Usuário, Estrelas,
    Sentimento, Categoria, Causa-Raiz, Celular (Marca e Modelo), Sistema Operacional e Versão,
    Preso no Android <= 12 (Sem Atualização), Versão do App, Texto do Comentário e Resposta Oficial.
    Se all=True ou scope='all', exporta 100% da base completa com todos os 500 comentários sem filtros.
    Se scope='filtered', respeita os filtros ativos.
    Formatos suportados: 'excel' (.xlsx) e 'csv' (.csv com UTF-8-BOM).
    """
    is_full_base = all or (scope == "all")
    if is_full_base:
        reviews = get_reviews(limit=10000, offset=0)
    else:
        reviews = get_reviews(
            store=store if store != "todas" else None,
            rating=rating if rating and rating > 0 else None,
            status=status if status != "todos" else None,
            sentiment=sentiment if sentiment != "todos" else None,
            root_cause_id=root_cause_id if root_cause_id != "todos" else None,
            os_name=os_name if os_name != "todos" else None,
            device_brand=device_brand if device_brand != "todas" else None,
            search=search,
            stuck_android_12=stuck_android_12,
            limit=10000,
            offset=0
        )

    root_cause_names = {
        "gov_br_cpf": "Falha no Gov.br e Vínculo de CPF",
        "senha_recuperacao": "Recuperação de Senha e Redefinição",
        "boletim_notas": "Boletim em Branco e Notas Ausentes",
        "faltas_frequencia": "Faltas e Frequência Divergentes",
        "crash_fechamento": "Crash e Fechamento Inesperado",
        "lentidao_tela_preta": "Lentidão Extrema e Tela Preta",
        "acesso_responsaveis": "Acesso dos Pais / Múltiplos Alunos",
        "elogios_satisfacao": "Elogios e Avaliações Positivas",
        "outros_problemas": "Problemas Gerais e Dúvidas",
        "geral_outros": "Geral / Sugestões Diversas"
    }

    # Padrão regex abrangente para remoção de emojis, pictogramas e símbolos especiais
    EMOJI_PATTERN = re.compile(
        "["
        "\U00010000-\U0010FFFF"  # Todos os planos astrais (emojis de expressões, pessoas, objetos, transporte)
        "\u2600-\u26FF"          # Símbolos diversos (ex: ⚠️, ⚡, ☕, ⛔, ☹, ☺, ♀, ♂)
        "\u2700-\u27BF"          # Dingbats (ex: ✅, ❌, ✂️, ✨)
        "\u2300-\u23FF"          # Símbolos técnicos (ex: ⏳, ⏱️)
        "\u2B50"                 # Estrela ⭐
        "\u2139"                 # Ícone de informação ℹ
        "\uFFFC"                 # Caractere de substituição de objeto ￼
        "\u200D"                 # Zero-width joiner
        "\uFE0E-\uFE0F"          # Variation selectors
        "\u20E3"                 # Combining Enclosing Keycap
        "\u2190-\u21FF"          # Setas
        "\u2900-\u297F"          # Setas complementares
        "\u2B00-\u2BFF"          # Símbolos e setas diversos
        "\u25A0-\u25FF"          # Formas geométricas
        "\u2460-\u24FF"          # Caracteres alfanuméricos circulados
        "]+",
        flags=re.UNICODE
    )

    def clean_text(val):
        """Limpa emojis, ícones e caracteres de controle especiais, preservando acentuação da língua portuguesa."""
        if val is None:
            return ""
        if isinstance(val, (int, float, bool)):
            return val
        s = str(val)
        # Remove emojis e pictogramas
        s = EMOJI_PATTERN.sub("", s)
        # Remove caracteres de controle invisíveis não imprimíveis
        s = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", s)
        # Normaliza espaços consecutivos deixados pela exclusão de ícones
        s = re.sub(r" +", " ", s).strip()
        return s

    from analytics.device_lifecycle import get_device_lifecycle

    headers = [
        "ID", "Loja", "Data", "Usuário", "Estrelas", "Sentimento", "Categoria",
        "Causa-Raiz (Diagnóstico)", "Marca Celular", "Modelo Celular", "Sistema Operacional",
        "Versão SO Atual", "Última Versão Oficial Fabricante", "Status Suporte Fabricante",
        "Preso no Android <= 12 (Sem Atualização)",

        "Versão App", "Título", "Comentário do Usuário", "Resposta Oficial / Sugerida",
        "Status", "Publicada na Loja"
    ]

    def build_row(r):
        store_display = "Google Play Store" if r.get("store") == "google" else "Apple App Store"
        rating_val = int(r.get('rating') or 0)
        
        sent = (r.get("sentiment") or "").lower()
        if sent == "positivo":
            sent_display = "Positivo"
        elif sent == "negativo":
            sent_display = "Negativo"
        else:
            sent_display = "Neutro"
            
        rc_id = r.get("root_cause_id") or ""
        rc_display = root_cause_names.get(rc_id, rc_id or "Não categorizado")
        
        resp_display = r.get("local_response") or r.get("ai_suggested_response") or ""

        life = get_device_lifecycle(r.get("device_brand"), r.get("device_model"))
        max_os_display = life.get("last_official_os") or life.get("max_os", "-")
        support_display = life.get("support_status", "-")

        
        is_stuck = r.get("is_stuck_android_12")
        stuck_cell = "SIM (Não atualiza > Android 12)" if is_stuck else "NÃO"
        
        return [
            clean_text(r.get("id", "")),
            clean_text(store_display),
            clean_text((r.get("review_date") or "")[:10]),
            clean_text(r.get("user_name") or "Usuário"),
            rating_val,
            clean_text(sent_display),
            clean_text(r.get("category") or "Geral"),
            clean_text(rc_display),
            clean_text(r.get("device_brand") or "Não especificado"),
            clean_text(r.get("device_model") or "Não especificado"),
            clean_text(r.get("os_name") or ("Android" if r.get("store") == "google" else "iOS")),
            clean_text(r.get("os_version") or "-"),
            clean_text(max_os_display),
            clean_text(support_display),
            clean_text(stuck_cell),
            clean_text(r.get("app_version") or "4.2.2"),
            clean_text(r.get("title") or "-"),
            clean_text(r.get("content") or ""),
            clean_text(resp_display),
            clean_text((r.get("status") or "pendente").capitalize()),
            "Sim" if r.get("published_to_store") else "Não"
        ]


    file_suffix = "Base_Completa_500_Comentarios" if is_full_base else "Filtradas"

    if format.lower() == "csv":
        output = io.StringIO()
        writer = csv.writer(output, delimiter=";", quoting=csv.QUOTE_MINIMAL)
        writer.writerow(headers)
        for r in reviews:
            writer.writerow(build_row(r))
        csv_data = output.getvalue().encode("utf-8-sig")
        return Response(
            content=csv_data,
            media_type="text/csv; charset=utf-8-sig",
            headers={"Content-Disposition": f'attachment; filename="Avaliacoes_Minha_Escola_MG_{file_suffix}.csv"'}
        )

    # Gera arquivo Excel (.xlsx) nativo com openpyxl
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Avaliações e Diagnósticos"
    ws.views.sheetView[0].showGridLines = True

    header_fill = PatternFill(start_color="1E1B4B", end_color="1E1B4B", fill_type="solid")
    header_font = Font(name="Segoe UI", size=10, bold=True, color="FFFFFF")
    header_align = Alignment(horizontal="center", vertical="center", wrap_text=True)

    thin_border = Border(
        left=Side(style='thin', color='CBD5E1'),
        right=Side(style='thin', color='CBD5E1'),
        top=Side(style='thin', color='CBD5E1'),
        bottom=Side(style='thin', color='CBD5E1')
    )

    ws.append(headers)
    ws.row_dimensions[1].height = 28

    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = header_align
        cell.border = thin_border

    row_font = Font(name="Segoe UI", size=9)
    center_align = Alignment(horizontal="center", vertical="center")
    left_align = Alignment(horizontal="left", vertical="center", wrap_text=True)

    for r in reviews:
        row_data = build_row(r)
        ws.append(row_data)
        curr_row = ws.max_row
        ws.row_dimensions[curr_row].height = 20

        for col_idx in range(1, len(row_data) + 1):
            c = ws.cell(row=curr_row, column=col_idx)
            c.font = row_font
            c.border = thin_border
            if col_idx in (1, 2, 3, 5, 6, 9, 11, 12, 13, 14, 15, 16, 20, 21):
                c.alignment = center_align
            else:
                c.alignment = left_align

    col_widths = {
        1: 8,   # ID
        2: 18,  # Loja
        3: 13,  # Data
        4: 20,  # Usuário
        5: 10,  # Estrelas
        6: 14,  # Sentimento
        7: 18,  # Categoria
        8: 34,  # Causa-raiz
        9: 16,  # Marca
        10: 18, # Modelo
        11: 14, # SO
        12: 14, # Versão SO
        13: 28, # Versão Máxima Suportada
        14: 32, # Status Suporte Fabricante/Google
        15: 32, # Preso no Android <= 12
        16: 12, # Versão App
        17: 25, # Título
        18: 50, # Comentário
        19: 50, # Resposta
        20: 12, # Status
        21: 14  # Publicada
    }
    for col_idx, width in col_widths.items():
        col_letter = get_column_letter(col_idx)
        ws.column_dimensions[col_letter].width = width

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    return Response(
        content=buffer.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="Avaliacoes_Minha_Escola_MG_{file_suffix}.xlsx"'}
    )


@app.post("/api/reviews/import-play-console")
async def api_import_play_console(file: UploadFile = File(...)):
    """
    Importa relatório CSV oficial exportado do Google Play Developer Console.
    Atualiza 100% dos comentários com telemetria oficial (Aparelho, Marca, SO Android e Código da Versão).
    """
    try:
        content = await file.read()
        res = import_play_console_csv(content)
        return res
    except Exception as e:
        logger.error(f"Erro ao importar CSV do Play Console: {e}")
        return JSONResponse(status_code=500, content={"success": False, "message": f"Erro ao processar CSV: {str(e)}"})

@app.post("/api/reviews/apply-all-auto-replies")
def api_apply_all_auto_replies():
    """
    Gera e aplica respostas automáticas padronizadas e personalizadas para todas as avaliações reais
    do Minha Escola MG (Google Play e Apple Store), cobrindo de 1 a 5 estrelas e respeitando o agrupamento de causa-raiz.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM reviews")
    rows = [dict(r) for r in cursor.fetchall()]
    
    updated_count = 0
    for r in rows:
        root_cause = r.get("root_cause_id")
        if not root_cause:
            c = classify_text_issue(r.get("content", ""), r.get("title", ""), r.get("rating", 3))
            root_cause = c["id"]
        
        reply_text = generate_auto_reply_for_review(r, root_cause_id=root_cause)
        
        cursor.execute("""
            UPDATE reviews 
            SET root_cause_id = ?, 
                ai_suggested_response = ?
            WHERE id = ?
        """, (root_cause, reply_text, r["id"]))
        updated_count += 1
        
    conn.commit()
    conn.close()
    return {
        "success": True, 
        "message": f"Respostas automáticas padronizadas aplicadas com sucesso a todas as {updated_count} avaliações reais (Google Play e Apple Store, 1 a 5 estrelas)!",
        "count": updated_count
    }

# -------------------------------------------------------------------------
# Endpoints do Módulo Fale Conosco (Suporte Prodemge)
# -------------------------------------------------------------------------

@app.get("/api/support-tickets")
def api_get_support_tickets(
    search: str = "",
    status: str = "",
    user_type: str = "",
    category: str = "",
    root_cause_id: str = "",
    has_mantis: bool = False,
    limit: int = 50,
    offset: int = 0
):
    try:
        from database.db import get_support_tickets
        return get_support_tickets(
            search=search,
            status=status,
            user_type=user_type,
            category=category,
            root_cause_id=root_cause_id,
            has_mantis=has_mantis,
            limit=limit,
            offset=offset
        )
    except Exception as e:
        logger.error(f"Erro ao buscar chamados do Fale Conosco: {e}")
        return JSONResponse(status_code=500, content={"error": str(e), "tickets": [], "total": 0})

@app.get("/api/support-tickets/stats")
def api_get_support_tickets_stats():
    try:
        from database.db import get_support_tickets_stats
        return get_support_tickets_stats()
    except Exception as e:
        logger.error(f"Erro ao calcular estatísticas do Fale Conosco: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/support-tickets/analytics")
def api_get_support_tickets_analytics():
    """
    Retorna o diagnóstico analítico completo do Fale Conosco, cobrindo todos os 13 campos da planilha
    de forma 100% isolada e sem misturar com as avaliações das lojas (Google Play e Apple Store).
    """
    try:
        from database.db import get_fale_conosco_analytics
        return get_fale_conosco_analytics()
    except Exception as e:
        logger.error(f"Erro ao gerar analytics do Fale Conosco: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/support-tickets/complexity")
def api_get_support_tickets_complexity():
    """
    Retorna o diagnóstico de Causas-Raiz & Complexidade Técnica dos 862 Chamados do Fale Conosco,
    com matriz arquitetural Prodemge/SEE, correlação Mantis e recomendações de engenharia.
    Isolado 100% das avaliações das lojas móveis.
    """
    try:
        from analytics.fale_conosco_complexity import get_fale_conosco_complexity_diagnostic
        return get_fale_conosco_complexity_diagnostic()
    except Exception as e:
        logger.error(f"Erro ao gerar diagnóstico de complexidade do Fale Conosco: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/api/support-tickets/import")
async def api_import_support_tickets(file: UploadFile = File(...)):
    try:
        from collector.fale_conosco_importer import import_fale_conosco_file
        content = await file.read()
        res = import_fale_conosco_file(content, filename=file.filename or "")
        return res
    except Exception as e:
        logger.error(f"Erro ao importar planilha do Fale Conosco: {e}")
        return JSONResponse(status_code=500, content={"success": False, "message": f"Erro ao processar arquivo: {str(e)}"})

@app.post("/api/support-tickets/{ticket_id}/generate-reply")
def api_generate_support_ticket_reply(ticket_id: str, request: Request):
    user = getattr(request.state, "user", None)
    if not user or user.get("email", "").lower() != SUPER_ADMIN_EMAIL.lower():
        raise HTTPException(status_code=403, detail="Apenas o administrador oficial tem permissão para gerar respostas.")
    try:
        from database.db import get_connection, upsert_support_ticket
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM support_tickets WHERE id = ?", (ticket_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            raise HTTPException(status_code=404, detail="Chamado não encontrado")
        
        ticket = dict(row)
        desc = ticket.get('description', '')
        cat = ticket.get('category', '')
        student_name = ticket.get('student_name', 'Estudante')
        
        if "token" in cat.lower() or "token" in desc.lower():
            reply = f"Olá, {student_name}!\n\nIdentificamos o erro de token de autenticação no aplicativo Minha Escola MG (Mantis 0198268). Nossa equipe técnica da Prodemge já atuou na infraestrutura de autenticação. Por favor, limpe o cache do aplicativo em Configurações > Aplicativos > Minha Escola MG > Armazenamento > Limpar Cache e tente entrar novamente via Conta Gov.br ou e-mail institucional.\n\nAtenciosamente,\nEquipe de Suporte Minha Escola MG"
        elif "gov" in cat.lower() or "seg.id" in desc.lower():
            reply = f"Olá, {student_name}!\n\nEm relação à dificuldade de acesso via Gov.br / SEG.ID (Mantis 0198289), orientamos que certifique-se de que o CPF do estudante ou do responsável esteja devidamente vinculado no cadastro escolar da rede estadual. Caso continue sendo redirecionado para criação de conta, sugerimos acessar pelo navegador em idaluno.educacao.mg.gov.br para verificar o e-mail educacional.\n\nAtenciosamente,\nEquipe de Suporte Minha Escola MG"
        elif "escola" in cat.lower() or "troca" in cat.lower():
            reply = f"Olá, {student_name}!\n\nSobre a atualização de vínculo para sua nova escola estadual (Mantis 0198728), a sincronização entre o sistema DED da secretaria escolar e o aplicativo ocorre periodicamente. Solicitamos que confirme na secretaria da sua nova escola se sua matrícula já foi finalizada no sistema. Após a confirmação da escola, deslogue do aplicativo e faça um novo login para atualizar sua turma.\n\nAtenciosamente,\nEquipe de Suporte Minha Escola MG"
        else:
            reply = f"Olá, {student_name}!\n\nRecebemos sua solicitação enviada pelo Fale Conosco do Minha Escola MG. Em relação ao seu relato: \"{desc[:100]}...\", orientamos que caso se trate de consulta de notas, faltas ou emissão de histórico escolar, esses lançamentos dependem diretamente do registro da secretaria da sua escola. Para dúvidas cadastrais, procure a secretaria escolar. Para problemas técnicos no app, mantenha o aplicativo sempre atualizado na versão mais recente da loja.\n\nAtenciosamente,\nEquipe de Suporte Minha Escola MG"
            
        ticket['ai_suggested_reply'] = reply
        upsert_support_ticket(ticket)
        return {"success": True, "reply": reply}
    except Exception as e:
        logger.error(f"Erro ao gerar resposta para chamado {ticket_id}: {e}")
        return JSONResponse(status_code=500, content={"success": False, "message": str(e)})

def run_sync_and_auto_analyze():
    """Função para sincronizar e rodar auto-análise e auto-resposta se habilitada"""
    google_reviews = fetch_google_play_reviews(count=150)
    for r in google_reviews:
        upsert_review(r)
        
    apple_reviews = fetch_apple_store_reviews(max_pages=5)
    for r in apple_reviews:
        upsert_review(r)

    # Verifica se auto-resposta para 5 estrelas está ligada
    auto_5_stars = get_setting("auto_reply_5_stars_only", "false") == "true"
    auto_publish = get_setting("auto_publish_direct", "false") == "true"
    gemini_key = get_setting("gemini_api_key", "")

    if auto_5_stars:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM reviews WHERE rating = 5 AND status = 'pendente' LIMIT 50")
        five_star_reviews = [dict(r) for r in cursor.fetchall()]
        conn.close()

        for r in five_star_reviews:
            analysis = analyze_review(r, api_key=gemini_key)
            resp_text = analysis["suggested_response"]

            # Se configurado para publicar direto nas lojas
            if auto_publish:
                if r["store"] == "google":
                    sa = get_setting("google_play_service_account", "")
                    if sa:
                        reply_to_google_play(r["review_id"], resp_text, sa)
                elif r["store"] == "apple":
                    k_id = get_setting("apple_key_id", "")
                    iss = get_setting("apple_issuer_id", "")
                    p8 = get_setting("apple_private_key_p8", "")
                    if k_id and iss and p8:
                        reply_to_apple_store(r["review_id"], resp_text, k_id, iss, p8)

            update_review_analysis(
                review_id=r["id"],
                sentiment=analysis["sentiment"],
                category=analysis["category"],
                suggested_response=resp_text
            )
            update_review_status(r["id"], "respondida", resp_text)

def resolve_google_play_service_account() -> str:
    """Busca a chave em configurações, variáveis de ambiente (com tolerância a nomes), arquivos secretos do Render ou raiz"""
    # 1. Configurações salvas no app
    sa = get_setting("google_play_service_account", "")
    if sa:
        return sa
    
    # 2. Variáveis de ambiente possíveis
    candidate_keys = [
        "GOOGLE_PLAY_SERVICE_ACCOUNT_JSON",
        "GOOGLE_PLAY_SERVICE_ACCOUNT",
        "GOOGLE_SERVICE_ACCOUNT_JSON",
        "GOOGLE_SERVICE_ACCOUNT",
        "PLAY_SERVICE_ACCOUNT_JSON",
        "GOOGLE_APPLICATION_CREDENTIALS"
    ]
    for k in candidate_keys:
        val = os.environ.get(k, "").strip()
        if val:
            return val
            
    # Procura qualquer variável de ambiente que contenha SERVICE_ACCOUNT
    for k, v in os.environ.items():
        if "SERVICE_ACCOUNT" in k.upper() and v.strip().startswith("{"):
            return v.strip()

    # 3. Secret Files padrão do Render (/etc/secrets/) e arquivos locais
    candidate_files = [
        "/etc/secrets/google_play_service_account.json",
        "/etc/secrets/service_account.json",
        "/etc/secrets/google-play-key.json",
        "google_play_service_account.json"
    ]
    for p in candidate_files:
        if os.path.exists(p):
            return p
            
    if os.path.exists("/etc/secrets"):
        try:
            for fname in os.listdir("/etc/secrets"):
                if fname.endswith(".json"):
                    return os.path.join("/etc/secrets", fname)
        except Exception:
            pass

    return ""

@app.post("/api/sync")
def api_sync():
    google_sa = resolve_google_play_service_account()
    google_reviews = []
    if google_sa:
        try:
            from collector.google_play import fetch_google_play_api_reviews
            google_reviews = fetch_google_play_api_reviews(google_sa)
        except Exception as e:
            logger.error(f"Falha ao sincronizar via Google Play API: {e}")

    # 1. Coleta avaliações públicas para manter a base ampla
    public_reviews = fetch_google_play_reviews(count=150)
    new_google = 0
    for r in public_reviews:
        if upsert_review(r):
            new_google += 1

    # 2. Sobrescreve e enriquece com telemetria oficial da Google Play Developer API
    if google_reviews:
        for r in google_reviews:
            if upsert_review(r):
                new_google += 1
            
    apple_reviews = fetch_apple_store_reviews(max_pages=5)
    new_apple = 0
    for r in apple_reviews:
        if upsert_review(r):
            new_apple += 1

    # Analisa automaticamente novos itens que chegarem
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM reviews WHERE sentiment IS NULL")
    unanalyzed = [dict(r) for r in cursor.fetchall()]
    conn.close()
    
    gemini_key = get_setting("gemini_api_key", "")
    for r in unanalyzed:
        analysis = analyze_review(r, api_key=gemini_key)
        update_review_analysis(
            review_id=r["id"],
            sentiment=analysis["sentiment"],
            category=analysis["category"],
            suggested_response=analysis["suggested_response"]
        )

    stats = get_stats()
    new_total = new_google + new_apple
    if new_total > 0:
        msg = f"Sincronização concluída com sucesso! {new_total} novas avaliações foram mineradas e processadas ({new_google} Google Play, {new_apple} Apple Store). Total no banco: {stats['total']}."
    else:
        msg = f"Sincronização concluída com sucesso em tempo real! Suas {stats['total']} avaliações já estão 100% atualizadas com a Google Play Store e Apple App Store (nenhuma nova avaliação foi publicada por usuários nas últimas horas)."

    return {
        "success": True,
        "message": msg,
        "total": stats["total"],
        "new_reviews": new_total
    }

@app.get("/api/test-google-play-api")
def api_test_google_play():
    """Diagnóstico para validar se a Service Account está configurada e respondendo"""
    google_sa = resolve_google_play_service_account()
    if not google_sa:
        all_env_keys = [k for k in os.environ.keys() if any(sub in k.upper() for sub in ["GOOGLE", "PLAY", "SERVICE", "ACCOUNT"])]
        return {
            "configured": False,
            "status": "missing_variable",
            "message": "Nenhuma variável de ambiente de Service Account ou arquivo foi encontrado no servidor.",
            "detected_env_keys": all_env_keys
        }
    
    try:
        from collector.google_play import fetch_google_play_api_reviews
        reviews = fetch_google_play_api_reviews(google_sa, max_results=5)
        if reviews:
            return {
                "configured": True,
                "status": "success",
                "message": f"Conexão oficial com a Google Play Developer API funcionando perfeitamente! Foram coletadas {len(reviews)} avaliações com telemetria direta da loja.",
                "sample_devices": [f"{r.get('user_name')}: {r.get('device_brand')} {r.get('device_model')}" for r in reviews[:5]]
            }
        else:
            return {
                "configured": True,
                "status": "empty_or_failed",
                "message": "A chave existe, mas a chamada à API não retornou dados. Verifique permissões."
            }
    except Exception as e:
        return {
            "configured": True,
            "status": "error",
            "message": f"Erro ao conectar na Google Play API: {str(e)}"
        }

@app.post("/api/analyze/{review_id}")
def api_analyze_one(review_id: str, request: Request):
    user = get_current_user_from_request(request)
    user_email = (user.get("email") if user else "").lower()
    if user_email != "mgminhaescola@gmail.com" and (not user or user.get("role") != "admin"):
        raise HTTPException(
            status_code=403, 
            detail="Apenas o usuário autorizado mgminhaescola@gmail.com possui permissão para regenerar respostas com IA."
        )

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM reviews WHERE id = ?", (review_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        raise HTTPException(status_code=404, detail="Avaliação não encontrada")
        
    review_dict = dict(row)
    api_key = get_setting("gemini_api_key")
    analysis = analyze_review(review_dict, api_key=api_key)
    
    update_review_analysis(
        review_id=review_id,
        sentiment=analysis["sentiment"],
        category=analysis["category"],
        suggested_response=analysis["suggested_response"]
    )
    
    return {"success": True, "analysis": analysis}

@app.post("/api/analyze-pending")
def api_analyze_pending():
    """Analisa com IA todas as avaliações que ainda não têm sentimento/resposta calculados"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM reviews WHERE sentiment IS NULL LIMIT 100")
    pending = [dict(r) for r in cursor.fetchall()]
    conn.close()
    
    api_key = get_setting("gemini_api_key")
    analyzed_count = 0
    for r in pending:
        analysis = analyze_review(r, api_key=api_key)
        update_review_analysis(
            review_id=r["id"],
            sentiment=analysis["sentiment"],
            category=analysis["category"],
            suggested_response=analysis["suggested_response"]
        )
        analyzed_count += 1
        
    return {"message": f"{analyzed_count} avaliações analisadas com sucesso!"}

@app.post("/api/reply")
def api_reply(req: ReplyRequest, request: Request):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM reviews WHERE id = ?", (req.review_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Avaliação não encontrada")

    review = dict(row)
    published = False
    warning_message = None

    # Se o usuário solicitou publicação direta na loja ou auto-publish está ligado
    should_send_store = req.send_to_store or (get_setting("auto_publish_direct", "false") == "true")

    if should_send_store:
        user = get_current_user_from_request(request)
        user_email = (user.get("email") if user else "").lower()
        if user_email != "mgminhaescola@gmail.com" and (not user or user.get("role") != "admin"):
            raise HTTPException(
                status_code=403, 
                detail="Apenas o usuário autorizado mgminhaescola@gmail.com possui permissão para mandar publicar respostas na loja oficial."
            )

        if review["store"] == "google":
            sa_creds = resolve_google_play_service_account()
            if sa_creds and sa_creds.strip():
                success, msg = reply_to_google_play(review["review_id"], req.response_text, sa_creds)
                if success:
                    published = True
                else:
                    return {
                        "success": False,
                        "published_to_store": False,
                        "error_type": "api_error",
                        "message": f"Erro retornado pela Google Play API: {msg}"
                    }
            else:
                return {
                    "success": False,
                    "missing_credentials": True,
                    "store": "google",
                    "review_id": req.review_id,
                    "message": "Credenciais da Google Play (Service Account JSON da PRODEMGE) não configuradas! Conecte sua conta para mandar publicar diretamente na loja."
                }
        elif review["store"] == "apple":
            k_id = get_setting("apple_key_id", "")
            iss = get_setting("apple_issuer_id", "")
            p8 = get_setting("apple_private_key_p8", "")
            if k_id and iss and p8:
                success, msg = reply_to_apple_store(review["review_id"], req.response_text, k_id, iss, p8)
                if success:
                    published = True
                else:
                    return {
                        "success": False,
                        "published_to_store": False,
                        "error_type": "api_error",
                        "message": f"Erro retornado pela Apple App Store API: {msg}"
                    }
            else:
                return {
                    "success": False,
                    "missing_credentials": True,
                    "store": "apple",
                    "review_id": req.review_id,
                    "message": "Credenciais da Apple App Store (App Store Connect API) não configuradas! Conecte sua conta para mandar publicar diretamente na loja."
                }

    update_review_status(
        review_id=req.review_id,
        status="respondida",
        response_text=req.response_text,
        published_to_store=published
    )

    if published:
        return {
            "success": True,
            "published_to_store": True,
            "message": "🎉 Resposta enviada e publicada com sucesso na loja oficial!"
        }
    else:
        return {
            "success": True,
            "published_to_store": False,
            "message": "Resposta aprovada e salva no sistema local! Pronta para cópia ou envio."
        }

@app.post("/api/reviews/publish-batch")
def api_publish_batch(request: Request, store: Optional[str] = None):
    """
    Publica em lote todas as avaliações com respostas aprovadas que ainda não foram enviadas às lojas.
    Exclusivo para mgminhaescola@gmail.com
    """
    user = get_current_user_from_request(request)
    user_email = (user.get("email") if user else "").lower()
    if user_email != "mgminhaescola@gmail.com" and (not user or user.get("role") != "admin"):
        raise HTTPException(
            status_code=403, 
            detail="Apenas o usuário autorizado mgminhaescola@gmail.com possui permissão para publicar respostas em lote."
        )

    conn = get_connection()
    cursor = conn.cursor()
    
    query = """
        SELECT * FROM reviews 
        WHERE status = 'respondida' 
          AND (published_to_store = 0 OR published_to_store IS NULL)
          AND (local_response IS NOT NULL OR ai_suggested_response IS NOT NULL)
    """
    params = []
    if store and store != 'todas':
        query += " AND store = ?"
        params.append(store)
        
    cursor.execute(query, params)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    
    if not rows:
        return {
            "success": True,
            "message": "Nenhuma resposta pendente para publicar na loja. Todas já foram enviadas ou ainda não têm resposta.",
            "published_count": 0,
            "failed_count": 0
        }
        
    google_sa = resolve_google_play_service_account()
    apple_k_id = get_setting("apple_key_id", "")
    apple_iss = get_setting("apple_issuer_id", "")
    apple_p8 = get_setting("apple_private_key_p8", "")
    
    has_google = any(r["store"] == "google" for r in rows)
    has_apple = any(r["store"] == "apple" for r in rows)
    
    if has_google and not (google_sa and google_sa.strip()):
        return {
            "success": False,
            "missing_credentials": True,
            "store": "google",
            "message": f"Para mandar publicar as {len(rows)} respostas na Google Play, configure o arquivo JSON da Service Account da PRODEMGE."
        }
        
    if has_apple and not (apple_k_id and apple_iss and apple_p8):
        return {
            "success": False,
            "missing_credentials": True,
            "store": "apple",
            "message": f"Para mandar publicar as {len(rows)} respostas na App Store, configure as credenciais do App Store Connect."
        }
        
    published_count = 0
    failed_count = 0
    errors = []
    
    for r in rows:
        resp_text = r.get("local_response") or r.get("ai_suggested_response") or ""
        if not resp_text:
            continue
            
        success = False
        msg = ""
        if r["store"] == "google":
            success, msg = reply_to_google_play(r["review_id"], resp_text, google_sa)
        elif r["store"] == "apple":
            success, msg = reply_to_apple_store(r["review_id"], resp_text, apple_k_id, apple_iss, apple_p8)
            
        if success:
            update_review_status(
                review_id=r["id"],
                status="respondida",
                response_text=resp_text,
                published_to_store=True
            )
            published_count += 1
        else:
            failed_count += 1
            errors.append(f"{r.get('user_name')}: {msg}")
            
    return {
        "success": True,
        "published_count": published_count,
        "failed_count": failed_count,
        "message": f"Publicação em lote finalizada: {published_count} respostas enviadas para as lojas com sucesso! (Falhas: {failed_count})",
        "errors": errors[:5]
    }

@app.post("/api/ignore/{review_id}")
def api_ignore(review_id: str):
    update_review_status(review_id=review_id, status="ignorada")
    return {"success": True, "message": "Avaliação marcada como ignorada."}

@app.get("/api/settings")
def api_get_settings():
    settings = get_all_settings()
    masked = dict(settings)
    if masked.get("gemini_api_key"):
        k = masked["gemini_api_key"]
        masked["gemini_api_key_masked"] = k[:6] + "..." + k[-4:] if len(k) > 10 else "***"
        
    sa = settings.get("google_play_service_account", "")
    masked["google_connected"] = bool(sa and sa.strip())
    if sa and sa.strip():
        try:
            sa_data = json.loads(sa)
            masked["google_client_email"] = sa_data.get("client_email", "")
        except Exception:
            masked["google_client_email"] = "Configurado"
            
    k_id = settings.get("apple_key_id", "")
    iss = settings.get("apple_issuer_id", "")
    p8 = settings.get("apple_private_key_p8", "")
    masked["apple_connected"] = bool(k_id and iss and p8)
    
    support_val = settings.get("support_contact_url") or settings.get("support_email") or "https://forms.cloud.microsoft/r/JmZhSzXtwG"
    masked["support_email"] = support_val
    masked["support_contact_url"] = support_val

    return masked

@app.post("/api/settings")
def api_update_settings(req: SettingsRequest):
    if req.gemini_api_key is not None:
        set_setting("gemini_api_key", req.gemini_api_key)
    if req.google_play_service_account is not None:
        set_setting("google_play_service_account", req.google_play_service_account)
    if req.apple_key_id is not None:
        set_setting("apple_key_id", req.apple_key_id)
    if req.apple_issuer_id is not None:
        set_setting("apple_issuer_id", req.apple_issuer_id)
    if req.apple_private_key_p8 is not None:
        set_setting("apple_private_key_p8", req.apple_private_key_p8)
    if req.auto_publish_direct is not None:
        set_setting("auto_publish_direct", req.auto_publish_direct)
    if req.auto_reply_5_stars_only is not None:
        set_setting("auto_reply_5_stars_only", req.auto_reply_5_stars_only)
    if req.auto_sync_interval is not None:
        set_setting("auto_sync_interval", req.auto_sync_interval)
    if req.support_email is not None:
        set_setting("support_email", req.support_email)
        set_setting("support_contact_url", req.support_email)
    if req.apple_downloads_custom is not None:
        set_setting("apple_downloads_custom", req.apple_downloads_custom.strip())
    return {"success": True, "message": "Configurações salvas com sucesso!"}

@app.post("/api/settings/test-gemini")
def api_test_gemini(req: TestKeyRequest):
    api_key = req.key if (req.key and req.key.strip()) else get_setting("gemini_api_key", "")
    ok, msg = test_gemini_key(api_key)
    return {"success": ok, "message": msg}

@app.post("/api/settings/test-google")
def api_test_google(req: TestGoogleRequest):
    sa = req.service_account if (req.service_account and req.service_account.strip()) else get_setting("google_play_service_account", "")
    ok, msg = test_google_play_credentials(sa)
    return {"success": ok, "message": msg}

@app.post("/api/settings/test-apple")
def api_test_apple(req: TestAppleRequest):
    k_id = req.key_id if (req.key_id and req.key_id.strip()) else get_setting("apple_key_id", "")
    iss = req.issuer_id if (req.issuer_id and req.issuer_id.strip()) else get_setting("apple_issuer_id", "")
    p8 = req.private_key_p8 if (req.private_key_p8 and req.private_key_p8.strip()) else get_setting("apple_private_key_p8", "")
    ok, msg = test_apple_credentials(k_id, iss, p8)
    return {"success": ok, "message": msg}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("web.app:app", host="127.0.0.1", port=8000, reload=True)
