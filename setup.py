import setuptools

with open("README.md", "r") as f:
    long_description = f.read()

setuptools.setup(
    name="bakabakabaka",
    version="0.5.5",
    description="Baka Admin's Kludge Assistant",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/elesiuta/baka",
    py_modules=["baka"],
    entry_points={"console_scripts": ["baka = baka:main"]},
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)"
    ],
)
