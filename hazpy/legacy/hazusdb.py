import os
import pandas as pd
import pyodbc as py
from sqlalchemy import create_engine
import sys
import urllib

# API new methods

# GET
"""
TS
    travel time to safety
    water depth
EQ
    inspected, restricted, unsafe
    PGA by tract
HU
    damaged essential facilities
    peak gust by track
"""


class HazusDB():
    """Creates a connection to the Hazus SQL Server database with methods to access
    databases, tables, and study regions
    """

    def __init__(self):
        self.conn = self.createConnection()
        # self.cursor = self.conn.cursor()
        self.databases = self.getDatabases()
        self.studyRegions = self.getStudyRegions()

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
                        conn = py.connect('Driver={d};SERVER={cn}\HAZUSPLUSSRVR; UID=SA;PWD=Gohazusplus_02'.format(
                            d=driver, cn=computer_name))
                        break
                    except:
                        continue
            # TODO add sqlalchemy connection
            # if orm == 'sqlalchemy':
            #     conn = create_engine('mssql+pyodbc://SA:Gohazusplus_02@HAZUSPLUSSRVR')
            # self.conn = conn
            return conn
        except:
            print("Unexpected error:", sys.exc_info()[0])
            raise

    def getDatabases(self):
        """Creates a dataframe of all databases in your Hazus installation

            Returns:
                df: pandas dataframe
        """
        try:
            query = 'SELECT name FROM sys.databases'
            df = pd.read_sql(query, self.conn)
            return df
        except:
            print("Unexpected error:", sys.exc_info()[0])
            raise

    def getTables(self, databaseName):
        """Creates a dataframe of all tables in a database

            Keyword Arguments:
                databaseName: str -- the name of the Hazus SQL Server database

            Returns:
                df: pandas dataframe
        """
        try:
            query = 'SELECT * FROM [%s].INFORMATION_SCHEMA.TABLES;' % databaseName
            df = pd.read_sql(query, self.conn)
            self.tables = df
            return df
        except:
            print("Unexpected error:", sys.exc_info()[0])
            raise

    def getStudyRegions(self):
        """Creates a dataframe of all study regions in the local Hazus SQL Server database

            Returns:
                studyRegions: pandas dataframe
        """
        try:
            # exclusionRows = ['master', 'tempdb', 'model',
            #                  'msdb', 'syHazus', 'CDMS', 'flTmpDB']
            # sql = 'SELECT [StateID] FROM [syHazus].[dbo].[syState]'
            # queryset = self.query(sql)
            # states = list(queryset['StateID'])
            # for state in states:
            #     exclusionRows.append(state)
            # sql = 'SELECT * FROM sys.databases'
            # df = self.query(sql)
            # studyRegions = df[~df['name'].isin(exclusionRows)]['name']
            # studyRegions = studyRegions.reset_index()
            # studyRegions = studyRegions.drop('index', axis=1)
            # self.studyRegions = studyRegions
            # return studyRegions

            sql = """SELECT [RegionName] as studyRegion FROM [syHazus].[dbo].[syStudyRegion]"""
            queryset = self.query(sql)
            studyRegions = list(queryset['studyRegion'])
            self.studyRegions = studyRegions
            return studyRegions
        except:
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
            df = pd.read_sql(sql, self.conn)
            return df
        except:
            print("Unexpected error:", sys.exc_info()[0])
            raise

    class EditSession(pd.DataFrame):
        """Creates an edit session for a Hazus database table

            Keyword Arguments:
                database: str -- the database or study region name \n
                schema: str -- the schema name, typically 'dbo' \n
                table: str -- the table name you want to edit

            Returns:
                df: pandas dataframe -- an editable dataframe. Use the save() method when finished.
        """

        def __init__(self, database, schema, table):
            try:
                super().__init__()
                self.database = database
                self.schema = schema
                self.table = table

                comp_name = os.environ['COMPUTERNAME']
                server = comp_name+"\HAZUSPLUSSRVR"
                user = 'SA'
                password = 'Gohazusplus_02'
                driver = 'ODBC Driver 13 for SQL Server'
                # driver = 'ODBC Driver 11 for SQL Server'
                engine = create_engine("mssql+pyodbc:///?odbc_connect={}".format(urllib.parse.quote_plus(
                    "DRIVER={0};SERVER={1};PORT=1433;DATABASE={2};UID={3};PWD={4};TDS_Version=8.0;".format(driver, server, database, user, password))))
                # self.engine = create_engine("mssql+pyodbc:///?odbc_connect={}".format(urllib.parse.quote_plus("DRIVER={4};SERVER={0};PORT=1433;DATABASE={1};UID={2};PWD={3};TDS_Version=8.0;".format(driserver, database, user, password, driver))))
                self.conn = engine.connect()

                sql = "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = N'"+table+"'"
                columns = list(pd.read_sql(sql, con=self.conn)['COLUMN_NAME'])
                columns = ['['+x+']' for x in columns]
                columns = ', '.join(columns)
                if '[Shape]' in columns:
                    columns = columns.replace(
                        '[Shape]', '[Shape].STAsText() as Shape')

                sql = 'select ' + columns + \
                    ' from ['+database+'].['+schema+'].['+table+']'
                df = pd.read_sql(sql, con=self.conn)
                super().__init__(df)
            except:
                print("Unexpected error:", sys.exc_info()[0])
                raise

        def save(self, replace=True):
            if replace:
                ifExists = 'replace'
            else:
                ifExists = 'fail'

            self.to_sql(self.table, schema=self.schema,
                        con=self.conn, index=False, if_exists=ifExists)
