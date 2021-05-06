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
|studyregion1|FL|StudyCase: user defined name?|riverine|1+: user defined name?|
|studyregion1|FL|StudyCase: user defined name?|coastal|1+: user defined name?|
|studyregion1|FL|StudyCase: user defined name?|riverine & coastal|1+: user defined name?|
|studyregion1|FL|StudyCase: user defined name?|surge|1: user defined name?|
|studyregion1|HU|1: user defined name?|probabilistic|7: 10, 20, 50, 100, 200, 500, 1000|
|studyregion1|HU|1: user defined name?|deterministic|1: user defined name?|
|studyregion1|TS|1: user defined name?|n/a|n/a|

Average Annualized Loss: ?

## Contact

Issues can be reported through the repository on Github (https://github.com/nhrap-hazus/export)

For questions contact fema-hazus-support@fema.dhs.gov

## To Use

**PART 1**

**1. Download and unzip the "export-Feature-BatchExport" Code from https://github.com/nhrap-dev/export/tree/Feature-BatchExport**

**PART 2**

**1. Download and unzip "hazpy-Feature-BatchExport" Code from https://github.com/nhrap-dev/hazpy/tree/Feature-BatchExport**

**2. In the unzipped "export-Feature-BatchExport", in the "export\Python_env" directory, copy the python script named 'batchExport.py'.**

    For Example: "C:\Users\Clindeman\Downloads\export-Feature-BatchExport\export-Feature-BatchExport\Python_env"

**3. Paste the python script 'batchExport.py' into the unzipped "hazpy-Feature-BatchExport" folder.**

    For Example: "C:\Users\Clindeman\Downloads\hazpy-Feature-BatchExport\hazpy-Feature-BatchExport"

**PART 3**

**1. Open the python file named "batchExport.py" in the "hazpy-Feature-BatchExport" folder and modify the User Defined Variables:**
    
   Modify the directory path containing the HPR files you want to batch export:

    hprDir = r'C:/workspace/hpr'               #The directory containing hpr files 
    
   Modify the directory path for the batchExport output to where you want them to be saved to:
    
    outDir = r'C:/workspace/batchexportOutput' #The directory for the output files 

**2. Open Anaconda desktop and select the 'hazus_env' environment**

![Anaconda hazus_env terminal](Images/BatchExport_Select_hazus_env.png "Anaconda hazus_env terminal")

**3. 'Open Terminal' from 'hazus_env'**

![Anaconda hazus_env terminal](Images/BatchExport_OpenTerminal.png "Anaconda hazus_env terminal")

**4. In the hazus_env terminal, change the current working directory to the directory you've unzipped the "hazpy-Feature-BatchExport" to:**

Type the following into the terminal and hit enter: 
    
    'cd C:/mydownloads/export/Python_env' 

**5. In the terminal run the "batchExport.py" script:**
    
Type the following into the terminal and hit enter: 

    'python batchExport.py'


