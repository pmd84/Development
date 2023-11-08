"""
Script documentation

- Tool parameters are accessed using arcpy.GetParameter() or 
                                     arcpy.GetParameterAsText()
- Update derived parameter values using arcpy.SetParameter() or
                                        arcpy.SetParameterAsText()
"""
import arcpy
import sys
import os

def getFIPScode(FFRMS_Geodatabase):
    #Get FIPS code from geodatabase S_FFRMS_Proj_Ar
    arcpy.AddMessage("Getting FIPS code from S_FFRMS_Proj_Ar")
    S_FFRMS_Proj_Ar = os.path.join(FFRMS_Geodatabase, "S_FFRMS_Proj_Ar")
    with arcpy.da.SearchCursor(S_FFRMS_Proj_Ar, ["PROJ_ZONE", "FIPS"]) as cursor:
        for row in cursor:
            UTM_ZONE = row[0]
            FIPS_code = row[1]
            break
    FIPS_code = FIPS_code[:5]

    return FIPS_code

def getDirectories(FFRMS_Geodatabase, state_abrv, FIPS_code, riv_or_cst):
    #Get/Set directory variables
    geodatabase_dir = os.path.dirname(FFRMS_Geodatabase)
    root_dir = os.path.dirname(geodatabase_dir)

    #Name of folder locations
    raster_dir_name = state_abrv + "_" + FIPS_code + "_Rasters"
    shapefile_dir_name = state_abrv + "_" + FIPS_code + "_Shapefiles"
    if riv_or_cst == "RIV":
        shapefile_subdir_name = "Riverine"
    elif riv_or_cst == "CST":
        shapefile_subdir_name = "Coastal"
    
    #Folder Paths
    raster_dir = os.path.join(root_dir, raster_dir_name)
    shapefile_dir = os.path.join(root_dir, shapefile_dir_name)
    shapefile_subdir = os.path.join(shapefile_dir, shapefile_subdir_name)

    arcpy.AddMessage("Raster Directory: {0}".format(raster_dir))
    arcpy.AddMessage("Shapefile Directory: {0}".format(shapefile_subdir_name))
    
    #Create if not already existing
    for directory in [raster_dir, shapefile_dir, shapefile_subdir]:
        if not os.path.exists(directory):
            arcpy.AddMessage("Creating directory: " + directory)
            os.makedirs(directory)

    return raster_dir, shapefile_dir, shapefile_subdir

def exportRasters(FFRMS_Geodatabase, raster_dir):
    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("##### Exporting Rasters to Standalone Geotiff Files #####") 
    arcpy.AddMessage("Saving Rasters to {0}".format(raster_dir))

    arcpy.env.workspace = FFRMS_Geodatabase

    for gdb_raster in arcpy.ListRasters():
        arcpy.AddMessage("Exporting {0}".format(gdb_raster))
        raster_name = os.path.basename(gdb_raster)
        output_raster_tif = os.path.join(raster_dir, raster_name+".tif")
        arcpy.management.CopyRaster(gdb_raster, output_raster_tif)

    arcpy.AddMessage("Raster Export Complete")

def exportShapefiles(FFRMS_Geodatabase, shapefile_dir):
    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("##### Exporting FFRMS Spatial Layers to Standalone Shapefiles #####")   
    arcpy.AddMessage("Saving shapefiles to {0}".format(shapefile_dir))

    arcpy.env.workspace = os.path.join(FFRMS_Geodatabase, "FFRMS_Spatial_Layers")
    
    for feature_class in arcpy.ListFeatureClasses():
        arcpy.AddMessage("Exporting {0}".format(feature_class))
        feature_class_name = os.path.basename(feature_class)
        output_feature_class = os.path.join(shapefile_dir, feature_class_name+".shp")

        arcpy.env.transferDomains = True if feature_class_name == "S_AOI_Ar" else False

        try:
            arcpy.conversion.ExportFeatures(in_features= feature_class, out_features= output_feature_class)
        except:
            arcpy.AddError("Export Failed for {0} - make sure feature class is not currently open in ArcGIS and try again".format(feature_class_name))
            exit()

        #Populate AOI_TYP and AOI_ISSUE fields with their domain descriptions, so output is not coded
        if "d_AOI_TYP" in [field.name for field in arcpy.ListFields(output_feature_class)]:
                arcpy.management.CalculateField(output_feature_class, "AOI_TYP", "!d_AOI_TYP!", "PYTHON3")
                arcpy.management.DeleteField(output_feature_class, "d_AOI_TYP")
        if "d_AOI_ISSU" in [field.name for field in arcpy.ListFields(output_feature_class)]:
                arcpy.management.CalculateField(output_feature_class, "AOI_ISSUE", "!d_AOI_ISSU!", "PYTHON3")
                arcpy.management.DeleteField(output_feature_class, "d_AOI_ISSU")

    #export L_Source_Cit table to shapefile folder in dbf form
    arcpy.AddMessage("Exporting L_Source_Cit table")
    L_Source_Cit = os.path.join(FFRMS_Geodatabase, "L_Source_Cit")
    arcpy.conversion.TableToTable(L_Source_Cit, shapefile_dir, "L_Source_Cit.dbf")

    arcpy.AddMessage("Shapefile Export Complete")

def checkEraseAreasOutputLocation(FFRMS_Geodatabase, Erase_Areas_Location, FIPS_code, state_abrv, raster_dir, shapefile_dir, shapefile_subdir):
    #export Erase_Areas to Working folder as a shapefile
    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("Checking validity of Erase_Areas export location")

    arcpy.AddMessage("Folder location of FFRMS Geodatabase: {0}".format(os.path.dirname(FFRMS_Geodatabase)))

    #check to see if Erase_Areas location is a folder or geodatabase
    if not arcpy.Exists(Erase_Areas_Location):
        arcpy.AddError("Erase_Areas Export Failed - pick a valid folder location or geodatabase and try again")
        exit()

    #Can't be saved to FFRMS Geodatabase
    if Erase_Areas_Location == FFRMS_Geodatabase:
        arcpy.AddError("Erase_Areas Export Failed - can't choose FFRMS Geodatabase as export location. Please choose another export location and try again.")
        exit()

    #Can't be saved to Raster or Shapefile folder
    if Erase_Areas_Location == shapefile_dir or Erase_Areas_Location == raster_dir or Erase_Areas_Location == shapefile_subdir:
        arcpy.AddError("Erase_Areas Export Failed - can't choose Raster or Shapefile folder as export location. Please choose another export location and try again.")
        exit()

    #Can't be saved to FFRMS Geodatabase parent folder
    if Erase_Areas_Location == os.path.dirname(FFRMS_Geodatabase):
        arcpy.AddError("Erase_Areas Export Failed - can't choose FFRMS Geodatabase parent folder as export location. Please choose another export location and try again.")
        exit()

    #Can't be saved to FFRMS County folder
    if Erase_Areas_Location == os.path.dirname(os.path.dirname(FFRMS_Geodatabase)):
        arcpy.AddError("Erase_Areas Export Failed - can't choose FFRMS County folder as export location. Please choose another export location and try again.")
        exit()

    #check if gdb, choose no extension 
    if os.path.splitext(Erase_Areas_Location)[1] == ".gdb":
        file_extension = ""
    #if the data type is a feature dataset, choose no extension
    elif arcpy.Describe(Erase_Areas_Location).dataType == "FeatureDataset":
        file_extension = ""
    #if the data type is a folder, choose .shp extension
    else:
        file_extension = ".shp"

    #Set file naming convention and location
    Erase_Areas_File = os.path.join(Erase_Areas_Location, "{0}_{1}_Erase_Areas{2}".format(state_abrv, FIPS_code, file_extension))
    arcpy.AddMessage("Erase_Areas export location is valid")
    arcpy.AddMessage("Erase_Areas will be exported to {0}".format(Erase_Areas_File))

    return Erase_Areas_File

def exportEraseAreas(FFRMS_Geodatabase, Erase_Areas_File):
    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("##### Exporting Erase_Areas to Standalone Shapefile #####")

    arcpy.env.workspace = FFRMS_Geodatabase
    
    #Find Erase_Areas feature class
    feature_classes = arcpy.ListFeatureClasses()
    Erase_Areas = None

    for feature_class in arcpy.ListFeatureClasses():
        if "Erase_Areas" in feature_class:
            arcpy.AddMessage("Erase_Areas found in FFRMS Geodatabase")
            Erase_Areas = os.path.join(FFRMS_Geodatabase, feature_class)
            break

    #Check if Erase_Areas is empty
    if Erase_Areas is None:
        arcpy.AddWarning("Erase_Areas Export Failed - no Erase_Areas file found")
        return
            
    arcpy.AddMessage("Exporting Erase_Areas to {0}".format(Erase_Areas_File))

    #Export Erase_Areas
    try:
        arcpy.conversion.ExportFeatures(Erase_Areas, Erase_Areas_File)
    except Exception as e:
        arcpy.AddError("Erase_Areas Export Failed - pick a valid folder location or geodatabase and try again")
        exit()

    #Double check that Erase_Areas was exported before deleting from geodatabase
    if arcpy.Exists(Erase_Areas_File):
        arcpy.AddMessage("Erase_Areas Export Successful")
        arcpy.AddMessage("Deleting Erase_Areas from FFRMS Geodatabase")
        arcpy.management.Delete(Erase_Areas)
    else:
        arcpy.AddError("Erase_Areas Export Failed - pick a valid folder location or geodatabase and try again")
        exit()

    arcpy.AddMessage("Erase_Areas Export Complete")

    
if __name__ == "__main__":

    #Get geodatabase as parameter from script tool
    FFRMS_Geodatabase = arcpy.GetParameterAsText(0)
    Erase_Areas_Location = arcpy.GetParameterAsText(1)
    arcpy.env.overwriteOutput = True
    arcpy.env.transferDomains = False

    #Get state abbreviation from geodatabase name
    Geodatabase_name_parts = FFRMS_Geodatabase.split("_")
    riv_or_cst = Geodatabase_name_parts[-1][:3]
    state_abrv = Geodatabase_name_parts[-3]
    county_all_caps = " ".join(Geodatabase_name_parts[:-3])
    
    #Get Fips Code
    FIPS_code = getFIPScode(FFRMS_Geodatabase)

    #Get export locations
    raster_dir, shapefile_dir, shapefile_subdir = getDirectories(FFRMS_Geodatabase, state_abrv, FIPS_code, riv_or_cst)

    Erase_Areas_File = checkEraseAreasOutputLocation(FFRMS_Geodatabase, Erase_Areas_Location, FIPS_code, state_abrv, raster_dir, shapefile_dir, shapefile_subdir)

    #Export Rasters, Shapefiles, and Erase_Areas
    exportEraseAreas(FFRMS_Geodatabase, Erase_Areas_File)
    exportRasters(FFRMS_Geodatabase, raster_dir)
    exportShapefiles(FFRMS_Geodatabase, shapefile_subdir)
    