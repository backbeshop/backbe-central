import sqlite3, json, os
from pathlib import Path


def _resolve_db_path() -> Path:
    """Resolve o caminho do banco SQLite.
    - Usa DB_PATH env var se definida (útil nos secrets do Streamlit Cloud).
    - Tenta criar o diretório local data/ (funciona em dev).
    - Se o filesystem for read-only (Streamlit Cloud), cai para /tmp.
    """
    env_path = os.getenv("DB_PATH")
    if env_path:
        p = Path(env_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    local_dir = Path(__file__).parent / "data"
    try:
        local_dir.mkdir(parents=True, exist_ok=True)
        return local_dir / "backbe.db"
    except OSError:
        # Streamlit Cloud: /mount/src/ é read-only → usa /tmp
        return Path("/tmp") / "backbe.db"


DB_PATH = _resolve_db_path()

def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    c = conn.cursor()

    # Tecidos
    c.execute("""
    CREATE TABLE IF NOT EXISTS tecidos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        tipo TEXT,
        unidade TEXT,
        preco_kg REAL,
        preco_metro REAL,
        peso_gsm REAL,
        largura_m REAL DEFAULT 1.5,
        cor TEXT,
        estoque REAL DEFAULT 0,
        estoque_unidade TEXT DEFAULT 'metros',
        observacoes TEXT,
        ativo INTEGER DEFAULT 1,
        criado_em TEXT DEFAULT (datetime('now'))
    )""")

    # Costureiras
    c.execute("""
    CREATE TABLE IF NOT EXISTS costureiras (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        tipo TEXT DEFAULT 'mae',
        ativa INTEGER DEFAULT 1
    )""")

    # Tabela de preços de costura por categoria
    c.execute("""
    CREATE TABLE IF NOT EXISTS costura_precos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        categoria TEXT NOT NULL,
        descricao TEXT,
        preco_mae REAL NOT NULL,
        preco_terc REAL,
        atualizado_em TEXT DEFAULT (datetime('now'))
    )""")

    # Ordens de producao
    c.execute("""
    CREATE TABLE IF NOT EXISTS ordens_producao (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        referencia TEXT,
        produto TEXT NOT NULL,
        quantidade INTEGER NOT NULL,
        tecido_id INTEGER REFERENCES tecidos(id),
        tecido_metros REAL,
        costureira_id INTEGER REFERENCES costureiras(id),
        status TEXT DEFAULT 'modelagem',
        prioridade TEXT DEFAULT 'normal',
        custo_tecido REAL,
        custo_costura REAL,
        custo_corte REAL DEFAULT 0,
        custo_aviamentos REAL DEFAULT 0,
        custo_embalagem REAL DEFAULT 10,
        custo_total REAL,
        observacoes TEXT,
        data_entrada TEXT DEFAULT (datetime('now','localtime')),
        data_prevista TEXT,
        data_conclusao TEXT
    )""")

    # Clientes CRM
    c.execute("""
    CREATE TABLE IF NOT EXISTS clientes_crm (
        ns_id TEXT PRIMARY KEY,
        nome TEXT,
        email TEXT,
        telefone TEXT,
        total_pedidos INTEGER DEFAULT 0,
        total_gasto REAL DEFAULT 0,
        ultimo_pedido TEXT,
        primeiro_pedido TEXT,
        segmento TEXT,
        tag TEXT,
        notas TEXT,
        atualizado_em TEXT DEFAULT (datetime('now'))
    )""")

    # Cache NS
    c.execute("""
    CREATE TABLE IF NOT EXISTS ns_cache (
        chave TEXT PRIMARY KEY,
        valor TEXT,
        expira_em TEXT
    )""")

    # Declarações MEI
    c.execute("""
    CREATE TABLE IF NOT EXISTS mei_declaracoes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        mei_nome TEXT NOT NULL,
        mei_razao TEXT,
        ano INTEGER NOT NULL,
        receita_bruta REAL DEFAULT 0,
        criado_em TEXT DEFAULT (datetime('now','localtime')),
        UNIQUE(mei_nome, ano)
    )""")

    # Transações MEI
    c.execute("""
    CREATE TABLE IF NOT EXISTS mei_transacoes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        declaracao_id INTEGER REFERENCES mei_declaracoes(id) ON DELETE CASCADE,
        data TEXT,
        descricao TEXT,
        valor REAL,
        tipo TEXT,
        contar_receita INTEGER DEFAULT 1,
        arquivo TEXT
    )""")

    # Fornecedores de tecidos ("Onde Comprar")
    c.execute("""
    CREATE TABLE IF NOT EXISTS tecidos_fornecedores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tecido_id INTEGER REFERENCES tecidos(id) ON DELETE CASCADE,
        fornecedor TEXT NOT NULL,
        contato TEXT,
        cidade TEXT,
        site TEXT,
        observacoes TEXT,
        criado_em TEXT DEFAULT (datetime('now','localtime'))
    )""")

    # Acabamentos / Peças
    c.execute("""
    CREATE TABLE IF NOT EXISTS acabamentos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        categoria TEXT DEFAULT 'outro',
        unidade TEXT DEFAULT 'unidade',
        preco REAL NOT NULL DEFAULT 0,
        observacoes TEXT,
        ativo INTEGER DEFAULT 1,
        criado_em TEXT DEFAULT (datetime('now','localtime'))
    )""")

    # Produtos Backbe (importados da planilha)
    c.execute("""
    CREATE TABLE IF NOT EXISTS produtos_backbe (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        colecao TEXT,
        metragem_cm REAL DEFAULT 0,
        custo_tecido REAL DEFAULT 0,
        custo_corte REAL DEFAULT 0,
        custo_costura REAL DEFAULT 0,
        custo_etiquetas REAL DEFAULT 0,
        custo_adicional REAL DEFAULT 0,
        custo_embalagem REAL DEFAULT 0,
        custo_modelagem REAL DEFAULT 0,
        lote_minimo INTEGER DEFAULT 10,
        custo_total REAL DEFAULT 0,
        preco_venda REAL DEFAULT 0,
        observacoes TEXT,
        ativo INTEGER DEFAULT 1,
        atualizado_em TEXT DEFAULT (datetime('now','localtime'))
    )""")

    # Relatório Mãe
    c.execute("""
    CREATE TABLE IF NOT EXISTS relatorio_mae (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        mes INTEGER NOT NULL,
        ano INTEGER NOT NULL,
        costureira_id INTEGER REFERENCES costureiras(id),
        total_pecas INTEGER DEFAULT 0,
        total_costura REAL DEFAULT 0,
        receita_mes REAL DEFAULT 0,
        comissao_pct REAL DEFAULT 3.0,
        comissao_valor REAL DEFAULT 0,
        total_pagar REAL DEFAULT 0,
        pago INTEGER DEFAULT 0,
        observacoes TEXT,
        criado_em TEXT DEFAULT (datetime('now','localtime')),
        UNIQUE(mes, ano, costureira_id)
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS relatorio_mae_itens (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        relatorio_id INTEGER REFERENCES relatorio_mae(id) ON DELETE CASCADE,
        produto TEXT NOT NULL,
        categoria TEXT,
        quantidade INTEGER DEFAULT 0,
        preco_unitario REAL DEFAULT 0,
        subtotal REAL DEFAULT 0
    )""")

    # Costureiras padrão
    c.execute("SELECT COUNT(*) FROM costureiras")
    if c.fetchone()[0] == 0:
        c.executemany("INSERT INTO costureiras (nome, tipo) VALUES (?, ?)", [
            ("Mãe", "mae"),
            ("Terceirizada 1", "terceirizada"),
            ("Terceirizada 2", "terceirizada"),
        ])
    # Fix nome antigo se existir
    c.execute("UPDATE costureiras SET nome='Mãe' WHERE nome='Mãe (Dilma)'")

    # Preços de costura padrão
    c.execute("SELECT COUNT(*) FROM costura_precos")
    if c.fetchone()[0] == 0:
        precos = [
            ("Blusa simples", "Blusa sem detalhes especiais", 15.0),
            ("Blusa com renda/detalhe", "Blusa com aplicação, renda ou bordado", 22.0),
            ("Cropped", "Top cropped ou cropped simples", 12.0),
            ("Body", "Body com abertura inferior", 18.0),
            ("Saia curta/midi", "Saia até o joelho ou midi", 15.0),
            ("Saia longa", "Saia maxi ou longa", 18.0),
            ("Calça", "Calça comprida de qualquer tecido", 22.0),
            ("Shorts/Bermuda", "Shorts ou bermuda", 15.0),
            ("Vestido simples", "Vestido sem forro ou detalhes complexos", 25.0),
            ("Vestido com forro", "Vestido forrado", 32.0),
            ("Conjunto (top + saia)", "Peças separadas mas produzidas juntas", 25.0),
            ("Conjunto (blusa + calça)", "Peças separadas mas produzidas juntas", 32.0),
            ("Macacão", "Macacão curto ou longo", 35.0),
            ("Corset/Espartilho", "Peça com estrutura ou rigilene", 30.0),
        ]
        for cat, desc, preco_mae in precos:
            c.execute(
                "INSERT INTO costura_precos (categoria, descricao, preco_mae, preco_terc) VALUES (?,?,?,?)",
                (cat, desc, preco_mae, round(preco_mae * 0.7, 2))
            )

    # Tecidos Backbe — seed persistente (inserido se não existir pelo nome)
    # (nome, tipo, unidade, preco_kg, preco_metro, peso_gsm, largura_m, cor, composicao, fornecedor)
    TECIDOS_SEED = [
        ("Tricoline",           "tecido", "metro", None, 12.90, None,  1.5, "diversas", "85% poliéster e 15% algodão", "gabtextil"),
        ("Alfaiataria Barbie",  "tecido", "metro", None, 12.90, None,  1.5, "diversas", "95% poliéster e 5% elastano", "gabtextil"),
        ("Gabardine",           "tecido", "metro", None, 12.50, 225.0, 1.5, "diversas", "100% poliéster",              "loja de tecidos"),
        ("Two Way",             "malha",  "metro", None, 15.90, None,  1.5, "diversas", "96% poliéster 4% elastano",   "loja de tecidos"),
        ("Duna Air Flow",       "tecido", "metro", None, 13.60, None,  1.5, "diversas", "",                            "loja de tecidos"),
        ("Duna Bordado",        "tecido", "metro", None, 14.90, None,  1.5, "diversas", "",                            "loja de tecidos"),
        ("Crepe Amanda",        "tecido", "metro", None, 14.20, None,  1.5, "diversas", "",                            "loja de tecidos"),
        ("Crepe com aplicação", "tecido", "metro", None, 14.90, None,  1.5, "diversas", "",                            "loja de tecidos"),
        ("Viscolinho",          "tecido", "metro", None, 12.90, None,  1.5, "diversas", "100% viscose",                "gab textil"),
    ]
    for (nome, tipo, unidade, preco_kg, preco_metro, gsm, largura, cor, composicao, forn_nome) in TECIDOS_SEED:
        exists = c.execute("SELECT id FROM tecidos WHERE nome=?", (nome,)).fetchone()
        if not exists:
            c.execute(
                "INSERT INTO tecidos (nome, tipo, unidade, preco_kg, preco_metro, peso_gsm, largura_m, cor, observacoes) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (nome, tipo, unidade, preco_kg, preco_metro, gsm, largura, cor, composicao)
            )
            tec_id = c.lastrowid
            if forn_nome:
                c.execute(
                    "INSERT INTO tecidos_fornecedores (tecido_id, fornecedor) VALUES (?,?)",
                    (tec_id, forn_nome)
                )

    conn.commit()
    conn.close()

def row_to_dict(row):
    return dict(row) if row else None

def rows_to_list(rows):
    return [dict(r) for r in rows]
