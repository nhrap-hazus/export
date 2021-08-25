from subprocess import call

import os
import requests

# Check if user is on FEMA domain
domain = os.popen('whoami').read().split('\\')[0]
# Set proxy for FEMA users
if domain == 'fema':
    fema_proxy = "http://proxy.apps.dhs.gov:80"
    http_proxy = "http://proxy.apps.dhs.gov:80"
    https_proxy = "http://proxy.apps.dhs.gov:80"
else:
    http_proxy = ''
    https_proxy = ''

proxy_dict = {
    "http": http_proxy,
    "https": https_proxy
}

# Download miniforge to %USERPROFILE%\Downloads
print('downloading miniforge...')
download_location = os.path.join(os.environ['USERPROFILE'], 'downloads')
url = 'https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Windows-x86_64.exe'
data = requests.get(url, allow_redirects=True, proxies=proxy_dict)
filename = os.path.join(download_location, 'Miniforge3-Windows-x86_64.exe')
with open(filename, 'wb') as file:
    file.write(data.content)

# Run miniforge installation
print('installing miniforge...')
# Silent Install Miniforge and add to PATH
mf_dir = os.path.join(os.environ['USERPROFILE'], 'miniforge3')
command = 'start /wait {} /InstallationType=JustMe /RegisterPython=1 /AddToPath=1 /S /D={}'.format(
    filename, mf_dir)
call(command, shell=True)

# Remove Downloaded File
os.remove(filename)
print('miniforge is now installed. Please close and reopen the terminal for changes to take affect.')
