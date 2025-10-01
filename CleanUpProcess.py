import pdfplumber
import pandas as pd

def extrair_eventos_pdf(caminho_pdf):
    eventos = []

    with pdfplumber.open(caminho_pdf) as pdf:
        for pagina in pdf.pages:
            tabelas = pagina.extract_tables()
            for tabela in tabelas:
                # Procurar cabeçalho que começa com "Evento"
                if tabela and "Evento" in tabela[0][0]:
                    for linha in tabela[1:]:
                        if len(linha) >= 5:
                            evento = {
                                "Evento": linha[0],
                                "Distância Testada (km)": linha[1],
                                "Perda Total (dB)": linha[2],
                                "Reflect. dB": linha[3],
                                "P. Total dB": linha[4],
                            }
                            eventos.append(evento)

    return pd.DataFrame(eventos)


def calcular_perda_maxima(eventos_df):
    try:
        # Escolha do comprimento de onda
        print("\nSelecione o comprimento de onda:")
        print("1 - 1310 nm")
        print("2 - 1550 nm")
        opcao = input("Opção: ")

        if opcao == "1":
            comprimento_onda = 1310
            coeficiente = 0.33
        elif opcao == "2":
            comprimento_onda = 1550
            coeficiente = 0.22
        else:
            print("⚠️ Opção inválida.")
            return

        # Aplicar cálculo da perda máxima para cada evento
        eventos_df["Distância Testada (km)"] = pd.to_numeric(
            eventos_df["Distância Testada (km)"].str.replace(",", "."), errors="coerce"
        )
        eventos_df["Perda Total (dB)"] = pd.to_numeric(
            eventos_df["Perda Total (dB)"].str.replace(",", "."), errors="coerce"
        )

        eventos_df["Perda Máxima Permitida (dB)"] = eventos_df["Distância Testada (km)"] * coeficiente

        # Resultado
        print("\n--- Resultado ---")
        print(f"Comprimento de onda (nm): {comprimento_onda}")
        print(eventos_df.to_string(index=False))

    except Exception as e:
        print(f"⚠️ Erro: {e}")


# ---------------------------
# Exemplo de uso
# ---------------------------
caminho_pdf = "relatorio_otdr.pdf"  # Substitua pelo ficheiro do relatório OTDR
eventos_df = extrair_eventos_pdf(caminho_pdf)

if not eventos_df.empty:
    calcular_perda_maxima(eventos_df)
else:
    print("⚠️ Nenhuma tabela de eventos encontrada no PDF.")
