# QIDI Box MCU chip temperature sensors for QIDI Max 4 Optimized.
#
# Adds `temperature_sensor BoxN_MCU`, the Box processor's own temperature, for
# every Box MCU Klipper is configured with, so Fluidd and the Box link monitor
# show it. QIDI regenerates the Box sections for however many Boxes it detects,
# so the sensors follow the configured `mcu mcu_boxN` objects instead of a
# fixed config section. No temperature limits are set, so these sensors never
# shut a Box down.

import configparser
import re

import configfile
from . import temperature_sensor

BOX_MCU_NAME = re.compile(r"^mcu (mcu_box(\d+))$")


def sensor_name(box_number):
    return "temperature_sensor Box%d_MCU" % (box_number,)


class BoxMcuTemperature:
    def __init__(self, config):
        printer = config.get_printer()
        # MCU objects are created before any other section loads, so every
        # configured Box MCU is visible here. Shared modules are loaded from the
        # real config because this file is included before printer.cfg's own
        # sensors.
        for module in ("heaters", "query_adc", "error_mcu"):
            printer.load_object(config, module)
        boxes = []
        for name, _mcu in printer.lookup_objects("mcu"):
            match = BOX_MCU_NAME.match(name)
            if match is not None:
                boxes.append((int(match.group(2)), match.group(1)))
        for box_number, mcu_name in sorted(boxes):
            section = sensor_name(box_number)
            fileconfig = configparser.RawConfigParser()
            fileconfig.add_section(section)
            fileconfig.set(section, "sensor_type", "temperature_mcu")
            fileconfig.set(section, "sensor_mcu", mcu_name)
            sensor_config = configfile.ConfigWrapper(
                printer, fileconfig, {}, section)
            printer.add_object(
                section, temperature_sensor.load_config_prefix(sensor_config))


def load_config(config):
    return BoxMcuTemperature(config)
