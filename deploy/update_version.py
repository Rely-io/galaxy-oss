import toml
import os


def main():
    with open("pyproject.toml", "r") as f:
        pyproject_content = toml.load(f)
    version = pyproject_content["tool"]["poetry"]["version"]

    init_file_path = os.path.join(os.path.dirname(__file__), "..", "galaxy", "__init__.py")

    with open(init_file_path, "r") as f:
        lines = f.readlines()

    with open(init_file_path, "w") as f:
        for line in lines:
            if line.startswith("__version__"):
                f.write(f'__version__ = "{version}"\n')
            else:
                f.write(line)


if __name__ == "__main__":
    main()
