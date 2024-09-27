import pytest
import logging

from galaxy.core.galaxy import Integration, register
from galaxy.core.models import Config


class IntegrationTest(Integration):
    _methods = []

    @register(_methods, group=1)
    async def method_one(self, *args, **kwargs):
        return [{"id": 1, "name": "test"}]

    @register(_methods, group=2)
    async def method_two(self, *args, **kwargs):
        return [{"id": 2, "name": "test"}]


@pytest.fixture
def config():
    return {
        "integration": {
            "type": "test_type",
            "id": "test_id",
            "executionType": "daemon",
            "scheduledInterval": 1,
            "defaultModelMappings": {"test": "test"},
            "dryRun": False,
            "properties": {"test": "test"},
        },
        "rely": {"url": "http://testurl.com", "token": "test_token"},
    }


@pytest.fixture
def logger():
    return logging.getLogger("test_logger")


@pytest.mark.asyncio
async def test_register_decorator(config):
    test_instance = IntegrationTest(Config(**config))

    # Ensure methods are registered
    assert len(test_instance._methods) == 2
    assert test_instance._methods[0][0].__name__ == "method_one"
    assert test_instance._methods[1][0].__name__ == "method_two"
    assert test_instance._methods[0][1] == 1
    assert test_instance._methods[1][1] == 2


if __name__ == "__main__":
    pytest.main()
