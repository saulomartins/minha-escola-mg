import sys
sys.stdout.reconfigure(encoding='utf-8')
from database.db import get_reviews, update_review_analysis, get_stats
from ai.analyzer import analyze_review

def test_reviews_flow():
    stats = get_stats()
    print("=== Estatísticas do Banco de Dados ===")
    print(f"Total: {stats['total']}")
    print(f"Google: {stats['google_total']} (Média: {stats['avg_google']})")
    print(f"Apple: {stats['apple_total']} (Média: {stats['avg_apple']})")
    
    reviews = get_reviews(limit=3)
    print("\n=== Testando Análise de IA em Comentários Reais ===")
    for idx, r in enumerate(reviews, 1):
        analysis = analyze_review(r)
        print(f"\n--- [Exemplo #{idx}] Loja: {r['store'].upper()} ---")
        print(f"Usuário: {r['user_name']}")
        print(f"Nota: {r['rating']} estrelas")
        print(f"Comentário: {r['content'][:120]}...")
        print(f"-> Sentimento: {analysis['sentiment']}")
        print(f"-> Categoria: {analysis['category']}")
        print(f"-> Resposta Sugerida: {analysis['suggested_response']}")
        
        update_review_analysis(
            review_id=r['id'],
            sentiment=analysis['sentiment'],
            category=analysis['category'],
            suggested_response=analysis['suggested_response']
        )
    print("\nAtualização no banco realizada com sucesso!")

if __name__ == "__main__":
    test_reviews_flow()
