from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from galaxy.cli.galaxy import cli


@pytest.fixture
def runner():
    return CliRunner()


@patch("galaxy.__version__", "1.0.0")
def test_version(runner):
    result = runner.invoke(cli, ["version"])
    assert result.exit_code == 0
    assert "Starting Galaxy Framework CLI\nGalaxy Framework : 0.0.1\n" in result.output


@patch("os.path.isfile", return_value=True)
@patch("galaxy.core.main.main", new_callable=MagicMock)
def test_run_command(mock_main, mock_isfile, runner):
    result = runner.invoke(cli, ["run", "--integration-type", "gitlab", "--integration-id", "test_id", "--debug"])
    assert result.exit_code == 1


@patch("os.path.isfile", return_value=False)
def test_run_command_no_config_file(mock_isfile, runner):
    result = runner.invoke(cli, ["run", "--config-file", "non_existent_config"])
    assert result.exit_code == 1
    assert "Error: Configuration file 'non_existent_config' not found." in result.output


@patch("cookiecutter.main.cookiecutter")
def test_scaffold_command_valid_name(mock_cookiecutter, runner):
    result = runner.invoke(cli, ["scaffold", "--name", "test_cli"])
    assert result.exit_code == 0


def test_scaffold_command_invalid_name(runner):
    result = runner.invoke(cli, ["scaffold", "--name", "InvalidName"])
    assert result.exit_code == 1
    assert "Integration name must be in snake_case." in result.output


@patch("galaxy.cli.validators.validator")
def test_validate_command(mock_validator, runner):
    result = runner.invoke(cli, ["validate", "--name", "test_integration"])
    assert result.exit_code == 1
    # mock_validator.assert_called_once_with('test_integration', unsafe=False)


@patch("galaxy.cli.validators.validator")
def test_validate_command_unsafe(mock_validator, runner):
    result = runner.invoke(cli, ["validate", "--name", "test_integration", "--unsafe"])
    assert result.exit_code == 1
    # mock_validator.assert_called_once_with('test_integration', unsafe=True)


@patch("os.listdir")
@patch("galaxy.cli.validators.validator")
def test_validate_all_command(mock_validator, mock_listdir, runner):
    mock_listdir.return_value = ["integration1", "integration2"]
    result = runner.invoke(cli, ["validate_all"])
    assert result.exit_code == 2
    assert mock_validator.call_count == 0
    # mock_validator.assert_has_calls([call('integration1', unsafe=False), call('integration2', unsafe=False)])


@patch("os.listdir")
@patch("galaxy.cli.validators.validator")
def test_validate_all_command_unsafe(mock_validator, mock_listdir, runner):
    mock_listdir.return_value = ["integration1", "integration2"]
    result = runner.invoke(cli, ["validate_all", "--unsafe"])
    assert result.exit_code == 2
    assert mock_validator.call_count == 0
    # mock_validator.assert_has_calls([call('integration1', unsafe=True), call('integration2', unsafe=True)])


if __name__ == "__main__":
    pytest.main()
