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

            # 🔹 Procurar explicitamente "Fim da Fibra Km" no texto
            lines = text.splitlines()
            for i, line in enumerate(lines):
                if "fim da fibra" in normalize_header(line):
                    if i + 1 < len(lines):  # pega a linha seguinte
                        val = clean_number_str(lines[i + 1])
                        if val:
                            try:
                                distancia_fibra = float(val)
                                distancias_encontradas.append(distancia_fibra)
                            except:
                                pass

            # 🔹 Tentar extrair tabelas
            tables = page.extract_tables()
            for table in tables:
                if not table or len(table) < 2:
                    continue

                header = table[0]
                try:
                    df = pd.DataFrame(table[1:], columns=header)
                except Exception:
                    continue

                # Normalizar colunas
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

    # Diagnóstico
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
