/** @odoo-module **/
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";
import { Component, onWillStart, onMounted, onWillUnmount, useState } from "@odoo/owl";

const { DateTime } = luxon;
const SQL_FORMAT = "yyyy-MM-dd HH:mm:ss";

export class FleetDashboard extends Component {
    static template = "control_vehiculos.Dashboard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.zone = user.context.tz || "America/Guayaquil";
        this.loadSerial = 0;
        this.state = useState({
            selected: this.now.toISODate(), mode: "week", loading: true, error: "",
            vehicles: [], events: [], pending: [], pendingCount: 0, isManager: false,
            refreshedAt: "", opening: false,
        });
        onWillStart(() => this.loadData());
        onMounted(() => {
            this.timer = setInterval(() => { if (!document.hidden) this.loadData(true); }, 60000);
        });
        onWillUnmount(() => { clearInterval(this.timer); this.loadSerial++; });
    }

    get now() { return DateTime.now().setZone(this.zone).setLocale("es"); }
    date(value) { return DateTime.fromISO(value, { zone: this.zone }).setLocale("es"); }
    instant(value) { return DateTime.fromSQL(value, { zone: "utc" }).setZone(this.zone).setLocale("es"); }
    sql(date) { return date.toUTC().toFormat(SQL_FORMAT); }
    get selectedDate() { return this.date(this.state.selected); }
    get bounds() {
        const date = this.selectedDate;
        if (this.state.mode === "week") {
            const start = date.startOf("week");
            return { start, end: start.plus({ days: 7 }) };
        }
        return { start: date.startOf("month").startOf("week"), end: date.endOf("month").startOf("week").plus({ days: 7 }) };
    }
    get periodLabel() {
        const { start, end } = this.bounds;
        if (this.state.mode === "month") return this.selectedDate.toFormat("LLLL yyyy");
        const last = end.minus({ days: 1 });
        return start.month === last.month
            ? `${start.day} – ${last.toFormat("d 'de' LLLL yyyy")}`
            : `${start.toFormat("d LLL")} – ${last.toFormat("d LLL yyyy")}`;
    }
    get selectedLabel() { return this.selectedDate.toFormat("cccc d 'de' LLLL").replace(/^./, c => c.toUpperCase()); }
    get days() {
        const { start, end } = this.bounds;
        const days = [];
        for (let date = start; date < end; date = date.plus({ days: 1 })) {
            const key = date.toISODate();
            days.push({ key, date, number: date.day, label: date.toFormat("ccc"),
                today: key === this.now.toISODate(), selected: key === this.state.selected,
                muted: this.state.mode === "month" && date.month !== this.selectedDate.month });
        }
        return days;
    }
    get weekdays() { return ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]; }
    get availableCount() { return this.state.vehicles.filter(v => this.freeSlot(v)).length; }

    async loadData(background = false) {
        const serial = ++this.loadSerial;
        const { start, end } = this.bounds;
        if (!background) this.state.loading = true;
        try {
            const data = await this.orm.call("fleet.vehicle", "get_calendar_data", [this.sql(start), this.sql(end)]);
            if (serial !== this.loadSerial) return;
            Object.assign(this.state, { vehicles: data.vehicles, events: data.events, pending: data.pending,
                pendingCount: data.pending_count || 0, isManager: data.is_manager,
                loading: false, error: "", refreshedAt: this.now.toFormat("HH:mm") });
        } catch {
            if (serial !== this.loadSerial) return;
            this.state.loading = false;
            this.state.error = "No pudimos actualizar la disponibilidad. Intenta de nuevo antes de solicitar.";
        }
    }

    async selectDay(key) {
        const oldStart = this.bounds.start.toISODate();
        this.state.selected = key;
        if (oldStart !== this.bounds.start.toISODate()) await this.loadData();
    }
    async changePeriod(direction) {
        const unit = this.state.mode === "week" ? { weeks: direction } : { months: direction };
        this.state.selected = this.selectedDate.plus(unit).toISODate();
        await this.loadData();
    }
    async changeDay(direction) { await this.selectDay(this.selectedDate.plus({ days: direction }).toISODate()); }
    async goToday() { this.state.selected = this.now.toISODate(); await this.loadData(); }
    async setMode(mode) { if (this.state.mode !== mode) { this.state.mode = mode; await this.loadData(); } }

    dayEvents(vehicle, day = this.state.selected) {
        const start = this.date(day).startOf("day");
        const end = start.plus({ days: 1 });
        return this.state.events.filter(e => e.vehicle_id === vehicle.id && this.instant(e.start) < end && this.instant(e.end) > start)
            .sort((a, b) => a.start.localeCompare(b.start));
    }
    eventTime(event) {
        if (["maintenance", "unavailable"].includes(event.kind)) return "Todo el día";
        if (event.open_end) return "Hasta registrar la devolución";
        const start = this.instant(event.start), end = this.instant(event.end);
        return start.hasSame(end, "day") ? `${start.toFormat("HH:mm")} – ${end.toFormat("HH:mm")}`
            : `${start.toFormat("d LLL, HH:mm")} → ${end.toFormat("d LLL, HH:mm")}`;
    }
    getEventLabel(event) { return `${event.title} · ${this.eventTime(event)}`; }
    photoUrl(vehicle) { return `/web/image/fleet.vehicle/${vehicle.id}/control_photo`; }

    dayStatus(vehicle, day = this.state.selected) {
        if (this.state.error) return { kind: "unavailable", label: "Sin actualizar" };
        const events = this.dayEvents(vehicle, day);
        const event = ["unavailable", "maintenance", "delivered", "reserved"].map(k => events.find(e => e.kind === k)).find(Boolean);
        if (event) return { kind: event.kind, label: event.open_end ? "Por devolver" : event.title };
        if (events.some(e => e.kind === "completed") && this.date(day).endOf("day") < this.now) return { kind: "completed", label: "Uso finalizado" };
        return { kind: "free", label: this.date(day).endOf("day") < this.now ? "Sin reservas" : "Disponible" };
    }

    // Busca un hueco real de al menos 30 minutos; los pendientes no bloquean el calendario.
    freeSlot(vehicle) {
        if (this.state.error || this.state.loading || vehicle.condition !== "enabled") return null;
        const dayStart = this.selectedDate.startOf("day"), dayEnd = dayStart.plus({ days: 1 });
        if (dayEnd <= this.now) return null;
        let cursor = dayStart;
        if (this.now > cursor) cursor = this.now.startOf("minute").plus({ minutes: 30 - this.now.minute % 30 });
        const intervals = this.dayEvents(vehicle).filter(e => e.blocks)
            .map(e => ({ start: this.instant(e.start), end: this.instant(e.end) }));
        const gaps = [];
        for (const interval of intervals) {
            if (interval.start > cursor) gaps.push({ start: cursor, end: DateTime.min(interval.start, dayEnd) });
            cursor = DateTime.max(cursor, interval.end);
        }
        if (cursor < dayEnd) gaps.push({ start: cursor, end: dayEnd });
        const valid = gaps.filter(gap => gap.end.diff(gap.start, "minutes").minutes >= 30);
        const preferred = dayStart.set({ hour: 8 });
        const gap = valid.find(g => g.start <= preferred && g.end >= preferred.plus({ minutes: 30 })) || valid[0];
        if (!gap) return null;
        const start = gap.start <= preferred && gap.end >= preferred.plus({ minutes: 30 }) ? preferred : gap.start;
        return { start, end: DateTime.min(start.plus({ hours: 1 }), gap.end) };
    }

    // Cada reserva ocupa una franja continua; las que coinciden usan filas diferentes.
    timeline(vehicle) {
        const days = this.days;
        const candidates = this.state.events.filter(e => e.vehicle_id === vehicle.id).map(event => {
            const indexes = days.map((d, i) => this.instant(event.start) < d.date.plus({ days: 1 }) && this.instant(event.end) >= d.date ? i : -1).filter(i => i >= 0);
            return indexes.length ? { ...event, first: indexes[0], last: indexes[indexes.length - 1] } : null;
        }).filter(Boolean).sort((a, b) => a.first - b.first || a.start.localeCompare(b.start));
        const lanes = [];
        const events = candidates.map(event => {
            let lane = lanes.findIndex(end => end < event.first);
            if (lane < 0) lane = lanes.length;
            lanes[lane] = event.last;
            return { ...event, style: `grid-column:${event.first + 1} / ${event.last + 2}; grid-row:${lane + 1}` };
        });
        return { events, height: `${Math.max(132, lanes.length * 50 + 24)}px` };
    }
    async chooseEvent(event) {
        const key = DateTime.max(this.instant(event.start).startOf("day"), this.bounds.start).toISODate();
        await this.selectDay(key);
        document.querySelector(".o_fleet_calendar .o_control_panel")?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
    async openEvent(event) {
        if (!event.record_id || !event.model) return;
        await this.action.doAction({ type: "ir.actions.act_window", res_model: event.model,
            res_id: event.record_id, views: [[false, "form"]], target: "current" });
    }
    async requestVehicle(vehicle) {
        if (this.state.opening) return;
        this.state.opening = true;
        try {
            await this.loadData(true);
            const currentVehicle = this.state.vehicles.find(v => v.id === vehicle.id);
            const slot = currentVehicle && this.freeSlot(currentVehicle);
            if (!slot) { this.notification.add("No hay un horario disponible para este día. Elige otra fecha.", { type: "warning" }); return; }
            const action = await this.orm.call("fleet.vehicle", "action_open_request_usage_wizard", [[vehicle.id]]);
            action.context = { ...action.context, default_requested_start: this.sql(slot.start), default_requested_end: this.sql(slot.end) };
            await this.action.doAction(action, { onClose: () => this.loadData(true) });
        } catch (error) {
            this.notification.add(error.data?.message || "No se pudo abrir la solicitud. Actualiza la disponibilidad e intenta de nuevo.", { type: "warning" });
        } finally { this.state.opening = false; }
    }
    pendingDate(row) { return this.instant(row.start).toFormat("d LLL · HH:mm"); }
    openPending(id) { return this.openEvent({ record_id: id, model: "control.vehicle.assignment" }); }
    openAllPending() {
        const domain = [["state", "=", "pending"]];
        if (!this.state.isManager) domain.push(["requester_id", "=", user.userId]);
        return this.action.doAction({ type: "ir.actions.act_window", name: this.state.isManager ? "Solicitudes pendientes" : "Mis solicitudes pendientes",
            res_model: "control.vehicle.assignment", domain, views: [[false, "list"], [false, "form"]] });
    }
    openVehicleList() {
        return this.action.doAction({ type: "ir.actions.act_window", name: "Vehículos", res_model: "fleet.vehicle", views: [[false, "kanban"], [false, "list"], [false, "form"]] });
    }
}

registry.category("actions").add("fleet_dashboard_action", FleetDashboard);
