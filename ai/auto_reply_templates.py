import re
from typing import Dict, Any, List, Optional
from database.db import get_connection, get_setting
from ai.analyzer import has_problem_context, strip_support_link
from config import get_app_name, get_organization_name, get_support_url, get_domain

OFFICIAL_SUPPORT_FORM = get_support_url()

def enforce_char_limit(text: str, max_chars: int = 350) -> str:
    """
    Garante que a resposta nunca exceda o limite rígido da loja (350 caracteres, contando espaços),
    preservando sempre o link do canal de suporte e a coerência das frases.
    """
    if not text:
        return ""
    text = re.sub(r'\s+', ' ', text).strip()
    if len(text) <= max_chars:
        return text

    # Localiza o link oficial no final (se houver)
    support_match = re.search(r'(Canal de (?:Suporte|Atendimento) Oficial:\s*(?:👉\s*)?https?://\S+)', text)
    if support_match:
        support_part = support_match.group(1).strip()
        body_part = text[:support_match.start()].strip()
    else:
        support_part = ""
        body_part = text

    available_for_body = max_chars - (len(support_part) + 1 if support_part else 0)

    if len(body_part) > available_for_body:
        cut = body_part[:available_for_body]
        last_punct = max(cut.rfind('.'), cut.rfind('!'), cut.rfind('?'))
        if last_punct > 50:
            body_part = cut[:last_punct + 1].strip()
        else:
            last_space = cut.rfind(' ')
            if last_space > 50:
                body_part = cut[:last_space].strip() + '.'
            else:
                body_part = cut.strip()

    final_text = f"{body_part} {support_part}".strip() if support_part else body_part
    if len(final_text) > max_chars:
        final_text = final_text[:max_chars].strip()

    return final_text

PROBLEM_TEMPLATES_CONFIG = {
    "login_sessao_recorrente": {
        "id": "login_sessao_recorrente",
        "name": "Instabilidade de Login, Conexão e Sessão",
        "description": "Usuários que enfrentam múltiplas tentativas para conseguir logar, aplicativo que desloga sozinho, tela de login em loop ou falhas de conexão/autenticação.",
        "keywords": ["login", "logar", "faça login", "tentativas", "desloga", "desconecta", "toda hora sai", "toda vez pede login", "não entra", "não consigo entrar", "não consigo acessar", "erro ao entrar", "erro de login", "não passa da tela de login", "trava no login", "sessão expirada", "token", "não autentica"],
        "severity": "Crítica",
        "complexity": "Média",
        "templates": {
            "critical": "Olá, {nome}! Sentimos pela instabilidade de login no {app_name}. Por favor, limpe o cache do app em Configurações > Aplicativos. Verifique na loja se há atualizações para o app. Se persistir, acione o Canal de Suporte Oficial: 👉 {canal_contato}",
            "moderate": "Olá, {nome}! Agradecemos pelo relato. Estamos trabalhando para otimizar o login do {app_name}. Mantenha o app atualizado na {loja}. Se precisar de auxílio, conte conosco no Canal de Suporte Oficial: 👉 {canal_contato}",
            "positive": "Olá, {nome}! Muito obrigado pela avaliação de {estrelas} estrelas no {app_name}! Continuamos trabalhando para garantir um acesso rápido e seguro a todos."
        }
    },
    "gov_br_cpf": {
        "id": "gov_br_cpf",
        "name": "Falha no Gov.br e Vínculo de CPF",
        "description": "Usuários com dificuldade para autenticar via Gov.br, erro de 'CPF não encontrado', dados cadastrais divergentes ou falha na integração com o Dataprev/SIMAVE.",
        "keywords": ["gov.br", "gov", "cpf", "conta gov", "vincular", "vínculo", "não reconhece cpf", "dados inválidos", "cpf incorreto", "erro de autenticação", "login gov"],
        "severity": "Crítica",
        "complexity": "Alta",
        "templates": {
            "critical": "Olá, {nome}! Sentimos pela dificuldade com Gov.br. Confirme se seu CPF e data de nascimento estão atualizados na escola. Verifique na loja se há atualizações para o app. Se persistir, acesse o Canal de Suporte Oficial: 👉 {canal_contato}",
            "moderate": "Olá, {nome}! O login Gov.br exige dados alinhados com o cadastro escolar. Caso continue com instabilidade, orientamos relatar pelo Canal de Suporte Oficial: 👉 {canal_contato}",
            "positive": "Olá, {nome}! Muito obrigado pela avaliação de {estrelas} estrelas no {app_name}! Trabalhamos constantemente na integração segura com o Gov.br. Conte conosco!"
        }
    },
    "senha_recuperacao": {
        "id": "senha_recuperacao",
        "name": "Recuperação de Senha e Redefinição",
        "description": "Usuários que esqueceram a senha, não recebem o código de redefinição por e-mail, senha bloqueada ou erro genérico de acesso.",
        "keywords": ["esqueci a senha", "esqueci minha senha", "redefinir", "recuperar senha", "código", "trocar senha", "senha inválida", "não envia email", "email não chega", "senha", "bloqueada", "não consigo entrar"],
        "severity": "Alta",
        "complexity": "Média",
        "templates": {
            "critical": "Olá, {nome}! Sentimos pela dificuldade na senha. Verifique a caixa de Spam. Se o e-mail cadastrado estiver desatualizado, procure a escola. Verifique atualizações na loja ou acione o Canal de Suporte Oficial: 👉 {canal_contato}",
            "moderate": "Olá, {nome}! Para redefinir sua senha com segurança, certifique-se de que o e-mail cadastrado na escola é o atual. Persistindo o erro, registre no Canal de Suporte Oficial: 👉 {canal_contato}",
            "positive": "Olá, {nome}! Agradecemos pela avaliação positiva de {estrelas} estrelas! Nosso objetivo é garantir acesso ágil e descomplicado ao {app_name}."
        }
    },
    "lentidao_tela_preta": {
        "id": "lentidao_tela_preta",
        "name": "Lentidão Extrema e Tela Preta",
        "keywords": ["tela preta", "tela branca", "lento", "lentidão", "travando", "trava", "carregando infinito", "roda roda", "não passa da tela", "atualização piorou", "ruim", "péssimo", "odiei", "horrível"],
        "description": "Relatos de aplicativo travando, carregamento infinito, tela preta ao abrir ou lentidão intensa após as atualizações mais recentes.",
        "severity": "Alta",
        "complexity": "Média",
        "templates": {
            "critical": "Olá, {nome}! Lamentamos a lentidão no {app_name}. Limpe o cache do app nas configurações do aparelho. Verifique na loja se há atualizações pendentes para o app. Se persistir, relate no Canal de Suporte Oficial: 👉 {canal_contato}",
            "moderate": "Olá, {nome}! Obrigado pelo aviso. Otimizações de velocidade são lançadas com frequência. Mantenha o app atualizado e, se precisar de auxílio, acione o Canal de Suporte Oficial: 👉 {canal_contato}",
            "positive": "Olá, {nome}! Muito obrigado pela avaliação de {estrelas} estrelas! Estamos sempre otimizando a velocidade do {app_name} para oferecer a melhor experiência."
        }
    },
    "boletim_notas": {
        "id": "boletim_notas",
        "name": "Boletim em Branco e Notas Ausentes",
        "keywords": ["nota", "notas", "boletim", "bimestre", "não carrega nota", "boletim em branco", "nota zerada", "não aparece nota", "nota sumiu", "lançamento de notas"],
        "description": "Problemas de visualização do boletim escolar, notas do bimestre que não carregam ou aparecem em branco/zeradas.",
        "severity": "Alta",
        "complexity": "Alta",
        "templates": {
            "critical": "Olá, {nome}! Entendemos a importância do boletim. As notas dependem do lançamento no Diário Escolar Digital. Verifique na loja se há atualizações do app ou consulte sua escola. Canal de Suporte Oficial: 👉 {canal_contato}",
            "moderate": "Olá, {nome}! A atualização das notas no app ocorre conforme o lançamento oficial pelos professores. Havendo dúvidas ou divergências, relate pelo Canal de Suporte Oficial: 👉 {canal_contato}",
            "positive": "Olá, {nome}! Ficamos muito felizes com a sua avaliação positiva! O acompanhamento das notas é fundamental e estamos empenhados em manter tudo sincronizado. Bons estudos!"
        }
    },
    "faltas_frequencia": {
        "id": "faltas_frequencia",
        "name": "Faltas e Frequência Divergentes",
        "keywords": ["falta", "faltas", "frequência", "presença", "falta errada", "computou falta", "sem presença"],
        "description": "Divergência entre as faltas reais do estudante e o que está computado no extrato de frequência do aplicativo.",
        "severity": "Média",
        "complexity": "Média",
        "templates": {
            "critical": "Olá, {nome}! O extrato de frequência reflete os registros do Diário Escolar Digital. Verifique na loja se há atualizações do app. Se houver divergências não resolvidas pela escola, acione o Canal de Suporte Oficial: 👉 {canal_contato}",
            "moderate": "Olá, {nome}! O controle de faltas reflete o Diário Escolar Digital. Caso note divergências na frequência, a escola poderá verificar, ou você pode relatar no Canal de Suporte Oficial: 👉 {canal_contato}",
            "positive": "Olá, {nome}! Muito obrigado pela avaliação de {estrelas} estrelas! O controle de frequência é essencial para o acompanhamento escolar. Conte conosco!"
        }
    },
    "crash_fechamento": {
        "id": "crash_fechamento",
        "name": "Fechamento Inesperado e Travamento",
        "description": "Aplicativo fecha sozinho logo após abrir ou durante o uso (Crash).",
        "keywords": ["fecha sozinho", "fechando", "fechou", "crash", "parou de funcionar", "fechando sozinho", "app fecha"],
        "severity": "Crítica",
        "complexity": "Alta",
        "templates": {
            "critical": "Olá, {nome}! Pedimos desculpas pelo fechamento do app. Nossa equipe está atuando nas correções. Limpe o cache e verifique na loja se há atualizações para o app. Se persistir, relate no Canal de Suporte Oficial: 👉 {canal_contato}",
            "moderate": "Olá, {nome}! Lamentamos o fechamento inesperado. Mantenha seu app atualizado na {loja}. Se o erro continuar, informe os detalhes do seu aparelho no Canal de Suporte Oficial: 👉 {canal_contato}",
            "positive": "Olá, {nome}! Agradecemos pela avaliação de {estrelas} estrelas! Trabalhamos para que o {app_name} seja sempre estável e rápido."
        }
    },
    "acesso_responsaveis": {
        "id": "acesso_responsaveis",
        "name": "Acesso de Pais e Responsáveis",
        "description": "Mães, pais ou responsáveis que não conseguem vincular os filhos, visualizar múltiplos estudantes ou alternar entre dependentes.",
        "keywords": ["filho", "filha", "responsável", "mãe", "pai", "dependentes", "vincular filho", "dois filhos", "não vejo meu filho", "outro filho"],
        "severity": "Alta",
        "complexity": "Média",
        "templates": {
            "critical": "Olá, {nome}! Para acesso de responsáveis, o vínculo deve estar regularizado na secretaria escolar. Verifique na loja se há atualizações para o app ou registre no Canal de Suporte Oficial: 👉 {canal_contato}",
            "moderate": "Olá, {nome}! Para vincular mais de um filho, o CPF do responsável deve constar no cadastro de cada estudante na escola. Havendo dúvidas, acione o Canal de Suporte Oficial: 👉 {canal_contato}",
            "positive": "Olá, {nome}! Ficamos muito felizes em apoiar o acompanhamento escolar dos seus filhos pelo {app_name}! Conte sempre com a nossa equipe."
        }
    },
    "outros_problemas": {
        "id": "outros_problemas",
        "name": "Problemas Gerais e Dificuldades Técnicas",
        "description": "Queixas genéricas sem menção a causa-raiz específica.",
        "keywords": ["ruim", "péssimo", "horrível", "não funciona", "lixo", "arrumem", "bosta", "desinstalando", "odio", "raiva", "vergonha"],
        "severity": "Média",
        "complexity": "Baixa",
        "templates": {
            "critical": "Olá, {nome}! Agradecemos pelo relato no {app_name}. Verifique na loja se há atualizações para o app. Para que nossa equipe analise e solucione seu caso, registre no Canal de Suporte Oficial: 👉 {canal_contato}",
            "moderate": "Olá, {nome}! Obrigado pelo feedback sobre o {app_name}. Mantenha o app sempre atualizado. Caso precise de suporte, acione o Canal de Suporte Oficial: 👉 {canal_contato}",
            "positive": "Olá, {nome}! Muito obrigado pela avaliação de {estrelas} estrelas no {app_name}! Estamos à disposição."
        }
    },
    "elogios_satisfacao": {
        "id": "elogios_satisfacao",
        "name": "Elogios, Gratidão e Avaliações Positivas",
        "description": "Avaliações elogiando a praticidade, notas altas e satisfação.",
        "keywords": ["ótimo", "otimo", "muito bom", "excelente", "maravilhoso", "parabéns", "parabens", "adorei", "gostei", "top", "perfeito", "ajuda muito", "prático", "facil", "fácil"],
        "severity": "Baixa",
        "complexity": "Baixa",
        "templates": {
            "critical": "Olá, {nome}! Obrigado pelo retorno sobre o {app_name}. Verifique na loja se há atualizações para o app. Se precisar de apoio, conte com o Canal de Suporte Oficial: 👉 {canal_contato}",
            "moderate": "Olá, {nome}! Agradecemos pela avaliação! Continuamos trabalhando para melhorar sua experiência no {app_name}.",
            "positive": "Olá, {nome}! Ficamos muito felizes com suas {estrelas} estrelas no {app_name}! Nosso compromisso é facilitar sua rotina diária. Muito obrigado!"
        }
    },
    "geral_outros": {
        "id": "geral_outros",
        "name": "Atendimento Geral e Outros Serviços",
        "description": "Dúvidas gerais, elogios ou solicitações sobre os serviços do Governo.",
        "keywords": ["governo", "serviço", "dúvida", "informação", "mg app", "cidadão"],
        "severity": "Baixa",
        "complexity": "Baixa",
        "templates": {
            "critical": "Olá, {nome}! Agradecemos pelo contato. Verifique na loja se há atualizações pendentes para o app. Se tiver dúvidas ou dificuldades, acesse o Canal de Atendimento Oficial: 👉 {canal_contato}",
            "moderate": "Olá, {nome}! Obrigado pela avaliação. Mantenha o {app_name} atualizado. Para dúvidas ou solicitações, acesse o Canal de Atendimento Oficial: 👉 {canal_contato}",
            "positive": "Olá, {nome}! Muito obrigado pela avaliação de {estrelas} estrelas no {app_name}! Estamos sempre à disposição."
        }
    },
    "usabilidade_interface": {
        "id": "usabilidade_interface",
        "name": "Usabilidade e Nova Interface",
        "description": "Comentários sobre a facilidade ou dificuldade de usar o app.",
        "keywords": ["layout", "visual", "interface", "design", "botão", "tela", "cores"],
        "severity": "Baixa",
        "complexity": "Baixa",
        "templates": {
            "critical": "Olá, {nome}! Agradecemos pelas sugestões no {app_name}. Verifique na loja se há atualizações para o app. Envie sua sugestão no Canal de Atendimento Oficial: 👉 {canal_contato}",
            "moderate": "Olá, {nome}! Obrigado pelo retorno sobre a navegação do {app_name}. Suas sugestões nos ajudam a evoluir continuamente.",
            "positive": "Olá, {nome}! Que ótimo saber que gostou da interface do {app_name}! Muito obrigado pelo feedback positivo!"
        }
    },
    "agendamento_uai_cin": {
        "id": "agendamento_uai_cin",
        "name": "Agendamento de Serviços (UAI, Carteira de Identidade / CIN)",
        "description": "Usuários tentando agendar emissão de CIN, RG ou serviços nas unidades UAI.",
        "keywords": ["uai", "agendar", "agendamento", "carteira de identidade", "cin", "rg", "vagas", "não tem vaga"],
        "severity": "Alta",
        "complexity": "Alta",
        "templates": {
            "critical": "Olá, {nome}! Sentimos pela dificuldade no agendamento. Novas vagas são abertas diariamente pelo sistema. Verifique atualizações na loja ou acesse o Canal de Atendimento Oficial: 👉 {canal_contato}",
            "moderate": "Olá, {nome}! Agradecemos o relato sobre o agendamento. Se persistir a dificuldade, registre no Canal de Atendimento Oficial: 👉 {canal_contato}",
            "positive": "Olá, {nome}! Ficamos muito felizes em ajudar no seu agendamento pelo {app_name}! Conte sempre conosco."
        }
    },
    "veiculos_detran_ipva": {
        "id": "veiculos_detran_ipva",
        "name": "Consulta de Veículos, CRLV e IPVA",
        "description": "Dificuldades em emitir CRLV, consultar IPVA ou taxas de veículos.",
        "keywords": ["crlv", "veículo", "veiculo", "ipva", "multa", "detran", "documento do carro", "licenciamento"],
        "severity": "Alta",
        "complexity": "Média",
        "templates": {
            "critical": "Olá, {nome}! Para consultas de veículos e IPVA, verifique se os dados estão corretos. Verifique atualizações na loja ou relate no Canal de Atendimento Oficial: 👉 {canal_contato}",
            "moderate": "Olá, {nome}! As informações de veículos são sincronizadas com a base estadual. Se houver divergências, acione o Canal de Atendimento Oficial: 👉 {canal_contato}",
            "positive": "Olá, {nome}! Muito obrigado pela avaliação de {estrelas} estrelas! A emissão de documentos pelo {app_name} veio para facilitar a sua vida."
        }
    },
    "login_govbr_biometria": {
        "id": "login_govbr_biometria",
        "name": "Autenticação Gov.br e Biometria Facial",
        "description": "Dificuldade no login do Gov.br ou reconhecimento facial no MG App.",
        "keywords": ["biometria", "reconhecimento facial", "gov.br", "gov", "foto", "selfie", "não reconhece", "cpf"],
        "severity": "Crítica",
        "complexity": "Alta",
        "templates": {
            "critical": "Olá, {nome}! A autenticação Gov.br com biometria depende da base federal. Limpe o cache e verifique atualizações na loja. Havendo erro, acesse o Canal de Atendimento Oficial: 👉 {canal_contato}",
            "moderate": "Olá, {nome}! Para biometria Gov.br, mantenha o app atualizado na {loja}. Persistindo o erro, acione o Canal de Atendimento Oficial: 👉 {canal_contato}",
            "positive": "Olá, {nome}! Muito obrigado pela avaliação de {estrelas} estrelas! A segurança do seu acesso pelo Gov.br é prioridade."
        }
    },
    "farmacia_minas_remedios": {
        "id": "farmacia_minas_remedios",
        "name": "Farmácia de Minas e Medicamentos",
        "description": "Consultas sobre medicamentos do SUS, Farmácia de Minas e disponibilidade.",
        "keywords": ["remédio", "remedio", "medicamento", "farmácia de minas", "farmacia", "insulina", "receita"],
        "severity": "Média",
        "complexity": "Baixa",
        "templates": {
            "critical": "Olá, {nome}! A disponibilidade de medicamentos reflete o estoque das farmácias regionais. Verifique atualizações na loja ou consulte o Canal de Atendimento Oficial: 👉 {canal_contato}",
            "moderate": "Olá, {nome}! Para informações sobre medicamentos, acompanhe no {app_name} ou registre dúvidas no Canal de Atendimento Oficial: 👉 {canal_contato}",
            "positive": "Olá, {nome}! Que ótimo saber que o {app_name} auxiliou na sua consulta à Farmácia de Minas! Obrigado pela avaliação!"
        }
    },
    "estabilidade_erros_app": {
        "id": "estabilidade_erros_app",
        "name": "Instabilidade, Erro Inesperado e Travamentos",
        "description": "Relatos de tela branca, travamentos ou mensagens de 'tente novamente mais tarde'.",
        "keywords": ["erro inesperado", "tente novamente", "fora do ar", "não abre", "tela branca", "travando", "lento"],
        "severity": "Alta",
        "complexity": "Média",
        "templates": {
            "critical": "Olá, {nome}! Lamentamos a instabilidade. Nossa equipe está atuando nas correções. Limpe o cache e verifique atualizações na loja. Se persistir, acesse o Canal de Atendimento Oficial: 👉 {canal_contato}",
            "moderate": "Olá, {nome}! Agradecemos pelo reporte técnico. Trabalhamos na estabilidade dos servidores. Se o erro continuar, relate pelo Canal de Atendimento Oficial: 👉 {canal_contato}",
            "positive": "Olá, {nome}! Agradecemos pela avaliação de {estrelas} estrelas! Continuamos investindo na estabilidade e velocidade do {app_name}."
        }
    },
    "usabilidade_navegacao": {
        "id": "usabilidade_navegacao",
        "name": "Usabilidade, Busca e Nova Interface",
        "description": "Comentários sobre dificuldade de encontrar serviços, busca (lupa) ou sugestões de interface.",
        "keywords": ["atualização", "layout", "piorou", "dificil", "lupa", "buscar", "complicado"],
        "severity": "Média",
        "complexity": "Baixa",
        "templates": {
            "critical": "Olá, {nome}! Agradecemos pelo feedback sobre a navegação no {app_name}. Verifique atualizações na loja ou registre sugestões detalhadas no Canal de Atendimento Oficial: 👉 {canal_contato}",
            "moderate": "Olá, {nome}! Obrigado por suas sugestões de melhoria no {app_name}. Elas são muito importantes para o aprimoramento contínuo.",
            "positive": "Olá, {nome}! Muito obrigado pelo retorno positivo sobre a facilidade de uso do {app_name}! Trabalhamos diariamente para facilitar a sua vida."
        }
    }
}

def generate_auto_reply_for_review(review: Dict[str, Any], root_cause_id: Optional[str] = None) -> str:
    """
    Gera a resposta automática com base na Causa-Raiz e na Nota (Estrelas).
    REGRAS CRÍTICAS:
    1. O texto final NUNCA pode ultrapassar 350 caracteres (contando espaços), que é o limite da loja!
    2. Para TODAS as avaliações de 1 a 3 estrelas: SEMPRE inclui o Canal de Suporte Oficial: 👉 {canal_contato}.
    3. Para notas abaixo de 3 estrelas (1 e 2 estrelas): SEMPRE inclui a orientação de verificar atualizações na loja.
    4. Para 5 estrelas: NUNCA inclui canal de suporte nem link.
    """
    target_app = (review.get("app_id") or (lambda: (__import__('config').get_app_id()))()).strip()

    user_name = review.get("user_name", "").strip()
    if not user_name or user_name.lower() in ("usuário", "usuario", "usuario google play", "usuário apple"):
        greeting_name = "estudante" if target_app == "minha_escola_mg" else "cidadão"
    else:
        # Se o nome for muito longo, usa apenas o primeiro nome para economizar caracteres
        parts = user_name.split()
        greeting_name = parts[0] if parts else user_name

    rating = int(review.get("rating", 3))
    content = review.get("content", "")
    store = review.get("store", "google")
    store_name = "Google Play Store" if store == "google" else "Apple App Store"

    canal_contato = get_support_url(target_app)
    if "@" in canal_contato or not canal_contato.strip():
        canal_contato = "https://forms.cloud.microsoft/r/JmZhSzXtwG" if target_app == "minha_escola_mg" else "https://www.mg.gov.br/atendimento"
    canal_contato = canal_contato.strip()

    is_problem = has_problem_context(content, rating)

    from analytics.complexity import classify_text_issue
    if not root_cause_id or root_cause_id not in PROBLEM_TEMPLATES_CONFIG:
        app_domain = get_domain(target_app)
        c = classify_text_issue(content, review.get("title", ""), rating, domain=app_domain)
        root_cause_id = c["id"]

    cfg = PROBLEM_TEMPLATES_CONFIG.get(root_cause_id, PROBLEM_TEMPLATES_CONFIG["outros_problemas"])

    if rating >= 5:
        is_problem = False
        template = cfg["templates"]["positive"]
    elif rating <= 2:
        template = cfg["templates"]["critical"]
    elif rating == 3:
        template = cfg["templates"]["moderate"]
    else:
        # 4 estrelas
        if is_problem:
            template = cfg["templates"]["moderate"]
        else:
            template = cfg["templates"]["positive"]

    from config import get_app_name as cfg_get_app_name, get_organization_name as cfg_get_org_name
    app_name = cfg_get_app_name(target_app)
    org_name = cfg_get_org_name()
    formatted = template.format(
        nome=greeting_name,
        loja=store_name,
        canal_contato=canal_contato,
        email=canal_contato,
        estrelas=rating,
        app_name=app_name,
        org_name=org_name
    )

    # Injeção de verificação de atualizações para avaliações abaixo de 3 estrelas (1 e 2 estrelas)
    if rating < 3:
        if not re.search(r'atualizaç|atualizar', formatted, re.IGNORECASE):
            update_text = "Verifique na loja se há atualizações para o app."
            if "Canal de Suporte Oficial:" in formatted:
                formatted = formatted.replace("Canal de Suporte Oficial:", f"{update_text} Canal de Suporte Oficial:")
            elif "Canal de Atendimento Oficial:" in formatted:
                formatted = formatted.replace("Canal de Atendimento Oficial:", f"{update_text} Canal de Atendimento Oficial:")
            else:
                formatted = f"{formatted} {update_text}"

    # Verificação estrita de segurança para 5 estrelas
    if rating >= 5:
        formatted = strip_support_link(formatted)
    elif (rating <= 3 or is_problem) and (canal_contato not in formatted and "forms.cloud.microsoft" not in formatted and "mg.gov.br" not in formatted):
        formatted = f"{formatted} Canal de Suporte Oficial: 👉 {canal_contato}"
    elif not is_problem and rating >= 4:
        formatted = strip_support_link(formatted)

    # Limpeza contra qualquer e-mail acidental
    formatted = re.sub(r'[\w\.-]+@[\w\.-]+\.\w+', '', formatted).strip()

    # REGRA FINAL INEGOCIÁVEL: Clampa estritamente para no máximo 350 caracteres
    return enforce_char_limit(formatted, max_chars=350)
