"""Prepara el acta de compromiso y el reporte sin alterar el permiso."""
import base64

from odoo import fields, models, _, tools
from ..reports.fuel_image import fuel_image
from ..reports.document_word import commitment_paragraphs, commitment_date
from odoo.exceptions import AccessError, ValidationError


class AssignmentDocument(models.Model):
    _inherit = 'control.vehicle.assignment'

    def _check_document_access(self, kind=None):
        """Restringe los documentos al administrador y el reporte a una devolución confirmada."""
        self.ensure_one()
        self.check_access('read')
        if not self._is_manager():
            raise AccessError(_('Solo el administrador de vehículos puede descargar o imprimir estos documentos.'))
        if kind == 'reporte' and (self.state not in ('returned', 'closed') or not self.checkin_at):
            raise ValidationError(_('Registra la devolución del vehículo antes de descargar o imprimir el reporte.'))

    def _document_action(self, kind):
        self._check_document_access(kind)
        return {'type': 'ir.actions.act_url', 'target': 'download',
                'url': f'/control_vehiculos/documento/{self.id}/{kind}'}

    def action_download_commitment(self):
        """Descarga el acta para revisar las condiciones y firmar la entrega."""
        return self._document_action('compromiso')

    def action_download_usage_report(self):
        """Descarga el reporte cuando la devolución ya está confirmada."""
        return self._document_action('reporte')

    def _get_document_data(self, kind):
        """Comparte datos y secciones entre el documento Word y la vista HTML."""
        self._check_document_access(kind)
        if kind not in ('compromiso', 'reporte'):
            raise ValidationError(_('Tipo de documento no válido.'))
        tz = self.env.user.tz or 'America/Guayaquil'

        def date(value):
            if not value:
                return 'Sin registrar'
            return fields.Datetime.context_timestamp(self.with_context(tz=tz), value).strftime('%d/%m/%Y %H:%M')

        def date_only(value):
            if not value:
                return 'Sin registrar'
            return fields.Datetime.context_timestamp(self.with_context(tz=tz), value).strftime('%d/%m/%Y')

        def number(value, suffix=''):
            return f'{value:,.2f}'.rstrip('0').rstrip('.').replace(',', '_').replace('.', ',').replace('_', '.') + suffix

        def format_duration(val):
            if not val: return '0h 00m'
            h = int(val)
            m = int(round((val - h) * 60))
            if m == 60: h, m = h+1, 0
            return f'{h}h {m:02d}m'

        def section(title, headers=(), rows=(), paragraphs=()):
            return {'title': title, 'headers': headers, 'rows': rows, 'paragraphs': paragraphs, 'gauges': []}

        def person(record):
            return record.name if record else 'Sin registrar'

        if kind == 'compromiso':
            with tools.file_open('control_vehiculos/static/src/img/document_logo.png', 'rb') as source:
                logo = base64.b64encode(source.read()).decode('ascii')
            driver = self.driver_user_id or self.requester_id
            download_date = date_only(fields.Datetime.now())
            return {'kind': kind, 'logo': logo, 'paragraphs': commitment_paragraphs(),
                    'download_date': download_date, 'date_label': commitment_date(download_date),
                    'signatures': [('Conductor / Empleado', person(driver)),
                                   ('Encargado del vehículo', person(self.delivered_by or self.operator_id))],
                    'filename': f'Acta_compromiso_{(self.name or "Sin_folio").replace("/", "_")}.pdf'}

        outgoing, incoming = bool(self.checkout_at), bool(self.checkin_at)
        driver = self.driver_user_id or self.requester_id
        outgoing_pending = 'Pendiente de entrega'
        incoming_pending = 'Pendiente de devolución'
        name = self.name or 'Sin folio'
        state = dict(self._fields['state']._description_selection(self.env)).get(self.state, self.state)

        sections = [section('01 - Identificación y autorización', rows=[
            ('Vehículo', self.vehicle_id.model_id.display_name),
            ('Placa', self.vehicle_id.license_plate or 'Sin placa'),
            ('Solicitante', person(self.requester_id)), ('Conductor', person(driver)),
            ('Destino', self.destination or 'Sin registrar'), ('Motivo', self.purpose or 'Sin registrar')
        ])]

        if self.state in ('rejected', 'cancelled'):
            sections.append(section('Motivo de la decisión', paragraphs=[self.decision_note if self.state == 'rejected' else self.cancellation_note or 'Sin observación registrada']))

        checks = [(line.name, ('Correcto' if line.is_ok else 'Revisar / no confirmado') if outgoing else 'Pendiente de entrega', line.note or '-')
                  for line in self.inspection_line_ids]
        if not checks:
            checks = [('Inspección', 'Sin registrar', '-')]

        sections.extend([
            section('02 - Registro de salida y devolución', ('Concepto', 'Salida', 'Devolución'), [
                ('Fecha y hora real', date(self.checkout_at) if outgoing else outgoing_pending, date(self.checkin_at) if incoming else incoming_pending),
                ('Kilometraje', number(self.checkout_km, ' km') if outgoing else outgoing_pending, number(self.checkin_km, ' km') if incoming else incoming_pending),
            ]),
            section('03 - Resumen del uso', rows=[
                ('Distancia recorrida', number(self.distance, ' km') if incoming and outgoing else incoming_pending),
                ('Duración del uso', format_duration(self.duration) if incoming and outgoing else incoming_pending),
            ]),
            section('04 - Verificación registrada', ('Elemento', 'Estado registrado', 'Observación'), checks,
                    ['Este cuadro corresponde a la verificación general registrada del vehículo.']),
        ])

        notes_rows = []
        if self.checkout_notes: notes_rows.append(('Entrega', self.checkout_notes))
        if incoming and self.checkin_notes: notes_rows.append(('Devolución', self.checkin_notes))
        if not incoming: notes_rows.append(('Devolución', incoming_pending))

        if self.incident_description:
            notes_rows.append(('Incidencia reportada', self.incident_description))
            incident_state = dict(self._fields['incident_state']._description_selection(self.env)).get(self.incident_state, 'Sin registrar')
            notes_rows.append(('Seguimiento', incident_state))

        if not self.checkout_notes and (not incoming or not self.checkin_notes) and not self.incident_description:
            sections.append(section('05 - Observaciones y novedades', paragraphs=['No se registraron observaciones ni novedades en este viaje.']))
        else:
            sections.append(section('05 - Observaciones y novedades', rows=notes_rows))


        # Evidencia Fotográfica
        def get_photo(field_name):
            val = getattr(self, field_name)
            return (val.decode('ascii') if isinstance(val, bytes) else val) if val else None

        all_photos = []
        for point, label in [('front', 'Frente'), ('glass', 'Parabrisas'), ('left', 'Lateral izquierdo'), ('right', 'Lateral derecho')]:
            p = get_photo(f'checkout_photo_{point}')
            if p:
                all_photos.append({'label': f'Salida: {label}', 'image': p})

        if incoming:
            for point, label in [('front', 'Frente'), ('glass', 'Parabrisas'), ('left', 'Lateral izquierdo'), ('right', 'Lateral derecho')]:
                p = get_photo(f'checkin_photo_{point}')
                if p:
                    all_photos.append({'label': f'Devolución: {label}', 'image': p})

        if self.incident_photo:
            p = get_photo('incident_photo')
            if p:
                all_photos.append({'label': 'Evidencia de incidencia', 'image': p})

        if all_photos:
            sections.append({'title': '06 - Evidencia Fotográfica', 'photos': all_photos})

        signatures = [('Conductor', person(driver)),
                      ('Encargado', person(self.returned_by or self.operator_id))]

        title = 'REPORTE DE USO VEHICULAR'
        subtitle = 'Asignación, recorrido y devolución'

        gauges = [('Combustible de salida', self.checkout_fuel if outgoing else None)]
        if kind == 'reporte':
            gauges.append(('Combustible de devolución', self.checkin_fuel if incoming else None))

        for label, value in gauges:
            next(s for s in sections if s['title'].startswith('02'))['gauges'].append({'label': label, 'value': value,
                'image': base64.b64encode(fuel_image(value)).decode('ascii'),
                'description': 'Sin registrar' if value is None else f'{value} %',
                'low': value is not None and value < 50})

        with tools.file_open('control_vehiculos/static/src/img/document_logo.png', 'rb') as logo_file:
            logo = base64.b64encode(logo_file.read()).decode('ascii')

        alerts = []
        if not outgoing:
            alerts.append('La entrega todavía no está confirmada. Este documento no acredita la salida del vehículo.')
        if kind == 'reporte' and not incoming:
            alerts.append('Reporte parcial: la devolución todavía no está registrada.')
        if outgoing and self.checkout_fuel < 50 or incoming and self.checkin_fuel < 50:
            alerts.append('Combustible registrado por debajo del mínimo del 50 %. Revisar la novedad con el encargado.')

        return {'kind': kind, 'title': title, 'subtitle': subtitle, 'folio': name,
                'logo': logo, 'company': self.company_id.name, 'state': state, 'generated': date_only(fields.Datetime.now()),
                'timezone': tz, 'sections': sections, 'alerts': alerts, 'signatures': signatures,
                'filename': f'{"Acta_compromiso" if kind == "compromiso" else "Reporte_uso"}_{name.replace("/", "_")}.pdf'}

class UsageReportValues(models.AbstractModel):
    _name = 'report.control_vehiculos.assignment_report'
    _description = 'Validación del reporte de uso vehicular'

    def _get_report_values(self, docids, data=None):
        """Muestra un aviso claro antes de intentar imprimir una devolución pendiente."""
        docs = self.env['control.vehicle.assignment'].browse(docids)
        for record in docs:
            record._check_document_access('reporte')
        return {'doc_ids': docids, 'doc_model': docs._name, 'docs': docs}
