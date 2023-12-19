from setuptools import setup, find_packages

setup(
    name="sat_com_topology",
    version="1.0",
    packages=find_packages(
        include=["satComTopology.sat_com_model", "satComTopology.sat_com_model.*"]
    ),
    install_requires=[],
)
