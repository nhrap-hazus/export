from subprocess import check_output, check_call, call, Popen
import os
import ctypes

def setProxyEnv():
    newEnv = os.environ.copy()
    newEnv["HTTP_PROXY"] = 'http://proxy.apps.dhs.gov:80'
    newEnv["HTTPS_PROXY"] = 'http://proxy.apps.dhs.gov:80'
    return newEnv

def installHazus():
    output = check_output('conda list')
    packages = list(map(lambda x: x.split(' ')[0], str(output).split('\\r\\n')))
    if not 'hazus' in packages:
        messageBox = ctypes.windll.user32.MessageBoxW
        returnValue = messageBox(None,"The Hazus Python package was not found on your computer and is required to run this tool. Would you like to install it now?","Hazus",0x40 | 0x1)
        if returnValue == 1:
            import os
            # messageBox = ctypes.windll.user32.MessageBoxW
            # returnValue = messageBox(None,"Good job pinochio","Hazus",0x40 | 0x1)
            output = check_output('conda config --show channels')
            channels = list(map(lambda x: x.strip(), str(output).replace('\\r\\n', '').split('-')))[1:]
            if not 'anaconda' in channels:
                call('conda config --add channels anaconda')
                print('anaconda channel added')
            if not 'conda' in channels and not 'forge' in channels:
                call('conda config --add channels conda-forge')
                print('conda-forge channel added')
            ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 1)
            print('Installing Hazus, please wait...')
            try:
                try:
                    check_call('echo y | conda install -c nhrap hazus', shell=True)
                    messageBox(None,"The Hazus Python package was successfully installed. Please reopen the utility.","Hazus", 0)
                except:
                    print('Adding proxies and retrying...')
                    proxyEnv = setProxyEnv()
                    check_call('echo y | conda install -c nhrap hazus', shell=True, env=proxyEnv)
                    messageBox(None,"The Hazus Python package was successfully installed. Please reopen the utility.","Hazus", 0)
            except:
                messageBox(None,"An error occured. The Hazus Python package was not installed. Please check your network settings and try again.","Hazus", 0)

def upgrade():
    call('echo y | pip uninstall hazus', shell=True)
    call('echo y | pip install hazus', shell=True)


"""
conda config --remove channels anaconda
conda config --remove channels conda-forge
"""