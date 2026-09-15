import os
import json
import logging
import re
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Você é o assistente oficial de suporte e atendimento ao usuário do aplicativo "Minha Escola MG" (aplicativo oficial da Secretaria de Estado de Educação de Minas Gerais - SEE/MG e PRODEMGE).
Sua missão é analisar avaliações e comentários de usuários (estudantes, pais, professores e responsáveis) nas lojas Google Play Store e Apple App Store, categorizar o problema e redigir uma resposta oficial, cordial, prestativa e empática em Português do Brasil.

Diretrizes para as respostas:
1. Seja sempre educado, acolhedor e profissional.
2. Cumprimente o usuário pelo nome (se disponível) ou cordialmente ("Olá!", "Olá, estudante/responsável!").
3. Para ELOGIOS (4 ou 5 estrelas): Agradeça o carinho e reforce o compromisso com a melhoria da educação e do aplicativo.
4. Para PROBLEMAS DE ACESSO/LOGIN/SENHA: Oriente a verificar se o cadastro no sistema escolar/Simave/Gov.br está atualizado na secretaria da escola, ou a utilizar a opção de recuperação de senha.
5. Para BUGS/TRAVAMENTOS/TELA PRETA: Peça desculpas pelo transtorno, sugira atualizar o aplicativo para a versão mais recente, limpar o cache do app ou reinstalar, e oriente que em caso de persistência entre em contato com o suporte da escola ou canal oficial de atendimento.
6. Para PROBLEMAS DE NOTAS/FALTAS NÃO ATUALIZADAS: Explique que o lançamento de notas e frequências depende da sincronização feita pelos professores/escola no Diário Escolar Digital (DED).
7. Mantenha a resposta concisa (máximo de 3 a 4 frases), ideal para leitura em lojas de aplicativos.
8. REGRA OBRIGATÓRIA: NUNCA utilize endereços de e-mail (como saulomartins.costa@gmail.com ou qualquer outro) na resposta. Se for necessário direcionar o usuário para atendimento ou reporte de falhas, utilize SEMPRE o formulário oficial da Prodemge: 👉 https://forms.cloud.microsoft/r/JmZhSzXtwG.

Você DEVE responder SEMPRE em formato JSON com o seguinte formato:
{
  "sentiment": "POSITIVO" | "NEUTRO" | "NEGATIVO",
  "category": "Login/Acesso" | "Boletim/Notas" | "Falha Técnica" | "Usabilidade" | "Elogio" | "Outros",
  "suggested_response": "Texto da resposta pronto para ser publicado"
}
"""

def heuristic_fallback_analysis(user_name: str, rating: int, content: str) -> Dict[str, Any]:
    """
    Análise heurística quando não há chave do Gemini configurada.
    """
    content_lower = content.lower()
    name_greeting = f"Olá, {user_name}!" if user_name and "usuário" not in user_name.lower() else "Olá!"
    
    # Sentimento
    if rating >= 4:
        sentiment = "POSITIVO"
    elif rating == 3:
        sentiment = "NEUTRO"
    else:
        sentiment = "NEGATIVO"
        
    # Categoria e Resposta
    if any(w in content_lower for w in ["senha", "login", "entrar", "gov", "cpf", "acesso", "conta", "recuperar"]):
        category = "Login/Acesso"
        response = f"{name_greeting} Sentimos muito pela dificuldade de acesso. Verifique se o seu CPF e dados cadastrais estão atualizados junto à secretaria da sua escola. Se o erro persistir, utilize a opção 'Esqueci minha senha' ou procure a coordenação escolar para verificar o seu cadastro no sistema."
    elif any(w in content_lower for w in ["nota", "boletim", "falta", "frequência", "frequencia", "bimestre", "ponto"]):
        category = "Boletim/Notas"
        response = f"{name_greeting} Agradecemos pelo seu relato. As notas e frequências exibidas no Minha Escola MG dependem do lançamento realizado pelos professores no Diário Escolar Digital. Caso haja divergências, orientamos consultar a secretaria da escola para verificar a sincronização dos dados."
    elif any(w in content_lower for w in ["trava", "fecha", "bug", "erro", "carrega", "preta", "lento", "ruim", "péssimo", "atualização"]):
        category = "Falha Técnica"
        response = f"{name_greeting} Lamentamos pelo ocorrido! Nossa equipe técnica está trabalhando continuamente em melhorias. Recomendamos verificar se o aplicativo está atualizado para a versão mais recente na loja e limpar os dados de cache nas configurações do aparelho."
    elif rating >= 4 or any(w in content_lower for w in ["ótimo", "otimo", "excelente", "muito bom", "parabéns", "parabens", "adorei", "gostei"]):
        category = "Elogio"
        response = f"{name_greeting} Ficamos muito felizes com a sua avaliação e carinho! Nosso objetivo é sempre facilitar o dia a dia da comunidade escolar mineira. Conte conosco!"
    else:
        category = "Outros"
        response = f"{name_greeting} Agradecemos por compartilhar sua opinião conosco. Suas sugestões e relatos são fundamentais para que possamos continuar aprimorando o Minha Escola MG."
        
    return {
        "sentiment": sentiment,
        "category": category,
        "suggested_response": response
    }

def analyze_review(review: Dict[str, Any], api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Analisa uma avaliação usando o Gemini API (se chave disponível) ou fallback heurístico.
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
                "suggested_response": f"Olá! Sentimos muito que sua experiência não tenha sido 5 estrelas. Caso tenha sugestões ou dúvidas, procure o atendimento da sua escola para podermos melhorar."
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
        return {
            "sentiment": data.get("sentiment", "NEUTRO"),
            "category": data.get("category", "Outros"),
            "suggested_response": data.get("suggested_response", "")
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
