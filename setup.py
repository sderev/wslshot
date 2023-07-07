from setuptools import setup, find_packages


VERSION = "0.0.2"


def read_requirements():
    with open("requirements.txt") as file:
        return list(file)


def get_long_description():
    with open("README.md", encoding="utf8") as file:
        return file.read()


setup(
    name="wslshot",
    description="",
    long_description=get_long_description(),
    long_description_content_type="text/markdown",
    author="Sébastien De Revière",
    url="https://github.com/sderev/wslshot",
    project_urls={
        "Documentation": "https://github.com/sderev/wslshot",
        "Issues": "http://github.com/sderev/wslshot/issues",
        "Changelog": "https://github.com/sderev/wslshot/releases",
    },
    license="Apache Licence, Version 2.0",
    version=VERSION,
    packages=find_packages(),
    install_requires=read_requirements(),
    entry_points={
        "console_scripts": [
            "wslshot = wslshot.cli:wslshot",
        ]
    },
    python_requires=">=3.8",
)
