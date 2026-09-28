import warnings

import pytest


@pytest.fixture(autouse=True)
def _quiet_partitura():
    # partitura emits many parse warnings on real MusicXML; they are noise in test output
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        yield
