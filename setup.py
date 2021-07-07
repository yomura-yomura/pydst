from setuptools import setup, find_packages
import setuptools.command.build_py
import dst_extension_build


class build_py(setuptools.command.build_py.build_py):
    def run(self):
        super(build_py, self).run()
        dst_extension_build.build()


class build(setuptools.command.build_py.build_py):
    def run(self):
        self.run_command("build_py")
        # super(build, self).run()
        # setuptools.command.build_py.build_py.run(self)


setup(
    name='pydst',
    version='0.1',
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
    cmdclass={"build_py": build_py}
)
