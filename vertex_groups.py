import bpy
import json

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

