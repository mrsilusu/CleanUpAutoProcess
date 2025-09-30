import streamlit as st
import pdfplumber
import re
import pandas as pd
import os

st.set_page_config(page_title="Analisador OTDR", layout="wide")

st.title("📊 Analisador OTDR (Comparação de Quadrimestres)")

# Upload de dois PDFs
col1, col2 = st.columns(2)
with col1:
    pdf_anterior = st.file_uploader("📂 Carregar Quadrimestre Anterior", type=["pdf"], key="anterior")
with col2:
    pdf_atual = st.file_uploader("📂 Carregar Quadrimestre Atual", type=["pdf"], key="atual")

# Função para extrair info do PDF
def extrair_info(pdf_file):
    if not pdf_file:
        return None

    fiber_id = os.path.splitext(pdf_file.name)[0]
    texto = ""

    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            texto += page.extract_text() + "\n"

    perda_total = None
    distancia_esperada = None
    eventos_criticos = []

    # Buscar perda total
    match_perda = re.search(r"(perda total db|perda do trecho)\s*[:=]?\s*([\d.,]+)", texto, re.IGNORECASE)
    if match_perda:
        perda_total = float(match_perda.group(2).replace(",", "."))

    # Buscar distância
    match_dist = re.search(r"(comprimento do trecho|fim da fibra)\s*[:=]?\s*([\d.,]+)", texto, re.IGNORECASE)
    if match_dist:
        distancia_esperada = float(match_dist.group(2).replace(",", "."))

    # Buscar eventos críticos
    eventos = re.findall(r"perda db\s*[:=]?\s*([\d.,]+)", texto, re.IGNORECASE)
    for ev in eventos:
        valor = float(ev.replace(",", "."))
        if valor > 0.2:
            eventos_criticos.append(valor)

    return {
        "Fiber ID": fiber_id,
        "Perda Total (dB)": perda_total,
        "Distância Esperada (km)": distancia_esperada,
        "Eventos Críticos (>0.2 dB)": ", ".join(map(str, eventos_criticos)) if eventos_criticos else "Nenhum"
    }

# Quando os dois forem carregados
if pdf_anterior and pdf_atual:
    st.subheader("📋 Resultado da Análise")

    dados_anterior = extrair_info(pdf_anterior)
    dados_atual = extrair_info(pdf_atual)

    if dados_anterior and dados_atual:
        perda_max_permitida = 0.35  # pode ajustar
        status = "OK"

        if dados_atual["Distância Esperada (km)"] and dados_atual["Distância Esperada (km)"] < (
            dados_anterior["Distância Esperada (km)"] or 0
        ):
            status = "PARTIDA"
        if dados_atual["Perda Total (dB)"] and dados_atual["Perda Total (dB)"] > perda_max_permitida:
            status = "ATENUADA"

        df = pd.DataFrame([{
            "Fiber ID": dados_atual["Fiber ID"],
            "Perda Total Anterior (dB)": dados_anterior["Perda Total (dB)"],
            "Perda Total Atual (dB)": dados_atual["Perda Total (dB)"],
            "Distância Esperada Atual (km)": dados_atual["Distância Esperada (km)"],
            "Eventos Críticos Atual": dados_atual["Eventos Críticos (>0.2 dB)"],
            "Status": status
        }])

        st.dataframe(df, use_container_width=True)

        # Botão de download
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("💾 Baixar Resultado (CSV)", data=csv, file_name="comparativo_otdr.csv", mime="text/csv")
