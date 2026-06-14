from pipeline.assets.medallion import (
    _normalizar_listado_pozos,
    _normalizar_produccion_no_convencional,
)


def test_normaliza_listado_pozos_basico():
    raw_csv = (
        "\ufeffidpozo,sigla,coordenadax,coordenaday,profundidad,gasplus,cuenca,provincia\n"
        "10,ABC,-68.5,-38.2,2500,si,NEUQUINA,Neuquen\n"
    ).encode("utf-8")

    df = _normalizar_listado_pozos(raw_csv, "2026-06-14")

    assert list(df["idpozo"]) == [10]
    assert df.loc[0, "longitud"] == -68.5
    assert df.loc[0, "latitud"] == -38.2
    assert bool(df.loc[0, "gasplus"]) is True
    assert str(df.loc[0, "fecha_extraccion"]) == "2026-06-14"


def test_normaliza_produccion_deduplica_y_marca_flags():
    raw_csv = (
        "idempresa,anio,mes,idpozo,prod_pet,prod_gas,prod_agua,iny_agua,iny_gas,"
        "iny_co2,iny_otro,tef,tipoextraccion,tipoestado,tipopozo,fecha_data,"
        "rectificado,habilitado,empresa,coordenadax,coordenaday,profundidad,"
        "idareapermisoconcesion,idareayacimiento,idcuenca,idprovincia\n"
        "YPF,2026,2,10,1,2,3,0,0,0,0,30,Surgencia,Activo,Gasifero,"
        "2026-02-28,f,t,YPF,-68.5,-38.2,2500,A1,Y1,C1,P1\n"
        "YPF,2026,2,10,-1,-2,3,0,0,0,0,35,Surgencia,Activo,Gasifero,"
        "2026-02-28,t,t,YPF,55,-70,20000,A1,Y1,C1,P1\n"
    ).encode("utf-8")

    df = _normalizar_produccion_no_convencional(raw_csv, "2026-06-14")

    assert len(df) == 1
    row = df.iloc[0]
    assert row["prod_pet"] == -1
    assert str(row["fecha_periodo"].date()) == "2026-02-28"
    assert bool(row["rectificado"]) is True
    assert bool(row["flag_prod_negativa"]) is True
    assert bool(row["flag_tef_fuera_rango"]) is True
    assert bool(row["flag_profundidad_fuera_rango"]) is True
    assert bool(row["flag_coordenadas_fuera_rango"]) is True
