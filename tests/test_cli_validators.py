import pytest

from galaxy.cli.validators import validate_blueprint_schema, validate_keys


# Mocking click.echo to avoid actual print calls during tests
@pytest.fixture
def mock_click_echo(mocker):
    return mocker.patch("click.echo")


def test_validate_blueprint_schema_valid():
    blueprint = {"type": "object", "properties": {"key": {"type": "string"}}}
    try:
        validate_blueprint_schema(blueprint)
    except Exception:
        pytest.fail("validate_blueprint_schema() raised Exception unexpectedly!")


def test_validate_blueprint_schema_invalid():
    invalid_blueprint = {"type": "invalid_type"}

    assert validate_blueprint_schema(invalid_blueprint) is None


def test_validate_keys_safe():
    d = {"some_key": "value"}
    expected = {"someKey": "value"}
    new_dict, errors = validate_keys(d, "test_resource", unsafe=True)
    assert new_dict == expected
    assert errors == []


def test_validate_keys_unsafe():
    d = {"some_key": "value", "anotherKey": "value2"}
    expected = {"some_key": "value", "anotherKey": "value2"}
    new_dict, errors = validate_keys(d, "test_resource", unsafe=False)
    assert new_dict == expected
    assert errors == ["Key 'some_key' for test_resource is not in camelCase."]
