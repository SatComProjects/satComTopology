from setuptools import setup, find_packages

setup(
    name="sat_com_topology",
    version="1.0",
    packages=find_packages(
        include=["sat_com_topology.sat_com_model", "sat_com_topology.sat_com_model.*"]
    ),
    install_requires=[],
)
