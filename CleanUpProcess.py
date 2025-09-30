import streamlit as st
import pandas as pd
import pdfplumber
import os

# ==============================
# Função: extrair dados do PDF
# ==============================
def parse_pdf_otdr(uploaded_file, fiber_id, quadrimestre, distancia_troco_km, perda_maxima_dB):
    """
    Lê relatório OTDR em PDF (formato texto/tabela).
    Extrai distância, perda total e eventos críticos.
    """
    eventos = []
    perda_total = 0.0
    distancia_fibra = 0.0

    with pdfplumber.open(uploaded_file) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                df = pd.DataFrame(table[1:], columns=table[0])  # primeira linha = header

                # Normalizar nomes de colunas
                df.columns = [c.strip().lower() for c in df.columns]

                # Procurar perda total
                if "perda total db" in df.columns:
                    try:
                        perda_total = float(df["perda total db"].dropna().iloc[-1])
                    except:
                        pass

                # Procurar distância
                if "distância" in df.columns:
                    try:
                        distancia_fibra = float(df["distância"].dropna().astype(float).max())
                    except:
                        pass

                # Procurar eventos críticos >0.2 dB
                if "perda (db)" in df.columns and "distância" in df.columns:
                    df["perda (db)"] = pd.to_numeric(df["perda (db)"], errors="coerce")
                    df["distância"] = pd.to_numeric(df["distância"], errors="coerce")
                    eventos_criticos = df[df["perda (db)"] > 0.2][["distância", "perda (db)"]]
                    eventos.extend(eventos_criticos.values.tolist())

    # Diagnóstico fibra
    if distancia_fibra < distancia_troco_km * 0.95:
        status = "Partida"
    elif perda_total > perda_maxima_dB:
        status = "Atenuada"
    else:
        status = "OK"

    return {
        "Fiber ID": fiber_id,
        "Quadrimestre": quadrimestre,
        "Distância Esperada (km)": distancia_troco_km,
        "Distância Medida (km)": distancia_fibra,
        "Perda Total (dB)": perda_total,
        "Eventos Críticos": len(eventos),
        "Status": status
    }

# ==============================
# Função salvar relatório
# ==============================
def salvar_relatorio(dados, filename="relatorio_otdr_pdf.xlsx"):
    df = pd.DataFrame(dados)
    df.to_excel(filename, index=False)
    return filename

# ==============================
# Interface Streamlit
# ==============================
st.set_page_config(page_title="Clean Up AutoProcess - PDF", layout="wide")

st.title("📡 Clean Up AutoProcess (PDF)")
st.write("Analisa relatórios OTDR em PDF (texto/tabela) por quadrimestre.")

# Inputs principais
distancia_troco = st.number_input("👉 Distância esperada do troço (km)", min_value=1.0, step=0.5)
perda_maxima = st.number_input("👉 Perda máxima permitida do link (dB)", min_value=0.1, step=0.1)

# Upload de 2 PDFs
st.subheader("📂 Importar relatórios PDF")
col1, col2 = st.columns(2)
with col1:
    file_prev = st.file_uploader("Quadrimestre Anterior (PDF)", type=["pdf"], key="q_prev")
    q_prev = st.selectbox("Selecione quadrimestre anterior", ["Q1", "Q2", "Q3"], index=0)
with col2:
    file_curr = st.file_uploader("Quadrimestre Atual (PDF)", type=["pdf"], key="q_curr")
    q_curr = st.selectbox("Selecione quadrimestre atual", ["Q1", "Q2", "Q3"], index=1)

# Processamento
if file_prev and file_curr:
    resultados = []

    for idx, (file, quad) in enumerate([(file_prev, q_prev), (file_curr, q_curr)], start=1):
        resultado = parse_pdf_otdr(
            uploaded_file=file,
            fiber_id=f"Fibra {idx}",
            quadrimestre=quad,
            distancia_troco_km=distancia_troco,
            perda_maxima_dB=perda_maxima
        )
        resultados.append(resultado)

    # Mostrar resultados
    df_resumo = pd.DataFrame(resultados)
    st.subheader("📊 Resultados")
    st.dataframe(df_resumo)

    # Comparação perdas
    st.subheader("🔎 Comparação entre quadrimestres")
    diff = resultados[1]["Perda Total (dB)"] - resultados[0]["Perda Total (dB)"]
    st.write(f"Variação da perda total: **{diff:.2f} dB** ({resultados[0]['Quadrimestre']} → {resultados[1]['Quadrimestre']})")

    # Salvar Excel
    if st.button("💾 Exportar para Excel"):
        filename = salvar_relatorio(resultados)
        st.success(f"Relatório salvo como {filename}")

# Limpar histórico
if st.button("🧹 Limpar histórico"):
    if os.path.exists("relatorio_otdr_pdf.xlsx"):
        os.remove("relatorio_otdr_pdf.xlsx")
    st.success("Histórico limpo com sucesso!")
