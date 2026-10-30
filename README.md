# 📱 Central de Inteligência de Avaliações Mobile & Respostas com IA

Plataforma em Python com painel web moderno para monitoramento em tempo real, diagnóstico técnico de causas-raiz, telemetria de hardware/SO e automação de respostas inteligentes com **Google Gemini** para aplicativos nas lojas **Google Play Store** e **Apple App Store**.

O sistema é **100% parametrizável (White-Label / Multi-App)**, podendo ser facilmente configurado para monitorar qualquer aplicativo mobile sem necessidade de alterações no código-fonte.

---

## 🚀 Funcionalidades Principais

1. **Leitura Automatizada de Avaliações (Multi-Store)**:
   - **Google Play Store**: Coleta pública das avaliações e dados de telemetria oficiais via `google-play-scraper` ou API oficial do Google Play Developer.
   - **Apple App Store**: Coleta contínua via RSS oficial e extração de respostas de desenvolvedor.
2. **Parametrização & White-Label (Multi-App)**:
   - Suporte a múltiplos perfis de aplicativos via `app_config.json`, variáveis de ambiente (`.env`) ou diretamente pelo painel web.
   - Presets prontos para migração rápida entre apps na pasta `presets/`.
3. **Diagnóstico Técnico de Hardware & SO**:
   - Mapeamento de fabricantes (Samsung, Motorola, Xiaomi, Apple) e versões de Sistema Operacional (Android vs iOS).
   - Identificação de aparelhos congelados em versões descontinuadas (ex: Android 12) e diretrizes de engenharia.
4. **Análise de Causas-Raiz & Complexidade**:
   - Taxonomia com 11 categorias de problemas (Instabilidade de Login, Travamento, Gov.br, Senhas, etc.).
   - Mapeamento de severidade, complexidade técnica e diretrizes de resolução.
5. **Automação de Respostas com Google Gemini (2.5 Flash)**:
   - Respostas personalizadas por estrela (1 a 5 ⭐), contexto de problema e persona oficial do app.
   - Regra estrita de segurança: 5 estrelas recebe agradecimento positivo sem links; notas com problemas recebem direcionamento ao canal oficial configurado.
   - Motor heurístico integrado de fallback caso a chave de IA não esteja configurada.
6. **Painel Executivo & Relatórios**:
   - Gráficos de eficiência da IA, sentimento vs estrelas e tendências temporais.
   - Exportação de relatórios executivos em PDF e impressão.
   - Gestão de acessos por Tokens de Convidados e Google Identity Services (RBAC).

---

## ⚙️ Como Parametrizar para Outro Aplicativo Mobile

Você pode configurar um novo aplicativo para monitoramento de **3 formas diferentes**:

### 1. Pelo Arquivo de Configuração Central (`app_config.json`)
Edite o arquivo `app_config.json` na raiz do projeto:

```json
{
  "app_name": "Meu Aplicativo Mobile",
  "app_short_name": "meuapp",
  "organization_name": "Minha Empresa / Instituição",
  "developer_name": "Equipe de Tecnologia e Suporte",
  "support_url": "https://suporte.meuapp.com.br",
  "google_play": {
    "package_name": "com.exemplo.meuapp",
    "country": "br",
    "language": "pt"
  },
  "apple_store": {
    "app_id": "1234567890",
    "country": "br"
  }
}
```

### 2. Por Variáveis de Ambiente (`.env` ou Cloud Deploy - Render / Docker)
Ideal para deploys em nuvem sem alterar arquivos versionados:

```env
APP_NAME=Meu Aplicativo Mobile
ORGANIZATION_NAME=Minha Empresa
GOOGLE_PLAY_PACKAGE=com.exemplo.meuapp
APPLE_STORE_ID=1234567890
SUPPORT_CHANNEL_URL=https://suporte.meuapp.com.br
```

### 3. Diretamente pelo Painel Web
1. Abra o painel web e clique em **Configurações** (ícone de engrenagem no cabeçalho).
2. Acesse a aba **`4. 📱 App Monitorado`**.
3. Selecione um perfil da pasta `presets/` ou preencha o Nome do App, Pacote da Play Store, ID da Apple Store e Canal de Suporte.
4. Clique em **Salvar Configurações**.

---

## 🛠️ Como Executar

### 1. Iniciar o Painel Web
```powershell
cd C:\Users\saulo\.gemini\antigravity\scratch\app-reviews-analyzer
.venv\Scripts\python.exe main.py
```
O painel estará disponível em: **`http://localhost:8055`**

### 2. Sincronizar Avaliações via Linha de Comando
```powershell
.venv\Scripts\python.exe main.py --sync
```

---

## 📁 Estrutura do Projeto

```
app-reviews-analyzer/
├── app_config.json          # Configuração ativa do aplicativo monitorado
├── config.py                # Módulo central de carregamento de configurações
├── presets/                 # Perfis prontos de aplicativos (Minha Escola MG, App Cidadão, etc.)
├── main.py                  # Entrypoint CLI e inicialização do servidor
├── collector/
│   ├── google_play.py       # Coletor dinâmico da Google Play Store
│   └── apple_store.py       # Coletor dinâmico da Apple App Store
├── ai/
│   ├── analyzer.py          # Analisador de sentimento e categoria via Gemini 2.5 Flash
│   └── auto_reply_templates.py # Templates dinâmicos de resposta por causa-raiz
├── analytics/
│   ├── complexity.py        # Diagnóstico de complexidade e causas-raiz
│   ├── temporal.py          # Tendências temporais e evolução de notas
│   └── device_detector.py   # Detecção de modelos e versões de Android/iOS
├── database/
│   ├── db.py                # Camada SQLite, persistência de tokens e settings
│   └── reviews.db           # Banco de dados local
└── web/
    ├── app.py               # API FastAPI e endpoints REST
    └── templates/
        ├── index.html       # Painel interativo responsivo (Tailwind + Chart.js)
        └── login.html       # Tela de login e autenticação com token/Google
```
