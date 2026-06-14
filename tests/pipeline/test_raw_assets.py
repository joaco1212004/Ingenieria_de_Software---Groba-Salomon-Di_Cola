from pipeline.assets.raw import _leer_csv_bronze, _normalizar_nombre_columna


def test_normaliza_nombre_columna_para_sql():
    assert _normalizar_nombre_columna("\ufeffCoordena da-X") == "coordena_da_x"
    assert _normalizar_nombre_columna(" idPozo ") == "idpozo"


def test_lee_csv_bronze_con_columnas_unicas():
    raw_csv = "idpozo,idpozo,coordenada-x\n1,2,-68.5\n".encode("utf-8")

    df = _leer_csv_bronze(raw_csv)

    assert list(df.columns) == ["idpozo", "idpozo_1", "coordenada_x"]
    assert df.loc[0, "idpozo"] == 1
