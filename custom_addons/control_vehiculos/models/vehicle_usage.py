"""Gestiona el ciclo de los permisos, sus inspecciones y la ventana de motivos."""

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError, UserError

CHECKS = [('ok', 'Correcto'), ('damaged', 'Con danno o falla'), ('na', 'No aplica')]
PARTS = [('body', 'Carroceria'), ('glass', 'Parabrisas y vidrios'), ('lights', 'Luces'), ('horn', 'Bocina / Pito'), ('tires', 'Llantas')]
PHOTOS = [('front', 'Frente'), ('glass', 'Parabrisas'), ('left', 'Lateral izquierdo'), ('right', 'Lateral derecho')]

FUEL_LEVELS = [
    ('100', 'Tanque Lleno (100%)'),
    ('75', '3/4 de Tanque (75%)'),
    ('50', 'Medio Tanque (50% - Minimo)'),
    ('25', '1/4 de Tanque (25% - Bajo)'),
    ('10', 'Reserva (10% - Alerta)'),
    ('0', 'Tanque Vacio (0%)'),
]


class VehicleAssignment(models.Model):
    _name = 'control.vehicle.assignment'
    _description = 'Historial de Uso / Asignacion de Vehiculo'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc, id desc'
    _check_company_auto = True

    driver_user_id = fields.Many2one('res.users', string='Conductor asignado', tracking=True)
    inspection_line_ids = fields.One2many('control.vehicle.inspection.line', 'assignment_id', string='Lineas de Inspeccion', default=lambda self: self._default_inspection_lines())
    checkin_line_ids = fields.One2many('control.vehicle.checkin.line', 'assignment_id', string='Lineas de Devolucion')

    @api.model
    def _default_inspection_lines(self):
        return [fields.Command.create({'name': label, 'is_ok': True}) for _, label in PARTS]

    @api.depends('vehicle_id.name', 'vehicle_id.model_id', 'state')
    def _compute_display_name(self):
        state_labels = dict(self._fields['state'].selection)
        for rec in self:
            if rec.vehicle_id:
                brand = rec.vehicle_id.model_id.brand_id.name if rec.vehicle_id.model_id.brand_id else ''
                model = rec.vehicle_id.model_id.name if rec.vehicle_id.model_id else ''
                vehicle_name = f"{brand} {model}".strip() or rec.vehicle_id.name.split('/')[0].strip()
            else:
                vehicle_name = 'Sin Vehiculo'
            state_label = state_labels.get(rec.state, 'Desconocido')
            rec.display_name = f"{vehicle_name} - {state_label}"


    name = fields.Char(default='Nuevo', readonly=True, copy=False)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, required=True)
    vehicle_id = fields.Many2one('fleet.vehicle', string='Vehiculo', required=True, check_company=True, tracking=True, ondelete='restrict')
    vehicle_photo = fields.Image(related='vehicle_id.control_photo')
    requester_id = fields.Many2one('res.users', string='Solicitante / conductor', default=lambda self: self.env.user, required=True, tracking=True)
    operator_id = fields.Many2one('res.users', string='Responsable operativo', required=True, default=lambda self: self.env.user, tracking=True)
    state = fields.Selection([
        ('pending', 'Pendiente'), ('approved', 'Aprobado'), ('delivered', 'En Ruta'),
        ('returned', 'Devuelto'), ('closed', 'Cerrado'), ('rejected', 'Rechazado'), ('cancelled', 'Cancelado')
    ], default='pending', readonly=True, tracking=True, copy=False)
    destination = fields.Char(string='Destino', required=True, tracking=True)
    purpose = fields.Text(string='Motivo del viaje', required=True, tracking=True)
    requested_start = fields.Date(string='Salida solicitada', required=True, tracking=True)
    requested_end = fields.Date(string='Regreso estimado', required=True, tracking=True)
    decision_note = fields.Text(string='Comentario / motivo de rechazo', tracking=True)
    decision_by = fields.Many2one('res.users', string='Decidido por', readonly=True)
    decision_at = fields.Datetime(string='Fecha de decision', readonly=True)
    decision_avatar = fields.Image(related='decision_by.avatar_128')
    delivered_at = fields.Datetime(string='Entrega confirmada', readonly=True)
    delivered_by = fields.Many2one('res.users', string='Entregado por', readonly=True)
    returned_by = fields.Many2one('res.users', string='Recibido por', readonly=True)
    closed_at = fields.Datetime(string='Cierre', readonly=True)
    closed_by = fields.Many2one('res.users', string='Cerrado por', readonly=True)
    cancelled_at = fields.Datetime(string='Cancelacion', readonly=True)
    cancelled_by = fields.Many2one('res.users', string='Cancelado por', readonly=True)
    cancellation_note = fields.Text(string='Motivo de cancelacion', tracking=True)
    checkout_km = fields.Float(string='Kilometraje de salida', tracking=True)
    checkout_fuel = fields.Integer(string='Combustible de salida', tracking=True)
    checkout_at = fields.Datetime(string='Salida real', tracking=True)
    checkout_signature = fields.Binary(string='Firma del conductor al recibir', attachment=True)
    checkout_notes = fields.Text(string='Observaciones de entrega', tracking=True)
    checkin_km = fields.Float(string='Kilometraje de regreso', tracking=True)
    checkin_fuel = fields.Integer(string='Combustible de regreso', tracking=True)
    checkin_at = fields.Datetime(string='Regreso real', tracking=True)
    fine_ids = fields.One2many('control.vehicle.fine', 'assignment_id', string='Multas de este viaje')
    fine_count = fields.Integer(string='Multas', compute='_compute_fine_count')

    @api.depends('fine_ids')
    def _compute_fine_count(self):
        for rec in self:
            rec.fine_count = len(rec.fine_ids)

    checkin_signature = fields.Binary(string='Firma del conductor al devolver', attachment=True)
    checkin_notes = fields.Text(string='Observaciones de devolucion', tracking=True)
    distance = fields.Float(string='Kilometros recorridos', compute='_compute_summary', store=True)
    duration = fields.Float(string='Horas de uso', compute='_compute_summary', store=True)
    low_fuel = fields.Boolean(compute='_compute_summary')
    new_damage = fields.Boolean(compute='_compute_summary')
    damage_summary = fields.Char(string='Diferencias detectadas', compute='_compute_summary')
    incident_description = fields.Text(string='Descripcion de la incidencia', tracking=True)
    incident_photo = fields.Image(string='Foto del dano', max_width=1600, max_height=1600)
    incident_state = fields.Selection([('reported', 'Reportada'), ('review', 'En revision'), ('resolved', 'Resuelta')], string='Estado de incidencia', tracking=True)
    incident_driver_id = fields.Many2one(related='driver_user_id', string='Conductor vinculado', readonly=True)
    incident_estimated_cost = fields.Monetary(string='Costo estimado', currency_field='currency_id', tracking=True)
    incident_actual_cost = fields.Monetary(string='Costo real', currency_field='currency_id', tracking=True)
    incident_cost_confirmed = fields.Boolean(string='Costo real confirmado', tracking=True)
    currency_id = fields.Many2one(related='company_id.currency_id')

    for _stage in ('checkout', 'checkin'):
        for _part, _label in PARTS:
            locals()[f'{_stage}_{_part}'] = fields.Selection(CHECKS, string=_label, tracking=True)
        for _point, _label in PHOTOS:
            locals()[f'{_stage}_photo_{_point}'] = fields.Image(string=_label, max_width=1600, max_height=1600)
    del _stage, _part, _label, _point

    @api.depends('checkout_km', 'checkin_km', 'checkout_at', 'checkin_at', 'checkin_fuel', *[f'{s}_{p}' for s in ('checkout', 'checkin') for p, label in PARTS])
    def _compute_summary(self):
        for rec in self:
            rec.distance = rec.checkin_km - rec.checkout_km if rec.checkin_at and rec.checkin_km >= rec.checkout_km else 0.0
            rec.duration = (rec.checkin_at - rec.checkout_at).total_seconds() / 3600.0 if rec.checkin_at and rec.checkout_at else 0.0
            rec.low_fuel = bool(rec.checkin_at and rec.checkin_fuel < 50)
            differences = [label for part, label in PARTS if rec[f'checkin_{part}'] == 'damaged' and rec[f'checkout_{part}'] == 'ok']
            rec.new_damage = bool(differences)
            rec.damage_summary = ', '.join(differences)

    def _is_manager(self):
        return self.env.su or self.env.user.has_group('fleet.fleet_group_manager')

    can_review = fields.Boolean(string='Puede revisar', compute='_compute_can_review')

    @api.depends('state')
    @api.depends_context('uid')
    def _compute_can_review(self):
        manager = self._is_manager()
        for rec in self:
            rec.can_review = manager and rec.state == 'pending'

    def _notify_decision(self):
        self.sudo().activity_ids.filtered(lambda a: a.summary == 'Revisar permiso de vehiculo').action_feedback(feedback='Solicitud revisada.')
        state_label = dict(self._fields['state'].selection).get(self.state, self.state)
        icon = 'Aprobada' if self.state == 'approved' else 'Rechazada'
        body = 'El permiso %s fue %s.' % (self.name, state_label)
        if self.decision_note:
            body += ' Motivo: %s' % self.decision_note
        self.message_notify(
            partner_ids=[self.requester_id.partner_id.id],
            subject='Solicitud %s - %s' % (self.name, icon),
            body=body,
            record_name=self.display_name,
            model_description='Permiso de uso vehicular',
            force_send=False,
        )

    def _notify_new_request(self):
        driver = self.driver_user_id or self.requester_id
        body = 'Nueva solicitud %s de %s para el vehiculo %s. Destino: %s.' % (
            self.name, driver.name, self.vehicle_id.name, self.destination or '-')
        self.message_notify(
            partner_ids=[self.operator_id.partner_id.id],
            subject='Nueva solicitud %s de %s' % (self.name, driver.name),
            body=body,
            record_name=self.display_name,
            model_description='Permiso de uso vehicular',
            force_send=False,
        )

    def _notify_cancelled(self):
        note = (' Motivo: ' + self.cancellation_note) if self.cancellation_note else ''
        body = 'El permiso %s fue cancelado por %s.%s' % (self.name, self.env.user.name, note)
        partners = list({self.operator_id.partner_id.id, self.requester_id.partner_id.id} - {self.env.user.partner_id.id})
        if partners:
            self.message_notify(
                partner_ids=partners,
                subject='Permiso %s cancelado' % self.name,
                body=body,
                record_name=self.display_name,
                model_description='Permiso de uso vehicular',
                force_send=False,
            )

    @api.model
    def action_cron_key_reminders(self):
        now = fields.Date.context_today(self)
        for rec in self.search([('state', '=', 'approved'), ('requested_start', '<=', now)]):
            driver = rec.driver_user_id or rec.requester_id
            body = 'El permiso %s debio salir pero las llaves no han sido entregadas al conductor %s.' % (rec.name, driver.name)
            rec.message_notify(
                partner_ids=list({rec.operator_id.partner_id.id, driver.partner_id.id}),
                subject='Pendiente: entregar llaves - %s' % rec.name,
                body=body, record_name=rec.display_name, model_description='Permiso de uso vehicular',
                force_send=False,
            )
        for rec in self.search([('state', '=', 'delivered'), ('requested_end', '<=', now)]):
            driver = rec.driver_user_id or rec.requester_id
            body = 'El vehiculo %s (permiso %s) debio regresar pero las llaves no han sido devueltas. Conductor: %s.' % (rec.vehicle_id.name, rec.name, driver.name)
            rec.message_notify(
                partner_ids=list({rec.operator_id.partner_id.id, driver.partner_id.id}),
                subject='Pendiente: devolver llaves - %s' % rec.name,
                body=body, record_name=rec.display_name, model_description='Permiso de uso vehicular',
                force_send=False,
            )

    def write(self, vals):
        request_fields = {'vehicle_id', 'destination', 'purpose', 'requested_start', 'requested_end', 'cancellation_note'}
        protected = {'state', 'name', 'company_id', 'decision_at', 'decision_by', 'delivered_at', 'delivered_by', 'returned_by', 'closed_at', 'closed_by', 'cancelled_at', 'cancelled_by', 'checkout_at', 'checkin_at'}
        if set(vals) & protected:
            raise ValidationError(_('Utiliza los botones del proceso para confirmar estados y fechas.'))
        for rec in self:
            rec._lock()
            if not rec._is_manager():
                if rec.requester_id != self.env.user or rec.state != 'pending' or set(vals) - request_fields:
                    raise ValidationError(_('Solo puedes modificar o cancelar tu propia solicitud pendiente.'))
            if set(vals) & ((request_fields - {'cancellation_note'}) | {'requester_id', 'operator_id'}):
                rec._expect('pending')
            if 'cancellation_note' in vals:
                rec._expect('pending', 'approved')
            if 'driver_user_id' in vals:
                rec._require_manager(); rec._expect('pending', 'approved')
            if 'decision_note' in vals:
                rec._require_manager(); rec._expect('pending')
            if any(k.startswith('checkout_') for k in vals):
                rec._require_manager(); rec._expect('approved')
            if any(k.startswith('checkin_') for k in vals):
                rec._require_manager(); rec._expect('delivered')
            if any(k.startswith('incident_') for k in vals):
                rec._require_manager(); rec._expect('delivered', 'returned', 'closed')
            if 'vehicle_id' in vals:
                raise UserError(_('Para cambiar de vehiculo, cancela esta solicitud y crea otra.'))
        result = super().write(vals)
        if set(vals) & {'requested_start', 'requested_end'}:
            for rec in self: rec._available()
        return result

    def unlink(self):
        raise UserError(_('Cancela el permiso para conservar su historial; no se permite eliminarlo.'))

    @api.onchange('vehicle_id', 'requested_start', 'requested_end')
    def _onchange_booking(self):
        if self.vehicle_id and self.vehicle_id.manager_id:
            self.operator_id = self.vehicle_id.manager_id
        if self.vehicle_id and self.requested_start and self.requested_end:
            conflict = self.env['control.vehicle.assignment'].sudo().search_count([
                ('id', '!=', self._origin.id or 0), ('vehicle_id', '=', self.vehicle_id.id),
                ('state', 'in', ['approved', 'delivered']),
                ('requested_start', '<=', self.requested_end), ('requested_end', '>=', self.requested_start),
            ])
            if conflict:
                return {'warning': {'title': _('Horario ocupado'), 'message': _('El vehiculo ya tiene un uso registrado en ese horario.')}}

    def _lock(self):
        self.ensure_one()
        self.check_access('write')
        self.env.cr.execute('SELECT id FROM control_vehicle_assignment WHERE id = %s FOR UPDATE', [self.id])
        self.invalidate_recordset()

    def _require_manager(self):
        if not self._is_manager():
            raise ValidationError(_('Solo el administrador de Flota puede realizar esta operacion.'))

    def _expect(self, *states):
        if self.state not in states:
            raise UserError(_('El registro cambio de estado. Actualiza la pantalla antes de continuar.'))

    def _transition(self, state, **values):
        if state in ('approved', 'rejected'):
            self._require_manager()
        return super(VehicleAssignment, self).write(dict(values, state=state))

    def _available(self):
        vehicle = self.vehicle_id
        self.env.cr.execute('SELECT id FROM fleet_vehicle WHERE id = %s FOR UPDATE', [vehicle.id])
        vehicle.invalidate_recordset()
        if not vehicle.active or vehicle.control_condition != 'enabled':
            raise ValidationError(_('El vehiculo no esta habilitado para uso.'))
        conflicts = self.sudo().search_count([
            ('id', '!=', self.id), ('vehicle_id', '=', vehicle.id),
            ('state', 'in', ['approved', 'delivered']),
            ('requested_start', '<=', self.requested_end), ('requested_end', '>=', self.requested_start),
        ])
        if conflicts:
            raise ValidationError(_('Este vehiculo ya esta reservado en ese horario. Elige otro rango.'))

    @api.constrains('requested_start', 'requested_end', 'checkout_km', 'checkin_km', 'checkout_fuel', 'checkin_fuel', 'incident_estimated_cost', 'incident_actual_cost')
    def _validate_values(self):
        for rec in self:
            if not (0 <= rec.checkout_fuel <= 100 and 0 <= rec.checkin_fuel <= 100):
                raise ValidationError(_('El combustible debe estar entre 0 y 100 %.'))
            if rec.requested_end <= rec.requested_start:
                raise ValidationError(_('El regreso estimado debe ser posterior a la salida solicitada.'))
            if min(rec.checkout_km, rec.checkin_km, rec.incident_estimated_cost, rec.incident_actual_cost) < 0:
                raise ValidationError(_('El kilometraje y los costos no pueden ser negativos.'))

    @api.model_create_multi
    def create(self, vals_list):
        allowed = {'vehicle_id', 'destination', 'purpose', 'requested_start', 'requested_end',
                   'requester_id', 'operator_id', 'company_id', 'driver_user_id', 'inspection_line_ids'}
        for vals in vals_list:
            if vals.get('state') == 'pending': vals.pop('state')
            if vals.get('name') == 'Nuevo': vals.pop('name')
            for key in set(vals) - allowed:
                if vals[key] in (False, None, '', 0): vals.pop(key)
            if set(vals) - allowed:
                raise ValidationError(_('Primero registra la solicitud; las demas etapas requieren aprobacion.'))
            if not self._is_manager():
                if vals.get('requester_id', self.env.uid) != self.env.uid:
                    raise ValidationError(_('La solicitud debe estar a tu nombre. El administrador asignara al conductor.'))
                vals['requester_id'] = self.env.uid
            vehicle = self.env['fleet.vehicle'].browse(vals.get('vehicle_id'))
            vehicle.check_access('read')
            supervisor = vehicle._get_permission_approver()
            if not supervisor or not supervisor.active or not supervisor.has_group('fleet.fleet_group_manager'):
                raise ValidationError(_('El vehiculo no tiene un Administrador con permisos suficientes.'))
            vals['operator_id'] = supervisor.id
            vals['state'] = 'pending'
            vals['name'] = self.env['ir.sequence'].next_by_code('control.vehicle.assignment') or 'Nuevo'
            if not vals.get('inspection_line_ids'):
                vals['inspection_line_ids'] = self._default_inspection_lines()
        safe_context = {k: v for k, v in self.env.context.items() if not k.startswith('default_')}
        records = super(VehicleAssignment, self.with_context(safe_context)).create(vals_list)
        for rec in records:
            rec._available()
            rec.sudo().activity_schedule('mail.mail_activity_data_todo', user_id=rec.operator_id.id,
                summary='Revisar permiso de vehiculo', note='Revisa las fechas y aprueba o rechaza el permiso.')
            rec._notify_new_request()
        return records

    def action_approve(self):
        self._require_manager(); self._lock(); self._expect('pending')
        self._available()
        self._transition('approved', decision_by=self.env.uid, decision_at=fields.Datetime.now())
        self._notify_decision()

    def action_open_reject_wizard(self):
        self.ensure_one(); self._require_manager(); self._expect('pending')
        return {'name': _('Rechazar Solicitud'), 'type': 'ir.actions.act_window',
                'res_model': 'control.vehicle.usage.reason.wizard', 'view_mode': 'form',
                'target': 'new', 'context': {'default_usage_id': self.id, 'default_action_type': 'reject'}}

    def action_open_cancel_wizard(self):
        self.ensure_one()
        return {'name': _('Cancelar Solicitud'), 'type': 'ir.actions.act_window',
                'res_model': 'control.vehicle.usage.reason.wizard', 'view_mode': 'form',
                'target': 'new', 'context': {'default_usage_id': self.id, 'default_action_type': 'cancel'}}

    def _validate_inspection(self, stage):
        if stage == 'checkout':
            if not self.checkout_km or self.checkout_km <= 0:
                raise ValidationError(_('Debes ingresar un kilometraje de salida valido mayor a 0.'))
            if self.checkout_fuel is False or self.checkout_fuel is None:
                raise ValidationError(_('Debes registrar el nivel de combustible de salida.'))
        elif stage == 'checkin':
            if not self.checkin_km or self.checkin_km <= 0:
                raise ValidationError(_('Debes ingresar el kilometraje de regreso.'))
            if self.checkin_fuel is False or self.checkin_fuel is None:
                raise ValidationError(_('Debes registrar el nivel de combustible de regreso.'))

    def action_deliver(self):
        self._require_manager(); self._lock(); self._expect('approved')
        if self.checkout_fuel < 50:
            raise ValidationError(_('Agrega combustible hasta al menos medio tanque (50 %) antes de entregar.'))
        self._validate_inspection('checkout')
        if self.checkout_km < self.vehicle_id.odometer:
            raise ValidationError(_('El kilometraje de salida (%s km) no puede ser menor al ultimo registrado del vehiculo (%s km).', self.checkout_km, self.vehicle_id.odometer))
        departure_time = fields.Datetime.now()
        checkin_lines = [fields.Command.create({'name': label, 'is_ok': True}) for _, label in PARTS]
        self._transition('delivered', delivered_at=departure_time, delivered_by=self.env.uid, checkout_at=departure_time, checkin_line_ids=checkin_lines)

    def action_return(self):
        self._require_manager(); self._lock(); self._expect('delivered')
        self._validate_inspection('checkin')
        if self.checkin_km < self.checkout_km:
            raise ValidationError(_('El kilometraje de regreso (%s km) no puede ser menor al de salida (%s km).', self.checkin_km, self.checkout_km))
        self._transition('returned', returned_by=self.env.uid, checkin_at=fields.Datetime.now())
        if self.checkin_km >= self.vehicle_id.odometer:
            self.vehicle_id.sudo().odometer = self.checkin_km

    def action_close(self):
        self._require_manager(); self._lock(); self._expect('returned')
        self._transition('closed', closed_at=fields.Datetime.now(), closed_by=self.env.uid)

    def action_download_docx(self):
        return self.action_download_usage_report()

    def action_report(self):
        self._check_document_access('reporte')
        return self.env.ref('control_vehiculos.assignment_report_action').report_action(self, config=False)

    def action_export_word(self):
        return self.action_download_usage_report()


class VehicleUsageReasonWizard(models.TransientModel):
    _name = 'control.vehicle.usage.reason.wizard'
    _description = 'Motivo de rechazo o cancelacion'

    usage_id = fields.Many2one('control.vehicle.assignment', required=True)
    action_type = fields.Selection([('reject', 'Rechazar'), ('cancel', 'Cancelar')], required=True)
    reason = fields.Text(string='Motivo', required=True)

    def action_confirm(self):
        self.ensure_one()
        if self.action_type == 'reject':
            self.usage_id.write({'decision_note': self.reason})
            self.usage_id._transition('rejected', rejected_at=fields.Datetime.now(), rejected_by=self.env.uid)
            self.usage_id._notify_decision()
        elif self.action_type == 'cancel':
            self.usage_id.write({'cancellation_note': self.reason})
            self.usage_id._transition('cancelled', cancelled_at=fields.Datetime.now(), cancelled_by=self.env.uid)
            self.usage_id._notify_cancelled()


class VehicleInspectionLine(models.Model):
    _name = 'control.vehicle.inspection.line'
    _description = 'Linea de inspeccion'
    assignment_id = fields.Many2one('control.vehicle.assignment', required=True, ondelete='cascade')
    name = fields.Char('Elemento a revisar', required=True)
    is_ok = fields.Boolean('OK (Visto)', default=False)
    note = fields.Char('Observacion')


class VehicleCheckinLine(models.Model):
    _name = 'control.vehicle.checkin.line'
    _description = 'Linea de inspeccion de devolucion'
    assignment_id = fields.Many2one('control.vehicle.assignment', required=True, ondelete='cascade')
    name = fields.Char('Elemento a revisar', required=True)
    is_ok = fields.Boolean('OK (Visto)', default=False)
    note = fields.Char('Observacion')
