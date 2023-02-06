from setuptools import find_packages, setup

from fdjj import __name__, __version__


def read_requirements():
    reqs = []
    with open("requirements.txt", "r") as f:
        for line in f:
            reqs.append(line.strip())

    return reqs


def read_readme():
    with open("README.md", "r", encoding="utf-8") as fh:
        long_description = fh.read()
    return long_description


setup(
    name=__name__,
    version=__version__,
    description="Fei Dao Jue Ji.",
    long_description=read_readme(),
    long_description_content_type="text/markdown",
    url="https://github.com/zhangxianbing/fdjj",
    packages=find_packages(include=[f"{__name__}*"]),
    install_requires=read_requirements(),
    python_requires=">=3.9",
    entry_points={
        "console_scripts": [
            f"{__name__} = {__name__}.{__name__}:main",
        ],
    },
)
