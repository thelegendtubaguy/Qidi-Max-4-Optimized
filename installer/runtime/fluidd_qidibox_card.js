// QidiBox dashboard card for QIDI's bundled Fluidd v1.30.5 (/home/qidi/fluidd/assets/index-DlFvHGAh.js).
// fluidd_box_filaments.py inserts this file verbatim into the bundle's module scope right after the stock Box card,
// so it may use that bundle's minified names: Xe CollapsableCard, R AppBtn, x VIcon, Oe VBtn, Ie VSelect, Fb VDialog,
// De VCard, lr VCardTitle, xe VCardText, F VDivider, I socket actions, hr filament-list mixin, wn filament-list parser,
// Wle stock Box Config view. Do not declare local names that shadow them. The card reads the same printer state and
// sends the same Box commands as the stock Box card, which it does not replace.
const TltgQidiBoxCard = (() => {
  const EXTERNAL = 16;
  const NONE = "#00000000";
  const COMMANDS = ["EJECT_FILAMENT_CONTROL", "LOAD_FILAMENT_CONTROL", "UNLOAD_FILAMENT_CONTROL"];
  const LEGACY_COMMANDS = ["E_BOX", "E_LOAD", "E_UNLOAD"];
  const [EJECT, LOAD, UNLOAD] = [0, 1, 2];
  // Same labels as the stock Box card: Box 1 slots are 1A-1D, Box 2 slots 2A-2D, and so on.
  const slotLabel = n => (n === EXTERNAL ? "Ext" : Math.floor(n / 4) + 1 + String.fromCharCode((n % 4) + 65));
  const slotNumber = value => {
    const match = /^slot(\d+)$/.exec(String(value || ""));
    return match ? parseInt(match[1], 10) : null;
  };
  const isColor = value => typeof value === "string" && /^#[0-9A-Fa-f]{6}$/.test(value);
  const textColor = color => (isColor(color) ? wn.getTextColor(color) : "inherit");

  const Spool = {
    functional: true,
    props: { color: String, present: Boolean },
    render(h, { props }) {
      const fill = props.present && isColor(props.color) ? props.color : "none";
      const flange = { attrs: { x: 4, width: 44, height: 7, rx: 3, fill: "#8d8d93" } };
      return h("svg", { attrs: { width: 52, height: 72, viewBox: "0 0 52 72" } }, [
        h("rect", {
          attrs: {
            x: 10, y: 8, width: 32, height: 56, rx: 3, fill,
            stroke: props.present ? "rgba(0,0,0,0.35)" : "rgba(128,128,128,0.7)",
            "stroke-dasharray": props.present ? null : "3 3"
          }
        }),
        props.present ? h("rect", { attrs: { x: 11, y: 9, width: 10, height: 54, fill: "#fff", opacity: 0.15 } }) : null,
        h("rect", { attrs: { x: 22, y: 9, width: 8, height: 54, fill: "rgba(0,0,0,0.18)" } }),
        h("rect", { ...flange, attrs: { ...flange.attrs, y: 2 } }),
        h("rect", { ...flange, attrs: { ...flange.attrs, y: 63 } })
      ]);
    }
  };

  // Slot tile under each spool: green border when filament is at the slot inlet, dashed amber while reading RFID,
  // and an outer outline in its auto-reload group's filament color, edged so dark and light filaments stay visible.
  const SlotTile = {
    functional: true,
    props: { label: String, color: String, present: Boolean, reading: Boolean, group: String },
    render(h, { props }) {
      const fill = props.present && isColor(props.color) ? props.color : "rgba(128,128,128,0.15)";
      return h("svg", { attrs: { width: 52, height: 26, viewBox: "0 0 120 60" } }, [
        props.group
          ? [
              h("rect", { attrs: { x: 3, y: 1, width: 114, height: 58, rx: 15, fill: "none", stroke: "rgba(128,128,128,0.9)", "stroke-width": 8 } }),
              h("rect", { attrs: { x: 3, y: 1, width: 114, height: 58, rx: 15, fill: "none", stroke: props.group, "stroke-width": 5 } })
            ]
          : null,
        h("rect", {
          attrs: {
            x: 12, y: 8, width: 96, height: 44, rx: 10, fill, "stroke-width": 5,
            stroke: props.reading ? "#ffb300" : props.present ? "#4caf50" : "#757575",
            "stroke-dasharray": props.reading ? "14 8" : null
          }
        }),
        h("text", {
          attrs: {
            x: 60, y: 41, "text-anchor": "middle", "font-weight": 700, "font-size": 26,
            fill: props.present && isColor(props.color) ? textColor(props.color) : "currentColor"
          }
        }, [props.label])
      ]);
    }
  };

  return {
    name: "TltgQidiBoxCard",
    mixins: [hr],
    data: () => ({ selected: 0, view: null, failed: false, editing: false, draft: null, mapping: null }),
    computed: {
      printer() {
        return this.$store.state.printer.printer;
      },
      variables() {
        return this.$store.getters["printer/getVariables"];
      },
      filas() {
        return this.$store.state.printer.officiallFilasList;
      },
      controller() {
        return this.printer.multi_color_controller;
      },
      boxCount() {
        return Math.max(0, Math.min(4, this.variables.boxCount || 0));
      },
      slotNumbers() {
        return Array.from({ length: this.boxCount * 4 }, (_, n) => n);
      },
      slots() {
        const slots = {};
        [...this.slotNumbers, EXTERNAL].forEach(n => (slots[n] = this.resolveSlot(n)));
        return slots;
      },
      // value_tN maps logical tool N to a slot; missing mappings fall back to the external spool at print start.
      toolMap() {
        const saved = (this.printer.save_variables && this.printer.save_variables.variables) || {};
        const map = [];
        for (let tool = 0; tool < 16; tool++) {
          const slot = slotNumber(saved["value_t" + tool]);
          if (slot !== null && this.slots[slot]) map.push({ tool, slot });
        }
        return map;
      },
      autoReload() {
        return this.$store.getters["printer/getAutoSwitchState"][2] === 1;
      },
      // Same grouping as the stock Box card's AUTO view: loaded Box slots with the same color, filament, and vendor
      // reload into each other. Groups are lettered in slot order and shown in their shared filament color.
      reloadGroups() {
        const byKey = {};
        this.slotNumbers.forEach(n => {
          const s = this.slots[n];
          if (!s.present) return;
          const key = `${s.color}-${s.name}-${s.vendor}`;
          (byKey[key] = byKey[key] || []).push(n);
        });
        const groups = {};
        Object.values(byKey)
          .filter(members => members.length > 1)
          .forEach((members, i) => members.forEach(n => (groups[n] = { letter: String.fromCharCode(65 + i), color: this.slots[members[0]].color, members })));
        return groups;
      },
      toolhead() {
        const sensor = this.printer["filament_switch_sensor filament_switch_sensor"];
        return !!(sensor && sensor.filament_detected);
      },
      // The slot the stock Box card marks as feeding the extruder.
      loadedSlot() {
        const sync = slotNumber(this.variables.slotSync);
        if (sync !== null) return sync;
        return this.variables.slotSync === "slot-1" && this.toolhead ? EXTERNAL : null;
      },
      // Hub filament sensor; 0 means filament is at the hub. 01.01.07.01 publishes it only on multi_color_controller.
      hub() {
        const extras = this.printer.box_extras;
        const box = this.controller && this.controller.box;
        if (extras && extras.b_endstop_state != null) return extras.b_endstop_state;
        return box ? box.b_endstop_state : null;
      },
      task() {
        const task = this.controller && this.controller.task;
        return task && task.flow_id != null ? task : null;
      },
      klippyReady() {
        const webhooks = this.printer.webhooks;
        return !webhooks || !webhooks.state || webhooks.state === "ready";
      },
      printing() {
        const stats = this.printer.print_stats;
        return String((stats && stats.state) || "").toLowerCase() === "printing";
      },
      busy() {
        const extras = this.printer.box_extras;
        return !this.klippyReady || this.printing || !!(extras && extras.box_button_state) || !!this.task;
      },
      // Like TLTG_RESET_TOOL_MAPPINGS, mappings change only while idle, so a paused print keeps its recovery state.
      mappingLocked() {
        const stats = this.printer.print_stats;
        return this.busy || String((stats && stats.state) || "").toLowerCase() === "paused";
      },
      // Tools for every active Box slot, plus any mapped beyond them.
      toolCount() {
        const mapped = this.toolMap.reduce((most, entry) => Math.max(most, entry.tool + 1), 0);
        return Math.min(16, Math.max(this.boxCount * 4, mapped, 1));
      },
      // On 01.01.07.01 the patched filament list carries the firmware filament database.
      catalog() {
        return (this.printer.box485 && this.filas && this.filas.tltgFilaments) || null;
      },
      palette() {
        const colors = (this.filas && this.filas.colordict) || {};
        return Array.from(new Set(Object.keys(colors).map(key => colors[key]).filter(isColor)));
      },
      current() {
        return this.slots[this.selected] || this.slots[EXTERNAL];
      },
      // The hub and toolhead sensors are shared by every slot. The hub sees the loaded slot's filament, or the
      // last-loaded slot's while it is parked or unloading; the toolhead sees only the loaded slot's.
      hubSlot() {
        if (this.hub !== 0) return null;
        return this.loadedSlot !== null && this.loadedSlot !== EXTERNAL ? this.loadedSlot : this.variables.lastLoadSlot;
      },
      toolheadSlot() {
        return this.toolhead ? this.loadedSlot : null;
      }
    },
    watch: {
      boxCount() {
        if (!this.slots[this.selected]) this.selected = this.loadedSlot !== null ? this.loadedSlot : 0;
      }
    },
    created() {
      if (this.loadedSlot !== null) this.selected = this.loadedSlot;
      if (this.filas) return;
      // The stock Box card loads the filament list; this card may be the only one on the dashboard.
      this.getOfficiallFilasList()
        .then(text => this.filas || this.$store.commit("printer/setOfficiallFilasList", wn.configToDict(text)))
        .catch(error => console.error("[tltg] QidiBox filament list failed", error));
    },
    errorCaptured(error) {
      console.error("[tltg] QidiBox card failed", error);
      this.failed = true;
      return false;
    },
    methods: {
      // Resolves a slot the same way the stock Box card does, through the patched getVariables getter and filament list.
      resolveSlot(n) {
        const v = this.variables;
        const d = this.filas;
        const external = n === EXTERNAL;
        const present = !!v.slot[n];
        const keys = external ? v.rackExtra : [v.colorSlot[n], v.filamentSlot[n], v.vendorSlot[n]];
        const fila = present && d ? d["fila" + keys[1]] : null;
        const stepper = this.printer["box_stepper slot" + n];
        return {
          n,
          label: slotLabel(n),
          present,
          external,
          color: (present && d && d.colordict[String(keys[0])]) || NONE,
          name: (fila && fila.filament) || "",
          type: (fila && fila.type) || "",
          vendor: (present && d && d.vendor_list[keys[2]]) || "",
          minTemp: fila && fila.min_temp,
          maxTemp: fila && fila.max_temp,
          boxMaxTemp: fila && fila.box_max_temp,
          reading: !!(stepper && stepper.rfid_state === 1)
        };
      },
      renderReloadMark(h, n) {
        const group = this.autoReload && this.reloadGroups[n];
        return h("div", {
          staticClass: "text-caption font-weight-bold d-flex align-center justify-center rounded-pill px-2 mt-1",
          style: {
            height: "16px", visibility: group ? "visible" : "hidden", background: group ? group.color : null,
            color: group ? textColor(group.color) : null, border: group ? "1px solid rgba(128,128,128,0.9)" : null
          },
          attrs: { title: group ? "Auto-reload group " + group.letter + ": " + group.members.map(slotLabel).join(", ") : null }
        }, group ? [h(x, { staticClass: "mr-1", attrs: { xSmall: true }, style: { color: "inherit" } }, ["$sync"]), group.letter] : []);
      },
      reloadText(n) {
        if (!this.autoReload) return "Automatic reload is off";
        const group = this.reloadGroups[n];
        if (!group) return "No auto-reload backup";
        return "Auto-reload with " + group.members.filter(m => m !== n).map(slotLabel).join(", ");
      },
      toolsFor(n) {
        return this.toolMap.filter(entry => entry.slot === n).map(entry => "T" + entry.tool);
      },
      // Mirrors the stock Box card's button rules: filament at the inlet allows Eject and Load; the slot that last
      // loaded with filament at the hub allows Unload instead of Load. The external spool has no Box controls.
      disabled(action) {
        const s = this.current;
        if (this.busy || s.external || !s.present) return true;
        const loaded = this.hub === 0 && this.variables.lastLoadSlot === s.n;
        if (action === LOAD) return loaded;
        if (action === UNLOAD) return !loaded;
        return false;
      },
      send(action) {
        if (this.disabled(action)) return;
        const n = this.current.n;
        I.printerGcodeScript(this.controller ? `${COMMANDS[action]} SLOT=${n}` : `${LEGACY_COMMANDS[action]} slot=${n}`);
      },
      readRfid() {
        const s = this.current;
        if (this.busy || s.external || !s.present) return;
        I.printerGcodeScript(this.controller ? `READ_RFID SLOT=${s.n}` : `RFID_READ SLOT=slot${s.n}`);
      },
      openEditor() {
        const s = this.current;
        const match = this.catalog.find(f => f.name === s.name && f.vendor === s.vendor) || this.catalog.find(f => f.name === s.name);
        this.draft = { n: s.n, id: match ? match.id : null, vendor: match ? match.vendor : s.vendor, color: isColor(s.color) ? s.color.toUpperCase() : null };
        this.editing = true;
      },
      // Saves the touchscreen's formats, as the patched stock pickers do: a QF filament ID and a one-element RGB list.
      saveEditor() {
        const d = this.draft;
        const s = this.slots[d.n];
        if (!s || this.busy) return;
        const before = this.catalog.find(f => f.name === s.name && f.vendor === s.vendor);
        if (d.id && (!before || before.id !== d.id)) I.printerGcodeScript(`SAVE_VARIABLE VARIABLE=filament_slot${d.n} VALUE='"${d.id}"'`);
        if (isColor(d.color) && d.color.toUpperCase() !== String(s.color).toUpperCase()) {
          I.printerGcodeScript(`SAVE_VARIABLE VARIABLE=color_slot${d.n} VALUE="['${d.color.slice(1).toUpperCase()}']"`);
        }
        this.editing = false;
      },
      unitClimate(box) {
        const sensor = this.printer["aht20_f heater_box" + (box + 1)];
        const heater = this.printer["heater_generic heater_box" + (box + 1)];
        return {
          humidity: sensor && sensor.humidity != null ? Math.round(sensor.humidity) : null,
          temperature: sensor && sensor.temperature != null ? Math.round(sensor.temperature) : null,
          target: heater && heater.target > 0 ? Math.round(heater.target) : null
        };
      },

      renderGate(h, s) {
        const tools = this.toolsFor(s.n);
        const loaded = this.loadedSlot === s.n;
        const selected = this.selected === s.n;
        return h("div", {
          key: s.n,
          staticClass: "d-flex flex-column align-center rounded py-1",
          style: {
            width: "60px",
            cursor: "pointer",
            background: selected ? "rgba(33,150,243,0.15)" : null,
            outline: selected ? "1px solid rgba(33,150,243,0.55)" : null
          },
          attrs: { title: s.present ? [s.label, s.vendor, s.name].filter(Boolean).join(" · ") : s.label + " · empty" },
          on: { click: () => (this.selected = s.n) }
        }, [
          h("div", {
            staticClass: "text-caption font-weight-bold text-truncate px-1",
            class: loaded ? "primary white--text rounded-pill" : "text--secondary",
            style: { minHeight: "18px", maxWidth: "58px" }
          }, [tools.join(" ")]),
          h("div", { style: { transform: loaded ? "translateY(-3px)" : null, filter: loaded ? "drop-shadow(0 0 5px rgba(255,255,255,0.35))" : null } }, [
            h(Spool, { props: { color: s.color, present: s.present } })
          ]),
          h(SlotTile, {
            props: {
              label: s.label, color: s.color, present: s.present, reading: s.reading,
              group: this.autoReload && this.reloadGroups[s.n] ? this.reloadGroups[s.n].color : null
            }
          }),
          this.renderReloadMark(h, s.n)
        ]);
      },
      renderUnit(h, title, slots, footer) {
        return h("div", {
          staticClass: "rounded-lg pa-2 pb-1",
          style: { background: this.$vuetify.theme.dark ? "rgba(255,255,255,0.05)" : "rgba(0,0,0,0.04)" }
        }, [
          h("div", { staticClass: "d-flex", style: { gap: "4px" } }, slots.map(s => this.renderGate(h, s))),
          h("div", {
            staticClass: "d-flex align-center text-caption text--secondary mt-1 pt-1 px-1",
            style: { gap: "8px", borderTop: "1px solid rgba(128,128,128,0.3)" }
          }, [h("span", { staticClass: "font-weight-medium text--primary" }, [title]), ...(footer || [])])
        ]);
      },
      renderClimate(h, box) {
        const c = this.unitClimate(box);
        const item = (icon, color, text) =>
          h("span", { staticClass: "d-inline-flex align-center" }, [h(x, { staticClass: color, attrs: { small: true } }, [icon]), text]);
        return [
          c.humidity !== null ? item("$humidity", "blue--text text--lighten-2", c.humidity + "%") : null,
          c.temperature !== null ? item("$thermometer", "deep-orange--text text--lighten-2", c.temperature + "°C") : null,
          c.target !== null ? h("span", { staticClass: "ml-auto" }, [item("$fire", "red--text", c.target + "°C")]) : null
        ];
      },
      renderUnits(h) {
        const units = [];
        for (let box = 0; box < this.boxCount; box++) {
          units.push(this.renderUnit(h, "Box " + (box + 1), [0, 1, 2, 3].map(i => this.slots[box * 4 + i]), this.renderClimate(h, box)));
        }
        units.push(this.renderUnit(h, "External", [this.slots[EXTERNAL]]));
        return h("div", { staticClass: "d-flex flex-wrap", style: { gap: "12px" } }, units);
      },
      statusText() {
        if (this.task) return "Box busy" + (this.task.current_step ? ": " + this.task.current_step : "");
        if (this.loadedSlot === null) return "No Box filament loaded";
        const tools = this.toolsFor(this.loadedSlot);
        return "Loaded " + slotLabel(this.loadedSlot) + (tools.length ? " (" + tools.join(", ") + ")" : "");
      },
      // Filament path for the selected slot. Each sensor lights, and the strand reaches it, only when it sees
      // this slot's filament: the inlet when filament is in the slot, then the hub, then the toolhead.
      renderPath(h) {
        const s = this.current;
        const atHub = !s.external && this.hubSlot === s.n;
        const atToolhead = this.toolheadSlot === s.n;
        const reach = atToolhead ? 262 : atHub ? 150 : s.present && !s.external ? 54 : 0;
        const color = isColor(s.color) ? s.color : "#9e9e9e";
        const outline = "rgba(128,128,128,0.8)";
        const zone = this.$vuetify.theme.dark ? "rgba(255,255,255,0.05)" : "rgba(0,0,0,0.04)";
        const sensor = (y, label, on, shown) =>
          shown
            ? [
                h("circle", { attrs: { cx: 92, cy: y, r: 7, fill: on ? "#4caf50" : "rgba(128,128,128,0.35)", stroke: outline } }),
                h("text", { attrs: { x: 108, y: y + 5, "font-size": 13, fill: "currentColor" } }, [label])
              ]
            : [];
        return h("svg", { attrs: { viewBox: "0 0 240 290", width: "100%" }, style: { maxWidth: "260px" } }, [
          h("rect", { attrs: { x: 4, y: 14, width: 232, height: 84, rx: 10, fill: zone } }),
          h("text", { attrs: { x: 14, y: 32, "font-size": 12, fill: "currentColor", opacity: 0.7 } }, [s.external ? "External" : "Slot " + s.label]),
          h("text", { attrs: { x: 108, y: 132, "font-size": 12, fill: "currentColor", opacity: 0.6 } }, ["PTFE"]),
          h("rect", { attrs: { x: 4, y: 160, width: 232, height: 86, rx: 10, fill: zone } }),
          h("text", { attrs: { x: 14, y: 178, "font-size": 12, fill: "currentColor", opacity: 0.7 } }, ["Toolhead"]),
          h("path", { attrs: { d: "M66 14v248l6 6h2l6-6V14", fill: "none", stroke: outline } }),
          reach ? h("rect", { attrs: { x: 67, y: 14, width: 12, height: reach - 14, fill: color } }) : null,
          reach === 262 ? h("polygon", { attrs: { points: "67,262 79,262 74,268 72,268", fill: color } }) : null,
          ...sensor(46, "Slot inlet", s.present, !s.external),
          ...sensor(78, "Hub", atHub, !s.external),
          ...sensor(196, "Toolhead sensor", atToolhead, true),
          h("circle", { attrs: { cx: 54, cy: 228, r: 9, fill: "rgba(128,128,128,0.6)" } }),
          h("circle", { attrs: { cx: 92, cy: 228, r: 9, fill: "rgba(128,128,128,0.6)" } }),
          h("text", { attrs: { x: 108, y: 233, "font-size": 13, fill: "currentColor" } }, ["Extruder"]),
          h("text", { attrs: { x: 108, y: 271, "font-size": 13, fill: "currentColor" } }, ["Nozzle"])
        ]);
      },
      renderSummary(h) {
        const s = this.current;
        const tools = this.toolsFor(s.n);
        const top = [s.external ? "External spool" : "Slot " + s.label, tools.length ? tools.join(", ") : "no tool", this.loadedSlot === s.n ? "loaded" : null]
          .filter(Boolean)
          .join(" · ");
        const temps = [
          s.minTemp != null && s.maxTemp != null ? `Nozzle ${s.minTemp}–${s.maxTemp}°C` : null,
          parseFloat(s.boxMaxTemp) > 0 ? `Box drying up to ${s.boxMaxTemp}°C` : null,
          s.reading ? "Reading RFID…" : null
        ].filter(Boolean);
        return h("div", { staticClass: "px-2 pb-2" }, [
          h("div", { staticClass: "text-overline text--secondary", style: { lineHeight: "1.6" } }, [top]),
          s.present && s.name
            ? h("div", { staticClass: "text-h6 d-flex align-center", style: { gap: "8px" } }, [
                h("span", { style: { width: "16px", height: "16px", borderRadius: "50%", background: s.color, border: "1px solid rgba(128,128,128,0.6)" } }),
                s.name
              ])
            : h("div", { staticClass: "text-h6 text--secondary" }, [s.present ? "Unknown filament" : "Empty"]),
          s.present ? h("div", { staticClass: "text-body-2 text--secondary" }, [[s.vendor, s.type, isColor(s.color) ? s.color.toUpperCase() : null].filter(Boolean).join(" · ")]) : null,
          temps.length ? h("div", { staticClass: "text-caption text--disabled" }, [temps.join(" · ")]) : null,
          s.present && !s.external ? h("div", { staticClass: "text-caption text--secondary d-flex align-center" }, [
            h(x, {
              staticClass: "mr-1",
              attrs: { xSmall: true }
            }, ["$sync"]),
            this.reloadText(s.n)
          ]) : null
        ]);
      },
      renderControls(h) {
        const s = this.current;
        const button = (label, icon, click, disabled) =>
          h(Oe, { props: { small: true, block: true, disabled }, on: { click } }, [h(x, { attrs: { small: true, left: true } }, [icon]), label]);
        const editable = !!this.catalog && s.present && !this.busy;
        return h("div", { staticClass: "pa-2", style: { display: "grid", gridTemplateColumns: "1fr 1fr", gap: "6px" } }, [
          button("Load", "$loadFilament", () => this.send(LOAD), this.disabled(LOAD)),
          button("Unload", "$unloadFilament", () => this.send(UNLOAD), this.disabled(UNLOAD)),
          button("Eject", "$up", () => this.send(EJECT), this.disabled(EJECT)),
          button("Read RFID", "$reRfid", this.readRfid, this.busy || s.external || !s.present),
          this.catalog ? h("div", { style: { gridColumn: "span 2" } }, [button("Edit filament", "$pencil", this.openEditor, !editable)]) : null
        ]);
      },
      // One small diagram per Box, plus the external spool, for each that has tools mapped to it. A tool maps to a
      // single slot, so lines never cross between Boxes, and the groups wrap like the units above at full size.
      renderToolMap(h) {
        const step = 36;
        const groups = [...Array.from({ length: this.boxCount }, (_, box) => [0, 1, 2, 3].map(i => box * 4 + i)), [EXTERNAL]]
          .map(slots => ({ slots, tools: this.toolMap.filter(entry => slots.includes(entry.slot)) }))
          .filter(group => group.tools.length);
        const chip = (cx, y, label, fill, ring, click) =>
          h("g", { style: { cursor: "pointer" }, on: { click } }, [
            h("rect", {
              attrs: {
                x: cx - 15, y, width: 30, height: 18, rx: 4, fill,
                stroke: ring || "rgba(128,128,128,0.6)", "stroke-width": ring ? 2 : 1
              }
            }),
            h("text", {
              attrs: { x: cx, y: y + 13, "text-anchor": "middle", "font-size": 10, "font-weight": 700, fill: isColor(fill) ? textColor(fill) : "currentColor" }
            }, [label])
          ]);
        const diagram = group => {
          const width = Math.max(group.tools.length, group.slots.length) * step;
          const toolX = i => (width - group.tools.length * step) / 2 + step / 2 + i * step;
          const slotX = n => (width - group.slots.length * step) / 2 + step / 2 + group.slots.indexOf(n) * step;
          const ring = n => (n === this.loadedSlot ? "#2196f3" : n === this.selected ? "currentColor" : null);
          return h("svg", {
            key: group.slots[0],
            staticClass: "rounded-lg",
            attrs: { viewBox: `0 0 ${width + 8} 104`, width: width + 8, height: 104 },
            style: { background: this.$vuetify.theme.dark ? "rgba(255,255,255,0.05)" : "rgba(0,0,0,0.04)" }
          }, [
            h("g", { attrs: { transform: "translate(4 2)" } }, [
              ...group.tools.map((entry, i) => {
                const s = this.slots[entry.slot];
                const active = entry.slot === this.loadedSlot;
                const [x1, x2] = [toolX(i), slotX(entry.slot)];
                return h("path", {
                  attrs: {
                    d: `M${x1} 22 C${x1} 50 ${x2} 50 ${x2} 78`, fill: "none", "stroke-width": active ? 3 : 2,
                    stroke: active ? "#2196f3" : s.present && isColor(s.color) ? s.color : "rgba(128,128,128,0.8)"
                  }
                });
              }),
              ...group.tools.map((entry, i) =>
                chip(toolX(i), 4, "T" + entry.tool, entry.slot === this.loadedSlot ? "#2196f3" : "rgba(128,128,128,0.25)", null, () =>
                  this.mappingLocked ? (this.selected = entry.slot) : this.openMapping())
              ),
              ...group.slots.map(n => {
                const s = this.slots[n];
                return chip(slotX(n), 78, s.label, s.present && isColor(s.color) ? s.color : "rgba(128,128,128,0.15)", ring(n), () => (this.selected = n));
              })
            ])
          ]);
        };
        return h("div", { staticClass: "text-center pt-2" }, [
          h("div", { staticClass: "d-flex flex-wrap justify-center", style: { gap: "12px" } }, groups.map(diagram)),
          h("div", { staticClass: "d-flex align-center justify-center mt-1", style: { gap: "8px" } }, [
            h("span", { staticClass: "text-caption text--disabled" }, ["Tool mapping"]),
            h(Oe, { props: { xSmall: true, text: true, disabled: this.mappingLocked }, on: { click: this.openMapping } }, [
              h(x, { attrs: { xSmall: true, left: true } }, ["$pencil"]),
              "Edit"
            ])
          ])
        ]);
      },
      openMapping() {
        if (this.mappingLocked) return;
        const draft = {};
        this.toolMap.forEach(entry => (draft[entry.tool] = entry.slot));
        this.mapping = draft;
      },
      // Writes only changed tools, in the format Fluidd's print dialog uses.
      saveMapping() {
        const draft = this.mapping;
        if (!draft || this.mappingLocked) return;
        const current = {};
        this.toolMap.forEach(entry => (current[entry.tool] = entry.slot));
        const lines = Object.keys(draft)
          .map(Number)
          .filter(tool => draft[tool] !== undefined && draft[tool] !== current[tool] && this.slots[draft[tool]])
          .map(tool => `SAVE_VARIABLE VARIABLE=value_t${tool} VALUE="'slot${draft[tool]}'"`);
        if (lines.length) I.printerGcodeScript(lines.join("\n"));
        this.mapping = null;
      },
      renderMappingEditor(h) {
        const draft = this.mapping;
        if (!draft) return null;
        const items = [...this.slotNumbers, EXTERNAL].map(n => {
          const s = this.slots[n];
          return { value: n, text: s.label + " · " + (s.present ? s.name || "Unknown filament" : "Empty"), color: s.present ? s.color : null };
        });
        const swatch = color =>
          h("span", {
            staticClass: "mr-2 flex-shrink-0",
            style: {
              width: "14px", height: "14px", borderRadius: "50%", display: "inline-block",
              background: isColor(color) ? color : "transparent", border: "1px solid rgba(128,128,128,0.6)"
            }
          });
        const option = ({ item }) => h("span", { staticClass: "d-flex align-center text-truncate" }, [swatch(item.color), item.text]);
        const rows = Array.from({ length: this.toolCount }, (_, tool) =>
          h("div", { key: tool, staticClass: "d-flex align-center", style: { gap: "8px" } }, [
            h("span", { staticClass: "font-weight-bold text-right", style: { minWidth: "32px" } }, ["T" + tool]),
            h(Ie, {
              props: {
                items, value: draft[tool], placeholder: "Not mapped", outlined: true, dense: true, hideDetails: true,
                menuProps: { offsetY: true }
              },
              scopedSlots: { item: option, selection: option },
              on: { change: slot => (this.mapping = { ...this.mapping, [tool]: slot }) }
            })
          ])
        );
        const identity = () => {
          const next = { ...this.mapping };
          for (let tool = 0; tool < Math.min(16, this.boxCount * 4); tool++) next[tool] = tool;
          this.mapping = next;
        };
        return h(Fb, { props: { value: true, maxWidth: 620, scrollable: true }, on: { input: value => value || (this.mapping = null) } }, [
          h(De, [
            h(lr, ["Tool mapping"]),
            h(xe, [
              h("div", { staticClass: "text-body-2 text--secondary mb-3" }, [
                "Choose the slot each tool loads, for tool changes and prints that do not set their own mapping. " +
                  "Fluidd's print dialog sets the mapping again for the print it starts, and a normal print end " +
                  "restores T0 → 1A, T1 → 1B, and so on."
              ]),
              h("div", { style: { display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(250px, 1fr))", gap: "8px 16px" } }, rows)
            ]),
            h("div", { staticClass: "d-flex align-center pa-2" }, [
              h(Oe, { props: { text: true }, on: { click: identity } }, ["Default"]),
              h("span", { staticClass: "flex-grow-1" }),
              h(Oe, { props: { text: true }, on: { click: () => (this.mapping = null) } }, ["Cancel"]),
              h(Oe, { props: { color: "primary", disabled: this.mappingLocked }, on: { click: this.saveMapping } }, ["Save"])
            ])
          ])
        ]);
      },
      renderEditor(h) {
        const d = this.draft;
        if (!d) return null;
        const vendors = Array.from(new Set(this.catalog.map(f => f.vendor)));
        const filaments = this.catalog.filter(f => f.vendor === d.vendor).map(f => ({ text: f.name, value: f.id }));
        const swatch = color =>
          h("div", {
            key: color,
            style: {
              width: "28px", height: "28px", borderRadius: "50%", background: color, cursor: "pointer",
              border: d.color === color.toUpperCase() ? "3px solid #2196f3" : "1px solid rgba(128,128,128,0.6)"
            },
            on: { click: () => (this.draft = { ...d, color: color.toUpperCase() }) }
          });
        return h(Fb, { props: { value: this.editing, maxWidth: 420 }, on: { input: value => (this.editing = value) } }, [
          h(De, [
            h(lr, ["Edit slot " + slotLabel(d.n)]),
            h(xe, [
              h(Ie, {
                staticClass: "mb-3",
                props: { label: "Vendor", items: vendors, value: d.vendor, outlined: true, dense: true, hideDetails: true },
                on: {
                  change: vendor => {
                    const now = this.catalog.find(f => f.id === d.id);
                    const same = this.catalog.filter(f => f.vendor === vendor);
                    const next = (now && same.find(f => f.type === now.type)) || same[0];
                    this.draft = { ...d, vendor, id: next ? next.id : null };
                  }
                }
              }),
              h(Ie, {
                staticClass: "mb-3",
                props: { label: "Filament", items: filaments, value: d.id, outlined: true, dense: true, hideDetails: true },
                on: { change: id => (this.draft = { ...d, id }) }
              }),
              h("div", { staticClass: "text-caption text--secondary mb-1" }, ["Color"]),
              h("div", { staticClass: "d-flex flex-wrap align-center", style: { gap: "6px" } }, [
                ...this.palette.map(swatch),
                h("input", {
                  attrs: { type: "color", value: d.color || "#FFFFFF", title: "Custom color" },
                  style: { width: "32px", height: "32px", border: "none", background: "none", cursor: "pointer" },
                  on: { input: event => (this.draft = { ...d, color: event.target.value.toUpperCase() }) }
                })
              ])
            ]),
            h("div", { staticClass: "d-flex justify-end pa-2" }, [
              h(Oe, { props: { text: true }, on: { click: () => (this.editing = false) } }, ["Cancel"]),
              h(Oe, { props: { color: "primary", disabled: this.busy || !d.id }, on: { click: this.saveEditor } }, ["Save"])
            ])
          ])
        ]);
      },
      renderBody(h) {
        if (this.view === "settings") {
          return h(Wle, { props: { value: true }, on: { input: value => value || (this.view = null) } });
        }
        if (this.failed) return h("div", { staticClass: "pa-4 text--secondary" }, ["QidiBox card unavailable; use the Box card."]);
        return h("div", { staticClass: "pa-3" }, [
          this.renderUnits(h),
          h("div", { staticClass: "d-flex flex-wrap mt-3", style: { gap: "8px" } }, [
            h("div", { staticClass: "d-flex flex-column align-center", style: { flex: "1 1 200px" } }, [
              h("div", { staticClass: "text-caption text--secondary mb-1" }, [this.statusText()]),
              this.renderPath(h)
            ]),
            h("div", { style: { flex: "1 1 280px" } }, [
              this.renderSummary(h),
              h(F),
              this.renderControls(h)
            ])
          ]),
          h(F, { staticClass: "mt-2" }),
          this.renderToolMap(h),
          this.editing ? this.renderEditor(h) : null,
          this.mapping ? this.renderMappingEditor(h) : null
        ]);
      }
    },
    render(h) {
      return h(
        Xe,
        {
          attrs: { title: "QidiBox", icon: "$box", draggable: true, "layout-path": "dashboard.tltg-qidi-box-card" },
          scopedSlots: {
            menu: () => [
              h(R, {
                staticClass: "ms-1 my-1",
                attrs: { small: true },
                on: { click: () => (this.view = this.view === "settings" ? null : "settings") }
              }, [h(x, { staticClass: "mr-1", attrs: { small: true } }, [this.view === "settings" ? "$close" : "$cog"]), this.view === "settings" ? "Close" : "Box settings"])
            ]
          }
        },
        [this.renderBody(h)]
      );
    }
  };
})();
