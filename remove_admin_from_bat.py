import os

bats = [x for x in os.listdir(os.getcwd()) if x.endswith('.bat')]

for bat in bats:
    file = open(bat, 'r')
    lines = [x for x in file]
    file.close()
    os.remove(bat)
    with open(bat, 'w+') as batWriter:
        for line in lines:
            batWriter.write(line)