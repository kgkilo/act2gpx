#https://code.google.com/p/ambit2gpx/source/browse/src/ambit2gpx.py

import os
import xml.dom.minidom
import getopt
import sys
from dateutil import parser #needs python-dateutil on Ubuntu
from datetime import timedelta

def child_elements(parent):
    elements = []
    for child in parent.childNodes:
        if child.nodeType != child.ELEMENT_NODE:
            continue
        elements.append(child)
    return elements

class ActXMLParser(object):
    __root = None
    __outputfile = None
    def __init__(self, xml_node, noalti, altibaro, \
            noext, nopower, notemp, output_file):
        assert isinstance(xml_node, xml.dom.Node)
        assert xml_node.nodeType == xml_node.ELEMENT_NODE
        self.__root = xml_node
        self.__outputfile = output_file
        self.__altibaro = altibaro
        self.__noalti = noalti
        self.__altitude = None
        self.__latitude = None
        self.__longitude = None
        self.__time =  None
        self.__hr = None
        self.__temperature = None
        self.__cadence = None
        self.__noext = noext
        self.__nopower = nopower
        self.__notemp = notemp
        self.__nb_trackpoints_parsed = 0

    def extension(self, hr, temperature, cadence, power):
        if (self.__noext == True):
            return ""

        extension_found = False

        hr_ext = ""
        if (hr != None):
            extension_found = True
            hr_ext = "<gpxtpx:hr>{hr}</gpxtpx:hr>".format(hr=hr)

        tmp_ext = ""
        if ((self.__notemp != True) and (temperature != None)):
            extension_found = True
            tmp_ext = "<gpxtpx:atemp>{temp}</gpxtpx:atemp>".format(temp=temperature)

        cad_ext = ""
        if (cadence != None):
            extension_found = True
            cad_ext = "<gpxtpx:cad>{cadence}</gpxtpx:cad>".format(cadence=cadence)

        pow_ext = ""
        if ((self.__nopower != True) and (power != None)):
            extension_found = True
            pow_ext = "<gpxtpx:power>{power}</gpxtpx:power>".format(power=power)

        if not extension_found:
            return ""

        #Compose return string
        ret = """<extensions>
        <gpxtpx:TrackPointExtension>
            {hrext}""".format(hrext=hr_ext)

        if tmp_ext != "":
            ret += """
            {tmpext}""".format(tmpext=tmp_ext)

        if pow_ext != "":
            ret += """
            {powext}""".format(powext=pow_ext)

        if cad_ext != "":
            ret += """
            {cadext}""".format(cadext=cad_ext)

        ret += """
        </gpxtpx:TrackPointExtension>
    </extensions>"""

        return ret


    def __parse_trackpoint(self, trackpoint):
        latitude = None
        longitude = None
        altitude = None
        speed = None
        hr = None
        cadence = None
        power = None
        temperature = None
        inttime = None
        distance = None
        s = None

        self.__nb_trackpoints_parsed += 1   #One more trackpoint parsed
        #Print a dot for every 100 trackpoint, as a progress bar
        if self.__nb_trackpoints_parsed % 100 == 0:
            sys.stdout.write(".")
            if self.__nb_trackpoints_parsed % (80*100) == 0:
                sys.stdout.write("\n")

        #Analyse trackpoint data
        #The ACT file uses commas instead of points in several values,
        #that's why so many replace() are needed
        for node in child_elements(trackpoint):
            key = node.tagName
            if key.lower() == "latitude":
                latitude = float(node.firstChild.nodeValue.replace(',', '.'))

            if key.lower() == "longitude":
                longitude = float(node.firstChild.nodeValue.replace(',', '.'))

            if key.lower() == "intervaltime":
                inttime = float(node.firstChild.nodeValue.replace(',', '.'))

            if key.lower() == "altitude":
                if self.__noalti:
                    altitude = 0
                elif self.__altibaro:
                    altitude = node.firstChild.nodeValue

            if key.lower() == "speed":
                speed = float(node.firstChild.nodeValue.replace(',', '.'))

            if key.lower() == "heartrate":
                #self.__hr = int((float(node.firstChild.nodeValue))*60+0.5)
                hr = int(node.firstChild.nodeValue)

            if key.lower() == "cadence":
                cadence = int(node.firstChild.nodeValue)

            if key.lower() == "power":
                power = int(node.firstChild.nodeValue)

            if key.lower() == "temperature":
                temperature = float(node.firstChild.nodeValue)-273

        #Timestamp is an increment from the previous trackpoint
        self.__time += timedelta(milliseconds=inttime*1000)
        s = self.__time.strftime("%Y-%m-%dT%H:%M:%SZ")

        #Format output
        if latitude != None and longitude != None:
            print >>self.__outputfile, """
<trkpt lat="{latitude}" lon="{longitude}"><ele>{altitude}</ele><time>{time}</time><speed>{speed}</speed>
    {extension}
</trkpt>
""".format(latitude=latitude, longitude=longitude, altitude=altitude, time=s, speed=speed, extension=self.extension(hr, temperature, cadence, power))


    def __parse_trackpoints(self, trackpoints):
        for node in child_elements(trackpoints):
            key = node.tagName

            #At first, we should get the start date/time
            if self.__time == None:
                if key.lower() == "trackmaster":
                    sTmp = ""
                    for tm in child_elements(node):
                        if tm.tagName.lower() == "trackname":
                            sTmp = tm.firstChild.nodeValue
                        if tm.tagName.lower() == "starttime":
                            sTmp = sTmp + ' ' + tm.firstChild.nodeValue
                    self.__time = parser.parse(sTmp)

            #Now let's get those trackpoints
            if key.lower() == "trackpoints":
                self.__parse_trackpoint(node)


    def execute(self):
        #Write GPX header
        #Creator set to Garmin Edge 800 so that Strava accepts
        # barometric altitude datae
        print >>self.__outputfile, '<?xml version="1.0" encoding="UTF-8" standalone="no" ?>'
        print >>self.__outputfile, """
<gpx version="1.1"
creator="Garmin Edge 800"
xmlns="http://www.topografix.com/GPX/1/1"
xmlns:gpxtpx="http://www.garmin.com/xmlschemas/TrackPointExtension/v1"
xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
xsi:schemaLocation="http://www.topografix.com/GPX/1/1 http://www.topografix.com/GPX/1/1/gpx.xsd">

  <metadata>
    <link href="https://github.com/kgkilo/act2gpx">
      <text>Act2GPX</text>
    </link>
  </metadata>

  <trk>
    <trkseg>
"""
#creator="act2gpx" version="1.0"

        #Parse ACT file
        root = self.__root
        for node in child_elements(root):
            key = node.tagName
            if key.lower() == "globalsat_gb580":
                self.__parse_trackpoints(node)

        #Finish writing GPX file
        print >>self.__outputfile,"""
    </trkseg>
  </trk>
</gpx>
"""


def usage():
    print """
act2gpx [--noalti] [--altibaro] [--noext] [--nopower] [--notemp] filename
Creates a file filename.gpx in GPX format from filename in Sportek TTS .act XML format.
If option --noalti is given, elevation will be set to zero.
If option --altibaro is given, elevation is retrieved from altibaro information. The default is to retrieve GPS elevation information.
If option --noext is given, extended data (hr, temperature, cadence, power) will not generated. Useful for instance if size of output file matters.
If option --nopower is given, power data will not be inserted in the extended dataset.
"""

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], "ha", ["help", "noalti", "altibaro", "noext", "nopower", "notemp"])
    except getopt.GetoptError, err:
        # print help information and exit:
        print str(err) # will print something like "option -a not recognized"
        usage()
        sys.exit(2)

    if len(sys.argv[1:]) == 0:
        usage()
        sys.exit(2)

    #Parse command-line options
    output = None
    verbose = False
    noalti = False
    altibaro = True #False
    noext = False
    nopower = False
    notemp = False
    for o, a in opts:
        if o in ("-h", "--help"):
            usage()
            sys.exit()
        elif o in ("-n", "--noalti"):
            noalti = True
        elif o in ("-a", "--altibaro"):
            altibaro = True
        elif o in ("--noext"):
            noext = True
        elif o in ("--nopower"):
            nopower = True
        elif o in ("--notemp"):
            notemp = True
        else:
            assert False, "unhandled option"

    filename = args[0]
    (root_filename, ext) = os.path.splitext(filename)
    if (ext == ""):
        filename += ".xml"
    if (not os.path.exists(filename)):
        print >>sys.stderr, "File {0} doesn't exist".format(filename)
        sys.exit()
    file = open(filename)
    file.readline() # Skip first line
    file_contents = file.read()
    file.close()

    print "Parsing file {0}".format(filename)
    doc = xml.dom.minidom.parseString('<?xml version="1.0" encoding="utf-8"?><top>' + file_contents + '</top>')
    assert doc != None
    top = doc.getElementsByTagName('top')
    assert len(top) == 1
    print "Done."

    output_filename = root_filename + '.gpx'
    output_file = open(output_filename, 'w')
    print "Creating file {0}".format(output_filename)
    ActXMLParser(top[0], noalti, altibaro, noext, nopower, notemp, output_file).execute()
    output_file.close()
    print "\nDone."

if __name__ == "__main__":
    main()
