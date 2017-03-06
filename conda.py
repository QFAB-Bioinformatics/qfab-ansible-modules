#!/usr/bin/python
# -*- coding: utf-8 -*-

### QFAB Conda Version Tool Deployment Module
#
# (c) 2017, Thom Cuddihy <t.cuddihy@qfab.org>
#
# Ansible module to easily deploy a versioned tool environments using Conda
# to bioinformatics linux servers (originally Genomics Virtual Labs).
#
# NOTE: this DOES include versioning of dependencies too :)
#
# Conda path is assumed to be consistent with GVL by default:
#   /mnt/gvl/apps/anaconda_ete/bin
#
# Minimum tested version of Conda is 4.0.11
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
# TODO: Too many iterations; do this at the end! ~tink

DOCUMENTATION = """
---
module: conda
author:
   - "Thom Cuddihy (@thom88)"
requirements:
   - "python >= 2.6"
   - "conda >= 4.0.11"
short_description: Package manager for Conda
description:
    - Manages Conda packages
options:
"""

EXAMPLES = """
    See options comment above :)
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

    #region constants
    CONDA_MAJOR_VERSION = 4
    CONDA_MINOR_VERSION = 0
    CONDA_TERT_VERSION = 11

    #endregion

    #region regex
    VALID_PATH_CHARS = r'''
            \w                  # alphanumeric characters (i.e., [a-zA-Z0-9_])
            \s                  # spaces
            :                   # colons
            {sep}               # the OS-specific path separator
            .                   # dots
            -                   # dashes
        '''.format(sep=os.path.sep)

    VALID_ENV_CHARS = r'''
            \w                  # alphanumeric characters (i.e., [a-zA-Z0-9_])
            .                   # dots
            -                   # dashes
        '''.format(sep=os.path.sep)

    VALID_PACKAGE_CHARS = r'''
            \w                  # alphanumeric characters (i.e., [a-zA-Z0-9_])
            .                   # dots
            =                   # version equals
            -                   # dashes
        '''

    INVALID_PATH_REGEX = _create_regex_group(VALID_PATH_CHARS)
    INVALID_ENV_REGEX = _create_regex_group(VALID_ENV_CHARS)
    INVALID_PACKAGE_REGEX = _create_regex_group(VALID_PACKAGE_CHARS)

    #endregion

    #region class validation
    @classmethod
    def valid_path(cls, path):
        if isinstance(path, basestring):
            return not cls.INVALID_PATH_REGEX.search(path)

        try:
            iter(path)
        except TypeError:
            return False
        else:
            paths = path
            for path_ in paths:
                if cls.INVALID_PATH_REGEX.search(path_):
                    return False
            return True

    @classmethod
    def valid_environment(cls, name):
        return (
            isinstance(name, basestring)
            and not cls.INVALID_ENV_REGEX.search(name)
        )

    @classmethod
    def valid_package(cls, package):
        return (
            isinstance(package, basestring)
            and not cls.INVALID_PACKAGE_REGEX.search(package)
        )

    @classmethod
    def valid_state(cls, state):
        if state is None:
            return True
        else:
            return (
                isinstance(state, basestring)
                and state.lower() in (
                    'present',
                    'absent',
                    'remove_env',
                )
            )

    @classmethod
    def valid_module(cls, module):
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

    # nasty direct property declarations to remove warning message
    # TODO rework to include validation in setters and use private vars
    @property
    def environment(self):
        return self.environment
    @property
    def state(self):
        return self.state

    @property
    def update_conda(self):
        return self.update_conda

    @property
    def channels(self):
        return self.channels

    @property
    def packages(self):
        return self.packages

    #endregion

    def __init__(self, module, environment, path, state, channels,
                 packages, update_conda):

        self._setup_status_vars()
        self._setup_instance_vars(module=module, environment=environment, path=path,
                                  state=state, channels=channels, packages=packages,
                                  update_conda=update_conda)
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

        cmd = [
            "{conda_path}".format(conda_path=self.conda_path),
            "info",
        ]
        rc, out, err = self.module.run_command(cmd)
        conda_return = out.split(' ')
        if not conda_return[1] == "conda":
            self.failed = True
            self.message = 'Unexpected return during conda check'
            raise CondaException('Unexpected return during conda check')
        conda_version = conda_return[2].split('.')

        # this is... probably the worse code I've ever written
        # TODO: fix this monstrosity
        self.update_only = False
        if conda_version[1] < self.CONDA_MAJOR_VERSION:
            self.update_only = True
        elif conda_version[1] == self.CONDA_MAJOR_VERSION:
            if conda_version[2] < self.CONDA_MINOR_VERSION:
                self.update_only = True
            elif conda_version[2] == self.CONDA_MINOR_VERSION:
                if conda_version[3] && (conda_version[3] < self.CONDA_TERT_VERSION):
                    self.update_only = True
        return self.conda_path

    def _status(self):
        return (self.failed, self.changed, self.message)
    #endregion

    #region checks

    def _environment_exists(self):
        if not self.valid_environment(self.environment):
            self.failed = True
            self.message = 'Invalid environment name: {0}'.format(self.environment)
            raise CondaException(self.message)

        cmd = [
            "{conda_path}".format(conda_path=self.conda_path),
            "env list | awk '{print $1}'",
        ]
        rc, out, err = self.module.run_command(cmd)
        if rc == 0:
            for line in out.split('\n'):
               if self.environment == line:
                   return True
            return False
        else:
            self.failed = True
            self.message = err.strip()
            raise CondaException(self.message)

    def _check_packages(self):
        bad_packages = []
        for package in self.packages:
            if not self.valid_package(package):
                self.failed = True
                bad_packages.append(package)
        if self.failed:
            self.message = 'Invalid packages: {0}'.format(bad_packages)
            raise CondaException(self.message)
        return True

    # TODO add check for individual package that calls `conda search` e.g.
    def _check_package(self):
        return True
    #endregion

    #region append commands
    def _add_channels_to_command(self, command):
        if self.channels:
            channels = self.channels.strip().split()
            all_channels = []
            for channel in channels:
                all_channels.append('--channel')
                all_channels.append(channel)

            return command[:2] + all_channels + command[2:]
        else:
            return command

    # TODO: refactor conda calls to actually use this again :)
    def _add_environment_to_command(self, command):
        if self.environment:
            env = []
            env.append("--name")
            env.append(self.environment)
            return command[:2] + env + command[2:]
        else:
            return command

    #endregion

    #region bulk commands
    def _install_packages(self):
        cmd = ([
            self.conda_path,
        ])
        new_env = False
        if self.environment:
            if self._environment_exists():
                cmd.append([
                    "install",
                    "-y",
                    "-n ",
                    self.environment,
                ])
            else:
                new_env = True
                cmd.append([
                    "create",
                    "-y",
                    "-n",
                    self.environment,
                ])
        for package in self.packages:
            cmd.append(package)
        cmd = self._add_channels_to_command(cmd)
        rc, out, err = self.module.run_command(cmd)
        if rc == 0:
            if out and isinstance(out, basestring):
                already_updated = any(
                    re.search(r'All requested packages already installed', s.strip(), re.IGNORECASE)
                    for s in out.split('\n')
                    if s
                )
                if not already_updated:
                    self.changed = True
                    if new_env:
                        self.message = 'Conda environment created successfully.'
                        self.changed_count += 1
                    else:
                        self.message = 'Conda environment updated successfully'
                        self.changed_count += 1
                else:
                    self.message = 'Conda environment already set up'
                    self.unchanged_count += 1
            return True
        else:
            self.failed = True
            self.message = err.strip()
            raise CondaException(self.message)
    

    def _uninstall_packages(self):
        if self.environment:
            if self._environment_exists():
                cmd = ([
                    self.conda_path,
                    "remove",
                    "-y",
                    "-n",
                    self.environment,
                ])
                rc, out, err = self.module.run_command(cmd)
                if rc == 0:
                    self.changed = True
                    self.message = 'Conda packages successfully removed from environment'
                    self.changed_count += 1
                else: # TODO add check for packages already uninstall rather than just any error
                    self.failed = True
                    self.message = err.strip()
                    raise CondaException(self.message)
            else:
                #self.failed = True # _is_ this a fail?
                self.message = "Environment not found"
                self.unchanged_count += 1
        else:
            self.failed = True
            self.message = "No environment passed to remove packages from"
            raise CondaException(self.message)
    #endregion

    #region conda commands

    def _update_conda(self):
        cmd = ([
            self.conda_path,
            'update -y -n root conda',
        ])
        cmd = self._add_environment_to_command(cmd)
        rc, out, err = self.module.run_command(cmd)
        if rc == 0:
            if out and isinstance(out, basestring):
                already_updated = any(
                    re.search(r'All requested packages already installed', s.strip(), re.IGNORECASE)
                    for s in out.split('\n')
                    if s
                )
                if not already_updated:
                    self.changed = True
                    self.message = 'Conda updated successfully.'
                    self.changed_count += 1
                else:
                    self.message = 'Conda already up-to-date.'
                    self.unchanged_count += 1
        else:
            self.failed = True
            self.message = err.strip()
            raise CondaException(self.message)

    def _remove_environment(self):
        if self.environment:
            if self._environment_exists():
                cmd = ([
                    self.conda_path,
                    "remove",
                    "-y",
                    "-n",
                    self.environment,
                ])

                rc, out, err = self.module.run_command(cmd)
                if rc == 0:
                    self.changed = True
                    self.message = 'Conda environment successfully removed'
                    self.changed_count += 1
                else:
                    self.failed = True
                    self.message = err.strip()
                    raise CondaException(self.message)
            else:
                #self.failed = True # _is_ this a fail?
                self.message = "Environment for removal not found"
                self.unchanged_count += 1
        else:
            self.failed = True
            self.message = "No environment passed for removal"
            raise CondaException(self.message)

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

        if self.update_only and not self.update_conda:
            self.failed = True
            self.message = 'Unsupported conda version. Please update first.'
            raise CondaException('Unsupported conda version. Please update first.')

        if self.update_conda:
            self._update_conda()

        if self.packages:
            if self.state == "present":
                return self._install_packages()
            elif self.state == 'absent':
                return self._uninstall_packages()
            elif self.state == 'remove_env':
                return self._remove_environment()

    #endregion

#region main setup
def main():
    module = AnsibleModule(
            argument_spec=dict(
                name=dict(
                    required=False,
                    type='str',
                ),
                path=dict(
                    default="/mnt/gvl/apps/anaconda_ete/bin",
                    required=False,
                    type='path',
                ),
                state=dict(
                    default="present",
                    choices=["present", "absent",
                             "remove_env"],
                ),
                channels=dict(
                    default=None,
                    aliases=["channel"],
                    type='list',
                ),
                dependencies=dict(
                    default=None,
                    aliases=["packages"],
                    type='list',
                ),
                update_conda=dict(
                    default=False,
                    type='bool',
                ),
            ),
            supports_check_mode=True,
        )

    p = module.params

    if p['name']:
        environment = p['name']
    else:
        environment = None

    path = p['path']
    if path:
        path = path.split(':')

    state = p['state']
    if state in ('present'):
        state = 'present'
    if state in ('absent'):
        state = 'absent'
    if state in ('remove_env',):
        state = 'remove_env'

    channels = p['channels']
    packages = p['dependencies']

    update_conda = p['update_conda']

    conda = Conda(module=module, environment=environment, path=path, state=state,
                  channels=channels,packages=packages, update_conda=update_conda,)

    (failed, changed, message) = conda.run()
    if failed:
        module.fail_json(msg=message)
    else:
        module.exit_json(changed=changed, msg=message)

#endregion

if __name__ == '__main__':
    main()