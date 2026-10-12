import logging
from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class DocumentController(http.Controller):
    """Controlador HTTP para el modelo control.vehicle.document"""

    @http.route('/control_vehiculos/document/list', type='json', auth='user')
    def get_documents(self, vehicle_id=None, **kwargs):
        """Consulta los documentos con sudo; filtra por vehículo si se indica."""
        domain = []
        if vehicle_id:
            domain.append(('vehicle_id', '=', int(vehicle_id)))

        docs = request.env['control.vehicle.document'].sudo().search_read(
            domain,
            ['id', 'name', 'document_type', 'issue_date', 'expiration_date', 'state']
        )
        return {'success': True, 'data': docs}
