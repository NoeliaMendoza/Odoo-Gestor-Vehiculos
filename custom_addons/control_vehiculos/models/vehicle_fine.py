from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class VehicleFine(models.Model):
    _name = 'control.vehicle.fine'
    _description = 'Multas e Infracciones de Transito'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(string='Referencia', required=True, copy=False, readonly=True, default=lambda self: _('Nuevo'))
    vehicle_id = fields.Many2one('fleet.vehicle', string='Vehículo', required=True, tracking=True)
    date = fields.Datetime(string='Fecha y hora de infracción', required=True, tracking=True, default=fields.Datetime.now)

    assignment_id = fields.Many2one('control.vehicle.assignment', string='Permiso de Uso', compute='_compute_assignment_and_driver', store=True, readonly=False, tracking=True, help="El sistema busca automáticamente el permiso activo en la fecha y hora de la infracción.")
    driver_id = fields.Many2one('res.users', string='Conductor / Responsable', compute='_compute_assignment_and_driver', store=True, readonly=False, tracking=True)

    amount = fields.Float(string='Monto de la multa ($)', required=True, tracking=True)
    reason = fields.Char(string='Motivo / Infracción', required=True, tracking=True)
    notes = fields.Text(string='Observaciones adicionales')

    paid = fields.Boolean(string='Multa Pagada', tracking=True, default=False)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('Nuevo')) == _('Nuevo'):
                vals['name'] = self.env['ir.sequence'].next_by_code('control.vehicle.fine') or _('Nuevo')
        records = super().create(vals_list)
        for rec in records:
            rec._notify_new_fine()
        return records

    def _notify_new_fine(self):
        """Notifica al conductor responsable cuando se registra una multa a su nombre."""
        if not self.driver_id:
            return
        body = (
            'Se ha registrado una multa <b>%s</b> para el vehiculo <b>%s</b>. '
            'Motivo: %s. Monto: %s.' % (
                self.name, self.vehicle_id.name,
                self.reason or '-',
                '$ %.2f' % self.amount,
            )
        )
        self.message_notify(
            partner_ids=[self.driver_id.partner_id.id],
            subject='Nueva multa %s registrada' % self.name,
            body=body,
            record_name=self.display_name,
            model_description='Multa de transito',
            force_send=False,
        )

    @api.model
    def action_cron_fine_reminders(self):
        """Cron semanal: notifica a los managers sobre multas pendientes de pago."""
        pending = self.search([('pending_payment', '=', True)])
        if not pending:
            return
        managers = self.env.ref('fleet.fleet_group_manager').users
        if not managers:
            return
        lines = ''.join(
            '<li><b>%s</b> — %s — %s — $%.2f</li>' % (
                f.name, f.vehicle_id.name, f.reason or '-', f.amount
            ) for f in pending
        )
        body = 'Hay <b>%d multa(s)</b> pendientes de pago:<ul>%s</ul>' % (len(pending), lines)
        managers[0].partner_id  # ensure loaded
        self.env['mail.thread'].message_notify(
            partner_ids=managers.mapped('partner_id').ids,
            subject='Resumen: %d multas pendientes de pago' % len(pending),
            body=body,
            model='control.vehicle.fine',
            force_send=False,
        )


    @api.depends('vehicle_id', 'date')
    def _compute_assignment_and_driver(self):
        for rec in self:
            if rec.vehicle_id and rec.date:
                # Buscar un permiso que cubra esta fecha y hora para este vehículo.
                # Consideramos desde la salida real (checkout_at) hasta el regreso real (checkin_at).
                # Si el viaje no ha terminado, checkin_at puede estar vacío, así que usamos el actual.
                domain = [
                    ('vehicle_id', '=', rec.vehicle_id.id),
                    ('state', 'in', ['delivered', 'returned', 'closed']),
                    ('checkout_at', '<=', rec.date),
                    '|', ('checkin_at', '>=', rec.date), ('checkin_at', '=', False)
                ]
                assignment = self.env['control.vehicle.assignment'].search(domain, order='checkout_at desc', limit=1)

                if assignment:
                    rec.assignment_id = assignment.id
                    rec.driver_id = assignment.driver_user_id.id or assignment.requester_id.id
                else:
                    rec.assignment_id = False
                    # Si no hay permiso, podría ser el encargado predeterminado del vehículo
                    rec.driver_id = self.env['res.users'].search([('partner_id', '=', rec.vehicle_id.driver_id.id)], limit=1).id if rec.vehicle_id.driver_id else False
            else:
                rec.assignment_id = False
                rec.driver_id = False
