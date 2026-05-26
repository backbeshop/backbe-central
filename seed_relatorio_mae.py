# -*- coding: utf-8 -*-
"""
Seed: producoes da mae costureira — Jan/Fev/Mar/Abr 2026
(produto, qtd, total_costura)
"""
import sqlite3

DB     = r'data/backbe.db'
MAE_ID = 1
ANO    = 2026

DADOS = {
    1: [  # Janeiro
        ("Blusa Malasia (antigo solaris)",       4,  60.00),
        ("Saia Algeria (com fenda)",             15, 255.00),
        ("Saia Georgia",                          4,  72.00),
        ("Blusa Novo Mexico",                     4,  60.00),
        ("Calca Islandia (ilhos)",                1,  33.00),
        ("Vestido Australia",                     1,  17.00),
        ("Blusa Havai (tomara que caia)",         6,  90.00),
        ("Blusa Maldivas (lastex)",               2,  44.00),
        ("Calca Maldivas (lastex)",               2,  52.00),
        ("Calca Havai",                           2,  40.00),
        ("Blusa Algeria gola",                    2,  26.00),
        ("Saia Australia Acetinada",              1,  17.00),
        ("Cropped Angola",                        1,  16.00),
        ("Calca Italia",                          1,  28.00),
        ("Saia Bolivia",                          3,  48.00),
        ("Blusa Luxemburgo (triangulo)",          2,  22.00),
        ("Cropped Grecia",                        2,  24.00),
        ("Vestido Luxemburgo (australia longo)",  1,  17.00),
        ("Mini Saia Australia",                   1,  15.00),
        ("Cropped Transpassado",                  1,  14.00),
    ],
    2: [  # Fevereiro
        ("Blusa Malasia (antigo solaris)",        4,  60.00),
        ("Cropped Grecia",                        5,  60.00),
        ("Blusa Luxemburgo (triangulo)",          4,  44.00),
        ("Saia Bolivia",                          2,  32.00),
        ("Mini Saia Australia",                   4,  60.00),
        ("Vestido Luxemburgo (australia longo)",  2,  34.00),
        ("Vestido Santorini",                     1,  18.00),
        ("Cropped Angola",                        6,  96.00),
        ("Vestido Grecia",                        1,  17.00),
        ("Saia Georgia",                          3,  54.00),
        ("Blusa Filipinas (soltinha)",            7,  77.00),
        ("Blusa Algeria gola",                    4,  52.00),
        ("Corset Tulum",                          1,  25.00),
        ("Calca Italia",                          9, 252.00),
        ("Vestido Australia",                     1,  17.00),
        ("Blusa Novo Mexico",                     1,  15.00),
        ("Blusa Havai (tomara que caia)",         3,  45.00),
        ("Vestido Maldivas (lastex)",             1,  17.00),
        ("Calca Havai",                           1,  20.00),
        ("Saia Bali",                             1,  14.00),
        ("Cropped Bali",                          1,  15.00),
    ],
    3: [  # Marco
        ("Saia Algeria (com fenda)",             37, 629.00),
        ("Vestido Luxemburgo (australia longo)",  3,  51.00),
        ("Cropped Angola",                        1,  16.00),
        ("Calca Angola",                          1,  20.00),
        ("Vestido Brasil (longo)",                2,  38.00),
        ("Vestido Santorini",                     2,  36.00),
        ("Calca Italia",                          5, 140.00),
        ("Cropped Bali",                          1,  15.00),
        ("Cropped Bangladesh",                    2,  30.00),
        ("Calca Havai",                           1,  20.00),
        ("Blusa Brasil",                          1,  19.00),
        ("Saia Dinamarca",                        2,  48.00),
        ("Saia Arabia",                           1,  16.00),
        ("Blusa Novo Mexico",                     2,  30.00),
        ("Calca Islandia (ilhos)",                1,  33.00),
        ("Blusa Georgia",                         1,  15.00),
        ("Saia Bali",                            12, 168.00),
    ],
    4: [  # Abril
        ("Blusa Novo Mexico",                     6,  90.00),
        ("Vestido Luxemburgo (australia longo)",  6, 102.00),
        ("Calca Algeria (pecinha)",               1,  30.00),
        ("Mini Saia Australia",                   2,  30.00),
        ("Calca Italia",                          2,  56.00),
        ("Vestido Maldivas (lastex)",             1,  17.00),
        ("Calca Maldivas (lastex)",               1,  26.00),
        ("Blusa Maldivas (lastex)",               1,  22.00),
        ("Saia Dinamarca",                        1,  24.00),
        ("Blusa Filipinas (soltinha)",            6,  66.00),
        ("Blusa Havai (tomara que caia)",         1,  15.00),
        ("Calca Angola",                          1,  20.00),
        ("Calca Islandia (ilhos)",                1,  33.00),
        ("Blusa Georgia",                         2,  30.00),
    ],
}

MESES = {1:"Janeiro", 2:"Fevereiro", 3:"Marco", 4:"Abril"}


def _recalc(conn, rel_id):
    itens = conn.execute(
        "SELECT quantidade, subtotal FROM relatorio_mae_itens WHERE relatorio_id=?",
        (rel_id,)
    ).fetchall()
    conn.execute(
        "UPDATE relatorio_mae SET total_pecas=?, total_costura=? WHERE id=?",
        (sum(i[0] for i in itens), sum(i[1] for i in itens), rel_id)
    )


def run():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    for mes, items in DADOS.items():
        conn.execute(
            "INSERT OR IGNORE INTO relatorio_mae "
            "(mes, ano, costureira_id, comissao_pct) VALUES (?,?,?,3.0)",
            (mes, ANO, MAE_ID)
        )
        conn.commit()
        rel = conn.execute(
            "SELECT id FROM relatorio_mae WHERE mes=? AND ano=? AND costureira_id=?",
            (mes, ANO, MAE_ID)
        ).fetchone()
        rel_id = rel["id"]

        conn.execute(
            "DELETE FROM relatorio_mae_itens WHERE relatorio_id=?", (rel_id,)
        )
        for prod, qtd, total_cos in items:
            preco_unit = round(total_cos / qtd, 2)
            conn.execute(
                "INSERT INTO relatorio_mae_itens "
                "(relatorio_id, produto, categoria, quantidade, preco_unitario, subtotal) "
                "VALUES (?,?,?,?,?,?)",
                (rel_id, prod, "", qtd, preco_unit, total_cos)
            )
        _recalc(conn, rel_id)
        conn.commit()
        total_pecas   = sum(q for _, q, _ in items)
        total_costura = sum(t for _, _, t in items)
        print(f"OK {MESES[mes]}: {total_pecas} pecas - R${total_costura:.2f}")

    conn.close()
    print("Seed costura concluido.")


if __name__ == "__main__":
    run()
