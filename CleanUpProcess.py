import streamlit as st
import pdfplumber
import re

def extrair_dados_pdf(uploaded_file):
    dados = {
        "fiber_id": uploaded_file.name,
        "distancia_esperada": None,
        "perda_total": None,
        "eventos_criticos": []
    }

    with pdfplumber.open(uploaded_file) as pdf:
        for pagina in pdf.pages:
            texto = pagina.extract_text()

            # Procurar distância esperada
            match_dist = re.search(r"(Fim da Fibra Km|Comprimento do trecho)\D*([\d,.]+)", texto, re.IGNORECASE)
            if match_dist:
                dados["distancia_esperada"] = float(match_dist.group(2).replace(",", "."))

            # Procurar perda total
            match_perda = re.search(r"(Perda Total dB|Perda do trecho)\D*([\d,.]+)", texto, re.IGNORECASE)
            if match_perda:
                dados["perda_total"] = float(match_perda.group(2).replace(",", "."))

            # Procurar eventos críticos (>0.2 dB)
            eventos = re.findall(r"([\d,.]+)\s*dB", texto)
            for e in eventos:
                valor = float(e.replace(",", "."))
                if valor > 0.2:
                    dados["eventos_criticos"].append(valor)

    return dados

def calcular_perda_maxima(distancia, comprimento_onda):
    if comprimento_onda == 1310:
        return distancia * 0.33
    elif comprimento_onda == 1550:
        return distancia * 0.22
    else:
        return None

def avaliar_status(distancia_pdf, perda_total, perda_maxima):
    if distancia_pdf is None or perda_total is None or perda_maxima is None:
        return "Dados insuficientes"

    if perda_total > perda_maxima:
        return "Atenuada"
    return "OK"

# ---------------- INTERFACE STREAMLIT ---------------- #

st.title("📊 Analisador de Relatórios OTDR (PDF)")

uploaded_file = st.file_uploader("Carregar relatório OTDR em PDF", type=["pdf"])

if uploaded_file:
    dados = extrair_dados_pdf(uploaded_file)

    st.subheader("📑 Dados Extraídos do PDF")
    st.write(f"**Fiber ID:** {dados['fiber_id']}")
    st.write(f"**Distância esperada (km):** {dados['distancia_esperada']}")
    st.write(f"**Perda Total (dB):** {dados['perda_total']}")
    st.write(f"**Eventos Críticos (>0.2 dB):** {dados['eventos_criticos']}")

    if dados["distancia_esperada"]:
        st.subheader("⚙️ Cálculo Automático")
        comprimento_onda = st.radio("Selecione o comprimento de onda:", [1310, 1550])

        perda_maxima = calcular_perda_maxima(dados["distancia_esperada"], comprimento_onda)

        st.write(f"**Comprimento de Onda:** {comprimento_onda} nm")
        st.write(f"**Perda Máxima Permitida (dB):** {perda_maxima:.2f}")

        status = avaliar_status(dados["distancia_esperada"], dados["perda_total"], perda_maxima)
        st.subheader("📌 Status da Fibra")
        st.success(status if status == "OK" else f"⚠️ {status}")
