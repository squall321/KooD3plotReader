from setuptools import setup, find_packages

setup(
    name="koo_sphere_report",
    version="2.0.0",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=["rich>=13.0"],
    entry_points={
        "console_scripts": [
            "koo_sphere_report=koo_sphere_report.__main__:main",
        ],
    },
)
