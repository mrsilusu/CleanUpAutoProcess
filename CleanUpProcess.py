import streamlit as st
import pandas as pd
import numpy as np
import os

# ==============================
# Funções utilitárias
# ==============================

def parse_sor_csv(uploaded_file, fiber_id, quadrimestre, distancia_troco_km, perda_maxima_dB):
    """
    Parser simplificado para ficheiros .sor exportados em CSV/Excel.
    Lê colunas como: Evento, Distância (km), Perda (dB), Perda Total (dB).
    """
    df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith(".csv") else pd.read_excel(uploaded_file)

    # Calcular perda total (último valor)
    perda_total = df["Perda Total dB"].iloc[-1] if "Perda Total dB" in df.columns else df["Perda (dB)"].sum()

    # Eventos críticos (>0.2 dB)
    eventos_criticos = df[df["Perda (dB)"] > 0.2][["Distância (km)", "Perda (dB)"]]

    # Distância final medida
    distancia_fibra = df["Distância (km)"].max()

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
        "Eventos Críticos": len(eventos_criticos),
        "Status": status
    }

def salvar_relatorio(dados, filename="relatorio_consolidado.xlsx"):
    df = pd.DataFrame(dados)
    df.to_excel(filename, index=False)
    return filename

# ==============================
# Interface Streamlit
# ==============================
st.set_page_config(page_title="Clean Up AutoProcess", layout="wide")

st.title("📡 Clean Up AutoProcess")
st.write("Análise comparativa de testes OTDR por quadrimestre (Plano B - Parser simplificado).")

# Inputs principais
distancia_troco = st.number_input("👉 Distância esperada do troço (km)", min_value=1.0, step=0.5)
perda_maxima = st.number_input("👉 Perda máxima permitida do link (dB)", min_value=0.1, step=0.1)

# Upload de 2 ficheiros
st.subheader("📂 Importar testes")
col1, col2 = st.columns(2)
with col1:
    file_prev = st.file_uploader("Quadrimestre Anterior", type=["csv", "xlsx"], key="q_prev")
    q_prev = st.selectbox("Selecione quadrimestre anterior", ["Q1", "Q2", "Q3"], index=0)
with col2:
    file_curr = st.file_uploader("Quadrimestre Atual", type=["csv", "xlsx"], key="q_curr")
    q_curr = st.selectbox("Selecione quadrimestre atual", ["Q1", "Q2", "Q3"], index=1)

# Processamento
if file_prev and file_curr:
    resultados = []

    for idx, (file, quad) in enumerate([(file_prev, q_prev), (file_curr, q_curr)], start=1):
        resultado = parse_sor_csv(
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
    if os.path.exists("relatorio_consolidado.xlsx"):
        os.remove("relatorio_consolidado.xlsx")
    st.success("Histórico limpo com sucesso!")
