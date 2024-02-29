from setuptools import setup, find_packages

setup(
    name="sat_com_topology",
    version="1.1",
    packages=find_packages(),
    install_requires=["networkx", "pyorbital"],
)
