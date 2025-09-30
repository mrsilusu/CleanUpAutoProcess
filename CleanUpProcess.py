import streamlit as st
import pdfplumber
import re
import os
import pandas as pd

st.set_page_config(page_title="Processador OTDR PDF", layout="wide")

st.title("📊 Processador de Relatórios OTDR (PDF)")

uploaded_file = st.file_uploader("Carregue o relatório OTDR em PDF", type=["pdf"])

# Função para extrair valores do PDF
def extract_otdr_info(pdf_path):
    data = {
        "Fiber ID": None,
        "Perda Total (dB)": None,
        "Distância Esperada (Km)": None,
        "Eventos Críticos": [],
        "Status": None
    }

    text_content = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text_content += page.extract_text() + "\n"

    # Fiber ID = nome do arquivo
    data["Fiber ID"] = os.path.basename(pdf_path)

    # Buscar Perda Total
    perda_match = re.search(r"(Perda Total dB|Perda do trecho)[:\s]*([\d,.]+)", text_content, re.IGNORECASE)
    if perda_match:
        data["Perda Total (dB)"] = float(perda_match.group(2).replace(",", "."))

    # Buscar Distância Esperada
    dist_match = re.search(r"(Fim da Fibra Km|Comprimento do trecho)[:\s]*([\d,.]+)", text_content, re.IGNORECASE)
    if dist_match:
        data["Distância Esperada (Km)"] = float(dist_match.group(2).replace(",", "."))

    # Buscar eventos críticos (todas perdas dB > 0.2)
    eventos = re.findall(r"Perda dB[:\s]*([\d,.]+)", text_content, re.IGNORECASE)
    eventos_criticos = [float(x.replace(",", ".")) for x in eventos if float(x.replace(",", ".")) > 0.2]
    data["Eventos Críticos"] = eventos_criticos

    # Definir Status
    if data["Distância Esperada (Km)"] is not None and data["Perda Total (dB)"] is not None:
        # Critérios de avaliação
        perda_limite = 0.35  # dB/km (ajustável)
        dist_ok = True  # neste caso não temos a "referência", apenas o extraído
        perda_ok = data["Perda Total (dB)"] <= perda_limite * (data["Distância Esperada (Km)"] or 1)

        if dist_ok and perda_ok:
            data["Status"] = "✅ OK"
        elif not perda_ok:
            data["Status"] = "⚠️ Atenuada"
        else:
            data["Status"] = "❌ Partida"
    else:
        data["Status"] = "❓ Informação insuficiente"

    return data

if uploaded_file:
    with open("temp.pdf", "wb") as f:
        f.write(uploaded_file.getbuffer())

    result = extract_otdr_info("temp.pdf")

    # Exibir resultados em tabela
    df = pd.DataFrame([{
        "Fiber ID": result["Fiber ID"],
        "Perda Total (dB)": result["Perda Total (dB)"],
        "Distância Esperada (Km)": result["Distância Esperada (Km)"],
        "Eventos Críticos": ", ".join([str(e) for e in result["Eventos Críticos"]]),
        "Status": result["Status"]
    }])

    st.subheader("📋 Resultado da Análise")
    st.dataframe(df)

    # Mostrar texto bruto (debug)
    with st.expander("🔎 Texto extraído do PDF"):
        with pdfplumber.open("temp.pdf") as pdf:
            for i, page in enumerate(pdf.pages):
                st.text_area(f"Página {i+1}", page.extract_text(), height=200)
