import json
import os
import pandas as pd
import pyodbc as py
from sqlalchemy import create_engine
import sys

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
        self.databases = self.getDatabases()
        self.studyRegions = self.getStudyRegions()

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
            print("Unexpected error getting databases:", sys.exc_info()[0])
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
            sql = """SELECT [RegionName] as studyRegion FROM [syHazus].[dbo].[syStudyRegion] WHERE Valid = 1 ORDER BY studyRegion"""
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
                print("Unexpected error initializing HAZUS DB:", sys.exc_info()[0])
                raise

        def save(self, replace=True):
            if replace:
                ifExists = 'replace'
            else:
                ifExists = 'fail'

            self.to_sql(self.table, schema=self.schema,
                        con=self.conn, index=False, if_exists=ifExists)

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
                "./connectionStrings.json"
        """
        with open("./src/connectionStrings.json") as f:
            connectionStrings = json.load(f)
            connectionString = connectionStrings[stringName]
        return connectionString

    def createConnection(self, orm="pyodbc"):
        """Creates a connection object to the local Hazus SQL Server database

        Key Argument:
            orm: string - - type of connection to return (choices: 'pyodbc', 'sqlalchemy')
        Returns:
            conn: pyodbc connection
        """
        try:
            # list all Windows SQL Server drivers
            drivers = [
                "{ODBC Driver 17 for SQL Server}",
                "{ODBC Driver 13.1 for SQL Server}",
                "{ODBC Driver 13 for SQL Server}",
                "{ODBC Driver 11 for SQL Server} ",
                "{SQL Server Native Client 11.0}",
                "{SQL Server Native Client 10.0}",
                "{SQL Native Client}",
                "{SQL Server}",
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
            print("Unexpected error creating database connection:", sys.exc_info()[0])
            raise