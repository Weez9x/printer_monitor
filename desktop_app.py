import os
import threading
import time
from pathlib import Path

from database import add_printer, delete_printer, initialize_database, list_printers
from desktop_dashboard import start_desktop_dashboard
from printer_checks import get_printer_details, is_print_service_available


CHECK_INTERVAL = 30
TCP_TIMEOUT = 3
DASHBOARD_HOST = "127.0.0.1"
DASHBOARD_PORT = 8765
SNMP_COMMUNITY = os.environ.get("PRINTER_SNMP_COMMUNITY", "public")

states = {}
check_lock = threading.Lock()


def current_status():
    # Берём список из базы при каждом запросе, чтобы изменения сразу появлялись в панели.
    printers = list_printers()
    with check_lock:
        return {
            "printers": [
                {
                    **printer,
                    "online": states.get(printer["id"], {}).get("online"),
                    "checked_at": states.get(printer["id"], {}).get("checked_at"),
                    "printer_status": states.get(printer["id"], {}).get("printer_status"),
                    "errors": states.get(printer["id"], {}).get("errors", []),
                    "snmp_error": states.get(printer["id"], {}).get("snmp_error"),
                }
                for printer in printers
            ]
        }


def check_printers():
    with check_lock:
        for printer in list_printers():
            device = {
                "ip": printer["ip"],
                "port": printer["port"],
                "snmp": bool(printer["snmp_enabled"]),
                "snmp_port": printer["snmp_port"],
                "snmp_community": SNMP_COMMUNITY,
            }
            online = is_print_service_available(device, TCP_TIMEOUT)
            details = get_printer_details(device)
            states[printer["id"]] = {
                "online": online,
                "checked_at": time.time(),
                **details,
            }
    return current_status()


def monitor_loop():
    while True:
        try:
            check_printers()
        except Exception as error:
            print(f"Не удалось обновить состояние принтеров: {error}")
        time.sleep(CHECK_INTERVAL)


def main():
    initialize_database()
    start_desktop_dashboard(
        get_status=current_status,
        check_now=check_printers,
        add_printer=add_printer,
        delete_printer=delete_printer,
        host=DASHBOARD_HOST,
        port=DASHBOARD_PORT,
    )
    threading.Thread(target=monitor_loop, daemon=True).start()
    print(f"Панель открыта: http://{DASHBOARD_HOST}:{DASHBOARD_PORT}")
    print(f"База данных: {Path(__file__).resolve().with_name('printers.db')}")
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        print("\nПанель закрыта.")


if __name__ == "__main__":
    main()
