from setuptools import setup, find_packages

setup(
    name="voxel",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "click>=8.0",
        "rich>=13.0",
        "requests>=2.28",
        "textual>=8.0",
        "tiktoken>=0.5.0",
    ],
    entry_points={
        "console_scripts": [
            "voxel=voxel.cli:cli",
        ],
    },
    python_requires=">=3.9",
    description="VOXEL - AI Coding Assistant for Termux (OpenCode/Kilo Code style)",
    author="VOXEL",
)
