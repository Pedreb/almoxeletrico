import streamlit as st
import sqlite3
import pandas as pd

# Função para criar conexão com o banco de dados e ativar FOREIGN KEY
def get_db_connection():
    conn = sqlite3.connect("estoque.db", check_same_thread=False)
    c = conn.cursor()
    c.execute("PRAGMA foreign_keys = ON;")  # Ativando suporte a FOREIGN KEY
    return conn

# Conexão com banco de dados SQLite
conn = get_db_connection()
c = conn.cursor()

# Criando tabelas
c.execute("""
CREATE TABLE IF NOT EXISTS materiais (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo INTEGER UNIQUE,
    descricao TEXT,
    unidade TEXT
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS movimentacoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo INTEGER,
    descricao TEXT,
    quantidade REAL,
    tipo TEXT,
    projeto TEXT,
    equipe TEXT,
    data_movimentacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(codigo) REFERENCES materiais(codigo)
)
""")

conn.commit()

# Interface Streamlit
st.title("Controle de Estoque")

menu = ["Cadastro de Materiais", "Entrada de Material", "Saída de Material", "Baixa EQTL", "Devolução de Material",
        "Estorno de Material", "Visão Geral do Estoque", "Projetos", "Consulta de Movimentação", "Inventário"]
escolha = st.sidebar.radio("Selecione uma opção:", menu)

# Tela de Inventário
if escolha == "Inventário":
    st.subheader("Inventário de Estoque")

    # Upload de planilha para atualização em lote
    arquivo = st.file_uploader("Importar Planilha de Inventário", type=["csv", "xlsx"])
    if arquivo:
        df = pd.read_excel(arquivo) if "xlsx" in arquivo.name else pd.read_csv(arquivo)

        if {"codigo", "descricao", "quantidade"}.issubset(df.columns):
            for _, row in df.iterrows():
                c.execute("SELECT COALESCE(SUM(quantidade), 0) FROM movimentacoes WHERE codigo = ?", (row["codigo"],))
                saldo_atual = c.fetchone()[0]

                nova_quantidade = row["quantidade"]
                ajuste = nova_quantidade - saldo_atual

                if ajuste != 0:
                    # Criando movimentação de ajuste
                    c.execute("""
                        INSERT INTO movimentacoes (codigo, descricao, quantidade, tipo, projeto, equipe) 
                        VALUES (?, ?, ?, 'ajuste_inventario', NULL, NULL)
                    """, (row["codigo"], row["descricao"], ajuste))
                    conn.commit()

            st.success("Inventário atualizado com sucesso!")
        else:
            st.error("A planilha deve conter as colunas: 'codigo', 'descricao' e 'quantidade'.")

    st.write("---")

    # Atualização Manual do Estoque
    st.subheader("Atualizar Estoque Manualmente")

    # Buscar materiais cadastrados
    c.execute("SELECT codigo, descricao FROM materiais")
    materiais = {str(m[0]): (m[0], m[1]) for m in c.fetchall()}

    if materiais:
        material_selecionado = st.selectbox("Selecione um Material", [""] + list(materiais.keys()))

        if material_selecionado:
            codigo, descricao = materiais[material_selecionado]
            st.text_input("Descrição", descricao, disabled=True)  # Campo bloqueado, apenas exibição

            # Buscar saldo atual
            c.execute("SELECT COALESCE(SUM(quantidade), 0) FROM movimentacoes WHERE codigo = ?", (codigo,))
            saldo_atual = c.fetchone()[0]

            # Inserir nova quantidade
            nova_quantidade = st.number_input("Nova Quantidade", min_value=0.0, step=1.0, value=float(saldo_atual or 0.0))

            if st.button("Atualizar Estoque"):
                ajuste = nova_quantidade - saldo_atual

                if ajuste != 0:
                    # Criando movimentação de ajuste
                    c.execute("""
                        INSERT INTO movimentacoes (codigo, descricao, quantidade, tipo, projeto, equipe) 
                        VALUES (?, ?, ?, 'ajuste_inventario', NULL, NULL)
                    """, (codigo, descricao, ajuste))
                    conn.commit()
                    st.success("Estoque atualizado com sucesso!")
                else:
                    st.info("O saldo já está correto, nenhuma alteração foi feita.")
    else:
        st.warning("Nenhum material cadastrado.")

# Tela de Estorno de Material
if escolha == "Estorno de Material":
    st.subheader("Estorno de Material")

    # Buscar projetos cadastrados
    c.execute("SELECT DISTINCT projeto FROM movimentacoes WHERE projeto IS NOT NULL")
    projetos = [projeto[0] for projeto in c.fetchall() if projeto[0]]
    projeto = st.selectbox("Projeto", projetos) if projetos else st.warning("Nenhum projeto cadastrado.")

    equipe = st.text_input("Código da Equipe")

    # Buscar materiais cadastrados
    c.execute("SELECT codigo, descricao FROM materiais")
    materiais = {f"{m[0]} - {m[1]}": m[0] for m in c.fetchall()}

    if materiais:
        material_selecionado = st.selectbox("Material", list(materiais.keys()))
        codigo = materiais[material_selecionado]
        quantidade = st.number_input("Quantidade", min_value=0, step=1)

        if st.button("Registrar Estorno"):
            if not projeto:
                st.error("O campo 'Projeto' é obrigatório!")
            elif not equipe.strip():
                st.error("O campo 'Código da Equipe' é obrigatório!")
            elif not codigo:
                st.error("Selecione um material!")
            elif quantidade <= 0:
                st.error("A quantidade deve ser maior que zero!")
            else:
                descricao = material_selecionado.split(" - ")[1]
                c.execute("""
                    INSERT INTO movimentacoes (codigo, descricao, quantidade, tipo, projeto, equipe) 
                    VALUES (?, ?, ?, 'estorno', ?, ?)
                """, (codigo, descricao, quantidade, projeto, equipe))
                conn.commit()
                st.success("Estorno registrado com sucesso!")
    else:
        st.warning("Nenhum material cadastrado.")

# Tela de Projetos com Cards
if escolha == "Projetos":
    st.subheader("Projetos e Equipes")
    c.execute("SELECT DISTINCT projeto FROM movimentacoes WHERE projeto IS NOT NULL")
    projetos = c.fetchall()

    for projeto in projetos:
        with st.expander(f"Projeto: {projeto[0]}"):
            c.execute("SELECT DISTINCT equipe FROM movimentacoes WHERE projeto = ?", (projeto[0],))
            equipes = c.fetchall()
            st.write("**Equipes:**", ", ".join([equipe[0] for equipe in equipes if equipe[0]]))

            st.write("**Movimentações no Projeto**")
            c.execute("""
                SELECT codigo, 
                       MAX(descricao) AS descricao, 
                       SUM(CASE WHEN tipo = 'saída' THEN quantidade ELSE 0 END) AS saidas,
                       SUM(CASE WHEN tipo = 'baixa_eqtl' THEN quantidade ELSE 0 END) AS baixas_eqtl,
                       SUM(CASE WHEN tipo = 'devolução' THEN quantidade ELSE 0 END) AS devolucoes,
                       SUM(CASE WHEN tipo = 'estorno' THEN quantidade ELSE 0 END) AS estornos
                FROM movimentacoes WHERE projeto = ?
                GROUP BY codigo
            """, (projeto[0],))
            dados_projeto = c.fetchall()
            df_projeto = pd.DataFrame(dados_projeto,
                                      columns=["Código", "Descrição", "Saídas", "Baixas EQTL", "Devoluções", "Estornos"])
            df_projeto["Saldo Atual"] = df_projeto["Saídas"] - df_projeto["Devoluções"]
            df_projeto["Status"] = df_projeto.apply(lambda row: "Baixado" if (row["Saídas"] == row["Baixas EQTL"]) and (row["Devoluções"] == row["Estornos"]) else "Pendente", axis=1)
            st.dataframe(df_projeto)

            # Botão para exportar XLSX
            xlsx_filename = f"projeto_{projeto[0]}.xlsx"
            with pd.ExcelWriter(xlsx_filename, engine='xlsxwriter') as writer:
                df_projeto.to_excel(writer, index=False, sheet_name='Movimentacoes')
                writer.close()

            with open(xlsx_filename, "rb") as file:
                st.download_button("Baixar XLSX", file, xlsx_filename,
                                   "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# Tela de Cadastro de Materiais
if escolha == "Cadastro de Materiais":
    st.subheader("Cadastro de Materiais")
    arquivo = st.file_uploader("Importar Planilha", type=["csv", "xlsx"])
    if arquivo:
        df = pd.read_excel(arquivo) if "xlsx" in arquivo.name else pd.read_csv(arquivo)
        for _, row in df.iterrows():
            c.execute("INSERT OR IGNORE INTO materiais (codigo, descricao, unidade) VALUES (?, ?, ?)",
                      (row["codigo"], row["descricao"], row["unidade"]))
        conn.commit()
        st.success("Materiais importados com sucesso!")

    codigo = st.text_input("Código do Material")
    descricao = st.text_input("Descrição")
    unidade = st.selectbox("Unidade de Medida", ["UN", "KG", "KIT", "M"])
    if st.button("Adicionar Material"):
        c.execute("INSERT OR IGNORE INTO materiais (codigo, descricao, unidade) VALUES (?, ?, ?)",
                  (codigo, descricao, unidade))
        conn.commit()
        st.success("Material cadastrado com sucesso!")

# Tela de Devolução de Material
if escolha == "Devolução de Material":
    st.subheader("Devolução de Material")

    # Buscar os projetos onde houve saída de material
    c.execute("SELECT DISTINCT projeto FROM movimentacoes WHERE tipo = 'saída' AND projeto IS NOT NULL")
    projetos = [projeto[0] for projeto in c.fetchall() if projeto[0]]

    if projetos:
        projeto = st.selectbox("Projeto", projetos)

        # Buscar materiais que tiveram saída para esse projeto
        c.execute("SELECT DISTINCT codigo, descricao FROM movimentacoes WHERE projeto = ? AND tipo = 'saída'",
                  (projeto,))
        materiais_saida = {f"{m[0]} - {m[1]}": m[0] for m in c.fetchall()}

        if materiais_saida:
            material_selecionado = st.selectbox("Material", list(materiais_saida.keys()))
            codigo = materiais_saida[material_selecionado]
            quantidade = st.number_input("Quantidade", min_value=0, step=1)

            if st.button("Registrar Devolução"):
                c.execute(
                    "INSERT INTO movimentacoes (codigo, descricao, quantidade, tipo, projeto) VALUES (?, (SELECT descricao FROM materiais WHERE codigo = ?), ?, 'devolução', ?)",
                    (codigo, codigo, quantidade, projeto))
                conn.commit()
                st.success("Devolução registrada com sucesso!")
        else:
            st.warning("Nenhum material foi retirado para esse projeto.")
    else:
        st.warning("Nenhum projeto com saída de material registrado.")

# Tela de Entrada de Material
elif escolha == "Entrada de Material":
    st.subheader("Entrada de Material")
    arquivo = st.file_uploader("Importar Planilha de Entradas", type=["csv", "xlsx"])
    if arquivo:
        df = pd.read_excel(arquivo) if "xlsx" in arquivo.name else pd.read_csv(arquivo)
        for _, row in df.iterrows():
            c.execute("INSERT INTO movimentacoes (codigo, descricao, quantidade, tipo) VALUES (?, ?, ?, 'entrada')",
                      (row["codigo"], row["descricao"], row["quantidade"]))
        conn.commit()
        st.success("Entradas registradas com sucesso!")

    codigo = st.number_input("Código do Material", min_value=1, step=1)
    if st.button("Buscar Material"):
        c.execute("SELECT descricao, unidade FROM materiais WHERE codigo = ?", (codigo,))
        material = c.fetchone()
        if material:
            descricao, unidade = material
            quantidade = st.number_input("Quantidade")
            if st.button("Registrar Entrada"):
                c.execute("INSERT INTO movimentacoes (codigo, descricao, quantidade, tipo) VALUES (?, ?, ?, 'entrada')",
                          (codigo, descricao, quantidade))
                conn.commit()
                st.success("Entrada registrada com sucesso!")
        else:
            st.error("Código não encontrado!")

# Tela de Saída de Material
if escolha == "Saída de Material":
    st.subheader("Saída de Material")

    # Upload de planilha para registrar saídas em lote
    arquivo = st.file_uploader("Importar Planilha de Saída", type=["csv", "xlsx"])
    if arquivo:
        df = pd.read_excel(arquivo) if "xlsx" in arquivo.name else pd.read_csv(arquivo)
        for _, row in df.iterrows():
            c.execute("SELECT descricao FROM materiais WHERE codigo = ?", (row["codigo"],))
            material = c.fetchone()
            if material:
                descricao = material[0]
                c.execute("""
                    INSERT INTO movimentacoes (codigo, descricao, quantidade, tipo, projeto, equipe) 
                    VALUES (?, ?, ?, 'saída', ?, ?)
                """, (row["codigo"], descricao, row["quantidade"], row["projeto"], row["equipe"]))
        conn.commit()
        st.success("Saídas registradas com sucesso!")

    projeto = st.text_input("Projeto")
    equipe = st.text_input("Código da Equipe")

    # Buscar materiais cadastrados
    c.execute("SELECT codigo, descricao FROM materiais")
    materiais = {f"{m[0]} - {m[1]}": m[0] for m in c.fetchall()}

    if materiais:
        material_selecionado = st.selectbox("Material", list(materiais.keys()))
        codigo = materiais[material_selecionado]
        quantidade = st.number_input("Quantidade", min_value=0, step=1)

        if st.button("Registrar Saída"):
            if not projeto.strip():
                st.error("O campo 'Projeto' é obrigatório!")
            elif not equipe.strip():
                st.error("O campo 'Código da Equipe' é obrigatório!")
            elif not codigo:
                st.error("Selecione um material!")
            elif quantidade <= 0:
                st.error("A quantidade deve ser maior que zero!")
            else:
                descricao = material_selecionado.split(" - ")[1]
                c.execute("""
                    INSERT INTO movimentacoes (codigo, descricao, quantidade, tipo, projeto, equipe) 
                    VALUES (?, ?, ?, 'saída', ?, ?)
                """, (codigo, descricao, quantidade, projeto, equipe))
                conn.commit()
                st.success("Saída registrada com sucesso!")
    else:
        st.warning("Nenhum material cadastrado.")

# Tela de Baixa EQTL
if escolha == "Baixa EQTL":
    st.subheader("Baixa EQTL")

    # Buscar materiais cadastrados
    c.execute("SELECT codigo, descricao FROM materiais")
    materiais = c.fetchall()
    material_dict = {str(m[0]): f"{m[0]} - {m[1]}" for m in materiais}  # Formato "Código - Descrição"

    # Importação via planilha
    arquivo = st.file_uploader("Importar Planilha de Baixa EQTL", type=["csv", "xlsx"])
    if arquivo:
        df = pd.read_excel(arquivo) if "xlsx" in arquivo.name else pd.read_csv(arquivo)

        for _, row in df.iterrows():
            c.execute("SELECT descricao FROM materiais WHERE codigo = ?", (row["codigo"],))
            descricao = c.fetchone()

            if descricao:
                descricao = descricao[0]  # Pegando o valor real dentro da tupla retornada pelo fetchone
                c.execute("""
                    INSERT INTO movimentacoes (codigo, descricao, quantidade, tipo, projeto, equipe) 
                    VALUES (?, ?, ?, 'baixa_eqtl', ?, ?)
                """, (row["codigo"], descricao, row["quantidade"], row["projeto"], row["equipe"]))
            else:
                st.warning(f"Código {row['codigo']} não encontrado no banco de dados.")

        conn.commit()
        st.success("Baixas EQTL registradas com sucesso!")

    projeto = st.text_input("Projeto")
    equipe = st.text_input("Código da Equipe")

    # Campo de busca do material
    codigo = st.selectbox("Código do Material", options=list(material_dict.keys()), format_func=lambda x: material_dict[x])

    quantidade = st.number_input("Quantidade", min_value=0.0, step=0.1)  # Convertendo tudo para float

    if st.button("Registrar Baixa EQTL"):
        if not projeto.strip():
            st.error("O campo 'Projeto' é obrigatório!")
        elif not equipe.strip():
            st.error("O campo 'Código da Equipe' é obrigatório!")
        elif not codigo:
            st.error("Selecione um material!")
        elif quantidade <= 0:
            st.error("A quantidade deve ser maior que zero!")
        else:
            descricao = material_dict.get(codigo, "")
            c.execute("""
                INSERT INTO movimentacoes (codigo, descricao, quantidade, tipo, projeto, equipe) 
                VALUES (?, ?, ?, 'baixa_eqtl', ?, ?)
            """, (codigo, descricao, quantidade, projeto, equipe))
            conn.commit()
            st.success("Baixa EQTL registrada com sucesso!")


# Tela de Visão Geral do Estoque
if escolha == "Visão Geral do Estoque":
    st.subheader("Visão Geral do Estoque")

    # Filtro opcional de materiais
    c.execute("SELECT codigo, descricao FROM materiais")
    materiais = {f"{m[0]} - {m[1]}": m[0] for m in c.fetchall()}
    material_selecionado = st.selectbox("Selecione um Material (Opcional)", ["Todos"] + list(materiais.keys()))
    codigo_material = materiais.get(material_selecionado)

    # Query base
    query = """
        SELECT m.codigo, 
               m.descricao, 
               COALESCE(SUM(CASE WHEN mov.tipo = 'entrada' THEN mov.quantidade ELSE 0 END), 0) AS entradas,
               COALESCE(SUM(CASE WHEN mov.tipo = 'saída' THEN mov.quantidade ELSE 0 END), 0) AS saidas,
               COALESCE(SUM(CASE WHEN mov.tipo = 'baixa_eqtl' THEN mov.quantidade ELSE 0 END), 0) AS baixas_eqtl,
               COALESCE(SUM(CASE WHEN mov.tipo = 'devolução' THEN mov.quantidade ELSE 0 END), 0) AS devolucoes,
               COALESCE(SUM(CASE WHEN mov.tipo = 'ajuste_inventario' THEN mov.quantidade ELSE 0 END), 0) AS ajustes
        FROM materiais m
        LEFT JOIN movimentacoes mov ON m.codigo = mov.codigo
    """

    params = []
    if material_selecionado != "Todos":
        query += " WHERE m.codigo = ?"
        params.append(codigo_material)

    query += " GROUP BY m.codigo, m.descricao"

    # Executar a query e carregar os dados
    c.execute(query, params)
    dados_estoque = c.fetchall()

    # Criar dataframe
    df_estoque = pd.DataFrame(dados_estoque,
                              columns=["Código", "Descrição", "Entradas", "Saídas", "Baixas EQTL", "Devoluções",
                                       "Ajustes"])

    # Novo saldo atualizado (agora incluindo os ajustes do inventário)
    df_estoque["Saldo Atual"] = df_estoque["Entradas"] - df_estoque["Saídas"] + df_estoque["Devoluções"] + df_estoque[
        "Ajustes"]

    # Exibir tabela na interface
    st.dataframe(df_estoque, use_container_width=True, height=400)

    # Botão para exportar XLSX
    xlsx_filename = "estoque.xlsx"
    with pd.ExcelWriter(xlsx_filename, engine='xlsxwriter') as writer:
        df_estoque.to_excel(writer, index=False, sheet_name='Estoque')
        writer.close()

    with open(xlsx_filename, "rb") as file:
        st.download_button("Baixar XLSX", file, xlsx_filename,
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# Tela de Consulta de Movimentação
if escolha == "Consulta de Movimentação":
    st.subheader("Consulta de Movimentação de Materiais")

    # Buscar materiais cadastrados
    c.execute("SELECT codigo, descricao FROM materiais")
    materiais = {f"{m[0]} - {m[1]}": m[0] for m in c.fetchall()}

    # Opções de filtros opcionais
    material_selecionado = st.selectbox("Selecione um Material (Opcional)", ["Todos"] + list(materiais.keys()))
    codigo_material = materiais.get(material_selecionado)

    tipo_movimentacao = st.selectbox("Tipo de Movimentação (Opcional)",
                                     ["Todos", "entrada", "saída", "devolução", "baixa_eqtl", "estorno"])
    data_inicial = st.date_input("Data Inicial (Opcional)", None)
    data_final = st.date_input("Data Final (Opcional)", None)

    if st.button("Consultar"):
        query = """
            SELECT data_movimentacao, codigo, descricao, tipo, quantidade, projeto, equipe 
            FROM movimentacoes WHERE 1=1
        """
        params = []

        if material_selecionado != "Todos":
            query += " AND codigo = ?"
            params.append(codigo_material)

        if tipo_movimentacao != "Todos":
            query += " AND tipo = ?"
            params.append(tipo_movimentacao)

        if data_inicial:
            query += " AND DATE(data_movimentacao) >= DATE(?)"
            params.append(data_inicial)

        if data_final:
            query += " AND DATE(data_movimentacao) <= DATE(?)"
            params.append(data_final)

        query += " ORDER BY data_movimentacao DESC"
        c.execute(query, params)
        dados_movimentacao = c.fetchall()

        if dados_movimentacao:
            df_movimentacao = pd.DataFrame(dados_movimentacao,
                                           columns=["Data", "Código", "Descrição", "Tipo", "Quantidade", "Projeto", "Equipe"])

            # Formatando data para o formato brasileiro
            df_movimentacao["Data"] = pd.to_datetime(df_movimentacao["Data"]).dt.strftime("%d/%m/%Y %H:%M:%S")

            st.dataframe(df_movimentacao)

            # Botão para exportar XLSX
            xlsx_filename = "movimentacoes.xlsx"
            with pd.ExcelWriter(xlsx_filename, engine='xlsxwriter') as writer:
                df_movimentacao.to_excel(writer, index=False, sheet_name='Movimentacoes')
                writer.close()

            with open(xlsx_filename, "rb") as file:
                st.download_button("Baixar XLSX", file, xlsx_filename,
                                   "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        else:
            st.warning("Nenhuma movimentação encontrada para os filtros selecionados.")

