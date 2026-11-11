import os
from typing import Optional

from dotenv import load_dotenv
from fastapi import Depends, HTTPException, Request, status
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from database import get_db
from models import Solicitacao, Usuario

load_dotenv()

SECRET_KEY = os.getenv(
    "SECRET_KEY", "chave_secreta_portal_solicitacoes_2026"
)
COOKIE_NAME = "portal_session"
SESSION_MAX_AGE = 60 * 60 * 8  # 8 horas

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
serializer = URLSafeTimedSerializer(SECRET_KEY, salt="portal-solicitacoes-sessao")


def gerar_hash_senha(senha: str) -> str:
    """Gera o hash seguro Bcrypt de uma senha em texto puro."""
    return pwd_context.hash(senha)


def verificar_senha(senha_plana: str, senha_hash: str) -> bool:
    """Compara uma senha em texto puro com seu hash Bcrypt."""
    return pwd_context.verify(senha_plana, senha_hash)


def criar_token_sessao(usuario_id: int, perfil: str) -> str:
    """Cria um token de sessão assinado com itsdangerous para o cookie HTTP-only."""
    payload = {"sub": int(usuario_id), "perfil": perfil}
    return serializer.dumps(payload)


def decodificar_token_sessao(token: str) -> Optional[dict]:
    """Decodifica e valida a assinatura e validade do token de sessão."""
    try:
        dados = serializer.loads(token, max_age=SESSION_MAX_AGE)
        return dados if isinstance(dados, dict) else None
    except (BadSignature, SignatureExpired):
        return None


def obter_usuario_logado_opcional(
    request: Request, db: Session = Depends(get_db)
) -> Optional[Usuario]:
    """Retorna o usuário autenticado via cookie ou None caso não esteja logado."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None

    dados = decodificar_token_sessao(token)
    if not dados or "sub" not in dados:
        return None

    try:
        usuario_id = int(dados["sub"])
    except (ValueError, TypeError):
        return None

    return db.query(Usuario).filter(Usuario.id == usuario_id).first()


def obter_usuario_logado(
    usuario: Optional[Usuario] = Depends(obter_usuario_logado_opcional),
) -> Usuario:
    """Exige que o usuário esteja autenticado; lança 401 caso contrário."""
    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Autenticação necessária. Faça login para acessar este recurso.",
        )
    return usuario


def exigir_analista(usuario: Usuario = Depends(obter_usuario_logado)) -> Usuario:
    """Exige que o usuário autenticado possua o perfil ANALISTA; lança 403 caso contrário."""
    if usuario.perfil != "ANALISTA":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado. Apenas usuários com perfil ANALISTA podem realizar esta ação.",
        )
    return usuario


def verificar_acesso_solicitacao(solicitacao: Solicitacao, usuario: Usuario) -> None:
    """
    Garante que um SOLICITANTE acesse apenas suas próprias solicitações,
    enquanto o ANALISTA pode acessar todas.
    """
    if usuario.perfil != "ANALISTA" and solicitacao.usuario_id != usuario.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado. Você não tem permissão para acessar a solicitação de outro usuário.",
        )
