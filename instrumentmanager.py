import time

import visa
import serial

from os.path import isfile
from functools import reduce

from instr.agilente8362b import AgilentE8362B
from instr.agilente8362bmock import AgilentE8362BMock
from arduino.arduinoparallel import ArduinoParallel
from arduino.arduinoparallelmock import ArduinoParallelMock

# MOCK
mock_enabled = True


class InstrumentManager(object):

    measure_params = {
        0: {
            'f1': 10_000_000,
            'f2': 8_000_000_000,
            'pow': -5,
            'points': 1601
        },
        1: {
            'f1': 10_000_000,
            'f2': 15_000_000_000,
            'pow': -5,
            'points': 1601
        },
    }

    level_codes = {
        0: {
            0.0:  0b000000,
            0.5:  0b000001,
            1.0:  0b000010,
            2.0:  0b000100,
            4.0:  0b001000,
            8.0:  0b010000,
            16.0: 0b100000,
            31.5: 0b111111
        },
        1: {
            0.0:    0b000000,
            0.25:   0b000001,
            0.5:    0b000010,
            1.0:    0b000100,
            2.0:    0b001000,
            4.0:    0b010000,
            8.0:    0b100000,
            15.75:  0b111111
        }
    }

    def __init__(self):
        super().__init__()
        print('instrument manager: init')

        self._analyzer: AgilentE8362BMock = None
        self._progr: ArduinoParallelMock = None

        self._samplePresent = False

        self._measure_data = list()

        self.analyzers = ['E8362B']

        self._res_freqs = list()
        self._res_baseline = list()
        self._res_normalized_att = list()
        self._res_s11 = list()
        self._res_s22 = list()

        self._res_att_err_per_freq = list()
        self._res_att_err_per_code = list()
        self._res_phase_shift = list()
        self._res_att = list()

    def findInstruments(self):
        print('instrument manager: find instruments')

        def find_com_ports():
            for port in [f'COM{i+1}' for i in range(256)]:
                try:
                    s = serial.Serial(port)
                    s.close()
                    yield port
                except (OSError, serial.SerialException):
                    pass

        def find_live():
            # TODO refactor this mess
            # TODO error handling
            rm = visa.ResourceManager()
            addrs = rm.list_resources()
            print(f'available resources: {addrs}')
            for addr in addrs:
                print(f'trying {addr}')
                try:
                    inst = rm.open_resource(addr)
                    idn = inst.query('*IDN?')
                    print(idn)
                    _, model, _, _ = idn.split(',')
                    if model in self.analyzers:
                        self._analyzer = AgilentE8362B(idn=idn, inst=inst)
                        print(f'{model} found at {addr}')
                        break
                except Exception as ex:
                    print(ex)

            try:
                for port in find_com_ports():
                    s = serial.Serial(port=port, baudrate=115200, parity=serial.PARITY_NONE,
                                      bytesize=8, stopbits=serial.STOPBITS_ONE, timeout=1)
                    if s.is_open:
                        s.write(b'#NAME\n')
                        while s.in_waiting == 0:
                            pass
                        ans = s.read_all().strip()
                        s.close()
                        if b'ARDUINO' in ans:
                            self._progr = ArduinoParallel(port=port, baudrate=115200, parity=serial.PARITY_NONE,
                                                          bytesize=8, stopbits=serial.STOPBITS_ONE, timeout=1)
                            break
                else:
                    raise ValueError('Arduino not found')

            except Exception as ex:
                print(ex)

        def find_mocks():
            self._analyzer = AgilentE8362BMock(idn='Agilent,E8362B mock,sn,firmware')
            self._progr = ArduinoParallelMock(port='COM4', baudrate=115200, parity=serial.PARITY_NONE, bytesize=8,
                                              stopbits=serial.STOPBITS_ONE, timeout=1)

        if mock_enabled:
            find_mocks()
        else:
            find_live()

        return self._analyzer is not None and self._progr is not None

    def getInstrumentNames(self):
        return self._analyzer.name, self._progr.name

    def checkSample(self):
        print('instrument manager: check sample')

        # TODO implement sample check

        chan = 1
        self._analyzer.send(f'SYSTem:FPRESet')
        self._analyzer.send(f"CALCulate{chan}:PARameter:DEFine:EXT 'check_s21',S21")
        self._analyzer.send(f'DISPlay:WINDow1:STATe ON')
        self._analyzer.send(f"DISPlay:WINDow1:TRACe1:FEED 'check_s21'")

        self._analyzer.query(f'INITiate{chan}:CONTinuous OFF;*OPC?')
        self._analyzer.send(f'SENSe{chan}:SWEep:TRIGger:POINt OFF')

        self._analyzer.send(f'SOURce{chan}:POWer1 -5dbm')
        self._analyzer.send(f'SENSe{chan}:FOM:RANGe1:SWEep:TYPE linear')
        self._analyzer.send(f'SENSe{chan}:SWEep:POINts 51')
        self._analyzer.send(f'SENSe{chan}:FREQuency:STARt 10MHz')
        self._analyzer.send(f'SENSe{chan}:FREQuency:STOP 8GHz')

        self._analyzer.query(f'INITiate{chan};*OPC?')

        self._analyzer.send(f"CALCulate{chan}:PARameter:SELect 'check_s21'")
        self._analyzer.send(f'FORMat ASCII')

        res = self._analyzer.query(f'CALCulate{chan}:DATA? FDATA')

        avg = reduce(lambda a, b: a + b, [float(val) for val in res.split(',')], 0) / 51

        print(f'>>> avg level: {avg}')

        if avg > -15:
            self._samplePresent = True
        else:
            self._samplePresent = False

        return self._samplePresent

    def measure(self, params):
        print(f'instrument manager: start measure {params}')

        self.measureTask(params)

        print('instrument manager: end measure')

    def measureTask(self, params):
        print(f'measurement task run {params}')

        chan = 1
        port = 1
        meas_pow = -5
        meas_f1 = 10_000_000
        meas_f2 = 8_000_000_000
        points = 1601

        # self._analyzer.send(f'SYSTem:FPRESet')

        self._analyzer.send(f'CALCulate{chan}:PARameter:DEFine:EXT "meas_s21",S21')
        # self._analyzer.send(f'DISPlay:WINDow1:STATe ON')
        self._analyzer.send(f'DISPlay:WINDow1:TRACe1:DELete')
        self._analyzer.send(f'DISPlay:WINDow1:TRACe1:FEED "meas_s21"')

        self._analyzer.query(f'INITiate{chan}:CONTinuous ON;*OPC?')
        # self._analyzer.send(f'SENSe{chan}:SWEep:TRIGger:POINt OFF')

        self._analyzer.send(f'SOURce{chan}:POWer{port} {meas_pow} dbm')
        self._analyzer.send(f'SENSe{chan}:FOM:RANGe1:SWEep:TYPE linear')
        self._analyzer.send(f'SENSe{chan}:SWEep:POINts {points}')
        self._analyzer.send(f'SENSe{chan}:FREQuency:STARt {meas_f1}')
        self._analyzer.send(f'SENSe{chan}:FREQuency:STOP {meas_f2}')

        # self._analyzer.query(f'INITiate{chan};*OPC?')
        self._analyzer.send(f'TRIG:SCOP CURRENT')

        self._analyzer.send(f'CALCulate{chan}:PARameter:SELect "meas_s21"')
        self._analyzer.send(f'FORMat ASCII')

        res = self._analyzer.query(f'CALCulate{chan}:DATA? FDATA')

        print(res)

# https://stackoverflow.com/questions/24214643/python-to-automatically-select-serial-ports-for-arduino

# калибровка 1 рез перед измерением
# sweep->sweep type->linear freq->start 10 MHz
#                                   end pm1 = 8gHz pm2 = 15gHz
# points 1601
# set channel 1
# channel->power->port1-> 5 dbm
# trace->measure->S21
# measure start
#
# trace->measure->S11 S22
#
#
#

