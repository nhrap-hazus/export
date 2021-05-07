# Hazus Batch Export Tool

The Hazus Batch Export Tool is an extension of the Hazus Export Tool that is meant for running Export on multiple Hazus Package Region (HPR) files 
(Hazus exported Study Region) within a directory. 

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

For information about the fields, values and units found in exported Hazus results data, please refer to the guide sheets in the data-dictionaries 
folder: "EQDataDictionary", "TSDataDictionary", "FLDataDictionary", and "HUDataDictionary". https://github.com/nhrap-hazus/export/tree/master/data-dictionaries 

**Hazus HPR Version Support:**

The batchExport script has been tested on HPR created by Hazus 3.1 and up. Hazus 2.1 created HPR and lower will likely fail. 
For HPR versions lower than 3.1 you could try using Hazus 4.2.3 or 5 to import the older HPR so that Hazus will update it 
and then export it to a new HPR.

There is a script in python_env that can be used to look in a directory and subdirectory for HPR files and read out what version of Hazus they
were created by. It will also notify if the HPR is not a valid zipfile and would thus fail to be run in the batchExport script.

**Hazus Loss Library (HLL) Metadata:**

There are three csv files named 'Analysis.csv', 'Download.csv', and 'Event.csv' that should exist in the batchExport output folder 
for each HPR file/StudyRegion.

HLL uses field validation for data types and fields with choices (e.g. hazard, analysisType), but for fields like source, any string will do.
Therefore if it says "FIX ME: USER INPUT NEEDED", it is possible to upload it like that.

Event.csv

* If the even is historic then it should have a value in the date field in YYYY-MM-DD.

Analysis.csv

* You can change the 'name' field to change what HLL displays.
* You can change the 'analysisType' to historic, deterministic or probabilistic.
* The 'date' refers to the date of the scenario analysis.
* You can change 'modifiedInventory' to true or false.

Download.csv

* You can add a url to the 'link' field for a row and HLL button for that item will open the link instead of the file.

**Renaming Study Regions and Scenarios:**

To rename the Study Region you can open the 'Event.csv' and modify the value in the 'name' field.

To rename the Scenario you can open the 'Analysis.csv' and modify the value in the 'name' field.

**Script Failure:**

If the script fails without dropping the bk_* (where * is the name of the hpr file or its .bk sql server backup database) database then you 
will need to do it manually. Using SQL Server Management Studio you can DELETE the bk_* database and using Windows explorer you can delete 
the temp folder that contains the unzipped contents of the HPR file.

**More Work To Be Done:**
- [ ] HLL Metadata (analysisType, date, and modifiedInventory fields)
- [ ] Event|HPR|SR boundary geojson output
- [ ] Analysis|Scenario|Studycase boundary geojson output
- [ ] More testing for EQ, HU, TS perils
- [ ] EQ impact area and hazard boundary output
- [ ] HU impact area and hazard boundary output
- [ ] TS hazard boundary output
- [ ] Fix potential hazus version lookup error if the hazus version does not exist in the set list
- [ ] Better script launch steps, i.e. double click one python file to run instead of Anaconda hazus_env terminal.

**Table of Possible Hazard/Scenario/Scenario Type/Return Period Combinations (NOT YET COMPLETE):**

|HPR / Study Region|Hazard|Scenario|Scenario Type|Return Period|
|---     |---   |---     |---          |---          |
|studyregion1|EQ|1: user defined name?|probabilistic|8: 100, 250, 500, 750, 1000, 1500, 2000, 2500|
|studyregion1|EQ|1: user defined name?|deterministic|1: user defined name?|
|studyregion1|FL|1+: StudyCase: user defined name?|riverine|1+: user defined name?|
|studyregion1|FL|1+: StudyCase: user defined name?|coastal|1+: user defined name?|
|studyregion1|FL|1+: StudyCase: user defined name?|riverine & coastal|1+: user defined name?|
|studyregion1|FL|1: StudyCase: user defined name?|surge|1: user defined name?|
|studyregion1|HU|1: user defined name?|probabilistic|7: 10, 20, 50, 100, 200, 500, 1000|
|studyregion1|HU|1: user defined name?|deterministic|1: user defined name?|
|studyregion1|TS|1: user defined name?|n/a|n/a|

Average Annualized Loss: ?

## Contact

Issues can be reported through the repository on Github (https://github.com/nhrap-hazus/export)

For questions contact fema-hazus-support@fema.dhs.gov

## To Use

**PART 1: Get the export code**

1. Download and unzip the "export-Feature-BatchExport" Code from https://github.com/nhrap-dev/export/tree/Feature-BatchExport

**PART 2: Get the hazpy code**

1. Download and unzip "hazpy-Feature-BatchExport" Code from https://github.com/nhrap-dev/hazpy/tree/Feature-BatchExport

2. In the unzipped "export-Feature-BatchExport", in the "export\Python_env" directory, copy the python script named 'batchExport.py'.

    For Example: "C:\Users\Clindeman\Downloads\export-Feature-BatchExport\export-Feature-BatchExport\Python_env"

3. Paste the python script 'batchExport.py' into the unzipped "hazpy-Feature-BatchExport" folder.

    For Example: "C:\Users\Clindeman\Downloads\hazpy-Feature-BatchExport\hazpy-Feature-BatchExport"

This allows the batchExport.py script to import the hazpy code in the directory it resides instead of the hazpy from hazus_env, however the
third party libraries in hazus_env are still required for batchExport.

**PART 3: Run the batchExport code in hazus_env python**

1. Open the python file named "batchExport.py" in the "hazpy-Feature-BatchExport" folder and modify the User Defined Variables:
    
   Modify the directory path containing the HPR files you want to batch export:

        hprDir = r'C:/workspace/hpr'               #The directory containing hpr files 
    
   Modify the directory path for the batchExport output to where you want them to be saved to:
    
        outDir = r'C:/workspace/batchexportOutput' #The directory for the output files 

   You can also modify the return periods directory name if you want to change the 'STAGE_' prefix by modifying it or deleting it:
    
        exportPath = Path.joinpath(Path(outputPath), str(hazard['Hazard']).strip(), str(scenario['ScenarioName']).strip(), 'STAGE_' + str(returnPeriod).strip()) 

2. Open Anaconda desktop and select the 'hazus_env' environment

![Anaconda hazus_env terminal](Images/BatchExport_Select_hazus_env.png "Anaconda hazus_env terminal")

3. 'Open Terminal' from 'hazus_env'

![Anaconda hazus_env terminal](Images/BatchExport_OpenTerminal.png "Anaconda hazus_env terminal")

4. In the hazus_env terminal, change the current working directory to the directory you've unzipped the "hazpy-Feature-BatchExport" to:

Type the following into the terminal and hit enter: 
    
    'cd C:/mydownloads/export/Python_env' 

5. In the terminal run the "batchExport.py" script:
    
Type the following into the terminal and hit enter: 

    'python batchExport.py'

It's recommended that if you want to rerun an HPR that you should delete or rename the previous run's output folder for that HPR. 

**PART 4: Update the Hazus Loss Library (HLL) Metadata**

1. Look for and replace the 'FIX ME' values in the field values in the 'Event.csv', 'Analysis.csv' and 'Downloads.csv' 
files in the output folder for each HPR