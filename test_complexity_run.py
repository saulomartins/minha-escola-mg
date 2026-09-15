import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding='utf-8')

from analytics.complexity import get_detailed_problem_analytics

data = get_detailed_problem_analytics()
print(f"Total de Avaliações Analisadas: {data['total_reviews']}")
print(f"Total de Reclamações Mapeadas: {data['total_complaints']}")
print("\n=== TOP PROBLEMAS MAIS FREQUENTES (OFENSORES) ===")
for idx, p in enumerate(data['top_offenders'], 1):
    print(f"\n#{idx} - {p['name']}")
    print(f"   Ocorrências: {p['count']} ({p['percentage']}% do total geral)")
    print(f"   Severidade: {p['severity']} | Complexidade Técnica: {p['complexity']}")
    print(f"   Nota Média: {p['avg_rating']} ⭐")
    print(f"   Recomendação Técnica: {p['recommendation']}")

print("\n=== DISTRIBUIÇÃO DE SEVERIDADE ===")
print(data['severity_distribution'])

print("\n=== DISTRIBUIÇÃO DE COMPLEXIDADE TÉCNICA ===")
print(data['complexity_distribution'])
