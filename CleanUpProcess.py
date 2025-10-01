import streamlit as st
import pandas as pd
import pdfplumber
import re
import os

# ==============================
# Função auxiliar: extrair distância testada
# ==============================
def extrair_distancia_testada(uploaded_file):
    """
    Lê o PDF e procura a distância testada.
    1) Tenta encontrar 'Fim da Fibra Km' no texto e pegar o valor abaixo.
    2) Caso não encontre, procura em tabelas e pega o maior valor na coluna 'Distância'.
    """
    distancia_fibra = None

    with pdfplumber.open(uploaded_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""

            # 🔹 1) Procurar "Fim da Fibra Km"
            match_dist = re.search(r"fim da fibra km\s*([\d.,]+)", text, re.IGNORECASE)
            if match_dist:
                distancia_fibra = float(match_dist.group(1).replace(",", "."))
                return distancia_fibra  # retorna logo que encontra

            # 🔹 2) Procurar em tabelas
            tables = page.extract_tables()
            for table in tables:
                if not table or len(table) < 2:
                    continue
                df = pd.DataFrame(table[1:], columns=table[0])
                df.columns = [c.strip().lower() for c in df.columns]

                if "distância" in df.columns:
                    try:
                        valores = pd.to_numeric(df["distância"], errors="coerce")
                        distancia_fibra = valores.max()
                        return distancia_fibra
                    except:
                        continue

    return distancia_fibra


# ==============================
# Função: extrair dados do PDF
# ==============================
def parse_pdf_otdr(uploaded_file, quadrimestre, distancia_troco_km, perda_maxima_dB):
    """
    Lê relatório OTDR em PDF.
    Extrai:
      - Fiber ID
      - Perda total
      - Distância testada (via função auxiliar)
      - Eventos
      - Status
    """
    fiber_id = os.path.splitext(uploaded_file.name)[0]
    perda_total = None
    eventos = []

    # 🔹 Usa função auxiliar para extrair distância
    distancia_fibra = extrair_distancia_testada(uploaded_file)

    with pdfplumber.open(uploaded_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""

            # Procurar perda total no texto
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

                if "evento" in df.columns:
                    for _, row in df.iterrows():
                        try:
                            ev = {
                                "Evento": row.get("evento"),
                                "Distância (km)": str(row.get("distância") or "").replace(",", "."),
                                "Perda dB": str(row.get("perda") or "").replace(",", "."),
                                "Reflect. dB": row.get("reflect.", ""),
                                "P. Total dB": row.get("p. total", "")
                            }
                            eventos.append(ev)
                        except Exception:
                            continue

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
