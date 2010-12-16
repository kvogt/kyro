from distutils.core import setup

setup(
    name = 'KYRO',
    version = '0.1',
    author = 'Kyle Vogt',
    author_email = 'kyle@justin.tv',
    description = 'BGP route analyzer and optimzer',
    package_dir = {'kyro': 'lib'},
    packages = ['kyro'],
    scripts = ['bin/analyzer.py', 'bin/router.py']
  )