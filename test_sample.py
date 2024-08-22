from gdb_dashboard_svd import SVDDevicesHelper


def test_svd():
    helper = SVDDevicesHelper()

    helper.load(['./example.svd'])

    assert helper.devices_name() == ['ARM_Example']

    assert helper.get_peripheral('foo') is None

    periph = helper.get_peripheral('TIMER0')

    assert periph.name == 'TIMER0'
