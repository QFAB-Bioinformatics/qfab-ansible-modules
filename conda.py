#!/usr/bin/python
# -*- coding: utf-8 -*-

### QFAB Conda Version Tool Deployment Module
#
# (c) 2017, Thom Cuddihy <t.cuddihy@qfab.org>
#
# Ansible module to easily deploy a versioned tool environment using Conda
# to bioinformatics linux servers (originally Genomics Virtual Labs).
#
# NOTE: this DOES include versioning of dependencies too :)
#
# Conda path is assumed to get consistent with GVL by default:
#   /mnt/gvl/apps/anaconda_ete/bin
#
# More information:
# QFAB: http://qfab.org/
# GVL:  https://www.gvl.org.au/
#
# Based on macports (Jimmy Tang <jcftang@gmail.com>)
#
# TODO: Add environment and Python version management

ANSIBLE_METADATA = {'status': ['preview'],
                    'supported_by': 'community',
                    'version': '1.0'}

# TODO: Make sure that option aliases are consistent!
DOCUMENTATION = """
---
module: conda
author:
   - "Thom Cuddihy (@thom88)"
requirements:
   - "python >= 2.6"
   - conda
short_description: Package manager for Conda
description:
    - Manages Conda packages
options:
    name:
        description:
            - name of package to install/remove
        required: false
        default: None
        aliases: ['pkg', 'package', 'formula']
    version:
        description:
            - version of module
        required: false
        default: None
        aliases: ['ver', 'vers']
    state:
        description:
            - state of the package
        choices: [ 'head', 'latest', 'present', 'absent', 'linked', 'unlinked' ]
        required: false
        default: present
    channels:
        description:
            - additional Conda channels to use
        required: false
        default: None
        aliases: ['channel']
    environment:
        description:
            - the Conda environment to address, either new or existing
        required: false
        default: None
        aliases: ['env', 'venv']
    path:
        description:
            - "':' separated list of paths to search for 'conda' executable.
        required: false
        default: '/mnt/gvl/apps/anaconda_ete/bin'
    install_options:
        description:
            - options flags to use to install a package
        required: false
        default: null
        aliases: ['options']
    update_conda:
        description:
            - bool whether to update the Conda installation
        required: false
        default: false
    upgrade_all:
        description:
            - bool whether to upgrade all installed packages to latest version
        required: false
        default: false
"""

EXAMPLES = """
# Install tool 'foo'
- conda:
    name: foo
    state: present

# Install 'foo' version 1.3
- conda:
    name: foo
    vers: 1.3
    state: present
"""

import os.path
from ansible.module_utils.basic import *

class CondaException(Exception):
    pass

#region utils
def _create_regex_group(s):
    lines = (line.strip() for line in s.split('\n') if line.strip())
    chars = filter(None, (line.split('#')[0].strip() for line in lines))
    group = r'[^' + r''.join(chars) + r']'
    return re.compile(group)
#endregion

class Conda(object):
    '''A class to manage Conda packages.'''

    #region regex
    VALID_PATH_CHARS = r'''
            \w                  # alphanumeric characters (i.e., [a-zA-Z0-9_])
            \s                  # spaces
            :                   # colons
            {sep}               # the OS-specific path separator
            .                   # dots
            -                   # dashes
        '''.format(sep=os.path.sep)

    VALID_CONDA_PATH_CHARS = r'''
            \w                  # alphanumeric characters (i.e., [a-zA-Z0-9_])
            \s                  # spaces
            {sep}               # the OS-specific path separator
            .                   # dots
            -                   # dashes
        '''.format(sep=os.path.sep)

    VALID_PACKAGE_CHARS = r'''
            \w                  # alphanumeric characters (i.e., [a-zA-Z0-9_])
            .                   # dots
            /                   # slash (for taps)
            \+                  # plusses
            -                   # dashes
            :                   # colons (for URLs)
        '''

    INVALID_PATH_REGEX = _create_regex_group(VALID_PATH_CHARS)
    INVALID_CONDA_PATH_REGEX = _create_regex_group(VALID_CONDA_PATH_CHARS)
    INVALID_PACKAGE_REGEX = _create_regex_group(VALID_PACKAGE_CHARS)

    #endregion

    #region  class validation
    @classmethod
    def valid_path(cls, path):
        '''
        `path` must be one of:
         - list of paths
         - a string containing only:
             - alphanumeric characters
             - dashes
             - dots
             - spaces
             - colons
             - os.path.sep
        '''

        if isinstance(path, basestring):
            return not cls.INVALID_PATH_REGEX.search(path)

        try:
            iter(path)
        except TypeError:
            return False
        else:
            paths = path
            return all(cls.valid_conda_path(path_) for path_ in paths)

    @classmethod
    def valid_conda_path(cls, conda_path):
        '''
        `conda_path` must be one of:
         - None
         - a string containing only:
             - alphanumeric characters
             - dashes
             - dots
             - spaces
             - os.path.sep
        '''

        if conda_path is None:
            return True

        return (
            isinstance(conda_path, basestring)
            and not cls.INVALID_CONDA_PATH_REGEX.search(conda_path)
        )

    @classmethod
    def valid_package(cls, package):
        '''A valid package is either None or alphanumeric.'''

        if package is None:
            return True

        return (
            isinstance(package, basestring)
            and not cls.INVALID_PACKAGE_REGEX.search(package)
        )

    @classmethod
    def valid_version(cls, version):
        '''A valid version is either None or alphanumeric.'''

        if version is None:
            return True

        return (
            isinstance(version, basestring)
            and not cls.INVALID_CONDA_PATH_REGEX.search(version)
        )

    @classmethod
    def valid_recipe(cls, recipe):
        '''A valid version is either None or alphanumeric + URL chars.'''

        if recipe is None:
            return True

        return (
            isinstance(recipe, basestring)
            and not cls.INVALID_PACKAGE_REGEX.search(recipe)
        )

    @classmethod
    def valid_state(cls, state):
        '''
        A valid state is one of:
            - None
            - present
            - installed
            - latest
            - absent
            - removed
            - uninstalled
        '''

        if state is None:
            return True
        else:
            return (
                isinstance(state, basestring)
                and state.lower() in (
                    'present',
                    'installed',
                    'latest',
                    'absent',
                    'removed',
                    'uninstalled'
                )
            )

    @classmethod
    def valid_module(cls, module):
        '''A valid module is an instance of AnsibleModule.'''

        return isinstance(module, AnsibleModule)

    #endregion

    #region properties
    @property
    def module(self):
        return self._module

    @module.setter
    def module(self, module):
        if not self.valid_module(module):
            self._module = None
            self.failed = True
            self.message = 'Invalid module: {0}.'.format(module)
            raise CondaException(self.message)
        else:
            self._module = module

    @property
    def path(self):
        return self._path

    @path.setter
    def path(self, path):
        if not self.valid_path(path):
            self._path = []
            self.failed = True
            self.message = 'Invalid path: {0}.'.format(path)
            raise CondaException(self.message)

        else:
            if isinstance(path, basestring):
                self._path = path.split(':')
            else:
                self._path = path

    @property
    def conda_path(self):
        return self._conda_path

    @conda_path.setter
    def conda_path(self, conda_path):
        if not self.valid_conda_path(conda_path):
            self._conda_path = None
            self.failed = True
            self.message = 'Invalid conda_path: {0}.'.format(conda_path)
            raise CondaException(self.message)

        else:
            self._conda_path = conda_path

    @property
    def params(self):
        return self._params

    @params.setter
    def params(self, params):
        self._params = self.module.params

    @property
    def current_package(self):
        return self._current_package

    @current_package.setter
    def current_package(self, package):
        if not self.valid_package(package):
            self._current_package = None
            self.failed = True
            self.message = 'Invalid package: {0}.'.format(package)
            raise CondaException(self.message)

        else:
            self._current_package = package

    # nasty direct property declarations to remove warning message
    @property
    def state(self):
        return self.state

    @property
    def packages(self):
        return self.packages

    @property
    def update_conda(self):
        return self.update_conda

    @property
    def upgrade_all(self):
        return self.upgrade_all

    #endregion

    def __init__(self, module, packages, versions, path, state,
                 channels, install_options, update_conda, upgrade_all):
        if not install_options:
            install_options = list()
        self._setup_status_vars()
        self._setup_instance_vars(module=module, packages=packages, versions=versions,
                                  path=path, state=state, channels=channels,
                                  install_options=install_options,
                                  update_conda=update_conda, upgrade_all=upgrade_all )
        self._prep()

    #region prep
    def _setup_status_vars(self):
        self.failed = False
        self.changed = False
        self.changed_count = 0
        self.unchanged_count = 0
        self.message = ''

    def _setup_instance_vars(self, **kwargs):
        for key, val in iteritems(kwargs):
            setattr(self, key, val)

    def _prep(self):
        self._prep_conda_path()

    def _prep_conda_path(self):
        if not self.module:
            self.conda_path = None
            self.failed = True
            self.message = 'AnsibleModule not set.'
            raise CondaException(self.message)

        self.conda_path = self.module.get_bin_path(
            'conda',
            required=True,
            opt_dirs=self.path,
        )
        if not self.conda_path:
            self.conda_path = None
            self.failed = True
            self.message = 'Unable to locate conda executable.'
            raise CondaException('Unable to locate conda executable.')

        return self.conda_path

    def _status(self):
        return (self.failed, self.changed, self.message)
    #endregion

    #region checks

    def _current_package_is_installed(self):
        return True

    def _current_package_is_activated(self):
        return True

    def _check_installed(module, conda, name):
        return True

    #endregion

    #region append commands

    def _add_channels_to_command(command, channels):
        return True

    def _add_extras_to_command(command, extras):
        return True

    #endregiob

    #region individual commands

    def _remove_package(module, conda, installed, name):
        return True

    def _install_package(module, conda, installed, name, version, installed_version):
        return True

    def _update_package(module, conda, installed, name):
        return True

    #endregion
    
    #region bulk commands
    def _install_packages(self):
        return True
    
    def _upgrade_packages(self):
        return True
    
    def _uninstall_packages(self):
        return True
    #endregion

    #region conda commands

    def _update_conda(self):
        return True

    def _upgrade_all(self):
        return True

    #endregion

    #region run

    def run(self):
        try:
            self._run()
        except CondaException:
            pass

        if not self.failed and (self.changed_count + self.unchanged_count > 1):
            self.message = "Changed: %d, Unchanged: %d" % (
                self.changed_count,
                self.unchanged_count,
            )
        (failed, changed, message) = self._status()

        return (failed, changed, message)

    def _run(self):
        if self.update_conda:
            self._update_conda()

        if self.upgrade_all:
            self._upgrade_all()

        if self.packages:
            if self.state == "present":
                return self._install_packages()
            elif self.state == 'installed':
                return self._install_packages()
            elif self.state == 'latest':
                return self._upgrade_packages()
            elif self.state == 'absent':
                return self._uninstall_packages()
            elif self.state == 'removed':
                return self._uninstall_packages()
            elif self.state == 'uninstalled':
                return self._uninstall_packages()
    #endregion

#region main setup
def main():
    module = AnsibleModule(
            argument_spec=dict(
                name=dict(
                    aliases=["pkg", "package"],
                    required=True,
                    type='list',
                ),
                version=dict(
                    aliases=["ver", "vers"],
                    required=False,
                    type='list'
                ),
                path=dict(
                    default="/mnt/gvl/apps/anaconda_ete/bin",
                    required=False,
                    type='path',
                ),
                state=dict(
                    default="present",
                    choices=[
                        "present", "installed", "latest",
                        "absent", "removed", "uninstalled",
                    ],
                ),
                channels=dict(
                    default=None,
                    aliases=["channel"],
                    type='list',
                ),
                install_options=dict(
                    default=None,
                    aliases=['options'],
                    type='list',
                ),
                update_conda=dict(
                    default=False,
                    type='bool',
                ),
                upgrade_all=dict(
                    default=False,
                    aliases=["upgrade"],
                    type='bool',
                )
            ),
            supports_check_mode=True,
        )

    p = module.params

    if p['name']:
        packages = p['name']
    else:
        packages = None

    versions = p['version']

    path = p['path']
    if path:
        path = path.split(':')

    state = p['state']
    if state in ('present', 'installed'):
        state = 'installed'
    if state in ('head',):
        state = 'head'
    if state in ('latest', 'upgraded'):
        state = 'upgraded'
    if state == 'linked':
        state = 'linked'
    if state == 'unlinked':
        state = 'unlinked'
    if state in ('absent', 'removed', 'uninstalled'):
        state = 'absent'

    channels = p['channels']

    p['install_options'] = p['install_options'] or []
    install_options = ['--{0}'.format(install_option)
                       for install_option in p['install_options']]

    update_conda = p['update_conda']
    upgrade_all = p['upgrade_all']

    conda = Conda(module=module, packages=packages, versions=versions,path=path,
                  state=state, channels=channels, install_options=install_options,
                  update_conda=update_conda, upgrade_all=upgrade_all, )

    (failed, changed, message) = conda.run()
    if failed:
        module.fail_json(msg=message)
    else:
        module.exit_json(changed=changed, msg=message)

#endregion

if __name__ == '__main__':
    main()