from datetime import datetime, timedelta
from passlib.context import CryptContext

from database import SessionLocal
from models import Usuario, Solicitacao, HistoricoStatus

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def gerar_hash_senha(senha: str) -> str:
    return pwd_context.hash(senha)


def run_seed() -> None:
    """Popula o banco PostgreSQL com 1 Analista, 2 Solicitantes e 10 solicitações fictícias."""
    db = SessionLocal()

    try:
        if db.query(Usuario).first():
            print("Banco de dados já possui registros. Seed ignorado.")
            return

        senha_padrao = gerar_hash_senha("123456")

        analista = Usuario(
            nome="Maria Oliveira",
            email="analista@empresa.com",
            senha_hash=senha_padrao,
            perfil="ANALISTA",
        )
        solicitante_1 = Usuario(
            nome="João Silva",
            email="joao@empresa.com",
            senha_hash=senha_padrao,
            perfil="SOLICITANTE",
        )
        solicitante_2 = Usuario(
            nome="Ana Costa",
            email="ana@empresa.com",
            senha_hash=senha_padrao,
            perfil="SOLICITANTE",
        )

        db.add_all([analista, solicitante_1, solicitante_2])
        db.flush()

        agora = datetime.now()

        dados_solicitacoes = [
            {
                "usuario_id": solicitante_1.id,
                "titulo": "Acesso ao sistema ERP corporativo",
                "descricao": "Solicito liberação de acesso ao módulo de compras no ERP para acompanhamento de pedidos do setor.",
                "categoria": "TI",
                "prioridade": "Alta",
                "status": "Em análise",
                "criada_em": agora - timedelta(days=9, hours=3),
            },
            {
                "usuario_id": solicitante_1.id,
                "titulo": "Reembolso de despesas de viagem técnica",
                "descricao": "Envio comprovantes referentes ao deslocamento e hospedagem na visita técnica à filial.",
                "categoria": "Financeiro",
                "prioridade": "Média",
                "status": "Concluída",
                "criada_em": agora - timedelta(days=8, hours=5),
            },
            {
                "usuario_id": solicitante_1.id,
                "titulo": "Troca de teclado com defeito na estação 14",
                "descricao": "Algumas teclas pararam de funcionar após atualização do posto de trabalho.",
                "categoria": "TI",
                "prioridade": "Baixa",
                "status": "Aberta",
                "criada_em": agora - timedelta(days=7, hours=2),
            },
            {
                "usuario_id": solicitante_1.id,
                "titulo": "Atualização de dados cadastrais e vale-transporte",
                "descricao": "Solicito alteração de endereço residencial e revisão da linha de transporte utilizada.",
                "categoria": "RH",
                "prioridade": "Baixa",
                "status": "Concluída",
                "criada_em": agora - timedelta(days=6, hours=1),
            },
            {
                "usuario_id": solicitante_1.id,
                "titulo": "Manutenção preventiva em coletor de dados do estoque",
                "descricao": "O leitor óptico do coletor 03 apresenta lentidão na leitura de código de barras.",
                "categoria": "Operações",
                "prioridade": "Alta",
                "status": "Aberta",
                "criada_em": agora - timedelta(days=4, hours=4),
            },
            {
                "usuario_id": solicitante_2.id,
                "titulo": "Configuração de VPN para trabalho remoto",
                "descricao": "Preciso do certificado de acesso VPN configurado no notebook corporativo.",
                "categoria": "TI",
                "prioridade": "Alta",
                "status": "Concluída",
                "criada_em": agora - timedelta(days=5, hours=6),
            },
            {
                "usuario_id": solicitante_2.id,
                "titulo": "Emissão de segunda via de nota fiscal de serviço",
                "descricao": "Cliente solicitou reenvio da nota fiscal referente à fatura do mês anterior.",
                "categoria": "Financeiro",
                "prioridade": "Média",
                "status": "Em análise",
                "criada_em": agora - timedelta(days=3, hours=5),
            },
            {
                "usuario_id": solicitante_2.id,
                "titulo": "Inclusão de dependente no plano de saúde",
                "descricao": "Solicito inclusão de dependente conforme documentação comprobatória.",
                "categoria": "RH",
                "prioridade": "Média",
                "status": "Aberta",
                "criada_em": agora - timedelta(days=2, hours=7),
            },
            {
                "usuario_id": solicitante_2.id,
                "titulo": "Requisição de EPIs para equipe de campo",
                "descricao": "Necessário envio de 5 kits de proteção individual para a equipe operacional.",
                "categoria": "Operações",
                "prioridade": "Alta",
                "status": "Em análise",
                "criada_em": agora - timedelta(days=1, hours=8),
            },
            {
                "usuario_id": solicitante_2.id,
                "titulo": "Aprovação de orçamento de fornecedor logístico",
                "descricao": "Encaminho cotação atualizada de frete para validação do centro de custo.",
                "categoria": "Financeiro",
                "prioridade": "Baixa",
                "status": "Concluída",
                "criada_em": agora - timedelta(hours=12),
            },
        ]

        for item in dados_solicitacoes:
            solicitacao = Solicitacao(**item)
            db.add(solicitacao)
            db.flush()

            if solicitacao.status in ("Em análise", "Concluída"):
                hist_analise = HistoricoStatus(
                    solicitacao_id=solicitacao.id,
                    usuario_id=analista.id,
                    status_anterior="Aberta",
                    novo_status="Em análise",
                    data=solicitacao.criada_em + timedelta(hours=2),
                )
                db.add(hist_analise)

            if solicitacao.status == "Concluída":
                hist_concluida = HistoricoStatus(
                    solicitacao_id=solicitacao.id,
                    usuario_id=analista.id,
                    status_anterior="Em análise",
                    novo_status="Concluída",
                    data=solicitacao.criada_em + timedelta(hours=6),
                )
                db.add(hist_concluida)

        db.commit()
        print("Seed concluído com sucesso! Usuários e 10 solicitações criados.")
    except Exception as exc:
        db.rollback()
        raise exc
    finally:
        db.close()


if __name__ == "__main__":
    run_seed()
