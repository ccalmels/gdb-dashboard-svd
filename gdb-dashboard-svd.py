import gdb
import os
from cmsis_svd.parser import SVDParser


class SVDDevicesHelper():
    """Helper to ease SVD device utilization"""

    def __init__(self):
        self.__devices = []

    def load(self, files):
        self.__devices.clear()

        for f in files:
            f = os.path.expandvars(os.path.expanduser(f))
            device = SVDParser.for_xml_file(f).get_device()
            if device is None:
                raise Exception(f'unable to load {f}')

            self.__devices.append(device)

    def devices_name(self):
        return [x.name for x in self.__devices]

    def get_peripheral(self, name):
        return next((p for d in self.__devices for p in d.peripherals
                     if p.name == name), None)

    @staticmethod
    def get_register_name(register):
        if register.display_name is not None:
            return register.display_name
        return register.name

    @staticmethod
    def get_register(peripheral, name):
        return next((r for r in peripheral.registers
                     if SVDDevicesHelper.get_register_name(r) == name), None)

    @staticmethod
    def split_argv(args):
        parameters = []
        options = []

        for arg in args:
            (options if arg.startswith('/') else parameters).append(arg)

        if len(options) > 1:
            raise Exception('only one format allowed')

        if len(options) == 0:
            return args, None

        if options[0] not in ['/a', '/x', '/u', '/t', '/_t']:
            raise Exception(f'unknown format: {options[0]}')

        return parameters, options[0]

    @staticmethod
    def convert_format(fmt, register_size_in_bits):
        if fmt == '/a':
            return 'address'
        if fmt == '/u':
            return 'd'
        if fmt == '/t':
            return f'#0{register_size_in_bits + 2}b'
        if fmt == '/_t':
            nb_separators = (register_size_in_bits + 3) // 4 - 1
            return f'#0{register_size_in_bits + nb_separators + 2}_b'
        if fmt == '/x':
            return f'#0{(register_size_in_bits + 3) // 4 + 2}x'

        raise Exception('Unkonw format \'fmt\'')

    @staticmethod
    def get_format(r, fmt):
        pointer_size = 8 * gdb.lookup_type('long').pointer().sizeof
        register_size = r.size if r.size is not None else pointer_size

        if fmt is None:
            if pointer_size == register_size \
               and (len(r.fields) == 0
                    or
                    (len(r.fields) == 1
                     and r.fields[0].bit_width == register_size)):
                # looks like an address
                fmt = '/a'
            else:
                fmt = '/x'

        return SVDDevicesHelper.convert_format(fmt, register_size)

    @staticmethod
    def get_addr_and_value(p, r, fmt, styling=False):
        pointer_size = 8 * gdb.lookup_type('long').pointer().sizeof
        register_size = (r.size if r.size is not None and r.size != 0
                         else pointer_size)
        gdb_pointer = gdb.selected_frame().architecture()\
                                          .integer_type(register_size, False)\
                                          .pointer()
        addr = gdb.Value(p.base_address + r.address_offset).cast(gdb_pointer)

        try:
            if fmt == 'address':
                value = addr.dereference().cast(gdb_pointer)\
                                          .format_string(styling=styling)
            else:
                value = f'{int(addr.dereference()):{fmt}}'

        except Exception:
            value = '<unavailable>'

        return addr.format_string(styling=styling), value

    def complete(self, text, word):
        if word is None:
            return gdb.COMPLETE_NONE

        args = gdb.string_to_argv(text)

        if len(args) > 0:
            if args[-1] == '/' or (word and args[-1][0] == '/'):
                return [x for x in ['a', 'x', 'u', 't', '_t']
                        if x.startswith(word)]
            if word:
                args.pop()

        # strip out options
        args = [x for x in args if not x.startswith('/')]

        if len(args) == 0:
            elems = (x.name for d in self.__devices for x in d.peripherals)
        elif len(args) == 1:
            peripheral = self.get_peripheral(args[0])
            if peripheral is None:
                return gdb.COMPLETE_NONE
            elems = (SVDDevicesHelper.get_register_name(r)
                     for r in peripheral.registers)
        else:
            return gdb.COMPLETE_NONE

        return [x for x in elems if x.startswith(word)]

    @staticmethod
    def one_liner(description):
        if description:
            return ' '.join(description.split())
        return ''

    def info(self):
        for d in self.__devices:
            yield f'{d.name}:\n'

            for p in d.peripherals:
                base = gdb.Value(p.base_address)\
                          .cast(gdb.lookup_type('long').pointer())

                yield (f'\t{p.name}'
                       f'\tbase: {base}'
                       f' ({SVDDevicesHelper.one_liner(p.description)})\n')

    def info_peripheral(self, peripheral):
        p = self.get_peripheral(peripheral)
        if p is not None:
            base = gdb.Value(p.base_address)\
                      .cast(gdb.lookup_type('long').pointer())

            yield f'{p.name} base: {base}\n'

            for r in p.registers:
                yield (f'\t{SVDDevicesHelper.get_register_name(r)}'
                       f'\toffset: {r.address_offset:#x}'
                       f' ({SVDDevicesHelper.one_liner(r.description)})\n')

    def info_register(self, peripheral, register):
        p = self.get_peripheral(peripheral)
        if p is not None:
            r = SVDDevicesHelper.get_register(p, register)
            if r is not None:
                addr = gdb.Value(p.base_address + r.address_offset)\
                          .cast(gdb.lookup_type('long').pointer())
                name = SVDDevicesHelper.get_register_name(r)
                desc = SVDDevicesHelper.one_liner(r.description)

                yield (f'{name} addr: {addr}'
                       f' (access: {r.access}, desc: {desc})\n')

                for f in r.fields:
                    if f.bit_width == 1:
                        bits = f'{f.bit_offset}'
                    else:
                        bits = (f'{f.bit_width + f.bit_offset - 1}:'
                                f'{f.bit_offset}')
                    yield (f'\t{f.name}'
                           f'\t[{bits}]'
                           f' ({SVDDevicesHelper.one_liner(f.description)})\n')


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
            gdb.write('Usage: info [peripheral [register]]\n')
            return

        for i in info_iterator:
            gdb.write(i)


class SVDGet(SVDCommon):
    """Get the addresse and value of a register"""

    def __init__(self, svd_devices_helper):
        super().__init__(svd_devices_helper, 'get')

    def invoke(self, argument, from_tty):
        try:
            args, fmt = SVDDevicesHelper.split_argv(
                gdb.string_to_argv(argument))
            peripheral, register = args
        except Exception as e:
            gdb.write(f'Exception: {e}\n')
            gdb.write('Usage: get [/axut_t] <peripheral> <register>\n')
            return

        p = self._svd_devices_helper.get_peripheral(peripheral)
        if p is not None:
            r = SVDDevicesHelper.get_register(p, register)
            if r is not None:
                fmt = SVDDevicesHelper.get_format(r, fmt)
                addr, value = SVDDevicesHelper.get_addr_and_value(
                    p, r, fmt, from_tty)

                gdb.write(f'{addr}:\t{value}\n')
            else:
                gdb.write(f'unknown register {register}\n')
        else:
            gdb.write(f'unknown peripheral {peripheral}\n')


class SVD(SVDDevicesHelper, Dashboard.Module):  # noqa: F821
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

        for index, (p, r, fmt, old_value) in enumerate(self.__registers):
            rname_format = f'>{int(term_width / 4 - len(p.name))}'
            rname = SVDDevicesHelper.get_register_name(r)
            addr, value = SVDDevicesHelper.get_addr_and_value(p, r, fmt)

            if old_value and old_value == value:
                changed = False
            else:
                self.__registers[index] = (p, r, fmt, value)
                changed = True

            line = ansi(  # noqa: F821
                f'{p.name} {rname:{rname_format}} ({addr}): ',
                R.style_low)  # noqa: F821
            line += ansi(  # noqa: F821
                f'{value}',
                R.style_selected_1 if changed else '')  # noqa: F821
            out.append(line)
        return out

    def load(self, arg):
        if not arg:
            raise Exception('No file specified')

        self.clear(None)
        SVDDevicesHelper.load(self, gdb.string_to_argv(arg))
        SVDInfo(self)
        SVDGet(self)

    def get_register(self, peripheral, register, fmt=None):
        p = self.get_peripheral(peripheral)
        if p is None:
            raise Exception(f'Peripheral {peripheral} not found')

        r = SVDDevicesHelper.get_register(p, register)
        if r is None:
            raise Exception(f'Register {register} not found '
                            f'for peripheral {peripheral}')

        for other_p, other_r, other_fmt, v in self.__registers:
            if other_p is p and other_r is r:
                return (p, r, other_fmt, v), True

        return (p, r, SVDDevicesHelper.get_format(r, fmt), None), False

    def add(self, arg):
        try:
            args, fmt = SVDDevicesHelper.split_argv(
                gdb.string_to_argv(arg))
            peripheral, register = args
        except Exception:
            raise Exception('Usage: add [/axut_t] <peripheral> <register>')

        register, is_present = self.get_register(peripheral, register, fmt)

        if is_present:
            raise Exception(f'{arg} already registered')

        if register[1].access in ['write-only', 'writeOnce']:
            raise Exception(f'{arg} not readable register')

        self.__registers.append(register)

    def remove(self, arg):
        try:
            peripheral, register = gdb.string_to_argv(arg)
        except Exception:
            raise Exception('Usage: remove <peripheral> <register>')

        register, is_present = self.get_register(peripheral, register)

        if not is_present:
            raise Exception(f'Register {arg} is not registered')

        self.__registers.remove(register)

    def remove_complete(self, text, word):
        if word is None:
            return gdb.COMPLETE_NONE

        args = gdb.string_to_argv(text)

        if len(args) > 0 and word:
            args.pop()

        if len(args) == 0:
            elems = (p for p, _, _, _ in self.__registers)
        elif len(args) == 1:
            elems = (r for p, r, _, _ in self.__registers if p.name == args[0])
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
