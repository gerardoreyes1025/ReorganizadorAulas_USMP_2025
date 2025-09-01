
##En realidad esto muestra las aulas libres
def get_ocupaciones_aula(connection, codigo_aula, ano='2025', semestre='2'):
    query = f"""
    SELECT 
        OFE.CODIGODIA, 
        OFE.HORAINICIO, 
        OFE.HORAFIN, 
        'OFERTA' AS ORIGEN, 
        OFE.CLAVEEVENTO AS DATO1, 
        OFE.ABREVIATURAEVENTO AS DATO2,
        (SELECT CAPACIDADMAXIMA FROM EVENTO WHERE CLAVE = OFE.CLAVEEVENTO LIMIT 1) AS CAPACIDADREQ,
        (SELECT CAPACIDADMAXIMA FROM EVENTO WHERE CLAVE = OFE.CLAVEEVENTO LIMIT 1) AS CAPACIDADMAXIMA,
        (SELECT EVE.DENOMINACION FROM EVENTO EVE WHERE EVE.ABREVIATURA = OFE.ABREVIATURAEVENTO LIMIT 1) AS NOMBRE_CURSO,
        (
            SELECT ESC.DENOMINACION
            FROM EVENTO EVE2
            JOIN PAQUETEEVENTOS PE 
                ON EVE2.ABREVIATURAPAQUETEEVENTOS = PE.ABREVIATURA
                AND PE.ANO = %s
                AND PE.SEMESTRE = %s
            JOIN PLANESTUDIOS PL ON PE.CLAVEPLANESTUDIOS = PL.CLAVE
            JOIN ESCUELA ESC ON PL.CLAVEESCUELA = ESC.CLAVE
            WHERE EVE2.CLAVE = OFE.CLAVEEVENTO
            AND EVE2.ANO = %s
            AND EVE2.SEMESTRE = %s
            LIMIT 1
        ) AS NOMBRE_PROGRAMA,
        (
            SELECT CONCAT(PER.APELLIDOPATERNO, ' ', PER.APELLIDOMATERNO, ', ', PER.NOMBRES)
            FROM PERSONA PER
            WHERE PER.CODIGOSAP = OFE.CODIGOSAPDOCENTE
            LIMIT 1
        ) AS NOMBRE_DOCENTE
    FROM OFERTA OFE
    WHERE OFE.CODIGOAULA = %s AND OFE.ANO = %s AND OFE.SEMESTRE = %s

    UNION ALL

    SELECT 
        CODIGODIA, HORAINICIO, HORAFIN, 'SEPARACIONAULA' AS ORIGEN, CODIGOACTIVIDAD AS DATO1, COMENTARIO AS DATO2,
        60 AS CAPACIDADREQ,
        NULL AS CAPACIDADMAXIMA,
        NULL AS NOMBRE_CURSO,
        NULL AS NOMBRE_PROGRAMA,
        NULL AS NOMBRE_DOCENTE
    FROM SEPARACIONAULA
    WHERE CODIGOAULA = %s AND FECHA >= CURDATE()

    UNION ALL

    SELECT 
        HOR.CODIGODIA, HOR.HORAINICIO, HOR.HORAFIN, 'CARGANOLECTIVA' AS ORIGEN, CNL.CODIGOACTIVIDADNOLECTIVA AS DATO1, CNL.CODIGOTIPOACTIVIDADNOLECTIVA AS DATO2,
        60 AS CAPACIDADREQ,
        NULL AS CAPACIDADMAXIMA,
        NULL AS NOMBRE_CURSO,
        NULL AS NOMBRE_PROGRAMA,
        NULL AS NOMBRE_DOCENTE
    FROM HORARIOCARGANOLECTIVA HOR
    JOIN CARGANOLECTIVA CNL ON HOR.CONSECUTIVOCARGANOLECTIVA = CNL.CONSECUTIVOCARGANOLECTIVA
    WHERE CNL.CODIGOAULA = %s AND CNL.ANO = %s AND CNL.SEMESTRE = %s

    ORDER BY CODIGODIA, HORAINICIO
    """
    params = (
        ano, semestre, ano, semestre,  # Para NOMBRE_PROGRAMA subquery
        codigo_aula, ano, semestre,    # Para el WHERE principal
        # ...otros params para los UNION ALL...
        codigo_aula, codigo_aula, ano, semestre
    )
    # params = (codigo_aula, ano, semestre, codigo_aula, codigo_aula, ano, semestre)

    cursor = connection.cursor(dictionary=True)
    cursor.execute(query, params)
    results = cursor.fetchall()
    cursor.close()
    return results




##Esto si saca aulas ocupadas xd
def get_ocupaciones(connection, campus_code, pabellon_codes, ano='2025', semestre='2'):
    pabellon_placeholders = ','.join(['%s'] * len(pabellon_codes))
    query = f"""
    SELECT 
        AULA.CODIGO, 
        AULA.DENOMINACION, 
        AULA.CAPACIDAD, 
        (
            SELECT GROUP_CONCAT(CONCAT(OFE.CODIGODIA, '-', OFE.HORAINICIO, '-', OFE.HORAFIN) SEPARATOR ';')
            FROM OFERTA OFE
            WHERE OFE.CODIGOAULA = AULA.CODIGO
              AND OFE.ANO = %s
              AND OFE.SEMESTRE = %s
        ) AS OFERTAS,
        (
            SELECT GROUP_CONCAT(CONCAT(HOR.CODIGODIA, '-', HOR.HORAINICIO, '-', HOR.HORAFIN) SEPARATOR ';')
            FROM HORARIOCARGANOLECTIVA HOR
            JOIN CARGANOLECTIVA CNL ON HOR.CONSECUTIVOCARGANOLECTIVA = CNL.CONSECUTIVOCARGANOLECTIVA
            WHERE CNL.CODIGOAULA = AULA.CODIGO
              AND CNL.ANO = %s
              AND CNL.SEMESTRE = %s
        ) AS CARGANOLECTIVA,
        (
            SELECT GROUP_CONCAT(CONCAT(SEP.CODIGODIA, '-', SEP.HORAINICIO, '-', SEP.HORAFIN) SEPARATOR ';')
            FROM SEPARACIONAULA SEP
            WHERE SEP.CODIGOAULA = AULA.CODIGO
              AND SEP.FECHA BETWEEN (SELECT FECHAINICIO FROM SEMESTRE WHERE CONCAT(ANO, SEMESTRE) = %s)
              AND (SELECT FECHAFIN FROM SEMESTRE WHERE CONCAT(ANO, SEMESTRE) = %s)
              AND SEP.FECHA >= CURDATE()
        ) AS SEPARACIONESAULA
    FROM AULA
    JOIN PABELLON PAB ON AULA.CODIGOPABELLON = PAB.CODIGO
    WHERE PAB.CODIGOCAMPUS = %s
      AND AULA.CODIGOPABELLON IN ({pabellon_placeholders})
      AND AULA.CAPACIDAD >= 0
      AND AULA.VIGENCIA = 1
      AND AULA.CODIGO REGEXP '^[0-9]+$'
      AND AULA.CODIGO NOT IN ('2101305', '2101306', '2101307', '2101308', '2101105')
    ORDER BY AULA.DENOMINACION ASC, AULA.CODIGO ASC;
    """
    params = [
        ano, semestre,      # OFERTA
        ano, semestre,      # CARGANOLECTIVA
        ano + semestre, ano + semestre,  # SEPARACIONAULA
        campus_code,
        *pabellon_codes     # Los pabellones deben ir al final
    ]
    cursor = connection.cursor(dictionary=True)
    cursor.execute(query, params)
    results = cursor.fetchall()
    cursor.close()
    return results