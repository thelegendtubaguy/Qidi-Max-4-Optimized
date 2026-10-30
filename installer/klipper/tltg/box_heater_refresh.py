# QIDI Box heater refresh for QIDI Max 4 Optimized.
#
# Klipper resends a heater's unchanged output only every 3.75 s, against the
# 5 s limit after which the heater's MCU shuts down. A QIDI Box heater reads its
# AHT20 sensor from Klipper's main loop, so while that loop is busy (at print
# start and end it stalls for over two seconds) the heater gets no updates at
# all. A Box heater holding a steady output, such as full power while heating,
# can then run out its 5 s and the Box disconnects.
#
# This module makes each Box heater resend an unchanged output every second, so
# it survives stalls of about three seconds. Other heaters, and every heater
# limit and safety check, are unchanged.

import logging
import re

REFRESH_TIME = 1.0
BOX_HEATER_NAME = re.compile(r"^heater_box\d+$")


class BoxHeaterRefresh:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.printer.register_event_handler("klippy:connect", self._connect)

    def _connect(self):
        pheaters = self.printer.lookup_object("heaters")
        for name, heater in sorted(getattr(pheaters, "heaters", {}).items()):
            if not BOX_HEATER_NAME.match(name):
                continue
            if not all(hasattr(heater, attr) for attr in
                       ("set_pwm", "next_pwm_time", "pwm_delay")):
                logging.warning("tltg_box_heater_refresh: %s has an unexpected"
                                " heater layout; refresh left unchanged", name)
                continue
            heater.set_pwm = self._wrap(heater, heater.set_pwm)
            logging.info("tltg_box_heater_refresh: %s resends every %.1f s",
                         name, REFRESH_TIME)

    def _wrap(self, heater, set_pwm):
        def refreshing_set_pwm(read_time, value):
            previous = heater.next_pwm_time
            set_pwm(read_time, value)
            if heater.next_pwm_time != previous:
                # The value was just sent; resend it sooner if unchanged.
                heater.next_pwm_time = min(
                    heater.next_pwm_time,
                    read_time + heater.pwm_delay + REFRESH_TIME)
        return refreshing_set_pwm


def load_config(config):
    return BoxHeaterRefresh(config)
