import streamlit as st
import pandas as pd
from datetime import timedelta

def preprocessar_notificacoes(df_notificacoes):
    """
    Pré-processa o DataFrame de notificações.
    Usa 'matricula' como ID do cliente e 'Done At' como data de envio.
    """
    st.write("Pré-processando notificações...")
    df_notificacoes = df_notificacoes.dropna(how='all') # Remove linhas completamente vazias

    # Coluna 'matricula' para ID do Cliente
    if 'matricula' in df_notificacoes.columns:
        df_notificacoes['ID_Cliente'] = df_notificacoes['matricula'].astype(str).str.strip()
    else:
        st.error("Coluna 'matricula' não encontrada no arquivo de notificações. Verifique o cabeçalho.")
        return pd.DataFrame()

    # Coluna 'Done At' para Data de Envio da Notificação
    if 'Done At' in df_notificacoes.columns:
        # Tenta converter a data no formato '%d/%m/%Y %H:%M:%S'
        df_notificacoes['Data_Envio_Notificacao'] = pd.to_datetime(df_notificacoes['Done At'], format='%d/%m/%Y %H:%M:%S', errors='coerce')
        # Se houver falhas, tenta outro formato comum para Excel
        if df_notificacoes['Data_Envio_Notificacao'].isnull().any():
            df_notificacoes['Data_Envio_Notificacao'] = pd.to_datetime(df_notificacoes['Done At'], errors='coerce')
    else:
        st.error("Coluna 'Done At' não encontrada no arquivo de notificações. Verifique o cabeçalho.")
        return pd.DataFrame()

    # Filtra apenas as colunas necessárias e remove linhas com datas inválidas ou IDs vazios
    df_notificacoes = df_notificacoes[['ID_Cliente', 'Data_Envio_Notificacao']].dropna(subset=['ID_Cliente', 'Data_Envio_Notificacao'])

    # Remove duplicatas de notificações para o mesmo cliente na mesma data de envio
    df_notificacoes = df_notificacoes.drop_duplicates(subset=['ID_Cliente', 'Data_Envio_Notificacao'])

    st.success(f"Notificações pré-processadas. Total de registros válidos: {len(df_notificacoes)}")
    return df_notificacoes

def preprocessar_pagamentos(df_pagamentos):
    """
    Pré-processa o DataFrame de pagamentos.
    Usa 'N° Ligação' como ID do cliente, 'Data Pagto.' como data de pagamento e 'Val. Autenticado' como valor.
    """
    st.write("Pré-processando pagamentos...")

    # Remove linhas completamente vazias
    df_pagamentos = df_pagamentos.dropna(how='all')

    # Coluna 'N° Ligação' para ID do Cliente
    if 'N° Ligação' in df_pagamentos.columns:
        df_pagamentos['ID_Cliente'] = df_pagamentos['N° Ligação'].astype(str).str.strip()
    else:
        st.error("Coluna 'N° Ligação' não encontrada no arquivo de pagamentos. Verifique o cabeçalho.")
        return pd.DataFrame()

    # Coluna 'Data Pagto.' para Data do Pagamento
    if 'Data Pagto.' in df_pagamentos.columns:
        # Tenta converter a data no formato '%d/%m/%Y'
        df_pagamentos['Data_Pagamento'] = pd.to_datetime(df_pagamentos['Data Pagto.'], format='%d/%m/%Y', errors='coerce')
        # Se houver falhas, tenta outro formato comum
        if df_pagamentos['Data_Pagamento'].isnull().any():
            df_pagamentos['Data_Pagamento'] = pd.to_datetime(df_pagamentos['Data Pagto.'], errors='coerce')
    else:
        st.error("Coluna 'Data Pagto.' não encontrada no arquivo de pagamentos. Verifique o cabeçalho.")
        return pd.DataFrame()

    # Coluna 'Val. Autenticado' para Valor Autenticado
    if 'Val. Autenticado' in df_pagamentos.columns:
        # Limpa e converte a coluna 'Val. Autenticado' para numérico
        # Substitui vírgula por ponto para decimal e remove pontos de milhar
        df_pagamentos['Valor_Autenticado'] = df_pagamentos['Val. Autenticado'].astype(str).str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
        df_pagamentos['Valor_Autenticado'] = pd.to_numeric(df_pagamentos['Valor_Autenticado'], errors='coerce')
    else:
        st.error("Coluna 'Val. Autenticado' não encontrada no arquivo de pagamentos. Verifique o cabeçalho.")
        return pd.DataFrame()

    # Filtra apenas as colunas necessárias e remove linhas com datas ou valores inválidos
    df_pagamentos = df_pagamentos[['ID_Cliente', 'Data_Pagamento', 'Valor_Autenticado']].dropna(subset=['ID_Cliente', 'Data_Pagamento', 'Valor_Autenticado'])

    # Filtra pagamentos com valor autenticado maior que zero
    df_pagamentos = df_pagamentos[df_pagamentos['Valor_Autenticado'] > 0]

    st.success(f"Pagamentos pré-processados. Total de registros válidos: {len(df_pagamentos)}")
    return df_pagamentos

def analisar_eficiencia_campanha(df_notificacoes, df_pagamentos, janela_dias):
    """
    Cruza as notificações com os pagamentos e calcula a eficiência da campanha.
    Considera todos os pagamentos dentro da janela e soma seus valores.
    """
    st.write("Iniciando análise de eficiência da campanha...")

    # Garante que os IDs de cliente sejam do mesmo tipo para o merge
    df_notificacoes['ID_Cliente'] = df_notificacoes['ID_Cliente'].astype(str)
    df_pagamentos['ID_Cliente'] = df_pagamentos['ID_Cliente'].astype(str)

    # Realiza um merge para combinar notificações com pagamentos
    # Usamos um outer merge para manter todas as notificações e todos os pagamentos
    df_campanha = pd.merge(df_notificacoes, df_pagamentos, on='ID_Cliente', how='left')

    # Calcula a data limite para o pagamento
    df_campanha['Data_Limite_Pagamento'] = df_campanha['Data_Envio_Notificacao'] + timedelta(days=janela_dias)

    # Identifica pagamentos dentro da janela
    df_campanha['Pagamento_Dentro_Janela'] = (
        (df_campanha['Data_Pagamento'] >= df_campanha['Data_Envio_Notificacao']) &
        (df_campanha['Data_Pagamento'] <= df_campanha['Data_Limite_Pagamento']) &
        (df_campanha['Valor_Autenticado'].notna()) &
        (df_campanha['Valor_Autenticado'] > 0)
    )

    # Agrupa por ID_Cliente e Data_Envio_Notificacao para somar os valores de pagamentos dentro da janela
    # e contar se houve pelo menos um pagamento válido
    resultados_agrupados = df_campanha.groupby(['ID_Cliente', 'Data_Envio_Notificacao']).agg(
        Total_Valor_Pago_Campanha=('Valor_Autenticado', lambda x: x[df_campanha.loc[x.index, 'Pagamento_Dentro_Janela']].sum()),
        Pagou_Na_Campanha=('Pagamento_Dentro_Janela', 'any') # True se qualquer pagamento foi dentro da janela
    ).reset_index()

    # Merge de volta com as notificações originais para incluir clientes que não pagaram
    df_final = pd.merge(df_notificacoes, resultados_agrupados, on=['ID_Cliente', 'Data_Envio_Notificacao'], how='left')

    # Preenche NaN para clientes que não tiveram pagamentos na campanha
    df_final['Total_Valor_Pago_Campanha'] = df_final['Total_Valor_Pago_Campanha'].fillna(0)
    df_final['Pagou_Na_Campanha'] = df_final['Pagou_Na_Campanha'].fillna(False)

    # Métricas da campanha
    total_clientes_notificados = len(df_notificacoes)
    clientes_que_pagaram = df_final['Pagou_Na_Campanha'].sum()
    valor_total_arrecadado = df_final['Total_Valor_Pago_Campanha'].sum()
    taxa_eficiencia = (clientes_que_pagaram / total_clientes_notificados * 100) if total_clientes_notificados > 0 else 0

    st.subheader("Resumo da Campanha")
    st.write(f"Total de clientes notificados: **{total_clientes_notificados}**")
    st.write(f"Clientes que realizaram pagamentos na janela: **{clientes_que_pagaram}**")
    st.write(f"Valor total arrecadado na campanha: **R$ {valor_total_arrecadado:,.2f}**")
    st.write(f"Taxa de eficiência da campanha: **{taxa_eficiencia:.2f}%**")

    st.subheader("Detalhes por Notificação")
    st.dataframe(df_final.head())

    return df_final

# --- Streamlit App ---
st.set_page_config(layout="wide")
st.title("Análise de Eficiência de Campanha de Notificação")

st.sidebar.header("Upload de Arquivos")
uploaded_file_notificacoes = st.sidebar.file_uploader("Escolha o arquivo Excel de Notificações", type=["xlsx"])
uploaded_file_pagamentos = st.sidebar.file_uploader("Escolha o arquivo CSV de Pagamentos", type=["csv"])

janela_dias = st.sidebar.slider(
    "Defina a janela de dias para considerar o pagamento após a notificação:",
    min_value=1,
    max_value=90,
    value=7
)

df_notificacoes = pd.DataFrame()
df_pagamentos = pd.DataFrame()

if uploaded_file_notificacoes is not None:
    try:
        df_notificacoes_raw = pd.read_excel(uploaded_file_notificacoes)
        df_notificacoes = preprocessar_notificacoes(df_notificacoes_raw)
        if not df_notificacoes.empty:
            st.sidebar.subheader("Prévia Notificações")
            st.sidebar.dataframe(df_notificacoes.head())
    except Exception as e:
        st.error(f"Erro ao ler ou pré-processar o arquivo de notificações: {e}")
        st.stop()

if uploaded_file_pagamentos is not None:
    try:
        # Tenta ler com delimitador ';' primeiro, depois ','
        try:
            df_pagamentos_raw = pd.read_csv(uploaded_file_pagamentos, sep=';', encoding='latin1')
        except Exception:
            uploaded_file_pagamentos.seek(0) # Volta o ponteiro do arquivo para o início
            df_pagamentos_raw = pd.read_csv(uploaded_file_pagamentos, sep=',', encoding='latin1')

        df_pagamentos = preprocessar_pagamentos(df_pagamentos_raw)
        if not df_pagamentos.empty:
            st.sidebar.subheader("Prévia Pagamentos")
            st.sidebar.dataframe(df_pagamentos.head())
    except Exception as e:
        st.error(f"Erro ao ler ou pré-processar o arquivo de pagamentos: {e}")
        st.stop()

if st.button("Executar Análise"):
    if not df_notificacoes.empty and not df_pagamentos.empty:
        with st.spinner("Processando dados e executando análise..."):
            df_resultado_campanha = analisar_eficiencia_campanha(df_notificacoes, df_pagamentos, janela_dias)
            st.success("Análise concluída!")

            # Opção para download do resultado
            if not df_resultado_campanha.empty:
                csv = df_resultado_campanha.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Baixar resultados da campanha (CSV)",
                    data=csv,
                    file_name="resultados_campanha.csv",
                    mime="text/csv",
                )
            else:
                st.info("Não há resultados para baixar, pois nenhum pagamento foi atribuído à campanha.")
    else:
        st.warning("Certifique-se de que ambos os arquivos foram carregados e pré-processados corretamente antes de executar a análise.")
