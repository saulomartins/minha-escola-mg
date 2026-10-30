"""
Módulo de Taxonomia Dinâmica de Causas-Raiz e Diagnóstico Multi-Domínio.
Permite que cada aplicativo mobile utilize causas-raiz relevantes para a sua realidade
(Educação, Serviços Públicos, Fintech, E-commerce, Saúde ou Geral).
"""

from typing import List, Dict, Any, Optional

# ==============================================================================
# 1. CAUSAS-RAIZ UNIVERSAIS (Presentes em 100% dos apps mobile)
# ==============================================================================

UNIVERSAL_CAUSES: List[Dict[str, Any]] = [
    {
        "id": "login_sessao_recorrente",
        "name": "Instabilidade de Login, Conexão e Sessão",
        "keywords": [
            "login", "logar", "fazer login", "faca login", "faz login", "tentativas",
            "tentativa", "tentando entrar", "tentar entrar", "desloga", "deslogando", "deslogou",
            "deslogar", "desconecta", "desconectando", "desconectou", "desconectar", "sai toda hora",
            "toda hora sai", "sai da conta", "toda vez pede login", "pede login toda", "toda vez tem que fazer login",
            "toda vez que entro", "coloco a conta", "nao entra", "nao consigo entrar",
            "nao consigo acessar", "nao da pra acessar", "sem acesso", "perdi o acesso",
            "erro ao entrar", "erro ao acessar", "erro de login", "erro ao logar",
            "nao passa da tela de login", "trava no login", "bug no login", "problemas para conectar",
            "nao conecta", "impossivel fazer login", "sessao expirada", "sessao expirou", "token",
            "nao autentica", "tela de login", "bloqueou meu acesso", "acessar minha conta",
            "entrar no aplicativo", "entrar no app", "nem entrar", "nao consigo nem entrar",
            "nao abre a conta", "nao reconhece a conta", "tentar logar", "tentativas ate o app",
            "bloqueou", "bloqueada", "bloqueio", "nao entra de primeira", "so entra quando quer",
            "para entrar", "pra entrar", "ao entrar", "senha e usuario", "usuario e senha", "minha conta",
            "dificil de abrir", "nao abre de jeito nenhum", "conectar", "conexao", "autenticacao",
            "erro de autenticacao", "fora do ar"
        ],
        "severity": "Crítica",
        "severity_color": "#dc2626",
        "complexity": "Média",
        "complexity_score": 2,
        "recommendation": "Persistir token de refresh de forma segura (AccountManager/Keychain), aumentar tolerância a timeout no gateway e tratar desconexões com reconexão automática silenciosa sem deslogar o usuário.",
        "templates": {
            "critical": "Olá, {nome}! Lamentamos muito pelo transtorno com a instabilidade de login no {app_name}. Nossa equipe técnica da {org_name} está atuando na infraestrutura para estabilizar as sessões e evitar desconexões. Como procedimento imediato, por favor limpe o cache do aplicativo nas configurações do aparelho e tente novamente. Caso a dificuldade persista, acione o Canal de Suporte Oficial: 👉 {canal_contato}",
            "moderate": "Olá, {nome}! Agradecemos pelo seu relato. Já estamos cientes da instabilidade no acesso e atuando para otimizar o processo de login do {app_name}. Recomendamos manter o app sempre atualizado na versão mais recente da {loja}. Se precisar de auxílio adicional, conte conosco no Canal de Suporte Oficial: 👉 {canal_contato}",
            "positive": "Olá, {nome}! Muito obrigado pela avaliação de {estrelas} estrelas no {app_name}! Continuamos trabalhando para garantir um acesso rápido e seguro a todos os usuários."
        }
    },
    {
        "id": "crash_fechamento",
        "name": "Crash e Fechamento Inesperado",
        "keywords": [
            "fecha sozinho", "fechando sozinho", "fechando", "fecha", "sai do app", "crash",
            "trava ao abrir", "nem abre", "parou de funcionar", "app parou", "nao abre",
            "fica fechando", "fecha do nada", "aplicativo fecha", "falha ao abrir", "parou inesperadamente"
        ],
        "severity": "Crítica",
        "severity_color": "#dc2626",
        "complexity": "Alta",
        "complexity_score": 3,
        "recommendation": "Monitorar stack traces no Crashlytics e corrigir vazamentos de memória e erros de ciclo de vida de Activities/Fragments em versões antigas do SO.",
        "templates": {
            "critical": "Olá, {nome}! Pedimos sinceras desculpas pelo fechamento inesperado do aplicativo. Nossa equipe de desenvolvimento está investigando e corrigindo as causas de instabilidade. Por gentileza, certifique-se de atualizar o app para a versão mais recente na {loja} e reiniciar o aparelho. Caso persista, pedimos que acesse o Canal de Suporte Oficial: 👉 {canal_contato}",
            "moderate": "Olá, {nome}! Agradecemos pelo relato. Estamos trabalhando para eliminar falhas de fechamento. Recomendamos reinstalar o aplicativo ou registrar o modelo do celular no Canal de Suporte Oficial: 👉 {canal_contato}",
            "positive": "Olá, {nome}! Agradecemos pela confiança e avaliação de {estrelas} estrelas! Nossa equipe continuará monitorando a estabilidade para garantir o melhor funcionamento."
        }
    },
    {
        "id": "lentidao_performance",
        "name": "Lentidão Extrema e Travamentos",
        "keywords": [
            "tela preta", "tela branca", "lento", "lentidao", "travando", "trava",
            "carregando infinito", "roda roda", "nao passa da tela", "atualizacao piorou",
            "carregamento infinito", "demora demais", "congelando", "congela", "fica carregando",
            "demora para carregar", "demora pra carregar", "nunca carrega", "demora pra atualizar",
            "fica rodando", "carregar e nunca carrega", "muito lento", "pessimo desempenho"
        ],
        "severity": "Alta",
        "severity_color": "#ea580c",
        "complexity": "Média",
        "complexity_score": 2,
        "recommendation": "Otimizar assets, implementar carregamento assíncrono (lazy loading) e timeouts amigáveis com botão de 'Tentar Novamente'.",
        "templates": {
            "critical": "Olá, {nome}! Lamentamos muito pela lentidão ou travamento no {app_name}. Nossa equipe técnica da {org_name} lançou atualizações para otimização de performance. Recomendamos atualizar o app para a versão mais recente na {loja} e limpar o cache nas configurações do aparelho. Se persistir, informe os detalhes no Canal de Suporte Oficial: 👉 {canal_contato}",
            "moderate": "Olá, {nome}! Obrigado por nos avisar sobre a lentidão. Estamos trabalhando continuamente na estabilidade do aplicativo. Certifique-se de manter o app atualizado e, caso precise de auxílio, relate no Canal de Suporte Oficial: 👉 {canal_contato}",
            "positive": "Olá, {nome}! Muito obrigado pela avaliação de {estrelas} estrelas! Estamos sempre otimizando a velocidade do {app_name} para oferecer a melhor experiência a você. Conte com a gente!"
        }
    },
    {
        "id": "senha_recuperacao",
        "name": "Recuperação de Acesso e Senha",
        "keywords": [
            "esqueci a senha", "esqueci minha senha", "redefinir senha", "recuperar senha",
            "trocar senha", "mudar senha", "senha temporaria", "redefinicao", "codigo de recuperacao",
            "redefinir a senha", "nao recebi codigo", "codigo nao chega", "email de redefinicao", "sms nao chega"
        ],
        "severity": "Alta",
        "severity_color": "#ea580c",
        "complexity": "Média",
        "complexity_score": 2,
        "recommendation": "Garantir entrega de tokens de recuperação por múltiplos canais (SMS, WhatsApp, E-mail) com validade clara e tela explicativa.",
        "templates": {
            "critical": "Olá, {nome}! Sentimos muito pela dificuldade na recuperação do acesso. Verifique se a mensagem não foi para a caixa de Spam/Lixo Eletrônico. Caso o e-mail ou telefone cadastrado esteja desatualizado, solicite o suporte pelo Canal Oficial: 👉 {canal_contato}",
            "moderate": "Olá, {nome}! Agradecemos pelo seu contato. Para recuperar sua senha com segurança, certifique-se de que os dados de contato cadastrados estão atualizados. Havendo divergência, registre no Canal de Suporte Oficial: 👉 {canal_contato}",
            "positive": "Olá, {nome}! Agradecemos pela avaliação positiva de {estrelas} estrelas! Nosso objetivo é garantir que seu acesso ao {app_name} seja sempre ágil e descomplicado. Conte conosco!"
        }
    },
    {
        "id": "atualizacao_compatibilidade",
        "name": "Falhas Pós-Atualização e Compatibilidade de SO",
        "keywords": [
            "depois da atualizacao", "apos atualizar", "atualizacao estragou", "versao nova piorou",
            "incompativel", "meu celular nao suporta", "versao do android", "versao do ios", "parou de funcionar depois",
            "nao atualiza na loja", "play store diz que nao e compativel"
        ],
        "severity": "Alta",
        "severity_color": "#ea580c",
        "complexity": "Alta",
        "complexity_score": 3,
        "recommendation": "Preservar compatibilidade retroativa (minSdkVersion adequada) e testar builds em aparelhos legados congelados nas versões anteriores de SO.",
        "templates": {
            "critical": "Olá, {nome}! Sentimos muito por qualquer dificuldade após a atualização. Nossa equipe de engenharia analisa os relatos de compatibilidade em cada versão de sistema operacional para liberar melhorias contínuas. Se o seu aparelho apresentar instabilidade, relate o modelo no Canal Oficial: 👉 {canal_contato}",
            "moderate": "Olá, {nome}! Agradecemos pelo retorno. Estamos ajustando a compatibilidade para diferentes versões e fabricantes. Se persistir a instabilidade, pedimos que acione o Canal de Suporte Oficial: 👉 {canal_contato}",
            "positive": "Olá, {nome}! Ficamos muito felizes em saber que a versão mais recente atendeu suas expectativas! Trabalhamos para trazer constantes melhorias ao {app_name}."
        }
    },
    {
        "id": "usabilidade_interface",
        "name": "Dificuldade de Usabilidade e Interface (UX)",
        "keywords": [
            "dificil de mexer", "confuso", "layout ruim", "interface feia", "botoes nao funcionam",
            "letras pequenas", "nao acho", "onde clica", "complicado", "nao entendi como usa", "intuitivo"
        ],
        "severity": "Média",
        "severity_color": "#eab308",
        "complexity": "Baixa",
        "complexity_score": 1,
        "recommendation": "Realizar testes de usabilidade (A/B testing) e simplificar o fluxo de navegação das principais funcionalidades.",
        "templates": {
            "critical": "Olá, {nome}! Agradecemos pelo feedback sobre a usabilidade. Nossa equipe de design de produto avalia constantemente a experiência do usuário para tornar o {app_name} cada vez mais simples e intuitivo. Caso tenha sugestões específicas, relate no Canal Oficial: 👉 {canal_contato}",
            "moderate": "Olá, {nome}! Obrigado pela sugestão de melhoria visual e operacional. Seus apontamentos nos ajudam a evoluir a interface do {app_name}.",
            "positive": "Olá, {nome}! Muito obrigado pelo retorno positivo sobre a facilidade de uso do {app_name}! Trabalhamos para manter tudo prático para você."
        }
    },
    {
        "id": "elogios_satisfacao",
        "name": "Elogios e Experiência Positiva",
        "keywords": [
            "otimo", "muito bom", "excelente", "parabens", "ajuda muito", "facil", "gostei",
            "adorei", "perfeito", "bom", "top", "maravilha", "pratico", "nota 10", "recomendo",
            "parabenizo", "show", "sensacional", "melhor app", "amo", "amei"
        ],
        "severity": "Baixa",
        "severity_color": "#16a34a",
        "complexity": "Baixa",
        "complexity_score": 1,
        "recommendation": "Manter respostas automáticas cordiais de agradecimento para fortalecer o engajamento e a pontuação nas lojas.",
        "templates": {
            "critical": "Olá, {nome}! Agradecemos pelo seu contato. Caso esteja enfrentando qualquer instabilidade ou dificuldade no {app_name}, pedimos que relate no Canal de Suporte Oficial: 👉 {canal_contato}",
            "moderate": "Olá, {nome}! Muito obrigado pelo retorno positivo. Se houver alguma dificuldade técnica que possamos ajudar a resolver, utilize o Canal de Suporte Oficial: 👉 {canal_contato}",
            "positive": "Olá, {nome}! Ficamos imensamente felizes com a sua avaliação de {estrelas} estrelas no {app_name}! Nosso compromisso diário é entregar a melhor experiência aos nossos usuários. Muito obrigado pelo carinho e conte sempre conosco!"
        }
    },
    {
        "id": "outros_problemas",
        "name": "Problemas Gerais e Dúvidas",
        "keywords": [
            "duvida", "ajuda", "problema", "socorro", "ruim", "pessimo", "odiei", "horrivel", "nao gostei", "bomba"
        ],
        "severity": "Média",
        "severity_color": "#94a3b8",
        "complexity": "Baixa",
        "complexity_score": 1,
        "recommendation": "Responder convidando o usuário a detalhar a experiência pelo canal oficial de suporte.",
        "templates": {
            "critical": "Olá, {nome}! Para nos ajudar a identificar e solucionar problemas no aplicativo {app_name}, pedimos que acesse o Canal de Suporte Oficial: 👉 {canal_contato}",
            "moderate": "Olá, {nome}! Agradecemos por compartilhar sua opinião. Se estiver enfrentando qualquer dificuldade ou dúvida técnica, pedimos que acesse o Canal de Suporte Oficial: 👉 {canal_contato}",
            "positive": "Olá, {nome}! Agradecemos pelo retorno e pelas observações. Estamos à disposição para apoiar você!"
        }
    }
]

# ==============================================================================
# 2. PACKS ESPECIALIZADOS POR DOMÍNIO DE NEGÓCIO
# ==============================================================================

DOMAIN_PACKS: Dict[str, List[Dict[str, Any]]] = {
    # Domínio: Educação / Gestão Escolar (ex: Minha Escola MG)
    "education": [
        {
            "id": "boletim_notas",
            "name": "Boletim em Branco e Notas Ausentes",
            "keywords": [
                "nota", "notas", "boletim", "bimestre", "nao carrega nota", "boletim em branco",
                "nota zerada", "nao aparece nota", "nota sumiu", "lancamento de notas", "ver as notas",
                "sem nota", "notas nao aparecem", "quadro de notas", "ver notas", "consultar nota"
            ],
            "severity": "Alta",
            "severity_color": "#ea580c",
            "complexity": "Alta",
            "complexity_score": 3,
            "recommendation": "Desenvolver cache offline no app e exibir um indicador claro com a data/hora da última sincronização do Diário Escolar Digital (DED).",
            "templates": {
                "critical": "Olá, {nome}! Entendemos a importância de acompanhar o boletim. As notas exibidas no {app_name} dependem da sincronização e homologação feitas pelos professores no sistema escolar. Caso o bimestre já tenha encerrado e as notas não apareçam, consulte a coordenação da sua escola ou relate no Canal de Suporte Oficial: 👉 {canal_contato}",
                "moderate": "Olá, {nome}! Agradecemos pelo seu relato. A atualização das notas no aplicativo ocorre conforme os professores realizam o lançamento oficial no sistema escolar. Havendo dúvidas ou divergências não solucionadas pela escola, relate pelo Canal de Suporte Oficial: 👉 {canal_contato}",
                "positive": "Olá, {nome}! Ficamos muito felizes com a sua avaliação positiva! O acompanhamento das notas é fundamental e estamos empenhados em manter tudo sempre sincronizado para você. Bons estudos!"
            }
        },
        {
            "id": "faltas_frequencia",
            "name": "Faltas e Frequência Divergentes",
            "keywords": [
                "falta", "faltas", "frequencia", "presenca", "falta errada", "computou falta",
                "sem presenca", "marcou falta", "quadro de faltas", "abono de falta",
                "dias que eu fui", "dias de aula"
            ],
            "severity": "Média",
            "severity_color": "#eab308",
            "complexity": "Média",
            "complexity_score": 2,
            "recommendation": "Exibir extrato detalhado de faltas com disciplina, data e motivo de abono homologado pela coordenação.",
            "templates": {
                "critical": "Olá, {nome}! Agradecemos pelo alerta sobre a frequência. O registro de faltas e presenças no app reflete os lançamentos dos professores no Diário Escolar. Se houver divergências não solucionadas pela secretaria da escola, relate os detalhes no Canal de Suporte Oficial: 👉 {canal_contato}",
                "moderate": "Olá, {nome}! O controle de faltas reflete o Diário Escolar Digital. Caso note divergências na frequência, a coordenação da sua escola poderá verificar e retificar os registros, ou você pode registrar no Canal de Suporte Oficial: 👉 {canal_contato}",
                "positive": "Olá, {nome}! Muito obrigado pela avaliação de {estrelas} estrelas! O controle de frequência é essencial para o acompanhamento escolar. Conte conosco!"
            }
        },
        {
            "id": "acesso_responsaveis",
            "name": "Acesso dos Pais / Múltiplos Alunos",
            "keywords": [
                "responsavel", "pais", "mae", "pai", "filho", "filhos", "ver meu filho",
                "dependente", "outro filho", "dois filhos", "duas filhas", "minha filha"
            ],
            "severity": "Média",
            "severity_color": "#eab308",
            "complexity": "Média",
            "complexity_score": 2,
            "recommendation": "Criar seletor dinâmico de dependentes no topo do app para responsáveis com mais de um aluno matriculado.",
            "templates": {
                "critical": "Olá, {nome}! Compreendemos sua necessidade de acompanhar seus filhos. Para que os dependentes apareçam no seu perfil, o CPF do responsável legal deve estar cadastrado de forma idêntica na matrícula de cada estudante. Orientamos procurar a secretaria escolar ou relatar pelo Canal de Suporte Oficial: 👉 {canal_contato}",
                "moderate": "Olá, {nome}! O vínculo de múltiplos estudantes ao mesmo responsável depende da conferência cadastral nas secretarias das respectivas escolas. Ficamos à disposição pelo Canal de Suporte Oficial: 👉 {canal_contato} caso precise de orientação adicional.",
                "positive": "Olá, {nome}! Que alegria receber sua avaliação positiva! É um prazer apoiar as famílias no acompanhamento da vida escolar dos estudantes. Obrigado!"
            }
        },
        {
            "id": "gov_br_cpf",
            "name": "Falha no Gov.br e Vínculo de CPF Escolar",
            "keywords": [
                "gov.br", "gov", "conta gov", "login gov", "gov br",
                "cpf", "vincular cpf", "vinculo de cpf", "nao reconhece cpf",
                "cpf nao encontrado", "cpf incorreto", "dados divergentes", "dados invalidos",
                "dataprev", "simade"
            ],
            "severity": "Crítica",
            "severity_color": "#dc2626",
            "complexity": "Alta",
            "complexity_score": 3,
            "recommendation": "Aprimorar tratamento de erros da integração OAuth Gov.br/Dataprev com mensagens instrutivas e suporte a múltiplos perfis de acesso.",
            "templates": {
                "critical": "Olá, {nome}! Sentimos muito pelo transtorno no acesso Gov.br. Esse erro geralmente ocorre por divergência cadastral entre a base federal e o cadastro escolar. Recomendamos confirmar seus dados cadastrais na secretaria da escola. Se o problema persistir, pedimos que acesse o Canal de Suporte Oficial: 👉 {canal_contato}",
                "moderate": "Olá, {nome}! Agradecemos pelo seu retorno. O login com Gov.br exige que os dados cadastrais estejam 100% alinhados com o sistema escolar. Caso o acesso continue instável, orientamos relatar pelo Canal de Suporte Oficial: 👉 {canal_contato}",
                "positive": "Olá, {nome}! Muito obrigado pela avaliação de {estrelas} estrelas no {app_name}! Trabalhamos constantemente na integração com o Gov.br para manter seu acesso seguro e prático. Conte conosco!"
            }
        }
    ],

    # Domínio: Serviços Públicos / Cidadão / Governo (ex: MG App Cidadão, Detran, Poupatempo)
    "public_services": [
        {
            "id": "gov_br_autenticacao",
            "name": "Falha na Autenticação Gov.br e Biometria Facial",
            "keywords": [
                "gov.br", "gov", "conta gov", "login gov", "nivel prata", "nivel ouro",
                "reconhecimento facial", "validacao facial", "biometria facial", "selfie", "camera nao abre", "rosto"
            ],
            "severity": "Crítica",
            "severity_color": "#dc2626",
            "complexity": "Alta",
            "complexity_score": 3,
            "recommendation": "Integrar SDK atualizado da validação facial Gov.br e orientar usuários sobre iluminação e permissões de câmera do aparelho.",
            "templates": {
                "critical": "Olá, {nome}! Sentimos muito pela dificuldade na autenticação Gov.br. A validação biométrica exige boa iluminação e permissões de câmera ativas. Caso o erro persista, consulte as diretrizes no Canal de Atendimento Oficial: 👉 {canal_contato}",
                "moderate": "Olá, {nome}! Agradecemos pelo contato. A autenticação pelo Gov.br é essencial para a segurança dos seus dados. Havendo instabilidades, acesse o Canal Oficial: 👉 {canal_contato}",
                "positive": "Olá, {nome}! Muito obrigado pela nota máxima no {app_name}! Trabalhamos para tornar o acesso aos serviços públicos cada vez mais ágil e seguro."
            }
        },
        {
            "id": "agendamento_atendimento",
            "name": "Dificuldade em Agendamento Presencial e Vagas",
            "keywords": [
                "agendamento", "agendar", "marcar", "uai", "poupatempo", "vagas", "sem vaga", "horario",
                "nao consigo agendar", "data indisponivel", "agendar atendimento", "unidade de atendimento"
            ],
            "severity": "Alta",
            "severity_color": "#ea580c",
            "complexity": "Média",
            "complexity_score": 2,
            "recommendation": "Exibir calendário preditivo com liberação de novos horários e permitir fila de espera digital com notificação push.",
            "templates": {
                "critical": "Olá, {nome}! Entendemos sua necessidade de realizar o agendamento. As vagas nas unidades são abertas periodicamente pelos órgãos competentes. Caso necessite de apoio prioritário, consulte o Canal Oficial: 👉 {canal_contato}",
                "moderate": "Olá, {nome}! Agradecemos pelo retorno. Recomendamos verificar os horários de abertura de novas vagas nas unidades de atendimento pelo Canal Oficial: 👉 {canal_contato}",
                "positive": "Olá, {nome}! Ficamos muito felizes que conseguiu agendar seus serviços com praticidade no {app_name}! Estamos à disposição."
            }
        },
        {
            "id": "emissao_documentos",
            "name": "Erro na Emissão de Documentos e Certidões",
            "keywords": [
                "cnh", "documento", "certidao", "crlv", "rg", "carteira de identidade", "baixar documento",
                "pdf nao abre", "nao baixa", "nao gera", "carteira digital", "licenciamento", "atestado"
            ],
            "severity": "Alta",
            "severity_color": "#ea580c",
            "complexity": "Alta",
            "complexity_score": 3,
            "recommendation": "Otimizar gerador de PDF mobile e permitir download/compartilhamento seguro via WhatsApp e e-mail.",
            "templates": {
                "critical": "Olá, {nome}! Pedimos desculpas pela dificuldade ao emitir seu documento digital. Verifique a conexão com a internet e espaço de armazenamento no aparelho. Se o erro persistir, acione o Canal Oficial: 👉 {canal_contato}",
                "moderate": "Olá, {nome}! Agradecemos pelo alerta sobre a emissão de documentos. Se precisar de suporte na emissão, conte conosco no Canal Oficial: 👉 {canal_contato}",
                "positive": "Olá, {nome}! Ficamos muito felizes que seus documentos digitais estão acessíveis e práticos no {app_name}! Um abraço da equipe!"
            }
        },
        {
            "id": "consulta_taxas_debitos",
            "name": "Divergência em IPVA, Multas e Guias DAE",
            "keywords": [
                "ipva", "multa", "multas", "dae", "taxa", "debito", "veiculo", "placa", "renavam", "pagamento",
                "codigo de barras", "guia de pagamento", "divida ativa"
            ],
            "severity": "Média",
            "severity_color": "#eab308",
            "complexity": "Média",
            "complexity_score": 2,
            "recommendation": "Validar sincronização em tempo real entre a Secretaria de Fazenda/Detran e os serviços de consulta do aplicativo.",
            "templates": {
                "critical": "Olá, {nome}! Caso tenha notado divergência em valores de tributos ou taxas, orientamos consultar o extrato detalhado diretamente pelo Canal de Suporte Oficial: 👉 {canal_contato}",
                "moderate": "Olá, {nome}! As informações tributárias e de débitos são sincronizadas com as bases oficiais dos órgãos arrecadadores. Para orientações, acesse o Canal Oficial: 👉 {canal_contato}",
                "positive": "Olá, {nome}! Muito obrigado pela avaliação de {estrelas} estrelas no {app_name}! Estamos sempre à disposição para facilitar suas consultas."
            }
        }
    ],

    # Domínio: Bancos / Fintechs / Pagamentos
    "fintech": [
        {
            "id": "pix_transferencias",
            "name": "Falhas no PIX e Transferências",
            "keywords": [
                "pix", "transferencia", "ted", "doc", "dinheiro nao caiu", "pix nao vai", "chave pix",
                "falha no pix", "comprovante", "pagar com pix", "qr code"
            ],
            "severity": "Crítica",
            "severity_color": "#dc2626",
            "complexity": "Alta",
            "complexity_score": 3,
            "recommendation": "Reforçar retentativas de requisição com chave idempotente e monitorar latência dos gateways do Banco Central.",
            "templates": {
                "critical": "Olá, {nome}! Lamentamos muito pelo transtorno com a operação PIX. Para que nossa equipe de segurança possa checar a transação imediatamente, acione o Suporte Oficial: 👉 {canal_contato}",
                "moderate": "Olá, {nome}! Transações financeiras exigem validação contínua. Caso precise de auxílio na compensação, conte conosco no Suporte Oficial: 👉 {canal_contato}",
                "positive": "Olá, {nome}! Muito obrigado pela avaliação de {estrelas} estrelas! Trabalhamos para manter suas operações financeiras ágeis e 100% seguras."
            }
        },
        {
            "id": "saldo_extrato",
            "name": "Extrato Incorreto ou Saldo Desatualizado",
            "keywords": [
                "saldo", "extrato", "saldo errado", "nao atualiza saldo", "lancamento desconhecido",
                "cobranca indevida", "sumiu dinheiro", "valores divergentes"
            ],
            "severity": "Alta",
            "severity_color": "#ea580c",
            "complexity": "Média",
            "complexity_score": 2,
            "recommendation": "Implementar atualização reativa (WebSockets) na tela de conta e histórico com paginação eficiente.",
            "templates": {
                "critical": "Olá, {nome}! Compreendemos sua preocupação com o saldo. Por favor, acione nosso canal de atendimento especializado para auditoria imediata da conta: 👉 {canal_contato}",
                "moderate": "Olá, {nome}! A atualização de saldo e lançamentos pode sofrer breve intervalo de sincronização. Se persistir, consulte nosso time no Canal Oficial: 👉 {canal_contato}",
                "positive": "Olá, {nome}! Ficamos muito felizes com a sua avaliação de {estrelas} estrelas no {app_name}! Conte sempre conosco para gerir suas finanças."
            }
        }
    ],

    # Domínio: E-commerce / Delivery / Vendas
    "ecommerce": [
        {
            "id": "carrinho_checkout",
            "name": "Falha no Carrinho e Finalização de Compra",
            "keywords": [
                "carrinho", "checkout", "finalizar compra", "nao fecha pedido", "erro ao comprar",
                "sacola", "itens sumiram", "comprar", "tela de pagamento", "carrinho trava"
            ],
            "severity": "Crítica",
            "severity_color": "#dc2626",
            "complexity": "Média",
            "complexity_score": 2,
            "recommendation": "Garantir persistência local do carrinho em SQLite/Room e validação assíncrona de estoque antes do checkout.",
            "templates": {
                "critical": "Olá, {nome}! Lamentamos pela dificuldade ao finalizar seu pedido. Nossa equipe técnica já está atuando para estabilizar o checkout. Caso precise de apoio, acione nosso suporte: 👉 {canal_contato}",
                "moderate": "Olá, {nome}! Agradecemos pelo aviso. Recomendamos limpar o cache do app e verificar se os itens estão disponíveis. Dúvidas pelo Canal Oficial: 👉 {canal_contato}",
                "positive": "Olá, {nome}! Adoramos saber que sua compra foi rápida e prática! Boas compras e conte sempre com o {app_name}!"
            }
        },
        {
            "id": "rastreio_entrega",
            "name": "Atraso na Entrega e Rastreamento Inexistente",
            "keywords": [
                "entrega", "atraso", "atrasou", "rastreio", "rastreamento", "pedido nao chegou",
                "transportadora", "status do pedido", "previsao de entrega", "onde esta meu pedido"
            ],
            "severity": "Alta",
            "severity_color": "#ea580c",
            "complexity": "Baixa",
            "complexity_score": 1,
            "recommendation": "Integrar webhooks de transportadoras com alertas push automáticos em cada movimentação da encomenda.",
            "templates": {
                "critical": "Olá, {nome}! Sentimos muito pelo atraso na entrega. Por favor, acione o canal de suporte com o número do seu pedido para cobrarmos a transportadora: 👉 {canal_contato}",
                "moderate": "Olá, {nome}! O rastreamento depende da atualização da transportadora. Caso o prazo tenha expirado, relate pelo Canal Oficial: 👉 {canal_contato}",
                "positive": "Olá, {nome}! Que ótimo que sua entrega foi pontual e sem complicações! Agradecemos pela avaliação de {estrelas} estrelas!"
            }
        }
    ]
}

# ==============================================================================
# 3. RESOLVEDOR DINÂMICO DE TAXONOMIA
# ==============================================================================

def get_root_causes_config(domain: Optional[str] = None, custom_causes: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    """
    Retorna a lista completa de causas-raiz configuradas para o domínio do aplicativo ativo.
    A ordem de prioridade para classificação é:
    1. Causas personalizadas do usuário (se houver)
    2. Causas especializadas do domínio (Educação, Serviços Públicos, Fintech, etc.)
    3. Causas universais mobile (Login, Crash, Lentidão, etc.)
    """
    if domain is None:
        try:
            from config import get_app_config
            cfg = get_app_config()
            domain = cfg.get("domain", "general")
            custom_causes = custom_causes or cfg.get("custom_causes")
        except Exception:
            domain = "general"

    domain = str(domain).lower().strip()
    result: List[Dict[str, Any]] = []

    # 1. Custom causes
    if custom_causes and isinstance(custom_causes, list):
        result.extend(custom_causes)

    # 2. Domain pack
    pack = DOMAIN_PACKS.get(domain, [])
    result.extend(pack)

    # 3. Universal causes
    existing_ids = {c["id"] for c in result}
    for uc in UNIVERSAL_CAUSES:
        if uc["id"] not in existing_ids:
            result.append(uc)

    return result

def get_root_causes_map(domain: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
    causes = get_root_causes_config(domain=domain)
    return {c["id"]: c for c in causes}
