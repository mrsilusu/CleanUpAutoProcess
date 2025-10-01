import streamlit as st
import pandas as pd
import pdfplumber
import re
import os
import unicodedata
import io
from datetime import datetime

# -----------------------------
# Configuração da Página
# -----------------------------
st.set_page_config(
    page_title="Clean Up AutoProcess - PDF",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -----------------------------
# Funções Auxiliares
# -----------------------------
def normalize_header(s):
    """Normaliza cabeçalhos para comparação"""
    if s is None:
        return ""
    s = str(s).strip().lower()
    s = unicodedata.normalize("NFD", s)
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    s = re.sub(r"\s+", " ", s)
    return s

def clean_number_str(s):
    """Limpa e extrai números de strings"""
    if s is None:
        return None
    s = str(s).strip()
    s = s.replace(",", ".")
    m = re.search(r"(-?\d+(?:\.\d+)?)", s)
    return m.group(1) if m else None

def extrair_fiber_id(nome_arquivo):
    """Extrai o Fiber ID do nome do arquivo PDF"""
    if nome_arquivo:
        nome_base = os.path.splitext(nome_arquivo)[0]
        return nome_base
    return "Relatorio_OTDR"

def calcular_perda_maxima(distancia, comprimento_onda):
    """Calcula a perda máxima permitida baseada na distância e comprimento de onda"""
    if comprimento_onda == 1310:
        return distancia * 0.33
    elif comprimento_onda == 1550:
        return distancia * 0.22
    else:
        return None

# ==============================
# Conversão PDF para Excel em Memória
# ==============================
def pdf_para_excel_memoria(uploaded_file):
    """Converte PDF para Excel em memória, preservando todas as tabelas"""
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        with pdfplumber.open(uploaded_file) as pdf:
            for page_num, page in enumerate(pdf.pages):
                # Extrair tabelas da página
                tables = page.extract_tables()
                
                for table_num, table in enumerate(tables):
                    if not table or len(table) < 2:
                        continue
                    
                    # Criar DataFrame mantendo estrutura original
                    try:
                        df = pd.DataFrame(table)
                        
                        # Nome da aba
                        sheet_name = f"P{page_num+1}_T{table_num+1}"
                        if len(sheet_name) > 31:
                            sheet_name = sheet_name[:31]
                        
                        # Salvar no Excel (sem cabeçalho para manter estrutura original)
                        df.to_excel(writer, sheet_name=sheet_name, index=False, header=False)
                        
                    except Exception as e:
                        continue
        
        # Se não encontrou tabelas, criar uma aba com o texto extraído
        if not writer.sheets:
            with pdfplumber.open(uploaded_file) as pdf:
                all_text = ""
                for page_num, page in enumerate(pdf.pages):
                    text = page.extract_text()
                    if text:
                        all_text += f"--- Página {page_num+1} ---\n{text}\n\n"
                
                if all_text:
                    df_text = pd.DataFrame({"Texto_Extraido": [all_text]})
                    df_text.to_excel(writer, sheet_name="Texto_Completo", index=False)
    
    output.seek(0)
    return output

# ==============================
# Função MELHORADA: Extrair Fim da Fibra
# ==============================
def extrair_fim_fibra(dataframes):
    """Busca 'Fim da Fibra Km' NAS TABELAS DO EXCEL com múltiplas estratégias"""
    
    st.sidebar.subheader("🔍 Buscando Fim da Fibra")
    
    for df_idx, df in enumerate(dataframes):
        # Converter DataFrame do Excel para busca
        df_str = df.astype(str)
        
        st.sidebar.write(f"**Tabela {df_idx+1}:** {df.shape[1]}x{df.shape[0]}")

        # ESTRATÉGIA 1: Busca direta por "Fim da Fibra Km"
        for row_idx in range(len(df_str)):
            for col_idx in range(len(df_str.columns)):
                celula = df_str.iloc[row_idx, col_idx].strip().lower()
                
                # Busca flexível - várias variações possíveis
                if any(term in celula for term in ["fim da fibra", "fim fibra", "fibra fim"]) and "km" in celula:
                    st.sidebar.success(f"✅ Estratégia 1: Encontrado na linha {row_idx+1}, coluna {col_idx+1}")
                    st.sidebar.info(f"📋 Célula encontrada: '{df_str.iloc[row_idx, col_idx]}'")
                    
                    # ESTRATÉGIA 1A: Valor na LINHA ABAIXO
                    if row_idx + 1 < len(df_str):
                        valor_abaixo = df_str.iloc[row_idx + 1, col_idx].strip()
                        st.sidebar.info(f"🔍 Valor linha abaixo: '{valor_abaixo}'")
                        numero_limpo = clean_number_str(valor_abaixo)
                        
                        if numero_limpo:
                            try:
                                distancia = float(numero_limpo)
                                st.sidebar.success(f"🎯 DISTÂNCIA ENCONTRADA: {distancia} km")
                                return distancia
                            except ValueError:
                                pass
                    
                    # ESTRATÉGIA 1B: Valor na MESMA LINHA (à direita)
                    for right_col in range(col_idx + 1, min(col_idx + 4, len(df_str.columns))):
                        valor_direita = df_str.iloc[row_idx, right_col].strip()
                        if valor_direita:
                            st.sidebar.info(f"🔍 Valor à direita (col {right_col+1}): '{valor_direita}'")
                            numero_limpo = clean_number_str(valor_direita)
                            if numero_limpo:
                                try:
                                    distancia = float(numero_limpo)
                                    st.sidebar.success(f"🎯 DISTÂNCIA ENCONTRADA: {distancia} km")
                                    return distancia
                                except ValueError:
                                    continue
        
        # ESTRATÉGIA 2: Busca por padrão de tabela de resumo
        # Procura por linha que tenha "fiber" no nome e número na coluna de distância
        for row_idx in range(min(5, len(df_str))):  # Só nas primeiras linhas
            linha = df_str.iloc[row_idx].tolist()
            st.sidebar.info(f"🔍 Linha {row_idx+1}: {linha}")
            
            # Verifica se esta linha parece ser um cabeçalho de resumo
            if any("fibra" in str(cel).lower() for cel in linha) or any("fim" in str(cel).lower() for cel in linha):
                st.sidebar.info(f"📋 Possível linha de cabeçalho encontrada na linha {row_idx+1}")
                
                # Procura números nas linhas abaixo
                for next_row in range(row_idx + 1, min(row_idx + 3, len(df_str))):
                    next_linha = df_str.iloc[next_row].tolist()
                    st.sidebar.info(f"🔍 Linha {next_row+1} (abaixo): {next_linha}")
                    
                    for celula in next_linha:
                        numero_limpo = clean_number_str(celula)
                        if numero_limpo:
                            try:
                                num = float(numero_limpo)
                                if 1 < num < 200:  # Faixa plausível para fibra
                                    st.sidebar.success(f"🎯 DISTÂNCIA ENCONTRADA (E2): {num} km")
                                    return num
                            except ValueError:
                                continue

        # ESTRATÉGIA 3: Busca por maiores números na tabela (fallback)
        maiores_numeros = []
        for row_idx in range(len(df_str)):
            for col_idx in range(len(df_str.columns)):
                valor = df_str.iloc[row_idx, col_idx].strip()
                numero_limpo = clean_number_str(valor)
                if numero_limpo:
                    try:
                        num = float(numero_limpo)
                        if 10 < num < 200:  # Faixa plausível para distância de fibra
                            maiores_numeros.append((num, row_idx, col_idx))
                    except ValueError:
                        continue
        
        if maiores_numeros:
            maiores_numeros.sort(reverse=True)
            maior_numero = maiores_numeros[0][0]
            st.sidebar.success(f"🎯 DISTÂNCIA (Fallback - maior número): {maior_numero} km")
            return maior_numero
    
    # ESTRATÉGIA 4: Busca no texto completo como última opção
    st.sidebar.warning("🔍 Estratégia 4: Buscando no texto completo...")
    for df in dataframes:
        texto_completo = " ".join(df.astype(str).values.flatten())
        # Procura por padrões como "60.285 km", "102.027 km", etc.
        padroes = re.findall(r'(\d+\.\d+)\s*km', texto_completo, re.IGNORECASE)
        for padrao in padroes:
            try:
                num = float(padrao)
                if 10 < num < 200:
                    st.sidebar.success(f"🎯 DISTÂNCIA (Regex): {num} km")
                    return num
            except ValueError:
                continue
    
    st.sidebar.error("❌ NENHUMA DISTÂNCIA ENCONTRADA em nenhuma estratégia")
    return None

# ==============================
# Função MELHORADA: Extrair Perda Total
# ==============================
def extrair_perda_total_eventos(dataframes):
    """Extrai perda total e eventos com múltiplas estratégias"""
    
    perda_total = None
    eventos = []
    
    st.sidebar.subheader("📊 Buscando Perda Total")
    
    for df in dataframes:
        df_str = df.astype(str)
        
        # ESTRATÉGIA 1: Busca por "Perda Total dB"
        for row_idx in range(len(df_str)):
            for col_idx in range(len(df_str.columns)):
                celula = df_str.iloc[row_idx, col_idx].strip().lower()
                
                if "perda total" in celula and "db" in celula:
                    st.sidebar.success(f"✅ 'Perda Total dB' encontrado na linha {row_idx+1}, coluna {col_idx+1}")
                    
                    # Procurar valor na mesma linha ou linha abaixo
                    if row_idx + 1 < len(df_str):
                        valor_perda = df_str.iloc[row_idx + 1, col_idx].strip()
                        st.sidebar.info(f"🔍 Valor abaixo: '{valor_perda}'")
                        perda_limpa = clean_number_str(valor_perda)
                        if perda_limpa:
                            try:
                                perda_total = float(perda_limpa)
                                st.sidebar.success(f"📊 PERDA TOTAL: {perda_total} dB")
                                return perda_total, eventos
                            except ValueError:
                                pass
                    
                    # Procurar na mesma linha
                    for right_col in range(col_idx + 1, min(col_idx + 4, len(df_str.columns))):
                        valor_direita = df_str.iloc[row_idx, right_col].strip()
                        if valor_direita:
                            st.sidebar.info(f"🔍 Valor à direita: '{valor_direita}'")
                            perda_limpa = clean_number_str(valor_direita)
                            if perda_limpa:
                                try:
                                    perda_total = float(perda_limpa)
                                    st.sidebar.success(f"📊 PERDA TOTAL: {perda_total} dB")
                                    return perda_total, eventos
                                except ValueError:
                                    continue
    
    # ESTRATÉGIA 2: Busca por números na faixa de perda
    st.sidebar.warning("🔍 Buscando perda por fallback...")
    for df in dataframes:
        df_str = df.astype(str)
        for row_idx in range(len(df_str)):
            for col_idx in range(len(df_str.columns)):
                valor = df_str.iloc[row_idx, col_idx].strip()
                numero_limpo = clean_number_str(valor)
                if numero_limpo:
                    try:
                        num = float(numero_limpo)
                        if 0.1 < num < 50:  # Faixa plausível para perda
                            # Verificar se está perto de texto relacionado a perda
                            celula = df_str.iloc[row_idx, col_idx].lower()
                            if any(term in celula for term in ['db', 'perda', 'loss']):
                                perda_total = num
                                st.sidebar.success(f"📊 PERDA (Fallback): {perda_total} dB")
                                return perda_total, eventos
                    except ValueError:
                        continue
    
    st.sidebar.error("❌ NENHUMA PERDA ENCONTRADA")
    return None, eventos

def determinar_status(distancia_fibra, perda_total, distancia_troco_km, perda_maxima_dB):
    """Determina o status da fibra baseado nos parâmetros"""
    
    if distancia_fibra is None:
        return "Dados Insuficientes"
    
    if distancia_fibra < distancia_troco_km * 0.95:
        return "Partida"
    elif perda_total is not None and perda_maxima_dB is not None and perda_total > perda_maxima_dB:
        return "Atenuada"
    else:
        return "OK"

# ==============================
# Processamento Principal
# ==============================
def processar_excel_memoria(excel_file, uploaded_file, quadrimestre, distancia_troco_km, perda_maxima_dB):
    """Processa os dados EXTRAÍDOS DO EXCEL EM MEMÓRIA"""
    
    # Nome do arquivo original (apenas para identificação)
    fiber_id = extrair_fiber_id(uploaded_file.name)
    
    try:
        # ABRIR EXCEL GERADO EM MEMÓRIA
        xls = pd.ExcelFile(excel_file)
        dados_combinados = []
        
        # LER TODAS AS ABAS DO EXCEL
        for sheet_name in xls.sheet_names:
            df = pd.read_excel(xls, sheet_name=sheet_name)
            dados_combinados.append(df)

        # EXTRAIR DADOS DO EXCEL (nunca do PDF)
        distancia_fibra = extrair_fim_fibra(dados_combinados)
        perda_total, eventos = extrair_perda_total_eventos(dados_combinados)
        
        # CALCULAR STATUS COM DADOS DO EXCEL
        status = determinar_status(distancia_fibra, perda_total, distancia_troco_km, perda_maxima_dB)
        
        return {
            "Fiber ID": fiber_id,
            "Quadrimestre": quadrimestre,
            "Distância Esperada (km)": distancia_troco_km,
            "Distância Testada (km)": distancia_fibra,  # ← AGORA DEVE VIR PREENCHIDA
            "Perda Total (dB)": perda_total,           # ← Do Excel  
            "Eventos": eventos if eventos else "Nenhum", # ← Do Excel
            "Status": status,
            "Total_Tabelas": len(dados_combinados)
        }
        
    except Exception as e:
        st.error(f"Erro ao processar dados do Excel: {e}")
        return None

# ==============================
# Função para Análise Comparativa
# ==============================
def analise_comparativa(dados_prev, dados_curr):
    """Faz análise comparativa entre quadrimestres"""
    
    analise = {
        "Comparação": [],
        "Quadrimestre_Anterior": [],
        "Quadrimestre_Atual": [],
        "Variação": []
    }
    
    # Distância
    analise["Comparação"].append("Distância Testada (km)")
    analise["Quadrimestre_Anterior"].append(dados_prev["Distância Testada (km)"])
    analise["Quadrimestre_Atual"].append(dados_curr["Distância Testada (km)"])
    
    if dados_prev["Distância Testada (km)"] == dados_curr["Distância Testada (km)"]:
        analise["Variação"].append("✅ Estável")
    else:
        analise["Variação"].append("⚠️ Alterada")
    
    # Status
    analise["Comparação"].append("Status")
    analise["Quadrimestre_Anterior"].append(dados_prev["Status"])
    analise["Quadrimestre_Atual"].append(dados_curr["Status"])
    
    if dados_prev["Status"] == dados_curr["Status"]:
        analise["Variação"].append("✅ Estável")
    elif dados_curr["Status"] == "OK":
        analise["Variação"].append("🟢 Melhorou")
    else:
        analise["Variação"].append("🔴 Piorou")
    
    return pd.DataFrame(analise)

# ==============================
# Interface Streamlit
# ==============================
def main():
    st.title("📡 Clean Up AutoProcess (PDF → Excel em Memória)")
    st.write("**Conversão automática de PDF para Excel em memória + Análise OTDR**")
    
    # Sidebar com informações
    st.sidebar.title("ℹ️ Informações")
    st.sidebar.write("""
    **Fluxo do Processamento:**
    1. 📄 PDF importado
    2. 🔄 Convertido para Excel em memória
    3. 🔍 Dados extraídos do Excel
    4. 📊 Resultados exibidos
    """)
    
    # Configurações principais
    st.subheader("⚙️ Configurações do Teste")
    
    col1, col2 = st.columns(2)
    with col1:
        distancia_troco = st.number_input(
            "👉 Distância esperada do troço (km)", 
            min_value=1.0, 
            step=0.5, 
            value=10.0,
            help="Distância esperada do link de fibra óptica"
        )
    with col2:
        comprimento_onda = st.selectbox(
            "👉 Selecione o comprimento de onda (nm)", 
            [1310, 1550], 
            index=1,
            help="Comprimento de onda utilizado no teste OTDR"
        )

    # Cálculo automático da perda máxima
    perda_maxima = calcular_perda_maxima(distancia_troco, comprimento_onda)
    
    if perda_maxima:
        st.info(f"🔎 **Perda máxima permitida do link: {perda_maxima:.2f} dB**")
    else:
        st.error("❌ Erro no cálculo da perda máxima")

    # Upload de arquivos
    st.subheader("📂 Upload de Relatórios PDF")
    col_prev, col_curr = st.columns(2)

    with col_prev:
        st.write("**📅 Quadrimestre Anterior**")
        file_prev = st.file_uploader(
            "Selecione PDF anterior", 
            type=["pdf"], 
            key="q_prev",
            help="Relatório OTDR do quadrimestre anterior"
        )
        q_prev = st.selectbox(
            "Selecione o quadrimestre", 
            ["Q1", "Q2", "Q3", "Q4"], 
            key="sel_prev"
        )

    with col_curr:
        st.write("**📅 Quadrimestre Atual**")
        file_curr = st.file_uploader(
            "Selecione PDF atual", 
            type=["pdf"], 
            key="q_curr",
            help="Relatório OTDR do quadrimestre atual"
        )
        q_curr = st.selectbox(
            "Selecione o quadrimestre", 
            ["Q1", "Q2", "Q3", "Q4"], 
            key="sel_curr"
        )

    # Processamento quando ambos arquivos são carregados
    if file_prev and file_curr:
        st.success("✅ PDFs importados! Iniciando conversão...")
        
        # PASSO 1: CONVERTER PDF PARA EXCEL
        with st.spinner("🔄 Convertendo PDF para Excel em memória..."):
            excel_prev = pdf_para_excel_memoria(file_prev)
            excel_curr = pdf_para_excel_memoria(file_curr)
        
        st.success("🎯 Excel em memória gerado! Extraindo dados...")
        
        # PASSO 2: PROCESSAR DADOS DO EXCEL
        with st.spinner("🔍 Analisando dados do Excel..."):
            resultado_prev = processar_excel_memoria(excel_prev, file_prev, q_prev, distancia_troco, perda_maxima)
            resultado_curr = processar_excel_memoria(excel_curr, file_curr, q_curr, distancia_troco, perda_maxima)
        
        # PASSO 3: EXIBIR RESULTADOS
        if resultado_prev and resultado_curr:
            st.subheader("📊 Resultados Resumidos (Dados Extraídos do Excel)")
            
            # Criar DataFrame resumido
            dados_resumo = []
            for resultado in [resultado_prev, resultado_curr]:
                dados_resumo.append({
                    "Fiber ID": resultado["Fiber ID"],
                    "Quadrimestre": resultado["Quadrimestre"],
                    "Distância Esperada (km)": resultado["Distância Esperada (km)"],
                    "Distância Testada (km)": resultado["Distância Testada (km)"],
                    "Perda Total (dB)": resultado["Perda Total (dB)"],
                    "Status": resultado["Status"]
                })
            
            df_resumo = pd.DataFrame(dados_resumo)
            st.dataframe(df_resumo, use_container_width=True)
            
            # Verificar se as distâncias foram extraídas
            if resultado_prev["Distância Testada (km)"] is None or resultado_curr["Distância Testada (km)"] is None:
                st.error("❌ ATENÇÃO: Não foi possível extrair a distância testada de um ou ambos os arquivos")
            else:
                st.success("✅ Distâncias testadas extraídas com sucesso!")
            
            # Análise Comparativa
            st.subheader("📈 Análise Comparativa")
            df_comparativo = analise_comparativa(resultado_prev, resultado_curr)
            st.dataframe(df_comparativo, use_container_width=True)
            
            # Detalhamento dos Dados Extraídos
            st.subheader("🔍 Detalhamento dos Dados Extraídos")
            
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**{q_prev} - Dados do Excel**")
                st.metric("Distância Testada", 
                         f"{resultado_prev['Distância Testada (km)']} km" if resultado_prev['Distância Testada (km)'] else "N/A")
                st.metric("Perda Total", 
                         f"{resultado_prev['Perda Total (dB)']} dB" if resultado_prev['Perda Total (dB)'] else "N/A")
                st.metric("Status", resultado_prev["Status"])
                st.metric("Total de Tabelas", resultado_prev["Total_Tabelas"])
                
            with col2:
                st.write(f"**{q_curr} - Dados do Excel**")
                st.metric("Distância Testada", 
                         f"{resultado_curr['Distância Testada (km)']} km" if resultado_curr['Distância Testada (km)'] else "N/A")
                st.metric("Perda Total", 
                         f"{resultado_curr['Perda Total (dB)']} dB" if resultado_curr['Perda Total (dB)'] else "N/A")
                st.metric("Status", resultado_curr["Status"])
                st.metric("Total de Tabelas", resultado_curr["Total_Tabelas"])
                
        else:
            st.error("❌ Erro no processamento dos dados. Verifique os arquivos PDF.")
    
    else:
        st.info("👆 Faça upload dos relatórios PDF dos dois quadrimestres para iniciar a análise.")
    
    # Rodapé
    st.markdown("---")
    st.caption("🔄 **Fluxo em Memória**: PDF → Excel Interno → Análise → Resultados")
    st.caption("📡 **Clean Up AutoProcess** - Desenvolvido para análise OTDR")

# ==============================
# Execução da Aplicação
# ==============================
if __name__ == "__main__":
    main()