import bpy
import json
import math
from collections import OrderedDict
from pathlib import Path

from .utilz import *

# Utility function to export armature data
def export_armature_data(context, filepath):
    armature = context.object

    if armature and armature.type == 'ARMATURE':
        if has_non_default_transforms(armature):
            show_warning("Warning: The armature has non-default transforms (location, rotation, or scale). The exported armature might not match the original armature's appearance exactly.")
        
        original_mode = context.mode

        # Switch to Edit Mode if necessary
        if context.mode != 'EDIT_ARMATURE':
            bpy.ops.object.mode_set(mode='EDIT')

        bones_data = []
        for bone in armature.data.edit_bones:
            bone_info = OrderedDict([
                ("name", bone.name),
                ("head", ["{:.6f}".format(bone.head.x), "{:.6f}".format(bone.head.y), "{:.6f}".format(bone.head.z)]),
                ("tail", ["{:.6f}".format(bone.tail.x), "{:.6f}".format(bone.tail.y), "{:.6f}".format(bone.tail.z)]),
                ("roll", "{:.6f}".format(math.degrees(bone.roll))),
                ("parent", bone.parent.name if bone.parent else None),
                ("connected", bone.use_connect),
                ("deform", bone.use_deform)
            ])
            bones_data.append(bone_info)

        json_data = json.dumps(bones_data, indent=4)
        json_data = json_data.replace('\n        [', ' [').replace('\n            ', ' ').replace('\n        ]', ' ]')

        # Write the JSON data to the specified file
        try:
            with open(filepath, 'w') as outfile:
                outfile.write(json_data)
        except IOError:
            print("Failed to write to file.")
            return {'CANCELLED'}

        # Restore the original mode
        bpy.ops.object.mode_set(mode=original_mode)

        print("Armature data has been exported")
        return {'FINISHED'}
    else:
        print("No armature selected")
        return {'CANCELLED'}

def create_and_import_armature_data(context, filepath):
    deselect_all_objects()
    armatureName = Path(filepath).stem
    bpy.ops.object.armature_add()
    armature = bpy.context.scene.objects.active
    armature.name = armatureName
    #armature = bpy.data.armatures.new(armatureName)
    #armature_object = bpy.data.objects.new(armatureName, armature)
    #bpy.context.scene.objects.link(armature_object)
    #armature_object = bpy.context.scene.objects.active
    #armature_object.select = True
    return import_armature_data(context, filepath)

# Utility function to import armature data.
# append=False: clears all existing bones first (default, original behaviour).
# append=True:  keeps existing bones; bones from the JSON are added or overwrite
#               existing ones by name. Missing parent bones are skipped with a warning.
def import_armature_data(context, filepath, append=False):
    armature = context.object
    # Load the JSON data
    bones_data = load_json(filepath)
    # Switch to Edit Mode to create/edit bones
    bpy.context.scene.objects.active = armature
    bpy.ops.object.mode_set(mode='EDIT')
    armature_data = armature.data

    if not append:
        # Original behaviour: wipe everything before importing
        for bone in armature_data.edit_bones:
            armature_data.edit_bones.remove(bone)
        existing_bones = {}
    else:
        # Keep existing bones; seed the lookup dict with them so parent
        # assignments can resolve to bones that were already in the armature.
        existing_bones = {b.name: b for b in armature_data.edit_bones}

    # created_bones tracks every bone available for parent lookups
    created_bones = dict(existing_bones)

    # Create or overwrite bones from the JSON data
    for bone_info in bones_data:
        head = [float(v) for v in bone_info["head"]]
        tail = [float(v) for v in bone_info["tail"]]
        roll = math.radians(float(bone_info["roll"]))

        # Reuse the existing edit_bone if present, otherwise create a new one
        if bone_info["name"] in existing_bones:
            bone = existing_bones[bone_info["name"]]
        else:
            bone = armature_data.edit_bones.new(bone_info["name"])

        bone.head = (head[0], head[1], head[2])
        bone.tail = (tail[0], tail[1], tail[2])
        bone.roll = roll
        bone.use_connect = bone_info["connected"]
        bone.use_deform = bone_info["deform"]
        created_bones[bone_info["name"]] = bone

    # Set parent bones after all bones have been created/updated
    for bone_info in bones_data:
        if bone_info["parent"]:
            parent_bone = created_bones.get(bone_info["parent"])
            if parent_bone:
                created_bones[bone_info["name"]].parent = parent_bone
            else:
                print("Warning: parent bone '{}' not found for '{}', skipping parent assignment.".format(
                    bone_info["parent"], bone_info["name"]))

    # Switch back to Object Mode
    bpy.ops.object.mode_set(mode='OBJECT')

    print("Armature has been imported from", filepath)
    return {'FINISHED'}
