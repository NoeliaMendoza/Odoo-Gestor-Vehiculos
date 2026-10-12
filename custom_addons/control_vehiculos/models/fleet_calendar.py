"""Disponibilidad compartida del calendario, con detalles limitados según el usuario."""
from datetime import datetime, time, timedelta

import pytz

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


class FleetCalendar(models.Model):
    _inherit = 'fleet.vehicle'

    @api.model
    def get_calendar_data(self, start, end):
        """Devuelve vehículos y horarios; las reservas ajenas solo revelan ocupación."""
        manager = self.env.su or self.env.user.has_group('fleet.fleet_group_manager')
        employee = self.env.user.has_group('control_vehiculos.group_assignment_driver')
        if not (manager or employee):
            raise AccessError(_('No tienes acceso al calendario de vehículos.'))
        try:
            start, end = fields.Datetime.to_datetime(start), fields.Datetime.to_datetime(end)
        except (TypeError, ValueError):
            raise ValidationError(_('Selecciona un período válido para el calendario.'))
        if not start or not end or end <= start or end - start > timedelta(days=45):
            raise ValidationError(_('El calendario admite períodos de hasta 45 días.'))

        vehicles = self.search([
            '|', ('company_id', '=', False), ('company_id', 'in', self.env.companies.ids),
        ], order='id')
        result = {'is_manager': manager, 'vehicles': [], 'events': [], 'pending': []}
        if not vehicles:
            return result
        for vehicle in vehicles:
            result['vehicles'].append({
                'id': vehicle.id,
                'name': vehicle.model_id.display_name or vehicle.display_name,
                'plate': vehicle.license_plate or _('Sin placa'),
                'has_photo': bool(vehicle.with_context(bin_size=True).control_photo),
                'seats': vehicle.seats,
                'condition': vehicle.control_condition,
            })

        def add_event(vehicle_id, begin, finish, kind, title, **details):
            if begin and finish and begin < end and finish > start:
                result['events'].append({
                    'key': f'event-{len(result["events"])}',
                    'vehicle_id': vehicle_id, 'kind': kind, 'title': title,
                    'start': fields.Datetime.to_string(begin),
                    'end': fields.Datetime.to_string(finish),
                    'blocks': kind in ('reserved', 'delivered', 'maintenance', 'unavailable'),
                    'record_id': False, 'model': False, 'requester': False,
                    'destination': False, 'own': False, 'open_end': False,
                    **details,
                })

        # El acceso elevado se limita a vehículos visibles y a los campos expuestos abajo.
        # No se devuelve el identificador ni datos personales de solicitudes ajenas.
        assignments = self.env['control.vehicle.assignment'].sudo().search([
            ('vehicle_id', 'in', vehicles.ids),
            ('company_id', 'in', self.env.companies.ids),
            ('state', 'in', ['approved', 'delivered', 'returned', 'closed']),
            '|', '|', ('state', '=', 'delivered'),
            '&', ('requested_start', '<', end), ('requested_end', '>', start),
            '&', ('checkout_at', '<', end), ('checkin_at', '>', start),
        ], order='requested_start, id')
        now = fields.Datetime.now()
        for assignment in assignments:
            own = assignment.requester_id.id == self.env.uid
            detail = {'own': own}
            if manager or own:
                detail.update({
                    'record_id': assignment.id, 'model': assignment._name,
                    'requester': assignment.requester_id.name,
                    'destination': assignment.destination,
                })
            # Tratamos "delivered" como "reserved" en el calendario para simplificar la vista
            kind = {'approved': 'reserved', 'delivered': 'reserved',
                    'returned': 'completed', 'closed': 'completed'}[assignment.state]
            begin = assignment.checkout_at or assignment.requested_start
            finish = assignment.checkin_at or assignment.requested_end
            title = _('Reservado') if kind == 'reserved' else _('Uso finalizado')

            if assignment.state == 'delivered' and finish <= now:
                finish = max(end, now)
                detail['open_end'] = True

            add_event(assignment.vehicle_id.id, begin, finish, kind, title, **detail)

        zone = pytz.timezone(self.env.user.tz or 'America/Guayaquil')
        local_start = pytz.utc.localize(start).astimezone(zone).date()
        local_end = pytz.utc.localize(end).astimezone(zone).date()

        def local_midnight(day):
            return zone.localize(datetime.combine(day, time.min)).astimezone(pytz.utc).replace(tzinfo=None)

        maintenances = self.env['control.vehicle.maintenance'].sudo().search([
            ('vehicle_id', 'in', vehicles.ids), ('state', 'in', ['scheduled', 'in_progress']),
            '|', ('state', '=', 'in_progress'), '&', ('date', '>=', local_start), ('date', '<=', local_end),
        ], order='date,id')
        for maintenance in maintenances:
            if maintenance.vehicle_id.control_condition in ('maintenance', 'disabled'):
                continue
            begin = local_midnight(maintenance.date)
            finish = end if maintenance.state == 'in_progress' else local_midnight(maintenance.date + timedelta(days=1))
            detail = {'record_id': maintenance.id, 'model': maintenance._name} if manager else {}
            add_event(maintenance.vehicle_id.id, begin, finish, 'maintenance', _('Mantenimiento'), **detail)

        for vehicle in vehicles:
            if vehicle.control_condition in ('maintenance', 'disabled'):
                kind = 'maintenance' if vehicle.control_condition == 'maintenance' else 'unavailable'
                add_event(vehicle.id, start, end, kind,
                          _('Mantenimiento') if kind == 'maintenance' else _('Fuera de servicio'))

        pending_domain = [('vehicle_id', 'in', vehicles.ids), ('state', '=', 'pending')]
        if not manager:
            pending_domain.append(('requester_id', '=', self.env.uid))
        pending = self.env['control.vehicle.assignment'].search(pending_domain, order='requested_start,id', limit=5)
        result['pending_count'] = self.env['control.vehicle.assignment'].search_count(pending_domain)
        result['pending'] = [{
            'id': row.id, 'vehicle': row.vehicle_id.model_id.display_name,
            'requester': row.requester_id.name if manager else False,
            'start': fields.Datetime.to_string(row.requested_start),
        } for row in pending]
        return result
