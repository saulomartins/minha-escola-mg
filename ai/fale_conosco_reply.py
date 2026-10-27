"""
Módulo de Geração de Respostas Inteligentes para Chamados do Fale Conosco
Minha Escola MG (Secretaria de Estado de Educação de Minas Gerais - SEE/MG & PRODEMGE)

Gera orientações oficiais, empáticas, didáticas e contextualizadas para os estudantes
e responsáveis com base nas 12 Causas-Raiz Técnicas identificadas e telemetria Prodemge.
Suporta geração via Gemini 2.5 Flash (quando API Key disponível) com fallback determinístico completo.
"""

import os
import re
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

def generate_fale_conosco_reply(ticket: Dict[str, Any], api_key: Optional[str] = None) -> str:
    """
    Gera a resposta sugerida de suporte para um chamado do Fale Conosco.
    Tenta utilizar a API do Google Gemini se a chave estiver configurada;
    caso contrário, utiliza o motor contextual baseado nas 12 Causas-Raiz e nos dados do cidadão.
    """
    student_name = (ticket.get('student_name') or 'Estudante').strip()
    user_type = ticket.get('user_type') or 'Aluno'
    school = (ticket.get('school_name') or '').strip()
    city = (ticket.get('city') or '').strip()
    desc = (ticket.get('description') or '').strip()
    rc_id = ticket.get('root_cause_id') or 'outros_suporte'
    cat = ticket.get('category') or 'Suporte Geral'
    internal = ticket.get('internal_analysis') or ''

    # Tenta usar Gemini se houver chave configurada
    effective_api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
    if not effective_api_key:
        try:
            from database.db import get_setting
            effective_api_key = get_setting("gemini_api_key", "")
        except Exception:
            effective_api_key = ""

    if effective_api_key:
        try:
            from google import genai
            client = genai.Client(api_key=effective_api_key)
            prompt = f"""Você é o atendente técnico oficial de suporte do aplicativo móvel 'Minha Escola MG' (Secretaria de Estado de Educação de Minas Gerais - SEE/MG e PRODEMGE).
Sua missão é responder ao chamado de suporte aberto pelo cidadão no canal 'Fale Conosco'.

Dados do Chamado:
- Nome do Usuário: {student_name}
- Perfil: {user_type} (Aluno ou Responsável)
- Escola Estadual: {school if school else 'Rede Estadual de MG'}
- Município: {city if city else 'Minas Gerais'}
- Causa-Raiz Classificada: {rc_id} ({cat})
- Análise Interna / Correlação: {internal if internal else 'Suporte Geral'}
- Mensagem enviada pelo cidadão: "{desc}"

Diretrizes Obrigatórias:
1. Responda em Português do Brasil com tom cordial, acolhedor, profissional e resolutivo.
2. Cumprimente pelo nome (ex: "Olá, {student_name}!" ou se for responsável "Olá, responsável por {student_name}!").
3. Forneça instruções passo a passo claras (limpeza de cache do app, validação de CPF no SIMADE/escola, portal idaluno.educacao.mg.gov.br, ou fechamento do bimestre no DED conforme aplicável).
4. Assinatura formal obrigatória ao final:
Atenciosamente,
Equipe de Atendimento e Suporte Minha Escola MG
Secretaria de Estado de Educação de Minas Gerais (SEE/MG) & Prodemge

Gere apenas o texto da mensagem final que será enviada por e-mail, sem formatações Markdown excessivas nem introduções artificiais."""

            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt
            )
            if response and response.text and len(response.text.strip()) > 50:
                return response.text.strip()
        except Exception as e:
            logger.warning(f"Chamada ao Gemini falhou ou API indisponível, usando motor de templates: {e}")

    # Fallback contextual de alta fidelidade baseado nas 12 Causas-Raiz
    return generate_deterministic_reply(student_name, user_type, school, city, desc, rc_id, cat, internal)


def generate_deterministic_reply(
    student_name: str,
    user_type: str,
    school: str,
    city: str,
    desc: str,
    rc_id: str,
    cat: str,
    internal: str
) -> str:
    """Gera resposta contextual oficial com base na matriz de Causas-Raiz e telemetria Prodemge."""
    is_resp = any(k in user_type.lower() for k in ['responsavel', 'responsável', 'mãe', 'mae', 'pai'])
    if is_resp:
        greeting = f"Olá, responsável por {student_name}!"
    else:
        greeting = f"Olá, {student_name}!"

    school_mention = f" da escola {school}" if school and school.lower() not in ['não informada', 'nao informada', 'none', ''] else ""

    # Instrução técnica detalhada por Causa-Raiz
    if rc_id == "oauth_gov_br":
        body = (
            f"Recebemos sua solicitação referente à dificuldade de acesso via Conta Gov.br / SEG.ID no aplicativo Minha Escola MG{school_mention}.\n\n"
            f"Para regularizar o seu acesso, recomendamos as seguintes etapas:\n"
            f"1. Verifique se o CPF utilizado no Gov.br é exatamente o mesmo informado na matrícula escolar junto à Secretaria da Educação (SEE/MG).\n"
            f"2. Caso o aplicativo entre em loop no navegador ou apresente tela em branco, acesse no seu celular: Configurações > Aplicativos > Navegador padrão (Google Chrome) > Armazenamento > 'Limpar Cache'.\n"
            f"3. Como alternativa oficial, acesse pelo navegador o portal idaluno.educacao.mg.gov.br para consultar seu e-mail institucional educacional e gerar nova senha temporária.\n"
            f"4. Se o seu CPF ainda não consta na sua ficha de matrícula, solicite à secretaria da sua escola a inclusão e validação cadastral no sistema SIMADE."
        )
    elif rc_id == "token_jwt_sessao":
        body = (
            f"Identificamos o seu relato sobre erro de autenticação / sessão expirada ('Token inválido' - Mantis 0198268) no aplicativo Minha Escola MG{school_mention}.\n\n"
            f"Nossa equipe técnica da Prodemge realizou melhorias na infraestrutura de autenticação. Para que seu aplicativo reconheça a nova sessão, siga o procedimento abaixo:\n"
            f"1. Feche totalmente o aplicativo Minha Escola MG na lista de aplicativos recentes.\n"
            f"2. No seu aparelho, vá em: Configurações > Aplicativos > Minha Escola MG > Armazenamento > toque em 'Limpar Cache' (e em seguida 'Limpar Dados').\n"
            f"3. Abra novamente o aplicativo e faça um novo login via Conta Gov.br ou e-mail institucional.\n"
            f"4. Mantenha o aplicativo sempre atualizado na versão mais recente disponível na Google Play Store ou Apple App Store."
        )
    elif rc_id == "ded_notas_boletim":
        body = (
            f"Recebemos seu chamado referente à visualização de notas, faltas e boletim escolar no aplicativo Minha Escola MG{school_mention}.\n\n"
            f"Gostaríamos de esclarecer que o aplicativo reflete diretamente os lançamentos pedagógicos efetuados pelos professores no sistema Diário Escolar Digital (DED).\n\n"
            f"Orientações importantes:\n"
            f"1. Se as notas ou frequência de determinado bimestre ou disciplina não aparecem, confirme com os professores ou com a secretaria da sua escola se o fechamento do período letivo já foi homologado no sistema.\n"
            f"2. No aplicativo, na aba de notas, arraste a tela de cima para baixo para forçar a atualização imediata dos dados em cache.\n"
            f"3. Caso o boletim físico da escola já tenha sido entregue com as notas lançadas, mas o aplicativo continue desatualizado, a direção da escola poderá solicitar o reprocessamento da sincronização da turma junto ao suporte do DED."
        )
    elif rc_id == "crash_loop_inicial":
        body = (
            f"Recebemos sua mensagem relatando que o aplicativo Minha Escola MG não está abrindo ou fecha sozinho no seu aparelho{school_mention}.\n\n"
            f"Para restabelecer o funcionamento correto do aplicativo no seu dispositivo, realize as ações abaixo:\n"
            f"1. Atualize o componente 'Android System WebView' e o aplicativo 'Google Chrome' pela Google Play Store (esses módulos do sistema são essenciais para renderizar as telas do app).\n"
            f"2. Limpe os arquivos temporários: Configurações do Celular > Aplicativos > Minha Escola MG > Armazenamento > 'Limpar Cache'.\n"
            f"3. Verifique se o seu dispositivo possui espaço livre na memória interna e uma conexão estável de internet.\n"
            f"4. Se a falha persistir, desinstale o aplicativo, reinicie o celular e reinstale a versão mais recente da loja oficial."
        )
    elif rc_id == "inconsistencia_cpf_ded":
        body = (
            f"Com relação ao aviso de 'CPF não encontrado' ou dados divergentes no aplicativo Minha Escola MG{school_mention}:\n\n"
            f"Essa situação ocorre quando o CPF do estudante ou do responsável ainda não foi cadastrado ou vinculado à ficha de matrícula no sistema SIMADE da Secretaria da Educação.\n\n"
            f"Como regularizar:\n"
            f"1. O estudante ou seu responsável legal deve entrar em contato com a Secretaria da Escola estadual onde estuda.\n"
            f"2. Solicite à secretaria escolar a conferência e inclusão do número do seu CPF e da data de nascimento exata na sua ficha cadastral no sistema SIMADE.\n"
            f"3. Após a confirmação da escola de que os dados foram salvos no sistema, o acesso pelo aplicativo é liberado no próximo ciclo de sincronização (em até 24h úteis)."
        )
    elif rc_id == "recuperacao_senha_idaluno":
        body = (
            f"Recebemos sua solicitação de recuperação de senha ou consulta do ID do Aluno para o aplicativo Minha Escola MG{school_mention}.\n\n"
            f"Você pode consultar seu número de ID e redefinir sua senha de acesso de forma autônoma e imediata:\n"
            f"1. Acesse pelo navegador de internet o portal oficial: idaluno.educacao.mg.gov.br\n"
            f"2. Preencha seu nome completo, data de nascimento e o nome da mãe exatamente como constam na certidão de nascimento ou no registro escolar.\n"
            f"3. O portal exibirá seu e-mail institucional educacional (ex: nome.sobrenome@aluno.mg.gov.br) e o botão para gerar uma nova senha de acesso.\n"
            f"4. Se houver divergência de grafia no nome, solicite à secretaria da sua escola a conferência dos seus dados cadastrais."
        )
    elif rc_id == "troca_escola_matricula":
        body = (
            f"Sobre o seu relato de transferência ou vinculação a uma nova escola estadual (Mantis 0198728){school_mention}:\n\n"
            f"A atualização da turma e da unidade escolar no aplicativo depende da conclusão e homologação da matrícula pela nova escola no sistema DED/SIMADE.\n\n"
            f"Orientações:\n"
            f"1. Confirme na secretaria da sua nova escola se a sua enturmação e matrícula já foram finalizadas no sistema da rede estadual.\n"
            f"2. Assim que a escola confirmar a conclusão, abra o aplicativo Minha Escola MG, acesse seu perfil, toque na opção 'Sair da Conta' e faça um novo login para que as turmas e matérias da nova escola sejam carregadas."
        )
    elif rc_id == "pe_de_meia_mec":
        body = (
            f"Recebemos sua dúvida referente ao programa Pé-de-Meia ou ao aplicativo Jornada do Estudante{school_mention}.\n\n"
            f"Gostaríamos de esclarecer que o programa Pé-de-Meia é uma iniciativa federal gerida pelo Ministério da Educação (MEC) e pela Caixa Econômica Federal.\n\n"
            f"Informações importantes:\n"
            f"1. A Secretaria de Estado de Educação de Minas Gerais (SEE/MG) envia periodicamente os dados de frequência e matrícula dos alunos elegíveis diretamente ao sistema central do MEC.\n"
            f"2. Para consultar a aprovação do benefício, valores e calendário de pagamento, consulte os canais oficiais do Governo Federal: o aplicativo 'Jornada do Estudante' (MEC) ou o aplicativo 'Caixa Tem'.\n"
            f"3. Caso haja alguma divergência de frequência escolar informada, procure a secretaria da sua escola para confirmar se seus lançamentos bimestrais estão atualizados no SIMADE."
        )
    elif rc_id == "demandas_secretaria_n1":
        body = (
            f"Recebemos sua solicitação enviada pelo canal de suporte do aplicativo Minha Escola MG{school_mention}.\n\n"
            f"Gostaríamos de informar que a emissão de documentos escolares oficiais (como histórico escolar, declaração de matrícula, transferência ou justificativa presencial de faltas) compete exclusivamente à Secretaria da Unidade Escolar onde o estudante estuda ou concluiu os estudos.\n\n"
            f"Recomendamos que você entre em contato diretamente com a secretaria da sua escola (presencialmente ou pelos canais de atendimento telefônico/e-mail da unidade escolar) para requerer o documento solicitado."
        )
    elif rc_id == "compatibilidade_dispositivo":
        body = (
            f"Recebemos seu relato referente à compatibilidade do aplicativo Minha Escola MG com o seu aparelho{school_mention}.\n\n"
            f"Requisitos técnicos e alternativas:\n"
            f"1. O aplicativo Minha Escola MG requer sistemas Android na versão 8.0 ou superior, ou iOS na versão 14.0 ou superior.\n"
            f"2. Verifique nas configurações do seu celular se existem atualizações de sistema operacional pendentes de instalação.\n"
            f"3. Caso o seu aparelho não suporte a instalação pela loja oficial, você e seus responsáveis podem acompanhar notas, frequência e boletim diretamente pelo navegador web no portal oficial: idaluno.educacao.mg.gov.br"
        )
    else:
        # outros_suporte / login_generico_bloqueio
        resumo_relato = f'"{desc[:120]}..."' if len(desc) > 10 else "seu relato de atendimento"
        body = (
            f"Recebemos sua solicitação enviada pelo canal oficial de suporte do aplicativo Minha Escola MG{school_mention}.\n\n"
            f"Em atenção ao {resumo_relato}, recomendamos certificar-se de que o aplicativo esteja atualizado na versão mais recente disponível na sua loja de aplicativos.\n\n"
            f"Para questões relacionadas a notas, faltas e dados de cadastro, lembre-se de que os lançamentos dependem do registro no Diário Escolar Digital pelos professores e secretaria da sua escola.\n"
            f"Caso precise consultar seu número de matrícula ou redefinir sua senha, acesse o portal idaluno.educacao.mg.gov.br ou entre em contato com a secretaria da sua instituição de ensino."
        )

    sign_off = (
        "Permanecemos à disposição para auxiliá-lo(a).\n\n"
        "Atenciosamente,\n"
        "Equipe de Atendimento e Suporte Minha Escola MG\n"
        "Secretaria de Estado de Educação de Minas Gerais (SEE/MG) & Prodemge"
    )

    return f"{greeting}\n\n{body}\n\n{sign_off}"
