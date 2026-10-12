"""Integra la consulta ANT en las tablas existentes de Documentos y Multas."""
from odoo import api, fields, models
from odoo.exceptions import UserError

from .vehicle_ant import MANAGER, STATES


class AntDocument(models.Model):
    _inherit = 'control.vehicle.document'

    ant_plate = fields.Char('Placa de origen ANT', readonly=True, copy=False)
    ant_checked_at = fields.Datetime('Última consulta ANT', readonly=True, copy=False)
    _sql_constraints = [('ant_registration_unique', 'unique(vehicle_id, ant_plate, document_type)', 'La matrícula ANT de esta placa ya está registrada.')]

    @api.model_create_multi
    def create(self, vals_list):
        if any(values.get('ant_plate') or values.get('ant_checked_at') for values in vals_list):
            raise UserError('El origen ANT se establece mediante la consulta del vehículo.')
        return super().create(vals_list)

    def write(self, values):
        if {'ant_plate', 'ant_checked_at'} & values.keys() or (
            self.filtered('ant_plate') and {'vehicle_id', 'document_type', 'name', 'issue_date', 'expiration_date'} & values.keys()
        ):
            raise UserError('Los datos de la matrícula ANT se actualizan consultando la placa. Puedes adjuntar el documento o agregar observaciones.')
        return super().write(values)

    def _sync_ant_registration(self, vehicle):
        """Actualiza una matrícula por placa, preservando archivos adjuntos y notas manuales."""
        if not vehicle.ant_expiration_date:
            return self.browse()
        document = self.search([('vehicle_id', '=', vehicle.id), ('document_type', '=', 'registration'), ('ant_plate', '=', vehicle.ant_checked_plate)], limit=1)
        values = dict(vehicle_id=vehicle.id, document_type='registration',
                      name='Matrícula ANT · %s' % vehicle.ant_checked_plate,
                      ant_plate=vehicle.ant_checked_plate, ant_checked_at=vehicle.ant_checked_at,
                      issue_date=vehicle.ant_registration_date, expiration_date=vehicle.ant_expiration_date)
        if document:
            super(AntDocument, document).write(values)
        else:
            # Adopta una ficha manual sólo si coinciden placa del vehículo, tipo y ambas fechas.
            candidates = self.search([('vehicle_id', '=', vehicle.id), ('document_type', '=', 'registration'),
                                      ('ant_plate', '=', False), ('issue_date', '=', vehicle.ant_registration_date),
                                      ('expiration_date', '=', vehicle.ant_expiration_date)])
            if len(candidates) == 1:
                document = candidates
                super(AntDocument, document).write(values)
            else:
                document = super(AntDocument, self).create(dict(values, notes='Datos consultados en ANT. La consulta no descarga el archivo de matrícula; puedes adjuntarlo aquí.'))
        return document


class AntFine(models.Model):
    _inherit = 'control.vehicle.fine'

    company_id = fields.Many2one(related='vehicle_id.company_id', store=True, index=True)
    ant_citation_id = fields.Many2one('control.vehicle.ant.citation', string='Citación ANT', ondelete='restrict', readonly=True, copy=False, index=True)
    ant_status = fields.Selection(related='ant_citation_id.status', string='Estado ANT', store=True)
    ant_in_last_query = fields.Boolean(related='ant_citation_id.in_last_query', string='Presente en última consulta', store=True)
    fine_status = fields.Selection(STATES, string='Estado', compute='_compute_fine_status', store=True)
    pending_payment = fields.Boolean(string='Pago pendiente', compute='_compute_fine_status', store=True)
    ant_entity = fields.Char(related='ant_citation_id.entity', string='Entidad ANT')
    ant_sanction = fields.Float(related='ant_citation_id.sanction', string='Sanción ANT (USD)')
    ant_penalty = fields.Float(related='ant_citation_id.penalty', string='Multa ANT (USD)')
    ant_remission = fields.Float(related='ant_citation_id.remission', string='Remisión ANT (USD)')
    ant_points = fields.Float(related='ant_citation_id.points', string='Puntos ANT')
    ant_notified_at = fields.Datetime(related='ant_citation_id.notified_at', string='Fecha de notificación')
    ant_checked_at = fields.Datetime(related='ant_citation_id.last_seen_at', string='Última consulta ANT')
    _sql_constraints = [('ant_citation_unique', 'unique(ant_citation_id)', 'Esta citación ANT ya aparece en Multas.')]

    @api.depends('paid', 'ant_citation_id', 'ant_status', 'ant_in_last_query')
    def _compute_fine_status(self):
        for fine in self:
            fine.fine_status = fine.ant_status if fine.ant_citation_id else ('paid' if fine.paid else 'pending')
            fine.pending_payment = (fine.ant_in_last_query and fine.ant_status in ('pending', 'agreement')) if fine.ant_citation_id else not fine.paid

    @api.depends('vehicle_id', 'date', 'ant_citation_id')
    def _compute_assignment_and_driver(self):
        imported = self.filtered('ant_citation_id')
        imported.assignment_id = False
        imported.driver_id = False
        super(AntFine, self - imported)._compute_assignment_and_driver()

    def _notify_new_fine(self):
        """Una importación histórica no debe enviar avisos al conductor actual."""
        if not self.ant_citation_id:
            return super()._notify_new_fine()

    @api.model_create_multi
    def create(self, vals_list):
        if any(values.get('ant_citation_id') for values in vals_list):
            raise UserError('Las multas ANT se registran consultando la placa del vehículo.')
        return super().create(vals_list)

    def write(self, values):
        if 'ant_citation_id' in values or (
            self.filtered('ant_citation_id') and {'name', 'vehicle_id', 'date', 'reason', 'amount', 'paid'} & values.keys()
        ):
            raise UserError('La información oficial de esta multa se actualiza desde Consultar. Puedes agregar observaciones.')
        return super().write(values)

    def unlink(self):
        if self.filtered('ant_citation_id'):
            raise UserError('Las citaciones ANT se conservan como historial. Su estado se actualiza desde el vehículo.')
        return super().unlink()

    def _sync_ant_vehicle(self, vehicle):
        """Crea una fila por citación, conservando sus cinco estados y el saldo informado."""
        result = self.browse()
        for citation in vehicle.ant_citation_ids.filtered('in_last_query'):
            fine = self.search([('ant_citation_id', '=', citation.id)], limit=1)
            values = dict(ant_citation_id=citation.id, vehicle_id=vehicle.id,
                          name='ANT-%s' % citation.external_id, date=citation.issued_at or False,
                          reason=citation.article or 'Citación ANT %s' % citation.citation_number,
                          amount=citation.sanction + citation.penalty, paid=citation.status == 'paid')
            # No se sustituye una fecha ausente por la fecha de hoy: eso atribuiría un hecho falso.
            if not citation.issued_at:
                raise UserError('ANT no informó la fecha de emisión de la citación %s. No se guardó una consulta parcial.' % citation.citation_number)
            if fine:
                super(AntFine, fine.with_context(tracking_disable=True)).write(values)
            else:
                fine = super(AntFine, self.with_context(tracking_disable=True, mail_create_nosubscribe=True)).create(values)
            result |= fine
        return result
