"""Select an environment without teaching runners about physics engines."""


def create_environment(
    *,
    backend="mujoco",
    robot=None,
    scene="tabletop_a",
    task="pick_place",
    libero_suite="libero_spatial",
    libero_task_id=0,
    init_state_id=0,
    render=True,
    libero_python=None,
    libero_root=None,
    observation_profile="debug_rgb128",
    robocasa_layout=11,
    robocasa_style=14,
):
    if backend == "mujoco":
        from maniloop.simulation.environment import RobotSim

        return RobotSim(render=render, robot=robot or "arx5", scene=scene, task=task)
    if backend == "libero":
        if robot not in (None, "panda"):
            raise ValueError(
                "Official LIBERO integration uses Panda; changing embodiment is a separate benchmark variant"
            )
        from .libero import LiberoEnvironment

        return LiberoEnvironment(
            suite=libero_suite,
            task_id=libero_task_id,
            init_state_id=init_state_id,
            render=render,
            python=libero_python,
            root=libero_root,
            observation_profile=observation_profile,
        )
    if backend == "robosuite":
        if robot not in (None, "panda"):
            raise ValueError("Initial robosuite integration supports Panda only")
        from .robosuite import RobosuiteEnvironment
        return RobosuiteEnvironment(task=task, render=render,
                                   observation_profile=observation_profile)
    if backend == "robocasa":
        if robot not in (None, "panda_omron"):
            raise ValueError("RoboCasa integration requires PandaOmron, not the fixed-base Panda")
        from .robocasa import RobocasaEnvironment
        return RobocasaEnvironment(task=task, render=render,
            observation_profile=observation_profile, layout=robocasa_layout, style=robocasa_style)
    raise ValueError("Unknown environment backend")


def options_from_args(args):
    keys = (
        "backend",
        "robot",
        "scene",
        "task",
        "libero_suite",
        "libero_task_id",
        "init_state_id",
        "observation_profile",
        "robocasa_layout",
        "robocasa_style",
    )
    return {key: getattr(args, key) for key in keys if hasattr(args, key)}
