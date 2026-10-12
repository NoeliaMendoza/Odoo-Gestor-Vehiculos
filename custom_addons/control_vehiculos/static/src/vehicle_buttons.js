/** @odoo-module **/
import { ListController } from "@web/views/list/list_controller";
import { listView } from "@web/views/list/list_view";
import { KanbanController } from "@web/views/kanban/kanban_controller";
import { kanbanView } from "@web/views/kanban/kanban_view";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class VehicleListController extends ListController {
    setup() {
        super.setup();
        this.action = useService("action");
    }
    openCalendar() {
        this.action.doAction("control_vehiculos.action_fleet_dashboard");
    }
}
export const vehicleListView = {
    ...listView,
    Controller: VehicleListController,
    buttonTemplate: "control_vehiculos.ListView.Buttons",
};
registry.category("views").add("control_vehicle_list", vehicleListView);

export class VehicleKanbanController extends KanbanController {
    setup() {
        super.setup();
        this.action = useService("action");
    }
    openCalendar() {
        this.action.doAction("control_vehiculos.action_fleet_dashboard");
    }
}
export const vehicleKanbanView = {
    ...kanbanView,
    Controller: VehicleKanbanController,
    buttonTemplate: "control_vehiculos.KanbanView.Buttons",
};
registry.category("views").add("control_vehicle_kanban", vehicleKanbanView);
