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
    Lê relatório OTDR em PDF (texto/tabela).
    Extrai:
      - Fiber ID (nome do arquivo no PDF)
      - Perda total
      - Distância esperada
      - Distância testada (último valor da coluna Distância na tabela de eventos)
      - Eventos (tabela completa)
      - Status (OK, Partida, Atenuada)
    """
    fiber_id = os.path.splitext(uploaded_file.name)[0]
    perda_total = None
    distancia_fibra = None
    eventos = []

    with pdfplumber.open(uploaded_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""

            # Procurar perda total no texto (backup caso não venha da tabela)
            match_perda = re.search(r"(perda total db|perda do trecho)\s*[:=]?\s*([\d.,]+)", text, re.IGNORECASE)
            if match_perda:
                perda_total = float(match_perda.group(2).replace(",", "."))

            # Procurar tabelas
            tables = page.extract_tables()
            for table in tables:
                if not table or len(table) < 2:
                    continue

                df = pd.DataFrame(table[1:], columns=table[0])
                df.columns = [c.strip().lower() for c in df.columns]

                # Se a tabela for a de eventos
                if "evento" in df.columns and "distância" in df.columns:
                    df["distância"] = pd.to_numeric(df["distância"], errors="coerce")

                    # Distância testada = último valor da coluna distância
                    if not df["distância"].dropna().empty:
                        distancia_fibra = df["distância"].dropna().iloc[-1]

                    for _, row in df.iterrows():
                        try:
                            ev = {
                                "Evento": row.get("evento"),
                                "Distância Testada (km)": row.get("distância"),
                                "Perda Total (dB)": row.get("perda"),
                                "Reflect. dB": row.get("reflect.", ""),
                                "P. Total dB": row.get("p. total", "")
                            }
                            eventos.append(ev)
                        except Exception:
                            continue

                # Tentar pegar perda total também das tabelas
                if "perda total db" in df.columns:
                    try:
                        perda_total = float(df["perda total db"].dropna().iloc[-1])
                    except:
                        pass

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
        "Distância Testada (km)": distancia_fibra,
        "Perda Total (dB)": perda_total,
        "Eventos": eventos if eventos else "Nenhum",
        "Status": status
    }

# ==============================
# Função salvar relatório
# ==============================
def salvar_relatorio(dados, filename="relatorio_otdr_pdf.xlsx"):
    # salvar resumo
    df = pd.DataFrame([{
        "Fiber ID": d["Fiber ID"],
        "Quadrimestre": d["Quadrimestre"],
        "Distância Esperada (km)": d["Distância Esperada (km)"],
        "Distância Testada (km)": d["Distância Testada (km)"],
        "Perda Total (dB)": d["Perda Total (dB)"],
        "Status": d["Status"]
    } for d in dados])
    df.to_excel(filename, index=False)

    # salvar eventos detalhados em outra aba
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

    # Mostrar resumo
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

    # Mostrar eventos detalhados
    st.subheader("📍 Eventos Extraídos")
    for r in resultados:
        if isinstance(r["Eventos"], list):
            st.write(f"### {r['Fiber ID']} - {r['Quadrimestre']}")
            st.dataframe(pd.DataFrame(r["Eventos"]))
        else:
            st.write(f"### {r['Fiber ID']} - {r['Quadrimestre']}: Nenhum evento encontrado")

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
