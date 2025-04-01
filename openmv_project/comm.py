# -*- coding: utf-8 -*-
import pyb
from pyb import UART

class ProtocolHandler:
    def __init__(self):
        self.uart = UART(3, 115200)
        self.seq_num = 0

    def send_acu_data(self, acu_id, x_mm, y_mm, pressure):
        # 数据压缩：将坐标映射到12位（0-4095）
        x_enc = min(max(x_mm, 0), 4095)
        y_enc = min(max(y_mm, 0), 4095)
        payload = bytearray([
            0xAA,
            self.seq_num % 256,
            ord(acu_id[0]), ord(acu_id[1]), ord(acu_id[2]),
            (x_enc >> 4) & 0xFF,  # 高8位
            ((x_enc & 0xF) << 4) | ((y_enc >> 8) & 0xF),  # 低4位 + 高4位
            y_enc & 0xFF,  # 低8位
            pressure
        ])
        crc = self._calc_crc(payload)
        packet = payload + bytearray([crc])
        self.uart.write(packet)
        self.seq_num += 1

    def _calc_crc(self, data):
        crc = 0
        for b in data:
            crc ^= b
            for _ in range(8):
                if crc & 0x80:
                    crc = (crc << 1) ^ 0x07
                else:
                    crc <<= 1
                crc &= 0xFF
        return crc
