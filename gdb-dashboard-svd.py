import gdb
from cmsis_svd.parser import SVDParser


class SVDDevicesHelper():
    """ Helper to ease SVD device utilization """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__devices = []

    def load(self, files):
        self.__devices.clear()

        for f in files:
            device = SVDParser.for_xml_file(f).get_device()
            if device is not None:
                self.__devices.append(device)
            else:
                raise Exception(f'unable to load {f}')

    def devices_name(self):
        return [x.name for x in self.__devices]

    def get_peripheral(self, name):
        for d in self.__devices:
            for p in d.peripherals:
                if p.name == name:
                    return p
        return None

    @staticmethod
    def get_register(peripheral, name):
        for r in peripheral.registers:
            if r.name == name:
                return r
        return None

    @staticmethod
    def get_addr_and_value(p, r):
        gdb_pointer = gdb.selected_frame().architecture()\
                                          .integer_type(r.size, False)\
                                          .pointer()
        addr = gdb.Value(p.base_address + r.address_offset).cast(gdb_pointer)

        try:
            if gdb_pointer.sizeof * 8 == r.size \
               and (len(r.fields) == 0
                    or
                    (len(r.fields) == 1 and r.fields[0].bit_width == r.size)):
                # it looks like this register content can be seen as an address
                value = f'{addr.dereference().cast(gdb_pointer)}'
            else:
                register_format = f'0>{int(r.size / 4)}x'
                value = f'0x{int(addr.dereference()):{register_format}}'
        except Exception:
            value = '<unavailable>'

        return f'{addr}', value

    def complete(self, text, word):
        args = text.split(' ')
        elems = []

        if len(args) == 1:
            for d in self.__devices:
                elems += d.peripherals
        elif len(args) == 2:
            elems = self.get_peripheral(args[0]).registers
        elif len(args) > 2:
            return gdb.COMPLETE_NONE

        return [x.name for x in elems if x.name.startswith(word)]


class SVD(SVDDevicesHelper, Dashboard.Module):
    """ Registers from SVD """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__registers = []

    def label(self):
        names = self.devices_name()

        if len(names) == 0:
            return 'SVD'
        return f'SVD [{",".join(names)}]'

    def lines(self, term_width, term_height, style_changed):
        out = []

        for index, (p, r, old_value) in enumerate(self.__registers):
            rname_format = f'>{int(term_width / 4 - len(p.name))}'
            addr, value = SVDDevicesHelper.get_addr_and_value(p, r)

            if old_value and old_value == value:
                changed = False
            else:
                self.__registers[index] = (p, r, value)
                changed = True

            line = ansi(f'{p.name} {r.name:{rname_format}} ({addr}): ',
                        R.style_low)
            line += ansi(f'{value}', R.style_selected_1 if changed else '')
            out.append(line)
        return out

    def load(self, arg):
        if arg:
            self.clear(arg)
            SVDDevicesHelper.load(self, arg.split(' '))
        else:
            raise Exception('No file specified')

    def add(self, arg):
        try:
            peripheral, register = arg.split(' ')
        except Exception:
            raise Exception('Usage: add <peripheral> <register>')

        p = self.get_peripheral(peripheral)
        if p is None:
            raise Exception(f'Peripheral {peripheral} not found')

        r = SVDDevicesHelper.get_register(p, register)
        if r is None:
            raise Exception(f'Register {register} not found')

        for other_p, other_r, _ in self.__registers:
            if other_p is p and other_r is r:
                raise Exception(f'{arg} already registered')

        self.__registers.append((p, r, None))

    def clear(self, arg):
        self.__registers.clear()

    def commands(self):
        return {
            'load': {
                'action': self.load,
                'doc': 'Load a SVD file',
                'complete': gdb.COMPLETE_FILENAME,
            },
            'add': {
                'action': self.add,
                'doc': 'Add a register to display',
                'complete': self.complete,
            },
            'clear': {
                'action': self.clear,
                'doc': 'Clear all registers',
            },
        }

    def attributes(self):
        return {
        }
