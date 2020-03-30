# This file is part of project Sverchok. It's copyrighted by the contributors
# recorded in the version control history of the file, available from
# its original location https://github.com/nortikin/sverchok/commit/master
#  
# SPDX-License-Identifier: GPL3
# License-Filename: LICENSE



def recursive_framed_location_finder(node, loc_xy):
    locx, locy = loc_xy
    if node.parent:
        locx += node.parent.location.x
        locy += node.parent.location.y
        return recursive_framed_location_finder(node.parent, (locx, locy))
    else:
        return locx, locy


def frame_adjust(caller_node, new_node):
    if caller_node.parent:
        new_node.parent = caller_node.parent
        loc_xy = new_node.location[:]
        locx, locy = recursive_framed_location_finder(new_node, loc_xy)
        new_node.location = locx, locy

def absolute_location_generic(node):
    """
    all nodes of type Sverchok Custom will have the absolute_location attribute,
    but some nodes (at the moment only ReRoute) are "part of the pynodes API" and can not
    be augmented, so this function will return the appropriate location for all nodes
    """
    if hasattr(node, 'absolute_location'):
        return node.absolute_location
    return recursive_framed_location_finder(node, node.location[:])


def scaled_dpi():
    """
    find the xy position for the blf content, adjusted for screen res.
    """
    ps = bpy.context.preferences.system
    return ps.dpi * ps.pixel_size / 72
