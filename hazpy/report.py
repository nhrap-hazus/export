from colour import Color
from jenkspy import jenks_breaks as nb
from matplotlib import pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, Normalize
from mpl_toolkits.axes_grid1.axes_divider import make_axes_locatable
from PyPDF2 import PdfFileReader, PdfFileWriter, PdfFileMerger
from PyPDF2.generic import BooleanObject, IndirectObject, NameObject, TextStringObject, DictionaryObject, NumberObject
from reportlab.pdfgen import canvas
from shapely.wkt import loads
from uuid import uuid4 as uuid

import contextily as cx
import datetime
import fitz
import geopandas as gpd
import matplotlib.ticker as ticker
import matplotlib.patheffects as pe
import os
import pandas as pd
import seaborn as sns
import shutil
import sys
import warnings

#from xhtml2pdf import pisa

# Disable pandas warnings
warnings.filterwarnings('ignore')

class Report:
    """-- A StudyRegion helper class --
    Creates a report object. Premade reports are exportable using the save method and
    specifying the report in the parameter premade. The Report class can also be used as an API
    to create reports using the addTable, addHistogram, and addMap methods.

    Keyword Arguments: \n
        title: str -- report title
        subtitle: str -- report subtitle
        icon: str -- report hazard icon (choices: 'earthquake', 'flood', 'hurricane', 'tsunami')

    """

    def __init__(self, studyRegionClass, title, subtitle, icon):
        # double underscores make the method private and not accessible when the class is initialized
        self.__getResults = studyRegionClass.getResults
        self.__getBuildingDamageByOccupancy = (
            studyRegionClass.getBuildingDamageByOccupancy
        )
        self.__getBuildingDamageByType = studyRegionClass.getBuildingDamageByType
        self.__getEssentialFacilities = studyRegionClass.getEssentialFacilities
        self.__getHazardGeoDataFrame = studyRegionClass.getHazardGeoDataFrame
        self.__getTravelTimeToSafety = studyRegionClass.getTravelTimeToSafety
        self.__getInjuries = studyRegionClass.getInjuries
        self.__getFatalities = studyRegionClass.getFatalities
        self.__getHazardBoundary = studyRegionClass.getHazardBoundary
        self.hazard = studyRegionClass.hazard
        self.scenario = studyRegionClass.scenario
        self.returnPeriod = studyRegionClass.returnPeriod
        self.assets = {
            'earthquake': 'https://fema-ftp-snapshot.s3.amazonaws.com/Hazus/Assets/hazard_icons/Earthquake_DHSGreen.png',
            'flood': 'https://fema-ftp-snapshot.s3.amazonaws.com/Hazus/Assets/hazard_icons/Flood_DHSGreen.png',
            'hurricane': 'https://fema-ftp-snapshot.s3.amazonaws.com/Hazus/Assets/hazard_icons/Hurricane_DHSGreen.png',
            'tsunami': 'https://fema-ftp-snapshot.s3.amazonaws.com/Hazus/Assets/hazard_icons/Tsunami_DHSGreen.png',
            'tornado': 'https://fema-ftp-snapshot.s3.amazonaws.com/Hazus/Assets/hazard_icons/Tornado_DHSGreen.png',
            'hazus': 'https://fema-ftp-snapshot.s3.amazonaws.com/Hazus/Assets/hazus_icons/hazus_cropped.png',
        }

        self.columnLeft = ''
        self.columnRight = ''
        self.title = title
        self.subtitle = subtitle
        self.icon = self.assets[icon]
        self.templateFillableLocation = 'Python_env/assets/templates'
        self.disclaimer = """The estimates of social and economic impacts contained in this report were produced using Hazus loss estimation methodology software which is based on current scientific and engineering knowledge. There are uncertainties inherent in any loss estimation
            technique. Therefore, there may be significant differences between the modeled results contained in this report and the actual social and economic losses following a specific {}.""".format(self.hazard)
        self.getCounties = studyRegionClass.getCounties
        self.getStates = studyRegionClass.getStates
        self._tempDirectory = 'hazpy-report-temp'

    def format_tick(self, num, pos):
        num = float('{:.3g}'.format(num))
        magnitude = 0
        while abs(num) >= 1000:
            magnitude += 1
            num /= 1000.0
        if self.hazard == 'flood':
            formatted_number = '${}{}'.format('{:f}'.format(num).rstrip('0').rstrip('.'), ['', 'K', 'M', 'B', 'T'][magnitude])
        else:
            formatted_number = '{}{}'.format('{:f}'.format(num).rstrip('0').rstrip('.'), ['', 'K', 'M', 'B', 'T'][magnitude])
        return formatted_number

# TODO: Remove/replace/refactor with format_tick?? - BC 
    def abbreviate(self, number):
        """[summary]

        Args:
            number ([type]): [description]

        Returns:
            [type]: [description]
        """
        try:
            num = float('{:.3g}'.format(number))
            magnitude = 0
            while abs(num) >= 1000:
                magnitude += 1
                num /= 1000.0
            formatted_number = '{}{}'.format('{:f}'.format(num).rstrip('0').rstrip('.'), ['', 'K', 'M', 'B', 'T'][magnitude])
            return formatted_number
        except:
            return str(number)

    def addCommas(self, number, abbreviate=False, truncate=False):
        """[summary]

        Args:
            number ([type]): [description]
            abbreviate (bool, optional): [description]. Defaults to False.
            truncate (bool, optional): [description]. Defaults to False.

        Returns:
            [type]: [description]
        """
        if truncate:
            number = int(round(number))
        if abbreviate:
            number = self.abbreviate(number)
        else:
            number = "{:,}".format(number)
        return number

    def toDollars(self, number, abbreviate=False, truncate=False):
        """[summary]

        Args:
            number ([type]): [description]
            abbreviate (bool, optional): [description]. Defaults to False.
            truncate (bool, optional): [description]. Defaults to False.

        Returns:
            [type]: [description]
        """
        if truncate:
            number = int(round(number))
        if abbreviate:
            dollars = self.abbreviate(number)
            dollars = '$' + dollars
        else:
            dollars = '$' + "{:,}".format(number)
            dollarsSplit = dollars.split('.')
            if len(dollarsSplit) > 1:
                dollars = '.'.join([dollarsSplit[0], dollarsSplit[1][0:1]])
        return dollars

    def addTable(self, df, title, total, column):
        """Adds a table to the report

        Keyword Arguments: \n
            df: pandas dataframe -- expects a StudyRegionDataFrame
            title: str -- section title
            total: str -- total callout box value
            column: str -- which column in the report to add to (options: 'left', 'right')
        """
        headers = ['<tr>']
        for col in df.columns:
            headers.append(
                '<th class="results_table_cells_header">' + col + '</th>')
        headers.append('</tr')
        headers = ''.join(headers)

        values = []
        for index in range(len(df)):
            row = ['<tr>']
            for col in df.columns:
                row.append(
                    '<td class="results_table_cells">'
                    + str(df.iloc[index][col])
                    + '</td>'
                )
            row.append('</tr>')
            values.append(''.join(row))
        values = ''.join(values)
        template = (
            """
            <div class="result_container">
                <table class="results_table">
                    <tr class="results_table_header">
                        <th class="results_table_header_title">
                            """
            + title
            + """
                        </th>
                        <th class="results_table_header_total">Total:</th>
                        <th class="results_table_header_number">"""
            + total
            + """</th>
                    </tr>
                </table>
                <table class="results_table">
                    """
            + headers
            + """
                    """
            + values
            + """
                </table>
            </div>
            <div class="result_container_spacer">_</div>
        """
        )
        if column == 'left':
            self.columnLeft = self.columnLeft + template
        if column == 'right':
            self.columnRight = self.columnRight + template

    def addMap(
        self,
        gdf,
        field,
        title,
        column,
        legend=False,
        formatTicks=True,
        cmap='Blues',
        scheme=None,
        classification_kwds=None,
        norm=None,
        boundary=True,
        k=None
    ):
        """Adds a map to the report

        Keyword Arguments: \n
            gdf: geopandas geodataframe -- a geodataframe containing the data to be mapped
            field: str -- the field for the choropleth
            title: str -- section title in the report
            column: str -- which column in the report to add to (options: 'left', 'right')
            legend (optional): bool -- adds a colorbar to the map; default = False
            formatTicks (optional): bool -- if True, it will abbreviate and add commas to tick marks; default = True
            cmap (optional): str -- the colormap used for the choropleth; default = 'Blues'
            scheme (optional): str -- the data classification breaks/range scheme; default = None
            classification_kwds (optional): dict -- data classification bins for the userdefined scheme; default = None
            norm(optional): class -- class to normalize data into intervals; default = None
            boundary(optional): bool -- if True, will include the hazard boundary to the map; default = True
        """
        try:
            fig = plt.figure(figsize=(10, 10), dpi=300)
            ax = fig.gca()
            ax2 = fig.gca()
            crs = 'EPSG:4326'
            # Add hazard boundary to map
            if boundary:
                boundary = self._Report__getHazardBoundary()
                if type(boundary) != gpd.GeoDataFrame:
                    try:
                        boundary['geometry'] = boundary['geometry'].apply(str)
                        boundary['geometry'] = boundary['geometry'].apply(loads)
                        boundary = gpd.GeoDataFrame(boundary, geometry='geometry', crs=crs)
                    except:
                        boundary['geometry'] = boundary['geometry'].apply(loads)
                        boundary = gpd.GeoDataFrame(boundary, geometry='geometry', crs=crs)
                # Apply minimal buffer to not cover hazards near study area boundary
                boundary['geometry'] = boundary.geometry.buffer(.0005)
                boundary.to_crs('EPSG:3857').plot(ax=ax, facecolor="none", edgecolor="darkgray", linewidth=0.5, alpha=0.7, linestyle='solid')
            
            if type(gdf) != gpd.GeoDataFrame:
                gdf['geometry'] = gdf['geometry'].apply(str)
                gdf['geometry'] = gdf['geometry'].apply(loads)
                gdf = gpd.GeoDataFrame(gdf, geometry='geometry', crs=crs)
            gdf.crs='EPSG:4326'

            try:
                gdf.to_crs('EPSG:3857', inplace=True)
                gdf.plot(
                    column=field,
                    cmap=cmap,
                    ax=ax,
                    linewidth=0.02,
                    edgecolor="darkgrey",
                    scheme=scheme,
                    classification_kwds=classification_kwds,
                    norm=norm,
                    alpha=0.9
                )
            except:
                gdf['geometry'] = gdf['geometry'].apply(str)
                gdf['geometry'] = gdf['geometry'].apply(loads)
                gdf.to_crs('EPSG:3857').plot(
                    column=field,
                    cmap=cmap,
                    ax=ax,
                    linewidth=0.02,
                    edgecolor="darkgrey",
                    scheme=scheme,
                    classification_kwds=classification_kwds,
                    norm=norm
                )

            # Add county layer
            counties = self.getCounties()
            counties.crs = 'EPSG:4326'
            counties.to_crs('EPSG:3857').plot(facecolor="none", edgecolor="gray", linewidth=0.15, ax=ax, linestyle='solid', alpha=0.7)
            # Add county labels
            labelDF = counties.to_crs('EPSG:3857')
            gdf.to_crs('EPSG:3857')
            gdf['dissolve'] = 1
            mask = gdf.dissolve(by='dissolve').envelope
            mask = mask.buffer(0)
            labelDF['geometry'] = labelDF.buffer(0)
            labelDF = gpd.clip(labelDF, mask)
            labelDF['centroid'] = [x.centroid for x in labelDF['geometry']]
            for row in range(len(labelDF)):
                name = labelDF.iloc[row]['name']
                coords = labelDF.iloc[row]['centroid']
                ax.annotate(
                    text=name,
                    xy=(float(coords.x), float(coords.y)),
                    horizontalalignment='center',
                    size=6,
                    color='white',
                    path_effects=[pe.withStroke(
                        linewidth=1, foreground='#404040')],
                )

            # Add state layer
            states = self.getStates()
            states.crs = 'EPSG:4326'
            states.to_crs('EPSG:3857').plot(
                facecolor="none", edgecolor="black", linewidth=0.5, ax=ax, linestyle='solid', alpha=0.7
            )


            fontsize = 3
            for idx in range(len(fig.axes)):
                fig.axes[idx].tick_params(labelsize=fontsize, size=fontsize)
            ax.axis('off')
            ax.axis('scaled')
            # Zoom into data extents
            xlim = ([gdf.total_bounds[0],  gdf.total_bounds[2]])
            ylim = ([gdf.total_bounds[1],  gdf.total_bounds[3]])
            ax.set_xlim(xlim)
            ax.set_ylim(ylim)
            # Add basemap
            cx.add_basemap(ax, source=cx.providers.Stamen.TonerLite, attribution=None, attribution_size=5, alpha=0.7)
            #ax.autoscale(enable=True, axis='both', tight=False)
            src = os.getcwd() + '/' + self._tempDirectory + '/' + str(uuid()) + ".png"
            fig.savefig(
                src,
                facecolor=fig.get_facecolor(),
                bbox_inches='tight',
                dpi=600,
            )
            fig.clf()
            plt.clf()

            # Convert PNG to PDF
            title = 'map-' + title
            if self.hazard == 'flood':
                if title == 'map-Economic Loss by Census Block':
                    x1 = 319
                    y1 = 133
                    x2 = 597
                    y2 = 372
                if title == 'map-Water Depth (ft) - 100-year':
                    x1 = 319
                    y1 = 412
                    x2 = 597
                    y2 = 628
            if self.hazard == 'earthquake':
                if title == 'map-Economic Loss by Census Tract (USD)':
                    x1 = 319
                    y1 = 114
                    x2 = 597
                    y2 = 350
                if title == 'map-Peak Ground Acceleration (g)':
                    x1 = 315
                    y1 = 425
                    x2 = 590
                    y2 = 660
            if self.hazard == 'hurricane':
                if title == 'map-Economic Loss by Census Tract (USD)':
                    x1 = 315
                    y1 = 130
                    x2 = 602
                    y2 = 380
                if title == 'map-Historic Wind Speeds (mph)':
                    x1 = 315
                    y1 = 410
                    x2 = 602
                    y2 = 630
            if self.hazard == 'tsunami':
                if title == 'map-Economic Loss by Census Block (USD)':
                    x1 = 322
                    y1 = 136
                    x2 = 594
                    y2 = 372
                if title == 'map-Travel Time to Safety (minutes)':
                    x1 = 18
                    y1 = 608
                    x2 = 300
                    y2 = 750
                if title == 'map-Water Depth (ft)':
                    x1 = 322
                    y1 = 410
                    x2 = 594
                    y2 = 640
            try:
                self.insert_image_to_pdf(src, x1, y1, x2, y2)
            except Exception as e:
                self.log_error(e)

                print("Unexpected error:", sys.exc_info()[0])
                pass
        except Exception as e:
            self.log_error(e)
            print("Unexpected error:", sys.exc_info()[0])
            pass

    def addHistogram(
        self,
        df,
        xCol,
        yCols,
        title,
        ylabel,
        column,
        colors=['#549534', '#f3de2c', '#bf2f37'],
    ):
        """Adds a histogram to the report

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
            x = [x.replace('ManufHousing', 'Manufactured\nHousing') for x in df[xCol].values] * len(yCols)
            y = []
            hue = []
            for valueColumn in yCols:
                for category in [x for x in df[xCol].values]:
                    y.append(df[df[xCol] == category][valueColumn].values[0])
                    hue.append(valueColumn)
            dfPlot = pd.DataFrame({'x': x, 'y': y, 'hue': hue})
            plt.figure(figsize=(5, 3), dpi=300)
            colorPalette = dict(zip(dfPlot.hue.unique(), colors))
            ax = sns.barplot(x='x', y='y', hue='hue',
                             data=dfPlot, palette=colorPalette)
            ax.set_xlabel('')
            plt.box(on=None)
            plt.legend(title='', fontsize=8)
            plt.xticks(fontsize=8)
            plt.yticks(fontsize=8)
            tick_locs=ax.yaxis.get_majorticklocs()  
            # TODO: Review fmt (formatting) - BC
            fmt = '{x:,.0f}'
            #tick = ticker.StrMethodFormatter(fmt)
            tick = ticker.FuncFormatter(self.format_tick)
            ax.yaxis.set_major_formatter(tick)
            plt.ylabel(ylabel, fontsize=9)
            plt.tight_layout(pad=0.1, h_pad=None, w_pad=None, rect=None)
            if not os.path.isdir(os.getcwd() + '/' + self._tempDirectory):
                os.mkdir(os.getcwd() + '/' + self._tempDirectory)
            src = os.getcwd() + '/' + self._tempDirectory + '/' + str(uuid()) + ".png"
            plt.savefig(src, pad_inches=0, bbox_inches='tight', dpi=600)
            plt.clf()
            if self.hazard == 'flood':
                if title == 'Building Damage by Occupancy Type':
                    x1 = 19
                    y1 = 116
                    x2 = 297
                    y2 = 245
                if title == 'Building Damage by Type':
                    x1 = 19
                    y1 = 432
                    x2 = 297
                    y2 = 568
            if self.hazard == 'hurricane':
                if title == 'Building Damage by Occupancy Type':
                    x1 = 19
                    y1 = 116
                    x2 = 297
                    y2 = 250
                if title == 'Damaged Essential Facilities':
                    x1 = 19
                    y1 = 434
                    x2 = 297
                    y2 = 568
            if self.hazard == 'tsunami':
                if title == 'Building Damage by Occupancy Type':
                    x1 = 19
                    y1 = 112
                    x2 = 297
                    y2 = 234

            if self.hazard != 'earthquake':
                self.insert_image_to_pdf(src, x1, y1, x2, y2)

        except Exception as e:
            self.log_error(e)
        
            print("Unexpected error:", sys.exc_info()[0])
            plt.clf()
            raise

    def save(self, path, deleteTemp=True, openFile=True, premade=None):
        """Creates a PDF of the report

        Keyword Arguments: \n
            path: str -- the output directory and file name (example: 'C://output_directory/filename.pdf')
            deleteTemp (optional): bool -- delete temp files used to create the report (default: True)
            openFile (optional): bool -- open the PDF after saving (default: True)
            premade (optional): str -- create a premade report (default: None; options: 'earthquake', 'flood', 'hurricane', 'tsunami')
        """
        try:
            if premade is not None:
                try:
                    self.buildPremade(path)
                except Exception as e:
                    self.log_error(e)

                    print("Unexpected error:", sys.exc_info()[0])

            # open output file for writing (truncated binary)
            # TODO: Disable updateTemplate, if not using HTML reports - BC
            #self.updateTemplate()
            #result_file = open(path, "w+b")

            # convert HTML to PDF
            #pisa_status = pisa.CreatePDF(self.template, dest=result_file)

            # close output file
            #result_file.close()

            if openFile:
                os.startfile(path)
            if deleteTemp:
                shutil.rmtree(os.getcwd() + '/' + self._tempDirectory)
            # self.columnLeft = ''
            # self.columnRight = ''

            # return False on success and True on errors
            # return pisa_status.err
        except Exception as e:
            self.log_error(e)

            print("Unexpected error:", sys.exc_info()[0])

            # if premade != None:
            #     self.columnLeft = ''
            #     self.columnRight = ''
            if deleteTemp:
                shutil.rmtree(os.getcwd() + '/' + self._tempDirectory)
            raise

    def insert_image_to_pdf(self, src, x1, y1, x2, y2):
        """Insert image (map/histogram) into fillable PDF

        Args:
            src (str): [description]
            title (str): [description]
            x1 (float): [description]
            y1 (float): [description]
            x2 (float): [description]
            y2 (float): [description]
        """
        templateFile = os.path.join(
            os.getcwd(), self._tempDirectory, self.hazard + '.pdf'
        )
        template = fitz.open(templateFile)
        imageFile = os.path.join(os.getcwd(), self._tempDirectory, src)
        imageRectangle = fitz.Rect(x1, y1, x2, y2)
        firstPage = template[0]
        firstPage.insertImage(
            imageRectangle, filename=imageFile)
        template.save(
            template.name,
            deflate=True,
            incremental=True,
            encryption=fitz.PDF_ENCRYPT_KEEP,
        )
        template.close()

    def insert_fillable_pdf(self, df, dictionary, columns):
        """Insert data into the fillable PDF

        Args:
            df ([type]): [description]
            dictionary (dict): [description]
            columns (list): [description]
        """
        for name, value in columns.items():
            # Set empty rows to default value
            if len(df) < 7:
                default_value = ["-"] * len(df.columns)
                for i in range(len(df), 7, 1):
                    df.loc[i] = default_value
            for row in df.reset_index(drop=True).head(7).itertuples():
                if isinstance(value, str):
                    dictItem = name + str(row.Index + 1)
                    dictionary[dictItem] = getattr(row, value)
                else:
                    dictItem = name + str(row.Index + 1)
                    # Omit empty rows
                    if getattr(row, value[0]) != "-":
                        dictionary[dictItem] = (
                            getattr(row, value[0]) + '/' + getattr(row, value[1])
                        )
                    else:
                        dictionary[dictItem] =  getattr(row, value[0])

    def set_needed_appearances(self, writer):
        """Set the needed appearances for the fillable PDF to show values in fillable form fields

        Args:
            writer ([type]): [description]

        Returns:
            [type]: [description]
        """
        catalog = writer._root_object
        # Set metadata properties
        if "/AcroForm" not in catalog:
            writer._root_object.update(
                {
                    NameObject("/AcroForm"): IndirectObject(
                        len(writer._objects), 0, writer
                    )
                }
            )
        if '/Lang' not in catalog:
            writer._root_object.update(
                {
                    NameObject('/Lang'): TextStringObject(
                        'en'
                    )
                }
            )
        if '/ViewerPreferences' not in catalog:
            writer._root_object.update(
                {
                    NameObject('/ViewerPreferences'): DictionaryObject(
                        {
                        }
                    )
                }
            )

        if '/MarkInfo' not in catalog:
            writer._root_object.update(
                {
                    NameObject('/MarkInfo'): DictionaryObject(
                        {
                        }
                    )
                }
            )
        # if "/StructTreeRoot" not in catalog:
        #     writer._root_object.update(
        #         {
        #             NameObject("/StructTreeRoot"): IndirectObject(
        #                 len(writer._objects), 0, writer
        #             )
        #         }
        #     )
        need_appearances = NameObject("/NeedAppearances")
        display_doc_title = NameObject('/DisplayDocTitle')
        marked_info = NameObject('/Marked')
        writer._root_object["/AcroForm"][need_appearances] = BooleanObject(
            True)
        writer._root_object["/ViewerPreferences"][display_doc_title] = BooleanObject(
            True)
        writer._root_object["/MarkInfo"][marked_info] = BooleanObject(
            True)

        return writer

    def write_fillable_pdf(self, data_dict, path, openFile=False):
        """Insert data into fillable PDF

        Args:
            data_dict (dict): [description]
            path (str): [description]
        """
        try:
            if path.split('/')[-1] == 'report_summary.pdf':
                outputPdf = path
        except:
            outputPdf = os.path.join(path, 'report_summary.pdf')
        #outputPdf = os.path.join(path, 'report_summary.pdf')
        reportTemplate = os.path.join(
            os.getcwd(), self._tempDirectory, self.hazard + '.pdf'
        )
        with open(reportTemplate, 'rb') as inputStream:
            pdfReader = PdfFileReader(inputStream, strict=False)
            pdfFileWriter = PdfFileWriter()
            self.set_needed_appearances(pdfFileWriter)
            if "/AcroForm" in pdfFileWriter._root_object:
                pdfFileWriter.addPage(pdfReader.getPage(0))
                pdfFileWriter.updatePageFormFieldValues(
                    pdfFileWriter.getPage(0), data_dict
                )
            # Turn off editable fields
            for j in range(0, len(pdfFileWriter.getPage(0)['/Annots'])):
                writer_annot = pdfFileWriter.getPage(0)['/Annots'][j].getObject()
                for field in data_dict:
                    if writer_annot.get('/T') == field:
                        writer_annot.update({
                            NameObject("/Ff"): NumberObject(1)    # make ReadOnly
                        })
            metadata = pdfReader.getDocumentInfo()
            pdfFileWriter.addMetadata(metadata)
            with open(outputPdf, 'wb') as outputStream:
                pdfFileWriter.write(outputStream)
            # Open PDF File
            if openFile:
                os.startfile(path)

    def buildPremade(self, path):
        """Builds a premade report"""
        try:
            # assign constants
            tableRowLimit = 7
            tonsToTruckLoadsCoef = 25
            hazard = self.hazard
            if not os.path.isdir(os.getcwd() + '\\' + self._tempDirectory):
                os.mkdir(os.getcwd() + '/' + self._tempDirectory)
            templateDirectory = os.path.join(
                os.getcwd(), self.templateFillableLocation, self.hazard.title() + '.pdf'
            )
            copyLocation = os.path.join(os.getcwd(), self._tempDirectory)
            shutil.copy(templateDirectory, copyLocation)

            ###################################################
            # Earthquake
            ###################################################
            if hazard == 'earthquake':
                eqDataDictionary = {}
                eqDataDictionary['title'] = self.title
                eqDataDictionary['date'] = 'Hazus Report Generated: {}'.format(
                    datetime.datetime.now().strftime('%m-%d-%Y').lstrip('0')
                )
                # get bulk of results
                results = self._Report__getResults()
                results = results.addGeometry()

                ###################################
                # Earthquake - Building Damage
                ###################################
                # add Building Damage by Occupancy Type
                try:
                    buildingDamageByOccupancy = (
                        self._Report__getBuildingDamageByOccupancy()
                    )

                    RES = buildingDamageByOccupancy[
                        buildingDamageByOccupancy['Occupancy'].apply(
                            lambda x: x.startswith('RES')
                        )
                    ]
                    COM = buildingDamageByOccupancy[
                        buildingDamageByOccupancy['Occupancy'].apply(
                            lambda x: x.startswith('COM')
                        )
                    ]
                    IND = buildingDamageByOccupancy[
                        buildingDamageByOccupancy['Occupancy'].apply(
                            lambda x: x.startswith('IND')
                        )
                    ]
                    AGR = buildingDamageByOccupancy[
                        buildingDamageByOccupancy['Occupancy'].apply(
                            lambda x: x.startswith('AGR')
                        )
                    ]
                    EDU = buildingDamageByOccupancy[
                        buildingDamageByOccupancy['Occupancy'].apply(
                            lambda x: x.startswith('EDU')
                        )
                    ]
                    GOV = buildingDamageByOccupancy[
                        buildingDamageByOccupancy['Occupancy'].apply(
                            lambda x: x.startswith('GOV')
                        )
                    ]
                    REL = buildingDamageByOccupancy[
                        buildingDamageByOccupancy['Occupancy'].apply(
                            lambda x: x.startswith('REL')
                        )
                    ]

                    eqDataDictionary['g_res'] = self.addCommas(
                        RES['Minor'].sum(), abbreviate=True
                    )
                    eqDataDictionary['g_com'] = self.addCommas(
                        COM['Minor'].sum(), abbreviate=True
                    )
                    eqDataDictionary['g_ind'] = self.addCommas(
                        IND['Minor'].sum(), abbreviate=True
                    )
                    eqDataDictionary['g_agr'] = self.addCommas(
                        AGR['Minor'].sum(), abbreviate=True
                    )
                    eqDataDictionary['g_edu'] = self.addCommas(
                        EDU['Minor'].sum(), abbreviate=True
                    )
                    eqDataDictionary['g_gov'] = self.addCommas(
                        GOV['Minor'].sum(), abbreviate=True
                    )
                    eqDataDictionary['g_rel'] = self.addCommas(
                        REL['Minor'].sum(), abbreviate=True
                    )
                    eqDataDictionary['y_res'] = self.addCommas(
                        RES['Major'].sum(), abbreviate=True
                    )
                    eqDataDictionary['y_com'] = self.addCommas(
                        COM['Major'].sum(), abbreviate=True
                    )
                    eqDataDictionary['y_ind'] = self.addCommas(
                        IND['Major'].sum(), abbreviate=True
                    )
                    eqDataDictionary['y_agr'] = self.addCommas(
                        AGR['Major'].sum(), abbreviate=True
                    )
                    eqDataDictionary['y_edu'] = self.addCommas(
                        EDU['Major'].sum(), abbreviate=True
                    )
                    eqDataDictionary['y_gov'] = self.addCommas(
                        GOV['Major'].sum(), abbreviate=True
                    )
                    eqDataDictionary['y_rel'] = self.addCommas(
                        REL['Major'].sum(), abbreviate=True
                    )
                    eqDataDictionary['r_res'] = self.addCommas(
                        RES['Destroyed'].sum(), abbreviate=True
                    )
                    eqDataDictionary['r_com'] = self.addCommas(
                        COM['Destroyed'].sum(), abbreviate=True
                    )
                    eqDataDictionary['r_ind'] = self.addCommas(
                        IND['Destroyed'].sum(), abbreviate=True
                    )
                    eqDataDictionary['r_agr'] = self.addCommas(
                        AGR['Destroyed'].sum(), abbreviate=True
                    )
                    eqDataDictionary['r_edu'] = self.addCommas(
                        EDU['Destroyed'].sum(), abbreviate=True
                    )
                    eqDataDictionary['r_gov'] = self.addCommas(
                        GOV['Destroyed'].sum(), abbreviate=True
                    )
                    eqDataDictionary['r_rel'] = self.addCommas(
                        REL['Destroyed'].sum(), abbreviate=True
                    )
                    # create category column
                    buildingDamageByOccupancy['xCol'] = [
                        x[0:3] for x in buildingDamageByOccupancy['Occupancy']
                    ]
                    # create new columns for major and destroyed
                    buildingDamageByOccupancy['Major & Destroyed'] = (
                        buildingDamageByOccupancy['Major']
                        + buildingDamageByOccupancy['Destroyed']
                    )
                    # list columns to group for each category
                    yCols = ['Affected', 'Minor', 'Major & Destroyed']
                    self.addHistogram(
                        buildingDamageByOccupancy,
                        'xCol',
                        yCols,
                        'Building Damage by Occupancy Type',
                        'Buildings',
                        'left',
                    )
                except Exception as e:
                    self.log_error(e)
                    print("Unexpected error:", sys.exc_info()[0])
                    pass
                ###################################
                # Earthquake Economic Loss
                ###################################
                # add economic loss
                try:
                    counties = self.getCounties()
                    economicResults = results[['tract', 'EconLoss']]
                    economicResults['countyfips'] = economicResults.tract.str[:5]
                    economicLoss = pd.merge(
                        economicResults, counties, how="inner", on=['countyfips']
                    )
                    economicLoss.drop(
                        ['size', 'tract', 'countyfips', 'geometry', 'crs'],
                        axis=1,
                        inplace=True,
                    )
                    economicLoss.columns = ['EconLoss', 'TopCounties', 'State']
                    # populate total
                    total = self.addCommas(
                        economicLoss['EconLoss'].sum(), truncate=True, abbreviate=True
                    )
                    # limit rows to the highest values & group by county
                    economicLoss = (
                        economicLoss.groupby(['TopCounties', 'State'])[
                            'EconLoss']
                        .sum()
                        .reset_index()
                    )
                    economicLoss = economicLoss.sort_values(
                        'EconLoss', ascending=False
                    )[0:tableRowLimit]
                    # format values
                    economicLoss['EconLoss'] = [
                        self.toDollars(x, abbreviate=True)
                        for x in economicLoss['EconLoss']
                    ]
                    columns = {
                        'econloss_county_': 'TopCounties',
                        'econloss_state_': 'State',
                        'econloss_total_': 'EconLoss',
                    }
                    eqDataDictionary['total_econloss'] = '$' + total
                    # Populate total count
                    eqDataDictionary['econ_loss_count'] = f"({self.abbreviate(len(economicResults.index)).replace(' ', '')} Tracts with Losses)"
                    self.insert_fillable_pdf(
                        economicLoss, eqDataDictionary, columns)
                    #  'total_econloss': total - Add to table
                    self.addTable(
                        economicLoss, 'Total Economic Loss', total, 'left')
                except Exception as e:
                    self.log_error(e)
                    print("Unexpected error:", sys.exc_info()[0])
                    pass
                ####################################################
                # Earthquake - Injuries and Fatalities
                ####################################################
                # add injuries and fatatilies
                try:
                    counties = self.getCounties()
                    injuriesAndFatatiliesResults = results[['tract']]
                    injuriesAndFatatiliesResults[
                        'countyfips'
                    ] = injuriesAndFatatiliesResults.tract.str[:5]
                    injuriesAndFatatilies = pd.merge(
                        injuriesAndFatatiliesResults,
                        counties,
                        how="inner",
                        on=['countyfips'],
                    )
                    injuriesAndFatatilies.drop(
                        ['size', 'countyfips', 'geometry', 'crs', 'tract'],
                        axis=1,
                        inplace=True,
                    )
                    injuriesAndFatatilies.columns = ['TopCounties', 'State']
                    injuriesAndFatatilies['InjuriesDay'] = (
                        results['Injury_DayLevel1']
                        + results['Injury_DayLevel2']
                        + results['Injury_DayLevel3']
                    )
                    injuriesAndFatatilies['InjuriesNight'] = (
                        results['Injury_NightLevel1']
                        + results['Injury_NightLevel2']
                        + results['Injury_NightLevel3']
                    )
                    injuriesAndFatatilies['FatalitiesDay'] = results['Fatalities_Day']
                    injuriesAndFatatilies['FatalitiesNight'] = results[
                        'Fatalities_Night'
                    ]
                    # populate totals
                    totalDay = (
                        self.addCommas(
                            (
                                injuriesAndFatatilies['InjuriesDay']
                                + injuriesAndFatatilies['FatalitiesDay']
                            ).sum(),
                            abbreviate=True,
                        )
                     #   + ' Day'
                    )
                    totalNight = (
                        self.addCommas(
                            (
                                injuriesAndFatatilies['InjuriesNight']
                                + injuriesAndFatatilies['FatalitiesNight']
                            ).sum(),
                            abbreviate=True,
                        )
                     #   + ' Night'
                    )
                    total = totalDay + '/' + totalNight
                    # limit rows to the highest values
                    injuriesAndFatatilies = (
                        injuriesAndFatatilies.groupby(['TopCounties', 'State'])[
                            'InjuriesDay',
                            'InjuriesNight',
                            'FatalitiesDay',
                            'FatalitiesNight',
                        ]
                        .sum()
                        .reset_index()
                    )
                    injuriesAndFatatilies = injuriesAndFatatilies.sort_values(
                        'InjuriesDay', ascending=False
                    )[0:tableRowLimit]
                    # format values
                    for column in injuriesAndFatatilies:
                        if column not in ['TopCounties', 'State']:
                            injuriesAndFatatilies[column] = [
                                self.addCommas(x, abbreviate=True)
                                for x in injuriesAndFatatilies[column]
                            ]
                    columns = {
                        'nonfatal_county_': 'TopCounties',
                        'nonfatal_state_': 'State',
                        'nonfatal_pop_': ['InjuriesDay', 'InjuriesNight'],
                        'nonfatal_injuries_': ['FatalitiesDay', 'FatalitiesNight'],
                    }
                    self.insert_fillable_pdf(
                        injuriesAndFatatilies, eqDataDictionary, columns
                    )
                    eqDataDictionary['total_day'] = totalDay
                    eqDataDictionary['total_night'] = totalNight
                    self.addTable(
                        injuriesAndFatatilies, 'Injuries and Fatatilies', total, 'left'
                    )
                except Exception as e:
                    self.log_error(e)
                    print("Unexpected error:", sys.exc_info()[0])
                    pass
                ################################################
                # Earthquake - Displaced Households & Shelter Needs
                ################################################
                # add displaced households and shelter needs
                try:
                    counties = self.getCounties()
                    displacedAndShelterResults = results[
                        ['tract', 'DisplacedHouseholds', 'ShelterNeeds']
                    ]
                    displacedAndShelterResults[
                        'countyfips'
                    ] = displacedAndShelterResults.tract.str[:5]
                    displacedAndShelter = pd.merge(
                        displacedAndShelterResults,
                        counties,
                        how="inner",
                        on=['countyfips'],
                    )
                    displacedAndShelter.drop(
                        ['size', 'countyfips', 'geometry', 'crs', 'tract'],
                        axis=1,
                        inplace=True,
                    )
                    displacedAndShelter.columns = [
                        'DisplacedHouseholds',
                        'ShelterNeeds',
                        'TopCounties',
                        'State',
                    ]
                    # populate totals
                    totalDisplaced = self.addCommas(
                        displacedAndShelter['DisplacedHouseholds'].sum(),
                        abbreviate=True,
                    )
                    totalShelter = self.addCommas(
                        displacedAndShelter['ShelterNeeds'].sum(), abbreviate=True
                    )
                    total = (
                        totalDisplaced
                        + ' Displaced/'
                        + totalShelter
                        + ' Needing Shelter'
                    )
                    # limit rows to the highest values
                    displacedAndShelter = (
                        displacedAndShelter.groupby(['TopCounties', 'State'])[
                            'DisplacedHouseholds', 'ShelterNeeds'
                        ]
                        .sum()
                        .reset_index()
                    )
                    displacedAndShelter = displacedAndShelter.sort_values(
                        'DisplacedHouseholds', ascending=False
                    )[0:tableRowLimit]
                    # format values
                    for column in displacedAndShelter:
                        if column not in ('State', 'TopCounties'):
                            displacedAndShelter[column] = [
                                self.addCommas(x, abbreviate=True)
                                for x in displacedAndShelter[column]
                            ]
                    columns = {
                        'shelter_county_': 'TopCounties',
                        'shelter_state_': 'State',
                        'shelter_house_': 'DisplacedHouseholds',
                        'shelter_need_': 'ShelterNeeds',
                    }
                    self.insert_fillable_pdf(
                        displacedAndShelter, eqDataDictionary, columns
                    )
                    eqDataDictionary['total_displaced'] = totalDisplaced
                    eqDataDictionary['total_need_shelter'] = totalShelter
                    self.addTable(
                        displacedAndShelter,
                        'Displaced Households and Short-Term Shelter Needs',
                        total,
                        'left',
                    )
                except Exception as e:
                    self.log_error(e)

                    print("Unexpected error:", sys.exc_info()[0])
                    pass
                ###################################
                # Earthquake - Economic Loss Map
                ###################################
                # add economic loss map
                try:
                    economicLoss = results[['tract', 'EconLoss', 'geometry']]
                    breaks = nb(results['EconLoss'], nb_class=4)
                    legend_item1 = breaks[0]
                    legend_item2 = breaks[1]
                    legend_item3 = breaks[2]
                    legend_item4 = breaks[3]
                    legend_item5 = breaks[4]
                    eqDataDictionary['legend_1'] = (
                        '$'
                        + self.abbreviate(legend_item1)
                        + '-'
                        + self.abbreviate(legend_item2)
                    )
                    eqDataDictionary['legend_2'] = (
                        '$'
                        + self.abbreviate(legend_item2)
                        + '-'
                        + self.abbreviate(legend_item3)
                    )
                    eqDataDictionary['legend_3'] = (
                        '$'
                        + self.abbreviate(legend_item3)
                        + '-'
                        + self.abbreviate(legend_item4)
                    )
                    eqDataDictionary['legend_4'] = (
                        '$'
                        + self.abbreviate(legend_item4)
                        + '-'
                        + self.abbreviate(legend_item5)
                    )
                    # convert to GeoDataFrame
                    economicLoss.geometry = economicLoss.geometry.apply(loads)
                    gdf = gpd.GeoDataFrame(economicLoss)
                    map_colors = ['#fabfa1', '#f3694c', '#d62128', '#6b0d0d']
                    color_ramp = LinearSegmentedColormap.from_list(
                        'color_list', [
                            Color(color).rgb for color in map_colors]
                    )
                    self.addMap(
                        gdf,
                        title='Economic Loss by Census Tract (USD)',
                        column='right',
                        field='EconLoss',
                        cmap=color_ramp,
                        scheme='NaturalBreaks',
                        k=4
                    )
                except Exception as e:
                    self.log_error(e)
                    print("Unexpected error:", sys.exc_info()[0])
                    pass
                ###################################
                # Earthquake - Hazard Map
                ###################################
                # add hazard map
                try:
                    gdf = self._Report__getHazardGeoDataFrame()
                    title = 'Peak Ground Acceleration (g)'
                    # limit the extent
                   # gdf = gdf[gdf['PARAMVALUE'] > 0.1]
                    map_colors = [
                        '#ffffff',
                        '#bfccff',
                        '#80ffff',
                        '#7aff93',
                        '#fefe0a',
                        '#ffc800',
                        '#ff9100',
                        '#ff0000',
                        '#800000',
                    ]

                    color_ramp = LinearSegmentedColormap.from_list(
                        'color_list', [
                            Color(color).rgb for color in map_colors]
                    )
                    # Are these PGV values? - BC
                    # TODO: Review if these are PGV or PGA values --> talk with Doug
                    # TODO: Are there any conversions needed?
                    # bins = [
                    #     0.002,
                    #     0.014,
                    #     0.039,
                    #     0.092,
                    #     0.180,
                    #     0.340,
                    #     0.650,
                    #     1.240,
                    #     3.000
                    # ]
                    # bins = [
                    #     .0016,
                    #     .0139,
                    #     .0389,
                    #     .0919,
                    #     .1799,
                    #     .3399,
                    #     .6499,
                    #     1.2399
                    # ]
                    bins = [
                        .0017,
                        .0140,
                        .0390,
                        .0920,
                        .1800,
                        .3400,
                        .6500,
                        1.24
                    ]

                    classification_kwds = {'bins': bins}
                    self.addMap(
                        gdf,
                        title=title,
                        column='right',
                        field='PARAMVALUE',
                        formatTicks=False,
                        cmap=color_ramp,
                        scheme='UserDefined',
                        classification_kwds=classification_kwds,
                        norm=Normalize(0, len(bins)),
                    )
                except Exception as e:
                    self.log_error(e)
                    print("Unexpected error:", sys.exc_info()[0])
                    pass
                ###################################
                # Earthquake - Add Debris
                ###################################
                # add debris
                try:
                    # TODO: Round truckloads debris
                    # populate and format values
                    bwTons = self.addCommas(
                        results['DebrisBW'].sum(), abbreviate=True)
                    csTons = self.addCommas(
                        results['DebrisCS'].sum(), abbreviate=True)
                    bwTruckLoads = self.addCommas(
                        results['DebrisBW'].sum() / tonsToTruckLoadsCoef,
                        abbreviate=True,
                    )
                    csTruckLoads = self.addCommas(
                        results['DebrisCS'].sum() / tonsToTruckLoadsCoef,
                        abbreviate=True,
                    )
                    # populate totals
                    totalTons = self.addCommas(
                        results['DebrisTotal'].sum(), abbreviate=True
                    )
                    totalTruckLoads = self.addCommas(
                        results['DebrisTotal'].sum() / tonsToTruckLoadsCoef,
                        abbreviate=True,
                    )
                    total = totalTons + ' Tons/' + totalTruckLoads + ' Truck Loads'
                    # build data dictionary
                    data = {
                        'Debris Type': ['Brick, Wood, and Other', 'Concrete & Steel'],
                        'Tons': [bwTons, csTons],
                        'Truck Loads': [bwTruckLoads, csTruckLoads],
                    }
                    # create DataFrame from data dictionary
                    debris = pd.DataFrame(
                        data, columns=['Debris Type', 'Tons', 'Truck Loads']
                    )
                    eqDataDictionary['debris_type_1'] = debris['Debris Type'][0]
                    eqDataDictionary['debris_tons_1'] = debris['Tons'][0]
                    eqDataDictionary['debris_type_2'] = debris['Debris Type'][1]
                    eqDataDictionary['debris_tons_2'] = debris['Tons'][1]
                    eqDataDictionary['total_debris_tons'] = totalTons
                    eqDataDictionary['total_debris_truckloads'] = totalTruckLoads
                    self.addTable(debris, 'Debris', total, 'right')
                    self.write_fillable_pdf(eqDataDictionary, path)
                except Exception as e:
                    self.log_error(e)
                    print("Unexpected error:", sys.exc_info()[0])
                    pass

            ###################################################
            # Flood
            ###################################################
            if hazard == 'flood':
                floodDataDictionary = {}
                floodDataDictionary['title'] = self.title
                floodDataDictionary['date'] = 'Hazus Report Generated: {}'.format(
                    datetime.datetime.now().strftime('%m-%d-%Y').lstrip('0')
                )
                # get bulk of results
                try:
                    results = self._Report__getResults()
                    results = results.addGeometry()
                except Exception as e:
                    self.log_error(e)

                    print("Unexpected error:", sys.exc_info()[0])
                    pass
                ###################################
                # Flood - Building Damage
                ###################################
                try:
                    # add Building Damage by Occupancy Type
                    buildingDamageByOccupancy = (
                        self._Report__getBuildingDamageByOccupancy()
                    )
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
                        x[0:3] for x in buildingDamageByOccupancy['Occupancy']
                    ]
                    buildingDamageByOccupancy = (
                        buildingDamageByOccupancy.groupby(['xCol'])[
                            'Building Loss', 'Content Loss', 'Total Loss'
                        ]
                        .sum()
                        .reset_index()
                    )

                    self.addHistogram(
                        buildingDamageByOccupancy,
                        'xCol',
                        yCols,
                        'Building Damage by Occupancy Type',
                        'Dollars (USD)',
                        'left',
                    )
                except Exception as e:
                    self.log_error(e)

                    print("Unexpected error:", sys.exc_info()[0])
                    pass
                ###################################
                # Flood Economic Loss
                ###################################
                # add economic loss
                try:
                    counties = self.getCounties()
                    economicResults = results[['block', 'EconLoss']]
                    economicResults['countyfips'] = economicResults.block.str[:5]
                    economicLoss = pd.merge(
                        economicResults, counties, how="inner", on=['countyfips']
                    )
                    economicLoss.drop(
                        ['size', 'countyfips', 'geometry', 'crs'],
                        axis=1,
                        inplace=True,
                    )
                    economicLoss.columns = [
                        'TopBlocks', 'EconomicLoss', 'CountyName', 'State']
                    # populate total
                    total = self.addCommas(
                        economicLoss['EconomicLoss'].sum(),
                        truncate=True,
                        abbreviate=True,
                    )
                    # limit rows to the highest values
                    economicLoss = economicLoss.sort_values(
                        'EconomicLoss', ascending=False
                    )[0:tableRowLimit]
                    # format values
                    economicLoss['EconomicLoss'] = [
                        self.toDollars(x, abbreviate=True)
                        for x in economicLoss['EconomicLoss']
                    ]
                    columns = {
                        'econloss_block_': 'TopBlocks',
                        'econloss_county_': 'CountyName',
                        'econloss_state_': 'State',
                        'econloss_total_': 'EconomicLoss',
                    }
                    floodDataDictionary['econ_loss_count'] = f"({self.abbreviate(len(economicResults.index)).replace(' ', '')} Blocks with Losses)"
                    self.insert_fillable_pdf(
                        economicLoss, floodDataDictionary, columns)
                    floodDataDictionary['total_econloss'] = '$' + total
                    self.addTable(
                        economicLoss, 'Total Economic Loss', total, 'left')
                except Exception as e:
                    self.log_error(e)

                    print("Unexpected error:", sys.exc_info()[0])
                    pass

                #######################################################
                # Flood - Building Damaged by Building Type
                #######################################################
                # add Building Damage by building type
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
                    self.addHistogram(
                        buildingDamageByType,
                        'xCol',
                        yCols,
                        'Building Damage by Type',
                        'Dollars (USD)',
                        'left',
                    )
                except Exception as e:
                    self.log_error(e)

                    print("Unexpected error:", sys.exc_info()[0])
                    pass

                ################################################
                # Flood - Displaced Households & Shelter Needs
                ################################################
                # add displaced households and shelter needs
                try:
                    counties = self.getCounties()
                    displacedAndShelterResults = results[
                        ['block', 'DisplacedPopulation', 'ShelterNeeds']
                    ]
                    displacedAndShelterResults[
                        'countyfips'
                    ] = displacedAndShelterResults.block.str[:5]
                    displacedAndShelter = pd.merge(
                        displacedAndShelterResults,
                        counties,
                        how="inner",
                        on=['countyfips'],
                    )
                    displacedAndShelter.drop(
                        ['size', 'countyfips', 'state', 'geometry', 'crs', 'name'],
                        axis=1,
                        inplace=True,
                    )
                    displacedAndShelter.columns = [
                        'TopBlocks',
                        'DisplacedPopulation',
                        'PeopleNeedingShelter',
                    ]
                    # populate totals
                    totalDisplaced = self.addCommas(
                        displacedAndShelter['DisplacedPopulation'].sum(),
                        abbreviate=True,
                    )
                    totalShelter = self.addCommas(
                        displacedAndShelter['PeopleNeedingShelter'].sum(),
                        abbreviate=True,
                    )
                    total = (
                        totalDisplaced
                        + ' Displaced/'
                        + totalShelter
                        + ' Needing Shelter'
                    )
                    # limit rows to the highest values
                    displacedAndShelter = displacedAndShelter.sort_values(
                        'DisplacedPopulation', ascending=False
                    )[0:tableRowLimit]
                    # format values
                    for column in displacedAndShelter:
                        if column != 'TopBlocks':
                            displacedAndShelter[column] = [
                                self.addCommas(x, abbreviate=True)
                                for x in displacedAndShelter[column]
                            ]
                    columns = {
                        'shelter_county_': 'TopBlocks',
                        'shelter_house_': 'DisplacedPopulation',
                        'shelter_need_': 'PeopleNeedingShelter',
                    }
                    self.insert_fillable_pdf(
                        displacedAndShelter, floodDataDictionary, columns
                    )
                  #  floodDataDictionary['total_shelter'] = total
                    floodDataDictionary['total_displaced'] = totalDisplaced
                    floodDataDictionary['total_need_shelter'] = totalShelter
                    self.addTable(
                        displacedAndShelter,
                        'Displaced Households and Sort-Term Shelter Needs',
                        total,
                        'left',
                    )
                except Exception as e:
                    self.log_error(e)
                    print("Unexpected error:", sys.exc_info()[0])
                    pass

                ###################################
                # Flood - Economic Loss Map
                ###################################
                # add economic loss map
                try:
                    economicLoss = results[['block', 'EconLoss', 'geometry']]
                    # convert to GeoDataFrame
                    breaks = nb(results['EconLoss'], nb_class=4)
                #    breaks = self.equal_interval(
                   #     results['EconLoss'].to_list(), 4)
                    legend_item1 = breaks[0]
                    legend_item2 = breaks[1]
                    legend_item3 = breaks[2]
                    legend_item4 = breaks[3]
                    legend_item5 = breaks[4]
                    floodDataDictionary['legend_1'] = (
                        '$'
                        + self.abbreviate(legend_item1)
                        + '-'
                        + self.abbreviate(legend_item2)
                    )
                    floodDataDictionary['legend_2'] = (
                        '$'
                        + self.abbreviate(legend_item2)
                        + '-'
                        + self.abbreviate(legend_item3)
                    )
                    floodDataDictionary['legend_3'] = (
                        '$'
                        + self.abbreviate(legend_item3)
                        + '-'
                        + self.abbreviate(legend_item4)
                    )
                    floodDataDictionary['legend_4'] = (
                        '$'
                        + self.abbreviate(legend_item4)
                        + '-'
                        + self.abbreviate(legend_item5)
                    )
                    economicLoss.geometry = economicLoss.geometry.apply(loads)
                    gdf = gpd.GeoDataFrame(economicLoss)
                    map_colors = ['#fabfa1', '#f3694c', '#d62128', '#6b0d0d']
                    color_ramp = LinearSegmentedColormap.from_list(
                        'color_list', [
                            Color(color).rgb for color in map_colors]
                    )
                    self.addMap(
                        gdf,
                        title='Economic Loss by Census Block',
                        column='right',
                        field='EconLoss',
                        cmap=color_ramp,
                        scheme='NaturalBreaks',
                        k=4
                    )
                except Exception as e:
                    self.log_error(e)
                    print("Unexpected error:", sys.exc_info()[0])
                    pass
                ###################################
                # Flood - Hazard Map
                ###################################
                # add hazard map
                try:
                    gdf = self._Report__getHazardGeoDataFrame()
                    title = 'Water Depth (ft) - 100-year'
                    gdf = gdf[gdf['PARAMVALUE'] > 0.1]
                    map_colors = ['#00FFFF', '#55AAFF', '#AA55FF', '#FF00FF'] # cool - BC
                    color_ramp = LinearSegmentedColormap.from_list(
                        'color_list', [
                            Color(color).rgb for color in map_colors]
                    )
                    # convert to GeoDataFrame
               #     breaks = nb(gdf['PARAMVALUE'], nb_class=4)
                    # breaks = self.equal_interval(
                    #     gdf['PARAMVALUE'].to_list(), 4)
                    # legend_item1 = breaks[0]
                    # legend_item2 = breaks[1]
                    # legend_item3 = breaks[2]
                    # legend_item4 = breaks[3]
                    # legend_item5 = breaks[4]
                    # floodDataDictionary['wd_legend_1'] = (
                    #     self.abbreviate(legend_item1)
                    #     + '-'
                    #     + self.abbreviate(legend_item2)
                    # )
                    # floodDataDictionary['wd_legend_2'] = (
                    #     self.abbreviate(legend_item2)
                    #     + '-'
                    #     + self.abbreviate(legend_item3)
                    # )
                    # floodDataDictionary['wd_legend_3'] = (
                    #     self.abbreviate(legend_item3)
                    #     + '-'
                    #     + self.abbreviate(legend_item4)
                    # )
                    # floodDataDictionary['wd_legend_4'] = (
                    #     self.abbreviate(legend_item4)
                    #     + '-'
                    #     + self.abbreviate(legend_item5)
                    # )
                    gdf = gdf.astype({'PARAMVALUE': 'int'})
                    floodDataDictionary['wd_legend_min'] = gdf['PARAMVALUE'].min()
                    floodDataDictionary['wd_legend_max'] = gdf['PARAMVALUE'].max()
                    self.addMap(
                        gdf,
                        title=title,
                        column='right',
                        field='PARAMVALUE',
                        formatTicks=False,
                        cmap=color_ramp,
                    )
                except Exception as e:
                    self.log_error(e)
                    print("Unexpected error:", sys.exc_info()[0])
                    pass

                ###################################
                # Flood - Add Debris
                ###################################
                # add debris
                try:
                # FinishTonsTotal,
                #  StructureTonsTotal,
                #  FoundationTonsTotal,
                # DebrisTotal
                    # populate and format values
                    # tons = self.addCommas(
                    #     results['DebrisTotal'].sum(), abbreviate=True)
                    tons = self.addCommas(
                        results['DebrisTotal'].sum(), abbreviate=True)
                    # truckLoads = self.addCommas(
                    #     results['DebrisTotal'].sum() * tonsToTruckLoadsCoef,
                    #     abbreviate=True,
                    # )
                    truckLoads = self.addCommas(
                        results['DebrisTotal'].sum() / tonsToTruckLoadsCoef,
                        abbreviate=True,
                    )
                    totalFinish = self.addCommas(
                        results['FinishTonsTotal'].sum(), abbreviate=True)
                    totalStructure = self.addCommas(
                        results['StructureTonsTotal'].sum(), abbreviate=True)
                    totalFoundation = self.addCommas(
                        results['FoundationTonsTotal'].sum() / tonsToTruckLoadsCoef,
                        abbreviate=True,
                    )

                    # populate totals
                    totalTons = tons
                    totalTruckLoads = truckLoads
                    total = totalTons + ' Tons/' + totalTruckLoads + ' Truck Loads'

                    # build data dictionary
                    # data = {
                    #     'Debris Type': ['All Debris (finishes, structure and foundation)'],
                    #     'Tons': [tons],
                    #     'Truck Loads': [truckLoads],
                    # }
                    data = {
                        'Debris Type': ['Foundation', 'Finish', 'Structure'],
                        'Tons': [totalFoundation, totalFinish, totalStructure],
                        'Truck Loads': [totalFoundation, totalFinish, totalStructure],
                    }
                    truckLoads = self.addCommas(
                        results['DebrisTotal'] / tonsToTruckLoadsCoef,
                        abbreviate=True,
                    )
                    # create DataFrame from data dictionary
                    debris = pd.DataFrame(
                        data, columns=['Debris Type', 'Tons', 'Truck Loads']
                    )
                    # floodDataDictionary['debris_type_1'] = debris['Debris Type'][0]
                    # floodDataDictionary['debris_tons_1'] = totalTons
                    floodDataDictionary['debris_type_1'] = "Finish"
                    floodDataDictionary['debris_tons_1'] = totalFinish
                    floodDataDictionary['debris_type_2'] = "Foundation"
                    floodDataDictionary['debris_tons_2'] = totalFoundation
                    floodDataDictionary['debris_type_3'] = "Structure"
                    floodDataDictionary['debris_tons_3'] = totalStructure
                    floodDataDictionary['total_debris_tons'] = totalTons
                    floodDataDictionary['total_debris_truckloads'] = totalTruckLoads
                    self.addTable(debris, 'Debris', total, 'right')
                    self.write_fillable_pdf(floodDataDictionary, path)
                except Exception as e:
                    self.log_error(e)
                    print("Unexpected error:", sys.exc_info()[0])
                    pass

            ###################################################
            # Hurricane
            ###################################################
            if hazard == 'hurricane':
                # get bulk of results
                hurDataDictionary = {}
                hurDataDictionary['title'] = self.title
                hurDataDictionary['date'] = 'Hazus Report Generated: {}'.format(
                    datetime.datetime.now().strftime('%m-%d-%Y').lstrip('0')
                )
                try:
                    results = self._Report__getResults()
                    results = results.addGeometry()
                except Exception as e:
                    self.log_error(e)
                    print("Unexpected error:", sys.exc_info()[0])
                    pass
                #######################################
                # Hurricane - Building Damage
                #######################################
                # add Building Damage by Occupancy Type
                try:
                    buildingDamageByOccupancy = (
                        self._Report__getBuildingDamageByOccupancy()
                    )
                    # create category column
                    buildingDamageByOccupancy['xCol'] = [
                        x[0:3] for x in buildingDamageByOccupancy['Occupancy']
                    ]
                    # create new columns for major and destroyed
                    buildingDamageByOccupancy['Major & Destroyed'] = (
                        buildingDamageByOccupancy['Major']
                        + buildingDamageByOccupancy['Destroyed']
                    )
                    # list columns to group for each category
                    yCols = ['Affected', 'Minor', 'Major & Destroyed']
                    buildingDamageByOccupancy = (
                        buildingDamageByOccupancy.groupby(['xCol'])[
                            'Affected', 'Minor', 'Major & Destroyed'
                        ]
                        .sum()
                        .reset_index()
                    )
                    self.addHistogram(
                        buildingDamageByOccupancy,
                        'xCol',
                        yCols,
                        'Building Damage by Occupancy Type',
                        'Building Count',
                        'left',
                    )
                except Exception as e:
                    self.log_error(e)
                    print("Unexpected error:", sys.exc_info()[0])
                    pass
                ###################################
                # Hurricane Economic Loss
                ###################################
                # add economic loss
                try:
                    counties = self.getCounties()
                    economicResults = results[['tract', 'EconLoss']]
                    economicResults['countyfips'] = economicResults.tract.str[:5]
                    economicLoss = pd.merge(
                        economicResults, counties, how="inner", on=['countyfips']
                    )
                    economicLoss.drop(
                        ['size', 'countyfips', 'tract', 'geometry', 'crs'],
                        axis=1,
                        inplace=True,
                    )
                    economicLoss.columns = ['EconLoss', 'TopCounties', 'State']
                    # populate total
                    total = self.addCommas(
                        economicLoss['EconLoss'].sum(), truncate=True, abbreviate=True
                    )
                    # limit rows to the highest values
                    economicLoss = (
                        economicLoss.groupby(['TopCounties', 'State'])[
                            'EconLoss']
                        .sum()
                        .reset_index()
                    )
                    economicLoss = economicLoss.sort_values(
                        'EconLoss', ascending=False
                    )[0:tableRowLimit]
                    # format values
                    economicLoss['EconLoss'] = [
                        self.toDollars(x, abbreviate=True)
                        for x in economicLoss['EconLoss']
                    ]
                    columns = {
                        'econloss_county_': 'TopCounties',
                        'econloss_state_': 'State',
                        'econloss_total_': 'EconLoss',
                    }
                    hurDataDictionary['econ_loss_count'] = f"({self.abbreviate(len(economicResults.index)).replace(' ', '')} Tracts with Losses)"
                    #hurDataDictionary['econ_loss_count'] = f"({self.abbreviate(len(economicResults.index)).replace(' ', '')} Tracts)"
                    self.insert_fillable_pdf(
                        economicLoss, hurDataDictionary, columns)
                    hurDataDictionary['total_econloss'] = '$' + total
                    self.addTable(
                        economicLoss, 'Total Economic Loss', total, 'left')
                except Exception as e:
                    self.log_error(e)
                    print("Unexpected error:", sys.exc_info()[0])
                    pass
                #######################################################
                # Hurricane - Damaged Essential Facilities
                #######################################################
                # add essential facilities
                try:
                    essentialFacilities = self._Report__getEssentialFacilities()
                    essentialFacilities['Major & Destroyed'] = (
                        essentialFacilities['Major'] +
                        essentialFacilities['Destroyed']
                    )
                    essentialFacilities = (
                        essentialFacilities.groupby(['FacilityType'])[
                            'Affected', 'Minor', 'Major & Destroyed'
                        ]
                        .sum()
                        .reset_index()
                    )
                    # Rename rows in FacilityType column
                    essentialFacilities['FacilityType'] = essentialFacilities['FacilityType'].replace({
                        'CareFlty' : 'Care Facilities',
                        'FireStation' : 'Fire Stations',
                        'PoliceStation' : 'Police Stations',
                        'School': 'Schools'
                    })

                    # list columns to group for each category
                    yCols = ['Affected', 'Minor', 'Major & Destroyed']
                    self.addHistogram(
                        essentialFacilities,
                        'FacilityType',
                        yCols,
                        'Damaged Essential Facilities',
                        'Total Facilities',
                        'left',
                    )
                except Exception as e:
                    self.log_error(e)
                    print("Unexpected error:", sys.exc_info()[0])
                    pass

                ###########################################################
                # Hurricane - Displaced Households & Shelter Needs
                ###########################################################
                # add displaced households and shelter needs
                try:
                    counties = self.getCounties()
                    displacedAndShelterResults = results[
                        ['tract', 'DisplacedHouseholds', 'ShelterNeeds']
                    ]
                    displacedAndShelterResults[
                        'countyfips'
                    ] = displacedAndShelterResults.tract.str[:5]
                    displacedAndShelter = pd.merge(
                        displacedAndShelterResults,
                        counties,
                        how="inner",
                        on=['countyfips'],
                    )
                    displacedAndShelter.drop(
                        ['size', 'countyfips', 'geometry', 'crs', 'tract'],
                        axis=1,
                        inplace=True,
                    )
                    displacedAndShelter.columns = [
                        'DisplacedHouseholds',
                        'ShelterNeeds',
                        'TopCounties',
                        'State',
                    ]
                    # populate totals
                    totalDisplaced = self.addCommas(
                        displacedAndShelter['DisplacedHouseholds'].sum(),
                        abbreviate=True,
                    )
                    totalShelter = self.addCommas(
                        displacedAndShelter['ShelterNeeds'].sum(), abbreviate=True
                    )
                    total = (
                        totalDisplaced
                        + ' Displaced/'
                        + totalShelter
                        + ' Needing Shelter'
                    )
                    # limit rows to the highest values
                    displacedAndShelter = (
                        displacedAndShelter.groupby(['TopCounties', 'State'])[
                            'DisplacedHouseholds', 'ShelterNeeds'
                        ]
                        .sum()
                        .reset_index()
                    )
                    displacedAndShelter = displacedAndShelter.sort_values(
                        'DisplacedHouseholds', ascending=False
                    )[0:tableRowLimit]
                    # format values
                    for column in displacedAndShelter:
                        if column != 'TopCounties':
                            displacedAndShelter[column] = [
                                self.addCommas(x, abbreviate=True)
                                for x in displacedAndShelter[column]
                            ]
                    columns = {
                        'shelter_county_': 'TopCounties',
                        'shelter_state_': 'State',
                        'shelter_house_': 'DisplacedHouseholds',
                        'shelter_need_': 'ShelterNeeds',
                    }
                    self.insert_fillable_pdf(
                        displacedAndShelter, hurDataDictionary, columns
                    )
                    hurDataDictionary['total_displaced']    = totalDisplaced
                    hurDataDictionary['total_need_shelter'] = totalShelter
                    self.addTable(
                        displacedAndShelter,
                        'Displaced Households and Short-Term Shelter Needs',
                        total,
                        'left',
                    )
                except Exception as e:
                    self.log_error(e)
                    print("Unexpected error:", sys.exc_info()[0])
                    pass

                ########################################
                # Hurricane - Economic Loss Map
                ########################################
                # add economic loss map
                try:
                    economicLoss = results[['tract', 'EconLoss', 'geometry']]
                    breaks = nb(results['EconLoss'], nb_class=4)
                    legend_item1 = breaks[0]
                    legend_item2 = breaks[1]
                    legend_item3 = breaks[2]
                    legend_item4 = breaks[3]
                    legend_item5 = breaks[4]
                    hurDataDictionary['legend_1'] = (
                        '$'
                        + self.abbreviate(legend_item1)
                        + '-'
                        + self.abbreviate(legend_item2)
                    )
                    hurDataDictionary['legend_2'] = (
                        '$'
                        + self.abbreviate(legend_item2)
                        + '-'
                        + self.abbreviate(legend_item3)
                    )
                    hurDataDictionary['legend_3'] = (
                        '$'
                        + self.abbreviate(legend_item3)
                        + '-'
                        + self.abbreviate(legend_item4)
                    )
                    hurDataDictionary['legend_4'] = (
                        '$'
                        + self.abbreviate(legend_item4)
                        + '-'
                        + self.abbreviate(legend_item5)
                    )
                    # convert to GeoDataFrame
                    economicLoss.geometry = economicLoss.geometry.apply(loads)
                    gdf = gpd.GeoDataFrame(economicLoss)
                    map_colors = ['#fabfa1', '#f3694c', '#d62128', '#6b0d0d']
                    color_ramp = LinearSegmentedColormap.from_list(
                        'color_list', [
                            Color(color).rgb for color in map_colors]
                    )
                    self.addMap(
                        gdf,
                        title='Economic Loss by Census Tract (USD)',
                        column='right',
                        field='EconLoss',
                        cmap=color_ramp,
                        scheme='NaturalBreaks',
                        k=4
                    )
                except Exception as e:
                    self.log_error(e)
                    print("Unexpected error:", sys.exc_info()[0])
                    pass

                ###################################
                # Hurricane - Wind Speed Map
                ###################################
                # add Wind Speed Map
                try:
                    gdf = self._Report__getHazardGeoDataFrame()
                    title = 'Historic Wind Speeds (mph)'
                    
                    # TODO: Verify if we want a static or dynamic legend - BC
                    max_wind = gdf['PARAMVALUE'].max()

                    map_colors = ['#4575b4', '#91bfdb', '#e0f3f8', '#fee090', '#fc8d59', '#d73027']
                    bins = [
                        75,
                        98,
                        122,
                        145,
                        169
                    ]
                    if max_wind < 122:
                        map_colors = map_colors[0:3]
                        bins = [
                            75,
                            98
                        ]
                        bins = bins[0:2]
                    elif max_wind < 145:
                        map_colors = map_colors[0:4]
                        bins = bins[0:3]

                #     legend_item1 = 50
                #     legend_item2 = bins[0]
                #     legend_item3 = bins[1]
                #     legend_item4 = bins[2]
                #     legend_item5 = bins[3]
                #     legend_item6 = bins[4]
                #     legend_item7 = "169+"

                #     hurDataDictionary['peak_gust_legend_1'] = (
                #         self.abbreviate(legend_item1)
                #         + '-'
                #         + self.abbreviate(legend_item2)
                #     )
                #     hurDataDictionary['peak_gust_legend_2'] = (
                #         self.abbreviate(legend_item2)
                #         + '-'
                #         + self.abbreviate(legend_item3)
                #     )
                #     hurDataDictionary['peak_gust_legend_3'] = (
                #         self.abbreviate(legend_item3)
                #         + '-'
                #         + self.abbreviate(legend_item4)
                #     )
                #     hurDataDictionary['peak_gust_legend_4'] = (
                #         self.abbreviate(legend_item4)
                #         + '-'
                #         + self.abbreviate(legend_item5)
                #     )
                #     hurDataDictionary['peak_gust_legend_5'] = (
                #         self.abbreviate(legend_item5)
                #         + '-'
                #         + self.abbreviate(legend_item6)
                #     )
                #     hurDataDictionary['peak_gust_legend_6'] = (
                #          self.abbreviate(legend_item7)
                #    )
                    color_ramp = LinearSegmentedColormap.from_list(
                        'color_list', [
                            Color(color).rgb for color in map_colors]
                    )
                    #bins = [round(bin) for bin in breaks]
                    classification_kwds = {'bins': bins}
                    self.addMap(
                        gdf,
                        title=title,
                        column='right',
                        field='PARAMVALUE',
                        formatTicks=False,
                        cmap=color_ramp,
                        scheme='UserDefined',
                        classification_kwds=classification_kwds
                    )
                except Exception as e:
                    self.log_error(e)
                    print("Unexpected error:", sys.exc_info()[0])
                    pass
                ###################################
                # Hurricane - Add Debris
                ###################################
                # add debris
                try:
                    # populate and format values
                    bwTons = self.addCommas(
                        results['DebrisBW'].sum(), abbreviate=True)
                    csTons = self.addCommas(
                        results['DebrisCS'].sum(), abbreviate=True)
                    treeTons = self.addCommas(
                        results['DebrisTree'].sum(), abbreviate=True
                    )
                    eligibleTreeTons = self.addCommas(
                        results['DebrisEligibleTree'].sum(), abbreviate=True
                    )
                    bwTruckLoads = self.addCommas(
                        results['DebrisBW'].sum() / tonsToTruckLoadsCoef,
                        abbreviate=True,
                    )
                    csTruckLoads = self.addCommas(
                        results['DebrisCS'].sum() / tonsToTruckLoadsCoef,
                        abbreviate=True,
                    )
                    treeTruckLoads = self.addCommas(
                        results['DebrisTree'].sum() / tonsToTruckLoadsCoef,
                        abbreviate=True,
                    )
                    eligibleTreeTruckLoads = self.addCommas(
                        results['DebrisEligibleTree'].sum() /
                        tonsToTruckLoadsCoef,
                        abbreviate=True,
                    )
                    # populate totals
                    totalTons = self.addCommas(
                        results['DebrisTotal'].sum(), abbreviate=True
                    )
                    totalTruckLoads = self.addCommas(
                        results['DebrisTotal'].sum() / tonsToTruckLoadsCoef,
                        abbreviate=True,
                    )
                    total = totalTons + ' Tons/' + totalTruckLoads + ' Truck Loads'
                    # build data dictionary
                    data = {
                        'Debris Type': [
                            'Brick, Wood, and Other',
                            'Concrete & Steel',
                            'Tree',
                            'Eligible Tree',
                        ],
                        'Tons': [bwTons, csTons, treeTons, eligibleTreeTons],
                        'Truck Loads': [
                            bwTruckLoads,
                            csTruckLoads,
                            treeTruckLoads,
                            eligibleTreeTruckLoads,
                        ],
                    }
                    # create DataFrame from data dictionary
                    debris = pd.DataFrame(
                        data, columns=['Debris Type', 'Tons', 'Truck Loads']
                    )
                    hurDataDictionary['debris_type_1'] = debris['Debris Type'][0]
                    hurDataDictionary['debris_tons_1'] = debris['Tons'][0]
                    hurDataDictionary['debris_type_2'] = debris['Debris Type'][1]
                    hurDataDictionary['debris_tons_2'] = debris['Tons'][1]
                    hurDataDictionary['debris_type_3'] = debris['Debris Type'][2]
                    hurDataDictionary['debris_tons_3'] = debris['Tons'][2]
                    hurDataDictionary['debris_type_4'] = debris['Debris Type'][3]
                    hurDataDictionary['debris_tons_4'] = debris['Tons'][3]
                    hurDataDictionary['total_debris_tons'] = totalTons
                    hurDataDictionary['total_debris_truckloads'] = totalTruckLoads
                    self.addTable(debris, 'Debris', total, 'right')
                    self.write_fillable_pdf(hurDataDictionary, path)
                except Exception as e:
                    self.log_error(e)
                    print("Unexpected error:", sys.exc_info()[0])
                    pass

            ###################################################
            # Tsunami
            ###################################################
            if hazard == 'tsunami':
                tsDataDictionary = {}
                tsDataDictionary['title'] = self.title
                tsDataDictionary['date'] = 'Hazus Report Generated: {}'.format(
                    datetime.datetime.now().strftime('%m-%d-%Y').lstrip('0')
                )
                # get bulk of results
                try:
                    results = self._Report__getResults()
                    results = results.addGeometry()
                except Exception as e:
                    self.log_error(e)
                    print("Unexpected error:", sys.exc_info()[0])
                    pass

                # add Building Damage by Occupancy Type
                try:
                    buildingDamageByOccupancy = (
                        self._Report__getBuildingDamageByOccupancy()
                    )
                    # create category column
                    buildingDamageByOccupancy['xCol'] = [
                        x[0:3] for x in buildingDamageByOccupancy['Occupancy']
                    ]
                    # create new columns for major and destroyed
                    buildingDamageByOccupancy['Major & Destroyed'] = (
                        buildingDamageByOccupancy['Major']
                        + buildingDamageByOccupancy['Destroyed']
                    )
                    # list columns to group for each category
                    yCols = ['Affected', 'Minor', 'Major & Destroyed']
                    buildingDamageByOccupancy = (
                        buildingDamageByOccupancy.groupby(['xCol'])[
                            'Affected', 'Minor', 'Major & Destroyed'
                        ]
                        .sum()
                        .reset_index()
                    )
                    self.addHistogram(
                        buildingDamageByOccupancy,
                        'xCol',
                        yCols,
                        'Building Damage by Occupancy Type',
                        'Building Count',
                        'left',
                    )
                except Exception as e:
                    self.log_error(e)
                    print("Unexpected error:", sys.exc_info()[0])
                    pass

                ###################################
                # Tsunami Economic Loss
                ###################################
                # add economic loss
                try:
                    counties = self.getCounties()
                    economicResults = results[['block', 'EconLoss']]
                    economicResults['countyfips'] = economicResults.block.str[:5]
                    economicLoss = pd.merge(
                        economicResults, counties, how="inner", on=['countyfips']
                    )
                    economicLoss.drop(
                        ['size', 'countyfips', 'geometry', 'crs'],
                        axis=1,
                        inplace=True,
                    )
                    economicLoss.columns = ['Block', 'EconLoss', 'CountyName', 'State']
                    economicLoss = (
                        economicLoss.groupby(['Block', 'CountyName', 'State'])['EconLoss']
                        .sum()
                        .reset_index()
                    )
                    # populate total
                    total = self.addCommas(
                        economicLoss['EconLoss'].sum(), truncate=True, abbreviate=True
                    )
                    # limit rows to the highest values
                    economicLoss = economicLoss.sort_values(
                        'EconLoss', ascending=False
                    )[0:tableRowLimit]
                    # format values
                    economicLoss['EconLoss'] = [
                        self.toDollars(x, abbreviate=True, truncate=True)
                        for x in economicLoss['EconLoss']
                    ]
                    columns = {
                        'econloss_block_': 'Block',
                        'econloss_county_': 'CountyName',
                        'econloss_state_': 'State',
                        'econloss_total_': 'EconLoss',
                    }
                    tsDataDictionary['econ_loss_count'] = f"({self.abbreviate(len(economicResults.index)).replace(' ', '')} Blocks with Losses)"
                    self.insert_fillable_pdf(
                        economicLoss, tsDataDictionary, columns)
                    tsDataDictionary['total_econloss'] = '$' + str(total)
                    #  'total_econloss': total - Add to table
                    self.addTable(
                        economicLoss, 'Total Economic Loss', total, 'left')
                except Exception as e:
                    self.log_error(e)
                    print("Unexpected error:", sys.exc_info()[0])
                    pass
                ####################################################
                # Tsunami - Injuries and Fatalities
                ####################################################
                # add injuries and fatatilies
                try:
                    counties = self.getCounties()
                    injuries = self._Report__getInjuries()
                    fatalities = self._Report__getFatalities()
                    injuriesAndFatatiliesResults = injuries.merge(
                        fatalities, on='block', how='outer'
                    )
                    injuriesAndFatatiliesResults = self._Report__getFatalities()
                    injuriesAndFatatiliesResults[
                        'countyfips'
                    ] = injuriesAndFatatiliesResults.block.str[:5]
                    injuriesAndFatatilies = pd.merge(
                        injuriesAndFatatiliesResults,
                        counties,
                        how="inner",
                        on=['countyfips'],
                    )
                    injuriesAndFatatilies.drop(
                        ['size', 'countyfips', 'geometry', 'crs', 'name'],
                        axis=1,
                        inplace=True,
                    )
                    # TODO: ReOrder to "Good; Fair; Poor"
                    injuriesAndFatatilies['Injuries Day'] = (
                       # results['Injuries_DayFair']
                        #+ 
                        results['Injuries_DayGood']
                        #+ results['Injuries_DayPoor']
                    )
                    injuriesAndFatatilies['InjuriesNight'] = (
                       # results['Injuries_NightFair']
                    #+
                         results['Injuries_NightGood']
                       # + results['Injuries_NightPoor']
                    )
                    injuriesAndFatatilies['Fatalities Day'] = (
                      #  results['Fatalities_DayPoor']
                     #   +
                         results['Fatalities_DayGood']
                     #   + results['Fatalities_DayFair']
                    )
                    injuriesAndFatatilies['Fatalities Night'] = (
                     #   results['Fatalities_NightPoor']
                        #+ 
                        results['Fatalities_NightGood']
                     #   + results['Fatalities_NightFair']
                    )
                    injuriesAndFatatilies.drop(
                        [
                            'Fatalities_DayFair',
                            'Fatalities_DayGood',
                            'Fatalities_DayPoor',
                            'Fatalities_NightFair',
                            'Fatalities_NightGood',
                            'Fatalities_NightPoor',
                        ],
                        axis=1,
                        inplace=True,
                    )
                    injuriesAndFatatilies.columns = [
                        'Block',
                        'State',
                        'InjuriesDay',
                        'InjuriesNight',
                        'FatalitiesDay',
                        'FatalitiesNight',
                    ]
                    # populate totals
                    totalDay = (
                        self.addCommas(
                            (
                                injuriesAndFatatilies['InjuriesDay']
                                + injuriesAndFatatilies['FatalitiesDay']
                            ).sum(),
                            abbreviate=True,
                        )
                      #  + ' Day'
                    )
                    totalNight = (
                        self.addCommas(
                            (
                                injuriesAndFatatilies['InjuriesNight']
                                + injuriesAndFatatilies['FatalitiesNight']
                            ).sum(),
                            abbreviate=True,
                        )
                      #  + ' Night'
                    )
                    total = totalDay + '/' + totalNight
                    # limit rows to the highest values
                    injuriesAndFatatilies = (
                        injuriesAndFatatilies.groupby(['Block', 'State'])[
                            'InjuriesDay',
                            'InjuriesNight',
                            'FatalitiesDay',
                            'FatalitiesNight',
                        ]
                        .sum()
                        .reset_index()
                    )
                    injuriesAndFatatilies = injuriesAndFatatilies.sort_values(
                        'InjuriesDay', ascending=False
                    )[0:tableRowLimit]
                    # format values
                    for column in injuriesAndFatatilies:
                        if column not in ['Block', 'State']:
                            injuriesAndFatatilies[column] = [
                                self.addCommas(x, abbreviate=True)
                                for x in injuriesAndFatatilies[column]
                            ]
                    columns = {
                        'nonfatal_county_': 'Block',
                        'nonfatal_state_': 'State',
                        'nonfatal_pop_': ['InjuriesDay', 'InjuriesNight'],
                        'nonfatal_injuries_': ['FatalitiesDay', 'FatalitiesNight'],
                    }
                    self.insert_fillable_pdf(
                        injuriesAndFatatilies, tsDataDictionary, columns
                    )
                    total = totalDay + '/' + totalNight
                    tsDataDictionary['total_day'] = totalDay
                    tsDataDictionary['total_night'] = totalNight
                    # TODO: Remove this - BC
                    #tsDataDictionary['total_injuries'] = total
                    self.addTable(
                        injuriesAndFatatilies, 'Injuries and Fatatilies', total, 'left'
                    )
                except Exception as e:
                    self.log_error(e)
                    print("Unexpected error:", sys.exc_info()[0])
                    pass

                ###################################
                # Tsunami - Economic Loss Map
                ###################################
                # add economic loss map
                try:
                    economicLoss = results[['block', 'EconLoss', 'geometry']]
                    # convert to GeoDataFrame
                    economicLoss = economicLoss[economicLoss['EconLoss'] > 1]

                    # TODO: Review breaks style - BC
                    # breaks = self.equal_interval(
                    #     economicLoss['EconLoss'].to_list(), 4)

                    breaks = nb(economicLoss['EconLoss'].to_list(), nb_class=4)

                    legend_item1 = breaks[0]
                    legend_item2 = breaks[1]
                    legend_item3 = breaks[2]
                    legend_item4 = breaks[3]
                    legend_item5 = breaks[4]
                    tsDataDictionary['legend_1'] = (
                        '$'
                        + self.abbreviate(legend_item1)
                        + '-'
                        + self.abbreviate(legend_item2)
                    )
                    tsDataDictionary['legend_2'] = (
                        '$'
                        + self.abbreviate(legend_item2)
                        + '-'
                        + self.abbreviate(legend_item3)
                    )
                    tsDataDictionary['legend_3'] = (
                        '$'
                        + self.abbreviate(legend_item3)
                        + '-'
                        + self.abbreviate(legend_item4)
                    )
                    tsDataDictionary['legend_4'] = (
                        '$'
                        + self.abbreviate(legend_item4)
                        + '-'
                        + self.abbreviate(legend_item5)
                    )
                    economicLoss.geometry = economicLoss.geometry.apply(loads)
                    gdf = gpd.GeoDataFrame(economicLoss)
                    map_colors = ['#fabfa1', '#f3694c', '#d62128', '#6b0d0d']
                    color_ramp = LinearSegmentedColormap.from_list(
                        'color_list', [
                            Color(color).rgb for color in map_colors]
                    )
                    self.addMap(
                        gdf,
                        title='Economic Loss by Census Block (USD)',
                        column='right',
                        field='EconLoss',
                        cmap=color_ramp,
                        scheme='NaturalBreaks',
                        k=4
                    )
                except Exception as e:
                    self.log_error(e)
                    print("Unexpected error:", sys.exc_info()[0])
                    pass

                ###################################
                # Tsunami - Hazard Map
                ###################################
                # add hazard map
                try:
                    gdf = self._Report__getHazardGeoDataFrame()
                    title = gdf.title
                    gdf = gdf[gdf['PARAMVALUE'] > 0.1]
                    gdf = gdf.astype({'PARAMVALUE': 'int'})
                    #map_colors = ['#e2edff', '#92c4de', '#3282be', '#083572']
                    map_colors = ['#00FFFF', '#55AAFF', '#AA55FF', '#FF00FF']
                    color_ramp = LinearSegmentedColormap.from_list(
                        'color_list', [
                            Color(color).rgb for color in map_colors]
                    )
                    tsDataDictionary['wd_legend_min'] = gdf['PARAMVALUE'].min()
                    tsDataDictionary['wd_legend_max'] = gdf['PARAMVALUE'].max()
                    self.addMap(
                        gdf,
                        title='Water Depth (ft)',
                        column='right',
                        field='PARAMVALUE',
                        formatTicks=False,
                        cmap=color_ramp,
                        boundary=False
                    )
                except Exception as e:
                    self.log_error(e)
                    print("Unexpected error:", sys.exc_info()[0])
                    pass

                #################################################
                # Tsunami - Travel Time to Safety Map
                #################################################
                # add travel time to safety map
                try:
                    travelTimeToSafety = self._Report__getTravelTimeToSafety()
                    title = 'Travel Time to Safety (minutes)'
                    #bins = [15, 30, 45, 60, 75, 90, 105, 1000]
                    #scheme = 'userdefined'
                    map_colors = [
                        '#f5e76b',
                        '#eacd60',
                        '#ddb155',
                        '#d2964a',
                        '#c77b3e',
                        '#bc6033',
                        '#b3492a',
                        '#b52a2d',
                    ]
                    color_ramp = LinearSegmentedColormap.from_list(
                        'color_list', [
                            Color(color).rgb for color in map_colors]
                    )

                    breaks = nb(travelTimeToSafety['travelTimeOver65yo'], nb_class=8)
                    tt_legend_0 = breaks[0]
                    tt_legend_1 = breaks[1]
                    tt_legend_2 = breaks[2]
                    tt_legend_3 = breaks[3]
                    tt_legend_4 = breaks[4]
                    tt_legend_5 = breaks[5]
                    tt_legend_6 = breaks[6]
                    tt_legend_7 = breaks[7]
                    tt_legend_8 = breaks[8]
                    tsDataDictionary['tt_legend_0'] = (
                        self.abbreviate(tt_legend_0)
                        + '-'
                        + self.abbreviate(tt_legend_1)
                    )
                    tsDataDictionary['tt_legend_1'] = (
                        self.abbreviate(tt_legend_1)
                        + '-'
                        + self.abbreviate(tt_legend_2)
                    )
                    tsDataDictionary['tt_legend_2'] = (
                        self.abbreviate(tt_legend_2)
                        + '-'
                        + self.abbreviate(tt_legend_3)
                    )
                    tsDataDictionary['tt_legend_3'] = (
                        self.abbreviate(tt_legend_3)
                        + '-'
                        + self.abbreviate(tt_legend_4)
                    )
                    tsDataDictionary['tt_legend_4'] = (
                        self.abbreviate(tt_legend_4)
                        + '-'
                        + self.abbreviate(tt_legend_5)
                    )
                    tsDataDictionary['tt_legend_5'] = (
                        self.abbreviate(tt_legend_5)
                        + '-'
                        + self.abbreviate(tt_legend_6)
                    )
                    tsDataDictionary['tt_legend_6'] = (
                        self.abbreviate(tt_legend_6)
                        + '-'
                        + self.abbreviate(tt_legend_7)
                    )
                    tsDataDictionary['tt_legend_7'] = (
                        self.abbreviate(tt_legend_7)
                        + '-'
                        + self.abbreviate(tt_legend_8)
                    )
                    bins = [round(bin) for bin in breaks[1:8]]
                    classification_kwds = {'bins': bins}
                    self.addMap(
                        travelTimeToSafety,
                        title=title,
                        column='right',
                        field='travelTimeOver65yo',
                        formatTicks=False,
                        cmap=color_ramp,
                        scheme='UserDefined',
                        classification_kwds=classification_kwds,
                        #norm=Normalize(0, len(bins))
                    )
                except Exception as e:
                    self.log_error(e)
                    print("Unexpected error:", sys.exc_info()[0])
                    pass
                self.write_fillable_pdf(tsDataDictionary, path)
        except Exception as e:
            self.log_error(e)
            print("Unexpected error:", sys.exc_info()[0])
            raise

    def equal_interval(self, values, classes=5):
        """
        Equal interval algorithm in Python

        Returns breaks based on dividing the range of 'values' into 'classes' parts.
        """
        _min = min(values)
        _max = max(values)
        unit = (_max - _min) / classes
        res = [_min + k * unit for k in range(classes + 1)]
        return res

    def log_error(self, e):
        print('\n')
        print(e)
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        print(fname)
        print(exc_type, exc_tb.tb_lineno)
        print('\n')