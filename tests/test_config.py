"""Phase 1 test: the project configuration can be imported and is valid."""


def test_settings_import():
    from config import settings

    assert settings.PROJECT_NAME == "ACALE"
    assert settings.PROJECT_ROOT.exists()
    assert isinstance(settings.RANDOM_SEED, int)


def test_parameters_import_and_are_valid():
    from config import parameters

    assert parameters.validate_parameters() == []


def test_security_constants():
    from config import parameters

    assert parameters.AEAD_ALGORITHM == "ChaCha20-Poly1305"
    assert parameters.KEY_SIZE_BYTES == 32
    assert parameters.NONCE_SIZE_BYTES == 12
    assert parameters.TAG_SIZE_BYTES == 16


def test_package_import():
    import acale

    assert acale.__version__ == "0.1.0"