import streamlit as st
import pandas as pd
import io
import re

# Função para normalizar nomes de colunas
def normalize_column_name(col_name):
    col_name = col_name.lower()
    col_name = re.sub(r'[^\w\s]', '', col_name) # Remove caracteres especiais
    col_name = re.sub(r'\s+', '_', col_name) # Substitui espaços por underscores
    return col_name

# Função para carregar e processar o arquivo de notificações
def load_and_process_notifications(uploaded_file):
    if uploaded_file.name.endswith('.xlsx'):
        df = pd.read_excel(uploaded_file)
    else:
        st.error("Por favor, carregue um arquivo .xlsx para as notificações.")
        return None

    # Normalizar nomes de colunas
    df.columns = [normalize_column_name(col) for col in df.columns]

    # Mapear e renomear colunas essenciais
    required_cols = {
        'to': 'id_cliente',
        'send_at': 'data_envio'
    }
    df = df.rename(columns=required_cols)

    # Verificar se as colunas essenciais existem após o renomeio
    if 'id_cliente' not in df.columns or 'data_envio' not in df.columns:
        st.error(f"As colunas 'To' e 'Send At' (ou suas versões normalizadas) são obrigatórias no arquivo de notificações.")
        return None

    # Limpar IDs de cliente (remover .0 se for float)
    df['id_cliente'] = df['id_cliente'].astype(str).str.replace(r'\.0$', '', regex=True)

    # Converter 'data_envio' para datetime
    df['data_envio'] = pd.to_datetime(df['data_envio'], errors='coerce', dayfirst=True)
    df = df.dropna(subset=['data_envio'])

    # Remover duplicatas de notificações para o mesmo cliente na mesma data
    df = df.drop_duplicates(subset=['id_cliente', 'data_envio'])

    return df

# Função para carregar e processar o arquivo de pagamentos
def load_and_process_payments(uploaded_file):
    if uploaded_file.name.endswith('.xlsx'):
        df = pd.read_excel(uploaded_file)
    elif uploaded_file.name.endswith('.csv'):
        # Tentar ler CSV com diferentes delimitadores
        try:
            df = pd.read_csv(uploaded_file, sep=';', encoding='latin1', on_bad_lines='skip')
        except Exception:
            uploaded_file.seek(0) # Resetar o ponteiro do arquivo
            try:
                df = pd.read_csv(uploaded_file, sep=',', encoding='latin1', on_bad_lines='skip')
            except Exception as e:
                st.error(f"Erro ao ler o arquivo CSV de pagamentos: {e}. Verifique o delimitador e a codificação.")
                return None
    else:
        st.error("Por favor, carregue um arquivo .xlsx ou .csv para os pagamentos.")
        return None

    # Normalizar nomes de colunas
    df.columns = [normalize_column_name(col) for col in df.columns]

    # Mapear e renomear colunas essenciais
    required_cols = {
        'n_ligaзгo': 'id_cliente', # Coluna 'Nє Ligaзгo'
        'data_pagto': 'data_pagamento', # Coluna 'Data Pagto.'
        'valor_pago': 'valor_pago' # Coluna 'Valor Pago'
    }
    df = df.rename(columns=required_cols)

    # Verificar se as colunas essenciais existem após o renomeio
    if 'id_cliente' not in df.columns or 'data_pagamento' not in df.columns or 'valor_pago' not in df.columns:
        st.error(f"As colunas 'Nє Ligaзгo', 'Data Pagto.' e 'Valor Pago' (ou suas versões normalizadas) são obrigatórias no arquivo de pagamentos.")
        return None

    # Limpar IDs de cliente (remover .0 se for float)
    df['id_cliente'] = df['id_cliente'].astype(str).str.replace(r'\.0$', '', regex=True)

    # Converter 'data_pagamento' para datetime
    df['data_pagamento'] = pd.to_datetime(df['data_pagamento'], errors='coerce', dayfirst=True)
    df = df.dropna(subset=['data_pagamento'])

    # Tratar a coluna 'valor_pago'
    # Remover pontos de milhar e substituir vírgulas por pontos decimais
    df['valor_pago'] = df['valor_pago'].astype(str).str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
    df['valor_pago'] = pd.to_numeric(df['valor_pago'], errors='coerce')
    df = df.dropna(subset=['valor_pago'])

    # Remover linhas onde o valor pago é 0 ou negativo, pois não representam um pagamento efetivo
    df = df[df['valor_pago'] > 0]

    return df

# Configuração da página Streamlit
st.set_page_config(layout="wide", page_title="Análise de Eficiência de Campanha de Cobrança")

st.title("Análise de Eficiência de Campanha de Cobrança via WhatsApp")

st.markdown("""
    Este aplicativo permite que você analise a eficiência de suas campanhas de cobrança via WhatsApp.
    Faça o upload de dois arquivos:
    1.  **Notificações:** Contém os registros de envio das mensagens (colunas `To` e `Send At`).
    2.  **Pagamentos:** Contém os registros de pagamentos dos clientes (colunas `Nє Ligaзгo`, `Data Pagto.` e `Valor Pago`).

    O script irá cruzar as informações, identificar pagamentos que ocorreram dentro de uma janela definida
    após o envio da notificação e calcular os valores envolvidos.
""")

# Barra lateral para uploads e parâmetros
st.sidebar.header("Upload de Arquivos e Parâmetros")

uploaded_notifications_file = st.sidebar.file_uploader(
    "1. Carregue o arquivo de Notificações (.xlsx)",
    type=["xlsx"],
    key="notifications_file"
)

uploaded_payments_file = st.sidebar.file_uploader(
    "2. Carregue o arquivo de Pagamentos (.xlsx ou .csv)",
    type=["xlsx", "csv"],
    key="payments_file"
)

days_window = st.sidebar.slider(
    "3. Defina a janela de dias para considerar o pagamento da campanha:",
    min_value=1,
    max_value=90,
    value=7,
    help="Um pagamento será considerado da campanha se ocorrer até X dias após a data de envio da notificação."
)

if st.sidebar.button("Executar Análise"):
    if uploaded_notifications_file is not None and uploaded_payments_file is not None:
        st.info("Carregando e processando arquivos...")

        df_notifications = load_and_process_notifications(uploaded_notifications_file)
        df_payments = load_and_process_payments(uploaded_payments_file)

        if df_notifications is not None and df_payments is not None:
            st.success("Arquivos carregados e processados com sucesso!")

            # Exibir informações básicas dos DataFrames
            st.subheader("Visão Geral dos Dados Carregados")
            st.write("---")
            st.write("### Notificações (primeiras 5 linhas)")
            st.dataframe(df_notifications.head())
            st.write(f"Total de notificações únicas: {len(df_notifications)}")
            st.write("---")
            st.write("### Pagamentos (primeiras 5 linhas)")
            st.dataframe(df_payments.head())
            st.write(f"Total de pagamentos válidos: {len(df_payments)}")
            st.write("---")

            st.subheader("Realizando o Cruzamento de Dados...")

            # Realizar o merge dos dataframes
            # Usamos um merge externo para manter todos os registros e ver o que não cruzou
            df_merged = pd.merge(df_notifications, df_payments, on='id_cliente', how='left', suffixes=('_notif', '_pagto'))

            # Filtrar pagamentos que ocorreram dentro da janela
            df_merged['dias_para_pagamento'] = (df_merged['data_pagamento'] - df_merged['data_envio']).dt.days

            # Pagamentos da campanha: data_pagamento >= data_envio E dias_para_pagamento <= days_window
            df_campaign_payments = df_merged[
                (df_merged['data_pagamento'] >= df_merged['data_envio']) &
                (df_merged['dias_para_pagamento'] <= days_window)
            ].copy()

            # Remover duplicatas de pagamentos para o mesmo cliente na mesma janela de notificação
            # Se um cliente pagou várias vezes dentro da janela de uma notificação, consideramos o primeiro pagamento válido
            # Ou, se houver múltiplas notificações para o mesmo cliente, e ele pagou, queremos associar ao primeiro envio relevante
            # Para simplificar, vamos considerar cada par (id_cliente, data_envio) como uma "oportunidade" de campanha
            # E para cada oportunidade, o primeiro pagamento dentro da janela.
            # Para a análise de eficiência, o que importa é se HOUVE um pagamento.
            df_campaign_payments_unique = df_campaign_payments.sort_values(by=['id_cliente', 'data_envio', 'data_pagamento']).drop_duplicates(subset=['id_cliente', 'data_envio'])


            st.subheader("Resultados da Análise")
            st.markdown("---")

            total_notificacoes = len(df_notifications)
            total_clientes_notificados = df_notifications['id_cliente'].nunique()

            total_pagamentos_campanha = len(df_campaign_payments_unique)
            clientes_pagaram_campanha = df_campaign_payments_unique['id_cliente'].nunique()
            valor_total_pago_campanha = df_campaign_payments_unique['valor_pago'].sum()

            st.write(f"**Total de Notificações Enviadas:** {total_notificacoes}")
            st.write(f"**Total de Clientes Notificados (únicos):** {total_clientes_notificados}")
            st.write(f"**Janela de Dias Considerada:** {days_window} dias")
            st.markdown("---")

            st.write(f"**Número de Pagamentos Atribuídos à Campanha:** {total_pagamentos_campanha}")
            st.write(f"**Número de Clientes que Pagaram Após a Notificação (dentro da janela):** {clientes_pagaram_campanha}")
            st.write(f"**Valor Total Arrecadado Atribuído à Campanha:** R$ {valor_total_pago_campanha:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
            st.markdown("---")

            if total_clientes_notificados > 0:
                taxa_conversao_clientes = (clientes_pagaram_campanha / total_clientes_notificados) * 100
                st.write(f"**Taxa de Conversão (Clientes):** {taxa_conversao_clientes:.2f}%")
            else:
                st.write("**Taxa de Conversão (Clientes):** Não foi possível calcular (nenhum cliente notificado).")

            st.markdown("---")
            st.subheader("Detalhes dos Pagamentos Atribuídos à Campanha")
            if not df_campaign_payments_unique.empty:
                st.dataframe(df_campaign_payments_unique[[
                    'id_cliente', 'data_envio', 'data_pagamento', 'valor_pago', 'dias_para_pagamento'
                ]].sort_values(by='data_envio'))

                # Opção para download
                csv_output = df_campaign_payments_unique.to_csv(index=False, decimal=',', sep=';', encoding='latin1')
                st.download_button(
                    label="Baixar Pagamentos da Campanha (CSV)",
                    data=csv_output,
                    file_name="pagamentos_campanha.csv",
                    mime="text/csv",
                )
            else:
                st.info("Nenhum pagamento encontrado dentro da janela definida para a campanha.")

        else:
            st.error("Não foi possível processar um ou ambos os arquivos. Verifique os formatos e as colunas esperadas.")
    else:
        st.warning("Por favor, carregue ambos os arquivos para iniciar a análise.")
