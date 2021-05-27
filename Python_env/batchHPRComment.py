"""
May 2021 Colin Lindeman clindeman@niyamit.com, colinlindeman@gmail.com
Helper script to list all hpr files and their hazus version.
"""
#IMPORTS
import zipfile
from pathlib import Path

#USER INPUT
hprDir = r'C:\HazusHPR'

#HAZUS Version Decoder Function
def getHPRHazusVersion(hprComment):
        versionLookupDict = { '060606':'Hazus MR1  '
                             ,'070707':'Hazus MR2  '
                             ,'080808':'Hazus MR3  '
                             ,'090909':'Hazus MR4  '
                             ,'101010':'Hazus MR5  '
                             ,'111111':'Hazus 2.0  '
                             ,'121212':'Hazus 2.1  '
                             ,'131313':'Hazus 3.0  '
                             ,'141414':'Hazus 3.1  '
                             ,'151515':'Hazus 4.0  '
                             ,'161616':'Hazus 4.1  '
                             ,'171717':'Hazus 4.2  '
                             ,'181818':'Hazus 4.2.1'
                             ,'191919':'Hazus 4.2.2'
                             ,'202020':'Hazus 4.2.3'
                             ,'212121':'Hazus 5.0  '}
        commentVersion = hprComment[1]
        if commentVersion in versionLookupDict:
            hprHazusVersion = versionLookupDict[commentVersion]
            return hprHazusVersion
        else:
            print(f'{hprComment[1]} not in Hazus version list.')

#MAIN PART OF SCRIPT
fileExt = r'**/*.hpr'
hprList = list(Path(hprDir).glob(fileExt))

for hpr in hprList:
    try:
        z = zipfile.ZipFile(hpr)
        zComment = z.comment.decode('UTF-8').split('|')
        print(getHPRHazusVersion(zComment), hpr)
    except Exception as e:
        print(f'Exception! {hpr}')
        print(' ',e)
