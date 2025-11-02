import bpy
import json
import os
import sys
import importlib


def exportVertexGroupsToJsonFile(ob, filename):
    ob = bpy.context.object
    assert ob is not None and ob.type == 'MESH', "active object invalid"
    # ensure we got the latest assignments and weights
    ob.update_from_editmode()
    #
    vgs = ob.vertex_groups
    vertexGroupsExport = {group.name:[ ] for group in vgs}
    #
    for v in ob.data.vertices:
        for g in v.groups:
            vertexGroupsExport[vgs[g.group].name].append({v.index : g.weight})
    #
    with open(filename, 'w') as outfile:
        json.dump(vertexGroupsExport, outfile, indent=4)


def importVertexGroupsFromJsonFile(ob, filename):
    def checkIfVertexGroupExistAndRecreateIt(ob, group):
        if group in ob.vertex_groups.keys():
            vgrp = ob.vertex_groups[group]
            ob.vertex_groups.remove(vgrp)
            vgrp = ob.vertex_groups.new(name=group)
        else:
            vgrp = ob.vertex_groups.new(name=group)
        return vgrp
    #
    ob = bpy.context.object
    assert ob is not None and ob.type == 'MESH', "active object invalid"
    # ensure we got the latest assignments and weights
    ob.update_from_editmode()
    #
    vgs = ob.vertex_groups
    f = open(filename,)
    # returns JSON object as a dictionary
    data = json.load(f)
    f.close()     # Closing file
    #
    #
    for vg,iwPairs in data.items():
        vgrp = checkIfVertexGroupExistAndRecreateIt(ob, vg)
        for pairs in iwPairs:
            for index,weight in pairs.items():
                #print ("adding index {0} with weight {1} for vg:{2}".format(index,weight,vg ))
                vgrp.add([int(index)], weight, 'REPLACE')

def importVertexGroupsFromDsfFile(ob, filename):
    def checkIfVertexGroupExistAndRecreateIt(ob, group):
        if group in ob.vertex_groups.keys():
            vgrp = ob.vertex_groups[group]
            ob.vertex_groups.remove(vgrp)
            vgrp = ob.vertex_groups.new(name=group)
        else:
            vgrp = ob.vertex_groups.new(name=group)
        return vgrp
    #
    ob = bpy.context.object
    assert ob is not None and ob.type == 'MESH', "active object invalid"
    # ensure we got the latest assignments and weights
    ob.update_from_editmode()
    #
    prev_mode = bpy.context.object.mode
    if prev_mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    #
    with open(filename, 'r', encoding='utf-8') as f:
        dsf = json.load(f)
    #
    # find the SkinBinding section
    skin_binding = None
    for mod in dsf.get("modifier_library", []):
        if mod.get("id") == "SkinBinding":
            skin_binding = mod["skin"]
            break
    
    if not skin_binding:
        raise RuntimeError("No SkinBinding block found in DSF!")
    
    # build a dictionary: bone_name → {vertex_index: weight}
    weights_by_joint = {}
    for joint in skin_binding["joints"]:
        bone_name = joint["id"]
        vertex_weights = {int(idx): float(val) for idx, val in joint["node_weights"]["values"]}
        weights_by_joint[bone_name] = vertex_weights
    #    
    # --- now create Blender vertex groups from that ---
    for bone_name, vert_weights in weights_by_joint.items():
        vgrp = checkIfVertexGroupExistAndRecreateIt(ob, bone_name)
        for vidx, w in vert_weights.items():
            vgrp.add([vidx], w, 'REPLACE')
    #
    if prev_mode != 'OBJECT':
        bpy.ops.object.mode_set(mode=prev_mode)
    print("Imported {} vertex groups from DSF into {}".format( len(weights_by_joint), ob.name ))



#exportVertexGroupsToDsfSnippetTxtFile

def removeEmptyVGroups(obj):
    try:
        vertex_groups = obj.vertex_groups
        groups = {r : None for r in range(len(vertex_groups))}
        for vert in obj.data.vertices:
            for vg in vert.groups:
                i = vg.group
                if i in groups:
                    del groups[i]
        #
        lis = [k for k in groups]
        lis.sort(reverse=True)
        for i in lis:
            vertex_groups.remove(vertex_groups[i])
    except:
        pass


def convertWeightsBetweenCharacters(context, source_name, target_name, mapping):
    """
    Convert vertex group weights on the active mesh using a mapping dict.
    mapping format: {target_bone: [source_bone1, source_bone2, ...]}
    If source bones don't exist, they're skipped.
    Unmapped vertex groups are left as-is.
    """
    obj = context.object

    if obj is None or obj.type != 'MESH':
        print("No active mesh object selected for weight conversion.")
        return {'CANCELLED'}

    mesh = obj.data
    vcount = len(mesh.vertices)
    # Collect all existing vertex groups for easy access
    vgroups = obj.vertex_groups
    group_lookup = {vg.name: vg for vg in vgroups}

    print("Converting weights on object:", obj.name)
    print("Source:", source_name, "→ Target:", target_name)

    # Track missing source groups
    used_sources = set()
    missing_sources = []
    
    # Iterate over each target group in mapping
    for target_bone, source_bones in mapping.items():
        # Get or create the target vertex group
        if target_bone in group_lookup:
            vg_target = group_lookup[target_bone]
        else:
            vg_target = vgroups.new(name=target_bone)
            group_lookup[target_bone] = vg_target

        # Temporary weight accumulator (same length as vertex count)
        accumulated = [0.0] * vcount

        # Sum weights from all listed source bones
        for src_name in source_bones:
            vg_src = group_lookup.get(src_name)
            if not vg_src:
                missing_sources.append(src_name)
                continue
            #
            used_sources.add(src_name)
            #
            for v in mesh.vertices:
                try:
                    w = vg_src.weight(v.index)
                    accumulated[v.index] += w
                except RuntimeError:
                    # vertex not assigned to this group
                    pass
        
        # Apply the accumulated weights to the target group
        for vidx, w in enumerate(accumulated):
            if w > 0.0:
                vg_target.add([vidx], w, 'REPLACE')
    
    # --- Cleanup step ---
    # Delete source vertex groups that were used in mapping,
    # except those with same name as any target.
    target_names = set(mapping.keys())
    for src_name in used_sources:
        if src_name in target_names:
            continue  # same name → keep
        vg = vgroups.get(src_name)
        if vg:
            vgroups.remove(vg)
    
    # Optional: print report summary
    print("Weight conversion complete.")
    if missing_sources:
        print("Missing source groups (skipped):", sorted(set(missing_sources)))

    return {'FINISHED'}
