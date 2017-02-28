# QFAB Ansible Modules #
A collection of modules developed as part of QFAB projects.

### Installation ###
Make ansible aware of any Python modules here. Easiest way is the inclusion of a `library` folder at the playbook level.

Add this a submodule to any git Ansible repository:
> git submodule add https://github.com/QFAB-Bioinformatics/qfab-ansible-modules library

To update the modules, pull the latest versions of all submodules using:
>git submodule update --recursive --remote


## Usage ##

### Linuxbrew ###
A fork of the Ansible community [homebrew module](https://github.com/ansible/ansible-modules-extras/blob/devel/packaging/os/homebrew.py) to include version provisioning. Version information required is the recipe version, and the path to the recipe ruby file itself. This can be a filepath accessible to the target machine (if the recipe files are included on a network share, or contained in the repo using the `copy` module), but it usually the URL to the raw Linuxbrew recipe repo, including a commit hash for the version required.

**NOTE:** this provides versioning only for the package itself. Brew recipes do not include version information for any dependencies, so a reliably consistent provision cannot be guaranteed using Linuxbrew. We (and the Galaxy Team) recommend using Conda packaging instead where possible.

#### Example ####
Var file:
```
linuxbrew_home: "/home/linuxbrew"
linuxbrew_path: "/home/linuxbrew/.linuxbrew/bin/brew"
linuxbrew_packages:
-
    name: fontconfig
    version: 2.11.1_2
    path: https://raw.githubusercontent.com/Linuxbrew/homebrew-core/085b0d07f0f69cd8b1be0cacb53fabd5fda396b4/Formula/fontconfig.rb
-
    name: gettext
    version: 0.19.8.1
    path: https://raw.githubusercontent.com/Linuxbrew/homebrew-core/0dc3d51ccdee9966f0ff63f41cc0639ae7db10f2/Formula/gettext.rb
-
    name: libffi
    version: 3.0.13
    path: https://raw.githubusercontent.com/Linuxbrew/homebrew-core/10ad7546196022b6a621860f5e3311988e0a3be8/Formula/libffi.rb

```

Task file:
```
- name: Install linuxbrew packages
  linuxbrew: name="{{ item.name }}"
            version="{{ item.version }}"
            recipe="{{ item.path }}"
            state=present
            path="{{ linuxbrew_path }}"
  with_items: "{{ linuxbrew_packages }}"
  environment:
    PATH: "{{ linuxbrew_home }}/.linuxbrew/bin:{{ ansible_env.PATH }}"
  sudo: no
```

### Conda ###
In-house developed module used to install version-specific software packages, including reliable versioning of their dependencies. Also able to create and manage multiple Conda Virtual Environments for further reliability.

WIP ~thom