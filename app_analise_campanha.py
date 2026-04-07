import streamlit as st
import pandas as pd
from datetime import timedelta
import io

# Configurações da página do Streamlit
st.set_page_config(layout="wide", page_title="Análise de Campanha de Pagamentos")

st.title("📊 Análise de Eficiência de Campanha de Pagamentos")
st.markdown("Faça o upload dos seus arquivos para analisar a performance da campanha.")

# --- Funções de Pré-processamento ---

@st.cache_data
def preprocessar_envios(uploaded_file):
    """Processa o arquivo de envios (notificações)."""
    try:
        df_envios = pd.read_excel(uploaded_file, engine='openpyxl')

        # Limpar linhas completamente vazias que podem vir do Excel
        df_envios.dropna(how='all', inplace=True)

        # Colunas esperadas e renomeadas
        col_to = 'To'
        col_send_at = 'Send At'

        if col_to not in df_envios.columns or col_send_at not in df_envios.columns:
            st.error(f"Arquivo de Envios: Colunas esperadas '{col_to}' ou '{col_send_at}' não encontradas.")
            return None

        df_envios = df_envios[[col_to, col_send_at]].copy()
        df_envios.rename(columns={
            col_to: 'TELEFONE_ENVIO',
            col_send_at: 'DATA_ENVIO'
        }, inplace=True)

        # Normalizar telefone: remover '55' e '.0'
        df_envios['TELEFONE_ENVIO'] = df_envios['TELEFONE_ENVIO'].astype(str).str.replace(r'^\s*55', '', regex=True).str.replace(r'\.0$', '', regex=True).str.strip()

        # Converter DATA_ENVIO para datetime
        df_envios['DATA_ENVIO'] = pd.to_datetime(df_envios['DATA_ENVIO'], errors='coerce', dayfirst=True)
        df_envios.dropna(subset=['DATA_ENVIO'], inplace=True)

        # Remover duplicatas de envios para o mesmo telefone na mesma data
        df_envios.drop_duplicates(subset=['TELEFONE_ENVIO', 'DATA_ENVIO'], inplace=True)

        return df_envios
    except Exception as e:
        st.error(f"Erro ao processar arquivo de Envios: {e}")
        return None

@st.cache_data
def preprocessar_pagamentos(uploaded_file):
    """Processa o arquivo de pagamentos (CSV ou XLSX)."""
    try:
        file_extension = uploaded_file.name.split('.')[-1].lower()
        df_pagamentos = None

        if file_extension == 'csv':
            # Tentar diferentes codificações para CSV
            encodings = ['latin1', 'utf-8', 'cp1252']
            for encoding in encodings:
                try:
                    df_pagamentos = pd.read_csv(
                        uploaded_file,
                        sep=';', # Força o delimitador para ponto e vírgula
                        decimal=',', # Força a vírgula como separador decimal
                        encoding=encoding,
                        on_bad_lines='skip' # Ignora linhas mal formatadas
                    )
                    # Se a leitura for bem-sucedida, sair do loop
                    break 
                except Exception:
                    continue
            if df_pagamentos is None:
                st.error("Não foi possível ler o arquivo CSV com as codificações tentadas (latin1, utf-8, cp1252).")
                return None
        elif file_extension == 'xlsx':
            df_pagamentos = pd.read_excel(uploaded_file, engine='openpyxl')
        else:
            st.error("Formato de arquivo de pagamentos não suportado. Use .csv ou .xlsx.")
            return None

        # Limpar linhas completamente vazias
        df_pagamentos.dropna(how='all', inplace=True)

        # Colunas esperadas e renomeadas (com tratamento para caracteres especiais)
        # Normaliza os nomes das colunas para remover espaços e caracteres especiais antes de procurar
        df_pagamentos.columns = [col.strip().replace(' ', '_').replace('º', '').replace('°', '').replace('ç', 'c').replace('ã', 'a').replace('ú', 'u').replace('á', 'a').replace('é', 'e').replace('í', 'i').replace('ó', 'o').replace('ü', 'u').replace('ñ', 'n').replace('.', '').replace('(', '').replace(')', '').replace('/', '').replace('\\', '').replace('-', '_') for col in df_pagamentos.columns]

        col_matricula = 'N_Ligacao' # Após normalização de 'Nº Ligação'
        col_data_pagto = 'Data_Pagto' # Após normalização de 'Data Pagto.'
        col_valor_autenticado = 'Val_Autenticado' # Após normalização de 'Val. Autenticado'

        if col_matricula not in df_pagamentos.columns or \
           col_data_pagto not in df_pagamentos.columns or \
           col_valor_autenticado not in df_pagamentos.columns:
            st.error(f"Arquivo de Pagamentos: Colunas esperadas '{col_matricula}', '{col_data_pagto}' ou '{col_valor_autenticado}' não encontradas após normalização dos nomes.")
            st.write("Colunas disponíveis:", df_pagamentos.columns.tolist())
            return None

        df_pagamentos = df_pagamentos[[col_matricula, col_data_pagto, col_valor_autenticado]].copy()
        df_pagamentos.rename(columns={
            col_matricula: 'MATRICULA_PAGAMENTO',
            col_data_pagto: 'DATA_PAGAMENTO',
            col_valor_autenticado: 'VALOR_PAGO'
        }, inplace=True)

        # Normalizar matrícula: remover '.0'
        df_pagamentos['MATRICULA_PAGAMENTO'] = df_pagamentos['MATRICULA_PAGAMENTO'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()

        # Converter DATA_PAGAMENTO para datetime
        df_pagamentos['DATA_PAGAMENTO'] = pd.to_datetime(df_pagamentos['DATA_PAGAMENTO'], errors='coerce', dayfirst=True)
        df_pagamentos.dropna(subset=['DATA_PAGAMENTO'], inplace=True)

        # Converter VALOR_PAGO para numérico
        # Já tratamos vírgula como decimal no read_csv, mas para excel ou caso haja erro
        df_pagamentos['VALOR_PAGO'] = pd.to_numeric(
            df_pagamentos['VALOR_PAGO'].astype(str).str.replace('.', '', regex=False).str.replace(',', '.', regex=False),
            errors='coerce'
        )
        df_pagamentos.dropna(subset=['VALOR_PAGO'], inplace=True)
        df_pagamentos = df_pagamentos[df_pagamentos['VALOR_PAGO'] > 0] # Considerar apenas pagamentos com valor > 0

        return df_pagamentos
    except Exception as e:
        st.error(f"Erro ao processar arquivo de Pagamentos: {e}")
        return None

@st.cache_data
def preprocessar_identificacao(uploaded_file):
    """Processa o arquivo de identificação de clientes."""
    try:
        df_identificacao = pd.read_excel(uploaded_file, engine='openpyxl')

        # Limpar linhas completamente vazias
        df_identificacao.dropna(how='all', inplace=True)

        # Colunas esperadas e renomeadas
        col_telefone = 'TELEFONE'
        col_matricula = 'MATRICULA'

        if col_telefone not in df_identificacao.columns or col_matricula not in df_identificacao.columns:
            st.error(f"Arquivo de Identificação: Colunas esperadas '{col_telefone}' ou '{col_matricula}' não encontradas.")
            return None

        df_identificacao = df_identificacao[[col_telefone, col_matricula]].copy()
        df_identificacao.rename(columns={
            col_telefone: 'TELEFONE_CLIENTE',
            col_matricula: 'MATRICULA_CLIENTE'
        }, inplace=True)

        # Normalizar telefone e matrícula: remover '.0'
        df_identificacao['TELEFONE_CLIENTE'] = df_identificacao['TELEFONE_CLIENTE'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
        df_identificacao['MATRICULA_CLIENTE'] = df_identificacao['MATRICULA_CLIENTE'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()

        df_identificacao.drop_duplicates(subset=['TELEFONE_CLIENTE', 'MATRICULA_CLIENTE'], inplace=True)

        return df_identificacao
    except Exception as e:
        st.error(f"Erro ao processar arquivo de Identificação: {e}")
        return None

# --- Interface do Streamlit ---

with st.sidebar:
    st.header("Upload de Arquivos")
    uploaded_file_envios = st.file_uploader("1. Upload Base de Envios (.xlsx)", type=["xlsx"])
    uploaded_file_pagamentos = st.file_uploader("2. Upload Base de Pagamentos (.csv ou .xlsx)", type=["csv", "xlsx"])
    uploaded_file_identificacao = st.file_uploader("3. Upload Base de Identificação de Clientes (.xlsx)", type=["xlsx"])

    st.header("Configurações da Análise")
    janela_dias = st.slider("Janela de dias para considerar o pagamento após a notificação", 1, 30, 7)

    st.markdown("---")
    if st.button("Executar Análise"):
        if uploaded_file_envios and uploaded_file_pagamentos and uploaded_file_identificacao:
            st.info("Processando arquivos, por favor aguarde...")

            df_envios = preprocessar_envios(uploaded_file_envios)
            df_pagamentos = preprocessar_pagamentos(uploaded_file_pagamentos)
            df_identificacao = preprocessar_identificacao(uploaded_file_identificacao)

            if df_envios is not None and df_pagamentos is not None and df_identificacao is not None:
                st.success("Arquivos processados com sucesso!")

                # 1. Cruzar Envios com Identificação (por telefone)
                df_envios_com_matricula = pd.merge(
                    df_envios,
                    df_identificacao,
                    left_on='TELEFONE_ENVIO',
                    right_on='TELEFONE_CLIENTE',
                    how='inner' # Apenas envios que podem ser associados a uma matrícula
                )
                # Remover colunas redundantes e duplicatas após o merge
                df_envios_com_matricula.drop(columns=['TELEFONE_CLIENTE'], inplace=True)
                df_envios_com_matricula.drop_duplicates(subset=['MATRICULA_CLIENTE', 'DATA_ENVIO'], inplace=True)

                total_clientes_notificados = df_envios_com_matricula['MATRICULA_CLIENTE'].nunique()

                if df_envios_com_matricula.empty:
                    st.warning("Nenhum envio pôde ser associado a uma matrícula de cliente. Verifique os dados de telefone na base de envios e identificação.")
                    st.metric(label="Total de Clientes Notificados (com Matrícula)", value="0")
                    st.metric(label="Clientes que Pagaram dentro da Janela", value="0")
                    st.metric(label="Valor Total Arrecadado na Campanha", value="R$ 0,00")
                    st.metric(label="Taxa de Eficiência da Campanha", value="0,00%")
                    st.stop()

                # 2. Cruzar com Pagamentos (por matrícula)
                df_analise = pd.merge(
                    df_envios_com_matricula,
                    df_pagamentos,
                    left_on='MATRICULA_CLIENTE',
                    right_on='MATRICULA_PAGAMENTO',
                    how='left' # Manter todos os envios, mesmo que não haja pagamento
                )
                # Remover coluna redundante
                df_analise.drop(columns=['MATRICULA_PAGAMENTO'], inplace=True)

                # Calcular a data limite para o pagamento
                df_analise['DATA_LIMITE_PAGAMENTO'] = df_analise['DATA_ENVIO'] + timedelta(days=janela_dias)

                # Filtrar pagamentos dentro da janela
                pagamentos_campanha = df_analise[
                    (df_analise['DATA_PAGAMENTO'].notna()) &
                    (df_analise['DATA_PAGAMENTO'] >= df_analise['DATA_ENVIO']) &
                    (df_analise['DATA_PAGAMENTO'] <= df_analise['DATA_LIMITE_PAGAMENTO'])
                ].copy() # Usar .copy() para evitar SettingWithCopyWarning

                # Agrupar pagamentos por cliente e notificação para somar valores e contar clientes únicos
                # Considerar que um cliente pode ter sido notificado e pago mais de uma vez dentro da janela
                # Cada linha aqui representa um pagamento válido dentro da janela para uma notificação específica

                # Para evitar contagem duplicada de clientes se pagou mais de uma vez para a mesma notificação
                clientes_que_pagaram = pagamentos_campanha['MATRICULA_CLIENTE'].nunique()
                valor_total_arrecadado = pagamentos_campanha['VALOR_PAGO'].sum()

                taxa_eficiencia = (clientes_que_pagaram / total_clientes_notificados) * 100 if total_clientes_notificados > 0 else 0

                st.header("Resultados da Análise")
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric(label="Total de Clientes Notificados (com Matrícula)", value=f"{total_clientes_notificados}")
                with col2:
                    st.metric(label="Clientes que Pagaram dentro da Janela", value=f"{clientes_que_pagaram}")
                with col3:
                    st.metric(label="Valor Total Arrecadado na Campanha", value=f"R$ {valor_total_arrecadado:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
                with col4:
                    st.metric(label="Taxa de Eficiência da Campanha", value=f"{taxa_eficiencia:,.2f}%".replace(",", "X").replace(".", ",").replace("X", "."))

                st.subheader("Detalhes dos Pagamentos Atribuídos à Campanha")
                if not pagamentos_campanha.empty:
                    # Selecionar e ordenar colunas para exibição e download
                    pagamentos_detalhe = pagamentos_campanha[[
                        'MATRICULA_CLIENTE', 'TELEFONE_ENVIO', 'DATA_ENVIO',
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
