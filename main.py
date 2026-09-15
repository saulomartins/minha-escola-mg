import argparse
import sys
import os
import uvicorn

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding='utf-8')

from database.db import init_db, upsert_review, get_stats, get_reviews
from collector.google_play import fetch_google_play_reviews
from collector.apple_store import fetch_apple_store_reviews
from ai.analyzer import analyze_review

def sync_all():
    print("Iniciando sincronização das avaliações do Minha Escola MG...")
    init_db()
    
    # Google Play
    print("-> Coletando avaliações da Google Play Store...")
    google_reviews = fetch_google_play_reviews(count=150)
    new_google = 0
    for r in google_reviews:
        if upsert_review(r):
            new_google += 1
    print(f"   Total obtido: {len(google_reviews)} (Novos no banco: {new_google})")

    # Apple App Store
    print("-> Coletando avaliações da Apple App Store...")
    apple_reviews = fetch_apple_store_reviews(max_pages=5)
    new_apple = 0
    for r in apple_reviews:
        if upsert_review(r):
            new_apple += 1
    print(f"   Total obtido: {len(apple_reviews)} (Novos no banco: {new_apple})")
    
    stats = get_stats()
    print("\nEstatísticas Atuais:")
    print(f"   Total de Avaliações: {stats['total']}")
    print(f"   Google Play: {stats['google_total']} (Média: {stats['avg_google']} estrelas)")
    print(f"   Apple Store: {stats['apple_total']} (Média: {stats['avg_apple']} estrelas)")

def run_server(host="0.0.0.0", port=8055):
    init_db()
    print(f"\n🚀 Servidor do Painel Web iniciado em: http://localhost:{port} (ou http://127.0.0.1:{port})")
    print("Pressione Ctrl+C para encerrar.\n")
    uvicorn.run("web.app:app", host=host, port=port, reload=False)

def main():
    parser = argparse.ArgumentParser(description="Sistema de Análise e Respostas de Avaliações - Minha Escola MG")
    parser.add_argument("--sync", action="store_true", help="Executa sincronização das lojas e salva no banco")
    parser.add_argument("--web", action="store_true", help="Inicia o painel web (padrão)")
    parser.add_argument("--port", type=int, default=8055, help="Porta para o servidor web (padrão 8055)")
    args = parser.parse_args()

    if args.sync:
        sync_all()
    else:
        # Se o banco estiver vazio, faz uma sincronização inicial automática
        stats = get_stats()
        if stats["total"] == 0:
            print("Banco de dados vazio. Executando primeira sincronização automática...")
            sync_all()
        run_server(port=args.port)

if __name__ == "__main__":
    main()
