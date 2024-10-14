from unittest.mock import AsyncMock, patch

import pytest

from galaxy.core.mapper import Mapper


@pytest.fixture
def mock_resource_filename():
    with patch("pkg_resources.resource_filename", return_value="dummy_path") as mock:
        yield mock


@pytest.fixture
def mock_load_integration_resource():
    mock = """
    resources:
      - kind: test_kind
        mappings:
          key1: '.data1'
          key2:
            sub_key1: '.data2'
            sub_key2:
              - '.data3'
    """
    with patch("galaxy.core.resources.load_integration_resource", mock):
        yield mock


@pytest.fixture
def mock_load_mapping():
    mock = AsyncMock(
        return_value=[{"kind": "test_kind", "mappings": {"key1": ".data1", "key2": {"sub_key1": ".data2"}}}]
    )
    with patch("galaxy.core.mapper.Mapper._load_mapping", mock):
        yield mock


@pytest.mark.asyncio
async def test_process(mock_resource_filename, mock_load_integration_resource, mock_load_mapping):
    mapper = Mapper("test_integration")
    json_data = [{"data1": "value1", "data2": "value2", "data3": "value3"}]
    entities = await mapper.process("test_kind", json_data)
    expected_entities = [{"key1": "value1", "key2": {"sub_key1": "value2"}}]
    mock_load_mapping.assert_awaited_once()
    assert entities == expected_entities
