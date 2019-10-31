import ctypes
import sys
from hazus.legacy import Exporting, getStudyRegions
import pyodbc as py
import os
import tkinter as tk
from tkinter import messagebox
from tkinter import filedialog
from tkinter import OptionMenu
from tkinter import StringVar
from tkinter import ttk
from tkinter import PhotoImage
from tkinter import Label
from tkinter import Canvas
from tkinter.ttk import Progressbar
from tkinter import TOP, RIGHT, LEFT, BOTTOM
from tkinter import N, S, E, W
from PIL import ImageTk,Image
from time import time, sleep
import json

class app():
    def __init__(self):
        # Create app
        self.root = tk.Tk()
        self.root.grid_propagate(0)
        
        # global styles
        config = json.loads(open('src/config.json').read())
        themeId = config['activeThemeId']
        theme = list(filter(lambda x: config['themes'][x]['themeId'] == themeId, config['themes']))[0]
        self.globalStyles = config['themes'][theme]['style']
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
        self.style.configure("BW.TCheckbutton", foreground=self.fontColor, background=self.backgroundColor, bordercolor=self.backgroundColor, side='LEFT')
        self.style.configure('TCombobox', background=self.backgroundColor, bordercolor=self.backgroundColor, relief='flat', lightcolor=self.backgroundColor, darkcolor=self.backgroundColor, borderwidth=4, foreground=self.foregroundColor)

        # App parameters
        self.root.title('Hazus Export Utility')
        self.root_h = 480
        self.root_w = 330
        self.root.geometry(str(self.root_w) + 'x' + str(self.root_h))
        windowWidth = self.root.winfo_reqwidth()
        windowHeight = self.root.winfo_reqheight()
        # Gets both half the screen width/height and window width/height
        positionRight = int(self.root.winfo_screenwidth()/2 - windowWidth)
        positionDown = int(self.root.winfo_screenheight()/3 - windowHeight)
        # Positions the window in the center of the page.
        self.root.geometry("+{}+{}".format(positionRight, positionDown))
        self.root.resizable(0, 0)
        self.root.configure(background=self.backgroundColor, highlightcolor='#fff')
    
        #App images
        self.root.wm_iconbitmap('src/assets/images/HazusHIcon.ico')
        self.img_data = ImageTk.PhotoImage(Image.open("src/assets/images/data_blue.png").resize((20,20), Image.BICUBIC))
        self.img_edit = ImageTk.PhotoImage(Image.open("src/assets/images/edit_blue.png").resize((20,20), Image.BICUBIC))
        self.img_folder = ImageTk.PhotoImage(Image.open("src/assets/images/folder_icon.png").resize((20,20), Image.BICUBIC))

        # Init dynamic row
        self.row = 0

    def updateProgressBar(self):
        with open(self.logFile) as f:
            log = json.loads(f.read())
            msg = log['log'][-1]['message']
            self.label_progress.config(text=msg)
            self.root.update_idletasks()
            self.progress['value'] += 13

    def browsefunc(self):
        self.output_directory = filedialog.askdirectory()
        self.input_studyRegion = self.dropdownMenu.get()
        self.text_outputDir.delete("1.0",'end-1c')
        if len(self.input_studyRegion) > 0:
            self.text_outputDir.insert("1.0",self.output_directory + '/' + self.input_studyRegion)
            self.root.update_idletasks()
        else:
            self.text_outputDir.insert("1.0",self.output_directory)
            self.root.update_idletasks()
    
    def on_field_change(self, index, value, op):
        try:
            self.input_studyRegion = self.dropdownMenu.get()
            self.output_directory = str(self.text_outputDir.get("1.0",'end-1c'))
            check = self.input_studyRegion in self.output_directory
            if (len(self.output_directory) > 0) and (not check):
                self.output_directory = '/'.join(self.output_directory.split('/')[0:-1])
                self.text_outputDir.delete('1.0', tk.END)
                self.text_outputDir.insert("1.0", self.output_directory + '/' + self.input_studyRegion)
            self.root.update_idletasks()
        except:
            pass
    
    def getTextFields(self):
        dict = {
            'title': self.text_title.get("1.0",'end-1c'),
            'meta': self.text_meta.get("1.0",'end-1c'),
            'output_directory': '/'.join(self.text_outputDir.get("1.0",'end-1c').split('/')[0:-1])
        }
        return dict


    def focus_next_widget(self, event):
        event.widget.tk_focusNext().focus()
        return("break")

    def on_enter_dir(self, e):
        self.button_outputDir['background'] = self.hoverColor

    def on_leave_dir(self, e):
        self.button_outputDir['background'] = self.backgroundColor

    def on_enter_run(self, e):
        self.button_run['background'] = '#006b96'

    def on_leave_run(self, e):
        self.button_run['background'] = '#0078a9'

    def run(self):
        try:       
            if (len(self.dropdownMenu.get()) > 0) and (len(self.text_outputDir.get("1.0",'end-1c')) > 0):
                if (self.opt_csv.get() + self.opt_shp.get() + self.opt_report.get() + self.opt_json.get()) > 0:
                    self.root.geometry(str(self.root_w)+ 'x' + str(self.root_h + 50))
                    # self.root.update()
                    self.root.update()
                    sleep(1)
                    # self.busy()
                    func_row = self.row
                    self.inputObj = self.getTextFields()
                    self.inputObj.update({'study_region': self.dropdownMenu.get()})
                    self.inputObj.update({'opt_csv': self.opt_csv.get()})
                    self.inputObj.update({'opt_shp': self.opt_shp.get()})
                    self.inputObj.update({'opt_report': self.opt_report.get()})
                    self.inputObj.update({'opt_json': self.opt_json.get()})
                    self.progress = Progressbar(mode = 'indeterminate')
                    self.progress.grid(row=func_row, column=1, pady=(0,10), padx=50, sticky='nsew')
                    func_row += 1
                    self.label_progress = tk.Label(self.root, text='Initializing', font='Helvetica 8', background=self.backgroundColor, fg=self.foregroundColor)
                    self.label_progress.grid(row=func_row, column=1, sticky='nsew')
                    self.label_progress.config(text='Establishing connection to SQL Server')
                    self.progress['value'] = 0
                    self.root.update_idletasks()
                    try:
                        t0 = time()
                        hazus = Exporting(self.inputObj)
                        hazus.setup()
                        hazus.logger.create(self.inputObj['output_directory'] + '/' + self.inputObj['study_region'])
                        self.logFile = hazus.logger.logFile
                        hazus.logger.log('Connected to SQL Server')
                        self.updateProgressBar()
                        hazus.logger.log('Retrieving and parsing data')
                        self.updateProgressBar()
                        hazus.getData()
                        hazus.logger.log('Results are ready for outputting')
                        self.updateProgressBar()
                        if self.inputObj['opt_csv']:
                            hazus.logger.log('Creating CSVs')
                            self.updateProgressBar()
                            hazus.toCSV()
                            hazus.logger.log('CSVs created')
                            self.updateProgressBar()
                        if self.inputObj['opt_shp']:
                            hazus.logger.log('Creating Shapefiles')
                            self.updateProgressBar()
                            hazus.toShapefile()
                            hazus.logger.log('Shapefiles created')
                            self.updateProgressBar()
                        if self.inputObj['opt_report']:
                            hazus.logger.log('Creating report (exchanging patience for maps)')
                            self.updateProgressBar()
                            hazus.toReport()
                            hazus.logger.log('Report created')
                            self.updateProgressBar()
                        hazus.logger.log('Finished exporting')
                        self.updateProgressBar()
                        print('Hazus results available locally at: ' + self.inputObj['output_directory'] +
                            '\\' + self.inputObj['study_region'])
                        self.progress['value'] = 100
                        # self.notbusy()
                        print('Total elasped time: ' + str(time() - t0))
                        tk.messagebox.showinfo("Hazus", "Success! Output files can be found at: " + self.inputObj['output_directory'] + '/' + self.inputObj['study_region'])
                        self.root.geometry(str(self.root_w) + 'x' + str(self.root_h))
                        self.progress.destroy()
                        self.label_progress.destroy()
                        hazus.logger.destroy()
                    except:
                        try:
                            self.progress.destroy()
                            self.label_progress.destroy()
                            hazus.logger.destroy()
                        except:
                            print('unable to destroy progress bar and label')
                        self.root.geometry(str(self.root_w) + 'x' + str(self.root_h))
                        # self.notbusy()
                        tk.messagebox.showerror('Hazus', str(sys.exc_info()[1]))
                else:
                    tk.messagebox.showwarning('Hazus', 'Select at least one option to export')
            else:
                tk.messagebox.showwarning('Hazus', 'Make sure a study region and output directory have been selected')
        except:
            self.root.geometry(str(self.root_w) + 'x' + str(self.root_h))
            ctypes.windll.user32.MessageBoxW(None, u"Unable to open correctly: " + str(sys.exc_info()[1]), u'Hazus - Message', 0)

    def build_gui(self):
            # App body
            # Required label
            self.label_required1 = tk.Label(self.root, text='*', font='Helvetica 14 bold', background=self.backgroundColor, fg=self.starColor)
            self.label_required1.grid(row=self.row, column=0, padx=(self.padl,0), pady=(20, 5), sticky=W)
            # Scenario name label
            self.label_scenarioName = tk.Label(self.root, text='Study Region', font='Helvetica 10 bold', background=self.backgroundColor, fg=self.fontColor)
            self.label_scenarioName.grid(row=self.row, column=1, padx=0, pady=(20, 5), sticky=W)
            self.row += 1
            
            # Get options for dropdown
            options = getStudyRegions()
            self.variable = StringVar(self.root)
            self.variable.set(options[0]) # default value
            
            # Scenario name dropdown menu
            self.v = StringVar()
            self.v.trace(W, self.on_field_change)
            self.dropdownMenu = ttk.Combobox(self.root, textvar=self.v, values=options, width=40, style='H.TCombobox')
            self.dropdownMenu.grid(row = self.row, column=1, padx=(0, 0), pady=(0,0), sticky=W)
            self.dropdownMenu.bind("<Tab>", self.focus_next_widget)

            # Scenario icon
            self.img_scenarioName = tk.Label(self.root, image=self.img_data, background=self.backgroundColor)
            self.img_scenarioName.grid(row=self.row, column=2, padx=0, pady=(0,0), sticky=W)
            self.row += 1

            # Output report title
            self.label_outputTitle = tk.Label(self.root, text='Report Title', font='Helvetica 10 bold', background=self.backgroundColor, fg=self.fontColor)
            self.label_outputTitle.grid(row=self.row, column=1, padx=0, pady=(20,5), sticky=W)
            self.row += 1

            # Output report title text form
            self.text_title = tk.Text(self.root, height=1, width=37, font='Helvetica 10', background=self.textEntryColor, relief='flat', highlightbackground=self.textBorderColor, highlightthickness=1, highlightcolor=self.textHighlightColor)
            self.text_title.grid(row = self.row, column=1, padx=(0, 0), pady=(0,0), sticky=W)
            self.text_title.bind("<Tab>", self.focus_next_widget)

            # Title icon 
            self.img_title = tk.Label(self.root, image=self.img_edit, background=self.backgroundColor)
            self.img_title.grid(row=self.row, column=2, padx=0, pady=(0,0), sticky=W)
            self.row += 1

            # Output report metadata label
            self.label_outputMetadata = tk.Label(self.root, text='Metadata/Notes', font='Helvetica 10 bold', background=self.backgroundColor, fg=self.fontColor)
            self.label_outputMetadata.grid(row=self.row, column=1, padx=0, pady=(20, 5), sticky=W)
            self.row += 1

            # Output report metadata text form
            self.text_meta = tk.Text(self.root, height=1, width=37, font='Helvetica 10', background=self.textEntryColor, relief='flat', highlightbackground=self.textBorderColor, highlightthickness=1, highlightcolor=self.textHighlightColor)
            self.text_meta.grid(row = self.row, column=1, padx=(0, 0), pady=(0,15), sticky=W)
            self.text_meta.bind("<Tab>", self.focus_next_widget)

            # Metadata icon 
            self.img_metadata = tk.Label(self.root, image=self.img_edit, background=self.backgroundColor)
            self.img_metadata.grid(row=self.row, column=2, padx=0, pady=(0,15), sticky=W)
            self.row += 1

            # Required label
            self.label_required2 = tk.Label(self.root, text='*', font='Helvetica 14 bold', background=self.backgroundColor, fg=self.starColor)
            self.label_required2.grid(row=self.row, column=0, padx=(self.padl,0), pady=(0, 0), sticky=W)
            # Output checkbox label
            self.label_outputMetadata = tk.Label(self.root, text='Export', font='Helvetica 10 bold', background=self.backgroundColor, fg=self.fontColor)
            self.label_outputMetadata.grid(row=self.row, column=1, padx=0, pady=(0, 0), sticky=W)

            # Output checkbox options
            xpadl = 200
            self.opt_csv = tk.IntVar(value=1)
            ttk.Checkbutton(self.root, text="Tabular", variable=self.opt_csv, style='BW.TCheckbutton').grid(row=self.row, column=1, padx=(xpadl,0), pady=0, sticky=W)
            self.row += 1
            self.opt_shp = tk.IntVar(value=1)
            ttk.Checkbutton(self.root, text="Spatial", variable=self.opt_shp, style='BW.TCheckbutton').grid(row=self.row, column=1, padx=(xpadl,0), pady=0, sticky=W)
            self.row += 1
            self.opt_report = tk.IntVar(value=1)
            ttk.Checkbutton(self.root, text="Report", variable=self.opt_report, style='BW.TCheckbutton').grid(row=self.row, column=1, padx=(xpadl,0), pady=0, sticky=W)
            self.row += 1
            self.opt_json = tk.IntVar(value=1)
            ttk.Checkbutton(self.root, text="Json", variable=self.opt_json, style='BW.TCheckbutton').grid(row=self.row, column=1, padx=(xpadl,0), pady=0, sticky=W)
            self.row += 1
            
            # Required label
            self.label_required3= tk.Label(self.root, text='*', font='Helvetica 14 bold', background=self.backgroundColor, fg=self.starColor)
            self.label_required3.grid(row=self.row, column=0, padx=(self.padl,0), pady=(10, 0), sticky=W)
            # Output directory label
            self.label_outputDir = tk.Label(self.root, text='Output Directory', font='Helvetica 10 bold', background=self.backgroundColor, fg=self.fontColor)
            self.label_outputDir.grid(row=self.row, column=1, padx=0, pady=(10,0), sticky=W)
            self.row += 1

            # Output directory text form
            self.text_outputDir = tk.Text(self.root, height=1, width=37, font='Helvetica 10', background=self.textEntryColor, relief='flat', highlightbackground=self.textBorderColor, highlightthickness=1, highlightcolor=self.textHighlightColor)
            self.text_outputDir.grid(row = self.row, column=1, padx=(0, 0), pady=(0,0), sticky=W)
            self.text_outputDir.bind("<Tab>", self.focus_next_widget)
            
            # Output directory browse button
            self.button_outputDir = tk.Button(self.root, text="", image=self.img_folder, command=self.browsefunc, relief='flat', background=self.backgroundColor, fg='#dfe8e8', cursor="hand2", font='Helvetica 8 bold')
            self.button_outputDir.grid(row=self.row, column=2, padx=0, pady=(0,0), sticky=W)
            self.button_outputDir.bind("<Tab>", self.focus_next_widget)
            self.button_outputDir.bind("<Enter>", self.on_enter_dir)
            self.button_outputDir.bind("<Leave>", self.on_leave_dir)
            self.row += 1
            
            # Run button
            self.button_run = tk.Button(self.root, text='Run', width=5, command=self.run, background='#0078a9', fg='#fff', cursor="hand2", font='Helvetica 8 bold', relief='flat')
            self.button_run.grid(row=self.row, column=1, columnspan=1, sticky='nsew', padx=50, pady=(30, 20))
            self.button_run.bind("<Enter>", self.on_enter_run)
            self.button_run.bind("<Leave>", self.on_leave_run)
            self.row += 1
            
    # Run app
    def run_app(self):
        self.build_gui()
        self.root.mainloop()
