import streamlit as st
import pandas as pd
from datetime import timedelta
import io

# Função para pré-processar o arquivo de notificações (Excel)
def preprocessar_notificacoes(df_notificacoes):
    st.write("Pré-processando notificações...")
    df_notificacoes = df_notificacoes.dropna(how='all') # Remove linhas completamente vazias

    # Renomear e tratar a coluna 'To' para ID do Cliente
    if 'To' in df_notificacoes.columns:
        # Converte para string, remove prefixo '55' (se existir) e '.0'
        df_notificacoes['ID_Cliente'] = df_notificacoes['To'].astype(str).str.replace(r'^\d{2}', '', regex=True).str.replace(r'\.0$', '', regex=True).str.strip()
    else:
        st.error("Coluna 'To' não encontrada no arquivo de notificações. Verifique o cabeçalho.")
        return pd.DataFrame()

    # Renomear e tratar a coluna 'Done At' para Data de Envio da Notificação
    if 'Done At' in df_notificacoes.columns:
        # Tenta múltiplos formatos de data para robustez
        df_notificacoes['Data_Envio_Notificacao'] = pd.to_datetime(df_notificacoes['Done At'], errors='coerce', dayfirst=True)
    else:
        st.error("Coluna 'Done At' não encontrada no arquivo de notificações. Verifique o cabeçalho.")
        return pd.DataFrame()

    # Remover linhas onde a data de envio não pôde ser convertida
    df_notificacoes = df_notificacoes.dropna(subset=['Data_Envio_Notificacao'])

    # Selecionar e renomear colunas relevantes
    df_notificacoes_processado = df_notificacoes[['ID_Cliente', 'Data_Envio_Notificacao']].copy()

    # Remover duplicatas de notificações para o mesmo cliente na mesma data
    df_notificacoes_processado = df_notificacoes_processado.drop_duplicates(subset=['ID_Cliente', 'Data_Envio_Notificacao'])

    st.success(f"Notificações pré-processadas: {len(df_notificacoes_processado)} registros válidos.")
    return df_notificacoes_processado

# Função para pré-processar o arquivo de pagamentos (CSV ou Excel)
def preprocessar_pagamentos(df_pagamentos):
    st.write("Pré-processando pagamentos...")
    df_pagamentos = df_pagamentos.dropna(how='all') # Remove linhas completamente vazias

    # Renomear e tratar a coluna 'N° Ligação' para ID do Cliente
    if 'N° Ligação' in df_pagamentos.columns:
        df_pagamentos['ID_Cliente'] = df_pagamentos['N° Ligação'].astype(str).str.strip()
    else:
        st.error("Coluna 'N° Ligação' não encontrada no arquivo de pagamentos. Verifique o cabeçalho.")
        return pd.DataFrame()

    # Renomear e tratar a coluna 'Data Pagto.' para Data de Pagamento
    if 'Data Pagto.' in df_pagamentos.columns:
        # Tenta múltiplos formatos de data para robustez
        df_pagamentos['Data_Pagamento'] = pd.to_datetime(df_pagamentos['Data Pagto.'], errors='coerce', dayfirst=True)
    else:
        st.error("Coluna 'Data Pagto.' não encontrada no arquivo de pagamentos. Verifique o cabeçalho.")
        return pd.DataFrame()

    # Renomear e tratar a coluna 'Val. Autenticado' para Valor Autenticado
    if 'Val. Autenticado' in df_pagamentos.columns:
        # Converte para string, substitui '.' por '' (milhar) e ',' por '.' (decimal)
        df_pagamentos['Valor_Autenticado'] = df_pagamentos['Val. Autenticado'].astype(str).str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
        df_pagamentos['Valor_Autenticado'] = pd.to_numeric(df_pagamentos['Valor_Autenticado'], errors='coerce')
    else:
        st.error("Coluna 'Val. Autenticado' não encontrada no arquivo de pagamentos. Verifique o cabeçalho.")
        return pd.DataFrame()

    # Remover linhas onde a data de pagamento ou o valor não puderam ser convertidos
    df_pagamentos = df_pagamentos.dropna(subset=['Data_Pagamento', 'Valor_Autenticado'])

    # Filtrar pagamentos com valor maior que zero
    df_pagamentos = df_pagamentos[df_pagamentos['Valor_Autenticado'] > 0]

    # Selecionar e renomear colunas relevantes
    df_pagamentos_processado = df_pagamentos[['ID_Cliente', 'Data_Pagamento', 'Valor_Autenticado']].copy()

    st.success(f"Pagamentos pré-processados: {len(df_pagamentos_processado)} registros válidos.")
    return df_pagamentos_processado

# Função para analisar a eficiência da campanha
def analisar_eficiencia_campanha(df_notificacoes, df_pagamentos, janela_dias):
    st.write(f"Analisando eficiência da campanha com janela de {janela_dias} dias...")

    if df_notificacoes.empty or df_pagamentos.empty:
        st.warning("Um dos DataFrames está vazio. Não é possível realizar a análise.")
        return pd.DataFrame(), pd.DataFrame()

    # Criar a data limite para o pagamento
    df_notificacoes['Data_Limite_Pagamento'] = df_notificacoes['Data_Envio_Notificacao'] + timedelta(days=janela_dias)

    # Realizar o merge dos DataFrames
    # Usamos um merge de tipo 'left' para manter todas as notificações
    df_cruzado = pd.merge(df_notificacoes, df_pagamentos, on='ID_Cliente', how='left')

    # Identificar pagamentos dentro da janela
    df_cruzado['Pagamento_Dentro_Janela'] = (
        (df_cruzado['Data_Pagamento'] >= df_cruzado['Data_Envio_Notificacao']) &
        (df_cruzado['Data_Pagamento'] <= df_cruzado['Data_Limite_Pagamento']) &
        (df_cruzado['Valor_Autenticado'].notna()) &
        (df_cruzado['Valor_Autenticado'] > 0)
    )

    # Criar um DataFrame de resultados da campanha
    df_resultados_campanha = df_cruzado[df_cruzado['Pagamento_Dentro_Janela']].copy()

    # Agrupar por ID_Cliente e Data_Envio_Notificacao para somar os valores e contar os pagamentos
    df_resumo_por_notificacao = df_resultados_campanha.groupby(['ID_Cliente', 'Data_Envio_Notificacao']).agg(
        Total_Pago_Campanha=('Valor_Autenticado', 'sum'),
        Qtd_Pagamentos_Campanha=('Data_Pagamento', 'count')
    ).reset_index()

    # Contar o número de clientes únicos que tiveram pagamentos dentro da janela
    clientes_com_pagamento = df_resumo_por_notificacao['ID_Cliente'].nunique()
    total_clientes_notificados = df_notificacoes['ID_Cliente'].nunique()

    st.success("Análise de campanha concluída.")
    return df_cruzado, df_resumo_por_notificacao, clientes_com_pagamento, total_clientes_notificados

# Configuração da interface Streamlit
st.set_page_config(layout="wide", page_title="Análise de Eficiência de Campanha")

st.title("📊 Análise de Eficiência de Campanha de Notificações")

st.sidebar.header("Upload de Arquivos")

# Upload do arquivo de notificações (Excel)
uploaded_file_notificacoes = st.sidebar.file_uploader(
    "Selecione o arquivo de Notificações (Excel)", type=["xlsx"], key="notificacoes_uploader"
)

# Upload do arquivo de pagamentos (CSV ou Excel)
uploaded_file_pagamentos = st.sidebar.file_uploader(
    "Selecione o arquivo de Pagamentos (CSV ou Excel)", type=["csv", "xlsx"], key="pagamentos_uploader"
)

# Slider para a janela de dias
janela_dias = st.sidebar.slider(
    "Janela de dias para considerar o pagamento após a notificação:",
    min_value=1, max_value=30, value=7
)

df_notificacoes_processado = pd.DataFrame()
df_pagamentos_processado = pd.DataFrame()

if uploaded_file_notificacoes is not None:
    try:
        df_notificacoes_raw = pd.read_excel(uploaded_file_notificacoes)
        df_notificacoes_processado = preprocessar_notificacoes(df_notificacoes_raw)
        if not df_notificacoes_processado.empty:
            st.sidebar.success("Arquivo de Notificações carregado e pré-processado com sucesso!")
            st.sidebar.dataframe(df_notificacoes_processado.head())
    except Exception as e:
        st.sidebar.error(f"Erro ao carregar ou pré-processar o arquivo de notificações: {e}")

if uploaded_file_pagamentos is not None:
    try:
        if uploaded_file_pagamentos.name.endswith('.csv'):
            # Tenta ler CSV com delimitador ';' e depois ','
            try:
                df_pagamentos_raw = pd.read_csv(uploaded_file_pagamentos, sep=';', encoding='latin1')
            except Exception:
                uploaded_file_pagamentos.seek(0) # Reset file pointer
                df_pagamentos_raw = pd.read_csv(uploaded_file_pagamentos, sep=',', encoding='latin1')
        elif uploaded_file_pagamentos.name.endswith('.xlsx'):
            df_pagamentos_raw = pd.read_excel(uploaded_file_pagamentos)
        else:
            st.sidebar.error("Formato de arquivo de pagamentos não suportado. Use .csv ou .xlsx.")
            df_pagamentos_raw = pd.DataFrame() # Define como DataFrame vazio para evitar erros

        if not df_pagamentos_raw.empty:
            df_pagamentos_processado = preprocessar_pagamentos(df_pagamentos_raw)
            if not df_pagamentos_processado.empty:
                st.sidebar.success("Arquivo de Pagamentos carregado e pré-processado com sucesso!")
                st.sidebar.dataframe(df_pagamentos_processado.head())
    except Exception as e:
        st.sidebar.error(f"Erro ao carregar ou pré-processar o arquivo de pagamentos: {e}")

st.sidebar.markdown("---")
if st.sidebar.button("Executar Análise"):
    if not df_notificacoes_processado.empty and not df_pagamentos_processado.empty:
        df_cruzado, df_resumo_por_notificacao, clientes_com_pagamento, total_clientes_notificados = \
            analisar_eficiencia_campanha(df_notificacoes_processado, df_pagamentos_processado, janela_dias)

        if not df_resumo_por_notificacao.empty:
            st.subheader("Resultados da Campanha")
            st.write(f"Total de clientes notificados: **{total_clientes_notificados}**")
            st.write(f"Clientes com pagamentos dentro da janela de {janela_dias} dias: **{clientes_com_pagamento}**")

            taxa_eficiencia = (clientes_com_pagamento / total_clientes_notificados) * 100 if total_clientes_notificados > 0 else 0
            st.write(f"Taxa de eficiência da campanha: **{taxa_eficiencia:.2f}%**")

            valor_total_arrecadado = df_resumo_por_notificacao['Total_Pago_Campanha'].sum()
            st.write(f"Valor total arrecadado na campanha (dentro da janela): **R$ {valor_total_arrecadado:,.2f}**")

            st.subheader("Detalhes dos Pagamentos da Campanha")
            st.dataframe(df_resumo_por_notificacao)

            st.subheader("Dados Cruzados Completos (Amostra)")
            st.dataframe(df_cruzado.head())

            csv_output = df_resumo_por_notificacao.to_csv(index=False, decimal=',', sep=';', encoding='latin1')
            st.download_button(
                label="Baixar Resultados da Campanha (CSV)",
                data=csv_output,
                file_name="resultados_campanha.csv",
                mime="text/csv",
            )
        else:
            st.info("Não há resultados para baixar, pois nenhum pagamento foi atribuído à campanha.")
    else:
        st.warning("Certifique-se de que ambos os arquivos foram carregados e pré-processados corretamente antes de executar a análise.")
