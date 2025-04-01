# -*- coding: utf-8 -*-
import pyb
from pyb import UART

class ProtocolHandler:
    def __init__(self):
        self.uart = UART(3, 115200)
        self.seq_num = 0

    def send_acu_data(self, acu_id, x_mm, y_mm, pressure):
        """
        数据包格式:
        [HEAD][SEQ][ID][X][Y][PRESS][CRC]
        0xAA  0x00 0x00 0x0000 0x0000 0x00 0x00
        """
        payload = bytearray([
            0xAA,  # 帧头
            self.seq_num % 256,
            ord(acu_id[0]), ord(acu_id[1]), ord(acu_id[2]),
            (x_mm >> 8) & 0xFF, x_mm & 0xFF,
            (y_mm >> 8) & 0xFF, y_mm & 0xFF,
            pressure
        ])

        crc = self._calc_crc(payload)
        packet = payload + bytearray([crc])
        self.uart.write(packet)
        self.seq_num +=1

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
