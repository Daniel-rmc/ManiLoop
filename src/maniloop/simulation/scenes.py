"""Compose reusable scene/object assets with an embodiment and task layout."""

import copy
import xml.etree.ElementTree as ET
import numpy as np
from maniloop.robots.specs import RobotSpec, ASSETS
from maniloop.tasks.tabletop import TabletopLayout


def scene_xml(robot: RobotSpec, layout: TabletopLayout) -> str:
    template = ET.parse(ASSETS.parent / "scenes/tabletop.xml").getroot()
    model = ET.parse(robot.model_path).getroot()
    world = template.find("worldbody")
    # Common object/fixture contact parameters remain the same across embodiments.
    for default in model.find("default"):
        if default.tag != "geom":
            template.find("default").append(copy.deepcopy(default))
    for tag in ("actuator", "contact", "equality", "tendon"):
        part = model.find(tag)
        if part is not None:
            template.append(copy.deepcopy(part))
    meshdir = model.find("compiler").get("meshdir", "")
    for original in model.find("asset"):
        if original.tag == "texture":
            continue
        item = copy.deepcopy(original)
        if item.tag == "mesh":
            item.set("file", str(robot.model_path.parent / meshdir / item.get("file")))
        template.find("asset").append(item)
    body = copy.deepcopy(
        model.find(f"worldbody/body[@name='{robot.config['base_body']}']")
    )
    if robot.name == "panda":
        for part in body.iter("body"):
            part.set("gravcomp", "1")
        hand = body.find(".//body[@name='hand']")
        ET.SubElement(hand, "site", name="tcp", pos="0 0 .1034", size=".003", group="4")
        ET.SubElement(
            hand,
            "camera",
            name="wrist",
            pos=".05 0 .03",
            xyaxes="1 0 0 0 -1 0",
            fovy="72",
        )
        camera = world.find("camera[@name='external']")
        position = np.array([1.05, -0.95, 0.92])
        z_axis = position - np.array([0.22, 0.0, 0.24])
        z_axis /= np.linalg.norm(z_axis)
        x_axis = np.cross([0.0, 0.0, 1.0], z_axis)
        x_axis /= np.linalg.norm(x_axis)
        y_axis = np.cross(z_axis, x_axis)
        camera.set("pos", " ".join(map(str, position)))
        camera.set("xyaxes", " ".join(map(str, np.r_[x_axis, y_axis])))
    world.insert(0, body)
    obj = ET.parse(ASSETS.parent / "objects/red_cube.xml").getroot()
    obj.set("pos", " ".join(map(str, layout.object_position)))
    world.append(obj)
    world.find("geom[@name='target_region']").set(
        "pos", f"{layout.target_position[0]} {layout.target_position[1]} .00025"
    )
    world.find("site[@name='target_center']").set(
        "pos", f"{layout.target_position[0]} {layout.target_position[1]} .001"
    )
    return ET.tostring(template, encoding="unicode")
