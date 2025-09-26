from src.db.queries import get_aula_ocupadasas
from src.db.queries import get_aula_libre

def parse_bloques(bloques_str):
    bloques = []
    if not bloques_str:
        return bloques
    for bloque in bloques_str.split(';'):
        if bloque:
            partes = bloque.split('-')
            if len(partes) == 3:
                bloques.append((partes[0], partes[1], partes[2]))
    return bloques


    
def sumar_minutos(hora, minutos):
    h, m = map(int, hora.split(":"))
    m += minutos
    h += m // 60
    m = m % 60
    return f"{h:02d}:{m:02d}"

class AulaLogic:
    def __init__(self, connection):
        self.connection = connection

    def fetch_libres(self, campus_code, pabellon_codes, ano='2025', semestre='2'):
        aulas = get_aula_ocupadasas(self.connection, campus_code, pabellon_codes, ano, semestre)
        dias = ['LU', 'MA', 'MI', 'JU', 'VI', 'SA', 'DO']
        hora_inicio_jornada = '07:00'
        hora_fin_jornada = '23:00'
        libres = {}

        for aula in aulas:
            key = (aula['CODIGO'], aula['DENOMINACION'], aula['CAPACIDAD'])
            ocupados = []
            ocupados += parse_bloques(aula['OFERTAS'])
            ocupados += parse_bloques(aula['CARGANOLECTIVA'])
            ocupados += parse_bloques(aula['SEPARACIONESAULA'])

            ocupados_por_dia = {dia: [] for dia in dias}
            for dia, ini, fin in ocupados:
                ocupados_por_dia[dia].append((ini, fin))

            libres[key] = []
            for dia in dias:
                bloques = sorted(ocupados_por_dia[dia])
                libre_inicio = hora_inicio_jornada
                for occ_ini, occ_fin in bloques:
                    if libre_inicio < occ_ini:
                        libres[key].append({'dia': dia, 'inicio': libre_inicio, 'fin': occ_ini})
                    libre_inicio = max(libre_inicio, occ_fin)
                if libre_inicio < hora_fin_jornada:
                    libres[key].append({'dia': dia, 'inicio': libre_inicio, 'fin': hora_fin_jornada})


        libres_ordenados = dict(sorted(libres.items(), key=lambda x: (x[0][1], x[0][0])))
        return libres_ordenados
    
    def get_aula_libre(self, campus_code, pabellon_codes, ano='2025', semestre='2'):
        return get_aula_libre(self.connection, campus_code, pabellon_codes, ano, semestre)