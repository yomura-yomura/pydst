from setuptools import setup, find_packages
from distutils.command.build_py import build_py
import dst_extension_build


class build(build_py):
    def run(self):
        dst_extension_build.build()
        super().run()


setup(
    name='pydst',
    version='0.0',
    description='',
    author='yomura',
    author_email='yomura@hoge.jp',
    url='https://github.com/yomura-yomura/pydst',
    packages=find_packages(),
    install_requires=[
        "numpy",
        "pycparser",
        "cffi",
        "more-itertools"
    ],
    cmdclass={"build": build}
)
