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

        # Remover duplicatas de notificações (mesmo telefone, mesma data de envio)
        df_envios.drop_duplicates(subset=['TELEFONE_ENVIO', 'DATA_ENVIO'], inplace=True)

        st.sidebar.success("Arquivo de Envios processado com sucesso.")
        return df_envios
    except Exception as e:
        st.sidebar.error(f"Erro ao processar o arquivo de Envios: {e}")
        return None

@st.cache_data
def load_and_process_pagamentos(uploaded_file):
    """Carrega e processa o arquivo de pagamentos."""
    try:
        df = None
        if uploaded_file.name.endswith('.csv'):
            # Tentar diferentes codificações e delimitadores para CSV
            for encoding in ['latin1', 'utf-8', 'cp1252']:
                try:
                    # Tentar ler sem cabeçalho e com delimitador ',' ou ';'
                    df = pd.read_csv(uploaded_file, sep=',', header=None, encoding=encoding, decimal=',', on_bad_lines='skip')
                    if df.shape[1] < 10: # Se a leitura com ',' falhar ou tiver poucas colunas, tentar com ';'
                        uploaded_file.seek(0) # Resetar o ponteiro do arquivo
                        df = pd.read_csv(uploaded_file, sep=';', header=None, encoding=encoding, decimal=',', on_bad_lines='skip')
                    break # Se a leitura for bem-sucedida, sair do loop
                except Exception:
                    continue
            if df is None:
                raise ValueError("Não foi possível ler o arquivo CSV com as codificações e delimitadores tentados.")
        elif uploaded_file.name.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(uploaded_file, header=None) # Ler Excel sem cabeçalho
        else:
            raise ValueError("Formato de arquivo de pagamentos não suportado. Use .csv ou .xlsx.")

        if df is None or df.empty:
            st.error("Arquivo de Pagamentos vazio ou não pôde ser lido.")
            return None

        # Verificar se o DataFrame tem colunas suficientes para o mapeamento
        if df.shape[1] < 10:
            st.error(f"Arquivo de Pagamentos: Esperava pelo menos 10 colunas, mas encontrou {df.shape[1]}.")
            return None

        # Mapear colunas por índice (0-based)
        # 0: Matrícula do Pagamento
        # 6: Data do Pagamento
        # 9: Valor Autenticado
        df_pagamentos = df.iloc[:, [0, 6, 9]].copy()
        df_pagamentos.columns = ['MATRICULA_PAGAMENTO', 'DATA_PAGAMENTO', 'VALOR_PAGO']

        # Normalizar MATRICULA_PAGAMENTO (remover '.0')
        df_pagamentos['MATRICULA_PAGAMENTO'] = df_pagamentos['MATRICULA_PAGAMENTO'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()

        # Converter DATA_PAGAMENTO para datetime
        df_pagamentos['DATA_PAGAMENTO'] = pd.to_datetime(df_pagamentos['DATA_PAGAMENTO'], errors='coerce', dayfirst=True)
        df_pagamentos.dropna(subset=['DATA_PAGAMENTO'], inplace=True) # Remover linhas com datas inválidas

        # Converter VALOR_PAGO para numérico
        df_pagamentos['VALOR_PAGO'] = pd.to_numeric(
            df_pagamentos['VALOR_PAGO'].astype(str).str.replace('.', '', regex=False).str.replace(',', '.', regex=False),
            errors='coerce'
        )
        df_pagamentos.dropna(subset=['VALOR_PAGO'], inplace=True) # Remover linhas com valores inválidos

        st.sidebar.success("Arquivo de Pagamentos processado com sucesso.")
        return df_pagamentos
    except Exception as e:
        st.sidebar.error(f"Erro ao processar o arquivo de Pagamentos: {e}")
        return None

@st.cache_data
def load_and_process_clientes(uploaded_file):
    """Carrega e processa o arquivo de identificação de clientes."""
    try:
        df_clientes = pd.read_excel(uploaded_file)

        # Verificar colunas essenciais
        required_cols = ['TELEFONE', 'MATRICULA', 'SITUACAO'] # Adicionando 'SITUACAO'
        if not all(col in df_clientes.columns for col in required_cols):
            st.error(f"Arquivo de Clientes: Colunas esperadas '{required_cols[0]}', '{required_cols[1]}' ou '{required_cols[2]}' não encontradas.")
            return None

        # Selecionar e renomear colunas
        df_clientes = df_clientes[['TELEFONE', 'MATRICULA', 'SITUACAO']].copy() # Incluindo 'SITUACAO'
        df_clientes.rename(columns={'TELEFONE': 'TELEFONE_CLIENTE', 'MATRICULA': 'MATRICULA_CLIENTE'}, inplace=True)

        # Normalizar TELEFONE_CLIENTE e MATRICULA_CLIENTE
        df_clientes['TELEFONE_CLIENTE'] = df_clientes['TELEFONE_CLIENTE'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
        df_clientes['MATRICULA_CLIENTE'] = df_clientes['MATRICULA_CLIENTE'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()

        # Converter 'SITUACAO' para numérico, tratando erros e preenchendo nulos com 0
        df_clientes['SITUACAO'] = pd.to_numeric(
            df_clientes['SITUACAO'].astype(str).str.replace('.', '', regex=False).str.replace(',', '.', regex=False),
            errors='coerce'
        ).fillna(0)

        # Remover duplicatas de clientes (considerando telefone e matrícula)
        df_clientes.drop_duplicates(subset=['TELEFONE_CLIENTE', 'MATRICULA_CLIENTE'], inplace=True)

        st.sidebar.success("Arquivo de Clientes processado com sucesso.")
        return df_clientes
    except Exception as e:
        st.sidebar.error(f"Erro ao processar o arquivo de Clientes: {e}")
        return None

# --- Interface do Streamlit ---

with st.sidebar:
    st.header("Upload de Arquivos")
    uploaded_envios = st.file_uploader("1. Base de Envios (Notificações - .xlsx)", type=["xlsx"])
    uploaded_pagamentos = st.file_uploader("2. Base de Pagamentos (.csv ou .xlsx)", type=["csv", "xlsx"])
    uploaded_clientes = st.file_uploader("3. Base de Identificação de Clientes (.xlsx)", type=["xlsx"])

    st.header("Configurações da Análise")
    window_days = st.slider("Janela de dias para considerar o pagamento após a notificação", 1, 30, 7)

    executar_analise = st.button("Executar Análise")

if executar_analise:
    if uploaded_envios and uploaded_pagamentos and uploaded_clientes:
        df_envios = load_and_process_envios(uploaded_envios)
        df_pagamentos = load_and_process_pagamentos(uploaded_pagamentos)
        df_clientes = load_and_process_clientes(uploaded_clientes)

        if df_envios is not None and df_pagamentos is not None and df_clientes is not None:
            st.subheader("Pré-visualização dos Dados Processados")
            st.write("--- Base de Envios ---")
            st.dataframe(df_envios.head())
            st.write("--- Base de Pagamentos ---")
            st.dataframe(df_pagamentos.head())
            st.write("--- Base de Identificação de Clientes ---")
            st.dataframe(df_clientes.head())
            st.markdown("---")

            # 1. Cruzar Envios com Clientes para obter a matrícula de cada notificação
            df_notificacoes_com_matricula = pd.merge(
                df_envios,
                df_clientes[['TELEFONE_CLIENTE', 'MATRICULA_CLIENTE', 'SITUACAO']], # Incluir 'SITUACAO'
                left_on='TELEFONE_ENVIO',
                right_on='TELEFONE_CLIENTE',
                how='inner'
            )
            # Renomear MATRICULA_CLIENTE para MATRICULA para facilitar o merge com pagamentos
            df_notificacoes_com_matricula.rename(columns={'MATRICULA_CLIENTE': 'MATRICULA'}, inplace=True)
            df_notificacoes_com_matricula.drop(columns=['TELEFONE_CLIENTE'], inplace=True)

            # Remover duplicatas de notificações (mesma matrícula, mesma data de envio)
            # Isso garante que cada notificação única para uma matrícula seja um ponto de partida para a janela
            df_notificacoes_com_matricula.drop_duplicates(subset=['MATRICULA', 'DATA_ENVIO'], inplace=True)

            if df_notificacoes_com_matricula.empty:
                st.warning("Nenhuma notificação pôde ser associada a uma matrícula válida na base de clientes.")
                st.stop()

            # 2. Cruzar Notificações (com Matrícula) com Pagamentos
            # Usar um merge 'left' para manter todas as notificações e tentar encontrar pagamentos
            df_campanha = pd.merge(
                df_notificacoes_com_matricula,
                df_pagamentos,
                left_on='MATRICULA',
                right_on='MATRICULA_PAGAMENTO',
                how='left'
            )
            df_campanha.drop(columns=['MATRICULA_PAGAMENTO'], inplace=True)

            # Calcular a data limite para o pagamento
            df_campanha['DATA_LIMITE_PAGAMENTO'] = df_campanha['DATA_ENVIO'] + timedelta(days=window_days)

            # Filtrar pagamentos que ocorreram dentro da janela
            pagamentos_dentro_janela = df_campanha[
                (df_campanha['DATA_PAGAMENTO'] >= df_campanha['DATA_ENVIO']) &
                (df_campanha['DATA_PAGAMENTO'] <= df_campanha['DATA_LIMITE_PAGAMENTO']) &
                (df_campanha['VALOR_PAGO'].notna()) # Apenas pagamentos com valor
            ].copy()

            # Calcular o número de dias após o envio para o gráfico
            if not pagamentos_dentro_janela.empty:
                pagamentos_dentro_janela['DIAS_APOS_ENVIO'] = (pagamentos_dentro_janela['DATA_PAGAMENTO'] - pagamentos_dentro_janela['DATA_ENVIO']).dt.days

            # --- Métricas da Campanha ---
            total_clientes_notificados = df_notificacoes_com_matricula['MATRICULA'].nunique()

            clientes_que_pagaram_matriculas = pagamentos_dentro_janela['MATRICULA'].nunique()
            valor_total_arrecadado = pagamentos_dentro_janela['VALOR_PAGO'].sum() if not pagamentos_dentro_janela.empty else 0

            taxa_eficiencia = (clientes_que_pagaram_matriculas / total_clientes_notificados * 100) if total_clientes_notificados > 0 else 0

            # --- NOVO CÁLCULO: Total da Dívida dos Clientes Notificados ---
            # Filtrar df_clientes para obter apenas as matrículas que foram notificadas
            matriculas_notificadas_validas = df_notificacoes_com_matricula['MATRICULA'].unique()
            df_clientes_notificados_com_divida = df_clientes[
                df_clientes['MATRICULA_CLIENTE'].isin(matriculas_notificadas_validas)
            ].copy()

            total_divida_notificados = df_clientes_notificados_com_divida['SITUACAO'].sum()

            st.subheader("Resultados da Análise da Campanha")
            col1, col2, col3, col4, col5 = st.columns(5)
            with col1:
                st.metric(label="Clientes Notificados (com Matrícula)", value=f"{total_clientes_notificados}")
            with col2:
                st.metric(label="Clientes que Pagaram na Janela", value=f"{clientes_que_pagaram_matriculas}")
            with col3:
                st.metric(label="Valor Total Arrecadado na Campanha", value=f"R$ {valor_total_arrecadado:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
            with col4:
                st.metric(label="Taxa de Eficiência da Campanha", value=f"{taxa_eficiencia:,.2f}%".replace(",", "X").replace(".", ",").replace("X", "."))
            with col5:
                st.metric(label="Total da Dívida dos Notificados", value=f"R$ {total_divida_notificados:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))


            st.markdown("---")
            st.subheader("Pagamentos por Dia Após o Envio da Notificação")
            if not pagamentos_dentro_janela.empty:
                pagamentos_por_dia = pagamentos_dentro_janela.groupby('DIAS_APOS_ENVIO')['VALOR_PAGO'].sum().reset_index()
                pagamentos_por_dia.rename(columns={'VALOR_PAGO': 'Valor Total Pago'}, inplace=True)

                fig = px.bar(
                    pagamentos_por_dia,
                    x='DIAS_APOS_ENVIO',
                    y='Valor Total Pago',
                    title='Valor Total Pago por Dia Após o Envio da Notificação',
                    labels={'DIAS_APOS_ENVIO': 'Dias Após o Envio da Notificação', 'Valor Total Pago': 'Valor Total Pago (R$)'},
                    hover_data={'Valor Total Pago': ':.2f'}
                )
                fig.update_layout(xaxis_title="Dias Após o Envio da Notificação", yaxis_title="Valor Total Pago (R$)")
                st.plotly_chart(fig, use_container_width=True)

                st.subheader("Detalhes dos Pagamentos Atribuídos à Campanha")
                # Selecionar colunas relevantes para exibição e download
                df_detalhes_pagamentos = pagamentos_dentro_janela[[
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
