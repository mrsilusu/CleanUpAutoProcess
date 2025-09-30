import streamlit as st
import pandas as pd
import numpy as np
from otdrlib import SorReader
import io

# ==========================
# Funções auxiliares
# ==========================
def ler_sor(uploaded_file):
    sor = SorReader(uploaded_file)
    data = sor.get_trace()
    df = pd.DataFrame({
        "distance": data.distance,   # eixo X (distância)
        "loss": data.loss,           # eixo Y (perda)
    })
    return df

def analisar_fibra(df_anterior, df_atual, fibra_id, distancia_backbone):
    result = {"fiber_id": fibra_id}

    # Perda máxima (comparação quadrimestres)
    result["perda_total_anterior"] = df_anterior["loss"].max()
    result["perda_total_atual"] = df_atual["loss"].max()
    result["variacao_perda"] = result["perda_total_atual"] - result["perda_total_anterior"]

    # Eventos > 0.2dB no quadrimestre atual
    eventos = df_atual[df_atual["loss"].diff().fillna(0) > 0.2]
    if not eventos.empty:
        result["eventos"] = "; ".join([f"{row.distance:.1f}m ({row.loss:.2f}dB)" for _, row in eventos.iterrows()])
    else:
        result["eventos"] = "Nenhum"

    # Diagnóstico simples
    if df_atual["distance"].max() < distancia_backbone:
        result["status"] = "Fibra partida"
    elif result["perda_total_atual"] > distancia_backbone * 0.35:  # regra exemplo: 0.35 dB/km
        result["status"] = "Fibra atenuada"
    else:
        result["status"] = "OK"

    return result


# ==========================
# Interface Streamlit
# ==========================
st.title("📡 Análise de Fibras Ópticas (.sor)")

st.write("Carregue os ficheiros .sor para comparar dois quadrimestres (anterior e atual).")

uploaded_anterior = st.file_uploader("📂 Upload Quadrimestre Anterior (.sor)", type=["sor"], key="anterior")
uploaded_atual = st.file_uploader("📂 Upload Quadrimestre Atual (.sor)", type=["sor"], key="atual")

distancia_backbone = st.number_input("Distância total do troço (em metros)", min_value=100, value=10000, step=100)

if uploaded_anterior and uploaded_atual:
    st.success("Ficheiros carregados com sucesso ✅")

    df_anterior = ler_sor(uploaded_anterior)
    df_atual = ler_sor(uploaded_atual)

    # Simulação: 48 fibras (pode ajustar conforme o cabo real)
    resultados = []
    for fibra in range(1, 49):
        r = analisar_fibra(df_anterior, df_atual, fibra, distancia_backbone)
        resultados.append(r)

    df_resultado = pd.DataFrame(resultados)

    st.subheader("📊 Resumo das fibras")
    st.dataframe(df_resultado)

    # Exportar Excel
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_resultado.to_excel(writer, index=False, sheet_name="Resumo")
    st.download_button(
        label="📥 Baixar resultados em Excel",
        data=output.getvalue(),
        file_name="analise_fibras.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    # Botão para limpar histórico
    if st.button("🗑️ Limpar histórico"):
        st.experimental_rerun()
