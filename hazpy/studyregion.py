import json
import os
import shutil
import subprocess
import sys
import zipfile
from functools import reduce
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pyodbc as py
import rasterio as rio
from osgeo import ogr
from rasterio import features
from shapely.wkt import loads

try:
    from .report import Report
    from .studyregiondataframe import StudyRegionDataFrame
except:
    from report import Report
    from studyregiondataframe import StudyRegionDataFrame

#from shapely.geometry.multipolygon import MultiPolygon
#from shapely.geometry.polygon import Polygon
#import urllib

# TODO check if all geojsons are oriented correctly; if not, apply orient
# try:
#     from shapely.ops import orient  # version >=1.7a2
# except:
#     from shapely.geometry.polygon import orient

class StudyRegion:
    """Creates a study region object using an existing study region in the local Hazus database

    Keyword Arguments:
        studyRegion: str -- the name of the study region
        hazard: str -- the name of the peril. Only necessary if the study region has more than one hazard.
    """

    scenario = ''

    def __init__(self, studyRegion=None, hprFilePath='', outputDir=''):
        self.hprFilePath = Path(hprFilePath)
        self.outputDir = Path.joinpath(Path(outputDir), self.hprFilePath.stem)
        self.tempDir = Path.joinpath(Path(outputDir), self.hprFilePath.stem + '_temp')
        
        self.hazard = ''
        #self.scenario = ''
        self.returnPeriod = '' #this can sometimes have trailing spaces
        self.hazusPackageRegion = self.hprFilePath.stem #for HazusPackageRegionDataFrame
        # TODO: Create subclasses for HPR & 'StudyRegion' - BC
        # TODO: Think of name for parent class - BC
        if studyRegion:
            self.conn = self.createConnection()
            self.name = studyRegion
            self.hazard = ''
            self.dbName = studyRegion
            self.setHazard()
            self.report = Report(self, self.name, "", self.hazard)
        else:
            self.hprComment = self.getHPRComment(self.hprFilePath)
            self.HazusVersion = self.getHPRHazusVersion(self.hprComment)
            self.Hazards = self.getHPRHazards(self.hprComment)
            self.dbName = '' #does not include 'bk_' prefix
            self.name = '' #'bk_' + self.dbName #also used in HazusPackageRegionDataFrame
            self.bkFilePath = ''
            self.LogicalNames = []
            self.LogicalName_data = ''
            self.LogicalName_log = '' #tuple ()

    def setHazard(self, hazard=None):
        # validate hazard
        hazards = self.getHazardsAnalyzed()
        if hazard == None and len(hazards) == 1:
            self.hazard = hazards[0]
        elif hazard == None and len(hazards) > 1:
            self.hazard = hazards[0]
        else:
            if hazard in hazards:
                self.hazard = hazard

    def setScenario(self, scenario=None):
        # validate scenario
        scenarios = self.getScenarios()
        if scenario == None or len(scenarios) == 1:
            self.scenario = scenarios[0]
        elif scenario == None and len(scenarios) > 1:
            self.scenario = scenarios[0]
            print(
                f"Defaulting to {scenarios[0]}"
            )
        else:
            if scenario in scenarios:
                self.scenario = scenario

    def createConnection(self, orm='pyodbc'):
        """ Creates a connection object to the local Hazus SQL Server database

            Key Argument:
                orm: string - - type of connection to return (choices: 'pyodbc', 'sqlalchemy')
            Returns:
                conn: pyodbc connection
        """
        try:
            # list all Windows SQL Server drivers
            drivers = [
                '{ODBC Driver 17 for SQL Server}',
                '{ODBC Driver 13.1 for SQL Server}',
                '{ODBC Driver 13 for SQL Server}',
                '{ODBC Driver 11 for SQL Server} ',
                '{SQL Server Native Client 11.0}',
                '{SQL Server Native Client 10.0}',
                '{SQL Native Client}',
                '{SQL Server}'
            ]
            computer_name = os.environ['COMPUTERNAME']
            if orm == 'pyodbc':
                # create connection with the latest driver
                for driver in drivers:
                    try:
                        conn = py.connect(self.getConnectionString('pyodbc').format(d=driver, cn=computer_name))
                        break
                    except:
                        conn = py.connect(self.getConnectionString('pyodbc_auth').format(d=driver, cn=computer_name))
                        break
            return conn
        except Exception as e:
            print('\n')
            print(e)
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            print(fname)
            print(exc_type, exc_tb.tb_lineno)
            print('\n')

            print("Unexpected error:", sys.exc_info()[0])
            raise

    def query(self, sql):
        """Performs a SQL query on the Hazus SQL Server database

        Keyword Arguments:
            sql: str -- a T-SQL query

        Returns:
            df: pandas dataframe
        """
        try:
            self.conn = self.createConnection()
            df = pd.read_sql(sql, self.conn)
            return StudyRegionDataFrame(self, df)
        except Exception as e:
            print('\n')
            print(e)
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            print(fname)
            print(exc_type, exc_tb.tb_lineno)
            print('\n')
            print(f'{sql}\n')
            print("Unexpected error with study region query:", sys.exc_info()[0])
            raise

    def getHazardBoundary(self):
        """Fetches the hazard boundary from a Hazus SQL Server database

        Returns:
            df: pandas dataframe -- geometry in WKT
        """
        try:
            sql = (
                "SELECT Shape.STAsText() as geometry from [%s].[dbo].[hzboundary]"
                % self.name
            )
            df = self.query(sql)
            return StudyRegionDataFrame(self, df)
        except:
            print("Unexpected error:", sys.exc_info()[0])
            raise

    def getEconomicLoss(self):
        """
        Queries the total economic loss for a study region from the local Hazus SQL Server database

            Returns:
                df: pandas dataframe -- a dataframe of economic loss
        """
        try:
            # constant to convert to real USD
            constant = 1000
            sqlDict = {
                "earthquake": """select Tract as tract, SUM(ISNULL(TotalLoss, 0)) * {c} as EconLoss 
                from {s}.dbo.[eqTractEconLoss] group by [eqTractEconLoss].Tract
                HAVING Sum(ISNULL(TotalLoss, 0)) * {c} > 0
                """.format(
                    s=self.name, c=constant
                ),
                "flood": """select CensusBlock as block, 
                Sum(ISNULL(CAST(TotalLoss AS BIGINT), 0)) * {c} as EconLoss from {s}.dbo.flFRGBSEcLossByTotal
                    where StudyCaseId = (select StudyCaseID from {s}.[dbo].[flStudyCase] where StudyCaseName = '{sc}')
                    and ReturnPeriodId = '{rp}'
                 group by CensusBlock
                 HAVING Sum(ISNULL(CAST(TotalLoss AS BIGINT), 0)) * {c} > 0
                 """.format(
                    s=self.name, c=constant, sc=self.scenario, rp=self.returnPeriod
                ),
                # NOTE: huSummaryLoss will result in double economic loss. It stores results for occupancy and structure type
                # 'hurricane': """select TRACT as tract, SUM(ISNULL(TotLoss, 0)) * {c} as EconLoss from {s}.dbo.[huSummaryLoss]
                #     where ReturnPeriod = '{rp} '
                #     and huScenarioName = '{sc}'
                #     group by Tract""".format(s=self.name, c=constant, rp=self.returnPeriod, sc=self.scenario),
                "hurricane": """
                    select TRACT as tract, SUM(ISNULL(Total, 0)) * {c} as EconLoss from {s}.dbo.[hv_huResultsOccAllLossT]
                        where Return_Period = '{rp}' 
                        and huScenarioName = '{sc}'
                        group by Tract
                        HAVING Sum(ISNULL(Total, 0)) * {c} > 0
                """.format(
                    s=self.name, c=constant, rp=self.returnPeriod, sc=self.scenario
                ),
                "tsunami": """select CensusBlock as block, SUM(ISNULL(TotalLoss, 0)) * {c} as EconLoss 
                from {s}.dbo.tsuvResDelKTotB group by CensusBlock
                HAVING Sum(ISNULL(TotalLoss, 0)) * {c} > 0
                """.format(
                    s=self.name, c=constant
                ),
            }
            df = self.query(sqlDict[self.hazard])
            return StudyRegionDataFrame(self, df)
        except:
            print("Unexpected error:", sys.exc_info()[0])
            raise

    def getTotalEconomicLoss(self):
        """
        Queries the total economic loss summation for a study region from the local Hazus SQL Server database

            Returns:
                totalLoss: integer -- the summation of total economic loss
        """
        totalLoss = self.getEconomicLoss()["EconLoss"].sum()
        return totalLoss

    def getBuildingDamage(self):
        try:
            constant = 1000
            sqlDict = {
                "earthquake": """SELECT Tract as tract, SUM(ISNULL(PDsNoneBC, 0))
                        As NoDamage, SUM(ISNULL(PDsSlightBC, 0)) AS Affected, SUM(ISNULL(PDsModerateBC, 0))
                        AS Minor, SUM(ISNULL(PDsExtensiveBC, 0)) AS Major,
                        SUM(ISNULL(PDsCompleteBC, 0)) AS Destroyed FROM [{s}].dbo.[eqTractDmg]
                        WHERE DmgMechType = 'STR' group by Tract
                """.format(
                    s=self.name
                ),
                "flood": """SELECT CensusBlock as block, 
                        SUM(ISNULL(CAST(TotalLoss AS BIGINT), 0)) * {c}
                        AS TotalLoss, 
                        SUM(ISNULL(CAST(BuildingLoss AS BIGINT), 0)) * {c} AS BldgLoss,
                        SUM(ISNULL(CAST(ContentsLoss AS BIGINT), 0)) * {c} AS ContLoss
                        FROM [{s}].dbo.[flFRGBSEcLossBySOccup] 
                        where StudyCaseId = (select StudyCaseID from {s}.[dbo].[flStudyCase] where StudyCaseName = '{sc}')
                        and ReturnPeriodId = '{rp}'
                        GROUP BY CensusBlock
                        """.format(
                    s=self.name, c=constant, sc=self.scenario, rp=self.returnPeriod
                ),
                "hurricane": """SELECT Tract AS tract,
                        SUM(ISNULL(NonDamage, 0)) As NoDamage, SUM(ISNULL(MinDamage, 0)) AS Affected,
                        SUM(ISNULL(ModDamage, 0)) AS Minor, SUM(ISNULL(SevDamage, 0)) AS Major,
                        SUM(ISNULL(ComDamage, 0)) AS Destroyed FROM [{s}].dbo.[huSummaryDamage]
                        WHERE GenBldgOrGenOcc IN('COM', 'AGR', 'GOV', 'EDU', 'REL','RES', 'IND')
                        and ReturnPeriod = '{rp}' 
                        and huScenarioName = '{sc}'
                        GROUP BY Tract""".format(
                    s=self.name, sc=self.scenario, rp=self.returnPeriod
                ),
                "tsunami": """select CBFips as block,
                        ISNULL(count(case when BldgLoss/NULLIF(ValStruct, 0) <= 0.05 then 1 end), 0) as Affected,
                        ISNULL(count(case when BldgLoss/NULLIF(ValStruct, 0) > 0.05 and BldgLoss/(ValStruct) <= 0.3 then 1 end), 0) as Minor,
                        ISNULL(count(case when BldgLoss/NULLIF(ValStruct, 0) > 0.3 and BldgLoss/(ValStruct) <= 0.5 then 1 end), 0) as Major,
                        ISNULL(count(case when BldgLoss/NULLIF(ValStruct, 0) > 0.5 then 1 end), 0) as Destroyed
                        from (select NsiID, ValStruct, ValCont  from {s}.dbo.tsHazNsiGbs) haz
                            left join (select NsiID, CBFips from {s}.dbo.tsNsiGbs) gbs
                            on haz.NsiID = gbs.NsiID
                            left join (select NsiID, BldgLoss from {s}.dbo.tsFRNsiGbs) frn
                            on haz.NsiID = frn.NsiID
                            group by CBFips""".format(
                    s=self.name
                ),
            }

            df = self.query(sqlDict[self.hazard])
            return StudyRegionDataFrame(self, df)
        except:
            raise

    def getBuildingDamageByOccupancy(self):
        """Queries the building damage by occupancy type for a study region from the local Hazus SQL Server database

        Returns:
            df: pandas dataframe -- a dataframe of building damage by occupancy type
        """
        try:
            constant = 1000
            sqlDict = {
                "earthquake": """SELECT Occupancy, SUM(ISNULL(PDsNoneBC, 0))
                        As NoDamage, SUM(ISNULL(PDsSlightBC, 0)) AS Affected, SUM(ISNULL(PDsModerateBC, 0))
                        AS Minor, SUM(ISNULL(PDsExtensiveBC, 0)) AS Major,
                        SUM(ISNULL(PDsCompleteBC, 0)) AS Destroyed FROM {s}.dbo.[eqTractDmg]
                        WHERE DmgMechType = 'STR' GROUP BY Occupancy""".format(
                    s=self.name
                ),
                "flood": """SELECT SOccup AS Occupancy, 
                        SUM(ISNULL(CAST(TotalLoss AS BIGINT), 0)) * {c}
                        AS TotalLoss, 
                        SUM(ISNULL(CAST(BuildingLoss AS BIGINT), 0)) * {c} AS BldgLoss,
                        SUM(ISNULL(CAST(ContentsLoss AS BIGINT), 0)) * {c} AS ContLoss
                        FROM {s}.dbo.[flFRGBSEcLossBySOccup]
                        where StudyCaseId = (select StudyCaseID from {s}.[dbo].[flStudyCase] where StudyCaseName = '{sc}')
                        and ReturnPeriodId = '{rp}'
                        GROUP BY SOccup
                        """.format(
                    s=self.name, c=constant, sc=self.scenario, rp=self.returnPeriod
                ),
                "hurricane": """SELECT GenBldgOrGenOcc AS Occupancy,
                        SUM(ISNULL(NonDamage, 0)) As NoDamage, SUM(ISNULL(MinDamage, 0)) AS Affected,
                        SUM(ISNULL(ModDamage, 0)) AS Minor, SUM(ISNULL(SevDamage, 0)) AS Major,
                        SUM(ISNULL(ComDamage, 0)) AS Destroyed FROM {s}.dbo.[huSummaryDamage]
                        WHERE GenBldgOrGenOcc IN('COM', 'AGR', 'GOV', 'EDU', 'REL','RES', 'IND')
                        and ReturnPeriod = '{rp}'
                        and huScenarioName = '{sc}'
                        GROUP BY GenBldgOrGenOcc""".format(
                    s=self.name, sc=self.scenario, rp=self.returnPeriod
                ),
                "tsunami": """SELECT 
                        CASE 
                            WHEN CHARINDEX('_', tsHazNsiGbs.NsiID) > 0 THEN LEFT(PARSENAME(REPLACE(tsHazNsiGbs.NsiID, '_', '.'), 2), 3)
                            ELSE LEFT(tsHazNsiGbs.NsiID, 3)
                        END As Occupancy,
                        COUNT({s}.dbo.tsHazNsiGbs.NsiID) As Total,
                        COUNT(CASE WHEN {s}.dbo.tsHazNsiGbs.ValStruct > 0 AND
                        (BldgLoss/({s}.dbo.tsHazNsiGbs.ValStruct))
                        <= 0.05 THEN 1 ELSE NULL END) As Affected,
                        COUNT(CASE WHEN {s}.dbo.tsHazNsiGbs.ValStruct > 0 AND
                        (BldgLoss/({s}.dbo.tsHazNsiGbs.ValStruct))
                        > 0.05 AND (BldgLoss/({s}.dbo.tsHazNsiGbs.ValStruct))
                        <= 0.3 THEN 1 ELSE NULL END) As Minor,
                        COUNT(CASE WHEN {s}.dbo.tsHazNsiGbs.ValStruct > 0 AND
                        (BldgLoss/({s}.dbo.tsHazNsiGbs.ValStruct+{s}.dbo.tsHazNsiGbs.ValCont))
                        > 0.3 AND (BldgLoss/({s}.dbo.tsHazNsiGbs.ValStruct))
                        <= 0.5 THEN 1 ELSE NULL END) As Major,
                        COUNT(CASE WHEN {s}.dbo.tsHazNsiGbs.ValStruct > 0  AND
                        (BldgLoss/({s}.dbo.tsHazNsiGbs.ValStruct))
                        > 0.5 THEN 1 ELSE NULL END) As Destroyed
                        FROM {s}.dbo.tsHazNsiGbs FULL JOIN {s}.dbo.tsNsiGbs
                        ON {s}.dbo.tsHazNsiGbs.NsiID = {s}.dbo.tsNsiGbs.NsiID
                        FULL JOIN [{s}].[dbo].[tsFRNsiGbs] ON {s}.dbo.tsNsiGbs.NsiID =
                        [{s}].[dbo].[tsFRNsiGbs].NsiID WHERE {s}.dbo.tsHazNsiGbs.NsiID IS NOT NULL
                        GROUP BY
                        CASE 
                            WHEN CHARINDEX('_', tsHazNsiGbs.NsiID) > 0 THEN LEFT(PARSENAME(REPLACE(tsHazNsiGbs.NsiID, '_', '.'), 2), 3)
                            ELSE LEFT(tsHazNsiGbs.NsiID, 3)
                        END""".format(
                    s=self.name
                ),
            }

            df = self.query(sqlDict[self.hazard])
            return StudyRegionDataFrame(self, df)
        except:
            print("Unexpected error:", sys.exc_info()[0])
            raise

    def getBuildingDamageByType(self):
        """Queries the building damage by structure type for a study region from the local Hazus SQL Server database

        Returns:
            df: pandas dataframe -- a dataframe of building damage by structure type
        """
        try:
            constant = 1000
            sqlDict = {
                "earthquake": """SELECT eqBldgType AS BldgType,
                        SUM(ISNULL(PDsNoneBC, 0)) As NoDamage, SUM(ISNULL(PDsSlightBC, 0)) AS Affected,
                        SUM(ISNULL(PDsModerateBC, 0)) AS Minor, SUM(ISNULL(PDsExtensiveBC, 0))
                        AS Major, SUM(ISNULL(PDsCompleteBC, 0)) AS Destroyed
                        FROM {s}.dbo.[eqTractDmg] WHERE DmgMechType = 'STR'
                        GROUP BY eqBldgType""".format(
                    s=self.name
                ),
                "flood": """SELECT BldgType, 
                SUM(ISNULL(TotalLoss, 0)) * {c} AS TotalLoss,
                        SUM(ISNULL(BuildingLoss, 0)) * {c} AS BldgLoss, 
                        SUM(ISNULL(ContentsLoss, 0)) * {c} AS ContLoss
                        FROM {s}.dbo.[flFRGBSEcLossByGBldgType] 
                        where StudyCaseId = (select StudyCaseID from {s}.[dbo].[flStudyCase] where StudyCaseName = '{sc}')
                        and ReturnPeriodId = '{rp}'
                        GROUP BY BldgType""".format(
                    s=self.name, c=constant, sc=self.scenario, rp=self.returnPeriod
                ),
                "hurricane": """SELECT 
                            GenBldgOrGenOcc AS [Building Type],
                            SUM(ISNULL(NonDamage, 0)) As NoDamage, 
                            SUM(ISNULL(MinDamage, 0)) AS Affected,
                            SUM(ISNULL(ModDamage, 0)) AS Minor, 
                            SUM(ISNULL(SevDamage, 0)) AS Major,
                            SUM(ISNULL(ComDamage, 0)) AS Destroyed 
                        FROM {s}.dbo.[huSummaryDamage]
                        WHERE GenBldgOrGenOcc IN ('CONCRETE', 'MASONRY', 'STEEL', 'WOOD', 'MH')
                        AND ReturnPeriod = '{rp}' 
                        AND huScenarioName = '{sc}'
                        GROUP BY GenBldgOrGenOcc""".format(
                    s=self.name, sc=self.scenario, rp=self.returnPeriod
                ),
                "tsunami": """SELECT
                            eqBldgType AS BldgType,
                            [Description],
                            COUNT({s}.dbo.tsHazNsiGbs.NsiID) As Structures,
                            COUNT(CASE WHEN {s}.dbo.tsHazNsiGbs.ValStruct > 0 AND
                            (BldgLoss/({s}.dbo.tsHazNsiGbs.ValStruct))
                            <= 0.05 THEN 1 ELSE NULL END) As Affected,
                        COUNT(CASE WHEN {s}.dbo.tsHazNsiGbs.ValStruct > 0 AND
                        (BldgLoss/({s}.dbo.tsHazNsiGbs.ValStruct))
                        > 0.05 AND (BldgLoss/({s}.dbo.tsHazNsiGbs.ValStruct))
                        <= 0.3 THEN 1 ELSE NULL END) As Minor,
                        COUNT(CASE WHEN {s}.dbo.tsHazNsiGbs.ValStruct > 0 AND
                        (BldgLoss/({s}.dbo.tsHazNsiGbs.ValStruct))
                        > 0.3 AND (BldgLoss/({s}.dbo.tsHazNsiGbs.ValStruct))
                        <= 0.5 THEN 1 ELSE NULL END) As Major,
                        COUNT(CASE WHEN {s}.dbo.tsHazNsiGbs.ValStruct > 0 AND
                        (BldgLoss/({s}.dbo.tsHazNsiGbs.ValStruct))
                        > 0.5 THEN 1 ELSE NULL END) As Destroyed
                        FROM {s}.dbo.tsHazNsiGbs FULL JOIN {s}.dbo.eqclBldgType
                        ON {s}.dbo.tsHazNsiGbs.EqBldgTypeID = {s}.dbo.eqclBldgType.DisplayOrder
                        FULL JOIN [{s}].[dbo].[tsFRNsiGbs] ON {s}.dbo.tsHazNsiGbs.NsiID =
                        [{s}].[dbo].[tsFRNsiGbs].NsiID WHERE EqBldgTypeID IS NOT NULL
                        GROUP BY eqBldgType, [Description]""".format(
                    s=self.name
                ),
            }

            df = self.query(sqlDict[self.hazard])
            return StudyRegionDataFrame(self, df)
        except:
            print("Unexpected error:", sys.exc_info()[0])
            raise

    def getInjuries(self):
        """Queries the injuries for a study region from the local Hazus SQL Server database

        Returns:
            df: pandas dataframe -- a dataframe of injuries
        """
        try:

            # NOTE injuries not available for flood model - placeholder below
            # NOTE injuries not available for hurricane model - placeholder below
            sqlDict = {
                "earthquake": """SELECT Tract as tract, SUM(CASE WHEN CasTime = 'N' THEN Level1Injury
                        ELSE 0 END) AS Injury_NightLevel1, SUM(CASE WHEN CasTime = 'N'
                        THEN Level2Injury ELSE 0 END) AS Injury_NightLevel2, SUM(CASE WHEN CasTime = 'N'
                        THEN Level3Injury ELSE 0 END) AS Injury_NightLevel3, 
                        SUM(CASE WHEN CasTime = 'N' THEN Level4Injury ELSE 0 END) AS Injury_NightLevel4,
                        SUM(CASE WHEN CasTime = 'N'
                        THEN Level1Injury ELSE 0 END) AS Injury_DayLevel1,  SUM(CASE WHEN CasTime = 'D'
                        THEN Level2Injury ELSE 0 END) AS Injury_DayLevel2, SUM(CASE WHEN CasTime = 'D'
                        THEN Level3Injury ELSE 0 END) AS Injury_DayLevel3,
                        SUM(CASE WHEN CasTime = 'D' THEN Level4Injury ELSE 0 END) AS Injury_DayLevel4
                         FROM {s}.dbo.[eqTractCasOccup]
                        WHERE CasTime IN ('N', 'D') AND InOutTot = 'Tot' GROUP BY Tract""".format(
                    s=self.name
                ),
                "flood": None,
                "hurricane": None,
                "tsunami": """SELECT
                        cdf.CensusBlock as block,
                        SUM(cdf.InjuryDayTotal) as Injuries_DayFair,
                        SUM(cdg.InjuryDayTotal) As Injuries_DayGood,
                        SUM(cdp.InjuryDayTotal) As Injuries_DayPoor,
                        SUM(cnf.InjuryNightTotal) As Injuries_NightFair,
                        SUM(cng.InjuryNightTotal) As Injuries_NightGood,
                        SUM(cnp.InjuryNightTotal) As Injuries_NightPoor
                            FROM {s}.dbo.tsCasualtyDayFair as cdf
                                FULL JOIN {s}.dbo.tsCasualtyDayGood as cdg
                                    ON cdf.CensusBlock = cdg.CensusBlock
                                FULL JOIN {s}.dbo.tsCasualtyDayPoor as cdp
                                    ON cdf.CensusBlock = cdp.CensusBlock
                                FULL JOIN {s}.dbo.tsCasualtyNightFair as cnf
                                    ON cdf.CensusBlock = cnf.CensusBlock
                                FULL JOIN {s}.dbo.tsCasualtyNightGood as cng
                                    ON cdf.CensusBlock = cng.CensusBlock
                                FULL JOIN {s}.dbo.tsCasualtyNightPoor as cnp
                                    ON cdf.CensusBlock = cnp.CensusBlock
                                group by cdf.CensusBlock""".format(
                    s=self.name
                ),
            }
            if (sqlDict[self.hazard] == None) and self.hazard == "hurricane":
                df = pd.DataFrame(columns=["tract", "Injuries"])
            elif (sqlDict[self.hazard] == None) and self.hazard == "flood":
                df = pd.DataFrame(columns=["block", "Injuries"])
            else:
                df = self.query(sqlDict[self.hazard])
            return StudyRegionDataFrame(self, df)
        except:
            print("Unexpected error:", sys.exc_info()[0])
            raise

    def getFatalities(self):
        """Queries the fatalities for a study region from the local Hazus SQL Server database

        Returns:
            df: pandas dataframe -- a dataframe of fatalities
        """
        try:

            # NOTE fatatilies not available for flood model - placeholder below
            # NOTE fatatilies not available for hurricane model - placeholder below
            sqlDict = {
                "earthquake": """SELECT Tract as tract, SUM(CASE WHEN CasTime = 'N'
                        THEN Level4Injury ELSE 0 End) AS Fatalities_Night, SUM(CASE WHEN CasTime = 'D'
                        THEN Level4Injury ELSE 0 End) AS Fatalities_Day FROM {s}.dbo.[eqTractCasOccup]
                        WHERE CasTime IN ('N', 'D') AND InOutTot = 'Tot' GROUP BY Tract""".format(
                    s=self.name
                ),
                "flood": None,
                "hurricane": None,
                "tsunami": """SELECT
                        cdf.CensusBlock as block,
                        SUM(cdf.FatalityDayTotal) As Fatalities_DayFair,
                        SUM(cdg.FatalityDayTotal) As Fatalities_DayGood,
                        SUM(cdp.FatalityDayTotal) As Fatalities_DayPoor,
                        SUM(cnf.FatalityNightTotal) As Fatalities_NightFair,
                        SUM(cng.FatalityNightTotal) As Fatalities_NightGood,
                        SUM(cnp.FatalityNightTotal) As Fatalities_NightPoor
                            FROM {s}.dbo.tsCasualtyDayFair as cdf
                                FULL JOIN {s}.dbo.tsCasualtyDayGood as cdg
                                    ON cdf.CensusBlock = cdg.CensusBlock
                                FULL JOIN {s}.dbo.tsCasualtyDayPoor as cdp
                                    ON cdf.CensusBlock = cdp.CensusBlock
                                FULL JOIN {s}.dbo.tsCasualtyNightFair as cnf
                                    ON cdf.CensusBlock = cnf.CensusBlock
                                FULL JOIN {s}.dbo.tsCasualtyNightGood as cng
                                    ON cdf.CensusBlock = cng.CensusBlock
                                FULL JOIN {s}.dbo.tsCasualtyNightPoor as cnp
                                    ON cdf.CensusBlock = cnp.CensusBlock
                                group by cdf.CensusBlock""".format(
                    s=self.name
                ),
            }

            if (sqlDict[self.hazard] == None) and self.hazard == "hurricane":
                df = pd.DataFrame(columns=["tract", "Fatalities"])
            elif (sqlDict[self.hazard] == None) and self.hazard == "flood":
                df = pd.DataFrame(columns=["block", "Fatalities"])
            else:
                df = self.query(sqlDict[self.hazard])
            return StudyRegionDataFrame(self, df)
        except:
            print("Unexpected error:", sys.exc_info()[0])
            raise

    def getDisplacedHouseholds(self):
        """Queries the displaced households for a study region from the local Hazus SQL Server database

        Returns:
            df: pandas dataframe -- a dataframe of displaced households
        """
        try:

            # TODO check to see if flood is displaced households or population -- database says pop
            # NOTE displaced households not available in tsunami model - placeholder below
            sqlDict = {
                "earthquake": """select Tract as tract, SUM(DisplacedHouseholds) as DisplacedHouseholds from {s}.dbo.eqTract group by Tract""".format(
                    s=self.name
                ),
                # TODO: Confirm if this is displaced household, and not displaced population (for the summation) - BC
                "flood": """select CensusBlock as block, SUM(DisplacedPop) as DisplacedPopulation from {s}.dbo.flFRShelter
                    where StudyCaseId = (select StudyCaseID from {s}.[dbo].[flStudyCase] where StudyCaseName = '{sc}')
                    and ReturnPeriodId = '{rp}'
                    group by CensusBlock""".format(
                    s=self.name, sc=self.scenario, rp=self.returnPeriod
                ),
                "hurricane": """select TRACT as tract, SUM(DISPLACEDHOUSEHOLDS) as DisplacedHouseholds from {s}.dbo.huShelterResultsT
                        where Return_Period = '{rp}' 
                        and huScenarioName = '{sc}'
                    group by Tract""".format(
                    s=self.name, sc=self.scenario, rp=self.returnPeriod
                ),
                "tsunami": None,
            }

            if (sqlDict[self.hazard] == None) and self.hazard == "tsunami":
                df = pd.DataFrame(columns=["block", "DisplacedHouseholds"])
            else:
                df = self.query(sqlDict[self.hazard])
            return StudyRegionDataFrame(self, df)
        except:
            print("Unexpected error:", sys.exc_info()[0])
            raise

    def getShelterNeeds(self):
        """Queries the short term shelter needs for a study region from the local Hazus SQL Server database

        Returns:
            df: pandas dataframe -- a dataframe of short term shelter needs
        """
        try:

            # NOTE shelter needs aren't available for the tsunami model - placeholder below
            sqlDict = {
                "earthquake": """select Tract as tract, SUM(ShortTermShelter) as ShelterNeeds from {s}.dbo.eqTract group by Tract""".format(
                    s=self.name
                ),
                "flood": """select CensusBlock as block, SUM(ShortTermNeeds) as ShelterNeeds from {s}.dbo.flFRShelter
                    where StudyCaseId = (select StudyCaseID from {s}.[dbo].[flStudyCase] where StudyCaseName = '{sc}')
                    and ReturnPeriodId = '{rp}'
                    group by CensusBlock""".format(
                    s=self.name, sc=self.scenario, rp=self.returnPeriod
                ),
                "hurricane": """select TRACT as tract, SUM(SHORTTERMSHELTERNEEDS) as ShelterNeeds from {s}.dbo.huShelterResultsT
                    where Return_Period = '{rp}' 
                    and huScenarioName = '{sc}'
                     group by Tract
                        """.format(
                    s=self.name, sc=self.scenario, rp=self.returnPeriod
                ),
                "tsunami": None,
            }
            if (sqlDict[self.hazard] == None) and self.hazard == "tsunami":
                df = pd.DataFrame(columns=["block", "ShelterNeeds"])
            else:
                df = self.query(sqlDict[self.hazard])
            return StudyRegionDataFrame(self, df)
        except:
            print("Unexpected error:", sys.exc_info()[0])
            raise

    def getDebris(self):
        """Queries the debris for a study region from the local Hazus SQL Server database

        Returns:
            df: pandas dataframe -- a dataframe of debris
        """
        try:
            constant = 1000
            # NOTE debris not available for tsunami model - placeholder below
            # NOTE hurricane is the only model NOT in thousands of tons. It doesn't need to be multipled by the constant
            sqlDict = {
                "earthquake": """select Tract as tract, SUM(DebrisW) * {c} as DebrisBW, SUM(DebrisS) * {c} as DebrisCS, SUM(DebrisTotal) * {c} as DebrisTotal from {s}.dbo.eqTract group by Tract""".format(
                    s=self.name, c=constant
                ),
                "flood": """select CensusBlock as block, 
                SUM(FinishTons) * {c} as FinishTonsTotal,
                SUM(StructureTons) * {c} as StructureTonsTotal,
                SUM(FoundationTons) * {c} as FoundationTonsTotal,
                SUM(FinishTons) + SUM(StructureTons) + SUM(FoundationTons) as DebrisTotal
                 from {s}.dbo.flFRDebris
                    where StudyCaseId = (select StudyCaseID from {s}.[dbo].[flStudyCase] where StudyCaseName = '{sc}')
                    and ReturnPeriodId = '{rp}'
                    group by CensusBlock""".format(
                    s=self.name, c=constant, sc=self.scenario, rp=self.returnPeriod
                ),
                "hurricane": """select d.tract, d.DebrisTotal, d.DebrisBW, d.DebrisCS, d.DebrisTree, (d.DebrisTree * p.TreeCollectionFactor) as DebrisEligibleTree from
                    (select Tract as tract, SUM(BRICKANDWOOD) as DebrisBW, SUM(CONCRETEANDSTEEL) as DebrisCS, SUM(Tree) as DebrisTree, SUM(BRICKANDWOOD + CONCRETEANDSTEEL + Tree) as DebrisTotal from {s}.dbo.huDebrisResultsT
                        where Return_Period = '{rp}'
                        and huScenarioName = '{sc}'
                        group by Tract) d
                        inner join (select Tract as tract, TreeCollectionFactor from {s}.dbo.huTreeParameters) p
                        on d.tract = p.tract
                """.format(
                    s=self.name, sc=self.scenario, rp=self.returnPeriod
                ),
                "tsunami": """select CensusBlock as block, SUM(FinishTons) * {c} as DebrisTotal from {s}.dbo.flFRDebris group by CensusBlock""".format(
                    s=self.name, c=constant
                ),
            }

            df = self.query(sqlDict[self.hazard])
            return StudyRegionDataFrame(self, df)
        except:
            print("Unexpected error:", sys.exc_info()[0])
            raise

    def getHazardsAnalyzed(self, returnType="list"):
        """Queries the local Hazus SQL Server database and returns all hazards analyzed

        Key Argument:
            returnType: string -- choices: 'list', 'dict'
        Returns:
            df: pandas dataframe -- a dataframe of the hazards analyzed
        """
        try:
            sql = (
                "select * from [syHazus].[dbo].[syStudyRegion] where [RegionName] = '"
                + self.name
                + "'"
            )
            df = self.query(sql)
            hazardsDict = {
                "earthquake": df["HasEqHazard"][0],
                "hurricane": df["HasHuHazard"][0],
                "tsunami": df["HasTsHazard"][0],
                "flood": df["HasFlHazard"][0],
            }
            if returnType == "dict":
                return hazardsDict
            if returnType == "list":
                hazardsList = list(
                    filter(lambda x: hazardsDict[x], hazardsDict))
                return hazardsList
        except Exception as e:
            print('\n')
            print(e)
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            print(fname)
            print(exc_type, exc_tb.tb_lineno)
            print('\n')

            print("Unexpected error:", sys.exc_info()[0])
            raise

    def getHazardGeoDataFrame(self, round=True):
        """Queries the local Hazus SQL Server database and returns a geodataframe of the hazard

        Keyword Arguments:
            round: boolean -- if True, the hazard rasters will be rounded to the nearest integer (default: True)

        Returns:
            hazardGDF: geopandas GeoDataFrame -- a geodataframe containing the spatial hazard data
        """
        if hasattr(self, 'hprComment'):
            try:
                hazard = self.hazard
                # the operator controls if hazard data includes zero values ('>=' does include; '>' doesn't include)
                # TODO operator is only part of hurricane - build operator into other hazards
                operator = '>='
                hazardDict = {}
                #EARTHQUAKE
                if hazard == 'earthquake':
                    try:
                        path = Path.joinpath(self.tempdir, self.name,'shape/pga.shp') #needs testing
                        gdf = gpd.read_file(path)
                    except:
                        #print('Unable to use raster...defaulting to database')
                        sql = """SELECT a.tract, PARAMVALUE, PGA_g, geometry FROM
                            (SELECT [Tract] as tract ,[PGA] as PARAMVALUE, [PGA] as PGA_g FROM {s}.[dbo].[eqTract]) a
                            inner join
                            (SELECT Tract as tract, Shape.STAsText() AS geometry FROM {s}.dbo.hzTract) b
                            on a.tract = b.tract""".format(s=self.name)
                        gdf = self.query(sql)
                    hazardDict['Peak Ground Acceleration (g)'] = gdf

                                    
                #FLOOD from TEST branch
                # TODO: Fix this to pass return period - BC
                if hazard == 'flood':
                    returnPeriodNumber = str(''.join(filter(str.isdigit, self.returnPeriod)))
                    # this is a list instead of a dictionary, because some of the 'name' properties are the same
                    pathHPRScenario = Path.joinpath(self.tempDir,self.scenario)
                    hazardPathDicts = [
                        #SLOSH MOM's TBD
                        #Deterministic Riverine
                        {'name': 'Water Depth (ft)', 'returnPeriod': '0', 'path': Path.joinpath(pathHPRScenario,'Riverine/Depth/mix0/w001001.adf')},
                        #Deterministic Coastal
                        {'name': 'Water Depth (ft)', 'returnPeriod': '0', 'path': Path.joinpath(pathHPRScenario,'Coastal/Depth/mix0/w001001.adf')},
                        #Probabilistic Riverine 5-year
                        {'name': 'Water Depth (ft) - 5-year', 'returnPeriod': '5', 'path': Path.joinpath(pathHPRScenario,'Riverine/Depth/rpd5/w001001.adf')},
                        #Probabilistic Riverine 10-year
                        {'name': 'Water Depth (ft) - 10-year', 'returnPeriod': '10', 'path': Path.joinpath(pathHPRScenario,'Riverine/Depth/rpd10/w001001.adf')},
                        #Probabilistic Riverine 25-year
                        {'name': 'Water Depth (ft) - 25-year', 'returnPeriod': '25', 'path': Path.joinpath(pathHPRScenario,'Riverine/Depth/rpd25/w001001.adf')},
                        #Probabilistic Riverine 50-year
                        {'name': 'Water Depth (ft) - 50-year', 'returnPeriod': '50', 'path': Path.joinpath(pathHPRScenario,'Riverine/Depth/rpd50/w001001.adf')},
                        #Probabilistic Riverine 100-year
                        {'name': 'Water Depth (ft) - 100-year', 'returnPeriod': '100', 'path': Path.joinpath(pathHPRScenario,'Riverine/Depth/rpd100/w001001.adf')},
                        #Probabilistic Riverine 500-year
                        {'name': 'Water Depth (ft) - 500-year', 'returnPeriod': '500', 'path': Path.joinpath(pathHPRScenario,'Riverine/Depth/rpd500/w001001.adf')},
                        #Probabilistic Coastal 5-year
                        {'name': 'Water Depth (ft) - 5-year', 'returnPeriod': '5', 'path': Path.joinpath(pathHPRScenario,'Coastal/Depth/rpd5/w001001.adf')},
                        #Probabilistic Coastal 10-year
                        {'name': 'Water Depth (ft) - 10-year', 'returnPeriod': '10', 'path': Path.joinpath(pathHPRScenario,'Coastal/Depth/rpd10/w001001.adf')},
                        #Probabilistic Coastal 25-year
                        {'name': 'Water Depth (ft) - 25-year', 'returnPeriod': '25', 'path': Path.joinpath(pathHPRScenario,'Coastal/Depth/rpd25/w001001.adf')},
                        #Probabilistic Coastal 50-year
                        {'name': 'Water Depth (ft) - 50-year', 'returnPeriod': '50', 'path': Path.joinpath(pathHPRScenario,'Coastal/Depth/rpd50/w001001.adf')},
                        #Probabilistic Coastal 100-year
                        {'name': 'Water Depth (ft) - 100-year', 'returnPeriod': '100', 'path': Path.joinpath(pathHPRScenario,'Coastal/Depth/rpd100/w001001.adf')},
                        #Probabilistic Coastal 500-year
                        {'name': 'Water Depth (ft) - 500-year', 'returnPeriod': '500', 'path': Path.joinpath(pathHPRScenario,'Coastal/Depth/rpd500/w001001.adf')}
                    ]

                    #FIM Flood Inundation Mapping; Can be 1 or many
                    #unzippedHPRname/scenarioname/Riverine/Depth/returnperiodname(rpd{X}))/w001001.adf
                    #Riverine i.e. nora_temp\nora_08\Riverine\Depth\rpd8\w001001.adf with a return period of rpd8
                    Selected_Rtn_Period = self.getFIMSelected_Rtn_Period()
                    Selected_Rtn_PeriodDict = {'name':'FIM: '+self.returnPeriod.strip(), 'returnPeriod':self.returnPeriod.strip(),
                                               'path':Path.joinpath(pathHPRScenario,'Riverine/Depth','rpd'+Selected_Rtn_Period,'w001001.adf')}
                    hazardPathDicts.append(Selected_Rtn_PeriodDict)
                    #Coastal
                    Selected_Rtn_PeriodDict = {'name':'FIM: '+self.returnPeriod.strip(), 'returnPeriod':self.returnPeriod.strip(),
                                               'path':Path.joinpath(pathHPRScenario,'Coastal/Depth','rpd'+Selected_Rtn_Period,'w001001.adf')}
                    hazardPathDicts.append(Selected_Rtn_PeriodDict)
                    #Riverine i.e. SanDiego_Final_temp\New_All4\Riverine\Depth\mix0\w001001.adf with a return period of 'mix0  '
                    Selected_Rtn_PeriodDict = {'name':'FIM: '+self.returnPeriod.strip(), 'returnPeriod':self.returnPeriod.strip(),
                                               'path':Path.joinpath(pathHPRScenario,'Riverine/Depth','mix0','w001001.adf')}
                    hazardPathDicts.append(Selected_Rtn_PeriodDict)
                    #Coastal 
                    Selected_Rtn_PeriodDict = {'name':'FIM: '+self.returnPeriod.strip(), 'returnPeriod':self.returnPeriod.strip(),
                                               'path':Path.joinpath(pathHPRScenario,'Coastal/Depth','mix0','w001001.adf')}
                    hazardPathDicts.append(Selected_Rtn_PeriodDict)

                    for idx in range(len(hazardPathDicts)):
                        if hazardPathDicts[idx]['returnPeriod'] == self.returnPeriod.strip() or self.returnPeriod == 'Mix0':
                            try:
                                if hazardPathDicts[idx]['path'].exists():
                                    raster = rio.open(hazardPathDicts[idx]['path'])
                                    affine = raster.meta.get('transform')
                                    crs = raster.meta.get('crs')
                                    band = raster.read(1)
                                    band = np.where(band < 0, 0, band)
                                    if round:
                                        band = np.around(band, 0)
                                    #features.shapes requires the input array dtype be one of 'int16', 'int32', 'uint8', 'uint16', 'float32'
                                    #This is a brute force way to convert the input dtype to a supported dtype
                                    if 'int' in str(band.dtype):
                                        band = band.astype('int16', copy=False)
                                    if 'float' in str(band.dtype):
                                        band = band.astype('float32', copy=False)
                                    geoms = []
                                    for geometry, value in features.shapes(band, transform=affine):
                                        try:
                                            if value >= 1:
                                                result = {'properties': {
                                                    'PARAMVALUE': value}, 'geometry': geometry}
                                                geoms.append(result)
                                        except:
                                            pass
                                    gdf = gpd.GeoDataFrame.from_features(geoms)
                                    gdf["Depth_ft"] = gdf["PARAMVALUE"]
                                    gdf.crs = crs
                                    gdf.geometry = gdf.geometry.to_crs(epsg=4326)
                                    hazardDict[hazardPathDicts[idx]['name']] = gdf
                            except Exception as e:
                                print('Exception hazardPathDicts:')
                                print(e)
                                pass

                                
                #HURRICANE        
                if hazard == 'hurricane':
                    try:
                        hazardPathDict = {
                            # Historic
                            'Historic Wind Speeds (mph)':
                            {'returnPeriod': '0',
                                'path': "SELECT Tract as tract, PeakGust as PARAMVALUE FROM {s}.[dbo].[hv_huHistoricWindSpeedT] WHERE PeakGust {o} 0 AND huScenarioName = '{sc}'".format(s=self.name, sc=self.scenario, o=operator)},
                            # Deterministic
                            'Wind Speeds (mph)':
                            {'returnPeriod': '0', 'path': "SELECT Tract as tract, PeakGust as PARAMVALUE FROM {s}.[dbo].[RgnExphuDetermWindSpeedResults] WHERE PeakGust {o} 0 AND huScenarioName = '{sc}'".format(
                                s=self.name, sc=self.scenario, o=operator)},
                            # Probabilistic 10-year
                            'Wind Speeds (mph) - 10-year':
                            {'returnPeriod': '10', 'path': 'SELECT Tract as tract, wRtnP1 as PARAMVALUE FROM {s}.[dbo].[huRPWindSpeeds] where wRtnP1 {o} 0'.format(
                                s=self.name, o=operator)},
                            # Probabilistic 20-year
                            'Wind Speeds (mph) - 20-year':
                            {'returnPeriod': '20', 'path': 'SELECT Tract as tract, wRtnP2 as PARAMVALUE FROM {s}.[dbo].[huRPWindSpeeds] where wRtnP2 {o} 0'.format(
                                s=self.name, o=operator)},
                            # Probabilistic 50-year
                            'Wind Speeds (mph) - 50-year':
                            {'returnPeriod': '50', 'path': 'SELECT Tract as tract, wRtnP3 as PARAMVALUE FROM {s}.[dbo].[huRPWindSpeeds] where wRtnP3 {o} 0'.format(
                                s=self.name, o=operator)},
                            # Probabilistic 100-year
                            'Wind Speeds (mph) - 100-year':
                            {'returnPeriod': '100', 'path': 'SELECT Tract as tract, wRtnP4 as PARAMVALUE FROM {s}.[dbo].[huRPWindSpeeds] where wRtnP4 {o} 0'.format(
                                s=self.name, o=operator)},
                            # Probabilistic 200-year
                            'Wind Speeds (mph) - 200-year':
                            {'returnPeriod': '200', 'path': 'SELECT Tract as tract, wRtnP5 as PARAMVALUE FROM {s}.[dbo].[huRPWindSpeeds] where wRtnP5 {o} 0'.format(
                                s=self.name, o=operator)},
                            # Probabilistic 500-year
                            'Wind Speeds (mph) - 500-year':
                            {'returnPeriod': '500', 'path': 'SELECT Tract as tract, wRtnP6 as PARAMVALUE FROM {s}.[dbo].[huRPWindSpeeds] where wRtnP6 {o} 0'.format(
                                s=self.name, o=operator)},
                            # Probabilistic 1000-year
                            'Wind Speeds (mph) - 1000-year':
                            {'returnPeriod': '1000', 'path': 'SELECT Tract as tract, wRtnP7 as PARAMVALUE FROM {s}.[dbo].[huRPWindSpeeds] where wRtnP7 {o} 0'.format(
                                s=self.name, o=operator)}
                        }
                        for key in hazardPathDict.keys():
                            if hazardPathDict[key]['returnPeriod'] == self.returnPeriod:
                                try:
                                    df = self.query(hazardPathDict[key]['path'])
                                    if len(df) > 0:
                                        sdf = StudyRegionDataFrame(self, df)
                                        sdf["Peak_Gust"] = sdf["PARAMVALUE"]
                                        sdf = sdf.addGeometry()
                                        sdf['geometry'] = sdf['geometry'].apply(
                                            loads)
                                        gdf = gpd.GeoDataFrame(
                                            sdf, geometry='geometry')
                                        hazardDict[key] = gdf
                                except:
                                    pass
                    except:
                        pass
                #TSUNAMI
                if hazard == 'tsunami':
                    raster = rio.open(Path.joinpath(self.tempDir, 'maxdg_ft/w001001.adf')) #needs testing
                    affine = raster.meta.get('transform')
                    crs = raster.meta.get('crs')
                    band = raster.read(1)
                    band = np.where(band < 0, 0, band)
                    if round:
                        band = np.around(band, 0)
                    #features.shapes requires the input array dtype be one of 'int16', 'int32', 'uint8', 'uint16', 'float32'
                    #This is a brute force way to convert the input dtype to a supported dtype
                    if 'int' in str(band.dtype):
                        band = band.astype('int16', copy=False)
                    if 'float' in str(band.dtype):
                        band = band.astype('float32', copy=False)

                    geoms = []
                    for geometry, value in features.shapes(band, transform=affine):
                        try:
                            if value >= 1:
                                result = {'properties': {
                                    'PARAMVALUE': value}, 'geometry': geometry}
                            geoms.append(result)
                        except:
                            pass
                    gdf = gpd.GeoDataFrame.from_features(geoms)
                    gdf.PARAMVALUE[gdf.PARAMVALUE > 60] = 0
                    gdf["Depth_ft"] = gdf["PARAMVALUE"]
                    gdf.crs = crs
                    gdf.geometry = gdf.geometry.to_crs(epsg=4326)
                    hazardDict['Water Depth (ft)'] = gdf

                keys = list(hazardDict.keys())
                if len(hazardDict.keys()) > 1:
                    gdf = gpd.GeoDataFrame(pd.concat([hazardDict[x] for x in keys], ignore_index=True), geometry='geometry')
                else:
                    gdf = hazardDict[keys[0]]
                sdf = StudyRegionDataFrame(self, gdf)
                sdf.title = keys[0]
                
                # TODO: Remove this - is it needed ? Currently throws off reports - BC
                # if hazard == 'earthquake':
                #     try:
                #         sdf.rename(columns={'PARAMVALUE': 'PGA_g'}, inplace=True)
                #     except Exception as e:
                #         print(e)
                # if hazard == 'flood':
                #     try:
                #         sdf.rename(columns={'PARAMVALUE': 'Depth_ft'}, inplace=True)
                #     except Exception as e:
                #         print(e)
                    
                return sdf
            except Exception as e:
                print("Unexpected error getHazardGeoDataFrame:", sys.exc_info()[0])
                print(e)
                raise
        else:
            try:
                hazard = self.hazard
                # the operator controls if hazard data includes zero values ('>=' does include; '>' doesn't include)
                # TODO operator is only part of hurricane - build operator into other hazards
                operator = ">="
                hazardDict = {}
                if hazard == "earthquake":
                    try:
                        path = "C:/HazusData/Regions/" + self.name + "/shape/pga.shp"
                        gdf = gpd.read_file(path)
                    except:
                        print('unable to use raster...defaulting to database')
                        sql = """SELECT a.tract, PARAMVALUE, PGA_g, geometry FROM
                            (SELECT [Tract] as tract ,[PGA] as PARAMVALUE, [PGA] as PGA_g FROM {s}.[dbo].[eqTract]) a
                            inner join
                            (SELECT Tract as tract, Shape.STAsText() AS geometry FROM {s}.dbo.hzTract) b
                            on a.tract = b.tract""".format(
                            s=self.name
                        )
                        gdf = self.query(sql)
                    hazardDict["Peak Ground Acceleration (g)"] = gdf
                if hazard == "flood":
                    # this is a list instead of a dictionary, because some of the 'name' properties are the same
                    # TODO: Create a loop for this in order to get all scenarios - BC
                    returnPeriodNumber = str(''.join(filter(str.isdigit, self.returnPeriod)))
                    if returnPeriodNumber == 0:
                        hazardPathDicts = [
                            # Deterministic Riverine
                            {
                                "name": "Water Depth (ft)",
                                "returnPeriod": "0",
                                "path": "C:/HazusData/Regions/"
                                + self.name
                                + "/"
                                + self.scenario
                                + "/Riverine/Depth/mix0/w001001.adf",
                            },
                            # Deterministic Coastal
                            {
                                "name": "Water Depth (ft)",
                                "returnPeriod": "0",
                                "path": "C:/HazusData/Regions/"
                                + self.name
                                + "/"
                                + self.scenario
                                + "/Coastal/Depth/mix0/w001001.adf",
                            }
                        ]
                    else:
                        hazardPathDicts = [
                        # Probabilistic Riverine 5-year # TODO - Change this comment - BC
                            {
                                "name": f"Water Depth (ft) - {returnPeriodNumber}-year",
                                "returnPeriod": f"{returnPeriodNumber}",
                                "path": "C:/HazusData/Regions/"
                                + self.name
                                + "/"
                                + self.scenario
                                + ("/Riverine/Depth/rpd" + f"{returnPeriodNumber}/w001001.adf"),
                            },
                            {
                                "name": f"Water Depth (ft) - {returnPeriodNumber}-year",
                                "returnPeriod": f"{returnPeriodNumber}",
                                "path": "C:/HazusData/Regions/"
                                + self.name
                                + "/"
                                + self.scenario
                                + ("/Coastal/Depth/rpd" + f"{returnPeriodNumber}/w001001.adf"),
                            }
                        ]
                    for idx in range(len(hazardPathDicts)):
                        if (
                            hazardPathDicts[idx]["returnPeriod"] == self.returnPeriod
                            or self.returnPeriod == "Mix0"
                        ):
                            try:
                                raster = rio.open(hazardPathDicts[idx]["path"])
                                affine = raster.meta.get("transform")
                                crs = raster.meta.get("crs")
                                band = raster.read(1)
                                band = np.where(band < 0, 0, band)
                                if round:
                                    band = np.rint(band)

                                geoms = []
                                for geometry, value in features.shapes(
                                    band, transform=affine
                                ):
                                    try:
                                        if value >= 1:
                                            result = {
                                                "properties": {"PARAMVALUE": value},
                                                "geometry": geometry,
                                            }
                                        geoms.append(result)
                                    except:
                                        print("Unexpected error:",
                                              sys.exc_info()[0])
                                        pass
                                gdf = gpd.GeoDataFrame.from_features(geoms)
                                gdf["Depth_ft"] = gdf["PARAMVALUE"]
                                gdf.crs = crs
                                gdf.geometry = gdf.geometry.to_crs(epsg=4326)
                                hazardDict[hazardPathDicts[idx]["name"]] = gdf
                            except:
                                pass
                # TODO: Refactor hurricanes (make similar to flood refactor) - BC
                if hazard == "hurricane":
                    try:
                        hazardPathDict = {
                            # Historic
                            "Historic Wind Speeds (mph)": {
                                "returnPeriod": "0",
                                "path": "SELECT Tract as tract, PeakGust * 1.275 as PARAMVALUE FROM {s}.[dbo].[hv_huHistoricWindSpeedT] WHERE PeakGust {o} 50 AND huScenarioName = '{sc}'".format(
                                    s=self.name, sc=self.scenario, o=operator
                                ),
                            },
                            # Deterministic
                            "Wind Speeds (mph)": {
                                "returnPeriod": "0",
                                "path": "SELECT Tract as tract, PeakGust as PARAMVALUE FROM {s}.[dbo].[hv_huDeterminsticWindSpeedResults] WHERE PeakGust {o} 50 AND huScenarioName = '{sc}'".format(
                                    s=self.name, sc=self.scenario, o=operator
                                ),
                            },
                            # Probabilistic 10-year
                            "Wind Speeds (mph) - 10-year": {
                                "returnPeriod": "10",
                                "path": "SELECT Tract as tract, f10yr as PARAMVALUE FROM {s}.[dbo].[huHazardMapWindSpeed] where f10yr {o} 0".format(
                                    s=self.name, o=operator
                                ),
                            },
                            # Probabilistic 20-year
                            "Wind Speeds (mph) - 20-year": {
                                "returnPeriod": "20",
                                "path": "SELECT Tract as tract, f20yr as PARAMVALUE FROM {s}.[dbo].[huHazardMapWindSpeed] where f20yr {o} 0".format(
                                    s=self.name, o=operator
                                ),
                            },
                            # Probabilistic 50-year
                            "Wind Speeds (mph) - 50-year": {
                                "returnPeriod": "50",
                                "path": "SELECT Tract as tract, f50yr as PARAMVALUE FROM {s}.[dbo].[huHazardMapWindSpeed] where f50yr {o} 0".format(
                                    s=self.name, o=operator
                                ),
                            },
                            # Probabilistic 100-year
                            "Wind Speeds (mph) - 100-year": {
                                "returnPeriod": "100",
                                "path": "SELECT Tract as tract, f100yr as PARAMVALUE FROM {s}.[dbo].[huHazardMapWindSpeed] where f100yr {o} 0".format(
                                    s=self.name, o=operator
                                ),
                            },
                            # Probabilistic 200-year
                            "Wind Speeds (mph) - 200-year": {
                                "returnPeriod": "200",
                                "path": "SELECT Tract as tract, f200yr as PARAMVALUE FROM {s}.[dbo].[huHazardMapWindSpeed] where f200yr {o} 0".format(
                                    s=self.name, o=operator
                                ),
                            },
                            # Probabilistic 500-year
                            "Wind Speeds (mph) - 500-year": {
                                "returnPeriod": "500",
                                "path": "SELECT Tract as tract, f500yr as PARAMVALUE FROM {s}.[dbo].[huHazardMapWindSpeed] where f500yr {o} 0".format(
                                    s=self.name, o=operator
                                ),
                            },
                            # Probabilistic 1000-year
                            "Wind Speeds (mph) - 1000-year": {
                                "returnPeriod": "1000",
                                "path": "SELECT Tract as tract, f1000yr as PARAMVALUE FROM {s}.[dbo].[huHazardMapWindSpeed] where f1000yr {o} 0".format(
                                    s=self.name, o=operator
                                ),
                            },
                        }
                        for key in hazardPathDict.keys():
                            if hazardPathDict[key]["returnPeriod"] == self.returnPeriod:
                                try:
                                    df = self.query(hazardPathDict[key]["path"])
                                    if len(df) > 0:
                                        sdf = StudyRegionDataFrame(self, df)
                                        sdf["Peak_Gust"] = sdf["PARAMVALUE"]
                                        sdf = sdf.addGeometry()
                                        sdf["geometry"] = sdf["geometry"].apply(
                                            loads)
                                        gdf = gpd.GeoDataFrame(
                                            sdf, geometry="geometry")
                                        hazardDict[key] = gdf
                                except:
                                    pass
                    except:
                        pass

                if hazard == "tsunami":
                    raster = rio.open(
                        r"C:\HazusData\Regions\{s}\maxdg_ft\w001001.adf".format(
                            s=self.name
                        )
                    )
                    affine = raster.meta.get("transform")
                    crs = raster.meta.get("crs")
                    band = raster.read(1)
                    band = np.where(band < 0, 0, band)
                    if round:
                        band = np.rint(band)

                    geoms = []
                    for geometry, value in features.shapes(band, transform=affine):
                        try:
                            if value >= 1:
                                result = {
                                    "properties": {"PARAMVALUE": value},
                                    "geometry": geometry,
                                }
                            geoms.append(result)
                        except:
                            pass
                    gdf = gpd.GeoDataFrame.from_features(geoms)
                    # TODO: Review this - BC
                    gdf.PARAMVALUE[gdf.PARAMVALUE > 60] = 0
                    gdf["Depth_ft"] = gdf["PARAMVALUE"]
                    gdf.crs = crs
                    gdf.geometry = gdf.geometry.to_crs(epsg=4326)
                    hazardDict["Water Depth (ft)"] = gdf

                keys = list(hazardDict.keys())
                if len(hazardDict.keys()) > 1:
                    gdf = gpd.GeoDataFrame(
                        pd.concat([hazardDict[x]
                                  for x in keys], ignore_index=True),
                        geometry="geometry",
                    )
                else:
                    gdf = hazardDict[keys[0]]
                sdf = StudyRegionDataFrame(self, gdf)
                sdf.title = keys[0]
                return sdf
            except:
                print("Unexpected error getting hazard geodataframe:", sys.exc_info()[0])
                pass

    def getScenarios(self, hazard=''):
        """Get a list of scenarios for a given hazard.

        Arguments:
            hazard: str -- the hazard type to filter scenarios on 'earthquake', 'hurricane', 'flood', 'tsunami'

        Returns:
            scenarios: list -- a list of scenarios for the given hazard
        
        """
        try:
            if hasattr(self, 'hprComment'):
                if self.hazard == 'earthquake':
                    sql = f"SELECT [eqScenarioname] as scenarios FROM [bk_{self.dbName}].[dbo].[RgnExpeqScenario]"
                if self.hazard == 'flood':
                    sql = f"SELECT [StudyCaseName] as scenarios FROM [bk_{self.dbName}].[dbo].[flStudyCase]"
                if self.hazard == 'hurricane':
                    sql = f"SELECT distinct(huScenarioName) as scenarios FROM [bk_{self.dbName}].dbo.[huSummaryLoss]"
                if self.hazard == 'tsunami':
                    sql = f"SELECT [ScenarioName] as scenarios FROM [bk_{self.dbName}].[dbo].[tsScenario]"
            else:
                if self.hazard == "earthquake":
                    sql = f"SELECT TABLE_NAME as name from {self.name}.INFORMATION_SCHEMA.tables"
                    df = self.query(sql)
                    if 'RgnExpeqScenario' in list(df["name"]):
                        sql = f"SELECT [EqScenarioname] as scenarios FROM [{self.dbName}].[dbo].[RgnExpeqScenario]"
                    else:
                        sql = f"SELECT [Scenarioname] as scenarios FROM [{self.dbName}].[dbo].[eqShakeMapScenario]"

                # flood can have many scenarios
                if self.hazard == "flood":
                    sql = f"SELECT [StudyCaseName] as scenarios FROM [{self.dbName}].[dbo].[flStudyCase]"
                
                # NOTE: huTemplateScenario can contain problematic suffixes if syHazus contains duplicate named scenarios; defaulting to distinct query
                # hurricane can only have one active scenario
                if self.hazard == "hurricane":
                    sql = f"SELECT distinct(huScenarioName) as scenarios FROM [{self.dbName}].dbo.[huSummaryLoss]"

                # tsunami can have many scenarios
                if self.hazard == "tsunami":
                    sql = f"SELECT [ScenarioName] as scenarios FROM [{self.dbName}].[dbo].[tsScenario]"
                

            queryset = self.query(sql)
            scenarios = list(queryset['scenarios'])
            return scenarios
        except Exception as e:
            print('\n')
            print(e)
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            print(fname)
            print(exc_type, exc_tb.tb_lineno)
            print('\n')
            print("Unexpected error getScenarios:", sys.exc_info()[0])
            raise

    def getReturnPeriods(self, hazard='', scenario=''):
        """Create a list of return periods for a given hazard and scenario.

            Keyword Arguments:
                hazard: str -- the hazard type 'earthquake', 'flood', 'hurricane', 'tsunami'
                scenario: str -- the scenario name to filter return periods by

            Returns:
                returnPeriods: list -- a list of return periods for a given hazard and scenario
        """
        try:
            if hasattr(self, 'hprComment'):
                if hazard == 'earthquake':
                    sql = f"SELECT [ReturnPeriod] as returnPeriod FROM [bk_{self.dbName}].[dbo].[RgnExpeqScenario]"
                if hazard == 'hurricane':
                    sql = f"SELECT DISTINCT [Return_Period] as returnPeriod FROM [bk_{self.dbName}].[dbo].[hv_huQsrEconLoss] WHERE huScenarioName = '{scenario}'"
                if hazard == 'flood':  # TODO test if this works for UDF
                    sql = f"""SELECT DISTINCT [ReturnPeriodID] as returnPeriod FROM [bk_{self.dbName}].[dbo].[flFRGBSEcLossByTotal]
                            WHERE StudyCaseId = (SELECT StudyCaseID FROM [bk_{self.dbName}].[dbo].[flStudyCase] WHERE StudyCaseName = '{scenario}')"""
                if hazard == 'tsunami':  # selecting 0 due to no return period existing in database
                    sql = f"SELECT '0' as returnPeriod FROM [bk_{self.dbName}].[dbo].[tsScenario]"
            else:
                if self.hazard == 'earthquake':
                    sql = f"SELECT [ReturnPeriod] as returnPeriod FROM [{self.dbName}].[dbo].[RgnExpeqScenario]"
                if self.hazard == 'hurricane':
                    sql = f"SELECT DISTINCT [Return_Period] as returnPeriod FROM [{self.dbName}].[dbo].[hv_huQsrEconLoss] WHERE huScenarioName = '{scenario}'"
                if self.hazard == 'flood':  # TODO test if this works for UDF
                    sql = f"""SELECT DISTINCT [ReturnPeriodID] as returnPeriod FROM [{self.dbName}].[dbo].[flFRGBSEcLossByTotal]
                            WHERE StudyCaseId = (SELECT StudyCaseID FROM [{self.dbName}].[dbo].[flStudyCase] WHERE StudyCaseName = '{scenario}')"""
                if self.hazard == 'tsunami':  # selecting 0 due to no return period existing in database
                    sql = f"SELECT '0' as returnPeriod FROM [{self.dbName}].[dbo].[tsScenario]"
            queryset = self.query(sql)
            returnPeriods = [str(returnPeriod).strip() for returnPeriod in queryset['returnPeriod'].values.tolist()]
            # Check for return periods
            # assign as 0 if no return periods exists 
            if len(returnPeriods) == 0 or ''.join(returnPeriods) == '-1':
                returnPeriods = '0'
            elif len(returnPeriods) == 1:
                self.returnPeriod = ''.join(returnPeriods)
                returnPeriods = self.returnPeriod
            else:
                # sort the multiple return periods
                returnPeriods = sorted(returnPeriods, key=lambda x: int(x))
            return returnPeriods
        except:
            print("Unexpected error getReturnPeriods:", sys.exc_info()[0])
            raise

    def getEssentialFacilities(self):
        """Queries the call essential facilities for a study region in local Hazus SQL Server database

        Returns:
            df: pandas dataframe -- a dataframe of the essential facilities and damages
        """
        try:
            essentialFacilities = [
                "AirportFlty",
                "BusFlty",
                "CareFlty",
                "CommunicationFlty",
                "Dams",
                "ElectricPowerFlty",
                "EmergencyCtr",
                "FerryFlty",
                "FireStation",
                "HighwayBridge",
                "HighwaySegment",
                "HighwayTunnel",
                "Levees",
                "LightRailBridge",
                "LightRailFlty",
                "LightRailSegment",
                "LightRailTunnel",
                "Military",
                "NaturalGasFlty",
                "NaturalGasPl",
                "NuclearFlty",
                "OilFlty",
                "OilPl",
                "PoliceStation",
                "PortFlty",
                "PotableWaterFlty",
                "RailFlty",
                "RailwayBridge",
                "RailwaySegment",
                "RailwayTunnel",
                "Runway",
                "School",
                "WasteWaterFlty",
                "WasteWaterPl",
            ]

            # TODO should tsunami be ts or eq? tsunami doesn't appear to contain essential facilities
            prefixDict = {
                "earthquake": "eq",
                "hurricane": "huResults",
                "flood": "flFR",
                "tsunami": "ts",
            }
            prefix = prefixDict[self.hazard]
            essentialFacilityDataFrames = {}
            for facility in essentialFacilities:
                try:
                    # get all column names for study region table
                    sql = """SELECT COLUMN_NAME as "fieldName" FROM {s}.INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = N'{p}{f}'""".format(
                        s=self.name, f=facility, p=prefix
                    )
                    df = self.query(sql)
                    if len(df) > 0:
                        srcolumns = df["fieldName"].tolist()
                        # remove confounding columns
                        if "StudyCaseId" in srcolumns:
                            srcolumns.remove("StudyCaseId")
                        if "ReturnPeriodId" in srcolumns:
                            srcolumns.remove("ReturnPeriodId")

                        # get Id column name
                        idColumnList = [x for x in srcolumns if facility in x]
                        if len(idColumnList) == 0:
                            idColumnList = [
                                x for x in srcolumns if x.endswith("Id")]
                        idColumn = idColumnList[0]

                        # build query fields for study region table
                        tempColumns = [x.replace(x, "[" + x + "]")
                                       for x in srcolumns]
                        tempColumns.insert(
                            0, "'" + facility + "'" + ' as "FacilityType"'
                        )
                        tempColumns.insert(
                            0, "[" + idColumn + "] as FacilityId")
                        studyRegionColumns = ", ".join(tempColumns)

                        # get all column names for hz table
                        sql = """SELECT COLUMN_NAME as "fieldName" FROM {s}.INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = N'hz{f}'""".format(
                            s=self.name, f=facility#, p=prefix
                        )
                        df = self.query(sql)
                        hzcolumns = df["fieldName"].tolist()

                        # build query fields for hz table
                        containFields = [
                            "Name",
                            "City",
                            "County",
                            "State",
                            "Fips",
                            "Shape",
                        ]
                        # limit fields to containFields
                        hzcolumns = [
                            x for x in hzcolumns if any(f in x for f in containFields)
                        ]
                        tempColumns = [x.replace(x, "[" + x + "]")
                                       for x in hzcolumns]
                        tempColumns = [
                            x.replace(
                                "[Shape]", "Shape.STAsText() as geometry")
                            for x in tempColumns
                        ]
                        tempColumns = [
                            x.replace("[Statea]", "[Statea] as State")
                            for x in tempColumns
                        ]
                        tempColumns.insert(
                            0, "[" + idColumn + "] as FacilityId")
                        hazusColumns = ", ".join(tempColumns)

                        # build queryset columns
                        # replace hzcolumns
                        hzcolumns = [x.replace("Statea", "State")
                                     for x in hzcolumns]
                        hzcolumns = [x.replace("Shape", "geometry")
                                     for x in hzcolumns]
                        # replace srcolumns
                        srcolumns = [
                            x.replace(idColumn, "FacilityId") for x in srcolumns
                        ]
                        srcolumns.insert(0, "FacilityType")
                        # rename minor/moderate/severe/complete
                        srcolumns = [
                            x.replace("MINOR", "MINOR as Affected") for x in srcolumns
                        ]
                        srcolumns = [
                            x.replace("MODERATE", "MODERATE as Minor")
                            for x in srcolumns
                        ]
                        srcolumns = [
                            x.replace("SEVERE", "SEVERE as Major") for x in srcolumns
                        ]
                        srcolumns = [
                            x.replace("COMPLETE", "COMPLETE as Destroyed")
                            for x in srcolumns
                        ]
                        hzcolumnsFinal = ", ".join(
                            ["hz." + x for x in hzcolumns])
                        srcolumnsFinal = ", ".join(
                            ["sr." + x for x in srcolumns])
                        querysetColumns = (
                            ", ".join([srcolumnsFinal, hzcolumnsFinal])).strip().rstrip(',')
                        # change to real dollars
                        if "sr.EconLoss" in querysetColumns:
                            querysetColumns = querysetColumns.replace(
                                "sr.EconLoss", "sr.EconLoss * 1000 as EconLoss"
                            ).rstrip(', ')
                        # build where clause
                        whereClauseDict = {
                            "earthquake": """where EconLoss > 0""",
                            "flood": """where StudyCaseId = (select StudyCaseID from {s}.[dbo].[flStudyCase] where StudyCaseName = '{sc}') and ReturnPeriodId = '{rp}'""".format(
                                s=self.name, sc=self.scenario, rp=self.returnPeriod
                            ),
                            "hurricane": """where Return_Period = '{rp}' and huScenarioName = '{sc}'""".format(
                                sc=self.scenario, rp=self.returnPeriod
                            ),
                            "tsunami": """where EconLoss > 0""",
                        }
                        whereClause = whereClauseDict[self.hazard]

                        # build dynamic sql query
                        sql = """
                                SELECT
                                    {qc}
                                    FROM
                                    (SELECT
                                        {src}
                                        from [{s}].[dbo].[{p}{f}]
                                        {wc}) sr
                                    left join
                                    (SELECT
                                        {hzc}
                                        from [{s}].[dbo].[hz{f}]) hz
                                    on hz.FacilityID = sr.FacilityID
                                """.format(
                            #i=idColumn,
                            s=self.name,
                            f=facility,
                            p=prefix,
                            qc=querysetColumns,
                            src=studyRegionColumns,
                            hzc=hazusColumns,
                            wc=whereClause
                        )

                        # get queryset from database
                        df = self.query(sql)
                        # check if the queryset contains data
                        if len(df) > 1:
                            # convert all booleans to string
                            mask = df.applymap(type) != bool
                            replaceDict = {True: "TRUE", False: "FALSE"}
                            df = df.where(mask, df.replace(replaceDict))
                            # add to dictionary
                            essentialFacilityDataFrames[facility] = df
                except:
                    print("Unexpected error:", sys.exc_info()[0])
                    pass
            # if essentialFacilityDataFrames contains data, concatenate into a dataframe
            if len(essentialFacilityDataFrames) > 0:
                essentialFacilityDf = pd.concat(
                    [x.fillna("null")
                     for x in essentialFacilityDataFrames.values()],
                    sort=False,
                ).fillna("null")
                return StudyRegionDataFrame(self, essentialFacilityDf)
            else:
                print("\nNo essential facility loss information for " +
                      self.name + '\n')
        except:
            print("Unexpected error:", sys.exc_info()[0])
            raise

    def getDemographics(self):
        """Summarizes demographics at the lowest level of geography

        Returns:
            df: pandas dataframe -- a dataframe of the summarized demographics
        """
        try:

            sqlDict = {
                "earthquake": """select Tract as tract, Population, Households FROM {s}.dbo.[hzDemographicsT]""".format(
                    s=self.name
                ),
                "flood": """select CensusBlock as block, Population, Households FROM {s}.dbo.[hzDemographicsB]""".format(
                    s=self.name
                ),
                "hurricane": """select Tract as tract, Population, Households FROM {s}.dbo.[hzDemographicsT]""".format(
                    s=self.name
                ),
                "tsunami": """select CensusBlock as block, Population, Households FROM {s}.dbo.[hzDemographicsB]""".format(
                    s=self.name
                ),
            }

            df = self.query(sqlDict[self.hazard])
            return StudyRegionDataFrame(self, df)
        except:
            print("Unexpected error:", sys.exc_info()[0])
            raise

    def getResults(self):
        """Summarizes results at the lowest level of geography

        Returns:
            df: pandas dataframe -- a dataframe of the summarized results
        """
        try:
            economicLoss = self.getEconomicLoss()
            buildingDamage = self.getBuildingDamage()
            fatalities = self.getFatalities()
            injuries = self.getInjuries()
            shelterNeeds = self.getShelterNeeds()
            displacedHouseholds = self.getDisplacedHouseholds()
            debris = self.getDebris()
            demographics = self.getDemographics()

            dataFrameList = [
                economicLoss,
                buildingDamage,
                fatalities,
                injuries,
                shelterNeeds,
                displacedHouseholds,
                debris,
                demographics,
            ]

            if "block" in economicLoss.columns:
                dfMerged = reduce(
                    lambda left, right: pd.merge(
                        left, right, on=["block"], how="outer"
                    ),
                    dataFrameList,
                )
            elif "tract" in economicLoss.columns:
                dfMerged = reduce(
                    lambda left, right: pd.merge(
                        left, right, on=["tract"], how="outer"
                    ),
                    dataFrameList,
                )
            elif "county" in economicLoss.columns:
                dfMerged = reduce(
                    lambda left, right: pd.merge(
                        left, right, on=["county"], how="outer"
                    ),
                    dataFrameList,
                )

            df = dfMerged[dfMerged["EconLoss"].notnull()]
            # Find the columns where each value is null
            empty_cols = [col for col in df.columns if df[col].isnull().all()]
            # Drop these columns from the dataframe
            df.drop(empty_cols, axis=1, inplace=True)

            return StudyRegionDataFrame(self, df)
        except:
            print("Unexpected error:", sys.exc_info()[0])
            raise

    def getCounties(self):
        """Creates a dataframe of the county name and geometry for all counties in the study region

        Returns:
            gdf: geopandas geodataframe -- a geodataframe of the counties
        """
        try:
            sql = """SELECT 
                        CountyFips as "countyfips",
                        CountyName as "name",
                        State  as "state",
                        NumAggrTracts as "size",
                        Shape.STAsText() as "geometry",
                        Shape.STSrid as "crs"
                        FROM [{s}].[dbo].[hzCounty]
                """.format(
                s=self.name
            )

            df = self.query(sql)
            df["geometry"] = df["geometry"].apply(loads)
            gdf = gpd.GeoDataFrame(df, geometry="geometry")
            return gdf
        except:
            print("Unexpected error:", sys.exc_info()[0])
            raise

    def getStates(self):
        """Creates a dataframe of the state name and geometry for all states in the study region

        Returns:
            gdf: geopandas geodataframe -- a geodataframe of the states
        """
        try:
            sql = """SELECT 
                        Shape.STAsText() as "geometry",
                        Shape.STSrid as "crs"
                        FROM [{s}].[dbo].[hzState]
                """.format(
                s=self.name
            )

            df = self.query(sql)
            df["geometry"] = df["geometry"].apply(loads)
            gdf = gpd.GeoDataFrame(df, geometry="geometry")
            return gdf
        except:
            print("Unexpected error:", sys.exc_info()[0])
            raise

    def getTravelTimeToSafety(self):
        """Creates a geodataframe of the travel time to safety

        Returns:
            gdf: geopandas geodataframe -- a geodataframe of the counties
        """
        if self.hazard == "tsunami":
            try:

                sql = """SELECT
                    tiger.CensusBlock,
                    tiger.Tract, tiger.Shape.STAsText() AS geometry,
                    ISNULL(travel.Trav_SafeUnder65, 0) as travelTimeUnder65yo,
                    ISNULL(travel.Trav_SafeOver65, 0) as travelTimeOver65yo
                        FROM {s}.dbo.[hzCensusBlock_TIGER] as tiger
                            FULL JOIN {s}.dbo.tsTravelTime as travel
                                ON tiger.CensusBlock = travel.CensusBlock
                    WHERE travel.Trav_SafeOver65 > 0""".format(
                    s=self.name
                )

                df = self.query(sql)
                df["geometry"] = df["geometry"].apply(loads)
                gdf = gpd.GeoDataFrame(df, geometry="geometry")
                return gdf
            except:
                print("Unexpected error:", sys.exc_info()[0])
                raise
        else:
            print("This method is only available for tsunami study regions")

# TODO: Pass Return Period to report & fix title of report
    def setReport(self):
        """Requires that Hazard, name are set
        """
        try:
            self.report = Report(self, self.name, "", self.hazard)
        except Exception as e:
            print('\n')
            print(e)
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            print(fname)
            print(exc_type, exc_tb.tb_lineno)
            print('\n')

    #GET .HPR FILE INFO
    def getHPRFileDateTime(self, hprPath, fileName):
        """Get the specified filename's date_time created from an hpr file.

        Keyword Arguments:
            hprPath: str -- a string of the full directory path and hpr filename.
            fileName: str -- a string of the filename in the hpr.

        Returns:
            fileDate_Time: str -- a string representing the file date in YYYY-MM-DD format

        Notes: ZipFile date_time: tuple https://docs.python.org/3/library/zipfile.html
        """
        try:
            z = zipfile.ZipFile(hprPath, 'r')
            dateTimeTuple = z.getinfo(fileName).date_time
            year = str(dateTimeTuple[0])
            month = str(dateTimeTuple[1]).zfill(2)
            day = str(dateTimeTuple[2]).zfill(2)
            dateTime = f'{year}-{month}-{day}'
            return dateTime
        except Exception as e:
            print('Exception getHPRFileDateTime:')
            print(e)

    def getHPRComment(self, hprPath):
        """Read an .hpr/zipfiles comments and assign to class property.

        Keyword Arguments:
            hprPath: str -- a string of the full directory path and hpr filename.

        Returns:
            zComment: list -- a python list of HPR attributes
    
        Notes: 
        """
        try:
            z = zipfile.ZipFile(hprPath)
            zComment = z.comment.decode('UTF-8').split('|')
            return zComment
        except Exception as e:
            print(f'Exception getHPRComment ({hprPath}):')
            print(e)

    def getHPRHazusVersion(self, hprComment):
        """
        Keyword Arguments:
            hprComment: list -- a python list of HPR attributes

        Returns:
            hprHazusVersion: string -- the Hazus version that created the HPR
            
        Notes:  Export is only going to support HPR as far back as Hazus 2.0.
           ?|Version|RegionName|.bk|Earthquake|Flood|Hurricane
           '31ed16|121212|NorCal-BayArea_SanAndreasM7-8|NorCal-BayArea_SanAndreasM7-8.bk|1|0|0'

           ?|Version|RegionName|.bk|Earthquake|Flood|Hurricane|Tsunami
           '31ed16|202020|FIMJacksonMO|FIMJacksonMO.bk|0|1|0|0'
           
           The first pipe is unknown what it is.
           EQ added 1997
           FL added 2003
           HU 2004
           TS 2017 added in Hazus 4.0
        """
        versionLookupDict = { '060606':'Hazus MR1'
                             ,'070707':'Hazus MR2'
                             ,'080808':'Hazus MR3'
                             ,'090909':'Hazus MR4'
                             ,'101010':'Hazus MR5'
                             ,'111111':'Hazus 2.0'
                             ,'121212':'Hazus 2.1'
                             ,'131313':'Hazus 3.0'
                             ,'141414':'Hazus 3.1'
                             ,'151515':'Hazus 4.0'
                             ,'161616':'Hazus 4.1'
                             ,'171717':'Hazus 4.2'
                             ,'181818':'Hazus 4.2.1'
                             ,'191919':'Hazus 4.2.2'
                             ,'202020':'Hazus 4.2.3'
                             ,'212121':'Hazus 5.0'
                             ,'222222':'Hazus 5.1'}
        commentVersion = hprComment[1]
        if commentVersion in versionLookupDict:
            hprHazusVersion = versionLookupDict[commentVersion]
            return hprHazusVersion
        else:
            print(f'{commentVersion} not in Hazus version list.')

    def getHPRBKFileName(self, hprComment):
        """Get the bk file name from a hpr comment.
        Keyword Arguments:
            hprComment: list -- a python list of HPR attributes

        Returns:
            commentBKFile: string -- the name of the .bk file
        """
        commentBKFile = hprComment[3]
        return commentBKFile

    def getHPRHazards(self, hprComment, returnType='list'):

        """Compare comments value to known Hazus version value to get common Hazus version.

        Keyword Arguments:
            hprComment: list -- a python list of HPR attributes
            returnType: string -- list|dict determines the return data type

        Returns:
            hazardsList: list -- a list of the HPR's Hazard types
            hazardsDict: dictionary -- a dict of the HPR's Hazard types

        Notes:
            ['earthquake','flood','hurricane','tsunami']
            {'earthquake':0|1,'flood':0|1,'hurricane':0|1,'tsunami':0|1}
        """
        #handle hpr after Hazus 4.0
        if len(hprComment) == 8:
            zRegionName = hprComment[2]
            hazardsDict = {
                'earthquake': int(hprComment[4]),
                'flood': int(hprComment[5]),
                'hurricane': int(hprComment[6]),
                'tsunami': int(hprComment[7])}
        #handle hpr before Hazus 4.0
        elif len(hprComment) == 7:
            zRegionName = hprComment[2]
            hazardsDict = {
                'earthquake': int(hprComment[4]),
                'flood': int(hprComment[5]),
                'hurricane': int(hprComment[6]),
                'tsunami': 0}
        if returnType == 'dict':
            return hazardsDict
        if returnType == 'list':
            hazardsList = list(
                filter(lambda x: hazardsDict[x], hazardsDict))
            return hazardsList

    #RESTORE .HPR TO HAZUS SQL SERVER
    def unzipHPR(self, hprPath, tempDir):
        """Unzip HPR to temp folder.

            Keyword Arguments:
                hprPath: str -- the path to the HPR file
                tempDir: str -- the output path to unzip the HPR file to

        """
        print(f'Unzipping {hprPath} to {tempDir}...')
        try:
            with zipfile.ZipFile(hprPath, 'r') as zip_ref:
                zip_ref.extractall(tempDir)
        except Exception as e:
            print('Exception unzipHPR:')
            print(e)
        print('...done')
        print()

    def getBKFilePathFromHPRComment(self, fileDir, hprComment):
        """Set the bkFilePath attribute.

            Keyword Arguments:
                fileDir: str -- the unzipped hpr directory
                
        Note: there can be many hpr files
        """
        try:
            bkFileName = self.getHPRBKFileName(self.hprComment)
            bkFilePath = Path.joinpath(Path(fileDir), bkFileName)
            if bkFilePath.exists():
                self.bkFilePath = bkFilePath
                self.dbName = bkFilePath.stem
                self.name = 'bk_' + self.dbName
            else:
                print(f'no bkfile in {fileDir}')
        except Exception as e:
            print('Unexpected error getBKFilePathFromHPRComment:')
            print(e)
    
    def getBKFilePath(self, fileDir):
        """Set the bkFilePath attribute.

            Keyword Arguments:
                fileDir: str -- the unzipped hpr directory
                
        Note: This method does not always choose the correct bk file when there are many
        """
        fileExt = r'*.bk'
        bkList = list(Path(fileDir).glob(fileExt))
        print(f'Available bk files in {fileDir}: {bkList}')
        if len(bkList) > 1:
            print(f'Too many .bk files ({len(bkList)}), choosing the first one {str(bkList[0])}')
            print()
            bkFilePath = Path.joinpath(fileDir, str(bkList[0]))
            self.bkFilePath = bkFilePath
            self.dbName = bkFilePath.stem
            self.name = 'bk_' + self.dbName
        elif len(bkList) == 1:
            print()
            bkFilePath = Path.joinpath(fileDir, str(bkList[0]))
            print(f'\nThe bk file path is:\n {bkFilePath}\n')
            self.bkFilePath = bkFilePath
            self.dbName = bkFilePath.stem
            self.name = 'bk_' + self.dbName
        else:
            print(f'no bkfile in {fileDir}')
        
    def getFileListHeadersFromDBFile(self, bkFilePath, cursor):
        """Create a standard FileListHeaders as a temporary table
            to determine the name of the .mdf data and log files to be
            recovered in sql server.

            Keyword Arguments:
                bkFilePath: str -- the unzipped hpr directory
                cursor: pyodbc connection cursor -- the sql server connection cursor object
                
            Returns:
                tuple: tuple -- LogicalName_data and LogicName_log fro bkfile

        """
        #Create temp table to hold .bk info...
        print(f'Creating and populating temporary table to hold {bkFilePath} FileListHeaders info...')
        cursor.execute("""CREATE TABLE #FileListHeaders (     
             LogicalName    nvarchar(128)
            ,PhysicalName   nvarchar(260)
            ,[Type] char(1)
            ,FileGroupName  nvarchar(128) NULL
            ,Size   numeric(20,0)
            ,MaxSize    numeric(20,0)
            ,FileID bigint
            ,CreateLSN  numeric(25,0)
            ,DropLSN    numeric(25,0) NULL
            ,UniqueID   uniqueidentifier
            ,ReadOnlyLSN    numeric(25,0) NULL
            ,ReadWriteLSN   numeric(25,0) NULL
            ,BackupSizeInBytes  bigint
            ,SourceBlockSize    int
            ,FileGroupID    int
            ,LogGroupGUID   uniqueidentifier NULL
            ,DifferentialBaseLSN    numeric(25,0) NULL
            ,DifferentialBaseGUID   uniqueidentifier NULL
            ,IsReadOnly bit
            ,IsPresent  bit
            )
            IF CAST(CAST(SERVERPROPERTY('ProductVersion') as char(4)) as float) > 9
            BEGIN
                ALTER TABLE #FileListHeaders ADD TDEThumbprint  varbinary(32) NULL
            END
            IF CAST(CAST(SERVERPROPERTY('ProductVersion') as char(2)) as float) > 12
            BEGIN
                ALTER TABLE #FileListHeaders ADD SnapshotURL    nvarchar(360) NULL
            END""")
        cursor.execute(f"INSERT INTO #FileListHeaders EXEC ('RESTORE FILELISTONLY FROM DISK = N''{bkFilePath}''')")
        #Get .bk mdf and log names...
        LogicalName_data = cursor.execute("SELECT LogicalName FROM #FileListHeaders WHERE Type = 'D'").fetchval()
        LogicalName_log = cursor.execute("SELECT LogicalName FROM #FileListHeaders WHERE Type = 'L'").fetchval()
        print(LogicalName_data) 
        print(LogicalName_log)
        cursor.execute("DROP TABLE #FileListHeaders")
        print('...done')
        print()
        return(LogicalName_data, LogicalName_log)

    def getConnectionString(self, stringName):
        """ Looks up a connection string in a json file based on an input argument

            Keyword Arguments:
                stringName: str -- the name of the connection string in the json file
                
            Returns:
                conn: pyodbc connection string that needs driver and computername updated

            Notes:
                Can we use relative path to this file for ./connectionStrings.json or
                is it relative to file that imported this file?
                os.path.join(Path(__file__).parent, "connectionStrings.json")
                "./src/connectionStrings.json"
        """
        with open("./src/connectionStrings.json") as f:
            connectionStrings = json.load(f)
            connectionString = connectionStrings[stringName]
        return connectionString

    def createConnection(self, orm='pyodbc'):
        """ Creates a connection object to the local Hazus SQL Server database

            Key Argument:
                orm: string - - type of connection to return (choices: 'pyodbc', 'sqlalchemy')
            Returns:
                conn: pyodbc connection
        """
        try:
            # list all Windows SQL Server drivers
            drivers = [
                '{ODBC Driver 17 for SQL Server}',
                '{ODBC Driver 13.1 for SQL Server}',    
                '{ODBC Driver 13 for SQL Server}',
                '{ODBC Driver 11 for SQL Server} ',
                '{SQL Server Native Client 11.0}',
                '{SQL Server Native Client 10.0}',
                '{SQL Native Client}',
                '{SQL Server}'
            ]
            computer_name = os.environ['COMPUTERNAME']
            if orm == 'pyodbc':
                # create connection with the latest driver
                for driver in drivers:
                    try:
                        conn = py.connect(self.getConnectionString('pyodbc').format(d=driver, cn=computer_name))
                        break
                    except:
                        conn = py.connect(self.getConnectionString('pyodbc_auth').format(d=driver, cn=computer_name))
                        break
            return conn
        except:
            print("Unexpected error:", sys.exc_info()[0])
            raise

    def restoreSQLServerBKFile(self, dbName, dirPath, bkFilePath, LogicalName_data, LogicalName_log, cursor):
        """
        Key Argument:
            dbName: str -- the name of the bk file database name
            dirPath: str -- the path where the bk .mdf files will be copied to (the unzipped hpr folder)
            bkFilePath: str -- the path to the bk file
            LogicalName_data: str -- the name of the bk files data .mdf file from FileListHeaders table
            LogicalName_log: str -- the name of the bk files log .mdf file from FileListHeaders table
            cursor: pydodb connection cursor -- cursor to perform the database restore

        Notes: Creates mdf and log files. Runs asynchronously. Database is not available via Hazus Study Regions.
            Appends 'bk_' to attached database dbName.
        """
        self.conn = self.createConnection()
        print(f'Restoring database: {dbName} ...')
        mdfPath = Path.joinpath(dirPath, f'{LogicalName_data}.mdf') 
        logPath = Path.joinpath(dirPath, f'{LogicalName_log}.mdf')
        cursor.execute(f"RESTORE DATABASE [bk_{dbName}] FROM DISK='{bkFilePath}' WITH REPLACE, MOVE '{LogicalName_data}' to '{mdfPath}', MOVE '{LogicalName_log}' to '{logPath}'")
        while cursor.nextset():
            pass
        print('...done')
        print()

    def restoreHPR(self):
        """Use several base functions together to effectively attach an hpr file to sql server for access by export functions.

        Notes:

        """
        #UnzipHPR...
        self.unzipHPR(self.hprFilePath, self.tempDir)
        #Find .bk files in unzipped folder...
        self.getBKFilePathFromHPRComment(self.tempDir, self.hprComment)
        #Connect to SQL Server Hazus...
        self.conn = self.createConnection()
        self.conn.autocommit = True
        self.cursor = self.conn.cursor()
        #Get .bk file FileListHeaders info...
        self.LogicalNames = self.getFileListHeadersFromDBFile(self.bkFilePath, self.cursor)
        self.LogicalName_data = self.LogicalNames[0]
        self.LogicalName_log = self.LogicalNames[1]
        #Restore the database using the FileListHeaders info...
        self.restoreSQLServerBKFile(self.dbName, self.tempDir, self.bkFilePath, self.LogicalName_data, self.LogicalName_log, self.cursor)

    #CLEANUP
    def dropDB(self):
        """Using HazusPackageRegion attributes, drop the bk_* database that was restored from the bkfile in the hpr.
        """
        print(f'Dropping {self.name}...')
        try:
            sqlServerDatabaseVersionRaw = self.conn.getinfo(py.SQL_DBMS_VER) #obtain the database version, ie '12.00.4100'
            sqlServerDatabaseVersion = int(sqlServerDatabaseVersionRaw.split('.')[0])
            if sqlServerDatabaseVersion < 13:
                self.conn.autocommit = True
                self.cursor.execute(f"USE MASTER IF EXISTS (SELECT * FROM sys.databases WHERE name='{self.name}') DROP DATABASE [{self.name}]") #sql server 2014-, Hazus 4.2.3
            if sqlServerDatabaseVersion >= 13:
                self.cursor.execute(f"USE MASTER ALTER DATABASE [{self.name}] SET SINGLE_USER WITH ROLLBACK IMMEDIATE DROP DATABASE IF EXISTS [{self.name}]") #sql server 2016+, Hazus 5.0
            print('...done')
            print()
        except Exception as e:
            print('Unexpected Error dropDB:')
            print(e)

    def deleteTempDir(self):
        """Using HazusPackageRegion attributes, delete the unzipped HPR directory.
        """
        print(f'Deleting temp folder:{self.tempDir}...')
        try:
            shutil.rmtree(self.tempDir)
            print('...done')
            print()
        except OSError as e:
            print ("Error: %s - %s." % (e.filename, e.strerror))

    def getAnalysisType(self):
        """Historical, Deterministic, Probabalistic. Deterministic includes historical and everything that is not probabilistic

            Notes:
                EQ: eqShakeMapSecenario EarthquakeType=Actual or Scenario and use Probabilistic when RgnExpeqScenario.EqScenarioType=P
                FL: Whenever Return Period is a number = probabalistic; when its mix0 its deterministic
                HU:
                TS:
        """
        try:
            if self.hazard == 'earthquake':
                sqlEqScenarioType = f'SELECT [EqScenarioType] FROM [bk_{self.dbName}].[dbo].[RgnExpeqScenario]'
                dfEqScenarioType = self.query(sqlEqScenarioType)
                EqScenarioType = dfEqScenarioType['EqScenarioType'].iat[0] #the table should be a single cell
                if EqScenarioType == 'M':
                    try:
                        sqlEarthquakeType = f'SELECT [EarthquakeType] FROM [bk_{self.dbName}].[dbo].[eqShakeMapScenario]'
                        dfEarthquakeType = self.query(sqlEarthquakeType)
                        EarthquakeType = dfEarthquakeType['EarthquakeType'].iat[0] #the table should be a single cell
                        if EarthquakeType == 'ACTUAL':
                            return 'Historic'
                        if EarthquakeType == 'SCENARIO':
                            return 'Deterministic'
                    except:
                        #The table eqShakeMapScenario does not always exist
                        return 'Deterministic'
                if EqScenarioType == 'U':
                    return 'Deterministic'
                if EqScenarioType == 'P':
                    return 'Probabilistic'
            if self.hazard == 'flood':
                pass
            if self.hazard == 'hurricane':
                sqlHurricaneType = f"SELECT [ScenarioType] FROM [bk_{self.dbName}].[dbo].[huTemplateScenario]"
                dfHurricaneType = self.query(sqlHurricaneType)
                HurricaneType = dfHurricaneType['ScenarioType'].iat[0] #the table should be a single cell
                return HurricaneType #Determinisitic, Historic, Probabilistic
            if self.hazard == 'tsunami':
                pass
            
        except Exception as e:
            print('Exception getAnalysisType:')
            print(e)

    def getEarthquakeShakemapUrl(self):
        """Get the ShakemapId

            Returns:
                str: string -- A url to USGS Shakemap Event
        """
        sql = f"SELECT [ShakeMapId] FROM [bk_{self.dbName}].[dbo].[eqShakeMapScenario]"
        try:
            df = self.query(sql)
            shakemapId = df['ShakeMapId'].iat[0] #the table should be a single cell
            shakemapUrl = f"https://earthquake.usgs.gov/scenarios/eventpage/{shakemapId}/executive"
            return shakemapUrl
        except Exception as e:
            print("Unexpected error getEarthquakeShakemapId:", sys.exc_info()[0])
            print(e)
            return None

    def getEarthquakeMagnitude(self):
        """Get the Earthquake magnitude

            Returns:
                str: string -- 
        """
        sql = f"SELECT [Magnitude] FROM [bk_{self.dbName}].[dbo].[RgnExpeqScenario]"
        try:
            df = self.query(sql)
            magnitude = df['Magnitude'].iat[0] #the table should be a single cell
            return magnitude
        except Exception as e:
            print("Unexpected error getEarthquakeMagnitude:", sys.exc_info()[0])
            print(e)

    def getEQShakeMapScenario(self):
        """Get the eqShakeMapScenario table as a dataframe to export

            Returns:
                df: pandas dataframe -- a dataframe of eqShakeMapScenario
        """
        try:
            sql = f"""SELECT [ID]
                      ,[ScenarioName]
                      ,[EarthquakeType]
                      ,[EventDescription]
                      ,[EpicenterLon]
                      ,[EpicenterLat]
                      ,[Magnitude]
                      ,[EpicenterDepth]
                      ,[ShakeMapVersion]
                      ,[ShakeMapOriginator]
                      ,[ShakeMapId]
                      FROM [bk_{self.dbName}].[dbo].[eqShakeMapScenario]"""
            df = self.query(sql)
            #return HazusPackageRegionDataFrame(self, df)
            return StudyRegionDataFrame(self, df)   # TODO: Change to this - BC
        except Exception as e:
            print('Unexpected error getEQShakeMapScenario:')
            print(e)

    def getFloodHazardType(self):
        """Determine the Flood Hazard Type; Riverine or Coastal.

            Returns:
                str: string --

            Notes:
                ********Not currently in use.************
                {s}.[dbo].[flHazType] has integer to string conversion of Hazard_Type.
        """
        sql = """SELECT [ParmValue]
                  FROM {s}.[dbo].[flStudyCaseParms]
                  WHERE [StudyCaseID] = 0 AND ParmKey = 'Hazard_Type'
                """.format(s=self.name)
        try:
            df = self.query(sql)
            Hazard_Type = df['ParmValue'].iat[0] #the table should be a single cell
            if Hazard_Type == 1:
                return 'Riverine'
            if Hazard_Type != 1:
                return 'Coastal'
        except Exception as e:
            print("Unexpected error getFloodHazardType:", sys.exc_info()[0])
            print(e)

    def getHazardsScenariosReturnPeriods(self):
        """Create a dictionary using the template in the notes so that it can be programmaticaly read to batch export.

        Arguments:
            self.hazard list assumes self.hazard is a list of strings

        Notes:
            ReturnPeriods may have extra spaces.
        
             [{'Hazard':'flood',
               'Scenarios':[
                               {'ScenarioName':'JacksonMO_01',
                                'ScenarioType':''
                                'ReturnPeriods':['29']
                               },
                               {'ScenarioName':'JacksonMO_02',
                                'ReturnPeriods':['2']
                               }
                           ]
              },
              {'Hazard':'hurricane',
              etc...}
             ]
        """
        print('Finding Hazards, Scenarios, Return Periods...')
        HSRPList = []
        for hazard in self.Hazards:
            hazardDict = {}
            hazardDict['Hazard'] = hazard
            self.hazard = hazard
            scenarioList = self.getScenarios(hazard)
            scenarioDictList = []
            for scenario in scenarioList:
                scenarioDict = {}
                scenarioDict['ScenarioName'] = scenario
                scenarioDict['ReturnPeriods'] = self.getReturnPeriods(hazard, scenario)
                rp = scenarioDict['ReturnPeriods']
                scenarioDictList.append(scenarioDict)
                
            hazardDict['Scenarios'] = scenarioDictList

            HSRPList.append(hazardDict)
            
        self.HazardsScenariosReturnPeriods = HSRPList
        print('...Done')
        print()

    def getFloodBoundaryPolyName(self, hazardType='R'):
        """Obtains the name of the HazardPoly in an unzipped HPR's scenario folder.

        Inputs:
            hazardType: string -- the hazard type R for Riverine, C for Coastal.
            
        Returns:
            BoundaryPolyName: string -- the name to the HazardPoly featureclass in the scenario .mdb

        Notes:
            ESRI Personal Geodatabase .mdb path differs based on hazard type Riverine|Coastal.
            Unsure how a dual Riverine and Coastal SR is setup, more testing needed.
            Sample Path (HPR/Scenario/hazardtype/CaseOutput.mdb/BoundaryPoly*):
                'nora_temp\nora_01\Riverine\CaseOutput.mdb' with 'BoundaryPolyRP101'.
        """
        if hazardType.upper() == 'R':
            hazardType = 'Riverine'
        if hazardType.upper() == 'C':
            hazardType = 'Coastal'
        self.floodMdbPath = str(Path.joinpath(self.tempDir, self.scenario, f'{hazardType}/CaseOutput.mdb'))
        mdbPath = self.floodMdbPath
        featsClassList = []
        driver = ogr.GetDriverByName("PGeo") #for ESRI .mdb
        
        try:
            gdb = driver.Open(mdbPath, 0) # 0 means read-only. 1 means writeable.
        except Exception as e:
            print(e)
            sys.exit()
        
        for featsClass_idx in range(gdb.GetLayerCount()):
            featsClass = gdb.GetLayerByIndex(featsClass_idx)
            featsClassList.append(featsClass.GetName())

        del gdb #cleanup
            
        for featsClass in featsClassList:
            if 'boundarypoly' in featsClass.lower():
                self.floodBoundaryPolygonName = featsClass
                BoundaryPolyName = featsClass
                return BoundaryPolyName        

    def exportFloodHazardPolyToShapefile(self, outputShapefile):
        """
        Inputs:
            outputShapefile: str -- name of the output shapefile and path.

        Notes:
            I.E. \nora_temp\nora_01\Riverine\CaseOutput.mdb or \nora_temp\nora_01\Coastal\CaseOutput.mdb ?
            I.E. BoundaryPolyRP101 but look for BoundaryPoly* as there should be one but the suffix may be different
        """
        try:
            mdbPath = self.floodMdbPath #r'C:\workspace\nora_temp\nora_01\Riverine\CaseOutput.mdb'
            boundaryPoly = self.floodBoundaryPolygonName
            command = f'ogr2ogr -f "ESRI Shapefile" "{outputShapefile}" "{mdbPath}" {boundaryPoly}'
            subprocess.check_call(command)
        except Exception as e:
            print(e)

    def exportFloodHazardPolyToShapefileToZipFile(self, outputShapefile):
        """
        Inputs:
            outputShapefile: str -- name of the output shapefile and path.

        Notes:
            I.E. \nora_temp\nora_01\Riverine\CaseOutput.mdb or \nora_temp\nora_01\Coastal\CaseOutput.mdb ?
            I.E. BoundaryPolyRP101 but look for BoundaryPoly* as there should be one but the suffix may be different
        """


        shapefileSuffixList = ['.shp', '.shx', '.dbf', '.prj', '.sbn',
                               '.sbx', '.fbn', '.fbx', '.ain', '.aih',
                               '.ixs', '.mxs', '.atx', '.shp.xml',
                               '.cpg', '.qix']
        try:
            mdbPath = self.floodMdbPath #r'C:\workspace\nora_temp\nora_01\Riverine\CaseOutput.mdb'
            boundaryPoly = self.floodBoundaryPolygonName
            command = f'ogr2ogr -f "ESRI Shapefile" "{outputShapefile}" "{mdbPath}" {boundaryPoly}'
            subprocess.check_call(command)
        except Exception as e:
            print("Unexpected error exportFloodHazardPolyToShapefileToZipFile 1:")
            print(e)
        try:
            #Get filename from path (i.e. results.shp) and create a zipfile of the same name...
            pathObject = Path(outputShapefile)
            pathZip = Path.joinpath(pathObject.parent, pathObject.stem + '.zip')
            #For each shapefile suffix, see if it exists for filename from path and if so, append it to the zipfile...
            with zipfile.ZipFile(pathZip, 'a') as myzip:
                for suffix in shapefileSuffixList:
                    shapefileFile = Path.joinpath(pathObject.parent, pathObject.stem + suffix)
                    if shapefileFile.exists():
                        myzip.write(shapefileFile, shapefileFile.name)
        except:
            print("Unexpected error exportFloodHazardPolyToShapefileToZipFile 2:", sys.exc_info()[0])
            raise
        try:
            #Delete the shapefile...
            driver = ogr.GetDriverByName("ESRI Shapefile")
            if pathObject.exists():
                 driver.DeleteDataSource(str(outputShapefile))
        except:
            print("Unexpected error exportFloodHazardPolyToShapefileToZipFile 3:", sys.exc_info()[0])
            raise

    def getFIMSelected_Rtn_Period(self):
        """Queries the HPR database for the unzipped hpr path to scenario/returnperiod depth grid

            Returns:
                str: string -- should be a string value with no leading or trailing spaces

        """
        sql = """DECLARE @var1 VARCHAR(30);     

                SELECT @var1 = '{sc}'; 

                SELECT @var1 = [StudyCaseID]         
                FROM [{s}].[dbo].[flStudyCase]      
                WHERE [StudyCaseName] = @var1 ;   

                SELECT [ParmValue]
                FROM [{s}].[dbo].[flStudyCaseParms]
                WHERE [StudyCaseID] = @var1 AND ParmKey = 'Selected_Rtn_Period'
                """.format(s=self.name, sc=self.scenario)
        try:
            df = self.query(sql)
            Selected_Rtn_Period = df['ParmValue'].iat[0] #the table should be a single cell
            return Selected_Rtn_Period.strip() 
        except Exception as e:
            print("Unexpected error getFIMSelected_Rtn_Period:", sys.exc_info()[0])
            print(e)
            raise 

    def getStudyRegionBoundary(self):
        """Get the study region area as a polygon.
            Returns:
                df: pandas dataframe -- a dataframe of the summarized demographics
        """
        print('getHzBoundary')
        try:

            sql = f"SELECT [OBJECTID],[Shape].STAsText() AS geometry FROM [{self.name}].[dbo].[hzboundary]"

            df = self.query(sql)
            return StudyRegionDataFrame(self, df)
        except:
            print("Unexpected error getStudyRegionBoundary:", sys.exc_info()[0])
            raise

    def getHurricaneTrack(self):
        """Get the Hurricane track as a line.
            Returns:
                df: pandas dataframe -- a dataframe of the hurricane track
            Notes:
                Only applicable to Historic and Deterministic Hurricane. Not
                available for Probabilistic nor AAL. Currently there is a potential
                issue with ogr2ogr PGEO .mdb connections not supported in some
                environments so Historic is not available.

                Historic: From DeterministicStormTracks based on Name in 'C:\Program Files (x86)\Hazus\Data\HU\WindField\huStormTrack.mdb'
                Deterministic: [RgnExphuStormTrack] Latitude and Longitude points (this is not a feature class)
        """
        try:
            pass
        except Exception as e:
            print("Unexpected error getHurricaneTrack:")
            print(e)

    def getGeographicCountUnitofResults(self, df):
        """ Counts the number of unique geographic units of the results
            Arguments:
                df: pandas dataframe -- a dataframe from the getResults() method

            Returns:
                df: tuple -- a tuple with the geographicCount and the geographicUnit
        """
        try:
            if 'block' in df.columns:
                geographicUnit  = 'block'
                geographicCount = len(pd.unique(df['block']))
            elif 'tract' in df.columns:
                geographicUnit  = 'tract'
                geographicCount = len(pd.unique(df['tract']))
            elif 'county' in df.columns:
                geographicUnit  = 'county'
                geographicCount = len(pd.unique(df['county']))
            else:
                geographicUnit = ''
                geographicCount = ''
            return (geographicCount, geographicUnit)
        except Exception as e:
            print('Unexpected error getGeographicCountUnitofResults:')
            print(e)
