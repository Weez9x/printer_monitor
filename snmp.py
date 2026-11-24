import random
import socket


PRINTER_STATUS_OID = (1, 3, 6, 1, 2, 1, 25, 3, 5, 1, 1)
PRINTER_ERRORS_OID = (1, 3, 6, 1, 2, 1, 25, 3, 5, 1, 2)
STATUS_NAMES = {
    1: "другое",
    2: "неизвестно",
    3: "ожидает печати",
    4: "печатает",
    5: "прогревается",
}
ERROR_NAMES = (
    "мало бумаги",
    "бумага закончилась",
    "мало тонера",
    "тонер закончился",
    "открыта крышка",
    "замятие бумаги",
    "принтер выключен или отключён",
    "требуется обслуживание",
)


def encode_length(length):
    if length < 128:
        return bytes([length])
    encoded = length.to_bytes((length.bit_length() + 7) // 8, "big")
    return bytes([0x80 | len(encoded)]) + encoded


def tlv(tag, value):
    return bytes([tag]) + encode_length(len(value)) + value


def encode_integer(value):
    length = 1
    while not (-(1 << (8 * length - 1)) <= value < (1 << (8 * length - 1))):
        length += 1
    return tlv(0x02, value.to_bytes(length, "big", signed=True))


def encode_oid(oid):
    parts = [oid[0] * 40 + oid[1], *oid[2:]]
    output = bytearray()
    for part in parts:
        encoded = [part & 0x7F]
        part >>= 7
        while part:
            encoded.insert(0, 0x80 | (part & 0x7F))
            part >>= 7
        output.extend(encoded)
    return tlv(0x06, bytes(output))


def read_tlv(data, offset=0):
    tag = data[offset]
    offset += 1
    length = data[offset]
    offset += 1
    if length & 0x80:
        count = length & 0x7F
        length = int.from_bytes(data[offset:offset + count], "big")
        offset += count
    end = offset + length
    if end > len(data):
        raise ValueError("Обрезанный SNMP-ответ")
    return tag, data[offset:end], end


def children(data):
    result = []
    offset = 0
    while offset < len(data):
        tag, value, offset = read_tlv(data, offset)
        result.append((tag, value))
    return result


def decode_oid(data):
    values = []
    value = 0
    for byte in data:
        value = (value << 7) | (byte & 0x7F)
        if not byte & 0x80:
            values.append(value)
            value = 0
    if not values:
        raise ValueError("Некорректный OID в SNMP-ответе")
    first = values.pop(0)
    return (min(first // 40, 2), first - min(first // 40, 2) * 40, *values)


def get_next(ip, community, oid, port=161, timeout=1.5):
    # Для каждой метрики просим SNMP-агент вернуть ближайшее значение в таблице.
    request_id = random.randint(1, 2**31 - 1)
    varbind = tlv(0x30, encode_oid(oid) + tlv(0x05, b""))
    pdu = tlv(0xA1, encode_integer(request_id) + encode_integer(0) + encode_integer(0) + tlv(0x30, varbind))
    packet = tlv(0x30, encode_integer(0) + tlv(0x04, community.encode()) + pdu)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(timeout)
        sock.sendto(packet, (ip, int(port)))
        response, _ = sock.recvfrom(65535)
    _, outer, _ = read_tlv(response)
    message = children(outer)
    response_pdu = children(message[2][1])
    error_status = int.from_bytes(response_pdu[1][1], "big", signed=True)
    if error_status:
        raise RuntimeError(f"SNMP вернул код ошибки {error_status}")
    varbind_list = children(response_pdu[3][1])
    if not varbind_list:
        raise RuntimeError("Принтер не вернул SNMP-данные")
    binding = children(varbind_list[0][1])
    return decode_oid(binding[0][1]), binding[1]


def read_printer_details(printer):
    # Printer-MIB отдаёт состояние и битовую маску типичных ошибок устройства.
    community = printer.get("snmp_community", "public")
    port = printer.get("snmp_port", 161)
    try:
        status_oid, status_value = get_next(printer["ip"], community, PRINTER_STATUS_OID, port)
        errors_oid, errors_value = get_next(printer["ip"], community, PRINTER_ERRORS_OID, port)
        if status_oid[:len(PRINTER_STATUS_OID)] != PRINTER_STATUS_OID:
            raise RuntimeError("SNMP-агент не сообщил состояние принтера")
        if errors_oid[:len(PRINTER_ERRORS_OID)] != PRINTER_ERRORS_OID:
            raise RuntimeError("SNMP-агент не сообщил ошибки принтера")
        status_number = int.from_bytes(status_value[1], "big", signed=True)
        status = STATUS_NAMES.get(status_number, f"код {status_number}")
        bits = errors_value[1]
        errors = [
            name for index, name in enumerate(ERROR_NAMES)
            if index // 8 < len(bits) and bits[index // 8] & (0x80 >> (index % 8))
        ]
        return {"printer_status": status, "errors": errors, "snmp_error": None}
    except (OSError, ValueError, IndexError, RuntimeError) as error:
        return {"printer_status": None, "errors": [], "snmp_error": str(error)}
