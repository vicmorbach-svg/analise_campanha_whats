import streamlit as st
import pandas as pd
from datetime import timedelta

# Configurações da página do Streamlit
st.set_page_config(layout="wide", page_title="Análise de Eficiência de Campanha")

st.title("📊 Análise de Eficiência de Campanha")
st.markdown("---")

# Funções de pré-processamento
@st.cache_data
def preprocessar_envios(df_envios):
    """
    Pré-processa o DataFrame de envios (notificações).
    Colunas esperadas: 'To' (telefone), 'Send At' (data de envio).
    """
    st.sidebar.info("Processando Base de Envios...")

    # Verificar se as colunas existem
    required_cols = ['To', 'Send At']
    if not all(col in df_envios.columns for col in required_cols):
        st.error(f"Base de Envios: Colunas esperadas '{required_cols}' não encontradas. Verifique o arquivo.")
        return pd.DataFrame()

    df_envios = df_envios.copy()

    # Limpar linhas com valores nulos nas colunas essenciais
    df_envios.dropna(subset=['To', 'Send At'], inplace=True)

    # Converter 'To' para string e limpar (remover '.0' e '55')
    df_envios['To'] = df_envios['To'].astype(str).str.replace(r'\.0$', '', regex=True)
    df_envios['To'] = df_envios['To'].apply(lambda x: x[2:] if x.startswith('55') and len(x) > 2 else x)
    df_envios['To'] = df_envios['To'].str.strip() # Remover espaços em branco

    # Converter 'Send At' para datetime
    df_envios['Send At'] = pd.to_datetime(df_envios['Send At'], errors='coerce', dayfirst=True)
    df_envios.dropna(subset=['Send At'], inplace=True) # Remover linhas com datas inválidas

    # Renomear colunas para padronização
    df_envios.rename(columns={'To': 'TELEFONE_ENVIO', 'Send At': 'DATA_ENVIO'}, inplace=True)

    # Remover duplicatas de envio para o mesmo telefone na mesma data (considerar apenas o primeiro envio)
    df_envios.sort_values(by='DATA_ENVIO', inplace=True)
    df_envios.drop_duplicates(subset=['TELEFONE_ENVIO', 'DATA_ENVIO'], keep='first', inplace=True)

    return df_envios[['TELEFONE_ENVIO', 'DATA_ENVIO']]

@st.cache_data
def preprocessar_pagamentos(df_pagamentos):
    """
    Pré-processa o DataFrame de pagamentos.
    Colunas esperadas: 'N° Ligação' (matrícula), 'Data Pagto.' (data pagamento), 'Val. Autenticado' (valor).
    """
    st.sidebar.info("Processando Base de Pagamentos...")

    # Verificar se as colunas existem
    required_cols = ['N° Ligação', 'Data Pagto.', 'Val. Autenticado']
    if not all(col in df_pagamentos.columns for col in required_cols):
        st.error(f"Base de Pagamentos: Colunas esperadas '{required_cols}' não encontradas. Verifique o arquivo.")
        return pd.DataFrame()

    df_pagamentos = df_pagamentos.copy()

    # Limpar linhas com valores nulos nas colunas essenciais
    df_pagamentos.dropna(subset=['N° Ligação', 'Data Pagto.', 'Val. Autenticado'], inplace=True)

    # Converter 'N° Ligação' para string e limpar (remover '.0')
    df_pagamentos['N° Ligação'] = df_pagamentos['N° Ligação'].astype(str).str.replace(r'\.0$', '', regex=True)
    df_pagamentos['N° Ligação'] = df_pagamentos['N° Ligação'].str.strip() # Remover espaços em branco

    # Converter 'Data Pagto.' para datetime
    df_pagamentos['Data Pagto.'] = pd.to_datetime(df_pagamentos['Data Pagto.'], errors='coerce', dayfirst=True)
    df_pagamentos.dropna(subset=['Data Pagto.'], inplace=True) # Remover linhas com datas inválidas

    # Tratar 'Val. Autenticado' para formato numérico brasileiro (vírgula como decimal)
    df_pagamentos['Val. Autenticado'] = df_pagamentos['Val. Autenticado'].astype(str).str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
    df_pagamentos['Val. Autenticado'] = pd.to_numeric(df_pagamentos['Val. Autenticado'], errors='coerce')
    df_pagamentos.dropna(subset=['Val. Autenticado'], inplace=True) # Remover linhas com valores inválidos
    df_pagamentos = df_pagamentos[df_pagamentos['Val. Autenticado'] > 0] # Considerar apenas pagamentos com valor > 0

    # Renomear colunas para padronização
    df_pagamentos.rename(columns={
        'N° Ligação': 'MATRICULA_PAGAMENTO',
        'Data Pagto.': 'DATA_PAGAMENTO',
        'Val. Autenticado': 'VALOR_PAGO'
    }, inplace=True)

    return df_pagamentos[['MATRICULA_PAGAMENTO', 'DATA_PAGAMENTO', 'VALOR_PAGO']]

@st.cache_data
def preprocessar_identificacao(df_identificacao):
    """
    Pré-processa o DataFrame de identificação de clientes.
    Colunas esperadas: 'TELEFONE', 'MATRICULA'.
    """
    st.sidebar.info("Processando Base de Identificação de Clientes...")

    # Verificar se as colunas existem
    required_cols = ['TELEFONE', 'MATRICULA']
    if not all(col in df_identificacao.columns for col in required_cols):
        st.error(f"Base de Identificação: Colunas esperadas '{required_cols}' não encontradas. Verifique o arquivo.")
        return pd.DataFrame()

    df_identificacao = df_identificacao.copy()

    # Limpar linhas com valores nulos nas colunas essenciais
    df_identificacao.dropna(subset=['TELEFONE', 'MATRICULA'], inplace=True)

    # Converter para string e limpar (remover '.0')
    df_identificacao['TELEFONE'] = df_identificacao['TELEFONE'].astype(str).str.replace(r'\.0$', '', regex=True)
    df_identificacao['MATRICULA'] = df_identificacao['MATRICULA'].astype(str).str.replace(r'\.0$', '', regex=True)
    df_identificacao['TELEFONE'] = df_identificacao['TELEFONE'].str.strip() # Remover espaços em branco
    df_identificacao['MATRICULA'] = df_identificacao['MATRICULA'].str.strip() # Remover espaços em branco

    # Renomear colunas para padronização
    df_identificacao.rename(columns={
        'TELEFONE': 'TELEFONE_CLIENTE',
        'MATRICULA': 'MATRICULA_CLIENTE'
    }, inplace=True)

    # Remover duplicatas, mantendo a primeira ocorrência
    df_identificacao.drop_duplicates(subset=['TELEFONE_CLIENTE', 'MATRICULA_CLIENTE'], keep='first', inplace=True)

    return df_identificacao[['TELEFONE_CLIENTE', 'MATRICULA_CLIENTE']]

@st.cache_data
def carregar_arquivo(uploaded_file):
    """Função para carregar arquivos CSV ou XLSX."""
    if uploaded_file is not None:
        file_extension = uploaded_file.name.split('.')[-1]
        try:
            if file_extension == 'csv':
                # Tentar ler com diferentes delimitadores
                try:
                    df = pd.read_csv(uploaded_file, sep=';', encoding='utf-8')
                except Exception:
                    uploaded_file.seek(0) # Resetar o ponteiro do arquivo
                    df = pd.read_csv(uploaded_file, sep=',', encoding='utf-8')
            elif file_extension in ['xlsx', 'xls']:
                df = pd.read_excel(uploaded_file)
            else:
                st.error("Formato de arquivo não suportado. Por favor, use .csv ou .xlsx.")
                return pd.DataFrame()
            return df
        except Exception as e:
            st.error(f"Erro ao carregar o arquivo: {e}. Verifique o formato e o conteúdo.")
            return pd.DataFrame()
    return pd.DataFrame()

# --- Barra Lateral para Upload de Arquivos e Parâmetros ---
st.sidebar.header("Upload de Arquivos")

uploaded_file_envios = st.sidebar.file_uploader(
    "1. Carregar Base de Envios (Notificações - .xlsx)",
    type=["xlsx"],
    key="envios_uploader"
)

uploaded_file_pagamentos = st.sidebar.file_uploader(
    "2. Carregar Base de Pagamentos (.csv ou .xlsx)",
    type=["csv", "xlsx"],
    key="pagamentos_uploader"
)

uploaded_file_identificacao = st.sidebar.file_uploader(
    "3. Carregar Base de Identificação de Clientes (.xlsx)",
    type=["xlsx"],
    key="identificacao_uploader"
)

st.sidebar.header("Parâmetros da Análise")
window_days = st.sidebar.slider(
    "Janela de dias para considerar o pagamento após a notificação:",
    min_value=1, max_value=60, value=10
)

st.sidebar.markdown("---")
run_analysis = st.sidebar.button("Executar Análise 🚀")

# --- Lógica Principal ---
if run_analysis:
    if uploaded_file_envios and uploaded_file_pagamentos and uploaded_file_identificacao:
        df_envios_raw = carregar_arquivo(uploaded_file_envios)
        df_pagamentos_raw = carregar_arquivo(uploaded_file_pagamentos)
        df_identificacao_raw = carregar_arquivo(uploaded_file_identificacao)

        if not df_envios_raw.empty and not df_pagamentos_raw.empty and not df_identificacao_raw.empty:
            df_envios = preprocessar_envios(df_envios_raw)
            df_pagamentos = preprocessar_pagamentos(df_pagamentos_raw)
            df_identificacao = preprocessar_identificacao(df_identificacao_raw)

            if df_envios.empty or df_pagamentos.empty or df_identificacao.empty:
                st.error("Um ou mais DataFrames estão vazios após o pré-processamento. Verifique as mensagens de erro acima e os arquivos.")
                st.stop()

            st.subheader("Pré-visualização dos Dados Processados")
            st.write("Base de Envios (Notificações):")
            st.dataframe(df_envios.head())
            st.write("Base de Pagamentos:")
            st.dataframe(df_pagamentos.head())
            st.write("Base de Identificação de Clientes:")
            st.dataframe(df_identificacao.head())
            st.markdown("---")

            st.subheader("Realizando Cruzamento de Dados...")

            # 1. Cruzar Envios com Identificação de Clientes (pelo telefone)
            # Isso adiciona a MATRICULA_CLIENTE à base de envios
            df_envios_com_matricula = pd.merge(
                df_envios,
                df_identificacao,
                left_on='TELEFONE_ENVIO',
                right_on='TELEFONE_CLIENTE',
                how='inner' # Apenas envios que têm um cliente correspondente na base de identificação
            )

            if df_envios_com_matricula.empty:
                st.warning("Nenhum envio pôde ser associado a uma matrícula de cliente. Verifique as colunas 'To' (envios) e 'TELEFONE' (identificação).")
                st.stop()

            # 2. Cruzar o resultado com a Base de Pagamentos (pela matrícula)
            # Isso traz os pagamentos para cada notificação que tem uma matrícula associada
            df_merged = pd.merge(
                df_envios_com_matricula,
                df_pagamentos,
                left_on='MATRICULA_CLIENTE',
                right_on='MATRICULA_PAGAMENTO',
                how='left' # Manter todas as notificações, mesmo que não haja pagamento
            )

            # Calcular a data limite para o pagamento
            df_merged['DATA_LIMITE_PAGAMENTO'] = df_merged['DATA_ENVIO'] + timedelta(days=window_days)

            # Identificar pagamentos dentro da janela
            df_merged['PAGAMENTO_DENTRO_JANELA'] = (
                (df_merged['DATA_PAGAMENTO'] >= df_merged['DATA_ENVIO']) &
                (df_merged['DATA_PAGAMENTO'] <= df_merged['DATA_LIMITE_PAGAMENTO'])
            )

            # Filtrar apenas os pagamentos que ocorreram dentro da janela
            pagamentos_campanha = df_merged[df_merged['PAGAMENTO_DENTRO_JANELA']].copy()

            st.subheader("Resultados da Análise de Eficiência da Campanha")

            total_clientes_notificados = df_envios_com_matricula['MATRICULA_CLIENTE'].nunique()

            if not pagamentos_campanha.empty:
                # Contar clientes únicos que pagaram dentro da janela
                clientes_que_pagaram = pagamentos_campanha['MATRICULA_CLIENTE'].nunique()
                valor_total_arrecadado = pagamentos_campanha['VALOR_PAGO'].sum()
                taxa_eficiencia = (clientes_que_pagaram / total_clientes_notificados) * 100 if total_clientes_notificados > 0 else 0

                st.metric(label="Total de Clientes Notificados (com Matrícula)", value=f"{total_clientes_notificados}")
                st.metric(label="Clientes que Pagaram dentro da Janela", value=f"{clientes_que_pagaram}")
                st.metric(label="Valor Total Arrecadado na Campanha", value=f"R$ {valor_total_arrecadado:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
                st.metric(label="Taxa de Eficiência da Campanha", value=f"{taxa_eficiencia:,.2f}%".replace(",", "X").replace(".", ",").replace("X", "."))

                st.markdown("---")
                st.subheader("Detalhes dos Pagamentos Atribuídos à Campanha")
                # Selecionar e exibir colunas relevantes para o detalhe
                pagamentos_detalhe = pagamentos_campanha[[
                    'TELEFONE_ENVIO', 'MATRICULA_CLIENTE', 'DATA_ENVIO',
                    'DATA_PAGAMENTO', 'VALOR_PAGO', 'DATA_LIMITE_PAGAMENTO'
                ]].sort_values(by='DATA_ENVIO').reset_index(drop=True)

                st.dataframe(pagamentos_detalhe)

                # Botão de download
                csv_output = pagamentos_detalhe.to_csv(index=False, sep=';', decimal=',', encoding='utf-8-sig')
                st.download_button(
                    label="Baixar Pagamentos da Campanha (CSV)",
                    data=csv_output,
                    file_name="pagamentos_campanha.csv",
                    mime="text/csv",
                )
            else:
                st.info("Nenhum pagamento encontrado dentro da janela definida para a campanha.")
                st.metric(label="Total de Clientes Notificados (com Matrícula)", value=f"{total_clientes_notificados}")
                st.metric(label="Clientes que Pagaram dentro da Janela", value="0")
                st.metric(label="Valor Total Arrecadado na Campanha", value="R$ 0,00")
                st.metric(label="Taxa de Eficiência da Campanha", value="0,00%")

        else:
            st.error("Não foi possível processar um ou mais arquivos. Verifique os formatos e as colunas esperadas.")
    else:
        st.warning("Por favor, carregue todos os três arquivos para iniciar a análise.")
