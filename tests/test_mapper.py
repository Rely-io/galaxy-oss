from unittest.mock import patch

import pytest

from galaxy.core.mapper import Mapper


@pytest.fixture
def mock_resource_filename():
    with patch("pkg_resources.resource_filename", return_value="dummy_path") as mock:
        yield mock


@pytest.fixture
def mock_load_integration_resource():
    mock_values = """
    resources:
      - kind: test_kind
        mappings:
          key1: '.data1'
          key2:
            sub_key1: '.data2'
            sub_key2:
              - '.data3'
    """
    with patch("galaxy.core.mapper.load_integration_resource", return_value=mock_values) as mock:
        yield mock


@pytest.mark.asyncio
async def test_process(mock_resource_filename, mock_load_integration_resource):
    json_data = [{"data1": "value1", "data2": "value2", "data3": "value3"}]
    expected_entities = [{"key1": "value1", "key2": {"sub_key1": "value2", "sub_key2": ["value3"]}}]

    mapper = Mapper("test_integration")
    entities = await mapper.process("test_kind", json_data)
    assert entities == expected_entities
    mock_load_integration_resource.assert_called_once()
