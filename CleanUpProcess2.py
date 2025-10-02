import streamlit as st
import pandas as pd
import pdfplumber
import io
import numpy as np
from fuzzywuzzy import fuzz
from fuzzywuzzy import process

# --- 1. Configuração e Gestão de Estado ---
st.set_page_config(
    page_title="PDF para Excel (Em Memória) com Busca Dinâmica",
    layout="wide"
)

st.title("📄 PDF para DataFrame (Excel) em Memória com Busca Dinâmica")
st.markdown("A aplicação converte o PDF para um DataFrame ('Excel em Memória') e permite a busca por similaridade em **todas as células**. Ao encontrar a célula com a palavra-chave, retorna o valor da célula imediatamente abaixo.")

# Inicialização do estado para persistir o DataFrame
if 'df_excel' not in st.session_state:
    st.session_state['df_excel'] = None

# --- 2. Funções de Processamento ---

@st.cache_data(show_spinner="A converter PDF para DataFrame (Excel em Memória)...")
def convert_pdf_to_dataframe(pdf_file_bytes):
    """
    Lê os bytes do PDF e retorna um DataFrame consolidado, usando pdfplumber.
    """
    list_of_dfs = []
    
    try:
        with pdfplumber.open(io.BytesIO(pdf_file_bytes)) as pdf:
            for page in pdf.pages:
                tabelas_pagina = page.extract_tables() 
                
                for table in tabelas_pagina:
                    # Garantir que a tabela não está vazia
                    if table and len(table) > 1 and table[0] is not None:
                        # O primeiro elemento é o cabeçalho, o resto são os dados
                        # Nota: Em tabelas muito soltas, pode ser necessário forçar a atribuição de nomes de colunas
                        try:
                            df = pd.DataFrame(table[1:], columns=table[0])
                        except ValueError:
                            # Caso o número de cabeçalhos não corresponda ao número de colunas
                            st.warning("⚠️ Ajuste de colunas necessário: usando a primeira linha como cabeçalho de fallback.")
                            df = pd.DataFrame(table[1:])
                            df.columns = [f'Col_{i}' for i in range(len(df.columns))]

                        list_of_dfs.append(df)
        
        if not list_of_dfs:
            st.error("❌ Nenhuma tabela foi encontrada no PDF.")
            return None
            
        final_df = pd.concat(list_of_dfs, ignore_index=True)
        final_df.dropna(how='all', inplace=True) 
        return final_df
        
    except Exception as e:
        st.error(f"❌ Erro inesperado durante a conversão: {e}")
        return None

def dynamic_fuzzy_search(df, user_query, threshold=85):
    """
    Busca por similaridade em TODAS as células do DataFrame.
    Retorna o valor da célula imediatamente abaixo da melhor correspondência.
    """
    best_score = -1
    best_location = None  # (row_index, col_name)

    # Iterar sobre todas as colunas
    for col_name in df.columns:
        # Iterar sobre todas as linhas da coluna (index é o índice da linha)
        for index, cell_value in df[col_name].items():
            if pd.isna(cell_value):
                continue
            
            # Compara a query com o valor da célula
            score = fuzz.ratio(str(cell_value).lower(), user_query.lower())
            
            if score > best_score and score >= threshold:
                best_score = score
                best_location = (index, col_name)
    
    if best_location:
        row_index, col_name = best_location
        
        # O valor desejado está na mesma coluna (col_name) mas na linha seguinte (row_index + 1)
        next_row_index = row_index + 1
        
        if next_row_index < len(df):
            # Usamos .loc para aceder ao valor pela linha e nome da coluna
            value_below = df.loc[next_row_index, col_name]
            
            return {
                'found_at_value': df.loc[row_index, col_name],
                'column': col_name,
                'row_found': row_index + 1, # +1 para ser compatível com o número de linha Excel
                'value_below': value_below,
                'score': best_score
            }
        else:
            return {'error': f'Correspondência encontrada em '{df.loc[row_index, col_name]}', mas é a última linha e não há célula abaixo para retornar.'}
    
    return {'error': f'Nenhuma correspondência com similaridade acima de {threshold}% encontrada para a busca: "{user_query}".'}


# --- 3. Interface do Streamlit (Fluxo) ---

# --- A. Upload e Conversão ---
st.header("1. Importar e Converter PDF")
uploaded_file = st.file_uploader("Selecione um ficheiro PDF para conversão", type="pdf")

if uploaded_file is not None:
    if st.session_state['df_excel'] is None or uploaded_file.name != st.session_state.get('last_file_name'):
        st.session_state['last_file_name'] = uploaded_file.name
        
        df_result = convert_pdf_to_dataframe(uploaded_file.read())
        
        if df_result is not None:
            st.session_state['df_excel'] = df_result
            st.success(f"✅ Conversão concluída! O 'Excel em Memória' foi criado com **{len(df_result)}** linhas.")

# --- B. Busca Dinâmica (Fuzzy) ---
if st.session_state['df_excel'] is not None:
    df = st.session_state['df_excel']
    
    st.markdown("---")
    st.header("2. Busca Dinâmica no 'Excel em Memória' (Qualquer Célula → Célula Abaixo)")
    st.markdown("Atenção: Esta busca é feita em **todas as células**. Com DataFrames muito grandes, pode levar alguns segundos.")

    # Área de input para a busca
    search_query = st.text_input(
        "Qual a palavra-chave a buscar?",
        key="dynamic_search_input",
        placeholder="Ex: Ponto de Partida, Fim de Fibra"
    )

    if st.button("Executar Busca Dinâmica e Retornar Valor Abaixo"):
        if search_query:
            # Chama a nova função de busca dinâmica
            result = dynamic_fuzzy_search(df, search_query)

            if 'value_below' in result:
                st.success(f"✅ Palavra-chave Encontrada! (Similaridade: {result['score']}%)")
                
                st.subheader(f"Valor Retornado da Célula Abaixo:")
                st.markdown(f"**Palavra-chave '{result['found_at_value']}' encontrada na Linha {result['row_found']}, Coluna '{result['column']}'.**")
                st.markdown("O **valor imediatamente abaixo** na mesma coluna é:")
                
                st.code(str(result['value_below']), language='text')

            elif 'error' in result:
                st.warning(f"⚠️ {result['error']}")
        else:
            st.warning("Por favor, introduza a palavra-chave para buscar.")

    # Exibe o DataFrame para contexto
    if st.checkbox("Mostrar o 'Excel em Memória' completo"):
        st.dataframe(df, use_container_width=True)