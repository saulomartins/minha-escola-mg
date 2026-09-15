# 🎓 Minha Escola MG - Analisador de Avaliações e Resposta Inteligente

Sistema em Python com painel web moderno para coletar, analisar com Inteligência Artificial e responder avaliações de usuários do aplicativo **Minha Escola MG** nas lojas **Google Play Store** e **Apple App Store**.

---

## 🚀 Funcionalidades

1. **Leitura Automatizada de Comentários**:
   - **Google Play Store**: Coleta pública das avaliações mais recentes via `google-play-scraper` do app `com.prodemge.minhaescolamg`.
   - **Apple App Store**: Coleta das avaliações e títulos via RSS oficial da Apple para o ID `6749247611`.
2. **Armazenamento e Histórico**:
   - Banco de dados SQLite local (`reviews.db`) com prevenção automática de duplicatas e controle de status (`pendente`, `respondida`, `ignorada`).
3. **Classificação e IA (Gemini)**:
   - **Sentimento**: Classifica como `POSITIVO`, `NEUTRO` ou `NEGATIVO`.
   - **Tópicos**: Identifica problemas frequentes (`Login/Acesso`, `Boletim/Notas`, `Falha Técnica`, `Elogio`, `Outros`).
   - **Respostas Humanizadas**: Redige respostas polidas, profissionais e personalizadas com o nome do usuário e orientações oficiais da rede estadual de ensino de MG.
   - **Motor Heurístico Integrado**: Funciona imediatamente mesmo sem configurar chave da API!
4. **Painel Web Moderno**:
   - Métricas em tempo real (média de notas, total por loja, gráfico de sentimentos).
   - Filtros dinâmicos por loja, estrelas (1 a 5), sentimento e status.
   - Botão para copiar resposta em 1 clique ou marcar como respondida.
   - Modal de configurações para chave da API Gemini e regras de auto-resposta.

---

## 🛠️ Como Executar

### 1. Pré-requisitos
- Python 3.10 ou superior instalado.

### 2. Ativar o ambiente virtual e rodar o sistema
No terminal PowerShell, dentro da pasta do projeto:

```powershell
cd C:\Users\saulo\.gemini\antigravity\scratch\app-reviews-analyzer

# Iniciar o servidor e painel web
.venv\Scripts\python.exe main.py
```

O sistema fará a sincronização inicial das lojas automaticamente e disponibilizará o painel no navegador em:
👉 **`http://localhost:8000`**

### 3. Sincronização via Linha de Comando (Opcional)
Se desejar apenas atualizar os dados sem abrir o navegador:

```powershell
.venv\Scripts\python.exe main.py --sync
```

---

## 🤖 Como Configurar o Gemini API (Opcional)

Por padrão, o sistema já conta com um mecanismo inteligente em português brasileiro para categorizar e gerar respostas. 

Caso queira usar os modelos mais recentes do **Google Gemini (Gemini 2.5 Flash)** para respostas ainda mais personalizadas:
1. Abra o painel web em `http://localhost:8000`.
2. Clique no botão **Configurações** (canto superior direito).
3. Cole sua chave gratuita obtida no [Google AI Studio](https://aistudio.google.com/).
4. Clique em **Salvar Configurações**.
