import streamlit as st
import pandas as pd
import pdfplumber
import re
import os
import unicodedata

# -----------------------------
# Helpers
# -----------------------------
def normalize_header(s):
    """Normaliza header: remove acentos, minuscula e espaços extras."""
    if s is None:
        return ""
    s = str(s).strip().lower()
    s = unicodedata.normalize("NFD", s)
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")  # remove acentos
    s = re.sub(r"\s+", " ", s)
    return s

def clean_number_str(s):
    """Limpa string numérica: substitui vírgula por ponto e extrai primeiro número válido."""
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
            lines = text.splitlines()

            # 🔹 Procurar explicitamente "Fim da Fibra Km"
            for i, line in enumerate(lines):
                if "fim da fibra" in normalize_header(line):
                    if i + 1 < len(lines):
                        val = clean_number_str(lines[i + 1])
                        if val:
                            try:
                                distancia_fibra = float(val)
                                distancias_encontradas.append(distancia_fibra)
                            except:
                                pass

            # 🔹 Extrair tabelas
            tables = page.extract_tables()
            for table in tables:
                if not table or len(table) < 2:
                    continue

                header = table[0]
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
                    elif "perda" in nh and "total" not in nh:
                        col_map[col] = "perda"
                    elif "p. total" in nh or "p total" in nh:
                        col_map[col] = "p_total"
                    elif "reflect" in nh:
                        col_map[col] = "reflect"
                df = df.rename(columns=col_map)

                # Eventos
                if "distancia" in df.columns:
                    serie = df["distancia"].astype(str).map(clean_number_str)
                    nums = pd.to_numeric(serie, errors="coerce").dropna()
                    if not nums.empty:
                        distancias_encontradas.extend(nums.tolist())

                    for _, row in df.iterrows():
                        ev = {
                            "Evento": row.get("evento"),
                            "Distância (km)": float(clean_number_str(row.get("distancia") or 0)) if row.get("distancia") else None,
                            "Perda (dB)": clean_number_str(row.get("perda")),
                            "Reflect. dB": row.get("reflect"),
                            "P. Total dB": clean_number_str(row.get("p_total"))
                        }
                        eventos.append(ev)

                # Perda total
                if "p_total" in df.columns:
                    serie_p = df["p_total"].astype(str).map(clean_number_str)
                    nums_p = pd.to_numeric(serie_p, errors="coerce").dropna()
                    if not nums_p.empty:
                        perda_total = float(nums_p.max())

    # 🔹 Definir a distância testada como o maior valor encontrado
    if distancias_encontradas:
        distancia_fibra = max(distancias_encontradas)

    # 🔹 Diagnóstico fibra
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
# Função salvar relatório
# ==============================
def salvar_relatorio(dados, filename="relatorio_otdr_pdf.xlsx"):
    df = pd.DataFrame([{
        "Fiber ID": d["Fiber ID"],
        "Quadrimestre": d["Quadrimestre"],
        "Distância Esperada (km)": d["Distância Esperada (km)"],
        "Distância Testada (km)": d["Distância Testada (km)"],
        "Perda Total (dB)": d["Perda Total (dB)"],
        "Status": d["Status"]
    } for d in dados])
    df.to_excel(filename, index=False)

    with pd.ExcelWriter(filename, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
        for d in dados:
            if isinstance(d["Eventos"], list):
                df_ev = pd.DataFrame(d["Eventos"])
                df_ev.to_excel(writer, sheet_name=f"{d['Quadrimestre']}_eventos", index=False)

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

    st.subheader("📍 Eventos Extraídos")
    for r in resultados:
        if isinstance(r["Eventos"], list):
            st.write(f"### {r['Fiber ID']} - {r['Quadrimestre']}")
            st.dataframe(pd.DataFrame(r["Eventos"]))
        else:
            st.write(f"### {r['Fiber ID']} - {r['Quadrimestre']}: Nenhum evento encontrado")

    st.subheader("🔎 Comparação entre quadrimestres")
    diff = (resultados[1]["Perda Total (dB)"] or 0) - (resultados[0]["Perda Total (dB)"] or 0)
    st.write(f"Variação da perda total: **{diff:.2f} dB** ({resultados[0]['Quadrimestre']} → {resultados[1]['Quadrimestre']})")

    if st.button("💾 Exportar para Excel"):
        filename = salvar_relatorio(resultados)
        st.success(f"Relatório salvo como {filename}")

if st.button("🧹 Limpar histórico"):
    if os.path.exists("relatorio_otdr_pdf.xlsx"):
        os.remove("relatorio_otdr_pdf.xlsx")
    st.success("Histórico limpo com sucesso!")
