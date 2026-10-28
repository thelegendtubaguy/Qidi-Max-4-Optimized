from __future__ import annotations

from .errors import InstallerError


OPERATION = "klipper_print_stats_manager_shutdown_reason"

RESET_HANDLER_STOCK = (
    "    def _handle_reset_stats(self):",
    '        logging.info("检查到！！错误，恢复默认状态！！")',
    "        self.set_main_status('ready') ",
)
# QIDI resets the status on every gcode:command_error. Leaving `printing` runs SET_TMC_FIELD, which Klipper refuses
# after a shutdown, so the refusal re-enters the handler until klippy dies and restarts into a bare MCU shutdown,
# hiding the original shutdown reason. A failing SET_TMC_FIELD re-enters the same way while Klipper is ready.
RESET_HANDLER_PATCHED = (
    "    def _handle_reset_stats(self):",
    "        # tltg-optimized: keep the shutdown reason; skip resets after shutdown and from within a reset",
    "        if self.printer.is_shutdown() or getattr(self, '_tltg_resetting', False):",
    "            return",
    '        logging.info("检查到！！错误，恢复默认状态！！")',
    "        self._tltg_resetting = True",
    "        try:",
    "            self.set_main_status('ready')",
    "        finally:",
    "            self._tltg_resetting = False",
)


class KlipperPrintStatsManagerError(InstallerError):
    pass


def patch_print_stats_manager(text: str) -> str:
    newline = "\r\n" if "\r\n" in text else "\n"
    stock = newline.join(RESET_HANDLER_STOCK) + newline
    patched = newline.join(RESET_HANDLER_PATCHED) + newline
    registration = 'self.printer.register_event_handler("gcode:command_error", self._handle_reset_stats)'
    if text.count(patched) == 1 and text.count(stock) == 0:
        return text
    if text.count(stock) == 1 and text.count(registration) == 1 and "class PrintStatusManager:" in text:
        result = text.replace(stock, patched, 1)
        compile(result, "print_stats_manager.py", "exec")
        return result
    raise KlipperPrintStatsManagerError("Klipper print_stats_manager.py does not match the reviewed QIDI source; preserving it.")
