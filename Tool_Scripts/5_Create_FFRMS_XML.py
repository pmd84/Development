"""
Script documentation

- Tool parameters are accessed using arcpy.GetParameter() or 
                                     arcpy.GetParameterAsText()
- Update derived parameter values using arcpy.SetParameter() or
                                        arcpy.SetParameterAsText()
"""
import arcpy
import arcpy
from sys import argv
import os
import json
import requests
from arcpy import env
from arcpy.sa import *
import xml.etree.ElementTree as ET
import glob
import sys
import shutil


def Check_Source_Data(Tool_Template_Folder):
    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("##### Checking Source Data in Tool Template Files Folder #####")

    #If no Tool_Template_Files folder is provided, use Stantec server location
    if Tool_Template_Folder == "" or Tool_Template_Folder == None:
        Tool_Template_Folder = r"\\us0525-ppfss01\shared_projects\203432303012\FFRMS_Zone3\tools\Tool_Template_Files"
        arcpy.AddMessage("No Tool Template Files location provided, using location on Stantec Server: {0}".format(Tool_Template_Folder))
    
    #Check to see if Tool_Template_Folder exists
    if not os.path.exists(Tool_Template_Folder):
        arcpy.AddError("Tool Template Files folder does not exist at provided lcoation Stantec Server. Please manually provide path to Tool Template Files folder and try again")
        sys.exit()
    else:
        arcpy.AddMessage("Tool Template Files folder found")
    
    #Define paths for template data
    HUC8_Shapefile = os.path.join(Tool_Template_Folder, "STARRII_FFRMS_HUC8s_Scope.shp")
    XML_template_file = os.path.join(Tool_Template_Folder, "XXXXXC_STARRII_FFRMS_metadata_template.xml")

    #Check or existence of template data
    for files in [HUC8_Shapefile, XML_template_file]:
        if not os.path.exists(files):
            arcpy.AddError("No {0} found in Tool Template Files folder. Please manually add {0} to Tool Template Files folder and try again".format(os.path.basename(files)))
            sys.exit()
        else:
            arcpy.AddMessage("{0} found".format(os.path.basename(files)))
    
    return HUC8_Shapefile, XML_template_file

def Copy_Template_XML_to_County_Folder(FFRMS_Geodatabase, XML_template_file, FIPS_CODE):
    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("##### Copying XML Template to County Folder #####")
    
    # Set new XML file name
    FFRMS_GDB_Name_Parts = os.path.basename(FFRMS_Geodatabase).split("_")
    riv_or_cst = FFRMS_GDB_Name_Parts[-1][:3]
    Output_Folder = os.path.dirname(os.path.dirname(FFRMS_Geodatabase))
    County_XML = os.path.join(Output_Folder, "{0}_FFRMS_metadata_{1}.xml".format(FIPS_CODE, riv_or_cst))

    # Copy the XML file using OS
    arcpy.AddMessage("Copying XML file to FFRMS County folder location: {0}".format(County_XML))
    shutil.copyfile(XML_template_file, County_XML)

    return County_XML
    
def Get_County_Info(FFRMS_Geodatabase, XML_data_replacements):
    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("##### Gathering County info from FFRMS_Geodatabase #####")
    #Get the FEMA_Date from the PUB_DATE field from L_Source_Cit where SOURCE_CIT field = "STUDY1"
    L_Source_Cit = os.path.join(FFRMS_Geodatabase, "L_Source_Cit")
    with arcpy.da.SearchCursor(L_Source_Cit, ["SOURCE_CIT", "PUB_DATE", "TITLE"]) as cursor:
        for row in cursor:
            if row[0] == "STUDY1":
                FEMA_DATE = row[1]
                break

    #convert FEMA_DATE from form MM/DD/YYYY to YYYYMMDD
    MM= FEMA_DATE.split("/")[0]
    DD= FEMA_DATE.split("/")[1]
    YYYY= FEMA_DATE.split("/")[2]
    PUBLICATION_DATE =YYYY+MM+DD
    arcpy.AddMessage("Publication Date: {0}".format(PUBLICATION_DATE))

    #Split geodatabase name apart to get county info
    FFRMS_GDB_Name_Parts = os.path.basename(FFRMS_Geodatabase).split("_")

    #Get County Name from FFRMS_GDB_Name_Parts
    COUNTY_ALL_CAPS = " ".join(FFRMS_GDB_Name_Parts[:-3])
    COUNTY_TITLE_CASE = COUNTY_ALL_CAPS.title()
    arcpy.AddMessage("County: {0}".format(COUNTY_TITLE_CASE))

    #Get State_Abrv and Full  Namefrom FFRMS_GDB_Name_Parts
    STATE_ABRV = FFRMS_GDB_Name_Parts[-3]
    state_name_abrv_dict = {"Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR", "California": "CA",
                            "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE", "Florida": "FL", "Georgia": "GA",
                            "Hawaii": "HI", "Idaho": "ID", "Illinois": "IL", "Indiana": "IN", "Iowa": "IA",
                            "Kansas": "KS", "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME", "Maryland": "MD",
                            "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN", "Mississippi": "MS",
                            "Missouri": "MO", "Montana": "MT", "Nebraska": "NE", "Nevada": "NV", "New Hampshire": "NH",
                            "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY", "North Carolina": "NC",
                            "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK", "Oregon": "OR", "Pennsylvania": "PA",
                            "Rhode Island": "RI", "South Carolina": "SC", "South Dakota": "SD", "Tennessee": "TN",
                            "Texas": "TX", "Utah": "UT", "Vermont": "VT", "Virginia": "VA", "Washington": "WA",
                            "West Virginia": "WV", "Wisconsin": "WI", "Wyoming": "WY", "American Samoa": "AS",
                            "Guam": "GU", "Puerto Rico": "PR", "Virgin Islands": "VI", 
                            "Northern Mariana Islands": "MP", "Federated States of Micronesia": "FM", 
                            "Marshall Islands": "MH", "District of Columbia": "DC"}

    state_abrv_name_dict = {v: k for k, v in state_name_abrv_dict.items()} #Reverse name_dict to get state name from abrv
    STATE_FULL_NAME = state_abrv_name_dict[STATE_ABRV]
    arcpy.AddMessage("State: {0}".format(STATE_FULL_NAME))
    
    #Get Riverine or Coastal from FFRMS_GDB_Name_Parts
    riv_or_cst = FFRMS_GDB_Name_Parts[-1]
    if riv_or_cst[:3] == "RIV":
        RIVERINE_OR_COASTAL = "Riverine"
    elif riv_or_cst[:3] == "CST":
        RIVERINE_OR_COASTAL = "Coastal"
    arcpy.AddMessage("FFRMS type: {0}".format(RIVERINE_OR_COASTAL))

    #Get FEMA Region from state abrv
    FEMA_region_dict = {'10': ['WA', 'AK', 'OR', 'ID'], 
                    '9':['CA', 'NV', 'AZ', 'HI', 'GU', 'AS', 'MP', 'FM', 'MH'], 
                    '8': ['UT', 'CO', 'WY', 'MT', 'ND', 'SD'], 
                    '7': ['NE', 'KS', 'IA', 'MO'], 
                    '6':['TX', 'OK', 'AR', 'LA', 'NM'], 
                    '5':['WI', 'IL', 'IN', 'MI', 'OH', 'MN'], 
                    '4':['TN', 'KY', 'MS', 'AL', 'GA', 'FL', 'SC', 'NC'], 
                    '3':['WV', 'VA', 'MD', 'DE', 'PA', 'DC'], 
                    '2':['NY', 'NJ', 'PR', 'VI'], 
                    '1':['VT', 'NH', 'ME', 'MA', 'CT', 'RI']}
    for FEMA_region, states in FEMA_region_dict.items():
        if STATE_ABRV in states:
            FEMA_REGION = FEMA_region
            break
    arcpy.AddMessage("FEMA Region: {0}".format(FEMA_REGION))

    #Get UTM code and FIPS code from S_FFRMS_Proj_Ar
    S_FFRMS_Proj_Ar = os.path.join(FFRMS_Geodatabase, "S_FFRMS_Proj_Ar")
    with arcpy.da.SearchCursor(S_FFRMS_Proj_Ar, ["PROJ_ZONE", "FIPS"]) as cursor:
        for row in cursor:
            UTM_ZONE = row[0]
            FIPS_CODE = row[1]
            break
    FIPS_CODE = FIPS_CODE[:5]

    arcpy.AddMessage("UTM Zone: {0}".format(UTM_ZONE))
    arcpy.AddMessage("FIPS Code: {0}".format(FIPS_CODE))

    #Remove 'N' if it's in the UTM zone
    if 'N' in UTM_ZONE:
        UTM_ZONE = UTM_ZONE[:-1]

    # UTM_Long_CM_dict = {"1":"-177", 
    #            "2":"-171", 
    #            "3":"-165", 
    #            "4":"-159", 
    #            "5":"-153", 
    #            "6":"-147", 
    #            "7":"-141", 
    #            "8":"-135", 
    #            "9":"-129", 
    #            "10":"-123", 
    #            "11":"-117", 
    #            "12":"-111", 
    #            "13":"-105", 
    #            "14":"-99", 
    #            "15":"-93", 
    #            "16":"-87", 
    #            "17":"-81", 
    #            "18":"-75", 
    #            "19":"-69", 
    #            "20":"-63",
    #            "55": "147"}
    
    #Determines the UTM Central Meridian, starting with UTM 1N as -177 and adding 6 degrees for each zone
    UTM_Long_CM_dict = {str(i): str(-177 + (i-1)*6) for i in range(1, 61)}

    UTM_ZONE_CENTRAL_MERIDIAN = UTM_Long_CM_dict[UTM_ZONE]

    XML_data_replacements['COUNTY_TITLE_CASE'] = COUNTY_TITLE_CASE
    XML_data_replacements['STATE_ABRV'] = STATE_ABRV
    XML_data_replacements['PUBLICATION_DATE'] = PUBLICATION_DATE
    XML_data_replacements['COUNTY_ALL_CAPS'] = COUNTY_ALL_CAPS
    XML_data_replacements['RIVERINE_OR_COASTAL'] = RIVERINE_OR_COASTAL
    XML_data_replacements['STATE_FULL_NAME'] = STATE_FULL_NAME
    XML_data_replacements['FEMA_REGION'] = FEMA_REGION
    XML_data_replacements['UTM_ZONE'] = UTM_ZONE
    XML_data_replacements['UTM_ZONE_CENTRAL_MERIDIAN'] = UTM_ZONE_CENTRAL_MERIDIAN
    XML_data_replacements['FIPS_CODE'] = FIPS_CODE

    return XML_data_replacements, FIPS_CODE, RIVERINE_OR_COASTAL

def Get_Project_Extents(FFRMS_Geodatabase, XML_data_replacements):
    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("##### Gathering Project Extents #####")

    #Get the S_FFRMS_Proj_Ar shapefile from the FFRMS geodatabase
    S_FFRMS_Proj_Ar = os.path.join(FFRMS_Geodatabase, "S_FFRMS_Proj_Ar")     

    #Project S_FFRMS_Proj_Ar to WSG84
    S_FFRMS_Proj_Ar_WGS84 = os.path.join(FFRMS_Geodatabase, "S_FFRMS_Proj_Ar_WGS84")
    arcpy.AddMessage("Projecting S_FFRMS_Proj_Ar to WSG84 to determine Project Extents in Decimal Degrees")
    arcpy.Project_management(S_FFRMS_Proj_Ar, S_FFRMS_Proj_Ar_WGS84, 4326)

    County_Y_Max_84 = str(round(arcpy.Describe(S_FFRMS_Proj_Ar_WGS84).extent.YMax,1))
    County_Y_min_84 = str(round(arcpy.Describe(S_FFRMS_Proj_Ar_WGS84).extent.YMin,1))
    County_X_Max_84 = str(round(arcpy.Describe(S_FFRMS_Proj_Ar_WGS84).extent.XMax,1))
    County_X_min_84 = str(round(arcpy.Describe(S_FFRMS_Proj_Ar_WGS84).extent.XMin,1))

    #delete projected file
    arcpy.Delete_management(S_FFRMS_Proj_Ar_WGS84)

    XML_data_replacements['WEST_DD'] = County_X_min_84
    XML_data_replacements['EAST_DD'] = County_X_Max_84
    XML_data_replacements['NORTH_DD'] = County_Y_Max_84
    XML_data_replacements['SOUTH_DD'] = County_Y_min_84

    arcpy.AddMessage("County Extents in Decimal Degrees:")
    arcpy.AddMessage("Western Limit {0}".format(County_X_min_84))
    arcpy.AddMessage("Eastern Limit {0}".format(County_X_Max_84))
    arcpy.AddMessage("Northern Limit {0}".format(County_Y_Max_84))
    arcpy.AddMessage("Southern Limit {0}".format(County_Y_min_84))

    return XML_data_replacements

    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("##### Getting HUC8 Information for County #####")

    #loop through Tool_Output_Folders (by HUC8)
    HUC8_dict = {}
    for output_folder in Tool_Output_Folders:
        HUC8 = os.path.basename(output_folder)
        arcpy.AddMessage("Getting HUC8 information for {0}".format(HUC8))
        
        #loop through all files in the output folder and find the HUC8 shapefile by starts with "HUC" and ends with ".shp"
        for root, dirs, files in os.walk(output_folder):
            for file in files:
                if file.startswith("HUC") and file.endswith(".shp"):
                    HUC8_shapefile = os.path.join(root, file)
                    arcpy.AddMessage("HUC8 shapefile: {0}".format(HUC8_shapefile))
                    break

    #use search cursor to get the first entry in the "huc8" field of the HUC8 shapefile
        HUC8_number = next(row[0] for row in arcpy.da.SearchCursor(HUC8_shapefile, "huc8"))
        HUC8_name = next(row[0] for row in arcpy.da.SearchCursor(HUC8_shapefile, "name"))
        arcpy.AddMessage("HUC8 number: {0}".format(HUC8_number))
        arcpy.AddMessage("HUC8 name: {0}".format(HUC8_name))

        HUC8_dict[HUC8_number] = HUC8_name

    return HUC8_dict

def Get_All_HUC8s_in_County(FFRMS_Geodatabase, HUC8_Shapefile):
    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("##### Getting HUC8 Information for County #####")    
    
    #Get the S_FFRMS_Proj_Ar shapefile from the FFRMS geodatabase
    arcpy.AddMessage("Getting the S_FFRMS_Proj_Ar shapefile from the FFRMS geodatabase")
    S_FFRMS_Proj_Ar = os.path.join(FFRMS_Geodatabase, "S_FFRMS_Proj_Ar")

    #Intersect the S_FFRMS_Proj_Ar shapefile with the HUC8 shapefile
    arcpy.AddMessage("Intersecting the S_FFRMS_Proj_Ar shapefile with the HUC8 shapefile")

    County_HUC8s= r"in_memory/County_HUC8s"
    #County_HUC8s = os.path.join(FFRMS_Geodatabase, "County_HUC8s")

    #Execute Intersect
    arcpy.Intersect_analysis([S_FFRMS_Proj_Ar, HUC8_Shapefile], County_HUC8s, "ALL", "", "INPUT")

    #create_HUC8_dictionary by searching through all elements of County_HUC8s, adding the HUC8 number and name to the dictionary
    HUC8_dict = {}
    with arcpy.da.SearchCursor(County_HUC8s, ["huc8", "name"]) as cursor:
        for row in cursor:
            HUC8_dict[row[0]] = row[1]

    #make sure huc8_dict is sorted in order of key number in ascending order
    HUC8_dict = dict(sorted(HUC8_dict.items(), key=lambda item: item[0]))
    
    arcpy.AddMessage("HUC8s within county: {0}".format(HUC8_dict))
    return HUC8_dict, County_HUC8s

def Update_HUC8_Place_Tags(filename, HUC8_dict):
    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("##### Updating XML HUC8 Placetags #####")
    
    # Parse the XML file
    tree = ET.parse(filename)
    root = tree.getroot()

    # Find the <place> element
    place_element = root.find('.//place')
    if not place_element:
        arcpy.AddMessage("No <place> element found")
        return

    #Loop through Placekeys, find the HUC8s and remove them, set index position for inserting new HUC8 tags
    for index, placekey in enumerate(place_element.findall('placekey')):
        if 'FEMA-CID' in placekey.text:
            HUC_unit_position = index+1
        if 'HYDROLOGIC UNIT' in placekey.text:
            place_element.remove(placekey)

    # Add HUC8 values after FEMA-CID
    if HUC_unit_position is not None:
        for number, name in HUC8_dict.items():
            #Set text for HUC8 Number
            hydrologic_unit_element = ET.Element('placekey')
            hydrologic_unit_element.text = 'HYDROLOGIC UNIT {0}'.format(number)
            #Set text for HUC8 Name
            name_element = ET.Element('placekey')
            name_element.text = name

            # Insert the elements after FEMA-CID
            place_element.insert(HUC_unit_position + 1, hydrologic_unit_element)
            place_element.insert(HUC_unit_position + 2, name_element)
            
            HUC_unit_position += 2
    
    write_xml(root, tree, County_XML)
    
    return

def Get_Raster_Info(FFRMS_Geodatabase, County_XML, XML_data_replacements):
    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("##### Getting Raster Information for County #####")

    arcpy.env.workspace = FFRMS_Geodatabase
    raster_names = arcpy.ListRasters()
    raster_count = len(raster_names)
    arcpy.AddMessage("Found {0} FVA rasters".format(raster_count))
    
    FVA_RASTER_NAME_0_2PCT=""
    for raster in raster_names:
        if "00FVA" in raster:
            FVA_RASTER_NAME_00 = raster
            XML_data_replacements['FVA_RASTER_NAME_00'] = FVA_RASTER_NAME_00
            arcpy.AddMessage("FVA00 RASTER: {0}".format(FVA_RASTER_NAME_00))
        if "01FVA" in raster:
            FVA_RASTER_NAME_01 = raster
            XML_data_replacements['FVA_RASTER_NAME_01'] = FVA_RASTER_NAME_01
            arcpy.AddMessage("FVA01 RASTER: {0}".format(FVA_RASTER_NAME_01))
        if "02FVA" in raster:
            FVA_RASTER_NAME_02 = raster
            XML_data_replacements['FVA_RASTER_NAME_02'] = FVA_RASTER_NAME_02
            arcpy.AddMessage("FVA02 RASTER: {0}".format(FVA_RASTER_NAME_02))
        if "03FVA" in raster:
            FVA_RASTER_NAME_03 = raster
            XML_data_replacements['FVA_RASTER_NAME_03'] = FVA_RASTER_NAME_03
            arcpy.AddMessage("FVA03 RASTER: {0}".format(FVA_RASTER_NAME_03))
        if "0_2PCT" in raster:
            FVA_RASTER_NAME_0_2PCT = raster
            XML_data_replacements['FVA_RASTER_NAME_0_2PCT'] = FVA_RASTER_NAME_0_2PCT
            arcpy.AddMessage("0_2PCT RASTER: {0}".format(FVA_RASTER_NAME_0_2PCT))

    # Remove 0_2PCT from XML if raster is not found        
    if FVA_RASTER_NAME_0_2PCT == "":
        arcpy.AddMessage(r"0_2PCT raster not found - removing 0.2% raster references in XML")

        tree = ET.parse(County_XML)
        root = tree.getroot()

        # Remove 0_2PCT <crossref> element
        for crossref in root.findall('.//crossref'):
            title = crossref.find('citeinfo/title')
            if title is not None and "Annual Chance" in title.text:
                for idinfo in root.findall('.//idinfo'):
                    if crossref in idinfo:
                        idinfo.remove(crossref)

        # Remove 0_2PCT from eainfo tag
        for eainfo in root.findall('.//eainfo'):
            for detailed in eainfo.findall('detailed'):
                enttypl = detailed.find('enttyp/enttypl')
                if enttypl is not None and enttypl.text == '[FVA_RASTER_NAME_0_2PCT]':
                    eainfo.remove(detailed)
        
        # Remove 0_2PCT from eadetcit tag
        for eadetcit in root.findall('.//eadetcit'):
            eadetcit.text = eadetcit.text.replace('[FVA_RASTER_NAME_0_2PCT]', '')

        write_xml(root, tree, County_XML)

    return XML_data_replacements
        
def indent_XML(elem, level=0):
    """Add whitespace to the XML to make it pretty."""
    i = "\n" + level*"  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
        for elem in elem:
            indent_XML(elem, level+1)
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i

def write_xml(root, tree, County_XML):
    #Make the XML pretty
    indent_XML(root)

    # Save the updated XML back to the same file
    with open(County_XML, 'wb') as f:
        f.write(b'<?xml version="1.0" encoding="utf-8"?>\n')
        tree.write(f, encoding='utf-8', xml_declaration=False)

def Update_XML_with_Replacement_Keys(County_XML, XML_data_replacements):
    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("##### Updating XML with County Info #####")
    # Parse the XML
    tree = ET.parse(County_XML)
    root = tree.getroot()

    # Recursive function to traverse and replace placeholders
    def traverse_and_replace(element):
        if element.text:
            for placeholder, value in XML_data_replacements.items():
                element.text = element.text.replace("[{}]".format(placeholder), str(value))
        for child in element:
            traverse_and_replace(child)

    # Call the recursive function starting from the root
    traverse_and_replace(root)

    #Write the XML
    write_xml(root, tree, County_XML)

if __name__ == "__main__":

    FFRMS_Geodatabase = arcpy.GetParameterAsText(0)
    Tool_Template_Folder = arcpy.GetParameterAsText(1)
    
    # Set the workspace
    arcpy.env.workspace = FFRMS_Geodatabase
    arcpy.env.overwriteOutput = True
    Output_folder = os.path.dirname(FFRMS_Geodatabase)

    #Check if XML_template_file and HUC8_Shapefile are provided
    HUC8_Shapefile, XML_template_file =  Check_Source_Data(Tool_Template_Folder)
    
    #Initialize XML_data_replacements dictionary
    XML_data_replacements = {}
    XML_data_replacements['PROGRESS'] = "Complete"

    #Get the production date and county name info from FFRMS Geodatabase and L_Source_Cit 
    XML_data_replacements, FIPS_CODE, RIVERINE_OR_COASTAL = Get_County_Info(FFRMS_Geodatabase, XML_data_replacements)

    #Copy template XML to county folder
    County_XML = Copy_Template_XML_to_County_Folder(FFRMS_Geodatabase, XML_template_file, FIPS_CODE)

    #Add max NESW extents in degrees to XML replacements
    XML_data_replacements = Get_Project_Extents(FFRMS_Geodatabase, XML_data_replacements)

    #Use HUC8 shapefile to determine all HUC8 numbers and names within the county
    HUC8_dict, County_HUC8s = Get_All_HUC8s_in_County(FFRMS_Geodatabase, HUC8_Shapefile)

    #Update HUC8 place tags in XML
    Update_HUC8_Place_Tags(County_XML, HUC8_dict)

    #Get Raster names, and remove 0.2% references in XML if no 500-year floodplain exists
    XML_data_replacements = Get_Raster_Info(FFRMS_Geodatabase, County_XML, XML_data_replacements)

    #Update the XML file with the replacements
    Update_XML_with_Replacement_Keys(County_XML, XML_data_replacements)



               	


