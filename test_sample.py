import pytest
from gdb_dashboard_svd import SVDDevicesHelper


def test_bad_svd():
    helper = SVDDevicesHelper()

    with pytest.raises(Exception):
        helper.load(['./requirements.txt'])


def test_good_svd():
    helper = SVDDevicesHelper()

    helper.load(['./example.svd'])

    assert helper.devices_name() == ['ARM_Example']

    assert helper.get_peripheral('foo') is None

    assert helper.get_peripheral(None) is None

    periph = helper.get_peripheral('TIMER0')

    assert periph.name == 'TIMER0'
