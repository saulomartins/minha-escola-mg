import os
import json
import logging
import re
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

OFFICIAL_SUPPORT_FORM = "https://forms.cloud.microsoft/r/JmZhSzXtwG"
OFFICIAL_SUPPORT_LABEL = "Canal de Suporte Oficial citado pela IA (Formulário Prodemge)"

SYSTEM_PROMPT = """Você é o assistente oficial de suporte e atendimento ao usuário do aplicativo "Minha Escola MG" (aplicativo oficial da Secretaria de Estado de Educação de Minas Gerais - SEE/MG e PRODEMGE).
Sua missão é analisar avaliações e comentários de usuários (estudantes, pais, professores e responsáveis) nas lojas Google Play Store e Apple App Store, categorizar o problema e redigir uma resposta oficial, cordial, prestativa e empática em Português do Brasil.

Diretrizes obrigatórias para as respostas:
1. Seja sempre educado, acolhedor e profissional.
2. Cumprimente o usuário pelo nome (se disponível) ou cordialmente ("Olá!", "Olá, estudante/responsável!").
3. REGRA CRÍTICA DO CANAL DE SUPORTE OFICIAL:
   - Para TODAS as avaliações com nota de 1 a 3 estrelas (1, 2 ou 3 estrelas): a resposta DEVE OBRIGATORIAMENTE indicar e solicitar que o usuário preencha o Canal de Suporte Oficial citado pela IA (Formulário Prodemge): https://forms.cloud.microsoft/r/JmZhSzXtwG.
   - Para avaliações de 4 ou 5 estrelas: avalie atentamente o comentário do usuário. Se houver QUALQUER menção ou contexto de problema, dificuldade, falha, erro, lentidão, travamento, tela preta, dificuldade de login/senha, divergência de notas ou faltas (ex: "o app é bom mas trava às vezes", "ótimo, porém não consigo ver o boletim", "gostei mas não entra"), a resposta TAMBÉM DEVE OBRIGATORIAMENTE solicitar que preencha o Canal de Suporte Oficial citado pela IA (Formulário Prodemge): https://forms.cloud.microsoft/r/JmZhSzXtwG.
   - Se a avaliação for de 4 ou 5 estrelas e contiver apenas elogios sinceros sem nenhum problema relatado, agradeça cordialmente sem necessidade do formulário.
4. REGRA OBRIGATÓRIA DE CONTATO: NUNCA utilize endereços de e-mail (como saulomartins.costa@gmail.com ou qualquer outro) na resposta. O único canal oficial a ser informado é o Canal de Suporte Oficial citado pela IA (Formulário Prodemge): https://forms.cloud.microsoft/r/JmZhSzXtwG.
5. Para PROBLEMAS DE ACESSO/LOGIN/SENHA: Oriente a verificar se o cadastro no sistema escolar/Simave/Gov.br está atualizado na secretaria da escola, ou a utilizar a recuperação de senha, e solicite o preenchimento do Canal de Suporte Oficial citado pela IA (Formulário Prodemge): https://forms.cloud.microsoft/r/JmZhSzXtwG.
6. Para BUGS/TRAVAMENTOS/TELA PRETA: Peça desculpas pelo transtorno, sugira atualizar o aplicativo para a versão mais recente, limpar o cache do app, e solicite o registro no Canal de Suporte Oficial citado pela IA (Formulário Prodemge): https://forms.cloud.microsoft/r/JmZhSzXtwG.
7. Para PROBLEMAS DE NOTAS/FALTAS NÃO ATUALIZADAS: Explique que o lançamento depende do Diário Escolar Digital (DED) pelos professores. Caso persista a divergência, oriente a procurar a coordenação da escola ou registrar no Canal de Suporte Oficial citado pela IA (Formulário Prodemge): https://forms.cloud.microsoft/r/JmZhSzXtwG.
8. Mantenha a resposta concisa (máximo de 3 a 4 frases), ideal para leitura em lojas de aplicativos.

Você DEVE responder SEMPRE em formato JSON com o seguinte formato:
{
  "sentiment": "POSITIVO" | "NEUTRO" | "NEGATIVO",
  "category": "Login/Acesso" | "Boletim/Notas" | "Falha Técnica" | "Usabilidade" | "Elogio" | "Outros",
  "suggested_response": "Texto da resposta pronto para ser publicado"
}
"""

def has_problem_context(content: str, rating: int) -> bool:
    """
    Avalia se a avaliação tem nota de 1 a 3 estrelas OU se contém qualquer contexto
    de problema, erro, falha, lentidão, bug ou dificuldade no texto do usuário.
    """
    if rating <= 3:
        return True

    text = (content or "").lower()
    problem_terms = [
        "problema", "erro", "bug", "falha", "trava", "travando", "travar", 
        "lento", "lentidão", "lentidao", "não entra", "nao entra", "não abre", 
        "nao abre", "fecha sozinho", "fechando", "fechar", "sai sozinho", "crash",
        "tela preta", "tela branca", "não consigo", "nao consigo", "dificuldade", 
        "senha", "esqueci", "recuperar", "bloquead", "nota sumiu", "não aparece", 
        "nao aparece", "divergência", "divergencia", "ajuda", "socorro", "arrumem", 
        "consertem", "corrijam", "piorou", "ruim", "péssimo", "pessimo", "odiei", 
        "horrível", "horrivel", "desinstalando", "mas ", "porém", "porem", "contudo", 
        "entretanto", "instável", "instavel", "não funciona", "nao funciona", 
        "cai toda hora", "carregando infinito", "não carrega", "nao carrega", 
        "faltou", "faltando", "consertar", "arrumar", "reclamar", "reclamação", 
        "reclamacao", "nada funciona", "não dá", "nao da", "deslogando", "desloga"
    ]
    return any(t in text for t in problem_terms)

def ensure_official_support_link(suggested_response: str, content: str, rating: int) -> str:
    """
    Garante que qualquer avaliação de 1 a 3 estrelas OU com qualquer contexto de problema
    contenham obrigatoriamente a indicação do Canal de Suporte Oficial citado pela IA (Formulário Prodemge).
    Garante também a remoção de qualquer menção acidental a e-mails.
    """
    cleaned = re.sub(r'[\w\.-]+@[\w\.-]+\.\w+', '', suggested_response).strip()
    
    if has_problem_context(content, rating):
        if "forms.cloud.microsoft" not in cleaned and "JmZhSzXtwG" not in cleaned:
            cleaned = (
                f"{cleaned} Para que possamos analisar e solucionar sua situação, por favor "
                f"preencha o Canal de Suporte Oficial citado pela IA (Formulário Prodemge): 👉 {OFFICIAL_SUPPORT_FORM}"
            )
            
    return cleaned

def heuristic_fallback_analysis(user_name: str, rating: int, content: str) -> Dict[str, Any]:
    """
    Análise heurística quando não há chave do Gemini configurada ou em caso de fallback.
    Garante sempre a indicação do Canal de Suporte Oficial citado pela IA (Formulário Prodemge)
    para notas de 1 a 3 estrelas ou qualquer menção a problemas.
    """
    content_lower = (content or "").lower()
    name_greeting = f"Olá, {user_name}!" if user_name and "usuário" not in user_name.lower() else "Olá!"
    
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
            f"Canal de Suporte Oficial citado pela IA (Formulário Prodemge): 👉 {OFFICIAL_SUPPORT_FORM}"
        )
    elif any(w in content_lower for w in ["nota", "boletim", "falta", "frequência", "frequencia", "bimestre", "ponto"]):
        category = "Boletim/Notas"
        response = (
            f"{name_greeting} Agradecemos pelo seu relato. As notas e frequências exibidas no Minha Escola MG "
            f"dependem da sincronização dos lançamentos feitos pelos professores no Diário Escolar Digital. "
            f"Caso haja divergências não resolvidas pela escola, por favor informe pelo "
            f"Canal de Suporte Oficial citado pela IA (Formulário Prodemge): 👉 {OFFICIAL_SUPPORT_FORM}"
        )
    elif any(w in content_lower for w in ["trava", "fecha", "bug", "erro", "carrega", "preta", "lento", "ruim", "péssimo", "atualização"]):
        category = "Falha Técnica"
        response = (
            f"{name_greeting} Lamentamos pelo ocorrido! Recomendamos verificar se o aplicativo está atualizado "
            f"para a versão mais recente na loja e limpar os dados de cache nas configurações do aparelho. "
            f"Persistindo a falha, pedimos que preencha o Canal de Suporte Oficial citado pela IA (Formulário Prodemge): 👉 {OFFICIAL_SUPPORT_FORM}"
        )
    elif rating >= 4 and not is_problem:
        category = "Elogio"
        response = f"{name_greeting} Ficamos muito felizes com a sua avaliação de {rating} estrelas e carinho! Nosso objetivo é sempre facilitar o dia a dia da comunidade escolar mineira. Conte conosco!"
    elif rating >= 4 and is_problem:
        category = "Falha Técnica" if any(w in content_lower for w in ["trava", "lento", "bug", "fecha"]) else "Usabilidade"
        response = (
            f"{name_greeting} Muito obrigado pela sua avaliação positiva! Notamos seu relato sobre instabilidade ou dificuldade. "
            f"Para que nossa equipe técnica possa verificar e solucionar o problema, por favor preencha o "
            f"Canal de Suporte Oficial citado pela IA (Formulário Prodemge): 👉 {OFFICIAL_SUPPORT_FORM}"
        )
    else:
        category = "Outros"
        response = (
            f"{name_greeting} Agradecemos por compartilhar sua opinião conosco. "
            f"Para nos ajudar a solucionar qualquer dificuldade ou dúvida no aplicativo, "
            f"pedimos que preencha o Canal de Suporte Oficial citado pela IA (Formulário Prodemge): 👉 {OFFICIAL_SUPPORT_FORM}"
        )
        
    return {
        "sentiment": sentiment,
        "category": category,
        "suggested_response": response
    }

def analyze_review(review: Dict[str, Any], api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Analisa uma avaliação usando o Gemini API (se chave disponível) ou fallback heurístico.
    Garante o direcionamento ao Canal de Suporte Oficial citado pela IA (Formulário Prodemge)
    para 1 a 3 estrelas e qualquer contexto de problema.
    """
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
                    f"Para nos ajudar a solucionar qualquer dificuldade no aplicativo, por favor registre no "
                    f"Canal de Suporte Oficial citado pela IA (Formulário Prodemge): 👉 {OFFICIAL_SUPPORT_FORM}"
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

DIRETRIZ MANDATÓRIA: Se a nota for de 1 a 3 estrelas OU se o comentário contiver QUALQUER menção a problema, erro, dificuldade, lentidão, tela preta, nota ou login (mesmo em avaliações de 4 ou 5 estrelas), a suggested_response DEVE OBRIGATORIAMENTE direcionar o usuário para o Canal de Suporte Oficial citado pela IA (Formulário Prodemge): https://forms.cloud.microsoft/r/JmZhSzXtwG.

Retorne o JSON estrito com sentiment, category e suggested_response."""

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config={
                "system_instruction": SYSTEM_PROMPT,
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
