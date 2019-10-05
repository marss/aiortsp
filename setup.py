import setuptools
import pathlib

root_dir = pathlib.Path(__file__).parent
with (root_dir / 'aiortsp' / '__version__.py').open(encoding='utf-8') as f:
    exec(f.read())

setuptools.setup(
    version=__version__,
)
