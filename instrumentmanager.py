import time
from itertools import repeat

import numpy
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
                    s = serial.Serial(port=port, baudrate=9600, parity=serial.PARITY_NONE,
                                      bytesize=8, stopbits=serial.STOPBITS_ONE, timeout=1)
                    if s.is_open:
                        # s.write(b'LPF,1')
                        s.write(bytes([0x23, 0x4E, 0x41, 0x4D, 0x45]))
                        # time.sleep(0.5)
                        while s.in_waiting == 0:
                            pass
                        ans = s.read_all()
                        s.close()
                        # if b'LPF is ' in ans:
                        if b'ARDUINO' in ans:
                            self._progr = ArduinoParallel(port=port, baudrate=9600, parity=serial.PARITY_NONE,
                                                          bytesize=8, stopbits=serial.STOPBITS_ONE, timeout=1)
                            break
                else:
                    raise ValueError('Arduino not found')

            except Exception as ex:
                print(ex)

        def find_mocks():
            self._analyzer = AgilentE8362BMock(idn='Agilent,E8362B mock,sn,firmware')
            self._progr = ArduinoParallelMock(port='COM4', baudrate=9600, parity=serial.PARITY_NONE, bytesize=8,
                                              stopbits=serial.STOPBITS_ONE, timeout=1)

        if mock_enabled:
            find_mocks()
        else:
            find_live()
            # self._progr = ArduinoParallelMock(port='COM4', baudrate=115200, parity=serial.PARITY_NONE, bytesize=8,
            #                                   stopbits=serial.STOPBITS_ONE, timeout=1)

        return self._analyzer is not None and self._progr is not None

    def getInstrumentNames(self):
        return self._analyzer.name, self._progr.name

    def checkSample(self):
        print('instrument manager: check sample')

        # TODO implement sample check

        chan = 1
        points = 51
        self._progr.set_lpf_code(0b100000)

        if not mock_enabled:
            time.sleep(1)

        self._analyzer.send(f'SYSTem:FPRESet')
        self._analyzer.send(f"CALCulate{chan}:PARameter:DEFine:EXT 'check_s21',S21")
        self._analyzer.send(f'DISPlay:WINDow1:STATe ON')
        self._analyzer.send(f"DISPlay:WINDow1:TRACe1:FEED 'check_s21'")

        self._analyzer.query(f'INITiate{chan}:CONTinuous OFF;*OPC?')
        self._analyzer.send(f'SENSe{chan}:SWEep:TRIGger:POINt OFF')

        self._analyzer.send(f'SOURce{chan}:POWer1 -5dbm')
        self._analyzer.send(f'SENSe{chan}:FOM:RANGe1:SWEep:TYPE linear')
        self._analyzer.send(f'SENSe{chan}:SWEep:POINts {points}')
        self._analyzer.send(f'SENSe{chan}:FREQuency:STARt 10MHz')
        self._analyzer.send(f'SENSe{chan}:FREQuency:STOP 8GHz')

        self._analyzer.query(f'INITiate{chan};*OPC?')

        self._analyzer.send(f"CALCulate{chan}:PARameter:SELect 'check_s21'")
        self._analyzer.send(f'FORMat ASCII')

        res = self._analyzer.query(f'CALCulate{chan}:DATA? FDATA')

        avg = reduce(lambda a, b: a + b, map(float, res.split(',')), 0) / points

        print(f'>>> avg level: {avg}')

        # if avg > -15:
        # if avg > -40:
        if avg > -90:
            self._samplePresent = True
        else:
            self._samplePresent = False

        return self._samplePresent

    def clear_data(self):
        self._res_freqs.clear()
        self._res_baseline.clear()
        self._res_normalized_att.clear()
        self._res_s11.clear()
        self._res_s22.clear()

        self._res_att_err_per_freq.clear()
        self._res_att_err_per_code.clear()
        self._res_phase_shift.clear()
        self._res_att.clear()

    def measure(self, params):
        print(f'instrument manager: start measure {params}')

        self.clear_data()

        self.measureTask(params)

        print('instrument manager: end measure')

    def measure_code(self, chan, name):
        print('measure param', name)
        self._analyzer.send(f'CALCulate{chan}:PARameter:SELect "{name}"')
        self._analyzer.send(f'FORMat ASCII')
        return self._analyzer.query(f'CALCulate{chan}:DATA? FDATA')

    def parse_measure_string(self, string: str):
        return [float(point) for point in string.split(',')]

    def measureTask(self, params):
        print(f'measurement task run {params}')

        chan = 1
        port = 1
        s21_name = 'meas_s21'
        s11_name = 'meas_s11'
        s22_name = 'meas_s22'

        meas_pow = self.measure_params[params]['pow']
        meas_f1 = self.measure_params[params]['f1']
        meas_f2 = self.measure_params[params]['f2']
        points = self.measure_params[params]['points']

        if mock_enabled:
            points = 51

        # self._analyzer.send(f'SYSTem:FPRESet')

        self._analyzer.send(f'CALCulate{chan}:PARameter:DEFine:EXT "{s21_name}",S21')
        self._analyzer.send(f'CALCulate{chan}:PARameter:DEFine:EXT "{s11_name}",S11')
        self._analyzer.send(f'CALCulate{chan}:PARameter:DEFine:EXT "{s22_name}",S22')
        self._analyzer.send(f'DISPlay:WINDow1:TRACe1:DELete')
        self._analyzer.send(f'DISPlay:WINDow1:TRACe1:FEED "{s21_name}"')
        self._analyzer.send(f'DISPlay:WINDow1:TRACe2:FEED "{s11_name}"')
        self._analyzer.send(f'DISPlay:WINDow1:TRACe3:FEED "{s22_name}"')

        self._analyzer.query(f'INITiate{chan}:CONTinuous ON;*OPC?')

        self._analyzer.send(f'SOURce{chan}:POWer{port} {meas_pow} dbm')
        self._analyzer.send(f'SENSe{chan}:FOM:RANGe1:SWEep:TYPE linear')
        self._analyzer.send(f'SENSe{chan}:SWEep:POINts {points}')
        self._analyzer.send(f'SENSe{chan}:FREQuency:STARt {meas_f1}')
        self._analyzer.send(f'SENSe{chan}:FREQuency:STOP {meas_f2}')

        s21s = list()
        s11s = list()
        s22s = list()

        for label, code in reversed(list(self.level_codes[params].items())):
            self._progr.set_lpf_code(code)

            if not mock_enabled:
                time.sleep(1)

            self._analyzer.send(f'TRIG:SCOP CURRENT')

            s21s.append(self.parse_measure_string(self.measure_code(chan, s21_name)))
            s11s.append(self.parse_measure_string(self.measure_code(chan, s11_name)))
            s22s.append(self.parse_measure_string(self.measure_code(chan, s22_name)))

        # gen freq data
        # TODO: read off PNA
        self._res_freqs = list(numpy.linspace(meas_f1, meas_f2, points))

        # calc baseline
        self._res_baseline = s21s[0]

        # calc normalized attenuation
        self._res_normalized_att = list()
        for s21 in s21s:
            self._res_normalized_att.append([s - b for s, b in zip(s21, self._res_baseline)])

        # calc S11, S22
        self._res_s11 = s11s
        self._res_s22 = s22s

        # calc attenuation error per code
        for data, att in zip(self._res_normalized_att, self.level_codes[params].values()):
            self._res_att_err_per_code.append([d - b - c for d, b, c in zip(data, self._res_baseline, repeat(att, len(data)))])

        # calc attenuation error per freq - ?
        # how to chose freqs?
        # interpolate data between setting points or simply connect points?

        # calc phase shift

        # calc attenuation
        self._res_att = s21s

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

