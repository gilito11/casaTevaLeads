"""
Tests completos para el sistema de filtrado de particulares.

Este módulo verifica que el filtrado funcione correctamente para:
- Detectar profesionales/inmobiliarias
- Detectar rechazo de inmobiliarias
- Decidir correctamente qué anuncios scrapear
"""

import pytest
from scrapers.utils.particular_filter import (
    es_profesional,
    permite_inmobiliarias,
    debe_scrapear,
    get_razon_rechazo,
)


class TestEsProfesional:
    """Tests para la función es_profesional()"""

    def test_nombre_contiene_inmobiliaria(self):
        """Debe detectar 'inmobiliaria' en el nombre"""
        data = {'nombre': 'Inmobiliaria Casa Bonita'}
        assert es_profesional(data) is True

    def test_nombre_contiene_agencia(self):
        """Debe detectar 'agencia' en el nombre"""
        data = {'nombre': 'Agencia Inmobiliaria del Este'}
        assert es_profesional(data) is True

    def test_nombre_contiene_real_estate(self):
        """Debe detectar 'real estate' en el nombre"""
        data = {'nombre': 'Barcelona Real Estate'}
        assert es_profesional(data) is True

    def test_descripcion_contiene_somos_agencia(self):
        """Debe detectar profesional en descripción"""
        data = {
            'nombre': 'Juan',
            'descripcion': 'Somos una agencia inmobiliaria con más de 20 años de experiencia'
        }
        assert es_profesional(data) is True

    def test_descripcion_contiene_promotora(self):
        """Debe detectar 'promotora' en descripción"""
        data = {
            'descripcion': 'Promotora de viviendas nuevas en Lleida'
        }
        assert es_profesional(data) is True

    def test_badges_profesional_verificado(self):
        """Debe detectar badge 'profesional verificado'"""
        data = {
            'nombre': 'Juan',
            'badges': ['profesional verificado', 'usuario activo']
        }
        assert es_profesional(data) is True

    def test_badges_agencia_verificada(self):
        """Debe detectar badge 'agencia verificada'"""
        data = {
            'nombre': 'María',
            'badges': ['agencia verificada']
        }
        assert es_profesional(data) is True

    def test_badges_pro(self):
        """Debe detectar badge 'pro'"""
        data = {
            'nombre': 'Carlos',
            'badges': ['pro']
        }
        assert es_profesional(data) is True

    def test_muchos_anuncios_activos(self):
        """Debe detectar como profesional si tiene >3 anuncios activos"""
        data = {
            'nombre': 'Pedro',
            'num_anuncios_activos': 10
        }
        assert es_profesional(data) is True

    def test_exactamente_4_anuncios_es_profesional(self):
        """Debe detectar como profesional con exactamente 4 anuncios"""
        data = {
            'nombre': 'Ana',
            'num_anuncios_activos': 4
        }
        assert es_profesional(data) is True

    def test_particular_normal(self):
        """Particular normal NO debe ser detectado como profesional"""
        data = {
            'nombre': 'Juan Pérez',
            'descripcion': 'Vendo piso por traslado',
            'badges': [],
            'num_anuncios_activos': 1
        }
        assert es_profesional(data) is False

    def test_3_anuncios_es_particular(self):
        """Con 3 anuncios o menos es particular"""
        data = {
            'nombre': 'María García',
            'num_anuncios_activos': 3
        }
        assert es_profesional(data) is False

    def test_case_insensitive_inmobiliaria(self):
        """Debe detectar variaciones de mayúsculas/minúsculas"""
        data = {'nombre': 'INMOBILIARIA todo en MAYÚSCULAS'}
        assert es_profesional(data) is True

    def test_case_insensitive_agencia(self):
        """Debe detectar 'AGENCIA' en mayúsculas"""
        data = {'descripcion': 'AGENCIA DE PROPIEDADES'}
        assert es_profesional(data) is True

    def test_campos_vacios(self):
        """Debe manejar campos vacíos correctamente"""
        data = {
            'nombre': '',
            'descripcion': '',
            'badges': [],
            'num_anuncios_activos': 0
        }
        assert es_profesional(data) is False

    def test_campos_none(self):
        """Debe manejar campos None correctamente"""
        data = {
            'nombre': None,
            'descripcion': None,
            'badges': None,
            'num_anuncios_activos': None
        }
        assert es_profesional(data) is False

    def test_diccionario_vacio(self):
        """Debe manejar diccionario vacío"""
        data = {}
        assert es_profesional(data) is False

    def test_servicios_inmobiliarios(self):
        """Debe detectar 'servicios inmobiliarios'"""
        data = {'nombre': 'Servicios Inmobiliarios Barcelona'}
        assert es_profesional(data) is True

    def test_gestoria_en_descripcion(self):
        """Debe detectar 'gestoría' en descripción"""
        data = {'descripcion': 'Gestoría inmobiliaria ofrece'}
        assert es_profesional(data) is True

    def test_asesor_inmobiliario(self):
        """Debe detectar 'asesor inmobiliario'"""
        data = {'nombre': 'Pedro - Asesor Inmobiliario'}
        assert es_profesional(data) is True


class TestPermiteInmobiliarias:
    """Tests para la función permite_inmobiliarias()"""

    def test_titulo_no_inmobiliarias(self):
        """Debe detectar 'NO INMOBILIARIAS' en título"""
        data = {'titulo': 'Piso en venta - NO INMOBILIARIAS'}
        assert permite_inmobiliarias(data) is False

    def test_titulo_no_agencias(self):
        """Debe detectar 'no agencias' en título"""
        data = {'titulo': 'Casa en venta, no agencias por favor'}
        assert permite_inmobiliarias(data) is False

    def test_descripcion_solo_particulares(self):
        """Debe detectar 'solo particulares' en descripción"""
        data = {
            'titulo': 'Piso en venta',
            'descripcion': 'Vendo piso por traslado. Solo particulares, gracias.'
        }
        assert permite_inmobiliarias(data) is False

    def test_descripcion_particular_a_particular(self):
        """Debe detectar 'particular a particular'"""
        data = {
            'descripcion': 'Trato de particular a particular, sin intermediarios'
        }
        assert permite_inmobiliarias(data) is False

    def test_descripcion_abstenerse_inmobiliarias(self):
        """Debe detectar 'abstenerse inmobiliarias'"""
        data = {
            'descripcion': 'Piso céntrico. Abstenerse inmobiliarias.'
        }
        assert permite_inmobiliarias(data) is False

    def test_descripcion_abstenerse_agencias(self):
        """Debe detectar 'abstenerse agencias'"""
        data = {
            'descripcion': 'Abstenerse agencias. Solo interesados directos.'
        }
        assert permite_inmobiliarias(data) is False

    def test_descripcion_no_intermediarios(self):
        """Debe detectar 'no intermediarios'"""
        data = {
            'descripcion': 'Vendo sin comisiones. No intermediarios.'
        }
        assert permite_inmobiliarias(data) is False

    def test_descripcion_solo_comprador_directo(self):
        """Debe detectar 'solo comprador directo'"""
        data = {
            'descripcion': 'Solo comprador directo, no agencias'
        }
        assert permite_inmobiliarias(data) is False

    def test_descripcion_sin_agencias(self):
        """Debe detectar 'sin agencias'"""
        data = {
            'descripcion': 'Venta directa sin agencias'
        }
        assert permite_inmobiliarias(data) is False

    def test_particular_que_permite(self):
        """Particular normal que SÍ permite inmobiliarias"""
        data = {
            'titulo': 'Piso en venta en Lleida',
            'descripcion': 'Piso de 3 habitaciones, buen estado, exterior'
        }
        assert permite_inmobiliarias(data) is True

    def test_case_insensitive_no_inmobiliarias(self):
        """Debe detectar variaciones de mayúsculas"""
        data = {'titulo': 'Piso - NO INMOBILIARIAS'}
        assert permite_inmobiliarias(data) is False

    def test_case_insensitive_solo_particulares(self):
        """Debe detectar 'SOLO PARTICULARES' en mayúsculas"""
        data = {'descripcion': 'SOLO PARTICULARES'}
        assert permite_inmobiliarias(data) is False

    def test_titulo_y_descripcion_rechazo(self):
        """Debe detectar rechazo en título O descripción"""
        data = {
            'titulo': 'Piso en venta - no agencias',
            'descripcion': 'Buen estado'
        }
        assert permite_inmobiliarias(data) is False

    def test_campos_vacios(self):
        """Debe manejar campos vacíos (permite por defecto)"""
        data = {
            'titulo': '',
            'descripcion': ''
        }
        assert permite_inmobiliarias(data) is True

    def test_campos_none(self):
        """Debe manejar campos None (permite por defecto)"""
        data = {
            'titulo': None,
            'descripcion': None
        }
        assert permite_inmobiliarias(data) is True

    def test_diccionario_vacio(self):
        """Debe manejar diccionario vacío (permite por defecto)"""
        data = {}
        assert permite_inmobiliarias(data) is True

    def test_sin_intermediarios(self):
        """Debe detectar 'sin intermediarios'"""
        data = {'descripcion': 'Venta directa sin intermediarios'}
        assert permite_inmobiliarias(data) is False

    def test_trato_directo(self):
        """Debe detectar 'trato directo'"""
        data = {'descripcion': 'Preferible trato directo con comprador'}
        assert permite_inmobiliarias(data) is False

    def test_particular_vende(self):
        """Debe detectar 'particular vende'"""
        data = {'titulo': 'Particular vende piso'}
        assert permite_inmobiliarias(data) is False

    def test_vendo_como_particular(self):
        """Debe detectar 'vendo como particular'"""
        data = {'descripcion': 'Vendo como particular, no soy profesional'}
        assert permite_inmobiliarias(data) is False


class TestDebeScrapear:
    """Tests para la función debe_scrapear()"""

    def test_profesional_no_scrapear(self):
        """NO debe scrapear anuncios de profesionales"""
        data = {'nombre': 'Inmobiliaria XYZ'}
        assert debe_scrapear(data) is False

    def test_particular_rechaza_no_scrapear(self):
        """NO debe scrapear si particular rechaza inmobiliarias"""
        data = {
            'nombre': 'Juan Pérez',
            'descripcion': 'NO INMOBILIARIAS por favor'
        }
        assert debe_scrapear(data) is False

    def test_particular_permite_si_scrapear(self):
        """SÍ debe scrapear particular que permite inmobiliarias"""
        data = {
            'nombre': 'María García',
            'titulo': 'Piso en venta',
            'descripcion': 'Piso de 3 habitaciones en buen estado',
            'num_anuncios_activos': 1
        }
        assert debe_scrapear(data) is True

    def test_profesional_aunque_no_rechace(self):
        """NO scrapear profesional aunque no rechace explícitamente"""
        data = {
            'nombre': 'Agencia Inmobiliaria',
            'descripcion': 'Piso en venta'
        }
        assert debe_scrapear(data) is False

    def test_particular_nuevo_si_scrapear(self):
        """SÍ scrapear particular nuevo (0 anuncios)"""
        data = {
            'nombre': 'Pedro López',
            'titulo': 'Primera venta',
            'num_anuncios_activos': 0
        }
        assert debe_scrapear(data) is True

    def test_profesional_con_muchos_anuncios(self):
        """NO scrapear usuario con muchos anuncios"""
        data = {
            'nombre': 'Carlos',
            'num_anuncios_activos': 15
        }
        assert debe_scrapear(data) is False

    def test_particular_con_badge_pro(self):
        """NO scrapear si tiene badge profesional"""
        data = {
            'nombre': 'Ana',
            'badges': ['pro'],
            'titulo': 'Piso en venta'
        }
        assert debe_scrapear(data) is False

    def test_caso_real_particular_valido(self):
        """Caso real: particular válido para scrapear"""
        data = {
            'nombre': 'Roberto Fernández',
            'titulo': 'Piso 3 hab Lleida centro',
            'descripcion': 'Vendo piso por traslado laboral. 3 habitaciones, 2 baños, garaje incluido.',
            'badges': ['usuario verificado'],
            'num_anuncios_activos': 1
        }
        assert debe_scrapear(data) is True

    def test_caso_real_inmobiliaria(self):
        """Caso real: inmobiliaria NO debe ser scrapeada"""
        data = {
            'nombre': 'Inmobiliaria Lleida Centre',
            'titulo': 'Piso en venta',
            'descripcion': 'Disponemos de amplio catálogo de propiedades',
            'badges': ['agencia verificada'],
            'num_anuncios_activos': 45
        }
        assert debe_scrapear(data) is False

    def test_caso_real_particular_rechaza(self):
        """Caso real: particular que rechaza inmobiliarias"""
        data = {
            'nombre': 'Laura Martínez',
            'titulo': 'Piso en venta - NO INMOBILIARIAS',
            'descripcion': 'Vendo piso heredado. Abstenerse agencias e intermediarios.',
            'num_anuncios_activos': 1
        }
        assert debe_scrapear(data) is False


class TestGetRazonRechazo:
    """Tests para la función get_razon_rechazo()"""

    def test_razon_es_profesional(self):
        """Debe retornar razón cuando es profesional"""
        data = {'nombre': 'Inmobiliaria ABC'}
        razon = get_razon_rechazo(data)
        assert razon == 'Es profesional/inmobiliaria'

    def test_razon_rechaza_inmobiliarias(self):
        """Debe retornar razón cuando rechaza inmobiliarias"""
        data = {
            'nombre': 'Juan',
            'descripcion': 'NO INMOBILIARIAS'
        }
        razon = get_razon_rechazo(data)
        assert razon == 'Rechaza contacto de inmobiliarias'

    def test_sin_razon_rechazo(self):
        """Debe retornar None si debe ser scrapeado"""
        data = {
            'nombre': 'María',
            'titulo': 'Piso en venta',
            'num_anuncios_activos': 1
        }
        razon = get_razon_rechazo(data)
        assert razon is None

    def test_prioridad_profesional(self):
        """Si es profesional Y rechaza, prioriza 'es profesional'"""
        data = {
            'nombre': 'Inmobiliaria XYZ',
            'descripcion': 'NO INMOBILIARIAS'  # Contradicción
        }
        razon = get_razon_rechazo(data)
        assert razon == 'Es profesional/inmobiliaria'


class TestCasosEdge:
    """Tests para casos edge y validaciones especiales"""

    def test_texto_con_espacios_extra(self):
        """Debe manejar textos con espacios extra"""
        data = {'nombre': '  Inmobiliaria   Casa Bonita  '}
        assert es_profesional(data) is True

    def test_texto_con_saltos_linea(self):
        """Debe manejar textos con saltos de línea"""
        data = {
            'descripcion': 'Piso en venta\n\nNO INMOBILIARIAS\n\nGracias'
        }
        assert permite_inmobiliarias(data) is False

    def test_badges_no_lista(self):
        """Debe manejar badges que no es una lista"""
        data = {
            'nombre': 'Juan',
            'badges': 'pro'  # String en vez de lista
        }
        # No debe crashear, debe manejarlo gracefully
        resultado = es_profesional(data)
        assert isinstance(resultado, bool)

    def test_num_anuncios_string(self):
        """Debe manejar num_anuncios_activos como string"""
        data = {
            'nombre': 'Pedro',
            'num_anuncios_activos': '10'  # String en vez de int
        }
        # No debe crashear
        resultado = es_profesional(data)
        assert isinstance(resultado, bool)

    def test_badges_con_none(self):
        """Debe manejar lista de badges con elementos None"""
        data = {
            'badges': [None, 'usuario activo', None]
        }
        resultado = es_profesional(data)
        assert resultado is False

    def test_unicode_caracteres_especiales(self):
        """Debe manejar caracteres especiales y acentos"""
        data = {
            'descripcion': 'Gestoría inmobiliaria - São Paulo'
        }
        assert es_profesional(data) is True

    def test_no_inmobiliarias_en_descripcion_no_es_profesional(self):
        """Si dice 'NO INMOBILIARIAS', no debe detectarse como profesional"""
        data = {'descripcion': 'Vendo piso. NO INMOBILIARIAS por favor'}
        # Aunque contiene la palabra "inmobiliarias", el contexto indica rechazo
        assert es_profesional(data) is False
