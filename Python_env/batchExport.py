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

def exportHPR(hprFile, outputDir):
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
    hllMetadataEvent = pd.DataFrame(columns=['uuid',
                                             'name',
                                             'geom',
                                             'date',
                                             'image',
                                             'updated'])

    hllMetadataScenario = pd.DataFrame(columns=['uuid',
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
                                                'updated',
                                                'event',
                                                'location',
                                                'geom'])

    hllMetadataDownload = pd.DataFrame(columns=['category',
                                                'subcategory',
                                                'name',
                                                'icon',
                                                'link',
                                                'file',
                                                'meta',
                                                'analysis',
                                                'dateUpdate'])


    #ITERATE OVER THE HAZARD, SCENARIO, RETURNPERIOD AVAIALABLE COMBINATIONS...
    for hazard in hpr.HazardsScenariosReturnPeriods:
        print(f"Hazard: {hazard['Hazard']}") #debug

        #ADD ROW TO hllMetadataEvent TABLE...
        hazardUUID = uuid.uuid4()
        #need to add path to hazard boundary (is this unique for each returnperiod/download in FIMS?)
        hllMetadataEvent = hllMetadataEvent.append({'uuid':hazardUUID,
                                                    'name':hpr.dbName}, ignore_index=True)

        #SCENARIOS/ANALYSIS
        for scenario in hazard['Scenarios']:
            print(f"Scenario: {scenario['ScenarioName']}") #debug

            #ADD ROW TO hllMetadataScenario TABLE...
            scenarioUUID = uuid.uuid4()
            #need to get analysis geometric boundary in geojson 4326, can be path to file?
            scenarioMETA = str({"HazusVersion":f"{hpr.HazusVersion}"}).replace("'",'"') #needs to be double quotes
            hllMetadataScenario = hllMetadataScenario.append({'uuid':scenarioUUID,
                                                              'name':scenario['ScenarioName'],
                                                              'hazard':hazard['Hazard'], #flood, hurricane, earthquake, tsunami, tornado
                                                              'analysisType':'FIX ME', #historic, deterministic, probabilistic
                                                              'date':'FIX ME', #YYYY-MM-DD
                                                              'source':'FIX ME: USER INPUT NEEDED', #Max100 chars
                                                              'modifiedInventory':'FIX ME', #true/false
                                                              'event':hazardUUID,
                                                              'meta':scenarioMETA}, ignore_index=True)
            #RETURNPERIODS/DOWNLOAD
            for returnPeriod in scenario['ReturnPeriods']:
                print(f"returnPeriod: {returnPeriod}") #debug

                #SET HPR HAZARD, SCENARIO, RETURNPERIOD...
                hpr.hazard = hazard['Hazard']
                hpr.scenario = scenario['ScenarioName']
                hpr.returnPeriod = returnPeriod
                print(f"hazard = {hpr.hazard}, scenario= {hpr.scenario}, returnPeriod = {hpr.returnPeriod}") #debug

                #GET BULK OF RESULTS...
                try:
                    print('Get bulk of results...')
                    results = hpr.getResults()
                    essentialFacilities = hpr.getEssentialFacilities()
                    if len(results) < 1:
                        print('No results found. Please check your Hazus Package Region and try again.')
                except Exception as e:
                    print(e)

                #CREATE A DIRECTORY FOR THE OUTPUT FOLDERS LIKE "HPR>Hazard>Scenario>STAGE_ReturnPeriod"...
                #returnperiod divider is set to STAGE for FIMs/PTS but can be changed back to RP for other.
                exportPath = Path.joinpath(Path(outputPath), str(hazard['Hazard']).strip(), str(scenario['ScenarioName']).strip(), 'STAGE_' + str(returnPeriod).strip())
                Path(exportPath).mkdir(parents=True, exist_ok=True) #this may make the earlier HPR dir creation redundant

                #EXPORT Hazus Package Region TO CSV...
                try:
                    try:
                        print('Writing results to csv...')
                        results.toCSV(Path.joinpath(exportPath, 'results.csv'))
                        #ADD ROW TO hllMetadataDownload TABLE...
                        downloadUUID = uuid.uuid4()
                        filePath = Path.joinpath(exportPath, 'results.csv')
                        filePathRel = str(filePath.relative_to(Path(hpr.outputDir)))
                        hllMetadataDownload = hllMetadataDownload.append({'category':returnPeriod,
                                                                          'subcategory':'Results',
                                                                          'name':'results.csv',
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
                        filePath = Path.joinpath(exportPath, 'building_damage_by_occupancy.csv')
                        filePathRel = str(filePath.relative_to(Path(hpr.outputDir)))
                        hllMetadataDownload = hllMetadataDownload.append({'category':returnPeriod,
                                                                          'subcategory':'Results',
                                                                          'name':'building_damage_by_occupancy.csv',
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
                        filePath = Path.joinpath(exportPath, 'building_damage_by_type.csv')
                        filePathRel = str(filePath.relative_to(Path(hpr.outputDir)))
                        hllMetadataDownload = hllMetadataDownload.append({'category':returnPeriod,
                                                                          'subcategory':'Results',
                                                                          'name':'building_damage_by_type.csv',
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
                        filePath = Path.joinpath(exportPath, 'damaged_facilities.csv')
                        filePathRel = str(filePath.relative_to(Path(hpr.outputDir)))
                        hllMetadataDownload = hllMetadataDownload.append({'category':returnPeriod,
                                                                          'subcategory':'Results',
                                                                          'name':'damaged_facilities.csv',
                                                                          'icon':'spreadsheet',
                                                                          'file':filePathRel,
                                                                          'analysis':scenarioUUID}, ignore_index=True)
                    except Exception as e:
                        print('Damaged facilities not available to export to csv.')
                        print(e)
                except Exception as e:
                    print('Unexpected error exporting CSVs')
                    print(e)
                        
                #EXPORT Hazus Package Region TO Shapefile...
                try:
                    try:
                        print('Writing results to shapefile...')
                        results.toShapefile(Path.joinpath(exportPath, 'results.shp'))
                        #ADD ROW TO hllMetadataDownload TABLE...
                        filePath = Path.joinpath(exportPath, 'results.shp')
                        filePathRel = str(filePath.relative_to(Path(hpr.outputDir)))
                        hllMetadataDownload = hllMetadataDownload.append({'category':returnPeriod,
                                                                          'subcategory':'Results',
                                                                          'name':'results.shp',
                                                                          'icon':'spatial',
                                                                          'file':filePathRel,
                                                                          'analysis':scenarioUUID}, ignore_index=True)
                    except Exception as e:
                        print('Base results not available to export to shapefile...')
                        print(e)
                        
                    try:
                        print('Writing Damaged facilities to shapefile.')
                        essentialFacilities.toShapefile(Path.joinpath(exportPath, 'damaged_facilities.shp'))
                        #ADD ROW TO hllMetadataDownload TABLE...
                        filePath = Path.joinpath(exportPath, 'damaged_facilities.shp')
                        filePathRel = str(filePath.relative_to(Path(hpr.outputDir)))
                        hllMetadataDownload = hllMetadataDownload.append({'category':returnPeriod,
                                                                          'subcategory':'Results',
                                                                          'name':'damaged_facilities.shp',
                                                                          'icon':'spatial',
                                                                          'file':filePathRel,
                                                                          'analysis':scenarioUUID}, ignore_index=True)
                    except Exception as e:
                        print('Damaged facilities not available to export to shapefile...')
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
                        filePath = Path.joinpath(exportPath, 'results.geojson')
                        filePathRel = str(filePath.relative_to(Path(hpr.outputDir)))
                        hllMetadataDownload = hllMetadataDownload.append({'category':returnPeriod,
                                                                          'subcategory':'Results',
                                                                          'name':'results.geojson',
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
                        filePath = Path.joinpath(exportPath, 'damaged_facilities.geojson')
                        filePathRel = str(filePath.relative_to(Path(hpr.outputDir)))
                        hllMetadataDownload = hllMetadataDownload.append({'category':returnPeriod,
                                                                          'subcategory':'Results',
                                                                          'name':'damaged_facilities.geojson',
                                                                          'icon':'spatial',
                                                                          'file':filePathRel,
                                                                          'analysisU':scenarioUUID}, ignore_index=True)
                    except Exception as e:
                        print('Damaged facilities not available to export to geojson.')
                        print(e)

                    if hazard == 'flood':
                        try:
                            print('Writing Flood Hazard Boundary Polygon to shapefile...')
                            hpr.getFloodBoundaryPolyName('R')
                            hpr.exportFloodHazardPolyToShapefile(Path.joinpath(exportPath, 'hazardBoundaryPoly.shp'))
                            #ADD ROW TO hllMetadataDownload TABLE...
                            filePath = Path.joinpath(exportPath, 'hazardBoundaryPoly.shp')
                            filePathRel = str(filePath.relative_to(Path(hpr.outputDir)))
                            hllMetadataDownload = hllMetadataDownload.append({'category':returnPeriod,
                                                                              'subcategory':'Results',
                                                                              'name':'hazardBoundaryPoly.shp',
                                                                              'icon':'spatial',
                                                                              'file':filePathRel,
                                                                              'analysis':scenarioUUID}, ignore_index=True)
                        except Exception as e:
                            print('Writing Hazard not available to export to shapefile...')
                            print(e)
                        

                    try:
                        print('Writing ImpactArea to geojson...')
                        econloss = hpr.getEconomicLoss()
                        if len(econloss.loc[econloss['EconLoss'] > 0]) > 0:
                            econloss.toHLLGeoJSON(Path.joinpath(exportPath, 'impactarea.geojson'))
                            #ADD ROW TO hllMetadataDownload TABLE...
                            filePath = Path.joinpath(exportPath, 'impactarea.geojson')
                            filePathRel = str(filePath.relative_to(Path(hpr.outputDir)))
                            hllMetadataDownload = hllMetadataDownload.append({'category':returnPeriod,
                                                                              'subcategory':'Results',
                                                                              'name':'impactarea.geojson',
                                                                              'icon':'spatial',
                                                                              'file':filePathRel,
                                                                              'analysis':scenarioUUID}, ignore_index=True)
                        else:
                            print('no econ loss for HLL geojson')
                    except Exception as e:
                        print('Convex Hull Simplified Economic loss not available to export to geojson.')
                        print(e)
                            
                except Exception as e:
                    print('Unexpected error exporting to GeoJSON:')
                    print(e)
                    
            print()
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
    try:
        hpr.dropDB()
    except Exception as e:
        print(e)

    #DELETE UNZIPPED HPR FOLDER...
    try:
        hpr.deleteTempDir()
    except Exception as e:
        print(e)

        
if __name__ == '__main__':
    print('Running batch export...')

    #USER DEFINED VALUES
    hprDir = r'C:/workspace/hpr'                    #The directory containing hpr files
    outDir = r'C:/workspace/batchexportOutput'   #The directory for the output files

    #print(f'Input Directory: {hprDir}') #debug
    #print(f'Output Directory: {outDir}') #debug
    
    print(f'HPR List:')
    fileExt = r'*.hpr'
    hprList = list(Path(hprDir).glob(fileExt))
    for hpr in hprList:
        print(hpr)

    if len(hprList) > 0:
        print(f'Processing HPRs...')
        for hpr in hprList:
            try:
                exportHPR(str(hpr), outDir)
            except Exception as e:
                print('Exception:')
                print(e)
        print()
    else:
        print('no HPR files found')
