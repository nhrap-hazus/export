from subprocess import call
call('CALL conda.bat activate hazus_env & start /min python src/run.py', shell=True)
