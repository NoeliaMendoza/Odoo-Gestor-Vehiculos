"""Ayudas usadas por el controlador de vehículos; no se ejecutan automáticamente al guardar desde otras vías."""

import re
from odoo import _
from odoo.exceptions import ValidationError
from odoo.http import request

# Constantes de validacion
PLATE_PATTERN = re.compile(r'^[A-Za-z0-9\-]{4,15}$')
VALID_VEHICLE_TYPES = ('car', 'pickup', 'van', 'truck', 'suv', 'motorcycle')
VALID_FUEL_TYPES = ('diesel', 'gasoline', 'full_hybrid', 'plug_in_hybrid_diesel',
                    'plug_in_hybrid_gasoline', 'cng', 'lpg', 'hydrogen', 'electric')
VALID_CONDITIONS = ('enabled', 'maintenance', 'disabled')
VALID_ODOMETER_UNITS = ('kilometers', 'miles')


class VehicleValidator:
    """Clase utilitaria para validacion de datos de vehiculos."""

    @staticmethod
    def clean_str(value):
        """Quita espacios de los extremos y devuelve None si el texto está vacío."""
        if not value:
            return None
        cleaned = str(value).strip()
        return cleaned if cleaned else None

    @staticmethod
    def clean_int(value, field_name='', min_val=None, max_val=None):
        """Convierte a entero y comprueba los límites indicados; permite valores vacíos."""
        if value is None or value == '':
            return None
        try:
            result = int(value)
        except (ValueError, TypeError):
            raise ValidationError(
                _('El campo "%s" debe ser un numero entero valido.', field_name))
        if min_val is not None and result < min_val:
            raise ValidationError(
                _('El campo "%s" no puede ser menor a %s.', field_name, min_val))
        if max_val is not None and result > max_val:
            raise ValidationError(
                _('El campo "%s" no puede ser mayor a %s.', field_name, max_val))
        return result

    @staticmethod
    def clean_float(value, field_name='', min_val=None):
        """Convierte a decimal y comprueba el mínimo indicado; permite valores vacíos."""
        if value is None or value == '':
            return None
        try:
            result = float(value)
        except (ValueError, TypeError):
            raise ValidationError(
                _('El campo "%s" debe ser un valor numerico valido.', field_name))
        if min_val is not None and result < min_val:
            raise ValidationError(
                _('El campo "%s" no puede ser menor a %s.', field_name, min_val))
        return result

    @classmethod
    def validate_vehicle_data(cls, data):
        """Prepara los datos del controlador de vehículos o lanza ValidationError si son inválidos."""
        errors = []
        vals = {}

        # --- CAMPOS OBLIGATORIOS ---

        # 1. Placa (license_plate) - obligatorio, formato alfanumerico
        plate = cls.clean_str(data.get('license_plate'))
        if not plate:
            errors.append(_('La placa del vehiculo es obligatoria.'))
        elif not PLATE_PATTERN.match(plate):
            errors.append(
                _('La placa debe contener entre 4 y 15 caracteres alfanumericos o guiones.'))
        else:
            # Verificar duplicados
            existing = request.env['fleet.vehicle'].sudo().search_count(
                [('license_plate', '=ilike', plate)])
            if existing:
                errors.append(
                    _('Ya existe un vehiculo registrado con la placa "%s".', plate))
            vals['license_plate'] = plate.upper()

        # 2. Modelo del vehiculo (model_id) - obligatorio
        model_id = cls.clean_int(
            data.get('model_id'), 'Modelo del vehiculo')
        if not model_id:
            errors.append(_('El modelo del vehiculo es obligatorio.'))
        else:
            model_exists = request.env['fleet.vehicle.model'].sudo().search_count(
                [('id', '=', model_id)])
            if not model_exists:
                errors.append(
                    _('El modelo de vehiculo seleccionado no existe en el sistema.'))
            vals['model_id'] = model_id

        # --- CAMPOS OPCIONALES CON VALIDACION ---

        # 3. Tipo de vehiculo (control_type)
        control_type = cls.clean_str(data.get('control_type'))
        if control_type:
            if control_type not in VALID_VEHICLE_TYPES:
                errors.append(
                    _('El tipo de vehiculo "%s" no es valido. Opciones: %s',
                      control_type, ', '.join(VALID_VEHICLE_TYPES)))
            else:
                vals['control_type'] = control_type
        else:
            vals['control_type'] = 'car'  # valor por defecto

        # 4. Tipo de combustible (fuel_type)
        fuel_type = cls.clean_str(data.get('fuel_type'))
        if fuel_type:
            if fuel_type not in VALID_FUEL_TYPES:
                errors.append(
                    _('El tipo de combustible "%s" no es valido.', fuel_type))
            else:
                vals['fuel_type'] = fuel_type

        # 5. Condicion operativa (control_condition)
        condition = cls.clean_str(data.get('control_condition'))
        if condition:
            if condition not in VALID_CONDITIONS:
                errors.append(
                    _('La condicion operativa "%s" no es valida. Opciones: %s',
                      condition, ', '.join(VALID_CONDITIONS)))
            else:
                vals['control_condition'] = condition
        else:
            vals['control_condition'] = 'enabled'

        # 6. Color
        color = cls.clean_str(data.get('color'))
        if color:
            if len(color) > 50:
                errors.append(_('El color no puede exceder 50 caracteres.'))
            else:
                vals['color'] = color

        # 7. Numero de chasis / VIN (vin_sn)
        vin = cls.clean_str(data.get('vin_sn'))
        if vin:
            if len(vin) < 5 or len(vin) > 25:
                errors.append(
                    _('El numero de chasis/VIN debe tener entre 5 y 25 caracteres.'))
            else:
                # Verificar duplicado de VIN
                vin_dup = request.env['fleet.vehicle'].sudo().search_count(
                    [('vin_sn', '=ilike', vin)])
                if vin_dup:
                    errors.append(
                        _('Ya existe un vehiculo con el numero de chasis "%s".', vin))
                vals['vin_sn'] = vin.upper()

        # 8. Numero de motor (engine_sn)
        engine = cls.clean_str(data.get('engine_sn'))
        if engine:
            if len(engine) > 30:
                errors.append(
                    _('El numero de motor no puede exceder 30 caracteres.'))
            else:
                vals['engine_sn'] = engine

        # 9. Ano del modelo (model_year)
        model_year = cls.clean_str(data.get('model_year'))
        if model_year:
            year_int = cls.clean_int(model_year, 'Ano del modelo', 1950, 2100)
            if year_int is not None:
                vals['model_year'] = str(year_int)

        # 10. Asientos (seats)
        seats = cls.clean_int(data.get('seats'), 'Numero de asientos', 1, 80)
        if seats is not None:
            vals['seats'] = seats

        # 11. Odometro inicial (odometer)
        odometer = cls.clean_float(
            data.get('odometer'), 'Kilometraje / Odometro', 0)
        if odometer is not None:
            vals['odometer'] = odometer

        # 12. Unidad de odometro
        odo_unit = cls.clean_str(data.get('odometer_unit'))
        if odo_unit:
            if odo_unit not in VALID_ODOMETER_UNITS:
                errors.append(
                    _('La unidad del odometro debe ser "kilometers" o "miles".'))
            else:
                vals['odometer_unit'] = odo_unit
        else:
            vals['odometer_unit'] = 'kilometers'

        # 13. Capacidad / Carga util (capacity_info)
        capacity = cls.clean_str(data.get('capacity_info'))
        if capacity:
            if len(capacity) > 100:
                errors.append(
                    _('La capacidad no puede exceder 100 caracteres.'))
            else:
                vals['capacity_info'] = capacity

        # 14. Encargado del vehiculo (driver_id)
        driver_id = cls.clean_int(data.get('driver_id'), 'Encargado del vehiculo')
        if driver_id:
            driver_exists = request.env['res.partner'].sudo().search_count(
                [('id', '=', driver_id)])
            if not driver_exists:
                errors.append(
                    _('El contacto seleccionado como encargado no existe.'))
            else:
                vals['driver_id'] = driver_id

        # 15. Administrador de permisos (manager_id)
        manager_id = cls.clean_int(data.get('manager_id'), 'Administrador de permisos')
        if manager_id:
            manager = request.env['res.users'].sudo().browse(manager_id)
            if not manager.exists():
                errors.append(
                    _('El usuario seleccionado como administrador no existe.'))
            elif not manager.has_group('fleet.fleet_group_manager'):
                errors.append(
                    _('El administrador de permisos debe pertenecer al grupo de Administradores de Flota.'))
            else:
                vals['manager_id'] = manager_id

        # 16. Departamento / Area (department_name)
        dept = cls.clean_str(data.get('department_name'))
        if dept:
            if len(dept) > 100:
                errors.append(
                    _('El departamento no puede exceder 100 caracteres.'))
            else:
                vals['department_name'] = dept

        # 17. Observaciones generales (control_notes)
        notes = cls.clean_str(data.get('control_notes'))
        if notes:
            if len(notes) > 2000:
                errors.append(
                    _('Las observaciones no pueden exceder 2000 caracteres.'))
            else:
                vals['control_notes'] = notes

        # --- ERRORES ACUMULADOS ---
        if errors:
            raise ValidationError('\n'.join(str(e) for e in errors))

        return vals
