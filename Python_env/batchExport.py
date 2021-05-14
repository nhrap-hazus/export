"""April 2021 Colin Lindeman, clindeman@niyamit.com, colinlindeman@gmail.com

Requirements: Python 3, Hazpy 0.0.1, Anaconda with hazus_env installed

Works for USGS FIM Flood HPR files.

How to use: Define your input folder containing hpr files and define
            an output folder to export the results and files to. This
            must be run from the python from the Anaconda virtual
            environment named hazus_env that is installed when the regular
            export tool is run.

            Start by going to the bottom of this script
            to change the user inputs, then open a terminal in anaconda
            hazus_env, navigate to this scripts directory, activate
            python in theh terminal and run this script.

"""

from hazpy.legacy import HazusPackageRegion
from pathlib import Path
import os
import pandas as pd
import uuid
import sys


def getflAnalysisLogDate(logfile):
    """Find the date of analysis from the flAnalysisLog.txt

        Key Argument:
            logfile: string -- the path to the logfie
        Returns:
            analysisLogDate: string -- The date the flAnalysisLog was created in YYYY-MM-DD
        Notes:
            1st Line of flAnalysisLog.txt:
            2021/04/20 11:49:28.227 File: "C:\HazusData\Regions\nora\nora_08\\flAnalysisLog.txt" created on-the-fly from MSSQL
            
    """
    try:
        file = open(logfile, 'r')
        analysisLogDate = file.readline()[0:10].replace('/','-')
        return analysisLogDate
    except Exception as e:
        print('Unexpected error getflAnalysisLogDate')
        print(e)
        return 'YYYY-MM-DD'

def exportHPR(hprFile, outputDir, deleteDB=1, deleteTempDir=1):
    """This tool will use hazpy.legacy.hazuspackagregion to batch export
        hpr files in a directory to a user specified output directory.
        

        Keyword Arguments:
                hprFile: str -- a directory path containing hpr files
            outputDir: str -- a directory to write export files to

        Notes: The hazpy legacy code has only been tested against USGS FIM
            Flood HPR files. It does not process HPR files in subdirectories
            of the main directory.
            
    """
    hpr = HazusPackageRegion(hprFilePath=hprFile, outputDir=outputDir)

    print(f"User Defined hprFilePath: {hpr.hprFilePath}") #debug
    print(f"User Defined outputDir = {hpr.outputDir}") #debug
    print(f"tempDir = {hpr.tempDir}") #debug
    print(f"hpr zipfile comment: {hpr.hprComment}") #debug
    print(f"Hazus Version: {hpr.HazusVersion}") #debug
    print(f"Available Hazards: {hpr.Hazards}") #debug
    print()

    try:
        hpr.restoreHPR()
    except Exception as e:
        print(e)

    hpr.getHazardsScenariosReturnPeriods()
    print(hpr.HazardsScenariosReturnPeriods) #debug

    #CREATE A DIRECTORY FOR THE OUTPUT FOLDERS...
    outputPath = hpr.outputDir
    if not os.path.exists(outputPath):
        os.mkdir(outputPath)
                
    #CREATE HAZUS LOSS LIBRARY (HLL) METADATA TABLES...
    hllMetadataEvent = pd.DataFrame(columns=['id',
                                             'name',
                                             'geom',
                                             'date',
                                             'image'])

    hllMetadataScenario = pd.DataFrame(columns=['id',
                                                'name',
                                                'hazard',
                                                'analysisType',
                                                'date',
                                                'source',
                                                'modifiedInventory',
                                                'geographicCount',
                                                'geographicUnit',
                                                'losses',
                                                'lossesUnit',
                                                'meta',
                                                'event',
                                                'geom'])

    hllMetadataDownload = pd.DataFrame(columns=['id',
                                                'category',
                                                'subcategory',
                                                'name',
                                                'icon',
                                                'link',
                                                'file',
                                                'meta',
                                                'analysis'])


    #ITERATE OVER THE HAZARD, SCENARIO, RETURNPERIOD AVAIALABLE COMBINATIONS...
    for hazard in hpr.HazardsScenariosReturnPeriods:
        print(f"Hazard: {hazard['Hazard']}") #debug
        
        #SET HPR HAZARD...
        hpr.hazard = hazard['Hazard']

        #EXPORT Hazus Package Region TO GeoJSON...
        exportPath = Path.joinpath(Path(outputPath))
        try:
            print('Writing StudyRegionBoundary to geojson...')
            hzBoundary = hpr.getHzBoundary()
            hzBoundary.toGeoJSON(Path.joinpath(exportPath, 'StudyRegionBoundary.geojson'))
        except Exception as e:
            print('StudyRegionBoundary not available to export to geojson')
            print(e)

        #Event metadata...
        #ADD ROW TO hllMetadataEvent TABLE...
        hazardUUID = uuid.uuid4()
        filePath = Path.joinpath(exportPath, 'StudyRegionBoundary.geojson')
        #filePathRel = str(filePath.relative_to(Path(hpr.outputDir))) #excludes sr name; for non-aggregate hll metadata
        filePathRel = str(filePath.relative_to(Path(hpr.outputDir).parent)) #includes SR name; for aggregate hll metadata
        #need to add path to hazard boundary (is this unique for each returnperiod/download in FIMS?)
        hllMetadataEvent = hllMetadataEvent.append({'id':hazardUUID,
                                                    'name':hpr.dbName,
                                                    'geom':filePathRel}, ignore_index=True)

        #SCENARIOS/ANALYSIS
        for scenario in hazard['Scenarios']:
            print(f"Scenario: {scenario['ScenarioName']}") #debug

            #SET HPR SCENARIO...
            hpr.scenario = scenario['ScenarioName']

            #Analysis Metadata part one of two...
            scenarioUUID = uuid.uuid4()
            scenarioMETA = {"Hazus Version":f"{hpr.HazusVersion}"}
            scenarioGEOM = '' #initialize variable to be set later
            
            if hazard['Hazard'] == 'flood':
                analysisType = 'Deterministic' #USGSFIM
                """i.e. 'C:\workspace\batchexportOutput\nora\nora_08\\flAnalysisLog.txt'"""
                logfile = Path.joinpath(Path(hpr.tempDir), scenario['ScenarioName'],'flAnalysisLog.txt')
                analysisDate = getflAnalysisLogDate(logfile)
            elif hazard['Hazard'] == 'earthquake':
                scenarioMETA["Magnitude"] = hpr.getEarthquakeMagnitude()
                analysisType = hpr.getAnalysisType()
                if analysisType in ['Shakemap', 'Scenario']:
                    scenarioMETA["ShakemapUrl"] = hpr.getEarthquakeShakemapUrl()
                analysisDate = hpr.getHPRFileDateTime(hpr.hprFilePath, 'AnalysisLog.txt')
            else:
                analysisDate = 'FIX ME (YYYY-MM-DD)', #YYYY-MM-DD

            #RETURNPERIODS/DOWNLOAD
            for returnPeriod in scenario['ReturnPeriods']:
                print(f"returnPeriod: {returnPeriod}") #debug

                #SET HPR RETURNPERIOD...
                hpr.returnPeriod = returnPeriod
                print(f"hazard = {hpr.hazard}, scenario = {hpr.scenario}, returnPeriod = {hpr.returnPeriod}") #debug

                #Downloads Metadata
                #For shakemap https://earthquake.usgs.gov/scenarios/eventpage/{shakemapID}/executive

                #GET BULK OF RESULTS...
                try:
                    print('Get bulk of results...')
                    results = hpr.getResults()
                    essentialFacilities = hpr.getEssentialFacilities()
                    if len(results) < 1:
                        print('No results found. Please check your Hazus Package Region and try again.')
                except Exception as e:
                    print(e)

                #CREATE A DIRECTORY FOR THE OUTPUT FOLDERS...
                if hazard['Hazard'] == 'earthquake' and analysisType in ['Shakemap', 'Scenario']:
                    #Deterministic;Shakemap;Scenario
                    exportPath = Path.joinpath(Path(outputPath), str(hazard['Hazard']).strip(), str(scenario['ScenarioName']).strip()) 
                elif hazard['Hazard'] == 'earthquake' and analysisType in ['Probabilistic']:
                    #Probabilistic
                    exportPath = Path.joinpath(Path(outputPath), str(hazard['Hazard']).strip(), str(scenario['ScenarioName']).strip(), str(returnPeriod).strip()) 
                elif hazard['Hazard'] == 'flood':
                    #USGS FIM Deterministic
                    exportPath = Path.joinpath(Path(outputPath), str(hazard['Hazard']).strip(), str(scenario['ScenarioName']).strip(), 'STAGE_' + str(returnPeriod).strip())
                elif hazard['Hazard'] == 'hurricane' and analysisType in ['Deterministic']:
                    #Deterministic
                    exportPath = Path.joinpath(Path(outputPath), str(hazard['Hazard']).strip(), str(scenario['ScenarioName']).strip()) 
                elif hazard['Hazard'] == 'hurricane' and analysisType in ['Probabilistic']:
                    #Probabilistic
                    exportPath = Path.joinpath(Path(outputPath), str(hazard['Hazard']).strip(), str(scenario['ScenarioName']).strip(), str(returnPeriod).strip()) 
                elif hazard['Hazard'] == 'tsunami':
                    exportPath = Path.joinpath(Path(outputPath), str(hazard['Hazard']).strip(), str(scenario['ScenarioName']).strip())
                else:
                    exportPath = Path.joinpath(Path(outputPath), str(hazard['Hazard']).strip(), str(scenario['ScenarioName']).strip(), str(returnPeriod).strip()) 
                Path(exportPath).mkdir(parents=True, exist_ok=True) #this may make the earlier HPR dir creation redundant

                #EXPORT Hazus Package Region TO CSV...
                try:
                    try:
                        print('Writing results to csv...')
                        results.toCSV(Path.joinpath(exportPath, 'results.csv'))
                        #ADD ROW TO hllMetadataDownload TABLE...
                        downloadUUID = uuid.uuid4()
                        filePath = Path.joinpath(exportPath, 'results.csv')
                        #filePathRel = str(filePath.relative_to(Path(hpr.outputDir))) #excludes sr name; for non-aggregate hll metadata
                        filePathRel = str(filePath.relative_to(Path(hpr.outputDir).parent)) #includes SR name; for aggregate hll metadata
                        hllMetadataDownload = hllMetadataDownload.append({'id':downloadUUID,
                                                                          'category':returnPeriod,
                                                                          'subcategory':'Results',
                                                                          'name':'Results.csv',
                                                                          'icon':'spreadsheet',
                                                                          'file':filePathRel,
                                                                          'analysis':scenarioUUID}, ignore_index=True)
                    except Exception as e:
                        print('Base results not available to export to csv...')
                        print(e)
                        
                    try:
                        print('Writing building damage by occupancy to CSV')
                        buildingDamageByOccupancy = hpr.getBuildingDamageByOccupancy()
                        buildingDamageByOccupancy.toCSV(Path.joinpath(exportPath, 'building_damage_by_occupancy.csv'))
                        #ADD ROW TO hllMetadataDownload TABLE...
                        downloadUUID = uuid.uuid4()
                        filePath = Path.joinpath(exportPath, 'building_damage_by_occupancy.csv')
                        #filePathRel = str(filePath.relative_to(Path(hpr.outputDir))) #excludes sr name; for non-aggregate hll metadata
                        filePathRel = str(filePath.relative_to(Path(hpr.outputDir).parent)) #includes SR name; for aggregate hll metadata
                        hllMetadataDownload = hllMetadataDownload.append({'id':downloadUUID,
                                                                          'category':returnPeriod,
                                                                          'subcategory':'Building Damage',
                                                                          'name':'Building Damage by Occupancy.csv',
                                                                          'icon':'spreadsheet',
                                                                          'file':filePathRel,
                                                                          'analysis':scenarioUUID}, ignore_index=True)
                    except Exception as e:
                        print('Building damage by occupancy not available to export to csv...')
                        print(e)
                        
                    try:
                        print('Writing building damage by type to CSV')
                        buildingDamageByType = hpr.getBuildingDamageByType()
                        buildingDamageByType.toCSV(Path.joinpath(exportPath,'building_damage_by_type.csv'))
                        #ADD ROW TO hllMetadataDownload TABLE...
                        downloadUUID = uuid.uuid4()
                        filePath = Path.joinpath(exportPath, 'building_damage_by_type.csv')
                        #filePathRel = str(filePath.relative_to(Path(hpr.outputDir))) #excludes sr name; for non-aggregate hll metadata
                        filePathRel = str(filePath.relative_to(Path(hpr.outputDir).parent)) #includes SR name; for aggregate hll metadata
                        hllMetadataDownload = hllMetadataDownload.append({'id':downloadUUID,
                                                                          'category':returnPeriod,
                                                                          'subcategory':'Building Damage',
                                                                          'name':'Building Damage by Type.csv',
                                                                          'icon':'spreadsheet',
                                                                          'file':filePathRel,
                                                                          'analysis':scenarioUUID}, ignore_index=True)
                    except Exception as e:
                        print('Building damage by type not available to export to csv...')
                        print(e)
                        
                    try:
                        print('Writing damaged facilities to CSV')
                        essentialFacilities.toCSV(Path.joinpath(exportPath, 'damaged_facilities.csv'))
                        #ADD ROW TO hllMetadataDownload TABLE...
                        downloadUUID = uuid.uuid4()
                        filePath = Path.joinpath(exportPath, 'damaged_facilities.csv')
                        #filePathRel = str(filePath.relative_to(Path(hpr.outputDir))) #excludes sr name; for non-aggregate hll metadata
                        filePathRel = str(filePath.relative_to(Path(hpr.outputDir).parent)) #includes SR name; for aggregate hll metadata
                        hllMetadataDownload = hllMetadataDownload.append({'id':downloadUUID,
                                                                          'category':returnPeriod,
                                                                          'subcategory':'Damaged Facilities',
                                                                          'name':'Damaged Facilities.csv',
                                                                          'icon':'spreadsheet',
                                                                          'file':filePathRel,
                                                                          'analysis':scenarioUUID}, ignore_index=True)
                    except Exception as e:
                        print('Damaged facilities not available to export to csv.')
                        print(e)
                        
                    if hpr.hazard == 'earthquake':
                        try:
                            print('Writing eqShakeMapScenario to CSV')
                            EQShakeMapScenario = hpr.getEQShakeMapScenario()
                            EQShakeMapScenario.toCSV(Path.joinpath(exportPath, 'ShakeMap_Scenario.csv'))
                            #ADD ROW TO hllMetadataDownload TABLE...
                            downloadUUID = uuid.uuid4()
                            filePath = Path.joinpath(exportPath, 'ShakeMap_Scenario.csv')
                            #filePathRel = str(filePath.relative_to(Path(hpr.outputDir))) #excludes sr name; for non-aggregate hll metadata
                            filePathRel = str(filePath.relative_to(Path(hpr.outputDir).parent)) #includes SR name; for aggregate hll metadata
                            hllMetadataDownload = hllMetadataDownload.append({'id':downloadUUID,
                                                                              'category':returnPeriod,
                                                                              'subcategory':'ShakeMap Scenario',
                                                                              'name':'ShakeMap Scenario.csv',
                                                                              'icon':'spreadsheet',
                                                                              'file':filePathRel,
                                                                              'analysis':scenarioUUID}, ignore_index=True)
                        except Exception as e:
                            print('eqShakeMapScenario not available to export to csv.')
                            print(e)

                    
                except Exception as e:
                    print('Unexpected error exporting CSVs')
                    print(e)
                        
                #EXPORT Hazus Package Region TO Shapefile...
                try:
                    try:
                        print('Writing results to shapefile to zipfile...')
                        results.toShapefiletoZipFile(Path.joinpath(exportPath, 'results.shp'), 'epsg:4326', 'epsg:4326')
                        #ADD ROW TO hllMetadataDownload TABLE...
                        downloadUUID = uuid.uuid4()
                        filePath = Path.joinpath(exportPath, 'results.zip')
                        #filePathRel = str(filePath.relative_to(Path(hpr.outputDir))) #excludes sr name; for non-aggregate hll metadata
                        filePathRel = str(filePath.relative_to(Path(hpr.outputDir).parent)) #includes SR name; for aggregate hll metadata
                        hllMetadataDownload = hllMetadataDownload.append({'id':downloadUUID,
                                                                          'category':returnPeriod,
                                                                          'subcategory':'Results',
                                                                          'name':'Results.shp',
                                                                          'icon':'spatial',
                                                                          'file':filePathRel,
                                                                          'analysis':scenarioUUID}, ignore_index=True)
                    except Exception as e:
                        #print('Base results not available to export to shapefile...')
                        print('Base results not available to export to shapefile to zipfile...')
                        print(e)
                        
                    try:
                        print('Writing Damaged facilities to shapefile to zipfile.')
                        essentialFacilities.toShapefiletoZipFile(Path.joinpath(exportPath, 'damaged_facilities.shp'), 'epsg:4326', 'epsg:4326')
                        #ADD ROW TO hllMetadataDownload TABLE...
                        downloadUUID = uuid.uuid4()
                        filePath = Path.joinpath(exportPath, 'damaged_facilities.zip')
                        #filePathRel = str(filePath.relative_to(Path(hpr.outputDir))) #excludes sr name; for non-aggregate hll metadata
                        filePathRel = str(filePath.relative_to(Path(hpr.outputDir).parent)) #includes SR name; for aggregate hll metadata
                        hllMetadataDownload = hllMetadataDownload.append({'id':downloadUUID,
                                                                          'category':returnPeriod,
                                                                          'subcategory':'Damaged Facilities',
                                                                          'name':'Damaged Facilities.shp',
                                                                          'icon':'spatial',
                                                                          'file':filePathRel,
                                                                          'analysis':scenarioUUID}, ignore_index=True)
                    except Exception as e:
                        #print('Damaged facilities not available to export to shapefile...')
                        print('Damaged facilities not available to export to shapefile to zipfile...')
                        print(e)

                    try:
                        print('Writing Hazard Boundary Polygon to shapefile to zipfile...')
                        #The following two commented out lines encounter ODBC issues on some machines,
                        #possibly due to 32 and 64bit access driver conflicts
##                            hpr.getFloodBoundaryPolyName('R')
##                            hpr.exportFloodHazardPolyToShapefileToZipFile(Path.joinpath(exportPath, 'hazardBoundaryPoly.shp'))
                        hazardGDF = hpr.getHazardGeoDataFrame()
                        hazardGDF.toShapefiletoZipFile(Path.joinpath(exportPath, 'hazardBoundaryPoly.shp'), 'epsg:4326', 'epsg:4326')
                        #ADD ROW TO hllMetadataDownload TABLE...
                        downloadUUID = uuid.uuid4()
                        filePath = Path.joinpath(exportPath, 'hazardBoundaryPoly.zip')
                        #filePathRel = str(filePath.relative_to(Path(hpr.outputDir))) #excludes sr name; for non-aggregate hll metadata
                        filePathRel = str(filePath.relative_to(Path(hpr.outputDir).parent)) #includes SR name; for aggregate hll metadata
                        hllMetadataDownload = hllMetadataDownload.append({'id':downloadUUID,
                                                                          'category':returnPeriod,
                                                                          'subcategory':'Hazard',
                                                                          'name':'Hazard Boundary.shp',
                                                                          'icon':'spatial',
                                                                          'file':filePathRel,
                                                                          'analysis':scenarioUUID}, ignore_index=True)
                    except Exception as e:
                        print('Writing Hazard Boundary not available to export to shapefile...')
                        print(e)
                        
                except Exception as e:
                    print(u"Unexpected error exporting Shapefile: ")
                    print(e)


                    
                #EXPORT Hazus Package Region TO GeoJSON...
                try:
                    try:
                        print('Writing Results to geojson...')
                        results.toGeoJSON(Path.joinpath(exportPath, 'results.geojson'))
                        #ADD ROW TO hllMetadataDownload TABLE...
                        downloadUUID = uuid.uuid4()
                        filePath = Path.joinpath(exportPath, 'results.geojson')
                        #filePathRel = str(filePath.relative_to(Path(hpr.outputDir))) #excludes sr name; for non-aggregate hll metadata
                        filePathRel = str(filePath.relative_to(Path(hpr.outputDir).parent)) #includes SR name; for aggregate hll metadata
                        hllMetadataDownload = hllMetadataDownload.append({'id':downloadUUID,
                                                                          'category':returnPeriod,
                                                                          'subcategory':'Results',
                                                                          'name':'Results.geojson',
                                                                          'icon':'spatial',
                                                                          'file':filePathRel,
                                                                          'analysis':scenarioUUID}, ignore_index=True)
                    except Exception as e:
                        print('Base results not available to export to geojson')
                        print(e)
                        
                    try:
                        print('Writing Damaged Facilities to geojson...')
                        essentialFacilities.toGeoJSON(Path.joinpath(exportPath, 'damaged_facilities.geojson'))
                        #ADD ROW TO hllMetadataDownload TABLE...
                        downloadUUID = uuid.uuid4()
                        filePath = Path.joinpath(exportPath, 'damaged_facilities.geojson')
                        #filePathRel = str(filePath.relative_to(Path(hpr.outputDir))) #excludes sr name; for non-aggregate hll metadata
                        filePathRel = str(filePath.relative_to(Path(hpr.outputDir).parent)) #includes SR name; for aggregate hll metadata
                        hllMetadataDownload = hllMetadataDownload.append({'id':downloadUUID,
                                                                          'category':returnPeriod,
                                                                          'subcategory':'Damaged Facilities',
                                                                          'name':'Damaged Facilities.geojson',
                                                                          'icon':'spatial',
                                                                          'file':filePathRel,
                                                                          'analysis':scenarioUUID}, ignore_index=True)
                    except Exception as e:
                        print('Damaged facilities not available to export to geojson.')
                        print(e)                        

                    try:
                        print('Writing ImpactArea to geojson...')
                        econloss = hpr.getEconomicLoss()
                        if len(econloss.loc[econloss['EconLoss'] > 0]) > 0:
                            econloss.toHLLGeoJSON(Path.joinpath(exportPath, 'impactarea.geojson'))
                            #ADD ROW TO hllMetadataDownload TABLE...
                            downloadUUID = uuid.uuid4()
                            filePath = Path.joinpath(exportPath, 'impactarea.geojson')
                            #filePathRel = str(filePath.relative_to(Path(hpr.outputDir))) #excludes sr name; for non-aggregate hll metadata
                            filePathRel = str(filePath.relative_to(Path(hpr.outputDir).parent)) #includes SR name; for aggregate hll metadata
                            hllMetadataDownload = hllMetadataDownload.append({'id':downloadUUID,
                                                                              'category':returnPeriod,
                                                                              'subcategory':'Hazard',
                                                                              'name':'Impact Area.geojson',
                                                                              'icon':'spatial',
                                                                              'file':filePathRel,
                                                                              'analysis':scenarioUUID}, ignore_index=True)
                        else:
                            print('no econ loss for HLL geojson')
                            
                    except Exception as e:
                        print('ImpactArea not available to export to geojson.')
                        print(e)

                    try:
                        """This section is to write the same impact area geojson but at the scenario level."""
                        print('Writing ImpactArea Scenario to geojson...')
                        econloss = hpr.getEconomicLoss()
                        if len(econloss.loc[econloss['EconLoss'] > 0]) > 0:
                            econloss.toHLLGeoJSON(Path.joinpath(exportPath.parent, 'impactarea.geojson'))
                            #ADD ROW TO hllMetadataDownload TABLE...
                            filePath = Path.joinpath(exportPath.parent, 'impactarea.geojson')
                            #filePathRel = str(filePath.relative_to(Path(hpr.outputDir))) #excludes sr name; for non-aggregate hll metadata
                            scenarioGEOM = str(filePath.relative_to(Path(hpr.outputDir).parent)) #includes SR name; for aggregate hll metadata
                        else:
                            print('no econ loss for HLL Scenario geojson')
                    except Exception as e:
                        print('ImpactArea Scenario not available to export to geojson.')
                        print(e)
                        
                except Exception as e:
                    print('Unexpected error exporting to GeoJSON:')
                    print(e)

            #Analysis Metadata part two of two...
            #ADD ROW TO hllMetadataScenario TABLE...
            hllMetadataScenario = hllMetadataScenario.append({'id':scenarioUUID,
                                                              'name':scenario['ScenarioName'],
                                                              'hazard':hazard['Hazard'], #flood, hurricane, earthquake, tsunami, tornado
                                                              'analysisType':analysisType, #historic, deterministic, probabilistic
                                                              'date':analysisDate, #YYYY-MM-DD
                                                              'source':'FIX ME: USER INPUT NEEDED (100 chars max)', #Max100 chars
                                                              'modifiedInventory':'false', #true/false
                                                              'meta':str(scenarioMETA).replace("'",'"'), #needs to be double quotes; one level Python dict/json
                                                              'event':hazardUUID,
                                                              'geom':scenarioGEOM}, #filepath to geojson
                                                             ignore_index=True)
            print()
            

    #EXPORT HLL METADATA (NOTE: openpyxl (*et_xmlfile, &jdcal)) not installed, can't export to excel)...
    ##hllMetadataPath = str(Path.joinpath(Path(outputPath), "exportHLLMetadata.xlsx"))
    ##hllMetadata.to_excel(hllMetadataPath)
            
    hllMetadataEventPath = str(Path.joinpath(Path(outputPath), "Event.csv"))
    hllMetadataEvent.to_csv(hllMetadataEventPath, index=False)

    hllMetadataAnalysisPath = str(Path.joinpath(Path(outputPath), "Analysis.csv"))
    hllMetadataScenario.to_csv(hllMetadataAnalysisPath, index=False)

    hllMetadataDownloadPath = str(Path.joinpath(Path(outputPath), "Download.csv"))
    hllMetadataDownload.to_csv(hllMetadataDownloadPath, index=False)

    #DROP SQL SERVER HPR DATABASE...
    if deleteDB == 1:
        hpr.dropDB()

    #DELETE UNZIPPED HPR FOLDER...
    if deleteTempDir == 1:
        hpr.deleteTempDir()


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
    print('Running batch export...')

    #USER DEFINED VALUES
    hprDir = r'C:/workspace/hpr'                    #The directory containing hpr files
    outDir = r'C:/workspace/batchexportOutput'   #The directory for the output files

    #CREATE A DIRECTORY FOR THE OUTPUT FOLDERS...
    if not os.path.exists(outDir):
        os.mkdir(outDir)

    #print(f'Input Directory: {hprDir}') #debug
    #print(f'Output Directory: {outDir}') #debug
    
    print(f'HPR List:')
    fileExt = r'*.hpr'
    hprList = list(Path(hprDir).glob(fileExt))
    for hpr in hprList:
        print(hpr)

    if len(hprList) > 0:
        print(f'Processing HPRs...')

        stdout_fileno = sys.stdout
        logfile = Path.joinpath(Path(outDir),'batchexportlog.txt')
        sys.stdout = open(logfile, 'w+')
        sys.stderr = sys.stdout
        
        for hpr in hprList:
            try:
                exportHPR(str(hpr), outDir, deleteDB=0, deleteTempDir=0)
                print()
            except Exception as e:
                print('Exception:')
                print(e)
                
        sys.stdout.close()
        sys.stderr.close()
        sys.stdout = stdout_fileno
        sys.stderr = sys.stdout
        print(f'Done. Check the {logfile}.')
        
        print('Aggregating HLL Metata...')
        aggregateHllMetadataFiles(outDir)
        print('Done.')
        
        print()
    else:
        print('no HPR files found')
        
