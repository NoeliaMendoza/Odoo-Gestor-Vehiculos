"""Datos consultados en ANT, separados de las multas registradas manualmente."""
from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError

from ..services.ant_client import AntError, date, fetch_vehicle, normalize_plate

MANAGER = 'fleet.fleet_group_manager'
STATES = [('pending', 'Pendiente'), ('disputed', 'En impugnación'), ('cancelled', 'Anulada'),
          ('paid', 'Pagada'), ('agreement', 'En convenio')]


class VehicleAnt(models.Model):
    _inherit = 'fleet.vehicle'

    ant_auto_sync = fields.Boolean('Consultar al guardar un vehículo nuevo', default=True, groups=MANAGER)
    ant_sync_message = fields.Text('Resultado de consulta automática', readonly=True, copy=False, groups=MANAGER)
    ant_checked_at = fields.Datetime('Última consulta ANT', readonly=True, copy=False, groups=MANAGER)
    ant_checked_plate = fields.Char('Placa consultada', readonly=True, copy=False, groups=MANAGER)
    ant_plate_changed = fields.Boolean(compute='_compute_ant_plate_changed', groups=MANAGER)
    ant_class = fields.Char('Clase según ANT', readonly=True, copy=False, groups=MANAGER)
    ant_service = fields.Char('Servicio según ANT', readonly=True, copy=False, groups=MANAGER)
    ant_registration_year = fields.Char('Año de matrícula', readonly=True, copy=False, groups=MANAGER)
    ant_registration_date = fields.Date('Fecha de matrícula', readonly=True, copy=False, groups=MANAGER)
    ant_expiration_date = fields.Date('Caducidad de matrícula', readonly=True, copy=False, groups=MANAGER)
    ant_tint = fields.Char('Registro de polarizado', readonly=True, copy=False, groups=MANAGER)
    ant_tint_expiration = fields.Date('Caducidad de polarizado', readonly=True, copy=False, groups=MANAGER)
    ant_pending_count = fields.Integer('Pendientes', readonly=True, copy=False, groups=MANAGER)
    ant_disputed_count = fields.Integer('En impugnación', readonly=True, copy=False, groups=MANAGER)
    ant_cancelled_count = fields.Integer('Anuladas', readonly=True, copy=False, groups=MANAGER)
    ant_paid_count = fields.Integer('Pagadas', readonly=True, copy=False, groups=MANAGER)
    ant_agreement_count = fields.Integer('En convenio', readonly=True, copy=False, groups=MANAGER)
    ant_pending = fields.Float('Valor pendiente (USD)', readonly=True, copy=False, groups=MANAGER, digits=(16, 2))
    ant_agreement = fields.Float('Valor en convenio (USD)', readonly=True, copy=False, groups=MANAGER, digits=(16, 2))
    ant_interest = fields.Float('Intereses pendientes (USD)', readonly=True, copy=False, groups=MANAGER, digits=(16, 2))
    ant_remission = fields.Float('Remisión (USD)', readonly=True, copy=False, groups=MANAGER, digits=(16, 2))
    ant_ant = fields.Float('Subtotal ANT (USD)', readonly=True, copy=False, groups=MANAGER, digits=(16, 2))
    ant_total = fields.Float('Total informado (USD)', readonly=True, copy=False, groups=MANAGER, digits=(16, 2))
    ant_citation_ids = fields.One2many('control.vehicle.ant.citation', 'vehicle_id', string='Citaciones ANT', readonly=True, groups=MANAGER)

    @api.model_create_multi
    def create(self, vals_list):
        """Guarda el vehículo y consulta ANT; si ANT falla, permite completar el registro manualmente."""
        vehicles = super().create(vals_list)
        if self.env.user.has_group(MANAGER):
            for vehicle in vehicles.filtered(lambda rec: rec.ant_auto_sync and rec.license_plate):
                try:
                    with self.env.cr.savepoint():
                        vehicle.action_consult_ant()
                except UserError as exc:
                    vehicle.ant_sync_message = 'Vehículo guardado. No se pudo completar la consulta ANT: %s' % exc
        return vehicles

    @api.depends('license_plate', 'ant_checked_plate')
    def _compute_ant_plate_changed(self):
        for vehicle in self:
            try:
                vehicle.ant_plate_changed = bool(vehicle.ant_checked_plate and normalize_plate(vehicle.license_plate) != vehicle.ant_checked_plate)
            except AntError:
                vehicle.ant_plate_changed = bool(vehicle.ant_checked_plate)

    def action_consult_ant_multi(self):
        """Consulta mltiple desde vista de lista."""
        success = 0
        errors = []
        for vehicle in self:
            try:
                vehicle.action_consult_ant()
                success += 1
            except UserError as e:
                errors.append(f"{vehicle.license_plate}: {e}")

        msg = f"Consultados {success} vehculos correctamente."
        if errors:
            msg += "\nErrores:\n" + "\n".join(errors)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Consulta masiva ANT',
                'message': msg,
                'type': 'warning' if errors else 'success',
                'sticky': True if errors else False,
                'next': {'type': 'ir.actions.client', 'tag': 'reload'}
            }
        }

    def action_consult_ant(self):
        """Consulta bajo petición; sólo guarda cuando ficha, saldo y citaciones están completos."""
        self.ensure_one()
        if not self.env.user.has_group(MANAGER):
            raise AccessError('Sólo el administrador de vehículos puede consultar la ANT.')
        self.check_access('write')
        if self.company_id and self.company_id not in self.env.companies:
            raise AccessError('El vehículo pertenece a otra compañía.')
        if self.ant_checked_at and (fields.Datetime.now() - self.ant_checked_at).total_seconds() < 60 and not self.ant_plate_changed:
            raise UserError('Acabas de consultar esta placa. Espera un minuto antes de actualizarla nuevamente.')
        try:
            data = fetch_vehicle(self.license_plate)
            info = data['vehicle']
            values = dict(ant_checked_plate=data['plate'], ant_checked_at=fields.Datetime.now(),
                          ant_class=info['Clase'], ant_service=info['Servicio'],
                          ant_registration_year=info['Año de Matrícula'],
                          ant_registration_date=date(info['Fecha de Matrícula']),
                          ant_expiration_date=date(info['Fecha de Caducidad']),
                          ant_tint=info.get('Polarizado') or False,
                          ant_tint_expiration=date(info.get('Fecha Caducidad', '')))
        except AntError as exc:
            raise UserError(str(exc)) from exc
        # La respuesta oficial completa marca/modelo, año y color; no inventa combustible ni kilometraje.
        brand = self.env['fleet.vehicle.model.brand'].search([('name', '=ilike', info['Marca'])], limit=1)
        if not brand:
            brand = self.env['fleet.vehicle.model.brand'].create({'name': info['Marca']})
        model = self.env['fleet.vehicle.model'].search([('name', '=ilike', info['Modelo']), ('brand_id', '=', brand.id)], limit=1)
        if not model:
            model = self.env['fleet.vehicle.model'].create({'name': info['Modelo'], 'brand_id': brand.id})
        values.update(model_id=model.id)
        if info['Año']:
            values['model_year'] = info['Año']
        if info['Color']:
            values['color'] = info['Color']
        for code, key in [('P', 'pending'), ('R', 'disputed'), ('A', 'cancelled'), ('G', 'paid'), ('C', 'agreement')]:
            values['ant_%s_count' % key] = data['counts'][code]
        values.update({'ant_' + key: value for key, value in data['totals'].items()})
        self.write(values)
        self.env['control.vehicle.ant.citation']._sync_vehicle(self, data['citations'])
        fines = self.env['control.vehicle.fine']._sync_ant_vehicle(self)
        document = self.env['control.vehicle.document']._sync_ant_registration(self)
        self.ant_sync_message = 'Consulta completada: %s citaciones en Multas. %s' % (
            len(fines), 'Matrícula actualizada en Documentos.' if document else 'ANT no informó una caducidad de matrícula; no se creó un documento incompleto.')
        return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
            'title': 'Consulta ANT completada', 'message': self.ant_sync_message,
            'type': 'success', 'sticky': False, 'next': {'type': 'ir.actions.client', 'tag': 'reload'}}}

    def _ant_related_action(self, xmlid):
        self.ensure_one()
        if not self.env.user.has_group(MANAGER):
            raise AccessError('Sólo el administrador de vehículos puede abrir esta información.')
        self.check_access('read')
        action = self.env['ir.actions.actions']._for_xml_id(xmlid)
        action.update(domain=[('vehicle_id', '=', self.id)], context={'default_vehicle_id': self.id})
        return action

    def action_open_ant_documents(self):
        return self._ant_related_action('control_vehiculos.action_vehicle_document')

    def action_open_ant_fines(self):
        return self._ant_related_action('control_vehiculos.action_vehicle_fine')


class AntCitation(models.Model):
    _name = 'control.vehicle.ant.citation'
    _description = 'Citación consultada en ANT'
    _rec_name = 'citation_number'
    _order = 'issued_at desc, id desc'

    vehicle_id = fields.Many2one('fleet.vehicle', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='vehicle_id.company_id', store=True, index=True)
    external_id = fields.Char('Número de infracción ANT', required=True, index=True)
    citation_number = fields.Char('Número de citación')
    plate = fields.Char('Placa consultada', required=True)
    entity = fields.Char('Entidad')
    status = fields.Selection(STATES, string='Estado ANT', required=True)
    issued_at = fields.Datetime('Fecha de emisión')
    notified_at = fields.Datetime('Fecha de notificación')
    payment_deadline = fields.Char('Límite de pago informado')
    points = fields.Float('Puntos')
    sanction = fields.Float('Sanción (USD)', digits=(16, 2))
    penalty = fields.Float('Multa (USD)', digits=(16, 2))
    remission = fields.Float('Remisión (USD)', digits=(16, 2))
    total = fields.Float('Total a pagar (USD)', digits=(16, 2))
    article = fields.Text('Artículo / Literal')
    blocked = fields.Boolean('Bloqueo informado')
    last_seen_at = fields.Datetime('Última vez consultada')
    in_last_query = fields.Boolean('Presente en última consulta')
    _sql_constraints = [('vehicle_ant_unique', 'unique(vehicle_id, external_id)', 'Esta citación ya fue consultada para el vehículo.')]

    @api.model_create_multi
    def create(self, vals_list):
        raise UserError('Las citaciones ANT se incorporan con el botón Consultar del vehículo.')

    def write(self, vals):
        raise UserError('Los datos ANT se actualizan consultando nuevamente la fuente.')

    def _sync_vehicle(self, vehicle, rows):
        """Actualiza por referencia externa, sin duplicar ni borrar citaciones antiguas."""
        existing = self.search([('vehicle_id', '=', vehicle.id)])
        super(AntCitation, existing).write({'in_last_query': False})
        by_id = {record.external_id: record for record in existing}
        for row in rows:
            values = dict(row, vehicle_id=vehicle.id, in_last_query=True, last_seen_at=vehicle.ant_checked_at)
            record = by_id.get(row['external_id'])
            if record:
                super(AntCitation, record).write(values)
            else:
                super(AntCitation, self).create(values)
