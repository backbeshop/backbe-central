# -*- coding: utf-8 -*-
"""
Seed: cortes da Vo Marcia — Jan/Fev/Mar/Abr 2026
(produto, qtd, total_corte, feito_pela_vo)
feito_pela_vo=1 → Vo Marcia cortou; 0 → outra pessoa
"""
import sqlite3

DB  = r'data/backbe.db'
ANO = 2026

# Extraido da coluna "Valor do Corte" da planilha
DADOS = {
    1: [  # Janeiro — todos por Vo Marcia (feito_pela_vo=1)
        ("Blusa Malasia (antigo solaris)",       4,  16.00, 1),
        ("Saia Algeria (com fenda)",             15,  60.00, 1),
        ("Saia Georgia",                          4,  12.00, 1),
        ("Blusa Novo Mexico",                     4,  16.00, 1),
        ("Calca Islandia (ilhos)",                1,   4.00, 1),
        ("Vestido Australia",                     1,   3.00, 1),
        ("Blusa Havai (tomara que caia)",         6,  18.00, 1),
        ("Blusa Maldivas (lastex)",               2,   8.00, 1),
        ("Calca Maldivas (lastex)",               2,   8.00, 1),
        ("Calca Havai",                           2,   8.00, 1),
        ("Blusa Algeria gola",                    2,   4.00, 1),
        ("Saia Australia Acetinada",              1,   4.00, 1),
        ("Cropped Angola",                        1,   3.00, 1),
        ("Calca Italia",                          1,   8.00, 1),
        ("Saia Bolivia",                          3,   9.00, 1),
        ("Blusa Luxemburgo (triangulo)",          2,   5.00, 1),
        ("Cropped Grecia",                        2,   4.00, 1),
        ("Vestido Luxemburgo (australia longo)",  1,   3.00, 1),
        ("Mini Saia Australia",                   1,   3.00, 1),
        ("Cropped Transpassado",                  1,   4.00, 1),
    ],
    2: [  # Fevereiro
        ("Blusa Malasia (antigo solaris)",        4,  16.00, 1),
        ("Cropped Grecia",                        5,  10.00, 1),
        ("Blusa Luxemburgo (triangulo)",          4,  10.00, 1),
        ("Saia Bolivia",                          2,   6.00, 1),
        ("Mini Saia Australia",                   4,  12.00, 1),
        ("Vestido Luxemburgo (australia longo)",  2,   6.00, 1),
        ("Vestido Santorini",                     1,   4.00, 1),
        ("Cropped Angola",                        6,  18.00, 1),
        ("Vestido Grecia",                        1,   3.00, 1),
        ("Saia Georgia",                          3,   9.00, 1),
        ("Blusa Filipinas (soltinha)",            7,  17.50, 1),
        ("Blusa Algeria gola",                    4,   8.00, 1),
        ("Corset Tulum",                          1,   5.00, 1),
        ("Calca Italia",                          9,  72.00, 1),
        ("Vestido Australia",                     1,   3.00, 1),
        ("Blusa Novo Mexico",                     1,   4.00, 1),
        ("Blusa Havai (tomara que caia)",         3,   9.00, 1),
        ("Vestido Maldivas (lastex)",             1,   5.00, 1),
        ("Calca Havai",                           1,   4.00, 1),
        ("Saia Bali",                             1,   3.00, 1),
        ("Cropped Bali",                          1,   4.00, 1),
    ],
    3: [  # Marco
        ("Saia Algeria (com fenda)",             37, 148.00, 1),
        ("Vestido Luxemburgo (australia longo)",  3,   9.00, 1),
        ("Cropped Angola",                        1,   3.00, 1),
        ("Calca Angola",                          1,   4.00, 1),
        ("Vestido Brasil (longo)",                2,   8.00, 1),
        ("Vestido Santorini",                     2,   8.00, 1),
        ("Calca Italia",                          5,  40.00, 1),
        ("Cropped Bali",                          1,   4.00, 1),
        ("Cropped Bangladesh",                    2,   6.00, 1),
        ("Calca Havai",                           1,   4.00, 1),
        ("Blusa Brasil",                          1,   4.00, 1),
        ("Saia Dinamarca",                        2,  14.00, 1),
        ("Saia Arabia",                           1,   3.00, 1),
        ("Blusa Novo Mexico",                     2,   8.00, 1),
        ("Calca Islandia (ilhos)",                1,   4.00, 1),
        ("Blusa Georgia",                         1,   3.00, 1),
        ("Saia Bali",                            12,  36.00, 1),
    ],
    4: [  # Abril
        ("Blusa Novo Mexico",                     6,  24.00, 1),
        ("Vestido Luxemburgo (australia longo)",  6,  18.00, 1),
        ("Calca Algeria (pecinha)",               1,   4.00, 1),
        ("Mini Saia Australia",                   2,   6.00, 1),
        ("Calca Italia",                          2,  16.00, 1),
        ("Vestido Maldivas (lastex)",             1,   5.00, 1),
        ("Calca Maldivas (lastex)",               1,   4.00, 1),
        ("Blusa Maldivas (lastex)",               1,   4.00, 1),
        ("Saia Dinamarca",                        1,   7.00, 1),
        ("Blusa Filipinas (soltinha)",            6,  15.00, 1),
        ("Blusa Havai (tomara que caia)",         1,   3.00, 1),
        ("Calca Angola",                          1,   4.00, 1),
        ("Calca Islandia (ilhos)",                1,   4.00, 1),
        ("Blusa Georgia",                         2,   6.00, 1),
    ],
}

MESES = {1:"Janeiro", 2:"Fevereiro", 3:"Marco", 4:"Abril"}


def run():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    # Cria tabelas se ainda nao existem (caso db.py nao tenha rodado)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS relatorio_corte (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        mes INTEGER NOT NULL, ano INTEGER NOT NULL,
        cortadora TEXT DEFAULT 'Vo Marcia',
        total_pecas INTEGER DEFAULT 0,
        total_corte REAL DEFAULT 0,
        pago INTEGER DEFAULT 0, observacoes TEXT,
        UNIQUE(mes, ano)
    )""")
    conn.execute("""
    CREATE TABLE IF NOT EXISTS relatorio_corte_itens (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        relatorio_id INTEGER NOT NULL REFERENCES relatorio_corte(id),
        produto TEXT NOT NULL,
        quantidade INTEGER DEFAULT 0,
        valor_corte_total REAL DEFAULT 0,
        valor_corte_unit REAL DEFAULT 0,
        feito_pela_vo INTEGER DEFAULT 1
    )""")
    conn.commit()

    for mes, items in DADOS.items():
        conn.execute(
            "INSERT OR IGNORE INTO relatorio_corte (mes, ano) VALUES (?,?)",
            (mes, ANO)
        )
        conn.commit()
        rel = conn.execute(
            "SELECT id FROM relatorio_corte WHERE mes=? AND ano=?",
            (mes, ANO)
        ).fetchone()
        rel_id = rel["id"]

        conn.execute(
            "DELETE FROM relatorio_corte_itens WHERE relatorio_id=?", (rel_id,)
        )
        for prod, qtd, total_cor, pela_vo in items:
            unit = round(total_cor / qtd, 2)
            conn.execute(
                "INSERT INTO relatorio_corte_itens "
                "(relatorio_id, produto, quantidade, valor_corte_total, "
                "valor_corte_unit, feito_pela_vo) VALUES (?,?,?,?,?,?)",
                (rel_id, prod, qtd, total_cor, unit, pela_vo)
            )

        # Recalcula totais (apenas itens da vo)
        total_pecas = sum(q for _, q, _, v in items if v)
        total_corte = sum(t for _, _, t, v in items if v)
        conn.execute(
            "UPDATE relatorio_corte SET total_pecas=?, total_corte=? WHERE id=?",
            (total_pecas, total_corte, rel_id)
        )
        conn.commit()
        print(f"OK {MESES[mes]}: {total_pecas} pecas Vo - R${total_corte:.2f}")

    conn.close()
    print("Seed corte concluido.")


if __name__ == "__main__":
    run()
