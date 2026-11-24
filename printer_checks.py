import socket

from snmp import read_printer_details


def is_print_service_available(printer, timeout):
    # Проверяем порт печати: так видим не только сам принтер, но и службу печати.
    try:
        with socket.create_connection(
            (printer["ip"], int(printer["port"])), timeout=timeout
        ):
            return True
    except (OSError, ValueError):
        return False


def get_printer_details(printer):
    if not printer["snmp"]:
        return {
            "printer_status": None,
            "errors": [],
            "snmp_error": "SNMP отключён для этого принтера",
        }
    return read_printer_details(printer)
