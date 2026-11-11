"""create initial tables and indexes

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-11-11 18:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "usuarios",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nome", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=150), nullable=False),
        sa.Column("senha_hash", sa.String(length=255), nullable=False),
        sa.Column("perfil", sa.String(length=30), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index(op.f("ix_usuarios_id"), "usuarios", ["id"], unique=False)
    op.create_index(op.f("ix_usuarios_email"), "usuarios", ["email"], unique=True)

    op.create_table(
        "solicitacoes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("titulo", sa.String(length=200), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=False),
        sa.Column("categoria", sa.String(length=50), nullable=False),
        sa.Column("prioridade", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="Aberta"),
        sa.Column("criada_em", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_solicitacoes_id"), "solicitacoes", ["id"], unique=False)
    op.create_index(
        op.f("ix_solicitacoes_usuario_id"),
        "solicitacoes",
        ["usuario_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_solicitacoes_status"),
        "solicitacoes",
        ["status"],
        unique=False,
    )

    op.create_table(
        "anexos",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("solicitacao_id", sa.Integer(), nullable=False),
        sa.Column("nome_original", sa.String(length=255), nullable=False),
        sa.Column("tipo", sa.String(length=50), nullable=False),
        sa.Column("caminho_seguro", sa.String(length=500), nullable=False),
        sa.Column("tamanho", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["solicitacao_id"], ["solicitacoes.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_anexos_id"), "anexos", ["id"], unique=False)

    op.create_table(
        "historico_status",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("solicitacao_id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("status_anterior", sa.String(length=30), nullable=False),
        sa.Column("novo_status", sa.String(length=30), nullable=False),
        sa.Column("data", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["solicitacao_id"], ["solicitacoes.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_historico_status_id"), "historico_status", ["id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_historico_status_id"), table_name="historico_status")
    op.drop_table("historico_status")
    op.drop_index(op.f("ix_anexos_id"), table_name="anexos")
    op.drop_table("anexos")
    op.drop_index(op.f("ix_solicitacoes_status"), table_name="solicitacoes")
    op.drop_index(op.f("ix_solicitacoes_usuario_id"), table_name="solicitacoes")
    op.drop_index(op.f("ix_solicitacoes_id"), table_name="solicitacoes")
    op.drop_table("solicitacoes")
    op.drop_index(op.f("ix_usuarios_email"), table_name="usuarios")
    op.drop_index(op.f("ix_usuarios_id"), table_name="usuarios")
    op.drop_table("usuarios")
