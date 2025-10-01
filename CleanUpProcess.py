import streamlit as st
import pandas as pd
import pdfplumber
import re
import os

# ==============================
# Função: extrair dados do PDF
# ==============================
def parse_pdf_otdr(uploaded_file, quadrimestre, distancia_troco_km, perda_maxima_dB):
    """
    Lê relatório OTDR em PDF (texto/tabela ou texto bruto).
    Extrai:
      - Fiber ID (nome do arquivo no PDF)
      - Perda total
      - Distância esperada
      - Eventos críticos >0.2 dB
      - Status (OK, Partida, Atenuada)
    """
    fiber_id = os.path.splitext(uploaded_file.name)[0]
    perda_total = None
    distancia_fibra = None
    eventos = []

    with pdfplumber.open(uploaded_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            # Procurar perda total
            match_perda = re.search(r"(perda total db|perda do trecho)\s*[:=]?\s*([\d.,]+)", text, re.IGNORECASE)
            if match_perda:
                perda_total = float(match_perda.group(2).replace(",", "."))

            # Procurar distância
            match_dist = re.search(r"(comprimento do trecho|fim da fibra)\s*[:=]?\s*([\d.,]+)", text, re.IGNORECASE)
            if match_dist:
                distancia_fibra = float(match_dist.group(2).replace(",", "."))

            # Procurar eventos críticos
            eventos_match = re.findall(r"perda db\s*[:=]?\s*([\d.,]+)", text, re.IGNORECASE)
            for ev in eventos_match:
                valor = float(ev.replace(",", "."))
                if valor > 0.2:
                    eventos.append(valor)

            # Também tentar buscar em tabelas (se existirem)
            tables = page.extract_tables()
            for table in tables:
                df = pd.DataFrame(table[1:], columns=table[0])
                df.columns = [c.strip().lower() for c in df.columns]

                if "perda total db" in df.columns:
                    try:
                        perda_total = float(df["perda total db"].dropna().iloc[-1])
                    except:
                        pass

                if "fim da fibra" in df.columns:
                    try:
                        distancia_fibra = float(df["fim da fibra"].dropna().astype(float).max())
                    except:
                        pass

                if "perda (db)" in df.columns:
                    df["perda (db)"] = pd.to_numeric(df["perda (db)"], errors="coerce")
                    eventos_criticos = df[df["perda (db)"] > 0.2]["perda (db)"].tolist()
                    eventos.extend(eventos_criticos)

    # Diagnóstico fibra
    status = "OK"
    if distancia_fibra is not None and distancia_fibra < distancia_troco_km * 0.95:
        status = "Partida"
    elif perda_total is not None and perda_total > perda_maxima_dB:
        status = "Atenuada"

    return {
        "Fiber ID": fiber_id,
        "Quadrimestre": quadrimestre,
        "Distância Esperada (km)": distancia_troco_km,
        "Distância Medida (km)": distancia_fibra,
        "Perda Total (dB)": perda_total,
        "Eventos Críticos (>0.2 dB)": ", ".join(map(str, eventos)) if eventos else "Nenhum",
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
# Função calcular perda máxima
# ==============================
def calcular_perda_maxima(distancia, comprimento_onda):
    if comprimento_onda == 1310:
        return distancia * 0.33
    elif comprimento_onda == 1550:
        return distancia * 0.22
    else:
        return None

# ==============================
# Interface Streamlit
# ==============================
st.set_page_config(page_title="Clean Up AutoProcess - PDF", layout="wide")

st.title("📡 Clean Up AutoProcess (PDF)")
st.write("Analisa relatórios OTDR em PDF (texto/tabela) por quadrimestre.")

# Inputs principais
distancia_troco = st.number_input("👉 Distância esperada do troço (km)", min_value=1.0, step=0.5)

# Escolha do comprimento de onda
comprimento_onda = st.selectbox("👉 Selecione o comprimento de onda (nm)", [1310, 1550], index=1)

# Cálculo automático da perda máxima
perda_maxima = calcular_perda_maxima(distancia_troco, comprimento_onda)
st.write(f"🔎 **Perda máxima permitida do link (dB): {perda_maxima:.2f}**")

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

    for file, quad in [(file_prev, q_prev), (file_curr, q_curr)]:
        resultado = parse_pdf_otdr(
            uploaded_file=file,
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
    diff = (resultados[1]["Perda Total (dB)"] or 0) - (resultados[0]["Perda Total (dB)"] or 0)
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
