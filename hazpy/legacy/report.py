from xhtml2pdf import pisa
import os
import pandas as pd

import geopandas as gpd
from shapely.wkt import loads

from matplotlib import pyplot as plt
from mpl_toolkits.axes_grid1.axes_divider import make_axes_locatable
import matplotlib.patheffects as pe
import matplotlib.ticker as ticker
import seaborn as sns
import shapely
import numpy as np
import shutil

import sys
from uuid import uuid4 as uuid


class Report():
    """ -- A StudyRegion helper class --
    Creates a report object. Premade reports are exportable using the save method and specifying the report in the parameter premade. The Report class can also be used as an API to create reports using the addTable, addHistogram, and addMap methods.

    Keyword Arguments: \n
        title: str -- report title
        subtitle: str -- report subtitle
        icon: str -- report hazard icon (choices: 'earthquake', 'flood', 'hurricane', 'tsunami')

    """

    def __init__(self, studyRegionClass, title, subtitle, icon):
        self.__getResults = studyRegionClass.getResults
        self.__getBuildingDamageByOccupancy = studyRegionClass.getBuildingDamageByOccupancy
        self.__getBuildingDamageByType = studyRegionClass.getBuildingDamageByType
        self.__getEssentialFacilities = studyRegionClass.getEssentialFacilities
        self.__getHazardGeoDataFrame = studyRegionClass.getHazardGeoDataFrame
        self.__getTravelTimeToSafety = studyRegionClass.getTravelTimeToSafety
        self.hazard = studyRegionClass.hazard
        self.scenario = studyRegionClass.scenario
        self.returnPeriod = studyRegionClass.returnPeriod
        self.assets = {
            'earthquake': 'https://fema-ftp-snapshot.s3.amazonaws.com/Hazus/Assets/hazard_icons/Earthquake_DHSGreen.png',
            'flood': 'https://fema-ftp-snapshot.s3.amazonaws.com/Hazus/Assets/hazard_icons/Flood_DHSGreen.png',
            'hurricane': 'https://fema-ftp-snapshot.s3.amazonaws.com/Hazus/Assets/hazard_icons/Hurricane_DHSGreen.png',
            'tsunami': 'https://fema-ftp-snapshot.s3.amazonaws.com/Hazus/Assets/hazard_icons/Tsunami_DHSGreen.png',
            'tornado': 'https://fema-ftp-snapshot.s3.amazonaws.com/Hazus/Assets/hazard_icons/Tornado_DHSGreen.png',
            'hazus': 'https://fema-ftp-snapshot.s3.amazonaws.com/Hazus/Assets/hazus_icons/hazus_cropped.png'
        }

        self.columnLeft = ''
        self.columnRight = ''
        self.title = title
        self.subtitle = subtitle
        self.icon = self.assets[icon]
        self.template = ''
        self.disclaimer = """The estimates of social and economic impacts contained in this report were produced using Hazus loss estimation methodology software which is based on current scientific and engineering knowledge. There are uncertainties inherent in any loss estimation
            technique. Therefore, there may be significant differences between the modeled results contained in this report and the actual social and economic losses following a specific earthquake. These results can be improved by using enhanced inventory, geotechnical,
            and observed ground motion data."""
        self.getCounties = studyRegionClass.getCounties
        self._tempDirectory = 'hazpy-report-temp'

    def abbreviate(self, number):
        try:
            digits = 0
            number = float(number)
            formattedString = str("{:,}".format(round(number, digits)))
            if ('.' in formattedString) and (digits == 0):
                formattedString = formattedString.split('.')[0]
            if (number > 1000) and (number < 1000000):
                split = formattedString.split(',')
                formattedString = split[0] + '.' + split[1][0:-1] + ' K'
            if (number > 1000000) and (number < 1000000000):
                split = formattedString.split(',')
                formattedString = split[0] + '.' + split[1][0:-1] + ' M'
            if (number > 1000000000) and (number < 1000000000000):
                split = formattedString.split(',')
                formattedString = split[0] + '.' + split[1][0:-1] + ' B'
            if (number > 1000000000000) and (number < 1000000000000000):
                split = formattedString.split(',')
                formattedString = split[0] + '.' + split[1][0:-1] + ' T'
            return formattedString
        except:
            return str(number)

    def addCommas(self, number, abbreviate=False, truncate=False):
        if truncate:
            number = int(round(number))
        if abbreviate:
            number = self.abbreviate(number)
        else:
            number = "{:,}".format(number)
        return number

    def toDollars(self, number, abbreviate=False, truncate=False):
        if truncate:
            number = int(round(number))
        if abbreviate:
            dollars = self.abbreviate(number)
            dollars = '$' + dollars
        else:
            dollars = '$'+"{:,}".format(number)
            dollarsSplit = dollars.split('.')
            if len(dollarsSplit) > 1:
                dollars = '.'.join([dollarsSplit[0], dollarsSplit[1][0:1]])
        return dollars

    def updateTemplate(self):
        self.template = """
            <html>
                <head>
                    <style>
                        @page {
                            size: a4 portrait;
                            @frame header_frame {
                                /*Static Frame*/
                                -pdf-frame-content: header_content;
                                left: 50pt;
                                width: 512pt;
                                top: 50pt;
                                height: 40pt;
                            }
                            @frame content_frame {
                                /*Content Frame*/
                                left: 20px;
                                right: 20px;
                                top: 20px;
                                bottom: 20px;
                            }
                            @frame footer_frame {
                                /*Another static Frame*/
                                -pdf-frame-content: footer_content;
                                left: 50pt;
                                width: 512pt;
                                top: 772pt;
                                height: 20pt;
                            }
                        }
                        .header_border {
                            font-size: 3px;
                            width: 512pt;
                            background-color: #0078a9;
                            color: #0078a9;
                            padding-top: 0;
                            padding-bottom: 0;
                            padding-left: 0;
                            padding-right: 0;
                        }
                        .header {
                            width: 512pt;
                            border: 2px solid #abadb0;
                            margin-top: 5px;
                            margin-bottom: 5px;
                            padding-top: 10px;
                            padding-bottom: 10px;
                            padding-left: 10px;
                            padding-right: 10px;
                        }
                        .header_table_cell_icon {
                            border: none;
                            width: 100px;
                            padding-top: 5px;
                            padding-bottom: 5px;
                            padding-left: 10px;
                            padding-right: 0;
                        }
                        .header_table_cell_icon_img {
                            width: auto;
                            height: 60px;
                        }
                        .header_table_cell_text {
                            border: none;
                            width: 50%;
                            text-align: left;
                            margin-left: 20px;
                            margin-left: 20px;
                        }
                        .header_table_cell_logo {
                            padding-top: 0;
                            padding-bottom: 0;
                            padding-left: 35px;
                            padding-right: 0;
                            border: none;
                        }
                        .header_table_cell_logo_img {
                            width: auto;
                            height: 40px;
                        }
                        .header_title {
                            font-size: 16px;
                            padding-top: 10px;
                            padding-bottom: 0;
                            padding-left: 0;
                            padding-right: 0;
                            margin-top: 10px;
                            margin-bottom: 0;
                            margin-left: 0;
                            margin-right: 0;

                        }
                        .header_subtitle {
                            font-size: 12px;
                            padding-top: 0;
                            padding-bottom: 0;
                            padding-left: 0;
                            padding-right: 0;
                            margin-top: 0;
                            margin-bottom: 0;
                            margin-left: 0;
                            margin-right: 0;
                        }
                        .column_left {
                            margin-top: 0;
                            padding-top: 5px;
                            padding-bottom: 0;
                            padding-left: 0;
                            padding-right: 5px;
                            height: 690pt;
                            vertical-align: top;
                        }
                        .column_right {
                            margin-top: 0;
                            padding-top: 5px;
                            padding-bottom: 0;
                            padding-left: 5px;
                            padding-right: 0;
                            height: 690pt;
                            vertical-align: top;
                        }
                        .report_columns {
                            padding-top: 5px;
                            padding-bottom: 5px;
                        }
                        .result_container {
                            padding-top: 0;
                            padding-bottom: 0;
                            padding-left: 0;
                            padding-right: 0;
                        }
                        .result_container_spacer {
                            font-size: 2px;
                            width: 100%;
                            background-color: #fff;
                            color: #fff;
                            padding-top: 0;
                            padding-bottom: 0;
                            padding-left: 0;
                            padding-right: 0;
                            margin-top: 0;
                            margin-bottom: 0;
                            margin-left: 0;
                            margin-right: 0;
                        }
                        .results_table {
                            height: auto;
                            width: 100%;
                            padding-top: 0;
                            padding-bottom: 0;
                            padding-left: 0;
                            padding-right: 0;
                            margin-top: 0;
                            margin-bottom: 0;
                            margin-left: 0;
                            margin-right: 0;
                        }
                        .results_header {
                            background-color: #0078a9;
                            color: #000;
                        }
                        .results_table_header {
                            background-color: #0078a9;
                            margin-bottom: 0;
                            padding-top: 3px;
                            padding-bottom: 1px;
                        }
                        .results_table_header_title {
                            color: #fff;
                            text-align: left;
                            padding-top: 3px;
                            padding-bottom: 1px;
                            padding-right: 1px;
                            padding-left: 5px;
                            width: 40%;
                        }
                        .results_table_header_title_solo {
                            color: #fff;
                            text-align: left;
                            padding-top: 3px;
                            padding-bottom: 1px;
                            padding-left: 5px;
                            width: 100%;
                        }
                        .results_table_header_total {
                            color: #fff;
                            text-align: right;
                            vertical-align: top;
                            padding-top: 3px;
                            padding-bottom: 1px;
                            padding-right: 1px;
                            padding-left: 0px;
                        }
                        .results_table_header_number {
                            color: #fff;
                            text-align: left;
                            padding-top: 3px;
                            padding-bottom: 1px;
                            padding-right: 1px;
                            padding-left: 0px;
                        }
                        .results_table_cells_header {
                            background-color: #abadb0;
                            color: #fff;
                            border: 1px solid #fff;
                            margin-top: 0;
                            padding-top: 3px;
                            padding-bottom: 1px;
                        }
                        .results_table_cells {
                            background-color: #f9f9f9;
                            border: 1px solid #fff;
                            color: #000;
                            text-align: left;
                            padding-top: 3px;
                            padding-bottom: 1px;
                            padding-left: 5px;
                        }
                        .results_table_img {
                            width: auto;
                            height: 400pt;
                            max-height: 400pt;
                        }
                        .disclaimer {
                            color: #c3c3c3;
                            font-size: 6pt;
                        }
                    </style>
                </head>
                <body>
                    <div id="content_frame">
                        <div class="header_border">_</div>
                        <div class="header">
                            <table>
                            <tr>
                                <td class="header_table_cell_icon">
                                <img
                                    class="header_table_cell_icon_img"
                                    src='"""+self.icon+"""'
                                    alt="hazard"
                                />
                                </td>
                                <td class="header_table_cell_text">
                                    <h1 class="header_title">"""+self.title+"""</h1>
                                    <p class="header_subtitle">"""+self.subtitle+"""</p>
                                </td>
                                <td class="header_table_cell_logo">
                                <img
                                    class="header_table_cell_logo_img"
                                    src='"""+self.assets['hazus']+"""'
                                    alt="hazus"
                                />
                                </td>
                            </tr>
                            </table>
                        </div>
                        <div class="header_border">_</div>
                        <table class="report_columns">
                            <tr>
                                <td class="column_left">
                                """+self.columnLeft+"""
                                </td>
                                <td class="column_right">
                                """+self.columnRight+"""
                                </td>
                            </tr>
                        </table>
                        <p class="disclaimer">"""+self.disclaimer+"""</p>
                    </div>
                </body>
            </html>
            """

    def addTable(self, df, title, total, column):
        """ Adds a table to the report

        Keyword Arguments: \n
            df: pandas dataframe -- expects a StudyRegionDataFrame
            title: str -- section title
            total: str -- total callout box value
            column: str -- which column in the report to add to (options: 'left', 'right')
        """
        headers = ['<tr>']
        for col in df.columns:
            headers.append(
                '<th class="results_table_cells_header">'+col+'</th>')
        headers.append('</tr')
        headers = ''.join(headers)

        values = []
        for index in range(len(df)):
            row = ['<tr>']
            for col in df.columns:
                row.append('<td class="results_table_cells">' +
                           str(df.iloc[index][col])+'</td>')
            row.append('</tr>')
            values.append(''.join(row))
        values = ''.join(values)

        template = """
            <div class="result_container">
                <table class="results_table">
                    <tr class="results_table_header">
                        <th class="results_table_header_title">
                            """+title+"""
                        </th>
                        <th class="results_table_header_total">Total:</th>
                        <th class="results_table_header_number">"""+total+"""</th>
                    </tr>
                </table>
                <table class="results_table">
                    """+headers+"""
                    """+values+"""
                </table>
            </div>
            <div class="result_container_spacer">_</div>
        """
        if column == 'left':
            self.columnLeft = self.columnLeft + template
        if column == 'right':
            self.columnRight = self.columnRight + template

    def addImage(self, src, title, column):
        """ Adds image block to the report

        Keyword Arguments: \n
            src: str -- the path and filename of the image
            title: str -- the title of the image
            column: str -- which column in the report to add to (options: 'left', 'right')
        """
        template = """
            <div class="result_container">
                <table class="results_table">
                <tr class="results_table_header">
                    <th class="results_table_header_title_solo">
                    """+title+"""
                    </th>
                </tr>
                </table>
                <img
                class="results_table_img"
                src='"""+src+"""'
                alt='"""+title+"""'
                />
            </div>
            <div class="result_container_spacer">_</div>
            """
        if column == 'left':
            self.columnLeft = self.columnLeft + template
        if column == 'right':
            self.columnRight = self.columnRight + template

    def addMap(self, gdf, field, title, column, legend=True, formatTicks=True, cmap='Blues'):
        """ Adds a map to the report

        Keyword Arguments: \n
            gdf: geopandas geodataframe -- a geodataframe containing the data to be mapped
            field: str -- the field for the choropleth
            title: str -- section title in the report
            column: str -- which column in the report to add to (options: 'left', 'right')
            legend (optional): bool -- adds a colorbar to the map
            formatTicks (optional): bool -- if True, it will abbreviate and add commas to tick marks
            cmap (optional): str -- the colormap used for the choropleth; default = 'Blues'
        """
        try:
            f_width = 3
            f_height = 3
            fig = plt.figure(figsize=(f_width, f_height), dpi=300)
            ax = fig.gca()
            ax2 = fig.gca()

            if type(gdf) != gpd.GeoDataFrame:
                gdf['geometry'] = gdf['geometry'].apply(str)
                gdf['geometry'] = gdf['geometry'].apply(loads)
                gdf = gpd.GeoDataFrame(gdf, geometry='geometry')
            try:
                gdf.plot(column=field, cmap=cmap, ax=ax)
            except:
                gdf['geometry'] = gdf['geometry'].apply(loads)
                gdf.plot(column=field, cmap=cmap, ax=ax)

            if legend == True:
                sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(vmin=gdf[field].min(), vmax=gdf[field].max()))
                sm._A = []

                divider = make_axes_locatable(ax)
                cax = divider.append_axes("top", size="10%", pad="20%")
                cb = fig.colorbar(sm, cax=cax, orientation="horizontal")
                cb.outline.set_visible(False)
                if formatTicks == True:
                    cb.ax.xaxis.set_major_formatter(ticker.FuncFormatter(lambda x, p: self.addCommas(x, abbreviate=True, truncate=True)))

                counties = self.getCounties()
                # reduce counties to those that intersect the results
                intersect = counties.intersects(gdf.geometry)
                counties = counties[intersect]

                gdf['dissolve'] = 1
                mask = gdf.dissolve(by='dissolve').envelope
                mask = mask.buffer(0)
                counties['geometry'] = counties.buffer(0)
                counties = gpd.clip(counties, mask)
                counties.plot(facecolor="none", edgecolor="darkgrey", linewidth=0.2, ax=ax2)
                # counties.plot(facecolor="none", edgecolor="darkgrey", linewidth=0.2, ax=ax2)
                annotationDf = counties.sort_values('size', ascending=False)[0:5]
                annotationDf = annotationDf.sort_values('size', ascending=True)

                annotationDf['centroid'] = [x.centroid for x in annotationDf['geometry']]

                maxSize = annotationDf['size'].max()
                topFontSize = 2.5
                annotationDf['fontSize'] = topFontSize * (annotationDf['size'] / annotationDf['size'].max()) + (topFontSize - ((annotationDf['size'] / annotationDf['size'].max()) * 2))
                for row in range(len(annotationDf)):
                    name = annotationDf.iloc[row]['name']
                    coords = annotationDf.iloc[row]['centroid']
                    ax.annotate(text=name, xy=(float(coords.x), float(coords.y)), horizontalalignment='center', size=annotationDf.iloc[row]['fontSize'], color='white', path_effects=[pe.withStroke(linewidth=1, foreground='#404040')])

            fontsize = 3
            for idx in range(len(fig.axes)):
                fig.axes[idx].tick_params(labelsize=fontsize, size=fontsize)

            ax.axis('off')
            ax.axis('scaled')
            if not os.path.isdir(os.getcwd() + '/' + self._tempDirectory):
                os.mkdir(os.getcwd() + '/' + self._tempDirectory)
            src = os.getcwd() + '/' + self._tempDirectory + '/'+str(uuid())+".png"
            fig.savefig(src, pad_inches=0, bbox_inches='tight', dpi=600)
            axExtent = ax.get_window_extent()
            if axExtent.width <= (axExtent.height / 2):
                ax.autoscale(enable=True, axis='x', tight=False)
                ax.margins(f_width, f_height)
                fig.savefig(src, pad_inches=0, bbox_inches='tight', dpi=600)
            fig.clf()
            plt.clf()


            template = """
                <div class="result_container">
                    <table class="results_table">
                    <tr class="results_table_header">
                        <th class="results_table_header_title_solo">
                        """+title+"""
                        </th>
                    </tr>
                    </table>
                    <img
                    class="results_table_img"
                    src='"""+src+"""'
                    alt='"""+title+"""'
                    />
                </div>
                <div class="result_container_spacer">_</div>
                """
            if column == 'left':
                self.columnLeft = self.columnLeft + template
            if column == 'right':
                self.columnRight = self.columnRight + template
        except:
            fig.clf()
            plt.clf()
            print("Unexpected error:", sys.exc_info()[0])
            raise

    def addHistogram(self, df, xCol, yCols, title, ylabel, column, colors=['#549534', '#f3de2c', '#bf2f37']):
        """ Adds a map to the report

        Keyword Arguments: \n
            df: pandas dataframe -- a geodataframe containing the data to be plotted
            xCol: str -- the categorical field
            yCols: list<str> -- the value fields
            title: str -- title for the report section
            ylabel: str -- y-axis label for the units being plotted in the yCols
            column: str -- which column in the report to add to (options: 'left', 'right')
            colors (optional if len(yCols) == 3): list<str> -- the colors for each field in yCols - should be same length (default = ['#549534', '#f3de2c', '#bf2f37'])
        """
        try:
            x = [x for x in df[xCol].values] * len(yCols)
            y = []
            hue = []
            for valueColumn in yCols:
                for category in [x for x in df[xCol].values]:
                    y.append(df[df[xCol] == category][valueColumn].values[0])
                    hue.append(valueColumn)
            dfPlot = pd.DataFrame({'x': x, 'y': y, 'hue': hue})
            plt.figure(figsize=(5, 3))
            colorPalette = dict(zip(dfPlot.hue.unique(), colors))
            ax = sns.barplot(x='x', y='y', hue='hue',
                             data=dfPlot, palette=colorPalette)
            ax.set_xlabel('')
            plt.box(on=None)
            plt.legend(title='', fontsize=8)
            plt.xticks(fontsize=8)
            plt.yticks(fontsize=8)
            fmt = '{x:,.0f}'
            tick = ticker.StrMethodFormatter(fmt)
            ax.yaxis.set_major_formatter(tick)
            plt.ylabel(ylabel, fontsize=9)
            plt.tight_layout(pad=0.1, h_pad=None, w_pad=None, rect=None)
            if not os.path.isdir(os.getcwd() + '/' + self._tempDirectory):
                os.mkdir(os.getcwd() + '/' + self._tempDirectory)
            src = os.getcwd() + '/' + self._tempDirectory + '/'+str(uuid())+".png"
            plt.savefig(src, pad_inches=0, bbox_inches='tight', dpi=600)
            plt.clf()

            template = """
                <div class="result_container">
                    <table class="results_table">
                    <tr class="results_table_header">
                        <th class="results_table_header_title_solo">
                        """+title+"""
                        </th>
                    </tr>
                    </table>
                    <img
                    class="results_table_img"
                    src='"""+src+"""'
                    alt='"""+title+"""'
                    />
                </div>
                <div class="result_container_spacer">_</div>
                """
            if column == 'left':
                self.columnLeft = self.columnLeft + template
            if column == 'right':
                self.columnRight = self.columnRight + template
        except:
            plt.clf()
            print("Unexpected error:", sys.exc_info()[0])
            raise


    def save(self, path, deleteTemp=True, openFile=True, build=False):
        """Creates a PDF of the report

        Keyword Arguments: \n
            path: str -- the output directory and file name (example: 'C://output_directory/filename.pdf')
            deleteTemp (optional): bool -- delete temp files used to create the report (default: True)
            openFile (optional): bool -- open the PDF after saving (default: True)
            build (optional): bool -- create a premade report (default: False)
        """
        try:
            if build:
                self.build()

            # open output file for writing (truncated binary)
            self.updateTemplate()
            result_file = open(path, "w+b")

            # convert HTML to PDF
            pisa_status = pisa.CreatePDF(
                self.template,
                dest=result_file)

            # close output file
            result_file.close()

            if openFile:
                os.startfile(path)
            if deleteTemp:
                shutil.rmtree(os.getcwd() + '/' + self._tempDirectory)
            self.clear()

            # return False on success and True on errors
            return pisa_status.err
        except:
            if build:
                self.clear()
            if deleteTemp:
                shutil.rmtree(os.getcwd() + '/' + self._tempDirectory)
            print("Unexpected error:", sys.exc_info()[0])
            raise
    
    def clear(self):
        self.columnLeft = ''
        self.columnRight = ''


    def build(self):
        """ Builds a premade report

        """

        try:
            # assign constants
            tableRowLimit = 7
            tonsToTruckLoadsCoef = 0.25
            hazard = self.hazard

            if hazard == 'earthquake':
                # get bulk of results
                try:
                    results = self._Report__getResults()
                    # results = results.addGeometry()
                    results = results.addCounties()
                    results_values = results.groupby(by=['county']).sum()
                    results = results.groupby(by=['county']).first()
                    for column in results_values.columns:
                        results[column] = results_values[column]
                    results = results.drop('tract', axis=1)
                    results = results.reset_index()

                except:
                    print("Unexpected error:", sys.exc_info()[0])
                    pass

                # add building damage by occupancy
                try:
                    buildingDamageByOccupancy = self._Report__getBuildingDamageByOccupancy()
                    # create category column
                    buildingDamageByOccupancy['xCol'] = [
                        x[0:3] for x in buildingDamageByOccupancy['Occupancy']]
                    # create new columns for major and destroyed
                    buildingDamageByOccupancy['Major & Destroyed'] = buildingDamageByOccupancy['Major'] + \
                        buildingDamageByOccupancy['Destroyed']
                    # list columns to group for each category
                    yCols = ['Affected', 'Minor', 'Major & Destroyed']
                    self.addHistogram(buildingDamageByOccupancy, 'xCol', yCols,
                                      'Building Damage By Occupancy', 'Buildings', 'left')
                except:
                    print("Unexpected error:", sys.exc_info()[0])
                    pass

                # add economic loss
                try:
                    economicLoss = results[['name', 'EconLoss']]
                    economicLoss.columns = [
                        'Top Counties', 'Economic Loss']
                    # populate total
                    total = self.addCommas(
                        economicLoss['Economic Loss'].sum(), truncate=True, abbreviate=True)
                    # limit rows to the highest values
                    economicLoss = economicLoss.sort_values(
                        'Economic Loss', ascending=False)[0:tableRowLimit]
                    # format values
                    economicLoss['Economic Loss'] = [self.toDollars(
                        x, abbreviate=True) for x in economicLoss['Economic Loss']]
                    self.addTable(
                        economicLoss, 'Total Economic Loss', total, 'left')
                except:
                    print("Unexpected error:", sys.exc_info()[0])
                    pass

                # add injuries and fatatilies
                try:
                    injuriesAndFatatilies = results[['name']]
                    injuriesAndFatatilies.columns = ['Top Counties']
                    injuriesAndFatatilies['Injuries Day'] = results['Injury_DayLevel1'] + \
                        results['Injury_DayLevel2'] + \
                        results['Injury_DayLevel3']
                    injuriesAndFatatilies['Injuries Night'] = results['Injury_NightLevel1'] + \
                        results['Injury_NightLevel2'] + \
                        results['Injury_NightLevel3']
                    injuriesAndFatatilies['Fatalities Day'] = results['Fatalities_Day']
                    injuriesAndFatatilies['Fatalities Night'] = results['Fatalities_Night']
                    # populate totals
                    totalDay = self.addCommas(
                        (injuriesAndFatatilies['Injuries Day'] + injuriesAndFatatilies['Fatalities Day']).sum(), abbreviate=True) + ' Day'
                    totalNight = self.addCommas(
                        (injuriesAndFatatilies['Injuries Night'] + injuriesAndFatatilies['Fatalities Night']).sum(), abbreviate=True) + ' Night'
                    total = totalDay + '/' + totalNight
                    # limit rows to the highest values
                    injuriesAndFatatilies = injuriesAndFatatilies.sort_values(
                        'Injuries Day', ascending=False)[0:tableRowLimit]
                    # format values
                    for column in injuriesAndFatatilies:
                        if column != 'Top Counties':
                            injuriesAndFatatilies[column] = [self.addCommas(
                                x, abbreviate=True) for x in injuriesAndFatatilies[column]]

                    self.addTable(injuriesAndFatatilies,
                                  'Injuries and Fatatilies', total, 'left')
                except:
                    print("Unexpected error:", sys.exc_info()[0])
                    pass

                # add displaced households and shelter needs
                try:
                    displacedAndShelter = results[[
                        'name', 'DisplacedHouseholds', 'ShelterNeeds']]
                    displacedAndShelter.columns = [
                        'Top Counties', 'Displaced Households', 'People Needing Shelter']
                    # populate totals
                    totalDisplaced = self.addCommas(
                        displacedAndShelter['Displaced Households'].sum(), abbreviate=True)
                    totalShelter = self.addCommas(
                        displacedAndShelter['People Needing Shelter'].sum(), abbreviate=True)
                    total = totalDisplaced + ' Displaced/' + totalShelter + ' Needing Shelter'
                    # limit rows to the highest values
                    displacedAndShelter = displacedAndShelter.sort_values(
                        'Displaced Households', ascending=False)[0:tableRowLimit]
                    # format values
                    for column in displacedAndShelter:
                        if column != 'Top Counties':
                            displacedAndShelter[column] = [self.addCommas(
                                x, abbreviate=True) for x in displacedAndShelter[column]]
                    self.addTable(
                        displacedAndShelter, 'Displaced Households and Sort-Term Shelter Needs', total, 'left')
                except:
                    print("Unexpected error:", sys.exc_info()[0])
                    pass

                # add economic loss map
                try:
                    economicLoss = results[['name', 'EconLoss', 'geometry']]
                    # convert to GeoDataFrame
                    economicLoss.geometry = economicLoss.geometry.apply(loads)
                    gdf = gpd.GeoDataFrame(economicLoss)
                    self.addMap(gdf, title='Economic Loss by County (USD)',
                                column='right', field='EconLoss', cmap='OrRd')
                except:
                    print("Unexpected error:", sys.exc_info()[0])
                    pass

                # add hazard map
                try:
                    gdf = self._Report__getHazardGeoDataFrame()
                    title = gdf.title
                    # limit the extent
                    gdf = gdf[gdf['PARAMVALUE'] > 0.1]
                    self.addMap(gdf, title=title,
                                column='right', field='PARAMVALUE', formatTicks=False, cmap='coolwarm')
                except:
                    print("Unexpected error:", sys.exc_info()[0])
                    pass

                # add debris
                try:
                    # populate and format values
                    bwTons = self.addCommas(
                        results['DebrisBW'].sum(), abbreviate=True)
                    csTons = self.addCommas(
                        results['DebrisCS'].sum(), abbreviate=True)
                    bwTruckLoads = self.addCommas(
                        results['DebrisBW'].sum() * tonsToTruckLoadsCoef, abbreviate=True)
                    csTruckLoads = self.addCommas(
                        results['DebrisCS'].sum() * tonsToTruckLoadsCoef, abbreviate=True)
                    # populate totals
                    totalTons = self.addCommas(
                        results['DebrisTotal'].sum(), abbreviate=True)
                    totalTruckLoads = self.addCommas(
                        results['DebrisTotal'].sum() * tonsToTruckLoadsCoef, abbreviate=True)
                    total = totalTons + ' Tons/' + totalTruckLoads + ' Truck Loads'
                    # build data dictionary
                    data = {'Debris Type': ['Brick, Wood, and Others', 'Contrete & Steel'], 'Tons': [
                        bwTons, csTons], 'Truck Loads': [bwTruckLoads, csTruckLoads]}
                    # create DataFrame from data dictionary
                    debris = pd.DataFrame(
                        data, columns=['Debris Type', 'Tons', 'Truck Loads'])
                    self.addTable(debris, 'Debris', total, 'right')
                except:
                    print("Unexpected error:", sys.exc_info()[0])
                    pass

            if hazard == 'flood':
                # get bulk of results
                try:
                    results = self._Report__getResults()
                    # results = results.addGeometry()
                    results = results.addCounties()
                    results_values = results.groupby(by=['county']).sum()
                    results = results.groupby(by=['county']).first()
                    for column in results_values.columns:
                        results[column] = results_values[column]
                    results = results.drop('block', axis=1)
                    results = results.reset_index()
                except:
                    print("Unexpected error:", sys.exc_info()[0])
                    pass

                try:
                    # add building damage by occupancy
                    buildingDamageByOccupancy = self._Report__getBuildingDamageByOccupancy()
                    # reorder the columns
                    cols = buildingDamageByOccupancy.columns.tolist()
                    cols = [cols[0]] + cols[2:] + [cols[1]]
                    buildingDamageByOccupancy = buildingDamageByOccupancy[cols]
                    # list columns to group for each category
                    yCols = ['Building Loss', 'Content Loss', 'Total Loss']
                    # rename the columns
                    buildingDamageByOccupancy.columns = ['Occupancy'] + yCols
                    # create category column
                    buildingDamageByOccupancy['xCol'] = [
                        x[0:3] for x in buildingDamageByOccupancy['Occupancy']]
                    self.addHistogram(buildingDamageByOccupancy, 'xCol', yCols,
                                      'Building Damage By Occupancy', 'Buildings', 'left')
                except:
                    print("Unexpected error:", sys.exc_info()[0])
                    pass

                # add economic loss
                try:
                    economicLoss = results[['name', 'EconLoss']]
                    economicLoss.columns = [
                        'Top Counties', 'Economic Loss']
                    # populate total
                    total = self.addCommas(
                        economicLoss['Economic Loss'].sum(), truncate=True, abbreviate=True)
                    # limit rows to the highest values
                    economicLoss = economicLoss.sort_values(
                        'Economic Loss', ascending=False)[0:tableRowLimit]
                    # format values
                    economicLoss['Economic Loss'] = [self.toDollars(
                        x, abbreviate=True) for x in economicLoss['Economic Loss']]
                    self.addTable(
                        economicLoss, 'Total Economic Loss', total, 'left')
                except:
                    print("Unexpected error:", sys.exc_info()[0])
                    pass

                # add building damage by building type
                try:
                    buildingDamageByType = self._Report__getBuildingDamageByType()
                    # reorder the columns
                    cols = buildingDamageByType.columns.tolist()
                    cols = [cols[0]] + cols[2:] + [cols[1]]
                    buildingDamageByType = buildingDamageByType[cols]
                    # list columns to group for each category
                    yCols = ['Building Loss', 'Content Loss', 'Total Loss']
                    # rename the columns & create category column
                    buildingDamageByType.columns = ['xCol'] + yCols
                    self.addHistogram(buildingDamageByType, 'xCol', yCols,
                                      'Building Damage By Type', 'Dollars (USD)', 'left')
                except:
                    print("Unexpected error:", sys.exc_info()[0])
                    pass

                # add displaced households and shelter needs
                try:
                    displacedAndShelter = results[[
                        'name', 'DisplacedHouseholds', 'ShelterNeeds']]
                    displacedAndShelter.columns = [
                        'Top Counties', 'Displaced Households', 'People Needing Shelter']
                    # populate totals
                    totalDisplaced = self.addCommas(
                        displacedAndShelter['Displaced Households'].sum(), abbreviate=True)
                    totalShelter = self.addCommas(
                        displacedAndShelter['People Needing Shelter'].sum(), abbreviate=True)
                    total = totalDisplaced + ' Displaced/' + totalShelter + ' Needing Shelter'
                    # limit rows to the highest values
                    displacedAndShelter = displacedAndShelter.sort_values(
                        'Displaced Households', ascending=False)[0:tableRowLimit]
                    # format values
                    for column in displacedAndShelter:
                        if column != 'Top Counties':
                            displacedAndShelter[column] = [self.addCommas(
                                x, abbreviate=True) for x in displacedAndShelter[column]]
                    self.addTable(
                        displacedAndShelter, 'Displaced Households and Sort-Term Shelter Needs', total, 'left')
                except:
                    print("Unexpected error:", sys.exc_info()[0])
                    pass

                # add economic loss map
                try:
                    economicLoss = results[['name', 'EconLoss', 'geometry']]
                    # convert to GeoDataFrame
                    economicLoss.geometry = economicLoss.geometry.apply(loads)
                    gdf = gpd.GeoDataFrame(economicLoss)
                    self.addMap(gdf, title='Economic Loss by County',
                                column='right', field='EconLoss', cmap='OrRd')

                except:
                    print("Unexpected error:", sys.exc_info()[0])
                    pass

                # add hazard map
                try:
                    gdf = self._Report__getHazardGeoDataFrame()
                    title = gdf.title
                    self.addMap(gdf, title=title,
                                column='right', field='PARAMVALUE', formatTicks=False, cmap='Blues')
                except:
                    print("Unexpected error:", sys.exc_info()[0])
                    pass

                # add debris
                try:
                    # populate and format values
                    tons = self.addCommas(
                        results['DebrisTotal'].sum(), abbreviate=True)
                    truckLoads = self.addCommas(
                        results['DebrisTotal'].sum() * tonsToTruckLoadsCoef, abbreviate=True)
                    # populate totals
                    totalTons = tons
                    totalTruckLoads = truckLoads
                    total = totalTons + ' Tons/' + totalTruckLoads + ' Truck Loads'
                    # build data dictionary
                    data = {'Debris Type': ['All Debris'], 'Tons': [
                        tons], 'Truck Loads': [truckLoads]}
                    # create DataFrame from data dictionary
                    debris = pd.DataFrame(
                        data, columns=['Debris Type', 'Tons', 'Truck Loads'])
                    self.addTable(debris, 'Debris', total, 'right')
                except:
                    print("Unexpected error:", sys.exc_info()[0])
                    pass

            if hazard == 'hurricane':
                # get bulk of results
                try:
                    results = self._Report__getResults()
                    # results = results.addGeometry()
                    results = results.addCounties()
                    results_values = results.groupby(by=['county']).sum()
                    results = results.groupby(by=['county']).first()
                    for column in results_values.columns:
                        results[column] = results_values[column]
                    results = results.drop('tract', axis=1)
                    results = results.reset_index()
                except:
                    print("Unexpected error:", sys.exc_info()[0])
                    pass

                # add building damage by occupancy
                try:
                    buildingDamageByOccupancy = self._Report__getBuildingDamageByOccupancy()
                    # create category column
                    buildingDamageByOccupancy['xCol'] = [
                        x[0:3] for x in buildingDamageByOccupancy['Occupancy']]
                    # create new columns for major and destroyed
                    buildingDamageByOccupancy['Major & Destroyed'] = buildingDamageByOccupancy['Major'] + \
                        buildingDamageByOccupancy['Destroyed']
                    # list columns to group for each category
                    yCols = ['Affected', 'Minor', 'Major & Destroyed']
                    self.addHistogram(buildingDamageByOccupancy, 'xCol', yCols,
                                      'Building Damage By Occupancy', 'Buildings', 'left')
                except:
                    print("Unexpected error:", sys.exc_info()[0])
                    pass

                # add economic loss
                try:
                    economicLoss = results[['name', 'EconLoss']]
                    economicLoss.columns = [
                        'Top Counties', 'Economic Loss']
                    # populate total
                    total = self.addCommas(
                        economicLoss['Economic Loss'].sum(), truncate=True, abbreviate=True)
                    # limit rows to the highest values
                    economicLoss = economicLoss.sort_values(
                        'Economic Loss', ascending=False)[0:tableRowLimit]
                    # format values
                    economicLoss['Economic Loss'] = [self.toDollars(
                        x, abbreviate=True) for x in economicLoss['Economic Loss']]
                    self.addTable(
                        economicLoss, 'Total Economic Loss', total, 'left')
                except:
                    print("Unexpected error:", sys.exc_info()[0])
                    pass

                # add essential facilities
                try:
                    essentialFacilities = self._Report__getEssentialFacilities()
                    # create category column
                    essentialFacilities.columns = [
                        x.replace('FacilityType', 'xCol') for x in essentialFacilities.columns]
                    essentialFacilities['Major & Destroyed'] = essentialFacilities['Major'] + \
                        essentialFacilities['Destroyed']
                    # list columns to group for each category
                    yCols = ['Affected', 'Minor', 'Major & Destroyed']
                    self.addHistogram(essentialFacilities, 'xCol', yCols,
                                      'Damaged Essential Facilities', 'Total Facilities', 'left')
                except:
                    print("Unexpected error:", sys.exc_info()[0])
                    pass

                # add displaced households and shelter needs
                try:
                    displacedAndShelter = results[[
                        'name', 'DisplacedHouseholds', 'ShelterNeeds']]
                    displacedAndShelter.columns = [
                        'Top Counties', 'Displaced Households', 'People Needing Shelter']
                    # populate totals
                    totalDisplaced = self.addCommas(
                        displacedAndShelter['Displaced Households'].sum(), abbreviate=True)
                    totalShelter = self.addCommas(
                        displacedAndShelter['People Needing Shelter'].sum(), abbreviate=True)
                    total = totalDisplaced + ' Displaced/' + totalShelter + ' Needing Shelter'
                    # limit rows to the highest values
                    displacedAndShelter = displacedAndShelter.sort_values(
                        'Displaced Households', ascending=False)[0:tableRowLimit]
                    # format values
                    for column in displacedAndShelter:
                        if column != 'Top Counties':
                            displacedAndShelter[column] = [self.addCommas(
                                x, abbreviate=True) for x in displacedAndShelter[column]]
                    self.addTable(
                        displacedAndShelter, 'Displaced Households and Sort-Term Shelter Needs', total, 'left')
                except:
                    print("Unexpected error:", sys.exc_info()[0])
                    pass

                # add economic loss map
                try:
                    economicLoss = results[['name', 'EconLoss', 'geometry']]
                    # convert to GeoDataFrame
                    economicLoss.geometry = economicLoss.geometry.apply(loads)
                    gdf = gpd.GeoDataFrame(economicLoss)
                    self.addMap(gdf, title='Economic Loss by County (USD)', column='right', field='EconLoss', cmap='OrRd')
                except:
                    print("Unexpected error:", sys.exc_info()[0])
                    pass

                # add hazard map
                try:
                    gdf = self._Report__getHazardGeoDataFrame()
                    title = gdf.title
                    # limit the extent
                    gdf = gdf[gdf['PARAMVALUE'] > 0.1]
                    self.addMap(gdf, title=title, column='right', field='PARAMVALUE', formatTicks=False, cmap='coolwarm')
                except:
                    print("Unexpected error:", sys.exc_info()[0])
                    pass

                # add debris
                try:
                    # populate and format values
                    bwTons = self.addCommas(
                        results['DebrisBW'].sum(), abbreviate=True)
                    csTons = self.addCommas(
                        results['DebrisCS'].sum(), abbreviate=True)
                    treeTons = self.addCommas(
                        results['DebrisTree'].sum(), abbreviate=True)
                    eligibleTreeTons = self.addCommas(
                        results['DebrisEligibleTree'].sum(), abbreviate=True)
                    bwTruckLoads = self.addCommas(
                        results['DebrisBW'].sum() * tonsToTruckLoadsCoef, abbreviate=True)
                    csTruckLoads = self.addCommas(
                        results['DebrisCS'].sum() * tonsToTruckLoadsCoef, abbreviate=True)
                    treeTruckLoads = self.addCommas(
                        results['DebrisTree'].sum() * tonsToTruckLoadsCoef, abbreviate=True)
                    eligibleTreeTruckLoads = self.addCommas(
                        results['DebrisEligibleTree'].sum() * tonsToTruckLoadsCoef, abbreviate=True)
                    # populate totals
                    totalTons = self.addCommas(
                        results['DebrisTotal'].sum(), abbreviate=True)
                    totalTruckLoads = self.addCommas(
                        results['DebrisTotal'].sum() * tonsToTruckLoadsCoef, abbreviate=True)
                    total = totalTons + ' Tons/' + totalTruckLoads + ' Truck Loads'
                    # build data dictionary
                    data = {'Debris Type': ['Brick, Wood, and Others', 'Contrete & Steel', 'Tree', 'Eligible Tree'], 'Tons': [
                        bwTons, csTons, treeTons, eligibleTreeTons], 'Truck Loads': [bwTruckLoads, csTruckLoads, treeTruckLoads, eligibleTreeTruckLoads]}
                    # create DataFrame from data dictionary
                    debris = pd.DataFrame(
                        data, columns=['Debris Type', 'Tons', 'Truck Loads'])
                    self.addTable(debris, 'Debris', total, 'right')
                except:
                    print("Unexpected error:", sys.exc_info()[0])
                    pass

            if hazard == 'tsunami':
                # get bulk of results
                try:
                    results = self._Report__getResults()
                    # results = results.addGeometry()
                    results = results.addCounties()
                    results_values = results.groupby(by=['county']).sum()
                    results = results.groupby(by=['county']).first()
                    for column in results_values.columns:
                        results[column] = results_values[column]
                    results = results.drop('block', axis=1)
                    results = results.reset_index()
                except:
                    print("Unexpected error:", sys.exc_info()[0])
                    pass

                # add building damage by occupancy
                try:
                    buildingDamageByOccupancy = self._Report__getBuildingDamageByOccupancy()
                    # create category column
                    buildingDamageByOccupancy['xCol'] = [
                        x[0:3] for x in buildingDamageByOccupancy['Occupancy']]
                    # create new columns for major and destroyed
                    buildingDamageByOccupancy['Major & Destroyed'] = buildingDamageByOccupancy['Major'] + \
                        buildingDamageByOccupancy['Destroyed']
                    # list columns to group for each category
                    yCols = ['Affected', 'Minor', 'Major & Destroyed']
                    self.addHistogram(buildingDamageByOccupancy, 'xCol', yCols,
                                      'Building Damage By Occupancy', 'Buildings', 'left')
                except:
                    print("Unexpected error:", sys.exc_info()[0])
                    pass

                # add economic loss
                try:
                    economicLoss = results[['name', 'EconLoss']]
                    economicLoss.columns = [
                        'Top Counties', 'Economic Loss']
                    # populate total
                    total = self.addCommas(
                        economicLoss['Economic Loss'].sum(), truncate=True, abbreviate=True)
                    # limit rows to the highest values
                    economicLoss = economicLoss.sort_values(
                        'Economic Loss', ascending=False)[0:tableRowLimit]
                    # format values
                    economicLoss['Economic Loss'] = [self.toDollars(
                        x, abbreviate=True) for x in economicLoss['Economic Loss']]
                    self.addTable(
                        economicLoss, 'Total Economic Loss', total, 'left')
                except:
                    print("Unexpected error:", sys.exc_info()[0])
                    pass

                # add injuries and fatatilies
                try:
                    injuriesAndFatatilies = results[['name']]
                    injuriesAndFatatilies.columns = ['Top Counties']
                    injuriesAndFatatilies['Injuries Day'] = results['Injuries_DayGood']
                    injuriesAndFatatilies['Injuries Night'] = results['Injuries_NightGood']
                    injuriesAndFatatilies['Fatalilties Day'] = results['Fatalities_DayGood']
                    injuriesAndFatatilies['Fatalilties Night'] = results['Fatalities_NightGood']
                    # populate totals
                    totalDay = self.addCommas(
                        (injuriesAndFatatilies['Injuries Day'] + injuriesAndFatatilies['Fatalilties Day']).sum(), abbreviate=True) + ' Day'
                    totalNight = self.addCommas(
                        (injuriesAndFatatilies['Injuries Night'] + injuriesAndFatatilies['Fatalilties Night']).sum(), abbreviate=True) + ' Night'
                    total = totalDay + '/' + totalNight
                    # limit rows to the highest values
                    injuriesAndFatatilies = injuriesAndFatatilies.sort_values(
                        'Injuries Day', ascending=False)[0:tableRowLimit]
                    # format values
                    for column in injuriesAndFatatilies:
                        if column != 'Top Counties':
                            injuriesAndFatatilies[column] = [self.addCommas(
                                x, abbreviate=True) for x in injuriesAndFatatilies[column]]

                    self.addTable(injuriesAndFatatilies,
                                  'Injuries and Fatatilies', total, 'left')
                except:
                    print("Unexpected error:", sys.exc_info()[0])
                    pass

                # add economic loss map
                try:
                    economicLoss = results[['name', 'EconLoss', 'geometry']]
                    # convert to GeoDataFrame
                    economicLoss.geometry = economicLoss.geometry.apply(loads)
                    gdf = gpd.GeoDataFrame(economicLoss)
                    self.addMap(gdf, title='Economic Loss by Counties (USD)',
                                column='right', field='EconLoss', cmap='OrRd')
                except:
                    print("Unexpected error:", sys.exc_info()[0])
                    pass

                # add hazard map
                try:
                    gdf = self._Report__getHazardGeoDataFrame()
                    title = gdf.title
                    self.addMap(gdf, title=title,
                                column='right', field='PARAMVALUE', formatTicks=False, cmap='Blues')
                except:
                    print("Unexpected error:", sys.exc_info()[0])
                    pass

                # add travel time to safety map
                try:
                    travelTimeToSafety = self._Report__getTravelTimeToSafety()
                    title = 'Travel Time to Safety (minutes)'
                    self.addMap(travelTimeToSafety, title=title,
                                column='right', field='travelTimeOver65yo', formatTicks=False, cmap='YlOrRd')
                except:
                    print("Unexpected error:", sys.exc_info()[0])
                    pass
        except:
            print("Unexpected error:", sys.exc_info()[0])
            raise
