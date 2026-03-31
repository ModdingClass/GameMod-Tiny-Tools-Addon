bl_info = {
    "name": "Game Mod Tiny Tools",
    "author": "ModdingClass",
    "version": (1, 0),
    "blender": (2, 79, 0),
    "description": "Game oriented tools for quick prototyping",
    "warning": "",
    "wiki_url": "",
    "category": "Import-Export"    
}


import collections
import os
import sys
import subprocess
import shutil
import zipfile
import inspect
import math
import threading
import time
import bmesh
import bpy
import mathutils
import math
import importlib
from mathutils import Vector
from bpy.app.handlers import persistent
from bpy.props import StringProperty, BoolProperty 
from bpy_extras.io_utils import ImportHelper 
from bpy_extras.io_utils import ExportHelper 
from bpy.types import Operator
import bpy.utils.previews
import re
from tempfile import NamedTemporaryFile

import decimal



# Import submodules once
from . import utilz
from . import armatures
from . import materials
from . import vertex_groups
from . import shapekeys

# Hot reload support (F8 in Blender)
if "bpy" in locals():
    importlib.reload(utilz)
    importlib.reload(armatures)
    importlib.reload(materials)
    importlib.reload(vertex_groups)
    importlib.reload(shapekeys)
    print("Reloaded multifiles")
else:
    print("Imported multifiles")



# Operator for exporting armature data
class GMTT_OT_export_armature_to_json(bpy.types.Operator, ExportHelper):
    bl_idname = "gmtt.export_armature_to_json"
    bl_label = "Export"
    bl_description = "Export armature data to JSON file"
    filename_ext = ".json"  # The file extension for the export

    # Filepath is handled by ExportHelper

    def execute(self, context):
        # Call the separated utility function to handle export
        result = armatures.export_armature_data(context, self.filepath)
        return result

# Operator for importing armature data
class GMTT_OT_import_armature_from_json(bpy.types.Operator, ImportHelper):
    bl_idname = "gmtt.import_armature_from_json"
    bl_label = "Import"
    bl_description = "Import armature data from JSON file"
    filename_ext = ".json"  # The file extension for the export

    # Filepath is handled by ImportHelper

    def execute(self, context):
        # Call the separated utility function to handle export
        result = armatures.import_armature_data(context, self.filepath)
        return result

# Operator for appending/overwriting bones into the active armature from a JSON file
class GMTT_OT_append_armature_from_json(bpy.types.Operator, ImportHelper):
    bl_idname = "gmtt.append_armature_from_json"
    bl_label = "Append / Overwrite Bones"
    bl_description = "Append bones from a JSON file into the active armature (adds new bones; overwrites existing ones by name)"
    filename_ext = ".json"

    def execute(self, context):
        result = armatures.import_armature_data(context, self.filepath, append=True)
        return result

# Operator for importing armature data
class GMTT_OT_create_and_import_armature_from_json(bpy.types.Operator, ImportHelper):
    bl_idname = "gmtt.create_and_import_armature_from_json"
    bl_label = "Import"
    bl_description = "Import new armature data from JSON file"
    filename_ext = ".json"  # The file extension for the export

    # Filepath is handled by ImportHelper

    def execute(self, context):
        # Call the separated utility function to handle export
        result = armatures.create_and_import_armature_data(context, self.filepath)
        return result    

# Panel for the exporter
class GMTT_PT_armature_tools(bpy.types.Panel):
    bl_label = "GMTT Armature Tools"
    bl_idname = "gmtt.armature_tools"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "data"
    #
    @classmethod
    def poll(cls, context):
        # Check if the context is for an armature
        return context.object and context.object.type == 'ARMATURE'
    #
    def draw(self, context):
        layout = self.layout
        layout.operator("gmtt.import_armature_from_json", text="Import Armature Data", icon='OUTLINER_DATA_ARMATURE')
        layout.operator("gmtt.append_armature_from_json", text="Append / Overwrite Bones", icon='OUTLINER_DATA_ARMATURE')
        layout.operator("gmtt.export_armature_to_json", text="Export Armature Data", icon='OUTLINER_DATA_ARMATURE')
    


def draw_add_custom_armature_importer_in_menu(self, context):
    layout = self.layout
    layout.operator("gmtt.create_and_import_armature_from_json", text="Import From JSON file", icon='IMPORT')


# this class extends ExportHelper !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
class GMTT_OT_export_materials_to_json(Operator, ExportHelper):
    ''''''
    bl_idname = "gmtt.export_materials_to_json"
    bl_label = "Export materials"
    bl_description = "Exports materials to a custom json file"

    filename_ext = ".json"  # ExportHelper mixin class uses this
    filter_glob = StringProperty(
        default='*.json',
        options={'HIDDEN'}
    )
    
    def execute(self, context):
        ob = bpy.context.object
        materials.exportMaterialsToJsonFile(ob, self.filepath)
        return {'FINISHED'}


# this class extends ImportHelper !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
class GMTT_OT_import_materials_from_json(Operator, ImportHelper):
    ''''''
    bl_idname = "gmtt.import_materials_from_json"
    bl_label = "Import materials"
    bl_description = "Import materials from a custom json file"

    filter_glob = StringProperty(
        default='*.json',
        options={'HIDDEN'}
    )
    
    def execute(self, context):
        ob = bpy.context.object
        materials.importMaterialsFromJsonFile(ob, self.filepath)
        return {'FINISHED'}
    

class GMTT_OT_sort_materials(bpy.types.Operator):
    """Sort materials alphabetically in the material slots"""
    bl_idname = "gmtt.sort_materials"
    bl_label = "Sort Materials"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        ob = context.object
        
        # Call the separate function to sort materials
        if not materials.sort_materials_in_object(ob):
            self.report({'WARNING'}, "Object has no materials to sort")
            return {'CANCELLED'}

        return {'FINISHED'}

class GMTT_OT_preprocess_materials(bpy.types.Operator):
    bl_idname = "gmtt.preprocess_materials"
    bl_label = "Preprocess Materials"
    bl_description = "Run material preprocessor for the active object"

    def execute(self, context):
        obj = bpy.context.scene.objects.active
        if not obj:
            self.report({'WARNING'}, "No active object")
            return {'CANCELLED'}
        parser = materials.MaterialProcessorParser(obj)

        # --- MERGE pass (backwards) ---
        parser.merge_ops = parser.parse_merges()
        print("=== MERGE OPERATIONS ===")
        for target_name, mat_list in reversed(parser.merge_ops):
            print("Merging:", mat_list, "->", target_name)
        #
        parser.execute_merges()  # same logic as before, process backwards
        
        
        
        
        # --- SEPARATE pass ---
        parser.separate_ops = parser.parse_separates()
        #
        print("=== SEPARATE OPERATIONS ===")
        for block in parser.separate_ops:
            sep_list = block['materials']
            suffix = block['suffix']
            print("Separating:", sep_list, "->", suffix)  
        parser.execute_separates(obj)  # now operates on merged object(s)

        return {'FINISHED'}

def draw_add_custom_sort_in_materials_dropdown_menu(self, context):
    self.layout.separator()
    self.layout.operator(
        GMTT_OT_sort_materials.bl_idname, 
        text="Sort Materials", 
        icon='SORTALPHA'
    )
    self.layout.operator(
        GMTT_OT_import_materials_from_json.bl_idname, 
        text="Import Materials", 
        icon='IMPORT'
    )
    self.layout.operator(
        GMTT_OT_export_materials_to_json.bl_idname, 
        text="Export Materials", 
        icon='EXPORT'
    )
    self.layout.operator(
    GMTT_OT_preprocess_materials.bl_idname, 
        text="Preprocess Materials", 
        icon='SAVE_PREFS'
    )



# this class extends ExportHelper !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
class GMTT_OT_export_vertex_weights_to_json(Operator, ExportHelper):
    ''''''
    bl_idname = "gmtt.export_vertex_weights_to_json"
    bl_label = "Export weights to JSON"
    bl_description = "Exports weights to a custom json file"

    filename_ext = ".json"  # ExportHelper mixin class uses this
    filter_glob = StringProperty(
        default='*.json',
        options={'HIDDEN'}
    )
    
    def execute(self, context):
        #bpy.context.scene.objects.active = None
        #for obj in bpy.data.objects:
        #    obj.select = False        
        #bpy.ops.object.select_all(action='DESELECT')
        print('Selected file:', self.filepath)
        path_to_file = self.filepath
        ob = bpy.context.object
        vertex_groups.exportVertexGroupsToJsonFile(ob, path_to_file)
        return {'FINISHED'}
    

# this class extends ImportHelper !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
class GMTT_OT_import_vertex_weights_from_json(Operator, ImportHelper):
    ''''''
    bl_idname = "gmtt.import_vertex_weights_from_json"
    bl_label = "Import weights from JSON"
    bl_description = "Import weights from a custom json file"

    filter_glob = StringProperty(
        default='*.json',
        options={'HIDDEN'}
    )
    
    def execute(self, context):
        #bpy.context.scene.objects.active = None
        #for obj in bpy.data.objects:
        #    obj.select = False        
        #bpy.ops.object.select_all(action='DESELECT')
        print('Selected file:', self.filepath)
        path_to_file = self.filepath
        ob = bpy.context.object
        vertex_groups.importVertexGroupsFromJsonFile(ob, path_to_file)
        return {'FINISHED'}


# this class extends ImportHelper !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
class GMTT_OT_import_vertex_weights_from_dsf(Operator, ImportHelper):
    ''''''
    bl_idname = "gmtt.import_vertex_weights_from_dsf"
    bl_label = "Import weights from DSF (DAZ)"
    bl_description = "Import weights from a DAZ DSF file"

    filter_glob = StringProperty(
        default='*.dsf',
        options={'HIDDEN'}
    )
    
    def execute(self, context):
        #bpy.context.scene.objects.active = None
        #for obj in bpy.data.objects:
        #    obj.select = False        
        #bpy.ops.object.select_all(action='DESELECT')
        print('Selected file:', self.filepath)
        path_to_file = self.filepath
        ob = bpy.context.object
        vertex_groups.importVertexGroupsFromDsfFile(ob, path_to_file)
        return {'FINISHED'}

# this class extends ImportHelper !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
class GMTT_OT_export_vertex_weights_to_dsf_snippet(Operator, ImportHelper):
    ''''''
    bl_idname = "gmtt.export_vertex_weights_to_dsf_snippet"
    bl_label = "Export weights to DSF snippet (Daz)"
    bl_description = "Export weights to a DSF file as a txt snippet"

    filter_glob = StringProperty(
        default='*.txt',
        options={'HIDDEN'}
    )
    
    def execute(self, context):
        #bpy.context.scene.objects.active = None
        #for obj in bpy.data.objects:
        #    obj.select = False        
        #bpy.ops.object.select_all(action='DESELECT')
        print('Selected file:', self.filepath)
        path_to_file = self.filepath
        ob = bpy.context.object
        print("Not actually implemented inside GMTT_OT_export_vertex_weights_to_dsf_snippet")
        #exportVertexGroupsToDsfSnippetTxtFile(ob, path_to_file)
        return {'FINISHED'}
    
# this class extends ImportHelper !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
class GMTT_OT_mesh_remove_empty_vgroups(Operator):
    ''''''
    bl_idname = "gmtt.mesh_remove_empty_vgroups"
    bl_label = "Remove Empty (Weightless) VGs"
    bl_description = "Remove Empty (Weightless) VGs"

    def execute(self, context):
        ob = bpy.context.object
        vertex_groups.removeEmptyVGroups(ob)
        return {'FINISHED'}

def draw_add_custom_functions_in_vertex_groups_dropdown_menu(self, context):
    self.layout.separator()

    self.layout.operator(
        GMTT_OT_import_vertex_weights_from_json.bl_idname, 
        text="Import Weights from JSON", 
        icon='IMPORT'
    )
    self.layout.operator(
        GMTT_OT_export_vertex_weights_to_json.bl_idname, 
        text="Export Weights to JSON", 
        icon='EXPORT'
    )  
    self.layout.operator(
        GMTT_OT_import_vertex_weights_from_dsf.bl_idname, 
        text="Import Weights from DSF (Daz)", 
        icon='IMPORT'
    )    
    self.layout.operator(
        GMTT_OT_export_vertex_weights_to_dsf_snippet.bl_idname, 
        text="Export Weights to DSF snippet (Daz)", 
        icon='EXPORT'
    )     
    self.layout.operator(
        GMTT_OT_convert_weights_between_characters.bl_idname, 
        text="Convert vertex groups weights between characters", 
        icon='ARROW_LEFTRIGHT'
    )
    #  
    self.layout.separator()  
    self.layout.operator(
        GMTT_OT_mesh_remove_empty_vgroups.bl_idname, 
        text="Remove Empty (Weightless) VGs", 
        icon='X'
    )          


# this class extends ExportHelper !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
class GMTT_OT_export_shapekeys_to_json(Operator, ExportHelper):
    ''''''
    bl_idname = "gmtt.export_shapekeys_to_json"
    bl_label = "Export shapekeys"
    bl_description = "Exports shapekeys to a custom json file"

    filename_ext = ".json"  # ExportHelper mixin class uses this
    filter_glob = StringProperty(
        default='*.json',
        options={'HIDDEN'}
    )
    
    def execute(self, context):
        print('Selected file:', self.filepath)
        path_to_file = self.filepath
        ob = bpy.context.object
        shapekeys.exportShapeKeysToJsonFile(ob, path_to_file)
        return {'FINISHED'}

#Non Interactive - because we dont want to open the file picker
# this class extends ExportHelper !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
class GMTT_OT_export_shapekeys_to_json_non_interactive(Operator):
    ''''''
    bl_idname = "gmtt.export_shapekeys_to_json_non_interactive"
    bl_label = "Export shapekeys (Non Interactive)"
    bl_description = "Exports shapekeys to a custom json file non interractive"

    filepath = StringProperty(name="Filepath", description="Path to JSON file")
    
    def execute(self, context):
        
        ob = context.object
        if not ob:
            self.report({'ERROR'}, "No active object found.")
            return {'CANCELLED'}
        path_to_file = self.filepath
        print('Pushing shapekeys to file:', path_to_file)
        try:
            shapekeys.exportShapeKeysToJsonFile(ob, path_to_file)
        except Exception as e:
            self.report({'ERROR'}, "Failed to export shapekeys: {}".format(e))
            return {'CANCELLED'}            
        return {'FINISHED'}    

# this class extends ImportHelper !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
class GMTT_OT_import_shapekeys_from_json(Operator, ImportHelper):
    ''''''
    bl_idname = "gmtt.import_shapekeys_from_json"
    bl_label = "Import shapekeys"
    bl_description = "Import shapekeys from a custom json file"
    filename_ext = ".json"  # ExportHelper mixin class uses this
    filter_glob = StringProperty(
        default='*.json',
        options={'HIDDEN'}
    )
    
    def execute(self, context):
        print('Selected file:', self.filepath)
        path_to_file = self.filepath
        ob = bpy.context.object
        shapekeys.importShapeKeysFromJsonFile(ob, path_to_file)
        return {'FINISHED'}

#Non Interactive - because we dont want to open the file picker
# this class extends ImportHelper !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
class GMTT_OT_import_shapekeys_from_json_non_interactive(Operator):
    ''''''
    bl_idname = "gmtt.import_shapekeys_from_json_non_interactive"
    bl_label = "Import shapekeys (Non Interactive)"
    bl_description = "Import shapekeys from a custom json file non interractive"

    filepath = StringProperty(name="Filepath", description="Path to JSON file")
    
    def execute(self, context):
        ob = context.object
        if not ob:
            self.report({'ERROR'}, "No active object found.")
            return {'CANCELLED'}
        path_to_file = self.filepath
        print('Loading shapekeys from file:', path_to_file)
        try:
            shapekeys.importShapeKeysFromJsonFile(ob, path_to_file)
        except Exception as e:
            self.report({'ERROR'}, "Failed to import shapekeys: {}".format(e))
            return {'CANCELLED'}
        return {'FINISHED'}




class GMTT_OT_split_shapekey_by_axis(bpy.types.Operator):
    """Split selected shape key into X, Y, Z components"""
    bl_idname = "gmtt.split_shapekey_by_axis"
    bl_label = "Split Shape Key by Axis"
    bl_options = {'REGISTER', 'UNDO'}
    #
    @classmethod
    def poll(cls, context):
        obj = context.object
        if (1==1):
            print ("polling is True")
            return True
        if obj and obj.type == 'MESH':
            return len(obj.data.shape_keys.key_blocks) > 0 and any(keyblock.select for keyblock in obj.data.shape_keys.key_blocks)
        return False
    #    
    def execute(self, context):
        obj = context.object
        print("executed, but: {}".format( len(obj.data.shape_keys.key_blocks) > 0 and any(keyblock.select for keyblock in obj.data.shape_keys.key_blocks)))
        if obj and obj.type == 'MESH' and obj.active_shape_key_index > 0:
            shapekeys.split_shape_key_by_axis(obj, obj.active_shape_key_index)
            return {'FINISHED'}
        return {'CANCELLED'}


def draw_add_custom_functions_in_shapekeys_dropdown_menu(self, context):
    self.layout.separator()
    op_row = self.layout.row()
    op_row.operator(
        GMTT_OT_split_shapekey_by_axis.bl_idname,
        text="Split Shapekey by Axis", 
        icon='MONKEY'
    )
    obj = context.object
    shape_keys = obj.data.shape_keys if obj and obj.type == 'MESH' else None
    # Check if there are shape keys and if any shape key is selected
    if ( obj.data.shape_keys != None and len(obj.data.shape_keys.key_blocks)>1 ):
        pass
    else:
        op_row.enabled=False
    self.layout.operator(
        GMTT_OT_import_shapekeys_from_json.bl_idname, 
        text="Import Shapekeys from JSON", 
        icon='IMPORT'
    )
    op_row = self.layout.row()
    op_row.operator(
        GMTT_OT_export_shapekeys_to_json.bl_idname, 
        text="Export Shapekeys to JSON", 
        icon='EXPORT'
    )
    if ( obj.data.shape_keys != None and len(obj.data.shape_keys.key_blocks)>1 ):
        pass
    else:
        op_row.enabled=False    


class GMTT_OT_strip_and_clean(bpy.types.Operator):
    """Strip and Clean Mesh Object"""
    bl_idname = "gmtt.object_strip_and_clean"
    bl_label = "Strip and Clean"
    bl_options = {'REGISTER', 'UNDO'}

    vg = bpy.props.BoolProperty(name="Remove Vertex Groups", default=False)
    sk = bpy.props.BoolProperty(name="Remove Shape Keys", default=False)
    mat = bpy.props.BoolProperty(name="Remove Materials", default=False)
    mod = bpy.props.BoolProperty(name="Remove Modifiers", default=False)
    all = bpy.props.BoolProperty(name="Remove All", default=False)

    def execute(self, context):
        obj = context.active_object
        if obj.type != 'MESH':
            self.report({'WARNING'}, "Active object is not a mesh.")
            return {'CANCELLED'}
        if self.all:
            vg = sk = mat = mod = True
        else:
            vg = self.vg
            sk = self.sk
            mat = self.mat
            mod = self.mod
        if vg:
            # Remove all vertex groups
            bpy.ops.object.vertex_group_remove(all=True)
            #if obj.vertex_groups:
            #    obj.vertex_groups.clear()
            self.report({'INFO'}, "Removed all vertex groups from {}.".format(obj.name))
        if sk:
            if obj.data.shape_keys:
                obj.active_shape_key_index = 0
                bpy.ops.object.shape_key_remove(all=True)
            self.report({'INFO'}, "Removed all shape keys from {}.".format(obj.name))                
            #if obj.data.shape_keys:
            #    blocks = obj.data.shape_keys.key_blocks
            #    for ind in reversed(range(len(blocks))):
            #        bl = blocks[ind]
            #        obj.shape_key_remove(bl[ind])
            #    
            #if obj.data.shape_keys:
            #    shape_keys = obj.data.shape_keys.key_blocks
            #    for i in range(len(shape_keys) - 1, -1, -1):
            #        obj.shape_key_remove(shape_keys[i])
            #    self.report({'INFO'}, "Removed all shape keys from {}.".format(obj.name))
        if mat:
            if obj.material_slots:
                obj.active_material_index = 0
                print("removing materials")
                for x in bpy.context.object.material_slots: #For all of the materials in the selected object:
                    bpy.context.object.active_material_index = 0 #select the top material
                    bpy.ops.object.material_slot_remove() 
                    #delete it                  
            self.report({'INFO'}, "Removed all materials from {}.".format(obj.name))
        if mod:
            if obj.modifiers:
                for modifier in obj.modifiers:
                    obj.modifiers.remove(modifier)
                self.report({'INFO'}, "Removed all modifiers from {}.".format(obj.name))
            self.report({'INFO'}, "Cleaning of {} completed.".format(obj.name))
        return {'FINISHED'}


class GMTT_OT_mesh_merge_weights(bpy.types.Operator):
    bl_idname = "gmtt.mesh_merge_weights"
    bl_label = "Merge Weights"
    bl_description = "Merge weights from selected bones to the active bone"

    @classmethod
    def poll(cls, context):
        return (context.object is not None and context.mode == 'PAINT_WEIGHT')

    def transferWeightsBetweenGroups(self, obj, source, target):
        vgs = obj.vertex_groups
        vgroups = {g.name: g.index for g in vgs}
        vertices = obj.data.vertices

        sourceIndex = vgroups.get(source)
        if sourceIndex is None:
            return

        targetIndex = vgroups.get(target)
        if targetIndex is None:
            new_vg = vgs.new(name=target)
            targetIndex = new_vg.index

        # Collect vertices and weights to merge
        merge_data = []
        for v in vertices:
            groups = [g.group for g in v.groups]
            if sourceIndex in groups:
                try:
                    w = vgs[source].weight(v.index)
                    merge_data.append((v.index, w))
                except RuntimeError:
                    pass

        # Apply merge
        for v, w in merge_data:
            vgs[target].add([v], w, 'ADD')
            vgs[source].remove([v])

    def execute(self, context):
        obj = context.object
        armature = None

        for mod in obj.modifiers:
            if mod.type == 'ARMATURE':
                armature = mod.object
                break

        if not armature or armature.type != 'ARMATURE':
            self.report({'ERROR'}, "No armature found.")
            return {'CANCELLED'}

        active_bone = context.active_pose_bone
        if not active_bone:
            self.report({'ERROR'}, "No active bone found.")
            return {'CANCELLED'}

        active_name = active_bone.name
        selected_bones = [b.name for b in armature.data.bones if b.select and b.name != active_name]

        if not selected_bones:
            self.report({'ERROR'}, "Select at least one other bone besides the active bone.")
            return {'CANCELLED'}

        for sbone in selected_bones:
            self.transferWeightsBetweenGroups(obj, sbone, active_name)

        self.report({'INFO'}, "Merged weights from {} → {}".format(selected_bones, active_name))

        #update the viewport
        bpy.context.object.data.update()

        return {'FINISHED'}




# list of character choices (identifier, name, description)
SKELETON_NAMES = [
    ('G3F', "Genesis 3 Female", ""),
    ('G8F', "Genesis 8 Female", ""),
    ('G9',  "Genesis 9", ""),
    ('UE5', "Unreal UE5 Mannequin", ""),
]

# --------------------------------------------------------------------
# Mapping Loader
# --------------------------------------------------------------------
def load_mappings(source_name, target_name):
    """
    Dynamically load a mapping module from the 'mapping' subfolder.
    Example: source='G9', target='G3F' → loads mapping/G3F_from_G9.py
    Must contain a variable named G3F_from_G9 = {...}
    """
    module_name = "%s_from_%s" % (target_name, source_name)
    base_path = os.path.join(os.path.dirname(__file__), "mappings")

    if base_path not in sys.path:
        sys.path.append(base_path)

    try:
        mapping_module = importlib.import_module(module_name)
        mapping_dict = getattr(mapping_module, module_name)
        print("Loaded mapping:", module_name)
        return mapping_dict
    except Exception as e:
        print("Failed to load mapping %s: %s" % (module_name, e))
        return None

# --------------------------------------------------------------------
# Main Operator
# --------------------------------------------------------------------
class GMTT_OT_convert_weights_between_characters(bpy.types.Operator):
    """Convert vertex groups weights between characters"""
    bl_idname = "gmtt.convert_weights_between_characters"
    bl_label = "Convert Vertex Groups Weights Between Characters"
    bl_options = {'REGISTER', 'UNDO'}

    source_character = bpy.props.EnumProperty(
        name="Source Character",
        description="Select the source character type",
        items=SKELETON_NAMES,
        default='G9'
    )

    target_character = bpy.props.EnumProperty(
        name="Target Character",
        description="Select the target character type",
        items=SKELETON_NAMES,
        default='UE5'
    )

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=300)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "source_character")
        layout.prop(self, "target_character")

    def execute(self, context):
        src = self.source_character
        tgt = self.target_character

        self.report({'INFO'}, "Converting %s -> %s" % (src, tgt))

        # Try to load mapping
        mapping = load_mappings(src, tgt)

        if mapping is None:
            self.report({'ERROR'}, "No mapping found for %s_from_%s" % (tgt, src))
            return {'CANCELLED'}

        # At this point, 'mapping' is a dictionary like:
        #   {"abdomenLower": ["spine1"], "chestUpper": ["spine4"], ...}
        # You can now apply your weight transfer logic here.
        #
        # Example placeholder:
        self.report({'INFO'}, "Loaded mapping with %d entries" % len(mapping))

        # TODO: call your weight-transfer function
        vertex_groups.convertWeightsBetweenCharacters(context, src, tgt, mapping)

        return {'FINISHED'}

    # You can test it directly:
    # bpy.ops.object.convert_weights_popup('INVOKE_DEFAULT')




# Register and unregister classes
def register():
    bpy.utils.register_class(GMTT_OT_strip_and_clean)
    bpy.utils.register_class(GMTT_OT_convert_weights_between_characters)
    bpy.utils.register_class(GMTT_OT_export_armature_to_json)
    bpy.utils.register_class(GMTT_OT_import_armature_from_json)
    bpy.utils.register_class(GMTT_OT_append_armature_from_json)
    bpy.utils.register_class(GMTT_OT_create_and_import_armature_from_json)
    bpy.types.INFO_MT_armature_add.append(draw_add_custom_armature_importer_in_menu)
    bpy.utils.register_class(GMTT_PT_armature_tools)
    #    
    bpy.utils.register_class(GMTT_OT_import_materials_from_json)
    bpy.utils.register_class(GMTT_OT_export_materials_to_json)    
    bpy.utils.register_class(GMTT_OT_sort_materials)    
    bpy.utils.register_class(GMTT_OT_preprocess_materials)
    bpy.types.MATERIAL_MT_specials.append(draw_add_custom_sort_in_materials_dropdown_menu)
    #
    bpy.utils.register_class(GMTT_OT_export_vertex_weights_to_json)
    bpy.utils.register_class(GMTT_OT_import_vertex_weights_from_json)
    bpy.utils.register_class(GMTT_OT_import_vertex_weights_from_dsf)    
    bpy.utils.register_class(GMTT_OT_export_vertex_weights_to_dsf_snippet)
    bpy.utils.register_class(GMTT_OT_mesh_remove_empty_vgroups)
    bpy.types.MESH_MT_vertex_group_specials.append(draw_add_custom_functions_in_vertex_groups_dropdown_menu)
    #
    bpy.utils.register_class(GMTT_OT_split_shapekey_by_axis)
    bpy.utils.register_class(GMTT_OT_export_shapekeys_to_json)
    bpy.utils.register_class(GMTT_OT_import_shapekeys_from_json)
    bpy.utils.register_class(GMTT_OT_export_shapekeys_to_json_non_interactive)
    bpy.utils.register_class(GMTT_OT_import_shapekeys_from_json_non_interactive)
    bpy.types.MESH_MT_shape_key_specials.append(draw_add_custom_functions_in_shapekeys_dropdown_menu)
    bpy.utils.register_class(GMTT_OT_mesh_merge_weights)

    

def unregister():
    bpy.utils.unregister_class(GMTT_OT_strip_and_clean)
    bpy.utils.unregister_class(GMTT_OT_convert_weights_between_characters)
    bpy.utils.unregister_class(GMTT_OT_export_armature_to_json)
    bpy.utils.unregister_class(GMTT_OT_import_armature_from_json)
    bpy.utils.unregister_class(GMTT_OT_append_armature_from_json)
    bpy.utils.unregister_class(GMTT_OT_create_and_import_armature_from_json)    
    bpy.types.INFO_MT_armature_add.remove(draw_add_custom_armature_importer_in_menu)    
    bpy.utils.unregister_class(GMTT_PT_armature_tools)
    #
    bpy.utils.unregister_class(GMTT_OT_import_materials_from_json)    
    bpy.utils.unregister_class(GMTT_OT_export_materials_to_json)    
    bpy.utils.unregister_class(GMTT_OT_sort_materials)
    bpy.utils.unregister_class(GMTT_OT_preprocess_materials)
    bpy.types.MATERIAL_MT_specials.remove(draw_add_custom_sort_in_materials_dropdown_menu)  
    #
    bpy.utils.unregister_class(GMTT_OT_split_shapekey_by_axis)
    bpy.utils.unregister_class(GMTT_OT_export_vertex_weights_to_json)
    bpy.utils.unregister_class(GMTT_OT_import_vertex_weights_from_json)
    bpy.utils.unregister_class(GMTT_OT_import_vertex_weights_from_dsf)   
    bpy.utils.unregister_class(GMTT_OT_export_vertex_weights_to_dsf_snippet)
    bpy.utils.unregister_class(GMTT_OT_mesh_remove_empty_vgroups)
    bpy.types.MESH_MT_vertex_group_specials.remove(draw_add_custom_functions_in_vertex_groups_dropdown_menu)
    #
    bpy.utils.unregister_class(GMTT_OT_export_shapekeys_to_json)
    bpy.utils.unregister_class(GMTT_OT_import_shapekeys_from_json)
    bpy.utils.unregister_class(GMTT_OT_export_shapekeys_to_json_non_interactive)
    bpy.utils.unregister_class(GMTT_OT_import_shapekeys_from_json_non_interactive)
    bpy.types.MESH_MT_shape_key_specials.remove(draw_add_custom_functions_in_shapekeys_dropdown_menu)    
    bpy.utils.unregister_class(GMTT_OT_mesh_merge_weights)


if __name__ == "__main__":
    register()
