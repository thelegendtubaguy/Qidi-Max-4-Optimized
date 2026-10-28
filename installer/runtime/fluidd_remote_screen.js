// Printer screen dashboard card for QIDI's bundled Fluidd v1.30.5 (/home/qidi/fluidd/assets/index-DlFvHGAh.js).
// fluidd_box_filaments.py inserts this file verbatim into the bundle's module scope just before the Dashboard view
// registers its cards, so it may use that bundle's minified names: Xe CollapsableCard, R AppBtn, x VIcon,
// rt Moonraker HTTP actions. Do not declare local names that shadow them. The card talks only to the package's
// screen service through nginx at /tltg-screen/ws, and only while it is expanded in a visible tab.
const TltgScreenCard = (() => {
  const RETRY_DELAYS = [1000, 2000, 5000, 10000];
  const MOVE_INTERVAL = 30;
  const CONFIRM_CONTROL =
    "Clicks, taps, and drags on the image will press the printer's touchscreen, including during a print. " +
    "Turn control on?";

  const View = {
    name: "TltgScreenView",
    props: { control: Boolean },
    data: () => ({
      state: "connecting",
      message: "",
      width: 800,
      height: 480,
      touch: false,
      hasFrame: false,
      fullscreen: false
    }),
    computed: {
      canControl() {
        return this.control && this.touch && this.state === "live";
      }
    },
    watch: {
      control(value) {
        value || this.release();
      },
      touch(value) {
        this.$emit("touch", value);
      }
    },
    created() {
      this.socket = null;
      this.connecting = false;
      this.retry = 0;
      this.timer = null;
      this.closed = false;
      this.pointer = null;
      this.lastMove = 0;
      this.pendingMove = null;
      this.decoding = false;
      this.nextFrame = null;
    },
    mounted() {
      document.addEventListener("visibilitychange", this.onVisibility);
      document.addEventListener("fullscreenchange", this.onFullscreen);
      // Cards render expanded until Fluidd loads the saved layout; a card collapsed there never connects.
      this.timer = setTimeout(() => this.connect(), 250);
    },
    beforeDestroy() {
      this.closed = true;
      document.removeEventListener("visibilitychange", this.onVisibility);
      document.removeEventListener("fullscreenchange", this.onFullscreen);
      this.disconnect();
    },
    methods: {
      // The service only accepts same-origin connections, so connect through the nginx serving this page.
      socketUrl(token) {
        const url = new URL("tltg-screen/ws", window.location.origin + "/");
        url.protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
        if (token) url.search = "?token=" + encodeURIComponent(token);
        return url.toString();
      },
      async connect() {
        if (this.closed || document.hidden || this.socket || this.connecting) return;
        clearTimeout(this.timer);
        this.connecting = true;
        let token = "";
        try {
          // A one-shot token proves this Fluidd session when Moonraker requires logins.
          const response = await rt.accessOneshotTokenGet();
          token = (response && response.data && response.data.result) || "";
        } catch (error) {
          token = "";
        }
        this.connecting = false;
        if (this.closed || document.hidden || this.socket) return;
        const socket = new WebSocket(this.socketUrl(token));
        socket.binaryType = "blob";
        socket.onmessage = event => this.onMessage(socket, event);
        socket.onclose = () => this.onClose(socket);
        this.socket = socket;
      },
      disconnect() {
        clearTimeout(this.timer);
        this.timer = null;
        const socket = this.socket;
        this.socket = null;
        this.pointer = null;
        if (socket) {
          socket.onmessage = null;
          socket.onclose = null;
          socket.close();
        }
      },
      onVisibility() {
        if (document.hidden) {
          this.disconnect();
          this.state = "paused";
        } else {
          this.connect();
        }
      },
      onFullscreen() {
        this.fullscreen = document.fullscreenElement === this.$el;
      },
      onMessage(socket, event) {
        if (socket !== this.socket) return;
        if (typeof event.data !== "string") {
          this.draw(event.data);
          return;
        }
        let message;
        try {
          message = JSON.parse(event.data);
        } catch (error) {
          return;
        }
        if (message.type === "hello") {
          this.state = "live";
          this.message = message.touch ? "" : message.touch_error || "touch input unavailable";
          this.width = message.width;
          this.height = message.height;
          this.touch = !!message.touch;
          this.retry = 0;
        } else if (message.type === "error") {
          this.state = "error";
          this.message = message.message;
        }
      },
      onClose(socket) {
        if (socket !== this.socket) return;
        this.socket = null;
        this.pointer = null;
        if (this.closed) return;
        if (this.state !== "error") {
          this.state = "disconnected";
          this.message = "";
        }
        const delay = RETRY_DELAYS[Math.min(this.retry, RETRY_DELAYS.length - 1)];
        this.retry++;
        this.timer = setTimeout(() => this.connect(), delay);
      },
      // Frames that arrive while one is decoding are skipped in favor of the newest.
      draw(blob) {
        if (this.decoding) {
          this.nextFrame = blob;
          return;
        }
        this.decoding = true;
        createImageBitmap(blob)
          .then(bitmap => {
            const canvas = this.$refs.canvas;
            if (canvas) {
              if (canvas.width !== bitmap.width) canvas.width = bitmap.width;
              if (canvas.height !== bitmap.height) canvas.height = bitmap.height;
              canvas.getContext("2d").drawImage(bitmap, 0, 0);
              this.hasFrame = true;
            }
            bitmap.close && bitmap.close();
          })
          .catch(() => {})
          .then(() => {
            this.decoding = false;
            const next = this.nextFrame;
            this.nextFrame = null;
            next && !this.closed && this.draw(next);
          });
      },
      // The canvas letterboxes the screen in full screen, so map through the fitted image.
      position(event) {
        const rect = this.$refs.canvas.getBoundingClientRect();
        const scale = Math.min(rect.width / this.width, rect.height / this.height);
        const left = rect.left + (rect.width - this.width * scale) / 2;
        const top = rect.top + (rect.height - this.height * scale) / 2;
        const clamp = (value, size) => Math.max(0, Math.min(size - 1, Math.round(value)));
        return {
          x: clamp((event.clientX - left) / scale, this.width),
          y: clamp((event.clientY - top) / scale, this.height)
        };
      },
      send(action, point) {
        const socket = this.socket;
        if (socket && socket.readyState === WebSocket.OPEN) {
          socket.send(JSON.stringify({ type: "touch", action, x: point.x, y: point.y }));
        }
      },
      release() {
        if (this.pointer === null) return;
        this.pointer = null;
        this.pendingMove = null;
        this.send("up", { x: 0, y: 0 });
      },
      onPointerDown(event) {
        if (!this.canControl || this.pointer !== null || event.button !== 0) return;
        event.preventDefault();
        this.pointer = event.pointerId;
        this.$refs.canvas.setPointerCapture && this.$refs.canvas.setPointerCapture(event.pointerId);
        this.lastMove = performance.now();
        this.send("down", this.position(event));
      },
      onPointerMove(event) {
        if (event.pointerId !== this.pointer) return;
        event.preventDefault();
        const point = this.position(event);
        const now = performance.now();
        if (now - this.lastMove >= MOVE_INTERVAL) {
          this.lastMove = now;
          this.pendingMove = null;
          this.send("move", point);
        } else {
          this.pendingMove = point;
        }
      },
      onPointerUp(event) {
        if (event.pointerId !== this.pointer) return;
        event.preventDefault();
        this.send("move", this.position(event));
        this.release();
      },
      onPointerCancel(event) {
        event.pointerId === this.pointer && this.release();
      },
      statusText() {
        if (this.state === "error") return "Printer screen unavailable: " + this.message;
        if (this.state === "disconnected") return "Printer screen disconnected. Reconnecting…";
        if (this.state === "paused") return "Paused while this tab is hidden.";
        if (!this.hasFrame) return "Connecting to the printer screen…";
        return "";
      }
    },
    render(h) {
      const status = this.statusText();
      const canvasStyle = this.fullscreen
        ? { width: "100%", height: "100%", objectFit: "contain" }
        : { width: "100%", height: "auto" };
      return h(
        "div",
        {
          style: {
            position: "relative",
            background: "#000",
            lineHeight: 0,
            ...(this.fullscreen ? { display: "flex", alignItems: "center", justifyContent: "center" } : {})
          }
        },
        [
          h("canvas", {
            ref: "canvas",
            attrs: { width: this.width, height: this.height },
            style: {
              ...canvasStyle,
              display: "block",
              touchAction: this.canControl ? "none" : "auto",
              cursor: this.canControl ? "pointer" : "default",
              opacity: this.hasFrame && this.state === "live" ? 1 : 0.4
            },
            on: {
              pointerdown: this.onPointerDown,
              pointermove: this.onPointerMove,
              pointerup: this.onPointerUp,
              pointercancel: this.onPointerCancel,
              lostpointercapture: this.onPointerCancel,
              contextmenu: event => this.canControl && event.preventDefault()
            }
          }),
          status
            ? h(
                "div",
                {
                  style: {
                    position: "absolute",
                    inset: 0,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    padding: "16px",
                    color: "#fff",
                    textAlign: "center",
                    lineHeight: 1.4,
                    pointerEvents: "none"
                  }
                },
                status
              )
            : null,
          this.state === "live" && this.message && !status
            ? h(
                "div",
                {
                  style: {
                    position: "absolute",
                    left: 0,
                    right: 0,
                    bottom: 0,
                    padding: "4px 8px",
                    background: "rgba(0,0,0,0.6)",
                    color: "#fff",
                    lineHeight: 1.4,
                    fontSize: "12px",
                    pointerEvents: "none"
                  }
                },
                "View only: " + this.message
              )
            : null
        ]
      );
    }
  };

  return {
    name: "TltgScreenCard",
    data: () => ({ collapsed: true, control: false, touch: false }),
    errorCaptured(error) {
      console.error("[tltg] Printer screen card failed", error);
      return false;
    },
    methods: {
      async toggleControl() {
        if (this.control) {
          this.control = false;
          return;
        }
        const confirmed = await this.$confirm(CONFIRM_CONTROL, {
          title: "Control the printer screen",
          color: "card-heading",
          icon: "$error"
        });
        // The card may have collapsed while the dialog was open.
        this.control = !!confirmed && !this.collapsed;
      },
      openFullscreen() {
        const view = this.$refs.view;
        view && view.$el.requestFullscreen && view.$el.requestFullscreen();
      },
      onCollapsed(value) {
        this.collapsed = value;
        if (value) {
          this.control = false;
          this.touch = false;
        }
      }
    },
    render(h) {
      const button = (label, icon, click, options) =>
        h(R, { staticClass: "ms-1 my-1", attrs: { small: true, disabled: !!(options && options.disabled) }, on: { click } }, [
          h(x, { staticClass: "mr-1", attrs: { small: true } }, [icon]),
          label
        ]);
      return h(
        Xe,
        {
          attrs: {
            title: "Printer screen",
            icon: "$screenshot",
            lazy: false,
            draggable: true,
            "layout-path": "dashboard.tltg-screen-card"
          },
          on: { collapsed: this.onCollapsed },
          scopedSlots: {
            menu: () =>
              this.collapsed
                ? []
                : [
                    button(this.control ? "Control on" : "View only", this.control ? "$lockOpen" : "$lock", this.toggleControl, {
                      disabled: !this.touch && !this.control
                    }),
                    button("Full screen", "$fullScreen", this.openFullscreen)
                  ]
          }
        },
        [
          this.collapsed
            ? null
            : h(View, {
                ref: "view",
                props: { control: this.control },
                on: { touch: value => (this.touch = value) }
              })
        ]
      );
    }
  };
})();
