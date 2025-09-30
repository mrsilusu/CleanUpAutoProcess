import streamlit as st
import pdfplumber
import re
import pandas as pd
import os

st.title("📊 Analisador OTDR - PDF")

# Upload PDF
pdf_file = st.file_uploader("Carregue o relatório OTDR (PDF)", type=["pdf"])

if pdf_file:
    fiber_id = os.path.splitext(pdf_file.name)[0]  # Nome do arquivo como Fiber ID
    texto = ""

    # Extrair texto com pdfplumber
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            texto += page.extract_text() + "\n"

    # Procurar padrões
    perda_total = None
    distancia_esperada = None
    eventos_criticos = []

    # Buscar perda total
    match_perda = re.search(r"(perda total db|perda do trecho)\s*[:=]?\s*([\d.,]+)", texto, re.IGNORECASE)
    if match_perda:
        perda_total = float(match_perda.group(2).replace(",", "."))

    # Buscar distância esperada
    match_dist = re.search(r"(comprimento do trecho|fim da fibra)\s*[:=]?\s*([\d.,]+)", texto, re.IGNORECASE)
    if match_dist:
        distancia_esperada = float(match_dist.group(2).replace(",", "."))

    # Buscar eventos críticos (>0.2 dB)
    eventos = re.findall(r"perda db\s*[:=]?\s*([\d.,]+)", texto, re.IGNORECASE)
    for ev in eventos:
        valor = float(ev.replace(",", "."))
        if valor > 0.2:
            eventos_criticos.append(valor)

    # Determinar status
    status = "OK"
    perda_max_permitida = 0.35  # exemplo, pode parametrizar

    if distancia_esperada and distancia_esperada < 10:  # Exemplo de troço = 10 km
        status = "PARTIDA"
    if perda_total and perda_total > perda_max_permitida:
        status = "ATENUADA"

    # Montar tabela final
    df = pd.DataFrame([{
        "Fiber ID": fiber_id,
        "Perda Total (dB)": perda_total,
        "Distância Esperada (km)": distancia_esperada,
        "Eventos Críticos (>0.2 dB)": ", ".join(map(str, eventos_criticos)) if eventos_criticos else "Nenhum",
        "Status": status
    }])

    st.subheader("📋 Resultado da Análise")
    st.dataframe(df)

    # Exportar para Excel/CSV
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button("💾 Baixar Resultado (CSV)", data=csv, file_name="resultado_otdr.csv", mime="text/csv")
