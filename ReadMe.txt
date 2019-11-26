# Hazus Export Utility

The Hazus Export Utility summarizes Hazus risk assessment results stored on your desktop Hazus database in a handful of text files, shapefiles, and a one-page graphic report. Launch the tool by double-clicking the hazus-export-utility.bat file in the download folder.

## To Use

1. Download zip folder of tool from GitHub, unzip

2. Double-click "hazus-export-utility.bat"

3. If you don't have the Hazus Python Library installed, follow the prompt to install, then double-click "hazus-export-utility.bat" again

4. Select a scenario from those stored in your desktop Hazus database, listed in the drop-down menu

5. Name the report file - you will be able to change the report title later

6. Type important notes about your Hazus model run (inputs, date, settings, version, etc.) in the Metadata/Notes section - these are       required for sharing your data later!

7. Select the types of summaries you want - text files, shape files, a pdf report, and/or a json file

8. Select a folder location for exports and the report

## Requirements

The Hazus Export tool requires Hazus, ArcGIS Desktop, and Anaconda to be installed on your computer. Anaconda is a free software that automatically manages all Python packages required to run Hazus open source utilities - including the Hazus Python package: https://fema-nhrap.s3.amazonaws.com/Hazus/Python/build/html/index.html

1. Go to https://www.anaconda.com/distribution/

2. Download Anaconda for Python 3

3. Complete the installation. During installation, make sure the following options are checked:

    - [x] Add Anaconda to my PATH environment variable
    - [x] Register Anaconda as my default Python
    - [x] Install Anaconda for local user, rather than all users

## Documentation

Please refer to the files "EQDataDictionary", "TSDataDictionary", "FLDataDictionary", and "HUDataDictionary" for detailed information about the fields, values and units found in exported Hazus results data.

## Contact

Issues can be reported through the repository on Github (https://github.com/nhrap-hazus)

For questions contact FEMA-NHRAP@fema.dhs.gov
