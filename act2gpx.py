'''
Convert a GlobalSat GB-580 .ACT file to a GPX file, including extensions.

Original idea from:
    https://code.google.com/p/ambit2gpx/source/browse/src/ambit2gpx.py
'''

import os
import xml.dom.minidom
import getopt
import sys
from dateutil import parser #needs python-dateutil on Ubuntu
from datetime import timedelta


def child_elements(parent):
    '''Returns a list of child elements of a node of an XML structure'''
    elements = []
    for child in parent.childNodes:
        if child.nodeType != child.ELEMENT_NODE:
            continue
        elements.append(child)
    return elements


class ActXMLParser(object):
    '''The main converter class'''

    def __init__(self, xml_node, opts, output_file):
        assert isinstance(xml_node, xml.dom.Node)
        assert xml_node.nodeType == xml_node.ELEMENT_NODE
        self.__root = xml_node
        self.__outputfile = output_file
        self.__time =  None
        self.__opts = opts
        self.__nb_trackpoints_parsed = 0


    def extension(self, heartrate, temperature, cadence, power):
        '''Compiles the GPX extension part of a trackpoint'''
        if self.__opts['noext']:
            return ""

        extension_found = False

        hr_ext = ""
        if (heartrate is not None):
            extension_found = True
            hr_ext = "<gpxtpx:hr>{hr}</gpxtpx:hr>".format(hr=heartrate)

        tmp_ext = ""
        if ((not self.__opts['notemp']) and (temperature is not None)):
            extension_found = True
            tmp_ext = "<gpxtpx:atemp>{temp}</gpxtpx:atemp>".format(
                                                    temp=temperature)

        cad_ext = ""
        if (cadence is not None):
            extension_found = True
            cad_ext = "<gpxtpx:cad>{cadence}</gpxtpx:cad>".format(
                                                    cadence=cadence)

        pow_ext = ""
        if ((not self.__opts['nopower']) and (power is not None)):
            extension_found = True
            pow_ext = "<gpxtpx:power>{power}</gpxtpx:power>".format(
                                                    power=power)

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


# pylint: disable=R0912
#Too many branches
    def __parse_trackpoint(self, trackpoint):
        '''Parse one trackpoint from the ACT file
            and write the appropriate GPX line'''
        latitude = None
        longitude = None
        altitude = None
        speed = None
        heartrate = None
        cadence = None
        power = None
        temperature = None
        inttime = None
        timestamp = None

        self.__nb_trackpoints_parsed += 1   #One more trackpoint parsed
        #Progress bar: print a dot for every 100 trackpoint
        if self.__nb_trackpoints_parsed % 100 == 0:
            sys.stdout.write(".")
            if self.__nb_trackpoints_parsed % (80*100) == 0:
                sys.stdout.write("\n")

        #Analyse trackpoint data
        #The ACT file uses commas instead of points in several values,
        #that's why so many replace() are needed
        for node in child_elements(trackpoint):
            key = node.tagName
            val = node.firstChild.nodeValue.replace(',', '.')

            if key.lower() == "latitude":
                latitude = float(val)

            if key.lower() == "longitude":
                longitude = float(val)

            if key.lower() == "intervaltime":
                inttime = float(val)

            if key.lower() == "altitude":
                if self.__opts['noalti']:
                    altitude = 0
                elif self.__opts['altibaro']:
                    altitude = int(val)

            if key.lower() == "speed":
                speed = float(val)

            if key.lower() == "heartrate":
                #heartrate = int((float(val)) * 60 + 0.5)
                heartrate = int(val)

            if key.lower() == "cadence":
                cadence = int(val)

            if key.lower() == "power":
                power = int(val)

            if key.lower() == "temperature":
                temperature = float(val) - 273

        #Timestamp is an increment from the previous trackpoint
        self.__time += timedelta(milliseconds = inttime * 1000)
        timestamp = self.__time.strftime("%Y-%m-%dT%H:%M:%SZ")

        #Format output
        if latitude is not None and longitude is not None:
            print >> self.__outputfile, """
<trkpt lat="{latitude}" lon="{longitude}"><ele>{altitude}</ele><time>{time}</time><speed>{speed}</speed>
    {extension}
</trkpt>
""".format(latitude=latitude, longitude=longitude, altitude=altitude,
            time=timestamp, speed=speed,
            extension=self.extension(heartrate, temperature, cadence,
                                     power))


    def __parse_trackpoints(self, trackpoints):
        '''Parse all trackpoints from the ACT file'''
        for node in child_elements(trackpoints):
            key = node.tagName

            #At first, we should get the start date/time
            if self.__time is None:
                if key.lower() == "trackmaster":
                    start_time = ""
                    for tm_node in child_elements(node):
                        if tm_node.tagName.lower() == "trackname":
                            start_time = tm_node.firstChild.nodeValue
                        if tm_node.tagName.lower() == "starttime":
                            start_time += ' ' \
                                + tm_node.firstChild.nodeValue
                    self.__time = parser.parse(start_time)

            #Now let's get those trackpoints
            if key.lower() == "trackpoints":
                self.__parse_trackpoint(node)


    def execute(self):
        '''Compile the contents of the GPX file'''
        #Write GPX header
        #Creator set to Garmin Edge 800 so that Strava accepts
        # barometric altitude datae
        print >> self.__outputfile, \
            '<?xml version="1.0" encoding="UTF-8" standalone="no" ?>'
        print >> self.__outputfile, """
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
        print >> self.__outputfile,"""
    </trkseg>
  </trk>
</gpx>
"""


def usage():
    '''Prints default usage help'''
    print """
act2gpx [--noalti] [--altibaro] [--noext] [--nopower] [--notemp] filename
Creates a file filename.gpx in GPX format from filename in Sportek TTS .act XML format.
If option --noalti is given, elevation will be set to zero.
If option --altibaro is given, elevation is retrieved from altibaro information. The default is to retrieve GPS elevation information.
If option --noext is given, extended data (heartrate, temperature, cadence, power) will not generated. Useful for instance if size of output file matters.
If option --nopower is given, power data will not be inserted in the extended dataset.
"""


def read_input_file(filename):
    '''Reads the contents of the input file'''
    input_file = open(filename)
    input_file.readline() # Skip first line
    file_contents = input_file.read()
    input_file.close()
    return file_contents


def write_output_file(root_filename, top_node, opts):
    '''Writes the top_node tree into a GPX file'''
    output_filename = root_filename + '.gpx'
    output_file = open(output_filename, 'w')
    print "Creating file {0}".format(output_filename)
    ActXMLParser(top_node[0], opts, output_file).execute()
    output_file.close()


def parse_act_file(file_contents):
    '''Parses the contents of the ACT file and returns it'''
    doc = xml.dom.minidom.parseString(
                        '<?xml version="1.0" encoding="utf-8"?><top>'
                        + file_contents + '</top>')
    assert doc is not None
    top = doc.getElementsByTagName('top')
    assert len(top) == 1
    return top


# pylint: disable=W0612
#Unused variable (arg)
def main():
    '''Erm.. main...'''

    try:
        ops, args = getopt.getopt(sys.argv[1:],
            "ha",
            ["help", "noalti", "altibaro", "noext",
            "nopower", "notemp"])
    except getopt.GetoptError, err:
        # print help information and exit:
        print str(err) # will print something like "option -a not recognized"
        usage()
        sys.exit(2)

    if not sys.argv[1:]:
        usage()
        sys.exit(2)

    #Parse command-line options
    opts = {'noalti':False,
            'altibaro':True,
            'noext':False,
            'nopower':False,
            'notemp':False}

    for option, arg in ops:
        if option in ("-h", "--help"):
            usage()
            sys.exit()
        elif option in ("-n", "--noalti"):
            opts['noalti'] = True
        elif option in ("-a", "--altibaro"):
            opts['altibaro'] = True
        elif option in ("--noext"):
            opts['noext'] = True
        elif option in ("--nopower"):
            opts['nopower'] = True
        elif option in ("--notemp"):
            opts['notemp'] = True
        else:
            assert False, "unhandled option"

    #Read input ACT file
    filename = args[0]
    (root_filename, ext) = os.path.splitext(filename)
    if (ext == ""):
        filename += ".xml"
    if (not os.path.exists(filename)):
        print >> sys.stderr, "File {0} doesn't exist".format(filename)
        sys.exit()
    file_contents = read_input_file(filename)

    #Parse ACT file contents
    print "Parsing file {0}".format(filename)
    top = parse_act_file(file_contents)
    print "Done."

    #Write output GPX file
    write_output_file(root_filename, top, opts)
    print "\nDone."

if __name__ == "__main__":
    main()
