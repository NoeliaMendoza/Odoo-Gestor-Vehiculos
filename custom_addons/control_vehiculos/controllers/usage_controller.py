import logging
from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class UsageController(http.Controller):
    """Controlador HTTP para el modelo control.vehicle.assignment"""

    @http.route('/control_vehiculos/usage/list', type='json', auth='user')
    def get_usages(self, vehicle_id=None, **kwargs):
        """Consulta las asignaciones con sudo; filtra por vehículo si se indica."""
        domain = []
        if vehicle_id:
            domain.append(('vehicle_id', '=', int(vehicle_id)))

        usages = request.env['control.vehicle.assignment'].sudo().search_read(
            domain,
            ['id', 'name', 'requester_id', 'destination', 'state']
        )
        return {'success': True, 'data': usages}
