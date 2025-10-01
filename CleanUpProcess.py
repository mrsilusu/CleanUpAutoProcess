import streamlit as st
import pandas as pd
import pdfplumber
import re
import os
import unicodedata
import io  # 🔹 necessário para Excel em memória

# -----------------------------
# Helpers
# -----------------------------
def normalize_header(s):
    if s is None:
        return ""
    s = str(s).strip().lower()
    s = unicodedata.normalize("NFD", s)
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    s = re.sub(r"\s+", " ", s)
    return s

def clean_number_str(s):
    if s is None:
        return None
    s = str(s).strip()
    s = s.replace(",", ".")
    m = re.search(r"(-?\d+(?:\.\d+)?)", s)
    return m.group(1) if m else None

# ==============================
# Função: extrair dados do PDF
# ==============================
def parse_pdf_otdr(uploaded_file, quadrimestre, distancia_troco_km, perda_maxima_dB):
    fiber_id = os.path.splitext(uploaded_file.name)[0]
    perda_total = None
    distancia_fibra = None
    eventos = []
    distancias_encontradas = []

    with pdfplumber.open(uploaded_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            tables = page.extract_tables()

            for table in tables:
                if not table or len(table) < 2:
                    continue

                header = table[0]
                norm_header = [normalize_header(h) for h in header]

                try:
                    df = pd.DataFrame(table[1:], columns=header)
                except Exception:
                    continue

                col_map = {}
                for col in df.columns:
                    nh = normalize_header(col)
                    if "evento" in nh:
                        col_map[col] = "evento"
                    elif "dist" in nh:
                        col_map[col] = "distancia"
                    elif "p" in nh and "total" in nh:
                        col_map[col] = "p_total"
                    elif "perda" in nh and "total" not in nh:
                        col_map[col] = "perda"
                    elif "reflect" in nh or "reflet" in nh:
                        col_map[col] = "reflect"
                    else:
                        col_map[col] = nh.replace(" ", "_")

                df = df.rename(columns=col_map)

                if "distancia" in df.columns:
                    serie = df["distancia"].astype(str).map(clean_number_str)
                    nums = pd.to_numeric(serie, errors="coerce").dropna()
                    if not nums.empty:
                        distancias_encontradas.extend(nums.tolist())

                    for _, row in df.iterrows():
                        ev = {}
                        ev["Evento"] = row.get("evento")
                        raw_dist = row.get("distancia")
                        dist_clean = clean_number_str(raw_dist)
                        ev["Distância (km)"] = float(dist_clean) if dist_clean else None
                        perda_val = row.get("perda") if "perda" in df.columns else row.get("p_total")
                        ev["Perda (dB)"] = clean_number_str(perda_val)
                        ev["Reflect. dB"] = row.get("reflect") if "reflect" in df.columns else None
                        ev["P. Total dB"] = clean_number_str(row.get("p_total")) if "p_total" in df.columns else None
                        eventos.append(ev)

                if "p_total" in df.columns:
                    serie_p = df["p_total"].astype(str).map(clean_number_str)
                    nums_p = pd.to_numeric(serie_p, errors="coerce").dropna()
                    if not nums_p.empty:
                        perda_total = float(nums_p.max())

    if distancias_encontradas:
        distancia_fibra = max(distancias_encontradas)

    status = "OK"
    if distancia_fibra is not None and distancia_fibra < distancia_troco_km * 0.95:
        status = "Partida"
    elif perda_total is not None and perda_maxima_dB is not None and perda_total > perda_maxima_dB:
        status = "Atenuada"

    return {
        "Fiber ID": fiber_id,
        "Quadrimestre": quadrimestre,
        "Distância Esperada (km)": distancia_troco_km,
        "Distância Testada (km)": distancia_fibra,
        "Perda Total (dB)": perda_total,
        "Eventos": eventos if eventos else "Nenhum",
        "Status": status
    }

# ==============================
# Função salvar relatório em memória
# ==============================
def salvar_relatorio_memoria(dados):
    output = io.BytesIO()
    df = pd.DataFrame([{
        "Fiber ID": d["Fiber ID"],
        "Quadrimestre": d["Quadrimestre"],
        "Distância Esperada (km)": d["Distância Esperada (km)"],
        "Distância Testada (km)": d["Distância Testada (km)"],
        "Perda Total (dB)": d["Perda Total (dB)"],
        "Status": d["Status"]
    } for d in dados])

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Resumo", index=False)
        for d in dados:
            if isinstance(d["Eventos"], list):
                df_ev = pd.DataFrame(d["Eventos"])
                df_ev.to_excel(writer, sheet_name=f"{d['Quadrimestre']}_eventos", index=False)

    output.seek(0)
    return output

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

distancia_troco = st.number_input("👉 Distância esperada do troço (km)", min_value=1.0, step=0.5)
comprimento_onda = st.selectbox("👉 Selecione o comprimento de onda (nm)", [1310, 1550], index=1)
perda_maxima = calcular_perda_maxima(distancia_troco, comprimento_onda)
st.write(f"🔎 **Perda máxima permitida do link (dB): {perda_maxima:.2f}**")

st.subheader("📂 Importar relatórios PDF")
col1, col2 = st.columns(2)
with col1:
    file_prev = st.file_uploader("Quadrimestre Anterior (PDF)", type=["pdf"], key="q_prev")
    q_prev = st.selectbox("Selecione quadrimestre anterior", ["Q1", "Q2", "Q3"], index=0)
with col2:
    file_curr = st.file_uploader("Quadrimestre Atual (PDF)", type=["pdf"], key="q_curr")
    q_curr = st.selectbox("Selecione quadrimestre atual", ["Q1", "Q2", "Q3"], index=1)

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

    df_resumo = pd.DataFrame([{
        "Fiber ID": r["Fiber ID"],
        "Quadrimestre": r["Quadrimestre"],
        "Distância Esperada (km)": r["Distância Esperada (km)"],
        "Distância Testada (km)": r["Distância Testada (km)"],
        "Perda Total (dB)": r["Perda Total (dB)"],
        "Status": r["Status"]
    } for r in resultados])
    st.subheader("📊 Resultados Resumidos")
    st.dataframe(df_resumo)

    # 🔹 Excel em memória
    excel_mem = salvar_relatorio_memoria(resultados)

    # reutilizando o excel em memória dentro do app
    xls = pd.ExcelFile(excel_mem)
    df_resumo_xls = pd.read_excel(xls, sheet_name="Resumo")

    st.subheader("📑 Resumo lido do Excel em memória")
    st.dataframe(df_resumo_xls)

    # botão de download opcional
    st.download_button(
        label="💾 Baixar relatório Excel",
        data=excel_mem,
        file_name="relatorio_otdr_memoria.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
