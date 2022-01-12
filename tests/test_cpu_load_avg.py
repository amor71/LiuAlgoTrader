import pytest
import psutil
import os



@pytest.mark.devtest
def test_load_cpu_avg():
    assert psutil.cpu_percent(interval=None) / psutil.cpu_count() >= 0.0
