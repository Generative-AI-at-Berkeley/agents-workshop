from config.settings import get_settings


def test_settings_cached():
	s1 = get_settings()
	s2 = get_settings()
	assert s1 is s2
