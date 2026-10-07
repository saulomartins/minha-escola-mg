import os
import json
import logging
import re
from typing import Dict, Any, Optional
from database.db import get_setting

logger = logging.getLogger(__name__)

DEFAULT_SUPPORT_URL = "https://forms.cloud.microsoft/r/JmZhSzXtwG"

def get_official_support_url() -> str:
    """
    Retorna dinamicamente a URL do campo de configuração
    'Canal de Suporte Oficial citado pela IA (Formulário Prodemge)'
    salvo nas configurações do sistema.
    """
    try:
        url = get_setting("support_contact_url") or get_setting("support_email") or DEFAULT_SUPPORT_URL
        if "@" in url or not url.strip():
            url = DEFAULT_SUPPORT_URL
        return url.strip()
    except Exception:
        return DEFAULT_SUPPORT_URL

def build_system_prompt(support_url: str) -> str:
    return f"""Você é o assistente oficial de suporte e atendimento ao usuário do aplicativo "Minha Escola MG" (aplicativo oficial da Secretaria de Estado de Educação de Minas Gerais - SEE/MG e PRODEMGE).
Sua missão é analisar avaliações e comentários de usuários (estudantes, pais, professores e responsáveis) nas lojas Google Play Store e Apple App Store, categorizar o problema e redigir uma resposta oficial, cordial, prestativa e empática em Português do Brasil.

Diretrizes obrigatórias para as respostas:
1. Seja sempre educado, acolhedor e profissional.
2. Cumprimente o usuário pelo nome (se disponível) ou cordialmente ("Olá!", "Olá, estudante/responsável!").
3. REGRA CRÍTICA DO CANAL DE SUPORTE OFICIAL:
   - REGRA ABSOLUTA PARA 5 ESTRELAS: Para TODAS as avaliações com nota 5 estrelas, NUNCA inclua link de formulário nem mencione "Canal de Suporte Oficial". Apenas agradeça de forma calorosa, cordial e prestativa pela avaliação e pela nota máxima no Minha Escola MG!
   - Para TODAS as avaliações com nota de 1 a 3 estrelas (1, 2 ou 3 estrelas): a resposta DEVE OBRIGATORIAMENTE indicar e solicitar que o usuário utilize exatamente:
     Canal de Suporte Oficial: 👉 {support_url}
   - Para avaliações de 4 estrelas: se contiver menção ou contexto de problema, falha ou lentidão, solicite o Canal de Suporte Oficial: 👉 {support_url}. Se for apenas elogio, agradeça cordialmente sem incluir o canal de suporte.
4. REGRA OBRIGATÓRIA DE CONTATO: NUNCA utilize endereços de e-mail (como saulomartins.costa@gmail.com ou qualquer outro) na resposta. O único canal oficial a ser informado quando houver problema/dificuldade é exatamente no formato:
   Canal de Suporte Oficial: 👉 {support_url}
5. Para PROBLEMAS DE ACESSO/LOGIN/SENHA: Oriente a verificar se o cadastro no sistema escolar/Simave/Gov.br está atualizado na secretaria da escola, ou a utilizar a recuperação de senha, e solicite o preenchimento do Canal de Suporte Oficial: 👉 {support_url}.
6. Para BUGS/TRAVAMENTOS/TELA PRETA: Peça desculpas pelo transtorno, sugira atualizar o aplicativo para a versão mais recente, limpar o cache do app, e solicite o registro no Canal de Suporte Oficial: 👉 {support_url}.
7. Para PROBLEMAS DE NOTAS/FALTAS NÃO ATUALIZADAS: Explique que o lançamento depende do Diário Escolar Digital (DED) pelos professores. Caso persista a divergência, oriente a procurar a coordenação da escola ou registrar no Canal de Suporte Oficial: 👉 {support_url}.
8. Mantenha a resposta concisa (máximo de 3 a 4 frases), ideal para leitura em lojas de aplicativos.

Você DEVE responder SEMPRE em formato JSON com o seguinte formato:
{{
  "sentiment": "POSITIVO" | "NEUTRO" | "NEGATIVO",
  "category": "Login/Acesso" | "Boletim/Notas" | "Falha Técnica" | "Usabilidade" | "Elogio" | "Outros",
  "suggested_response": "Texto da resposta pronto para ser publicado"
}}
"""

def has_problem_context(content: str, rating: int) -> bool:
    """
    Avalia se a avaliação tem nota de 1 a 3 estrelas OU se contém qualquer contexto
    de problema, erro, falha, lentidão, bug ou dificuldade no texto do usuário.
    REGRA ABSOLUTA: Para avaliações de 5 estrelas, NUNCA considera problema para fins
    de inclusão do formulário de suporte (5 estrelas nunca recebe link de formulário).
    """
    if rating >= 5:
        return False

    if rating <= 3:
        return True

    text = (content or "").lower().strip()
    if not text:
        return False

    # Conjunções adversativas indicando que mesmo com 4 estrelas há uma ressalva/dificuldade
    if re.search(r'\b(mas|porém|porem|contudo|entretanto|todavia)\b', text):
        return True

    problem_terms = [
        "problema", "erro", "bug", "falha", "trava", "travando", "travar", "travou",
        "lento", "lentidão", "lentidao", "não entra", "nao entra", "não abre", 
        "nao abre", "fecha sozinho", "fechando", "fechar", "sai sozinho", "crash",
        "tela preta", "tela branca", "não consigo", "nao consigo", "dificuldade", 
        "dificil", "difícil", "confuso", "complicado", "senha", "esqueci", "recuperar", 
        "bloquead", "nota sumiu", "não aparece", "nao aparece", "não carrega", "nao carrega",
        "não atualiza", "nao atualiza", "divergência", "divergencia", "socorro", 
        "arrumem", "consertem", "corrijam", "piorou", "ruim", "péssimo", "pessimo", "odiei", 
        "horrível", "horrivel", "desinstalando", "instável", "instavel", "não funciona", 
        "nao funciona", "cai toda hora", "carregando infinito", "faltou", "faltando", 
        "consertar", "arrumar", "reclamar", "reclamação", "reclamacao", "nada funciona", 
        "não dá", "nao da", "deslogando", "desloga", "parou", "demora", "demorando", 
        "falhando", "sumiu", "sumiram", "não recebi", "nao recebi"
    ]
    return any(t in text for t in problem_terms)

def strip_support_link(text: str) -> str:
    """
    Remove sentenças ou trechos que direcionam para o canal de suporte oficial,
    formulários e avisos residuais de instabilidade quando a avaliação for 5 estrelas.
    Garante uma resposta cordial, limpa e calorosa de agradecimento.
    """
    if not text:
        return ""

    # Divide em frases preservando pontuação
    sentences = re.split(r'([.!?]+(?:\s+|$))', text)
    
    kept_sentences = []
    i = 0
    while i < len(sentences):
        chunk = sentences[i]
        punct = sentences[i + 1] if i + 1 < len(sentences) else ""
        i += 2
        
        chunk_clean = chunk.strip()
        if not chunk_clean:
            continue
            
        lower_chunk = chunk_clean.lower()
        # Verifica se esta frase é sobre suporte, formulário ou aviso de problema residual
        is_support_phrase = (
            "canal de suporte" in lower_chunk or
            "forms.cloud.microsoft" in lower_chunk or
            "forms.office.com" in lower_chunk or
            "suporte oficial" in lower_chunk or
            "jmzhszxtwg" in lower_chunk or
            "notamos que você mencionou" in lower_chunk or
            "notamos que voce mencionou" in lower_chunk or
            "instabilidade ou dificuldade" in lower_chunk or
            "equipe técnica possa verificar" in lower_chunk or
            "equipe tecnica possa verificar" in lower_chunk or
            "para que possamos analisar e solucionar" in lower_chunk or
            "caso esteja enfrentando qualquer instabilidade" in lower_chunk or
            "se estiver enfrentando qualquer" in lower_chunk or
            "se houver alguma dificuldade técnica" in lower_chunk
        )
        
        if not is_support_phrase:
            # Se não for de suporte, limpa qualquer URL residual e emoji de apontamento
            cleaned_chunk = re.sub(r'https?://\S+', '', chunk_clean).strip()
            cleaned_chunk = re.sub(r'👉', '', cleaned_chunk).strip()
            if cleaned_chunk:
                kept_sentences.append(cleaned_chunk + (punct.rstrip() or "."))
    
    result = " ".join(kept_sentences).strip()
    
    # Se por acaso todas as frases foram removidas, mantém uma saudação cordial positiva
    if not result:
        result = "Agradecemos pela excelente avaliação no Minha Escola MG! Conte sempre conosco!"
        
    return result

def ensure_official_support_link(suggested_response: str, content: str, rating: int) -> str:
    """
    Garante que qualquer avaliação de 1 a 3 estrelas OU com qualquer contexto de problema
    contenham obrigatoriamente a indicação do Canal de Suporte Oficial no formato exato:
    'Canal de Suporte Oficial: 👉 {support_url}'.
    
    REGRA ABSOLUTA PARA 5 ESTRELAS: Para comentários com 5 estrelas, NUNCA coloca o formulário
    nem o link nem o canal de suporte. Apenas agradece pelo retorno positivo.
    """
    support_url = get_official_support_url()
    cleaned = re.sub(r'[\w\.-]+@[\w\.-]+\.\w+', '', suggested_response).strip()
    
    # Substitui formatos legados para o formato padrão exato
    cleaned = re.sub(
        r'Canal de Suporte Oficial citado pela IA \(Formulário Prodemge\):\s*(👉\s*)?',
        'Canal de Suporte Oficial: 👉 ',
        cleaned
    )
    cleaned = re.sub(
        r'Canal de Suporte Oficial \(Formulário Prodemge\):\s*(👉\s*)?',
        'Canal de Suporte Oficial: 👉 ',
        cleaned
    )
    
    if rating >= 5:
        # REGRA ABSOLUTA: 5 estrelas NUNCA recebe link de suporte ou formulário
        return strip_support_link(cleaned)
    
    is_problem = has_problem_context(content, rating)
    
    if is_problem:
        # Se for 1-3 estrelas OU 4 estrelas COM relato de problema, GARANTE o link
        if support_url not in cleaned and "forms.cloud.microsoft" not in cleaned:
            cleaned = (
                f"{cleaned} Para que possamos analisar e solucionar sua situação, por favor "
                f"acesse o Canal de Suporte Oficial: 👉 {support_url}"
            )
    else:
        cleaned = strip_support_link(cleaned)
            
    return cleaned

def heuristic_fallback_analysis(user_name: str, rating: int, content: str) -> Dict[str, Any]:
    """
    Análise heurística quando não há chave do Gemini configurada ou em caso de fallback.
    REGRA ABSOLUTA: Para avaliações de 5 estrelas, SEMPRE retorna agradecimento positivo sem formulário.
    """
    support_url = get_official_support_url()
    content_lower = (content or "").lower()
    name_greeting = f"Olá, {user_name}!" if user_name and "usuário" not in user_name.lower() else "Olá!"
    
    # REGRA ABSOLUTA: 5 estrelas é sempre elogio caloroso sem link
    if rating >= 5:
        return {
            "sentiment": "POSITIVO",
            "category": "Elogio",
            "suggested_response": (
                f"{name_greeting} Ficamos muito felizes com a sua avaliação de 5 estrelas no Minha Escola MG! "
                f"Nosso compromisso diário é facilitar a rotina de toda a comunidade escolar mineira. "
                f"Muito obrigado pelo carinho e conte sempre conosco!"
            )
        }
    
    is_problem = has_problem_context(content, rating)
    
    # Sentimento
    if rating >= 4 and not is_problem:
        sentiment = "POSITIVO"
    elif rating >= 4 and is_problem:
        sentiment = "NEUTRO"
    elif rating == 3:
        sentiment = "NEUTRO"
    else:
        sentiment = "NEGATIVO"
        
    # Categoria e Resposta
    if any(w in content_lower for w in ["senha", "login", "entrar", "gov", "cpf", "acesso", "conta", "recuperar"]):
        category = "Login/Acesso"
        response = (
            f"{name_greeting} Sentimos muito pela dificuldade de acesso. "
            f"Verifique se o seu CPF e dados cadastrais estão atualizados junto à secretaria da sua escola. "
            f"Se a dificuldade persistir, utilize a opção 'Esqueci minha senha' ou solicite suporte pelo "
            f"Canal de Suporte Oficial: 👉 {support_url}"
        )
    elif any(w in content_lower for w in ["nota", "boletim", "falta", "frequência", "frequencia", "bimestre", "ponto"]):
        category = "Boletim/Notas"
        response = (
            f"{name_greeting} Agradecemos pelo seu relato. As notas e frequências exibidas no Minha Escola MG "
            f"dependem da sincronização dos lançamentos feitos pelos professores no Diário Escolar Digital. "
            f"Caso haja divergências não resolvidas pela escola, por favor informe pelo "
            f"Canal de Suporte Oficial: 👉 {support_url}"
        )
    elif any(w in content_lower for w in ["trava", "fecha", "bug", "erro", "carrega", "preta", "lento", "ruim", "péssimo", "atualização"]):
        category = "Falha Técnica"
        response = (
            f"{name_greeting} Lamentamos pelo ocorrido! Recomendamos verificar se o aplicativo está atualizado "
            f"para a versão mais recente na loja e limpar os dados de cache nas configurações do aparelho. "
            f"Persistindo a falha, pedimos que acesse o Canal de Suporte Oficial: 👉 {support_url}"
        )
    elif rating >= 4 and not is_problem:
        category = "Elogio"
        response = f"{name_greeting} Ficamos muito felizes com a sua avaliação de {rating} estrelas e carinho! Nosso objetivo é sempre facilitar o dia a dia da comunidade escolar mineira. Conte conosco!"
    elif rating >= 4 and is_problem:
        category = "Falha Técnica" if any(w in content_lower for w in ["trava", "lento", "bug", "fecha"]) else "Usabilidade"
        response = (
            f"{name_greeting} Muito obrigado pela sua avaliação positiva! Notamos seu relato sobre instabilidade ou dificuldade. "
            f"Para que nossa equipe técnica possa verificar e solucionar o problema, por favor acesse o "
            f"Canal de Suporte Oficial: 👉 {support_url}"
        )
    else:
        category = "Outros"
        response = (
            f"{name_greeting} Agradecemos por compartilhar sua opinião conosco. "
            f"Para nos ajudar a solucionar qualquer dificuldade ou dúvida no aplicativo, "
            f"pedimos que acesse o Canal de Suporte Oficial: 👉 {support_url}"
        )
        
    return {
        "sentiment": sentiment,
        "category": category,
        "suggested_response": response
    }

def analyze_review(review: Dict[str, Any], api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Analisa uma avaliação usando o Gemini API (se chave disponível) ou fallback heurístico.
    Garante o direcionamento ao Canal de Suporte Oficial no formato exato:
    'Canal de Suporte Oficial: 👉 {support_url}'
    """
    support_url = get_official_support_url()
    user_name = review.get("user_name", "Usuário")
    rating = review.get("rating", 3)
    content = review.get("content", "")
    store = review.get("store", "Loja")
    
    # Se não tiver conteúdo de texto e for só nota
    if not content.strip():
        if rating >= 4:
            return {
                "sentiment": "POSITIVO",
                "category": "Elogio",
                "suggested_response": f"Olá! Muito obrigado pela sua avaliação de {rating} estrelas no Minha Escola MG! Estamos sempre à disposição."
            }
        else:
            return {
                "sentiment": "NEGATIVO" if rating <= 2 else "NEUTRO",
                "category": "Outros",
                "suggested_response": (
                    f"Olá! Sentimos muito que sua experiência não tenha sido 5 estrelas. "
                    f"Para nos ajudar a solucionar qualquer dificuldade no aplicativo, por favor acesse o "
                    f"Canal de Suporte Oficial: 👉 {support_url}"
                )
            }

    effective_api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
    
    if not effective_api_key:
        return heuristic_fallback_analysis(user_name, rating, content)
        
    try:
        from google import genai
        client = genai.Client(api_key=effective_api_key)
        
        prompt = f"""Analise a seguinte avaliação do app Minha Escola MG recebida na loja {store.upper()}:
Nome do usuário: {user_name}
Nota: {rating} estrelas
Comentário: "{content}"

DIRETRIZ MANDATÓRIA:
1. Para comentários com nota de 5 estrelas: NUNCA inclua o link do formulário nem a frase "Canal de Suporte Oficial". Apenas agradeça calorosamente pelo apoio, carinho e nota máxima.
2. Para notas de 1 a 3 estrelas (ou 4 estrelas com relato de problema/dificuldade), a suggested_response DEVE OBRIGATORIAMENTE direcionar o usuário para:
Canal de Suporte Oficial: 👉 {support_url}

Retorne o JSON estrito com sentiment, category e suggested_response."""

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config={
                "system_instruction": build_system_prompt(support_url),
                "response_mime_type": "application/json"
            }
        )
        
        text = response.text.strip()
        data = json.loads(text)
        raw_suggested = data.get("suggested_response", "")
        final_suggested = ensure_official_support_link(raw_suggested, content, rating)
        
        return {
            "sentiment": data.get("sentiment", "NEUTRO"),
            "category": data.get("category", "Outros"),
            "suggested_response": final_suggested
        }
    except Exception as e:
        logger.warning(f"Falha ao chamar Gemini API ({e}). Usando fallback heurístico.")
        return heuristic_fallback_analysis(user_name, rating, content)

def test_gemini_key(api_key: str) -> tuple[bool, str]:
    """
    Testa se a chave do Gemini API é válida fazendo uma chamada leve.
    """
    if not api_key or not api_key.strip():
        return False, "Chave da API não fornecida."
    try:
        from google import genai
        client = genai.Client(api_key=api_key.strip())
        resp = client.models.generate_content(
            model="gemini-2.5-flash",
            contents="Responda apenas: OK"
        )
        if resp.text:
            return True, "Chave da API Gemini validada com sucesso! (Gemini 2.5 Flash conectado)"
        return False, "Resposta vazia da API."
    except Exception as e:
        return False, f"Falha na validação: {str(e)}"
