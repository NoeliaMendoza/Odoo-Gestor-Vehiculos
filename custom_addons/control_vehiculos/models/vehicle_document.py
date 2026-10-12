"""Registra documentos del vehículo y calcula su vigencia."""

from odoo import api, fields, models


class VehicleDocument(models.Model):
    _name = 'control.vehicle.document'
    _description = 'Documento de Vehículo'
    _order = 'expiration_date asc, id desc'

    vehicle_id = fields.Many2one(
        'fleet.vehicle', string='Vehículo', required=True, ondelete='cascade'
    )
    document_type = fields.Selection([
        ('registration', 'Matrícula'),
        ('insurance', 'Seguro'),
        ('inspection', 'Revisión Técnica Vehicular'),
        ('permit', 'Permiso de circulación'),
        ('other', 'Otro documento'),
    ], string='Tipo de documento', required=True, default='registration')

    name = fields.Char(string='Número / Título del documento', required=True)
    issue_date = fields.Date(string='Fecha de emisión')
    expiration_date = fields.Date(string='Fecha de vencimiento', required=True)

    days_to_expire = fields.Integer(
        string='Días restantes', compute='_compute_status', store=True
    )
    state = fields.Selection([
        ('valid', 'Vigente'),
        ('expiring', 'Por vencer'),
        ('expired', 'Vencido'),
    ], string='Estado', compute='_compute_status', store=True, required=True, default='valid')

    document_file = fields.Binary(string='Archivo del documento', attachment=True)
    file_name = fields.Char(string='Nombre de archivo')
    cost = fields.Monetary(string='Costo asociado', currency_field='currency_id')

    company_id = fields.Many2one(
        'res.company', related='vehicle_id.company_id', store=True
    )
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id'
    )
    notes = fields.Text(string='Observaciones')

    @api.depends('expiration_date')
    def _compute_status(self):
        """Calcula días restantes y vigencia; marca por vencer cuando quedan 30 días o menos."""
        today = fields.Date.context_today(self)
        for rec in self:
            if not rec.expiration_date:
                rec.days_to_expire = 0
                rec.state = 'valid'
                continue
            delta = (rec.expiration_date - today).days
            rec.days_to_expire = delta
            if delta < 0:
                rec.state = 'expired'
            elif delta <= 30:
                rec.state = 'expiring'
            else:
                rec.state = 'valid'

    @api.model
    def action_cron_document_alerts(self):
        """Cron diario: notifica sobre documentos vencidos o por vencer (<=30 dias)."""
        today = fields.Date.context_today(self)
        managers = self.env.ref('fleet.fleet_group_manager').users
        if not managers:
            return
        partner_ids = managers.mapped('partner_id').ids

        # Documentos por vencer en los proximos 30 dias
        expiring = self.search([('state', '=', 'expiring')])
        for doc in expiring:
            body = (
                'El documento <b>%s</b> del vehiculo <b>%s</b> vence en <b>%d dias</b> (%s).' % (
                    doc.name, doc.vehicle_id.name, doc.days_to_expire,
                    doc.expiration_date.strftime('%d/%m/%Y'),
                )
            )
            self.env['mail.thread'].message_notify(
                partner_ids=partner_ids,
                subject='Documento por vencer: %s - %s' % (doc.vehicle_id.name, doc.name),
                body=body,
                model='control.vehicle.document',
                res_id=doc.id,
                force_send=False,
            )

        # Documentos ya vencidos (solo notificar una vez al dia los recien vencidos)
        expired_today = self.search([
            ('state', '=', 'expired'),
            ('expiration_date', '=', today),
        ])
        for doc in expired_today:
            body = (
                'El documento <b>%s</b> del vehiculo <b>%s</b> ha <b>vencido hoy</b> (%s). '
                'Renuevalo a la brevedad.' % (
                    doc.name, doc.vehicle_id.name,
                    doc.expiration_date.strftime('%d/%m/%Y'),
                )
            )
            self.env['mail.thread'].message_notify(
                partner_ids=partner_ids,
                subject='VENCIDO hoy: %s - %s' % (doc.vehicle_id.name, doc.name),
                body=body,
                model='control.vehicle.document',
                res_id=doc.id,
                force_send=False,
            )
