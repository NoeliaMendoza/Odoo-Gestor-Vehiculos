/** @odoo-module **/
import { Component, useState } from '@odoo/owl';
import { registry } from '@web/core/registry';
import { standardFieldProps } from '@web/views/fields/standard_field_props';

export class FuelGauge extends Component {
    static template = 'control_vehiculos.FuelGauge';
    static props = { ...standardFieldProps };
    // Prepara el mensaje de error del campo de combustible.
    setup() {
        this.state = useState({ error: '' });
    }
    // Lee el porcentaje del registro que se está editando.
    get value() {
        return this.props.record.data[this.props.name];
    }
    // Distingue un campo vacío del valor válido 0 %.
    get hasValue() {
        return (
            this.value !== false &&
            this.value !== undefined &&
            this.value !== null &&
            this.value !== ''
        );
    }
    // Indica si el nivel registrado está por debajo del 50 %.
    get low() {
        return this.hasValue && Number(this.value) < 50;
    }
    // Identifica si el campo corresponde al combustible de salida.
    get checkout() {
        return this.props.name === 'checkout_fuel';
    }
    // Convierte el porcentaje en el giro de la aguja del medidor.
    get rotation() {
        return `rotate(${Number(this.value) * 1.8} 140 130)`;
    }
    // Define los porcentajes de los botones de selección rápida.
    get choices() {
        return [0, 25, 50, 75, 100];
    }
    // Valida un porcentaje entero entre 0 y 100 y actualiza el formulario.
    async select(value) {
        if (this.props.readonly) return;
        if (
            value === '' ||
            !Number.isInteger(Number(value)) ||
            Number(value) < 0 ||
            Number(value) > 100
        ) {
            this.state.error = 'Escribe un porcentaje entero entre 0 y 100.';
            return;
        }
        this.state.error = '';
        await this.props.record.update({ [this.props.name]: Number(value) });
    }
    // Procesa el número escrito y restaura el valor anterior si es inválido.
    async onNumberChange(ev) {
        await this.select(ev.target.value);
        if (this.state.error) ev.target.value = this.hasValue ? this.value : '';
    }
    // Actualiza el porcentaje al mover la barra deslizante.
    onRangeInput(ev) {
        return this.select(ev.target.value);
    }
}
registry
    .category('fields')
    .add('vehicle_fuel_gauge', { component: FuelGauge, supportedTypes: ['integer'] });
