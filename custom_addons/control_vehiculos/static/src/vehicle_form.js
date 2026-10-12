/** @odoo-module **/
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { formView } from "@web/views/form/form_view";
import { FormController } from "@web/views/form/form_controller";

class VehicleFormController extends FormController {
    static template = "control_vehiculos.FormView";
    // Activa el servicio que muestra mensajes al usuario.
    setup() {
        super.setup();
        this.vehicleNotification = useService("notification");
    }
    // Recuerda si el vehículo es nuevo antes de guardarlo.
    async onWillSaveRecord(record, changes) {
        this.vehicleWasNew = record.isNew;
        return super.onWillSaveRecord(record, changes);
    }
    // Muestra la confirmación de registro o actualización después de guardar.
    async onRecordSaved(record, changes) {
        await super.onRecordSaved(record, changes);
        const plate = record.data.license_plate || "Sin placa";
        this.vehicleNotification.add(
            `Los datos del vehículo ${plate} se guardaron correctamente.`,
            { title: this.vehicleWasNew ? "Vehículo registrado" : "Vehículo actualizado", type: "success" }
        );
    }
    // Personaliza la confirmación de eliminación y su mensaje de resultado.
    get deleteConfirmationDialogProps() {
        const props = super.deleteConfirmationDialogProps;
        const plate = this.model.root.data.license_plate || "Sin placa";
        const confirm = props.confirm;
        return {
            ...props,
            title: "Eliminar vehículo",
            body: `¿Eliminar el vehículo ${plate}? Esta operación elimina su registro y puede afectar datos relacionados. Si deseas conservar su historial, utiliza Archivar.`,
            confirmLabel: "Eliminar vehículo",
            cancelLabel: "Conservar vehículo",
            confirm: async () => {
                await confirm();
                this.vehicleNotification.add(`El vehículo ${plate} se eliminó correctamente.`, { title: "Vehículo eliminado", type: "success" });
            },
        };
    }
    // Explica el archivado y muestra un aviso cuando termina.
    get archiveDialogProps() {
        const props = super.archiveDialogProps;
        const plate = this.model.root.data.license_plate || "Sin placa";
        const confirm = props.confirm;
        return {
            ...props,
            body: `¿Archivar el vehículo ${plate}? Dejará de aparecer en la lista habitual. Sus datos se conservarán y podrás restaurarlo desde el filtro Archivados.`,
            confirm: async () => {
                await confirm();
                this.vehicleNotification.add(`El vehículo ${plate} se archivó. Su historial se conserva.`, { title: "Vehículo archivado", type: "success" });
            },
        };
    }
    // Añade una confirmación visual después de restaurar un vehículo archivado.
    getStaticActionMenuItems() {
        const items = super.getStaticActionMenuItems();
        const restore = items.unarchive.callback;
        items.unarchive.callback = async () => {
            const plate = this.model.root.data.license_plate || "Sin placa";
            await restore();
            this.vehicleNotification.add(`El vehículo ${plate} vuelve a aparecer en la lista habitual.`, { title: "Vehículo restaurado", type: "success" });
        };
        return items;
    }
}
registry.category("views").add("control_vehicle_form", { ...formView, Controller: VehicleFormController });
