"""Registra los gastos de cada vehículo"""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class VehicleCost(models.Model):
    _name = 'control.vehicle.cost'
    _description = 'Costo de Vehículo'
    _order = 'date desc, id desc'

    vehicle_id = fields.Many2one(
        'fleet.vehicle', string='Vehículo', required=True, ondelete='cascade'
    )
    name = fields.Char(string='Concepto de costo', required=True)
    cost_type = fields.Selection([
        ('maintenance', 'Mantenimiento'),
        ('fuel', 'Combustible'),
        ('insurance', 'Seguro'),
        ('fine', 'Multa / Penalización'),
        ('incident', 'Incidencia / Daño'),
        ('other', 'Otros gastos'),
    ], string='Categoría de gasto', required=True, default='other')

    date = fields.Date(string='Fecha del gasto', default=fields.Date.context_today, required=True)
    amount = fields.Monetary(string='Monto', required=True, currency_field='currency_id')

    company_id = fields.Many2one(
        'res.company', related='vehicle_id.company_id', store=True
    )
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id'
    )

    maintenance_id = fields.Many2one(
        'control.vehicle.maintenance', string='Mantenimiento vinculado', ondelete='set null'
    )
    usage_id = fields.Many2one(
        'control.vehicle.assignment', string='Uso / Viaje vinculado', ondelete='set null'
    )
    notes = fields.Text(string='Observaciones')

    @api.constrains('amount')
    def _check_amount(self):
        """Impide guardar un costo con un importe negativo."""
        for rec in self:
            if rec.amount < 0:
                raise ValidationError(_('El monto del costo no puede ser negativo.'))
