import sqlite3
import re
from collections import Counter, defaultdict
from datetime import datetime
from typing import Dict, List, Any, Optional

from database.db import get_connection

FC_ROOT_CAUSES_CONFIG = [
    {
        "id": "oauth_gov_br",
        "name": "Falha na Autenticação Gov.br & SEG.ID",
        "short_name": "OAuth Gov.br / SEG.ID",
        "icon": "fa-shield-halved",
        "color": "#ef4444", # rose-500
        "bg_color": "#fef2f2",
        "severity": "Crítica",
        "severity_level": 3,
        "complexity": "Alta",
        "complexity_score": 3,
        "architectural_layer": "Autenticação Federal Gov.br / SEG.ID Prodemge",
        "layer_id": "govbr_auth",
        "resolution_scope": "Hotfix de Gateway OAuth / Tolerância a Timeout",
        "mantis_codes": ["Mantis 0198289", "Mantis 0198367", "Mantis 0198369", "Mantis 0199117", "Mantis 0199115", "Mantis 0199114"],
        "recommendation": "Otimizar tempo de resposta do handshake OAuth 2.0 com o Gov.br, mitigar loops de redirecionamento para o navegador e detalhar na tela do usuário pendências cadastrais de CPF na Receita Federal.",
        "engineering_details": "Ajustar cabeçalhos de autorização e ciclo de vida do token de autorização trocado entre o gateway SEG.ID Prodemge e o Provedor Federal MGI. Tratar HTTP 401/403 com mensagens didáticas."
    },
    {
        "id": "token_jwt_sessao",
        "name": "Expiração de Token JWT & Sessão Interrompida",
        "short_name": "Token JWT / Sessão",
        "icon": "fa-key",
        "color": "#dc2626", # red-600
        "bg_color": "#fef2f2",
        "severity": "Crítica",
        "severity_level": 3,
        "complexity": "Alta",
        "complexity_score": 3,
        "architectural_layer": "Backend Prodemge (APIs REST & Sessão JWT)",
        "layer_id": "backend_prodemge",
        "resolution_scope": "Refresh Token Automático / Tratamento de Concorrência",
        "mantis_codes": ["Mantis 0198268", "Mantis 0198274", "Mantis 0198269"],
        "recommendation": "Implementar renovação silenciosa de token (Refresh Token) no app móvel antes do término da vigência e blindar APIs contra race conditions quando múltiplas requisições paralelas falham com token nulo.",
        "engineering_details": "O erro 'cesão finalizada' e 'erro de token' decorre do término da janela de expiração do JWT sem mecanismo de revalidação em segundo plano no app móvel."
    },
    {
        "id": "ded_notas_boletim",
        "name": "Sincronização Diário Escolar (DED) & Boletim/Faltas",
        "short_name": "Sincronização DED / Notas",
        "icon": "fa-graduation-cap",
        "color": "#f59e0b", # amber-500
        "bg_color": "#fffbeb",
        "severity": "Alta",
        "severity_level": 2,
        "complexity": "Média",
        "complexity_score": 2,
        "architectural_layer": "Integração DED / SIMADE (Sincronização de Dados)",
        "layer_id": "ded_integration",
        "resolution_scope": "Cache Local no App & Fila de Sincronização Assíncrona",
        "mantis_codes": ["Mantis 0197546"],
        "recommendation": "Criar cache offline no aplicativo com exibição clara do carimbo da 'última sincronização com a escola' e disparar fila de atualização assíncrona entre o banco DED e as APIs do Minha Escola MG.",
        "engineering_details": "Muitos relatos de 'boletim zerado' ocorrem durante o fechamento de bimestre, quando a carga simultânea no banco DED gera lentidão ou timeout na entrega dos dados aos alunos."
    },
    {
        "id": "crash_loop_inicial",
        "name": "Falha de Inicialização / App Não Abre / Loop na Splash",
        "short_name": "Crash / App Não Abre",
        "icon": "fa-triangle-exclamation",
        "color": "#ea580c", # orange-600
        "bg_color": "#fff7ed",
        "severity": "Crítica",
        "severity_level": 3,
        "complexity": "Média",
        "complexity_score": 2,
        "architectural_layer": "Frontend Mobile (Android / iOS)",
        "layer_id": "mobile_frontend",
        "resolution_scope": "Correção de Splash Screen / Limpeza de Cache Corrompido",
        "mantis_codes": ["Mantis 0198290", "Mantis 0198601", "Mantis 0198600", "Mantis 0198361"],
        "recommendation": "Blindar a inicialização com tratamento global de exceções, rotina automática de expurgo de armazenamento local corrompido em atualizações e desacoplamento de chamadas síncronas na splash screen.",
        "engineering_details": "Usuários relatam que o app fecha sozinho ao abrir ou retorna em loop infinito à tela inicial. Indica travamento de thread principal ou falha ao desserializar credenciais em storage."
    },
    {
        "id": "login_generico_bloqueio",
        "name": "Dificuldade de Acesso & Bloqueio Geral de Conta",
        "short_name": "Bloqueio Geral de Acesso",
        "icon": "fa-lock",
        "color": "#6366f1", # indigo-500
        "bg_color": "#eef2ff",
        "severity": "Alta",
        "severity_level": 2,
        "complexity": "Baixa",
        "complexity_score": 1,
        "architectural_layer": "Camada de Autenticação / Suporte ao Usuário",
        "layer_id": "user_support",
        "resolution_scope": "Telas Instrutivas / Diagnóstico Rápido de Credenciais",
        "mantis_codes": [],
        "recommendation": "Inserir assistente interativo de login no próprio app orientando o usuário passo a passo sobre formato de email institucional (@aluno.mg.gov.br) e verificação do status da conta.",
        "engineering_details": "Chamados onde o usuário relata genericamente não conseguir entrar ou ter a conta bloqueada, comumente resolvidos via validação de formato de dados ou reset de tentativa excessiva."
    },
    {
        "id": "recuperacao_senha_idaluno",
        "name": "Recuperação de Senha & Consulta de ID do Aluno",
        "short_name": "Senha & Portal idaluno",
        "icon": "fa-id-card",
        "color": "#8b5cf6", # purple-500
        "bg_color": "#f5f3ff",
        "severity": "Média",
        "severity_level": 2,
        "complexity": "Baixa",
        "complexity_score": 1,
        "architectural_layer": "Suporte N1 / Portal idaluno",
        "layer_id": "user_support",
        "resolution_scope": "Autoatendimento idaluno.mg.gov.br",
        "mantis_codes": [],
        "recommendation": "Ampliar a autonomia do portal idaluno com recuperação de senha por SMS/WhatsApp do responsável e busca instantânea de ID por nome completo e data de nascimento.",
        "engineering_details": "Grande volume de chamados de alunos que não sabem seu ID ou não receberam código de redefinição de senha por e-mail."
    },
    {
        "id": "inconsistencia_cpf_ded",
        "name": "Cadastro e Vínculo de CPF no SIMADE / DED",
        "short_name": "Vínculo de CPF no DED",
        "icon": "fa-user-slash",
        "color": "#e11d48", # rose-600
        "bg_color": "#fff1f2",
        "severity": "Alta",
        "severity_level": 2,
        "complexity": "Média",
        "complexity_score": 2,
        "architectural_layer": "Base Cadastral SIMADE / Secretaria Escolar",
        "layer_id": "cadastral_simade",
        "resolution_scope": "Validador Cadastral / Conciliação SIMADE",
        "mantis_codes": ["Mantis 0198288", "Mantis 198288"],
        "recommendation": "Disponibilizar validador no portal idaluno que informe se o CPF digitado diverge da certidão cadastrada na escola ou se a matrícula está arquivada no SIMADE.",
        "engineering_details": "Casos onde o aluno digita dados corretos mas o backend responde 'Aluno não encontrado' porque na secretaria o CPF não foi preenchido ou está com dígitos trocados."
    },
    {
        "id": "troca_escola_matricula",
        "name": "Vínculo com Escola Antiga / Troca de Unidade Escolar",
        "short_name": "Troca de Escola / Matrícula",
        "icon": "fa-school",
        "color": "#0ea5e9", # sky-500
        "bg_color": "#f0f9ff",
        "severity": "Média",
        "severity_level": 2,
        "complexity": "Média",
        "complexity_score": 2,
        "architectural_layer": "Regras de Negócio SIMADE",
        "layer_id": "cadastral_simade",
        "resolution_scope": "Filtro de Ano Letivo & Matrícula Ativa na API",
        "mantis_codes": ["Mantis 0198728", "Mantis 0198727", "Mantis 0198729"],
        "recommendation": "Assegurar que as consultas das APIs do app filtrem apenas a matrícula com status 'Ativa' no ano letivo vigente, ocultando escolas anteriores após transferência.",
        "engineering_details": "Alunos transferidos continuam enxergando notas da escola antiga ou não localizam a turma atual no app por concorrência de múltiplos registros de matrícula no SIMADE."
    },
    {
        "id": "demandas_secretaria_n1",
        "name": "Demandas Administrativas da Secretaria (Fora de TI)",
        "short_name": "Secretaria / Documentos (Fora TI)",
        "icon": "fa-file-lines",
        "color": "#64748b", # slate-500
        "bg_color": "#f8fafc",
        "severity": "Baixa",
        "severity_level": 1,
        "complexity": "Baixa",
        "complexity_score": 1,
        "architectural_layer": "Secretaria Escolar / Atendimento Presencial",
        "layer_id": "secretaria_adm",
        "resolution_scope": "Triagem no Formulário / Encaminhamento para a Escola",
        "mantis_codes": [],
        "recommendation": "Incluir filtro prévio no formulário do Fale Conosco informando que pedidos de declaração, atestado e histórico escolar devem ser solicitados diretamente à secretaria da escola.",
        "engineering_details": "Chamados que não envolvem bugs no software, mas sobrecarregam a equipe de TI da Prodemge com solicitações administrativas escolares."
    },
    {
        "id": "compatibilidade_dispositivo",
        "name": "Compatibilidade de Aparelho & Versão de SO",
        "short_name": "Compatibilidade Aparelho / WebView",
        "icon": "fa-mobile-screen-button",
        "color": "#14b8a6", # teal-500
        "bg_color": "#f0fdf4",
        "severity": "Alta",
        "severity_level": 2,
        "complexity": "Média",
        "complexity_score": 2,
        "architectural_layer": "Compatibilidade Mobile (Android <= 12 / WebViews)",
        "layer_id": "mobile_frontend",
        "resolution_scope": "Polyfills & Atualização de WebView",
        "mantis_codes": [],
        "recommendation": "Reduzir o peso do bundle da aplicação, manter suporte a WebViews do Android 10-12 e incluir tutorial para atualização da WebView na Google Play Store.",
        "engineering_details": "Aparelhos com Android antigo que não conseguem carregar a tela de autenticação Gov.br por falta de suporte aos padrões web modernos na WebView do sistema."
    },
    {
        "id": "pe_de_meia_mec",
        "name": "Programa Pé-de-Meia & Jornada do Estudante (MEC)",
        "short_name": "Pé-de-Meia (MEC)",
        "icon": "fa-coins",
        "color": "#10b981", # emerald-500
        "bg_color": "#ecfdf5",
        "severity": "Média",
        "severity_level": 2,
        "complexity": "Média",
        "complexity_score": 2,
        "architectural_layer": "Integração Federal MEC / FNDE",
        "layer_id": "federal_mec",
        "resolution_scope": "Esclarecimento Cadastral / Informações da SEE",
        "mantis_codes": [],
        "recommendation": "Adicionar banner explicativo no aplicativo informando os critérios de elegibilidade do Pé-de-Meia e direcionando dúvidas para o aplicativo oficial Jornada do Estudante (MEC).",
        "engineering_details": "Dúvidas sobre recebimento do incentivo federal, dependentes de envio mensal da frequência escolar pela SEE/MG ao Ministério da Educação."
    },
    {
        "id": "outros_suporte",
        "name": "Dúvidas Gerais & Suporte Operacional",
        "short_name": "Suporte Geral & Dúvidas",
        "icon": "fa-circle-question",
        "color": "#94a3b8", # slate-400
        "bg_color": "#f8fafc",
        "severity": "Baixa",
        "severity_level": 1,
        "complexity": "Baixa",
        "complexity_score": 1,
        "architectural_layer": "Suporte Operacional N1",
        "layer_id": "user_support",
        "resolution_scope": "Base de Conhecimento / FAQ",
        "mantis_codes": [],
        "recommendation": "Consolidar central de ajuda dentro do aplicativo respondendo dúvidas frequentes sobre uso do diário e datas de avaliações.",
        "engineering_details": "Demandas gerais e mensagens informativas sem caracterização de incidente técnico ou indisponibilidade de sistema."
    }
]

ARCHITECTURAL_LAYERS_CONFIG = [
    {
        "layer_id": "govbr_auth",
        "name": "Autenticação Federal Gov.br / SEG.ID Prodemge",
        "icon": "fa-shield-halved",
        "color": "#dc2626",
        "scope": "Integração Externa (MGI) & Gateway Estadual",
        "team": "Equipe de Autenticação Prodemge & SEG.ID"
    },
    {
        "layer_id": "backend_prodemge",
        "name": "Backend Prodemge (APIs REST & Sessão JWT)",
        "icon": "fa-server",
        "color": "#e11d48",
        "scope": "Serviços Centrais, Tokens & Banco de Dados",
        "team": "Engenharia de Backend Prodemge"
    },
    {
        "layer_id": "ded_integration",
        "name": "Integração DED / SIMADE (Sincronização de Dados)",
        "icon": "fa-database",
        "color": "#f59e0b",
        "scope": "Sincronização Diário Escolar Digital",
        "team": "Equipe DED / SIMADE Prodemge"
    },
    {
        "layer_id": "mobile_frontend",
        "name": "Frontend Mobile (App Minha Escola MG)",
        "icon": "fa-mobile-screen",
        "color": "#ea580c",
        "scope": "Aplicativo Android / iOS & WebViews",
        "team": "Desenvolvimento Mobile Prodemge"
    },
    {
        "layer_id": "cadastral_simade",
        "name": "Base Cadastral SIMADE / Secretaria Escolar",
        "icon": "fa-address-card",
        "color": "#8b5cf6",
        "scope": "Dados de Matrícula, Turmas e CPFs de Alunos",
        "team": "Gestão de Cadastro Escolar SEE/MG"
    },
    {
        "layer_id": "user_support",
        "name": "Suporte ao Usuário / Autoatendimento N1",
        "icon": "fa-headset",
        "color": "#6366f1",
        "scope": "Portal idaluno, Reset de Senhas e Dúvidas",
        "team": "Central de Atendimento SEE/MG & Suporte N1"
    },
    {
        "layer_id": "secretaria_adm",
        "name": "Secretaria Escolar / Atendimento Presencial",
        "icon": "fa-building-columns",
        "color": "#64748b",
        "scope": "Históricos, Declarações e Atendimento Físico",
        "team": "Secretarias das Unidades Escolares"
    },
    {
        "layer_id": "federal_mec",
        "name": "Integração Federal MEC / FNDE",
        "icon": "fa-landmark",
        "color": "#10b981",
        "scope": "Programas Nacionais (Pé-de-Meia)",
        "team": "MEC & FNDE Federal"
    }
]

def classify_fc_ticket(description: str, internal_analysis: str = "", category: str = "") -> Dict[str, Any]:
    """
    Classifica um chamado do Fale Conosco com base em:
    1. Anotação técnica do Mantis Prodemge
    2. Termos descritos pelo usuário
    3. Categoria preliminar da planilha
    """
    desc_str = (description or "").strip()
    ana_str = (internal_analysis or "").strip()
    cat_str = (category or "").strip()
    text = f"{desc_str} {ana_str} {cat_str}".lower()

    # Prioridade 1: Código Mantis explícito
    if any(m in ana_str for m in ["0198289", "0198367", "0198369", "0199117", "0199115", "0199114"]):
        chosen_id = "oauth_gov_br"
    elif any(m in ana_str for m in ["0198268", "0198274", "0198269"]):
        chosen_id = "token_jwt_sessao"
    elif any(m in ana_str for m in ["0197546"]):
        chosen_id = "ded_notas_boletim"
    elif any(m in ana_str for m in ["0198288", "198288"]):
        chosen_id = "inconsistencia_cpf_ded"
    elif any(m in ana_str for m in ["0198290", "0198601", "0198600", "0198361"]):
        chosen_id = "crash_loop_inicial"
    elif any(m in ana_str for m in ["0198728", "0198727", "0198729"]):
        chosen_id = "troca_escola_matricula"
    # Prioridade 2: Gatilhos fortes de texto
    elif any(k in text for k in ["token", "sessao finalizada", "sesso finalizada", "cesao finalizada", "ceso finalizada", "erro de token"]):
        chosen_id = "token_jwt_sessao"
    elif any(k in text for k in ["gov.br", "gov", "seg.id", "conta gov", "login gov", "login pelo gov"]):
        chosen_id = "oauth_gov_br"
    elif any(k in text for k in ["boletim", "nota", "notas", "bimestre", "frequencia", "frequncia", "falta", "faltas", "presena", "presenca"]):
        chosen_id = "ded_notas_boletim"
    elif any(k in text for k in ["cpf", "cpf no vinculado", "cpf nao vinculado", "no encontrado no ded", "nao encontrado no ded", "no cadastrado", "nao cadastrado"]):
        chosen_id = "inconsistencia_cpf_ded"
    elif any(k in text for k in ["pe de meia", "p de meia", "p-de-meia", "pe-de-meia", "pedemeia", "jornada do estudante"]):
        chosen_id = "pe_de_meia_mec"
    elif any(k in text for k in ["troca de escola", "escola antiga", "transferencia", "transferncia", "mudei de escola", "troquei de escola"]):
        chosen_id = "troca_escola_matricula"
    elif any(k in text for k in ["historico", "histrico", "declarao", "declaracao", "secretaria", "atestado", "documento"]):
        chosen_id = "demandas_secretaria_n1"
    elif any(k in text for k in ["compativel", "compatvel", "redmi", "samsung", "motorola", "dispositivo", "aparelho", "verso do android", "versao do android"]):
        chosen_id = "compatibilidade_dispositivo"
    elif any(k in text for k in ["senha", "redefinir", "recuperar", "idaluno", "id do aluno", "meu id", "cdigo", "codigo", "bloqueado", "bloqueada", "desativada"]):
        chosen_id = "recuperacao_senha_idaluno"
    elif any(k in text for k in ["no abre", "nao abre", "fecha", "fechando", "trava", "travando", "tela preta", "tela branca", "loop", "reinicia"]):
        chosen_id = "crash_loop_inicial"
    # Prioridade 3: Categorias da planilha original
    elif cat_str == "Notas e Frequência":
        chosen_id = "ded_notas_boletim"
    elif cat_str == "Login Gov.br / SEG.ID":
        chosen_id = "oauth_gov_br"
    elif cat_str == "Instabilidade / Falha no App":
        chosen_id = "crash_loop_inicial"
    elif cat_str == "Erro de Token de Autenticação":
        chosen_id = "token_jwt_sessao"
    elif cat_str == "Recuperação de Senha / ID":
        chosen_id = "recuperacao_senha_idaluno"
    elif cat_str == "Cadastro de Aluno / CPF Não Vinculado":
        chosen_id = "inconsistencia_cpf_ded"
    elif cat_str == "Documentação / Secretaria":
        chosen_id = "demandas_secretaria_n1"
    elif cat_str == "Vínculo / Troca de Escola":
        chosen_id = "troca_escola_matricula"
    elif cat_str == "Pé-de-Meia / Jornada Estudante":
        chosen_id = "pe_de_meia_mec"
    elif cat_str == "Compatibilidade de Dispositivo":
        chosen_id = "compatibilidade_dispositivo"
    # Prioridade 4: Menção genérica de entrada
    elif any(k in text for k in ["entrar", "entra", "acessar", "acesso", "login", "conta"]):
        chosen_id = "login_generico_bloqueio"
    else:
        chosen_id = "outros_suporte"

    # Encontra configuração correspondente
    for cfg in FC_ROOT_CAUSES_CONFIG:
        if cfg["id"] == chosen_id:
            return cfg

    return FC_ROOT_CAUSES_CONFIG[-1]


def backfill_support_tickets_root_causes() -> int:
    """
    Garante que a coluna root_cause_id existe na tabela support_tickets
    e preenche todos os chamados com a causa-raiz técnica correta.
    Retorna o número de chamados atualizados.
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Adiciona coluna se não existir
    try:
        cursor.execute("ALTER TABLE support_tickets ADD COLUMN root_cause_id TEXT;")
        conn.commit()
    except Exception:
        pass

    cursor.execute("SELECT id, description, internal_analysis, category, root_cause_id FROM support_tickets")
    rows = cursor.fetchall()
    updated = 0

    for r in rows:
        t_id, desc, ana, cat, curr_rc = r[0], r[1], r[2], r[3], r[4]
        classified = classify_fc_ticket(desc or "", ana or "", cat or "")
        new_rc = classified["id"]
        if curr_rc != new_rc:
            cursor.execute("UPDATE support_tickets SET root_cause_id = ? WHERE id = ?", (new_rc, t_id))
            updated += 1

    conn.commit()
    conn.close()
    return updated


def get_fale_conosco_complexity_diagnostic() -> Dict[str, Any]:
    """
    Gera o diagnóstico completo de Causas-Raiz e Complexidade Técnica dos 862 Chamados do Fale Conosco,
    com matriz arquitetural, correlação com o Mantis da Prodemge, níveis de severidade e
    recomendações técnicas detalhadas para a engenharia de software da Prodemge e da SEE/MG.
    Isolado 100% dos dados de avaliações das lojas móveis.
    """
    # Garante que os registros estão classificados e indexados
    backfill_support_tickets_root_causes()

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, ticket_date, user_type, student_name, student_cpf, student_id,
               school_name, description, city, status, internal_analysis, category, root_cause_id
        FROM support_tickets
        ORDER BY ticket_date DESC
    """)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()

    total_tickets = len(rows)
    if total_tickets == 0:
        return {
            "summary": {
                "total_tickets": 0, "high_critical_complexity_count": 0, "high_critical_complexity_pct": 0,
                "medium_complexity_count": 0, "medium_complexity_pct": 0, "low_complexity_count": 0,
                "low_complexity_pct": 0, "average_complexity_score": 0, "critical_severity_count": 0,
                "critical_severity_pct": 0, "mantis_linked_count": 0, "mantis_linked_pct": 0,
                "external_federal_deps_count": 0, "external_federal_deps_pct": 0, "administrative_off_it_count": 0
            },
            "cause_matrix": [],
            "architectural_layers": [],
            "severity_complexity_matrix": {},
            "mantis_summary": []
        }

    tickets_by_cause = defaultdict(list)
    mantis_counts_overall = Counter()
    layer_counts = Counter()
    severity_counts = Counter()
    complexity_counts = Counter()
    complexity_scores_sum = 0

    cfg_by_id = {c["id"]: c for c in FC_ROOT_CAUSES_CONFIG}

    for t in rows:
        rc_id = t.get("root_cause_id") or "outros_suporte"
        cfg = cfg_by_id.get(rc_id, FC_ROOT_CAUSES_CONFIG[-1])

        tickets_by_cause[rc_id].append(t)
        layer_counts[cfg["layer_id"]] += 1
        severity_counts[cfg["severity"]] += 1
        complexity_counts[cfg["complexity"]] += 1
        complexity_scores_sum += cfg["complexity_score"]

        # Análise de Mantis
        ana = (t.get("internal_analysis") or "").strip()
        if ana and "mantis" in ana.lower():
            mantis_matches = re.findall(r"Mantis\s*#?([0-9]+)", ana, re.IGNORECASE)
            if mantis_matches:
                for m in mantis_matches:
                    mantis_counts_overall[f"Mantis {m}"] += 1
            else:
                mantis_counts_overall[ana] += 1

    # Monta a matriz detalhada por causa-raiz
    cause_matrix = []
    for cfg in FC_ROOT_CAUSES_CONFIG:
        rc_id = cfg["id"]
        c_tickets = tickets_by_cause.get(rc_id, [])
        count = len(c_tickets)
        pct = round((count / total_tickets) * 100, 1) if total_tickets > 0 else 0.0

        # Mantis específicos desta causa
        c_mantis = Counter()
        for t in c_tickets:
            ana = (t.get("internal_analysis") or "").strip()
            if ana and "mantis" in ana.lower():
                matches = re.findall(r"Mantis\s*#?([0-9]+)", ana, re.IGNORECASE)
                for m in matches:
                    c_mantis[f"Mantis {m}"] += 1

        # Amostra de chamados reais (3 mais recentes)
        samples = []
        for t in c_tickets[:3]:
            desc_text = (t.get("description") or "").strip()
            snippet = (desc_text[:140] + ("..." if len(desc_text) > 140 else "")) if desc_text else "(Chamado sem descrição textual)"
            t_date = t.get("ticket_date") or ""
            formatted_date = t_date[:10] if t_date else "-"
            if len(t_date) >= 16:
                try:
                    dt_obj = datetime.strptime(t_date[:19], "%Y-%m-%d %H:%M:%S")
                    formatted_date = dt_obj.strftime("%d/%m/%Y às %H:%M")
                except Exception:
                    pass

            samples.append({
                "id": t["id"],
                "date": formatted_date,
                "student_name": t.get("student_name") or "Aluno",
                "user_type": t.get("user_type") or "Aluno",
                "school": t.get("school_name") or "Não informada",
                "city": t.get("city") or "Não informada",
                "status": t.get("status") or "Pendente",
                "internal_analysis": t.get("internal_analysis") or "",
                "description_snippet": snippet,
                "has_attachment": bool(t.get("attachment_url"))
            })

        cause_matrix.append({
            "id": cfg["id"],
            "name": cfg["name"],
            "short_name": cfg["short_name"],
            "icon": cfg["icon"],
            "color": cfg["color"],
            "bg_color": cfg["bg_color"],
            "severity": cfg["severity"],
            "severity_level": cfg["severity_level"],
            "complexity": cfg["complexity"],
            "complexity_score": cfg["complexity_score"],
            "architectural_layer": cfg["architectural_layer"],
            "layer_id": cfg["layer_id"],
            "resolution_scope": cfg["resolution_scope"],
            "total_count": count,
            "percentage": pct,
            "mantis_list": [{"code": k, "count": v} for k, v in c_mantis.most_common(5)],
            "recommendation": cfg["recommendation"],
            "engineering_details": cfg["engineering_details"],
            "sample_tickets": samples
        })

    # Ordena causas por quantidade decrescente
    cause_matrix.sort(key=lambda x: x["total_count"], reverse=True)

    # Camadas arquiteturais agregadas
    layers_data = []
    layer_cfg_by_id = {l["layer_id"]: l for l in ARCHITECTURAL_LAYERS_CONFIG}
    for l_id, l_cnt in layer_counts.most_common():
        l_cfg = layer_cfg_by_id.get(l_id, {
            "name": l_id,
            "icon": "fa-layer-group",
            "color": "#64748b",
            "scope": "Camada Técnica",
            "team": "Equipe de TI"
        })
        layers_data.append({
            "layer_id": l_id,
            "name": l_cfg["name"],
            "icon": l_cfg["icon"],
            "color": l_cfg["color"],
            "scope": l_cfg["scope"],
            "team": l_cfg["team"],
            "count": l_cnt,
            "percentage": round((l_cnt / total_tickets) * 100, 1)
        })

    # Matriz Cruzada de Gravidade x Complexidade (Classificação P1, P2, P3, P4)
    p1_count = 0 # Crítica + Alta Complexidade (Hotfixes urgentes)
    p2_count = 0 # Crítica + Média OU Alta + Alta/Média
    p3_count = 0 # Média + Baixa/Média
    p4_count = 0 # Baixa + Baixa (Admin / Não-TI)

    for c in cause_matrix:
        cnt = c["total_count"]
        if c["severity"] == "Crítica" and c["complexity"] == "Alta":
            p1_count += cnt
        elif c["severity"] == "Crítica" or (c["severity"] == "Alta" and c["complexity"] in ("Alta", "Média")):
            p2_count += cnt
        elif c["severity"] == "Média" or c["complexity"] == "Média":
            p3_count += cnt
        else:
            p4_count += cnt

    # KPIs executivos
    high_critical = complexity_counts.get("Alta", 0)
    medium = complexity_counts.get("Média", 0)
    low = complexity_counts.get("Baixa", 0)
    critical_sev = severity_counts.get("Crítica", 0)
    mantis_linked = sum(mantis_counts_overall.values())
    ext_deps = layer_counts.get("govbr_auth", 0) + layer_counts.get("federal_mec", 0)
    admin_off = layer_counts.get("secretaria_adm", 0)

    avg_complexity = round(complexity_scores_sum / total_tickets, 2) if total_tickets > 0 else 0.0

    return {
        "summary": {
            "total_tickets": total_tickets,
            "high_critical_complexity_count": high_critical,
            "high_critical_complexity_pct": round((high_critical / total_tickets) * 100, 1),
            "medium_complexity_count": medium,
            "medium_complexity_pct": round((medium / total_tickets) * 100, 1),
            "low_complexity_count": low,
            "low_complexity_pct": round((low / total_tickets) * 100, 1),
            "average_complexity_score": avg_complexity,
            "critical_severity_count": critical_sev,
            "critical_severity_pct": round((critical_sev / total_tickets) * 100, 1),
            "mantis_linked_count": mantis_linked,
            "mantis_linked_pct": round((mantis_linked / total_tickets) * 100, 1),
            "external_federal_deps_count": ext_deps,
            "external_federal_deps_pct": round((ext_deps / total_tickets) * 100, 1),
            "administrative_off_it_count": admin_off,
            "administrative_off_it_pct": round((admin_off / total_tickets) * 100, 1),
            "priorities": {
                "p1_urgent_hotfix": {"count": p1_count, "pct": round((p1_count / total_tickets) * 100, 1), "label": "P1 - Bloqueante / Hotfix de Gateway e JWT"},
                "p2_structural": {"count": p2_count, "pct": round((p2_count / total_tickets) * 100, 1), "label": "P2 - Alta Gravidade / Sincronização DED e Crash"},
                "p3_improvements": {"count": p3_count, "pct": round((p3_count / total_tickets) * 100, 1), "label": "P3 - Moderada / Autoatendimento e Cadastro"},
                "p4_operational": {"count": p4_count, "pct": round((p4_count / total_tickets) * 100, 1), "label": "P4 - Operacional / Triagem N1 e Secretaria"}
            }
        },
        "cause_matrix": cause_matrix,
        "architectural_layers": layers_data,
        "mantis_summary": [{"code": k, "count": v} for k, v in mantis_counts_overall.most_common(12)],
        "recommendations_roadmap": [
            {
                "priority": "P1 - Imediato",
                "badge_color": "bg-rose-100 text-rose-800 border-rose-200",
                "title": "Renovação Silenciosa de JWT e Handshake Resiliente no Gov.br",
                "target": "Backend Prodemge & Gateway SEG.ID",
                "impact": f"Elimina {high_critical} chamados críticos ({round((high_critical/total_tickets)*100, 1)}% da base)",
                "action": "Implementar interceptor HTTP no app para auto-refresh de tokens JWT antes da expiração e aumentar tolerância de timeout do gateway Prodemge no OAuth 2.0."
            },
            {
                "priority": "P2 - Curto Prazo",
                "badge_color": "bg-amber-100 text-amber-900 border-amber-200",
                "title": "Cache Inteligente de Boletim e Blindagem de Splash Screen",
                "target": "Frontend Mobile & Integração DED",
                "impact": f"Resolve {medium} chamados de alta visibilidade ({round((medium/total_tickets)*100, 1)}% da base)",
                "action": "Armazenar última versão válida das notas no dispositivo com indicação de sincronização e adicionar tratamento de exceção para evitar fechamento inesperado do app."
            },
            {
                "priority": "P3 - Médio Prazo",
                "badge_color": "bg-blue-100 text-blue-800 border-blue-200",
                "title": "Validador Cadastral de CPF e Autoatendimento de Senhas no idaluno",
                "target": "Portal idaluno & Suporte N1",
                "impact": f"Desafoga {low} chamados operacionais ({round((low/total_tickets)*100, 1)}% da base)",
                "action": "Permitir auto-recuperação de senhas institucionais e consulta de ID de aluno sem dependência de formulário de suporte, com alerta sobre dados na secretaria da escola."
            }
        ]
    }
