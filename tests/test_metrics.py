import math

from lantiq_onu_exporter import metrics


def test_clear_reports_no_data_instead_of_zero():
    metrics.publish({"gpon_uptime_seconds": 123.0, "gpon_ploam_state": 5}, {"bip": 0})
    metrics.clear()
    assert all(math.isnan(gauge._value.get()) for gauge in metrics.GAUGES.values())
    assert metrics.GTC.fields == {}


def test_publish_sets_missing_values_to_nan():
    metrics.publish({"gpon_ploam_state": 5}, {})
    assert metrics.GAUGES["gpon_ploam_state"]._value.get() == 5
    assert math.isnan(metrics.GAUGES["gpon_uptime_seconds"]._value.get())
