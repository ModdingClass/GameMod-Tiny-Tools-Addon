import bpy
import json

from .utilz import *


def get_3d_view_context(obj):
    """Return a context override that ensures 3D View operations work."""
    override = bpy.context.copy()
    for area in bpy.context.screen.areas:
        if area.type == 'VIEW_3D':
            override['area'] = area
            for region in area.regions:
                if region.type == 'WINDOW':
                    override['region'] = region
                    break
            break
    override['object'] = obj
    override['active_object'] = obj
    override['selected_objects'] = [obj]
    override['selected_editable_objects'] = [obj]
    return override

def make_active(obj):
    bpy.ops.object.mode_set(mode='OBJECT')
    scene = bpy.context.scene
    for o in scene.objects:
        o.select = False
    obj.select = True
    scene.objects.active = obj
    return obj

def exportMaterialsToJsonFile(ob, filename):
    ob = bpy.context.object
    assert ob is not None and ob.type == 'MESH', "active object invalid"
    # ensure we got the latest assignments and materials?!? (do we realy need that?!?)
    ob.update_from_editmode()
    #
    mats = ob.material_slots
    materialsExport = {mat.name:[ ] for mat in mats}
    #materialsExport = ob.material_slots.keys()   <-TypeError: list indices must be integers or slices, not str
    for f in ob.data.polygons:
        materialsExport[ob.material_slots[:][f.material_index].name].append(f.index)
    with open(filename, 'w') as outfile:
        outfile.write(prnDict(materialsExport).replace("'", "\""))


def importMaterialsFromJsonFile(ob, filename):
    def checkIfMaterialExistElseCreateIt(ob, material):
        mat = bpy.data.materials.get(material)
        #if it doesnt exist, create it.
        if mat is None:
            # create material
            mat = bpy.data.materials.new(name=material)
            #assign material
        if mat.name not in ob.material_slots.keys():
            ob.data.materials.append(mat)     
        return mat

    #
    ob = bpy.context.object
    assert ob is not None and ob.type == 'MESH', "active object invalid"
    # ensure we got the latest assignments and weights
    ob.update_from_editmode()
    #
    f = open(filename,)
    # returns JSON object as a dictionary
    data = json.load(f)
    f.close()     # Closing file
    #
    #
    for matName,faceIndices in data.items():
        material = checkIfMaterialExistElseCreateIt(ob, matName)
        material_index = bpy.context.object.material_slots.find(material.name)
        for i in faceIndices:
            ob.data.polygons[i].material_index = material_index
    #

def sort_materials_in_object(ob):
    # Check if object has materials
    if not ob or not ob.material_slots:
        return False
    
    ob_mats = [mat.name for mat in ob.material_slots]
    ob_mats.sort()

    for i, mat_name in enumerate(ob_mats):
        # Set active material slot to the last slot
        ob.active_material_index = len(ob.material_slots) - 1
        # Find the material with the matching name
        while ob.active_material.name != mat_name:
            ob.active_material_index -= 1
        # Move the material slot to the correct position
        while ob.active_material_index > i:
            bpy.ops.object.material_slot_move(direction='UP')
    
    return True


class MaterialProcessorParser(object):
    """Parses material name directives and executes MERGE/SEPARATE operations."""

    def __init__(self, obj):
        self.obj = obj
        self.materials = self._get_object_materials()
        self.merge_ops = []       # list of (target_name, [material names])
        self.separate_ops = []    # list of (suffix, [material names])

    # ----------------------------------------------------
    def _get_object_materials(self):
        """Return unique materials from self.obj."""
        mats = []
        if self.obj and self.obj.type == 'MESH':
            for slot in self.obj.material_slots:
                if slot.material and slot.material not in mats:
                    mats.append(slot.material)
        return mats

    # ----------------------------------------------------
    def parse_merges(self):
        """Parse MERGE blocks and build merge_ops."""
        self.merge_ops = []
        current_target = None
        current_list = []
        in_block = False

        for mat in self.materials:
            name = mat.name.strip()
            if name.startswith("##MERGE:"):
                in_block = True
                current_target = name.split("##MERGE:", 1)[1].strip()
                current_list = []
                continue
            elif name.startswith("##MERGE_END##"):
                if in_block:
                    self.merge_ops.append((current_target, list(current_list)))
                    in_block = False
                    current_target = None
                    current_list = []
                continue

            if in_block:
                base_name = name.split(".")[0]
                if base_name not in current_list:
                    current_list.append(base_name)

        return self.merge_ops

    def parse_separates(self):
        """
        Parse SEPARATE blocks and build separate_ops.
        Each entry in self.separate_ops will be a dict:
            {
                'suffix': <suffix>,
                'materials': [<base material names>],
                'start_mat': <Material object for ##SEPARATE:>,
                'end_mat': <Material object for ##SEPARATE_END##>
            }
        """
        self.separate_ops = []
        current_suffix = None
        current_list = []
        start_mat = None
        end_mat = None
        in_block = False

        for mat in self.materials:
            name = mat.name.strip()

            if name.startswith("##SEPARATE:"):
                in_block = True
                current_suffix = name.split("##SEPARATE:", 1)[1].strip()
                current_list = []
                start_mat = mat
                continue

            elif name.startswith("##SEPARATE_END##"):
                if in_block:
                    end_mat = mat
                    self.separate_ops.append({
                        'suffix': current_suffix,
                        'materials': list(current_list),
                        'start_mat': start_mat,
                        'end_mat': end_mat
                    })
                    # reset
                    in_block = False
                    current_suffix = None
                    current_list = []
                    start_mat = None
                    end_mat = None
                continue

            # inside block, collect materials
            if in_block:
                base_name = name.split(".")[0].strip()
                if base_name not in current_list:
                    current_list.append(base_name)

        return self.separate_ops


    # ----------------------------------------------------
    # --- MERGE logic ---
    # ----------------------------------------------------
    def execute_merges(self):
        """Execute all merge operations (backwards to avoid index issues)."""
        if not self.obj or self.obj.type != 'MESH':
            return

        for target_name, mat_list in reversed(self.merge_ops):
            self._execute_merge_block(self.obj, target_name, mat_list)

    def _execute_merge_block(self, obj, target_name, mat_list):
        """Merge faces from mat_list into a single material named target_name."""
        if not obj or obj.type != 'MESH':
            return

        # Ensure target material exists
        if target_name in bpy.data.materials:
            target_mat = bpy.data.materials[target_name]
        else:
            target_mat = bpy.data.materials.new(target_name)

        # Add target material to object if missing
        slot_names = [slot.material.name for slot in obj.material_slots if slot.material]
        if target_mat.name not in slot_names:
            bpy.ops.object.material_slot_add()
            obj.material_slots[-1].material = target_mat

        # Reassign faces
        target_slot_index = None
        for i, slot in enumerate(obj.material_slots):
            if slot.material == target_mat:
                target_slot_index = i
                break
        if target_slot_index is None:
            return

        for poly in obj.data.polygons:
            if poly.material_index >= len(obj.material_slots):
                continue
            slot_mat = obj.material_slots[poly.material_index].material
            if slot_mat and slot_mat.name.split(".")[0] in mat_list:
                poly.material_index = target_slot_index

        # Remove old source material slots (the ones actually merged)
        for i in reversed(range(len(obj.material_slots))):
            slot = obj.material_slots[i]
            if slot.material and slot.material.name.split(".")[0] in mat_list:
                obj.active_material_index = i
                bpy.ops.object.material_slot_remove()

        # Immediately remove the MERGE directive slots for this block
        to_remove = []
        for i, slot in enumerate(obj.material_slots):
            mat = slot.material
            if not mat:
                continue
            name = mat.name.strip()
            if name.startswith("##MERGE") or name.startswith("##MERGE_END##"):
                to_remove.append((i, mat))

        for i, mat in reversed(to_remove):
            obj.active_material_index = i
            bpy.ops.object.material_slot_remove()


    # ----------------------------------------------------
    # --- SEPARATE logic ---
    # ----------------------------------------------------

    def execute_separates(self, obj):
        """
        Iterate all SEPARATE blocks one at a time.
        Each block produces a new object with the given suffix and only its materials.
        """
        if not obj or obj.type != 'MESH' or not self.separate_ops:
            return

        bpy.ops.object.mode_set(mode='OBJECT')

        for block_index, block in enumerate(self.separate_ops):
            suffix = block['suffix']
            mat_list = block['materials']
            start_mat = block['start_mat'].name
            end_mat = block['end_mat'].name
            self._execute_separate_block( obj, suffix, mat_list,start_mat, end_mat)




    # def execute_separates(self):
    #     """Execute all separate operations (backwards)."""
    #     if not self.obj or self.obj.type != 'MESH':
    #         return

    #     for suffix, mat_list in reversed(self.separate_ops):
    #         self._execute_separate_block(self.obj, suffix, mat_list)

    def _execute_separate_block(self, obj, suffix, mat_list, start_mat, end_mat):
        """
        Separate faces for a single SEPARATE block.
        Cleans the new object and removes block materials from the main object.
        """
        if not obj or obj.type != 'MESH' or not mat_list:
            return

        bpy.ops.object.mode_set(mode='OBJECT')

        # Deselect all faces first
        for poly in obj.data.polygons:
            poly.select = False

        # Select faces for this SEPARATE block
        for poly in obj.data.polygons:
            slot_mat = obj.material_slots[poly.material_index].material
            if slot_mat and slot_mat.name.split(".")[0].strip() in mat_list:
                poly.select = True

        # Separate selected faces into a new object
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.separate(type='SELECTED')
        bpy.ops.object.mode_set(mode='OBJECT')

        # Find newly created object(s)
        new_objs = [o for o in bpy.context.scene.objects if o.select and o != obj]

        for child_obj in new_objs:
            # Rename
            child_obj.name = obj.name + "_" + suffix
            # Clean child object materials
            self._cleanup_separate_child_object(child_obj, mat_list)
            print("=== SEPARATE BLOCK ===")
            print("Separated object:", child_obj.name)
            print("Materials kept:", [s.material.name for s in child_obj.material_slots if s.material])

        # Remove block materials from the main object
        self._cleanup_separate_base_object(obj, ([start_mat] + mat_list + [end_mat]) )

        print("Main object after block cleanup:", obj.name)
        print("Remaining materials:", [s.material.name for s in obj.material_slots if s.material])



    def _cleanup_separate_child_object(self, child_obj, keep_names):
        """
        Clean the new separated object.
        Only keep materials in keep_names and remove all SEPARATE directives.
        """
        if not child_obj or child_obj.type != 'MESH':
            return
        #
        override = get_3d_view_context(child_obj)
        bpy.ops.object.select_all(action='DESELECT')
        bpy.context.scene.objects.active = child_obj
        #child_obj.select = True
        make_active(child_obj)
        print("Working on mesh object:{}".format(child_obj.name))
        # Ensure the child object is active and selected
        # Normalize names
        keep_set = set([n.strip() for n in keep_names])
        #
        to_remove = []
        for i, slot in enumerate(child_obj.material_slots):
            mat = slot.material
            print("Checking material slot with name: {}".format(mat.name))
            if not mat:
                continue
            # base name without Blender numeric suffix
            base_name = mat.name.split(".")[0].strip()
            # remove directive slots or any material not in keep_names
            if base_name.startswith("##SEPARATE") or base_name.startswith("##SEPARATE_END") or base_name not in keep_set:
                to_remove.append(i)
                print("Preparing to remove material slot with name: {} and index {}".format(mat.name, i))
            else:
                print("Keeping material slot with name: {} and index {}".format(mat.name, i))
        #make_active(child_obj)        
        # Remove slots in reverse order to avoid index shifts
        for i in reversed(to_remove):
            child_obj.active_material_index = i
            #the effing most important thing in this entire world, miss the override for the context to get screwed
            bpy.ops.object.material_slot_remove(override)
        #
        # for i, slot in enumerate(child_obj.material_slots):    
        #     mat = slot.material
        #     print("Checking material slot with name: {}".format(mat.name))
        #     if i in to_remove:
        #         print("setting mat: {} as None".format(mat.name))
        #         mat = None               
        #
        # rvs = reversed(list(enumerate(child_obj.data.materials)))
        # for i, mat in rvs:
        #     if mat.name not in keep_set:
        #         child_obj.data.materials.pop(index=i)
        #
        # print("Remaining slots after cleanup:")
        # for slot in child_obj.material_slots:
        #     if slot.material:
        #         print(slot.material.name)


    def _cleanup_separate_base_object(self, obj, mat_list):
        """
        Remove materials in the block plus the block's directive materials.
        'block' is a dict from parse_separates().
        """
        #keep_set = set([m.name for m in obj.data.materials if m.name not in mat_list])
        obj.select = True
        bpy.context.scene.objects.active = obj
        # remove slots not in keep_set
        # for i in reversed(range(len(obj.data.materials))):
        #     mat = obj.data.materials[i]
        #     if not mat:
        #         continue
        #     if mat.name in mat_list:
        #         print("Removing from base object material: {} with index {}".format(mat.name,i))
        #         #obj.data.materials.pop(index=i)        
        #         obj.active_material_index = i
        #         bpy.ops.object.material_slot_remove()
        #
        materials_list = bpy.context.object.material_slots.keys()
        for mat in materials_list:
            if (mat in mat_list):
                mat_index = bpy.context.object.material_slots.find(mat)
                bpy.context.object.active_material_index = mat_index
                bpy.ops.object.material_slot_remove()

def get_object_materials(obj):
    """Return all unique materials actually used by a given object."""
    mats = []
    if obj and obj.type == 'MESH':
        for slot in obj.material_slots:
            if slot.material and slot.material not in mats:
                mats.append(slot.material)
    return mats

# -----------------------------------------------------------------
# Example of use inside Blender 2.79
# -----------------------------------------------------------------
def test_parser():
    parser = MaterialProcessorParser(bpy.context.active_object)
    # --- MERGE pass (backwards) ---
    parser.merge_ops = parser.parse_merge_blocks()
    parser.execute_merges()  # same logic as before, process backwards

    # --- SEPARATE pass ---
    parser.separate_ops = parser.parse_separate_blocks()
    parser.execute_separates()  # now operates on merged object(s)



#from io_game_mod_tiny_tools import materials
#materials.test_parser()