from setuptools import setup, find_packages

short_descr = ("Tools for parsing, manipulating, and replaying QIIME 2 "
               "analyses leveraging the framework's decentralized provenance "
               "data tracking.")

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
   name='provenance_lib',
   version='0.0.1',
   description=short_descr,
   long_description=long_description,
   url='https://github.com/ChrisKeefe/provenance_py.git',
   author='Chris Keefe',
   author_email='crk239@nau.edu',
   license='BSD-3-clause',
   packages=find_packages(),
   install_requires=['pyyaml>=5.3', 'bibtexparser>=1.0', 'pytest>=6',
                     'pytest-cov>=2.0', 'flake8'],
)
