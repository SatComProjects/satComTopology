from setuptools import setup, find_packages

setup(
    name="sat_com_topology",
    version="2.0",
    packages=find_packages(),
    install_requires=["networkx", "pyorbital"],
)
