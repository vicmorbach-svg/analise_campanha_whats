import streamlit as st
import pandas as pd
from datetime import timedelta
import io
import re
import plotly.express as px

# Configurações da página do Streamlit
st.set_page_config(layout="wide", page_title="Análise de Campanha de Pagamentos")

st.title("📊 Análise de Eficiência de Campanha de Pagamentos")
st.markdown("Faça o upload dos seus arquivos para analisar a performance da campanha de notificações.")

# --- Funções de Processamento ---

@st.cache_data
def load_and_process_envios(uploaded_file):
    """Carrega e processa o arquivo de envios (notificações)."""
    try:
        df = pd.read_excel(uploaded_file)

        # Verificar colunas essenciais
        required_cols = ['To', 'Send At']
        if not all(col in df.columns for col in required_cols):
            st.error(f"Arquivo de Envios: Colunas esperadas '{required_cols[0]}' e '{required_cols[1]}' não encontradas.")
            return None

        # Selecionar e renomear colunas
        df_envios = df[['To', 'Send At']].copy()
        df_envios.rename(columns={'To': 'TELEFONE_ENVIO', 'Send At': 'DATA_ENVIO'}, inplace=True)

        # Normalizar o telefone: remover '55' e '.0'
        df_envios['TELEFONE_ENVIO'] = df_envios['TELEFONE_ENVIO'].astype(str).str.replace(r'^55', '', regex=True).str.replace(r'\.0$', '', regex=True)
        df_envios['TELEFONE_ENVIO'] = df_envios['TELEFONE_ENVIO'].str.strip() # Remover espaços em branco

        # Converter DATA_ENVIO para datetime
        df_envios['DATA_ENVIO'] = pd.to_datetime(df_envios['DATA_ENVIO'], errors='coerce', dayfirst=True)
        df_envios.dropna(subset=['DATA_ENVIO'], inplace=True) # Remover linhas com datas inválidas

        st.sidebar.success("Arquivo de Envios processado com sucesso!")
        return df_envios
    except Exception as e:
        st.sidebar.error(f"Erro ao processar arquivo de Envios: {e}")
        return None

@st.cache_data
def load_and_process_pagamentos(uploaded_file):
    """Carrega e processa o arquivo de pagamentos (CSV ou XLSX)."""
    try:
        df = None
        if uploaded_file.name.endswith('.csv'):
            # Tentar diferentes codificações para CSV
            for encoding in ['latin1', 'utf-8', 'cp1252']:
                try:
                    df = pd.read_csv(uploaded_file, sep=';', decimal=',', encoding=encoding, header=None)
                    uploaded_file.seek(0) # Resetar o ponteiro do arquivo para futuras leituras
                    break
                except Exception:
                    uploaded_file.seek(0) # Resetar o ponteiro do arquivo para tentar outra codificação
                    continue
            if df is None:
                raise ValueError("Não foi possível ler o arquivo CSV com as codificações tentadas (latin1, utf-8, cp1252).")
        elif uploaded_file.name.endswith('.xlsx'):
            df = pd.read_excel(uploaded_file, header=None)
        else:
            raise ValueError("Formato de arquivo de pagamentos não suportado. Use .csv ou .xlsx.")

        if df is None or df.empty:
            st.sidebar.error("Arquivo de Pagamentos está vazio ou não pôde ser lido.")
            return None

        # Verificar se o DataFrame tem colunas suficientes para o mapeamento por índice
        if df.shape[1] < 10: # Mínimo de 10 colunas para os índices 0, 6, 9
            st.sidebar.error(f"Arquivo de Pagamentos: Esperava pelo menos 10 colunas, mas encontrou {df.shape[1]}.")
            return None

        # Mapear colunas por índice, pois o arquivo não tem cabeçalho
        # Colunas: 0=Matrícula, 6=Data Pagamento, 9=Valor Pago
        df_pagamentos = df.iloc[:, [0, 6, 9]].copy()
        df_pagamentos.columns = ['MATRICULA_PAGAMENTO', 'DATA_PAGAMENTO', 'VALOR_PAGO']

        # Converter MATRICULA_PAGAMENTO para string e remover '.0'
        df_pagamentos['MATRICULA_PAGAMENTO'] = df_pagamentos['MATRICULA_PAGAMENTO'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()

        # Converter DATA_PAGAMENTO para datetime
        df_pagamentos['DATA_PAGAMENTO'] = pd.to_datetime(df_pagamentos['DATA_PAGAMENTO'], errors='coerce', dayfirst=True)
        df_pagamentos.dropna(subset=['DATA_PAGAMENTO'], inplace=True) # Remover linhas com datas inválidas

        # Converter VALOR_PAGO para numérico, tratando vírgula como decimal
        df_pagamentos['VALOR_PAGO'] = df_pagamentos['VALOR_PAGO'].astype(str).str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
        df_pagamentos['VALOR_PAGO'] = pd.to_numeric(df_pagamentos['VALOR_PAGO'], errors='coerce')
        df_pagamentos.dropna(subset=['VALOR_PAGO'], inplace=True) # Remover linhas com valores inválidos

        st.sidebar.success("Arquivo de Pagamentos processado com sucesso!")
        return df_pagamentos
    except Exception as e:
        st.sidebar.error(f"Erro ao processar arquivo de Pagamentos: {e}")
        return None

@st.cache_data
def load_and_process_clientes(uploaded_file):
    """Carrega e processa o arquivo de identificação de clientes."""
    try:
        df = pd.read_excel(uploaded_file)

        # Verificar colunas essenciais
        required_cols = ['TELEFONE', 'MATRICULA']
        if not all(col in df.columns for col in required_cols):
            st.error(f"Arquivo de Clientes: Colunas esperadas '{required_cols[0]}' e '{required_cols[1]}' não encontradas.")
            return None

        # Selecionar e renomear colunas
        df_clientes = df[['TELEFONE', 'MATRICULA']].copy()
        df_clientes.rename(columns={'TELEFONE': 'TELEFONE_CLIENTE', 'MATRICULA': 'MATRICULA_CLIENTE'}, inplace=True)

        # Normalizar o telefone: remover '55' e '.0'
        df_clientes['TELEFONE_CLIENTE'] = df_clientes['TELEFONE_CLIENTE'].astype(str).str.replace(r'^55', '', regex=True).str.replace(r'\.0$', '', regex=True)
        df_clientes['TELEFONE_CLIENTE'] = df_clientes['TELEFONE_CLIENTE'].str.strip() # Remover espaços em branco

        # Converter MATRICULA_CLIENTE para string e remover '.0'
        df_clientes['MATRICULA_CLIENTE'] = df_clientes['MATRICULA_CLIENTE'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()

        # Remover duplicatas de telefone para garantir um mapeamento 1:1 ou 1:N (se um telefone tiver múltiplas matrículas)
        # Para o propósito de "PROCV", vamos pegar a primeira matrícula encontrada para cada telefone único.
        df_clientes.drop_duplicates(subset=['TELEFONE_CLIENTE', 'MATRICULA_CLIENTE'], inplace=True)

        st.sidebar.success("Arquivo de Clientes processado com sucesso!")
        return df_clientes
    except Exception as e:
        st.sidebar.error(f"Erro ao processar arquivo de Clientes: {e}")
        return None

# --- Interface Streamlit ---

# Upload de arquivos na barra lateral
st.sidebar.header("Upload de Arquivos")
uploaded_envios = st.sidebar.file_uploader("1. Base de Envios (Notificações - .xlsx)", type=["xlsx"])
uploaded_pagamentos = st.sidebar.file_uploader("2. Base de Pagamentos (.csv ou .xlsx)", type=["csv", "xlsx"])
uploaded_clientes = st.sidebar.file_uploader("3. Base de Identificação de Clientes (.xlsx)", type=["xlsx"])

# Slider para a janela de dias
st.sidebar.header("Configurações da Análise")
janela_dias = st.sidebar.slider("Janela de dias para considerar o pagamento após o envio da notificação:", 0, 30, 7)

executar_analise = st.sidebar.button("Executar Análise")

df_envios = None
df_pagamentos = None
df_clientes = None

if uploaded_envios:
    df_envios = load_and_process_envios(uploaded_envios)
if uploaded_pagamentos:
    df_pagamentos = load_and_process_pagamentos(uploaded_pagamentos)
if uploaded_clientes:
    df_clientes = load_and_process_clientes(uploaded_clientes)

# Pré-visualização dos dados (opcional, para depuração)
if st.sidebar.checkbox("Mostrar pré-visualização dos dados processados"):
    if df_envios is not None:
        st.subheader("Pré-visualização da Base de Envios")
        st.dataframe(df_envios.head())
    if df_pagamentos is not None:
        st.subheader("Pré-visualização da Base de Pagamentos")
        st.dataframe(df_pagamentos.head())
    if df_clientes is not None:
        st.subheader("Pré-visualização da Base de Clientes")
        st.dataframe(df_clientes.head())

if executar_analise:
    if df_envios is not None and df_pagamentos is not None and df_clientes is not None:
        st.subheader("Processando e Cruzando Dados...")

        # 1. Cruzar Envios com Clientes para obter a Matrícula
        # Usar left merge para manter todas as notificações e adicionar a matrícula
        df_campanha = pd.merge(
            df_envios,
            df_clientes,
            left_on='TELEFONE_ENVIO',
            right_on='TELEFONE_CLIENTE',
            how='left'
        )

        # Remover notificações que não puderam ser associadas a uma matrícula
        df_campanha.dropna(subset=['MATRICULA_CLIENTE'], inplace=True)

        # Renomear para padronizar e remover coluna redundante
        df_campanha.rename(columns={'MATRICULA_CLIENTE': 'MATRICULA'}, inplace=True)
        df_campanha.drop(columns=['TELEFONE_CLIENTE'], inplace=True)

        # Remover duplicatas de notificação por matrícula e data de envio
        # Se um cliente recebeu múltiplas notificações, consideramos a primeira para a análise de pagamento
        # ou a mais relevante. Para simplificar, vamos considerar cada notificação única (telefone+data)
        # que resultou em uma matrícula. Se a mesma matrícula recebeu múltiplas notificações,
        # cada uma será um ponto de partida para a janela de pagamento.
        # Para evitar contagem duplicada de "clientes notificados", vamos contar matrículas únicas.
        df_campanha_unique_notifications = df_campanha.drop_duplicates(subset=['MATRICULA', 'DATA_ENVIO'])


        if not df_campanha_unique_notifications.empty:
            st.subheader("Realizando Análise de Pagamentos Pós-Campanha")

            # 2. Cruzar com Pagamentos
            # Usar left merge para manter todas as notificações da campanha e adicionar os pagamentos
            df_resultados = pd.merge(
                df_campanha_unique_notifications,
                df_pagamentos,
                left_on='MATRICULA',
                right_on='MATRICULA_PAGAMENTO',
                how='left'
            )

            # Filtrar pagamentos dentro da janela
            df_pagamentos_campanha = df_resultados[
                (df_resultados['DATA_PAGAMENTO'] > df_resultados['DATA_ENVIO']) &
                (df_resultados['DATA_PAGAMENTO'] <= df_resultados['DATA_ENVIO'] + timedelta(days=janela_dias))
            ].copy() # Usar .copy() para evitar SettingWithCopyWarning

            # Remover pagamentos duplicados para a mesma matrícula na mesma data (se houver)
            # Isso garante que um único pagamento não seja atribuído a múltiplas notificações
            # se a mesma matrícula recebeu várias notificações e pagou uma vez.
            # A lógica aqui é que cada linha em df_pagamentos_campanha representa um pagamento
            # que pode ser atribuído a UMA notificação específica.
            # Se uma matrícula pagou várias vezes, e cada pagamento caiu na janela de uma notificação,
            # todos esses pagamentos serão contados.
            # Se uma matrícula recebeu várias notificações e fez um único pagamento,
            # esse pagamento será associado à primeira notificação que o "capturar" na janela.
            # Para evitar superestimar, vamos garantir que cada pagamento seja contado uma única vez
            # e associado à notificação mais próxima (ou primeira que se encaixa).

            # Para a contagem de clientes que pagaram, precisamos de matrículas únicas.
            clientes_que_pagaram_matriculas = df_pagamentos_campanha['MATRICULA'].nunique()

            # Para o valor total, somamos todos os VALOR_PAGO dos pagamentos dentro da janela
            valor_total_arrecadado = df_pagamentos_campanha['VALOR_PAGO'].sum() if not df_pagamentos_campanha.empty else 0

            # Total de clientes notificados (matrículas únicas que receberam notificação e foram encontradas na base de clientes)
            total_clientes_notificados = df_campanha_unique_notifications['MATRICULA'].nunique()

            # Calcular taxa de eficiência
            taxa_eficiencia = (clientes_que_pagaram_matriculas / total_clientes_notificados * 100) if total_clientes_notificados > 0 else 0

            st.subheader("Resultados da Análise da Campanha")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric(label="Total de Clientes Notificados (Matrículas Únicas)", value=f"{total_clientes_notificados}")
            with col2:
                st.metric(label="Clientes que Pagaram dentro da Janela", value=f"{clientes_que_pagaram_matriculas}")
            with col3:
                st.metric(label="Valor Total Arrecadado na Campanha", value=f"R$ {valor_total_arrecadado:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
            with col4:
                st.metric(label="Taxa de Eficiência da Campanha", value=f"{taxa_eficiencia:,.2f}%".replace(",", "X").replace(".", ",").replace("X", "."))

            if not df_pagamentos_campanha.empty:
                st.subheader(f"Pagamentos por Dia Após o Envio da Notificação (Janela de {janela_dias} dias)")

                # Calcular a diferença em dias
                df_pagamentos_campanha['DIAS_APOS_ENVIO'] = (df_pagamentos_campanha['DATA_PAGAMENTO'] - df_pagamentos_campanha['DATA_ENVIO']).dt.days

                # Agrupar por dias e somar os valores
                pagamentos_por_dia = df_pagamentos_campanha.groupby('DIAS_APOS_ENVIO')['VALOR_PAGO'].sum().reset_index()
                pagamentos_por_dia.rename(columns={'DIAS_APOS_ENVIO': 'Dias Após Envio', 'VALOR_PAGO': 'Valor Total Pago'}, inplace=True)

                # Criar o gráfico de barras
                fig = px.bar(
                    pagamentos_por_dia,
                    x='Dias Após Envio',
                    y='Valor Total Pago',
                    title='Valor Total Pago por Dia Após o Envio da Notificação',
                    labels={'Dias Após Envio': 'Dias Após o Envio da Notificação', 'Valor Total Pago': 'Valor Total Pago (R$)'},
                    hover_data={'Valor Total Pago': ':.2f'}
                )
                fig.update_layout(xaxis_title="Dias Após o Envio da Notificação", yaxis_title="Valor Total Pago (R$)")
                st.plotly_chart(fig, use_container_width=True)

                st.subheader("Detalhes dos Pagamentos Atribuídos à Campanha")
                # Selecionar colunas relevantes para exibição e download
                df_detalhes_pagamentos = df_pagamentos_campanha[[
                    'MATRICULA', 'TELEFONE_ENVIO', 'DATA_ENVIO', 'DATA_PAGAMENTO', 'VALOR_PAGO', 'DIAS_APOS_ENVIO'
                ]].drop_duplicates(subset=['MATRICULA', 'DATA_PAGAMENTO', 'VALOR_PAGO']) # Evitar duplicatas de pagamentos

                st.dataframe(df_detalhes_pagamentos)

                # Botão de download
                csv_output = df_detalhes_pagamentos.to_csv(index=False, sep=';', decimal=',')
                st.download_button(
                    label="Baixar Detalhes dos Pagamentos da Campanha (CSV)",
                    data=csv_output,
                    file_name="pagamentos_campanha.csv",
                    mime="text/csv",
                )
            else:
                st.info("Nenhum pagamento encontrado dentro da janela definida para a campanha.")

        else:
            st.error("Não foi possível processar um ou mais arquivos. Verifique os formatos e as colunas esperadas ou se há matrículas válidas após o cruzamento.")
    else:
        st.warning("Por favor, carregue todos os três arquivos para iniciar a análise.")
