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

import os
import numpy as np
import bgl
import bpy
from bpy.props import (
    FloatProperty, EnumProperty, StringProperty, BoolProperty, IntProperty
)
from sverchok.data_structure import updateNode, node_id
from sverchok.node_tree import SverchCustomTreeNode
from sverchok.ui import nodeview_bgl_viewer_draw_mk2 as nvBGL2
from sverchok.ui import sv_image as svIMG
from sverchok.utils.sv_operator_mixins import (
    SvGenericDirectorySelector, SvGenericCallbackWithParams
)


class SvTextureViewerOperator(bpy.types.Operator, SvGenericCallbackWithParams):
    """ Save the image with passed settings """
    bl_idname = "node.sv_texview_callback"
    bl_label = "Execute a function on the calling node"


gl_color_list = [
    ('BW', 'bw', 'grayscale texture', '', 0),
    ('RGB', 'rgb', 'rgb colored texture', '', 1),
    ('RGBA', 'rgba', 'rgba colored texture', '', 2)
]

gl_color_dict = {
    'BW': 6409,  # GL_LUMINANCE
    'RGB': 6407,  # GL_RGB
    'RGBA': 6408  # GL_RGBA
}

factor_buffer_dict = {
    'BW': 1,  # GL_LUMINANCE
    'RGB': 3,  # GL_RGB
    'RGBA': 4  # GL_RGBA
}


def init_texture(width, height, texname, texture, clr):
    # function to init the texture
    bgl.glPixelStorei(bgl.GL_UNPACK_ALIGNMENT, 1)
    bgl.glEnable(bgl.GL_TEXTURE_2D)
    bgl.glBindTexture(bgl.GL_TEXTURE_2D, texname)
    bgl.glActiveTexture(bgl.GL_TEXTURE0)
    bgl.glTexParameterf(bgl.GL_TEXTURE_2D, bgl.GL_TEXTURE_WRAP_S, bgl.GL_CLAMP)
    bgl.glTexParameterf(bgl.GL_TEXTURE_2D, bgl.GL_TEXTURE_WRAP_T, bgl.GL_CLAMP)
    bgl.glTexParameterf(bgl.GL_TEXTURE_2D, bgl.GL_TEXTURE_MAG_FILTER, bgl.GL_LINEAR)
    bgl.glTexParameterf(bgl.GL_TEXTURE_2D, bgl.GL_TEXTURE_MIN_FILTER, bgl.GL_LINEAR)
    bgl.glTexImage2D(
        bgl.GL_TEXTURE_2D,
        0, clr, width, height,
        0, clr, bgl.GL_FLOAT, texture
    )


def simple_screen(x, y, args):
    # draw a simple scren display for the texture
    texture, texname, width, height = args

    def draw_texture(x=0, y=0, w=30, h=10, texname=texname):
        # function to draw a texture
        bgl.glDisable(bgl.GL_DEPTH_TEST)
        act_tex = bgl.Buffer(bgl.GL_INT, 1)
        bgl.glGetIntegerv(bgl.GL_TEXTURE_2D, act_tex)
        bgl.glEnable(bgl.GL_TEXTURE_2D)
        bgl.glActiveTexture(bgl.GL_TEXTURE0)
        bgl.glTexEnvf(bgl.GL_TEXTURE_ENV, bgl.GL_TEXTURE_ENV_MODE, bgl.GL_REPLACE)
        bgl.glBindTexture(bgl.GL_TEXTURE_2D, texname)
        texco = [(0, 1), (1, 1), (1, 0), (0, 0)]
        verco = [(x, y), (x + w, y), (x + w, y - h), (x, y - h)]
        bgl.glPolygonMode(bgl.GL_FRONT_AND_BACK, bgl.GL_FILL)
        bgl.glBegin(bgl.GL_QUADS)
        for i in range(4):
            bgl.glTexCoord3f(texco[i][0], texco[i][1], 0.0)
            bgl.glVertex2f(verco[i][0], verco[i][1])
        bgl.glEnd()
        # restoring settings
        bgl.glBindTexture(bgl.GL_TEXTURE_2D, act_tex[0])
        bgl.glDisable(bgl.GL_TEXTURE_2D)
    draw_texture(x=x, y=y, w=width, h=height, texname=texname)


class SvTextureViewerNode(bpy.types.Node, SverchCustomTreeNode):
    '''Texture Viewer node'''
    bl_idname = 'SvTextureViewerNode'
    bl_label = 'Texture viewer'
    texture = {}

    n_id = StringProperty(default='')

    activate = BoolProperty(
        name='Show', description='Activate texture drawing',
        default=True, update=updateNode)

    width_custom_tex = IntProperty(
        min=0, max=1024, default=206, name='Width Tex',
        description="set the custom texture size", update=updateNode)

    height_custom_tex = IntProperty(
        min=0, max=1024, default=124, name='Height Tex',
        description="set the custom texture size", update=updateNode)

    color_mode = EnumProperty(
        items=gl_color_list, description="Offers color options",
        default="BW", update=updateNode)

    in_float = FloatProperty(
        min=0.0, max=1.0, default=0.0, name='Float Input',
        description='Input for texture', update=updateNode)

    def draw_buttons(self, context, layout):
        row = layout.row()
        row.prop(self, 'activate')
        row = layout.row(align=True)
        row.prop(self, 'color_mode', expand=True)
        row = layout.row(align=True)
        row.prop(self, 'width_custom_tex')
        row.prop(self, 'height_custom_tex')

    def sv_init(self, context):
        self.width = 180
        self.inputs.new('StringsSocket', "Float").prop_name = 'in_float'

    def delete_texture(self):
        n_id = node_id(self)
        if n_id in self.texture:
            names = bgl.Buffer(bgl.GL_INT, 1, [self.texture[n_id]])
            bgl.glDeleteTextures(1, names)

    def process(self):
        n_id = node_id(self)
        self.delete_texture()
        nvBGL2.callback_disable(n_id)
        if not (self.inputs['Float'].is_linked and self.activate):
            return
        width, height, colm = self.width_custom_tex, self.height_custom_tex, self.color_mode
        data = np.array(self.inputs['Float'].sv_get(deepcopy=False)).flatten()
        total_size = (width * height) * factor_buffer_dict.get(colm)
        texture = bgl.Buffer(bgl.GL_FLOAT, total_size, np.resize(data, total_size))
        name = bgl.Buffer(bgl.GL_INT, 1)
        bgl.glGenTextures(1, name)
        self.texture[n_id] = name[0]
        init_texture(width, height, name[0], texture, gl_color_dict.get(colm))
        draw_data = {
            'tree_name': self.id_data.name[:],
            'mode': 'custom_function',
            'custom_function': simple_screen,
            'loc': (self.location[0] + 80, self.location[1]),
            'args': (texture, self.texture[n_id], width, height)
        }
        nvBGL2.callback_enable(n_id, draw_data)

    def free(self):
        nvBGL2.callback_disable(node_id(self))
        self.delete_texture()
    # reset n_id on copy

    def copy(self, node):
        self.n_id = ''


def register():
    bpy.utils.register_class(SvTextureViewerOperator)
    bpy.utils.register_class(SvTextureViewerNode)


def unregister():
    bpy.utils.unregister_class(SvTextureViewerNode)
    bpy.utils.unregister_class(SvTextureViewerOperator)
