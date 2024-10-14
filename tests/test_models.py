import pytest
from pydantic import ValidationError
from unittest.mock import mock_open
from galaxy.core.models import Config, RelyConfig, IntegrationConfig, ExecutionType


@pytest.fixture
def valid_yaml():
    return """
rely:
  token: "test_token"
  url: "https://test.url"
integration:
  id: "integration_id"
  type: "integration_type"
  executionType: "daemon"
  scheduledInterval: 30
  defaultModelMappings:
    key1: "value1"
    key2: "value2"
  dryRun: true
  properties:
    prop1: "value1"
    prop2: "value2"
"""


@pytest.fixture
def invalid_yaml():
    return """
rely:
  token: "test_token"
  url: "https://test.url"
integration:
  id: "integration_id"
  type: "integration_type"
  executionType: "invalid_execution_type"
  scheduledInterval: 30
  defaultModelMappings:
    key1: "value1"
    key2: "value2"
  dryRun: true
  properties:
    prop1: "value1"
    prop2: "value2"
"""


def test_rely_config():
    data = {"token": "test_token", "url": "https://test.url"}
    config = RelyConfig(**data)
    assert config.token == data["token"]
    assert config.url == data["url"]


def test_integration_config():
    data = {
        "id": "integration_id",
        "type": "integration_type",
        "executionType": "daemon",
        "scheduledInterval": 30,
        "defaultModelMappings": {"key1": "value1", "key2": "value2"},
        "dryRun": True,
        "properties": {"prop1": "value1", "prop2": "value2"},
    }
    config = IntegrationConfig(**data)
    assert config.id == data["id"]
    assert config.type == data["type"]
    assert config.execution_type == data["executionType"]
    assert config.scheduled_interval == data["scheduledInterval"]
    assert config.default_model_mappings == data["defaultModelMappings"]
    assert config.dry_run == data["dryRun"]
    assert config.properties == data["properties"]


def test_config_from_yaml(valid_yaml, mocker):
    mocker.patch("builtins.open", mock_open(read_data=valid_yaml))
    config = Config.from_yaml("dummy_path")
    assert config.rely.token == "test_token"
    assert config.rely.url == "https://test.url"
    assert config.integration.id == "integration_id"
    assert config.integration.type == "integration_type"
    assert config.integration.execution_type == ExecutionType.DAEMON
    assert config.integration.scheduled_interval == 30
    assert config.integration.default_model_mappings == {"key1": "value1", "key2": "value2"}
    assert config.integration.dry_run is True
    assert config.integration.properties == {"prop1": "value1", "prop2": "value2"}


def test_config_from_invalid_yaml(invalid_yaml, mocker):
    mocker.patch("builtins.open", mock_open(read_data=invalid_yaml))
    with pytest.raises(ValidationError):
        Config.from_yaml("dummy_path")


if __name__ == "__main__":
    pytest.main()
