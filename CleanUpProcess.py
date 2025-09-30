import streamlit as st
import pandas as pd
import os
from datetime import datetime

# Limites de perda por comprimento de onda (dB/km)
LIMITES_PERDA = {1550: 0.22, 1310: 0.33}

# ======================
# Função para simular leitura de .SOR
# ======================
def parse_sor(file_name, content):
    """Simula extração de dados de um arquivo .sor"""
    fiber_id = os.path.splitext(file_name)[0]
    data_teste = datetime.now().strftime("%Y-%m-%d")
    perda_total = round(0.1 + 0.05 * (hash(fiber_id) % 5), 3)
    onda = 1550
    distancia = round(10 + (hash(fiber_id) % 30) * 0.5, 2)

    return {
        "Fibra": fiber_id,
        "Data": data_teste,
        "Perda(dB)": perda_total,
        "Comprimento de Onda(nm)": onda,
        "Distância(km)": distancia
    }

# ======================
# Normalização de colunas
# ======================
def normalize_columns(df):
    mapping = {}
    for col in df.columns:
        c = str(col).lower().strip()
        if "fiber" in c or "fibra" in c:
            mapping[col] = "Fibra"
        elif "data" in c:
            mapping[col] = "Data"
        elif "perda" in c or "loss" in c:
            mapping[col] = "Perda(dB)"
        elif "onda" in c or "1310" in c or "1550" in c:
            mapping[col] = "Comprimento de Onda(nm)"
        elif "dist" in c or "km" in c:
            mapping[col] = "Distância(km)"
        else:
            mapping[col] = col
    df = df.rename(columns=mapping)
    if "Data" in df.columns:
        df["Data"] = pd.to_datetime(df["Data"], errors="coerce")
    return df

# ======================
# Carregar consolidado
# ======================
def carregar_consolidado(nome_arquivo="consolidado.csv"):
    if os.path.exists(nome_arquivo):
        df = pd.read_csv(nome_arquivo, encoding="utf-8")
        df = normalize_columns(df)
        return df
    return pd.DataFrame(columns=["Fibra", "Data", "Perda(dB)", "Comprimento de Onda(nm)", "Distância(km)"])

# ======================
# Salvar consolidado
# ======================
def salvar_consolidado(df, nome_arquivo="consolidado.csv"):
    df.to_csv(nome_arquivo, index=False, encoding="utf-8")

# ======================
# Análise comparativa
# ======================
def analisar_dados(df):
    if df.empty:
        st.warning("⚠️ Nenhum dado disponível para análise.")
        return

    df["Data"] = pd.to_datetime(df["Data"], errors="coerce")
    df['Quadrimestre'] = df['Data'].dt.month.apply(lambda m: (m-1)//4 + 1)

    agrupado = df.groupby(["Fibra", "Quadrimestre"]).agg({
        "Perda(dB)": "mean",
        "Distância(km)": "mean",
        "Comprimento de Onda(nm)": "first"
    }).reset_index()

    resultados = []
    for fibra in agrupado['Fibra'].unique():
        dados_fibra = agrupado[agrupado['Fibra'] == fibra].sort_values("Quadrimestre")
        dados_fibra = dados_fibra.set_index("Quadrimestre")
        for q in [1, 2, 3]:
            if q in dados_fibra.index and ((q % 3) + 1) in dados_fibra.index:
                perda_q = dados_fibra.loc[q, "Perda(dB)"]
                perda_q_next = dados_fibra.loc[(q % 3) + 1, "Perda(dB)"]
                distancia = dados_fibra.loc[q, "Distância(km)"]
                onda = dados_fibra.loc[q, "Comprimento de Onda(nm)"]
                perda_esperada = LIMITES_PERDA.get(onda, 0.25) * distancia
                aumento = round(perda_q_next - perda_q, 3)
                status = "⚠️ ALERTA" if perda_q_next > perda_esperada else "✅ OK"
                resultados.append([fibra, f"Q{q}->Q{(q%3)+1}", perda_q, perda_q_next, perda_esperada, aumento, status])

    df_result = pd.DataFrame(resultados, columns=["Fibra", "Comparação", "Perda Inicial", "Perda Final", "Perda Esperada", "Δ Perda", "Status"])
    if df_result.empty:
        st.info("⏳ Aguardando dados de mais quadrimestres para iniciar comparações.")
    else:
        st.subheader("📊 Resultados Comparativos")
        st.dataframe(df_result)

# ======================
# Interface Streamlit
# ======================
def main():
    st.title("📡 Clean Up AutoProcess")
    st.write("Plataforma de análise de testes OTDR (.sor) com comparativos quadrimestrais.")

    df = carregar_consolidado()

    uploaded_files = st.file_uploader("📂 Envie arquivos .SOR", type=["sor"], accept_multiple_files=True)

    if uploaded_files:
        for uploaded_file in uploaded_files:
            novo_registro = parse_sor(uploaded_file.name, uploaded_file.getvalue())
            df = pd.concat([df, pd.DataFrame([novo_registro])], ignore_index=True)
            df = normalize_columns(df)

        salvar_consolidado(df)
        st.success(f"{len(uploaded_files)} arquivos importados com sucesso!")

    if not df.empty:
        st.subheader("📋 Dados Consolidados")
        st.dataframe(df.tail(20))  # mostra últimas 20 linhas
        analisar_dados(df)

if __name__ == "__main__":
    main()
