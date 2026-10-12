"""Amplía los vehículos de Flota con alertas, costos, solicitudes de uso."""

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class FleetVehicle(models.Model):
    _inherit = 'fleet.vehicle'


    def _get_permission_approver(self):
        """Obtiene el administrador asignado o el usuario del encargado como alternativa."""
        self.ensure_one()
        approver = self.manager_id
        if not approver and self.driver_id:
            approver = self.env['res.users'].search([('partner_id', '=', self.driver_id.id)], limit=1)
        return approver


    # Visual and technical controls
    control_photo = fields.Image(string='Foto del vehículo', max_width=1280, max_height=1280)
    control_type = fields.Selection([
        ('car', 'Automóvil'),
        ('pickup', 'Camioneta'),
        ('van', 'Van / Buseta'),
        ('truck', 'Camión'),
        ('suv', 'SUV'),
        ('motorcycle', 'Motocicleta'),
    ], string='Tipo de vehículo', default='car')

    control_condition = fields.Selection([
        ('enabled', 'Habilitado para uso'),
        ('maintenance', 'En mantenimiento'),
        ('disabled', 'Fuera de servicio'),
    ], string='Condición operativa', default='enabled',
        help='Condición física y operativa del vehículo.')

    control_notes = fields.Text(string='Observaciones generales')
    control_color_hex = fields.Char(string='Muestra de color', help='Referencia visual aproximada del color de la carrocería.')

    # Technical data extensions
    vin_sn = fields.Char(string='Número de chasis / VIN')
    engine_sn = fields.Char(string='Número de motor')
    capacity_info = fields.Char(string='Capacidad / Carga útil', help='Ej.: 5 pasajeros / 1.5 Toneladas')

    # Responsibles & Assignment
    current_operator_id = fields.Many2one(
        'res.users', string='Responsable operativo actual', tracking=True
    )
    department_name = fields.Char(string='Departamento / Área')
    assignment_date = fields.Date(string='Fecha de asignación actual', default=fields.Date.context_today)
    assignment_status = fields.Selection([
        ('assigned', 'En uso / Asignado'),
        ('available', 'Disponible'),
        ('unassigned', 'Sin asignar'),
    ], string='Estado de asignación', compute='_compute_assignment_status', store=True)

    # Sub-tabs Relational Fields
    maintenance_ids = fields.One2many(
        'control.vehicle.maintenance', 'vehicle_id', string='Mantenimientos'
    )
    document_ids = fields.One2many(
        'control.vehicle.document', 'vehicle_id', string='Documentos'
    )
    fine_ids = fields.One2many(
        'control.vehicle.fine', 'vehicle_id', string='Multas'
    )
    fine_count = fields.Integer(string='Multas', compute='_compute_fine_count')

    @api.depends('fine_ids')
    def _compute_fine_count(self):
        for rec in self:
            rec.fine_count = len(rec.fine_ids)

    usage_ids = fields.One2many(
        'control.vehicle.assignment', 'vehicle_id', string='Historial de Uso'
    )
    cost_ids = fields.One2many(
        'control.vehicle.cost', 'vehicle_id', string='Costos'
    )

    # Alert Indicators
    document_alert_count = fields.Integer(string='Documentos por vencer/vencidos', compute='_compute_alerts', store=True)
    maintenance_alert_count = fields.Integer(string='Mantenimientos atrasados', compute='_compute_alerts', store=True)
    has_critical_alerts = fields.Boolean(compute='_compute_alerts', store=True)
    critical_alert_text = fields.Char(string='Alerta crítica principal', compute='_compute_alerts', store=True)

    # Cost summaries
    total_cost = fields.Monetary(string='Costo Total Acumulado', compute='_compute_cost_summary', currency_field='currency_id')
    monthly_cost = fields.Monetary(string='Costo Último Mes', compute='_compute_cost_summary', currency_field='currency_id')
    annual_cost = fields.Monetary(string='Costo Último Año', compute='_compute_cost_summary', currency_field='currency_id')
    cost_per_km = fields.Float(string='Costo por Kilómetro', compute='_compute_cost_summary')

    @api.depends('driver_id', 'current_operator_id', 'usage_ids.state')
    def _compute_assignment_status(self):
        """Marca como asignado si tiene un uso activo, conductor o encargado actual."""
        for rec in self:
            active_usage = rec.usage_ids.filtered(lambda u: u.state in ['delivered'])
            if active_usage:
                rec.assignment_status = 'assigned'
            else:
                rec.assignment_status = 'available'

    @api.depends('document_ids.state', 'maintenance_ids.is_overdue', 'maintenance_ids.remaining_km', 'fine_ids.pending_payment')
    def _compute_alerts(self):
        """Cuenta y resume las alertas de documentos, mantenimientos y multas del vehículo."""
        for rec in self:
            doc_alerts = rec.document_ids.filtered(lambda d: d.state in ['expiring', 'expired'])
            maint_alerts = rec.maintenance_ids.filtered(lambda m: m.is_overdue or (m.remaining_km <= 500 and m.state in ['scheduled', 'in_progress']))
            fine_alerts = rec.fine_ids.filtered(lambda f: f.pending_payment)

            rec.document_alert_count = len(doc_alerts)
            rec.maintenance_alert_count = len(maint_alerts)
            rec.has_critical_alerts = bool(doc_alerts or maint_alerts or fine_alerts)

            messages = []
            expired_docs = doc_alerts.filtered(lambda d: d.state == 'expired')
            expiring_docs = doc_alerts.filtered(lambda d: d.state == 'expiring')
            if expired_docs:
                messages.append(_('%s doc(s) vencido(s)', len(expired_docs)))
            elif expiring_docs:
                first_exp = expiring_docs[0]
                messages.append(_('%s vence en %s días', first_exp.name, first_exp.days_to_expire))

            if fine_alerts:
                messages.append(_('%s multa(s) pdte.', len(fine_alerts)))

            if maint_alerts:
                overdue_maint = maint_alerts.filtered(lambda m: m.is_overdue)
                if overdue_maint:
                    messages.append(_('Mantenimiento atrasado %s km', abs(int(overdue_maint[0].remaining_km))))
                else:
                    messages.append(_('Mantenimiento en %s km', int(maint_alerts[0].remaining_km)))

            rec.critical_alert_text = ' / '.join(messages) if messages else False

    @api.depends('cost_ids.amount', 'cost_ids.date', 'odometer')
    def _compute_cost_summary(self):
        """Suma los costos totales, mensuales y anuales, y calcula el costo por kilómetro."""
        today = fields.Date.context_today(self)
        for rec in self:
            costs = rec.cost_ids
            rec.total_cost = sum(costs.mapped('amount'))

            monthly = costs.filtered(lambda c: c.date and c.date.month == today.month and c.date.year == today.year)
            rec.monthly_cost = sum(monthly.mapped('amount'))

            annual = costs.filtered(lambda c: c.date and c.date.year == today.year)
            rec.annual_cost = sum(annual.mapped('amount'))

            rec.cost_per_km = (rec.total_cost / rec.odometer) if rec.odometer and rec.odometer > 0 else 0.0


    # Permite guardar el vehículo antes de completar su modelo con la consulta ANT.
    model_id = fields.Many2one('fleet.vehicle.model', 'Modelo', required=False)

    def action_decommission_vehicle(self):
        """Deshabilita y archiva el vehículo, y registra la baja en su historial."""
        for rec in self:
            rec.control_condition = 'disabled'
            rec.active = False
            rec.message_post(body="El vehículo ha sido Dado de Baja y archivado del sistema.")

    def action_open_request_usage_wizard(self):
        """Comprueba el aprobador y abre un formulario modal para solicitar este vehículo."""
        self.ensure_one()
        approver = self._get_permission_approver()

        if not approver:
            raise UserError('Este vehículo aún no tiene un "Administrador de permisos" ni un Conductor asignado. Por favor, avisa a gerencia para que le asignen un jefe antes de solicitarlo.')
        if not approver.has_group('fleet.fleet_group_manager'):
            raise UserError(f'La persona asignada para aprobar permisos de este vehículo ({approver.name}) no tiene el rol de Administrador en el sistema. Avisa a gerencia para que corrijan esto.')

        return {
            'name': _('Solicitar uso de vehículo'),
            'type': 'ir.actions.act_window',
            'res_model': 'control.vehicle.assignment',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_vehicle_id': self.id,
                'default_requester_id': self.env.uid,
                'default_operator_id': approver.id,
            }
        }
