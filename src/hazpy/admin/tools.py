import os


def createSkeleton(toolName, directory):
    """ Creates a skeleton for HazPy tools
    """
    # format inputs
    if not directory.endswith('/'):
        directory += '/'
    toolName = toolName.replace(' ', '-')
    toolDirectory = directory + toolName + '/'
    srcDirectory = toolDirectory + 'src/'

    # make app directory
    os.mkdir(directory + toolName)

    # make root files
    # write tool entry point file
    with open(toolDirectory + toolName + '.py', 'a') as f:
        content = [
            "from subprocess import call",
            "try:",
            "    # check if the virtual environment has been created",
            "    virtual_env = 'hazus_env'",
            "    res = call('CALL conda.bat activate ' + virtual_env, shell=True)",
            "    if res == 1:",
            "        # create the virtual environment",
            "        from src.manage import createHazusEnvironment",
            "        createHazusEnvironment()",
            "    else:",
            "        call('CALL conda.bat activate hazus_env && start /min python src/app.py', shell=True)",
            "        call('CALL conda.bat activate hazus_env && start /min python src/update.py', shell=True)",
            "except:",
            "    import ctypes",
            "    import sys",
            "    messageBox = ctypes.windll.user32.MessageBoxW",
            "    messageBox(0, 'Unexpected error:' + sys.exc_info()[0] + ' | If this problem persists, contact hazus-support@riskmapcds.com.', 'HazPy', 0x1000)",
        ]
        for line in content:
            f.write(line + '\n')

    with open(toolDirectory + 'README.md', 'a') as f:
        content = [
            '# ' + toolName + '\n',
            '## Requirements \n',
            toolName + ' requires Anaconda to be installed on your computer. Anaconda is a free software that automatically manages all Python packages required to run Hazus open source tools - including the HazPy \n',
            '1. Go to https://www.anaconda.com/distribution/ \n',
            '2. Download Anaconda for Python 3 \n',
            '3. Complete the installation. During installation, make sure the following options are checked: \n',
            '   - [x] **Add Anaconda to my PATH environment variable**',
            '   - [x] Register Anaconda as my default Python'
            '## To Use \n',
            'Follow the steps below to run '+toolName+'. To ensure .py files run when double-clicked, right-click the .py file and go to Properties. Under the "General" tab next to "Opens With", make sure "python.exe" is selected. If not, click "Change" and select "python.exe" from your Python installation directory. \n',
            '**1. Download zip folder from GitHub, unzip.** \n',
            "**2. Double-click '+toolName+'.py. If you don't have the Hazus Python Library installed, follow the prompt to install, then double-click '+toolName+'.py again** \n"
            '## Contact \n',
            'For questions contact hazus-support@riskmapcds.com \n'
        ]
        for line in content:
            f.write(line + '\n')

    # make the src directory
    os.mkdir(srcDirectory)
    # make the assests directory
    os.mkdir(srcDirectory + 'assets')

    # make src directory files
    # make the init file
    with open(srcDirectory + '__init__.py', 'a') as f:
        content = [
            '"""',
            "   HazPy",
            "   ~~~~~",
            "    ",
            "   FEMA developed module for analzying risk and loss from natural hazards.",
            "   ",
            "   :copyright: 2019 by FEMA's Natural Hazards and Risk Assesment Program.",
            "   :license: cc, see LICENSE for more details.",
            "   :author: FirstName LastName; EmailAddress",
            '"""',
            "__version__ = '0.0.1'",
            "__all__ = ['']"
        ]
        for line in content:
            f.write(line + '\n')
    # make the app gui file
    with open(srcDirectory + 'app.py', 'a') as f:
        f.close()
    # make the config file
    with open(srcDirectory + 'config.json', 'a') as f:
        f.close()
    # make the manage file
    with open(srcDirectory + 'manage.py', 'a') as f:
        f.close()
    # make the update file
    with open(srcDirectory + 'update.py', 'a') as f:
        f.close()
