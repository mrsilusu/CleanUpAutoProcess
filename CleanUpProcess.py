import streamlit as st
import pandas as pd
import numpy as np
import os
import re
from pyOTDR.OTDR import OTDRReader

# ==============================
# Função para ler arquivos .sor
# ==============================
def ler_sor(arquivo, fiber_id=None):
    """
    Lê informações de um arquivo OTDR (.sor).
    Retorna dataframe com:
    - Fiber ID
    - Perda total
    - Distância
    - Eventos (lista de tuplas: perda, distância)
    """
    otdr = OTDRReader(arquivo)

    # Identificação da fibra
    if fiber_id is None:
        nome = arquivo.name if hasattr(arquivo, "name") else str(arquivo)
        match = re.search(r"(\d+)", nome)
        fiber_id = int(match.group(1)) if match else 0

    # Distância total da fibra
    distancia = round(otdr.getFiberLength() / 1000, 2)  # m → km

    # Perda total
    perda_total = round(otdr.getTotalLoss(), 2)

    # Eventos
    eventos = []
    for ev in otdr.getEvents():
        perda = round(ev["loss"], 2)
        pos = round(ev["distance"] / 1000, 2)  # m → km
        eventos.append((perda, pos))

    return pd.DataFrame([{
        "fiber_id": fiber_id,
        "perda_total_dB": perda_total,
        "distancia_km": distancia,
        "eventos": eventos
    }])

# ==============================
# Comparação entre quadrimestres
# ==============================
def analisar_comparacao(df_ant, df_atual, quadrimestre_ant, quadrimestre_atual, distancia_troco, perda_max_troco):
    resultados = []
    for _, row_atual in df_atual.iterrows():
        fid = row_atual["fiber_id"]
        perda_atual = row_atual["perda_total_dB"]
        dist_atual = row_atual["distancia_km"]

        # Procurar fibra no quadrimestre anterior
        row_ant = df_ant[df_ant["fiber_id"] == fid]
        perda_ant = row_ant["perda_total_dB"].iloc[0] if not row_ant.empty else 0.0

        # Variação
        variacao = round(perda_atual - perda_ant, 2)

        # Eventos críticos
        eventos_criticos = [f"{ev[0]}dB @ {ev[1]}km" for ev in row_atual["eventos"] if ev[0] > 0.2]

        # Estado
        if dist_atual < distancia_troco:
            estado = "Partida"
        elif perda_atual > perda_max_troco:
            estado = "Atenuada"
        else:
            estado = "OK"

        resultados.append({
            "Fiber ID": fid,
            f"Perda {quadrimestre_ant}": perda_ant,
            f"Perda {quadrimestre_atual}": perda_atual,
            "Variação dB": variacao,
            "Eventos >0.2dB": "; ".join(eventos_criticos),
            "Estado": estado
        })
    return pd.DataFrame(resultados)

# ==============================
# Streamlit UI
# ==============================
st.title("📡 Clean Up AutoProcess – Análise OTDR (com parser real)")

quadrimestre_ant = st.selectbox("Quadrimestre anterior", ["Q1", "Q2", "Q3"])
quadrimestre_atual = st.selectbox("Quadrimestre atual", ["Q1", "Q2", "Q3"])
distancia_troco = st.number_input("Distância do troço (km)", min_value=0.1, value=10.0)
perda_max_troco = st.number_input("Perda máxima do link (dB)", min_value=0.1, value=2.0)

# Upload
st.subheader("Importar arquivos .sor")
files_ant = st.file_uploader("Quadrimestre anterior (.sor)", type=["sor"], accept_multiple_files=True)
files_atual = st.file_uploader("Quadrimestre atual (.sor)", type=["sor"], accept_multiple_files=True)

if files_ant and files_atual:
    st.success("✔️ Arquivos carregados. Processando...")

    # Ler todos os arquivos (um dataframe por quadrimestre)
    df_ant = pd.concat([ler_sor(f) for f in files_ant], ignore_index=True)
    df_atual = pd.concat([ler_sor(f) for f in files_atual], ignore_index=True)

    # Comparação
    df_resultados = analisar_comparacao(df_ant, df_atual,
                                        quadrimestre_ant, quadrimestre_atual,
                                        distancia_troco, perda_max_troco)

    st.subheader("📊 Resultados da Comparação")
    st.dataframe(df_resultados)

    # Resumo geral
    st.subheader("📋 Resumo")
    resumo = df_resultados[["Fiber ID", f"Perda {quadrimestre_atual}", "Estado"]]
    st.dataframe(resumo)

    # Exportar
    st.download_button("⬇️ Baixar CSV",
                       df_resultados.to_csv(index=False).encode("utf-8"),
                       "resultado_otdr.csv",
                       "text/csv")

# Botão limpar histórico
if st.button("🧹 Limpar histórico"):
    if os.path.exists("resultado_otdr.csv"):
        os.remove("resultado_otdr.csv")
    st.warning("Histórico limpo.")
