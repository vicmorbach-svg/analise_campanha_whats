import streamlit as st
import pandas as pd
from datetime import timedelta

def preprocessar_notificacoes(df_notificacoes):
    """
    Pré-processa o DataFrame de notificações.
    Extrai o número de telefone do campo 'To' e converte a data de envio.
    """
    st.write("Pré-processando notificações...")
    # Remove linhas completamente vazias
    df_notificacoes = df_notificacoes.dropna(how='all')

    # Renomeia a coluna 'To' para 'ID_Cliente' e 'Send At' para 'Data_Envio_Notificacao'
    # Converte o número de telefone para string e remove o prefixo '55' se existir
    if 'To' in df_notificacoes.columns:
        df_notificacoes['ID_Cliente'] = df_notificacoes['To'].astype(str).str.replace(r'^\d{2}', '', regex=True).str.replace(r'\.0$', '', regex=True)
    else:
        st.error("Coluna 'To' não encontrada no arquivo de notificações. Verifique o cabeçalho.")
        return pd.DataFrame()

    if 'Send At' in df_notificacoes.columns:
        df_notificacoes['Data_Envio_Notificacao'] = pd.to_datetime(df_notificacoes['Send At'], format='%d/%m/%Y %H:%M:%S', errors='coerce')
    else:
        st.error("Coluna 'Send At' não encontrada no arquivo de notificações. Verifique o cabeçalho.")
        return pd.DataFrame()

    # Filtra apenas as colunas necessárias e remove linhas com datas inválidas
    df_notificacoes = df_notificacoes[['ID_Cliente', 'Data_Envio_Notificacao']].dropna(subset=['Data_Envio_Notificacao'])
    st.success(f"Notificações pré-processadas. Total de registros válidos: {len(df_notificacoes)}")
    return df_notificacoes

def preprocessar_pagamentos(df_pagamentos):
    """
    Pré-processa o DataFrame de pagamentos.
    Converte o ID do cliente e a data de pagamento.
    """
    st.write("Pré-processando pagamentos...")
    # Remove linhas completamente vazias
    df_pagamentos = df_pagamentos.dropna(how='all')

    # Renomeia as colunas e trata os dados
    # A coluna 'Nє Ligaзгo' parece ser o ID do cliente
    if 'Nє Ligaзгo' in df_pagamentos.columns:
        df_pagamentos['ID_Cliente'] = df_pagamentos['Nє Ligaзгo'].astype(str).str.replace(r'\.0$', '', regex=True)
    else:
        st.error("Coluna 'Nє Ligaзгo' não encontrada no arquivo de pagamentos. Verifique o cabeçalho.")
        return pd.DataFrame()

    if 'Data Pagto.' in df_pagamentos.columns:
        df_pagamentos['Data_Pagamento'] = pd.to_datetime(df_pagamentos['Data Pagto.'], format='%d/%m/%Y', errors='coerce')
    else:
        st.error("Coluna 'Data Pagto.' não encontrada no arquivo de pagamentos. Verifique o cabeçalho.")
        return pd.DataFrame()

    if 'Valor Pago' in df_pagamentos.columns:
        # Tenta converter 'Valor Pago', tratando vírgulas como separador decimal e removendo pontos de milhar
        df_pagamentos['Valor_Pago'] = df_pagamentos['Valor Pago'].astype(str).str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
        df_pagamentos['Valor_Pago'] = pd.to_numeric(df_pagamentos['Valor_Pago'], errors='coerce').fillna(0)
    else:
        st.error("Coluna 'Valor Pago' não encontrada no arquivo de pagamentos. Verifique o cabeçalho.")
        return pd.DataFrame()

    # Filtra apenas as colunas necessárias e remove linhas com datas inválidas ou IDs vazios
    df_pagamentos = df_pagamentos[['ID_Cliente', 'Data_Pagamento', 'Valor_Pago']].dropna(subset=['Data_Pagamento', 'ID_Cliente'])
    # Remove pagamentos com valor zero, a menos que sejam relevantes para a análise de "não pago"
    df_pagamentos = df_pagamentos[df_pagamentos['Valor_Pago'] > 0]

    st.success(f"Pagamentos pré-processados. Total de registros válidos: {len(df_pagamentos)}")
    return df_pagamentos

def analisar_eficiencia_campanha(df_notificacoes, df_pagamentos, janela_dias):
    """
    Analisa a eficiência de uma campanha de cobrança.
    """
    st.subheader("Iniciando análise da campanha...")

    # Garante que os IDs de cliente sejam do mesmo tipo para o merge
    df_notificacoes['ID_Cliente'] = df_notificacoes['ID_Cliente'].astype(str)
    df_pagamentos['ID_Cliente'] = df_pagamentos['ID_Cliente'].astype(str)

    # Realiza o merge das notificações com os pagamentos
    # Usamos um merge 'left' para manter todos os clientes notificados
    df_analise = pd.merge(
        df_notificacoes,
        df_pagamentos,
        on='ID_Cliente',
        how='left'
    )

    # Calcula a data limite para o pagamento ser considerado da campanha
    df_analise['Data_Limite_Pagamento'] = df_analise['Data_Envio_Notificacao'] + timedelta(days=janela_dias)

    # Identifica se o pagamento ocorreu dentro da janela
    df_analise['Pagamento_Dentro_Janela'] = (
        (df_analise['Data_Pagamento'] >= df_analise['Data_Envio_Notificacao']) &
        (df_analise['Data_Pagamento'] <= df_analise['Data_Limite_Pagamento'])
    )

    # Remove pagamentos que não estão dentro da janela ou que não têm data de pagamento
    # Para a análise de "pagamentos da campanha", só nos interessam os que se encaixam
    df_pagamentos_campanha = df_analise[df_analise['Pagamento_Dentro_Janela']].copy()

    # Agrupa por cliente para evitar contagem duplicada de notificações para múltiplos pagamentos
    clientes_notificados_unicos = df_notificacoes['ID_Cliente'].nunique()
    pagamentos_dentro_janela_unicos = df_pagamentos_campanha['ID_Cliente'].nunique()
    valor_total_pago_campanha = df_pagamentos_campanha['Valor_Pago'].sum()

    st.subheader("Resultados da Análise:")
    st.write(f"Total de clientes notificados: **{clientes_notificados_unicos}**")
    st.write(f"Clientes que pagaram dentro da janela de {janela_dias} dias: **{pagamentos_dentro_janela_unicos}**")
    st.write(f"Valor total pago atribuído à campanha: **R$ {valor_total_pago_campanha:,.2f}**")

    if clientes_notificados_unicos > 0:
        taxa_eficiencia = (pagamentos_dentro_janela_unicos / clientes_notificados_unicos) * 100
        st.write(f"Taxa de eficiência da campanha (clientes que pagaram): **{taxa_eficiencia:.2f}%**")
    else:
        st.write("Não há clientes notificados para calcular a taxa de eficiência.")

    st.subheader("Detalhes dos Pagamentos Atribuídos à Campanha:")
    if not df_pagamentos_campanha.empty:
        st.dataframe(df_pagamentos_campanha[['ID_Cliente', 'Data_Envio_Notificacao', 'Data_Pagamento', 'Valor_Pago', 'Pagamento_Dentro_Janela']])
    else:
        st.info("Nenhum pagamento encontrado dentro da janela da campanha.")

    return df_pagamentos_campanha

# --- Streamlit App ---
st.set_page_config(layout="wide")
st.title("Análise de Eficiência de Campanha de Cobrança")

st.markdown("""
Este aplicativo permite analisar a eficiência de uma campanha de cobrança
cruzando dados de notificações (WhatsApp) com dados de pagamentos.
""")

# Upload de arquivos
st.sidebar.header("Upload de Arquivos")
uploaded_file_notificacoes = st.sidebar.file_uploader("Selecione o arquivo de Notificações (Excel)", type=["xlsx"])
uploaded_file_pagamentos = st.sidebar.file_uploader("Selecione o arquivo de Pagamentos (CSV)", type=["csv"])

janela_dias = st.sidebar.slider("Defina a janela de dias para considerar o pagamento da campanha:", 1, 30, 7)

if uploaded_file_notificacoes and uploaded_file_pagamentos:
    st.success("Arquivos carregados com sucesso!")

    # Carregar e pré-processar notificações
    try:
        df_notificacoes_raw = pd.read_excel(uploaded_file_notificacoes)
        df_notificacoes = preprocessar_notificacoes(df_notificacoes_raw)
        if not df_notificacoes.empty:
            st.sidebar.write("Pré-visualização Notificações:")
            st.sidebar.dataframe(df_notificacoes.head())
            # Salvar em Parquet (opcional, aqui apenas para demonstração de conceito)
            # df_notificacoes.to_parquet("notificacoes.parquet", index=False)
            # st.sidebar.write("Notificações salvas em formato Parquet (na memória).")
        else:
            st.error("Erro ao pré-processar o arquivo de notificações. Verifique o formato das colunas.")
            st.stop()
    except Exception as e:
        st.error(f"Erro ao ler ou pré-processar o arquivo de notificações: {e}")
        st.stop()

    # Carregar e pré-processar pagamentos
    try:
        # Tenta ler o CSV com diferentes delimitadores se o padrão falhar
        try:
            df_pagamentos_raw = pd.read_csv(uploaded_file_pagamentos, sep=';', encoding='latin1')
        except Exception:
            uploaded_file_pagamentos.seek(0) # Reset file pointer
            df_pagamentos_raw = pd.read_csv(uploaded_file_pagamentos, sep=',', encoding='latin1')

        df_pagamentos = preprocessar_pagamentos(df_pagamentos_raw)
        if not df_pagamentos.empty:
            st.sidebar.write("Pré-visualização Pagamentos:")
            st.sidebar.dataframe(df_pagamentos.head())
            # Salvar em Parquet (opcional)
            # df_pagamentos.to_parquet("pagamentos.parquet", index=False)
            # st.sidebar.write("Pagamentos salvos em formato Parquet (na memória).")
        else:
            st.error("Erro ao pré-processar o arquivo de pagamentos. Verifique o formato das colunas.")
            st.stop()
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
            st.warning("Certifique-se de que ambos os arquivos foram carregados e pré-processados corretamente.")
