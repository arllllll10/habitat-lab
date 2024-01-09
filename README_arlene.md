[20231225]

in ''stable'' branch, it can run siro_sandbox
    
    ```
    HABITAT_SIM_LOG=warning MAGNUM_LOG=warning python examples/siro_sandbox/sandbox_app.py --disable-inverse-kinematics --never-end --gui-controlled-agent-index 1 --app-state rearrange --cfg social_rearrange/pop_play.yaml --cfg-opts habitat.environment.iterator_options.cycle=False habitat_baselines.evaluate=True habitat_baselines.num_environments=1 habitat_baselines.eval.should_load_ckpt=False habitat_baselines.rl.agent.num_pool_agents_per_type='[1,1]' habitat.simulator.habitat_sim_v0.allow_sliding=False
    ```

''addon_humanoid'' branch cannot run siro_sandbox

in current ''stable'' branch, the cotent of 'habitat-lab/habitat-lab/habitat/articulated_agents/humanoids/README.md' is copied from ''addon_humanoid'' branch



## convert smplx-> urdf: 
../blender-4.0.2-linux-x64/blender -b -P scripts/export_smplx_bodies_fixed.py


## human config: 
    habitact-lab/habitat/config/habitat/simulator/agents/human.yaml



## data assets 
    e.g. data/humanoids/humanoid_data/female_2/
    [name].urdf (converted from .fbx )
    [name].ao_config.json
    [name].glb (converted from smplx )
    [name].fbx  (converted from smplx )
    [name]_motion_data_smplx.pkl > (converted by habitat-lab/habitat/utils/humanoid_utils.py)

## load glb:
in test/test_humanoid.py:
    ```
    humanoid_path = f"data/humanoids/humanoid_data/{humanoid_name}/{humanoid_name}.urdf"
    walk_pose_path = f"data/humanoids/humanoid_data/{humanoid_name}/{humanoid_name}_motion_data_smplx.pkl"

    agent_config = {"articulated_agent_urdf": humanoid_path,
                    "motion_data_path": walk_pose_path,}
    kin_humanoid = kinematic_humanoid.KinematicHumanoid(agent_config, sim)
    kin_humanoid.reconfigure()
    ```

    --> habitat.articulated_agents.humanoids.kinematic_humanoid 
    --> habitat.articulated_agents.mobile_manipulator.MobileManipulator
    --> habitat.articulated_agents.manipulator.Manipulator ( habitat-lab/habitat/articulated_agents/manipulator.py)
    --> reconfigure()
        -> ```
            self.sim_obj = ao_mgr.add_articulated_object_from_urdf(
                self.urdf_path,
                fixed_base=self._fixed_base,
                maintain_link_order=self._maintain_link_order,
            )
            ```


for now, 'data/humanoids/humanoid_data/avatar_0/avatar_0_motion_data_smplx.pkl' is a copied version of 'data/humanoids/humanoid_data/female_2/female_2_motion_data_smplx.pkl'.
if we use 'habitat/utils/humanoid_utils.py' to generate .pkl file, it won't work in 'python -m pytest -s test/test_humanoid.py::test_humanoid_controller'

-> now, it works as show in 'test_humanoid_wrapper_avatar_0.mp4', but the converted urdf file (from smplx) is without texture

-> but it is for sure that we can convert from  smplx to urdf and then load into habitat



20240108

HABITAT_SIM_LOG=warning MAGNUM_LOG=warning \
python examples/siro_sandbox/sandbox_app.py \
--app-state fetch \
--disable-inverse-kinematics \
--never-end \
--gui-controlled-agent-index 1 \
--cfg experiments_hab3/pop_play_kinematic_llnav_humanoid_spot.yaml \
--cfg-opts \
habitat.task.actions.agent_0_oracle_nav_action.type=OracleNavCoordAction \
habitat.task.actions.agent_0_arm_action.disable_grip=False \
habitat_baselines.evaluate=True \
habitat_baselines.num_environments=1 \
habitat.simulator.step_physics=True \
habitat_baselines.eval.should_load_ckpt=False \
habitat.task.measurements.cooperate_subgoal_reward.end_on_collide=False
