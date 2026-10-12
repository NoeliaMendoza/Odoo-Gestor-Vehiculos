"""Programa mantenimientos y registra su avance, finalización y costo."""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class VehicleMaintenance(models.Model):
    _name = 'control.vehicle.maintenance'
    _description = 'Mantenimiento de Vehículo'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    vehicle_id = fields.Many2one(
        'fleet.vehicle', string='Vehículo', required=True, ondelete='cascade', tracking=True
    )
    name = fields.Char(string='Descripción del mantenimiento', required=True, tracking=True)
    maintenance_type = fields.Selection([
        ('preventive', 'Preventivo'),
        ('corrective', 'Correctivo'),
        ('inspection', 'Inspección / Revisión'),
        ('tires', 'Llantas / Alineación'),
        ('other', 'Otro'),
    ], string='Tipo de Mantenimiento', default='preventive', required=True, tracking=True)

    date = fields.Date(string='Fecha', default=fields.Date.context_today, required=True, tracking=True)
    last_km = fields.Float(string='Último mantenimiento (km)', help='Kilometraje del mantenimiento previo')
    next_km = fields.Float(string='Próximo mantenimiento (km)', required=True, tracking=True, help='Kilometraje proyectado para el mantenimiento')
    current_km = fields.Float(
        string='Kilometraje actual del vehículo', related='vehicle_id.odometer', readonly=True
    )
    remaining_km = fields.Float(
        string='Kilometraje restante', compute='_compute_status', store=True
    )
    progress_pct = fields.Float(
        string='Progreso (%)', compute='_compute_status'
    )
    is_overdue = fields.Boolean(
        string='Mantenimiento vencido', compute='_compute_status', store=True
    )

    state = fields.Selection([
        ('scheduled', 'Programado'),
        ('in_progress', 'En proceso'),
        ('done', 'Realizado'),
        ('cancelled', 'Cancelado'),
    ], string='Estado', default='scheduled', required=True, tracking=True)

    workshop = fields.Char(string='Taller / Proveedor', tracking=True)
    responsible_id = fields.Many2one(
        'res.users', string='Responsable', default=lambda self: self.env.user, tracking=True
    )
    cost = fields.Monetary(string='Costo', currency_field='currency_id', tracking=True)
    company_id = fields.Many2one(
        'res.company', related='vehicle_id.company_id', store=True
    )
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id'
    )
    notes = fields.Text(string='Observaciones / Repuestos')

    @api.onchange('vehicle_id', 'maintenance_type')
    def _onchange_vehicle_id(self):
        """Sugiere kilometrajes de mantenimiento al seleccionar un vehículo."""
        if self.vehicle_id:
            odo = self.vehicle_id.odometer or 0.0
            if not self.last_km:
                self.last_km = odo
            if not self.next_km or self.next_km <= self.last_km:
                # Sugerir +5000 km para preventivos
                self.next_km = odo + (5000.0 if self.maintenance_type == 'preventive' else 1000.0)

    @api.depends('next_km', 'last_km', 'vehicle_id.odometer', 'state')
    def _compute_status(self):
        """Calcula kilómetros restantes, atraso y avance del intervalo de mantenimiento."""
        for rec in self:
            current = rec.vehicle_id.odometer if rec.vehicle_id else 0.0
            next_km = rec.next_km or 0.0
            last = rec.last_km or 0.0

            rec.remaining_km = next_km - current if next_km > 0 else 0.0
            rec.is_overdue = bool(next_km > 0 and current > next_km and rec.state in ['scheduled', 'in_progress'])

            if next_km > last and next_km > 0:
                total_interval = next_km - last
                elapsed = current - last
                pct = (elapsed / total_interval) * 100.0 if total_interval > 0 else 0.0
                rec.progress_pct = min(max(pct, 0.0), 100.0)
            else:
                rec.progress_pct = 0.0

    @api.constrains('cost', 'next_km', 'last_km')
    def _check_km_values(self):
        """Impide guardar costos o kilometrajes negativos."""
        for rec in self:
            if rec.cost < 0:
                raise ValidationError(_('El costo no puede ser negativo.'))
            if rec.next_km < 0 or rec.last_km < 0:
                raise ValidationError(_('El kilometraje no puede ser negativo.'))

    def action_start(self):
        """Marca el mantenimiento como en curso."""
        for rec in self:
            rec.state = 'in_progress'
            if rec.vehicle_id:
                rec.vehicle_id.control_condition = 'maintenance'

    def action_complete(self):
        """Finaliza el mantenimiento, registra su costo si es positivo y actualiza el odómetro si corresponde."""
        for rec in self:
            if rec.state == 'done':
                continue
            if rec.cost < 0:
                raise ValidationError(_('El costo no puede ser negativo.'))
            rec.state = 'done'
            if rec.vehicle_id:
                rec.vehicle_id.control_condition = 'enabled'

            # Registrar costo si aplica
            if rec.cost > 0:
                self.env['control.vehicle.cost'].create({
                    'vehicle_id': rec.vehicle_id.id,
                    'name': f"Mantenimiento: {rec.name}",
                    'cost_type': 'maintenance',
                    'date': rec.date or fields.Date.today(),
                    'amount': rec.cost,
                    'notes': f"Taller: {rec.workshop or 'N/A'}. {rec.notes or ''}",
                    'maintenance_id': rec.id,
                })

            # Actualizar odómetro si el mantenimiento fue posterior al odómetro actual
            if rec.next_km > rec.vehicle_id.odometer:
                rec.vehicle_id.odometer = rec.next_km

    def action_cancel(self):
        """Marca el mantenimiento como cancelado."""
        for rec in self:
            rec.state = 'cancelled'
