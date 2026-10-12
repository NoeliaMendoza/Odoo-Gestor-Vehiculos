"""Lee la consulta pública de ANT por placa; no ejecuta acciones en el portal."""
import re
import time
from datetime import datetime
from decimal import Decimal, InvalidOperation
from urllib.parse import parse_qs, urlsplit

import pytz
import requests
from lxml import html

BASE = 'https://consultaweb.ant.gob.ec/PortalWEB/paginas/clientes/'
STATES = {'P': 'pending', 'R': 'disputed', 'A': 'cancelled', 'G': 'paid', 'C': 'agreement'}


class AntError(ValueError):
    """La respuesta no permite afirmar que la consulta esté completa."""


def normalize_plate(value):
    plate = re.sub(r'[\s-]', '', value or '').upper()
    if not re.fullmatch(r'[A-Z]{2,3}[0-9]{3,4}[A-Z]?', plate):
        raise AntError('Escribe una placa válida, por ejemplo ABC-1234.')
    return plate


def clean(value):
    return ' '.join(value.split())


def number(value):
    text = str(value).replace('$', '').replace(' ', '').strip()
    if ',' in text:
        text = text.replace('.', '').replace(',', '.')
    try:
        result = Decimal(text)
        if not result.is_finite():
            raise InvalidOperation
        return float(result)
    except InvalidOperation as exc:
        raise AntError('La ANT devolvió un importe no reconocido.') from exc


def date(value):
    if not value.strip():
        return False
    try:
        return datetime.strptime(value.strip(), '%d-%m-%Y').date().isoformat()
    except ValueError as exc:
        raise AntError('La ANT devolvió una fecha no reconocida.') from exc


def timestamp(value):
    if not value or str(value).strip().lower() in ('null', '-'):
        return False
    try:
        local = datetime.fromisoformat(str(value).strip())
        if local.tzinfo is None:
            local = pytz.timezone('America/Guayaquil').localize(local)
        return local.astimezone(pytz.UTC).replace(tzinfo=None).strftime('%Y-%m-%d %H:%M:%S')
    except ValueError as exc:
        raise AntError('La ANT devolvió una hora no reconocida.') from exc


def parse_vehicle(body, plate):
    tree = html.fromstring(body)
    shown = tree.xpath('//td[contains(@class,"titulo2")]/strong/text()')
    if not any(normalize_plate(p) == plate for p in shown):
        raise AntError('La ANT no devolvió la ficha de esta placa. No se modificaron los datos anteriores.')
    labels = {}
    for td in tree.xpath('//td[contains(@class,"titulo")]'):
        following = td.getnext()
        if following is not None and 'detalle_formulario' in following.get('class', ''):
            labels[clean(td.text_content()).rstrip(':').strip()] = clean(following.text_content())
    required = ['Marca', 'Modelo', 'Año', 'Color', 'Clase', 'Servicio', 'Año de Matrícula', 'Fecha de Matrícula', 'Fecha de Caducidad']
    if any(key not in labels for key in required) or not labels['Marca'] or not labels['Modelo']:
        raise AntError('El formato de la ficha ANT cambió o está incompleto.')
    urls = re.findall(r"url\s*:\s*['\"](clp_json_citaciones\.jsp\?[^'\"]+)", body)
    balance = tree.xpath('//iframe[@id="iframe_estado_cuenta"]/@src')
    if not urls or not balance:
        raise AntError('No se encontraron las consultas de citaciones de la ANT.')
    counts = {}
    for radio in tree.xpath('//input[@name="radiobutton"]'):
        code = radio.get('value')
        match = re.search(r'\((\d+)\)', radio.getparent().text_content())
        if code in STATES and match:
            counts[code] = int(match.group(1))
    if set(counts) != set(STATES):
        raise AntError('La ANT no devolvió todos los estados de citaciones.')
    # Sólo se reutilizan parámetros de las rutas públicas conocidas; nunca un host arbitrario.
    params = {}
    allowed = ('ps_id_contrato', 'ps_id_persona')
    for url in urls:
        candidate = {key: values[0] for key, values in parse_qs(urlsplit(url).query).items()}
        if all(candidate.get(key, '').isdigit() for key in allowed):
            params = candidate
            break
    if any(not params.get(k, '').isdigit() for k in allowed):
        raise AntError('La ANT no devolvió los identificadores de consulta.')
    params = {key: params[key] for key in allowed}
    params.update(ps_placa=plate, ps_identificacion=plate, ps_tipo_identificacion='PLA')
    return labels, counts, params


def parse_balance(body):
    tree = html.fromstring(body)
    mapping = {'Valor Pendiente': 'pending', 'Valor Convenio': 'agreement', 'Intereses Pendiente': 'interest', 'Total remisión': 'remission', 'ANT': 'ant', 'TOTAL': 'total'}
    totals = {}
    for td in tree.xpath('//td'):
        key = clean(td.text_content()).replace('$', '').rstrip(' :')
        if key in mapping and td.getnext() is not None:
            totals[mapping[key]] = number(td.getnext().text_content())
    if set(totals) != set(mapping.values()):
        raise AntError('El estado de cuenta de la ANT está incompleto.')
    return totals


def parse_row(row, status, plate):
    cells = row.get('cell')
    if not isinstance(cells, list) or len(cells) < 20 or not str(row.get('id', '')).isdigit():
        raise AntError('El detalle de una citación no tiene el formato esperado.')
    if str(cells[1]) != str(row['id']) or normalize_plate(cells[4]) != plate:
        raise AntError('Una citación no corresponde a la placa consultada.')
    return dict(external_id=str(row['id']), citation_number=cells[3], entity=cells[2],
                plate=plate, status=status, issued_at=timestamp(cells[6]), notified_at=timestamp(cells[7]),
                payment_deadline=cells[8], points=number(cells[9]), sanction=number(cells[13]),
                penalty=number(cells[14]), remission=number(cells[15]), total=number(cells[16]),
                article=clean(cells[17]), blocked=cells[19] == 'B')


def fetch_vehicle(plate, session=None):
    """Obtiene ficha, saldo y TODAS las páginas; falla antes de guardar si falta alguna."""
    plate = normalize_plate(plate)
    own_session = session is None
    session = session or requests.Session()
    deadline = time.monotonic() + 50

    def get(path, params):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise AntError('La ANT tardó demasiado. Intenta consultar nuevamente.')
        response = session.get(BASE + path, params=params, timeout=(5, min(15, remaining)), allow_redirects=False)
        response.raise_for_status()
        if response.status_code != 200:
            raise AntError('La ANT no entregó una respuesta válida.')
        if len(response.content) > 3_000_000:
            raise AntError('La respuesta ANT excede el tamaño previsto.')
        return response

    try:
        response = get('clp_grid_citaciones.jsp', dict(ps_tipo_identificacion='PLA', ps_identificacion=plate, ps_placa=''))
        labels, counts, params = parse_vehicle(response.text, plate)
        balance_params = dict(params, ps_persona=params['ps_id_persona'], ps_opcion='P')
        totals = parse_balance(get('clp_estado_cuenta.jsp', balance_params).text)
        citations = []
        for code, status in STATES.items():
            expected = counts[code]
            seen = set()
            for page in range(1, 11):
                payload = get('clp_json_citaciones.jsp', dict(params, ps_opcion=code, _search='false', rows=50, page=page, sidx='fecha_emision', sord='desc')).json()
                if not isinstance(payload, dict) or int(payload.get('records', -1)) != expected:
                    raise AntError('La cantidad de citaciones cambió durante la consulta. Vuelve a consultar.')
                pages = int(payload.get('total', -1))
                rows = payload.get('rows')
                if not isinstance(rows, list) or not 0 <= pages <= 10 or int(payload.get('page', -1)) != page:
                    raise AntError('No se pudo verificar la paginación de las citaciones.')
                for row in rows:
                    item = parse_row(row, status, plate)
                    if item['external_id'] in seen:
                        raise AntError('La ANT repitió una citación durante la consulta.')
                    seen.add(item['external_id'])
                    citations.append(item)
                if page >= pages:
                    break
            if len(seen) != expected:
                raise AntError('La ANT no entregó todas las citaciones. Conservamos la consulta anterior.')
        if len({r['external_id'] for r in citations}) != len(citations):
            raise AntError('Una citación apareció en estados diferentes. Vuelve a consultar.')
        return dict(plate=plate, vehicle=labels, counts=counts, totals=totals, citations=citations)
    except requests.RequestException as exc:
        raise AntError('No fue posible conectar con la ANT. Intenta nuevamente; los datos anteriores se conservan.') from exc
    except (ValueError, TypeError, KeyError) as exc:
        if isinstance(exc, AntError):
            raise
        raise AntError('La ANT devolvió una respuesta incompleta o no reconocida.') from exc
    finally:
        if own_session:
            session.close()
