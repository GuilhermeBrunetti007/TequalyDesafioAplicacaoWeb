# Portal de Solicitações Internas

Aplicação web monolítica em Python desenvolvida para registrar solicitações internas, enviar anexos com validação e proteção de acesso, acompanhar o histórico de mudanças de status e apresentar indicadores gerenciais.

---

## 1. Como executar o projeto passo a passo

### Pré-requisitos
- **Python 3.11+**
- **PostgreSQL 16** instalado localmente e em execução na porta `5432`

### Passo 1: Criar o banco de dados no PostgreSQL local
No terminal (ou via pgAdmin / `psql`), crie o banco de dados `portal_solicitacoes`:
```bash
psql -U postgres -h localhost -c "CREATE DATABASE portal_solicitacoes;"
```

### Passo 2: Configurar o arquivo `.env`
Copie o arquivo de exemplo `.env.example` para `.env` na raiz do projeto:

**No Windows (PowerShell):**
```powershell
Copy-Item .env.example .env
```

**No Linux / macOS:**
```bash
cp .env.example .env
```

Verifique se a variável `DATABASE_URL` no `.env` está apontando para o seu PostgreSQL local:
```ini
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/portal_solicitacoes
SECRET_KEY=chave_secreta_portal_solicitacoes_2026
```

### Passo 3: Criar e ativar o ambiente virtual (`.venv`) e instalar as dependências
**No Windows (PowerShell):**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**No Linux / macOS:**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Passo 4: Executar as migrations do banco de dados (Alembic)
```bash
alembic upgrade head
```

### Passo 5: Popular o banco com os dados fictícios iniciais (`seed.py`)
```bash
python seed.py
```

### Passo 6: Iniciar o servidor da aplicação
```bash
uvicorn main:app --reload
```
Acesse no navegador: **http://127.0.0.1:8000/login**

### Passo 7: Executar a suíte de testes automatizados (`pytest`)
```bash
pytest -v
```

---

## 2. Contas fictícias de demonstração

O script `seed.py` cria automaticamente 1 usuário com perfil **Analista**, 2 usuários com perfil **Solicitante** e 10 solicitações fictícias distribuídas entre diferentes categorias, prioridades, datas e históricos de status:

| Perfil | Nome | E-mail | Senha | Permissões no Sistema |
| :--- | :--- | :--- | :--- | :--- |
| **ANALISTA** | Maria Oliveira | `analista@empresa.com` | `123456` | Visualiza todas as solicitações, baixa qualquer anexo, exporta CSV completo e altera status para *Em análise* ou *Concluída*. |
| **SOLICITANTE** | João Silva | `joao@empresa.com` | `123456` | Cadastra novas solicitações, envia anexos e visualiza, filtra e exporta apenas as demandas que ele mesmo abriu. |
| **SOLICITANTE** | Ana Costa | `ana@empresa.com` | `123456` | Segunda conta de solicitante para validar o isolamento de permissões (retorna erro HTTP 403 ao tentar acessar solicitação ou anexo de outro usuário). |

---

## 3. Decisões técnicas

- **Python (FastAPI) + SQLAlchemy + Alembic + PostgreSQL:** Escolhi essa stack pela clareza e legibilidade do código, pelo versionamento seguro do schema relacional (`usuarios`, `solicitacoes`, `anexos` e `historico_status`, com índices em `solicitacoes.usuario_id` e `solicitacoes.status`) e pela prevenção nativa contra *SQL Injection*, já que todas as operações de banco são feitas via ORM sem concatenação de SQL.
- **Jinja2 + Bootstrap 5 CDN + Chart.js CDN:** Optei por templates HTML renderizados diretamente pelo FastAPI com estilização via Bootstrap 5 CDN para manter uma arquitetura monolítica simples, limpa e focada nas regras de negócio, banco de dados e segurança exigidas pelo desafio.
- **Catálogo fixo para categorias:** Mantive as categorias (`TI`, `Financeiro`, `RH` e `Operações`) como um catálogo fixo validado na aplicação para simplificar as consultas e manter o foco no fluxo principal, podendo evoluir facilmente para uma tabela própria caso surja necessidade de cadastro dinâmico no futuro.
- **Segurança no Backend:** As senhas são salvas exclusivamente com hash **Bcrypt** (`passlib`), a autenticação utiliza cookie `HttpOnly` assinado com `itsdangerous` e os anexos passam por validação estrita de tipo (`.pdf`, `.jpg`, `.png`) e tamanho máximo (5 MB) no servidor, sendo armazenados renomeados com `uuid4()` em `storage/uploads/` (fora de acesso público direto) e entregues apenas pela rota autenticada `/anexos/{id}/download`.

---

## 4. O que funciona e o que ficou pendente

### O que funciona (Prioridade 1 e Prioridade 2 completas)
- [x] **PostgreSQL e Migrations (Alembic):** Criação versionada das 4 tabelas relacionais com PK/FK, constraints, índices em `usuario_id` e `status` e script `seed.py` com usuários e solicitações fictícias.
- [x] **Acesso e Permissões:** Login com senha protegida por hash Bcrypt, controle de perfil (`SOLICITANTE` e `ANALISTA`) validado no backend e proteção no download de anexos (`403 Forbidden` para acessos não autorizados).
- [x] **Cadastro de Solicitações e Anexos:** Formulário com título, descrição, categoria e prioridade, status inicial `Aberta`, data automática e upload opcional de PDF, JPG ou PNG até 5 MB validado no backend.
- [x] **Listagem, Acompanhamento e Histórico:** Listagem com filtro por status e período, visualização de detalhes, alteração de status pelo Analista para `Em análise` ou `Concluída` e gravação automática em `historico_status` na mesma transação.
- [x] **Dashboard Gerencial:** Indicadores de *Total*, *Abertas*, *Em análise* e *Concluídas* e gráficos com Chart.js por status e por categoria refletindo os registros reais do PostgreSQL.
- [x] **Relatórios e Exportação CSV:** Filtro por período e status com exportação em `.csv` respeitando rigorosamente a permissão do perfil logado.
- [x] **Testes Automatizados (`pytest`):** Suíte validando login, isolamento de permissão entre Solicitante e Analista, mudança de status com histórico, bloqueio de arquivo inválido e exportação CSV diretamente no PostgreSQL.

### O que ficou pendente
- [ ] **Exportação de relatório em PDF:** Não foi incluída por ser um item opcional/diferencial, priorizando a entrega completa e testada de todos os itens obrigatórios e da exportação em CSV.

---

## 5. Uso de ferramentas de IA

Durante o desenvolvimento deste projeto, utilizei o **Gemini** como ferramenta de apoio para revisar a modelagem relacional e as relações do banco de dados, estruturar os templates HTML com Bootstrap 5 e auxiliar na depuração, correções de bugs e validação dos testes. Todas as regras de negócio, consultas SQLAlchemy, validações de segurança e testes foram revisados e validados localmente.
