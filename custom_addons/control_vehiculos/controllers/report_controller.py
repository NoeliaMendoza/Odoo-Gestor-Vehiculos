"""Descargas de documentos con las mismas restricciones que el permiso."""
from odoo import http
from odoo.exceptions import AccessError, MissingError, ValidationError
from odoo.http import request, content_disposition
from ..reports.document_pdf import build_pdf


class AssignmentReportController(http.Controller):
    @http.route('/control_vehiculos/documento/<int:assignment_id>/<string:kind>',
                type='http', auth='user', methods=['GET'])
    def download_document(self, assignment_id, kind, **kwargs):
        """Genera PDF en memoria; no expone documentos de otros empleados."""
        if kind not in ('compromiso', 'reporte'):
            return request.not_found()
        assignment = request.env['control.vehicle.assignment'].browse(assignment_id)
        try:
            if not assignment.exists():
                return request.not_found()
            data = assignment._get_document_data(kind)
        except (AccessError, MissingError):
            return request.not_found()
        except ValidationError:
            return request.make_response('Registra la devolución del vehículo antes de descargar el reporte.',
                status=400, headers=[('Content-Type', 'text/plain; charset=utf-8'), ('Cache-Control', 'no-store')])
        return request.make_response(build_pdf(data), headers=[
            ('Content-Type', 'application/pdf'),
            ('Content-Disposition', content_disposition(data['filename'])),
            ('Cache-Control', 'private, no-store'),
            ('X-Content-Type-Options', 'nosniff'),
        ])

    @http.route('/control_vehiculos/descargar_acta/<int:assignment_id>',
                type='http', auth='user', methods=['GET'])
    def descargar_acta_docx(self, assignment_id, **kwargs):
        """Mantiene los enlaces anteriores al informe de uso."""
        return self.download_document(assignment_id, 'reporte', **kwargs)
