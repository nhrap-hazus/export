import json
from subprocess import call

try:
    # load config
    try:
        with open('./src/config.json') as configFile:
            config = json.load(configFile)
    except:
        with open('./config.json') as configFile:
            config = json.load(configFile)

    # check if the virtual environment has been created
    release = config['release']
    virtual_env = config[release]['virtualEnvironment']
    res = call('CALL conda.bat activate ' + virtual_env, shell=True)
    if res == 1:
        # create the virtual environment
        from src.manage import createHazPyEnvironment
        createHazPyEnvironment()
    else:
        call('CALL conda.bat activate '+virtual_env +
             ' && start /min python src/app.py', shell=True)
        # call('CALL conda.bat activate '+virtual_env +
        #      ' && start /min python src/update.py', shell=True)
except:
    import ctypes
    import sys
    messageBox = ctypes.windll.user32.MessageBoxW
    error = sys.exc_info()[0]
    try:
        messageBox(0, u"Unexpected error: {er} | If this problem persists, contact hazus-support@riskmapcds.com.".format(er=error), u"HazPy", 0x1000)
    except:
        messageBox(
            0, u"Unexpected error | If this problem persists, contact hazus-support@riskmapcds.com.", u"HazPy", 0x1000)
