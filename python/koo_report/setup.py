from setuptools import setup, find_packages

setup(
    name="koo_report",
    version="1.0.0",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=["rich>=13.0"],
    entry_points={
        "console_scripts": [
            "koo_report=koo_report.__main__:main",
        ],
    },
)
