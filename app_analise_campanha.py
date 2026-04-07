import streamlit as st
import pandas as pd
from datetime import timedelta
import io
import re
import plotly.express as px

# Configurações da página do Streamlit
st.set_page_config(layout="wide", page_title="Análise de campanha de cobrança via Whatsapp")

st.title("📊 Análise de eficiência de campanha de cobrança via Whatsapp")
st.markdown("Faça o upload dos seus arquivos para analisar a performance da campanha de notificações.")

# --- Funções de Processamento ---

@st.cache_data
def load_and_process_envios(uploaded_file):
    """Carrega e processa o relatório de envios Infobip."""
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

        # Normalizar TELEFONE_ENVIO (remover '55' e '.0')
        df_envios['TELEFONE_ENVIO'] = df_envios['TELEFONE_ENVIO'].astype(str).str.replace(r'^55|\.0$', '', regex=True)

        # Converter DATA_ENVIO para datetime
        df_envios['DATA_ENVIO'] = pd.to_datetime(df_envios['DATA_ENVIO'], errors='coerce')
        df_envios.dropna(subset=['DATA_ENVIO'], inplace=True)

        st.sidebar.success("Arquivo de Envios processado com sucesso.")
        return df_envios
    except Exception as e:
        st.sidebar.error(f"Erro ao processar o arquivo de Envios: {e}")
        return None

@st.cache_data
def load_and_process_pagamentos(uploaded_file):
    """Carrega e processa o arquivo de pagamentos."""
    try:
        # Tentar ler como CSV ou Excel
        if uploaded_file.name.endswith('.csv'):
            # Tentar diferentes codificações e delimitadores para CSV
            for encoding in ['latin1', 'utf-8', 'cp1252']:
                try:
                    df = pd.read_csv(uploaded_file, encoding=encoding, sep=';', decimal=',')
                    break
                except Exception:
                    uploaded_file.seek(0) # Resetar o ponteiro do arquivo para tentar novamente
                    try: # Tentar com vírgula como delimitador
                        df = pd.read_csv(uploaded_file, encoding=encoding, sep=',', decimal=',')
                        break
                    except Exception:
                        uploaded_file.seek(0) # Resetar novamente
                        continue
            else:
                st.sidebar.error("Não foi possível ler o arquivo CSV de pagamentos com as codificações e delimitadores tentados.")
                return None
        elif uploaded_file.name.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(uploaded_file)
        else:
            st.sidebar.error("Formato de arquivo de pagamentos não suportado. Por favor, use .csv ou .xlsx.")
            return None

        # --- Ajuste CRÍTICO: Atribuir nomes de colunas com base na posição ---
        # Como o arquivo não tem cabeçalho, vamos atribuir nomes genéricos e depois renomear
        num_cols = df.shape[1]

        # Verificar se os índices existem no DataFrame
        if num_cols < 10: # Precisamos de pelo menos até o índice 9
            st.sidebar.error(f"Arquivo de Pagamentos: Número insuficiente de colunas ({num_cols}). Esperado pelo menos 10 colunas para mapeamento.")
            return None

        # Selecionar as colunas por índice e renomear
        df_pagamentos = df.iloc[:, [0, 6, 9]].copy() # Seleciona as colunas por índice
        df_pagamentos.columns = ['MATRICULA_PAGAMENTO', 'DATA_PAGAMENTO', 'VALOR_PAGO'] # Renomeia

        # Converter DATA_PAGAMENTO para datetime
        df_pagamentos['DATA_PAGAMENTO'] = pd.to_datetime(df_pagamentos['DATA_PAGAMENTO'], errors='coerce')
        df_pagamentos.dropna(subset=['DATA_PAGAMENTO'], inplace=True)

        # Converter VALOR_PAGO para numérico
        df_pagamentos['VALOR_PAGO'] = pd.to_numeric(
            df_pagamentos['VALOR_PAGO'].astype(str).str.replace('.', '', regex=False).str.replace(',', '.', regex=False),
            errors='coerce'
        )
        df_pagamentos.dropna(subset=['VALOR_PAGO'], inplace=True)

        st.sidebar.success("Arquivo de Pagamentos processado com sucesso.")
        return df_pagamentos
    except Exception as e:
        st.sidebar.error(f"Erro ao processar o arquivo de Pagamentos: {e}")
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

        # Normalizar TELEFONE_CLIENTE (remover '55' e '.0')
        df_clientes['TELEFONE_CLIENTE'] = df_clientes['TELEFONE_CLIENTE'].astype(str).str.replace(r'^55|\.0$', '', regex=True)

        # Garantir que MATRICULA_CLIENTE seja string para o merge
        df_clientes['MATRICULA_CLIENTE'] = df_clientes['MATRICULA_CLIENTE'].astype(str).str.replace(r'\.0$', '', regex=True)

        st.sidebar.success("Arquivo de Clientes processado com sucesso.")
        return df_clientes
    except Exception as e:
        st.sidebar.error(f"Erro ao processar o arquivo de Clientes: {e}")
        return None

# --- Interface do Streamlit ---

with st.sidebar:
    st.header("Upload de Arquivos")
    uploaded_file_envios = st.file_uploader("1. Base de Envios (Notificações - .xlsx)", type=["xlsx"])
    uploaded_file_pagamentos = st.file_uploader("2. Base de Pagamentos (.csv ou .xlsx)", type=["csv", "xlsx"])
    uploaded_file_clientes = st.file_uploader("3. Base de Identificação de Clientes (.xlsx)", type=["xlsx"])

    st.markdown("---")
    st.header("Configurações da Análise")
    janela_dias = st.slider("Janela de dias para considerar o pagamento após o envio da notificação", 1, 30, 7)

    st.markdown("---")
    executar_analise = st.button("Executar Análise")

# --- Lógica Principal ---
if executar_analise:
    if uploaded_file_envios and uploaded_file_pagamentos and uploaded_file_clientes:
        df_envios = load_and_process_envios(uploaded_file_envios)
        df_pagamentos = load_and_process_pagamentos(uploaded_file_pagamentos)
        df_clientes = load_and_process_clientes(uploaded_file_clientes)

        if df_envios is not None and df_pagamentos is not None and df_clientes is not None:
            st.subheader("Pré-visualização dos Dados Processados")
            st.write("Base de Envios (Notificações):")
            st.dataframe(df_envios.head())
            st.write("Base de Pagamentos:")
            st.dataframe(df_pagamentos.head())
            st.write("Base de Identificação de Clientes:")
            st.dataframe(df_clientes.head())

            st.subheader("Realizando Cruzamento de Dados...")

            # 1. Cruzar envios com clientes para obter a matrícula
            df_campanha = pd.merge(
                df_envios,
                df_clientes,
                left_on='TELEFONE_ENVIO',
                right_on='TELEFONE_CLIENTE',
                how='inner'
            )
            # Remover duplicatas de envios para o mesmo telefone/matrícula no mesmo dia, se houver
            df_campanha.drop_duplicates(subset=['TELEFONE_ENVIO', 'MATRICULA_CLIENTE', 'DATA_ENVIO'], inplace=True)

            if df_campanha.empty:
                st.warning("Nenhum cliente notificado pôde ser associado a uma matrícula. Verifique os dados de telefone e matrícula.")
                st.stop()

            st.info(f"Total de {len(df_campanha)} notificações associadas a clientes com matrícula.")

            # 2. Cruzar a base de campanha com pagamentos
            # Garantir que as colunas de matrícula sejam do mesmo tipo para o merge
            df_campanha['MATRICULA_CLIENTE'] = df_campanha['MATRICULA_CLIENTE'].astype(str)
            df_pagamentos['MATRICULA_PAGAMENTO'] = df_pagamentos['MATRICULA_PAGAMENTO'].astype(str)

            df_merged = pd.merge(
                df_campanha,
                df_pagamentos,
                left_on='MATRICULA_CLIENTE',
                right_on='MATRICULA_PAGAMENTO',
                how='inner' # Usar inner para considerar apenas pagamentos que têm uma notificação correspondente
            )

            if df_merged.empty:
                st.warning("Nenhum pagamento encontrado para os clientes notificados.")
                st.metric(label="Total de Clientes Notificados (com Matrícula)", value=f"{len(df_campanha)}")
                st.metric(label="Clientes que Pagaram dentro da Janela", value="0")
                st.metric(label="Valor Total Arrecadado na Campanha", value="R$ 0,00")
                st.metric(label="Taxa de Eficiência da Campanha", value="0,00%")
                st.stop()

            # 3. Filtrar pagamentos dentro da janela de dias
            df_pagamentos_campanha = df_merged[
                (df_merged['DATA_PAGAMENTO'] > df_merged['DATA_ENVIO']) &
                (df_merged['DATA_PAGAMENTO'] <= df_merged['DATA_ENVIO'] + timedelta(days=janela_dias))
            ].copy() # Usar .copy() para evitar SettingWithCopyWarning

            # Resumo da Campanha
            total_clientes_notificados = df_campanha['MATRICULA_CLIENTE'].nunique()

            clientes_que_pagaram = df_pagamentos_campanha['MATRICULA_CLIENTE'].nunique()
            valor_total_arrecadado = df_pagamentos_campanha['VALOR_PAGO'].sum()

            taxa_eficiencia = (clientes_que_pagaram / total_clientes_notificados * 100) if total_clientes_notificados > 0 else 0

            st.header("Resultados da Análise da Campanha")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric(label="Total de Clientes Notificados (com Matrícula)", value=f"{total_clientes_notificados}")
            with col2:
                st.metric(label="Clientes que Pagaram dentro da Janela", value=f"{clientes_que_pagaram}")
            with col3:
                st.metric(label="Valor Total Arrecadado na Campanha", value=f"R$ {valor_total_arrecadado:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
            with col4:
                st.metric(label="Taxa de Eficiência da Campanha", value=f"{taxa_eficiencia:,.2f}%".replace(",", "X").replace(".", ",").replace("X", "."))

            st.markdown("---")
            st.subheader("Pagamentos por Dia Após o Envio da Notificação")

            if not df_pagamentos_campanha.empty:
                # Calcular dias para pagamento
                df_pagamentos_campanha['DIAS_PARA_PAGAMENTO'] = (df_pagamentos_campanha['DATA_PAGAMENTO'] - df_pagamentos_campanha['DATA_ENVIO']).dt.days

                # Agrupar por dias para pagamento e somar o valor
                pagamentos_por_dia = df_pagamentos_campanha.groupby('DIAS_PARA_PAGAMENTO')['VALOR_PAGO'].sum().reset_index()
                pagamentos_por_dia.rename(columns={'VALOR_PAGO': 'Valor Total Pago'}, inplace=True)

                # Criar o gráfico
                fig = px.bar(
                    pagamentos_por_dia,
                    x='DIAS_PARA_PAGAMENTO',
                    y='Valor Total Pago',
                    title='Valor Total Pago por Dia Após o Envio da Notificação',
                    labels={'DIAS_PARA_PAGAMENTO': 'Dias Após Envio da Notificação', 'Valor Total Pago': 'Valor Total Pago (R$)'},
                    hover_data={'Valor Total Pago': ':.2f'}
                )
                fig.update_layout(xaxis_title="Dias Após Envio da Notificação", yaxis_title="Valor Total Pago (R$)")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Nenhum pagamento encontrado dentro da janela para gerar o gráfico.")

            st.markdown("---")
            st.subheader("Detalhes dos Pagamentos Atribuídos à Campanha")
            if not df_pagamentos_campanha.empty:
                # Selecionar e ordenar colunas para exibição e download
                pagamentos_detalhe = df_pagamentos_campanha[[
                    'MATRICULA_CLIENTE', 'TELEFONE_ENVIO', 'DATA_ENVIO',
                    'DATA_PAGAMENTO', 'VALOR_PAGO'
                ]].sort_values(by='DATA_ENVIO').reset_index(drop=True)

                st.dataframe(pagamentos_detalhe)

                # Botão de download
                csv_output = pagamentos_detalhe.to_csv(index=False, sep=';', decimal=',', encoding='utf-8-sig')
                st.download_button(
                    label="Baixar Detalhes dos Pagamentos da Campanha (CSV)",
                    data=csv_output,
                    file_name="pagamentos_campanha.csv",
                    mime="text/csv",
                )
            else:
                st.info("Nenhum pagamento encontrado dentro da janela definida para a campanha.")

        else:
            st.error("Não foi possível processar um ou mais arquivos. Verifique os formatos e as colunas esperadas.")
    else:
        st.warning("Por favor, carregue todos os três arquivos para iniciar a análise.")
