import pytest
import psutil

@pytest.mark.devtest
def test_one_minute():
    assert psutil.getloadavg()[0] >= 0.0
    
@pytest.mark.devtest
def test_five_minute():
    assert psutil.getloadavg()[1] >= 0.0

    
@pytest.mark.devtest
def test_fifteen_minute():
    assert psutil.getloadavg()[2] >= 0.0