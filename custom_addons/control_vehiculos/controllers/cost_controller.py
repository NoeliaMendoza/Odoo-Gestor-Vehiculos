import logging
from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class CostController(http.Controller):
    """Controlador HTTP para el modelo control.vehicle.cost"""

    @http.route('/control_vehiculos/cost/list', type='json', auth='user')
    def get_costs(self, vehicle_id=None, **kwargs):
        """Consulta los costos con sudo y devuelve sus datos; filtra por vehículo si se indica."""
        domain = []
        if vehicle_id:
            domain.append(('vehicle_id', '=', int(vehicle_id)))

        costs = request.env['control.vehicle.cost'].sudo().search_read(
            domain,
            ['id', 'name', 'date', 'cost_type', 'amount', 'notes']
        )
        return {'success': True, 'data': costs}
