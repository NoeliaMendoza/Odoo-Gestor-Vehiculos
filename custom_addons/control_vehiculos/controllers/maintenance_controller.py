import logging
from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class MaintenanceController(http.Controller):
    """Controlador HTTP para el modelo control.vehicle.maintenance"""

    @http.route('/control_vehiculos/maintenance/list', type='json', auth='user')
    def get_maintenances(self, vehicle_id=None, **kwargs):
        """Consulta los mantenimientos con sudo; filtra por vehículo si se indica."""
        domain = []
        if vehicle_id:
            domain.append(('vehicle_id', '=', int(vehicle_id)))

        maint = request.env['control.vehicle.maintenance'].sudo().search_read(
            domain,
            ['id', 'name', 'date', 'maintenance_type', 'workshop', 'state']
        )
        return {'success': True, 'data': maint}
