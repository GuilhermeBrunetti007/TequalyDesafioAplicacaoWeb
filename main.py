import csv
import io
import os
import shutil
import uuid
from datetime import datetime
from typing import Optional

from dotenv import load_dotenv
from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    RedirectResponse,
    StreamingResponse,
)
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from auth import (
    COOKIE_NAME,
    SESSION_MAX_AGE,
    criar_token_sessao,
    exigir_analista,
    obter_usuario_logado,
    obter_usuario_logado_opcional,
    verificar_acesso_solicitacao,
    verificar_senha,
)
from database import get_db
from models import (
    CATEGORIAS_VALIDAS,
    PRIORIDADES_VALIDAS,
    STATUS_VALIDOS,
    Anexo,
    HistoricoStatus,
    Solicitacao,
    Usuario,
)

load_dotenv()

app = FastAPI(
    title="Portal de Solicitações Internas",
    description="Aplicação monolítica em Python (FastAPI + SQLAlchemy + PostgreSQL + Jinja2) para gestão de demandas.",
    version="1.0.0",
)

UPLOAD_DIR = os.getenv("UPLOAD_DIR", os.path.join("storage", "uploads"))
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs("templates", exist_ok=True)

templates = Jinja2Templates(directory="templates")

STATUS_ALTERACAO_ANALISTA = ("Em análise", "Concluída")
EXTENSOES_PERMITIDAS = {".pdf", ".jpg", ".png"}
TIPOS_MIME_MAP = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".png": "image/png",
}
TAMANHO_MAXIMO_BYTES = 5 * 1024 * 1024  # 5 MB
TAMANHO_MAXIMO_TITULO = 200


def converter_periodo_datas(
    data_inicio: Optional[str] = None,
    data_fim: Optional[str] = None,
) -> tuple[Optional[datetime], Optional[datetime]]:
    """Converte strings de data (YYYY-MM-DD) com segurança e valida se o período é consistente."""
    dt_inicio = None
    dt_fim = None

    if data_inicio and data_inicio.strip():
        try:
            dt_inicio = datetime.strptime(data_inicio.strip(), "%Y-%m-%d")
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Formato de data inicial inválido. Utilize AAAA-MM-DD.",
            )

    if data_fim and data_fim.strip():
        try:
            dt_fim = datetime.strptime(data_fim.strip(), "%Y-%m-%d").replace(
                hour=23, minute=59, second=59
            )
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Formato de data final inválido. Utilize AAAA-MM-DD.",
            )

    if dt_inicio and dt_fim and dt_inicio > dt_fim:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A data inicial não pode ser maior que a data final.",
        )

    return dt_inicio, dt_fim


def aplicar_filtros_solicitacoes(
    query,
    usuario: Usuario,
    status_filtro: Optional[str] = None,
    data_inicio: Optional[str] = None,
    data_fim: Optional[str] = None,
):
    """Aplica restrição de perfil (Solicitante vs Analista) e filtros de status e período."""
    if usuario.perfil != "ANALISTA":
        query = query.filter(Solicitacao.usuario_id == usuario.id)

    if status_filtro and status_filtro in STATUS_VALIDOS:
        query = query.filter(Solicitacao.status == status_filtro)

    dt_inicio, dt_fim = converter_periodo_datas(data_inicio, data_fim)

    if dt_inicio:
        query = query.filter(Solicitacao.criada_em >= dt_inicio)

    if dt_fim:
        query = query.filter(Solicitacao.criada_em <= dt_fim)

    return query


def validar_e_salvar_anexo(arquivo: UploadFile) -> dict:
    """
    Valida extensão (.pdf, .jpg, .png), rejeita arquivos vazios (0 bytes) e verifica
    o tamanho máximo (5 MB) no backend, salvando o arquivo renomeado com UUID4 em storage/uploads/.
    """
    nome_original = os.path.basename((arquivo.filename or "").strip())
    _, extensao = os.path.splitext(nome_original.lower())

    if not nome_original or extensao not in EXTENSOES_PERMITIDAS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Formato de arquivo inválido. Apenas arquivos .pdf, .jpg e .png são permitidos.",
        )

    conteudo = arquivo.file.read()
    tamanho = len(conteudo)

    if tamanho == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O arquivo enviado está vazio (0 bytes). Selecione um arquivo válido.",
        )

    if tamanho > TAMANHO_MAXIMO_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O arquivo excede o tamanho máximo permitido de 5 MB.",
        )

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    nome_seguro = f"{uuid.uuid4().hex}{extensao}"
    caminho_seguro = os.path.join(UPLOAD_DIR, nome_seguro)

    arquivo.file.seek(0)
    with open(caminho_seguro, "wb") as f_out:
        shutil.copyfileobj(arquivo.file, f_out)

    return {
        "nome_original": nome_original,
        "tipo": TIPOS_MIME_MAP.get(extensao, "application/octet-stream"),
        "caminho_seguro": caminho_seguro,
        "tamanho": tamanho,
    }


@app.get("/", response_class=HTMLResponse)
def index(
    usuario: Optional[Usuario] = Depends(obter_usuario_logado_opcional),
):
    if not usuario:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/login", response_class=HTMLResponse)
def pagina_login(
    request: Request,
    usuario: Optional[Usuario] = Depends(obter_usuario_logado_opcional),
):
    if usuario:
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse(
        request,
        "login.html",
        {"erro": None},
    )


@app.post("/login", response_class=HTMLResponse)
def realizar_login(
    request: Request,
    email: str = Form(...),
    senha: str = Form(...),
    db: Session = Depends(get_db),
):
    usuario = (
        db.query(Usuario).filter(Usuario.email == email.strip().lower()).first()
    )
    if not usuario or not verificar_senha(senha, usuario.senha_hash):
        return templates.TemplateResponse(
            request,
            "login.html",
            {"erro": "E-mail ou senha inválidos. Verifique suas credenciais."},
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    token = criar_token_sessao(usuario.id, usuario.perfil)
    response = RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=SESSION_MAX_AGE,
    )
    return response


@app.get("/logout")
def realizar_logout():
    response = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(COOKIE_NAME)
    return response


@app.get("/dashboard", response_class=HTMLResponse)
def pagina_dashboard(
    request: Request,
    usuario: Optional[Usuario] = Depends(obter_usuario_logado_opcional),
    db: Session = Depends(get_db),
):
    if not usuario:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    query_base = aplicar_filtros_solicitacoes(db.query(Solicitacao), usuario)

    total = query_base.count()
    abertas = query_base.filter(Solicitacao.status == "Aberta").count()
    em_analise = query_base.filter(Solicitacao.status == "Em análise").count()
    concluidas = query_base.filter(Solicitacao.status == "Concluída").count()

    contagem_categorias_db = dict(
        query_base.with_entities(Solicitacao.categoria, func.count(Solicitacao.id))
        .group_by(Solicitacao.categoria)
        .all()
    )
    labels_categorias = list(CATEGORIAS_VALIDAS)
    valores_categorias = [
        contagem_categorias_db.get(cat, 0) for cat in labels_categorias
    ]

    ultimas_solicitacoes = (
        query_base.order_by(Solicitacao.criada_em.desc(), Solicitacao.id.desc())
        .limit(5)
        .all()
    )

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "usuario": usuario,
            "total": total,
            "abertas": abertas,
            "em_analise": em_analise,
            "concluidas": concluidas,
            "labels_status": ["Aberta", "Em análise", "Concluída"],
            "valores_status": [abertas, em_analise, concluidas],
            "labels_categorias": labels_categorias,
            "valores_categorias": valores_categorias,
            "ultimas_solicitacoes": ultimas_solicitacoes,
        },
    )


@app.get("/solicitacoes", response_class=HTMLResponse)
def listar_solicitacoes(
    request: Request,
    status_filtro: Optional[str] = None,
    status_param: Optional[str] = None,
    data_inicio: Optional[str] = None,
    data_fim: Optional[str] = None,
    sucesso: Optional[str] = None,
    erro: Optional[str] = None,
    usuario: Optional[Usuario] = Depends(obter_usuario_logado_opcional),
    db: Session = Depends(get_db),
):
    if not usuario:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    filtro_status_efetivo = (
        status_filtro
        or status_param
        or request.query_params.get("status")
        or ""
    )

    query = db.query(Solicitacao)
    try:
        query = aplicar_filtros_solicitacoes(
            query, usuario, filtro_status_efetivo, data_inicio, data_fim
        )
    except HTTPException as exc:
        erro = exc.detail
        query = aplicar_filtros_solicitacoes(
            db.query(Solicitacao), usuario, filtro_status_efetivo
        )

    solicitacoes = query.order_by(
        Solicitacao.criada_em.desc(), Solicitacao.id.desc()
    ).all()

    return templates.TemplateResponse(
        request,
        "solicitacoes.html",
        {
            "usuario": usuario,
            "solicitacoes": solicitacoes,
            "categorias": CATEGORIAS_VALIDAS,
            "prioridades": PRIORIDADES_VALIDAS,
            "status_validos": STATUS_VALIDOS,
            "status_filtro": filtro_status_efetivo,
            "data_inicio": data_inicio or "",
            "data_fim": data_fim or "",
            "sucesso": sucesso,
            "erro": erro,
        },
    )


@app.post("/solicitacoes")
def criar_solicitacao(
    titulo: str = Form(...),
    descricao: str = Form(...),
    categoria: str = Form(...),
    prioridade: str = Form(...),
    arquivo: Optional[UploadFile] = File(default=None),
    usuario: Usuario = Depends(obter_usuario_logado),
    db: Session = Depends(get_db),
):
    titulo_limpo = titulo.strip()
    descricao_limpa = descricao.strip()

    if not titulo_limpo or not descricao_limpa:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Título e descrição são obrigatórios e não podem conter apenas espaços em branco.",
        )

    if len(titulo_limpo) > TAMANHO_MAXIMO_TITULO:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"O título deve ter no máximo {TAMANHO_MAXIMO_TITULO} caracteres.",
        )

    if categoria not in CATEGORIAS_VALIDAS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Categoria inválida. Opções permitidas: {', '.join(CATEGORIAS_VALIDAS)}.",
        )

    if prioridade not in PRIORIDADES_VALIDAS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Prioridade inválida. Opções permitidas: {', '.join(PRIORIDADES_VALIDAS)}.",
        )

    metadados_anexo = None
    if arquivo and arquivo.filename and arquivo.filename.strip():
        metadados_anexo = validar_e_salvar_anexo(arquivo)

    nova_solicitacao = Solicitacao(
        usuario_id=usuario.id,
        titulo=titulo_limpo,
        descricao=descricao_limpa,
        categoria=categoria,
        prioridade=prioridade,
        status="Aberta",
    )
    db.add(nova_solicitacao)
    db.flush()

    if metadados_anexo:
        novo_anexo = Anexo(
            solicitacao_id=nova_solicitacao.id,
            **metadados_anexo,
        )
        db.add(novo_anexo)

    db.commit()
    db.refresh(nova_solicitacao)

    return RedirectResponse(
        url=f"/solicitacoes/{nova_solicitacao.id}?sucesso=Solicita%C3%A7%C3%A3o+cadastrada+com+sucesso",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@app.get("/solicitacoes/exportar-csv")
@app.get("/relatorios/csv")
def exportar_relatorio_csv(
    request: Request,
    status_filtro: Optional[str] = None,
    data_inicio: Optional[str] = None,
    data_fim: Optional[str] = None,
    usuario: Usuario = Depends(obter_usuario_logado),
    db: Session = Depends(get_db),
):
    filtro_status_efetivo = (
        status_filtro or request.query_params.get("status") or ""
    )

    query = db.query(Solicitacao)
    query = aplicar_filtros_solicitacoes(
        query, usuario, filtro_status_efetivo, data_inicio, data_fim
    )
    solicitacoes = query.order_by(
        Solicitacao.criada_em.desc(), Solicitacao.id.desc()
    ).all()

    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";")

    writer.writerow(
        [
            "ID",
            "Titulo",
            "Categoria",
            "Prioridade",
            "Status",
            "Solicitante",
            "Email Solicitante",
            "Data de Criacao",
        ]
    )

    for sol in solicitacoes:
        writer.writerow(
            [
                sol.id,
                sol.titulo,
                sol.categoria,
                sol.prioridade,
                sol.status,
                sol.usuario.nome if sol.usuario else "",
                sol.usuario.email if sol.usuario else "",
                sol.criada_em.strftime("%Y-%m-%d %H:%M:%S") if sol.criada_em else "",
            ]
        )

    conteudo_csv = "\ufeff" + buffer.getvalue()
    buffer.close()

    return StreamingResponse(
        iter([conteudo_csv]),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="relatorio_solicitacoes.csv"'
        },
    )


@app.get("/solicitacoes/{solicitacao_id}", response_class=HTMLResponse)
def detalhar_solicitacao(
    solicitacao_id: int,
    request: Request,
    sucesso: Optional[str] = None,
    erro: Optional[str] = None,
    usuario: Optional[Usuario] = Depends(obter_usuario_logado_opcional),
    db: Session = Depends(get_db),
):
    if not usuario:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    solicitacao = (
        db.query(Solicitacao).filter(Solicitacao.id == solicitacao_id).first()
    )
    if not solicitacao:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Solicitação não encontrada.",
        )

    verificar_acesso_solicitacao(solicitacao, usuario)

    return templates.TemplateResponse(
        request,
        "detalhe_solicitacao.html",
        {
            "usuario": usuario,
            "solicitacao": solicitacao,
            "status_opcoes_analista": STATUS_ALTERACAO_ANALISTA,
            "sucesso": sucesso,
            "erro": erro,
        },
    )


@app.post("/solicitacoes/{solicitacao_id}/status")
def atualizar_status_solicitacao(
    solicitacao_id: int,
    novo_status: str = Form(...),
    analista: Usuario = Depends(exigir_analista),
    db: Session = Depends(get_db),
):
    novo_status_limpo = novo_status.strip()
    if novo_status_limpo not in STATUS_ALTERACAO_ANALISTA:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Status inválido. O Analista pode alterar apenas para: {', '.join(STATUS_ALTERACAO_ANALISTA)}.",
        )

    solicitacao = (
        db.query(Solicitacao).filter(Solicitacao.id == solicitacao_id).first()
    )
    if not solicitacao:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Solicitação não encontrada.",
        )

    status_anterior = solicitacao.status
    if status_anterior == novo_status_limpo:
        return RedirectResponse(
            url=f"/solicitacoes/{solicitacao.id}?sucesso=A+solicita%C3%A7%C3%A3o+j%C3%A1+se+encontra+com+este+status",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    solicitacao.status = novo_status_limpo
    registro_historico = HistoricoStatus(
        solicitacao_id=solicitacao.id,
        usuario_id=analista.id,
        status_anterior=status_anterior,
        novo_status=novo_status_limpo,
        data=datetime.now(),
    )
    db.add(registro_historico)
    db.commit()

    return RedirectResponse(
        url=f"/solicitacoes/{solicitacao.id}?sucesso=Status+atualizado+com+sucesso",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@app.get("/anexos/{anexo_id}/download")
def baixar_anexo(
    anexo_id: int,
    usuario: Usuario = Depends(obter_usuario_logado),
    db: Session = Depends(get_db),
):
    anexo = db.query(Anexo).filter(Anexo.id == anexo_id).first()
    if not anexo or not anexo.solicitacao:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Anexo não encontrado.",
        )

    verificar_acesso_solicitacao(anexo.solicitacao, usuario)

    if not os.path.isfile(anexo.caminho_seguro):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Arquivo físico não encontrado no servidor.",
        )

    return FileResponse(
        path=anexo.caminho_seguro,
        filename=anexo.nome_original,
        media_type=anexo.tipo,
    )
