import logging
from odoo import http, _
from odoo.http import request
from odoo.exceptions import AccessError, ValidationError
from .vehicle_validator import VehicleValidator

_logger = logging.getLogger(__name__)


class VehicleController(http.Controller):
    """Controlador HTTP para el modelo de vehiculos."""

    @http.route('/control_vehiculos/vehicle/create',
                type='json', auth='user', methods=['POST'])
    def create_vehicle(self, **kwargs):
        """Valida los datos recibidos por esta ruta y devuelve el vehículo creado o un error."""
        try:
            # Delegamos la logica pesada de validacion al validador
            vals = VehicleValidator.validate_vehicle_data(kwargs)

            # Crear vehiculo
            vehicle = request.env['fleet.vehicle'].with_company(
                request.env.company).create(vals)

            _logger.info(
                'Vehiculo creado: %s (ID: %s) por usuario %s',
                vehicle.display_name, vehicle.id, request.env.user.name)

            return {
                'success': True,
                'vehicle_id': vehicle.id,
                'vehicle_name': vehicle.display_name,
                'license_plate': vehicle.license_plate,
                'message': _('Vehiculo "%s" registrado exitosamente.', vehicle.display_name),
            }

        except ValidationError as e:
            return {
                'success': False,
                'error_type': 'validation',
                'errors': str(e.args[0]) if e.args else str(e),
            }
        except AccessError as e:
            return {
                'success': False,
                'error_type': 'access',
                'errors': str(e.args[0]) if e.args else _('No tienes permisos para crear vehiculos.'),
            }
        except Exception as e:
            _logger.exception('Error inesperado al crear vehiculo')
            return {
                'success': False,
                'error_type': 'server',
                'errors': _('Error inesperado del servidor. Contacta al administrador.'),
            }

    @http.route('/control_vehiculos/vehicle/form_data',
                type='json', auth='user', methods=['POST'])
    def get_form_data(self, **kwargs):
        """Devuelve modelos, marcas, responsables y opciones para llenar el formulario."""
        try:
            models = request.env['fleet.vehicle.model'].sudo().search_read(
                [], ['id', 'name', 'brand_id'], order='name')

            brands = request.env['fleet.vehicle.model.brand'].sudo().search_read(
                [], ['id', 'name'], order='name')

            fleet_manager_group = request.env.ref('fleet.fleet_group_manager')
            managers = request.env['res.users'].sudo().search_read(
                [('groups_id', 'in', fleet_manager_group.id),
                 ('active', '=', True)],
                ['id', 'name'], order='name')

            partners = request.env['res.partner'].sudo().search_read(
                [('active', '=', True), ('is_company', '=', False)],
                ['id', 'name'], order='name', limit=200)

            return {
                'success': True,
                'vehicle_types': [
                    {'value': 'car', 'label': 'Automovil'},
                    {'value': 'pickup', 'label': 'Camioneta'},
                    {'value': 'van', 'label': 'Van / Buseta'},
                    {'value': 'truck', 'label': 'Camion'},
                    {'value': 'suv', 'label': 'SUV'},
                    {'value': 'motorcycle', 'label': 'Motocicleta'},
                ],
                'fuel_types': [
                    {'value': 'diesel', 'label': 'Diesel'},
                    {'value': 'gasoline', 'label': 'Gasolina'},
                    {'value': 'full_hybrid', 'label': 'Hibrido'},
                    {'value': 'plug_in_hybrid_diesel', 'label': 'Hibrido enchufable (Diesel)'},
                    {'value': 'plug_in_hybrid_gasoline', 'label': 'Hibrido enchufable (Gasolina)'},
                    {'value': 'cng', 'label': 'Gas Natural (CNG)'},
                    {'value': 'lpg', 'label': 'Gas LP (LPG)'},
                    {'value': 'hydrogen', 'label': 'Hidrogeno'},
                    {'value': 'electric', 'label': 'Electrico'},
                ],
                'conditions': [
                    {'value': 'enabled', 'label': 'Habilitado para uso'},
                    {'value': 'maintenance', 'label': 'En mantenimiento'},
                    {'value': 'disabled', 'label': 'Fuera de servicio'},
                ],
                'models': models,
                'brands': brands,
                'managers': managers,
                'partners': partners,
            }

        except Exception as e:
            _logger.exception('Error al obtener datos del formulario')
            return {
                'success': False,
                'errors': _('Error al cargar los datos del formulario.'),
            }

    @http.route('/control_vehiculos/vehicle/validate_plate',
                type='json', auth='user', methods=['POST'])
    def validate_plate(self, plate='', **kwargs):
        """Comprueba el formato y los duplicados de la placa enviada a esta ruta."""
        plate = (plate or '').strip().upper()
        if not plate:
            return {'valid': False, 'message': _('La placa es obligatoria.')}

        if not PLATE_PATTERN.match(plate):
            return {
                'valid': False,
                'message': _('Formato de placa invalido (4-15 caracteres alfanumericos o guiones).'),
            }

        exists = request.env['fleet.vehicle'].sudo().search_count(
            [('license_plate', '=ilike', plate)])
        if exists:
            return {
                'valid': False,
                'message': _('Ya existe un vehiculo con esta placa.'),
            }

        return {'valid': True, 'message': _('Placa disponible.')}
