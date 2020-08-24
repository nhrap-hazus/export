import pandas as pd
import geopandas as gpd
import sys
from shapely.wkt import loads
from shapely.geometry.multipolygon import MultiPolygon
from shapely.geometry.polygon import Polygon


class StudyRegionDataFrame(pd.DataFrame):
    """ -- StudyRegion helper class --
        Intializes a study region dataframe class - A pandas dataframe extended with extra methods


        Keyword Arguments: \n
            studyRegionClass: StudyRegion -- an initialized StudyRegion class
            df: pandas dataframe -- a dataframe to extend as a StudyRegionDataFrame

    """

    def __init__(self, studyRegionClass, df):
        super().__init__(df)
        try:
            self.studyRegion = studyRegionClass.name
        except:
            self.studyRegion = studyRegionClass.studyRegion
        self.conn = studyRegionClass.conn
        self.query = studyRegionClass.query

    def addCensusTracts(self):
        """ Queries the census tract geometry for a study region in local Hazus SQL Server database

            Returns:
                df: pandas dataframe -- a dataframe of the census geometry and fips codes
        """
        try:
            temp_df = self.copy()
            if not 'tract' in temp_df.columns:
                sql = """SELECT [CensusBlock] as block ,[Tract] as tract FROM {s}.[dbo].[hzCensusBlock]""".format(s=self.studyRegion)
                update_df = self.query(sql)
                temp_df = pd.merge(update_df, temp_df, on="block")

            sql = """SELECT Tract as tract, Shape.STAsText() AS geometry FROM {s}.dbo.hzTract""".format(
                s=self.studyRegion)
            update_df = self.query(sql)
            temp_df = pd.merge(update_df, temp_df, on="tract")
            return StudyRegionDataFrame(self, temp_df)
        except:
            print("Unexpected error:", sys.exc_info()[0])
            raise

    def addCensusBlocks(self):
        """ Queries the census block geometry for a study region in local Hazus SQL Server database

            Returns:
                df: pandas dataframe -- a dataframe of the census geometry and fips codes
        """
        try:

            sql = """SELECT CensusBlock as block, Shape.STAsText() AS geometry FROM {s}.dbo.hzCensusBlock""".format(
                s=self.studyRegion)

            df = self.query(sql)
            newDf = pd.merge(df, self, on="block")
            return StudyRegionDataFrame(self, newDf)
        except:
            print("Unexpected error:", sys.exc_info()[0])
            raise

    def addCounties(self):
        """ Queries the county geometry for a study region in local Hazus SQL Server database

            Returns:
                df: pandas dataframe -- a dataframe of the census geometry and fips codes
        """
        try:

            temp_df = self.copy()
            if not 'county' in temp_df.columns:
                if not 'tract' in temp_df.columns:
                    sql = """SELECT [CensusBlock] as block, [Tract] as tract FROM {s}.[dbo].[hzCensusBlock]""".format(s=self.studyRegion)
                    update_df = self.query(sql)
                    temp_df = pd.merge(update_df, temp_df, on="block")
                sql = """SELECT [Tract] as tract, [CountyFips] as countyfips FROM {s}.[dbo].[hzTract]""".format(s=self.studyRegion)
                update_df = self.query(sql)
                temp_df = pd.merge(update_df, temp_df, on="tract")

            sql = """select state, county, countyfips, geometry from 
                    (SELECT State as stateid, CountyFips as countyfips, CountyName as county, Shape.STAsText() AS geometry FROM {s}.dbo.hzCounty) c
                    inner join (select StateID as stateid, StateName as state FROM [syHazus].[dbo].[syState]) s
                    on c.stateid = s.stateid""".format(s=self.studyRegion) 

            update_df = self.query(sql)
            temp_df = pd.merge(update_df, temp_df, on="countyfips")
            return StudyRegionDataFrame(self, temp_df)
        except:
            print("Unexpected error:", sys.exc_info()[0])
            raise

    def addGeometry(self):
        """ Adds geometry to any HazusDB class dataframe with a census block, tract, or county id

            Keyword Arguments: \n
                dataframe: pandas dataframe -- a HazusDB generated dataframe with a fips column named either block, tract, or county
            Returns:
                df: pandas dataframe -- a copy of the input dataframe with the geometry added
        """
        try:
            if 'block' in self.columns:
                df = self.addCensusBlocks()
                return StudyRegionDataFrame(self, df)
            elif 'tract' in self.columns:
                df = self.addCensusTracts()
                return StudyRegionDataFrame(self, df)
            elif 'county' in self.columns:
                df = self.addCounties()
                return StudyRegionDataFrame(self, df)
            else:
                print(
                    'Unable to find the column name block, tract, or county in the dataframe input')
        except:
            print("Unexpected error:", sys.exc_info()[0])
            raise

    def toCSV(self, path):
        """ Exports a StudyRegionDataFrame to a CSV

            Keyword Arguments: \n
                path: str -- the output directory path, file name, and extention (example: 'C:/directory/filename.csv')
        """
        self.to_csv(path, index=False)

    def toShapefile(self, path):
        """ Exports a StudyRegionDataFrame to an Esri Shapefile

            Keyword Arguments: \n
                path: str -- the output directory path, file name, and extention (example: 'C:/directory/filename.shp')
        """
        try:
            if 'geometry' not in self.columns:
                self = self.addGeometry()
            self['geometry'] = self['geometry'].apply(lambda x: loads(str(x)))
            gdf = gpd.GeoDataFrame(self, geometry='geometry')
            gdf.to_file(path, driver='ESRI Shapefile')
        except:
            print("Unexpected error:", sys.exc_info()[0])
            raise

    def toGeoJSON(self, path):
        """ Exports a StudyRegionDataFrame to a web compatible GeoJSON

            Keyword Arguments: \n
                path: str -- the output directory path, file name, and extention (example: 'C:/directory/filename.geojson')
        """
        try:
            if 'geometry' not in self.columns:
                self = self.addGeometry()
            self['geometry'] = self['geometry'].apply(lambda x: loads(str(x)))
            self['geometry'] = [MultiPolygon([x]) if type(
                x) == Polygon else x for x in self['geometry']]
            gdf = gpd.GeoDataFrame(self, geometry='geometry')
            gdf.to_file(path, driver='GeoJSON')
        except:
            print("Unexpected error:", sys.exc_info()[0])
            raise
