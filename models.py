from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from database import Base

# Catálogos fixos da aplicação
PERFIS_VALIDOS = ("SOLICITANTE", "ANALISTA")
CATEGORIAS_VALIDAS = ("TI", "Financeiro", "RH", "Operações")
PRIORIDADES_VALIDAS = ("Baixa", "Média", "Alta")
STATUS_VALIDOS = ("Aberta", "Em análise", "Concluída")


class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(120), nullable=False)
    email = Column(String(150), unique=True, nullable=False, index=True)
    senha_hash = Column(String(255), nullable=False)
    perfil = Column(String(30), nullable=False, default="SOLICITANTE")

    solicitacoes = relationship(
        "Solicitacao",
        back_populates="usuario",
        cascade="all, delete-orphan",
    )
    alteracoes_status = relationship(
        "HistoricoStatus",
        back_populates="usuario",
    )


class Solicitacao(Base):
    __tablename__ = "solicitacoes"

    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(
        Integer,
        ForeignKey("usuarios.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    titulo = Column(String(200), nullable=False)
    descricao = Column(Text, nullable=False)
    categoria = Column(String(50), nullable=False)
    prioridade = Column(String(30), nullable=False)
    status = Column(String(30), nullable=False, default="Aberta", index=True)
    criada_em = Column(DateTime, nullable=False, default=datetime.now)

    usuario = relationship("Usuario", back_populates="solicitacoes")
    anexos = relationship(
        "Anexo",
        back_populates="solicitacao",
        cascade="all, delete-orphan",
    )
    historico = relationship(
        "HistoricoStatus",
        back_populates="solicitacao",
        cascade="all, delete-orphan",
        order_by="HistoricoStatus.data.desc(), HistoricoStatus.id.desc()",
    )


class Anexo(Base):
    __tablename__ = "anexos"

    id = Column(Integer, primary_key=True, index=True)
    solicitacao_id = Column(
        Integer,
        ForeignKey("solicitacoes.id", ondelete="CASCADE"),
        nullable=False,
    )
    nome_original = Column(String(255), nullable=False)
    tipo = Column(String(50), nullable=False)
    caminho_seguro = Column(String(500), nullable=False)
    tamanho = Column(Integer, nullable=False)

    solicitacao = relationship("Solicitacao", back_populates="anexos")


class HistoricoStatus(Base):
    __tablename__ = "historico_status"

    id = Column(Integer, primary_key=True, index=True)
    solicitacao_id = Column(
        Integer,
        ForeignKey("solicitacoes.id", ondelete="CASCADE"),
        nullable=False,
    )
    usuario_id = Column(
        Integer,
        ForeignKey("usuarios.id", ondelete="SET NULL"),
        nullable=False,
    )
    status_anterior = Column(String(30), nullable=False)
    novo_status = Column(String(30), nullable=False)
    data = Column(DateTime, nullable=False, default=datetime.now)

    solicitacao = relationship("Solicitacao", back_populates="historico")
    usuario = relationship("Usuario", back_populates="alteracoes_status")
