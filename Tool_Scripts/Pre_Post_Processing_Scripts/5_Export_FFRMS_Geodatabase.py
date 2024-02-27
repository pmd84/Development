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
from arcpy import AddMessage as msg
from arcpy import AddWarning as wrn

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

        arcpy.env.transferDomains = True if (feature_class_name == "S_AOI_Ar" or feature_class_name == "S_Raster_QC_Pt") else False

        try:
            arcpy.conversion.ExportFeatures(in_features= feature_class, out_features= output_feature_class)
        except Exception as e:
            #try using feature class to feature class tool
            try:
                msg("Export Features Failed - trying Feature Class to Feature Class tool")
                arcpy.conversion.FeatureClassToShapefile(Input_Features=feature_class, Output_Folder=os.path.dirname(output_feature_class))
                #arcpy.conversion.FeatureClassToFeatureClass(feature_class, shapefile_dir, feature_class_name)
            except Exception as e:
                wrn("Feature Class to Feature Class tool failed - check licensing and ensure you have advanced arcgis license")
                wrn(f"Error Message: {e}")
                arcpy.AddError("Export Failed for {0} - make sure feature class is not currently open in ArcGIS and try again".format(feature_class_name))
                exit()

        #Populate AOI_TYP and AOI_ISSUE fields with their domain descriptions, so output is not coded
        if "d_AOI_TYP" in [field.name for field in arcpy.ListFields(output_feature_class)]:
                arcpy.management.CalculateField(output_feature_class, "AOI_TYP", "!d_AOI_TYP!", "PYTHON3")
                arcpy.management.DeleteField(output_feature_class, "d_AOI_TYP")
        if "d_AOI_ISSU" in [field.name for field in arcpy.ListFields(output_feature_class)]:
                arcpy.management.CalculateField(output_feature_class, "AOI_ISSUE", "!d_AOI_ISSU!", "PYTHON3")
                arcpy.management.DeleteField(output_feature_class, "d_AOI_ISSU")
        if "d_PASS_FAI" in [field.name for field in arcpy.ListFields(output_feature_class)]:
                arcpy.management.CalculateField(output_feature_class, "PASS_FAIL", "!d_PASS_FAI!", "PYTHON3")
                arcpy.management.DeleteField(output_feature_class, "d_PASS_FAI")

    #export L_Source_Cit table to shapefile folder in dbf form
    arcpy.AddMessage("Exporting L_Source_Cit table")
    L_Source_Cit = os.path.join(FFRMS_Geodatabase, "L_Source_Cit")
    arcpy.conversion.TableToTable(L_Source_Cit, shapefile_dir, "L_Source_Cit.dbf")

    arcpy.AddMessage("Shapefile Export Complete")

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
    Features_to_Export = arcpy.GetParameterAsText(1)

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

    #Export Rasters, Shapefiles, and Erase_Areas
    if Features_to_Export =="Shapefiles Only":
        exportShapefiles(FFRMS_Geodatabase, shapefile_subdir)
    elif Features_to_Export == "Rasters Only":
        exportRasters(FFRMS_Geodatabase, raster_dir)
    elif Features_to_Export == "All":
        exportRasters(FFRMS_Geodatabase, raster_dir)
        exportShapefiles(FFRMS_Geodatabase, shapefile_subdir)



    