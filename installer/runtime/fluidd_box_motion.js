// QIDI Box load/unload motion section, rendered at the end of the Box Config view of QIDI's bundled
// Fluidd v1.30.5 (/home/qidi/fluidd/assets/index-DlFvHGAh.js). fluidd_box_filaments.py inserts this file
// verbatim into the bundle's module scope, so it may use that bundle's minified Vuetify components:
// F VDivider, xe VCardText, Oe VBtn, ce VTextField, Y VRow, k VCol. Do not declare local names
// that shadow them. The section reads printer.tltg_box_feed_motion and edits only through TLTG_BOX_MOTION.
const TltgBoxMotion = (() => {
  const FIELDS = [
    ["fast_length", "Fast length", v => v.fast_length],
    ["fast_speed_1", "Fast speed 1", v => v.fast_speed_1],
    ["fast_speed_2", "Fast speed 2", v => v.fast_speed_2],
    ["approach_speed", "Approach speed", v => v.approach_speed],
    ["load_accel", "Load accel", v => v.load_accel],
    ["unload_speed_1", "Unload speed 1", v => v.unload_speed_1],
    ["unload_speed_2", "Unload speed 2", v => v.unload_speed_2],
    ["unload_accel", "Unload accel", v => v.unload_accel],
    ["unload_extruder_length", "Extruder retract", v => v.unload_extruder_length]
  ];
  // Settings that apply to every slot and have no per-slot override.
  const GLOBAL_ONLY = ["unload_extruder_length"];
  const fieldsFor = scope => FIELDS.filter(([key]) => scope === "global" || !GLOBAL_ONLY.includes(key));
  const UNAVAILABLE = "Box motion settings unavailable";
  const isSet = value => value !== null && value !== undefined;
  const slotNumber = key => {
    const match = /^slot(\d+)$/.exec(key);
    return match ? parseInt(match[1], 10) : null;
  };
  // Same labels as the Box card: Box 1 slots are 1A-1D, Box 2 slots 2A-2D, and so on.
  const slotLabel = n => Math.floor(n / 4) + 1 + String.fromCharCode((n % 4) + 65);

  return {
    name: "TltgBoxMotion",
    data: () => ({ open: null, drafts: {}, errors: {}, pending: false, failed: false }),
    computed: {
      motion() {
        const value = this.$store.state.printer.printer.tltg_box_feed_motion;
        return value && typeof value === "object" ? value : null;
      },
      active() {
        const s = this.motion;
        return !!(s && s.active && s.settings && s.vendor && s.limits);
      },
      slotKeys() {
        const slots = (this.motion && this.motion.slots) || {};
        return Object.keys(slots)
          .filter(key => slotNumber(key) !== null && slots[key])
          .sort((a, b) => slotNumber(a) - slotNumber(b));
      },
      printing() {
        const stats = this.$store.state.printer.printer.print_stats;
        const state = String((stats && stats.state) || "").toLowerCase();
        return state === "printing" || state === "paused";
      },
      // Live subscribed status only: Fluidd's cached server info and QIDI's Box flags can lag behind.
      klippyReady() {
        const webhooks = this.$store.state.printer.printer.webhooks;
        return !webhooks || !webhooks.state || webhooks.state === "ready";
      },
      locked() {
        return this.pending || this.printing || !this.klippyReady;
      }
    },
    errorCaptured(error) {
      console.error("[tltg] Box motion section failed", error);
      this.failed = true;
      return false;
    },
    methods: {
      limitText(key) {
        const limit = this.motion.limits[key];
        return limit ? limit.min + "–" + limit.max + " " + (limit.unit || "") : "";
      },
      invalid(key, raw) {
        const value = String(isSet(raw) ? raw : "").trim();
        const limit = this.motion.limits[key];
        if (value === "" || !limit) return false;
        const number = Number(value);
        return !/^\d+$/.test(value) || number < limit.min || number > limit.max;
      },
      // Status publishes an unusable saved value as its repr string, or as an out-of-range number.
      badSaved(key, value) {
        return isSet(value) && (typeof value !== "number" || this.invalid(key, value));
      },
      // Changed parameters only; a cleared field, or an untouched unusable saved value, is unset with the scope's clear word.
      changes(scope) {
        const drafts = this.drafts[scope] || {};
        const current = scope === "global" ? this.motion.settings : (this.motion.slots[scope] || {}).overrides || {};
        const clear = scope === "global" ? "vendor" : "global";
        const params = [];
        let invalid = false;
        for (const [key] of fieldsFor(scope)) {
          if (!(key in drafts)) {
            this.badSaved(key, current[key]) && params.push(key.toUpperCase() + "=" + clear);
            continue;
          }
          const value = String(isSet(drafts[key]) ? drafts[key] : "").trim();
          if (this.invalid(key, value)) invalid = true;
          else if (value === "") isSet(current[key]) && params.push(key.toUpperCase() + "=" + clear);
          else if (Number(value) !== current[key]) params.push(key.toUpperCase() + "=" + Number(value));
        }
        return invalid ? null : params;
      },
      setDraft(scope, key, value) {
        this.$set(this.drafts, scope, { ...(this.drafts[scope] || {}), [key]: value });
      },
      clearScope(scope) {
        this.$delete(this.drafts, scope);
        this.$delete(this.errors, scope);
      },
      async confirm(message) {
        if (typeof this.$confirm === "function") {
          return await this.$confirm(message, { title: "Load/unload motion", color: "card-heading", icon: "$error" });
        }
        return window.confirm(message);
      },
      // HTTP returns a refused command's reason, which the websocket helper only sends to the console.
      async run(scope, script, message) {
        if (this.locked || (message && !(await this.confirm(message)))) return;
        this.pending = true;
        this.$delete(this.errors, scope);
        try {
          await this.$httpClient.post("/printer/gcode/script", { script });
          this.$delete(this.drafts, scope);
        } catch (error) {
          const data = error && error.response && error.response.data;
          const reason = data && data.error && data.error.message;
          this.$set(this.errors, scope, reason || (error && error.message) || String(error));
        } finally {
          this.pending = false;
        }
      },
      apply(scope) {
        const params = this.changes(scope);
        if (!params || !params.length) return;
        const target = scope === "global" ? "" : " SLOT=" + slotNumber(scope);
        this.run(scope, "TLTG_BOX_MOTION" + target + " " + params.join(" "));
      },
      toggle(key) {
        if (this.open) this.clearScope(this.open);
        this.open = this.open === key ? null : key;
      },

      renderFields(h, scope, values, placeholder) {
        const drafts = this.drafts[scope] || {};
        return h(Y, { props: { dense: true } }, fieldsFor(scope).map(([key, label]) => {
          const saved = values[key];
          const bad = !(key in drafts) && this.badSaved(key, saved);
          const value = key in drafts ? drafts[key] : isSet(saved) && !bad ? String(saved) : "";
          return h(k, { key, props: { cols: 6, sm: 3 } }, [
            h(ce, {
              props: {
                value,
                label,
                placeholder: String(placeholder(key)),
                persistentPlaceholder: true,
                hint: this.limitText(key),
                rules: [v => !this.invalid(key, v) || "Whole number " + this.limitText(key)],
                type: "number",
                outlined: true,
                dense: true,
                hideDetails: "auto",
                errorMessages: bad ? "Saved value " + saved + " is invalid; Apply clears it" : undefined,
                disabled: this.locked
              },
              on: { input: v => this.setDraft(scope, key, v) }
            })
          ]);
        }));
      },
      renderButton(h, label, click, options) {
        const opts = options || {};
        return h(Oe, {
          staticClass: "ml-2",
          props: { small: true, text: !opts.primary, color: opts.primary ? "primary" : undefined, disabled: this.locked || !!opts.disabled },
          on: { click }
        }, [label]);
      },
      renderActions(h, scope, buttons) {
        const params = this.changes(scope);
        const error = this.errors[scope];
        return [
          error ? h("div", { staticClass: "error--text text-body-2 mt-1", attrs: { role: "alert" } }, [error]) : null,
          h("div", { staticClass: "d-flex flex-wrap justify-end mt-1" }, [
            ...buttons,
            this.renderButton(h, "Apply", () => this.apply(scope), { primary: true, disabled: !params || !params.length })
          ])
        ];
      },
      renderValue(h, text, overridden) {
        return overridden
          ? h("span", { staticClass: "primary--text font-weight-bold", attrs: { title: "Slot override" } }, [text + "*"])
          : h("span", [text]);
      },
      renderSlot(h, key) {
        const slot = this.motion.slots[key];
        const overrides = slot.overrides || {};
        const load = slot.load || {};
        const unload = slot.unload || {};
        const n = slotNumber(key);
        const v = (value, setting) => this.renderValue(h, isSet(value) ? String(value) : "?", isSet(overrides[setting]));
        const errors = [["Load", load], ["Unload", unload]].filter(([, p]) => p.state === "error" && p.error);
        const isOpen = this.open === key;
        const globals = this.motion.settings;
        const vendor = this.motion.vendor;
        return h("div", { key, staticClass: "py-2" }, [
          h("div", { staticClass: "d-flex align-center flex-wrap" }, [
            h("span", { staticClass: "font-weight-bold mr-1", style: { minWidth: "2em" } }, [slotLabel(n)]),
            h("span", { staticClass: "flex-grow-1" }),
            h(Oe, { props: { xSmall: true, text: true }, on: { click: () => this.toggle(key) } }, [isOpen ? "Close" : "Edit"])
          ]),
          h("div", { staticClass: "text-body-2" }, [
            "Load ", v(load.fast_length, "fast_length"), " mm @ ", v(load.fast_speed_1, "fast_speed_1"), "/",
            v(load.fast_speed_2, "fast_speed_2"), " → ", v(load.approach_speed, "approach_speed"),
            " mm/s, accel ", v(load.accel, "load_accel"), "; unload ", v(unload.speed_1, "unload_speed_1"), "/",
            v(unload.speed_2, "unload_speed_2"), " mm/s, accel ", v(unload.accel, "unload_accel")
          ]),
          ...errors.map(([label, p]) => h("div", { staticClass: "error--text text-caption" }, [label + ": " + p.error])),
          isOpen
            ? h("div", { staticClass: "mt-2" }, [
                h("div", { staticClass: "text-caption text--secondary mb-2" }, ["Blank fields follow the global setting."]),
                this.renderFields(h, key, overrides, setting => {
                  if (isSet(globals[setting]) && !this.badSaved(setting, globals[setting])) return globals[setting];
                  const field = FIELDS.find(([name]) => name === setting);
                  return field[2](vendor);
                }),
                ...this.renderActions(h, key, [
                  this.renderButton(h, "Reset slot", () =>
                    this.run(key, "TLTG_BOX_MOTION SLOT=" + n + " RESET=1", "Clear every override for slot " + slotLabel(n) + "?"))
                ])
              ])
            : null
        ]);
      },
      renderBody(h) {
        const s = this.motion;
        const title = h("div", { staticClass: "text-subtitle-1" }, ["Load/unload motion"]);
        if (this.failed || !this.active) {
          const text = this.failed ? UNAVAILABLE : (s && s.status) || UNAVAILABLE;
          return [title, h("div", { staticClass: "text-body-2 text--secondary" }, [text])];
        }
        const notes = [...(s.problems || [])];
        if (s.vendor_keys && s.vendor_keys.length) notes.push("Vendor motion keys change the baseline: " + s.vendor_keys.join(", "));
        return [
          title,
          ...notes.map(note => h("div", { staticClass: "warning--text text-caption" }, [note])),
          this.locked && !this.pending
            ? h("div", { staticClass: "text-caption text--secondary" }, ["Editing is unavailable while printing."])
            : null,
          h("div", { staticClass: "text-caption text--secondary mt-2 mb-2" }, ["All slots. Blank fields use the vendor value."]),
          this.renderFields(h, "global", s.settings, key => FIELDS.find(([name]) => name === key)[2](s.vendor)),
          ...this.renderActions(h, "global", [
            this.renderButton(h, "Reset", () =>
              this.run("global", "TLTG_BOX_MOTION RESET=1", "Reset all Box motion settings and every slot override to vendor values?"))
          ]),
          h(F, { staticClass: "mt-2" }),
          ...this.slotKeys.map((key, i) => [i ? h(F) : null, this.renderSlot(h, key)]).flat()
        ];
      }
    },
    render(h) {
      let body;
      try {
        body = this.renderBody(h);
      } catch (error) {
        console.error("[tltg] Box motion section failed", error);
        body = [h("div", { staticClass: "text-body-2 text--secondary" }, [UNAVAILABLE])];
      }
      return h("div", { staticClass: "tltg-box-motion" }, [h(F), h(xe, { staticClass: "pt-3" }, body)]);
    }
  };
})();
