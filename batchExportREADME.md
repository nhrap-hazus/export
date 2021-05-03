# Hazus Batch Export Tool

The Hazus Batch Export Tool is an extension of the Hazus Export Tool that is meant for running Export on multiple Hazus Package Region (HPR) files (Hazus exported Study Region) within a directory.

## Requirements

The Hazus Export tool requires Hazus, ArcGIS Desktop, and Anaconda to be installed on your computer. Anaconda is a free software that automatically manages all Python packages required to run Hazus open source tools - including the Hazus Python package: https://fema-nhrap.s3.amazonaws.com/Hazus/Python/build/html/index.html

1. Go to https://www.anaconda.com/distribution/

2. Download Anaconda for Python 3

3. Complete the installation. During installation, make sure the following options are checked:

   - [x] **Add Anaconda to my PATH environment variable**
   - [x] Register Anaconda as my default Python

4. Dwnload the zip folder of Export from GitHub and unzip it.

5. Run the Hazus Export Tool to install hazpy in the hazus_env Anaconda virtual environment (Read the README for the Hazus Export Tool on the steps)

## Documentation

For information about the fields, values and units found in exported Hazus results data, please refer to the guide sheets in the data-dictionaries folder: "EQDataDictionary", "TSDataDictionary", "FLDataDictionary", and "HUDataDictionary". https://github.com/nhrap-hazus/export/tree/master/data-dictionaries 

Table of possible Hazard/Scenario/Scenario Type/Return Period combinations:

|HPR / Study Region|Hazard|Scenario|Scenario Type|Return Period|
|---     |---   |---     |---          |---          |
|studyregion1|EQ|1: user defined name?|probabilistic|8: 100, 250, 500, 750, 1000, 1500, 2000, 2500|
|studyregion1|EQ|1: user defined name?|deterministic|1: user defined name?|
|studyregion1|FL|StudyCase: user defined name?|riverine|1 to many: user defined name?|
|studyregion1|FL|StudyCase: user defined name?|coastal|1 to many: user defined name?|
|studyregion1|FL|StudyCase: user defined name?|riverine & coastal|1 to many: user defined?|
|studyregion1|FL|StudyCase: user defined name?|surge|1: user defined name?|
|studyregion1|HU|1: user defined name?|probabilistic|7: 10, 20, 50, 100, 200, 500, 1000|
|studyregion1|HU|1: user defined name?|deterministic|1: user defined name?|
|studyregion1|TS|1: user defined name?|n/a|n/a|

Average Annualized Loss: ?

## Contact

Issues can be reported through the repository on Github (https://github.com/nhrap-hazus/export)

For questions contact fema-hazus-support@fema.dhs.gov

## To Use

Follow the steps below to run FAST. To ensure .py files run when double-clicked, right-click the .py file and go to Properties. Under the "General" tab next to "Opens With", make sure "python.exe" is selected. If not, click "Change" and select "python.exe" from your Python installation directory.

**1. In the Export/python_env folder there is a python file named batchExport, open it and modify the User Defined Variables**
    
    Modify the directory path containing the HPR files to batch export
    
    Modify the directory path for the output of the batch export

**2. Open Anaconda desktop and select the 'hazus_env' environment**

**3. 'Open Terminal' from 'hazus_env'**

**4. In the hazus_env terminal change directory to the location you've downloaded the export tool to**

    type: 'cd C:/mydownloads/export/Python_env' into the terminal and hit enter

**5. In the terminal run the batchExport.py script**
    
    type: 'python batchExport.py'


