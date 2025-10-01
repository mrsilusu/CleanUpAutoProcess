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
    # substituir vírgula por ponto
    s = s.replace(",", ".")
    # procurar padrão numérico (ex.: 102.027)
    m = re.search(r"(-?\d+(?:\.\d+)?)", s)
    return m.group(1) if m else None

# ==============================
# Função: extrair dados do PDF
# ==============================
def parse_pdf_otdr(uploaded_file, quadrimestre, distancia_troco_km, perda_maxima_dB):
    """
    Lê relatório OTDR em PDF (texto/tabela).
    Estratégias robustas para obter:
      - Distância Testada (km) = MAIOR valor da coluna "Distância" na tabela de eventos
      - Perda Total (dB) = preferencialmente última/maior P. Total da tabela
      - Eventos: lista de registros por linha da tabela (mapear colunas)
    """
    fiber_id = os.path.splitext(uploaded_file.name)[0]
    perda_total = None
    distancia_fibra = None
    eventos = []

    # acumular distâncias encontradas
    distancias_encontradas = []

    with pdfplumber.open(uploaded_file) as pdf:
        # percorre todas as páginas
        for page in pdf.pages:
            text = page.extract_text() or ""

            # 1) TENTAR EXTRAIR TABELAS E MAPEAR COLUNAS
            tables = page.extract_tables()
            for table in tables:
                if not table or len(table) < 2:
                    continue

                header = table[0]
                # normalizar cabeçalho para identificar colunas
                norm_header = [normalize_header(h) for h in header]

                # construir DataFrame para facilitar manipulação
                try:
                    df = pd.DataFrame(table[1:], columns=header)
                except Exception:
                    # fallback caso a tabela esteja "desalinhada"
                    continue

                # criar dicionário de mapeamento: coluna_original -> nome_padrao
                col_map = {}
                for col in df.columns:
                    nh = normalize_header(col)
                    if "evento" in nh:
                        col_map[col] = "evento"
                    elif "dist" in nh:  # distancia, distancia km, distancia (km), etc.
                        col_map[col] = "distancia"
                    elif ("p. total" in nh) or ("p total" in nh) or ("p.total" in nh) or ("p total db" in nh) or ("p. total db" in nh) or (nh.startswith("p ") and "total" in nh):
                        col_map[col] = "p_total"
                    elif "perda" in nh and "total" not in nh:
                        col_map[col] = "perda"
                    elif "reflect" in nh or "reflet" in nh:
                        col_map[col] = "reflect"
                    elif "declive" in nh:
                        col_map[col] = "declive"
                    elif "sec" in nh or "secc" in nh:  # secção / secao / sec
                        col_map[col] = "seccao"
                    else:
                        # manter nome normalizado para possíveis usos
                        col_map[col] = nh.replace(" ", "_")

                # renomear colunas
                df = df.rename(columns=col_map)

                # se existe coluna distancia: extrair números e pegar maior
                if "distancia" in df.columns:
                    # limpar e extrair número em cada célula
                    # converte para string e processa
                    serie = df["distancia"].astype(str).map(clean_number_str)
                    nums = pd.to_numeric(serie, errors="coerce").dropna()
                    if not nums.empty:
                        # adicionar à lista global
                        distancias_encontradas.extend(nums.tolist())

                    # montar eventos com mapeamento consistente
                    for _, row in df.iterrows():
                        ev = {}
                        ev["Evento"] = row.get("evento") if "evento" in df.columns else None
                        ev["Distância (km)"] = None
                        raw_dist = row.get("distancia")
                        dist_clean = clean_number_str(raw_dist)
                        if dist_clean is not None:
                            try:
                                ev["Distância (km)"] = float(dist_clean)
                            except:
                                ev["Distância (km)"] = dist_clean
                        # Perda: preferir coluna 'perda' se existir, senão 'p_total'
                        perda_val = None
                        if "perda" in df.columns:
                            perda_val = row.get("perda")
                        elif "p_total" in df.columns:
                            perda_val = row.get("p_total")
                        ev["Perda (dB)"] = clean_number_str(perda_val)
                        # reflect
                        ev["Reflect. dB"] = row.get("reflect") if "reflect" in df.columns else None
                        ev["Declive"] = row.get("declive") if "declive" in df.columns else None
                        ev["Secção"] = row.get("seccao") if "seccao" in df.columns else None
                        # P. Total (dB)
                        p_total_val = row.get("p_total") if "p_total" in df.columns else None
                        ev["P. Total dB"] = clean_number_str(p_total_val)
                        eventos.append(ev)

                # tentar extrair perda total global a partir de coluna p_total (pegar o maior/último)
                if "p_total" in df.columns:
                    serie_p = df["p_total"].astype(str).map(clean_number_str)
                    nums_p = pd.to_numeric(serie_p, errors="coerce").dropna()
                    if not nums_p.empty:
                        perda_total = float(nums_p.max())

            # 2) SE AINDA NAO HOUVE TABELA BEM DETECTADA, tentar heurística por texto (linhas)
            if not distancias_encontradas:
                lines = text.splitlines()
                # procurar a linha de cabeçalho que contenha 'evento' e 'dist' (pode conter 'distância' sem acento)
                header_idx = None
                header_cols = None
                for i, line in enumerate(lines):
                    # normalizar versão sem acento
                    ln = normalize_header(line)
                    if "evento" in ln and ("distancia" in ln or "distância" in ln):
                        header_idx = i
                        # dividir cabeçalho por 2+ espaços/tab para formar colunas
                        header_cols = re.split(r"\s{2,}|\t", line.strip())
                        break
                if header_idx is not None:
                    # linhas seguintes até linha em branco ou até que pareçam não ser mais linhas de tabela
                    for rowline in lines[header_idx + 1:]:
                        if not rowline.strip():
                            break
                        parts = re.split(r"\s{2,}|\t", rowline.strip())
                        if len(parts) >= 2:
                            # segunda coluna é distância
                            dist_part = parts[1]
                            dist_clean = clean_number_str(dist_part)
                            if dist_clean:
                                try:
                                    dist_val = float(dist_clean)
                                    distancias_encontradas.append(dist_val)
                                except:
                                    pass
                            # Também montar evento mínimo (Evento, Distância, Perda se disponível)
                            ev = {}
                            ev["Evento"] = parts[0] if len(parts) > 0 else None
                            ev["Distância (km)"] = float(clean_number_str(parts[1])) if clean_number_str(parts[1]) else None
                            ev["Perda (dB)"] = clean_number_str(parts[2]) if len(parts) > 2 else None
                            eventos.append(ev)

            # 3) fallback: extrair números plausíveis do texto (apenas se nada encontrado)
            if not distancias_encontradas:
                # procurar números com 2-6 dígitos e parte decimal (ex.: 102.027)
                possible = re.findall(r"([0-9]{1,3}(?:[.,][0-9]{1,6}))", text)
                for p in possible:
                    v = clean_number_str(p)
                    if v:
                        try:
                            num = float(v)
                            # considerar distâncias plausíveis (>0.1 km)
                            if num >= 0.1:
                                distancias_encontradas.append(num)
                        except:
                            pass

    # depois de percorrer todas páginas: escolher MAIOR valor encontrado (última/maior distância)
    if distancias_encontradas:
        distancia_fibra = max(distancias_encontradas)

    # se ainda não conseguiu encontrar perda_total, tentar extrair do texto geral (backup)
    if perda_total is None:
        # ler todo o pdf rapidamente (se não foi feito) e buscar padrões
        try:
            with pdfplumber.open(uploaded_file) as pdf:
                full_text = ""
                for p in pdf.pages:
                    full_text += (p.extract_text() or "") + "\n"
            m = re.search(r"(perda total db|perda do trecho|perda total)\s*[:=]?\s*([\d.,]+)", full_text, re.IGNORECASE)
            if m:
                perda_total = float(m.group(2).replace(",", "."))
        except Exception:
            pass

    # Diagnóstico fibra (status)
    status = "OK"
    if distancia_fibra is not None and distancia_fibra < distancia_troco_km * 0.95:
        status = "Partida"
    elif perda_total is not None and perda_maxima_dB is not None and perda_total > perda_maxima_dB:
        status = "Atenuada"

    # converter eventos: garantir tipos numericos onde possivel
    for ev in eventos:
        # Distância (km)
        if ev.get("Distância (km)") is not None:
            try:
                ev["Distância (km)"] = float(ev["Distância (km)"])
            except:
                pass
        # Perda
        if ev.get("Perda (dB)") is not None:
            try:
                ev["Perda (dB)"] = float(str(ev["Perda (dB)"]).replace(",", "."))
            except:
                pass
        if ev.get("P. Total dB") is not None:
            try:
                ev["P. Total dB"] = float(str(ev["P. Total dB"]).replace(",", "."))
            except:
                pass

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
                # normalizar nomes das colunas para folha
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
# Interface Streamlit (sem alterações no layout)
# ==============================
st.set_page_config(page_title="Clean Up AutoProcess - PDF", layout="wide")

st.title("📡 Clean Up AutoProcess (PDF)")
st.write("Analisa relatórios OTDR em PDF (texto/tabela) por quadrimestre.")

# Inputs principais (mantidos)
distancia_troco = st.number_input("👉 Distância esperada do troço (km)", min_value=1.0, step=0.5)

comprimento_onda = st.selectbox("👉 Selecione o comprimento de onda (nm)", [1310, 1550], index=1)

perda_maxima = calcular_perda_maxima(distancia_troco, comprimento_onda)
st.write(f"🔎 **Perda máxima permitida do link (dB): {perda_maxima:.2f}**")

# Upload de 2 PDFs (mantido)
st.subheader("📂 Importar relatórios PDF")
col1, col2 = st.columns(2)
with col1:
    file_prev = st.file_uploader("Quadrimestre Anterior (PDF)", type=["pdf"], key="q_prev")
    q_prev = st.selectbox("Selecione quadrimestre anterior", ["Q1", "Q2", "Q3"], index=0)
with col2:
    file_curr = st.file_uploader("Quadrimestre Atual (PDF)", type=["pdf"], key="q_curr")
    q_curr = st.selectbox("Selecione quadrimestre atual", ["Q1", "Q2", "Q3"], index=1)

# Processamento (mantido)
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
