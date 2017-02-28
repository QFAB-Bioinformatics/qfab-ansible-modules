# To Do #
## Linuxbrew ##
* Changes Logic
    * On init: check that `package`, `version`, and `recipe` arrays are equal length and valid
    * States switching:
        * present:  check that module/version exists, unlink other versions, install
        * absent:   check that module/version exists, remove only that version
        * linked:   check if version is not None: add version check, add parameter to link code
        * unlinked: check if version is not None: add version check, add parameter to unlink code
        * head:     ignore version, install latest HEAD commit
        * latest:   ignore version, install latest brew recipe


## Conda ##
* Finish local code, test, commit
    * while bugs > Math.min(tolerable_bugs): code; test; fix; done;