# FocusFlow

> Plataforma de produtividade estilo Notion + Pomodoro, com controle de tempo por tarefa em tempo real.

---

## Stack

- **Backend:** Python Flask + Flask-Login + Flask-SQLAlchemy + Bcrypt
- **Banco:** MySQL 8+
- **Frontend:** HTML5 + CSS3 + JavaScript puro (sem frameworks externos)
- **Design:** Dark mode, glassmorphism, animacoes suaves

---

## Instalacao local

### 1. Pre-requisitos

- Python 3.10+
- MySQL 8.0+
- pip

### 2. Clonar / descompactar o projeto

```
cd focusflow
```

### 3. Criar ambiente virtual

```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate
```

### 4. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 5. Criar banco de dados MySQL

```bash
mysql -u root -p < schema.sql
```

Ou manualmente:
```sql
CREATE DATABASE focusflow CHARACTER SET utf8mb4;
```

### 6. Configurar credenciais

Edite `config.py` ou crie um arquivo `.env`:

```
MYSQL_HOST=localhost
MYSQL_USER=root
MYSQL_PASSWORD=sua_senha
MYSQL_DB=focusflow
SECRET_KEY=troque-por-uma-chave-segura
```

Ou edite diretamente a classe `Config` em `config.py`.

### 7. Rodar a aplicacao

```bash
python run.py
```

Acesse: **http://localhost:5000**

As tabelas do banco sao criadas automaticamente na primeira execucao.

---

## Estrutura do Projeto

```
focusflow/
├── app/
│   ├── __init__.py          # Factory da aplicacao Flask
│   ├── models.py            # Modelos SQLAlchemy (User, Task, TaskSession)
│   ├── auth/
│   │   ├── __init__.py
│   │   └── routes.py        # Login, registro, logout
│   ├── tasks/
│   │   ├── __init__.py
│   │   └── routes.py        # CRUD de tarefas + API do timer
│   ├── main/
│   │   ├── __init__.py
│   │   └── routes.py        # Dashboard e historico
│   ├── static/
│   │   ├── css/app.css      # Estilos completos
│   │   └── js/
│   │       ├── app.js       # Utilitarios gerais
│   │       └── timer.js     # Motor do timer em tempo real
│   └── templates/
│       ├── base.html        # Layout base com sidebar
│       ├── dashboard.html   # Dashboard principal
│       ├── history.html     # Historico de dias
│       ├── auth/
│       │   ├── login.html
│       │   └── register.html
│       └── tasks/
│           ├── list.html    # Lista de tarefas
│           └── form.html    # Criar / editar tarefa
├── config.py                # Configuracoes da aplicacao
├── run.py                   # Ponto de entrada
├── schema.sql               # Script SQL para criar banco
└── requirements.txt
```

---

## Funcionalidades

### Autenticacao
- Registro, login e logout
- Senhas criptografadas com bcrypt
- Sessoes persistentes com Flask-Login

### Tarefas
- Criar / editar / excluir tarefas
- Definir nome, descricao, duracao diaria, cor e icone
- Marcar como recorrente (aparece todo dia automaticamente)

### Timer inteligente
- Play / Pause / Reset por tarefa
- Timer roda em tempo real no browser (JavaScript)
- Sincroniza com banco a cada 10 segundos e ao pausar
- Apenas uma tarefa roda por vez — as demais sao pausadas automaticamente
- Estado persiste ao recarregar a pagina
- Notificacao visual ao concluir

### Dashboard
- Progresso diario em percentual e barra animada
- Mini grafico dos ultimos 7 dias
- Cards de tarefa com anel de progresso SVG animado

### Historico
- Feed dos ultimos 30 dias
- Por dia: tarefas realizadas, tempo total, percentual de conclusao

---

## API do Timer (uso interno)

| Endpoint | Metodo | Descricao |
|---|---|---|
| `/tasks/api/timer/start/<id>` | POST | Inicia timer (pausa outros) |
| `/tasks/api/timer/pause/<id>` | POST | Pausa timer |
| `/tasks/api/timer/reset/<id>` | POST | Reseta sessao do dia |
| `/tasks/api/timer/sync/<id>`  | POST | Salva elapsed seconds |
| `/tasks/api/tasks/state`      | GET  | Estado atual de todas as tarefas |

---

## Personalizacao

- Cores e icones definidos em `app/tasks/routes.py` (listas `TASK_COLORS` e `TASK_ICONS`)
- Paleta de cores do sistema em `app/static/css/app.css` (variaveis CSS `:root`)
- Para adicionar novas paginas, crie um blueprint seguindo o padrao de `app/main/`
