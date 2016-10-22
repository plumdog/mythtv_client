from setuptools import setup


setup(
    name='MythTV Services Client',
    packages=['mythtv_client'],
    version='0.0.1',
    install_requires=[
        'requests',
        # TODO: vtypes
    ],
    author='Andrew Plummer',
    author_email='plummer574@gmail.com',
    url='https://github.com/plumdog/mythtv_client',
    description='For making requests to the MythTV Services API.',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Operating System :: OS Independent',
    ])
