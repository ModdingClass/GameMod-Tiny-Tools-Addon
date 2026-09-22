import bpy
import json
import os
import mathutils
from mathutils import Vector
from decimal import Decimal
import re

from .utilz import *

def exportShapeKeysToJsonFile(ob, filename):
    
    def round_floats(o):
        if isinstance(o, float): return "~{:.8f}~".format(o)
        if isinstance(o, dict): return {k: round_floats(v) for k, v in o.items()}
        if isinstance(o, (list, tuple)): return [round_floats(x) for x in o]
        return o    
    #
    ob = bpy.context.object
    assert ob is not None and ob.type == 'MESH', "active object invalid"
    # ensure we got the latest assignments and weights
    ob.update_from_editmode()
    #
    me = ob.data
    basis_verts = ob.data.shape_keys.key_blocks[0]

    json_sk_exporter = "" #in properties it could be defined as  bbb_eye_L_morph,bbb_eye_R_morph,bbb_vagfix_morph

    if ob.data.get("json_sk_exporter") is not None:
        json_sk_exporter = ob.data.get("json_sk_exporter")

    skKeys = []
    for key in ob.data.shape_keys.key_blocks[1:]:
        SKName = key.name
        if json_sk_exporter == "":
            skKeys.append(SKName)
        else:    
            if SKName in json_sk_exporter:
                skKeys.append(SKName)

    skKeysExport = {keyName:[ ] for keyName in skKeys}

    epsilon = 0.000001
    for keyName in skKeys:
        key = ob.data.shape_keys.key_blocks[keyName]
        data = []
        for i in range(len(me.vertices)):
            delta = (key.data[i].co - basis_verts.data[i].co)
            if ( abs(delta.x) < epsilon and abs(delta.y) < epsilon and abs(delta.z) < epsilon ):
                delta = Vector((0,0,0))
            data.append( [ delta.x,  delta.y,  delta.z ] )
        skKeysExport[keyName] = data

   
    
    outStr= json.dumps(round_floats(skKeysExport))
    outStr = outStr.replace("{", "{\n\t").replace("}","\n}" )               #split arrays on rows 
    outStr = outStr.replace("]], ","] ],\n\t").replace("[[","[ [")          #add a space between main brackets
    outStr = outStr.replace("\"~","").replace("~\"","")                     # convert from strings with prefix/suffix back to readable floats
    outStr = outStr.replace("-0.00000000","0").replace("0.00000000","0")        #replace long zeros
    with open(filename, 'w') as outfile:
        outfile.write( outStr )
    
    #with open(filename, 'w') as outfile:
    #    outfile.write(prnDict(skKeysExport).replace("'", "\""))        



def importShapeKeysFromJsonFile(ob, filename):
    def checkIfShapekeyExistAndRecreateIt(ob, shapekey):
        if shapekey in [key.name for key in ob.data.shape_keys.key_blocks[1:]]:
            # setting the active shapekey
            iIndex = ob.data.shape_keys.key_blocks.keys().index(shapekey)
            ob.active_shape_key_index = iIndex
            # delete it
            bpy.ops.object.shape_key_remove()
        ob.shape_key_add(shapekey)
        iIndex = ob.data.shape_keys.key_blocks.keys().index(shapekey)
        ob.active_shape_key_index = iIndex
        ob.data.shape_keys.use_relative = True          
    #
    ob = bpy.context.object
    assert ob is not None and ob.type == 'MESH', "active object invalid"
    # ensure we got the latest assignments and weights
    ob.update_from_editmode()
    me = ob.data
    #
    f = open(filename,)
    # returns JSON object as a dictionary
    data = json.load(f)
    f.close()     # Closing file
    if len( data.items() ) == 0 :
        ShowMessageBox("No data in input json file!", "Error", 'ERROR')
        return
    #
    #check to see if json file has same number of vertices
    for skName,arr in data.items():
        if len(arr) == len(me.vertices):
            #all good, we can continue
            break
        else:
            ShowMessageBox("Vertex count not matching!", "Error", 'ERROR')
            return 
    #
    #check to see if we have the Basis Shapekey, otherwise create it
    if ( ob.data.shape_keys == None or len(ob.data.shape_keys.key_blocks)==0 ):
        sk_basis = ob.shape_key_add(name='Basis',from_mix=False)
        sk_basis.interpolation = 'KEY_LINEAR'
        # must set relative to false here
        ob.data.shape_keys.use_relative = False
    #
    basis_verts = ob.data.shape_keys.key_blocks[0]
    #
    for skName,arr in data.items():
        checkIfShapekeyExistAndRecreateIt(ob,skName)
        key = ob.data.shape_keys.key_blocks[skName]
        for i in range(len(me.vertices)):
            #here we should check if arr is already (0,0,0)
            key.data[i].co = basis_verts.data[i].co + Vector( tuple(e for e in arr[i])  )




def split_shape_key_by_axis(obj, shape_key_index):
    """
    Splits the selected shape key into three separate keys affecting only X, Y, and Z axes.
    """
    if obj.type != 'MESH':
        return
    
    mesh = obj.data
    shape_keys = mesh.shape_keys
    key_blocks = shape_keys.key_blocks
    
    if not shape_keys or shape_key_index < 0 or shape_key_index >= len(key_blocks):
        return
    
    base_key = key_blocks[0]
    selected_key = key_blocks[shape_key_index]
    
    # Create new shape keys for each axis
    key_x = obj.shape_key_add(name="{}_X".format(selected_key.name), from_mix=False)
    key_y = obj.shape_key_add(name="{}_Y".format(selected_key.name), from_mix=False)
    key_z = obj.shape_key_add(name="{}_Z".format(selected_key.name), from_mix=False)
    
    # Set the new shape keys to affect only their respective axis
    for v_index in range(len(base_key.data)):
        base_coord = base_key.data[v_index].co
        selected_coord = selected_key.data[v_index].co
        delta = selected_coord - base_coord
        
        # Explicitly create vectors with only one axis set
        delta_x = mathutils.Vector((delta.x, 0, 0))
        delta_y = mathutils.Vector((0, delta.y, 0))
        delta_z = mathutils.Vector((0, 0, delta.z))
        
        key_x.data[v_index].co = base_coord + delta_x
        key_y.data[v_index].co = base_coord + delta_y
        key_z.data[v_index].co = base_coord + delta_z




# ---------------------------------------------------------------------------
# Morphs from obj files
# ---------------------------------------------------------------------------

OBJ_MORPH_TRANSFORM_TOLERANCE = 1e-6
_IDENTITY_MATRIX = mathutils.Matrix.Identity(4)


def _matrixIsIdentity(matrix):
    for row in range(4):
        for col in range(4):
            if abs(matrix[row][col] - _IDENTITY_MATRIX[row][col]) > OBJ_MORPH_TRANSFORM_TOLERANCE:
                return False
    return True


def objectTransformIsZeroed(ob):
    """True when the object sits at the origin, unrotated and at scale 1.

    Shape key coordinates live in the target's OBJECT LOCAL space, so a morph
    can only be dropped in as world coordinates when the target's local space
    and world space are the same thing. matrix_world is checked as well as the
    loc/rot/scale channels, because a parent or a delta transform moves a mesh
    whose own channels still read as default.
    """
    if has_non_default_transforms(ob):
        return False
    return _matrixIsIdentity(ob.matrix_world)


def deleteObjectDataLevel(ob):
    """Remove an object and its mesh without going through bpy.ops.

    Keeps the whole import/delete cycle on one API level, and clears the active
    slot first so the scene is never left pointing at a removed object.
    """
    data = ob.data
    scene = bpy.context.scene
    if scene.objects.active is not None and scene.objects.active.name == ob.name:
        scene.objects.active = None
    for a_scene in bpy.data.scenes:
        if ob.name in a_scene.objects:
            a_scene.objects.unlink(ob)
    bpy.data.objects.remove(ob)
    if data is not None and data.users == 0 and isinstance(data, bpy.types.Mesh):
        bpy.data.meshes.remove(data)


def _importObjFileAsObject(filepath):
    """Import one obj file and return the single mesh object it produced.

    split_mode='OFF' is what keeps the file's vertex order intact. A morph is a
    per-index delta, so any reordering turns the shape key into noise.
    """
    names_before = set(ob.name for ob in bpy.data.objects)
    bpy.ops.import_scene.obj(filepath=filepath, split_mode='OFF', use_image_search=False)
    imported = [ob for ob in bpy.data.objects if ob.name not in names_before]
    meshes = [ob for ob in imported if ob.type == 'MESH']
    if len(meshes) != 1:
        for ob in imported:
            deleteObjectDataLevel(ob)
        raise ValueError("expected a single mesh in the obj file, got {}".format(len(meshes)))
    keeper = meshes[0]
    for ob in imported:
        if ob.name != keeper.name:
            deleteObjectDataLevel(ob)
    return keeper


def _normalizedCoordinates(ob):
    """The object's vertex positions with its own transform baked in.

    Same result as Object > Apply > All Transforms on the import, without the
    operator. The obj importer parks the Y-up to Z-up conversion in matrix_world
    (io_scene_obj/import_obj.py:1309) instead of in the mesh data, so an
    un-normalized morph would arrive rotated 90 degrees about X.
    """
    mesh = ob.data
    vertex_count = len(mesh.vertices)
    coordinates = [0.0] * (vertex_count * 3)
    mesh.vertices.foreach_get("co", coordinates)
    if _matrixIsIdentity(ob.matrix_world):
        return coordinates
    matrix = ob.matrix_world
    for index in range(vertex_count):
        offset = index * 3
        position = matrix * Vector((coordinates[offset], coordinates[offset + 1], coordinates[offset + 2]))
        coordinates[offset] = position.x
        coordinates[offset + 1] = position.y
        coordinates[offset + 2] = position.z
    return coordinates


def _recreateShapeKey(ob, shapekey_name):
    """Add shape key `shapekey_name`, replacing one of that name if it exists."""
    if ob.data.shape_keys is None:
        basis = ob.shape_key_add("Basis", from_mix=False)
        basis.interpolation = 'KEY_LINEAR'
    ob.data.shape_keys.use_relative = True
    existing = ob.data.shape_keys.key_blocks.get(shapekey_name)
    if existing is not None:
        ob.shape_key_remove(existing)
    key = ob.shape_key_add(shapekey_name, from_mix=False)
    key.interpolation = 'KEY_LINEAR'
    return key


def _removeOrphanDatablocks(material_names_before, image_names_before):
    """Drop the materials and images an obj import created and nothing uses.

    An obj with usemtl lines makes a material per surface on every import, so a
    batch of morphs otherwise leaves one pile of unused datablocks per file.
    """
    removed = 0
    for material in list(bpy.data.materials):
        if material.name not in material_names_before and material.users == 0:
            bpy.data.materials.remove(material)
            removed += 1
    for image in list(bpy.data.images):
        if image.name not in image_names_before and image.users == 0:
            bpy.data.images.remove(image)
            removed += 1
    return removed


def importShapeKeyFromObjFile(target_object, filepath):
    """Import one obj file and add it to target_object as a shape key.

    The shape key is named after the file. The imported object is deleted again
    before returning, whether the transfer worked or not. Returns a dict with
    what the caller needs for its console report; raises ValueError when the obj
    does not fit the target.
    """
    shapekey_name = os.path.splitext(os.path.basename(filepath))[0]
    material_names_before = set(material.name for material in bpy.data.materials)
    image_names_before = set(image.name for image in bpy.data.images)
    source_object = _importObjFileAsObject(filepath)
    try:
        source_vertex_count = len(source_object.data.vertices)
        target_vertex_count = len(target_object.data.vertices)
        if source_vertex_count != target_vertex_count:
            raise ValueError("vertex count {} does not match the target's {}".format(
                source_vertex_count, target_vertex_count))
        normalized = not _matrixIsIdentity(source_object.matrix_world)
        coordinates = _normalizedCoordinates(source_object)
        key = _recreateShapeKey(target_object, shapekey_name)
        key.data.foreach_set("co", coordinates)
    finally:
        deleteObjectDataLevel(source_object)
        orphans_removed = _removeOrphanDatablocks(material_names_before, image_names_before)
    target_object.data.update()
    return {
        "name": shapekey_name,
        "vertices": source_vertex_count,
        "normalized": normalized,
        "orphans_removed": orphans_removed,
    }
