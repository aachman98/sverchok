# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

import bpy
from bpy.props import BoolProperty, StringProperty
import bmesh

import sverchok
from sverchok.node_tree import SverchCustomTreeNode
from sverchok.utils.nodes_mixins.sv_animatable_nodes import SvAnimatableNode
from sverchok.data_structure import updateNode
from sverchok.utils.sv_bmesh_utils import pydata_from_bmesh
from sverchok.core.handlers import get_sv_depsgraph, set_sv_depsgraph_need

class SvOB3Callback(bpy.types.Operator):

    bl_idname = "node.ob3_callback"
    bl_label = "Object In mk3 callback"
    bl_options = {'INTERNAL'}

    fn_name: StringProperty(default='')
    node_name: StringProperty(default='')
    tree_name: StringProperty(default='')

    def execute(self, context):
        """
        returns the operator's 'self' too to allow the code being called to
        print from self.report.
        """
        if self.tree_name and self.node_name:
            ng = bpy.data.node_groups[self.tree_name]
            node = ng.nodes[self.node_name]
        else:
            node = context.node

        getattr(node, self.fn_name)(self)
        return {'FINISHED'}



class SvObjectsNodeMK3(bpy.types.Node, SverchCustomTreeNode, SvAnimatableNode):
    """
    Triggers: Input Scene Objects
    Tooltip: Get Scene Objects into Sverchok Tree
    """
    bl_idname = 'SvObjectsNodeMK3'
    bl_label = 'Objects in'
    bl_icon = 'OUTLINER_OB_EMPTY'
    sv_icon = 'SV_OBJECTS_IN'

    def hide_show_versgroups(self, context):
        outs = self.outputs
        showing_vg = 'Vers_grouped' in outs

        if self.vergroups and not showing_vg:
            outs.new('SvStringsSocket', 'Vers_grouped')
        elif not self.vergroups and showing_vg:
            outs.remove(outs['Vers_grouped'])

    def modifiers_handle(self, context):
        set_sv_depsgraph_need(self.modifiers)
        updateNode(self, context)

    groupname: StringProperty(
        name='groupname', description='group of objects (green outline CTRL+G)',
        default='', update=updateNode)

    modifiers: BoolProperty(
        name='Modifiers',
        description='Apply modifier geometry to import (original untouched)',
        default=False, update=modifiers_handle)

    vergroups: BoolProperty(
        name='Vergroups',
        description='Use vertex groups to nesty insertion',
        default=False, update=hide_show_versgroups)

    sort: BoolProperty(
        name='sort by name',
        description='sorting inserted objects by names',
        default=True, update=updateNode)

    object_names: bpy.props.CollectionProperty(type=bpy.types.PropertyGroup)
    to3d: BoolProperty(
        default=False, 
        description="Show in Sverchok control panel",
        update=updateNode)


    def sv_init(self, context):
        new = self.outputs.new
        new('SvVerticesSocket', "Vertices")
        new('SvStringsSocket', "Edges")
        new('SvStringsSocket', "Polygons")
        new('SvStringsSocket', "MaterialIdx")
        new('SvMatrixSocket', "Matrixes")
        new('SvObjectSocket', "Object")


    def get_objects_from_scene(self, ops):
        """
        Collect selected objects
        """
        self.object_names.clear()

        if self.groupname and groups[self.groupname].objects:
            groups = bpy.data.groups
            names = [obj.name for obj in groups[self.groupname].objects]
        else:
            names = [obj.name for obj in bpy.data.objects if (obj.select_get() and len(obj.users_scene) > 0 and len(obj.users_collection) > 0)]

        if self.sort:
            names.sort()

        for name in names:
            self.object_names.add().name = name

        if not self.object_names:
            ops.report({'WARNING'}, "Warning, no selected objects in the scene")
            return

        self.process_node(None)


    def select_objs(self, ops):
        """select all objects referenced by node"""
        for item in self.object_names:
            bpy.data.objects[item.name].select = True

        if not self.object_names:
            ops.report({'WARNING'}, "Warning, no object associated with the obj in Node")


    def draw_obj_names(self, layout):
        # display names currently being tracked, stop at the first 5..
        if self.object_names:
            remain = len(self.object_names) - 5

            for i, obj_ref in enumerate(self.object_names):
                layout.label(text=obj_ref.name)
                if i > 4 and remain > 0:
                    postfix = ('' if remain == 1 else 's')
                    more_items = '... {0} more item' + postfix
                    layout.label(text=more_items.format(remain))
                    break
        else:
            layout.label(text='--None--')

    def draw_buttons(self, context, layout):
        self.draw_animatable_buttons(layout, icon_only=True)
        col = layout.column(align=True)
        row = col.row()
        op_text = "Get selection"  # fallback

        try:
            addon = context.preferences.addons.get(sverchok.__name__)
            if addon.preferences.over_sized_buttons:
                row.scale_y = 4.0
                op_text = "G E T"
        except:
            pass

        callback = 'node.ob3_callback'
        row.operator(callback, text=op_text).fn_name = 'get_objects_from_scene'

        col = layout.column(align=True)
        row = col.row(align=True)
        row.prop(self, 'sort', text='Sort', toggle=True)
        row.prop(self, "modifiers", text="Post", toggle=True)
        row.prop(self, "vergroups", text="VeGr", toggle=True)

        #  i don't even know what this is supposed to do.... not useful enough i think..
        #  row = col.row(align=True)
        #  row.operator(callback, text="Select Objects").fn_name = 'select_objs'

        self.draw_obj_names(layout)

    def draw_buttons_ext(self, context, layout):
        layout.prop(self, 'to3d', text="To Control panel")
        self.draw_animatable_buttons(layout)

    @property
    def draw_3dpanel(self):
        return True if self.to3d and any((s.is_linked for s in self.outputs)) else False

    def draw_buttons_3dpanel(self, layout):
        callback = 'node.ob3_callback'
        row = layout.row(align=True)
        row.label(text=self.label if self.label else self.name)
        colo = row.row(align=True)
        colo.scale_x = 1.6
        op = colo.operator(callback, text="Get")
        op.fn_name = 'get_objects_from_scene'
        op.tree_name = self.id_data.name
        op.node_name = self.name


    def get_verts_and_vertgroups(self, obj_data):
        vers = []
        vers_grouped = []
        for k, v in enumerate(obj_data.vertices):
            if self.vergroups and v.groups.values():
                vers_grouped.append(k)
            vers.append(list(v.co))
        return vers, vers_grouped

    def get_materials_from_bmesh(self, bm):
        return [face.material_index for face in bm.faces[:]]

    def get_materials_from_mesh(self, mesh):
        return [face.material_index for face in mesh.polygons[:]]

    def sv_free(self):
        set_sv_depsgraph_need(False)

    def process(self):

        if not self.object_names:
            return

        scene = bpy.context.scene
        data_objects = bpy.data.objects
        outputs = self.outputs


        edgs_out = []
        vers_out = []
        vers_out_grouped = []
        pols_out = []
        mtrx_out = []
        materials_out = []

        if self.modifiers:
            sv_depsgraph = get_sv_depsgraph()

        # iterate through references
        for obj in (data_objects.get(o.name) for o in self.object_names):

            if not obj:
                continue

            edgs = []
            vers = []
            vers_grouped = []
            pols = []
            mtrx = []
            materials = []

            with self.sv_throttle_tree_update():

                mtrx = obj.matrix_world
                if obj.type in {'EMPTY', 'CAMERA', 'LAMP' }:
                    mtrx_out.append(mtrx)
                    continue
                try:
                    if obj.mode == 'EDIT' and obj.type == 'MESH':
                        # Mesh objects do not currently return what you see
                        # from 3dview while in edit mode when using obj.to_mesh.
                        me = obj.data
                        bm = bmesh.from_edit_mesh(me)
                        vers, edgs, pols = pydata_from_bmesh(bm)
                        materials = self.get_materials_from_bmesh(bm)
                        del bm
                    else:

                        """
                        this is where the magic happens.
                        because we are in throttled tree update state at this point, we can aquire a depsgraph if
                        - modifiers
                        - or vertex groups are desired

                        """

                        if self.modifiers:

                            obj = sv_depsgraph.objects[obj.name]
                            obj_data = obj.to_mesh(preserve_all_data_layers=True, depsgraph=sv_depsgraph)
                        else:
                            obj_data = obj.to_mesh()

                        if obj_data.polygons:
                            pols = [list(p.vertices) for p in obj_data.polygons]
                        vers, vers_grouped = self.get_verts_and_vertgroups(obj_data)
                        materials = self.get_materials_from_mesh(obj_data)
                        edgs = obj_data.edge_keys

                        obj.to_mesh_clear()


                except Exception as err:
                    print('failure in process between frozen area', self.name, err)

            vers_out.append(vers)
            edgs_out.append(edgs)
            pols_out.append(pols)
            mtrx_out.append(mtrx)
            materials_out.append(materials)
            vers_out_grouped.append(vers_grouped)

        if vers_out and vers_out[0]:
            outputs['Vertices'].sv_set(vers_out)
            outputs['Edges'].sv_set(edgs_out)
            outputs['Polygons'].sv_set(pols_out)
            if 'MaterialIdx' in outputs:
                outputs['MaterialIdx'].sv_set(materials_out)

            if 'Vers_grouped' in outputs and self.vergroups:
                outputs['Vers_grouped'].sv_set(vers_out_grouped)

        outputs['Matrixes'].sv_set(mtrx_out)
        outputs['Object'].sv_set([data_objects.get(o.name) for o in self.object_names])


    def storage_get_data(self, node_dict):
        node_dict['object_names'] = [o.name for o in self.object_names]


classes = [SvOB3Callback, SvObjectsNodeMK3]


def register():
    _ = [bpy.utils.register_class(c) for c in classes]


def unregister():
    _ = [bpy.utils.unregister_class(c) for c in classes]
