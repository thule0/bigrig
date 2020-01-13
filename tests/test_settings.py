from bigrig.config import Settings


def test_simple_config(datadir):
    settings = Settings()
    settings.configure(datadir / 'config/simple')
    assert settings.origin.location == 'http://pypi'
    assert len(settings.targets) == 1
    t = settings.targets['co7_37']
    assert t.vars == dict(pythonver='3.7', os='co7')
    assert t.location == './br/co7_37/'
