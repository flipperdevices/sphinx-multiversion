# sphinx-multiversion [![Build Status](https://travis-ci.org/Holzhaus/sphinx-multiversion.svg?branch=master)](https://travis-ci.org/Holzhaus/sphinx-multiversion)

Sphinx extension for building self-hosted versioned docs.

This extension aims to provide a clean implementation that tries to avoid
messing with Sphinx internals as much as possible.

Documentation can be found at: https://holzhaus.github.io/sphinx-multiversion/

## Fork changes

- Now it works only if conf.py is placed in the submodule, 
and it's trying to find other refs where submodules have the same commit as the submodule on the current branch.


- Added the --debug option to print debug logs.
    ```bash
    sphinx-multiversion <source_dir> <output_dir> --debug
