# SPDX-FileCopyrightText: Copyright (c) 2024 Tod Kurt
# SPDX-License-Identifier: MIT
"""
`patch_saver`
================================================================================

Patch persistence (saving and loading) tools to and from JSON.

Part of synth_tools.

"""

import json
import time

from synth_tools.patch import Patch

patches_save_fname = "/saved_patches.json"

last_write_time = time.monotonic()


def to_dict(obj):
    """
    Turn an object into a dict, if it can, including subobjects.
    """
    props = set(dir(obj)) - set(dir(obj.__class__))  # list of obj properties
    d = {}  # dict to hold props
    for p in props:
        d[p] = getattr(obj,p)
        if d[p] is None:  # deal with unset properties
            pass
        elif not isinstance(d[p], (float,int,str)):
            d[p] = to_dict(d[p])  # go deeper
    return d

def from_dict(d,cls):
    """
    Take a dict and class and create an object and fill out its props
    using dict keys as prop names and values as prop values.
    Class must have a zero-argument constructor
    """
    obj = cls()
    for propname in d:
        attr = getattr(obj,propname)   # obj attribute w/ name in p
        if attr is None:
            pass
        elif isinstance(attr, (float,int,str)):
            setattr(obj, propname, d[propname])  # can set directly if simple type
        else:
            # otherwise object, so get class of that obj
            childcls = getattr(attr,'__class__')
            setattr(obj, propname, from_dict(d[propname], childcls))  # go deeper
    return obj


def copy(obj):
    """Copy an object, by passing it through dict space"""
    return from_dict(to_dict(obj), obj.__class__)


def to_json(obj):
    """
    Turn an object or list of objects into JSON. 
    """
    if type(obj) is list:  # list of objects
        o = [to_dict(e) for e in obj]  # turn list of objs into list of dicts
    else:
        o = to_dict(obj)
    return json.dumps(o)

def from_json(json_str, cls):
    """
    Turn a JSON string representing an object or list of objects of class
    type `cls` and turn them into Python objects.
    The `cls` class must have a zero-argument constructor.
    """
    d = json.loads(json_str)
    if type(d) is list:
        return [from_dict(e,cls) for e in d]
    else:
        return from_dict(d, cls)


def load_patches(fname=patches_save_fname):
    """Read entire patch set from disk into RAM"""
    print("load_patches: loading...")
    try:
        with open(fname, 'r') as fp:
            patches_json_str = fp.read()
            #print("load_patches: patches_json_str:\n", patches_json_str)
            patches = from_json(patches_json_str, Patch)
            print("load_patches: done")
            return patches
    except Exception as e:
        print("load_patches: could not load", fname, "error:",e)
    return None  # if badness

def save_patches(patches, fname=patches_save_fname):
    """Write entire patch set from RAM to disk"""
    global last_write_time
    print("save_patches: saving...")
    # only allow writes every 10 seconds, to save flash
    if time.monotonic() - last_write_time < 10: 
        print("save_patches: too soon, try later")
        return
    last_write_time = time.monotonic()

    patches_json_str = to_json(patches)
    #print("save_patches: patches_json_str:\n",patches_json_str)
    try:
        with open(fname, 'w') as fp:
            fp.write(patches_json_str)
            
    except Exception:
        print("could not save patches, no boot.py?")
    print("save_patches: done")
        


def test():
    patch = Patch()
    json_str = to_json(patch)
    print("json:", json_str)
    pnew = from_json(json_str, Patch)
    print("json2:", to_json(pnew))
    
    json_str = to_json(patches)
    print("json patches:", json_str)
    patches_new = from_json(json_str, Patch)
    print("json patches:", to_json(patches_new))
    
