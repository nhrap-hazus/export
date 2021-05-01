"""2021 Colin Lindeman
Python 3, Hazpy
Fit for Flood FIMS, will need to adjust for the other perils EQ, HU, TS.
"""

from hazpy.legacy import HazusPackageRegion
##from hazpy.legacy import reports
from pathlib import Path
import os
import pandas as pd
import uuid

def exportHPR(hprFile, outputDir):
    """
    """
    #hpr = HazusPackageRegion(hprFilePath=file, outputDir=r'C:\workspace')
    hpr = HazusPackageRegion(hprFilePath=hprFile, outputDir=outputDir)

    print(hpr.hprFilePath)
    print(hpr.outputDir)
    print(hpr.tempDir)
    print(hpr.hprComment)
    print(hpr.HazusVersion)
    print(hpr.Hazards)
    print()

    try:
        hpr.restoreHPR()
    except Exception as e:
        print(e)

    hpr.getHazardsScenariosReturnPeriods()

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
        print(hazard['Hazard'])

        #ADD ROW TO hllMetadataEvent TABLE...
        hazardUUID = uuid.uuid4()
        #need to add path to hazard boundary (is this unique for each returnperiod/download in FIMS?)
        hllMetadataEvent = hllMetadataEvent.append({'uuid':hazardUUID,
                                                    'name':hpr.dbName}, ignore_index=True)

        #SCENARIOS/ANALYSIS
        for scenario in hazard['Scenarios']:
            print(scenario['ScenarioName'])

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
                print(returnPeriod)

                #SET HPR HAZARD, SCENARIO, RETURNPERIOD...
                hpr.hazard = hazard['Hazard']
                hpr.scenario = scenario['ScenarioName']
                hpr.returnPeriod = returnPeriod
                print(hpr.hazard, hpr.scenario, hpr.returnPeriod)

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
                        
    ##                try:
    ##                    print('Writing hazard to shapefile.')
    ##                    hazardGDF = hpr.getHazardGeoDataFrame()
    ##                    hazardGDF.toShapefile(Path.joinpath(exportPath, 'hazard.shp'))
    ##                    #ADD ROW TO hllMetadataDownload TABLE...
    ##                    filePath = Path.joinpath(exportPath, 'hazard.shp')
    ##                    filePathRel = str(filePath.relative_to(Path(hpr.outputDir)))
    ##                    hllMetadataDownload = hllMetadataDownload.append({'category':returnPeriod,
    ##                                                                      'subcategory':'Results',
    ##                                                                      'name':'hazard.shp',
    ##                                                                      'icon':'spatial',
    ##                                                                      'file':filePathRel,
    ##                                                                      'analysis':scenarioUUID}, ignore_index=True)
    ##                except Exception as e:
    ##                    print('Hazard not available to export to shapefile...')
    ##                    print(e)
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
                        
    ##                try:
    ##                    print('Writing Hazard to geojson...')
    ##                    hazardGDF = hpr.getHazardGeoDataFrame()
    ##                    hazardGDF.toGeoJSON(Path.joinpath(exportPath, 'hazard.geojson'))
    ##                    #ADD ROW TO hllMetadataDownload TABLE...
    ##                    filePath = Path.joinpath(exportPath, 'hazard.geojson')
    ##                    filePathRel = str(filePath.relative_to(Path(hpr.outputDir)))
    ##                    hllMetadataDownload = hllMetadataDownload.append({'category':returnPeriod,
    ##                                                                      'subcategory':'Results',
    ##                                                                      'name':'hazard.geojson',
    ##                                                                      'icon':'spatial',
    ##                                                                      'file':filePathRel,
    ##                                                                      'analysis':scenarioUUID}, ignore_index=True)
    ##                except Exception as e:
    ##                    print('Writing Hazard not available to export to geojson...')
    ##                    print(e)

                    #if hazard == 'flood':
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
                            econloss.toHLLGeoJSON(Path.joinpath(exportPath, 'econloss_simpconvexHLL.geojson'))
                            #ADD ROW TO hllMetadataDownload TABLE...
                            filePath = Path.joinpath(exportPath, 'econloss_simpconvexHLL.geojson')
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
                    print('Hazard not available to export to geojson.')
                    
                #EXPORT Hazus Package Region TO PDF USING REPORT MODULE...
##                try:
##                    ##hpr.report = Report(hpr.name, '', hpr.hazard) #inits with self.hazard
##                    reportTitle = hpr.text_reportTitle.get("1.0", 'end-1c')
##                    if len(reportTitle) > 0:
##                        hpr.report.title = reportTitle
##                    reportSubtitle = text_reportSubtitle.get("1.0", 'end-1c')
##                    if len(reportSubtitle) > 0:
##                        hpr.report.subtitle = reportSubtitle
##                    ##hpr.createReport() #added
##                    hpr.report.save(Path.joinpath(exportPath, 'report_summary.pdf'), build=True)
##                except Exception as e:
##                    print(u"Unexpected error exporting the PDF (report): ")
##                    print(e)

                #EXPORT Hazus Package Region TO PDF USING REPORTS MODULE...
                    #no pdfrw library, need to add to environment
##                try:
                    
                except Exception as e:
                    print(u"Unexpected error exporting the PDF (reports): ")
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
    #CREATE HazusPackageRegion OBJECT...
    #file = r'C:\workspace\hprfiles\NorCal-BayArea_SanAndreasM7-8.hpr' #EQ
    #file = r'C:\workspace\hprfiles\banMO.hpr' #Flood FIM
    #file = r'C:\workspace\hprfiles\FIMHPRs\LChamNYVT_1.hpr' #sample FIM, largest size, 6 returnperiods?
    #file = r'C:\workspace\hprfiles\FIMHPRs\nora.hpr' #sample FIM
    #file = r'C:\workspace\hprfiles\FIMHPRs\lanmi_01.hpr' #sample FIM should have 305 depth grids
    #file = r'C:\workspace\hprfiles\FIMHPRs\vlypark.hpr' #Sample FIM
    #file = r'C:\workspace\hprfiles\FIMHPRs\cfwgoshOR.hpr' #Sample FIM
    #exportHPR(file, outputDir=r'C:\workspace')
    
    #ITERATE OVER THE HPRs...
    hprDir = r'C:\workspace\SprintReviewDemo'
    fileExt = r'*.hpr'
    print(f'HPR List from {hprDir}...')
    hprList = list(Path(hprDir).glob(fileExt))
    for hpr in hprList:
        print(hpr)
    print(f'Processing HPRs...')
    for hpr in hprList:
        exportHPR(hpr, r'C:\workspace\SprintReviewDemo')
    print()
