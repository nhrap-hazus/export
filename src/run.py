try:
    try:
        from manage import internetConnected, checkForHazusUpdates, checkForToolUpdates
    except:
        from src.manage import internetConnected, checkForHazusUpdates, checkForToolUpdates
    if internetConnected():
        checkForHazusUpdates()
        checkForToolUpdates()

    from subprocess import check_call
    try:
        check_call('conda activate hazus_env && python __main__.pyw', shell=True)
    except:
        check_call('activate hazus_env && python __main__.pyw', shell=True)
except:
    import ctypes
    messageBox = ctypes.windll.user32.MessageBoxW
    messageBox(0,"The tool was unable to open. You need internet connection for this tool to update. If this problem persists, contact hazus-support@riskmapcds.com","Hazus", 0x1000)