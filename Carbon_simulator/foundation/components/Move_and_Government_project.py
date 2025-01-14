import numpy as np
from numpy.random import rand

from Carbon_simulator.foundation.base.base_component import (
    BaseComponent,
    component_registry,
)


@component_registry.add
class Gather(BaseComponent):

    name = "Gather"
    required_entities = ["Carbon_idx", "Carbon_emission", "Coin", "Green_project", "Labor"]
    agent_subclasses = ["BasicMobileAgent"]

    def __init__(
        self,
        *base_component_args,
        move_labor=1.0,
        collect_labor=30,
        collect_cost_coin=10,
        collect_idx=1,
        **base_component_kwargs
    ):
        super().__init__(*base_component_args, **base_component_kwargs)

        self.move_labor = float(move_labor)
        assert self.move_labor >= 0

        self.collect_labor = float(collect_labor)
        assert self.collect_labor >= 0

        self.collect_cost_coin = float(collect_cost_coin)
        assert self.collect_cost_coin >= 0

        self.collect_idx = float(collect_idx)
        assert self.collect_idx >= 0

        self.gathers = []

        self._aidx = np.arange(self.n_agents)[:, None].repeat(4, axis=1)
        self._roff = np.array([[0, 0, -1, 1]])
        self._coff = np.array([[-1, 1, 0, 0]])

    # Required methods for implementing components
    # --------------------------------------------

    def get_n_actions(self, agent_cls_name):
        """
        See base_component.py for detailed description.

        Adds 4 actions (move up, down, left, or right) for mobile agents.
        """
        # This component adds 4 action that agents can take:
        # move up, down, left, or right
        if agent_cls_name == "BasicMobileAgent":
            return 4
        return None

    def get_additional_state_fields(self, agent_cls_name):
        """
        See base_component.py for detailed description.

        For mobile agents, add state field for collection skill.
        """
        if agent_cls_name not in self.agent_subclasses:
            return {}
        if agent_cls_name == "BasicMobileAgent":
            return {}
        raise NotImplementedError

    def component_step(self):
        """
        See base_component.py for detailed description.

        Move to adjacent, unoccupied locations. Collect resources when moving to
        populated resource tiles, adding the resource to the agent's inventory and
        de-populating it from the tile.
        """
        world = self.world
        gathers = []
        if self.world.timestep % self.period != 1:
            for agent in world.get_random_order_agents():

                action = agent.get_component_action(self.name)

                r, c = [int(x) for x in agent.loc]

                if action is None:
                    continue

                if action == 0:  # NO-OP!
                    new_r, new_c = r, c

                elif action <= 4:
                    if action == 1:  # Left
                        new_r, new_c = r, c - 1
                    elif action == 2:  # Right
                        new_r, new_c = r, c + 1
                    elif action == 3:  # Up
                        new_r, new_c = r - 1, c
                    else:  # action == 4, # Down
                        new_r, new_c = r + 1, c

                    # Attempt to move the agent (if the new coordinates aren't accessible,
                    # nothing will happen)
                    for resource, health in world.location_resources(new_r, new_c).items():
                        if resource == "Carbon_project" and health >= 1:
                            if agent.state["inventory"]["Coin"]>self.collect_cost_coin:
                                agent.state["inventory"][resource] += world.location_resources(new_r, new_c)[resource]

                                world.consume_resource(resource, new_r, new_c)

                                world.create_landmark("Green_project", new_r, new_c, agent.idx)
                                agent.state["inventory"]["Carbon_idx"] += self.collect_idx

                                # Incur the labor cost of collecting a resource
                                agent.state["endogenous"]["Labor"] += self.collect_labor

                                agent.state["inventory"]["Coin"] -= self.collect_cost_coin
                                # Log the gather
                                gathers.append(
                                    dict(
                                        agent=agent.idx,
                                        resource=resource,
                                        loc=[new_r, new_c],
                                    )
                                )
                            else:
                                new_r, new_c = r, c


                    new_r, new_c = world.set_agent_loc(agent, new_r, new_c)

                    # If the agent did move, incur the labor cost of moving
                    if (new_r != r) or (new_c != c):
                        agent.state["endogenous"]["Labor"] += self.move_labor

                else:
                    raise ValueError



        self.gathers.append(gathers)

    def generate_observations(self):
        """
        See base_component.py for detailed description.

        Here, agents observe their collection skill. The planner does not observe
        anything from this component.
        """
        return {}

    def generate_masks(self, completions=0):
        """
        See base_component.py for detailed description.

        Prevent moving to adjacent tiles that are already occupied (or outside the
        boundaries of the world)
        """
        world = self.world

        coords = np.array([agent.loc for agent in world.agents])[:, :, None]
        ris = coords[:, 0] + self._roff + 1
        cis = coords[:, 1] + self._coff + 1

        occ = np.pad(world.maps.unoccupied, ((1, 1), (1, 1)))
        acc = np.pad(world.maps.accessibility, ((0, 0), (1, 1), (1, 1)))
        mask_array = np.logical_and(occ[ris, cis], acc[self._aidx, ris, cis]).astype(
            np.float32
        )

        masks = {agent.idx: mask_array[i] for i, agent in enumerate(world.agents)}

        return masks

    # For non-required customization
    # ------------------------------

    def additional_reset_steps(self):
        """
        See base_component.py for detailed description.

        Re-sample agents' collection skills.
        """

        self.gathers = []

    def get_dense_log(self):
        """
        Log resource collections.

        Returns:
            gathers (list): A list of gather events. Each entry corresponds to a single
                timestep and contains a description of any resource gathers that
                occurred on that timestep.

        """
        return self.gathers
