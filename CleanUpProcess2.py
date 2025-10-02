import streamlit as st
import pandas as pd
import tabula
import io
import os

# --- 1. Configuração da Página ---
st.set_page_config(
    page_title="PDF para Excel (Em Memória) com Streamlit",
    layout="wide"
)

st.title("📄 PDF para DataFrame (Excel) em Memória")
st.markdown("Esta aplicação importa tabelas de um PDF para um objeto **Pandas DataFrame** em memória, simulando a conversão para um ficheiro Excel sem a necessidade de o descarregar. O processamento usa `tabula-py`.")

# --- 2. Gestão de Estado (Simulação de 'Memória' do Excel) ---
# O Streamlit é stateless. Usamos st.session_state para armazenar
# o DataFrame gerado entre as interações do utilizador.
if 'df_excel' not in st.session_state:
    st.session_state['df_excel'] = None
if 'df_extracted' not in st.session_state:
    st.session_state['df_extracted'] = None

# --- 3. Funções de Processamento ---

@st.cache_data(show_spinner="A processar PDF (Requer Java)...")
def convert_pdf_to_dataframe(pdf_file_bytes):
    """
    Lê os bytes do PDF e retorna um DataFrame consolidado.
    Esta função é decorada para evitar reprocessar o ficheiro desnecessariamente.
    """
    try:
        # Lê o ficheiro PDF em memória
        pdf_bytes = io.BytesIO(pdf_file_bytes)
        
        # Extrai todas as tabelas de todas as páginas
        # stream=True é bom para PDFs com linhas delimitadas
        list_of_dfs = tabula.read_pdf(pdf_bytes, pages='all', multiple_tables=True, stream=True)
        
        if not list_of_dfs:
            st.error("❌ Nenhuma tabela foi encontrada no PDF. Tente com outro ficheiro ou ajuste as opções de extração.")
            return None
            
        # Concatena todos os DataFrames em um único "Excel em memória"
        final_df = pd.concat(list_of_dfs, ignore_index=True)
        return final_df
        
    except Exception as e:
        # Apanha erros comuns, como a falta do Java JRE
        if "No Java Runtime Environment (JRE) found" in str(e):
            st.error("❌ **ERRO CRÍTICO:** O 'tabula-py' requer o **Java Runtime Environment (JRE)** instalado. Verifique o seu ambiente.")
        else:
            st.error(f"❌ Erro inesperado durante a conversão: {e}")
        return None

def extract_columns(df, columns_to_extract):
    """Extrai as colunas desejadas do DataFrame principal."""
    try:
        # Lógica de extração: o coração do seu "fluxo de Excel gerado"
        extracted_df = df[columns_to_extract].copy()
        return extracted_df
    except KeyError as e:
        st.error(f"❌ Erro: Coluna não encontrada. Verifique o nome da coluna: {e}")
        return None

# --- 4. Interface do Streamlit (Fluxo) ---

# --- Passo 1: Upload e Conversão ---
st.header("1. Importar e Converter PDF")
uploaded_file = st.file_uploader("Selecione um ficheiro PDF para conversão", type="pdf")

if uploaded_file is not None:
    # Mostra um spinner enquanto processa, mas só se for um novo upload ou não estiver em cache
    if st.session_state['df_excel'] is None or uploaded_file.name != st.session_state.get('last_file_name'):
        st.session_state['last_file_name'] = uploaded_file.name
        
        # Passa o conteúdo do ficheiro (bytes) para a função de cache
        df_result = convert_pdf_to_dataframe(uploaded_file.read())
        
        if df_result is not None:
            st.session_state['df_excel'] = df_result
            st.session_state['df_extracted'] = None # Limpa a extração anterior
            st.success(f"✅ Conversão concluída! DataFrame (Excel em Memória) criado com sucesso com **{len(df_result)}** linhas e **{len(df_result.columns)}** colunas.")

# --- Passo 2: Visualizar e Extrair Colunas Desejadas ---
if st.session_state['df_excel'] is not None:
    df = st.session_state['df_excel']
    st.header("2. Trabalhar com o 'Excel Gerado' (DataFrame em Memória)")
    
    # Exibe as primeiras linhas do "Excel"
    st.subheader("Pré-visualização do DataFrame Completo")
    st.info(f"O seu DataFrame tem {len(df)} linhas. Aqui estão as primeiras 5.")
    st.dataframe(df.head(), use_container_width=True)
    
    # Seleção de Colunas
    st.subheader("Extrair Colunas")
    
    # Dropdown para selecionar as colunas. Permite seleção múltipla.
    available_columns = df.columns.tolist()
    columns_to_extract = st.multiselect(
        "Selecione as colunas que deseja extrair para o fluxo:",
        options=available_columns,
        default=available_columns # Seleciona todas por padrão
    )
    
    # Botão para iniciar o fluxo de extração
    if st.button("Executar Fluxo de Extração"):
        if columns_to_extract:
            df_extracted = extract_columns(df, columns_to_extract)
            if df_extracted is not None:
                st.session_state['df_extracted'] = df_extracted
                st.success("✅ Extração de colunas concluída. O novo DataFrame está pronto!")
        else:
            st.warning("⚠️ Por favor, selecione pelo menos uma coluna para extrair.")

# --- Passo 3: Apresentar o Resultado Final ---
if st.session_state['df_extracted'] is not None:
    df_final = st.session_state['df_extracted']
    st.header("3. Resultado Final do Fluxo")
    
    st.dataframe(df_final, use_container_width=True)
    
    # Opção para Download (Opcional, mas útil para testes)
    csv_buffer = io.StringIO()
    df_final.to_csv(csv_buffer, index=False)
    st.download_button(
        label="Descarregar Resultado (CSV)",
        data=csv_buffer.getvalue(),
        file_name="dados_extraidos.csv",
        mime="text/csv"
    )