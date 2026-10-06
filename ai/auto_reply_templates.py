import re
from typing import Dict, Any, List, Optional
from database.db import get_connection, get_setting
from ai.analyzer import has_problem_context

# Configuração e descrição detalhada de cada causa-raiz com templates para todas as estrelas
OFFICIAL_SUPPORT_FORM = "https://forms.cloud.microsoft/r/JmZhSzXtwG"

PROBLEM_TEMPLATES_CONFIG = {
    "gov_br_cpf": {
        "id": "gov_br_cpf",
        "name": "Falha no Gov.br e Vínculo de CPF",
        "description": "Usuários com dificuldade para autenticar via Gov.br, erro de 'CPF não encontrado', dados cadastrais divergentes ou falha na integração com o Dataprev/SIMAVE.",
        "keywords": ["gov.br", "gov", "cpf", "conta gov", "vincular", "vínculo", "não reconhece cpf", "dados inválidos", "cpf incorreto", "erro de autenticação", "login gov"],
        "severity": "Crítica",
        "complexity": "Alta",
        "templates": {
            "critical": "Olá, {nome}! Sentimos muito pelo transtorno no acesso Gov.br. Esse erro geralmente ocorre por divergência cadastral entre a base federal e a secretaria da escola. Recomendamos confirmar se o seu CPF e data de nascimento estão atualizados junto à coordenação da sua escola. Se o problema persistir, pedimos que acesse o Canal de Suporte Oficial: 👉 {canal_contato}",
            "moderate": "Olá, {nome}! Agradecemos pelo seu retorno. O login com Gov.br exige que os dados cadastrais estejam 100% alinhados com o cadastro escolar. Caso o acesso continue instável, orientamos relatar pelo Canal de Suporte Oficial: 👉 {canal_contato}",
            "positive": "Olá, {nome}! Muito obrigado pela avaliação de {estrelas} estrelas no Minha Escola MG! Trabalhamos constantemente na integração com o Gov.br para manter seu acesso seguro e prático. Conte conosco!"
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
            "critical": "Olá, {nome}! Sentimos muito pela dificuldade na recuperação da senha. Verifique se a mensagem não foi para a caixa de Spam/Lixo Eletrônico. Caso o e-mail cadastrado na escola seja antigo ou inacessível, solicite a atualização junto à secretaria da sua escola ou registre no Canal de Suporte Oficial: 👉 {canal_contato}",
            "moderate": "Olá, {nome}! Agradecemos pelo seu contato. Para recuperar sua senha com segurança, certifique-se de que o e-mail cadastrado na escola é o seu e-mail atual. Havendo qualquer divergência ou persistindo o erro, consulte a secretaria da escola ou registre no Canal de Suporte Oficial: 👉 {canal_contato}",
            "positive": "Olá, {nome}! Agradecemos pela avaliação positiva de {estrelas} estrelas! Nosso objetivo é garantir que seu acesso ao Minha Escola MG seja sempre ágil e descomplicado. Um abraço da equipe!"
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
            "critical": "Olá, {nome}! Lamentamos muito pela lentidão ou travamento no Minha Escola MG. Nossa equipe técnica da Prodemge lançou atualizações para otimização de performance. Recomendamos atualizar o app para a versão mais recente na {loja} e limpar o cache nas configurações do aparelho. Se persistir, informe os detalhes no Canal de Suporte Oficial: 👉 {canal_contato}",
            "moderate": "Olá, {nome}! Obrigado por nos avisar sobre a lentidão. Estamos trabalhando continuamente na estabilidade do aplicativo. Certifique-se de manter o app atualizado e, caso precise de auxílio, relate no Canal de Suporte Oficial: 👉 {canal_contato}",
            "positive": "Olá, {nome}! Muito obrigado pela avaliação de {estrelas} estrelas! Estamos sempre otimizando a velocidade do Minha Escola MG para oferecer a melhor experiência a você. Conte com a gente!"
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
            "critical": "Olá, {nome}! Entendemos a importância de acompanhar o boletim. As notas exibidas no Minha Escola MG dependem da sincronização e homologação feitas pelos professores no Diário Escolar Digital (DED). Caso o bimestre já tenha encerrado e as notas não apareçam, consulte a coordenação da sua escola ou relate no Canal de Suporte Oficial: 👉 {canal_contato}",
            "moderate": "Olá, {nome}! Agradecemos pelo seu relato. A atualização das notas no aplicativo ocorre conforme os professores realizam o lançamento oficial no sistema escolar. Havendo dúvidas ou divergências não solucionadas pela escola, relate pelo Canal de Suporte Oficial: 👉 {canal_contato}",
            "positive": "Olá, {nome}! Ficamos muito felizes com a sua avaliação positiva! O acompanhamento das notas é fundamental e estamos empenhados em manter tudo sempre sincronizado para você. Bons estudos!"
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
            "critical": "Olá, {nome}! Agradecemos pelo alerta sobre a frequência. O registro de faltas e presenças no app é alimentado pelos professores no Diário Escolar Digital. Se houver divergências não solucionadas pela secretaria da escola, relate os detalhes no Canal de Suporte Oficial: 👉 {canal_contato}",
            "moderate": "Olá, {nome}! O controle de faltas reflete o Diário Escolar Digital. Caso note divergências na frequência, a coordenação da sua escola poderá verificar e retificar os registros, ou você pode registrar no Canal de Suporte Oficial: 👉 {canal_contato}",
            "positive": "Olá, {nome}! Muito obrigado pela avaliação de {estrelas} estrelas! O controle de frequência é essencial para o acompanhamento escolar. Conte conosco!"
        }
    },
    "crash_fechamento": {
        "id": "crash_fechamento",
        "name": "Crash e Fechamento Inesperado",
        "keywords": ["fecha sozinho", "fechando sozinho", "sai do app", "crash", "trava ao abrir", "nem abre", "parou de funcionar", "app parou"],
        "description": "O aplicativo fecha abruptamente, encerra o processo ou não conclui a inicialização.",
        "severity": "Crítica",
        "complexity": "Alta",
        "templates": {
            "critical": "Olá, {nome}! Pedimos sinceras desculpas pelo fechamento inesperado do aplicativo. Nossa equipe de desenvolvimento está corrigindo as causas de instabilidade. Por gentileza, certifique-se de atualizar o app para a versão mais recente na {loja} e reiniciar o aparelho. Caso persista, pedimos que acesse o Canal de Suporte Oficial: 👉 {canal_contato}",
            "moderate": "Olá, {nome}! Agradecemos pelo relato. Estamos trabalhando para eliminar falhas de fechamento. Recomendamos reinstalar o aplicativo ou registrar o modelo do celular no Canal de Suporte Oficial: 👉 {canal_contato}",
            "positive": "Olá, {nome}! Agradecemos pela confiança e avaliação de {estrelas} estrelas! Nossa equipe continuará monitorando a estabilidade para garantir o melhor funcionamento."
        }
    },
    "acesso_responsaveis": {
        "id": "acesso_responsaveis",
        "name": "Acesso dos Pais / Múltiplos Alunos",
        "keywords": ["responsável", "responsavel", "pais", "mãe", "mae", "pai", "filho", "filhos", "ver meu filho", "dependente"],
        "description": "Dificuldade de pais ou responsáveis legais em visualizar múltiplos dependentes matriculados na rede estadual.",
        "severity": "Média",
        "complexity": "Média",
        "templates": {
            "critical": "Olá, {nome}! Compreendemos sua necessidade de acompanhar seus filhos. Para que os dependentes apareçam no seu perfil, o CPF do responsável legal deve estar cadastrado de forma idêntica na matrícula de cada estudante. Orientamos procurar a secretaria escolar ou relatar pelo Canal de Suporte Oficial: 👉 {canal_contato}",
            "moderate": "Olá, {nome}! O vínculo de múltiplos estudantes ao mesmo responsável depende da conferência cadastral nas secretarias das respectivas escolas. Ficamos à disposição pelo Canal de Suporte Oficial: 👉 {canal_contato} caso precise de orientação adicional.",
            "positive": "Olá, {nome}! Que alegria receber sua avaliação positiva! É um prazer apoiar as famílias no acompanhamento da vida escolar dos estudantes mineiros. Obrigado!"
        }
    },
    "outros_problemas": {
        "id": "outros_problemas",
        "name": "Problemas Gerais e Dúvidas",
        "keywords": ["outros", "dúvida", "ajuda", "problema"],
        "description": "Comentários com notas baixas (1 ou 2 estrelas) que não mencionam uma palavra-chave específica, ou dúvidas diversas de utilização.",
        "severity": "Média",
        "complexity": "Baixa",
        "templates": {
            "critical": "Olá, {nome}! Para nos ajudar a identificar e solucionar problemas no aplicativo Minha Escola MG, pedimos que acesse o Canal de Suporte Oficial: 👉 {canal_contato}",
            "moderate": "Olá, {nome}! Agradecemos por compartilhar sua opinião. Se estiver enfrentando qualquer dificuldade ou dúvida técnica, pedimos que acesse o Canal de Suporte Oficial: 👉 {canal_contato}",
            "positive": "Olá, {nome}! Agradecemos pelo retorno e pelas observações. Estamos à disposição para apoiar sua jornada escolar!"
        }
    },
    "elogios_satisfacao": {
        "id": "elogios_satisfacao",
        "name": "Elogios e Avaliações Positivas",
        "keywords": ["ótimo", "muito bom", "excelente", "parabéns", "ajuda muito", "fácil", "gostei", "adorei", "perfeito", "bom"],
        "description": "Avaliações de 4 e 5 estrelas contendo elogios, agradecimentos e reconhecimento da utilidade do aplicativo.",
        "severity": "Baixa",
        "complexity": "Baixa",
        "templates": {
            "critical": "Olá, {nome}! Agradecemos pelo seu contato. Caso esteja enfrentando qualquer instabilidade ou dificuldade no Minha Escola MG, pedimos que relate no Canal de Suporte Oficial: 👉 {canal_contato}",
            "moderate": "Olá, {nome}! Muito obrigado pelo retorno positivo. Se houver alguma dificuldade técnica que possamos ajudar a resolver, utilize o Canal de Suporte Oficial: 👉 {canal_contato}",
            "positive": "Olá, {nome}! Ficamos imensamente felizes com a sua avaliação de {estrelas} estrelas no Minha Escola MG! Nosso compromisso diário é facilitar a rotina de toda a comunidade escolar mineira. Muito obrigado pelo carinho e conte sempre conosco!"
        }
    },
    "geral_outros": {
        "id": "geral_outros",
        "name": "Geral / Sugestões Diversas",
        "keywords": ["sugestão", "melhorar", "poderia", "recurso", "atualização", "ajuda"],
        "description": "Comentários com notas moderadas ou sugestões de funcionalidades pedagógicas sem reporte de falhas impeditivas.",
        "severity": "Baixa",
        "complexity": "Baixa",
        "templates": {
            "critical": "Olá, {nome}! Sentimos muito por qualquer inconveniente no Minha Escola MG. Para nos ajudar a identificar e solucionar ocorrências, pedimos que acesse o Canal de Suporte Oficial: 👉 {canal_contato}",
            "moderate": "Olá, {nome}! Muito obrigado por compartilhar sua visão e sugestões de aprimoramento. Se notar qualquer instabilidade ou precisar de auxílio técnico, registre no Canal de Suporte Oficial: 👉 {canal_contato}",
            "positive": "Olá, {nome}! Agradecemos pela avaliação de {estrelas} estrelas no Minha Escola MG! Trabalhamos para tornar o dia a dia escolar cada vez mais prático. Conte conosco!"
        }
    }
}

def generate_auto_reply_for_review(review: Dict[str, Any], root_cause_id: Optional[str] = None) -> str:
    """
    Gera a resposta automática com base na Causa-Raiz e na Nota (Estrelas).
    REGRAS CRÍTICAS:
    1. Para TODAS as avaliações de 1 a 3 estrelas: SEMPRE inclui o Canal de Suporte Oficial: 👉 {canal_contato}.
    2. Para 4 ou 5 estrelas: se contiver QUALQUER contexto de problema no texto do usuário, TAMBÉM inclui o Canal de Suporte Oficial: 👉 {canal_contato}.
    3. A URL sempre vem do campo de configuração 'Canal de Suporte Oficial citado pela IA (Formulário Prodemge)' (support_contact_url / support_email).
    4. NUNCA inclui e-mails pessoais ou de desenvolvedores (ex: saulomartins.costa@gmail.com).
    """
    user_name = review.get("user_name", "").strip()
    if not user_name or user_name.lower() in ("usuário", "usuario", "usuario google play", "usuário apple"):
        greeting_name = "estudante/responsável"
    else:
        greeting_name = user_name

    rating = int(review.get("rating", 3))
    content = review.get("content", "")
    store = review.get("store", "google")
    store_name = "Google Play Store" if store == "google" else "Apple App Store"

    # Obtém o canal de contato oficial configurado no campo "Canal de Suporte Oficial citado pela IA (Formulário Prodemge)"
    canal_contato = get_setting("support_contact_url") or get_setting("support_email") or OFFICIAL_SUPPORT_FORM
    # REGRA ABSOLUTA: NUNCA usar endereços de e-mail (como saulomartins.costa@gmail.com)
    if "@" in canal_contato or not canal_contato.strip():
        canal_contato = OFFICIAL_SUPPORT_FORM
    canal_contato = canal_contato.strip()

    # Avalia se há contexto de problema
    is_problem = has_problem_context(content, rating)

    # Identifica o grupo se não fornecido
    from analytics.complexity import classify_text_issue
    if not root_cause_id or root_cause_id not in PROBLEM_TEMPLATES_CONFIG:
        c = classify_text_issue(content, review.get("title", ""), rating)
        root_cause_id = c["id"]

    cfg = PROBLEM_TEMPLATES_CONFIG.get(root_cause_id, PROBLEM_TEMPLATES_CONFIG["outros_problemas"])

    # Seleciona o template pelo nível de estrelas e pelo contexto de problema
    if rating <= 2:
        template = cfg["templates"]["critical"]
    elif rating == 3:
        template = cfg["templates"]["moderate"]
    else:
        # 4 ou 5 estrelas
        if is_problem:
            # Usuário deu nota alta, mas relatou erro, bug, lentidão ou problema
            template = (
                cfg["templates"]["positive"] + 
                " Notamos que você mencionou uma instabilidade ou dificuldade. "
                "Para que nossa equipe técnica possa verificar e solucionar o ocorrido, pedimos que acesse o "
                "Canal de Suporte Oficial: 👉 {canal_contato}"
            )
        else:
            template = cfg["templates"]["positive"]

    formatted = template.format(
        nome=greeting_name,
        loja=store_name,
        canal_contato=canal_contato,
        email=canal_contato,
        estrelas=rating
    )

    # Verificação estrita de segurança:
    # Se for 1 a 3 estrelas OU se houver contexto de problema, GARANTE que o canal oficial está no texto final!
    if (rating <= 3 or is_problem) and (canal_contato not in formatted and "forms.cloud.microsoft" not in formatted):
        formatted = (
            f"{formatted} Para que possamos analisar e solucionar sua situação, por favor acesse o "
            f"Canal de Suporte Oficial: 👉 {canal_contato}"
        )

    # Substitui formatos legados para o formato novo padrão
    formatted = re.sub(
        r'Canal de Suporte Oficial citado pela IA \(Formulário Prodemge\):\s*(👉\s*)?',
        'Canal de Suporte Oficial: 👉 ',
        formatted
    )
    formatted = re.sub(
        r'Canal de Suporte Oficial \(Formulário Prodemge\):\s*(👉\s*)?',
        'Canal de Suporte Oficial: 👉 ',
        formatted
    )

    # Limpeza contra qualquer e-mail acidental
    formatted = re.sub(r'[\w\.-]+@[\w\.-]+\.\w+', '', formatted).strip()

    return formatted
