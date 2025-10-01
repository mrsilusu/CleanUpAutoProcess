import streamlit as st
import pdfplumber
import pandas as pd

# ==============================
# Função para extrair eventos
# ==============================
def extrair_eventos_pdf(arquivo_pdf):
    eventos = []
    with pdfplumber.open(arquivo_pdf) as pdf:
        for pagina in pdf.pages:
            tabelas = pagina.extract_tables()
            for tabela in tabelas:
                if not tabela:
                    continue

                colunas = tabela[0]
                if "Evento" in colunas:
                    for linha in tabela[1:]:
                        if len(linha) >= 5:  # Garante que há todas as colunas
                            evento = {
                                "Evento": linha[0],
                                "Distância Testada (km)": linha[1],
                                "Perda Total (dB)": linha[2],  # aqui usamos Perda dB
                                "Reflect. dB": linha[3],
                                "P. Total dB": linha[4]
                            }
                            eventos.append(evento)
    return pd.DataFrame(eventos)

# ==============================
# Interface Streamlit
# ==============================
st.set_page_config(page_title="Extração de Eventos OTDR", layout="wide")

st.title("📊 Extração de Eventos do Relatório OTDR")

# Upload do PDF
arquivo_pdf = st.file_uploader("Carregue o PDF do relatório OTDR", type="pdf")

# Processamento
if arquivo_pdf is not None:
    try:
        eventos_df = extrair_eventos_pdf(arquivo_pdf)

        if not eventos_df.empty:
            st.success("✅ Tabela de eventos extraída com sucesso!")
            st.dataframe(eventos_df, use_container_width=True)

            # Opção para download em Excel
            excel_bytes = eventos_df.to_excel(index=False, engine="openpyxl")
            st.download_button(
                label="⬇️ Baixar tabela em Excel",
                data=excel_bytes,
                file_name="eventos_otdr.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.warning("⚠️ Nenhuma tabela de eventos foi encontrada no PDF.")
    except Exception as e:
        st.error(f"Erro ao processar o PDF: {e}")
