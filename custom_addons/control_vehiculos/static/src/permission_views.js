/** @odoo-module **/
import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { ListController } from "@web/views/list/list_controller";
import { formView } from "@web/views/form/form_view";
import { FormController } from "@web/views/form/form_controller";
// Usa la plantilla personalizada de la lista de permisos.
class PermissionListController extends ListController { static template = "control_vehiculos.PermissionList"; }
// Usa la plantilla personalizada del formulario de permisos.
class PermissionFormController extends FormController { static template = "control_vehiculos.PermissionForm"; }
registry.category("views").add("vehicle_permission_list", {...listView, Controller: PermissionListController});
registry.category("views").add("vehicle_permission_form", {...formView, Controller: PermissionFormController});
