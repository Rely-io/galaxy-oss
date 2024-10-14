import pytest
import shutil
import os


@pytest.fixture(scope="session", autouse=True)
def cleanup():
    yield  # This will run the tests
    folder_to_delete = "galaxy/integrations/test_cli"
    if os.path.exists(folder_to_delete):
        shutil.rmtree(folder_to_delete)
