import io
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from fastapi.testclient import TestClient

import main
from auth import gerar_hash_senha
from database import Base, SessionLocal, engine
from models import Anexo, HistoricoStatus, Solicitacao, Usuario
from seed import run_seed


def limpar_tabelas(db) -> None:
    """Remove os registros das tabelas no PostgreSQL respeitando a ordem das chaves estrangeiras."""
    db.query(HistoricoStatus).delete()
    db.query(Anexo).delete()
    db.query(Solicitacao).delete()
    db.query(Usuario).delete()
    db.commit()


@pytest.fixture(scope="session", autouse=True)
def restaurar_seed_ao_final():
    """Garante que o banco PostgreSQL termine a suíte de testes populado com os dados do seed."""
    Base.metadata.create_all(bind=engine)
    yield
    db = SessionLocal()
    try:
        limpar_tabelas(db)
    finally:
        db.close()
    run_seed()


@pytest.fixture()
def ambiente_teste():
    """Configura sessão no PostgreSQL, usuários de teste e diretório temporário de uploads."""
    Base.metadata.create_all(bind=engine)
    pasta_temp = tempfile.mkdtemp(prefix="portal_uploads_test_")
    pasta_original = main.UPLOAD_DIR
    main.UPLOAD_DIR = pasta_temp

    db = SessionLocal()
    limpar_tabelas(db)

    senha_hash = gerar_hash_senha("123456")

    analista = Usuario(
        nome="Maria Oliveira",
        email="analista@empresa.com",
        senha_hash=senha_hash,
        perfil="ANALISTA",
    )
    solicitante_1 = Usuario(
        nome="João Silva",
        email="joao@empresa.com",
        senha_hash=senha_hash,
        perfil="SOLICITANTE",
    )
    solicitante_2 = Usuario(
        nome="Ana Costa",
        email="ana@empresa.com",
        senha_hash=senha_hash,
        perfil="SOLICITANTE",
    )
    db.add_all([analista, solicitante_1, solicitante_2])
    db.commit()

    yield db

    limpar_tabelas(db)
    db.close()
    main.UPLOAD_DIR = pasta_original
    shutil.rmtree(pasta_temp, ignore_errors=True)


def autenticar_cliente(email: str, senha: str = "123456") -> TestClient:
    """Realiza login e retorna um TestClient autenticado."""
    client = TestClient(main.app)
    resp = client.post(
        "/login",
        data={"email": email, "senha": senha},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    return client


def test_login_credenciais_validas_e_invalidas(ambiente_teste):
    client = TestClient(main.app)

    resp_erro = client.post(
        "/login",
        data={"email": "joao@empresa.com", "senha": "senha-errada"},
        follow_redirects=False,
    )
    assert resp_erro.status_code == 401
    assert "inválidos" in resp_erro.text

    resp_ok = client.post(
        "/login",
        data={"email": "joao@empresa.com", "senha": "123456"},
        follow_redirects=False,
    )
    assert resp_ok.status_code == 303
    assert resp_ok.headers["location"] == "/dashboard"
    assert main.COOKIE_NAME in resp_ok.cookies


def test_permissao_isolamento_entre_solicitantes_e_acesso_analista(ambiente_teste):
    db = ambiente_teste

    client_joao = autenticar_cliente("joao@empresa.com")
    conteudo_pdf = b"%PDF-1.4 Conteudo de teste do comprovante"
    resp_criacao = client_joao.post(
        "/solicitacoes",
        data={
            "titulo": "Acesso ao módulo financeiro",
            "descricao": "Preciso consultar notas fiscais do trimestre.",
            "categoria": "Financeiro",
            "prioridade": "Alta",
        },
        files={"arquivo": ("comprovante.pdf", io.BytesIO(conteudo_pdf), "application/pdf")},
        follow_redirects=False,
    )
    assert resp_criacao.status_code == 303

    solicitacao_joao = db.query(Solicitacao).first()
    anexo_joao = db.query(Anexo).first()
    assert solicitacao_joao is not None
    assert anexo_joao is not None

    # Solicitante 2 (Ana) tenta acessar solicitação e anexo de João -> 403 Forbidden
    client_ana = autenticar_cliente("ana@empresa.com")
    resp_detalhe_ana = client_ana.get(f"/solicitacoes/{solicitacao_joao.id}")
    assert resp_detalhe_ana.status_code == 403

    resp_download_ana = client_ana.get(f"/anexos/{anexo_joao.id}/download")
    assert resp_download_ana.status_code == 403

    # Analista acessa solicitação e baixa anexo normalmente -> 200 OK
    client_analista = autenticar_cliente("analista@empresa.com")
    resp_detalhe_analista = client_analista.get(f"/solicitacoes/{solicitacao_joao.id}")
    assert resp_detalhe_analista.status_code == 200

    resp_download_analista = client_analista.get(f"/anexos/{anexo_joao.id}/download")
    assert resp_download_analista.status_code == 200
    assert resp_download_analista.content == conteudo_pdf


def test_mudanca_de_status_e_registro_de_historico(ambiente_teste):
    db = ambiente_teste

    client_joao = autenticar_cliente("joao@empresa.com")
    client_joao.post(
        "/solicitacoes",
        data={
            "titulo": "Instalação de pacote de dados",
            "descricao": "Solicito instalação na máquina de desenvolvimento.",
            "categoria": "TI",
            "prioridade": "Média",
        },
        follow_redirects=False,
    )
    solicitacao = db.query(Solicitacao).first()
    assert solicitacao.status == "Aberta"

    # Solicitante não pode alterar status -> 403 Forbidden
    resp_proibido = client_joao.post(
        f"/solicitacoes/{solicitacao.id}/status",
        data={"novo_status": "Em análise"},
        follow_redirects=False,
    )
    assert resp_proibido.status_code == 403

    # Analista altera para 'Em análise' e depois para 'Concluída'
    client_analista = autenticar_cliente("analista@empresa.com")
    resp_analise = client_analista.post(
        f"/solicitacoes/{solicitacao.id}/status",
        data={"novo_status": "Em análise"},
        follow_redirects=False,
    )
    assert resp_analise.status_code == 303

    resp_concluida = client_analista.post(
        f"/solicitacoes/{solicitacao.id}/status",
        data={"novo_status": "Concluída"},
        follow_redirects=False,
    )
    assert resp_concluida.status_code == 303

    db.expire_all()
    solicitacao_atualizada = (
        db.query(Solicitacao).filter(Solicitacao.id == solicitacao.id).first()
    )
    assert solicitacao_atualizada.status == "Concluída"

    historicos = (
        db.query(HistoricoStatus)
        .filter(HistoricoStatus.solicitacao_id == solicitacao.id)
        .order_by(HistoricoStatus.id.asc())
        .all()
    )
    assert len(historicos) == 2
    assert historicos[0].status_anterior == "Aberta"
    assert historicos[0].novo_status == "Em análise"
    assert historicos[1].status_anterior == "Em análise"
    assert historicos[1].novo_status == "Concluída"


def test_bloqueio_de_arquivo_invalido_extensao_e_tamanho(ambiente_teste):
    client_joao = autenticar_cliente("joao@empresa.com")

    resp_extensao = client_joao.post(
        "/solicitacoes",
        data={
            "titulo": "Teste de upload inválido",
            "descricao": "Tentando enviar arquivo executável.",
            "categoria": "TI",
            "prioridade": "Baixa",
        },
        files={"arquivo": ("script.exe", io.BytesIO(b"MZ-fake-binary"), "application/octet-stream")},
        follow_redirects=False,
    )
    assert resp_extensao.status_code == 400
    assert "Formato de arquivo inválido" in resp_extensao.json()["detail"]

    conteudo_acima_5mb = b"A" * (5 * 1024 * 1024 + 100)
    resp_tamanho = client_joao.post(
        "/solicitacoes",
        data={
            "titulo": "Teste de arquivo gigante",
            "descricao": "Tentando enviar PDF maior que 5 MB.",
            "categoria": "Operações",
            "prioridade": "Média",
        },
        files={"arquivo": ("grande.pdf", io.BytesIO(conteudo_acima_5mb), "application/pdf")},
        follow_redirects=False,
    )
    assert resp_tamanho.status_code == 400
    assert "5 MB" in resp_tamanho.json()["detail"]


def test_dashboard_e_exportacao_csv_respeitando_perfil(ambiente_teste):
    client_joao = autenticar_cliente("joao@empresa.com")
    client_ana = autenticar_cliente("ana@empresa.com")
    client_analista = autenticar_cliente("analista@empresa.com")

    client_joao.post(
        "/solicitacoes",
        data={
            "titulo": "Chamado do João",
            "descricao": "Demanda aberta por João.",
            "categoria": "RH",
            "prioridade": "Baixa",
        },
        follow_redirects=False,
    )
    client_ana.post(
        "/solicitacoes",
        data={
            "titulo": "Chamado da Ana",
            "descricao": "Demanda aberta por Ana.",
            "categoria": "TI",
            "prioridade": "Alta",
        },
        follow_redirects=False,
    )

    csv_joao = client_joao.get("/relatorios/csv").text
    assert "Chamado do João" in csv_joao
    assert "Chamado da Ana" not in csv_joao

    csv_analista = client_analista.get("/relatorios/csv").text
    assert "Chamado do João" in csv_analista
    assert "Chamado da Ana" in csv_analista

    resp_dash = client_analista.get("/dashboard")
    assert resp_dash.status_code == 200
    assert "Painel de Indicadores" in resp_dash.text
