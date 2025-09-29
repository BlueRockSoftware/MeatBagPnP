#!/usr/bin/env python3
import csv
import sys
import argparse
from urllib.request import urlopen

# Modern Python 3 imports for Qt
try:
    from PySide6 import QtGui, QtCore, QtWidgets
    from PySide6.QtWebEngineWidgets import QWebEngineView as WebView
    from PySide6 import QtWidgets as Widgets
except ImportError:
    try:
        from PySide2 import QtGui, QtCore, QtWidgets
        from PySide2.QtWebEngineWidgets import QWebEngineView as WebView
        from PySide2 import QtWidgets as Widgets
    except ImportError as ex:
        print(f"Failed to import PySide6 or PySide2: {ex}")
        print("Please install PySide6 or PySide2: pip install PySide6")
        sys.exit(1)

# Note: sgmllib was removed in Python 3, but it's not actually used in this code
# If HTML parsing is needed, use html.parser or BeautifulSoup instead


class PCBPainter(Widgets.QDialog):
    def __init__(self, parent):
        super(PCBPainter, self).__init__(parent)

        self.imglabel = Widgets.QLabel()

        vb = Widgets.QVBoxLayout()
        vb.addWidget(self.imglabel)

        openpb = Widgets.QPushButton("Set PCB Image")
        openpb.clicked.connect(self.set_image)

        self.timerFocus = QtCore.QTimer()
        self.timerFocus.setSingleShot(True)
        self.timerFocus.timeout.connect(self.clearfocus)

        self.pcbwidth = Widgets.QDoubleSpinBox()
        self.pcbwidth.setMinimum(0)
        self.pcbwidth.setMaximum(100000)
        self.pcbwidth.valueChanged.connect(self.clearfocusdelay)
        self.pcbheight = Widgets.QDoubleSpinBox()
        self.pcbheight.setMinimum(0)
        self.pcbheight.setMaximum(100000)
        self.pcbheight.valueChanged.connect(self.clearfocusdelay)
        self.marker_diameter = 20  # Increased from 5 to 20 for better visibility

        buttongrid = Widgets.QHBoxLayout()
        buttongrid.addWidget(openpb)
        buttongrid.addSpacing(5)
        buttongrid.addWidget(Widgets.QLabel("PCB Width (units): "))
        buttongrid.addWidget(self.pcbwidth)
        buttongrid.addSpacing(5)
        buttongrid.addWidget(Widgets.QLabel("PCB Height (units):"))
        buttongrid.addWidget(self.pcbheight)
        buttongrid.addStretch(5)

        vb.addLayout(buttongrid)

        self.setLayout(vb)
        
        # Set reasonable window size constraints for display
        self.setMaximumSize(1000, 800)  # Reasonable maximum size
        self.resize(800, 600)  # Initial size
        
        # Store original and display image separately
        self.original_base = None  # Original image for coordinate calculations
        self.display_scale = 1.0   # Scale factor for display

        self.image_path = ""

    def marker_diameter_increment(self):
        self.marker_diameter += 10
        # used as key action callback, so return true to redraw
        return True

    def marker_diameter_decrement(self):
        if self.marker_diameter < 10:
            return False
        
        self.marker_diameter -= 10
        # used as key action callback, so return true to redraw
        return True



    def draw_marker(self, x, y, mirror=False):
        """Draw a placement marker"""

        boardwidth = self.pcbwidth.value()
        boardheight = self.pcbheight.value()

        try:
            # Use original image dimensions for accurate coordinate calculations
            scale_x = float(self.original_base.width()) / float(boardwidth)
            scale_y = float(self.original_base.height()) / float(boardheight)
        except ZeroDivisionError:
            Widgets.QMessageBox.warning(self, "Division by Zero", "Division by zero - did you set board height & width in image?")
            raise

        x = x * scale_x
        y = y * scale_y

        #Y taken from wrong side normally
        y = self.original_base.height() - y
        
        if mirror:
            x = self.original_base.width() - x
        
        print(f"Drawing marker at pixel coordinates: ({x:.1f}, {y:.1f})")
        
        # Convert to integer coordinates for pixel-perfect positioning
        x_int = int(round(x))
        y_int = int(round(y))
        
        # Calculate marker radius for centered drawing
        radius = self.marker_diameter // 2
        
        painter = QtGui.QPainter()
        painter.begin(self.base)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        
        # Draw shadow/outline (black circle, slightly larger)
        painter.setBrush(QtGui.QBrush(QtCore.Qt.black))
        painter.setPen(QtCore.Qt.NoPen)
        painter.setOpacity(0.7)
        shadow_rect = QtCore.QRect(x_int - radius - 2, y_int - radius - 2, 
                                  self.marker_diameter + 4, self.marker_diameter + 4)
        painter.drawEllipse(shadow_rect)
        
        # Draw main marker (bright red circle)
        painter.setBrush(QtGui.QBrush(QtCore.Qt.red))
        painter.setOpacity(1.0)
        marker_rect = QtCore.QRect(x_int - radius, y_int - radius, 
                                  self.marker_diameter, self.marker_diameter)
        painter.drawEllipse(marker_rect)
        
        # Draw center crosshair for precise positioning
        painter.setPen(QtGui.QPen(QtCore.Qt.white, 2))
        painter.drawLine(x_int - radius//2, y_int, x_int + radius//2, y_int)  # Horizontal line
        painter.drawLine(x_int, y_int - radius//2, x_int, y_int + radius//2)  # Vertical line
        
        painter.end()

    def xy_to_draw(self, x, y, mirror):

        self.reload_base()

        self.draw_marker(x, y, mirror)
        
        self.redraw()
    

    def reload_base(self):
        # Load original image for coordinate calculations
        self.original_base = QtGui.QImage(self.image_path)
        # Convert to RGB32 format if it's an indexed format to support QPainter operations
        if self.original_base.format() == QtGui.QImage.Format_Indexed8 or self.original_base.format() == QtGui.QImage.Format_Mono:
            self.original_base = self.original_base.convertToFormat(QtGui.QImage.Format_RGB32)
        
        # Create working copy for drawing markers
        self.base = self.original_base.copy()
        
        # Calculate display scale to fit within reasonable window size
        max_display_width = 800
        max_display_height = 600
        
        scale_x = max_display_width / self.original_base.width()
        scale_y = max_display_height / self.original_base.height()
        self.display_scale = min(scale_x, scale_y, 1.0)  # Don't upscale, only downscale

    def redraw(self):
        # Scale image for display while keeping original for coordinates
        if self.display_scale < 1.0:
            display_width = int(self.base.width() * self.display_scale)
            display_height = int(self.base.height() * self.display_scale)
            scaled_image = self.base.scaled(display_width, display_height, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
            self.imglabel.setPixmap(QtGui.QPixmap.fromImage(scaled_image))
        else:
            self.imglabel.setPixmap(QtGui.QPixmap.fromImage(self.base))
    
    def configure_pcb_dimensions(self, height, width):
        self.pcbwidth.setValue(width)
        self.pcbheight.setValue(height)
    
    def image_selected(self, filename):
        if filename:
            self.image_path = filename
            self.reload_base()
            self.redraw()

    def set_image(self):
        filename, filter = Widgets.QFileDialog.getOpenFileName(parent=self, caption='Select PCB Image', dir='.',
                                                             filter='PCB Image (*.png)')

        self.image_selected(filename)

    def clearfocusdelay(self):
        """After 5 seconds clear focus, used to avoid accidently writing stuff here with scan gun"""
        self.timerFocus.start(5000)

    def clearfocus(self):
        self.pcbwidth.clearFocus()
        self.pcbheight.clearFocus()


class MeatBagCSVSettings(object):
    def __init__(self):
        self.col_layer = 0
        self.col_x = 0
        self.col_y = 0
        self.col_pn = 0
        self.col_des = 0
        self.col_com = 0

        #Starting data row (row=0 is often header)
        self.row_start = 0


class MeatBagCSVSettingsAltium(MeatBagCSVSettings):
    def __init__(self):
        super(MeatBagCSVSettingsAltium, self).__init__()
        self.col_layer = 2
        self.col_x = 4
        self.col_y = 5
        self.col_pn = 8
        self.col_des = 0
        self.col_com = 1

        #Starting data row (row=0 is often header)
        self.row_start = 1


class MeatBagCSVSettingsKicadSingleLayer(MeatBagCSVSettings):
    def __init__(self):
        super(MeatBagCSVSettingsKicadSingleLayer, self).__init__()
        #Default kicad .pos file layout: Ref,Val,Package,PosX,PosY,Rot,Side,
        # e.g. "C1","100n","C_0805_2012Metric",94.500000,-65.500000,90.000000,top

        self.col_layer = -1
        self.col_x = 3
        self.col_y = 4
        self.col_pn = 1
        self.col_des = 0
        self.col_com = 1

        #Starting data row (row=0 is often header)
        self.row_start = 1

class MeatBagCSVSettingsKicadMultiLayer(MeatBagCSVSettingsKicadSingleLayer):
    def __init__(self):
        super(MeatBagCSVSettingsKicadMultiLayer, self).__init__()
        #Default kicad .pos file layout: Ref,Val,Package,PosX,PosY,Rot,Side
        self.col_layer = 6


class KeyAction(object):
    """ action associated with a key """
    def __init__(self, key, callback):
        self.key = key.lower()
        self.cb = callback
    def matches(self, txt):
        if txt is None:
            return False
        if self.key == txt.lower():
            return True
        return False
    
    def trigger(self):
        return self.cb()


class MeatBagWindow(Widgets.QMainWindow):
    
    def __init__(self, csvSettings, parsedArgs):
        super(MeatBagWindow, self).__init__()
        self.setWindowTitle("Meat Bag Pick-n-Place v0.0000000003")

        self.efilter = filterObj(self)
        self.installEventFilter(self.efilter)

        self.initLayout()
        self.initMenus()
        if csvSettings:
            self.csv_settings = csvSettings
        else:
            self.csv_settings = MeatBagCSVSettingsAltium()

        self.getSettings()
        self.show()

        self.webView = WebView()
        self.webView.loadFinished.connect(self.lookupdone)

        self.last_keys = ""
        self.timerScan = QtCore.QTimer()
        self.timerScan.setSingleShot(True)
        self.timerScan.timeout.connect(self.timesUp)

        self.timerScanLineEdit = QtCore.QTimer()
        self.timerScanLineEdit.setSingleShot(True)
        self.timerScanLineEdit.timeout.connect(self.scanline_changed_dly)

        self.build_side = 0
        self.all_components_data = []  # Store all component data for filtering

        self.cur_placement = None
        self.drawing_all_same_value = False
        if parsedArgs is None:
            return
        # handle cmd line args
        if parsedArgs.image:
            self.pcbpainter.image_selected(parsedArgs.image)
        
        if parsedArgs.width and parsedArgs.height:
            self.pcbpainter.configure_pcb_dimensions(parsedArgs.height, parsedArgs.width)
        
        if parsedArgs.csv:
            self.parseCSVFile(parsedArgs.csv)

    def getSettings(self):
        """Configure settings. Eventually ask user, for now configure in source."""
        pass

        
    def initLayout(self):
        mainLayout = Widgets.QVBoxLayout()

        ###Main parts table
        self.table = Widgets.QTableWidget()
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.installEventFilter(self.efilter)
        self.table.cellClicked.connect(self.table_cellClicked)

        ###Build Configuration
        gbBuildSetup = Widgets.QGroupBox()
        gbBuildSetup.setTitle("Build Settings")
        buildLayout = Widgets.QGridLayout()

        #Top/Bottom Selection
        cbSide = Widgets.QComboBox()
        cbSide.addItem("Top")
        cbSide.addItem("Bottom")
        cbSide.activated.connect(self.sideSelectionChanged)
        cbSide.installEventFilter(self.efilter)
        
        buildLayout.addWidget(cbSide, 0, 0)
        gbBuildSetup.setLayout(buildLayout)


        ###Part Display
        gbPart = Widgets.QGroupBox()
        gbPart.setTitle("Part Info")

        self.topDes = Widgets.QLineEdit()
        self.topDes.setReadOnly(True)
        self.botDes = Widgets.QLineEdit()
        self.botDes.setReadOnly(True)

        partLayout = Widgets.QGridLayout()

        label_cur = Widgets.QLabel("Current Placement:")
        f = label_cur.font()
        f.setPointSize(12)
        label_cur.setFont(f)
        partLayout.addWidget(label_cur, 0, 0)

        self.place = Widgets.QLineEdit()
        f = self.place.font()
        f.setPointSize(12)
        self.place.setFont(f)
        self.place.setReadOnly(True)
        partLayout.addWidget(self.place, 0, 1)

        partLayout.addWidget(Widgets.QLabel("Top-Side Designators:"), 2, 0)
        partLayout.addWidget(Widgets.QLabel("Bot-Side Designators:"), 3, 0)
        partLayout.addWidget(self.topDes, 2, 1)
        partLayout.addWidget(self.botDes, 3, 1)

        gbPart.setLayout(partLayout)

        ### Debug Stuff

        gbDebug = Widgets.QGroupBox()
        gbDebug.setTitle("Part Number Info")

        self.scanLine = Widgets.QPlainTextEdit()
        self.scanLine.setFixedHeight(40)
        self.scanLine.setSizePolicy(Widgets.QSizePolicy.Minimum, Widgets.QSizePolicy.Minimum)
        self.scanLine.textChanged.connect(self.scanline_changed)

        debugLayout = Widgets.QHBoxLayout()
        debugLayout.addWidget(Widgets.QLabel("Scan Output (or paste P/N here):"))
        debugLayout.addWidget(self.scanLine)

        gbDebug.setLayout(debugLayout)

        ### Rest of Stuff
        window = Widgets.QWidget()
        window.setLayout(mainLayout)

        self.pcbpainter = PCBPainter(window)
        self.pcbpainter.show()
        self.pcbpainter.installEventFilter(self.efilter)
        
        mainLayout.addWidget(self.table)
        mainLayout.addWidget(gbBuildSetup)
        mainLayout.addWidget(gbPart)
        mainLayout.addWidget(gbDebug)

        self.setCentralWidget(window)

    def initMenus(self):
        self.openAct = QtGui.QAction("&Open...", self)
        self.openAct.setShortcut(QtGui.QKeySequence.Open)
        self.openAct.setStatusTip("Open an existing file")
        self.openAct.triggered.connect(self.openFile)

        self.fileMenu = self.menuBar().addMenu("&File")
        self.fileMenu.addAction(self.openAct)

    def isTopLayer(self, row):
        """Check if a given row (0-based index) is top-side or bottom-side part"""
        if self.csv_settings.col_layer < 0:
            return True

        tb = self.table.item(row, self.csv_settings.col_layer).text()

        if tb.lower().startswith("top"):
            return True
        elif tb.lower().startswith("bot"):
            return False
        else:
            raise ValueError(f"Unknown layer for row {row}: '{tb.lower()}' in col {self.csv_settings.col_layer}")

    def sideSelectionChanged(self, indx):
        """User changed build side"""
        self.build_side = indx
        # Update table to show only components for the selected side
        self.update_table_for_selected_side()

    def highlight_component_at_row(self, row):
        """Directly highlight the component at the specified table row"""
        try:
            # Get the component reference (designator)
            ref = self.table.item(row, self.csv_settings.col_des).text()
            
            # Get coordinates
            x = float(self.table.item(row, self.csv_settings.col_x).text())
            y = float(self.table.item(row, self.csv_settings.col_y).text())
            
            # Determine if it's a top or bottom layer component
            is_bottom = not self.isTopLayer(row)
            
            # Update the current placement display
            self.place.setText(ref)
            
            # Draw the marker
            self.pcbpainter.xy_to_draw(x, y, is_bottom)
            
            print(f"Highlighting {ref} at ({x}, {y})")
            
        except (ValueError, AttributeError) as e:
            print(f"Error highlighting component at row {row}: {e}")

    def table_cellClicked(self, row, col):
        """User click on a cell"""
        
        # Skip header rows
        if row < self.csv_settings.row_start:
            return
        
        # For direct reference highlighting, highlight the clicked component immediately
        self.highlight_component_at_row(row)
        
        # Also try the original part number matching for compatibility
        pn = self.table.item(row, self.csv_settings.col_pn).text()
        com = self.table.item(row, self.csv_settings.col_com).text()
        
        if pn is None or pn == "":
            #raise ValueError("Null PN for row - matching with Comment")
            self.process_new_com(com)
        else:
            self.process_new_pn(pn)


    def openFile(self):
        """Open new CSV PnP file"""

        filename, filter = Widgets.QFileDialog.getOpenFileName(parent=self, caption='Select PnP file', dir='.', filter='CSV files (*.csv *.mnt)')

        if not filename:
            return
        
        return self.parseCSVFile(filename)

    def group_components_by_value(self, ppdata):
        """Group components by their values for intuitive placement workflow"""
        if not ppdata or len(ppdata) == 0:
            return ppdata
            
        # Keep header row separate
        header_row = ppdata[0]
        data_rows = ppdata[1:] if len(ppdata) > 1 else []
        
        # Group components by value (column 1 in KiCad format)
        value_groups = {}
        
        for row in data_rows:
            if len(row) <= self.csv_settings.col_com:
                continue
                
            value = row[self.csv_settings.col_com]  # Component value (like "0.1uF", "10k")
            layer = row[self.csv_settings.col_layer] if self.csv_settings.col_layer >= 0 else "top"
            
            # Create a key combining value and layer for better organization
            key = f"{value}_{layer}"
            
            if key not in value_groups:
                value_groups[key] = []
            value_groups[key].append(row)
        
        # Sort groups by value name for consistent ordering
        sorted_groups = sorted(value_groups.items())
        
        # Rebuild the data with header first, then grouped components
        grouped_data = [header_row]
        
        for group_key, components in sorted_groups:
            # Sort components within each group by designator
            components.sort(key=lambda x: x[self.csv_settings.col_des] if len(x) > self.csv_settings.col_des else "")
            grouped_data.extend(components)
        
        print(f"Grouped {len(data_rows)} components into {len(value_groups)} groups")
        return grouped_data

    def parseCSVFile(self, filename):
        ppdata = []
        
        with open(filename, "r") as csvfile:
            ppfile = csv.reader(csvfile, delimiter=',', quotechar='"')
            for row in ppfile:
                if len(row) < 4:
                    print(f"Skipped line: {' '.join(row)}")
                else:
                    ppdata.append(row)

        # Store all component data for filtering
        self.all_components_data = self.group_components_by_value(ppdata)
        
        # Display components based on current side selection
        self.update_table_for_selected_side()

    def update_table_for_selected_side(self):
        """Update table to show only components for the selected side"""
        if not self.all_components_data:
            return
            
        # Filter components based on selected side
        filtered_data = []
        header_row = self.all_components_data[0]  # Always include header
        filtered_data.append(header_row)
        
        # Determine which side to show (0 = top, 1 = bottom)
        target_side = "top" if self.build_side == 0 else "bottom"
        
        for row in self.all_components_data[1:]:  # Skip header row
            if len(row) > self.csv_settings.col_layer and self.csv_settings.col_layer >= 0:
                layer = row[self.csv_settings.col_layer].lower()
                if layer.startswith(target_side[:3]):  # "top" or "bot"
                    filtered_data.append(row)
            elif self.csv_settings.col_layer < 0:  # No layer column, assume top
                if target_side == "top":
                    filtered_data.append(row)
        
        # Update table with filtered data
        self.table.clear()
        numRows = len(filtered_data)
        numCols = len(header_row) + 1
        self.table.setRowCount(numRows)
        self.table.setColumnCount(numCols)
        
        for r in range(0, numRows):
            for c in range(0, numCols - 1):
                try:
                    self.table.setItem(r, c, Widgets.QTableWidgetItem(filtered_data[r][c]))
                except IndexError:
                    self.table.setItem(r, c, Widgets.QTableWidgetItem("???"))

            checkitem = Widgets.QTableWidgetItem()
            checkitem.setCheckState(QtCore.Qt.Unchecked)
            self.table.setItem(r, numCols-1, checkitem)

        # Rebuild local database for filtered data
        self.pdb = []
        for r in range(0, numRows):
            if r < len(filtered_data) and len(filtered_data[r]) > self.csv_settings.col_pn:
                self.pdb.append(filtered_data[r][self.csv_settings.col_pn])
            else:
                self.pdb.append("")

        self.pdc = []
        for r in range(0, numRows):
            if r < len(filtered_data) and len(filtered_data[r]) > self.csv_settings.col_com:
                self.pdc.append(filtered_data[r][self.csv_settings.col_com])
            else:
                self.pdc.append("")
        
        side_name = "TOP" if self.build_side == 0 else "BOTTOM"
        component_count = numRows - 1  # Subtract header row
        print(f"Showing {component_count} {side_name} side components")
        
        self.recolourTable()

    def recolourTable(self):
        """Redo the table colour stuff"""
        rowcnt = self.table.rowCount()
        colcnt = self.table.columnCount()

        for r in range(self.csv_settings.row_start, rowcnt):
            try:
                placed = self.table.item(r, colcnt-1).checkState() == QtCore.Qt.Checked
                if placed:
                    alpha = 5
                else:
                    alpha = 120
                if self.isTopLayer(r):
                    bgc = QtGui.QColor(255, 0, 0, alpha)
                else:
                    bgc = QtGui.QColor(0, 0, 255, alpha)
            except ValueError:
                bgc = QtCore.Qt.lightGray

            for c in range(0, colcnt):

                self.table.item(r, c).setBackground(bgc)

    def key_pressed(self, key):
        self.last_keys += key
        self.timerScan.start(100)

    def timesUp(self, _=None):
        """A timer is used to detect end of scan (so no newline on scanner is assumed)"""

        scan = self.last_keys
        self.last_keys = ""

        if scan == " ":
            #User is moving between items
            last_place = self.cur_placement

            try:
                self.table.item(last_place, self.table.columnCount()-1).setCheckState(QtCore.Qt.Checked)
            except TypeError:
                pass

            self.find_next_placement()
            self.recolourTable()
            return


        #Remove line endings etc
        scan = scan.strip()

        #This triggers scan stuff
        self.scanLine.setPlainText(scan)

    def process_keystroke(self, txt):
        action_map = [
            KeyAction('+', self.pcbpainter.marker_diameter_increment),
            KeyAction('-', self.pcbpainter.marker_diameter_decrement),
            KeyAction('a', self.toggle_draw_all_of_current_value)
        ]
        refresh_placement = False
        for k in action_map:
            if k.matches(txt):
                #print("Have match")
                if k.trigger():
                    #print("Should refresh")
                    refresh_placement = True
        
        if refresh_placement:
            self.update_placement()

    def process_new_scan(self, scan):
        """Process a new barcode scan, convert to manufacture PN"""
        if len(scan) < 5:
            self.process_keystroke(scan)
            return

        self.topDes.setText("")
        self.botDes.setText("")

        #Check if we match already
        self.process_new_pn(scan, update_placement=False)

        if len(self.topDesList) > 0 or len(self.botDesList) > 0:
            self.find_next_placement()
            return

        #Failed - try web lookup

        if scan[0] == '[' and scan[1] == ')':
            # DIGIKEY
            if len(scan) > 30:
                pn_start = scan.split('1P')[1]
                pn = pn_start.split('K1K5')[0]
                self.process_new_pn(pn)
            else:
                internal_pn = scan[0:7]
                qty = int(scan[10:16])

                print("Old-style barcode, attempting lookup")
                sock = urlopen(
                    f'https://www.digikey.com/product-detail/en/keystone-electronics/4245C/36-4245C-ND/{internal_pn}')
                data = sock.read().decode('utf-8')
                raise NotImplementedError("Old-style barcode not implemented")

                #TODO: If you need to fix this, hack around following code to get actual PN not supplier one
                # data = data.split(" ")
                digikey_pn = data.split('content="sku:')[1].split("-ND")[0] + "-ND"
                # print(f"{digikey_pn}: {qty}")
        else:
            # MOUSER???
            print("Maybe Mouser? Trying lookup - WAITING FOR WEBPAGE NOW")
            #Use webview as need JS
            self.webView.load(QtCore.QUrl(f'https://ca.mouser.com/search/ProductDetail.aspx?R={scan}'))

    def lookupdone(self, _=None):
        """Called when website loaded"""
        # Note: QWebEngineView doesn't have mainFrame().toHtml() like the old QtWebKit
        # This needs to be rewritten using the async toHtml() method
        def handle_html(html):
            #Decode website type - try mouser first
            try:
                pn = html.split('<div id="divManufacturerPartNum">')[1].split("</div>")[0]
                pn = pn.split('<h1>')[1].split('</h1>')[0]
                print(f"Found PN: {pn}")
                self.process_new_pn(pn)
            except IndexError:
                print("Failed to find PN in returned site.")
        
        # Use the async method for getting HTML content
        self.webView.page().toHtml(handle_html)

    def process_new_com(self, com, update_placement=True):
        """Given a Comment, find all likely matches"""
        matchlist = []

        #Simple matching algorithm
        
        for i in range(0, len(self.pdc)):
            #print("checking")
            if (len(self.pdc[i]) > 3 and self.pdc[i] in com) or com in self.pdc[i]:
                matchlist.append(i)
        #print(matchlist)

        self.topDesList = []
        self.botDesList = []
        topDesStr = ""
        botDesStr = ""

        for r in matchlist:
            if self.isTopLayer(r):
                self.topDesList.append(r)
                topDesStr += self.table.item(r, self.csv_settings.col_des).text() + ", "
            else:
                self.botDesList.append(r)
                botDesStr += self.table.item(r, self.csv_settings.col_des).text() + ", "

        self.topDes.setText(topDesStr)
        self.botDes.setText(botDesStr)

        if update_placement:
            self.find_next_placement()   


    def process_new_pn(self, pn, update_placement=True):
        """Given a manufacturer's PN, find all likely matches"""
        matchlist = []

        #Simple matching algorithm
        for i in range(0, len(self.pdb)):
            if (len(self.pdb[i]) > 4 and self.pdb[i] in pn) or pn in self.pdb[i]:
                matchlist.append(i)

        self.topDesList = []
        self.botDesList = []
        topDesStr = ""
        botDesStr = ""

        for r in matchlist:
            if self.isTopLayer(r):
                self.topDesList.append(r)
                topDesStr += self.table.item(r, self.csv_settings.col_des).text() + ", "
            else:
                self.botDesList.append(r)
                botDesStr += self.table.item(r, self.csv_settings.col_des).text() + ", "

        self.topDes.setText(topDesStr)
        self.botDes.setText(botDesStr)

        if update_placement:
            self.find_next_placement()

    def toggle_draw_all_of_current_value(self):
        #print("draw_all_of_current_value")
        if self.cur_placement is None or not self.cur_placement:
            print("NO CUR PLACEMENT")
            return False
        
        if self.drawing_all_same_value:
            self.drawing_all_same_value = False
            self.update_placement()
            return

        if self.build_side == 0:
            parts = self.topDesList
        else:
            parts = self.botDesList
        cur_part_num_txt = self.table.item(self.cur_placement, self.csv_settings.col_pn).text()
        matchingPartsPos = []
        for p in parts:
            if p != self.cur_placement and  self.table.item(p, self.csv_settings.col_pn).text() == cur_part_num_txt:
                matchingPartsPos.append([float(self.table.item(p, self.csv_settings.col_x).text()), 
                                       float(self.table.item(p, self.csv_settings.col_y).text())])

        if not len(matchingPartsPos):
            print("No matching parts")
            return False
        self.update_placement()
        for pos in matchingPartsPos:
            self.pcbpainter.draw_marker(pos[0], pos[1])

        
        self.drawing_all_same_value = True
        self.pcbpainter.redraw()
        return False
        

    def find_next_placement(self):
        """Check the list for unplaced part on active layer"""
        self.cur_placement = None

        if self.build_side == 0:
            parts = self.topDesList
        else:
            parts = self.botDesList

        last_col = self.table.columnCount() - 1

        for p in parts:
            if self.table.item(p, last_col).checkState() == QtCore.Qt.Unchecked:
                #Next placement is 'p'
                self.cur_placement = p
                self.table.scrollToItem(self.table.item(p, 0))
                break

        self.update_placement()

    def update_placement(self):
        """Using variable self.cur_placement, update display to show location, name, etc."""
        self.drawing_all_same_value = False
        if self.cur_placement is not None:
            self.place.setText(self.table.item(self.cur_placement, self.csv_settings.col_des).text())

            self.pcbpainter.xy_to_draw(float(self.table.item(self.cur_placement, self.csv_settings.col_x).text()),
                                       float(self.table.item(self.cur_placement, self.csv_settings.col_y).text()),
                                       not self.isTopLayer(self.cur_placement))

        else:
            if len(self.topDesList) == 0 and len(self.botDesList) == 0:
                self.place.setText("Not Found")
            else:
                self.place.setText("Done")


    def scanline_changed(self):
        self.timerScanLineEdit.start(100)

    def scanline_changed_dly(self):
        self.process_new_scan(self.scanLine.toPlainText())
        self.scanLine.clearFocus()


class filterObj(QtCore.QObject):
    def __init__(self, windowObj):
        QtCore.QObject.__init__(self)
        self.windowObj = windowObj

    def eventFilter(self, obj, event):
        if (event.type() == QtCore.QEvent.KeyPress):
            key = event.text()

            self.windowObj.key_pressed(key)
            return True
        else:
            return False


def main():
    parser = argparse.ArgumentParser(description='MeatBagPnP')
    parser.add_argument('--csv', dest='csv',  help='CSV file to use')
    parser.add_argument('--format', dest='format', default='altium', help='CSV file format (altium|kicad|eagle)')
    parser.add_argument('--width', type=float, default=0.0, help='PCB width')
    parser.add_argument('--height', type=float, default=0.0, help='PCB height')
    parser.add_argument('--image')
    args = parser.parse_args()
    csvSettingsAvailable = dict(
        altium=MeatBagCSVSettingsAltium(),
        eagle=MeatBagCSVSettingsAltium(),  # same as altium for now
        kicad=MeatBagCSVSettingsKicadMultiLayer(),
        default=MeatBagCSVSettingsAltium()
    )
    csvSettings = csvSettingsAvailable['default']
    if args.format and args.format in csvSettingsAvailable:
        csvSettings = csvSettingsAvailable[args.format]
    else:
        print("Using default CSV format")
    
    app = Widgets.QApplication(sys.argv)
    ex = MeatBagWindow(csvSettings, args)
    app.exec()


if __name__ == '__main__':
    main()
