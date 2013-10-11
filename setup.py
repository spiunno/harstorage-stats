from setuptools import setup

setup(
    name='Harstorage stats',
    version='1.0',
    long_description=__doc__,
    packages=['harstorage_stats'],
    include_package_data=True,
    zip_safe=False,
    install_requires=['Flask', 'couchbase', 'gviz_data_table']
)
