"""
analytics/device_lifecycle.py
Base de conhecimento de ciclo de vida de hardware e suporte de Sistemas Operacionais.
Mapeia para cada aparelho:
- Versão de SO com que foi lançado
- Última versão de SO disponibilizada oficialmente pelo fabricante (Max OS)
- Situação do suporte pelo fabricante (Motorola, Samsung, Xiaomi, Apple) e Google
- Recomendações técnicas para a equipe de desenvolvimento (Prodemge)
"""

from typing import Dict, Any, Optional

# Base de modelos comuns no mercado brasileiro e no banco de dados
DEVICE_LIFECYCLE_DB = {
    # Motorola - Modelos Presos no Android <= 12 (Sem Atualização para Android 13+)
    "moto g22": {
        "brand": "Motorola",
        "model_name": "Moto G22",
        "launch_os": "Android 12",
        "max_os": "Android 12 (Nunca recebeu Android 13)",
        "is_stuck_android_12": True,
        "support_status": "🔴 Preso no Android 12 pelo Fabricante",
        "status_badge": "red",
        "google_oem_notes": "A Motorola NUNCA liberou o Android 13 para o Moto G22 no Brasil. 100% dos usuários deste modelo estão permanentemente no Android 12.",
        "dev_recommendation": "Impossível o usuário atualizar o celular. O aplicativo DEVE manter retrocompatibilidade e tolerância a falhas para o Android 12."
    },
    "moto e22": {
        "brand": "Motorola",
        "model_name": "Moto E22 / E22i",
        "launch_os": "Android 12 Go",
        "max_os": "Android 12 Go",
        "is_stuck_android_12": True,
        "support_status": "🔴 Preso no Android 12 Go (Sem Upgrades)",
        "status_badge": "red",
        "google_oem_notes": "A linha Moto E não recebe novas versões de SO pela Motorola. Permanece permanentemente no Android 12 Go.",
        "dev_recommendation": "Android Go Edition possui limites severos de memória RAM. Exige views leves sem animações pesadas."
    },
    "moto e32": {
        "brand": "Motorola",
        "model_name": "Moto E32",
        "launch_os": "Android 11",
        "max_os": "Android 12",
        "is_stuck_android_12": True,
        "support_status": "🔴 Preso no Android 12 (Suporte Encerrado)",
        "status_badge": "red",
        "google_oem_notes": "Recebeu atualização para Android 12 e teve suporte encerrado pela Motorola. Não recebe Android 13 ou 14.",
        "dev_recommendation": "Garantir compatibilidade com WebView e APIs do Android 12."
    },
    "moto g20": {
        "brand": "Motorola",
        "model_name": "Moto G20",
        "launch_os": "Android 11",
        "max_os": "Android 11",
        "is_stuck_android_12": True,
        "support_status": "🔴 Preso no Android 11 (Sem Atualização)",
        "status_badge": "red",
        "google_oem_notes": "Aparelho de entrada que nunca recebeu atualização de SO da Motorola. Preso no Android 11.",
        "dev_recommendation": "Suporte a Android 11 legado."
    },
    "moto g10": {
        "brand": "Motorola",
        "model_name": "Moto G10",
        "launch_os": "Android 11",
        "max_os": "Android 11",
        "is_stuck_android_12": True,
        "support_status": "🔴 Preso no Android 11 (Descontinuado)",
        "status_badge": "red",
        "google_oem_notes": "Encerrado no Android 11 sem previsão ou possibilidade de upgrade.",
        "dev_recommendation": "Compatibilidade com SO legado."
    },
    "moto g30": {
        "brand": "Motorola",
        "model_name": "Moto G30",
        "launch_os": "Android 11",
        "max_os": "Android 12",
        "is_stuck_android_12": True,
        "support_status": "🔴 Preso no Android 12 (Ciclo Encerrado)",
        "status_badge": "red",
        "google_oem_notes": "Atualizado para Android 12 e encerrado pela Motorola. Não recebe Android 13.",
        "dev_recommendation": "Otimizar para chip Snapdragon 662 no Android 12."
    },
    "moto g7": {
        "brand": "Motorola",
        "model_name": "Moto G7 / Play / Power",
        "launch_os": "Android 9 (Pie)",
        "max_os": "Android 10",
        "is_stuck_android_12": True,
        "support_status": "🔴 Descontinuado (Parou no Android 10)",
        "status_badge": "red",
        "google_oem_notes": "Suporte encerrado há anos. Preso no Android 10.",
        "dev_recommendation": "Dispositivo legado de alunos de baixa renda."
    },
    "moto g8": {
        "brand": "Motorola",
        "model_name": "Moto G8 / Play / Power",
        "launch_os": "Android 10",
        "max_os": "Android 11",
        "is_stuck_android_12": True,
        "support_status": "🔴 Descontinuado (Parou no Android 11)",
        "status_badge": "red",
        "google_oem_notes": "Suporte encerrado no Android 11.",
        "dev_recommendation": "Dispositivo legado."
    },
    "moto g9": {
        "brand": "Motorola",
        "model_name": "Moto G9 / Play / Plus",
        "launch_os": "Android 10",
        "max_os": "Android 11",
        "is_stuck_android_12": True,
        "support_status": "🔴 Descontinuado (Parou no Android 11)",
        "status_badge": "red",
        "google_oem_notes": "Suporte encerrado no Android 11.",
        "dev_recommendation": "Dispositivo legado."
    },

    # Motorola - Outros Modelos
    "moto g32": {
        "brand": "Motorola",
        "model_name": "Moto G32",
        "launch_os": "Android 12",
        "max_os": "Android 13",
        "is_stuck_android_12": False,
        "support_status": "⚠️ Encerrado no Android 13 (Sem Android 14)",
        "status_badge": "amber",
        "google_oem_notes": "A Motorola encerrou as atualizações de SO no Android 13. Não há e não haverá atualização para Android 14 ou 15.",
        "dev_recommendation": "Usuários no Android 12 que não atualizaram estão presos nele. Como o aparelho não suporta versões mais novas, qualquer correção de bug deve ser feita diretamente no código do aplicativo."
    },
    "moto g04": {
        "brand": "Motorola",
        "model_name": "Moto G04",
        "launch_os": "Android 14",
        "max_os": "Android 14",
        "is_stuck_android_12": False,
        "support_status": "⚠️ Sem previsão de novos upgrades",
        "status_badge": "amber",
        "google_oem_notes": "Aparelho de entrada lançado com Android 14. A Motorola costuma não disponibilizar novas versões de SO para a linha G0x.",
        "dev_recommendation": "Otimizar uso de RAM (aparelho com 4GB). Garantir carregamento assíncrono."
    },
    "moto g14": {
        "brand": "Motorola",
        "model_name": "Moto G14",
        "launch_os": "Android 13",
        "max_os": "Android 14",
        "is_stuck_android_12": False,
        "support_status": "⚠️ Ciclo final no Android 14",
        "status_badge": "amber",
        "google_oem_notes": "Recebeu upgrade para Android 14. Não receberá Android 15.",
        "dev_recommendation": "Manter compatibilidade com Android 13 e 14."
    },
    "moto g54": {
        "brand": "Motorola",
        "model_name": "Moto G54",
        "launch_os": "Android 13",
        "max_os": "Android 14",
        "is_stuck_android_12": False,
        "support_status": "✅ Suporte Ativo",
        "status_badge": "green",
        "google_oem_notes": "Recebeu Android 14 e patches regulares de segurança.",
        "dev_recommendation": "Excelente compatibilidade de hardware."
    },

    # Samsung - Modelos Presos no Android <= 12
    "galaxy a10": {
        "brand": "Samsung",
        "model_name": "Galaxy A10 / A10s",
        "launch_os": "Android 9 (Pie)",
        "max_os": "Android 11",
        "is_stuck_android_12": True,
        "support_status": "🔴 Preso no Android 11 (Descontinuado)",
        "status_badge": "red",
        "google_oem_notes": "Aparelho descontinuado pela Samsung e com suporte de segurança já encerrado pelo Google. Nunca receberá Android 12 ou 13.",
        "dev_recommendation": "Se o app exigir Android 12+, este aparelho não conseguirá instalar na Google Play."
    },
    "galaxy a01": {
        "brand": "Samsung",
        "model_name": "Galaxy A01 / Core",
        "launch_os": "Android 10",
        "max_os": "Android 11 / 12 (Core)",
        "is_stuck_android_12": True,
        "support_status": "🔴 Preso no Android 11/12 (Descontinuado)",
        "status_badge": "red",
        "google_oem_notes": "Suporte encerrado permanentemente pela Samsung.",
        "dev_recommendation": "Memória RAM extremamente limitada (2GB). Requer versão ultra leve."
    },
    "galaxy a02": {
        "brand": "Samsung",
        "model_name": "Galaxy A02 / A02s",
        "launch_os": "Android 10 / 11",
        "max_os": "Android 12",
        "is_stuck_android_12": True,
        "support_status": "🔴 Preso no Android 12 (Sem Android 13)",
        "status_badge": "red",
        "google_oem_notes": "A Samsung encerrou atualizações no Android 12 (One UI Core 4.1). Não recebe Android 13.",
        "dev_recommendation": "Otimizar telas pesadas."
    },
    "galaxy a03 core": {
        "brand": "Samsung",
        "model_name": "Galaxy A03 Core",
        "launch_os": "Android 11 Go",
        "max_os": "Android 12 Go",
        "is_stuck_android_12": True,
        "support_status": "🔴 Preso no Android 12 Go (Sem Android 13)",
        "status_badge": "red",
        "google_oem_notes": "Modelo com Android Go Edition, parado no Android 12 Go sem upgrade para Android 13.",
        "dev_recommendation": "Gerenciamento severo de RAM."
    },
    "galaxy a11": {
        "brand": "Samsung",
        "model_name": "Galaxy A11",
        "launch_os": "Android 10",
        "max_os": "Android 12",
        "is_stuck_android_12": True,
        "support_status": "🔴 Preso no Android 12 (Sem Android 13)",
        "status_badge": "red",
        "google_oem_notes": "A Samsung encerrou atualizações no Android 12.",
        "dev_recommendation": "Compatibilidade com Android 12."
    },
    "galaxy a12": {
        "brand": "Samsung",
        "model_name": "Galaxy A12",
        "launch_os": "Android 10",
        "max_os": "Android 12",
        "is_stuck_android_12": True,
        "support_status": "🔴 Preso no Android 12 (Sem Android 13)",
        "status_badge": "red",
        "google_oem_notes": "Um dos aparelhos mais vendidos no Brasil. Encerrado permanentemente no Android 12 pela Samsung.",
        "dev_recommendation": "Essencial garantir bom desempenho no Android 12 para atender milhões de usuários deste modelo."
    },
    "galaxy a20": {
        "brand": "Samsung",
        "model_name": "Galaxy A20 / A20s",
        "launch_os": "Android 9",
        "max_os": "Android 11",
        "is_stuck_android_12": True,
        "support_status": "🔴 Preso no Android 11 (Descontinuado)",
        "status_badge": "red",
        "google_oem_notes": "Suporte encerrado no Android 11.",
        "dev_recommendation": "Aparelho antigo comum entre famílias de estudantes."
    },
    "galaxy a21s": {
        "brand": "Samsung",
        "model_name": "Galaxy A21s",
        "launch_os": "Android 10",
        "max_os": "Android 12",
        "is_stuck_android_12": True,
        "support_status": "🔴 Preso no Android 12 (Sem Android 13)",
        "status_badge": "red",
        "google_oem_notes": "Encerrado no Android 12 pela Samsung.",
        "dev_recommendation": "Manter suporte ao Android 12."
    },
    "galaxy j4": {
        "brand": "Samsung",
        "model_name": "Galaxy J4 / J4+",
        "launch_os": "Android 8.0",
        "max_os": "Android 10",
        "is_stuck_android_12": True,
        "support_status": "🔴 Descontinuado (Parou no Android 10)",
        "status_badge": "red",
        "google_oem_notes": "Linha Galaxy J descontinuada pela Samsung.",
        "dev_recommendation": "Dispositivo legado."
    },
    "galaxy j7": {
        "brand": "Samsung",
        "model_name": "Galaxy J7 / Prime",
        "launch_os": "Android 6.0",
        "max_os": "Android 9 (Pie)",
        "is_stuck_android_12": True,
        "support_status": "🔴 Descontinuado (Parou no Android 9)",
        "status_badge": "red",
        "google_oem_notes": "Descontinuado há anos.",
        "dev_recommendation": "Aparelho muito antigo."
    },

    # Samsung - Outros Modelos
    "galaxy a03": {
        "brand": "Samsung",
        "model_name": "Galaxy A03",
        "launch_os": "Android 11",
        "max_os": "Android 13",
        "is_stuck_android_12": False,
        "support_status": "⚠️ Encerrado no Android 13",
        "status_badge": "amber",
        "google_oem_notes": "A Samsung encerrou grandes atualizações no Android 13.",
        "dev_recommendation": "Processador Unisoc humilde; necessita de bom gerenciamento de rede."
    },
    "galaxy a14": {
        "brand": "Samsung",
        "model_name": "Galaxy A14",
        "launch_os": "Android 13",
        "max_os": "Android 15 (Política Samsung)",
        "is_stuck_android_12": False,
        "support_status": "✅ Suporte Ativo Samsung",
        "status_badge": "green",
        "google_oem_notes": "A Samsung garante até Android 15 para o A14.",
        "dev_recommendation": "Aparelho muito comum entre estudantes no Brasil."
    },
    "galaxy s20 fe": {
        "brand": "Samsung",
        "model_name": "Galaxy S20 FE",
        "launch_os": "Android 10",
        "max_os": "Android 13",
        "is_stuck_android_12": False,
        "support_status": "⚠️ Encerrado no Android 13 (Sem Android 14)",
        "status_badge": "amber",
        "google_oem_notes": "A Samsung encerrou a linha S20 no Android 13 (One UI 5.1). Não recebe Android 14.",
        "dev_recommendation": "Hardware potente, problemas nele geralmente são de rede ou WebView."
    },

    # Xiaomi - Modelos Presos no Android <= 12
    "redmi 9": {
        "brand": "Xiaomi",
        "model_name": "Redmi 9 / 9A / 9C",
        "launch_os": "Android 10 (MIUI 11)",
        "max_os": "Android 11 (MIUI 12.5)",
        "is_stuck_android_12": True,
        "support_status": "🔴 Preso no Android 11 (Descontinuado)",
        "status_badge": "red",
        "google_oem_notes": "A Xiaomi encerrou atualizações no Android 11. Sem upgrade para Android 12 ou 13.",
        "dev_recommendation": "Aparelho de baixo custo muito popular."
    },
    "redmi 10a": {
        "brand": "Xiaomi",
        "model_name": "Redmi 10A",
        "launch_os": "Android 11",
        "max_os": "Android 11 (MIUI 12.5)",
        "is_stuck_android_12": True,
        "support_status": "🔴 Preso no Android 11 (Sem Upgrades)",
        "status_badge": "red",
        "google_oem_notes": "Parado no Android 11 pela Xiaomi.",
        "dev_recommendation": "Manter compatibilidade com Android 11."
    },
    "redmi note 8": {
        "brand": "Xiaomi",
        "model_name": "Redmi Note 8",
        "launch_os": "Android 9 (Pie)",
        "max_os": "Android 11",
        "is_stuck_android_12": True,
        "support_status": "🔴 Preso no Android 11 (Descontinuado)",
        "status_badge": "red",
        "google_oem_notes": "Um dos aparelhos Xiaomi mais vendidos no Brasil. Encerrado no Android 11.",
        "dev_recommendation": "Hardware de 2019 ainda em uso por muitos alunos."
    },
    "redmi note 9": {
        "brand": "Xiaomi",
        "model_name": "Redmi Note 9 / 9S",
        "launch_os": "Android 10",
        "max_os": "Android 12 (MIUI 13)",
        "is_stuck_android_12": True,
        "support_status": "🔴 Preso no Android 12 (Sem Android 13)",
        "status_badge": "red",
        "google_oem_notes": "Encerrado no Android 12 pela Xiaomi. Não recebe Android 13.",
        "dev_recommendation": "Otimizar para MIUI 13 no Android 12."
    },

    # Xiaomi - Outros Modelos
    "redmi 13c": {
        "brand": "Xiaomi",
        "model_name": "Redmi 13C",
        "launch_os": "Android 13 (MIUI 14)",
        "max_os": "Android 14 (HyperOS)",
        "is_stuck_android_12": False,
        "support_status": "✅ Atualizado para Android 14",
        "status_badge": "green",
        "google_oem_notes": "A Xiaomi disponibilizou upgrade para o HyperOS (Android 14).",
        "dev_recommendation": "Em versões de 4GB RAM, o HyperOS consome muita memória de fundo. Recomenda-se evitar memory leaks na abertura de PDFs e notas."
    },
    "redmi 12c": {
        "brand": "Xiaomi",
        "model_name": "Redmi 12C",
        "launch_os": "Android 12",
        "max_os": "Android 13",
        "is_stuck_android_12": False,
        "support_status": "⚠️ Encerrado no Android 13",
        "status_badge": "amber",
        "google_oem_notes": "A Xiaomi encerrou atualizações no Android 13.",
        "dev_recommendation": "Manter suporte ao Android 12 e 13."
    },
    "redmi note 12": {
        "brand": "Xiaomi",
        "model_name": "Redmi Note 12",
        "launch_os": "Android 13",
        "max_os": "Android 14 (HyperOS)",
        "is_stuck_android_12": False,
        "support_status": "✅ Suporte Ativo",
        "status_badge": "green",
        "google_oem_notes": "Atualizado para Android 14.",
        "dev_recommendation": "Hardware intermediário equilibrado."
    },

    # LG - Todos os Modelos Presos no Android <= 12 (Divisão Encerrada)
    "lg k52": {
        "brand": "LG",
        "model_name": "LG K52",
        "launch_os": "Android 10",
        "max_os": "Android 11",
        "is_stuck_android_12": True,
        "support_status": "🔴 Preso no Android 11 (LG Fechou Divisão Mobile)",
        "status_badge": "red",
        "google_oem_notes": "A LG encerrou sua divisão mundial de celulares. Não há suporte, correções ou upgrades para Android 12 ou 13.",
        "dev_recommendation": "Usuário não tem para onde ir. Qualquer correção de compatibilidade é de responsabilidade da Prodemge."
    },
    "lg k62": {
        "brand": "LG",
        "model_name": "LG K62",
        "launch_os": "Android 10",
        "max_os": "Android 12",
        "is_stuck_android_12": True,
        "support_status": "🔴 Preso no Android 12 (LG Fechou Divisão Mobile)",
        "status_badge": "red",
        "google_oem_notes": "Recebeu Android 12 final antes do encerramento da divisão de celulares da LG.",
        "dev_recommendation": "Compatibilidade com Android 12."
    },
    "lg k41s": {
        "brand": "LG",
        "model_name": "LG K41s / K51s",
        "launch_os": "Android 9",
        "max_os": "Android 11",
        "is_stuck_android_12": True,
        "support_status": "🔴 Preso no Android 11 (Divisão Encerrada)",
        "status_badge": "red",
        "google_oem_notes": "Suporte encerrado.",
        "dev_recommendation": "Dispositivo legado."
    },

    # Apple
    "iphone 6s": {
        "brand": "Apple",
        "model_name": "iPhone 6s / 7",
        "launch_os": "iOS 9 / 10",
        "max_os": "iOS 15.8",
        "is_stuck_android_12": False,
        "support_status": "🔴 Descontinuado pela Apple (Parou no iOS 15)",
        "status_badge": "red",
        "google_oem_notes": "A Apple não permite atualizar para iOS 16, 17 ou 18.",
        "dev_recommendation": "Não há novos recursos de sistema disponíveis."
    },
    "iphone 8": {
        "brand": "Apple",
        "model_name": "iPhone 8 / iPhone X",
        "launch_os": "iOS 11",
        "max_os": "iOS 16.7",
        "is_stuck_android_12": False,
        "support_status": "⚠️ Encerrado no iOS 16 (Sem iOS 17/18)",
        "status_badge": "amber",
        "google_oem_notes": "A Apple encerrou o suporte a novas versões no iOS 16.",
        "dev_recommendation": "Aparelhos presos no iOS 16."
    },
    "iphone 11": {
        "brand": "Apple",
        "model_name": "iPhone 11",
        "launch_os": "iOS 13",
        "max_os": "iOS 18 (Atual)",
        "is_stuck_android_12": False,
        "support_status": "✅ Suporte Ativo Apple",
        "status_badge": "green",
        "google_oem_notes": "Suporte pleno à versão mais recente do iOS.",
        "dev_recommendation": "Excelente estabilidade."
    }
}


# Base de ciclo de vida dos Sistemas Operacionais (Google & Apple)
OS_LIFECYCLE_DB = {
    "Android 15": {
        "os_name": "Android",
        "version": "Android 15",
        "launch_year": "2024",
        "google_status": "✅ Suporte Total e Ativo pelo Google",
        "badge": "green",
        "details": "Versão mais recente com suporte pleno a todas as APIs modernas."
    },
    "Android 14": {
        "os_name": "Android",
        "version": "Android 14",
        "launch_year": "2023",
        "google_status": "✅ Suporte Total e Ativo pelo Google",
        "badge": "green",
        "details": "Versão estável com distribuição em expansão em aparelhos 2023/2024."
    },
    "Android 13": {
        "os_name": "Android",
        "version": "Android 13",
        "launch_year": "2022",
        "google_status": "🟡 Suporte de Manutenção pelo Google",
        "badge": "blue",
        "details": "Recebe patches de segurança, mas a maioria dos fabricantes encerrou novas builds."
    },
    "Android 12": {
        "os_name": "Android",
        "version": "Android 12 / 12L",
        "launch_year": "2021",
        "google_status": "⚠️ Sem suporte ativo do Google / Descontinuado por Fabricantes",
        "badge": "amber",
        "details": "Gargalo Crítico: O Google encerrou o suporte ativo e os fabricantes não liberaram Android 13/14 para modelos de entrada. Milhões de aparelhos no Brasil estão permanentemente travados no Android 12 sem possibilidade de upgrade pelo usuário."
    },
    "Android 11": {
        "os_name": "Android",
        "version": "Android 11",
        "launch_year": "2020",
        "google_status": "🔴 Descontinuado pelo Google (Sem Patches)",
        "badge": "red",
        "details": "Fim do ciclo de vida de segurança pelo Google."
    },
    "Android 10": {
        "os_name": "Android",
        "version": "Android 10 e anteriores",
        "launch_year": "2019",
        "google_status": "🔴 Legado / Sem Suporte",
        "badge": "red",
        "details": "Sistemas obsoletos com suporte descontinuado."
    },
    "iOS 18": {
        "os_name": "iOS",
        "version": "iOS 18",
        "launch_year": "2024",
        "google_status": "✅ Suporte Pleno Apple",
        "badge": "green",
        "details": "Versão mais recente da Apple."
    },
    "iOS 17": {
        "os_name": "iOS",
        "version": "iOS 17",
        "launch_year": "2023",
        "google_status": "✅ Suporte Ativo Apple",
        "badge": "green",
        "details": "Suporte oficial e compatibilidade plena."
    },
    "iOS 16": {
        "os_name": "iOS",
        "version": "iOS 16",
        "launch_year": "2022",
        "google_status": "🟡 Manutenção Estrita Apple",
        "badge": "amber",
        "details": "Recebe apenas patches críticos de segurança. iPhone 8 e X pararam aqui."
    },
    "iOS 15": {
        "os_name": "iOS",
        "version": "iOS 15 e anteriores",
        "launch_year": "2021",
        "google_status": "🔴 Descontinuado para Novos Recursos",
        "badge": "red",
        "details": "Aparelhos como iPhone 6s e 7 não suportam versões mais novas."
    }
}

def get_device_lifecycle(brand: Optional[str], model: Optional[str]) -> Dict[str, Any]:
    """
    Retorna metadados de ciclo de vida e última versão de SO suportada para um modelo de celular.
    """
    if not model or model in ("Não especificado", "Geral", "Dispositivo Android", "Apple iPhone"):
        b_name = (brand or "").lower()
        if "apple" in b_name:
            return {
                "launch_os": "iOS 15 - 18",
                "max_os": "iOS 18 (Varia por modelo)",
                "support_status": "ℹ️ Depende do iPhone (Apple oculta modelo)",
                "status_badge": "slate",
                "notes": "A Apple não informa o modelo do iPhone nas avaliações por privacidade. Modelos do iPhone XR/11 em diante suportam iOS 18; iPhone X/8 pararam no iOS 16.",
                "recommendation": "Garantir compatibilidade com iOS 16 em diante."
            }
        return {
            "launch_os": "Variável",
            "max_os": "Depende do modelo específico",
            "support_status": "ℹ️ Modelo não especificado no comentário",
            "status_badge": "slate",
            "notes": "O usuário não digitou o modelo específico no texto do comentário.",
            "recommendation": "Solicitar o modelo do celular no formulário de suporte caso o usuário relate erro de sistema."
        }
        
    m_clean = model.lower().strip()
    
    # 1. Busca exata
    if m_clean in DEVICE_LIFECYCLE_DB:
        return DEVICE_LIFECYCLE_DB[m_clean]
        
    # 2. Busca por termos
    for key, data in DEVICE_LIFECYCLE_DB.items():
        if key in m_clean or m_clean in key:
            return data
            
    # 3. Heurísticas baseadas no nome
    if "g22" in m_clean:
        return DEVICE_LIFECYCLE_DB["moto g22"]
    if "e22" in m_clean:
        return DEVICE_LIFECYCLE_DB["moto e22"]
    if "e32" in m_clean:
        return DEVICE_LIFECYCLE_DB["moto e32"]
    if "g20" in m_clean:
        return DEVICE_LIFECYCLE_DB["moto g20"]
    if "g10" in m_clean:
        return DEVICE_LIFECYCLE_DB["moto g10"]
    if "g30" in m_clean:
        return DEVICE_LIFECYCLE_DB["moto g30"]
    if "g32" in m_clean:
        return DEVICE_LIFECYCLE_DB["moto g32"]
    if "g04" in m_clean:
        return DEVICE_LIFECYCLE_DB["moto g04"]
    if "g14" in m_clean:
        return DEVICE_LIFECYCLE_DB["moto g14"]
    if "g54" in m_clean:
        return DEVICE_LIFECYCLE_DB["moto g54"]
    if "g7" in m_clean:
        return DEVICE_LIFECYCLE_DB["moto g7"]
    if "g8" in m_clean:
        return DEVICE_LIFECYCLE_DB["moto g8"]
    if "g9" in m_clean:
        return DEVICE_LIFECYCLE_DB["moto g9"]
    if "a10" in m_clean:
        return DEVICE_LIFECYCLE_DB["galaxy a10"]
    if "a01" in m_clean:
        return DEVICE_LIFECYCLE_DB["galaxy a01"]
    if "a02" in m_clean:
        return DEVICE_LIFECYCLE_DB["galaxy a02"]
    if "a03" in m_clean:
        return DEVICE_LIFECYCLE_DB["galaxy a03 core"] if "core" in m_clean else DEVICE_LIFECYCLE_DB["galaxy a03"]
    if "a11" in m_clean:
        return DEVICE_LIFECYCLE_DB["galaxy a11"]
    if "a12" in m_clean:
        return DEVICE_LIFECYCLE_DB["galaxy a12"]
    if "a14" in m_clean:
        return DEVICE_LIFECYCLE_DB["galaxy a14"]
    if "a20" in m_clean:
        return DEVICE_LIFECYCLE_DB["galaxy a20"]
    if "a21" in m_clean:
        return DEVICE_LIFECYCLE_DB["galaxy a21s"]
    if "k52" in m_clean:
        return DEVICE_LIFECYCLE_DB["lg k52"]
    if "k62" in m_clean:
        return DEVICE_LIFECYCLE_DB["lg k62"]
    if "k41" in m_clean or "k51" in m_clean:
        return DEVICE_LIFECYCLE_DB["lg k41s"]
    if "13c" in m_clean:
        return DEVICE_LIFECYCLE_DB["redmi 13c"]
    if "12c" in m_clean:
        return DEVICE_LIFECYCLE_DB["redmi 12c"]
    if "note 12" in m_clean:
        return DEVICE_LIFECYCLE_DB["redmi note 12"]
    if "note 8" in m_clean:
        return DEVICE_LIFECYCLE_DB["redmi note 8"]
    if "note 9" in m_clean:
        return DEVICE_LIFECYCLE_DB["redmi note 9"]
    if "10a" in m_clean:
        return DEVICE_LIFECYCLE_DB["redmi 10a"]
    if "redmi 9" in m_clean or "9a" in m_clean or "9c" in m_clean:
        return DEVICE_LIFECYCLE_DB["redmi 9"]
        
    # Padrão para modelos desconhecidos
    return {
        "launch_os": "Não catalogado",
        "max_os": "Verificar com fabricante",
        "is_stuck_android_12": False,
        "support_status": "🟡 Verificar com o fabricante",
        "status_badge": "amber",
        "notes": f"Modelo {model} identificado via relato do usuário.",
        "recommendation": "Verificar se o fabricante disponibilizou Android 13/14 para este hardware específico."
    }

def get_os_lifecycle(os_version_str: Optional[str]) -> Dict[str, Any]:
    """
    Retorna o status de suporte do Google ou Apple para uma dada versão de SO.
    """
    if not os_version_str:
        return {
            "google_status": "Indefinido",
            "badge": "slate",
            "details": "Versão não informada."
        }
        
    v_clean = os_version_str.strip()
    
    # Busca direta
    for k, v in OS_LIFECYCLE_DB.items():
        if k.lower() in v_clean.lower():
            return v
            
    # Procura por números
    if "15" in v_clean:
        return OS_LIFECYCLE_DB.get("Android 15" if "ios" not in v_clean.lower() else "iOS 18", {})
    if "14" in v_clean:
        return OS_LIFECYCLE_DB.get("Android 14" if "ios" not in v_clean.lower() else "iOS 17", {})
    if "13" in v_clean:
        return OS_LIFECYCLE_DB.get("Android 13" if "ios" not in v_clean.lower() else "iOS 16", {})
    if "12" in v_clean:
        return OS_LIFECYCLE_DB.get("Android 12", {})
    if "11" in v_clean:
        return OS_LIFECYCLE_DB.get("Android 11", {})
    if any(n in v_clean for n in ["10", "9", "8", "7", "6", "5"]):
        return OS_LIFECYCLE_DB.get("Android 10", {})
        
    return {
        "google_status": "Verificar",
        "badge": "slate",
        "details": f"Versão {os_version_str}"
    }

def evaluate_stuck_android_12(
    brand: Optional[str] = None,
    model: Optional[str] = None,
    os_name: Optional[str] = None,
    os_version: Optional[str] = None,
    content: Optional[str] = None
) -> Dict[str, Any]:
    """
    Avalia se um dispositivo/avaliação refere-se a um celular que NÃO ATUALIZA para versão maior que Android 12
    (ou seja, parou no Android 12, 11, 10 ou anterior, e não recebe mais atualização para Android 13+).
    """
    brand_lower = (brand or "").lower()
    os_name_lower = (os_name or "").lower()
    content_lower = (content or "").lower()
    os_ver_str = (os_version or "").strip()
    
    # Se for Apple / iOS, não se aplica à regra do Android
    if "apple" in brand_lower or "ios" in os_name_lower or "iphone" in brand_lower or "ipad" in brand_lower:
        return {
            "is_stuck": False,
            "badge_text": None,
            "badge_subtext": None,
            "badge_color": None,
            "reason": "Dispositivo Apple iOS (não utiliza Android)",
            "max_os": "iOS",
            "support_status": "Apple",
            "user_action_possible": True,
            "recommendation": ""
        }
        
    life = get_device_lifecycle(brand, model)
    max_os = life.get("max_os", "")
    
    is_stuck = False
    reasons = []
    
    # 1. Verificação direta pelo modelo catalogado
    if life.get("is_stuck_android_12") is True:
        is_stuck = True
        reasons.append(f"O modelo '{life.get('model_name', model)}' parou em {max_os}. A fabricante encerrou as atualizações e não libera Android 13+.")
        
    # 2. Verificação se max_os explicitamente indica <= 12
    elif any(k in max_os.lower() for k in ["android 12", "android 11", "android 10", "android 9", "android 8"]) and not any(k in max_os.lower() for k in ["android 13", "android 14", "android 15"]):
        is_stuck = True
        reasons.append(f"Aparelho com suporte máximo homologado em {max_os}.")
        
    # 3. Verificação pela versão de SO relatada
    if any(k in os_ver_str for k in ["Android 12", "Android 11", "Android 10", "Android 9", "Android 8", "Android 7", "Android 6", "Android 5"]):
        # Se for Android 12 ou anterior, e o modelo não é confirmado como tendo Android 14/15
        if not ("Android 14" in max_os or "Android 15" in max_os):
            is_stuck = True
            reasons.append(f"Aparelho no {os_ver_str} (Google encerrou suporte ativo e fabricantes congelaram modelos de entrada sem upgrade para Android 13+).")
            
    # 4. Verificação por menção explícita no texto da avaliação
    incompat_phrases = [
        "não pode ser instalado mais no android 12",
        "não instala mais no android 12",
        "parou de funcionar no android 12",
        "não tem atualização pra alguns celulares",
        "no celular do meu filho não dá para baixar",
        "parou de ser compatível com meu telefone",
        "não é compatível com esta versão",
        "não dá para todos os celular",
        "meu celular não atualiza",
        "celular antigo",
        "aparelho antigo",
        "não atualiza mais",
        "incompatível com meu celular",
        "dispositivo não é compatível"
    ]
    for phrase in incompat_phrases:
        if phrase in content_lower:
            is_stuck = True
            reasons.append(f"Relato explícito do usuário: '{phrase}'.")
            break
            
    if is_stuck:
        final_reason = " | ".join(reasons) if reasons else f"Aparelho preso em {max_os} sem suporte a Android 13+."
        return {
            "is_stuck": True,
            "badge_text": "🛑 Preso no Android ≤ 12",
            "badge_subtext": "Sem atualização para Android 13+",
            "badge_color": "red",
            "reason": final_reason,
            "max_os": max_os if max_os != "Verificar com fabricante" else (os_ver_str or "Android 12"),
            "last_official_os": life.get("last_official_os") or (max_os if max_os != "Verificar com fabricante" else (os_ver_str or "Android 12")),
            "support_status": life.get("support_status", "🔴 Descontinuado no Android 12"),
            "google_oem_notes": life.get("google_oem_notes", "Fabricante e Google não fornecem atualizações para Android 13 ou superior."),
            "user_action_possible": False,
            "recommendation": "Impossível o usuário atualizar o celular. A Prodemge deve otimizar o código, reduzir consumo de RAM e garantir compatibilidade no APK."
        }
        
    return {
        "is_stuck": False,
        "badge_text": None,
        "badge_subtext": None,
        "badge_color": None,
        "reason": "Dispositivo com suporte ou atualizável para Android 13+.",
        "max_os": max_os,
        "last_official_os": life.get("last_official_os") or max_os,
        "support_status": life.get("support_status", "Ativo"),
        "user_action_possible": True,
        "recommendation": life.get("dev_recommendation", "")
    }

