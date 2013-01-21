from setuptools import find_packages, setup

version='1.0.6a'

setup(name='TracGitosis',
      version=version,
      description="gitosis basic settings",
      author='Christophe Drevet',
      author_email='dr4ke@dr4ke.net',
      url='',
      keywords='trac gitosis plugin',
      license="GPLv3+",
      packages=find_packages(exclude=['ez_setup', 'examples', 'tests*']),
      include_package_data=True,
      package_data={ 'tracgitosis': ['templates/*', 'htdocs/*'] },
      zip_safe=False,
      entry_points = """
      [trac.plugins]
      tracgitosis = tracgitosis
      """,
      )

