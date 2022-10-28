import gdb
from cmsis_svd.parser import SVDParser


class SVDDevicesHelper():
    """Helper to ease SVD device utilization"""
    def __init__(self):
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
        else:
            return gdb.COMPLETE_NONE

        return [x.name for x in elems if x.name.startswith(word)]

    @staticmethod
    def one_liner(description):
        if description:
            return ' '.join(description.split())
        return ''

    def info(self):
        for d in self.__devices:
            yield f'{d.name}:\n'

            for p in d.peripherals:
                yield f'\t{p.name} '\
                    f'({SVDDevicesHelper.one_liner(p.description)})\n'

    def info_peripheral(self, peripheral):
        p = self.get_peripheral(peripheral)
        if p is not None:
            yield f'{p.name}:\n'

            for r in p.registers:
                yield f'\t{r.name} '\
                    f'({SVDDevicesHelper.one_liner(r.description)})\n'

    def info_register(self, peripheral, register):
        p = self.get_peripheral(peripheral)
        if p is not None:
            r = SVDDevicesHelper.get_register(p, register)
            if r is not None:
                yield f'{r.name}:\n'

                for f in r.fields:
                    yield f'\t{f.name} '\
                        f'{f.bit_width + f.bit_offset}:{f.bit_offset} '\
                        f'({SVDDevicesHelper.one_liner(f.description)})\n'


class SVDPrefix(gdb.Command):
    """Prefix SVD"""
    def __init__(self):
        super().__init__('svd', gdb.COMMAND_USER, gdb.COMPLETE_NONE, True)


class SVDCommon(gdb.Command):
    """Parent class for all standalone commands"""
    def __init__(self, svd_devices_helper, name):
        super().__init__('svd ' + name, gdb.COMMAND_DATA)
        self._svd_devices_helper = svd_devices_helper

    def complete(self, text, words):
        return self._svd_devices_helper.complete(text, words)


class SVDInfo(SVDCommon):
    """Returns information about the devices, a peripheral or a register"""
    def __init__(self, svd_devices_helper):
        super().__init__(svd_devices_helper, 'info')

    def invoke(self, argument, from_tty):
        args = gdb.string_to_argv(argument)

        if len(args) == 0:
            info_iterator = self._svd_devices_helper.info()
        elif len(args) == 1:
            info_iterator = self._svd_devices_helper.info_peripheral(args[0])
        elif len(args) == 2:
            info_iterator = self._svd_devices_helper.\
                info_register(args[0], args[1])
        else:
            gdb.write('Too much arguments\n')
            return

        for i in info_iterator:
            gdb.write(i)


class SVDGet(SVDCommon):
    """Get the addresse and value of a register"""
    def __init__(self, svd_devices_helper):
        super().__init__(svd_devices_helper, 'get')

    def invoke(self, argument, from_tty):
        try:
            peripheral, register = gdb.string_to_argv(argument)
        except Exception:
            gdb.write('Usage: add <peripheral> <register>\n')
            return

        p = self._svd_devices_helper.get_peripheral(peripheral)
        if p is not None:
            r = SVDDevicesHelper.get_register(p, register)
            if r is not None:
                addr, value = self._svd_devices_helper.get_addr_and_value(p, r)

                gdb.write(f'{addr}: {value}\n')
            else:
                gdb.write(f'unknown register {register}\n')
        else:
            gdb.write(f'unknown peripheral {peripheral}\n')


class SVD(SVDDevicesHelper, Dashboard.Module):
    """Display some registers defined in SVD files"""
    def __init__(self):
        super().__init__()
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
            self.clear(None)
            SVDDevicesHelper.load(self, gdb.string_to_argv(arg))
            SVDInfo(self)
            SVDGet(self)
        else:
            raise Exception('No file specified')

    def get_register(self, name, arg):
        try:
            peripheral, register = gdb.string_to_argv(arg)
        except Exception:
            raise Exception(f'Usage: {name} <peripheral> <register>')

        p = self.get_peripheral(peripheral)
        if p is None:
            raise Exception(f'Peripheral {peripheral} not found')

        r = SVDDevicesHelper.get_register(p, register)
        if r is None:
            raise Exception(f'Register {register} not found '
                            f'for peripheral {peripheral}')

        for other_p, other_r, v in self.__registers:
            if other_p is p and other_r is r:
                return (p, r, v), True

        return (p, r, None), False

    def add(self, arg):
        register, is_present = self.get_register('add', arg)

        if is_present:
            raise Exception(f'{arg} already registered')

        self.__registers.append(register)

    def remove(self, arg):
        register, is_present = self.get_register('remove', arg)

        if not is_present:
            raise Exception(f'Register {arg} is not registered')

        self.__registers.remove(register)

    def remove_complete(self, text, word):
        args = text.split(' ')
        elems = []

        if len(args) == 1:
            elems = [p for p, _, _ in self.__registers]
        elif len(args) == 2:
            elems = [r for p, r, _ in self.__registers if p.name == args[0]]
        else:
            return gdb.COMPLETE_NONE

        return [x.name for x in elems if x.name.startswith(word)]

    def clear(self, arg):
        self.__registers.clear()

    def commands(self):
        return {
            'load': {
                'action': self.load,
                'doc': 'Load SVD files',
                'complete': gdb.COMPLETE_FILENAME,
            },
            'add': {
                'action': self.add,
                'doc': 'Add a register to display',
                'complete': self.complete,
            },
            'remove': {
                'action': self.remove,
                'doc': 'Remove a register',
                'complete': self.remove_complete,
            },
            'clear': {
                'action': self.clear,
                'doc': 'Clear all registers',
            },
        }

    def attributes(self):
        return {
        }


SVDPrefix()
