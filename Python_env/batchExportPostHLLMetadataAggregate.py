"""April 2021 Colin Lindeman, clindeman@niyamit.com, colinlindeman@gmail.com

Requirements: Python 3, Hazpy 0.0.1, Anaconda with hazus_env installed

Recursively finds .hpr files in input folder (and subdirectories).

How to use: Define your input folder containing hpr files and define
            an output folder to export the results and files to. This
            must be run from the python from the Anaconda virtual
            environment named hazus_env that is installed when the regular
            export tool is run.

            Start by going to the bottom of this script
            to change the user inputs, then open a terminal in anaconda
            hazus_env, navigate to this scripts directory, activate
            python in the terminal and run this script.

"""

from pathlib import Path
import os
import pandas as pd
import uuid
import sys


def aggregateHllMetadataFiles(directory):
    """This tool crawls a directory and subdirectory for hll metadata files and
    aggregates them into one at the root level.
    
    Keyword Arguments:
        directory: str -- a batchExport root directory

    Notes:
        The path should be the root folder containing all the exported hpr folder.
        'Event.csv','Analysis.csv','Download.csv'. Wath out for the relative path in
        the hll metadata.
    """
    print(directory) #user defined outputdir
    try:
        df = pd.concat(map(pd.read_csv, list(Path(directory).glob('**/Event.csv'))))
        df.to_csv(str(Path.joinpath(Path(directory), "Event.csv")), index=False)
    except Exception as e:
        print('Unexpected error aggregating HLL Metadata')
        print(e)
    try:
        df = pd.concat(map(pd.read_csv, list(Path(directory).glob('**/Analysis.csv'))))
        df.to_csv(str(Path.joinpath(Path(directory), "Analysis.csv")), index=False)
    except Exception as e:
        print('Unexpected error aggregating HLL Metadata')
        print(e)
    try:
        df = pd.concat(map(pd.read_csv, list(Path(directory).glob('**/Download.csv'))))
        #df['file'] = str(Path(directory).name) + df['file'].astype(str)
        df.to_csv(str(Path.joinpath(Path(directory), "Download.csv")), index=False)
    except Exception as e:
        print('Unexpected error aggregating HLL Metadata')
        print(e)
        
if __name__ == '__main__':
    #USER DEFINED VALUES
    Dir = r'C:\workspace\batchexportOutput\New folder' #The directory containing hpr files

    print('Aggregating HLL Metadata...')
    aggregateHllMetadataFiles(Dir)
    print('Done.')
    
    print()
        
