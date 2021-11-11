import ctypes
import json
import os
import sys
import tkinter as tk
from time import time
from tkinter import (BOTTOM, LEFT, RIGHT, TOP, Canvas, E, Label, N, OptionMenu,
                     PhotoImage, S, StringVar, W, filedialog, messagebox, ttk)
from tkinter.ttk import Progressbar

from PIL import Image, ImageTk

from draftemail import draftEmail
from hazusdb import HazusDB
from studyregion import StudyRegion


class App:
    def __init__(self):
        """tkinter application that uses HazPy to export Hazus results"""
        # Create app
        self.root = tk.Tk()

        # load config
        self.config = json.loads(open('src/config.json').read())

        # global styles
        self.globalStyles = self.config['themes'][self.config['activeTheme']]
        self.backgroundColor = self.globalStyles['backgroundColor']
        self.foregroundColor = self.globalStyles['foregroundColor']
        self.hoverColor = self.globalStyles['hoverColor']
        self.fontColor = self.globalStyles['fontColor']
        self.textEntryColor = self.globalStyles['textEntryColor']
        self.starColor = self.globalStyles['starColor']
        self.padl = 15
        # tk styles
        self.textBorderColor = self.globalStyles['textBorderColor']
        self.textHighlightColor = self.globalStyles['textHighlightColor']

        # ttk styles classes
        self.style = ttk.Style()
        self.style.configure(
            "BW.TCheckbutton",
            foreground=self.fontColor,
            background=self.backgroundColor,
            bordercolor=self.backgroundColor,
            side='LEFT',
        )
        self.style.configure(
            'TCombobox',
            background=self.backgroundColor,
            bordercolor=self.backgroundColor,
            relief='flat',
            lightcolor=self.backgroundColor,
            darkcolor=self.backgroundColor,
            borderwidth=4,
            foreground=self.foregroundColor,
        )

        # App parameters
        self.root.title('Export Tool')
        self.root.configure(background=self.backgroundColor, highlightcolor='#fff')

        # App images
        self.root.wm_iconbitmap('Python_env/assets/images/Hazus.ico')
        self.img_data = ImageTk.PhotoImage(
            Image.open("Python_env/assets/images/data_blue.png").resize(
                (20, 20), Image.BICUBIC
            )
        )
        self.img_edit = ImageTk.PhotoImage(
            Image.open("Python_env/assets/images/edit_blue.png").resize(
                (20, 20), Image.BICUBIC
            )
        )
        self.img_folder = ImageTk.PhotoImage(
            Image.open("Python_env/assets/images/folder_icon.png").resize(
                (20, 20), Image.BICUBIC
            )
        )

        # Init dynamic row
        self.row = 0

    def updateProgressBar(self, value, message):
        """Updates the progress bar text and position when processing"""
        self.label_progress.config(text=message)
        self.root.update_idletasks()
        self.bar_progress['value'] = value

    def browsefunc(self):
        """Opens a file explorer window and sets the ouputDirectory as the selection"""
        self.outputDirectory = filedialog.askdirectory()
        self.outputDirectory = self.outputDirectory.replace('\n', '')
        self.text_outputDirectory.delete("1.0", 'end-1c')
        if len(self.dropdown_studyRegion.get()) > 0:
            self.text_outputDirectory.insert(
                "1.0", self.outputDirectory + '/' + self.dropdown_studyRegion.get()
            )
            self.root.update_idletasks()
        else:
            self.text_outputDirectory.insert("1.0", self.outputDirectory)
            self.root.update_idletasks()

    def focus_next_widget(self, event):
        """makes the interface focus on the next widget"""
        event.widget.tk_focusNext().focus()
        return "break"

    def focus_previous_widget(self, event):
        """makes the interface focus on the previous widget"""
        event.widget.tk_focusPrev().focus()
        return "break"

    # TODO update hover actions
    def on_enter_dir(self, e):
        self.button_outputDir['background'] = self.hoverColor

    def on_leave_dir(self, e):
        self.button_outputDir['background'] = self.backgroundColor

    def on_enter_run(self, e):
        self.button_run['background'] = '#006b96'

    def on_leave_run(self, e):
        self.button_run['background'] = '#0078a9'

    def run(self):
        """runs the export with all the user parameters selected"""
        try:
            # init time
            t0 = time()

            # make sure all options are selected and get all info
            if not self.validateRequiredFields():
                ctypes.windll.user32.MessageBoxW(
                    None,
                    u"Please select these required fields prior to exporting: {e}".format(
                        e=self.selection_errors
                    ),
                    u'HazPy - Message',
                    0,
                )
                return None

            # (extra) draft email if the checkbox is selected
            try:
                if 'opt_draftEmail' in dir(self) and self.studyRegion.hazard.lower() == 'hurricane':
                    if self.exportOptions['draftEmail']:
                        draftEmail(self.studyRegion)
                    # return if only draftEmail is checked
                    if (
                        self.exportOptions['csv']
                        + self.exportOptions['shapefile']
                        + self.exportOptions['geojson']
                        + self.exportOptions['report']
                        == 0
                    ):
                        tk.messagebox.showinfo(
                            "HazPy",
                            "Complete - Draft email can be found in the draft folder of Outlook",
                        )
                        return
            except Exception as e:
                print('Unable to draft email')
                print(e)

            # add progress bar
            self.addWidget_progress()

            # calculate progress bar increments
            exportOptionsCount = 0
            if self.exportOptions['csv']:
                exportOptionsCount += 4
            if self.exportOptions['shapefile']:
                exportOptionsCount += 3
            if self.exportOptions['geojson']:
                exportOptionsCount += 3
            if self.exportOptions['report']:
                exportOptionsCount += 2
            # if self.exportOptions['draftEmail']:
            #     exportOptionsCount += 1
            progressIncrement = 100 / exportOptionsCount
            progressValue = 0

            # create a directory for the output files
            outputPath = self.text_outputDirectory.get("1.0", 'end')
            outputPath = outputPath.replace('\n', '')
            if not os.path.exists(outputPath):
                os.mkdir(outputPath)

            # get bulk of results
            try:
                progressValue = progressValue + progressIncrement
                msg = 'Retrieving base results'
                self.updateProgressBar(progressValue, msg)
                results = self.studyRegion.getResults()
                essentialFacilities = self.studyRegion.getEssentialFacilities()

                # check if the study region contains result data
                if len(results) < 1:
                    tk.messagebox.showwarning(
                        'HazPy',
                        'No results found. Please check your study region and try again.',
                    )
            except:
                ctypes.windll.user32.MessageBoxW(
                    None,
                    u"Unexpected error retrieving base results: "
                    + str(sys.exc_info()[0]),
                    u'HazPy - Message',
                    0,
                )

            # export study region to csv if the checkbox is selected
            if self.exportOptions['csv']:
                try:
                    progressValue = progressValue + progressIncrement
                    self.updateProgressBar(progressValue, 'Writing results to CSV')
                    if results is not None:
                        try:
                            results.toCSV(outputPath + '/results.csv')
                        except:
                            print('Base results not available to export.')
                    try:
                        progressValue = progressValue + progressIncrement
                        self.updateProgressBar(
                            progressValue, 'Writing building damage by occupancy to CSV'
                            )
                        buildingDamageByOccupancy = (
                            self.studyRegion.getBuildingDamageByOccupancy()
                        )
                        if buildingDamageByOccupancy is not None:
                            buildingDamageByOccupancy.toCSV(
                                outputPath + '/building_damage_by_occupancy.csv'
                            )
                    except:
                        print('Building damage by occupancy not available to export.')
                    try:
                        progressValue = progressValue + progressIncrement
                        self.updateProgressBar(
                            progressValue, 'Writing building damage by type to CSV'
                            )
                        buildingDamageByType = (
                            self.studyRegion.getBuildingDamageByType()
                            )
                        if buildingDamageByType is not None:
                            buildingDamageByType.toCSV(
                                outputPath + '/building_damage_by_type.csv'
                            )
                    except:
                        print('Building damage by type not available to export.')
                    try:
                        progressValue = progressValue + progressIncrement
                        self.updateProgressBar(
                            progressValue, 'Writing damaged facilities to CSV'
                        )
                        if essentialFacilities is not None:
                            essentialFacilities.toCSV(
                                outputPath + '/damaged_facilities.csv'
                        )
                    except Exception as e:
                        print(e)
                except:
                    ctypes.windll.user32.MessageBoxW(
                        None,
                        u"Unexpected error exporting CSVs: " + str(sys.exc_info()[0]),
                        u'HazPy - Message',
                        0,
                    )

            # export study region to Shapefile if the checkbox is selected
            if self.exportOptions['shapefile']:
                try:
                    progressValue = progressValue + progressIncrement
                    self.updateProgressBar(
                        progressValue, 'Writing results to Shapefile'
                    )
                    if results is not None:
                        try:
                            results.toShapefile(outputPath + '/results.shp')
                        except:
                            print('Base results not available to export.')
                    try:
                        progressValue = progressValue + progressIncrement
                        if essentialFacilities is not None:
                            self.updateProgressBar(
                                progressValue, 'Writing damaged facilities to Shapefile'
                            )
                            essentialFacilities.toShapefile(
                                outputPath + '/damaged_facilities.shp'
                            )
                    except Exception as e:
                        print(e)
                    try:
                        progressValue = progressValue + progressIncrement
                        self.updateProgressBar(
                            progressValue, 'Writing hazard to Shapefile'
                        )
                        if not 'hazard' in dir():
                            hazard = self.studyRegion.getHazardGeoDataFrame()
                        if hazard is not None:
                            hazard.toShapefile(outputPath + '/hazard.shp')
                    except:
                        print('Hazard not available to export.')
                except:
                    ctypes.windll.user32.MessageBoxW(
                        None,
                        u"Unexpected error exporting Shapefile: "
                        + str(sys.exc_info()[0]),
                        u'HazPy - Message',
                        0,
                    )

            # export study region to GeoJSON if the checkbox is selected
            if self.exportOptions['geojson']:
                try:
                    progressValue = progressValue + progressIncrement
                    msg = 'Writing results to GeoJSON'
                    self.updateProgressBar(progressValue, msg)
                    if results is not None:
                        try:
                            results.toGeoJSON(outputPath + '/results.geojson')
                        except:
                            print('Base results not available to export.')
                    try:
                        progressValue = progressValue + progressIncrement
                        self.updateProgressBar(
                            progressValue, 'Writing damaged facilities to GeoJSON'
                        )
                        if essentialFacilities is not None:
                            essentialFacilities.toGeoJSON(
                                outputPath + '/damaged_facilities.geojson'
                            )
                    except Exception as e:
                        print(e)
                    try:
                        progressValue = progressValue + progressIncrement
                        self.updateProgressBar(
                            progressValue, 'Writing hazard to GeoJSON'
                        )
                        if not 'hazard' in dir():
                            hazard = self.studyRegion.getHazardGeoDataFrame()
                        if hazard is not None:
                            hazard.toGeoJSON(outputPath + '/hazard.geojson')
                    except:
                        print('Hazard not available to export.')
                except:
                    ctypes.windll.user32.MessageBoxW(
                        None,
                        u"Unexpected error exporting GeoJSON: "
                        + str(sys.exc_info()[0]),
                        u'HazPy - Message',
                        0,
                    )

            # export study region to pdf if the checkbox is selected
            if self.exportOptions['report']:
                try:
                    progressValue = progressValue + progressIncrement
                    msg = 'Writing results to PDF (exchanging patience for maps)'
                    self.updateProgressBar(progressValue, msg)
                    reportTitle = self.text_reportTitle.get("1.0", 'end-1c')
                    if len(reportTitle) > 0:
                        self.studyRegion.report.title = reportTitle
                    reportSubtitle = self.text_reportSubtitle.get("1.0", 'end-1c')
                    if len(reportSubtitle) > 0:
                        self.studyRegion.report.subtitle = reportSubtitle
                    self.studyRegion.report.save(
                        outputPath + '/report_summary.pdf', premade=''
                    )
                except:
                    ctypes.windll.user32.MessageBoxW(
                        None,
                        u"Unexpected error exporting the PDF: "
                        + str(sys.exc_info()[0]),
                        u'HazPy - Message',
                        0,
                    )

            # show export is complete
            self.updateProgressBar(100, 'Complete')
            print('Results available at: ' + outputPath)
            print('Total elapsed time: ' + str(time() - t0))
            tk.messagebox.showinfo(
                "HazPy", "Complete - Output files can be found at: " + outputPath
            )
            self.removeWidget_progress()

        except Exception as e:
            print(e)
            # if the export fails
            if 'bar_progress' in dir(self):
                self.removeWidget_progress()
            ctypes.windll.user32.MessageBoxW(
                None,
                u"Unexpected export error: " + str(sys.exc_info()[0]),
                u'HazPy - Message',
                0,
            )

    def validateRequiredFields(self):
        """checks that the user has completed all required fields"""
        try:
            # create a list to store error strings - this will prompt the user to complete every error found
            self.selection_errors = []
            # defaults all fields validated to true
            validated = True

            # validate dropdown menus
            # validates that a study region is selected
            if self.dropdown_studyRegion.winfo_ismapped():
                value = self.dropdown_studyRegion.get()
                if len(value) > 0:
                    self.studyRegion = StudyRegion(studyRegion=str(value))
                else:
                    self.selection_errors.append('Study Region')
                    validated = False

            # validates that a scenario is selected or auto-assigned
            if (
                'dropdown_scenario' in dir(self)
                and self.dropdown_scenario.winfo_ismapped()
            ):
                if self.value_scenario.get() is None:
                    value = self.dropdown_scenario.get()
                    if len(value) > 0:
                        self.studyRegion.setScenario(value)
                    # elif self.value_scenario.get() is not None:
                    #     value = self.value_scenario.get()
                    else:
                        self.selection_errors.append('Scenario')
                        validated = False
                else:
                    self.studyRegion.scenario = self.value_scenario.get()
            else:
                if len(self.options_scenario) == 1:
                    self.studyRegion.scenario = self.options_scenario[0]
                else:
                    self.studyRegion.scenario = ''


            # validates that a hazard is selected or auto-assigned
            if 'dropdown_hazard' in dir(self) and self.dropdown_hazard.winfo_ismapped():
                value = self.dropdown_hazard.get()
                if len(value) > 0:
                    self.studyRegion.setHazard(value)
                    self.studyRegion.report.hazard = value
                else:
                    self.selection_errors.append('Hazard')
                    validated = False

            # validates that a return period is selected or auto-assigned
            if type(self.options_returnPeriod) is list:
               # if self.studyRegion.returnPeriod is None:
                if (
                    'dropdown_returnPeriod' in dir(self)
                    and self.dropdown_returnPeriod.winfo_ismapped()
                ):
                    value = self.dropdown_returnPeriod.get()
                    self.studyRegion.returnPeriod = value
            else:
                self.studyRegion.returnPeriod = self.options_returnPeriod

            # validate export checkboxes
            self.exportOptions = {}
            self.exportOptions['csv'] = self.opt_csv.get()
            self.exportOptions['shapefile'] = self.opt_shp.get()
            self.exportOptions['geojson'] = self.opt_geojson.get()
            self.exportOptions['report'] = self.opt_report.get()

            # validates if the sum is greater than zero - if selected, they each checkbox will have a value of 1
            exportOptionsCount = sum([x for x in self.exportOptions.values()])
            if exportOptionsCount == 0:
                self.selection_errors.append('export checkbox')
                validated = False

            # validate output directory
            _outputDirectory = self.text_outputDirectory.get("1.0", 'end')
            _outputDirectory = _outputDirectory.replace('\n', '')
            if len(_outputDirectory) == 0:
                self.selection_errors.append('output directory')
                validated = False

            # (extra) validate only if exists - MUST be last in validation
            if 'opt_draftEmail' in dir(self):
                val = self.opt_draftEmail.get()
                self.exportOptions['draftEmail'] = val
                if val == 1:
                    validated = True

            return validated
        except Exception as e:
            print('\n')
            print(e)
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            print(fname)
            print(exc_type, exc_tb.tb_lineno)
            print('\n')

            print(e)
            # validation check fails
            validated = False
            ctypes.windll.user32.MessageBoxW(
                None,
                u"Unexpected export validation error: " + str(sys.exc_info()[0]),
                u'HazPy - Message',
                0,
            )

    def addWidget_report(self, row):
        """adds the report title and report subtitle widgets"""
        # report title
        self.label_reportTitle = tk.Label(
            self.root,
            text='Report Title',
            font='Helvetica 10 bold',
            background=self.backgroundColor,
            fg=self.fontColor,
        )
        self.label_reportTitle.grid(row=row, column=1, padx=0, pady=(20, 5), sticky=W)
        row += 1
        # report title text input
        self.text_reportTitle = tk.Text(
            self.root,
            height=1,
            width=37,
            font='Helvetica 10',
            background=self.textEntryColor,
            relief='flat',
            highlightbackground=self.textBorderColor,
            highlightthickness=1,
            highlightcolor=self.textHighlightColor,
        )
        self.text_reportTitle.grid(
            row=row, column=1, padx=(0, 0), pady=(0, 0), sticky=W
        )
        # report title icon
        self.img_reportTitle = tk.Label(
            self.root, image=self.img_edit, background=self.backgroundColor
        )
        self.img_reportTitle.grid(
            row=row, column=2, padx=(0, self.padl), pady=(0, 0), sticky=W
        )
        row += 1

        # report subtitle
        # report subtitle label
        self.label_reportSubtitle = tk.Label(
            self.root,
            text='Report Subtitle',
            font='Helvetica 10 bold',
            background=self.backgroundColor,
            fg=self.fontColor,
        )
        self.label_reportSubtitle.grid(
            row=row, column=1, padx=0, pady=(20, 5), sticky=W
        )
        row += 1
        # report subtitle text input
        self.text_reportSubtitle = tk.Text(
            self.root,
            height=1,
            width=37,
            font='Helvetica 10',
            background=self.textEntryColor,
            relief='flat',
            highlightbackground=self.textBorderColor,
            highlightthickness=1,
            highlightcolor=self.textHighlightColor,
        )
        self.text_reportSubtitle.grid(
            row=row, column=1, padx=(0, 0), pady=(0, 0), sticky=W
        )
        # report subtitle icon
        self.img_reportSubtitle = tk.Label(
            self.root, image=self.img_edit, background=self.backgroundColor
        )
        self.img_reportSubtitle.grid(
            row=row, column=2, padx=(0, self.padl), pady=(0, 0), sticky=W
        )

    def removeWidget_report(self):
        """removes the report title and report subtitle widgets"""
        self.label_reportTitle.grid_forget()
        self.text_reportTitle.grid_forget()
        self.text_reportTitle.delete('1.0', 'end')
        self.img_reportTitle.grid_forget()

        self.label_reportSubtitle.grid_forget()
        self.text_reportSubtitle.grid_forget()
        self.text_reportSubtitle.delete('1.0', 'end')
        self.img_reportSubtitle.grid_forget()

    def handle_reportCheckbox(self):
        """adds and removes the report widgets based off checkbox selection"""
        val = self.opt_report.get()
        if val == 0:
            self.removeWidget_report()
        if val == 1:
            self.addWidget_report(self.row_report)

    def handle_draftEmailCheckbox(self):
        """handles the draft email checkbox"""
        val = self.opt_draftEmail.get()

    def addWidget_hazard(self, row):
        """adds the hazard dropdown widget"""
        # requred label
        self.required_hazard = tk.Label(
            self.root,
            text='*',
            font='Helvetica 14 bold',
            background=self.backgroundColor,
            fg=self.starColor,
        )
        self.required_hazard.grid(
            row=10, column=0, padx=(self.padl, 0), pady=(20, 5), sticky=W
        )
        # # hazard label
        self.label_hazard = tk.Label(
            self.root,
            text='Hazard',
            font='Helvetica 10 bold',
            background=self.backgroundColor,
            fg=self.fontColor,
        )
        self.label_hazard.grid(row=10, column=1, padx=0, pady=(20, 5), sticky=W)
        #row = 10
        # # hazard dropdown
        self.dropdown_hazard = ttk.Combobox(
            self.root,
            textvar=self.value_hazard,
            values=self.options_hazard,
            width=40,
            style='H.TCombobox',
        )
        self.dropdown_hazard.grid(row=11, column=1, padx=(0, 0), pady=(0, 0), sticky=W)

    def removeWidget_hazard(self):
        """removes the hazard dropdown widget"""
        self.required_hazard.grid_forget()
        self.label_hazard.grid_forget()
        self.dropdown_hazard.grid_forget()
        self.dropdown_hazard.set('')

    def addWidget_scenario(self, row):
        """adds the scenario dropdown widget"""
        # requred label
        self.required_scenario = tk.Label(
            self.root,
            text='*',
            font='Helvetica 14 bold',
            background=self.backgroundColor,
            fg=self.starColor,
        )
        self.required_scenario.grid(
            row=row, column=0, padx=(self.padl, 0), pady=(20, 5), sticky=W
        )
        # scenario label
        self.label_scenario = tk.Label(
            self.root,
            text='Scenario',
            font='Helvetica 10 bold',
            background=self.backgroundColor,
            fg=self.fontColor,
        )
        self.label_scenario.grid(row=row, column=1, padx=0, pady=(20, 5), sticky=W)
        row += 1
        # scenario dropdown
        self.dropdown_scenario = ttk.Combobox(
            self.root,
            textvar=self.value_scenario,
            values=self.options_scenario,
            width=40,
            style='H.TCombobox',
        )
        self.dropdown_scenario.grid(
            row=row, column=1, padx=(0, 0), pady=(0, 0), sticky=W
        )

    def removeWidget_scenario(self):
        """removes the scenario dropdown widget"""
        self.required_scenario.grid_forget()
        self.label_scenario.grid_forget()
        self.dropdown_scenario.grid_forget()
        self.dropdown_scenario.set('')

    def addWidget_returnPeriod(self, row):
        """adds the return period dropdown widget"""
        # required label
        self.required_returnPeriod = tk.Label(
            self.root,
            text='*',
            font='Helvetica 14 bold',
            background=self.backgroundColor,
            fg=self.starColor,
        )
        self.required_returnPeriod.grid(
            row=row, column=0, padx=(self.padl, 0), pady=(20, 5), sticky=W
        )
        # return period label
        self.label_returnPeriod = tk.Label(
            self.root,
            text='Return Period',
            font='Helvetica 10 bold',
            background=self.backgroundColor,
            fg=self.fontColor,
        )
        self.label_returnPeriod.grid(row=row, column=1, padx=0, pady=(20, 5), sticky=W)
        row += 1
        # return period dropdown
        self.dropdown_returnPeriod = ttk.Combobox(
            self.root,
            textvar=self.value_returnPeriod,
            values=self.options_returnPeriod,
            width=40,
            style='H.TCombobox',
        )
        self.dropdown_returnPeriod.grid(
            row=row, column=1, padx=(0, 0), pady=(0, 0), sticky=W
        )

    def removeWidget_returnPeriod(self):
        """removes the return period dropdown widget"""
        self.required_returnPeriod.grid_forget()
        self.label_returnPeriod.grid_forget()
        self.dropdown_returnPeriod.grid_forget()
        self.dropdown_returnPeriod.set('')

    def addWidget_progress(self):
        """adds the progress bar widget"""
        row = self.row_progress

        self.bar_progress = Progressbar(mode='indeterminate')
        self.bar_progress.grid(row=row, column=1, pady=(0, 10), padx=50, sticky='nsew')
        self.root.update_idletasks()
        row += 1
        self.label_progress = tk.Label(
            self.root,
            text='Initializing',
            font='Helvetica 8',
            background=self.backgroundColor,
            fg=self.foregroundColor,
        )
        self.label_progress.grid(row=row, pady=(0, 10), column=1, sticky='nsew')
        row += 1
        self.label_progress.config(text='Initializing')
        self.bar_progress['value'] = 0
        self.root.update_idletasks()
        self.root.update()

    def removeWidget_progress(self):
        """removes the progress bar widget"""
        self.bar_progress.grid_forget()
        self.label_progress.grid_forget()

    def handle_studyRegion(self, name, index, operation):
        """handles widget creation and removal and initializes the study region class based off the study region dropdown selection"""
        try:
            value = self.value_studyRegion.get()
            # Remove draft email check button
            if hasattr(self, 'draft_email_button'):
                self.draft_email_button.grid_forget()
            # if a study region is selected
            if value != '':
                # init StudyRegion class
                self.studyRegion = StudyRegion(studyRegion=str(value))
                # Add Draft Email checkbutton for hurricanes
                if self.studyRegion.hazard.lower() == 'hurricane':
                    self.opt_draftEmail = tk.IntVar(value=1)
                    xpadl = 200
                    self.draft_email_button = ttk.Checkbutton(
                        self.root,
                        text="Draft Email",
                        variable=self.opt_draftEmail,
                        style='BW.TCheckbutton',
                        command=self.handle_draftEmailCheckbox,
                    )
                    self.draft_email_button.grid(row=8, column=1, padx=(xpadl, 0), pady=0, sticky=W)
                # get lists of hazards, scenarios, and return periods
                self.options_hazard = self.studyRegion.getHazardsAnalyzed()
                self.options_scenario = self.studyRegion.getScenarios()
                if len(self.options_scenario) > 1:
                    self.options_returnPeriod = self.studyRegion.getReturnPeriods()
                else:
                    self.studyRegion.setScenario(scenario=''.join(self.options_scenario))
                    self.studyRegion.scenario = str(''.join(self.options_scenario))
                    self.options_returnPeriod = self.studyRegion.getReturnPeriods(scenario=self.studyRegion.scenario)

                # try to remove previous widgets if they exist
                try:
                    self.removeWidget_hazard()
                except:
                    pass
                try:
                    self.removeWidget_scenario()
                except:
                    pass
                try:
                    self.removeWidget_returnPeriod()
                except:
                    pass

                # add widgets if multiple options exist
                if len(self.options_hazard) > 1:
                    self.addWidget_hazard(self.row_hazard)
                if  len(self.options_scenario) > 1:
                    self.addWidget_scenario(self.row_scenario)
                if self.options_returnPeriod is not None and isinstance(self.options_returnPeriod, list):
                    self.addWidget_returnPeriod(self.row_returnPeriod)

                # update the output directory
                if len(self.text_outputDirectory.get("1.0", 'end-1c')) > 0:
                    self.text_outputDirectory.delete("1.0", 'end-1c')
                    self.text_outputDirectory.insert(
                        "1.0", self.outputDirectory + '/' + self.studyRegion.name
                    )
        except Exception as e:
            print(e)
            ctypes.windll.user32.MessageBoxW(
                None,
                u"Unable to initialize the Study Region. Please select another Study Region to continue. Error: "
                + str(sys.exc_info()[0]),
                u'HazPy - Message',
                0,
            )

    def handle_hazard(self, name, index, operation):
        """handles the selection of a hazard from the hazard widget"""
        value = self.value_hazard.get()
        # if value selected
        if value != '':
            # update study region class with value
            self.studyRegion.setHazard(value)
            # Remove Draft Email check button, if exists
            if hasattr(self, 'draft_email_button'):
                self.draft_email_button.grid_forget()
            # Add Draft Email check button if selected hazard is hurricane
            if str(value).lower() == 'hurricane':
                self.opt_draftEmail = tk.IntVar(value=1)
                xpadl = 200
                self.draft_email_button = ttk.Checkbutton(
                    self.root,
                    text="Draft Email",
                    variable=self.opt_draftEmail,
                    style='BW.TCheckbutton',
                    command=self.handle_draftEmailCheckbox,
                )
                self.draft_email_button.grid(row=8, column=1, padx=(xpadl, 0), pady=0, sticky=W)
            print('Hazard set as ' + str(value))

            # get new scenario list
            self.options_scenario = self.studyRegion.getScenarios()
            # remove previous scenario widget if exists
            try:
                self.removeWidget_scenario()
            except:
                pass
            # add scenario widget if more than one option exists
            if len(self.options_scenario) > 1:
                self.addWidget_scenario()
            else:
                self.options_scenario = self.studyRegion.getScenarios()

    def handle_scenario(self, name, index, operation):
        """handles the selection of a scenario from the scenario widget"""
        value = self.value_scenario.get()
        # if value selected
        if value != '':
            # update study region class with value
            self.studyRegion.setScenario(value)
            print(f'Scenario set as: {value}')
            self.studyRegion.report.hazard = value
            # get new return period list
            self.options_returnPeriod = self.studyRegion.getReturnPeriods(scenario=(str(value)))
            try:
                self.removeWidget_returnPeriod()
            except:
                pass
            # add return period widget if more than one option exists
            if len(self.options_returnPeriod) > 1:
                self.options_returnPeriod = self.studyRegion.getReturnPeriods(scenario=(str(value)))
                print(f'Return Period set as: {self.options_returnPeriod}')
        else:
            value = ''.join(self.options_scenario)
            self.studyRegion.setScenario(value)
            self.studyRegion.scenario = value

    def handle_returnPeriod(self, name, index, operation):
        """handles the selection of a return period from the return period widget"""
        value = self.value_returnPeriod.get()
        # if value exists
        if value != '':
            # update study region class with value
            print('Return Period set as ' + str(value))
            self.studyRegion.returnPeriod = str(value)

    def build_gui(self):
        """builds the GUI"""
        try:
            # initialize dropdown options
            options_studyRegion = HazusDB().getStudyRegions()
            self.value_studyRegion = StringVar(name='studyRegion')
            self.value_studyRegion.trace('w', self.handle_studyRegion)

            self.options_hazard = []
            self.value_hazard = StringVar(name='hazard')
            self.value_hazard.trace('w', self.handle_hazard)

            self.options_scenario = []
            self.value_scenario = StringVar(name='scenario')
            self.value_scenario.trace(W, self.handle_scenario)

            self.options_returnPeriod = []
            self.value_returnPeriod = StringVar(name='returnPeriod')
            self.value_returnPeriod.trace(W, self.handle_returnPeriod)

            # requred label
            self.required_studyRegion = tk.Label(
                self.root,
                text='*',
                font='Helvetica 14 bold',
                background=self.backgroundColor,
                fg=self.starColor,
            )
            self.required_studyRegion.grid(
                row=self.row, column=0, padx=(self.padl, 0), pady=(20, 5), sticky=W
            )
            # Study Region label
            self.label_studyRegion = tk.Label(
                self.root,
                text='Study Region',
                font='Helvetica 10 bold',
                background=self.backgroundColor,
                fg=self.fontColor,
            )
            self.label_studyRegion.grid(
                row=self.row, column=1, padx=0, pady=(20, 5), sticky=W
            )
            self.row += 1
            # Study Region dropdown
            self.dropdown_studyRegion = ttk.Combobox(
                self.root,
                textvar=self.value_studyRegion,
                values=options_studyRegion,
                width=40,
                style='H.TCombobox',
            )
            self.dropdown_studyRegion.grid(
                row=self.row, column=1, padx=(0, 0), pady=(0, 0), sticky=W
            )
            # Study Region icon
            self.img_scenarioName = tk.Label(
                self.root, image=self.img_data, background=self.backgroundColor
            )
            self.img_scenarioName.grid(
                row=self.row, column=2, padx=(0, self.padl), pady=(0, 0), sticky=W
            )
            self.row += 1

            # requred label
            self.required_export = tk.Label(
                self.root,
                text='*',
                font='Helvetica 14 bold',
                background=self.backgroundColor,
                fg=self.starColor,
            )
            self.required_export.grid(
                row=self.row, column=0, padx=(self.padl, 0), pady=(20, 5), sticky=W
            )
            # export label
            self.label_export = tk.Label(
                self.root,
                text='Export',
                font='Helvetica 10 bold',
                background=self.backgroundColor,
                fg=self.fontColor,
            )
            self.label_export.grid(
                row=self.row, column=1, padx=0, pady=(20, 5), sticky=W
            )
            self.row += 1

            # export options
            xpadl = 200
            # CSV
            self.opt_csv = tk.IntVar(value=1)
            ttk.Checkbutton(
                self.root, text="CSV", variable=self.opt_csv, style='BW.TCheckbutton'
            ).grid(row=self.row, column=1, padx=(xpadl, 0), pady=0, sticky=W)
            self.row += 1
            # shapefile
            self.opt_shp = tk.IntVar(value=1)
            ttk.Checkbutton(
                self.root,
                text="Shapefile",
                variable=self.opt_shp,
                style='BW.TCheckbutton',
            ).grid(row=self.row, column=1, padx=(xpadl, 0), pady=0, sticky=W)
            self.row += 1
            # geojson
            self.opt_geojson = tk.IntVar(value=1)
            ttk.Checkbutton(
                self.root,
                text="GeoJSON",
                variable=self.opt_geojson,
                style='BW.TCheckbutton',
            ).grid(row=self.row, column=1, padx=(xpadl, 0), pady=0, sticky=W)
            self.row += 1
            # report
            self.opt_report = tk.IntVar(value=1)
            ttk.Checkbutton(
                self.root,
                text="Report",
                variable=self.opt_report,
                style='BW.TCheckbutton',
                command=self.handle_reportCheckbox,
            ).grid(row=self.row, column=1, padx=(xpadl, 0), pady=0, sticky=W)
            self.row += 1
            # (extra) draft email
            if self.config['extras']['draftEmail']:
                # Draft email is currently disabled by default
                self.opt_draftEmail = tk.IntVar(value=0)
                ttk.Checkbutton(
                    self.root,
                    text="Draft Email",
                    variable=self.opt_draftEmail,
                    style='BW.TCheckbutton',
                    command=self.handle_draftEmailCheckbox,
                ).grid(row=self.row, column=1, padx=(xpadl, 0), pady=0, sticky=W)
                self.row += 1

            # hazard
            self.row_hazard = self.row
            self.row += 2

            # scenario
            self.row_scenario = self.row
            self.row += 2

            # return period
            self.row_returnPeriod = self.row
            self.row += 2

            # report title
            self.row_report = self.row
            if self.opt_report.get() == 1:
                self.addWidget_report(self.row_report)
            self.row += 4

            # requred label
            self.label_required1 = tk.Label(
                self.root,
                text='*',
                font='Helvetica 14 bold',
                background=self.backgroundColor,
                fg=self.starColor,
            )
            self.label_required1.grid(
                row=self.row, column=0, padx=(self.padl, 0), pady=(20, 5), sticky=W
            )
            # output directory label
            self.label_outputDirectory = tk.Label(
                self.root,
                text='Output Directory',
                font='Helvetica 10 bold',
                background=self.backgroundColor,
                fg=self.fontColor,
            )
            self.label_outputDirectory.grid(
                row=self.row, column=1, padx=0, pady=(10, 0), sticky=W
            )
            self.row += 1
            # output directory form
            self.text_outputDirectory = tk.Text(
                self.root,
                height=1,
                width=37,
                font='Helvetica 10',
                background=self.textEntryColor,
                relief='flat',
                highlightbackground=self.textBorderColor,
                highlightthickness=1,
                highlightcolor=self.textHighlightColor,
            )
            self.text_outputDirectory.grid(
                row=self.row, column=1, padx=(0, 0), pady=(0, 0), sticky=W
            )
            # output directory icon
            self.button_outputDirectory = tk.Button(
                self.root,
                text="",
                image=self.img_folder,
                command=self.browsefunc,
                relief='flat',
                background=self.backgroundColor,
                fg='#dfe8e8',
                cursor="hand2",
                font='Helvetica 8 bold',
            )
            self.button_outputDirectory.grid(
                row=self.row, column=2, padx=(0, self.padl), pady=(0, 0), sticky=W
            )
            self.row += 1

            # run button
            self.button_run = tk.Button(
                self.root,
                text='Export',
                width=5,
                command=self.run,
                background='#0078a9',
                fg='#fff',
                cursor="hand2",
                font='Helvetica 8 bold',
                relief='flat',
            )
            self.button_run.grid(
                row=self.row,
                column=1,
                columnspan=1,
                sticky='nsew',
                padx=50,
                pady=(30, 20),
            )
            self.row += 2

            # progress bar
            self.row_progress = self.row
            self.row += 1

            # bind widget actions
            self.text_reportTitle.bind('<Tab>', self.focus_next_widget)
            self.text_reportSubtitle.bind('<Tab>', self.focus_next_widget)
            self.text_outputDirectory.bind('<Tab>', self.focus_next_widget)
            self.text_reportTitle.bind('<Shift-Tab>', self.focus_previous_widget)
            self.text_reportSubtitle.bind('<Shift-Tab>', self.focus_previous_widget)
            self.text_outputDirectory.bind('<Shift-Tab>', self.focus_previous_widget)

        except:
            messageBox = ctypes.windll.user32.MessageBoxW
            messageBox(
                0,
                "Unable to build the app: "
                + str(sys.exc_info()[0])
                + " | If this problem persists, contact fema-hazus-support@fema.dhs.gov.",
                "HazPy",
                0x1000,
            )

    def centerApp(self):
        try:
            screenWidth = self.root.winfo_screenwidth()
            screenHeight = self.root.winfo_screenheight()
            windowWidth = self.root.winfo_reqwidth() + 100
            windowHeight = self.root.winfo_reqheight() + 300

            positionRight = int(screenWidth / 2 - windowWidth / 2)
            positionDown = int(screenHeight / 2 - windowHeight / 2)

            self.root.geometry("+{}+{}".format(positionRight, positionDown))
        except:
            print('unable to center the app')
            pass

    def start(self):
        """builds the GUI and starts the app"""
        self.build_gui()
        self.centerApp()  # center application on screen
        self.root.lift()  # bring app to front
        self.root.mainloop()


# Start the app
app = App()
app.start()