# -*- coding: utf-8 -*-
"""
ModEM data and response visualization with a gui.

The user will be able to choose from stations within the data to look at
in either impedance or apparent resistivity and phase.

The functionality is quite simple at the moment

JP 2014
"""
# 
#==============================================================================
from PyQt4 import QtCore, QtGui
import mtpy.modeling.modem_new as modem
from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt4agg import NavigationToolbar2QTAgg as NavigationToolbar
from matplotlib.figure import Figure
from matplotlib.patches import Ellipse
import mtpy.imaging.mtplottools as mtplottools
import matplotlib.gridspec as gridspec
import numpy as np
import matplotlib.pyplot as plt
import os
import mtpy.analysis.pt as mtpt
import mtpy.utils.exceptions as mtex
from matplotlib.colors import Normalize
import matplotlib.colorbar as mcb
import mtpy.imaging.mtcolors as mtcl
import mtpy.modeling.ws3dinv as ws

try:
    _fromUtf8 = QtCore.QString.fromUtf8
except AttributeError:
    def _fromUtf8(s):
        return s

try:
    _encoding = QtGui.QApplication.UnicodeUTF8
    def _translate(context, text, disambig):
        return QtGui.QApplication.translate(context, text, disambig, _encoding)
except AttributeError:
    def _translate(context, text, disambig):
        return QtGui.QApplication.translate(context, text, disambig)
# 
#==============================================================================


class Ui_MainWindow(mtplottools.MTArrows, mtplottools.MTEllipse):
    def __init__(self):
        
        self.modem_model_fn = None
        self.modem_data_fn = None
        self.modem_resp_fn = None
                
        self.save_plots = 'y'
        self.plot_period_index = None
        self.plot_period_list = None
        self.period_dict = None
        
        self.map_scale = 'km'
        #make map scale
        if self.map_scale == 'km':
            self.dscale = 1000.
            self._ellipse_dict = {'size':1}
            self._arrow_dict = {'size':.5,
                                'head_length':.05,
                                'head_width':.05,
                                'lw':.75}
                                
        elif self.map_scale == 'm':
            self.dscale = 1.
            self._ellipse_dict = {'size':500}
            self._arrow_dict = {'size':500,
                                'head_length':50,
                                'head_width':50,
                                'lw':.75}
        
        self._read_ellipse_dict()
        self._read_arrow_dict()
        
        self.ew_limits = None
        self.ns_limits = None
        
        self.pad_east = 2*self.ellipse_size
        self.pad_north = 2*self.ellipse_size
        
        self.plot_grid = 'n'
        
        
        self.xminorticks = 1000/self.dscale
        self.yminorticks = 1000/self.dscale
        
        self.residual_cmap = 'mt_wh2or'
        self.font_size = 7
        
        self.cb_tick_step = 45
        self.cb_residual_tick_step = 3
        self.cb_pt_pad = 1.2
        self.cb_res_pad = .5
        
        
        self.res_limits = (0,4)
        self.res_cmap = 'jet_r'
        
        #--> set the ellipse properties -------------------
        
        self.subplot_right = .99
        self.subplot_left = .085
        self.subplot_top = .92
        self.subplot_bottom = .1
        self.subplot_hspace = .2
        self.subplot_wspace = .05
        
        # arrays to put data into        
        self.pt_data_arr = None
        self.pt_resp_arr = None
        self.pt_resid_arr = None

        self.dir_path = os.getcwd()
        
    def setupUi(self, MainWindow):
        MainWindow.setWindowTitle("Plot ModEM MT Response as PT Maps")
        MainWindow.resize(1920, 1080)
        
        #make a central widget that everything is tied to.
        self.central_widget = QtGui.QWidget(MainWindow)
        self.central_widget.setWindowTitle("Plot MT Response")
        
        #make a widget that will be the station list
        self.list_widget = QtGui.QListWidget()
        self.list_widget.itemClicked.connect(self.get_period)
        self.list_widget.setMaximumWidth(150)

        # this is the Canvas Widget that displays the `figure`
        # it takes the `figure` instance as a parameter to __init__
        self.figure = Figure(dpi=150)
        self.mpl_widget = FigureCanvas(self.figure)
        
        #make sure the figure takes up the entire plottable space
        self.mpl_widget.setSizePolicy(QtGui.QSizePolicy.Expanding,
                                     QtGui.QSizePolicy.Expanding)

        # this is the Navigation widget
        # it takes the Canvas widget and a parent
        self.mpl_toolbar = NavigationToolbar(self.mpl_widget, MainWindow)
         
        # set the layout for the plot
        mpl_vbox = QtGui.QVBoxLayout()
        mpl_vbox.addWidget(self.mpl_toolbar)
        mpl_vbox.addWidget(self.mpl_widget)
        
        # set the layout the main window
        layout = QtGui.QHBoxLayout()
        layout.addWidget(self.list_widget)
        layout.addLayout(mpl_vbox)
        self.central_widget.setLayout(layout)

        #set the geometry of each widget        
        self.list_widget.setObjectName(_fromUtf8("listWidget"))
        self.mpl_widget.setObjectName(_fromUtf8("mpl_widget"))
        self.mpl_widget.updateGeometry()

        #set the central widget
        MainWindow.setCentralWidget(self.central_widget)

        #create a menu bar on the window
        self.menubar = QtGui.QMenuBar(MainWindow)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 1920, 38))
        self.menubar.setObjectName(_fromUtf8("menubar"))

        # add a tab for File --> open, close, save
        self.menu_data_file = QtGui.QMenu(self.menubar)
        self.menu_data_file.setTitle("Data File")
        
        self.menu_resp_file = QtGui.QMenu(self.menubar)
        self.menu_resp_file.setTitle("Response File")
        
        self.menu_model_file = QtGui.QMenu(self.menubar)
        self.menu_model_file.setTitle("Model File")
        
        # add a tab for chaning the display
        self.menu_display = QtGui.QMenu(self.menubar)
        self.menu_display.setTitle("Display")

        MainWindow.setMenuBar(self.menubar)

        # add a status bar on the bottom of the main window
        self.statusbar = QtGui.QStatusBar(MainWindow)
        self.statusbar.setObjectName(_fromUtf8("statusbar"))

        MainWindow.setStatusBar(self.statusbar)
        
        # set an open option that on click opens a modem file
        self.action_data_open = QtGui.QAction(MainWindow)
        self.action_data_open.setText("Open")
        self.action_data_open.triggered.connect(self.get_data_fn)

        # set a close that closes the main window
        self.action_close = QtGui.QAction(MainWindow)
        self.action_close.setText("Close")
        self.action_close.triggered.connect(MainWindow.close)

        # set a save option that will eventually save the masked data
        self.action_save = QtGui.QAction(MainWindow)
        self.action_save.setText("Save")

        # add the action on the menu tab
        self.menu_data_file.addAction(self.action_data_open)
        self.menu_data_file.addAction(self.action_close)
        self.menu_data_file.addAction(self.action_save)
        self.menubar.addAction(self.menu_data_file.menuAction())
        
        self.action_resp_open = QtGui.QAction(MainWindow)
        self.action_resp_open.setText("Open")
        self.action_resp_open.triggered.connect(self.get_resp_fn)
        self.menu_resp_file.addAction(self.action_resp_open)
        self.menubar.addAction(self.menu_resp_file.menuAction())
        
        self.action_model_open = QtGui.QAction(MainWindow)
        self.action_model_open.setText("Open")
        self.action_model_open.triggered.connect(self.get_model_fn)
        self.menu_model_file.addAction(self.action_model_open)
        self.menubar.addAction(self.menu_model_file.menuAction())
#        
        #adding options for display plot type        
#        self.menu_plot_type = QtGui.QMenu(MainWindow)
#        self.menu_plot_type.setTitle("Plot Type")
#        self.menuDisplay.addMenu(self.menu_plot_type)
#        self.menubar.addAction(self.menuDisplay.menuAction())
#        
#        #set plot impedance or resistivity and phase
#        self.action_plot_z = QtGui.QAction(MainWindow)
#        self.action_plot_z.setText('Impedance')
#        self.action_plot_z.setCheckable(True)
#        self.menu_plot_type.addAction(self.action_plot_z)
#        self.action_plot_z.toggled.connect(self.status_checked_ptz)
#        
#        self.action_plot_rp = QtGui.QAction(MainWindow)
#        self.action_plot_rp.setText('Resistivity-Phase')
#        self.action_plot_rp.setCheckable(True)
#        self.menu_plot_type.addAction(self.action_plot_rp)
#        self.action_plot_rp.toggled.connect(self.status_checked_ptrp)
        
        self.action_plot_settings = QtGui.QAction(MainWindow)
        self.action_plot_settings.setText('Settings')
        self.action_plot_settings.triggered.connect(self.show_settings)
        self.menu_display.addAction(self.action_plot_settings)
        self.menubar.addAction(self.menu_display.menuAction())
        
#        self.menuDisplay.addAction(self.menu_plot_style.menuAction())
#        self.menu_display.addAction(self.menu_plot_type.menuAction())
    
        #self.retranslateUi(MainWindow)
        # be sure to connnect all slots first
        QtCore.QMetaObject.connectSlotsByName(MainWindow)
        
                    
    def get_data_fn(self):
        """
        get the filename from a file dialogue
        
        """        

        fn_dialog = QtGui.QFileDialog()
        fn = str(fn_dialog.getOpenFileName(caption='Choose ModEM data file',
                                       filter='(*.dat);; (*.data)'))
                                       
        self.modem_data = modem.Data()
        self.modem_data.read_data_file(fn)
        self.modem_data_fn = fn
        
        self.dirpath = os.path.dirname(fn)
        
        self.period_list = sorted(self.modem_data.period_list)
        self.period_dict = dict([('{0:.5f}'.format(key), value) for value, key
                                 in enumerate(self.period_list)])
        
        self.list_widget.clear()
        
        #this will add the station name for each station to the qwidget list
        for period in self.period_list:
            self.list_widget.addItem('{0:.5f}'.format(period))
            
        self.plot_period = self.period_list[0]
            
    def get_model_fn(self):
        """
        get the filename from a file dialogue
        
        """        

        fn_dialog = QtGui.QFileDialog()
        fn = str(fn_dialog.getOpenFileName(caption='Choose ModEM model file',
                                       filter='(*.rho);; (*.ws)'))
                                   
        self.modem_model = modem.Model()
        self.modem_model.read_model_file(fn)
        self.modem_model_fn = fn
        self.plot()
        
        
    def get_period(self, widget_item):
        """
        get the station name from the clicked station 
        """
        self.plot_period = str(widget_item.text()) 
        self.plot()
        
    def get_resp_fn(self):
        """
        get response file name
        """
        
        fn_dialog = QtGui.QFileDialog(directory=self.dirpath)
        fn = str(fn_dialog.getOpenFileName(caption='Choose ModEM response file',
                                       filter='*.dat'))
                                       
        self.modem_resp = modem.Data()
        self.modem_resp.read_data_file(fn)
        self.modem_resp_fn = fn
        self.plot()
        
    def show_settings(self):
#        kw_dict = {'fs':self.fs,
#                   'lw':self.lw,
#                   'ms':self.ms,
#                   'e_capthick':self.e_capthick,
#                   'e_capsize':self.e_capsize,
#                   'cted':self.cted}
        self.settings_window = PlotSettings(None, **self.__dict__)
        self.settings_window.show()
        self.settings_window.settings_updated.connect(self.update_settings)
        
    def update_settings(self):
        
        for attr in sorted(self.settings_window.__dict__.keys()):
            setattr(self, attr, self.settings_window.__dict__[attr])
            print attr, self.__dict__[attr]
            
        self.plot()
        
    def _get_pt(self):
        """
        put pt parameters into something useful for plotting
        """
        
        ns = len(self.modem_data.mt_dict.keys())
        nf = len(self.modem_data.period_list)
        
        data_pt_arr = np.zeros((nf, ns), dtype=[('phimin', np.float),
                                                ('phimax', np.float),
                                                ('skew', np.float),
                                                ('azimuth', np.float),
                                                ('east', np.float),
                                                ('north', np.float),
                                                ('txr', np.float),
                                                ('tyr', np.float),
                                                ('txi', np.float),
                                                ('tyi', np.float)])
        if self.modem_resp_fn is not None:
            model_pt_arr = np.zeros((nf, ns), dtype=[('phimin', np.float),
                                                    ('phimax', np.float),
                                                    ('skew', np.float),
                                                    ('azimuth', np.float),
                                                    ('east', np.float),
                                                    ('north', np.float),
                                                    ('txr', np.float),
                                                    ('tyr', np.float),
                                                    ('txi', np.float),
                                                    ('tyi', np.float)])
            
            res_pt_arr = np.zeros((nf, ns), dtype=[('phimin', np.float),
                                                    ('phimax', np.float),
                                                    ('skew', np.float),
                                                    ('azimuth', np.float),
                                                    ('east', np.float),
                                                    ('north', np.float),
                                                    ('geometric_mean', np.float),
                                                    ('txr', np.float),
                                                    ('tyr', np.float),
                                                    ('txi', np.float),
                                                    ('tyi', np.float)])
                                                
        for ii, key in enumerate(self.modem_data.mt_dict.keys()):
            east = self.modem_data.mt_dict[key].grid_east/self.dscale
            north = self.modem_data.mt_dict[key].grid_north/self.dscale
            dpt = self.modem_data.mt_dict[key].pt
            data_pt_arr[:, ii]['east'] = east
            data_pt_arr[:, ii]['north'] = north
            data_pt_arr[:, ii]['phimin'] = dpt.phimin[0]
            data_pt_arr[:, ii]['phimax'] = dpt.phimax[0]
            data_pt_arr[:, ii]['azimuth'] = dpt.azimuth[0]
            data_pt_arr[:, ii]['skew'] = dpt.beta[0]

            # compute tipper data
            tip = self.modem_data.mt_dict[key].Tipper
            tip._compute_mag_direction()
                        
            data_pt_arr[:, ii]['txr'] = tip.mag_real*\
                                        np.sin(np.deg2rad(tip.angle_real))
            data_pt_arr[:, ii]['tyr'] = tip.mag_real*\
                                        np.cos(np.deg2rad(tip.angle_real))
            data_pt_arr[:, ii]['txi'] = tip.mag_imag*\
                                        np.sin(np.deg2rad(tip.angle_imag))
            data_pt_arr[:, ii]['tyi'] = tip.mag_imag*\
                                        np.cos(np.deg2rad(tip.angle_imag))
            if self.modem_resp_fn is not None:
                mpt = self.modem_resp.mt_dict[key].pt
                
                model_pt_arr[:, ii]['east'] = east
                model_pt_arr[:, ii]['north'] = north
                model_pt_arr[:, ii]['phimin'] = mpt.phimin[0]
                model_pt_arr[:, ii]['phimax'] = mpt.phimax[0]
                model_pt_arr[:, ii]['azimuth'] = mpt.azimuth[0]
                model_pt_arr[:, ii]['skew'] = mpt.beta[0]
                
                mtip = self.modem_resp.mt_dict[key].Tipper
                mtip._compute_mag_direction()
                            
                model_pt_arr[:, ii]['txr'] = mtip.mag_real*\
                                            np.sin(np.deg2rad(mtip.angle_real))
                model_pt_arr[:, ii]['tyr'] = mtip.mag_real*\
                                            np.cos(np.deg2rad(mtip.angle_real))
                model_pt_arr[:, ii]['txi'] = mtip.mag_imag*\
                                            np.sin(np.deg2rad(mtip.angle_imag))
                model_pt_arr[:, ii]['tyi'] = mtip.mag_imag*\
                                            np.cos(np.deg2rad(mtip.angle_imag))
                try:
                    rpt = mtpt.ResidualPhaseTensor(pt_object1=dpt, 
                                                   pt_object2=mpt)
                    rpt = rpt.residual_pt
                    res_pt_arr[:, ii]['east'] = east
                    res_pt_arr[:, ii]['north'] = north
                    res_pt_arr[:, ii]['phimin'] = rpt.phimin[0]
                    res_pt_arr[:, ii]['phimax'] = rpt.phimax[0]
                    res_pt_arr[:, ii]['azimuth'] = rpt.azimuth[0]
                    res_pt_arr[:, ii]['skew'] = rpt.beta[0]
                    res_pt_arr[:, ii]['geometric_mean'] = np.sqrt(abs(rpt.phimin[0]*\
                                                                  rpt.phimax[0]))
                                                                  
            
                except mtex.MTpyError_PT:
                    print key, dpt.pt.shape, mpt.pt.shape
                    
                res_pt_arr[:, ii]['txr'] = data_pt_arr[:, ii]['txr']-\
                                            model_pt_arr[:, ii]['txr']
                res_pt_arr[:, ii]['tyr'] = data_pt_arr[:, ii]['tyr']-\
                                            model_pt_arr[:, ii]['tyr']
                res_pt_arr[:, ii]['txi'] = data_pt_arr[:, ii]['txi']-\
                                            model_pt_arr[:, ii]['txi']
                res_pt_arr[:, ii]['tyi'] = data_pt_arr[:, ii]['tyi']-\
                                            model_pt_arr[:, ii]['tyi']
                
                
        #make these attributes        
        self.pt_data_arr = data_pt_arr
        if self.modem_resp_fn is not None:
            self.pt_resp_arr = model_pt_arr
            self.pt_resid_arr = res_pt_arr
                
    def plot(self):
        """
        plot phase tensor maps for data and or response, each figure is of a
        different period.  If response is input a third column is added which is 
        the residual phase tensor showing where the model is not fitting the data 
        well.  The data is plotted in km.
        
        """
        
        #make sure there is PT data
        if self.modem_data_fn is not None:
            print self.modem_data_fn
            if self.pt_data_arr is None:
                print 'data array is none'
                self._get_pt()
            if self.modem_resp_fn is not None:
                if self.pt_resp_arr is None:
                    self._get_pt()
        
        # make a grid of subplots 
        gs = gridspec.GridSpec(1, 3, hspace=self.subplot_hspace,
                               wspace=self.subplot_wspace)
                               
        font_dict = {'size':self.font_size+2, 'weight':'bold'}
        
        #set some parameters for the colorbar
        ckmin = float(self.ellipse_range[0])
        ckmax = float(self.ellipse_range[1])
        try:
            ckstep = float(self.ellipse_range[2])
        except IndexError:
            if self.ellipse_cmap == 'mt_seg_bl2wh2rd':
                raise ValueError('Need to input range as (min, max, step)')
            else:
                ckstep = 3
        bounds = np.arange(ckmin, ckmax+ckstep, ckstep)
        
        # set plot limits to be the station area
        if self.ew_limits == None:
            east_min = self.pt_data_arr['east'].min()-self.pad_east
            east_max = self.pt_data_arr['east'].max()+self.pad_east

            self.ew_limits = (east_min, east_max)
            
        if self.ns_limits == None:
            north_min = self.pt_data_arr['north'].min()-self.pad_north
            north_max = self.pt_data_arr['north'].max()+self.pad_north

            self.ns_limits = (north_min, north_max)
        print self.ew_limits, self.ns_limits, self.pad_east, self.pad_north
        #-------------plot phase tensors------------------------------------                    
        data_ii = self.period_dict[self.plot_period]
        
        print data_ii, type(self.pt_data_arr)
        
        self.figure.clf()
                         
        if self.modem_resp_fn is not None:
            axd = self.figure.add_subplot(gs[0, 0], aspect='equal')
            axm = self.figure.add_subplot(gs[0, 1], aspect='equal')
            axr = self.figure.add_subplot(gs[0, 2], aspect='equal')
            ax_list = [axd, axm, axr]
        
        else:
            axd = self.figure.add_subplot(gs[0, :], aspect='equal')
            ax_list = [axd]
            
        arr_dir = (-1)**self.arrow_direction
        
        #plot model below the phase tensors
        if self.modem_model_fn is not None:
            approx_depth, d_index = ws.estimate_skin_depth(self.modem_model.res_model.copy(),
                                                        self.modem_model.grid_z.copy()/self.dscale, 
                                                        float(self.plot_period), 
                                                        dscale=self.dscale)  
            #need to add an extra row and column to east and north to make sure 
            #all is plotted see pcolor for details.
            plot_east = np.append(self.modem_model.grid_east, 
                                  self.modem_model.grid_east[-1]*1.25)/\
                                  self.dscale
            plot_north = np.append(self.modem_model.grid_north, 
                                   self.modem_model.grid_north[-1]*1.25)/\
                                   self.dscale
            
            #make a mesh grid for plotting
            #the 'ij' makes sure the resulting grid is in east, north
            self.mesh_east, self.mesh_north = np.meshgrid(plot_east, 
                                                          plot_north,
                                                          indexing='ij')
            
            for ax in ax_list:
                plot_res = np.log10(self.modem_model.res_model[:, :, d_index].T)
                ax.pcolormesh(self.mesh_east,
                               self.mesh_north, 
                               plot_res,
                               cmap=self.res_cmap,
                               vmin=self.res_limits[0],
                               vmax=self.res_limits[1])
                
            
        #--> plot data phase tensors
        for pt in self.pt_data_arr[data_ii]:
            eheight = pt['phimin']/\
                      self.pt_data_arr[data_ii]['phimax'].max()*\
                      self.ellipse_size
            ewidth = pt['phimax']/\
                      self.pt_data_arr[data_ii]['phimax'].max()*\
                      self.ellipse_size
                      
            ellipse = Ellipse((pt['east'],
                               pt['north']),
                               width=ewidth,
                               height=eheight,
                               angle=90-pt['azimuth'])
            
            #get ellipse color
            if self.ellipse_cmap.find('seg')>0:
                ellipse.set_facecolor(mtcl.get_plot_color(pt[self.ellipse_colorby],
                                                     self.ellipse_colorby,
                                                     self.ellipse_cmap,
                                                     ckmin,
                                                     ckmax,
                                                     bounds=bounds))
            else:
                ellipse.set_facecolor(mtcl.get_plot_color(pt[self.ellipse_colorby],
                                                     self.ellipse_colorby,
                                                     self.ellipse_cmap,
                                                     ckmin,
                                                     ckmax))
            
            axd.add_artist(ellipse)
            
            #-----------Plot Induction Arrows---------------------------
            if pt['txr'] != 0.0:
                real_mag = np.sqrt(abs(pt['txr'])**2+abs(pt['tyr'])**2)
                imag_mag = np.sqrt(abs(pt['txi'])**2+abs(pt['tyi'])**2)
                #plot real tipper
                if real_mag <= self.arrow_threshold:
                    axd.arrow(pt['east'],
                              pt['north'],
                              self.arrow_size*pt['txr']*arr_dir,
                              self.arrow_size*pt['tyr']*arr_dir,
                              lw=self.arrow_lw,
                              facecolor=self.arrow_color_real,
                              edgecolor=self.arrow_color_real,
                              length_includes_head=False,
                              head_width=self.arrow_head_width,
                              head_length=self.arrow_head_length)
                else:
                    pass
                    
                #plot imaginary tipper
                if imag_mag <= self.arrow_threshold:
                    axd.arrow(pt['east'],
                              pt['north'],
                              self.arrow_size*pt['txi']*arr_dir,
                              self.arrow_size*pt['tyi']*arr_dir,
                              lw=self.arrow_lw,
                              facecolor=self.arrow_color_imag,
                              edgecolor=self.arrow_color_imag,
                              length_includes_head=False,
                              head_width=self.arrow_head_width,
                              head_length=self.arrow_head_length)
                else:
                    pass
                
        #-----------plot response phase tensors---------------
        if self.modem_resp_fn is not None:
            rcmin = np.floor(self.pt_resid_arr['geometric_mean'].min())
            rcmax = np.floor(self.pt_resid_arr['geometric_mean'].max())
            for mpt, rpt in zip(self.pt_resp_arr[data_ii], 
                                self.pt_resid_arr[data_ii]):
                eheight = mpt['phimin']/\
                          self.pt_resp_arr[data_ii]['phimax'].max()*\
                          self.ellipse_size
                ewidth = mpt['phimax']/\
                          self.pt_resp_arr[data_ii]['phimax'].max()*\
                          self.ellipse_size
                          
                ellipsem = Ellipse((mpt['east'],
                                   mpt['north']),
                                   width=ewidth,
                                   height=eheight,
                                   angle=90-mpt['azimuth'])
                
                #get ellipse color
                if self.ellipse_cmap.find('seg')>0:
                    ellipsem.set_facecolor(mtcl.get_plot_color(mpt[self.ellipse_colorby],
                                                         self.ellipse_colorby,
                                                         self.ellipse_cmap,
                                                         ckmin,
                                                         ckmax,
                                                         bounds=bounds))
                else:
                    ellipsem.set_facecolor(mtcl.get_plot_color(mpt[self.ellipse_colorby],
                                                         self.ellipse_colorby,
                                                         self.ellipse_cmap,
                                                         ckmin,
                                                         ckmax))
            
                axm.add_artist(ellipsem)
                
                #-----------Plot Induction Arrows---------------------------
                if mpt['txr'] != 0.0:
                    real_mag = np.sqrt(abs(mpt['txr'])**2+abs(mpt['tyr'])**2)
                    imag_mag = np.sqrt(abs(mpt['txi'])**2+abs(mpt['tyi'])**2)
                    #plot real tipper
                    if real_mag <= self.arrow_threshold:
                        axm.arrow(mpt['east'],
                                  mpt['north'],
                                  self.arrow_size*mpt['txr']*arr_dir,
                                  self.arrow_size*mpt['tyr']*arr_dir,
                                  lw=self.arrow_lw,
                                  facecolor=self.arrow_color_real,
                                  edgecolor=self.arrow_color_real,
                                  length_includes_head=False,
                                  head_width=self.arrow_head_width,
                                  head_length=self.arrow_head_length)
                    else:
                        pass
                        
                    #plot imaginary tipper
                    if imag_mag <= self.arrow_threshold:
                        axm.arrow(mpt['east'],
                                  mpt['north'],
                                  self.arrow_size*mpt['txi']*arr_dir,
                                  self.arrow_size*mpt['tyi']*arr_dir,
                                  lw=self.arrow_lw,
                                  facecolor=self.arrow_color_imag,
                                  edgecolor=self.arrow_color_imag,
                                  length_includes_head=False,
                                  head_width=self.arrow_head_width,
                                  head_length=self.arrow_head_length)
                    else:
                        pass
                
                #-----------plot residual phase tensors---------------
                eheight = rpt['phimin']/\
                          self.pt_resid_arr[data_ii]['phimax'].max()*\
                          self.ellipse_size
                ewidth = rpt['phimax']/\
                          self.pt_resid_arr[data_ii]['phimax'].max()*\
                          self.ellipse_size
                          
                ellipser = Ellipse((rpt['east'],
                                   rpt['north']),
                                   width=ewidth,
                                   height=eheight,
                                   angle=rpt['azimuth'])
                
                #get ellipse color
                rpt_color = np.sqrt(abs(rpt['phimin']*rpt['phimax']))
                if self.ellipse_cmap.find('seg')>0:
                    ellipser.set_facecolor(mtcl.get_plot_color(rpt_color,
                                                         'geometric_mean',
                                                         self.residual_cmap,
                                                         ckmin,
                                                         ckmax,
                                                         bounds=bounds))
                else:
                    ellipser.set_facecolor(mtcl.get_plot_color(rpt_color,
                                                         'geometric_mean',
                                                         self.residual_cmap,
                                                         ckmin,
                                                         ckmax))
                
                
                axr.add_artist(ellipser)
                
                #-----------Plot Induction Arrows---------------------------
                if rpt['txr'] != 0.0:
                    real_mag = np.sqrt(abs(rpt['txr'])**2+abs(rpt['tyr'])**2)
                    imag_mag = np.sqrt(abs(rpt['txi'])**2+abs(rpt['tyi'])**2)
                    #plot real tipper
                    if real_mag <= self.arrow_threshold:
                        axr.arrow(rpt['east'],
                                  rpt['north'],
                                  self.arrow_size*rpt['txr']*arr_dir,
                                  self.arrow_size*rpt['tyr']*arr_dir,
                                  lw=self.arrow_lw,
                                  facecolor=self.arrow_color_real,
                                  edgecolor=self.arrow_color_real,
                                  length_includes_head=False,
                                  head_width=self.arrow_head_width,
                                  head_length=self.arrow_head_length)
                    else:
                        pass
                        
                    #plot imaginary tipper
                    if imag_mag <= self.arrow_threshold:
                        axr.arrow(rpt['east'],
                                  rpt['north'],
                                  self.arrow_size*rpt['txi']*arr_dir,
                                  self.arrow_size*rpt['tyi']*arr_dir,
                                  lw=self.arrow_lw,
                                  facecolor=self.arrow_color_imag,
                                  edgecolor=self.arrow_color_imag,
                                  length_includes_head=False,
                                  head_width=self.arrow_head_width,
                                  head_length=self.arrow_head_length)
                    else:
                        pass
                
        #--> set axes properties
        # data
        axd.set_xlim(self.ew_limits)
        axd.set_ylim(self.ns_limits)
        axd.set_xlabel('Easting ({0})'.format(self.map_scale), 
                       fontdict=font_dict)
        axd.set_ylabel('Northing ({0})'.format(self.map_scale),
                       fontdict=font_dict)
        #make a colorbar for phase tensors
        #bb = axd.axes.get_position().bounds
        bb = axd.get_position().bounds
        y1 = .25*(2+(self.ns_limits[1]-self.ns_limits[0])/
                 (self.ew_limits[1]-self.ew_limits[0]))
        cb_location = (3.35*bb[2]/5+bb[0], 
                        y1*self.cb_pt_pad, .295*bb[2], .02)
        cbaxd = self.figure.add_axes(cb_location)
        cbd = mcb.ColorbarBase(cbaxd, 
                               cmap=mtcl.cmapdict[self.ellipse_cmap],
                               norm=Normalize(vmin=ckmin,
                                              vmax=ckmax),
                               orientation='horizontal')
        cbd.ax.xaxis.set_label_position('top')
        cbd.ax.xaxis.set_label_coords(.5, 1.75)
        cbd.set_label(mtplottools.ckdict[self.ellipse_colorby])
        cbd.set_ticks(np.arange(ckmin, ckmax+self.cb_tick_step, 
                                self.cb_tick_step))
                                
        axd.text(self.ew_limits[0]*.95,
                 self.ns_limits[1]*.95,
                 'Data',
                 horizontalalignment='left',
                 verticalalignment='top',
                 bbox={'facecolor':'white'},
                 fontdict={'size':self.font_size+1})
                
        #Model and residual
        if self.modem_resp_fn is not None:
            for aa, ax in enumerate([axm, axr]):
                ax.set_xlim(self.ew_limits)
                ax.set_ylim(self.ns_limits)
                ax.set_xlabel('Easting ({0})'.format(self.map_scale), 
                               fontdict=font_dict)
                plt.setp(ax.yaxis.get_ticklabels(), visible=False)
                #make a colorbar ontop of axis
                bb = ax.axes.get_position().bounds
                y1 = .25*(2+(self.ns_limits[1]-self.ns_limits[0])/
                         (self.ew_limits[1]-self.ew_limits[0]))
                cb_location = (3.35*bb[2]/5+bb[0], 
                               y1*self.cb_pt_pad, .295*bb[2], .02)
                cbax = self.figure.add_axes(cb_location)
                if aa == 0:
                    cb = mcb.ColorbarBase(cbax, 
                                          cmap=mtcl.cmapdict[self.ellipse_cmap],
                                          norm=Normalize(vmin=ckmin,
                                                         vmax=ckmax),
                                           orientation='horizontal')
                    cb.ax.xaxis.set_label_position('top')
                    cb.ax.xaxis.set_label_coords(.5, 1.75)
                    cb.set_label(mtplottools.ckdict[self.ellipse_colorby])
                    cb.set_ticks(np.arange(ckmin, ckmax+self.cb_tick_step, 
                                self.cb_tick_step))
                    ax.text(self.ew_limits[0]*.95,
                            self.ns_limits[1]*.95,
                            'Model',
                            horizontalalignment='left',
                            verticalalignment='top',
                            bbox={'facecolor':'white'},
                             fontdict={'size':self.font_size+1})
                else:
                    cb = mcb.ColorbarBase(cbax, 
                                          cmap=mtcl.cmapdict[self.residual_cmap],
                                           norm=Normalize(vmin=rcmin,
                                                          vmax=rcmax),
                                           orientation='horizontal')
                    cb.ax.xaxis.set_label_position('top')
                    cb.ax.xaxis.set_label_coords(.5, 1.75)
                    cb.set_label(r"$\sqrt{\Phi_{min} \Phi_{max}}$")
                    cb_ticks = [rcmin, (rcmax-rcmin)/2, rcmax]
                    cb.set_ticks(cb_ticks)
                    ax.text(self.ew_limits[0]*.95,
                            self.ns_limits[1]*.95,
                            'Residual',
                            horizontalalignment='left',
                            verticalalignment='top',
                            bbox={'facecolor':'white'},
                            fontdict={'size':self.font_size+1})
        
        if self.modem_model_fn is not None:
            for ax in ax_list:
                ax.tick_params(direction='out')
                bb = ax.axes.get_position().bounds
                y1 = .25*(2-(self.ns_limits[1]-self.ns_limits[0])/
                         (self.ew_limits[1]-self.ew_limits[0]))
                cb_position = (3.0*bb[2]/5+bb[0], 
                               y1*self.cb_res_pad, .35*bb[2], .02)
                cbax = self.figure.add_axes(cb_position)
                cb = mcb.ColorbarBase(cbax, 
                                      cmap=self.res_cmap,
                                      norm=Normalize(vmin=self.res_limits[0],
                                                     vmax=self.res_limits[1]),
                                      orientation='horizontal')
                cb.ax.xaxis.set_label_position('top')
                cb.ax.xaxis.set_label_coords(.5, 1.5)
                cb.set_label('Resistivity ($\Omega \cdot$m)')
                cb_ticks = np.arange(np.floor(self.res_limits[0]), 
                                     np.ceil(self.res_limits[1]+1), 1)
                cb.set_ticks(cb_ticks)
                cb.set_ticklabels([mtplottools.labeldict[ctk] for ctk in cb_ticks])

        self.mpl_widget.draw()
        
class PlotSettings(QtGui.QWidget):
    settings_updated = QtCore.pyqtSignal()
    def __init__(self, parent, **kwargs):
        super(PlotSettings, self).__init__(parent)
        
        self.fs = kwargs.pop('fs', 10)
        
        self.map_scale = kwargs.pop('map_scale', 'km')
        
        if self.map_scale == 'km': 
            self.ellipse_size = kwargs.pop('ellipse_size', .5)
            self.arrow_head_length = kwargs.pop('arrow_head_length', .025)
            self.arrow_head_width = kwargs.pop('arrow_head_width', .025)
            self.arrow_size = kwargs.pop('arrow_size', .5)
            self.pad_east = kwargs.pop('pad_east', 1)
            self.pad_north = kwargs.pop('pad_north', 1)
            
        if self.map_scale == 'm': 
            self.ellipse_size = kwargs.pop('ellipse_size', 500)
            self.arrow_head_length = kwargs.pop('arrow_head_length', 50)
            self.arrow_head_width = kwargs.pop('arrow_head_width', 50)
            self.arrow_size = kwargs.pop('arrow_size', 500)
            self.pad_east = kwargs.pop('pad_east', 1000)
            self.pad_north = kwargs.pop('pad_north', 1000)
            
        self.ellipse_cmap = kwargs.pop('ellipse_cmap', 'mt_bl2wh2rd')
        self.ellipse_range = kwargs.pop('ellipse_range', [0, 90, 5])
        self.ellipse_colorby = kwargs.pop('ellipse_colorby', 'phimin')
        
        if type(self.ellipse_range) == tuple:
            self.ellipse_range = list(self.ellipse_range)
        
        self.arrow_threshold = kwargs.pop('arrow_threshold', 2)
        self.arrow_color_imag = kwargs.pop('arrow_color_imag', 'b')
        self.arrow_color_real = kwargs.pop('arrow_color_real', 'k')
        self.arrow_direction = kwargs.pop('arrow_direction', 0)
        self.arrow_lw = kwargs.pop('arrow_lw', .75)
        
        self.subplot_wspace = kwargs.pop('subplot_wspace', .2)
        self.subplot_hspace = kwargs.pop('subplot_hspace', .0)
        self.subplot_right = kwargs.pop('subplot_right', .98)
        self.subplot_left = kwargs.pop('subplot_left', .08)
        self.subplot_top = kwargs.pop('subplot_top', .93)
        self.subplot_bottom = kwargs.pop('subplot_bottom', .08)

        
        self.initUI()

    def initUI(self):
        #--> line properties
        fs_label = QtGui.QLabel('Font Size')
        fs_edit = QtGui.QLineEdit()
        fs_edit.setText('{0:.1f}'.format(self.fs))
        fs_edit.textChanged[str].connect(self.set_text_fs)
        
        mapscale_label = QtGui.QLabel('Map Scale')
        mapscale_combo = QtGui.QComboBox()
        mapscale_combo.addItem('km')
        mapscale_combo.addItem('m')
        mapscale_combo.activated[str].connect(self.set_mapscale) 
        
        pad_east_label = QtGui.QLabel('Map Pad East')
        pad_east_edit = QtGui.QLineEdit()
        pad_east_edit.setText('{0:.3f}'.format(self.pad_east))
        pad_east_edit.textChanged[str].connect(self.set_pad_east)
        
        pad_north_label = QtGui.QLabel('Map Pad North')
        pad_north_edit = QtGui.QLineEdit()
        pad_north_edit.setText('{0:.3f}'.format(self.pad_north))
        pad_north_edit.textChanged[str].connect(self.set_pad_north)
        
        grid_line = QtGui.QGridLayout()
        grid_line.setSpacing(10)
        
        grid_line.addWidget(fs_label, 1, 0)
        grid_line.addWidget(fs_edit, 1, 1)
        
        grid_line.addWidget(mapscale_label, 1, 2)
        grid_line.addWidget(mapscale_combo, 1, 3)
        
        grid_line.addWidget(pad_east_label, 1, 4)
        grid_line.addWidget(pad_east_edit, 1, 5)
        
        grid_line.addWidget(pad_north_label, 1, 6)
        grid_line.addWidget(pad_north_edit, 1, 7)
        
        #--> ellipse properties
        ellipse_size_label = QtGui.QLabel('Ellipse Size')
        ellipse_size_edit = QtGui.QLineEdit()
        ellipse_size_edit.setText('{0:.2f}'.format(self.ellipse_size))
        ellipse_size_edit.textChanged[str].connect(self.set_ellipse_size)
        
        ellipse_range_label = QtGui.QLabel('Ellipse Range (min, max, step)')
        
        ellipse_range_edit_min = QtGui.QLineEdit()
        try:
            ellipse_range_edit_min.setText('{0:.2f}'.format(self.ellipse_range[0]))
        except IndexError:
            if self.ellipse_colorby == 'skew':
                ellipse_range_edit_min.setText('{0:.2f}'.format(-9))
                self.ellipse_range = [-9.0]
            else:
                ellipse_range_edit_min.setText('{0:.2f}'.format(0))
                self.ellipse_range = [0]
        ellipse_range_edit_min.textChanged[str].connect(self.set_ellipse_range_min)
        
        ellipse_range_edit_max = QtGui.QLineEdit()
        try:
            ellipse_range_edit_max.setText('{0:.2f}'.format(self.ellipse_range[1]))
        except IndexError:
            if self.ellipse_colorby == 'skew':
                ellipse_range_edit_max.setText('{0:.2f}'.format(9))
                self.ellipse_range.append(9.0)
            else:
                ellipse_range_edit_max.setText('{0:.2f}'.format(90))
                self.ellipse_range.append(90.0)
        ellipse_range_edit_max.textChanged[str].connect(self.set_ellipse_range_max)
        
        ellipse_range_edit_step = QtGui.QLineEdit()
        try:
            ellipse_range_edit_step.setText('{0:.2f}'.format(self.ellipse_range[0]))
        except IndexError:
            if self.ellipse_colorby == 'skew':
                ellipse_range_edit_step.setText('{0:.2f}'.format(3))
                self.ellipse_range.append(3.0)
            else:
                ellipse_range_edit_step.setText('{0:.2f}'.format(5))
                self.ellipse_range.append(5)
        ellipse_range_edit_step.textChanged[str].connect(self.set_ellipse_range_step)

        range_grid = QtGui.QGridLayout()
        range_grid.setSpacing(5)
        range_grid.addWidget(ellipse_range_edit_min, 1, 0)
        range_grid.addWidget(ellipse_range_edit_max, 1, 1)
        range_grid.addWidget(ellipse_range_edit_step, 1, 2)

        ellipse_colorby_label = QtGui.QLabel('Ellipse Color By')
        ellipse_colorby_combo = QtGui.QComboBox()
        ellipse_colorby_combo.addItem('phimin')
        ellipse_colorby_combo.addItem('phimax')
        ellipse_colorby_combo.addItem('ellipticty')
        ellipse_colorby_combo.addItem('skew')
        ellipse_colorby_combo.addItem('skew_seg')
        ellipse_colorby_combo.activated[str].connect(self.set_ellipse_colorby)
        
        ellipse_cmap_label = QtGui.QLabel('Ellipse Color Map')
        ellipse_cmap_combo = QtGui.QComboBox()
        ellipse_cmap_combo.addItem('mt_bl2wh2rd')
        ellipse_cmap_combo.addItem('mt_yl2rd')
        ellipse_cmap_combo.addItem('mt_wh2bl')
        ellipse_cmap_combo.addItem('mt_bl2gr2rd')
        ellipse_cmap_combo.addItem('mt_rd2gr2bl')
        ellipse_cmap_combo.addItem('mt_seg_bl2wh2rd')
        ellipse_cmap_combo.activated[str].connect(self.set_ellipse_cmap)
        
        ellipse_grid = QtGui.QGridLayout()
        ellipse_grid.setSpacing(10)
        
        ellipse_grid.addWidget(ellipse_size_label, 1, 0)
        ellipse_grid.addWidget(ellipse_size_edit, 1, 1)
        
        ellipse_grid.addWidget(ellipse_range_label, 1, 2)
        ellipse_grid.addLayout(range_grid, 1, 3)
        
        ellipse_grid.addWidget(ellipse_colorby_label, 1, 4)
        ellipse_grid.addWidget(ellipse_colorby_combo, 1, 5)
        
        ellipse_grid.addWidget(ellipse_cmap_label, 1, 6)
        ellipse_grid.addWidget(ellipse_cmap_combo, 1, 7)
        
        #--> plot limits
#        ylimr_xx_label = QtGui.QLabel('Res_xx')
#        ylimr_xx_edit = QtGui.QLineEdit()
#        ylimr_xx_edit.setText('{0}'.format(self.res_xx_limits))
#        ylimr_xx_edit.textChanged[str].connect(self.set_text_res_xx) 
#        
#        ylimr_xy_label = QtGui.QLabel('Res_xy')
#        ylimr_xy_edit = QtGui.QLineEdit()
#        ylimr_xy_edit.setText('{0}'.format(self.res_xy_limits))
#        ylimr_xy_edit.textChanged[str].connect(self.set_text_res_xy) 
#        
#        ylimr_yx_label = QtGui.QLabel('Res_yx')
#        ylimr_yx_edit = QtGui.QLineEdit()
#        ylimr_yx_edit.setText('{0}'.format(self.res_yx_limits))
#        ylimr_yx_edit.textChanged[str].connect(self.set_text_res_yx) 
#        
#        ylimr_yy_label = QtGui.QLabel('Res_yy')
#        ylimr_yy_edit = QtGui.QLineEdit()
#        ylimr_yy_edit.setText('{0}'.format(self.res_yy_limits))
#        ylimr_yy_edit.textChanged[str].connect(self.set_text_res_yy)  
#        
#        ylimp_xx_label = QtGui.QLabel('phase_xx')
#        ylimp_xx_edit = QtGui.QLineEdit()
#        ylimp_xx_edit.setText('{0}'.format(self.phase_xx_limits))
#        ylimp_xx_edit.textChanged[str].connect(self.set_text_phase_xx) 
#        
#        ylimp_xy_label = QtGui.QLabel('phase_xy')
#        ylimp_xy_edit = QtGui.QLineEdit()
#        ylimp_xy_edit.setText('{0}'.format(self.phase_xy_limits))
#        ylimp_xy_edit.textChanged[str].connect(self.set_text_phase_xy) 
#        
#        ylimp_yx_label = QtGui.QLabel('phase_yx')
#        ylimp_yx_edit = QtGui.QLineEdit()
#        ylimp_yx_edit.setText('{0}'.format(self.phase_yx_limits))
#        ylimp_yx_edit.textChanged[str].connect(self.set_text_phase_yx) 
#        
#        ylimp_yy_label = QtGui.QLabel('phase_yy')
#        ylimp_yy_edit = QtGui.QLineEdit()
#        ylimp_yy_edit.setText('{0}'.format(self.phase_yy_limits))
#        ylimp_yy_edit.textChanged[str].connect(self.set_text_phase_yy)        
#        
#        limits_grid = QtGui.QGridLayout()
#        limits_grid.setSpacing(10)
#        
#        limits_label = QtGui.QLabel('Plot Limits: (Res=Real, Phase=Imaginary)'
#                                    ' --> input on a linear scale')
#        
#        limits_grid.addWidget(limits_label, 1, 0, 1, 7)
#        
#        limits_grid.addWidget(ylimr_xx_label, 2, 0)
#        limits_grid.addWidget(ylimr_xx_edit, 2, 1)
#        limits_grid.addWidget(ylimr_xy_label, 2, 2)
#        limits_grid.addWidget(ylimr_xy_edit, 2, 3)
#        limits_grid.addWidget(ylimr_yx_label, 2, 4)
#        limits_grid.addWidget(ylimr_yx_edit, 2, 5)
#        limits_grid.addWidget(ylimr_yy_label, 2, 6)
#        limits_grid.addWidget(ylimr_yy_edit, 2, 7)
#        
#        limits_grid.addWidget(ylimp_xx_label, 3, 0)
#        limits_grid.addWidget(ylimp_xx_edit, 3, 1)
#        limits_grid.addWidget(ylimp_xy_label, 3, 2)
#        limits_grid.addWidget(ylimp_xy_edit, 3, 3)
#        limits_grid.addWidget(ylimp_yx_label, 3, 4)
#        limits_grid.addWidget(ylimp_yx_edit, 3, 5)
#        limits_grid.addWidget(ylimp_yy_label, 3, 6)
#        limits_grid.addWidget(ylimp_yy_edit, 3, 7)
#        
#        #--> legend properties
#        legend_pos_label = QtGui.QLabel('Legend Position')
#        legend_pos_edit = QtGui.QLineEdit()
#        legend_pos_edit.setText('{0}'.format(self.legend_pos))
#        legend_pos_edit.textChanged[str].connect(self.set_text_legend_pos)
#        
#        legend_grid = QtGui.QGridLayout()
#        legend_grid.setSpacing(10)
#        
#        legend_grid.addWidget(QtGui.QLabel('Legend Properties:'), 1, 0)
#        legend_grid.addWidget(legend_pos_label, 1, 2,)
#        legend_grid.addWidget(legend_pos_edit, 1, 3)
        
        update_button = QtGui.QPushButton('Update')
        update_button.clicked.connect(self.update_settings)        
        
        vbox = QtGui.QVBoxLayout()
        vbox.addLayout(grid_line)
        vbox.addLayout(ellipse_grid)
#        vbox.addLayout(limits_grid)
#        vbox.addLayout(legend_grid)
        vbox.addWidget(update_button)
        
        self.setLayout(vbox) 
        
        self.setGeometry(300, 300, 350, 300)
        self.resize(1350, 500)
        self.setWindowTitle('Plot Settings')    
        self.show()

    def set_text_fs(self, text):
        try:
            self.fs = float(text)
        except ValueError:
            print "Enter a float point number"
            
    def set_mapscale(self, text):
        self.map_scale = str(text)
            
    def set_pad_east(self, text):
        try:
            self.pad_east = float(text)
        except ValueError:
            print "Enter a float point number"

    
    def set_pad_north(self, text):
        try:
            self.pad_north = float(text)
        except ValueError:
            print "Enter a float point number"
            
    def set_ellipse_size(self, text):
        try:
            self.ellipse_size = float(text)
        except ValueError:
            print "Enter a float point number"
            
    def set_ellipse_range_min(self, text):
        try:
            self.ellipse_range[0] = float(text) 
        except ValueError:
            print "Enter a float point number"
            
    def set_ellipse_range_max(self, text):
        try:
            self.ellipse_range[1] = float(text) 
        except ValueError:
            print "Enter a float point number"
    def set_ellipse_range_step(self, text):
        try:
            self.ellipse_range[2] = float(text)
        except IndexError:
            self.ellipse_range.append(float(text))
        except ValueError:
            print "Enter a float point number"
            
    def set_ellipse_cmap(self, text):
        self.ellipse_cmap = str(text)
        
    def set_ellipse_colorby(self, text):
        self.ellipse_colorby = str(text)
            
            
    def update_settings(self):
        self.settings_updated.emit()

#def main():
    
def main():
#if __name__ == "__main__":
    import sys
    app = QtGui.QApplication(sys.argv)
    MainWindow = QtGui.QMainWindow()
    ui = Ui_MainWindow()
    ui.setupUi(MainWindow)
    MainWindow.show()
    sys.exit(app.exec_())

if __name__ == '__main__':

    main()